# Haus-Bus Integration for Home Assistant

## High-Level Description

[Haus-Bus.de](https://www.haus-bus.de/) is a manufacturer of smart home components based in Germany.
This integration communicates to any of the Haus-Bus devices natively within Home assistant without communicating to any external server or cloud.

The integration works on push basis to achieve optimal performance without any latence.

## Supported Platforms
- Light  
- Switch  
- Sensor  
- Binary Sensor  
- Cover  
- Button  
- Event  

## Config Flow
This integration supports UI config flow  

1. Home Assistant → „Settings“ → „Devices and Services“ → „Add integration" → enter **Haus-Bus**   
2. Devices are discovered and added automatically
3. In addition a button is generated to manually start the device discovery   


## Services

### `hausbus.discover_devices`
- Description: Manually starts a device discovery  


## Installation

### 📦 HACS Installation (Recommended)

The easiest way to install **Hausbus* is via **[HACS (Home Assistant Community Store)](https://hacs.xyz/)**.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=hausbus&repository=integration_hausbus&category=Integration)

### Manual Steps:

1. Ensure **[HACS](https://hacs.xyz/docs/setup/download)** is installed in Home Assistant.
2. Go to **HACS → Custom Repositories**.
3. Add this repository: `https://github.com/hausbus/integration_hausbus` as type `Integration`
4. Install **Hausbus** from HACS.
5. **Clear your browser cache** and reload Home Assistant.

## Supported devices
All devices shown on www.haus-bus.de are supported by this integration.
The devices are automatically detected in the local network via UDP broadcast, upon loading the integration.

## Debugging integration

If you have problems with the Hausbus integration you can add debug prints to the log.

```yaml
logger:
  default: info
  logs:
    custom_components.hausbus: debug
```

## Removal Instructions

To remove the Haus-Bus integration from Home Assistant, follow these steps:

1. Go to **Settings → Devices & Integrations** in Home Assistant.
2. Find the **Haus-Bus** integration and click **Remove**.
3. This will:
   - Unload all platforms (light, switch, sensor, etc.)
   - Deregister the `hausbus.discover_devices` service
   - Remove all Config Entries and options
   - Clean up local device registry entries

After removal, all Haus-Bus devices and settings will be fully cleaned from Home Assistant.
