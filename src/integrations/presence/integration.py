from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from typing import List, Optional
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)
from apscheduler.schedulers.base import BaseScheduler
import asyncssh
from omegaconf import DictConfig, ListConfig

from src.integrations.base.integration import BaseIntegration, Integration

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


EXPECT_BUTTON_CLICK = range(1)


class PresenceIntegration(Integration):
    def __init__(
        self,
        logger: Logger,
        scheduler: BaseScheduler,
        integrations: List[BaseIntegration],
        config: DictConfig,
        state_overrides: DictConfig,
        host: str,
        username: str,
        password: str,
        devices: ListConfig,
    ):
        super().__init__(
            config=config, scheduler=scheduler, integrations=integrations, logger=logger
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

    async def command_presence(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        keyboard: List[List[InlineKeyboardButton]] = []

        for person in self.state.persons:
            # calculate minutes since last seen

            last_seen: int = -1
            if person.last_seen is not None:
                last_seen = (
                    datetime.now(self.scheduler.timezone) - person.last_seen
                ).seconds // 60
                # round to full minutes
                last_seen = last_seen - (last_seen % 1)

            if last_seen == -1:
                last_seen_message = "never"
            elif last_seen == 0:
                last_seen_message = "just now"
            elif last_seen >= 1:  # noqa
                last_seen_message = f"{last_seen} minutes ago"
            else:
                last_seen_message = "unknown"

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f'👤 {person.name} is {"home" if person.present else "not home"} ({last_seen_message})',
                        callback_data=f"toggle_person_{person.name}",
                    ),
                ]
            )

        # add vacation mode toggle
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🏖 Vacation mode is {'on' if self.state.vacation_mode else 'off'}",
                    callback_data="toggle_vacation_mode",
                ),
            ]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(  # type: ignore
            "Let's see who's home!",
            reply_markup=reply_markup,
        )

        return EXPECT_BUTTON_CLICK

    async def callback_toggle_person(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        query = update.callback_query
        await query.answer()  # type: ignore
        await query.edit_message_text(  # type: ignore
            text="Oops, there is no way to toggle presence yet..."
        )
        return ConversationHandler.END

    async def toggle_vacation_mode(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        query = update.callback_query
        await query.answer()  # type: ignore
        self.state.vacation_mode = not self.state.vacation_mode
        await self.persistant_state.set(self.state)

        if self.state.vacation_mode:
            await query.edit_message_text(  # type: ignore
                text="Vacation mode is now on, enjoy your trip! 🏖"
            )
            return ConversationHandler.END
        else:
            await query.edit_message_text(  # type: ignore
                text="Vacation mode is now off, welcome back! 🏡"
            )
            return ConversationHandler.END

    async def register_telegram_commands(self, application: Application):
        application.add_handler(
            ConversationHandler(
                entry_points=[
                    CommandHandler("presence", self.command_presence),
                ],
                states={
                    EXPECT_BUTTON_CLICK: [
                        CallbackQueryHandler(
                            self.callback_toggle_person, pattern="^toggle_person_*"
                        ),
                        CallbackQueryHandler(
                            self.toggle_vacation_mode, pattern="^toggle_vacation_mode$"
                        ),
                    ],
                },
                fallbacks=[],
            )
        )
        self.bot: Optional[Bot] = application.bot
        return await super().register_telegram_commands(application=application)

    async def shutdown(self):
        return await super().shutdown()
