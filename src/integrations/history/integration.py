from logging import Logger
from typing import Callable, List, Optional

from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig
from telegram.ext import (
    Application,
)

from src.integrations.base import BaseIntegration, Integration, TelegramHandler


class HistoryIntegration(Integration):
    def __init__(
        self,
        config: DictConfig,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        logger: Logger,
        telegram_handler: Optional[Callable[..., TelegramHandler]],
    ):
        super().__init__(
            config=config,
            scheduler=scheduler,
            integrations=integrations,
            logger=logger,
            telegram_handler=telegram_handler,
        )

        # scheduler.add_job(self.start)

    async def register_telegram_commands(self, application: Application) -> None:
        await super().register_telegram_commands(application=application)

    async def shutdown(self):
        return await super().shutdown()
