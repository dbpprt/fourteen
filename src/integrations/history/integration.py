from logging import Logger
from typing import List

from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig

from src.integrations.base.integration import BaseIntegration, Integration
from telegram.ext import (
    Application,
)


class HistoryIntegration(Integration):
    def __init__(
        self,
        logger: Logger,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        config: DictConfig,
    ):
        super().__init__(
            config=config, scheduler=scheduler, integrations=integrations, logger=logger
        )

        # scheduler.add_job(self.start)

    async def register_telegram_commands(self, application: Application):
        return await super().register_telegram_commands(application=application)

    async def shutdown(self):
        return await super().shutdown()
