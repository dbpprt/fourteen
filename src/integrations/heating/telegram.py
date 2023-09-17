from datetime import datetime
from logging import Logger

import yaml
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.integrations.base import TelegramHandler
from src.integrations.heating import HeatingIntegration

EXPECT_BUTTON_CLICK, EXPECT_STATE_KEY, EXPECT_STATE_VALUE = range(3)


class HeatingTelegramHandler(TelegramHandler[HeatingIntegration]):
    def __init__(self, logger: Logger, integration: HeatingIntegration):
        self.logger = logger
        self.integration = integration

    async def command_heating(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.integration.last_boiler_info is None:
            await update.message.reply_text(  # type: ignore
                "The boiler is currently not available!"
            )

            return

        keyboard = [
            [
                InlineKeyboardButton(
                    f"🔛 Heating active: {self.integration.state.heating_active}",
                    callback_data="toggle_heating_active",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🌡️ Flow temperature: {self.integration.last_boiler_info.current_flow_temperature}°C",
                    callback_data="not_supported",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🌡️ Selected flow temperature: {self.integration.last_boiler_info.selected_flow_temperature}°C",
                    callback_data="not_supported",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"🌡️ Calculated flow temperature: {self.integration.target_supply_temperature}°C",
                    callback_data="not_supported",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔎 Show boiler state",
                    callback_data="show_boiler_state",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔎 Show persistent state",
                    callback_data="show_persistent_state",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🖊️ Edit persistent state",
                    callback_data="edit_persistent_state",
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        last_refreshed_seconds_ago = (
            datetime.now() - self.integration.last_boiler_info_timestamp
        ).seconds

        await update.message.reply_text(  # type: ignore
            f"Data has been refreshed {last_refreshed_seconds_ago} seconds ago:",
            reply_markup=reply_markup,
        )

        return EXPECT_BUTTON_CLICK

    async def edit_persistent_state(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        query = update.callback_query
        await query.answer()  # type: ignore

        # get all keys from self.state
        keys = [
            [key]
            for key in self.integration.state.__dict__.keys()
            if not key.startswith("_")
        ]

        reply_markup = ReplyKeyboardMarkup(
            keys,
            one_time_keyboard=True,
            input_field_placeholder="Which?",
        )

        await query.message.reply_text(  # type: ignore
            "What property do you want to change?",
            reply_markup=reply_markup,
        )

        return EXPECT_STATE_KEY

    async def set_persistent_state_key(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        key: str = update.message.text  # type: ignore

        # if key not in self.state abort
        if not hasattr(self.integration.state, key):
            await update.message.reply_text(  # type: ignore
                f"Sorry, {key} is not a valid key!"
            )
            return ConversationHandler.END

        context.user_data["key"] = key  # type: ignore
        await update.message.reply_text(  # type: ignore
            f"Ok, what should the new value for {key} be? It is currently {getattr(self.integration.state, key)}"
        )

        return EXPECT_STATE_VALUE

    async def set_persistent_state_value(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        value: str = update.message.text  # type: ignore
        old_value = getattr(self.state, context.user_data["key"])  # type: ignore

        key = context.user_data["key"]  # type: ignore

        try:  # try to convert value to old_value type
            # set new value, persist it and update self.state
            # automatically detect target type
            if isinstance(old_value, bool):
                new_value = value.lower() == "true"
            elif isinstance(old_value, int):
                new_value = int(value)
            elif isinstance(old_value, float):
                new_value = float(value)
            else:
                new_value = str(value)
        except:  # noqa
            self.logger.exception(f"Failed to convert {value} to {type(old_value)}")
            await update.message.reply_text(  # type: ignore
                f"Failed to convert {value} to {type(old_value)}"
            )
        else:
            setattr(self.integration.state, key, new_value)
            await self.integration.persistent_state.set(self.integration.state)

            await update.message.reply_text(  # type: ignore
                f"Ok, setting {key} from {old_value} to {value}..."
            )

        return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        return ConversationHandler.END

    async def not_supported(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        query = update.callback_query
        await query.answer()  # type: ignore
        await query.edit_message_text(  # type: ignore
            text="Oops, this is not supported yet..."
        )
        return ConversationHandler.END

    async def button_clicked_toggle_heating(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        query = update.callback_query
        await query.answer()  # type: ignore
        self.integration.state.heating_active = (
            not self.integration.state.heating_active
        )
        await self.integration.persistent_state.set(self.integration.state)
        self.logger.info(
            f"Set heating_active to {self.integration.state.heating_active}"
        )
        await query.edit_message_text(  # type: ignore
            text=f"Ok! Heating is now {'on' if self.integration.state.heating_active else 'off'}..."
        )
        return ConversationHandler.END

    async def show_persistent_state(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Show new choice of buttons"""
        query = update.callback_query
        await query.answer()  # type: ignore
        await query.edit_message_text(text=yaml.dump(self.integration.state))  # type: ignore
        return ConversationHandler.END

    async def show_boiler_state(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Show new choice of buttons"""
        query = update.callback_query
        await query.answer()  # type: ignore
        await query.edit_message_text(text=yaml.dump(self.integration.last_boiler_info))  # type: ignore
        return ConversationHandler.END

    async def register_telegram_commands(self, application: Application) -> None:
        conversation_handler = ConversationHandler(
            per_chat=True,
            per_user=True,
            entry_points=[CommandHandler("heating", self.command_heating)],
            states={
                EXPECT_BUTTON_CLICK: [
                    CallbackQueryHandler(
                        self.button_clicked_toggle_heating,
                        pattern="^toggle_heating_active$",
                    ),
                    CallbackQueryHandler(
                        self.show_boiler_state,
                        pattern="^show_boiler_state$",
                    ),
                    CallbackQueryHandler(
                        self.show_persistent_state,
                        pattern="^show_persistent_state$",
                    ),
                    CallbackQueryHandler(
                        self.edit_persistent_state,
                        pattern="^edit_persistent_state$",
                    ),
                    CallbackQueryHandler(
                        self.not_supported,
                        pattern="^not_supported$",
                    ),
                ],
                EXPECT_STATE_KEY: [
                    MessageHandler(
                        filters.ALL,
                        self.set_persistent_state_key,
                    )
                ],
                EXPECT_STATE_VALUE: [
                    MessageHandler(
                        filters.ALL,
                        self.set_persistent_state_value,
                    )
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )

        application.add_handler(conversation_handler)
        await super().register_telegram_commands(application=application)
