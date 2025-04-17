# %%
import base64
from statistics import mean, median

import dotenv
import logging
import math
import os
import pytz
import requests
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from garth.exc import GarthHTTPError
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

garmin_obj = None
banner_text = """

*****  █▀▀ ▄▀█ █▀█ █▀▄▀█ █ █▄ █    █▀▀ █▀█ ▄▀█ █▀▀ ▄▀█ █▄ █ ▄▀█  *****
*****  █▄█ █▀█ █▀▄ █ ▀ █ █ █ ▀█    █▄█ █▀▄ █▀█ █▀  █▀█ █ ▀█ █▀█  *****

______________________________________________________________________

By Arpan Ghosh | Please consider supporting the project if you love it
______________________________________________________________________

"""
print(banner_text)

env_override = dotenv.load_dotenv("override-default-vars.env", override=True)
if env_override:
    logging.warning("System ENV variables are overriden with override-default-vars.env")

# %%
INFLUXDB_HOST = os.getenv("INFLUXDB_HOST", 'your.influxdb.hostname')  # Required
INFLUXDB_PORT = int(os.getenv("INFLUXDB_PORT", 8086))  # Required
INFLUXDB_USERNAME = os.getenv("INFLUXDB_USERNAME", 'influxdb_username')  # Required
INFLUXDB_PASSWORD = os.getenv("INFLUXDB_PASSWORD", 'influxdb_access_password')  # Required
INFLUXDB_DATABASE = os.getenv("INFLUXDB_DATABASE", 'GarminStats')  # Required
TOKEN_DIR = os.getenv("TOKEN_DIR", "~/.garminconnect")  # optional
GARMINCONNECT_EMAIL = os.environ.get("GARMINCONNECT_EMAIL", None)  # optional, asks in prompt on run if not provided
GARMINCONNECT_PASSWORD = base64.b64decode(os.getenv("GARMINCONNECT_BASE64_PASSWORD")).decode("utf-8") if os.getenv(
    "GARMINCONNECT_BASE64_PASSWORD") != None else None  # optional, asks in prompt on run if not provided
GARMIN_DEVICENAME = os.getenv("GARMIN_DEVICENAME",
                              "Unknown")  # optional, attepmts to set the same automatically if not given
AUTO_DATE_RANGE = False if os.getenv("AUTO_DATE_RANGE") in ['False', 'false', 'FALSE', 'f', 'F', 'no', 'No', 'NO',
                                                            '0'] else True  # optional
MANUAL_START_DATE = os.getenv("MANUAL_START_DATE",
                              None)  # optional, in YYYY-MM-DD format, if you want to bulk update only from specific date
MANUAL_END_DATE = os.getenv("MANUAL_END_DATE", datetime.today().strftime(
    '%Y-%m-%d'))  # optional, in YYYY-MM-DD format, if you want to bulk update until a specific date
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # optional
FETCH_FAILED_WAIT_SECONDS = int(os.getenv("FETCH_FAILED_WAIT_SECONDS", 1800))  # optional
RATE_LIMIT_CALLS_SECONDS = int(os.getenv("RATE_LIMIT_CALLS_SECONDS", 5))  # optional
INFLUXDB_ENDPOINT_IS_HTTP = False if os.getenv("INFLUXDB_ENDPOINT_IS_HTTP") in ['False', 'false', 'FALSE', 'f', 'F',
                                                                                'no', 'No', 'NO',
                                                                                '0'] else True  # optional
GARMIN_DEVICENAME_AUTOMATIC = False if GARMIN_DEVICENAME != "Unknown" else True  # optional
UPDATE_INTERVAL_SECONDS = int(os.getenv("UPDATE_INTERVAL_SECONDS", 300))  # optional

# %%
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# %%
try:
    if INFLUXDB_ENDPOINT_IS_HTTP:
        influxdbclient = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USERNAME,
                                        password=INFLUXDB_PASSWORD)
    else:
        influxdbclient = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT, username=INFLUXDB_USERNAME,
                                        password=INFLUXDB_PASSWORD, ssl=True, verify_ssl=True)
    influxdbclient.switch_database(INFLUXDB_DATABASE)
    influxdbclient.ping()
except InfluxDBClientError as err:
    logging.error("Unable to connect with influxdb database! Aborted")
    raise InfluxDBClientError("InfluxDB connection failed:" + str(err))


# %%
def iter_days(start_date: str, end_date: str):
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    current = end

    while current >= start:
        yield current.strftime('%Y-%m-%d')
        current -= timedelta(days=1)


# %%
def garmin_login():
    try:
        logging.info(f"Trying to login to Garmin Connect using token data from directory '{TOKEN_DIR}'...")
        garmin = Garmin()
        garmin.login(TOKEN_DIR)
        logging.info("login to Garmin Connect successful using stored session tokens.")

    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
        logging.warning(
            "Session is expired or login information not present/incorrect. You'll need to log in again...login with your Garmin Connect credentials to generate them.")
        try:
            user_email = GARMINCONNECT_EMAIL or input("Enter Garminconnect Login e-mail: ")
            user_password = GARMINCONNECT_PASSWORD or input(
                "Enter Garminconnect password (characters will be visible): ")
            garmin = Garmin(
                email=user_email, password=user_password, is_cn=False, return_on_mfa=True
            )
            result1, result2 = garmin.login()
            if result1 == "needs_mfa":  # MFA is required
                mfa_code = input("MFA one-time code (via email or SMS): ")
                garmin.resume_login(result2, mfa_code)

            garmin.garth.dump(TOKEN_DIR)
            logging.info(f"Oauth tokens stored in '{TOKEN_DIR}' directory for future use")

            garmin.login(TOKEN_DIR)
            logging.info("login to Garmin Connect successful using stored session tokens.")

        except (
                FileNotFoundError,
                GarthHTTPError,
                GarminConnectAuthenticationError,
                requests.exceptions.HTTPError,
        ) as err:
            logging.error(str(err))
            raise Exception("Session is expired : please login again and restart the script")

    return garmin


