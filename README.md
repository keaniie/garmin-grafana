

<p align="center">
<img src="https://i.imgur.com/PYsbwqj.png" width="450" height="164" align="center">
</p>

# Garmin Grafana

A docker container to fetch data from Garmin servers and store the data in a local influxdb database for appealing visualization with Garfana.

> [!TIP]
> If you are a **Fitbit user**, please check out the [sister project](https://github.com/arpanghosh8453/fitbit-grafana) made for Fitbit

## Dashboard Example

![Dashboard](https://github.com/arpanghosh8453/garmin-grafana/blob/main/Grafana_Dashboard/Garmin-Grafana-Dashboard-Preview.png?raw=true)

## Features

- Automatic data collection from Garmin
- Collects comprehensive health metrics including:
  - Heart Rate Data
  - Hourly steps Heatmap
  - Daily Step Count
  - Sleep Data and patterns (SpO2, Breathing rate, Sleep movements, HRV)
  - Sleep regularity heatmap (Visualize sleep routine)
  - Stress Data 
  - Body Battery data
  - Calories
  - Sleep Score
  - Activity Minutes and HR zones
  - Activity Timeline (workouts)
  - GPS data from workouts (track, pace, altitude, HR)
  - And more...
- Automated data fetching in regular interval (set and forget)
- Historical data backfilling

## Why use this project?

- **Free and Fully Open Source**: 100% transparent and open project — modify, distribute extend, and self-host as you wish, with no hidden costs. Just credit the author and support this project as you please!

- **Local Ownership**: Keep a complete, private backup of your Garmin data. The script automatically syncs new data after each Garmin Connect upload — no manual action needed ("set and forget").

- **Full Visualization Freedom**: You're not limited by Garmin’s app. Combine multiple metrics on a single panel, zoom into specific time windows, view raw (non-averaged) data over days or weeks, and build fully custom dashboards.

- **Deeper Insights - All day metrics**: Explore your data to discover patterns, optimize performance, and track trends over longer periods of time. Export for advanced analysis (Python, Excel, etc.) from Grafana, set custom alerts, or create new personalized metrics. This project fetches _almost_ everything from your Garmin watch - not just limited to Activities analytics like most other online platforms 

- **No 3rd party data sharing**: You avoid sharing your sensitive health related data with any 3rd party service provider while having a great data visualization platform for free!

## Automatic Install with helper script (Recommended For less techy people)

> [!IMPORTANT]
> This script is for initial setup only. if you already have used it or followed the manual setup to deploy this project, you should not run this again once the garminconnect OAuth tokens are saved (first successful data fetch). Please check the `update to new versions` section for upgrading the container(s).

> [!TIP]
> If you are getting some errors you can't figure out, give the almighty [ChatGPT](https://chat.openai.com/) as try, it's often known to be helpful troubleshooting issues with this project and script. 

This script requires a linux environment. If Docker is not installed on your Linux/MacOS system, follow the instructions to [install docker manually](https://docs.docker.com/engine/install/) on Linux. There is also an [automated docker installation script](https://github.com/docker/docker-install) available using the one-liner command `curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh`.

If you are on `Windows` you should consider using [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) to get a linux sub-system up and running.

#### Detailed steps for Windows users are as follows:

- [Install docker desktop](https://docs.docker.com/get-started/introduction/get-docker-desktop/)
- Install WSL and Ubuntu from the Micorosft store
- Start -> Run -> type `WSL.exe`, Follow the prompts to create your Linux sudo (admin) user and password
- Open docker desktop to agree to the EULA
- Reboot your machine
- Once back up, WSL and Docker should be installed and linked together.
- Start -> Run -> type `WSL.exe`,then run the below bash command

For Linux or MacOS, simply run the following bash command from your linux command line (terminal).

You may need to run the script with `sudo` (linux administrator) privilages or it may fail due to some permission error.

```bash
cd ~ && git clone https://github.com/arpanghosh8453/garmin-grafana.git garmin-grafana && cd garmin-grafana && sudo bash ./easy-install.sh
```  

Enter the Garmin Connect credentials when prompted and you should be all up and running (your will be prompted for 2FA code as well if you have that set up). Once the data keeps coming, you can check out the `http://localhost:3000` to reach Grafana (by default), do the initial setup with the default username `admin` and password `admin`. Check out the dashboards link on the left sidebar. you should have a dashboard auto-configured as `Garmin-Stats` under the dashboards section. There you should see the data added. It will **keep updating automatically** as soon as new data syncs with your Garmin Connect account.

> [!NOTE]
> When you run this for the first time, it will only automatically fetch the data for **last 7 days** only and keep pulling new data that syncs with Garmin Connect moving forward. if you want to sync your older data, that is super easy to do. You just need the run the following command in the terminal replacing the YYYY-MM-DD with appropriate start and end dates (MANUAL_START_DATE value must be older than MANUAL_END_DATE value) 
>
> ```bash
> docker compose run --rm -e MANUAL_START_DATE=YYYY-MM-DD -e MANUAL_END_DATE=YYYY-MM-DD garmin-fetch-data
> ```

That should be everything you need for now! 

## Manual Install with Docker (Recommended if you understand linux concepts)

> [!IMPORTANT]
> Install docker if you don't have it already. Docker is supported in all major platforms/OS. Please check the [docker installation guide](https://docs.docker.com/engine/install/). You can install it on Windows via WSL, on Unraid via Docker Compose plugin, on Proxmox via Docker-LXC, and natively on Linux and Mac.

1. Clone this repository with the command `git clone https://github.com/arpanghosh8453/garmin-grafana.git`. Change your working directory with `cd garmin-grafana`. Then create a folder named `garminconnect-tokens` inside the current folder (`garmin-grafana`) with the command `mkdir garminconnect-tokens`. Run `chown -R 1000:1000 garminconnect-tokens` to change the ownership of the garminconnect-tokens folder (so the `garmin-fetch-data` container's internal user can use it to store the Authentication tokens). You can also run `chmod -R 777 garminconnect-tokens` to make the folder generally available for every user on the system if you keep getting `PermissionError` during script execution. Cloning this repository allows you to maintain the forder and files structure, and allows you to use Grafana self-privisioning database.

2. Create an empty `compose.yml` file inside the current `garmin-grafana` folder with the content of the given [compose-example.yml](./compose-example.yml) or simply rename the present `compose-example.yml` file to `compose.yml` with `mv compose-example.yml compose.yml` ( Change the environment variables inside according to instructions )

3. You can use two additional environment variables `GARMINCONNECT_EMAIL` and `GARMINCONNECT_BASE64_PASSWORD` to add the login information directly. otherwise you will need to enter them in the initial setup phase when prompted. If you are not using these environment variables to pass your garmin Connect login informations, you must remove them altogether (remove the full lines including the variable names or comment out with a `#` in front of the variable names - as done in the example be default) from the compose file - leaving them to placeholder values or empty values might lead to invalid login attempt and possibily `401 Client Error`. Please note that here the password must be encoded with [Base64](http://base64encode.org/) when using the `GARMINCONNECT_BASE64_PASSWORD` ENV variable. This is to ensure your Garmin Connect password is not in plaintext in the compose file. The script will decode it and use it when required. If you set these two ENV variables and do not have two factor authentication (via SMS or email), you can directly jump to `step 5`. If you are in mainland China and use Garmin-cn account you need to set `GARMINCONNECT_IS_CN=True`

> [!NOTE]
> If you are planning to use Influxdb V3, you need to enter the admin access token in `INFLUXDB_V3_ACCESS_TOKEN`. To generate the admin token you should run `docker exec influxdb influxdb3 create token --admin` command. This will give you the admin token which you must update to `INFLUXDB_V3_ACCESS_TOKEN` ENV variable. You can do this only once and the token can't be viewed or retrieved ever again (influxdb only stores a hash of it in the database for comparison). So please store this token carefully. 

4. If you did not set up the email and password ENV variables or have 2FA enabled, you must run the following command first to get the Email, password and 2FA code prompt interactively: `docker pull thisisarpanghosh/garmin-fetch-data:latest && docker compose run --rm garmin-fetch-data`. Enter the Email, Password (the characters will be visible when you type to avoid confusion, so find some privacy. If you paste the password, make sure there is no trailing space or unwanted characters), and 2FA code (if you have that enabled). Once you see the successful authentication message, you are good to go. The script will exit on it's own prompting you to restart the script (follow next step). This will automatically remove this orphan container as this was started with the `--rm` flag. You need to login like this **only once**. The script will [save the session Authentication tokens](https://github.com/cyberjunky/python-garminconnect/issues/213#issuecomment-2213292471) in the container's internal `/home/appuser/.garminconnect` folder for future use. That token can be used for all the future requests as long as it's valid (expected session token lifetime is about [one year](https://github.com/cyberjunky/python-garminconnect/issues/213), as Garmin seems to use long term valid access tokens instead of short term valid {access token + refresh token} pairs). This helps in reusing the authentication without logging in every time when the container starts, as that leads to `429 Client Error`, when login is attempted repeatedly from the same IP address. If you run into `429 Client Error` during your first login attempt with this script, please refer to the troubleshooting section below. 

> [!TIP]
> You can un-comment the line `# user: root` in the `compose.yml` file to run the container as root (superuser) - this will resolve any permission error or read/write issue you are encountering. Use this if the above `chown` or `chmod` did not work for you and you keep getting the `Permission Error` during running this initial setup. If you do this, you must change the compose volume mount from `./garminconnect-tokens:/home/appuser/.garminconnect` to `./garminconnect-tokens:/root/.garminconnect` so that the token files are preserved when you take down the containers with `docker compose down` for restarting or rebuilding. 

5. If you are using self provisioning provided with this project for Grafana setup, then you should run `sed -i 's/\${DS_GARMIN_STATS}/garmin_influxdb/g' Grafana_Dashboard/Garmin-Grafana-Dashboard.json` (assuming you are currently in the root garmin-grafana directory) to update the placeholder variable name `${DS_GARMIN_STATS}` (for supporting external import) in the dashboard JSON to static `garmin_influxdb` as it is the uid set during the self provisioning of the dashboard. 
   
6. Finally run : `docker compose up -d` ( to launch the full stack in detached mode ). Thereafter you should check the logs with `docker compose logs --follow` to see any potential error from the containers. This will help you debug the issue, if there is any (specially read/write permission issues). if you are using docker volumes, there are little chance of this happending as file permissions will be managed by docker. For bind mounts, if you are having permission issues, please check the troubleshooting section.

7. Now you can check out the `http://localhost:3000` to reach Grafana (by default), do the initial setup with the default username `admin` and password `admin`. If you have cloned the repository as instructed in step 1, and using self-provisioning for the grafana dashboards + databases, then you should have a automatic dashboard setup under the Dashboards section named as `Garmin-Grafana`filled with data! - and you are done!. 
  
8. if you are not using self-provisioning, then you need to manually add influxdb as the data source and continue follow the rest of these instructions. Please note the influxdb hostname is set as `influxdb` with port `8086` so you should use `http://influxdb:8086` for the address during data source setup and not `http://localhost:8086` because influxdb is a running as a separate container but part of the same docker network and stack. Here the database name should be `GarminStats` matching the influxdb DB name from the docker compose. The query language used for the dashboard is `influxql` which is supported by both InfluxDB 1.x and 3.x, so please select that from the language dropdown during setup. Use the same username and password you used for your influxdb container (check your docker compose config for influxdb container, here we used `influxdb_user` and `influxdb_secret_password` in default configuration) Test the connection to make sure the influxdb is up and reachable (you are good to go if it finds the measurements when you test the connection)

9. To use the Grafana dashboard with manual import, please use the [JSON file](https://github.com/arpanghosh8453/garmin-grafana/blob/main/Grafana_Dashboard/Garmin-Grafana-Dashboard.json) downloaded directly from GitHub or use the import code **23245** to pull them directly from the Grafana dashboard cloud. In the Grafana dashboard, the heatmap panels require an additional plugin that you must install. This can be done by using the `GF_PLUGINS_PREINSTALL=marcusolsson-hourly-heatmap-panel` environment variable like in the [compose-example.yml](./compose-example.yml) file, or after the creation of the container very easily with docker commands. Just run `docker exec -it grafana grafana cli plugins install marcusolsson-hourly-heatmap-panel` and then run `docker restart grafana` to apply that plugin update. Now, you should be able to see the Heatmap panels on the dashboard loading successfully.

> [!NOTE]
> When you run this for the first time, it will only automatically fetch the data for **last 7 days** only and keep pulling new data that syncs with Garmin Connect moving forward. In order to sync back older data, use the following command replacing the YYYY-MM-DD with appropriate start and end dates (MANUAL_START_DATE value must be older than MANUAL_END_DATE value) 
>
> ```bash
> docker compose run --rm -e MANUAL_START_DATE=YYYY-MM-DD -e MANUAL_END_DATE=YYYY-MM-DD garmin-fetch-data
> ```

If you have come this far, everything should be working. If not, please check the **troubleshooting section** for known issues. If it is already working, **CONGRATULATIONS!**. Enjoy your dashboard and keep exercising!. If you like the dashboard and my sincere effort behind it, please **star this repository**. If you enjoy it a lot and want to show your appreciation and share the joy with me, feel free to [buy me a coffee](https://ko-fi.com/A0A84F3DP). Maintaining this project takes a lot of my free time and your support keeps me motivated to develop more features for the community and spend more time on similar projects. if you are having any trouble, feel free to open an issue here, I will try my best to help you!

---

This project is made for InfluxDB 1.11, as Flux queries on influxDB 2.x can be problematic to use with Grafana at times. In fact, InfluxQL is being reintroduced in InfluxDB 3.0, reflecting user feedback. Grafana also has better compatibility/stability with InfluxQL from InfluxDB 1.11. Moreover, there are statistical evidence that Influxdb 1.11 queries run faster compared to influxdb 2.x. Since InfluxDB 2.x offers no clear benefits for this project, there are no plans for a migration.

Support of current [Influxdb 3](https://docs.influxdata.com/influxdb3/core/) OSS is also available with this project [ `Experimental` ]

> [!IMPORTANT]
> Please note that InfluxDB 3.x OSS limits the query time limit to 72 hours. This can be extended more by setting `INFLUXDB3_QUERY_FILE_LIMIT` to a very high value with a potential risk of crashing the container (OOM Error). As we are interested in visualization long term data trends, this limit defeats the purpose. Hence, we strongly recommend using InfluxDB 1.11.x (default settings) to our users as long as it's not discontinued from production. 

Example `compose.yml` file contents is given here for a quick start.

> [!TIP]
> The Docker image is also available as `ghcr.io/arpanghosh8453/garmin-fetch-data:latest` alongside `thisisarpanghosh/garmin-fetch-data:latest`.

```yaml
services:
  garmin-fetch-data:
    restart: unless-stopped
    image: thisisarpanghosh/garmin-fetch-data:latest
    container_name: garmin-fetch-data
    # user: root # Runs the container as root user, uncomment this line if you are getting permission issues which can't be resolved otherwise For this, you also need to change the below volume mount from './garminconnect-tokens:/home/appuser/.garminconnect' to './garminconnect-tokens:/root/.garminconnect' to ensure the token files persist during container rebuilding. 
    depends_on:
      - influxdb
    volumes:
      - ./garminconnect-tokens:/home/appuser/.garminconnect # (persistent tokens storage - garminconnect-tokens folder must be owned by 1000:1000) - should be './garminconnect-tokens:/root/.garminconnect' instead if you are using user: root
    environment:
      - INFLUXDB_HOST=influxdb
      - INFLUXDB_PORT=8086 # Influxdb V3 maps to 8181 instead of 8086 of V1
      - INFLUXDB_USERNAME=influxdb_user # user should have read/write access to INFLUXDB_DATABASE (Required for influxdb 1.x, ignore for influxdb 3.x - set the 3.x specific variables)
      - INFLUXDB_PASSWORD=influxdb_secret_password # (Required for influxdb 1.x, ignore for influxdb 3.x - set the 3.x specific variables)
      - INFLUXDB_DATABASE=GarminStats
      - GARMINCONNECT_IS_CN=False # Set this to True if you are in mainland China or use Garmin-cn (Default False)
      #####################################################################################
      # - GARMINCONNECT_EMAIL=your_garminconnect_email # optional, read the setup docs. (remove or comment out this line altogether if not used)
      # - GARMINCONNECT_BASE64_PASSWORD=your_base64_encoded_garminconnect_password # optional, must be Base64 encoded, read setup docs. (remove or comment out this line altogether if not used)
      #####################################################################################
      # The following ENV variables are required only if you are using influxdb V3 (You won't have to set the above )
      #####################################################################################
      # - INFLUXDB_VERSION=1 # Required for influxdb V3, Default is 1, must be overridden with 3 if using Influxdb V3
      # - INFLUXDB_V3_ACCESS_TOKEN=your_influxdb_admin_access_token # Required for influxdb V3 (ignored for V1), Set this to your admin access token (or a token that has database R/W access) - You can generate this by following step 3 notes in the README instructions
      #####################################################################################
      # The following ENV variables will override some default settings. 
      # Please read the README guide before using them as they may change how the script behaves
      #####################################################################################
      # - LOG_LEVEL=INFO # change to DEBUG to get DEBUG logs
      # - UPDATE_INTERVAL_SECONDS=300 # Default update check interval is set to 5 minutes
      # - FETCH_ADVANCED_TRAINING_DATA=False # This enables fetching additional data : Training Readiness, Hill score and Endurance score as available when set to True
      # - KEEP_FIT_FILES=False # Stores the FIT files (downloads and saves them) when set to True - read docs for more details
      # - ALWAYS_PROCESS_FIT_FILES=False # Enables processing FIT files even if GPS data is not present in it when set to True, default False
      # - USER_TIMEZONE="" # Can hardcode user's timezone, fetches timezone automatically and dynamically on each run if set to empty (default) - Read docs
      # - INFLUXDB_ENDPOINT_IS_HTTP=True # Set this to False if you are using HTTPS for your influxdb connection (over the internet)
      # - FORCE_REPROCESS_ACTIVITIES=True # Enables re-processing of FIT files on iterative updates when set to True (default), setting to False may save processing time but known for skipping activities

  influxdb:
    restart: unless-stopped
    container_name: influxdb
    hostname: influxdb
    environment:
      - INFLUXDB_DB=GarminStats
      - INFLUXDB_USER=influxdb_user
      - INFLUXDB_USER_PASSWORD=influxdb_secret_password
      - INFLUXDB_DATA_INDEX_VERSION=tsi1
      #############################################################
      # The following ENV variables are applicable for InfluxDB V3
      #############################################################
      # - INFLUXDB3_MAX_HTTP_REQUEST_SIZE=10485760
      # - INFLUXDB3_NODE_IDENTIFIER_PREFIX=Influxdb-node1
      # - INFLUXDB3_BUCKET=GarminStats
      # - INFLUXDB3_OBJECT_STORE=file
      # - INFLUXDB3_DB_DIR=/data
      # - INFLUXDB3_QUERY_FILE_LIMIT=5000 # this set to be a very high value if you want to view long term data
    expose:
      - '8086' # Influxdb V3 should expose "8181" (Change INFLUXDB_PORT on garmin-fetch-data appropriately for InfluxDB V3)
    volumes:
      - influxdb_data:/var/lib/influxdb # InfluxDB V3 bind mount should be set like - influxdb_data:/data if you set INFLUXDB3_DB_DIR=/data (instead of /var/lib/influxdb)
    image: 'influxdb:1.11' # You must change this to 'quay.io/influxdb/influxdb3-core:latest' for influxdb V3

  grafana:
    restart: unless-stopped
    container_name: grafana
    hostname: grafana
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_PLUGINS_PREINSTALL=marcusolsson-hourly-heatmap-panel
    volumes:
      - grafana_data:/var/lib/grafana
      - ./Grafana_Datasource:/etc/grafana/provisioning/datasources # (optional) Self provisioning influxdb datasource
      - ./Grafana_Dashboard:/etc/grafana/provisioning/dashboards # (optional) self provisioning grafana dashboard
    ports:
      - '3000:3000'
    image: 'grafana/grafana:latest'

volumes:
  influxdb_data:
  grafana_data:

```
### Additional configuration and environment variables

✅ The Above compose file creates an open read/write access influxdb database with no authentication. Unless you expose this database to the open internet directly, this poses no threat. If you share your local network, you may enable authentication and grant appropriate read/write access to the influxdb_user on the GarminStats database manually if you want with `INFLUXDB_ADMIN_ENABLED`, `INFLUXDB_ADMIN_USER`, and `INFLUXDB_ADMIN_PASSWORD` ENV variables during the setup by following the [influxdb guide](https://github.com/docker-library/docs/blob/master/influxdb/README.md) but this won't be covered here for the sake of simplicity.

✅ You can also enable additional advanced training data fetching with `FETCH_ADVANCED_TRAINING_DATA=True` flag in the compose file. This will fetch and store data such as training readiness, hill score, VO2 max, and Race prediction if you have them available on Garmin connect. The implementations of this should work fine in theory but not thoroughly tested. This is currently an experimental feature. There is no panel showing these data on the provided grafana dashboard. You must create your own to visualize these on Grafana.

✅ By default, the pulled FIT files are not stored as files to save storage space during import (an in-memory IO buffer is used instead). If you want to keep the FIT files downloaded during the import for future use in `Strava` or any other application where FIT files are supported for import, you can turn on `KEEP_FIT_FILES=True` under `garmin-fetch-data` environment variables in the compose file. To access the files from the host machine, you should create a folder named `fit_filestore` with `mkdir fit_filestore` inside the `garmin-fetch-data` folder (where your compose file is currently located) and change the ownership with `chown 1000:1000 fit_filestore`, and then must setup a volume bind mount like this `./fit_filestore:/home/appuser/fit_filestore` under the volumes section of `garmin-fetch-data`. This would map the container's internal `/home/appuser/fit_filestore` folder to the `fit_filestore` folder you created. You will see the FIT files for your activities appear inside this `fit_filestore` folder once the script starts running.

✅ By default indoor activities FIT files lacking GPS data are not processed (Activity summaries are processed for all activities, just not the detailed intra-activity HR, Pace etc. which are included only inside the FIT files and require additional processing power) to save resources and processing time per fetched activity. If you want to process all activities regardless of GPS data availabliliy associated with the activity, you can set `ALWAYS_PROCESS_FIT_FILES=True` in the environment variables section of the `garmin-fetch-data` container as that will ensure all FIT files are processed irrespective of GPS data availability with the activities.  

✅ If you are having missing data on previous days till midnight (which are available on Garmin Connect but missing on dashboard) or sync issues when using the automatic periodic fetching, consider updating the container to recent version and use `USER_TIMEZONE` environment variable under the `garmin-fetch-data` service. This variable is optional and the script tries to determine the timezone and fetch the UTC offset automatically if this variable is set as empty. If you see the automatic identification is not working for you, this variable can be used to override that behaviour and ensures the script is using the hardcoded timezone for all data fetching related activities. The previous gaps won't be filled (you need to fetch them using historic bulk update method), but moving forward, the script will keep everything in sync. 

✅ Want this dashboard in **Imperial units** instead of **metric units**? I can't maintain two separate dashboards at the same time but here is an [excellent step-by-step guide](https://github.com/arpanghosh8453/garmin-grafana/issues/27#issuecomment-2817081738) on how you can do it yourself on your dashboard!

## Collecting periodic watch battery levels

Unfortunately, Garmin Connect does not sync the device battery level (possibly due to infrequent passive syncing intervals). Hence, it's not possible to get the watch's battery data directly using this setup. However, I have found an alternative, which requires a lot of additional setup (out of the scope for this project - but I will give a brief walkthrough). 

You will need a self-hosted/cloud instance of [homeassistant](https://www.home-assistant.io/) and [GarminHomeAssistant (Watch Application) from Connect IQ](https://apps.garmin.com/en-US/apps/61c91d28-ec5e-438d-9f83-39e9f45b199d). Detailed installation instructions are [available here](https://github.com/house-of-abbey/GarminHomeAssistant). This application is Free and open source as well just like this project, and the maintainer is very supportive! 

After you install it, you need to enable the battery level and other stats collection (background running) in the application settings on Connect IQ. You will see the battery level history on HomeAssistant entities panel (appearing as `sensor.garmin_device_battery_level`) thereafter. If you want to integrate this data to the InfluxDB database and Grafana dashboard you have with this project, you need to add an additional InfluxDB addon configuration in the `configuration.yaml` file of HomeAssistant installation like following. 

```yaml
influxdb:
  host: influxdb
  port: 8086
  database: GarminStats
  username: influxdb_user
  password: influxdb_secret_password
  ssl: false
  verify_ssl: false
  max_retries: 3
  include:
    entities:
       - sensor.garmin_device_battery_level
  tags:
    source: hass
```
There is a Grafana panel in the dashboard (given with this project) which displays this data when available. If you do not have this setup, you should remove that panel from the dashboard, as battery data collection is not possible from the watch otherwise.  

## Historical data fetching (bulk update)

> [!TIP]
> Please note that this process is intentionally rate limited with a 5 second wait period between each day update to ensure the Garmin servers are not overloaded with requests when using bulk update. You can update the value with `RATE_LIMIT_CALLS_SECONDS` ENV variable in the `garmin-fetch-data` container, but lowering it is not recommended, 

#### Procedure

1. Please run the above docker based installation steps `1` to `4` first (to set up the Garmin Connect login session tokens if not done already).

2. Stop the running container and remove it with `docker compose down` if running already

3. Run command `docker compose run --rm -e MANUAL_START_DATE=YYYY-MM-DD -e MANUAL_END_DATE=YYYY-MM-DD garmin-fetch-data` to update the data between the two dates. You need to replace the `YYYY-MM-DD` with the actual dates in that format, for example `docker compose run --rm -e MANUAL_START_DATE=2025-04-12 -e MANUAL_END_DATE=2025-04-14 garmin-fetch-data`. The `MANUAL_END_DATE` variable is optional, if not provided, the script assumes it to be the current date. `MANUAL_END_DATE` must be in future to the `MANUAL_START_DATE` variable passed, and in case they are same, data is still pulled for that specific date. 

4. Please note that the bulk data fetching is done in **reverse chronological order**. So you will have recent data first and it will keep going back until it hits `MANUAL_START_DATE`. You can have this running in background. If this terminates after some time unexpectedly, you can check back the last successful update date from the container stdout logs and use that as the `MANUAL_END_DATE` when running bulk update again as it's done in reverse chronological order.

4. After successful bulk fetching, you will see a `Bulk update success` message and the container will exit and remove itself automatically. 

5. Now you can run the regular periodic update with `docker compose up -d`

## Update to new versions

Updating with docker is super simple. Just go to the folder where the `compose.yml` is and run `docker compose pull` and then `docker compose down && docker compose up -d`. Please verify if everything is running correctly by checking the logs with `docker compose logs --follow`

> [!CAUTION]
> If you run `docker compose down -v`, that (using the `-v` flag) will purge the persistant docker volumes for the influxdb (if you are using docker volumes - default setup) which will wipe out all the data and databases stored in the influxdb container. Please be careful about this action but it can be useful if you want to start fresh wiping out the old database and container. This action cannot be undone. 

## Backup Database

Whether you are using a bind mount or a docker volume, creating a restorable archival backup of your valuable health data is always advised. Assuming you named your database as `GarminStats` and influxdb container name is `influxdb`, you can use the following script to create a static archival backup of your data present in the influxdb database at that time point. This restore points can be used to re-create the influxdb database with the archived data without requesting them from Garmin's servers again, which is not only time consuming but also resource intensive. 

```bash
#!/bin/bash
TIMESTAMP=$(date +%F_%H-%M)
BACKUP_DIR="./influxdb_backups/$TIMESTAMP"
mkdir -p "$BACKUP_DIR"
docker exec influxdb influxd backup -portable -db GarminStats /tmp/influxdb_backup
docker cp influxdb:/tmp/influxdb_backup "$BACKUP_DIR"
docker exec influxdb rm -r /tmp/influxdb_backup"
```

The above bash script would create a folder named `influxdb_backups` inside your current working directory and create a subfolder under it with current date-time. Then it will create the backup for `GarminStats` database and copy the backup files to that location. 

For restoring the data from a backup, you first need to make the files available inside the new influxdb docker container. You can use `docker cp` or volume bind mount for this. Once the backup data is available to the container internally, you can simply run `docker exec influxdb influxd restore -portable -db GarminStats /path/to/internal-backup-directory` to restore the backup.

Please read detailed guide on this from the [influxDB documentation for backup and restore](https://docs.influxdata.com/influxdb/v1/administration/backup_and_restore/)


## Troubleshooting

- The issued session token is apparently [valid only for 1 year](https://github.com/cyberjunky/python-garminconnect/issues/213) or less. Therefore, the automatic fetch will fail after the token expires. If you are using it more than one year, you may need to stop, remove and redeploy the container (follow the same instructions for initial setup, you will be asked for the username and password + 2FA code again). if you are not using MFA/2FA (SMS or email one time code), you can use the `GARMINCONNECT_EMAIL` and `GARMINCONNECT_BASE64_PASSWORD` (remember, this is [base64 encoded](http://base64encode.org/) password, not plaintext) ENV variables in the compose file to give this info directly, so the script will be able to re-generate the tokens once they expire. Unfortunately, if you are using MFA/2FA, you need to enter the one time code manually after rebuilding the container every year when the tokens expire to keep the script running (Once the session token is valid again, the script will automatically back-fill the data you missed)

- If you are getting `429 Client Error` after a few login tries during the initial setup, this is an indication that you are being rate limited based on your public IP. Garmin has a set limit for repeated login attempts from the same IP address to protect your account. You can wait for a few hours or a day, or switch to a different wifi network outside your home (will give you a new public IP) or just simply use mobile hotspot (will give you a new public IP as well) for the initial login attempt. This should work in theory as [discussed here](https://github.com/matin/garth/discussions/60).

- Running into `401 Client Error` when trying to login for the first time? make sure you are using the correct username and password for your account. If you enter it at runtime, it should be in plaintext but if you add it with environment variables in the docker compose stack, it must be [Base64 encoded](https://www.base64encode.org/). if you are 100% sure you are using the right credentials, and still get this error, it's probably due to the fact that you are connected to a VPN network which is preventing the log in request (see issue [#20](https://github.com/arpanghosh8453/garmin-grafana/issues/20)). If you are not using a VPN, then please try running the container with mobile hotspot network or with a VPN exit tunnel (both gives you a different public IP) - you need to try this from a different network somehow. 

- If you want to bind mount the docker volumes for the `garmin-fetch-data` container, please keep in mind that the script runs with the internal user `appuser` with uid and gid set as 1000. So please chown the bind mount folder accordingly as stated in the above instructions. Also, `grafana` container requires the bind mount folders to be owned by `472:472` and `influxdb:1.11` container requires the bind mount folders to be owned by `1500:1500`. If none of this solves the `Permission Denied` issue for you, you can change the bind mount folder permission as `777` with `chmod -R 777 garminconnect-tokens`. Another solutiuon could be to add `user: root` in the container configuration to run it as root instead of default `appuser` (this option has security considerations)

- If the Activities details (GPS, Pace, HR, Altitude) are not appearing on the dashboard, make sure to select an Activity listed on the top left conner of the Dashboard (In the `Activity with GPS` variable dropdown). If you see no values are available there, but in the log you see the activities are being pulled successfully, then it's due to a Grafana Bug. Go to the dashboard variable settings, and please ensure the correct datasource is selected for the variable and the query is set to `SHOW TAG VALUES FROM "ActivityGPS" WITH KEY = "ActivitySelector" WHERE $timeFilter`. Once you set this properly after the dashboard import, the values should show up correctly in the dropdown and you will be able to select specific Activity and view it's stats on the dashboard.

- Missing the battery levels data on the dashboard? Check out the section titled `Collecting periodic watch battery levels` to know how to set it up. 

## Credits

This project is made possible by **generous community contribution** towards the [gofundme](https://gofund.me/0d53b8d1) advertised in [this post](https://www.reddit.com/r/Garmin/comments/1jucwhu/update_free_and_open_source_garmin_grafana/) on Reddit's [r/garmin](https://www.reddit.com/r/Garmin) community. I wanted to build this tool for a long time, but funds were never sufficient for me to get a Garmin, because they are pretty expensive. With the community donations, I was able to buy a `Garmin Vivoactive 6` and built this tool open to everyone. if you are using this tool and enjoy it, please remember what made this possible! Huge shoutout to the [r/garmin](https://www.reddit.com/r/Garmin) community for being generous, trusting me and actively supporting my idea!

## Dependencies

- [python-garminconnect](https://github.com/cyberjunky/python-garminconnect) by [cyberjunky](https://github.com/cyberjunky) : Garmin Web API wrapper

- [garth](https://github.com/matin/garth) by [matin](https://github.com/matin) : Used for Garmin SSO Authentication

## Limitations

This project depends on Garmin cloud. This does not directly sync data from your watch. Your data syncs to Garmin cloud first, and then within the set interval, the script periodically fetches the data from the Garmin servers using the locally stored Oauth tokens. Implementing direct sync is quite tricky and it will unpair your current device and overtake the syncing activities. If there is any script or user error, this might cause permanent data loss. As this project do not come with any kind of liability or warranty, it falls on the user using this. If you are looking for direct sync from your watch, this project is not for you. You might look into the [Gargetbridge project](https://gadgetbridge.org/gadgets/wearables/garmin/), which might be able to accomplish this for you if you are ready to take full responsibility of your data. This direct sync feature is currently not in our roadmap. 

## Love this project?

I'm thrilled that you're using this dashboard. Your interest and engagement mean a lot to me! You can view and analyze more detailed health statistics with this setup than paying a connect+ subscription fee to Garmin.

Maintaining and improving this project takes a significant amount of my free time. Your support helps keep me motivated to add new features and work on similar projects that benefit the community.

If you find this project helpful, please consider:

⭐ Starring this repository to show your support and spread the news!

☕ [Buying me a coffee](https://ko-fi.com/A0A84F3DP) if you'd like to contribute to its maintenance and future development.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/A0A84F3DP)
<a href="https://www.buymeacoffee.com/arpandesign"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=✌️&slug=arpandesign&button_colour=5F7FFF&font_colour=ffffff&font_family=Inter&outline_colour=000000&coffee_colour=FFDD00" width=200 height=32 alt="Buy me a coffee"/></a>
<noscript><a href="https://liberapay.com/arpandesign/donate"><img alt="Donate using Liberapay" src="https://liberapay.com/assets/widgets/donate.svg"></a></noscript>

## Need Help?

If you're experiencing any issues with running this project or have questions, feel free to [open an issue](https://github.com/arpanghosh8453/garmin-grafana/issues/new/choose) on this repository. I'll do my best to assist you.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=arpanghosh8453/garmin-grafana&type=Date)](https://www.star-history.com/#arpanghosh8453/garmin-grafana&Date)
