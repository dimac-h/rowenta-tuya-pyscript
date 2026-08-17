import tinytuya
from datetime import datetime, time as dtime

# --- EDIT ME: your device's local Tuya credentials ---
# Get these with the tinytuya wizard (see README) or your own local-Tuya setup.
DEVICE_ID = "YOUR_DEVICE_ID"
LOCAL_KEY = "YOUR_LOCAL_KEY"
DEVICE_IP = "192.168.1.XXX"

# --- EDIT ME: when your vacuum is scheduled to clean ---
# Only used to avoid polling the device outside of cleaning runs.
# weekday(): Mon=0 ... Sun=6. Each entry is (days, start, end).
CLEANING_WINDOWS = [
    ({0, 3}, dtime(10, 0), dtime(11, 0)),  # Mon & Thu, 10:00-11:00
    ({5}, dtime(16, 0), dtime(17, 0)),     # Sat, 16:00-17:00
]


def _in_cleaning_window(now):
    for days, start, end in CLEANING_WINDOWS:
        if now.weekday() in days and start <= now.time() < end:
            return True
    return False


@pyscript_compile
def _poll_device():
    d = tinytuya.Device(DEVICE_ID, DEVICE_IP, LOCAL_KEY)
    d.set_version(3.3)
    return d.status()


@pyscript_compile
def _send_return_home():
    d = tinytuya.Device(DEVICE_ID, DEVICE_IP, LOCAL_KEY)
    d.set_version(3.3)
    d.set_value(3, True)


@pyscript_compile
def _send_reset_map():
    d = tinytuya.Device(DEVICE_ID, DEVICE_IP, LOCAL_KEY)
    d.set_version(3.3)
    d.set_value(13, True)


# Runs on every pyscript (re)start, plus a weekly safety-net poll.
# state.set() sensors are not persisted across restarts, so without the
# "startup" trigger they'd stay "unavailable" until the next cron fire.
@time_trigger("startup", "cron(0 8 * * 1)")
@service
def poll_rowenta_vacuum():
    result = task.executor(_poll_device)
    dps = result.get("dps") if result else None
    if not dps:
        log.warning(f"Rowenta vacuum: no response from {DEVICE_IP}, skipping this poll")
        return
    state.set("sensor.rowenta_edge_brush_life", dps.get("17"), {"unit_of_measurement": "min", "icon": "mdi:broom"})
    state.set("sensor.rowenta_roller_brush_life", dps.get("19"), {"unit_of_measurement": "min", "icon": "mdi:broom"})
    state.set("sensor.rowenta_filter_life", dps.get("21"), {"unit_of_measurement": "min", "icon": "mdi:air-filter"})
    state.set("sensor.rowenta_cistern_level", dps.get("10"), {"icon": "mdi:water"})
    state.set("sensor.rowenta_total_clean_area", dps.get("29"), {"unit_of_measurement": "m2", "icon": "mdi:floor-plan"})
    state.set("sensor.rowenta_total_clean_time", dps.get("31"), {"unit_of_measurement": "min", "icon": "mdi:clock-outline"})


# Polls the vacuum's live status DP once a minute, but only inside
# CLEANING_WINDOWS above, so it stays quiet ~166 hours out of every week.
@time_trigger("period(now, 1min)")
def poll_rowenta_status():
    if not _in_cleaning_window(datetime.now()):
        return
    result = task.executor(_poll_device)
    dps = result.get("dps") if result else None
    if not dps:
        log.warning(f"Rowenta vacuum: no response from {DEVICE_IP}, skipping status poll")
        return
    state.set("sensor.rowenta_status", dps.get("5"), {"icon": "mdi:robot-vacuum"})


@service
def rowenta_return_home():
    task.executor(_send_return_home)


@service
def rowenta_reset_map():
    task.executor(_send_reset_map)
