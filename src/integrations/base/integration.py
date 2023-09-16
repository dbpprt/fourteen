from abc import ABC, abstractmethod
from logging import Logger
from typing import Callable, List, Optional

from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig
from telegram.ext import Application

from src.integrations.base import TelegramHandler


class BaseIntegration(TelegramHandler, ABC):
    def __init__(self):
        pass

    # @abstractmethod
    # async def register_telegram_commands(self, application: Application):
    #     pass


class Integration(BaseIntegration, ABC):
    def __init__(
        self,
        config: DictConfig,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        logger: Logger,
        telegram_handler: Optional[Callable[..., TelegramHandler]],
    ):
        self.config = config
        self.scheduler = scheduler
        self.integrations = integrations
        self.logger = logger

        if telegram_handler is not None:
            self.telegram_handler = telegram_handler(logger=logger, integration=self)
        else:
            self.telegram_handler = None

        super().__init__()

    async def register_telegram_commands(self, application: Application):
        if self.telegram_handler:
            return await self.telegram_handler.register_telegram_commands(
                application=application
            )
        else:
            return await super().register_telegram_commands(application=application)

    @abstractmethod
    async def shutdown(self):
        pass
