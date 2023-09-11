from logging import Logger
from typing import List

from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig

from src.integrations.base.integration import BaseIntegration, Integration
from telegram import Update
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

        scheduler.add_job(self.start)

    async def command_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,  # type: ignore
            text="Your chat id is: {}".format(update.effective_chat.id),  # type: ignore
        )

    async def register_telegram_commands(self, application: Application):
        application.add_handler(CommandHandler("status", self.command_status))
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