# %%
def write_points_to_influxdb(points):
    try:
        if len(points) != 0:
            influxdbclient.write_points(points)
            logging.info("Successfully updated influxdb database with new points")
    except InfluxDBClientError as err:
        logging.error("Unable to connect with database! " + str(err))


# %%
def get_daily_stats(date_str):
    points_list = []
    stats_json = garmin_obj.get_stats(date_str)
    if stats_json['wellnessStartTimeGmt'] and datetime.strptime(date_str, "%Y-%m-%d") < datetime.today():
        points_list.append({
            "measurement": "DailyStats",
            "time": pytz.timezone("UTC").localize(
                datetime.strptime(stats_json['wellnessStartTimeGmt'], "%Y-%m-%dT%H:%M:%S.%f")).isoformat(),
            "tags": {
                "Device": GARMIN_DEVICENAME
            },
            "fields": {
                "activeKilocalories": stats_json.get('activeKilocalories'),
                "bmrKilocalories": stats_json.get('bmrKilocalories'),

                'totalSteps': stats_json.get('totalSteps'),
                'totalDistanceMeters': stats_json.get('totalDistanceMeters'),

                "highlyActiveSeconds": stats_json.get("highlyActiveSeconds"),
                "activeSeconds": stats_json.get("activeSeconds"),
                "sedentarySeconds": stats_json.get("sedentarySeconds"),
                "sleepingSeconds": stats_json.get("sleepingSeconds"),
                "moderateIntensityMinutes": stats_json.get("moderateIntensityMinutes"),
                "vigorousIntensityMinutes": stats_json.get("vigorousIntensityMinutes"),

                "floorsAscendedInMeters": stats_json.get("floorsAscendedInMeters"),
                "floorsDescendedInMeters": stats_json.get("floorsDescendedInMeters"),
                "floorsAscended": stats_json.get("floorsAscended"),
                "floorsDescended": stats_json.get("floorsDescended"),

                "minHeartRate": stats_json.get("minHeartRate"),
                "maxHeartRate": stats_json.get("maxHeartRate"),
                "restingHeartRate": stats_json.get("restingHeartRate"),
                "minAvgHeartRate": stats_json.get("minAvgHeartRate"),
                "maxAvgHeartRate": stats_json.get("maxAvgHeartRate"),

                "stressDuration": stats_json.get("stressDuration"),
                "restStressDuration": stats_json.get("restStressDuration"),
                "activityStressDuration": stats_json.get("activityStressDuration"),
                "uncategorizedStressDuration": stats_json.get("uncategorizedStressDuration"),
                "totalStressDuration": stats_json.get("totalStressDuration"),
                "lowStressDuration": stats_json.get("lowStressDuration"),
                "mediumStressDuration": stats_json.get("mediumStressDuration"),
                "highStressDuration": stats_json.get("highStressDuration"),

                "stressPercentage": stats_json.get("stressPercentage"),
                "restStressPercentage": stats_json.get("restStressPercentage"),
                "activityStressPercentage": stats_json.get("activityStressPercentage"),
                "uncategorizedStressPercentage": stats_json.get("uncategorizedStressPercentage"),
                "lowStressPercentage": stats_json.get("lowStressPercentage"),
                "mediumStressPercentage": stats_json.get("mediumStressPercentage"),
                "highStressPercentage": stats_json.get("highStressPercentage"),

                "bodyBatteryChargedValue": stats_json.get("bodyBatteryChargedValue"),
                "bodyBatteryDrainedValue": stats_json.get("bodyBatteryDrainedValue"),
                "bodyBatteryHighestValue": stats_json.get("bodyBatteryHighestValue"),
                "bodyBatteryLowestValue": stats_json.get("bodyBatteryLowestValue"),
                "bodyBatteryDuringSleep": stats_json.get("bodyBatteryDuringSleep"),
                "bodyBatteryAtWakeTime": stats_json.get("bodyBatteryAtWakeTime"),

                "averageSpo2": stats_json.get("averageSpo2"),
                "lowestSpo2": stats_json.get("lowestSpo2"),
            }
        })
        if points_list:
            logging.info(f"Success : Fetching daily matrices for date {date_str}")
        return points_list
    else:
        logging.debug("No daily stat data available for the give date " + date_str)
        return []


# %%
def get_last_sync():
    global GARMIN_DEVICENAME
    points_list = []
    sync_data = garmin_obj.get_device_last_used()
    if GARMIN_DEVICENAME_AUTOMATIC:
        GARMIN_DEVICENAME = sync_data.get('lastUsedDeviceName') or "Unknown"
    points_list.append({
        "measurement": "DeviceSync",
        "time": datetime.fromtimestamp(sync_data['lastUsedDeviceUploadTime'] / 1000,
                                       tz=pytz.timezone("UTC")).isoformat(),
        "tags": {
            "Device": GARMIN_DEVICENAME
        },
        "fields": {
            "imageUrl": sync_data.get('imageUrl'),
            "Device": GARMIN_DEVICENAME
        }
    })
    if points_list:
        logging.info(f"Success : Updated device last sync time")
    else:
        logging.warning("No associated/synced Garmin device found with your account")
    return points_list


# %%
def get_sleep_data(date_str):
    points_list = []
    all_sleep_data = garmin_obj.get_sleep_data(date_str)
    sleep_json = all_sleep_data.get("dailySleepDTO", None)
    if sleep_json["sleepEndTimestampGMT"]:
        points_list.append({
            "measurement": "SleepSummary",
            "time": datetime.fromtimestamp(sleep_json["sleepEndTimestampGMT"] / 1000,
                                           tz=pytz.timezone("UTC")).isoformat(),
            "tags": {
                "Device": GARMIN_DEVICENAME
            },
            "fields": {
                "sleepTimeSeconds": sleep_json.get("sleepTimeSeconds"),
                "deepSleepSeconds": sleep_json.get("deepSleepSeconds"),
                "lightSleepSeconds": sleep_json.get("lightSleepSeconds"),
                "remSleepSeconds": sleep_json.get("remSleepSeconds"),
                "awakeSleepSeconds": sleep_json.get("awakeSleepSeconds"),
                "averageSpO2Value": sleep_json.get("averageSpO2Value"),
                "lowestSpO2Value": sleep_json.get("lowestSpO2Value"),
                "highestSpO2Value": sleep_json.get("highestSpO2Value"),
                "averageRespirationValue": sleep_json.get("averageRespirationValue"),
                "lowestRespirationValue": sleep_json.get("lowestRespirationValue"),
                "highestRespirationValue": sleep_json.get("highestRespirationValue"),
                "awakeCount": sleep_json.get("awakeCount"),
                "avgSleepStress": sleep_json.get("avgSleepStress"),
                "sleepScore": sleep_json.get("sleepScores", {}).get("overall", {}).get("value"),
                "restlessMomentsCount": all_sleep_data.get("restlessMomentsCount"),
                "avgOvernightHrv": all_sleep_data.get("avgOvernightHrv"),
                "bodyBatteryChange": all_sleep_data.get("bodyBatteryChange"),
                "restingHeartRate": all_sleep_data.get("restingHeartRate")
            }
        })
    sleep_movement_intraday = all_sleep_data.get("sleepMovement")
    if sleep_movement_intraday:
        for entry in sleep_movement_intraday:
            points_list.append({
                "measurement": "SleepIntraday",
                "time": pytz.timezone("UTC").localize(
                    datetime.strptime(entry["startGMT"], "%Y-%m-%dT%H:%M:%S.%f")).isoformat(),
                "tags": {
                    "Device": GARMIN_DEVICENAME
                },
                "fields": {
                    "SleepMovementActivityLevel": entry.get("activityLevel", -1),
                    "SleepMovementActivitySeconds": int((datetime.strptime(entry["endGMT"],
                                                                           "%Y-%m-%dT%H:%M:%S.%f") - datetime.strptime(
                        entry["startGMT"], "%Y-%m-%dT%H:%M:%S.%f")).total_seconds())
                }
            })
    sleep_levels_intraday = all_sleep_data.get("sleepLevels")
    if sleep_levels_intraday:
        for entry in sleep_levels_intraday:
            if entry.get("activityLevel"):
                points_list.append({
                    "measurement": "SleepIntraday",
                    "time": pytz.timezone("UTC").localize(
                        datetime.strptime(entry["startGMT"], "%Y-%m-%dT%H:%M:%S.%f")).isoformat(),
                    "tags": {
                        "Device": GARMIN_DEVICENAME
                    },
                    "fields": {
                        "SleepStageLevel": entry.get("activityLevel"),
                        "SleepStageSeconds": int((datetime.strptime(entry["endGMT"],
                                                                    "%Y-%m-%dT%H:%M:%S.%f") - datetime.strptime(
                            entry["startGMT"], "%Y-%m-%dT%H:%M:%S.%f")).total_seconds())
                    }
                })
    sleep_restlessness_intraday = all_sleep_data.get("sleepRestlessMoments")
    if sleep_restlessness_intraday:
        for entry in sleep_restlessness_intraday:
            if entry.get("value"):
                points_list.append({
                    "measurement": "SleepIntraday",
                    "time": datetime.fromtimestamp(entry["startGMT"] / 1000, tz=pytz.timezone("UTC")).isoformat(),
                    "tags": {
                        "Device": GARMIN_DEVICENAME
                    },
                    "fields": {
                        "sleepRestlessValue": entry.get("value")
                    }
                })
    sleep_spo2_intraday = all_sleep_data.get("wellnessEpochSPO2DataDTOList")
    if sleep_spo2_intraday:
        for entry in sleep_spo2_intraday:
            if entry.get("spo2Reading"):
                points_list.append({
                    "measurement": "SleepIntraday",
                    "time": pytz.timezone("UTC").localize(
                        datetime.strptime(entry["epochTimestamp"], "%Y-%m-%dT%H:%M:%S.%f")).isoformat(),
                    "tags": {
                        "Device": GARMIN_DEVICENAME
                    },
                    "fields": {
                        "spo2Reading": entry.get("spo2Reading")
                    }
                })
    sleep_respiration_intraday = all_sleep_data.get("wellnessEpochRespirationDataDTOList")
    if sleep_respiration_intraday:
        for entry in sleep_respiration_intraday:
            if entry.get("respirationValue"):
                points_list.append({
                    "measurement": "SleepIntraday",
                    "time": datetime.fromtimestamp(entry["startTimeGMT"] / 1000, tz=pytz.timezone("UTC")).isoformat(),
                    "tags": {
                        "Device": GARMIN_DEVICENAME
                    },
                    "fields": {
                        "respirationValue": entry.get("respirationValue")
                    }
                })
    sleep_heart_rate_intraday = all_sleep_data.get("sleepHeartRate")
    if sleep_heart_rate_intraday:
        for entry in sleep_heart_rate_intraday:
            if entry.get("value"):
                points_list.append({
                    "measurement": "SleepIntraday",
                    "time": datetime.fromtimestamp(entry["startGMT"] / 1000, tz=pytz.timezone("UTC")).isoformat(),
                    "tags": {
                        "Device": GARMIN_DEVICENAME
                    },
                    "fields": {
                        "heartRate": entry.get("value")
                    }
                })
    sleep_stress_intraday = all_sleep_data.get("sleepStress")
    if sleep_stress_intraday:
        for entry in sleep_stress_intraday:
            if entry.get("value"):
                points_list.append({
                    "measurement": "SleepIntraday",
                    "time": datetime.fromtimestamp(entry["startGMT"] / 1000, tz=pytz.timezone("UTC")).isoformat(),
                    "tags": {
                        "Device": GARMIN_DEVICENAME
                    },
                    "fields": {
                        "stressValue": entry.get("value")
                    }
                })
    sleep_bb_intraday = all_sleep_data.get("sleepBodyBattery")
    if sleep_bb_intraday:
        for entry in sleep_bb_intraday:
            if entry.get("value"):
                points_list.append({
                    "measurement": "SleepIntraday",
                    "time": datetime.fromtimestamp(entry["startGMT"] / 1000, tz=pytz.timezone("UTC")).isoformat(),
                    "tags": {
                        "Device": GARMIN_DEVICENAME
                    },
                    "fields": {
                        "bodyBattery": entry.get("value")
                    }
                })
    sleep_hrv_intraday = all_sleep_data.get("hrvData")
    if sleep_hrv_intraday:
        for entry in sleep_hrv_intraday:
            if entry.get("value"):
                points_list.append({
                    "measurement": "SleepIntraday",
                    "time": datetime.fromtimestamp(entry["startGMT"] / 1000, tz=pytz.timezone("UTC")).isoformat(),
                    "tags": {
                        "Device": GARMIN_DEVICENAME
                    },
                    "fields": {
                        "hrvData": entry.get("value")
                    }
                })
    if points_list:
        logging.info(f"Success : Fetching intraday sleep matrices for date {date_str}")
    return points_list


