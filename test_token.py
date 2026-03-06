import os
import telebot
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(token)

try:
    me = bot.get_me()
    print(f"Token manzili: TO'G'RI ✅")
    print(f"Bot nomi: {me.first_name}")
    print(f"Username: @{me.username}")
except Exception as e:
    print(f"Xatolik: TOKEn xato yoki faol emas! ❌")
    print(f"Batafsil: {e}")
