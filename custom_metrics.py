# %%
import logging
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from statistics import mean, median
import pytz


# %%
def get_training_load(garmin_obj, date_str, start_dt, end_dt):
    """
    Calculate Banister TRIMP for the activity slice between start_dt and end_dt.
    """
    stats = garmin_obj.get_stats(date_str)
    rhr = stats.get("restingHeartRate")
    maxhr = stats.get("maxHeartRate")
    if rhr is None or maxhr is None or maxhr <= rhr:
        logging.debug(f"Skipping TRIMP: invalid RHR/MHR ({rhr}/{maxhr})")
        return 0.0

    hr_vals = garmin_obj.get_heart_rates(date_str).get("heartRateValues") or []
    if len(hr_vals) < 2:
        logging.debug("No intraday HR, skipping TRIMP")
        return 0.0

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    window = [(t, hr) for t, hr in hr_vals if hr is not None and start_ms <= t < end_ms]
    if len(window) < 2:
        return 0.0

    total_trimp = 0.0
    for (t0, hr0), (t1, hr1) in zip(window, window[1:]):
        dt_min = (t1 - t0) / 1000.0 / 60.0
        hr_mid = (hr0 + hr1) / 2.0
        x = (hr_mid - rhr) / (maxhr - rhr)
        if x > 0:
            total_trimp += dt_min * x * math.exp(1.92 * x)

    return total_trimp


# %%
def get_vo2max(garmin_obj, date_str, garmin_device_name):
    """
    Estimate VO2max for a given date using the Heart‐Rate Ratio Method:
      VO2max = 15.3 * (HRmax / HRrest)
    (Uth N. et al., Eur J Appl Physiol 2004) :contentReference[oaicite:0]{index=0}
    """
    points_list = []

    # 1) grab resting & max HR from daily stats
    stats = garmin_obj.get_stats(date_str)
    rhr = stats.get("restingHeartRate")
    maxhr = stats.get("maxHeartRate")
    if rhr is None or maxhr is None or rhr <= 0:
        logging.debug(f"Skipping VO2max for {date_str}: invalid RHR/MHR ({rhr}/{maxhr})")
        return []

    # 2) compute VO2max
    vo2 = 15.3 * (maxhr / rhr)

    # 3) timestamp at UTC midnight
    ts = (
        datetime.strptime(date_str, "%Y-%m-%d")
        .replace(tzinfo=pytz.UTC)
        .isoformat()
    )

    points_list.append({
        "measurement": "VO2Max",
        "time": ts,
        "tags": {"Device": garmin_device_name},
        "fields": {"estimatedVo2Max": round(vo2, 2)}
    })

    logging.info(f"Success : Estimated VO2max={vo2:.2f} ml/kg/min for {date_str}")
    return points_list