# %%
def get_intraday_hr(date_str):
    points_list = []
    hr_list = garmin_obj.get_heart_rates(date_str).get("heartRateValues") or []
    for entry in hr_list:
        if entry[1]:
            points_list.append({
                "measurement": "HeartRateIntraday",
                "time": datetime.fromtimestamp(entry[0] / 1000, tz=pytz.timezone("UTC")).isoformat(),
                "tags": {
                    "Device": GARMIN_DEVICENAME
                },
                "fields": {
                    "HeartRate": entry[1]
                }
            })
    if points_list:
        logging.info(f"Success : Fetching intraday Heart Rate for date {date_str}")
    return points_list


# %%
def get_intraday_steps(date_str):
    points_list = []
    steps_list = garmin_obj.get_steps_data(date_str)
    for entry in steps_list:
        if entry["steps"] or entry["steps"] == 0:
            points_list.append({
                "measurement": "StepsIntraday",
                "time": pytz.timezone("UTC").localize(
                    datetime.strptime(entry['startGMT'], "%Y-%m-%dT%H:%M:%S.%f")).isoformat(),
                "tags": {
                    "Device": GARMIN_DEVICENAME
                },
                "fields": {
                    "StepsCount": entry["steps"]
                }
            })
    if points_list:
        logging.info(f"Success : Fetching intraday steps for date {date_str}")
    return points_list


# %%
def get_intraday_stress(date_str):
    points_list = []
    stress_list = garmin_obj.get_stress_data(date_str).get('stressValuesArray') or []
    for entry in stress_list:
        if entry[1] or entry[1] == 0:
            points_list.append({
                "measurement": "StressIntraday",
                "time": datetime.fromtimestamp(entry[0] / 1000, tz=pytz.timezone("UTC")).isoformat(),
                "tags": {
                    "Device": GARMIN_DEVICENAME
                },
                "fields": {
                    "stressLevel": entry[1]
                }
            })
    bb_list = garmin_obj.get_stress_data(date_str).get('bodyBatteryValuesArray') or []
    for entry in bb_list:
        if entry[2] or entry[2] == 0:
            points_list.append({
                "measurement": "BodyBatteryIntraday",
                "time": datetime.fromtimestamp(entry[0] / 1000, tz=pytz.timezone("UTC")).isoformat(),
                "tags": {
                    "Device": GARMIN_DEVICENAME
                },
                "fields": {
                    "BodyBatteryLevel": entry[2]
                }
            })
    if points_list:
        logging.info(f"Success : Fetching intraday stress and Body Battery values for date {date_str}")
    return points_list


# %%
def get_intraday_br(date_str):
    points_list = []
    br_list = garmin_obj.get_respiration_data(date_str).get('respirationValuesArray') or []
    for entry in br_list:
        if entry[1]:
            points_list.append({
                "measurement": "BreathingRateIntraday",
                "time": datetime.fromtimestamp(entry[0] / 1000, tz=pytz.timezone("UTC")).isoformat(),
                "tags": {
                    "Device": GARMIN_DEVICENAME
                },
                "fields": {
                    "BreathingRate": entry[1]
                }
            })
    if points_list:
        logging.info(f"Success : Fetching intraday Breathing Rate for date {date_str}")
    return points_list


# %%
def get_intraday_hrv(date_str):
    points_list = []
    hrv_list = (garmin_obj.get_hrv_data(date_str) or {}).get('hrvReadings') or []
    for entry in hrv_list:
        if entry.get('hrvValue'):
            points_list.append({
                "measurement": "HRV_Intraday",
                "time": pytz.timezone("UTC").localize(
                    datetime.strptime(entry['readingTimeGMT'], "%Y-%m-%dT%H:%M:%S.%f")).isoformat(),
                "tags": {
                    "Device": GARMIN_DEVICENAME
                },
                "fields": {
                    "hrvValue": entry.get('hrvValue')
                }
            })
    if points_list:
        logging.info(f"Success : Fetching intraday HRV for date {date_str}")
    return points_list


# %%
def get_body_composition(date_str):
    points_list = []
    weight_list_all = garmin_obj.get_weigh_ins(date_str, date_str).get('dailyWeightSummaries', [])
    if weight_list_all:
        weight_list = weight_list_all[0].get('allWeightMetrics', [])
        for weight_dict in weight_list:
            data_fields = {
                "weight": weight_dict.get("weight"),
                "bmi": weight_dict.get("bmi"),
                "bodyFat": weight_dict.get("bodyFat"),
                "bodyWater": weight_dict.get("bodyWater"),
            }
            if not all(value is None for value in data_fields.values()):
                points_list.append({
                    "measurement": "BodyComposition",
                    "time": datetime.fromtimestamp((weight_dict['timestampGMT'] / 1000),
                                                   tz=pytz.timezone("UTC")).isoformat() if weight_dict[
                        'timestampGMT'] else datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12,
                                                                                             tzinfo=pytz.UTC).isoformat(),
                    # Use GMT 12:00 is timestamp is not available (issue #15)
                    "tags": {
                        "Device": GARMIN_DEVICENAME,
                        "Frequency": "Intraday",
                        "SourceType": weight_dict.get('sourceType', "Unknown")
                    },
                    "fields": data_fields
                })
        logging.info(f"Success : Fetching intraday Body Composition (Weight, BMI etc) for date {date_str}")
    return points_list


# %%
def get_activity_summary(date_str):
    points_list = []
    activity_with_gps_id_dict = {}
    activity_list = garmin_obj.get_activities_by_date(date_str, date_str)
    for activity in activity_list:
        if activity.get('hasPolyline'):
            activity_with_gps_id_dict[activity.get('activityId')] = activity.get('activityType', {}).get('typeKey',
                                                                                                         "Unknown")
        if "startTimeGMT" in activity:  # "startTimeGMT" should be available for all activities (fix #13)
            points_list.append({
                "measurement": "ActivitySummary",
                "time": datetime.strptime(activity["startTimeGMT"], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=pytz.UTC).isoformat(),
                "tags": {
                    "Device": GARMIN_DEVICENAME
                },
                "fields": {
                    'activityId': activity.get('activityId'),
                    'deviceId': activity.get('deviceId'),
                    'activityName': activity.get('activityName'),
                    'activityType': activity.get('activityType', {}).get('typeKey', None),
                    'distance': activity.get('distance'),
                    'elapsedDuration': activity.get('elapsedDuration'),
                    'movingDuration': activity.get('movingDuration'),
                    'averageSpeed': activity.get('averageSpeed'),
                    'maxSpeed': activity.get('maxSpeed'),
                    'calories': activity.get('calories'),
                    'bmrCalories': activity.get('bmrCalories'),
                    'averageHR': activity.get('averageHR'),
                    'maxHR': activity.get('maxHR'),
                    'locationName': activity.get('locationName'),
                    'lapCount': activity.get('lapCount'),
                    'hrTimeInZone_1': activity.get('hrTimeInZone_1'),
                    'hrTimeInZone_2': activity.get('hrTimeInZone_2'),
                    'hrTimeInZone_3': activity.get('hrTimeInZone_3'),
                    'hrTimeInZone_4': activity.get('hrTimeInZone_4'),
                    'hrTimeInZone_5': activity.get('hrTimeInZone_5'),
                }
            })
            points_list.append({
                "measurement": "ActivitySummary",
                "time": (datetime.strptime(activity["startTimeGMT"], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=pytz.UTC) + timedelta(seconds=int(activity.get('elapsedDuration', 0)))).isoformat(),
                "tags": {
                    "Device": GARMIN_DEVICENAME,
                    "ActivityID": activity.get('activityId'),
                    "ActivitySelector": datetime.strptime(activity["startTimeGMT"], "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=pytz.UTC).strftime('%Y%m%dT%H%M%SUTC-') + activity.get('activityType', {}).get('typeKey',
                                                                                                              "Unknown")
                },
                "fields": {
                    'activityId': activity.get('activityId'),
                    'deviceId': activity.get('deviceId'),
                    'activityName': "END",
                    'activityType': "No Activity",
                }
            })
            logging.info(
                f"Success : Fetching Activity summary with id {activity.get('activityId')} for date {date_str}")
        else:
            logging.warning(
                f"Skipped : Start Timestamp missing for activity id {activity.get('activityId')} for date {date_str}")
    return points_list, activity_with_gps_id_dict


# %%
import math
import pytz
from datetime import datetime


