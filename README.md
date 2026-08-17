# Rowenta/Tuya robot vacuum pyscript

A small [pyscript](https://github.com/custom-components/pyscript) script for Home Assistant that
talks **directly** to a local-Tuya robot vacuum (no cloud, no app) and exposes a few things the
stock Tuya/localtuya integrations usually don't give you:

- `sensor.rowenta_roller_brush_life`, `edge_brush_life`, `filter_life` (in minutes remaining)
- `sensor.rowenta_cistern_level`, `total_clean_area`, `total_clean_time`
- `sensor.rowenta_status` — the vacuum's live cleaning status, polled only during the time
  windows you actually care about (so it stays quiet the rest of the week)
- `pyscript.rowenta_return_home` and `pyscript.rowenta_reset_map` — services you can call from
  automations or the dashboard

It was written for a Rowenta X-Plorer robot vacuum, but the approach works for pretty much any
local-Tuya device — you'll just need to adjust the DP (data point) numbers for your own model.

## Why this exists

If you've set up `localtuya` and found that some device — especially robot vacuums — keeps
losing its connection and won't reconnect reliably, this is a workaround: instead of one
long-lived connection, this script opens a fresh, one-shot connection every time it needs data.
It's less real-time, but far more resilient in practice.

## Prerequisites

1. Home Assistant with the [pyscript](https://github.com/custom-components/pyscript) custom
   component installed (via HACS or manually).
2. Your device's **local key**, **device ID**, and **local IP**. The easiest way to get these is
   the [tinytuya](https://github.com/jasonacox/tinytuya) setup wizard:
   ```
   pip install tinytuya
   python -m tinytuya wizard
   ```
   Follow the prompts (you'll need a free Tuya IoT developer account, linked to the app your
   vacuum is registered in). The wizard prints a device listing with `id`, `key`, and a `mapping`
   of DP numbers to functions — keep that output, you'll need it for the next step.

## Finding your device's DP numbers

Every Tuya device exposes its state as numbered "DPs" (data points). The wizard's `mapping`
output tells you what each number means for your specific device, e.g.:

```
"17": {"code": "edge_brush", ...}
"19": {"code": "roll_brush", ...}
"5":  {"code": "status", ...}
```

The DP numbers in `vacuum.py` (`17`, `19`, `21`, `10`, `29`, `31`, `5`, `3`, `13`) match one
specific Rowenta model — **check your own device's mapping and adjust the numbers** in the
`dps.get(...)` calls if they differ.

## Install

1. Copy `vacuum.py` and `requirements.txt` into `/config/pyscript/` on your Home Assistant
   instance.
2. Edit the top of `vacuum.py`:
   ```python
   DEVICE_ID = "YOUR_DEVICE_ID"
   LOCAL_KEY = "YOUR_LOCAL_KEY"
   DEVICE_IP = "192.168.1.XXX"
   ```
3. Adjust `CLEANING_WINDOWS` to match when your vacuum actually runs (this just controls when
   `poll_rowenta_status` bothers to check in — it doesn't schedule the vacuum itself).
4. Reload pyscript (Developer Tools → Actions → `pyscript.reload`, or restart Home Assistant).

## Using it in automations

`sensor.rowenta_status` reflects the vacuum's real DP-level status string (e.g. `cleaning`,
`goto_charge`, `charging`, `standby` — check your own device's mapping for the exact enum values).
A simple "started cleaning" automation:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.rowenta_status
    to: "cleaning"
actions:
  - action: notify.mobile_app_your_phone
    data:
      message: "Vacuum started cleaning."
```

And a "no progress for 15 minutes" stuck-detector, using Home Assistant's built-in `for:` on a
state trigger — it only fires if the status holds still on one value, since a vacuum that's
actually moving keeps transitioning between states:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.rowenta_status
    to: ["cleaning", "zone_clean", "part_clean", "goto_pos", "pos_arrived", "pos_unarrive"]
    for: "00:15:00"
actions:
  - action: notify.mobile_app_your_phone
    data:
      message: "No progress for 15+ minutes — may be stuck."
```

## Caveats

- **Fault bitmaps often don't work.** Many cheap Tuya vacuums define a generic 30-bit `fault` DP
  in their cloud schema, but the firmware never actually sets it for real problems like a jammed
  brush. Don't assume you'll get a clean "stuck" signal from the device — the stale-status
  heuristic above is a workaround for exactly this.
- **`state.set()` sensors are not persistent.** They disappear after every Home Assistant/pyscript
  restart until the function runs again — hence the `"startup"` trigger on the maintenance-sensor
  poll, so you're not left with `unavailable` sensors for up to a week.
- **One device session at a time.** Most local-Tuya devices only tolerate one active local-key
  connection. If you're also running `localtuya` against the same device, expect occasional
  contention.
