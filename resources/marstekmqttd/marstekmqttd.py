"""
marstekmqttd.py — Daemon MQTT pour batteries Marstek
=====================================================

Deux modes de fonctionnement par batterie :

  Mode UDP pur (hybrid_mode=False, défaut)
  ─────────────────────────────────────────
  Boucle à période fixe (param['period']).
  Fréquences relatives par modulo (×3, ×5, ×10) comme dans la version originale.
  Tout passe par MarstekUDPClient.

  Mode Hybride UDP + Modbus/TCP (hybrid_mode=True)
  ─────────────────────────────────────────────────
  4 tâches asyncio indépendantes par worker :

    _task_1s   (Modbus)
    _task_10 (Modbus)
    _task_1min (ModBus+UDP)
    _task_10min   (Modbus)

  La config hybride est reçue via MQTT sur le topic
  marstek/config/{name-ble_mac}, envoyée une seule fois au démarrage.
  Le worker bascule en mode hybride à la volée, sans redémarrage.

Parallélisme
────────────
  Un DeviceWorker par batterie, tous lancés en parallèle via asyncio.gather().
  Chaque worker possède sa propre instance MarstekUDPClient et AsyncModbusTcpClient.
  L'état partagé (mqttc, mqtt_lock, command_queue, config_queue) est passé en paramètre.
"""

import asyncio
from dataclasses import dataclass
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable, TypedDict, Optional
import argparse
import logging
import time
import paho.mqtt.client as mqtt
import os
import yaml
from marstekdata import MARSTEK_REGISTER,MARSTEK_API_SCALER

# ---------------------------------------------------------------------------
# Topics MQTT
# ---------------------------------------------------------------------------
MARSTEK_TOPIC_DEVICE = "marstek/device"
MARSTEK_TOPIC_STATUS = "marstek/status"
MARSTEK_TOPIC_ACTION = "marstek/action"
MARSTEK_TOPIC_CONFIG = "marstek/config"   # ← nouveau : réception config hybride

# Port Modbus TCP standard
MODBUS_DEFAULT_PORT = 502

# ---------------------------------------------------------------------------
# Chargement dynamique de l'intégration Marstek (hors Home Assistant)
# ---------------------------------------------------------------------------

