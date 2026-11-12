# Installation

Requires Home Assistant 2026.11 or newer.

## 1. Using the Marketplace (recommended way)

1. Open the Home Assistant Marketplace
2. Search for "Zenkit" and install it, or use the link below.
3. Restart Home Assistant.

[![Open your Home Assistant instance and open a repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=despokd&repository=homeassistant-zenkit&category=integration)

If you use this method, your component will always update to the latest version.

## 2. Manual

- Download the latest zip release from [Github Releases](https://github.com/despokd/homeassistant-zenkit/releases/latest)
- Extract the zip file
- Copy the folder "zenkit" from within custom_components with all of its components to `<config>/custom_components/`

where `<config>` is your Home Assistant configuration directory.

>__NOTE__: Do not download the file by using the link above directly, the status in the "main" branch can be in development and therefore is maybe not working.