# %%
def get_activity_vo2(garmin_obj, date_str, influxdbclient, garmin_device_name):
    """
    Estimate per-activity VO₂ for running and cycling on date_str:
      • Running (flat): VO2 = 0.2 * (speed_m_s*60) + 3.5
      • Cycling (ACSM): VO2 = (1.8 * (power_W*6.12) / weight_kg) + 7
    """
    points = []

    # 1) get a weight for cycling (if any)
    weight = None
    wdata = garmin_obj.get_weigh_ins(date_str, date_str) \
        .get('dailyWeightSummaries', [])
    if wdata:
        for m in wdata[0].get('allWeightMetrics', []):
            if m.get('weight') is not None:
                weight = m['weight']
                break

    # 1b) Fallback: if still no weight, query InfluxDB for last known
    if weight is None:
        # midnight at end of the day
        day_end = (
            datetime.strptime(date_str, "%Y-%m-%d")
            .replace(hour=23, minute=59, second=59, tzinfo=pytz.UTC)
            .isoformat()
        )
        q = influxdbclient.query(
            f"SELECT last(\"weight\") AS w "
            f"FROM \"BodyComposition\" "
            f"WHERE \"Device\" = '{garmin_device_name}' AND time <= '{day_end}'"
        )
        pts = list(q.get_points())
        if pts and pts[0].get("w") is not None:
            weight = pts[0]["w"]


    # 2) fetch all activities for that day
    acts = garmin_obj.get_activities_by_date(date_str, date_str)
    for act in acts:
        typ = act.get("activityType", {}).get("typeKey")
        if typ not in ("running", "cycling", "cycling_road", "cycling_mountain", "cycling_indoor", "indoor_cycling", "virtual_ride"):
            logging.info(f"Skipping VO2 for activity {act.get('activityId')} because type '{type}' is not in list")
            continue

        start = act.get("startTimeGMT")
        if not start:
            logging.debug(f"Skipping VO2 for activity {act.get('activityId')}: no startTime")
            continue

        # timestamp at activity start (UTC)
        t0 = datetime.strptime(start, "%Y-%m-%d %H:%M:%S") \
            .replace(tzinfo=pytz.UTC).isoformat()

        fields = {}
        tags = {
            "Device": garmin_device_name,
            "ActivityID": act.get("activityId"),
            "ActivityType": typ
        }

        if typ == "running":
            avg_sp = act.get("averageSpeed")  # m/s
            max_sp = act.get("maxSpeed")  # m/s

            def vo2_run(s_m_s):
                s_m_min = s_m_s * 60.0
                return 0.2 * s_m_min + 3.5

            if avg_sp:
                fields["vo2_run_avg"] = round(vo2_run(avg_sp), 2)
            if max_sp:
                fields["vo2_run_peak"] = round(vo2_run(max_sp), 2)

        if (typ.startswith("cycling") or typ.startswith("virtual_ride") or typ.startswith("indoor_cycling")) and weight:
            avg_pw = act.get("avgPower") or act.get("averageWatts")
            max_pw = act.get("maxPower") or act.get("maxWatts")
            weight = weight / 1000.0

            def vo2_cyc(watts):
                work_rate = watts * 6.12
                return (1.8 * work_rate / weight) + 7

            if avg_pw:
                fields["vo2_cyc_avg"] = round(vo2_cyc(avg_pw), 2)
            if max_pw:
                fields["vo2_cyc_peak"] = round(vo2_cyc(max_pw), 2)

        if fields:
            points.append({
                "measurement": "ActivityVO2Est",
                "time": t0,
                "tags": tags,
                "fields": fields
            })

    if points:
        logging.info(f"Success : Estimated VO₂ for {len(points)} point(s) on {date_str} with points: {points}")
    return points