def load_module_from_file(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

integration_path = Path(__file__).parent.parent.parent / "3rdparty/marstek_local_api"
if not integration_path.exists():
    integration_path = Path("/marstek_local_api")
if not integration_path.exists():
    print("ERROR: Cannot find integration at:")
    print(f"  - {Path(__file__).parent.parent.parent / '3rdparty/marstek_local_api'}")
    print("  - /marstek_local_api")
    sys.exit(1)

package_name = "marstek_local_api"

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


# ---------------------------------------------------------------------------
# Mocks Home Assistant
# ---------------------------------------------------------------------------

class MockHomeAssistant:
    pass

class MockDataUpdateCoordinator:
    def __init__(self, hass, logger, name, update_interval):
        pass

class MockUpdateFailed(Exception):
    pass

class MockSensorDeviceClass:
    BATTERY = "battery"; TEMPERATURE = "temperature"; ENERGY_STORAGE = "energy_storage"
    POWER = "power"; ENERGY = "energy"; SIGNAL_STRENGTH = "signal_strength"
    DURATION = "duration"; VOLTAGE = "voltage"; CURRENT = "current"

class MockSensorEntity:
    pass

@dataclass
class MockSensorEntityDescription:
    key: str
    name: str | None = None
    native_unit_of_measurement: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    value_fn: Callable[[dict], Any] | None = None
    available_fn: Callable[[dict], bool] | None = None

class MockSensorStateClass:
    MEASUREMENT = "measurement"; TOTAL_INCREASING = "total_increasing"

class MockConfigEntry:
    pass

class MockDeviceInfo:
    pass

class MockCoordinatorEntity:
    pass

class MockAddEntitiesCallback:
    pass

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

# Chargement des modules Marstek
const         = load_module_from_file(f"{package_name}.const",         integration_path / "const.py")
api_module    = load_module_from_file(f"{package_name}.api",           integration_path / "api.py")

MarstekUDPClient     = api_module.MarstekUDPClient
DEFAULT_PORT         = const.DEFAULT_PORT
DEVICE_MODEL_VENUS_D = const.DEVICE_MODEL_VENUS_D

# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------

class DeviceState(TypedDict, total=False):
    name: str
    ip: str
    mac: str
    ble_mac: str
    firmware: str
    # Config hybride
    hybrid_mode: bool
    modbus_ip: Optional[str]
    modbus_port: int
    # Données communes
    mode: str
    bat_state: str
    bat_soc: Optional[int]
    ongrid_power: Optional[int]
    offgrid_power: Optional[int]
    bat_temp: Optional[float]
    bat_capacity: Optional[int]
    rated_capacity: Optional[int]
    charg_flag: Optional[bool]
    dischrg_flag: Optional[bool]
    a_power: Optional[int]
    b_power: Optional[int]
    c_power: Optional[int]
    ct_state: Optional[int]
    total_power: Optional[int]
    input_energy: Optional[int]
    output_energy: Optional[int]
    pv_power: Optional[int]
    pv_voltage: Optional[float]
    pv_current: Optional[float]
    total_grid_input_energy: Optional[int]
    total_grid_output_energy: Optional[int]
    total_load_energy: Optional[int]
    total_pv_energy: Optional[int]


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

class MockHass:
    def __init__(self):
        self.data = {}

def format_value(value, unit="") -> str:
    if value is None:
        return "N/A"
    return f"{value}{unit}" if isinstance(value, (int, float)) else str(value)

def load_config(config_file: Path) -> dict:
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def to_signed(val, size=1):
    retval = val
    if retval & (1 << (16*size - 1)):
        retval -= (1 << 16*size)
    return retval

# ---------------------------------------------------------------------------
# DeviceWorker
# ---------------------------------------------------------------------------

class DeviceWorker:
    """
    Worker autonome par batterie.

    Mode UDP pur  → une boucle cadencée par param['period'], fréquences en modulo.
    Mode hybride  → 4 tâches asyncio indépendantes (_task_1s, _task_10s,
                    _task_1min, _task_10min) lancées via asyncio.gather().
                    Basculement à la volée sur réception de la config MQTT.

    Ressources partagées (thread/coroutine-safe) :
      mqttc         — paho thread-safe pour publish()
      mqtt_lock     — asyncio.Lock pour sérialiser wait_for_publish()
      command_queue — asyncio.Queue : commandes MQTT (actions)
      config_queue  — asyncio.Queue : config hybride reçue par MQTT
    """

    def __init__(
        self,
        device: DeviceState,
        param: dict,
        mqttc: mqtt.Client,
        mqtt_lock: asyncio.Lock,
        command_queue: asyncio.Queue,
        config_queue: asyncio.Queue,
    ):
        self.device        = device
        self.param         = param
        self.mqttc         = mqttc
        self.mqtt_lock     = mqtt_lock
        self.command_queue = command_queue
        self.config_queue  = config_queue
        self.label         = f"{device['name']}-{device['ble_mac']}"
        self.logger        = logging.getLogger(f"worker.{self.label}")
        self.type = device['name']
        self.fw = str(device['firmware'])
        self.enabled: int = 1

        # État hybride
        self.hybrid_mode: bool        = False
        self.modbus_ip:   Optional[str] = None
        self.modbus_port: int          = MODBUS_DEFAULT_PORT
        self._modbus_client            = None   # AsyncModbusTcpClient, créé à la demande
        self.modbus_id: int           = 1
        self._hybrid_tasks: list[asyncio.Task] = []

        # UDP
        self.hass        = MockHass()
        self.api         = MarstekUDPClient(self.hass, port=param['port'])
        self.loop_count  = 1   # utilisé en mode UDP pur uniquement
        self.fail_count  = 0

    # -----------------------------------------------------------------------
    # Helpers merge/filtrage *** pour UDP seulement ***
    # -----------------------------------------------------------------------

    def _add_to_update(self, dst: dict, src: dict, keys: set) -> dict:
        for k, v in src.items():
            if k in keys:
                if k in MARSTEK_API_SCALER.keys():
                    btype = self.type
                    fw = self.fw
                    if btype not in MARSTEK_API_SCALER[k]:
                        btype = 'default'
                        self.logger.warning(f"⚠️  battery type = '{btype}' not found in scaler matrix, using 'default' type")
                    if fw not in MARSTEK_API_SCALER[k][btype]:
                        fw = 'default'
                        self.logger.warning(
                            f"⚠️  firware = '{fw}' not found in scaler matrix, using 'default' fw")
                    coeff = MARSTEK_API_SCALER[k][btype][fw]
                    dst[k] = v*coeff
                else:
                    dst[k] = v
            elif v != 0:
                self.logger.warning(f"⚠️  Data ignored : {k}={v}")
        return dst

    def _upd_es_mode(self, d, s):
        return self._add_to_update(d, s, {'id','bat_soc','mode','ongrid_power','offgrid_power'})
    def _upd_battery(self, d, s):
        return self._add_to_update(d, s, {'bat_soc','charg_flag','dischrg_flag','bat_temp','bat_capacity','rated_capacity'})
    def _upd_em(self, d, s):
        return self._add_to_update(d, s, {'a_power','b_power','c_power','ct_state','input_energy','output_energy','total_power'})
    def _upd_pv(self, d, s):
        return self._add_to_update(d, s, {'pv_power','pv_voltage','pv_current'})
    def _upd_es_status(self, d, s):
        return self._add_to_update(d, s, {'bat_soc','bat_capacity','total_grid_input_energy',
                                          'total_grid_output_energy','total_load_energy','total_pv_energy'})

    # -----------------------------------------------------------------------
    # Publication MQTT
    # -----------------------------------------------------------------------

    async def _publish(self, update: dict):
        """Publie uniquement les valeurs ayant changé."""
        changed = {k: v for k, v in update.items() if self.device.get(k) != v}
        if not changed:
            return
        self.device.update(changed)
        payload = json.dumps(changed)
        topic   = f"{MARSTEK_TOPIC_STATUS}/{self.label}"
        async with self.mqtt_lock:
            pub = self.mqttc.publish(topic, payload, retain=True)
            pub.wait_for_publish()

    # -----------------------------------------------------------------------
    # Appel UDP générique avec gestion d'erreur
    # -----------------------------------------------------------------------

    async def _udp_call(self, coro_fn, label: str):
        try:
            self.api.host = self.device['ip']
            return await coro_fn()
        except PermissionError as err:
            self.logger.error(f"❌ UDP Socket rejected ({label}) : {err}")
        except (EOFError, SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            self.logger.error(f"❌ UDP Error ({label}) : {e}")
            import traceback; traceback.print_exc()
        self.fail_count += 1
        return None

    # -----------------------------------------------------------------------
    # Reconnexion UDP
    # -----------------------------------------------------------------------

    async def _udp_reconnect(self):
        self.logger.error("❌ Battery UDP not responding, reconnecting...")
        await self.api.disconnect()
        await asyncio.sleep(1.0)
        self.api = MarstekUDPClient(self.hass, port=self.param['port'])
        await self.api.connect()
        self.fail_count = 0

    # -----------------------------------------------------------------------
    # Modbus : connexion / déconnexion / lecture
    # -----------------------------------------------------------------------

    async def _modbus_connect(self) -> bool:
        """Crée et connecte le client Modbus TCP. Retourne True si succès."""
        try:
            from pymodbus.client import AsyncModbusTcpClient
            self._modbus_client = AsyncModbusTcpClient(
                host=self.modbus_ip,
                port=self.modbus_port,
                timeout=self.param['timeout'],
            )
            await self._modbus_client.connect()
            if self._modbus_client.connected:
                self.logger.info(f"✅ Modbus connected → {self.modbus_ip}:{self.modbus_port}")
                return True
            else:
                self.logger.error(f"❌ Modbus : connection failed to {self.modbus_ip}:{self.modbus_port}")
                return False
        except Exception as e:
            self.logger.error(f"❌ Modbus connection exception : {e}")
            return False

    async def _modbus_disconnect(self):
        if self._modbus_client and self._modbus_client.connected:
            self._modbus_client.close()
            self._modbus_client = None
            self.logger.info("Modbus disconnected")

    async def _modbus_read_registers(self, address: int, count: int, unit: int = 1) -> Optional[list]:
        """
        Lit `count` registres Holding à partir de `address`.
        Reconnecte automatiquement si nécessaire.
        Retourne la liste des valeurs brutes, ou None en cas d'erreur.
        """
        for attempt in range(self.param['retry']):
            try:
                if not self._modbus_client or not self._modbus_client.connected:
                    self.logger.warning(f"⚠️  Modbus disconnected, reconnecting (tentative {attempt+1})")
                    if not await self._modbus_connect():
                        await asyncio.sleep(1.0)
                        continue
                result = await self._modbus_client.read_holding_registers(
                    address=address, count=count, device_id=unit
                )
                if result.isError():
                    self.logger.warning(f"⚠️  Modbus register error {address} : {result}")
                    continue
                return result.registers
            except (EOFError, SystemExit, KeyboardInterrupt):
                raise
            except Exception as e:
                self.logger.error(f"❌ Modbus register reading {address} : {e}")
                self._modbus_client = None   # force reconnexion au prochain appel
                await asyncio.sleep(0.5)
        return None

    # -----------------------------------------------------------------------
    # Lectures Modbus métier
    # (adresses à adapter selon le registre map réel de la batterie Marstek)
    # -----------------------------------------------------------------------

    async def _modbus_get_data(self, regid):
        if regid in MARSTEK_REGISTER.keys():
            # Verification type de batterie et firmware
            btype = self.type
            if btype not in MARSTEK_REGISTER[regid].keys():
                self.logger.warning(f"⚠️  No register found for battery type = '{btype}', using to 'default' type")
                btype = 'default'

            fw = self.fw
            if self.fw not in MARSTEK_REGISTER[regid][btype].keys():
                self.logger.warning(f"⚠️  No register found for firmware = '{fw}', using 'default' firmware")
                fw = 'default'

            # lecture du registre
            registreData = MARSTEK_REGISTER[regid][btype][fw]
            regs = await self._modbus_read_registers(registreData.adr, registreData.taille, self.modbus_id)
            if regs is None:
                return None
            # reconstruction de la valeur
            val = 0
            for reg in regs:
                val = (val << 16) | reg

            coef = registreData.coef
            if registreData.type == 'sint':
                val = to_signed(val)
            if (coef != 1) and (coef != 0):
                if coef < 1:
                    coef = int(1/coef)
                    val /= coef
                else:
                    val *= coef
            return val
        else:
            self.logger.warning(f"⚠️  No register found for '{regid}'")
            return None

    async def _modbus_get_state(self) -> str:
        valState = await self._modbus_get_data('bat_state')
        if valState is None:
            return None
        state = "Unknown"
        if valState == 0:
            state = "Sleep"
        elif valState == 1:
            state = "Standby"
        elif valState == 2:
            state = "Charging"
        elif valState == 3:
            state = "Discharging"
        elif valState == 4:
            state = "Backup"
        elif valState == 5:
            state = "Upgrading"
        elif valState == 6:
            state = "Bypass"
        return state

    async def _modbus_get_ongrid_power(self) -> int:
        val = await self._modbus_get_data('ongrid_power')
        return val

    async def _modbus_get_offgrid_power(self) -> int:
        val = await self._modbus_get_data('offgrid_power')
        return val

    async def _modbus_get_soc(self) -> int:
        val = await self._modbus_get_data('bat_soc')
        return val

    async def _modbus_get_temp(self) -> int:
        val = await self._modbus_get_data('bat_temp')
        return val

    async def _modbus_get_input_energy(self) -> int:
        val = await self._modbus_get_data('total_grid_input_energy')
        return val

    async def _modbus_get_output_energy(self) -> int:
        val = await self._modbus_get_data('total_grid_output_energy')
        return val

    async def _modbus_get_rated_capacity(self)  -> int:
        val = await self._modbus_get_data('rated_capacity')
        return val

    async def _modbus_get_ble_mac(self)  -> int:
        val = await self._modbus_get_data('ble_mac')
        return val

    async def _modbus_get_wifi_mac(self)  -> int:
        val = await self._modbus_get_data('mac')
        return val

    async def _modbus_get_ip(self)  -> int:
        val = await self._modbus_get_data('ip')
        return val

    async def _modbus_get_firmware(self) -> int:
        val = await self._modbus_get_data('EMS_version')
        return val

    # -----------------------------------------------------------------------
    # Commandes MQTT
    # -----------------------------------------------------------------------

    async def _process_commands(self):
        """Dépile la queue globale, exécute les commandes de ce worker, remet les autres."""
        pending = []
        while not self.command_queue.empty():
            item = self.command_queue.get_nowait()
            if item['name'] == self.device['name'] and item['ble_mac'] == self.device['ble_mac']:
                await self._execute_command(item['msg'])
            else:
                pending.append(item)
        for item in pending:
            await self.command_queue.put(item)

    async def _execute_command(self, msg: dict):
        cmd    = msg.get('cmd')
        update: dict = {}

        if cmd == 'Auto':
            config = {"mode": "Auto", "auto_cfg": {"enable": 1}}
        elif cmd == 'AI':
            config = {"mode": "AI", "ai_cfg": {"enable": 1}}
        elif cmd == 'Manual':
            config = {"mode": "Manual", "manual_cfg": {
                "time_num": 9, "start_time": "00:00", "end_time": "23:59",
                "week_set": 127, "power": msg.get('power', 0), "enable": 1}}
        elif cmd == 'Passive':
            config = {"mode": "Passive", "passive_cfg": {
                "power": msg.get('power', 0), "cd_time": 300}}
        elif cmd == 'Ups':
            config = {"mode": "UPS", "ups_cfg": {"enable": 1}}
        else:
            self.logger.warning(f"⚠️  Unknown command : {cmd}")
            return

        self.logger.info(f"Sending UDP command : {json.dumps(config)}")
        try:
            self.api.host = self.device['ip']
            result = await self.api.set_es_mode(config)
            if result:
                self.logger.info("✅ Command successfully executed")
                update['mode'] = cmd
                await self._publish(update)
            else:
                self.logger.warning("⚠️  Command not executed")
        except PermissionError as err:
            self.logger.error(f"❌ UDP socket rejected : {err}")
        except Exception as e:
            self.logger.error(f"❌ Command error : {e}")
            import traceback; traceback.print_exc()

    # -----------------------------------------------------------------------
    # Réception config hybride
    # -----------------------------------------------------------------------

    async def _process_config(self):
        """
        Dépile la config_queue pour ce worker.
        Si une config hybride est reçue, bascule en mode hybride à la volée.
        """
        pending = []
        while not self.config_queue.empty():
            item = self.config_queue.get_nowait()
            if item['name'] == self.device['name'] and item['ble_mac'] == self.device['ble_mac']:
                await self._apply_config(item['cfg'])
            else:
                pending.append(item)
        for item in pending:
            await self.config_queue.put(item)

    async def _apply_config(self, cfg: dict):
        """
        Applique une nouvelle configuration reçue par MQTT.
        Gère le basculement entre mode UDP pur et mode hybride à la volée.
        """
        new_hybrid   = cfg.get('mode', False)
        new_modbus_ip   = cfg.get('ip')
        new_modbus_port = cfg.get('port', MODBUS_DEFAULT_PORT)
        new_id = cfg.get('serverId', 1)
        new_enabled = cfg.get('enabled', 1)

        # recup ID modbus et etat activation
        self.modbus_id = new_id
        self.enabled = new_enabled

        # Pas de changement → rien à faire
        if new_hybrid == self.hybrid_mode and new_modbus_ip == self.modbus_ip:
            return

        self.logger.info(f"📡 New mode request received : Hybride mode req={new_hybrid}, Modbus IP={new_modbus_ip}:{new_modbus_port}")

        # ── Désactivation du mode hybride ──
        if self.hybrid_mode and not new_hybrid:
            self.logger.info("🔄 Switching → UDP Mode")
            await self._stop_hybrid_tasks()
            await self._modbus_disconnect()
            self.hybrid_mode = False
            return

        # ── Activation / mise à jour du mode hybride ──
        if new_hybrid:
            if not new_modbus_ip:
                self.logger.error("❌ Hybrid mode requested but no Modbus IP specified → Ignored")
                return

            # Arrêt des tâches hybrides existantes si changement d'IP
            if self._hybrid_tasks:
                await self._stop_hybrid_tasks()
                await self._modbus_disconnect()

            self.modbus_ip   = new_modbus_ip
            self.modbus_port = new_modbus_port
            self.hybrid_mode = True

            connected = await self._modbus_connect()
            if not connected:
                self.logger.error("❌ Unable to to connect to Modbus → Hybrid mode cancelled")
                self.hybrid_mode = False
                return

            self.logger.info("🚀 Switching → Hybrid mode")
            # Invalidation explicite des données CT non disponibles en Modbus
            await self._publish({
                'a_power': 0, 'b_power': 0, 'c_power': 0,
                'ct_state': 0, 'total_power': 0,
            })
            self._start_hybrid_tasks()

    # -----------------------------------------------------------------------
    # Tâches hybrides
    # -----------------------------------------------------------------------

    def _start_hybrid_tasks(self):
        """Lance les 4 tâches périodiques en mode hybride."""
        self._hybrid_tasks = [
            asyncio.create_task(self._task_1s(),    name=f"{self.label}-1s"),
            asyncio.create_task(self._task_10s(),  name=f"{self.label}-10s"),
            asyncio.create_task(self._task_1min(),  name=f"{self.label}-1min"),
            asyncio.create_task(self._task_10min(),    name=f"{self.label}-10min"),
        ]
        for t in self._hybrid_tasks:
            t.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task):
        """Callback appelé quand une tâche hybride se termine (erreur non gérée)."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc and not isinstance(exc, (KeyboardInterrupt, SystemExit)):
            self.logger.error(f"❌ Hybrid Task {task.get_name()} ended with exception : {exc}")

    async def _stop_hybrid_tasks(self):
        """Annule et attend la fin de toutes les tâches hybrides."""
        for t in self._hybrid_tasks:
            t.cancel()
        if self._hybrid_tasks:
            await asyncio.gather(*self._hybrid_tasks, return_exceptions=True)
        self._hybrid_tasks = []
        self.logger.info("All hybrid tasks stopped")

    # ── Tâche 1s : Etat / Puissances instantanées / SOC (Modbus) ──────────────────────────
    async def _task_1s(self):
        self.logger.info("▶  1s Task Started (Modbus)")
        while True:
            start = time.perf_counter()
            update: dict = {}
            clearToUpdate = False
            if self.enabled:
                try:
                    await self._process_commands()   # commandes traitées aussi depuis la tâche 1s
                    data = await self._modbus_get_state()
                    if data:
                        update['bat_state'] = data
                        clearToUpdate = True
                        if data != self.device.get('bat_state'):
                            ongridpower = await self._modbus_get_ongrid_power()
                            offgridpower = await self._modbus_get_offgrid_power()
                            if (ongridpower is not None) and (offgridpower is not None):
                                update['ongrid_power'] = ongridpower
                                update['offgrid_power'] = offgridpower
                                self.logger.info(
                                    f"  [1s] state = {data}"
                                    f" / OnGrid Power = {ongridpower} W"
                                    f" / OffGrid Power = {offgridpower} W")
                            else:
                                self.logger.warning("⚠️  [1s] Grid power reading failed")
                            soc = await self._modbus_get_soc()
                            if soc is not None:
                                update['bat_soc'] = int(soc)
                                self.logger.info(f"  [1s] soc = {soc} %")
                            else:
                                self.logger.warning("⚠️  [1s] SOC reading failed")
                        else:
                            self.logger.info(f"  [1s] still {data} ...")
                    else:
                        self.logger.warning("⚠️  [1s] State reading failed")
                    if clearToUpdate:
                        await self._publish(update)
                except (EOFError, SystemExit, KeyboardInterrupt, asyncio.CancelledError):
                    raise
                except Exception as e:
                    self.logger.error(f"❌ [1s] Exception : {e}")
                    import traceback; traceback.print_exc()
            else:
                self.logger.error("🔄 Doing nothing - Battery is disabled")

            elapsed = time.perf_counter() - start
            await asyncio.sleep(max(0.0, 1.0 - elapsed))

    # ── Tâche 10sec : Puissances instantannées (si etat <> Standby) et SOC + calcul capacité (UDP)  ────────────
    async def _task_10s(self):
        self.logger.info("▶  10s Task Started (Modbus)")
        await asyncio.sleep(0.5)
        while True:
            start = time.perf_counter()
            update: dict = {}
            clearToUpdate = False
            if self.enabled:
                try:
                    if self.device.get('bat_state') != 'Standby':
                        ongridpower = await self._modbus_get_ongrid_power()
                        offgridpower = await self._modbus_get_offgrid_power()

                        if (ongridpower is not None) and (offgridpower is not None):
                            update['ongrid_power'] = ongridpower
                            update['offgrid_power'] = offgridpower
                            self.logger.info(
                                f"  [10s] OnGrid Power = {ongridpower} W"
                                f" / OffGrid Power = {offgridpower} W")
                            clearToUpdate = True
                        else:
                            self.logger.warning("⚠️  [10s] Grid power reading failed")
                        soc = await self._modbus_get_soc()
                        if soc is not None:
                            update['bat_soc'] = int(soc)
                            self.logger.info(f"  [10s] soc = {soc} %")
                            if self.device.get('rated_capacity') is not None:
                                update['bat_capacity'] = int(((self.device.get('rated_capacity')*soc)/100))
                                self.logger.info(f"  [10s] bat_capacity = {update['bat_capacity']} Wh")
                            clearToUpdate = True
                        else:
                            self.logger.warning("⚠️  [10s] SOC reading/bat capacity calculation failed")
                    else:
                        self.logger.debug(f"  [10s] state='Standby' — skipping power/SOC read")

                    if clearToUpdate:
                        await self._publish(update)
                except (EOFError, SystemExit, KeyboardInterrupt, asyncio.CancelledError):
                    raise
                except Exception as e:
                    self.logger.error(f"❌ [10s] Exception : {e}")
                    import traceback
                    traceback.print_exc()
            else:
                self.logger.error("🔄 Doing nothing - Battery is disabled")

            elapsed = time.perf_counter() - start
            await asyncio.sleep(max(0.0, 10.0 - elapsed))

    # ── Tâche 1min  : Temperature, Energie totale (modbus) + Mode (UDP) ───────────────────────────
    async def _task_1min(self):
        self.logger.info("▶  1min Task Started (Modbus+UDP)")
        # Attente initiale décalée pour éviter une collision avec 1s/1min au démarrage
        await asyncio.sleep(1.0)

        while True:
            start = time.perf_counter()
            update: dict = {}
            clearToUpdate = False
            if self.enabled:
                try:
                    # recuperation de la temperature
                    temp = await self._modbus_get_temp()
                    if temp is not None:
                        update['bat_temp'] = temp
                        self.logger.info(f"  [1min] temp = {temp} °C")
                        clearToUpdate = True
                    else:
                        self.logger.warning("⚠️  [1mim] Temperature Reading failed")

                    # recuperation energie totale
                    ginput = await self._modbus_get_input_energy()
                    goutput = await self._modbus_get_output_energy()
                    if (ginput is not None) and (goutput is not None):
                        update['total_grid_input_energy'] = ginput
                        update['total_grid_output_energy'] = goutput
                        self.logger.info(
                            f"  [1min] Total input Energy = {ginput} Wh"
                            f" / Total output Energy = {goutput} Wh")
                        clearToUpdate = True
                    else:
                        self.logger.warning("⚠️  [1mim] Total Input/Output Energy reading failed")

                    # recuperation mode via UDP
                    timeout = self.param['timeout']
                    retry = self.param['retry']
                    mode_status = await self._udp_call(
                        lambda: self.api.get_es_mode(timeout=timeout, max_attempts=retry), "get_es_mode")
                    if mode_status:
                        if 'mode' in mode_status.keys():
                            update['mode'] = mode_status['mode']
                            self.logger.info(f"  [1min] Mode = {update['mode']}")
                            clearToUpdate = True
                    else:
                        self.logger.warning("⚠️  [1mim] Mode reading (UDP) failed")

                    # Update via mqtt si necessaire
                    if clearToUpdate:
                        await self._publish(update)

                except (EOFError, SystemExit, KeyboardInterrupt, asyncio.CancelledError):
                    raise
                except Exception as e:
                    self.logger.error(f"❌ [1min] Exception : {e}")
                    import traceback
                    traceback.print_exc()
            else:
                self.logger.error("🔄 Doing nothing - Battery is disabled")

            elapsed = time.perf_counter() - start
            await asyncio.sleep(max(0.0, 60.0 - elapsed))

    # ── Tâche 10min  : forcage valeurs ct / rated capacity / firmware (modbus) ──────────────────────────────────
    async def _task_10min(self):
        self.logger.info("▶  10min Task Started (Modbus)")
        await asyncio.sleep(10.0)   # décalage initial
        while True:
            start = time.perf_counter()
            update: dict = {}
            clearToUpdate = False
            if self.enabled:
                try:
                    maxrate = await self._modbus_get_rated_capacity()
                    if maxrate is not None:
                        update['rated_capacity'] = maxrate
                        self.logger.info(f"  [10min] Rated Capacity = {maxrate} W")
                        clearToUpdate = True
                    else:
                        self.logger.warning("⚠️  [10mim] Échec lecture mode rated capacity")

                    fw = await self._modbus_get_firmware()
                    if fw is not None:
                        update['firmware'] = str(fw)
                        self.logger.info(f"  [10min] Firmware = {fw}")
                        clearToUpdate = True
                    else:
                        self.logger.warning("⚠️  [10mim] Échec lecture version firmware")

                    # Update via mqtt si necessaire
                    if clearToUpdate:
                        await self._publish(update)

                except (EOFError, SystemExit, KeyboardInterrupt, asyncio.CancelledError):
                    raise
                except Exception as e:
                    self.logger.error(f"❌ [10min] Exception : {e}")
                    import traceback
                    traceback.print_exc()
            else:
                self.logger.error("🔄 Doing nothing - Battery is disabled")

            elapsed = time.perf_counter() - start
            await asyncio.sleep(max(0.0, 600.0 - elapsed))

    # -----------------------------------------------------------------------
    # Mode UDP pur — cycle de polling
    # -----------------------------------------------------------------------
    async def _udp_poll_cycle(self):
        update: dict = {}
        lc      = self.loop_count
        timeout = self.param['timeout']
        retry   = self.param['retry']
        is_venus = self.device['name'] == DEVICE_MODEL_VENUS_D

        if self.enabled:
            # ES Mode (chaque cycle)
            mode_status = await self._udp_call(
                lambda: self.api.get_es_mode(timeout=timeout, max_attempts=retry), "get_es_mode")
            if mode_status:
                try:
                    update = self._upd_es_mode(update, mode_status)
                    if update['ongrid_power'] == 0:
                        if update['offgrid_power'] != 0:
                            update['bat_state'] = "Bypass"
                        else:
                            update['bat_state'] = "Standby"
                    elif update['ongrid_power'] < 0:
                        update['bat_state'] = "Charging"
                    else:
                        update['bat_state'] = "Discharging"

                    self.logger.info(f"  Mode={update['mode']} / Status={update['bat_state']} / "
                                     f"Power={format_value(update['ongrid_power'],' W')} / SOC={format_value(update['bat_soc'],'%')}")
                    self.fail_count = 0
                except KeyError as e:
                    self.logger.error(f"KeyError get_es_mode : {e}")
            else:
                self.logger.warning("⚠️  UDP ES_MODE reading failed")
                self.fail_count += retry

            # Battery status (×3)
            if lc % 3 == 0:
                bat = await self._udp_call(
                    lambda: self.api.get_battery_status(timeout=timeout, max_attempts=retry), "get_battery_status")
                if bat:
                    try:
                        #bat['bat_temp']     = scaling.scale_value(bat['bat_temp'],     'bat_temp')
                        #bat['bat_capacity'] = scaling.scale_value(bat['bat_capacity'], 'bat_capacity')
                        bat['bat_soc'] = bat.pop('soc', bat.get('bat_soc'))
                        update = self._upd_battery(update, bat)
                        self.logger.info(f"  SOC={format_value(update['bat_soc'],'%')} / Temp={format_value(update['bat_temp'],'°C')} / Cap={format_value(update['bat_capacity'],' Wh')}")
                        self.fail_count = 0
                    except KeyError as e:
                        self.logger.error(f"KeyError get_battery_status : {e}")
                else:
                    self.logger.warning("⚠️  UDP BAT_STATUS reading failed")
                    self.fail_count += retry

            # EM + PV (×5)
            if lc % 5 == 0:
                em = await self._udp_call(
                    lambda: self.api.get_em_status(timeout=timeout, max_attempts=retry), "get_em_status")
                if em:
                    try:
                        update = self._upd_em(update, em)
                        ct = update['ct_state'] == 1
                        self.logger.info(f"  CT={ct} / Total={format_value(update['total_power'],' W')}")
                        self.fail_count = 0
                    except KeyError as e:
                        self.logger.error(f"KeyError get_em_status : {e}")
                else:
                    self.logger.warning("⚠️  UDP EM_STATUS reading failed")
                    self.fail_count += retry

                if is_venus:
                    pv = await self._udp_call(
                        lambda: self.api.get_pv_status(timeout=timeout, max_attempts=retry), "get_pv_status")
                    if pv:
                        try:
                            update = self._upd_pv(update, pv)
                            self.logger.info(f"  PV={format_value(update['pv_power'],' W')}")
                            self.fail_count = 0
                        except KeyError as e:
                            self.logger.error(f"KeyError get_pv_status : {e}")
                    else:
                        self.logger.warning("⚠️  UDP PV_STATUS reading failed")
                        self.fail_count += retry

            # ES Status (×10)
            if lc % 10 == 0:
                es = await self._udp_call(
                    lambda: self.api.get_es_status(timeout=timeout, max_attempts=retry), "get_es_status")
                if es:
                    try:
                        update = self._upd_es_status(update, es)
                        self.logger.info(f"  Solar={format_value(update['total_pv_energy'],' Wh')} / Import={format_value(update['total_grid_input_energy'],' Wh')} / Export={format_value(update['total_grid_output_energy'],' Wh')}")
                        self.fail_count = 0
                    except KeyError as e:
                        self.logger.error(f"KeyError get_es_status : {e}")
                else:
                    self.logger.warning("⚠️  UDP ES_STATUS reading failed")
                    self.fail_count += retry

            await self._publish(update)
        else:
            self.logger.error("🔄 Doing nothing - Battery is disabled")
    # -----------------------------------------------------------------------
    # Boucle principale du worker
    # -----------------------------------------------------------------------

    async def _wait_for_next_cycle(self, duration: float):
        self.logger.debug(f"  [wait] Début — durée={duration:.1f}s hybrid={self.hybrid_mode}")
        deadline = time.perf_counter() + duration

        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                self.logger.debug(f"  [wait] Timer écoulé normalement")
                break

            sleep_task = asyncio.create_task(asyncio.sleep(remaining))
            cfg_task = asyncio.create_task(self.config_queue.get())

            if self.hybrid_mode:
                done, pending = await asyncio.wait(
                    {sleep_task, cfg_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
            else:
                cmd_task = asyncio.create_task(self.command_queue.get())
                done, pending = await asyncio.wait(
                    {sleep_task, cfg_task, cmd_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

            for t in pending:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

            if cfg_task in done:
                item = cfg_task.result()
                self.logger.debug(f"  [wait] Config reçue : {item}")
                await self.config_queue.put(item)
                mode_before = self.hybrid_mode
                await self._process_config()
                if self.hybrid_mode != mode_before:
                    self.logger.debug(f"  [wait] Changement de mode détecté → sortie")
                    break
            elif not self.hybrid_mode and cmd_task in done:
                item = cmd_task.result()
                self.logger.debug(f"  [wait] Commande reçue : {item}")
                await self.command_queue.put(item)
                await self._process_commands()
            else:
                self.logger.debug(f"  [wait] Timer écoulé normalement")
                break

    async def run(self):
        self.logger.info(f"▶  Worker Started — {self.label} ({self.device['ip']})")
        await self.api.connect()

        while True:
            # Config traitée en tête de boucle pour le premier cycle
            # et après chaque cycle complet
            await self._process_config()

            if self.hybrid_mode:
                # Les commandes sont traitées par _task_1s toutes les secondes.
                # On surveille quand même la config_queue pour détecter
                # un retour éventuel en mode UDP.
                await self._wait_for_next_cycle(1.0)  # ← remplace asyncio.sleep(1.0)
            else:
                self.logger.info(f"--- [{self.label}] UDP Loop {self.loop_count} ---")
                start = time.perf_counter()

                #await self._process_commands()
                await self._udp_poll_cycle()

                if self.fail_count > 10:
                    await self._udp_reconnect()

                elapsed = time.perf_counter() - start

                # Sleep interruptible : commandes ET configs traitées immédiatement
                await self._wait_for_next_cycle(max(1.0, self.param['period'] - elapsed))
                self.loop_count = (self.loop_count % 30) + 1

# ---------------------------------------------------------------------------
# Daemon principal
# ---------------------------------------------------------------------------

def main(args):
    param = {}
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            print(f"ERROR: Config file not found: {config_path}"); sys.exit(1)
        param.update(load_config(config_path))

    cli_overrides = {
        'port': args.port, 'mqtt-ip': args.mqtt_address, 'mqtt-port': args.mqtt_port,
        'mqtt-username': args.mqtt_username, 'mqtt-password': args.mqtt_password,
        'timeout': args.timeout, 'retry': args.retry, 'period': args.poll_period,
        'pidfile': args.pidfile, 'log': args.log,
    }
    for k, v in cli_overrides.items():
        if v is not None:
            param[k] = v

    defaults = {
        'port': 30000, 'mqtt-ip': '192.168.0.50', 'mqtt-port': 1883,
        'mqtt-username': '', 'mqtt-password': '', 'timeout': 5,
        'retry': 3, 'period': 10, 'pidfile': 'daemon.pid', 'log': 'info',
    }
    for k, v in defaults.items():
        param.setdefault(k, v)

    log_levels = {'debug': logging.DEBUG, 'info': logging.INFO,
                  'warning': logging.WARNING, 'error': logging.ERROR}
    logging.basicConfig(
        stream=sys.stdout,
        level=log_levels.get(param.get('log', 'info').lower(), logging.INFO),
        format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
    )
    logger = logging.getLogger("main")
    logger.info(f"Starting — API:{param['port']} MQTT:{param['mqtt-ip']}:{param['mqtt-port']} period:{param['period']}s")

    pidfile = param['pidfile']
    with open(pidfile, 'w') as f:
        f.write(f"{os.getpid()}\n")

    try:
        asyncio.run(action(param))
    except (EOFError, SystemExit, KeyboardInterrupt):
        logger.info("Daemon stopped.")
    finally:
        try:
            os.remove(pidfile)
        except FileNotFoundError:
            pass
    sys.exit(0)

async def action(param: dict):
    logger = logging.getLogger("main")
    loop = asyncio.get_event_loop()

    command_queue: asyncio.Queue = asyncio.Queue()   # commandes marstek/action
    config_queue:  asyncio.Queue = asyncio.Queue()   # config  marstek/config
    mqtt_lock = asyncio.Lock()

    # -----------------------------------------------------------------------
    # Callbacks MQTT
    # -----------------------------------------------------------------------

    def on_connect(client, userdata, flags, reason_code, properties):
        # VERSION2 : reason_code est un objet ReasonCode (is_failure=True si erreur)
        if reason_code.is_failure:
            logger.error(f"❌ MQTT connection failed : {reason_code}")
        else:
            logger.info(f"✅ MQTT broker connected ({reason_code})")
            # Les abonnements sont placés ici (dans on_connect) pour être
            # automatiquement re-souscrits en cas de reconnexion automatique paho
            client.subscribe(f"{MARSTEK_TOPIC_ACTION}/#")
            client.subscribe(f"{MARSTEK_TOPIC_CONFIG}/#")

    def on_disconnect(client, userdata, flags, reason_code, properties):
        # VERSION2 : reason_code == 0 → déconnexion propre demandée par le client
        if reason_code != 0:
            logger.warning(f"⚠️  Unexpected MQTT disconnect : {reason_code}")

    def on_message(client, userdata, message):
        topic = message.topic
        logger.debug(f"  [mqtt] Message reçu sur {topic}")
        try:
            payload = json.loads(message.payload)
        except json.JSONDecodeError:
            logger.error(f"❌ Invalid JSON Payload for {topic}")
            return

        # loop est capturée par closure depuis action()
        # call_soon_threadsafe est thread-safe : réveille immédiatement
        # la coroutine asyncio qui attend sur queue.get()

        if topic.startswith(f"{MARSTEK_TOPIC_CONFIG}/"):
            src = topic[len(f"{MARSTEK_TOPIC_CONFIG}/"):]
            parts = src.split('-', 1)
            if len(parts) == 2:
                item = {'name': parts[0], 'ble_mac': parts[1], 'cfg': payload}
                loop.call_soon_threadsafe(config_queue.put_nowait, item)
            else:
                logger.warning(f"⚠️  Invalid CONFIG Topic : {topic}")
            return

        if topic.startswith(f"{MARSTEK_TOPIC_ACTION}/"):
            src = topic[len(f"{MARSTEK_TOPIC_ACTION}/"):]
            parts = src.split('-', 1)
            if len(parts) == 2:
                item = {'name': parts[0], 'ble_mac': parts[1], 'msg': payload}
                loop.call_soon_threadsafe(command_queue.put_nowait, item)
            else:
                logger.warning(f"⚠️  Invalid ACTION Topic : {topic}")

    def send_detected_devices(dev_list: list):
        for dev in dev_list:
            src   = f"{dev['name']}-{dev['ble_mac']}"
            topic = f"{MARSTEK_TOPIC_DEVICE}/{src}"
            pub   = mqttc.publish(topic, json.dumps(dev), retain=True)
            pub.wait_for_publish()

    # -----------------------------------------------------------------------
    # Connexion MQTT
    # -----------------------------------------------------------------------
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if param['mqtt-username'] and param['mqtt-password']:
        mqttc.username_pw_set(username=param['mqtt-username'], password=param['mqtt-password'])
    mqttc.on_connect    = on_connect
    mqttc.on_disconnect = on_disconnect
    mqttc.on_message    = on_message
    mqttc.connect(host=param['mqtt-ip'], port=param['mqtt-port'], keepalive=60)
    mqttc.loop_start()

    # -----------------------------------------------------------------------
    # Découverte UDP initiale
    # -----------------------------------------------------------------------
    hass = MockHass()
    api  = MarstekUDPClient(hass, port=param['port'])

    async def discover() -> list:
        try:
            return await api.discover_devices(timeout=10)
        except PermissionError as err:
            logger.error(f"❌ Socket UDP refusé : {err}")
        except Exception as e:
            logger.error(f"❌ Erreur découverte : {e}")
            import traceback; traceback.print_exc()
        return []

    devices: list[DeviceState] = []
    while not devices:
        await api.connect()
        await asyncio.sleep(1.0)
        devices = await discover()
        if not devices:
            logger.warning("❌ No device found, re-trying...")
            await api.disconnect()
            await asyncio.sleep(1.0)

    send_detected_devices(devices)
    await api.disconnect()

    logger.info(f"✅ {len(devices)} device(s) found :")
    for i, d in enumerate(devices, 1):
        logger.info(f"  [{i}] {d['name']}  IP={d['ip']}  MAC={d['mac']}  FW=v{d['firmware']}")

    await asyncio.sleep(2.0)

    # -----------------------------------------------------------------------
    # Lancement des workers en parallèle
    # -----------------------------------------------------------------------
    workers = [
        DeviceWorker(device, param, mqttc, mqtt_lock, command_queue, config_queue)
        for device in devices
    ]
    logger.info(f"🚀 Launching {len(workers)} worker(s) in parallel")

    results = await asyncio.gather(
        *[w.run() for w in workers],
        return_exceptions=True
    )
    for i, result in enumerate(results):
        if isinstance(result, Exception) and not isinstance(result, (KeyboardInterrupt, SystemExit)):
            logger.error(f"❌ Worker [{workers[i].label}] ended with exception : {result}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(prog='marstekmqttd', description='Daemon MQTT pour batteries Marstek')
parser.add_argument("--config",        type=str, default=None, help="Fichier de configuration YAML")
parser.add_argument("--port",          type=int, default=None, help="Port UDP API Marstek")
parser.add_argument("--mqtt_address",  type=str, default=None, help="Adresse IP broker MQTT")
parser.add_argument("--mqtt_port",     type=int, default=None, help="Port broker MQTT")
parser.add_argument("--mqtt-username", type=str, default=None, help="Utilisateur MQTT")
parser.add_argument("--mqtt-password", type=str, default=None, help="Mot de passe MQTT")
parser.add_argument("--timeout",       type=int, default=None, help="Timeout API (secondes)")
parser.add_argument("--retry",         type=int, default=None, help="Nombre de tentatives API")
parser.add_argument("--poll_period",   type=int, default=None, help="Période polling UDP (secondes)")
parser.add_argument("--pidfile",       type=str, default=None, help="Chemin fichier PID")
parser.add_argument("--log",           type=str, default=None, choices=['debug','info','warning','error'])
parser.set_defaults(func=main)

args = parser.parse_args()
args.func(args)
