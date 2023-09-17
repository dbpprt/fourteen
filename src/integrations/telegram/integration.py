from logging import Logger
from typing import Callable, List, Optional

from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig

from src.integrations.base import BaseIntegration, Integration, TelegramHandler
from telegram.ext import (
    ApplicationBuilder,
    PicklePersistence,
)


class TelegramIntegration(Integration):
    def __init__(
        self,
        config: DictConfig,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        logger: Logger,
        telegram_handler: Optional[Callable[..., TelegramHandler]],
        bot_token: str,
        telegram_persistence_location: str,
    ):
        super().__init__(
            config=config,
            scheduler=scheduler,
            integrations=integrations,
            logger=logger,
            telegram_handler=telegram_handler,
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
