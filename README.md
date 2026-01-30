# Aqara Devices Integration for Home Assistant
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Hassfest](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hassfest.yml/badge.svg)](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hassfest.yml)
[![HACS Action](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hacs_action.yml/badge.svg)](https://github.com/Darkdragon14/ha-aqara-devices/actions/workflows/hacs_action.yml)
[![release](https://img.shields.io/github/v/release/Darkdragon14/aqara-fp2-integration.svg)](https://github.com/Darkdragon14/aqara-fp2-integration/releases)

`Aqara Devices (Hub G3 and FP2)` exposes the cloud features of the Aqara Camera Hub G3 and Presence Sensor FP2 directly inside Home Assistant. The integration keeps critical toggles, gesture events, PTZ controls, and FP2 telemetry in sync so that automations can react instantly without touching the Aqara mobile app.

## Installation

### HACS installation

To install this integration via [HACS](https://hacs.xyz/):

1. Add this repository as a custom repository in HACS  
   • Go to **HACS → Integrations → Add Custom Repository**.  
   • Enter `https://github.com/Darkdragon14/aqara-fp2-integration` and pick **Integration**.
2. Search for **Aqara Devices** inside HACS and install it.
3. Restart Home Assistant to load the new component.
4. Go to **Settings → Devices & Services → Add Integration**.
5. Search for **Aqara Devices** and follow the config flow.

### Manual installation (alternative)

1. Copy the `custom_components/ha_aqara_devices` directory into your Home Assistant `custom_components` folder.
2. Restart Home Assistant.
3. Add the **Aqara Devices** integration from **Settings → Devices & Services**.

## How it works

This integration talks to the same API that the Aqara mobile application uses. The Home Assistant config flow walks you through:

1. **Providing Aqara credentials** – the username/password are encrypted with the Aqara RSA key before being sent to the cloud.
2. **Selecting your cloud area** – EU, US, CN, or OTHER so that requests are routed to the right backend.
3. **Automatic discovery** – the component logs in, fetches all Aqara devices, then keeps `lumi.camera.gwpgl1` entries (Aqara Camera Hub G3) and `lumi.motion.agl001` entries (Presence Sensor FP2). Both families reuse the same authenticated session.
4. **State syncing** – a coordinator polls `/app/v1.0/lumi/res/query` once per second to collect G3 switch states, while gesture sensors use `/history/log` timestamps to emulate momentary binary sensors. FP2 devices combine `/res/query` and `/res/query/by/resourceId` calls to expose occupancy, heart rate/respiration metrics, illuminance, and configuration flags as entities.
5. **Commands** – switches and numbers call `/app/v1.0/lumi/res/write`, PTZ buttons call `/lumi/devex/camera/operate`, and the alarm bell button briefly enables the siren then resets it.

Because the integration must log in on your behalf, make sure the Aqara account has two-factor actions resolved in the official app first, and prefer creating a dedicated Aqara sub-account for Home Assistant if possible.

### Supported entities

| Platform | Entities | Description |
| --- | --- | --- |
| **Switches (G3)** | Video, Detect Human, Detect Pet, Detect Gesture, Detect Face, Mode Cruise | Toggle the G3 camera processing pipelines remotely. |
| **Buttons (G3)** | PTZ Up/Down/Left/Right, Ring Alarm Bell | Fire PTZ pulses or ring the built-in siren on demand. |
| **Binary sensors (G3)** | Night vision, Gesture V sign/Four/High Five/Finger Gun/OK | Read-only sensors updated every second; gesture sensors stay on for ~10s to emulate momentary presses. |
| **Binary sensors (FP2)** | Presence, Connectivity | Occupancy state and online/offline status for each FP2. |
| **Sensors (FP2)** | Illuminance, Heart Rate, Respiration Rate, Body Movement, Sleep State, installation/mounting metadata, sensitivity/configuration selectors | Combines FP2 telemetry and configuration flags so dashboards and automations can react instantly. |
| **Numbers (G3)** | Volume | Adjust the camera speaker volume (0–100). |

Each G3 discovered in your Aqara account gets its own set of entities with device metadata so you can build automations, scenes, or dashboards right away.

## Future improvements

* Expose FP2 zone assignments and history per-area to complement the global occupancy sensor. :rocket:
* Provide in-UI feedback for failed PTZ or siren commands. :rocket:
* Optionally throttle polling frequency per device to reduce cloud load. :hammer_and_wrench:
* Improve error handling, translations, and diagnostics to simplify troubleshooting. :hammer_and_wrench:

## Missing translation

Want to see your language? Please open an issue or submit a PR with new entries under `custom_components/ha_aqara_devices/translations/`. I’ll happily merge or help provide the translations. :smile:
