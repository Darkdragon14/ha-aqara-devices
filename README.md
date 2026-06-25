# Aqara Devices Integration for Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Hassfest](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hassfest.yml/badge.svg)](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hassfest.yml)
[![HACS Action](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hacs_action.yml/badge.svg)](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hacs_action.yml)
[![release](https://img.shields.io/github/v/release/Darkdragon14/ha-aqara-devices.svg)](https://github.com/Darkdragon14/ha-aqara-devices/releases)

`Aqara Devices (G3, G2H Pro, G410, G4, M3, M100, M200, FP2, FP300, A100 Pro, and Xingyao/ACN002 locks)` connects supported Aqara cameras, doorbells, hubs, presence sensors, and locks to Home Assistant with Aqara Open API v3 and `aqara-rocketmq-bridge`.

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
| `Doorbell G4` | `aqara.lock.agl002`, `lumi.camera.acn005` |
| `Hub M3` | `lumi.gateway.acn012`, `lumi.gateway.agl004` |
| `Hub M100` | `lumi.gateway.agl008`, `lumi.gateway.agl010` |
| `Presence Sensor FP2` | `lumi.motion.agl001` |
| `Presence Multi-Sensor FP300` | `lumi.sensor_occupy.agl8` |
| `Door Lock A100 Pro` | `aqara.lock.acn001` |
| `Smart Video Door Lock Xingyao` (`全自动智能猫眼门锁 星耀`) | `aqara.lock.acn002` |

Each discovered supported device in your Aqara account gets its own entities and device metadata inside Home Assistant.

For the full per-device entity details, see the published bridge documentation:

- [Supported devices reference](https://darkdragon14.github.io/aqara-rocketmq-bridge/devices/)

## Need Help?

- [Full setup and troubleshooting guide](https://darkdragon14.github.io/aqara-rocketmq-bridge/)
- [Issues and feature requests](https://github.com/Darkdragon14/ha-aqara-devices/issues)

## Missing translation

Want to see your language? Open an issue or submit a PR with new entries under `custom_components/ha_aqara_devices/translations/`.
