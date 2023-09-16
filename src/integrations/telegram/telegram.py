from logging import Logger
from src.integrations.base import TelegramHandler

from telegram import Update
from src.integrations.telegram import TelegramIntegration

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)


class DefaultTelegramHandler(TelegramHandler[TelegramIntegration]):
    def __init__(self, logger: Logger, integration: TelegramIntegration):
        self.logger = logger
        self.integration = integration

    async def register_telegram_commands(self, application: Application):
        application.add_handler(CommandHandler("status", self.command_status))
        await super().register_telegram_commands(application=application)

    async def command_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,  # type: ignore
            text="Your chat id is: {}".format(update.effective_chat.id),  # type: ignore
        )
