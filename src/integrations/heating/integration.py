from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import List

from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.integrations.base.integration import BaseIntegration, Integration
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


class HeatingIntegration(Integration):
    def __init__(
        self,
        logger: Logger,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        config: DictConfig,
        boiler: EmsClient,
    ):
        super().__init__(
            config=config, scheduler=scheduler, integrations=integrations, logger=logger
        )

        self.boiler = boiler
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
        self.persistant_state: PersistentState[State] = PersistentState(
            "heating", self.config.data_dir
        )

        # default values for heating state
        await self.persistant_state.initialize(
            State(
                heating_active=True,
                heating_curve_inclination=1.1,
                heating_curve_parallel_shift=0.0,
                heating_curve_max_supply_temperature=50,
                heating_curve_min_supply_temperature=30,
                heating_curve_target_room_temperature=20.0,
            )
        )
        self.state: State = await self.persistant_state.get()

    def calculate_supply_temperature(self) -> int:
        if self.state.heating_active is False:
            return 0

        if self.last_boiler_info is None:
            self.logger.warning(
                "No boiler info available, unable to calculate supply temperature!"
            )
            return 0

        outside_temperature = self.last_boiler_info.outside_temperature
        dar = outside_temperature - self.state.heating_curve_target_room_temperature
        target_supply_temperature = (
            self.state.heating_curve_target_room_temperature
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
            self.logger.info("Retrieved boiler_info", boiler_info)
        except Exception as e:
            self.last_ems_error = e
            self.logger.exception("Failed to retrieve boiler_info", e)
            # TODO: Notify user

        self.target_supply_temperature = self.calculate_supply_temperature()
        self.logger.info(
            f"Calculated target supply temperature: {self.target_supply_temperature}"
        )

        response = await self.boiler.set_variable(
            "selflowtemp", self.target_supply_temperature
        )
        self.logger.warning("Set target supply temperature, response: ", response)

    async def command_heating(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.last_boiler_info is None:
            await update.message.reply_text(  # type: ignore
                "The boiler is currently not available!"
            )

            return

        keyboard = [
            [
                InlineKeyboardButton(
                    f"Heating active: {self.last_boiler_info.heating_active}",
                    callback_data="button",
                ),
                InlineKeyboardButton(
                    f"Flow temperature: {self.last_boiler_info.current_flow_temperature}°C",
                    callback_data="button",
                ),
                InlineKeyboardButton(
                    f"Selected flow temperature: {self.last_boiler_info.selected_flow_temperature}°C",
                    callback_data="button",
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(  # type: ignore
            "Data has been refreshed xxx seconds ago:",
            reply_markup=reply_markup,
        )

    async def register_telegram_commands(self, application: Application):
        application.add_handler(CommandHandler("heating", self.command_heating))
        return await super().register_telegram_commands(application=application)

    async def shutdown(self):
        await self.boiler.close()
        return await super().shutdown()
