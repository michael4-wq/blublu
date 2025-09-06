from pyrogram.types import ReplyKeyboardMarkup
import buttons

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [buttons.time_button, buttons.back_button],
        [buttons.help_button],
        [buttons.meme_en_button, buttons.meme_ru_button]
    ],
    resize_keyboard=True
)