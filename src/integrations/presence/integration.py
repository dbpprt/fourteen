from datetime import datetime
from logging import Logger
from typing import List

from apscheduler.schedulers.base import BaseScheduler
import asyncssh
from omegaconf import DictConfig, ListConfig

from src.integrations.base.integration import BaseIntegration, Integration
from telegram.ext import (
    Application,
)


class PresenceIntegration(Integration):
    def __init__(
        self,
        logger: Logger,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        config: DictConfig,
        host: str,
        username: str,
        password: str,
        devices: ListConfig,
    ):
        super().__init__(
            config=config, scheduler=scheduler, integrations=integrations, logger=logger
        )

        self.host = host
        self.username = username
        self.password = password
        self.devices = devices

        scheduler.add_job(
            self.refresh,
            "interval",
            seconds=60,
            next_run_time=datetime.now(scheduler.timezone),
        )

    async def refresh(self):
        async with asyncssh.connect(
            self.host, username=self.username, password=self.password
        ) as connection:
            for device in self.devices:
                result = await connection.run(
                    f'mca-dump | jq ". | {"{port_table}"}" | grep -c "{device.mac}"',
                    check=False,
                )

                # this is a hack, but it works
                # a very insecure hack
                device_present = eval(str(result.stdout)) >= 1
                self.logger.info(f"Device present: {device_present}")

    async def register_telegram_commands(self, application: Application):
        return await super().register_telegram_commands(application=application)

    async def shutdown(self):
        return await super().shutdown()