def get_training_load(date_str):
    """
    Calculate Banister TRIMP (training load) for a given date
    based on intraday heart‐rate series, resting HR and max HR.
    """
    points_list = []

    # 1) fetch resting & max HR from daily stats
    stats = garmin_obj.get_stats(date_str)
    rhr = stats.get("restingHeartRate")
    maxhr = stats.get("maxHeartRate")
    if rhr is None or maxhr is None or maxhr <= rhr:
        logging.debug(f"Skipping TRIMP for {date_str}: invalid RHR/MHR ({rhr}/{maxhr})")
        return []

    # 2) fetch intraday heart‐rate values: list of [timestamp_ms, hr_value]
    hr_vals = garmin_obj.get_heart_rates(date_str).get("heartRateValues") or []
    if len(hr_vals) < 2:
        logging.debug(f"No intraday HR series for {date_str}, skipping TRIMP")
        return []

    # 3) accumulate Banister TRIMP
    total_trimp = 0.0
    for (t0, hr0), (t1, hr1) in zip(hr_vals, hr_vals[1:]):
        # skip any slice where HR is missing
        if hr0 is None or hr1 is None:
            continue

        # Δt in minutes
        dt_min = (t1 - t0) / 1000.0 / 60.0
        # relative intensity x = (HR - RHR) / (MHR - RHR), use midpoint HR
        hr_mid = (hr0 + hr1) / 2.0
        x = (hr_mid - rhr) / (maxhr - rhr)
        if x <= 0:
            continue

        # Banister’s formula with b = 1.92 (typical for men)
        total_trimp += dt_min * x * math.exp(1.92 * x)

    # 4) write a single point at the date’s UTC midnight
    ts = datetime.strptime(date_str, "%Y-%m-%d") \
        .replace(tzinfo=pytz.UTC).isoformat()
    points_list.append({
        "measurement": "TrainingLoad",
        "time": ts,
        "tags": {"Device": GARMIN_DEVICENAME},
        "fields": {"banisterTRIMP": round(total_trimp, 2)}
    })

    logging.info(f"Success : Calculated TRIMP={total_trimp:.2f} for {date_str}")
    return points_list


# %%
def get_vo2max(date_str):
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
        "tags": {"Device": GARMIN_DEVICENAME},
        "fields": {"estimatedVo2Max": round(vo2, 2)}
    })

    logging.info(f"Success : Estimated VO2max={vo2:.2f} ml/kg/min for {date_str}")
    return points_list


# %%
def get_activity_vo2(date_str):
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

    # 2) fetch all activities for that day
    acts = garmin_obj.get_activities_by_date(date_str, date_str)
    for act in acts:
        typ = act.get("activityType", {}).get("typeKey")
        if typ not in ("running", "cycling", "cycling_road", "cycling_mountain", "cycling_indoor"):
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
            "Device": GARMIN_DEVICENAME,
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

        # handle any cycling subtype
        if typ.startswith("cycling") and weight:
            avg_pw = act.get("averageWatts")
            max_pw = act.get("maxWatts")

            def vo2_cyc(watts):
                work_rate = watts * 6.12  # kgm/min
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
        logging.info(f"Success : Estimated VO₂ for {len(points)} point(s) on {date_str}")
    return points


# %%
def get_vo2max_segmented(date_str):
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
    rhr   = stats.get("restingHeartRate")
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
            t  = tp.findtext("tcx:Time", namespaces=ns)
            if hr and sp and t:
                track.append((
                    datetime.fromisoformat(t.replace("Z","")).timestamp(),
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
            "time":        ts,
            "tags":        {"Device": GARMIN_DEVICENAME},
            "fields":      {"estimate": round(vo2_uth, 2)}
        }]

    # 4) segment into ≥10 min chunks at ≥70% HRmax
    hr_thr = rhr + 0.7*(maxhr - rhr)
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
        slope = sum((xi-xm)*(yi-ym) for xi,yi in zip(X,Y)) \
                / sum((xi-xm)**2 for xi in X)
        intercept = ym - slope*xm
        vo2max = slope*maxhr + intercept
    else:
        vo2max = 15.3 * (maxhr / rhr)  # Uth fallback

    # 7) emit one point at midnight UTC
    ts = datetime.strptime(date_str, "%Y-%m-%d") \
        .replace(tzinfo=pytz.UTC).isoformat()
    points.append({
        "measurement": "VO2Max",
        "time":        ts,
        "tags":        {"Device": GARMIN_DEVICENAME},
        "fields":      {"estimate": round(vo2max, 2)}
    })

    logging.info(f"Segmented VO2max={vo2max:.2f} for {date_str}")
    return points


# %%
import pytz, logging
from datetime import datetime, timedelta

