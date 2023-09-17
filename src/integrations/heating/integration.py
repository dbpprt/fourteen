from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import Callable, List, Optional

import ujson
import yaml
from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig

from src.integrations.base import BaseIntegration, Integration, TelegramHandler
from src.integrations.heating.utils.ems_client import BoilerInfo, EmsClient
from src.utils.persistant_state import PersistentState


@dataclass
class State:
    heating_active: bool
    heating_curve_inclination: float
    heating_curve_parallel_shift: float
    heating_curve_max_supply_temperature: int
    heating_curve_min_supply_temperature: int
    heating_curve_target_room_temperature: float
    heating_curve_target_night_room_temperature: float
    heating_curve_day_start_hour: int
    heating_curve_day_start_minute: int
    heating_curve_day_end_hour: int
    heating_curve_day_end_minute: int


class HeatingIntegration(Integration):
    def __init__(
        self,
        config: DictConfig,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        logger: Logger,
        telegram_handler: Optional[Callable[..., TelegramHandler]],
        boiler: EmsClient,
        state_overrides: DictConfig,
    ):
        super().__init__(
            config=config,
            scheduler=scheduler,
            integrations=integrations,
            logger=logger,
            telegram_handler=telegram_handler,
        )

        self.boiler = boiler
        self.state_overrides = state_overrides
        self.last_boiler_info = None
        self.target_supply_temperature: int = 0

        scheduler.add_job(self.initialize)
        scheduler.add_job(
            self.refresh,
            "interval",
            seconds=30,
            next_run_time=datetime.now(scheduler.timezone),
        )

    async def initialize(self):
        self.persistent_state: PersistentState[State] = PersistentState(
            "heating", self.config.data_dir
        )

        # default values for heating state
        await self.persistent_state.initialize(
            State(
                heating_active=False,
                heating_curve_inclination=1.1,
                heating_curve_parallel_shift=0.0,
                heating_curve_max_supply_temperature=50,
                heating_curve_min_supply_temperature=30,
                heating_curve_target_room_temperature=20.0,
                heating_curve_target_night_room_temperature=17.5,
                heating_curve_day_start_hour=6,
                heating_curve_day_start_minute=0,
                heating_curve_day_end_hour=22,
                heating_curve_day_end_minute=0,
            )
        )

        self.state: State = await self.persistent_state.get()
        # override state with values from config
        for key, value in self.state_overrides.items():
            setattr(self.state, str(key), value)

        self.logger.info(f"Initialized heating integration with state: {self.state}")

    def calculate_supply_temperature(self) -> int:
        if self.state.heating_active is False:
            return 0

        if self.last_boiler_info is None:
            self.logger.warning(
                "No boiler info available, unable to calculate supply temperature!"
            )
            return 0

        target_room_temperature = self.state.heating_curve_target_room_temperature
        now = datetime.now(tz=self.scheduler.timezone)
        # check if we are in the night time (hours and minutes)
        if (
            now.hour < self.state.heating_curve_day_start_hour
            or now.hour > self.state.heating_curve_day_end_hour
            or (
                now.hour == self.state.heating_curve_day_start_hour
                and now.minute < self.state.heating_curve_day_start_minute
            )
            or (
                now.hour == self.state.heating_curve_day_end_hour
                and now.minute > self.state.heating_curve_day_end_minute
            )
        ):
            target_room_temperature = (
                self.state.heating_curve_target_night_room_temperature
            )

        outside_temperature = self.last_boiler_info.outside_temperature
        dar = outside_temperature - target_room_temperature
        target_supply_temperature = (
            target_room_temperature
            + self.state.heating_curve_parallel_shift
            - self.state.heating_curve_inclination
            * dar
            * (1.4347 + 0.021 * dar + 247.9 * 10**-6 * dar**2)
        )

        if target_supply_temperature < self.state.heating_curve_min_supply_temperature:
            return self.state.heating_curve_min_supply_temperature
        elif (
            target_supply_temperature > self.state.heating_curve_max_supply_temperature
        ):
            return self.state.heating_curve_max_supply_temperature
        else:
            return round(target_supply_temperature)

    async def refresh(self):
        self.logger.info("Refreshing heating integration")

        try:
            boiler_info: BoilerInfo = await self.boiler.info()
            self.last_boiler_info = boiler_info
            # Only used for informational purposes!
            self.last_boiler_info_timestamp = datetime.now()
            self.last_ems_error = None
            self.logger.info("Retrieved boiler_info {}".format(yaml.dump(boiler_info)))
        except Exception as e:
            self.last_ems_error = e
            self.logger.exception("Failed to retrieve boiler_info")
            # TODO: Notify user

        self.target_supply_temperature = self.calculate_supply_temperature()
        self.logger.info(
            f"Calculated target supply temperature: {self.target_supply_temperature}"
        )

        if self.target_supply_temperature == 0:
            self.logger.info("Target supply temperature is 0, not setting it!")
            return

        response = await self.boiler.set_variable(
            "selflowtemp", self.target_supply_temperature
        )

        self.logger.info(
            f"Set target supply temperature, response: {ujson.dumps(response)}"
        )

        if response["message"] != "OK":
            self.logger.error("Failed to set target supply temperature")
            # TODO: Notify user

    async def shutdown(self):
        await self.boiler.close()
        return await super().shutdown()
