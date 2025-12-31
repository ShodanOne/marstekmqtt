# Marstek Plugin for Jeedom

<img width="154" height="174" alt="Image" src="https://github.com/user-attachments/assets/1f65299b-b955-4b85-9443-9262e751178c" />

> **Firmware warning:** Marstek’s Local API firmware is still immature, so most glitches originate in the batteries, not here.
> Report issues to Marstek unless you can clearly trace them to this project.\
> **Note :** This plugin has been tested on a Venus E 3.0 with firmware 145.116.110.

Jeedom plugin for Marstek energy storage systems using the official Local API (Rev 1.0).\
It provides comprehensive monitoring and control of Marstek Venus C/D/E devices without requiring cloud connectivity or additional hardware.

This plugin is still in beta version. It targets following Marstek Devices : Venus C, Venus D, Venus E.\
Protocol: JSON over UDP (port 30000+)

It relies on marstek_local_api from [ha-marstek-api](https://github.com/jaapp/ha-marstek-local-api) project

## Prerequisites

- Local API must be enabled in Marstek app
- Python 3.10
- paho-mqtt python library
- Jeddom [MQTT Manager](https://market.jeedom.com/index.php?v=d&p=market_display&id=4213) plugin

## 1. Installation

- Jeedom [MQTT Manager](https://market.jeedom.com/index.php?v=d&p=market_display&id=4213) plugin
- unzip the folder marstekmqtt.zip in your Jeedom /plugins directory (or upload marstekmqtt directory in/plugins using Jeedom file editor
- Go to th plugin management section
- Select marstekmqtt plugin
- Activate the plugin :
    - dependencys install should start automatically (if not, launch dependencies manually)
      > First dependencies install make take time since Python 3.10 will be installed in venv
  
## 2. Plugin Configuration

<img width="2662" height="340" alt="Image" src="https://github.com/user-attachments/assets/6eec3341-3655-4ab2-8572-7c5c75284c67" />
Default configuration should work as long as API has been enabled from the app on port 30000.\
It is recommanded to keep Timeout / Retry / Period parameters at the default value.

<ins>Parameter description</ins> :
- **Marstek API Port (Port API Marstek)** :
  UDP Port number specified on the Marstek app - default is 30000.
- **Timeout (Timeout requete API)** :
  Timeout for an API request to be processed in seconds - default value is 5s, may have to be increased in case of trouble.
  > Not recommended to be lower than 2s.
- **Retry (Nb tentative requete API)** :
  Max number of retry for an API request - default value is 3.
- **Polling period (Periode sondage (s))** :
  Minimun Polling period for API polling in seconds - default value is 10s, may have to be increased in case of trouble.
  > Not recommended to be lower than 5s, does not make sense to set a value lower than timeout.
- **Remote Daemon (Demon distant)** :
  For debug purposes only, must remain unchecked.
  
## 3. Plugin startup
> Before starting the plugin, make sur all your Marstek devices are connected to the same network as your Jeedom.
- Start the plugin
- The plugin will automatically detect Marstek devices on your network and create associated Jeedom Equipment.
  (the detection period will last ~15s).
- The plugin will then enter the main loop, polling API and executing command coming from Jeedom

## 4. Functionning

### 4.1. Periodical poll
The plugin periodically polls data on detected devices (1 loop is done every *Polling Period* seconds minimum).\
The polling period may be much longer than the specified minimum value, depending on the number of devices on your network, the request timeout and retry.\
For performance concerns, not all data are retrieve at every loop.
> **Note :** Wifi and bluetooth data are read only once at device discovery, they are not updated afterward.

### 4.2. Requested data depending loop
The full set of Data is retrived after 100 s by default *(10xPolling Period default value)*.
- **Every loop** :
  By default, those values are retrieved every 10s *(Polling Period default value)*.
  - Battery Mode
  - Battery SOC
  - On-grid power
  - Off-grid power
- **Every 3 loops** :
  By default, those values are retrieved every 30s *(3xPolling Period default value)*.
  - Battery temperature
  - Battery Remaing capacity
- **Every 5 loops** :
  By default, those values are retrieved every 50s *(5xPolling Period default value)*.
  - Meter State
  - Meter A power value
  - Meter B power value
  - Meter C power value
  - Meter total power value
  - PV power (Venus D only)
  - PV current (Venus D only)
  - PV voltage (Venus D only)
- **Every 10 loops** :
  By default, those values are retrieved every 100s *(10xPolling Period default value)*.
  - Total Grid Input Energy
  - Total Grid Output Energy
  - Total load Energy
  - Total Solar Energy (Venus D only)
    
### 4.3. Calculated data
The plugin also provides calculated data for each device :
- **Battery State** : Can be Charing/Discharging/Idle/Passthrough *(based on On-grid power and Off-grid power)*
- **Battery SOH** : Calculated whenb SOC is 100% and charging is completed.
## 5. Todo / Knwon issues
Here is a non-exhaustive list of things not yet implemented and known issues :
- Battery software sometimes crash : it reverts to manual mode, Idle, CT lost and API disconnected.
  *I noticed this behaviour on Venus E Gen 3.0 on firmware 145.116.110, not sure if it is due to the plugin polling or not.*
- TODO : Jeedom information specific to PV are not created yet (even if Venus D is detected).
- And probably much more undiscovered remaining ...
