from abc import ABC, abstractmethod
from logging import Logger
from telegram.ext import Application

from typing import TypeVar, Generic

T = TypeVar("T", bound="TelegramHandler")


class TelegramHandler(Generic[T], ABC):
    def __init__(self, logger: Logger, integration: T, *args, **kwargs):
        self.logger = logger
        self.integration = integration

    @abstractmethod
    async def register_telegram_commands(self, application: Application):
        pass
