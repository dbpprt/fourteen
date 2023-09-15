from dataclasses import dataclass
from logging import Logger
from typing import Any, Dict, List, Optional
from aioesphomeapi.client import APIClient
from aioesphomeapi.core import APIConnectionError
from aioesphomeapi import BinarySensorInfo, DeviceInfo, SensorInfo, SwitchInfo


@dataclass
class Sensor:
    name: str
    key: int
    state: Optional[float]
    unit_of_measurement: str


@dataclass
class BinarySensor:
    name: str
    key: int
    state: Optional[bool]


@dataclass
class Switch:
    name: str
    key: int
    state: Optional[bool]


class ESPHomeDevice:
    def __init__(self, logger: Logger, host: str, encryption_key: str):
        self.logger = logger
        self.host = host
        self.encryption_key = encryption_key

        self.api_client = APIClient(
            host,
            6053,
            None,
            noise_psk=encryption_key,
        )

        self.is_connected = False
        self.is_expected_disconnect = False
        self.is_initialized = False

        self._reset_state()

    def _reset_state(self):
        self._name: Optional[str] = None
        self._mac_address: Optional[str] = None
        self._last_compilation_time: Optional[str] = None

        self.sensors: List[Sensor] = []
        self.binary_sensors: List[BinarySensor] = []
        self.switches: List[Switch] = []
        # key -> sensor
        # used to map the state changes to the correct sensor
        self._mappings: Dict[int, Any] = {}

    async def on_disconnect(self, expected_disconnect: bool):
        self.is_connected = False
        self.is_expected_disconnect = expected_disconnect
        self.logger.warning(
            f"Disconnected from ESPHome device {self.host}. Disconnect was expected: {expected_disconnect}"
        )

    async def connect(self) -> Optional[DeviceInfo]:
        try:
            await self.api_client.connect(login=True, on_stop=self.on_disconnect)
            device_info = await self.api_client.device_info()
            self.is_connected = True
            self.logger.info(
                f"Successfully connected to ESPHome device {self.host} with name {device_info.name}"
            )
            return device_info
        except APIConnectionError:
            self.logger.warning(f"Could not connect to ESPHome device {self.host}")
            return None
        except Exception:
            self.logger.exception(f"Could not connect to ESPHome device {self.host}")
            return None

    async def heartbeat(self):
        if self.is_connected:
            device_info = await self.api_client.device_info()
            # TODO: Check whether we have a new build and reset all entities
            # WIP: This is actually not needed, devices will disconnect with expected_disconnect=True
            if device_info.compilation_time != self._last_compilation_time:
                self.logger.info(
                    f"ESPHome device {self.host} has a new build. Resetting all entities"
                )
                await self.initialize(device_info)
        else:
            self.logger.info(
                f"ESPHome device {self.host} is not connected. Reconnecting"
            )
            await self.initialize()

    async def initialize(self, device_info: Optional[DeviceInfo] = None) -> bool:
        if not device_info:
            device_info = await self.connect()

            if device_info is None:
                return False

        self._reset_state()
        self._name = device_info.name
        self._mac_address = device_info.mac_address
        self._last_compilation_time = device_info.compilation_time

        entity_services = await self.api_client.list_entities_services()
        # flatten the list of lists return by list_entities_services
        entity_services = [item for sublist in entity_services for item in sublist]

        for entity_service in entity_services:
            if isinstance(entity_service, BinarySensorInfo):
                sensor = BinarySensor(
                    name=entity_service.object_id,
                    key=entity_service.key,
                    state=None,
                )
                self.binary_sensors.append(sensor)
                self._mappings[entity_service.key] = sensor

            if isinstance(entity_service, SensorInfo):
                sensor = Sensor(
                    name=entity_service.object_id,
                    key=entity_service.key,
                    state=None,
                    unit_of_measurement=entity_service.unit_of_measurement,
                )
                self.sensors.append(sensor)
                self._mappings[entity_service.key] = sensor

            if isinstance(entity_service, SwitchInfo):
                switch = Switch(
                    name=entity_service.object_id,
                    key=entity_service.key,
                    state=None,
                )
                self.switches.append(switch)
                self._mappings[entity_service.key] = switch

        # subscribe to the state changes
        await self.api_client.subscribe_states(
            lambda state: self.handle_state_change(state)
        )

        self.is_initialized = True

        return True

    def handle_state_change(self, state):
        sensor = self._mappings[state.key]
        sensor.state = state.state
        self.logger.debug(
            f"ESPHome device: {self._name} - State of {sensor.name} is {sensor.state}"
        )
