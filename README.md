# SR Mini BLE

An unofficial Python BLE controller for the iGPSPORT SR Mini light. The package
is organized around a small async BLE client, a protocol encoder, light commands,
and a CLI, following the broad structure of
[python-igps-ble](https://github.com/hudsonbrendon/python-igps-ble).

The command format is based on the iGPSPORT Ride 8.06.50 decompiled source.
This is an initial implementation; it has not yet been validated against a
physical SR Mini.

## Install with uv

```sh
uv sync
```

## Use

```sh
uv run srmini scan
uv run srmini modes
uv run srmini set-mode high_always --dry-run
uv run srmini set-mode 1
uv run srmini set-mode off --address <BLE-address>
```

Wake the light before scanning. Without `--address`, `set-mode` scans and uses a
single device named SR Mini; if multiple matches are found, specify the address.

The implemented command sets the current light mode through BLE UART RX
(`6e400002-b5a3-f393-e0a9-e50e24dcca9e`). The app's corresponding TX
notification characteristic is `6e400003-b5a3-f393-e0a9-e50e24dcca9e`.
`--dry-run` prints the encoded frame and never connects to BLE.

Mode IDs and names are from the app's `BLE_LIGHT_MODE` enum. Whether each mode is
supported by a particular firmware/device variant is not queried yet.
