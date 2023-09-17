from logging import Logger

from telegram.ext import Application

from src.integrations.base import TelegramHandler
from src.integrations.esphome import ESPHomeIntegration


class ESPHomeTelegramHandler(TelegramHandler[ESPHomeIntegration]):
    def __init__(self, logger: Logger, integration: ESPHomeIntegration):
        self.logger = logger
        self.integration = integration

    async def register_telegram_commands(self, application: Application) -> None:
        await super().register_telegram_commands(application=application)
