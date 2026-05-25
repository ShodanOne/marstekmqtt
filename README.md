# Marstek Plugin for Jeedom

<img width="154" height="174" alt="Image" src="https://github.com/user-attachments/assets/1f65299b-b955-4b85-9443-9262e751178c" />

> **Firmware warning:** Marstek’s Local API firmware is still immature, so most glitches do not come from this plugin.
> Report issues to Marstek unless you can clearly trace them to this project.\
> **Note :** This plugin has been tested on a Venus E 3.0 with firmware 148.

Jeedom plugin for Marstek energy storage systems using the official Local API (Rev 2.0) and Modbus over IP.\
It provides comprehensive monitoring and control of Marstek Venus C/D/E devices without requiring cloud connectivity.

This plugin is still in beta version. It should works with the following Marstek Devices : Venus C, Venus D, Venus E.

It relies on marstek_local_api from [ha-marstek-api](https://github.com/jaapp/ha-marstek-local-api) project

## Prerequisites

- Local API must be enabled in Marstek app
- Python 3.11 (will be installed by the plugin in *resources/venv* directory)
- paho-mqtt python library (will be installed by the plugin in *resources/venv* directory)
- pymodbus python library (will be installed by the plugin in *resources/venv* directory)
- pyyaml python library (will be installed by the plugin in *resources/venv* directory)
- [marstek_local_api](https://github.com/jaapp/ha-marstek-local-api/tree/master/custom_components/marstek_local_api) (will be installed by the plugin in *3rdparty* directory)
- Jeddom [MQTT Manager](https://market.jeedom.com/index.php?v=d&p=market_display&id=4213) plugin

## 1. Installation

- Jeedom [MQTT Manager](https://market.jeedom.com/index.php?v=d&p=market_display&id=4213) plugin must be installed and running on your Jeedom.
- unzip the folder in your Jeedom /plugins directory (or upload marstekmqtt directory in/plugins using Jeedom file editor
- make sure the plugin directory name is *marstekmqtt* in your Jeedom *plugins* directory
- Go to th plugin management section
- Select marstekmqtt plugin
- Activate the plugin :
    - dependencies install should start automatically (if not, launch dependencies manually)
      > First dependencies install may take time especially if Python 3.11 must be installed in venv
  
## 2. Plugin Configuration

<img width="2656" height="342" alt="Image" src="https://github.com/user-attachments/assets/5a58188f-9121-49e6-a330-93cd7476f880" />

Default configuration should work as long as API has been enabled from the app on port 30000.\
From lessons learned, it is recommanded to set Timeout = 10s / Retry = 3 / Period = 60s.

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
  > Does not make sense to set a value lower than timeout.
- **Remote Daemon (Demon distant)** :
  For debug purposes only, must remain unchecked.
  
## 3. Plugin startup
> Before starting the plugin, make sur all your Marstek devices are connected to the same network as your Jeedom.
- Start the plugin
- The plugin will automatically detect Marstek devices on your network and create associated Jeedom Equipment.
  (the detection period will last ~15s).
- The plugin will then enter the main loop, polling API or Modbus and executing command coming from Jeedom
### 3.1. Device page Example
Here is a screenshot of an automatically created device :
<img width="3008" height="1190" alt="image" src="https://github.com/user-attachments/assets/23db43e4-5771-48c6-a33c-b00a5a963da6" />

- Device name can be modified.
- Network information are read at detection
- Hybrid mode can be activated/de-activated
  >- When activated : Modbus IP, Modbus Port and Server Id must be specified
  >- Default vlaue for Modbus Port is 502
  >- Default value for Server Id is 1 (works with Elfin module), you may try 0 if your get error when trying to retrieve Modbus data. 
- Additionnal information on the device are provided

### 3.2. Device dashboard interface
Here is a screenshot of a dashboard viewof the device (I know, it's ugly, but I am not familiar at all with html coding) :
<img width="250" height="750" alt="image" src="https://github.com/user-attachments/assets/0d191037-6beb-4d0c-a51d-1d47891f4ac4" />

## 4. Functionning

### 4.1. Periodical poll
Periodical poll is the defaut mode, it relies only on the Local UDP API.
The plugin periodically polls data on detected devices (1 loop is done every *Polling Period* seconds minimum).\
The polling period may be much longer than the specified minimum value, depending if timeout is reached timeout and retry tentative.\
For performance concerns, not all data are retrieve at every loop.
> **Note :** Wifi and bluetooth data are read only once at device discovery, they are not updated afterward.

**Requested data depending loop**
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

### 4.2. Hybid Mode
Hybrid mode is a dedicated mode that mainly relies on Modbus over IP. It requires A modbus to IP device (like Elfin EW11 module) to be connected to RS485 port, or a wire ethernet connection for Venus C 3.0.\
It can be activated through the device configuration page. You can revert to Periodical Poll through API at any time by de-activating Hybrid mode.\
Hybrid mode activate 4 different task for each battery :
- **Every 1 sec** :
  - Battery state is read on Modbus
  - Upon battery state change : On-Grid Power, Off-Grid Power and SOC are read on Modbus

- **Every 10 sec** :
  if Battery is not in 'Standby' State :
  - On-Grid Power, Off-Grid Power and SOC are read on Modbus
  - Battery capacity is calculated
  - 
- **Every 1 min** :
  - Temperature, total input Energy, total Output Energy are read on Modbus
  - Battery efficiency is calculated
  - battery mode is read through API
 
- **Every 10 min** :
  - Battery total capacity and battery firmware are read on Modbus

>**Note**: In hybrid mode, CT data are not retrieved and are all set to zero.

### 4.3. Calculated data
The plugin also provides calculated data for each device :
- **Battery SOH** : Calculated when SOC is 100% and charging is completed => This may be removed in future version since it may not be relevant.
* In API Polling mode, 'Battery State' is calculated (based on On-grid power and Off-grid power) : can be Charing/Discharging/Standby/Passthrough*

### 4.4. Commands
The plugin allows to change battery mode between Auto, AI, Manual, Passive and UPS.

<img width="333" height="180" alt="image" src="https://github.com/user-attachments/assets/36c77679-a451-4410-a3bb-d0e4c003a774" />

- **Auto, AI and UPS** mode :
   Those 3 modes do not require any additionnal parameters, just click on the command to activate.
- **Manual** mode :
  - Calendar :
    The plugin does not implement a 'calendar' selection for this mode (and will probably never, since I'm not good at html coding).\
    It hard codes a calendar that is active at anytime (from 00:00 to 23:59, everyday).
    > **Warning** : this calendar will overwrite the one you may have created in the app
  - Power value :
    The desired power value is specified through the *Mode Power* value (negative for charging, positive for discharging).
    > Note *Mode Power* value is taken into account at mode activation only (if you change it later, the power value for Manual mode will remain unchanged)
- **Passive** mode :
  - Power value :
    The desired power value is specified through the *Mode Power* value (negative for charging, positive for discharging).
    > Note *Mode Power* value is taken into account at mode activation only (if you change it later, the power value for Passive mode will remain unchanged)
  - Duration :
    The duration for the passive mode is currently hard coded to 300s. It may be possible to adjust it in future release of the plugin.
    
## 5. Todo / Known issues
Here is a non-exhaustive list of things not yet implemented and known issues :
- Battery software sometimes crash : it reverts to manual mode, Idle, CT lost (arbitrary changed to CT-003) and API disconnected.\
  *This issues has been reported on ha_marstek-local-api Github, it seems to be a weakness of Marstek API (do not hesitate to report it to Marstek using the app). Increasing Timeout/poll period may help to avoid the issue.*
- Plugin does not allow to specify a calendar for Manual Mode.
- TODO : Jeedom information specific to PV are not created yet (even if Venus D is detected).
- TODO : Add command to allow duration adjustment for Passive Mode
- TODO : Dynamic power value change for Manual and Passive mode 
- And probably much more undiscovered issues remaining ...
