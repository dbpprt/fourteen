from datetime import datetime
from logging import Logger
from typing import List

from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.integrations.base.integration import BaseIntegration, Integration
from src.integrations.heating.utils.ems_client import BoilerInfo, EmsClient


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

        scheduler.add_job(
            self.refresh,
            "interval",
            seconds=10,
            next_run_time=datetime.now(scheduler.timezone),
        )
        # self.heating = Heating(config.heating)

    async def refresh(self):
        self.logger.info("Refreshing heating integration")

        boiler_info: BoilerInfo = await self.boiler.info()
        self.last_boiler_info = boiler_info
        self.logger.info("Retrieved boiler_info", boiler_info)

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
