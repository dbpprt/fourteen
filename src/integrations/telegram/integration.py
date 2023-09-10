from logging import Logger
from typing import List

from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig

from src.integrations.base.integration import BaseIntegration, Integration
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    PicklePersistence,
)


class TelegramIntegration(Integration):
    def __init__(
        self,
        logger: Logger,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        config: DictConfig,
        bot_token: str,
        telegram_persistence_location: str,
    ):
        super().__init__(
            config=config, scheduler=scheduler, integrations=integrations, logger=logger
        )

        persistence = PicklePersistence(filepath=telegram_persistence_location)
        self.application = (
            ApplicationBuilder()
            .token(bot_token)
            .persistence(persistence)
            .arbitrary_callback_data(True)
            .build()
        )

        start_handler = CommandHandler("start", self.command_start)
        self.application.add_handler(start_handler)

        # status_handler = CommandHandler("status", self.command_status)
        # self.application.add_handler(status_handler)

        # heating_handler = CommandHandler("heating", self.command_heating)
        # self.application.add_handler(heating_handler)

        scheduler.add_job(self.start)

    async def command_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,  # type: ignore
            text="The overall system status is: OK",
        )

    async def command_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [
                InlineKeyboardButton("1", callback_data="1"),
                InlineKeyboardButton("2", callback_data="2"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=update.effective_chat.id,  # type: ignore
            text="I'm a bot, please talk to me!",
            reply_markup=reply_markup,
        )

    async def register_telegram_commands(self, application: Application):
        application.add_handler(CommandHandler("start", self.command_start))
        return await super().register_telegram_commands(application=application)

    async def start(self):
        for integration in self.integrations:
            await integration.register_telegram_commands(self.application)

        # TODO: Retry if it fails
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()  # type: ignore

    async def shutdown(self):
        await self.application.updater.stop()  # type: ignore
        await self.application.stop()
        await self.application.shutdown()
        return await super().shutdown()
