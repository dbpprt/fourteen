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
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

from src.integrations.base import TelegramHandler
from src.integrations.presence import PresenceIntegration

EXPECT_BUTTON_CLICK = range(1)


class PresenceTelegramHandler(TelegramHandler[PresenceIntegration]):
    def __init__(self, logger: Logger, integration: PresenceIntegration):
        self.logger = logger
        self.integration = integration

    async def command_presence(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        keyboard: List[List[InlineKeyboardButton]] = []

        for person in self.integration.state.persons:
            # calculate minutes since last seen

            last_seen: int = -1
            if person.last_seen is not None:
                last_seen = (
                    datetime.now(self.integration.scheduler.timezone) - person.last_seen
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
                    f"🏖 Vacation mode is {'on' if self.integration.state.vacation_mode else 'off'}",
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
        self.integration.state.vacation_mode = not self.integration.state.vacation_mode
        await self.integration.persistant_state.set(self.integration.state)

        if self.integration.state.vacation_mode:
            await query.edit_message_text(  # type: ignore
                text="Vacation mode is now on, enjoy your trip! 🏖"
            )
            return ConversationHandler.END
        else:
            await query.edit_message_text(  # type: ignore
                text="Vacation mode is now off, welcome back! 🏡"
            )
            return ConversationHandler.END

    async def register_telegram_commands(self, application: Application) -> None:
        await super().register_telegram_commands(application=application)

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
