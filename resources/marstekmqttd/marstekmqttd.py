import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable
import argparse
import logging
import time
import paho.mqtt.client as mqtt
import os

MARSTEK_TOPIC_DEVICE = "marstek/device"
MARSTEK_TOPIC_STATUS = "marstek/status"
MARSTEK_TOPIC_ACTION = "marstek/action"


def load_module_from_file(module_name: str, file_path: Path):
    """Load a Python module directly from a file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Get paths to integration modules
# Try common locations
integration_path = Path(__file__).parent / "marstek_local_api"
if not integration_path.exists():
    # Try HA location
    integration_path = Path("/marstek_local_api")

if not integration_path.exists():
    print(f"ERROR: Cannot find integration at:")
    print(f"  - {Path(__file__).parent / 'marstek_local_api'}")
    print(f"  - /marstek_local_api")
    sys.exit(1)

# Create a fake package structure to allow relative imports
package_name = "marstek_local_api"

# Ensure package hierarchy exists for relative imports
custom_components_pkg = sys.modules.get("custom_components")
if custom_components_pkg is None:
    custom_components_pkg = type(sys)("custom_components")
    custom_components_pkg.__path__ = [str(integration_path.parent)]
    sys.modules["custom_components"] = custom_components_pkg

marstek_pkg = sys.modules.get(package_name)
if marstek_pkg is None:
    marstek_pkg = type(sys)(package_name)
    marstek_pkg.__path__ = [str(integration_path)]
    sys.modules[package_name] = marstek_pkg

# Mock homeassistant modules that are imported by integration
# Create a mock HomeAssistant class and other required classes
class MockHomeAssistant:
    """Mock HomeAssistant class."""
    pass

class MockDataUpdateCoordinator:
    """Mock DataUpdateCoordinator class."""
    def __init__(self, hass, logger, name, update_interval):
        """Mock init that accepts coordinator parameters."""
        pass

class MockUpdateFailed(Exception):
    """Mock UpdateFailed exception."""
    pass

class MockSensorDeviceClass:
    """Mock SensorDeviceClass."""
    BATTERY = "battery"
    TEMPERATURE = "temperature"
    ENERGY_STORAGE = "energy_storage"
    POWER = "power"
    ENERGY = "energy"
    SIGNAL_STRENGTH = "signal_strength"
    DURATION = "duration"
    VOLTAGE = "voltage"
    CURRENT = "current"

class MockSensorEntity:
    """Mock SensorEntity class."""
    pass

@dataclass
class MockSensorEntityDescription:
    """Mock SensorEntityDescription class."""
    key: str
    name: str | None = None
    native_unit_of_measurement: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    value_fn: Callable[[dict], Any] | None = None
    available_fn: Callable[[dict], bool] | None = None

class MockSensorStateClass:
    """Mock SensorStateClass."""
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"

class MockConfigEntry:
    """Mock ConfigEntry class."""
    pass

class MockDeviceInfo:
    """Mock DeviceInfo class."""
    pass

class MockCoordinatorEntity:
    """Mock CoordinatorEntity class."""
    pass

class MockAddEntitiesCallback:
    """Mock AddEntitiesCallback class."""
    pass

# Create mock modules
homeassistant_core = type(sys)('homeassistant.core')
homeassistant_core.HomeAssistant = MockHomeAssistant

homeassistant_helpers_update_coordinator = type(sys)('homeassistant.helpers.update_coordinator')
homeassistant_helpers_update_coordinator.DataUpdateCoordinator = MockDataUpdateCoordinator
homeassistant_helpers_update_coordinator.UpdateFailed = MockUpdateFailed
homeassistant_helpers_update_coordinator.CoordinatorEntity = MockCoordinatorEntity

homeassistant_components_sensor = type(sys)('homeassistant.components.sensor')
homeassistant_components_sensor.SensorDeviceClass = MockSensorDeviceClass
homeassistant_components_sensor.SensorEntity = MockSensorEntity
homeassistant_components_sensor.SensorEntityDescription = MockSensorEntityDescription
homeassistant_components_sensor.SensorStateClass = MockSensorStateClass

homeassistant_config_entries = type(sys)('homeassistant.config_entries')
homeassistant_config_entries.ConfigEntry = MockConfigEntry

homeassistant_const = type(sys)('homeassistant.const')
homeassistant_const.PERCENTAGE = "%"
homeassistant_const.UnitOfElectricCurrent = type('UnitOfElectricCurrent', (), {'AMPERE': 'A'})()
homeassistant_const.UnitOfElectricPotential = type('UnitOfElectricPotential', (), {'VOLT': 'V'})()
homeassistant_const.UnitOfEnergy = type('UnitOfEnergy', (), {'WATT_HOUR': 'Wh', 'KILO_WATT_HOUR': 'kWh'})()
homeassistant_const.UnitOfPower = type('UnitOfPower', (), {'WATT': 'W'})()
homeassistant_const.UnitOfTemperature = type('UnitOfTemperature', (), {'CELSIUS': '°C'})()
homeassistant_const.UnitOfTime = type('UnitOfTime', (), {'SECONDS': 's'})()

homeassistant_helpers_entity = type(sys)('homeassistant.helpers.entity')
homeassistant_helpers_entity.DeviceInfo = MockDeviceInfo

homeassistant_helpers_entity_platform = type(sys)('homeassistant.helpers.entity_platform')
homeassistant_helpers_entity_platform.AddEntitiesCallback = MockAddEntitiesCallback

# Register mock modules
sys.modules['homeassistant'] = type(sys)('homeassistant')
sys.modules['homeassistant.core'] = homeassistant_core
sys.modules['homeassistant.helpers'] = type(sys)('homeassistant.helpers')
sys.modules['homeassistant.helpers.update_coordinator'] = homeassistant_helpers_update_coordinator
sys.modules['homeassistant.components'] = type(sys)('homeassistant.components')
sys.modules['homeassistant.components.sensor'] = homeassistant_components_sensor
sys.modules['homeassistant.config_entries'] = homeassistant_config_entries
sys.modules['homeassistant.const'] = homeassistant_const
sys.modules['homeassistant.helpers.entity'] = homeassistant_helpers_entity
sys.modules['homeassistant.helpers.entity_platform'] = homeassistant_helpers_entity_platform

# Load integration modules in dependency order
const = load_module_from_file(f"{package_name}.const", integration_path / "const.py")
api_module = load_module_from_file(f"{package_name}.api", integration_path / "api.py")
#coordinator_module = load_module_from_file(f"{package_name}.coordinator", integration_path / "coordinator.py")
#sensor_module = load_module_from_file(f"{package_name}.sensor", integration_path / "sensor.py")
compat_module = load_module_from_file(f"{package_name}.compatibility", integration_path / "compatibility.py")

# Extract what we need
MarstekUDPClient = api_module.MarstekUDPClient
CompatibilityMatrix = compat_module.CompatibilityMatrix
DEFAULT_PORT = const.DEFAULT_PORT
DEVICE_MODEL_VENUS_D = const.DEVICE_MODEL_VENUS_D
#SENSOR_TYPES = sensor_module.SENSOR_TYPES


class MockHass:
    """Mock Home Assistant object for testing."""

    def __init__(self):
        self.data = {}

def format_value(value, unit=""):
    """Format value with unit for display."""
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{value}{unit}"
    return str(value)

def main(args):
    param = {}
    if args.log == "debug":
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(asctime)s %(message)s")
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(message)s")
    logger = logging.getLogger()

    logger.info("Daemon started successfully\n")
    logger.debug("MQTTIP=" + args.mqtt_address + " Port=" + str(args.mqtt_port))
    #logger.debug("MQTTClient=" + args.mqtt_client)
    #logger.debug("MQTTuser=" + args.mqtt_username + " MQTTpass=" + args.mqtt_password + "\n")

    param['mqtt-ip'] = args.mqtt_address
    param['mqtt-port'] = args.mqtt_port
    #param['mqtt-client'] = args.mqtt_client
    param['mqtt-username'] = args.mqtt_username
    param['mqtt-password'] = args.mqtt_password
    param['timeout'] = args.timeout
    param['retry'] = args.retry
    param['period'] = args.poll_period
    param['pidfile'] = args.pidfile

    # Ecriture du fichier PID
    pid = str(os.getpid())
    logger.warning("Writing PID %s to %s", pid, param['pidfile'])
    open(param['pidfile'], 'w').write("%s\n" % pid)

    try :
        asyncio.run(action(param))
    except (EOFError, SystemExit, KeyboardInterrupt):
        os.remove(param['pidfile'])
        sys.exit(0)



async def action(param):

    logger = logging.getLogger()
    loop_count:int = 1
    fail_count:int = 0

    def add_to_update(dst, src, filter):
        retval = dst
        for k in src.keys():
            if k in filter:
                retval[k] = src[k]
            elif src[k] != 0:
                logger.warning('⚠️ IGNORED data with attribute '+k+'='+str(src[k]))
        return retval

    def update_es_mode(dst, src):
        filter = {'id', 'bat_soc', 'mode', 'ongrid_power', 'offgrid_power'}
        retval = add_to_update(dst, src, filter)
        return retval

    def update_battery_status(dst, src):
        filter = {'bat_soc', 'charg_flag', 'dischrg_flag', 'bat_temp', 'bat_capacity','rated_capacity'}
        retval = add_to_update(dst, src, filter)
        return retval

    def update_em_status(dst, src):
        filter = {'a_power', 'b_power', 'c_power', 'ct_state', 'input_energy', 'output_energy', 'total_power'}
        retval = add_to_update(dst, src, filter)
        return retval

    def update_pv_status(dst, src):
        filter = {'pv_power', 'pv_voltage', 'pv_current'}
        retval = add_to_update(dst, src, filter)
        return retval

    def update_es_status(dst, src):
        filter = {'bat_soc', 'bat_capacity', 'total_grid_input_energy', 'total_grid_output_energy', 'total_load_energy', 'total_pv_energy'}
        retval = add_to_update(dst, src, filter)
        return retval

    def update_and_send_device_changes(index, value):
        changed = []
        for k in value.keys():
            if k in devices[index].keys():
                if devices[index][k] != value[k]:
                    devices[index][k] = value[k]
                    changed.append(k)
            else:
                devices[index][k] = value[k]
                changed.append(k)
        if changed:
            src = devices[index]['name']+'-'+devices[index]['ble_mac']
            topic_prefix = MARSTEK_TOPIC_STATUS
            topic_str = '{}/{}'.format(topic_prefix, src)
            data={}
            for k in changed:
                data[k] = devices[index][k]
            payload = json.dumps(data)
            pub = mqttc.publish(topic_str, payload, retain=True)
            pub.wait_for_publish()

    def on_connect(client, userdata, flags, rc):
        client.subscribe("{}/#".format(MARSTEK_TOPIC_ACTION))

    def on_message(client, userdata, message):
        topic = message.topic
        data = message.payload
        src = topic.replace('{}/'.format(MARSTEK_TOPIC_ACTION), '')
        tabsrc = src.split('-')
        name = tabsrc[0]
        ble_mac = tabsrc[1]
        for dev in devices:
            if (dev['name'] == name) and (dev['ble_mac'] == ble_mac):
                msg = json.loads(data)
                config = None
                if msg['cmd'] == 'Auto':
                    config= {
                        "mode": "Auto",
                        "auto_cfg": {
                            "enable": 1}}
                elif msg['cmd'] == 'AI':
                    config = {
                        "mode": "AI",
                        "ai_cfg": {
                            "enable": 1}}
                elif msg['cmd'] == 'Manual':
                    config = {
                        "mode": "Manual",
                        "manual_cfg": {
                            "time_num": 1,
                            "start_time": "00:00",
                            "end_time": "23:59",
                            "week_set": 127,
                            "power": msg['power'],
                            "enable": 1}}
                elif msg['cmd'] == 'Passive':
                    config = {
                        "mode": "Passive",
                        "passive_cfg": {"power": msg['power'],
                                        "cd_time": 300}}
                if config:
                    logger.info('Sending Command : ' + json.dumps(config))
                    try:
                        api.host = dev['ip']
                        send_result = asyncio.run(api.set_es_mode(config))
                        if not(send_result):
                            logging.warning("⚠️ Unexpected result while sending command " + json.dumps(config) + " - something may have went wrong !")
                        else:
                            logging.warning("✅ Command "+ json.dumps(config) + " sent successfully !")
                    except PermissionError as err:
                        logging.error(f"❌ Unable to open UDP socket on port {DEFAULT_PORT}: {err}")
                    except Exception as e:
                        logging.error(f"❌ Error during api call: {e}")
                        import traceback
                        traceback.print_exc()
                    break

    def send_detected_devices(devList):
        topic_prefix = MARSTEK_TOPIC_DEVICE
        for dev in devList:
            src = dev['name']+'-'+dev['ble_mac']
            topic_str = '{}/{}'.format(topic_prefix, src)
            payload = json.dumps(dev)
            pub = mqttc.publish(topic_str, payload, retain=True)
            pub.wait_for_publish()

    async def discover():
        devList = []
        try:
            logger.debug(f"Broadcasting on port {DEFAULT_PORT}...")
            devList = await api.discover_devices(timeout=10)
        except PermissionError as err:
            logger.error(f"❌ Unable to open UDP socket on port {DEFAULT_PORT}: {err}")
            return devList
        except Exception as e:
            print(f"❌ Error during discover: {e}")
            import traceback
            traceback.print_exc()
            return devList
        if devList:
            send_detected_devices(devList)
        return devList

    # Init variables
    devices = []

    # Init Marstek API
    hass = MockHass()
    api = MarstekUDPClient(hass, port=DEFAULT_PORT)

    # demarrage MQTT
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    if param['mqtt-username'] and param['mqtt-password']:
        logger.info('MQTT username and password provided')
        mqttc.username_pw_set(username=param['mqtt-username'], password=param['mqtt-password'])
    mqttc.connect(host=param['mqtt-ip'], port=param['mqtt-port'], keepalive=60)
    mqttc.on_message = on_message
    mqttc.on_connect = on_connect
    mqttc.loop_start()

    # Boucle detection initiale des batteries
    while not devices:
        await api.connect()
        await asyncio.sleep(1.0)
        devices = await discover()
        if not devices:
            logger.warning("❌ No devices found! Retrying...")
            await api.disconnect()
            await asyncio.sleep(1.0)

    if devices:
        logger.info(f"✅ Found {len(devices)} device(s):")
        for i, device in enumerate(devices, 1):
            logger.info(f"Device {i}:")
            logger.info(f"  Model:       {device['name']}")
            logger.info(f"  IP Address:  {device['ip']}")
            logger.info(f"  MAC:         {device['mac']}")
            logger.info(f"  Firmware:    v{device['firmware']}")
            logger.info("-----------------------------------")

    # demarrage API
    await asyncio.sleep(2.0)
    await api.connect()

    # Boucle principale
    while True:
        logger.info("--------- Loop " + str(loop_count) + " ---------")
        starttime = time.perf_counter()
        for device_idx, device in enumerate(devices, 1):

            firmware = device['firmware']
            is_venus_d = device['name'] == DEVICE_MODEL_VENUS_D
            update = {}

            # Initialisation de la matrice de compatibilité
            scalingMatrix = CompatibilityMatrix(device['name'], firmware)

            # recupération de 'ES.mode' à chaque cycle
            try:
                api.host = device['ip']
                mode_status = await api.get_es_mode(timeout=param['timeout'], max_attempts=param['retry'])
            except PermissionError as err:
                logging.error(f"❌ Unable to open UDP socket on port {DEFAULT_PORT}: {err}")
                fail_count += 1
            except (EOFError, SystemExit,KeyboardInterrupt) :
                raise
            except Exception as e:
                logging.error(f"❌ Error during api call: {e}")
                import traceback
                traceback.print_exc()
                fail_count += 1

            if mode_status:
                update = update_es_mode(update, mode_status)
                try :
                    logger.info(f"  Current Mode:           {update['mode']}")
                    logger.info(f"  Grid Power:             {format_value(update['ongrid_power'], ' W')}")
                    logger.info(f"  Off-Grid Power:         {format_value(update['offgrid_power'], ' W')}")
                    logger.info(f"  Battery SOC:            {format_value(update['bat_soc'], '%')}")
                    #update_and_send_device_changes(device_idx-1, mode_status)
                    fail_count = 0
                except KeyError as e:
                    logger.error("Key error while reading mode => "+json.dumps(mode_status))
                    logger.error("Exception "+str(e))
            else:
                logger.warning("⚠️  Failed to get operating mode")
                fail_count += param['retry']

            # recuperation de 'battery status' tous les 3 cycles
            if loop_count % 3 == 0:
                try :
                    api.host = device['ip']
                    battery_status = await api.get_battery_status(timeout=param['timeout'], max_attempts=param['retry'])
                except PermissionError as err:
                    logging.error(f"❌ Unable to open UDP socket on port {DEFAULT_PORT}: {err}")
                    fail_count += 1
                except (EOFError, SystemExit, KeyboardInterrupt):
                    raise
                except Exception as e:
                    logging.error(f"❌ Error during api call: {e}")
                    import traceback
                    traceback.print_exc()
                    fail_count += 1

                if battery_status:
                    try :
                        battery_status['bat_temp'] = scalingMatrix.scale_value(battery_status['bat_temp'],'bat_temp')
                        battery_status['bat_capacity'] = scalingMatrix.scale_value(battery_status['bat_capacity'],'bat_capacity')
                        battery_status['bat_soc'] = battery_status.get('soc')
                        del battery_status['soc']
                        update = update_battery_status(update, battery_status)

                        logger.info(f"  State of Charge:        {format_value(update['bat_soc'], '%')}")
                        logger.info(f"  Temperature:            {format_value(update['bat_temp'], '°C')}")
                        logger.info(f"  Remaining Capacity:     {format_value(update['bat_capacity'], ' Wh')}")
                        logger.info(f"  Rated Capacity:         {format_value(update['rated_capacity'], ' Wh')}")
                        logger.info(f"  Charging Enabled:       {update['charg_flag']}")
                        logger.info(f"  Discharging Enabled:    {update['dischrg_flag']}")
                        fail_count = 0
                    except KeyError as e:
                        logger.error("Key error while reading battery_status => " + json.dumps(battery_status))
                        logger.error("Exception " + str(e))
                else:
                    logger.warning("⚠️  Failed to get battery status")
                    fail_count += param['retry']

            # recuperation de 'EM' et 'PV' (si applicable) tous les 5 cycles
            if loop_count % 5 == 0:  # CT / PV
                try:
                    api.host = device['ip']
                    em_status = await api.get_em_status(timeout=param['timeout'], max_attempts=param['retry'])
                except PermissionError as err:
                    logging.error(f"❌ Unable to open UDP socket on port {DEFAULT_PORT}: {err}")
                    fail_count += 1
                except (EOFError, SystemExit, KeyboardInterrupt):
                    raise
                except Exception as e:
                    logging.error(f"❌ Error during api call: {e}")
                    import traceback
                    traceback.print_exc()
                    fail_count += 1

                if em_status:
                    try :
                        update = update_em_status(update, em_status)
                        ct_connected = em_status['ct_state'] == 1
                        logger.info(f"  CT Connected:           {ct_connected}")
                        if ct_connected:
                            logger.info(f"  Phase A Power:          {format_value(em_status['a_power'], ' W')}")
                            logger.info(f"  Phase B Power:          {format_value(em_status['b_power'], ' W')}")
                            logger.info(f"  Phase C Power:          {format_value(em_status['c_power'], ' W')}")
                            logger.info(f"  Total Power:            {format_value(em_status['total_power'], ' W')}")
                        else:
                            logger.info("  (No CT connected)")
                        fail_count = 0
                    except KeyError as e:
                        logger.error("Key error while reading em_status => " + json.dumps(em_status))
                        logger.error("Exception " + str(e))
                else:
                    logger.warning("⚠️  Failed to get energy meter status")
                    fail_count += param['retry']

                if is_venus_d:
                    try:
                        api.host = device['ip']
                        pv_status = await api.get_pv_status(timeout=param['timeout'], max_attempts=param['retry'])
                    except PermissionError as err:
                        logging.error(f"❌ Unable to open UDP socket on port {DEFAULT_PORT}: {err}")
                        fail_count += 1
                    except (EOFError, SystemExit, KeyboardInterrupt):
                        raise
                    except Exception as e:
                        logging.error(f"❌ Error during api call: {e}")
                        import traceback
                        traceback.print_exc()
                        fail_count += 1
                    if pv_status:
                        try :
                            update = update_pv_status(update, pv_status)
                            logger.info(f"  PV Power:               {format_value(pv_status['pv_power'], ' W')}")
                            logger.info(f"  PV Voltage:             {format_value(pv_status['pv_voltage'], ' V')}")
                            logger.info(f"  PV Current:             {format_value(pv_status['pv_current'], ' A')}")
                            fail_count = 0
                        except KeyError as e:
                            logger.error("Key error while reading pv_status => " + json.dumps(pv_status))
                            logger.error("Exception " + str(e))
                    else:
                        logger.warning("⚠️  Failed to get PV status")
                        fail_count += param['retry']

            # Recupération de ES tous les 10 cycles
            if loop_count % 10 == 0:
                try:
                    api.host = device['ip']
                    es_status = await api.get_es_status(timeout=param['timeout'], max_attempts=param['retry'])
                except PermissionError as err:
                    logging.error(f"❌ Unable to open UDP socket on port {DEFAULT_PORT}: {err}")
                    fail_count += 1
                except (EOFError, SystemExit, KeyboardInterrupt):
                    raise
                except Exception as e:
                    logging.error(f"❌ Error during api call: {e}")
                    import traceback
                    traceback.print_exc()
                    fail_count += 1
                if es_status:
                    try :
                        es_status['total_grid_input_energy'] = scalingMatrix.scale_value(es_status['total_grid_input_energy'], 'total_grid_input_energy')
                        es_status['total_grid_output_energy'] = scalingMatrix.scale_value(es_status['total_grid_output_energy'], 'total_grid_output_energy')
                        es_status['total_load_energy'] = scalingMatrix.scale_value(es_status['total_load_energy'],'total_load_energy')
                        update = update_es_status(update, es_status)
                        logger.info(f"  Total Solar Energy:     {format_value(es_status['total_pv_energy'], ' Wh')}")
                        logger.info(f"  Total Grid Import:      {format_value(es_status['total_grid_input_energy'], ' Wh')}")
                        logger.info(f"  Total Grid Export:      {format_value(es_status['total_grid_output_energy'], ' Wh')}")
                        logger.info(f"  Total Load Energy:      {format_value(es_status['total_load_energy'], ' Wh')}")
                        fail_count = 0
                    except KeyError as e:
                        logger.error("Key error while reading es_status => " + json.dumps(es_status))
                        logger.error("Exception " + str(e))
                else:
                    logger.warning("⚠️  Failed to get energy system status")
                    fail_count += param['retry']

            update_and_send_device_changes(device_idx - 1, update)

        # calcul de la durée de pause avant de recommencer une boucle
        endtime = time.perf_counter()
        elapsed = endtime - starttime
        if elapsed < param['period']:
            duration = param['period'] - elapsed
            await asyncio.sleep(duration)
        else:
            await asyncio.sleep(1.0)

        # incrémentation du numero de boucle modulo 30
        loop_count += 1
        if loop_count > 30:
            loop_count=1

        # Surveillance de la connection
        if fail_count > 10:
            logger.error('❌ Battery not responsing, trying to reconnect ...')
            logger.error('-> Disconnecting ...')
            await api.disconnect()
            await asyncio.sleep(1.0)
            logger.error('-> Reconnecting ...')
            api = MarstekUDPClient(hass, port=DEFAULT_PORT)
            await api.connect()
            fail_count = 0

parser = argparse.ArgumentParser(prog='testmqtt')
parser.add_argument("--mqtt_address", type=str, help="mqtt ip address", default="192.168.0.70")
#parser.add_argument("--mqtt_client", type=str, help="mqtt client id", default="marstek")
parser.add_argument("--mqtt_port", type=int, help="mqtt ip port", default=1883)
parser.add_argument("--mqtt-username", type=str, help="MQTT username", default="Shodan")
parser.add_argument("--mqtt-password", type=str, help="MQTT password",default="Raph33")
parser.add_argument("--timeout", type=int, help="Marstek API timeout",default=5)
parser.add_argument("--retry", type=int, help="Marstek API retry#",default=3)
parser.add_argument("--poll_period", type=int, help="Marstek API poll period",default=10.0)
parser.add_argument("--pidfile", type=str, help="MQTT password",default="daemon.pid")
parser.add_argument("--log", type=str, help="logging level", default="info")
parser.set_defaults(func=main)
args = parser.parse_args()
args.func(args)
