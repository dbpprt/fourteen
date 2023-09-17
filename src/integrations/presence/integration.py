from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import Callable, List, Optional

import asyncssh
from apscheduler.schedulers.base import BaseScheduler
from omegaconf import DictConfig, ListConfig
from telegram import (
    Bot,
)

from src.integrations.base import BaseIntegration, Integration, TelegramHandler
from src.utils.persistant_state import PersistentState


@dataclass
class State:
    @dataclass
    class Person:
        name: str
        present: bool
        last_seen: Optional[datetime]

    vacation_mode: bool
    persons: List[Person]


class PresenceIntegration(Integration):
    def __init__(
        self,
        config: DictConfig,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        logger: Logger,
        telegram_handler: Optional[Callable[..., TelegramHandler]],
        state_overrides: DictConfig,
        host: str,
        username: str,
        password: str,
        devices: ListConfig,
    ):
        super().__init__(
            config=config,
            scheduler=scheduler,
            integrations=integrations,
            logger=logger,
            telegram_handler=telegram_handler,
        )

        self.state_overrides = state_overrides
        self.host = host
        self.username = username
        self.password = password
        self.devices = devices

        self.bot: Optional[Bot] = None

        scheduler.add_job(self.initialize)
        scheduler.add_job(
            self.refresh,
            "interval",
            seconds=60,
            next_run_time=datetime.now(scheduler.timezone),
        )
        # scheduler.add_job(
        #     self.confirom_home_occupancy,
        #     "interval",
        #     minutes=15,
        #     next_run_time=datetime.now(scheduler.timezone),
        # )

    @property
    def vacation_mode(self) -> bool:
        return self.state.vacation_mode

    @property
    def persons(self) -> List[State.Person]:
        return self.state.persons

    @property
    def home_occupied(self) -> bool:
        for person in self.persons:
            if person.present:
                return True
        return False

    async def initialize(self):
        self.persistant_state: PersistentState[State] = PersistentState(
            "presence", self.config.data_dir
        )

        # default values for heating state
        await self.persistant_state.initialize(State(vacation_mode=False, persons=[]))

        self.state: State = await self.persistant_state.get()
        # override state with values from config
        for key, value in self.state_overrides.items():
            setattr(self.state, str(key), value)

        # TODO: This might not be needed or even wanted
        self.state.persons = []
        for device in self.devices:
            self.state.persons.append(
                State.Person(name=device.name, present=False, last_seen=None)
            )

        self.logger.info(f"Initialized presence integration with state: {self.state}")

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
                self.logger.info(
                    f"{device.name} is present: {device_present} | with mac: {device.mac}"
                )

                # update state
                for person in self.state.persons:
                    if person.name == device.name:
                        person.present = device_present
                        person.last_seen = datetime.now(self.scheduler.timezone)

        await self.persistant_state.set(self.state)

    # async def confirom_home_occupancy(self):
    #     # send a telegram message to a configured list of users
    #     # ask them to confirm that they left the house
    #     # if no one confirms, assume that no one is home

    #     if self.vacation_mode:
    #         self.logger.info("Vacation mode is on, skipping confirmation")
    #         return

    #     if self.bot is None:
    #         self.logger.error("Bot is not initialized, skipping confirmation")
    #         return

    #     # TODO: Build this...
    #     return 0

    async def shutdown(self):
        return await super().shutdown()
