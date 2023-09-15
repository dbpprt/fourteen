from datetime import datetime
from logging import Logger
from typing import List
from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig, ListConfig
from src.integrations.esphome.utils.device import ESPHomeDevice

from src.integrations.base.integration import BaseIntegration, Integration
from telegram.ext import (
    Application,
)


class ESPHomeIntegration(Integration):
    def __init__(
        self,
        logger: Logger,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        config: DictConfig,
        state_overrides: DictConfig,
        devices: ListConfig,
    ):
        super().__init__(
            config=config, scheduler=scheduler, integrations=integrations, logger=logger
        )

        self.state_overrides = state_overrides
        self.devices: List[ESPHomeDevice] = []

        for device in devices:
            self.devices.append(
                ESPHomeDevice(
                    logger=logger,
                    host=device.host,
                    encryption_key=device.encryption_key,
                )
            )

        scheduler.add_job(
            self.initialize_devices,
            "interval",
            seconds=30,
            next_run_time=datetime.now(scheduler.timezone),
        )

    async def initialize_devices(self):
        for device in self.devices:
            if not device.is_initialized:
                # return value is the state of the device
                self.scheduler.add_job(device.initialize)
            else:
                self.scheduler.add_job(device.heartbeat)

    async def register_telegram_commands(self, application: Application):
        return await super().register_telegram_commands(application=application)

    async def shutdown(self):
        return await super().shutdown()
