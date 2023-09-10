from abc import ABC, abstractmethod
from logging import Logger
from typing import List

from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig
from telegram.ext import Application


class BaseIntegration(ABC):
    def __init__(self):
        pass

    @abstractmethod
    async def register_telegram_commands(self, application: Application):
        pass


class Integration(ABC):
    def __init__(
        self,
        config: DictConfig,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        logger: Logger,
    ):
        self.config = config
        self.scheduler = scheduler
        self.integrations = integrations
        self.logger = logger

    @abstractmethod
    async def register_telegram_commands(self, application: Application):
        pass

    @abstractmethod
    async def shutdown(self):
        pass