# %%
def get_vo2max_segmented(garmin_obj, date_str, garmin_device_name):
    """
    Segment‐based VO2max estimation for running:
      • find ≥10 min segments at ≥70% HRmax
      • compute instant VO2 via ACSM
      • linear‐regress VO2 vs HR → VO2max
      • fallback to Uth HR‐ratio if no good segments
    """
    points = []

    # 1) fetch RHR & HRmax
    stats = garmin_obj.get_stats(date_str)
    rhr = stats.get("restingHeartRate")
    maxhr = stats.get("maxHeartRate")
    if not rhr or not maxhr or maxhr <= rhr:
        logging.debug(f"No valid RHR/MHR on {date_str}, skipping segmented VO2max")
        return []

    # 2) fetch activity summaries and build ID→type map
    acts = garmin_obj.get_activities_by_date(date_str, date_str)
    id_type = {
        a["activityId"]: a.get("activityType", {}).get("typeKey")
        for a in acts if a.get("hasPolyline")
    }
    if not id_type:
        logging.debug(f"No polyline activities on {date_str}, skipping segmented VO2max")
        return []

    # 3) download all TCX GPS+HR points for those activities
    track = []
    ns = {
        "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
        "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2"
    }
    for act_id in id_type:
        try:
            tcx = garmin_obj.download_activity(act_id,
                                               dl_fmt=garmin_obj.ActivityDownloadFormat.TCX
                                               ).decode("utf-8")
        except Exception as e:
            logging.warning(f"Failed GPS download for {act_id}: {e}")
            continue

        root = ET.fromstring(tcx)
        for tp in root.findall(".//tcx:Trackpoint", ns):
            hr = tp.findtext("tcx:HeartRateBpm/tcx:Value", namespaces=ns)
            sp = tp.findtext("tcx:Extensions/ns3:TPX/ns3:Speed", namespaces=ns)
            t = tp.findtext("tcx:Time", namespaces=ns)
            if hr and sp and t:
                track.append((
                    datetime.fromisoformat(t.replace("Z", "")).timestamp(),
                    float(hr), float(sp)
                ))

    if not track:
        logging.debug(f"No valid GPS+HR points on {date_str}, fallback to Uth")
        # fallback to Uth method
        vo2_uth = 15.3 * (maxhr / rhr)
        ts = datetime.strptime(date_str, "%Y-%m-%d") \
            .replace(tzinfo=pytz.UTC).isoformat()
        return [{
            "measurement": "VO2Max",
            "time": ts,
            "tags": {"Device": garmin_device_name},
            "fields": {"estimate": round(vo2_uth, 2)}
        }]

    # 4) segment into ≥10 min chunks at ≥70% HRmax
    hr_thr = rhr + 0.7 * (maxhr - rhr)
    segments = []
    seg = []
    for t, hr, sp in track:
        if hr >= hr_thr:
            seg.append((t, hr, sp))
        else:
            if len(seg) >= 600:  # 10 min in seconds
                segments.append(seg)
            seg = []
    if len(seg) >= 600:
        segments.append(seg)

    # 5) build regression data (HR vs ACSM VO2)
    X = []
    Y = []
    for seg in segments:
        for _, hr, sp in seg:
            vo2_inst = 0.2 * (sp * 60) + 3.5
            X.append(hr)
            Y.append(vo2_inst)

    # 6) regress if possible
    if X:
        xm, ym = mean(X), mean(Y)
        slope = sum((xi - xm) * (yi - ym) for xi, yi in zip(X, Y)) \
                / sum((xi - xm) ** 2 for xi in X)
        intercept = ym - slope * xm
        vo2max = slope * maxhr + intercept
    else:
        vo2max = 15.3 * (maxhr / rhr)  # Uth fallback

    # 7) emit one point at midnight UTC
    ts = datetime.strptime(date_str, "%Y-%m-%d") \
        .replace(tzinfo=pytz.UTC).isoformat()
    points.append({
        "measurement": "VO2Max",
        "time": ts,
        "tags": {"Device": garmin_device_name},
        "fields": {"estimate": round(vo2max, 2)}
    })

    logging.info(f"Segmented VO2max={vo2max:.2f} for {date_str}")
    return points


