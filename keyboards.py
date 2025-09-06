from pyrogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup
import buttons

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [buttons.time_button, buttons.back_button],
        [buttons.help_button],
        ],
resize_keyboard=True
)