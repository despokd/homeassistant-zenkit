# Configuration

Go to Configuration -> Integrations and click on "add integration". Then search for "Zenkit".

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=zenkit)

### Configuration Variables

- __token__: Your API Key from Your Account > Integrations > API Key

### Refresh button

Data is polled every 60 seconds. Press the __Refresh Zenkit data__ button (`button.zenkit_refresh`) to update all lists immediately, e.g. after changing list fields in Zenkit. It can also be pressed from automations with the `button.press` action. New lists still require a reload of the integration.