# %%
def get_training_readiness(garmin_obj, date_str, influxdbclient, garmin_device_name):
    """
    Compute a 0–100 Training Readiness score:
      • Acute Load       (20%)  – today’s TRIMP vs 7‑day ATL
      • HRV Status       (20%)  – last night’s RMSSD
      • Recovery Time    (20%)  – same as Acute Load
      • Sleep Score LN   (15%)  – last night’s sleepScore
      • Sleep History 3N (15%)  – avg sleepScore last 3 nights
      • Stress History 3D(10%) – avg stressPercentage last 3 days
    """
    points = []
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
    end_ts = (day + timedelta(hours=23, minutes=59, seconds=59)).isoformat()

    # 1) TRIMP history → CTL & ATL
    start_ctl = (day - timedelta(days=41)).isoformat()
    res42 = influxdbclient.query(
        f"SELECT last(\"banisterTRIMP\") AS trimp "
        "FROM \"TrainingLoad\" "
        f"WHERE time >= '{start_ctl}' AND time <= '{end_ts}' "
        "GROUP BY time(1d)"
    )
    loads42 = [p["trimp"] for p in res42.get_points() if p.get("trimp") is not None]

    start_atl = (day - timedelta(days=6)).isoformat()
    res7 = influxdbclient.query(
        f"SELECT last(\"banisterTRIMP\") AS trimp "
        "FROM \"TrainingLoad\" "
        f"WHERE time >= '{start_atl}' AND time <= '{end_ts}' "
        "GROUP BY time(1d)"
    )
    loads7 = [p["trimp"] for p in res7.get_points() if p.get("trimp") is not None]

    today_trimp = loads7[-1] if loads7 else 0.0
    ctl = mean(loads42) if loads42 else 0.0
    atl = mean(loads7) if loads7 else 0.0

    logging.debug(f"{date_str}: loads7={loads7}, today_trimp={today_trimp:.1f}, CTL={ctl:.1f}, ATL={atl:.1f}")

    # 2) Acute Load & Recovery (20% each)
    acute_score = 1.0 - min(today_trimp / atl, 1.0) if atl > 0 else 1.0
    recovery_score = acute_score
    logging.debug(f"{date_str}: acute_score={acute_score:.3f}")

    # 3) Sleep & HRV (35% total)
    sleep_res = influxdbclient.query(
        f"SELECT last(\"sleepScore\") AS slp, last(\"avgOvernightHrv\") AS hrv "
        "FROM \"SleepSummary\" "
        f"WHERE time >= '{day.isoformat()}' AND time <= '{end_ts}'"
    ).get_points()
    rec = next(sleep_res, {})
    sleep_last = rec.get("slp", 0.0)
    hrv = rec.get("hrv", 0.0)
    if hrv is None:
        hrv = 0.0

    sleep_score = min(sleep_last / 100.0, 1.0)
    hrv_score = min(hrv / 50.0, 1.0)

    # Sleep history (last 3 nights)
    start_sleep3 = (day - timedelta(days=2)).isoformat()
    s3 = influxdbclient.query(
        f"SELECT last(\"sleepScore\") AS slp "
        "FROM \"SleepSummary\" "
        f"WHERE time >= '{start_sleep3}' AND time <= '{end_ts}' "
        "GROUP BY time(1d)"
    )
    sleeps = [p["slp"] for p in s3.get_points() if p.get("slp") is not None]
    sleep_hist_score = (mean(sleeps) / 100.0) if sleeps else sleep_score

    logging.debug(f"{date_str}: sleep_last={sleep_last}, sleep_hist_scores={sleeps}")

    # 4) Stress history (last 3 days) – use stressPercentage
    start_str3 = (day - timedelta(days=2)).isoformat()
    sres = influxdbclient.query(
        f"SELECT last(\"stressPercentage\") AS sp "
        "FROM \"DailyStats\" "
        f"WHERE time >= '{start_str3}' AND time <= '{end_ts}' "
        "GROUP BY time(1d)"
    )
    stress_pcts = [p["sp"] for p in sres.get_points() if p.get("sp") is not None]
    avg_pct = mean(stress_pcts) if stress_pcts else 0.0

    if len(stress_pcts) < 3:
        stress_score = 0.5
    else:
        stress_score = 1.0 - min(avg_pct / 100.0, 1.0)

    logging.info(f"{date_str}: stress_pcts={stress_pcts}, stress_score={stress_score:.3f}")

    # 5) Combine with weights
    readiness = (
            0.20 * acute_score +
            0.20 * hrv_score +
            0.20 * recovery_score +
            0.15 * sleep_score +
            0.15 * sleep_hist_score +
            0.10 * stress_score
    )
    readiness_pct = round(readiness * 100)

    logging.info(
        f"{date_str} – components: acute={acute_score:.3f}, hrv={hrv_score:.3f}, "
        f"rec={recovery_score:.3f}, sleepLN={sleep_score:.3f}, "
        f"sleep3N={sleep_hist_score:.3f}, stress={stress_score:.3f}"
    )
    logging.info(f"Training Readiness: {readiness_pct}%")

    # 6) Write to Influx
    points.append({
        "measurement": "TrainingReadiness",
        "time": day.isoformat(),
        "tags": {"Device": garmin_device_name},
        "fields": {
            "readiness": readiness_pct,
            "CTL": round(ctl, 1),
            "ATL": round(atl, 1),
            "TSB": round(ctl - atl, 1),
            "sleepScore": round(sleep_last, 1),
            "sleepHist": round(sleep_hist_score * 100, 1),
            "avgOvernightHrv": round(hrv, 1),
            "stressPct": round(avg_pct if stress_pcts else 0, 1)
        }
    })

    return points


