from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import List

from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

from src.integrations.base.integration import BaseIntegration, Integration
from src.integrations.heating.utils.ems_client import BoilerInfo, EmsClient
from src.utils.persistant_state import PersistentState
import ujson


@dataclass
class State:
    heating_active: bool
    heating_curve_inclination: float
    heating_curve_parallel_shift: float
    heating_curve_max_supply_temperature: int
    heating_curve_min_supply_temperature: int
    heating_curve_target_room_temperature: float


EXPECT_BUTTON_CLICK = range(1)


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

        if self.target_supply_temperature == 0:
            self.logger.info("Target supply temperature is 0, not setting it!")
            return

        response = await self.boiler.set_variable(
            "selflowtemp", self.target_supply_temperature
        )

        self.logger.warning(
            f"Set target supply temperature, response: {ujson.dumps(response)}"
        )

        if response["message"] != "OK":
            self.logger.error("Failed to set target supply temperature")
            # TODO: Notify user

    async def command_heating(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.last_boiler_info is None:
            await update.message.reply_text(  # type: ignore
                "The boiler is currently not available!"
            )

            return

        keyboard = [
            [
                InlineKeyboardButton(
                    f"🔛 Heating active: {self.state.heating_active}",
                    callback_data="toggle_heating_active",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🌡️ Flow temperature: {self.last_boiler_info.current_flow_temperature}°C",
                    callback_data=".",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🌡️ Selected flow temperature: {self.last_boiler_info.selected_flow_temperature}°C",
                    callback_data=".",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🌡️ Calculated flow temperature: {self.target_supply_temperature}°C",
                    callback_data=".",
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(  # type: ignore
            "Data has been refreshed xxx seconds ago:",
            reply_markup=reply_markup,
        )

        return EXPECT_BUTTON_CLICK

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return ConversationHandler.END

    async def button_clicked_toggle_heating(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Show new choice of buttons"""
        query = update.callback_query
        await query.answer()  # type: ignore
        self.state.heating_active = not self.state.heating_active
        await self.persistant_state.set(self.state)
        self.logger.info(f"Set heating_active to {self.state.heating_active}")
        await query.edit_message_text(  # type: ignore
            text=f"Ok! Heating is now {'on' if self.state.heating_active else 'off'}"
        )
        return ConversationHandler.END

    async def register_telegram_commands(self, application: Application):
        conversation_handler = ConversationHandler(
            entry_points=[CommandHandler("heating", self.command_heating)],
            states={
                EXPECT_BUTTON_CLICK: [
                    CallbackQueryHandler(
                        self.button_clicked_toggle_heating,
                        pattern="^toggle_heating_active$",
                    ),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        application.add_handler(conversation_handler)
        return await super().register_telegram_commands(application=application)

    async def shutdown(self):
        await self.boiler.close()
        return await super().shutdown()
