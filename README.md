# Aqara Devices Integration for Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Hassfest](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hassfest.yml/badge.svg)](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hassfest.yml)
[![HACS Action](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hacs_action.yml/badge.svg)](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hacs_action.yml)
[![release](https://img.shields.io/github/v/release/Darkdragon14/ha-aqara-devices.svg)](https://github.com/Darkdragon14/ha-aqara-devices/releases)

`Aqara Devices (G3, G2H Pro, G410, G4, M1S, M1S Gen 2, M3, M100, M200, FP2, FP300, A100, A100 Pro, Xingyao/ACN002 locks, and U200)` connects supported Aqara cameras, doorbells, hubs, presence sensors, and locks to Home Assistant with Aqara Open API v3 and `aqara-rocketmq-bridge`.

Instead of relying only on periodic polling, the integration now uses Aqara Message Push -> RocketMQ -> bridge -> Server-Sent Events (SSE) so Home Assistant receives live updates while the integration keeps Aqara authentication, token refresh, and resource subscriptions in sync.

## Documentation

- [Setup guide](https://darkdragon14.github.io/aqara-rocketmq-bridge/)
- [Architecture notes](https://darkdragon14.github.io/aqara-rocketmq-bridge/ARCHITECTURE/)
- [Bridge repository](https://github.com/Darkdragon14/aqara-rocketmq-bridge)
- [Integration repository](https://github.com/Darkdragon14/ha-aqara-devices)

## What You Need Before Starting

Before adding the integration, prepare:

- an Aqara developer account and project;
- `APP_ID`, `KEY_ID`, and `APP_KEY` from the Aqara developer console;
- `MQ_NAMESRV_ADDR` from Aqara `Message push`;
- a strong `BRIDGE_TOKEN`;
- a reachable bridge URL for Home Assistant;
- Home Assistant with this integration installed.

For the complete step-by-step setup, follow the published guide linked above.

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Darkdragon14&repository=ha-aqara-devices)

1. Click the button above, or add `https://github.com/Darkdragon14/ha-aqara-devices` manually as a custom repository in HACS with category `Integration`.
2. Search for `Aqara Devices` and install it.
3. Restart Home Assistant.
4. Go to `Settings -> Devices & Services -> Add Integration`.
5. Search for `Aqara Devices`.

### Manual installation

1. Copy `custom_components/ha_aqara_devices` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the `Aqara Devices` integration from `Settings -> Devices & Services`.

## Quick Start

### 1. Configure Aqara Message Push

In the Aqara developer console:

1. Create or open your Aqara project.
2. Copy `APP_ID`, `KEY_ID`, and `APP_KEY`.
3. Open `Message push`.
4. Select `Get messages based on message queue`.
5. Enable push and keep `User-defined subscription mode`.
6. Copy the `MQ message subscription address` as `MQ_NAMESRV_ADDR`.

### 2. Run the bridge

Use one of these supported paths:

| Home Assistant installation | Bridge deployment | Typical `Bridge URL` |
| --- | --- | --- |
| Home Assistant Container | Docker or Compose | `http://aqara-rocketmq-bridge:8080` |
| Home Assistant OS | `Aqara RocketMQ Bridge` add-on | `http://HOME_ASSISTANT_IP:8080` or your reverse-proxy URL |

For Home Assistant OS, add the bridge add-on repository automatically:

[![Open your Home Assistant instance and add this add-on repository.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FDarkdragon14%2Faqara-rocketmq-bridge)

Bridge setup details, add-on instructions, and Compose examples are in the published guide:

- [Aqara RocketMQ Bridge setup guide](https://darkdragon14.github.io/aqara-rocketmq-bridge/)

### 3. Add the integration in Home Assistant

The config flow asks for:

| Field | Value |
| --- | --- |
| `Aqara account (email or phone)` | Your Aqara login identifier |
| `Region` | `EU`, `US`, `CN`, `RU`, `KR`, `SG`, or `OTHER` |
| `Bridge URL` | The URL Home Assistant can use to reach the bridge |
| `Bridge token` | The same token as `BRIDGE_TOKEN` |
| `App ID` | Your Aqara `APP_ID` |
| `App key` | Your Aqara `APP_KEY` |
| `Key ID` | Your Aqara `KEY_ID` |

After the first step, Aqara sends a verification code to your email address or phone number. Enter that authorization code to finish setup.

### Optional camera live streams with go2rtc

G3, G2H Pro, G410, and G4 devices can expose a Home Assistant `camera` entity through a separate [go2rtc](https://github.com/AlexxIT/go2rtc) instance. Video support is optional; all other Aqara entities continue to work when go2rtc is not installed.

> [!IMPORTANT]
> Camera configurations created with the prerelease tag `v1.4.0-beta-camera-rtsp-streams` are not migrated. Direct RTSP settings cannot be converted into a HomeKit pairing and are ignored by this version. Reconfigure each camera through go2rtc; the old `rtsp_cameras` options are left untouched so downgrading does not destroy them.

For Home Assistant OS or Supervised, install the go2rtc add-on from `https://github.com/AlexxIT/hassio-addons`. Home Assistant Container users can run the official `alexxit/go2rtc` container instead. Keep the go2rtc API and media ports on localhost or a trusted private network.

Open the integration options and use:

| Menu | Purpose |
| --- | --- |
| `Account and bridge` | Update Aqara Open API account details, developer keys, or bridge connection settings |
| `go2rtc` | Configure and validate the go2rtc API and RTSP output URLs |
| `Camera streams` | Pair a discovered camera or associate an existing go2rtc stream |

When pairing a camera, select the Aqara device, select the local HomeKit camera discovered by go2rtc, and enter its HomeKit pairing code. The code is sent directly to go2rtc and is not stored by this integration. go2rtc performs the local HomeKit pairing, stores its pairing keys, and provides the stream consumed by Home Assistant. The HomeKit Device integration is not required.

The automatically paired stream currently exposes video only. HomeKit uses AAC-ELD audio, which requires an additional FFmpeg transcoding source; advanced users can configure that in go2rtc and associate the resulting existing stream.

HomeKit cameras generally pair with one controller at a time. If discovery or pairing fails, remove any existing Apple Home, HomeKit Device, or other go2rtc pairing first. This does not remove the camera from the Aqara app or affect its Aqara Open API entities.

Advanced users can associate an existing go2rtc stream instead of pairing through the integration. Streams created outside this integration are never deleted or unpaired automatically.

### Hub child devices

The integration discovers child devices connected to supported G3, G2H Pro, M1S, M1S Gen 2, M3, M100, and M200 hubs and registers each child under its parent hub in Home Assistant. Readable Aqara resources are exposed as generic read-only `sensor` or `binary_sensor` entities.

Only resources considered safe and useful are enabled automatically, including reportable binary states and common measurements with units. Writable, unknown, or less useful resources are disabled by default. To use one of these entities, open the child device in Home Assistant, select its disabled entities, and enable the ones you need. Enabling or disabling a child entity reloads the integration so polling and Aqara subscriptions stay aligned with the active entities.

The `ha_aqara_devices.open_pairing_mode` and `ha_aqara_devices.close_pairing_mode` services can start or stop child-device pairing on a supported hub. Both services require the parent hub's Aqara DID.

M1S and M1S Gen 2 hubs also expose their native night light, Wi-Fi signal strength, system and alarm volume, alarm ringtone, and alarm control. The original M1S additionally exposes its doorbell ringtone, music volume and duration, alarm duration, and music playback control.

## How It Works

`Aqara RocketMQ -> aqara-rocketmq-bridge -> SSE -> ha_aqara_devices -> Home Assistant`

- `aqara-rocketmq-bridge` consumes Aqara Message Push events and exposes `GET /health` and `GET /events`;
- `ha_aqara_devices` validates the bridge, connects to the SSE stream with `Authorization: Bearer <bridge token>`, and manages Aqara Open API authentication;
- the integration subscribes only to the Aqara resources it needs and creates entities for supported devices.

## Supported Devices

| Device | Models |
| --- | --- |
| `Hub G3` | `lumi.camera.gwpgl1`, `lumi.camera.gwpagl01` |
| `Camera Hub G2H Pro` | `lumi.camera.agl001`, `lumi.camera.acn003` |
| `Doorbell G410` | `lumi.camera.acn017`, `lumi.camera.agl006` |
| `Doorbell G4` | `lumi.camera.agl002`, `lumi.camera.acn005` |
| `Hub M1S` | `lumi.gateway.aeu01` |
| `Hub M1S Gen 2` | `lumi.gateway.agl002` |
| `Hub M3` | `lumi.gateway.acn012`, `lumi.gateway.agl004` |
| `Hub M100` | `lumi.gateway.agl008`, `lumi.gateway.agl010` |
| `Presence Sensor FP2` | `lumi.motion.agl001` |
| `Presence Multi-Sensor FP300` | `lumi.sensor_occupy.agl8` |
| `Door Lock A100` | `aqara.lock.agl002` |
| `Door Lock A100 Pro` | `aqara.lock.acn001` |
| `Smart Lock U200` | `aqara.matter.4447_10242` |
| `Smart Lock U200 Lite` | `aqara.matter.4447_10247` |
| `Smart Video Door Lock Xingyao` (`全自动智能猫眼门锁 星耀`) | `aqara.lock.acn002` |

Each discovered supported device in your Aqara account gets its own entities and device metadata inside Home Assistant.

For the full per-device entity details, see the published bridge documentation:

- [Supported devices reference](https://darkdragon14.github.io/aqara-rocketmq-bridge/devices/)

The U200 and U200 Lite are exposed by Aqara as Matter models `aqara.matter.4447_10242` and `aqara.matter.4447_10247`, so this integration reads them through the Aqara trait API instead of the older resource API.

## Need Help?

- [Full setup and troubleshooting guide](https://darkdragon14.github.io/aqara-rocketmq-bridge/)
- [Issues and feature requests](https://github.com/Darkdragon14/ha-aqara-devices/issues)

## Credits / Acknowledgements

Camera streaming is powered by [AlexxIT/go2rtc](https://github.com/AlexxIT/go2rtc), distributed separately under the MIT license.
Thanks also to Aqara support for their help and information; this project is community-maintained and is not officially affiliated with or endorsed by Aqara.

## Missing translation

Want to see your language? Open an issue or submit a PR with new entries under `custom_components/ha_aqara_devices/translations/`.