def get_training_readiness(date_str):
    """
    Calculate a 0–100 Training Readiness score for date_str:
      • CTL = avg banisterTRIMP over the past 42 days
      • ATL = avg banisterTRIMP over the past 7 days
      • TSB = CTL - ATL
      • HRV_norm = overnight RMSSD / 50 (cap at 1.0)
      • Sleep_norm = sleepScore / 100
      • Readiness = 40%*TSB_norm + 40%*HRV_norm + 20%*Sleep_norm
    """
    points = []
    # parse date
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=pytz.UTC)
    # helper to format Influx time strings
    fmt = lambda dt: dt.isoformat()
    # 1) fetch last 42 days of TRIMP
    start_ctl = fmt(day - timedelta(days=41))
    res42 = influxdbclient.query(
        f"SELECT last(\"banisterTRIMP\") FROM \"TrainingLoad\" "
        f"WHERE time >= '{start_ctl}' and time <= '{fmt(day + timedelta(hours=23,minutes=59))}' "
        "GROUP BY time(1d)"
    )
    loads42 = [p['last'] for p in res42.get_points() if p.get('last') is not None]
    # 2) fetch last 7 days of TRIMP
    start_atl = fmt(day - timedelta(days=6))
    res7 = influxdbclient.query(
        f"SELECT last(\"banisterTRIMP\") FROM \"TrainingLoad\" "
        f"WHERE time >= '{start_atl}' and time <= '{fmt(day + timedelta(hours=23,minutes=59))}' "
        "GROUP BY time(1d)"
    )
    loads7 = [p['last'] for p in res7.get_points() if p.get('last') is not None]

    if len(loads7) < 3:
        logging.debug(f"Not enough load history for {date_str}, skipping readiness")
        return []

    ctl = sum(loads42) / len(loads42) if loads42 else 0
    atl = sum(loads7)  / len(loads7)
    tsb = ctl - atl

    # normalize TSB: assume +/-30 pts covers most users
    tsb_norm = max(0.0, min((tsb + 30)/60, 1.0))

    # 3) fetch HRV & sleep score from that night’s SleepSummary
    sleep_res = influxdbclient.query(
        f"SELECT last(\"avgOvernightHrv\") AS hrv, "
        f"last(\"sleepScore\") AS slp "
        f"FROM \"SleepSummary\" "
        f"WHERE time >= '{fmt(day)}' AND time <= '{fmt(day + timedelta(hours=23,minutes=59))}'"
    ).get_points()
    rec = next(sleep_res, {})
    hrv = rec.get('hrv') or 0
    sleep = rec.get('slp') or 0

    hrv_norm   = min(hrv/50.0, 1.0)    # cap at RMSSD=50ms
    sleep_norm = sleep/100.0

    # 4) weighted sum → 0–1
    readiness = 0.4*tsb_norm + 0.4*hrv_norm + 0.2*sleep_norm
    readiness_pct = round(readiness * 100, 0)

    # 5) write one point at UTC midnight of date_str
    ts = fmt(day)
    points.append({
        "measurement": "TrainingReadiness",
        "time":        ts,
        "tags":        {"Device": GARMIN_DEVICENAME},
        "fields": {
            "readiness": readiness_pct,
            "TSB": round(tsb,1),
            "CTL": round(ctl,1),
            "ATL": round(atl,1),
            "avgOvernightHrv": round(hrv,1),
            "sleepScore": round(sleep,1)
        }
    })

    logging.info(f"Success: Training Readiness={readiness_pct}% for {date_str}")
    return points


# %%
def get_lactate_threshold(date_str):
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
        "tcx":"http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
        "ext":"http://www.garmin.com/xmlschemas/ActivityExtension/v2"
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
            hr = tp.findtext("tcx:HeartRateBpm/tcx:Value",   namespaces=ns)
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

    avg_pace = median(pace_list)
    logging.debug(f"{len(pace_list)} threshold points on {date_str}")

    mins = int(avg_pace)
    secs = int(round((avg_pace - mins) * 60))
    pace_str = f"{mins:02d}:{secs:02d}"  # e.g. "05:15"

    # 3) write result at midnight UTC
    ts = datetime.strptime(date_str, "%Y-%m-%d") \
        .replace(tzinfo=pytz.UTC).isoformat()
    points.append({
        "measurement": "LactateThreshold",
        "time":        ts,
        "tags":        {"Device": GARMIN_DEVICENAME},
        "fields": {
            "hr_lactate":   round(hr_target, 1),
            "pace_lactate": pace_str
        }
    })

    logging.info(f"LT HR≈{hr_target:.1f}, pace≈{avg_pace:.2f} min/km on {date_str}")
    return points


# %%
def fetch_activity_GPS(activityIDdict):
    points_list = []
    for activityID in activityIDdict.keys():
        try:
            root = ET.fromstring(
                garmin_obj.download_activity(activityID, dl_fmt=garmin_obj.ActivityDownloadFormat.TCX).decode("UTF-8"))
        except requests.exceptions.Timeout as err:
            logging.warning(f"Request timeout for fetching large activity record {activityID} - skipping record")
            return []
        ns = {"tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
              "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2"}
        for activity in root.findall("tcx:Activities/tcx:Activity", ns):
            activity_type = activityIDdict[activityID]
            activity_start_time = datetime.fromisoformat(activity.find("tcx:Id", ns).text.strip("Z"))
            lap_index = 1
            for lap in activity.findall("tcx:Lap", ns):
                lap_start_time = datetime.fromisoformat(lap.attrib.get("StartTime").strip("Z"))
                for tp in lap.findall(".//tcx:Trackpoint", ns):
                    time_obj = datetime.fromisoformat(tp.findtext("tcx:Time", default=None, namespaces=ns).strip("Z"))
                    lat = tp.findtext("tcx:Position/tcx:LatitudeDegrees", default=None, namespaces=ns)
                    lon = tp.findtext("tcx:Position/tcx:LongitudeDegrees", default=None, namespaces=ns)
                    alt = tp.findtext("tcx:AltitudeMeters", default=None, namespaces=ns)
                    dist = tp.findtext("tcx:DistanceMeters", default=None, namespaces=ns)
                    hr = tp.findtext("tcx:HeartRateBpm/tcx:Value", default=None, namespaces=ns)
                    speed = tp.findtext("tcx:Extensions/ns3:TPX/ns3:Speed", default=None, namespaces=ns)

                    try:
                        lat = float(lat)
                    except:
                        lat = None
                    try:
                        lon = float(lon)
                    except:
                        lon = None
                    try:
                        alt = float(alt)
                    except:
                        alt = None
                    try:
                        dist = float(dist)
                    except:
                        dist = None
                    try:
                        hr = float(hr)
                    except:
                        hr = None
                    try:
                        speed = float(speed)
                    except:
                        speed = None

                    point = {
                        "measurement": "ActivityGPS",
                        "time": time_obj.isoformat(),
                        "tags": {
                            "Device": GARMIN_DEVICENAME,
                            "ActivityID": activityID,
                            "ActivitySelector": activity_start_time.strftime('%Y%m%dT%H%M%SUTC-') + activity_type
                        },
                        "fields": {
                            "ActivityName": activity_type,
                            "ActivityID": activityID,
                            "Latitude": lat,
                            "Longitude": lon,
                            "Altitude": alt,
                            "Distance": dist,
                            "HeartRate": hr,
                            "Speed": speed,
                            "lap": lap_index
                        }
                    }
                    points_list.append(point)

                lap_index += 1
        logging.info(f"Success : Fetching TCX details for activity with id {activityID}")
    return points_list


# %%
def daily_fetch_write(date_str):
    write_points_to_influxdb(get_daily_stats(date_str))
    write_points_to_influxdb(get_sleep_data(date_str))
    write_points_to_influxdb(get_intraday_steps(date_str))
    write_points_to_influxdb(get_intraday_hr(date_str))
    write_points_to_influxdb(get_intraday_stress(date_str))
    write_points_to_influxdb(get_intraday_br(date_str))
    write_points_to_influxdb(get_intraday_hrv(date_str))
    write_points_to_influxdb(get_body_composition(date_str))
    activity_summary_points_list, activity_with_gps_id_dict = get_activity_summary(date_str)
    write_points_to_influxdb(activity_summary_points_list)
    write_points_to_influxdb(fetch_activity_GPS(activity_with_gps_id_dict))
    write_points_to_influxdb(get_training_load(date_str))
    write_points_to_influxdb(get_vo2max(date_str))
    write_points_to_influxdb(get_activity_vo2(date_str))
    write_points_to_influxdb(get_vo2max_segmented(date_str))
    write_points_to_influxdb(get_training_readiness(date_str))
    write_points_to_influxdb(get_lactate_threshold(date_str))


# %%
def fetch_write_bulk(start_date_str, end_date_str):
    global garmin_obj
    logging.info("Fetching data for the given period in reverse chronological order")
    time.sleep(3)
    write_points_to_influxdb(get_last_sync())
    for current_date in iter_days(start_date_str, end_date_str):
        repeat_loop = True
        while repeat_loop:
            try:
                daily_fetch_write(current_date)
                logging.info(
                    f"Success : Fetched all available health metrics for date {current_date} (skipped any if unavailable)")
                logging.info(f"Waiting : for {RATE_LIMIT_CALLS_SECONDS} seconds")
                time.sleep(RATE_LIMIT_CALLS_SECONDS)
                repeat_loop = False
            except GarminConnectTooManyRequestsError as err:
                logging.error(err)
                logging.info(
                    f"Too many requests (429) : Failed to fetch one or more matrices - will retry for date {current_date}")
                logging.info(f"Waiting : for {FETCH_FAILED_WAIT_SECONDS} seconds")
                time.sleep(FETCH_FAILED_WAIT_SECONDS)
                repeat_loop = True
            except (
                    GarminConnectConnectionError,
                    requests.exceptions.HTTPError,
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                    GarthHTTPError
            ) as err:
                logging.error(err)
                logging.info(f"Connection Error : Failed to fetch one or more matrices - skipping date {current_date}")
                logging.info(f"Waiting : for {RATE_LIMIT_CALLS_SECONDS} seconds")
                time.sleep(RATE_LIMIT_CALLS_SECONDS)
                repeat_loop = False
            except GarminConnectAuthenticationError as err:
                logging.error(err)
                logging.info(
                    f"Authentication Failed : Retrying login with given credentials (won't work automatically for MFA/2FA enabled accounts)")
                garmin_obj = garmin_login()
                time.sleep(5)
                repeat_loop = True


# %%
garmin_obj = garmin_login()

# %%
if MANUAL_START_DATE:
    fetch_write_bulk(MANUAL_START_DATE, MANUAL_END_DATE)
    logging.info(
        f"Bulk update success : Fetched all available health metrics for date range {MANUAL_START_DATE} to {MANUAL_END_DATE}")
    exit(0)
else:
    try:
        last_influxdb_sync_time_UTC = pytz.utc.localize(datetime.strptime(
            list(influxdbclient.query(f"SELECT * FROM HeartRateIntraday ORDER BY time DESC LIMIT 1").get_points())[0][
                'time'], "%Y-%m-%dT%H:%M:%SZ"))
    except:
        logging.warning(
            "No previously synced data found in local InfluxDB database, defaulting to 7 day initial fetching. Use specific start date ENV variable to bulk update past data")
        last_influxdb_sync_time_UTC = (datetime.today() - timedelta(days=7)).astimezone(pytz.timezone("UTC"))

    while True:
        last_watch_sync_time_UTC = datetime.fromtimestamp(
            int(garmin_obj.get_device_last_used().get('lastUsedDeviceUploadTime') / 1000)).astimezone(
            pytz.timezone("UTC"))
        if last_influxdb_sync_time_UTC < last_watch_sync_time_UTC:
            logging.info(f"Update found : Current watch sync time is {last_watch_sync_time_UTC} UTC")
            fetch_write_bulk(last_influxdb_sync_time_UTC.strftime('%Y-%m-%d'),
                             last_watch_sync_time_UTC.strftime('%Y-%m-%d'))
            last_influxdb_sync_time_UTC = last_watch_sync_time_UTC
        else:
            logging.info(f"No new data found : Current watch and influxdb sync time is {last_watch_sync_time_UTC} UTC")
        logging.info(f"waiting for {UPDATE_INTERVAL_SECONDS} seconds before next automatic update calls")
        time.sleep(UPDATE_INTERVAL_SECONDS)
