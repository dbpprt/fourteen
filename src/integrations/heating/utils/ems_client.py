from dataclasses import dataclass
from logging import Logger
from typing import Any, Optional

import aiohttp
import ujson


@dataclass
class BoilerInfo:
    heating_active: bool
    selected_flow_temperature: int
    heating_pump_modulation: int
    outside_temperature: float
    current_flow_temperature: float
    flame_current: float
    heating_pump: bool
    service_code_number: int
    service_code: str
    maintenance_message: str


class EmsClient:
    def __init__(self, host: str, access_token: str, device_name: str, logger: Logger):
        self.host = host
        self.access_token = access_token
        self.device_name = device_name
        self.logger = logger
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + self.access_token,
        }

        self.session: Optional[aiohttp.ClientSession] = None

    async def create_session_if_necessary(self):
        if self.session is None:
            self.session = aiohttp.ClientSession(
                self.host, headers=self.headers, json_serialize=ujson.dumps
            )

    def url(self, path: Optional[str] = None) -> str:
        return f"/api/{self.device_name}/{path}" if path else f"/api/{self.device_name}"

    async def set_variable(self, variable: str, value: Any):
        await self.create_session_if_necessary()

        async with self.session.post(self.url(), json={"cmd": variable, "data": value}) as response:  # type: ignore
            return await response.json()

    async def info(self) -> BoilerInfo:
        await self.create_session_if_necessary()

        async with self.session.get(self.url("info")) as response:  # type: ignore
            json = await response.json()

            return BoilerInfo(
                heating_active=json["heating active"] == "on",
                selected_flow_temperature=json["selected flow temperature"],
                heating_pump_modulation=json["heating pump modulation"],
                outside_temperature=json["outside temperature"],
                current_flow_temperature=json["current flow temperature"],
                flame_current=json["flame current"],
                heating_pump=json["heating pump"] == "on",
                service_code_number=json["service code number"],
                service_code=json["service code"],
                maintenance_message=json["maintenance message"],
            )

    async def close(self):
        await self.session.close()  # type: ignore
