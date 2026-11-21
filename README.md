# SR Mini BLE

An unofficial Python BLE controller for the iGPSPORT SR Mini light. The package
is organized around a small async BLE client, a protocol encoder, light commands,
and a CLI, following the broad structure of
[python-igps-ble](https://github.com/hudsonbrendon/python-igps-ble).

The command format is based on the iGPSPORT Ride 8.06.50 decompiled source.
This is an initial implementation; it has not yet been fully validated against a
physical SR Mini.

## Install with uv

```sh
uv sync
```

## Use

```sh
uv run srmini scan
uv run srmini info
uv run srmini radar on
uv run srmini radar off
uv run srmini modes
uv run srmini set-mode high_always --dry-run
uv run srmini set-mode 1
uv run srmini set-mode off --address <BLE-address>
```

Wake the light before scanning. Without `--address`, `set-mode` scans and uses a
single device named SR Mini; if multiple matches are found, specify the address.
Mode `14` is the left turn signal and may not illuminate the main beam. To test
the main light, try `uv run srmini set-mode 1` (high steady mode) or `2` (medium
steady mode). Mode `0` is off.

The implemented command sets the current light mode through BLE UART RX
(`6e400002-b5a3-f393-e0a9-e50e24dcca9e`). The app's corresponding TX
notification characteristic is `6e400003-b5a3-f393-e0a9-e50e24dcca9e`.
`--dry-run` prints the encoded frame and never connects to BLE.
Frames are split into ATT-sized writes, matching the app's UART write behavior.

`radar on` and `radar off` use the same smart configuration as the app's
Intelligent Function Configuration → Radars switch (`BLCS_RADAR`, service 106,
subservice 4). This is separate from the `PCS_DATA_BROADCAST` setting, which
only controls radar data notifications.

`radar-alert on` and `radar-alert off` control the adjacent Radar Alert switch
on that page (`BLCS_RADAR_WARN`, config value 21). It controls alert behavior,
which the app exposes separately from the main Radars switch.

`auto-sleep on` and `auto-sleep off` write the app's Auto Sleep setting
(`BLCS_AUTO_SLEEP`, config value 4), including its timeout slider value:

```sh
uv run srmini auto-sleep on --timeout-seconds 300
uv run srmini auto-sleep off --timeout-seconds 300
uv run srmini auto-sleep timeout 300
```

The timeout is in seconds. The app slider accepts 30–1200 seconds in 30-second
steps. `auto-sleep timeout N` sets the slider value and leaves Auto Sleep on by
default; pass `--enabled off` to keep it off. Switch commands default to 30
seconds unless `--timeout-seconds` is supplied.

`info` reads standard BLE manufacturer/revision/serial/battery characteristics
and the standard Current Time characteristic when present, then requests the
app's `PIS_ALL_INFO` response for battery voltage, temperature, and memory. The
decompiled SR Mini info schema does not include a separate protocol version;
that field is shown as not reported. Temperature and memory are printed in the
device's raw units; the protocol source does not document their scales.

Mode IDs and names are from the app's `BLE_LIGHT_MODE` enum. Whether each mode is
supported by a particular firmware/device variant is not queried yet.

## Mode checklist

| ID | Mode | Works? |
| --- | --- | --- |
| 0 | off | y |
| 1 | high_always | y |
| 2 | mid_always | y |
| 3 | low_always | y |
| 4 | high_blink | y |
| 5 | low_blink | y |
| 6 | gradient | n |
| 7 | high_level_1 | n |
| 8 | high_level_2 | n |
| 9 | high_level_3 | n |
| 10 | low_level_1 | n |
| 11 | low_level_2 | n |
| 12 | low_level_3 | n |
| 13 | rotation | n |
| 14 | left_turn | n |
| 15 | right_turn | n |
| 16 | superhigh | n |
| 17 | sos | n |
| 18 | comet | y |
| 19 | waterfall | y |
| 20 | pinwheel | n |

