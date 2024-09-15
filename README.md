# Zenkit Integration for Homeassistant

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

The `zenkit` integrations adds your lists from [Zenkit](https://zenkit.com) currently as ToDo lists.

## Installation

### 1. Using HACS (recommended way)

This integration is a not yet an official HACS Integration.

1. Open HACS
2. Open options with the three dots at the upper right
3. Add this repo https://github.com/despokd/homeassistant-zenkit as a custom repository with type `Integration`
4. then install the "Zenkit" integration or use the link below.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=despokd&repository=homeassistant-zenkit&category=integration)

If you use this method, your component will always update to the latest version.

### 2. Manual

- Download the latest zip release from [Github Releases](https://github.com/despokd/homeassistant-zenkit/releases/latest)
- Extract the zip file
- Copy the folder "zenkit" from within custom_components with all of its components to `<config>/custom_components/`

where `<config>` is your Home Assistant configuration directory.

>__NOTE__: Do not download the file by using the link above directly, the status in the "main" branch can be in development and therefore is maybe not working.

## Configuration

Go to Configuration -> Integrations and click on "add integration". Then search for "Zenkit".

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=zenkit)

### Configuration Variables

- __api_key__: Your API Key from Your Account > Integrations > API Key

## Releases

- auto released by workflow
- managed by `COMPONENT_VERSION` variable at GitHub Actions
