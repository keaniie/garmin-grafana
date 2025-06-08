import os
import argparse
from datetime import datetime, timedelta
import pytz
from garminconnect import Garmin
import xml.etree.ElementTree as ET
import math

# ------------------------------------------------------------------
# Automated VO2max Calculation, Race Predictions & Load Focus
# ------------------------------------------------------------------

def calculate_vo2max_ratio(stats):
    """
    Estimate VO2max via Uth heart-rate ratio method: 15.3 * (HRmax/HRrest)
    """
    rhr = stats.get('restingHeartRate')
    maxhr = stats.get('maxHeartRate')
    if rhr and maxhr and maxhr > rhr:
        return 15.3 * (maxhr / rhr)
    return None


def calculate_vo2max_segmented(garmin_obj, date_str):
    """
    Segment-based VO2max estimation:
      • Download TCX for all runs on date
      • extract HR and speed points
      • collect ≥10-min segments at ≥70% HRmax
      • regress ACSM VO2 (0.2*v*60+3.5) vs HR
      • predict VO2max from slope*HRmax+intercept
    """
    # fetch stats
    stats = garmin_obj.get_stats(date_str)
    rhr = stats.get('restingHeartRate')
    maxhr = stats.get('maxHeartRate')
    if not rhr or not maxhr or maxhr <= rhr:
        return None
    # gather track data
    track = []
    activities = garmin_obj.get_activities_by_date(date_str, date_str)
    for a in activities:
        if not a.get('hasPolyline'):
            continue
        tcx = garmin_obj.download_activity(a['activityId'], dl_fmt=garmin_obj.ActivityDownloadFormat.TCX).decode('utf-8')
        root = ET.fromstring(tcx)
        ns = {'tcx':'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2',
              'ns3':'http://www.garmin.com/xmlschemas/ActivityExtension/v2'}
        for tp in root.findall('.//tcx:Trackpoint', ns):
            hr = tp.findtext('tcx:HeartRateBpm/tcx:Value', namespaces=ns)
            sp = tp.findtext('tcx:Extensions/ns3:TPX/ns3:Speed', namespaces=ns)
            t = tp.findtext('tcx:Time', namespaces=ns)
            if hr and sp and t:
                track.append((datetime.fromisoformat(t.replace('Z','')).timestamp(), float(hr), float(sp)))
    # segment at ≥70% HRmax for ≥600s
    hr_thr = rhr + 0.7 * (maxhr - rhr)
    segments = []
    seg = []
    for t, hr, sp in track:
        if hr >= hr_thr:
            seg.append((hr, sp))
        else:
            if len(seg) >= 600:
                segments.append(seg)
            seg = []
    if len(seg) >= 600:
        segments.append(seg)
    # if no segments, fallback to ratio
    if not segments:
        return calculate_vo2max_ratio(stats)
    # linear regression X=HR, Y=VO2_inst
    X=[]; Y=[]
    for seg in segments:
        for hr, sp in seg:
            vo2_inst = 0.2 * (sp*60) + 3.5
            X.append(hr); Y.append(vo2_inst)
    xm = sum(X)/len(X); ym = sum(Y)/len(Y)
    num = sum((xi-xm)*(yi-ym) for xi,yi in zip(X,Y))
    den = sum((xi-xm)**2 for xi in X)
    if den==0: return calculate_vo2max_ratio(stats)
    slope = num/den; intercept = ym - slope*xm
    return slope*maxhr + intercept


def fetch_vo2max(garmin_obj, date_str):
    """
    Try segmented VO2max, else Uth ratio
    """
    vo2_seg = calculate_vo2max_segmented(garmin_obj, date_str)
    if vo2_seg:
        return round(vo2_seg,2)
    stats = garmin_obj.get_stats(date_str)
    vo2_ratio = calculate_vo2max_ratio(stats)
    return round(vo2_ratio,2) if vo2_ratio else None


def predict_race_times_from_vo2(vo2max):
    """
    Predict race times (s) using ACSM equation & %VO2max intensities
    Percents: 5K@95%,10K@90%,Half@85%,Marathon@75%
    """
    targets = {'5K':5000,'10K':10000,'Half Marathon':21097.5,'Marathon':42195}
    perc = {'5K':0.95,'10K':0.90,'Half Marathon':0.85,'Marathon':0.75}
    preds={}
    for race,dist in targets.items():
        vo2_eff = vo2max * perc[race]
        speed = (vo2_eff-3.5)/0.2/60 if vo2_eff>3.5 else 0
        preds[race] = round(dist/speed) if speed>0 else None
    return preds


def calculate_training_load_focus(garmin_obj, end_date_str, days=7):
    """
    Weekly HR-zone focus percentages
    """
    zones=[0]*5
    end=datetime.strptime(end_date_str,'%Y-%m-%d').replace(tzinfo=pytz.UTC)
    for i in range(days):
        d=(end - timedelta(days=i)).strftime('%Y-%m-%d')
        for act in garmin_obj.get_activities_by_date(d,d):
            for z in range(1,6): zones[z-1]+=act.get(f'hrTimeInZone_{z}',0) or 0
    total=sum(zones)
    if total==0: return None
    return {
        'low_aerobic':round((zones[0]+zones[1])/total*100,1),
        'high_aerobic':round((zones[2]+zones[3])/total*100,1),
        'anaerobic':round(zones[4]/total*100,1)
    }


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('-t','--token-dir',default=os.getenv('TOKEN_DIR','~/.garminconnect'))
    p.add_argument('-d','--date',default=datetime.now(pytz.UTC).strftime('%Y-%m-%d'))
    p.add_argument('-n','--days',type=int,default=7)
    return p.parse_args()

if __name__=='__main__':
    args=parse_args()
    garmin=Garmin(); garmin.login(os.path.expanduser(args.token_dir))

    vo2=fetch_vo2max(garmin,args.date)
    print(f"Estimated VO2max on {args.date}: {vo2 if vo2 else 'Unavailable'}")

    print("\nPredicted Race Times:")
    if vo2:
        for race,secs in predict_race_times_from_vo2(vo2).items():
            if secs:
                h,rem=divmod(secs,3600); m,s=divmod(rem,60)
                print(f"  {race}: {h}h{m:02d}m{s:02d}s")
            else: print(f"  {race}: N/A")
    else: print("  Cannot predict races without VO2max.")

    print(f"\nWeekly Training Load Focus ({args.days} days ending {args.date}):")
    focus=calculate_training_load_focus(garmin,args.date,args.days)
    if focus:
        for k,v in focus.items(): print(f"  {k}: {v}%")
    else: print("  No HR-zone data.")