# %%
def get_hrv_baseline(garmin_obj, date_str, influxdbclient, garmin_device_name):
    """
    Calculate a rolling HRV baseline & trend:
      - baseline = mean(RMSSD last 7 nights)
      - trend    = mean(RMSSD last 3 nights)
      - ratio    = trend / baseline
    Returns list of InfluxDB points or [] if insufficient data.
    """
    points = []
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=pytz.UTC)

    # Query last 28 nights of RMSSD
    start28 = (day - timedelta(days=27)).isoformat()
    res = influxdbclient.query(
        f"SELECT last(\"avgOvernightHrv\") AS hrv "
        f"FROM \"SleepSummary\" "
        f"WHERE time >= '{start28}' AND time <= '{day.isoformat()}' "
        "GROUP BY time(1d)"
    )
    arr = [p["hrv"] for p in res.get_points() if p.get("hrv") is not None]

    # Need at least 7 values to form a baseline
    if len(arr) < 7:
        logging.debug(f"Skipping HRV baseline for {date_str}: only {len(arr)} days of data")
        return []

    baseline = mean(arr[-7:])
    trend = mean(arr[-3:])
    ratio = trend / baseline if baseline else None

    ts = day.isoformat()
    points.append({
        "measurement": "HRVTrend",
        "time": ts,
        "tags": {"Device": garmin_device_name},
        "fields": {
            "baseline": round(baseline, 1),
            "trend": round(trend, 1),
            "ratio": round(ratio, 3) if ratio is not None else None
        }
    })
    logging.info(f"Success : HRV-baseline={baseline:.1f}, trend={trend:.1f}, ratio={ratio:.3f} on {date_str}")
    return points


# %%
def get_acwr(garmin_obj, date_str, influxdbclient, garmin_device_name):
    """
    Calculate Acute:Chronic Workload Ratio (ACWR) for the given date.
    ACWR = mean(TRIMP last 7 days) / mean(TRIMP last 28 days)
    Returns a list of InfluxDB points or an empty list if not enough data.
    """
    points = []
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=pytz.UTC)

    # Helper to query TRIMP over a date range (inclusive)
    def query_trimp(start_dt, end_dt):
        q = (
            influxdbclient.query(
                f"SELECT last(\"banisterTRIMP\") AS trimp "
                f"FROM \"TrainingLoad\" "
                f"WHERE time >= '{start_dt}' AND time <= '{end_dt}' "
                "GROUP BY time(1d)"
            )
            .get_points()
        )
        return [p["trimp"] for p in q if p.get("trimp") is not None]

    # Define windows
    end_ts = day.isoformat()
    start7 = (day - timedelta(days=6)).isoformat()
    start28 = (day - timedelta(days=27)).isoformat()

    wk7 = query_trimp(start7, end_ts)
    wk28 = query_trimp(start28, end_ts)

    # Need at least one week and four weeks of data
    if len(wk7) < 1 or len(wk28) < 1:
        return []

    acwr = mean(wk7) / mean(wk28)

    # Build point at midnight UTC
    ts = day.isoformat()
    points.append({
        "measurement": "TrainingLoad",
        "time": ts,
        "tags": {"Device": garmin_device_name},
        "fields": {"ACWR": round(acwr, 2)}
    })
    logging.info(f"Success : Calculated ACWR={acwr:.2f} for {date_str}")
    return points


