from pyrogram.types import KeyboardButton, InlineKeyboardButton
from pyrogram import emoji

back_button = KeyboardButton(f"{emoji.BACK_ARROW} Назад")
time_button = KeyboardButton(f"{emoji.ALARM_CLOCK} Время")
help_button = KeyboardButton(f"{emoji.WHITE_QUESTION_MARK} Помощь")