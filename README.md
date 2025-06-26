# About Haus-Bus.de

[Haus-Bus.de](https://haus-bus.secure-stores.de/) is a manufacturer of smart home equipment based in Germany.
This integration communicates to any of the Haus-Bus devices equipped with a LAN port.


## Installation

### 📦 HACS Installation (Recommended)

The easiest way to install **Hausbus* is via **[HACS (Home Assistant Community Store)](https://hacs.xyz/)**.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Zero545&repository=integration_hausbus&category=Integration)

### Manual Steps:

1. Ensure **[HACS](https://hacs.xyz/docs/setup/download)** is installed in Home Assistant.
2. Go to **HACS → Custom Repositories**.
3. Add this repository: `https://github.com/hausbus/integration_hausbus` as type `Integration`
4. Install **Hausbus** from HACS.
5. **Clear your browser cache** and reload Home Assistant.

## Supported devices

Currently only switch and light based devices are supported, i.e. all relais and dimmer channels on the devices [16 channel relais](https://haus-bus.de/?showProduct=8), [12 channel relais](https://haus-bus.de/?showProduct=20), [8-channel IO-Module](https://haus-bus.de/?showProduct=6), [22-channel IO-module](https://haus-bus.de/?showProduct=5), [32-channel IO-module](https://haus-bus.de/?showProduct=2) [8-channel 230V dimmer](https://haus-bus.de/?showProduct=14), [2-channel RGB dimmer](https://haus-bus.de/?showProduct=9).

The supported devices are automatically detected in the local network via UDP broadcast, upon loading the integration.

## Debugging integration

If you have problems with the Hausbus integration you can add debug prints to the log.

```yaml
logger:
  default: info
  logs:
    custom_components.hausbus: debug
```