# %%
def get_lactate_threshold(garmin_obj, date_str, garmin_device_name):
    """
    Estimate running LT from TCX trackpoints:
      • target HR = 0.88 * HRmax ±3 bpm
      • average pace (min/km) when HR in that band
    """
    points = []

    # 1) fetch HRmax
    stats = garmin_obj.get_stats(date_str)
    maxhr = stats.get("maxHeartRate")
    if not maxhr:
        return []

    hr_target = 0.88 * maxhr
    lo, hi = hr_target - 3, hr_target + 3

    # 2) download TCX for each run
    acts = garmin_obj.get_activities_by_date(date_str, date_str)
    pace_list = []
    ns = {
        "tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
        "ext": "http://www.garmin.com/xmlschemas/ActivityExtension/v2"
    }

    for a in acts:
        if a.get("activityType", {}).get("typeKey") != "running":
            continue
        tcx = garmin_obj.download_activity(
            a["activityId"],
            dl_fmt=garmin_obj.ActivityDownloadFormat.TCX
        ).decode("utf-8")
        root = ET.fromstring(tcx)

        for tp in root.findall(".//tcx:Trackpoint", ns):
            hr = tp.findtext("tcx:HeartRateBpm/tcx:Value", namespaces=ns)
            sp = tp.findtext("tcx:Extensions/ext:TPX/ext:Speed", namespaces=ns)
            if not hr or not sp:
                continue

            hr = float(hr)
            speed_m_s = float(sp)

            # skip zero/invalid speeds
            if speed_m_s <= 0:
                continue

            if lo <= hr <= hi and speed_m_s > 2:  # ~7 km/h
                # correct pace formula: (1000 m)/(speed m/s) -> seconds, /60 -> minutes
                pace_min_per_km = (1000.0 / speed_m_s) / 60.0
                pace_list.append(pace_min_per_km)

    if not pace_list:
        logging.debug(f"No valid threshold-speed points on {date_str}")
        return []

    med_pace = median(pace_list)
    logging.debug(f"{len(pace_list)} threshold points on {date_str}, median pace={med_pace:.2f}")

    mins = int(med_pace)
    secs = int(round((med_pace - mins) * 60))
    pace_str = f"{mins:02d}:{secs:02d}"

    # 3) write result at midnight UTC
    ts = datetime.strptime(date_str, "%Y-%m-%d") \
        .replace(tzinfo=pytz.UTC).isoformat()
    points.append({
        "measurement": "LactateThreshold",
        "time": ts,
        "tags": {"Device": garmin_device_name},
        "fields": {
            "hr_lactate": round(hr_target, 1),
            "pace_lactate_num": round(med_pace, 2),
            "pace_lactate_str": pace_str
        }
    })

    logging.info(f"LT HR≈{hr_target:.1f}, median pace≈{med_pace:.2f} min/km on {date_str}")
    return points


# %%
def get_training_load_focus(garmin_obj, date_str, garmin_device_name):
    pts = []
    ts = garmin_obj.get_training_status(date_str)
    lf = ts.get('loadFocus', {})
    if lf:
        fields = {
            'lowAerobic': lf.get('lowAerobic'),
            'highAerobic': lf.get('highAerobic'),
            'anaerobic':  lf.get('anaerobic'),
            'targetLow':  lf.get('targetLow'),
            'targetHigh': lf.get('targetHigh')
        }
        pts.append({
            "measurement": "TrainingLoadFocus",
            "time": datetime.strptime(date_str, "%Y-%m-%d")
            .replace(hour=12, tzinfo=pytz.UTC)
            .isoformat(),
            "tags": {"Device": garmin_device_name},
            "fields": fields
        })
    return pts


# %%
def compute_ctl_atl(date_str, influxdbclient, device):
    """
    Returns a tuple (ATL, CTL) for the given date:
      • ATL = mean(TRIMP last 7 days)
      • CTL = mean(TRIMP last 42 days)
    """
    # parse our reference day at UTC midnight
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
    end_ts = day + timedelta(hours=23, minutes=59, seconds=59)

    # helper to query banisterTRIMP over a window
    def query_trimp(start_delta_days):
        start = (day - timedelta(days=start_delta_days - 1)).isoformat()
        end   = end_ts.isoformat()
        q = influxdbclient.query(
            f"SELECT last(\"banisterTRIMP\") AS trimp "
            f"FROM \"TrainingLoad\" "
            f"WHERE time >= '{start}' AND time <= '{end}' "
            "GROUP BY time(1d)"
        ).get_points()
        return [pt["trimp"] for pt in q if pt.get("trimp") is not None]

    # ATL = 7-day average
    trimp_7  = query_trimp(7)
    atl      = mean(trimp_7) if trimp_7 else 0.0

    # CTL = 42-day average
    trimp_42 = query_trimp(42)
    ctl      = mean(trimp_42) if trimp_42 else 0.0

    return atl, ctl


 
def get_readiness_inputs(garmin_obj, date_str, influxdbclient, device):
    """
    Always emit exactly one ReadinessInputs point for the given date_str,
    filling missing metrics with zeros or None so last(...) and fill(previous)
    in your Grafana query will work correctly.
    """
    from datetime import datetime, timedelta
    import pytz
    from statistics import mean

    # 1) Build day boundaries
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
    start_dt = day
    end_dt   = day + timedelta(days=1)

    # 2) Pull Garmin daily stats
    stats = garmin_obj.get_stats(date_str) or {}
    bb_wake    = stats.get("bodyBatteryAtWakeTime") or stats.get("bodyBatteryAtWake") or None
    stress_pct = stats.get("stressPercentage") or 0.0

    # 3) Pull sleep summary
    sleep = garmin_obj.get_sleep_data(date_str) or {}
    avg_hrv     = sleep.get("avgOvernightHrv") or None
    sleep_score = (sleep.get("dailySleepDTO", {})
                       .get("sleepScores", {})
                       .get("overall", {})
                       .get("value")) or None

    # 4) Compute 3-night sleep history
    pts = list(influxdbclient.query(
        f"SELECT last(\"sleepScore\") AS sc "
        f"FROM \"ReadinessInputs\" "
        f"WHERE time >= '{(day - timedelta(days=2)).isoformat()}' AND time < '{end_dt.isoformat()}' "
        "GROUP BY time(1d)"
    ).get_points())
    sleep_hist = round(mean([p["sc"] for p in pts if p.get("sc") is not None]), 1) if pts else None

    # 5) Compute today’s acuteLoad, ATL & CTL
    trimp_today = get_training_load(garmin_obj, date_str, start_dt, end_dt) or 0.0
    atl, ctl    = compute_ctl_atl(date_str, influxdbclient, device)

    # 6) Build exactly one point (fields default to 0 or None)
    point = {
        "measurement": "ReadinessInputs",
        "time": f"{date_str}T07:00:00Z",
        "tags": {"Device": device},
        "fields": {
            "acuteLoad":         float(trimp_today),
            "ATL":               round(atl, 1),
            "CTL":               round(ctl, 1),
            "avgOvernightHrv":   avg_hrv,
            "sleepScore":        sleep_score,
            "sleepHist":         sleep_hist,
            "stressPct":         float(stress_pct),
            "bodyBatteryAtWake": bb_wake
        }
    }

    return [point]
