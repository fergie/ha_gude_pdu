# GUDE PDU Integration for Home Assistant

A modern [Home Assistant](https://www.home-assistant.io/) custom component integration for monitoring and controlling [GUDE Systems](https://gude-systems.com/) Power Distribution Units (PDUs) using their native HTTP(S) CGI/JSON API.

This project is not endorsed by, directly affiliated with, maintained, authorised, or sponsored by GUDE Systems GmbH.

_If you want to show your support please [buy me a coffee](https://www.buymeacoffee.com/fergieweb)._

## Supported Devices

This integration supports GUDE Systems Expert Power Control (EPC) and Expert Sensor Box devices that provide the GUDE HTTP(S) JSON API (`/status.json` or `/statusjsn.js`), including:

- **Expert Power Control 8031 / 8035 / 8041 / 8045 / 8080 / 8090 series**
- **Expert Power Control 8210 / 8220 / 8221 / 8226 / 8291 series**
- **Expert Power Control 1105 / 1202 / 8316 series**

## Features & Supported Functions

- **Outlet Child Devices & Switching**: Each switchable power port (`Outlet 1` .. `Outlet N`) is registered as a Home Assistant child device under the main PDU device, exposing an individual switch entity (`SwitchDeviceClass.OUTLET`) with real-time state feedback and any per-outlet telemetry sensors.
- **Electrical Telemetry**: Automatic discovery of line, residual, and port sensors:
  - Voltage (V)
  - Current & Residual Current (A)
  - Active Power (W)
  - Apparent Power (VA, disabled by default)
  - Reactive Power (VAR, disabled by default)
  - Energy Meters (kWh with `SensorStateClass.TOTAL_INCREASING`)
  - Frequency (Hz) & Power Factor
- **Environmental Telemetry**: Ambient temperature (°C), relative humidity (%), and atmospheric pressure (hPa) for connected GUDE sensor modules (e.g., 7101 / 7104 / 7105 / 7106).
- **Device & System Diagnostics**: System uptime (`Uptime`), internal CPU temperature (`Tcpu`), internal supply voltages (`Vsystem`, disabled by default), firmware version, MAC address, and downloadable Home Assistant Diagnostics with sensitive data redaction.
- **UI Config, Reauth & Reconfigure Flows**: Full UI setup with live connection verification, SSL toggle, HTTP Basic Auth, session login (`/login.json` + `sessionidX`), re-authentication, and reconfiguration.
- **Legacy Fallback**: Automatic detection and fallback between `/status.json` and legacy `/statusjsn.js` CGI endpoints.

## Data Updates

The integration polls the PDU locally (`local_polling`) every **30 seconds** for updated outlet states, electrical measurements, environmental sensors, and system diagnostics. When an outlet switch is toggled in Home Assistant, the integration immediately sends the command and triggers a coordinator refresh.

## Installation

### Marketplace

1. Click the button below to open this repository in the Home Assistant [Marketplace](https://www.home-assistant.io/integrations/marketplace/):

[![Open your Home Assistant instance and open a repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=fergie&repository=ha_gude_pdu&category=Integration)

2. Restart Home Assistant.
3. Navigate to **Settings** -> **Devices & Services** -> **+ Add integration**.
4. Search for **GUDE PDU**.
5. Enter the connection parameters (see below).

### Manual Installation

1. Copy the `custom_components/gude_pdu` folder from the latest release of this repo into your Home Assistant installation's `custom_components` directory (`<config_dir>/custom_components/gude_pdu/`).
2. Restart Home Assistant.
3. Navigate to **Settings** -> **Devices & Services** -> **+ Add integration**.
4. Search for **GUDE PDU**.

### Configuration Parameters

| Parameter | Description | Default |
| --- | --- | --- |
| **Host** | Hostname or IPv4/IPv6 address of the GUDE PDU on your local network. | *(Required)* |
| **Port** | HTTP or HTTPS port number of the PDU web interface. | `80` |
| **Uses an SSL certificate** | Connect over HTTPS (`https://`) instead of HTTP (`http://`). | `false` |
| **Verify SSL certificate** | Validate the PDU's TLS certificate against trusted CA certificates. Disable for self-signed certificates. | `false` |
| **Username** | Username for HTTP Basic or Session authentication (if enabled on the PDU). | *(Optional)* |
| **Password** | Password for HTTP Basic or Session authentication. | *(Optional)* |

## Removal Instructions

1. Navigate to **Settings** -> **Devices & Services** and select the **GUDE PDU** integration.
2. Click the three-dot menu next to the configured PDU entry and select **Delete**.
3. If installed via the Marketplace, remove the **GUDE PDU** integration from the Marketplace by opening the repository, selecting the three dots menu in the upper-right corner, then clicking **Remove**.  For manual installations, delete the `<config_dir>/custom_components/gude_pdu/` directory.  In both cases you should restart Home Assistant to complete the process.

## Use Cases & Automation Examples

### Rebooting Network Equipment on Connectivity Loss

```yaml
automation:
  - alias: "Power cycle router outlet on internet drop"
    triggers:
      - trigger: state
        entity_id: binary_sensor.wan_connected
        to: "off"
        for: "00:05:00"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.epc8041_outlet_1
      - delay: "00:00:10"
      - action: switch.turn_on
        target:
          entity_id: switch.epc8041_outlet_1
```

### Rack Over-Temperature Alert

```yaml
automation:
  - alias: "Server rack high temperature alert"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.epc8291_1_temperature
        above: 35
    actions:
      - action: notify.persistent_notification
        data:
          title: "Rack Temperature Warning"
          message: "PDU ambient temperature reached {{ states('sensor.epc8291_1_temperature') }} °C."
```

## Known Limitations

- **Polling Only**: GUDE PDUs do not push state changes over WebSockets to Home Assistant; external outlet toggles performed directly on the PDU web UI or physical buttons update on the next polling cycle (up to 30 seconds).
- **HTTP CGI Command Permission**: To control outlets from Home Assistant, ensure **Allow HTTP CLI / CGI commands** (or the corresponding user permission) is enabled in your GUDE PDU's web interface settings.

## Troubleshooting

- **Failed to connect (`cannot_connect`)**: Verify the IP/hostname, port (`80` for HTTP, `443` for HTTPS), and whether HTTPS (`Uses an SSL certificate`) matches your PDU configuration. If using a self-signed certificate on the PDU, uncheck **Verify SSL certificate**.
- **Invalid authentication (`invalid_auth`)**: Verify your PDU username and password. Both HTTP Basic Authentication and GUDE Session Authentication (`/login.json`) are supported.
- **Switching outlets fails**: Check that the configured user has permission to switch ports and that CGI/JSON control commands are enabled under the PDU's HTTP/Security configuration.

## Development & Testing

This repository uses [uv](https://docs.astral.sh/uv/) (with Python 3.14+) for dependency management, static analysis, and testing:

```bash
# Install dependencies into .venv
uv sync

# Run pytest with coverage (enforces >= 95% coverage)
uv run pytest

# Update Syrupy test snapshots (if diagnostics output intentionally changes)
uv run pytest --snapshot-update

# Run linting, formatting, and spell checks
uv run ruff check .
uv run ruff format --check .
uv run codespell

# Auto-fix lint issues and format code
uv run ruff check --fix .
uv run ruff format .

# Run strict static type checking
uv run mypy custom_components/gude_pdu tests
```

### Pre-commit Hooks

A `.pre-commit-config.yaml` configuration is included to automatically run `ruff` (linting and formatting), `codespell`, `mypy`, release version checks, and [Conventional Commits](https://www.conventionalcommits.org/) commit message validation (`conventional-pre-commit`) before each commit:

```bash
# Install the git pre-commit and commit-msg hooks
uv run pre-commit install

# Run all pre-commit hooks manually across all files
uv run pre-commit run --all-files
```

### Continuous Integration (Hassfest & HACS)

The CI GitHub Action (`.github/workflows/ci.yaml`) runs the full test suite (`pytest`, `ruff`, `codespell`, `mypy`, Hassfest, and HACS validation) on push and pull requests to `main`. To run Hassfest and HACS validations locally, use these commands from the repository root:

Hassfest:

```bash
docker run --rm --platform linux/amd64 -v "$(pwd):/github/workspace" ghcr.io/home-assistant/hassfest
```

HACS:

```bash
docker run --rm --platform linux/amd64 \
  -v "$(pwd):/github/workspace" \
  -e GITHUB_WORKSPACE="/github/workspace" \
  -e GITHUB_REPOSITORY="fergie/ha_gude_pdu" \
  -e GITHUB_ACTOR="[GITHUB_USERNAME]" \
  -e INPUT_CATEGORY="integration" \
  -e INPUT_GITHUB_TOKEN="$(gh auth token)" \
  ghcr.io/hacs/action:main
```

### Releases

Releases are automated via `.github/workflows/release.yaml` using [`googleapis/release-please-action`](https://github.com/googleapis/release-please-action) following the [Home Assistant Marketplace Releases Guide](https://contributors.home-assistant.io/marketplace/guides/releases/):

1. Commit changes to `main` using [Conventional Commits](https://www.conventionalcommits.org/) (e.g., `fix: ...` for patch releases, `feat: ...` for minor releases, or `feat!: ...` / `BREAKING CHANGE:` for breaking changes).
2. Release Please automatically opens or updates a Release PR on `main` that bumps the version across `pyproject.toml`, `custom_components/gude_pdu/manifest.json`, `uv.lock`, and `.release-please-manifest.json`, and updates `CHANGELOG.md`.
3. Merging the Release PR automatically tags the commit (`vX.Y.Z`) and publishes the GitHub Release.

## Architecture & API References

- [GUDE API Overview](https://wiki.gude-systems.com/API_Overview_eng)
- [EPC HTTP/CGI Interface](https://wiki.gude-systems.com/EPC_HTTP_Interface)
- [HTTP JSON Sensor Data Specification](https://wiki.gude-systems.com/HTTP_JSON_Sensor_Data)
