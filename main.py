import config
import custom_filters
import buttons
import keyboards
from pyrogram import Client
from pyrogram import filters
import time
from custom_filters import button_filter, reply_text_filter
from pyrogram.types import Message


bot = Client(
    name="my_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
)

@bot.on_message(filters.command("start") | button_filter(buttons.back_button))
async def start_command(_, message: Message):
    await message.reply(
        "Привет! Я бот, который умеет считать, показывать время и показывать инфорацию по мемам\n"
        f"Нажми на кнопку {buttons.help_button.text} для помощи.",
        reply_markup=keyboards.main_keyboard
    )


@bot.on_message(filters.command("time") | button_filter(buttons.time_button))
async def time_command(_, message: Message):
    current_time = time.strftime("%H:%M:%S")
    await message.reply(
        f"⏰ Сейчас: {current_time}",
        reply_markup=keyboards.main_keyboard
    )

    if __name__ == "__main__":
        bot.run()
