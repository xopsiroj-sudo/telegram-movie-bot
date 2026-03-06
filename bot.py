import os
import sys
import logging
import sqlite3
import subprocess
from flask import Flask, request
import telebot
from dotenv import load_dotenv

# --- Automatic Dependency Installation ---
def install_dependencies():
    required = ["pyTelegramBotAPI", "flask", "python-dotenv"]
    for package in required:
        try:
            __import__(package if package != "pyTelegramBotAPI" else "telebot")
        except ImportError:
            print(f"Installing missing dependency: {package}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Uncomment to auto-check on run (though requirement 2 says pip install ...)
# install_dependencies()

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Load Environment Variables ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_RAW = os.getenv("ADMIN_ID") or os.getenv("ADMINS", "")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_LINK = os.getenv("CHANNEL_LINK")
CHANNELS_RAW = os.getenv("CHANNELS", "") # Format: "@chan1|link1,@chan2|link2"
PORT = int(os.getenv("PORT", 5000))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# ADMIN_IDs listini shakllantirish
ADMIN_IDS = [sid.strip() for sid in ADMIN_IDS_RAW.split(",") if sid.strip()]

# CHANNELS listini shakllantirish
REQUIRED_CHANNELS = []
if CHANNELS_RAW:
    for item in CHANNELS_RAW.split(","):
        if "|" in item:
            cid, clink = item.split("|", 1)
            REQUIRED_CHANNELS.append({"id": cid.strip(), "link": clink.strip()})
        else:
            REQUIRED_CHANNELS.append({"id": item.strip(), "link": None})
elif CHANNEL_ID:
    REQUIRED_CHANNELS.append({"id": CHANNEL_ID, "link": CHANNEL_LINK})

if not BOT_TOKEN or not ADMIN_IDS:
    logger.error("BOT_TOKEN or ADMIN_ID not found in .env file")
    sys.exit(1)

# --- Database Initialization ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "movies.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            file_identifier TEXT NOT NULL,
            title TEXT,
            category TEXT,
            type TEXT DEFAULT 'path',
            views INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            join_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN search_count INTEGER DEFAULT 0")
    except: pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_active DATETIME DEFAULT CURRENT_TIMESTAMP")
    except: pass
    
    conn.commit()
    conn.close()
    logger.info("Ma'lumotlar bazasi tekshirildi/yaratildi.")

from datetime import date

def stat_inc():
    today = str(date.today())
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO stats(day) VALUES (?)", (today,))
        cursor.execute("UPDATE stats SET searches = searches + 1 WHERE day=?", (today,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Stat error: {e}")

def register_user(user_id, username):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
        cursor.execute("UPDATE users SET last_active = CURRENT_TIMESTAMP, search_count = search_count + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error registering user: {e}")

init_db()

# --- Telegram Bot Setup ---
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Majburiy Obuna Tekshiruvi ---
def check_subscription(user_id):
    for channel in REQUIRED_CHANNELS:
        try:
            member = bot.get_chat_member(channel['id'], user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                logger.info(f"Foydalanuvchi {user_id} {channel['id']} kanalida emas.")
                return False
        except Exception as e:
            logger.error(f"Subscription check error for {channel['id']}: {e}")
            continue
            
    return True

def get_subscription_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    for channel in REQUIRED_CHANNELS:
        url = channel['link']
        if not url:
            try:
                chat = bot.get_chat(channel['id'])
                url = f"https://t.me/{chat.username}" if chat.username else chat.invite_link
            except:
                url = f"https://t.me/{channel['id'].replace('@', '')}"
        chan_name = channel['id']
        markup.add(telebot.types.InlineKeyboardButton(f"➕ {chan_name} ga a'zo bo'lish", url=url))
    
    markup.add(telebot.types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    return markup

# --- Bot Command Handlers ---

def get_main_menu():
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(telebot.types.KeyboardButton("🔍 Qidirish"))
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    register_user(message.from_user.id, message.from_user.username)
    
    if not check_subscription(message.from_user.id):
        bot.send_message(
            message.chat.id, 
            "Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling! 👇", 
            reply_markup=get_subscription_markup()
        )
        return

    bot.reply_to(message, "Kino Botiga xush kelibsiz! ✅\nKino olish uchun kodni yoki nomini yuboring.", reply_markup=get_main_menu())

@bot.message_handler(commands=['debug'])
def debug_info(message):
    res = f"ℹ️ **Debug Ma'lumotlari:**\n\n"
    res += f"👤 Sizning ID: `{message.from_user.id}`\n"
    res += f"👑 Adminlar: `{', '.join(ADMIN_IDS)}` (Siz admin: {'✅' if str(message.from_user.id) in ADMIN_IDS else '❌'})\n"
    res += f"📢 Kerakli kanallar soni: {len(REQUIRED_CHANNELS)}\n"
    res += f"📂 Baza yo'li: `{DB_PATH}`"
    bot.reply_to(message, res, parse_mode="Markdown")

@bot.message_handler(commands=['checkbot'])
def check_bot_access(message):
    if str(message.from_user.id) not in ADMIN_IDS: return
    try:
        chat = bot.get_chat(CHANNEL_ID)
        bot.reply_to(message, f"Kanal topildi! ✅\nNomi: {chat.title}\nID: `{chat.id}`", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"Xatolik: Kanal topilmadi! ❌\nBatafsil: {e}")

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if str(message.from_user.id) not in ADMIN_IDS:
        bot.reply_to(message, f"Ruxsat berilmagan. Sizning ID: `{message.from_user.id}`", parse_mode="Markdown")
        return
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("📊 Statistika", callback_data="stats"))
    markup.add(telebot.types.InlineKeyboardButton("🎬 Kinolar ro'yxati", callback_data="list_movies"))
    markup.add(telebot.types.InlineKeyboardButton("🗑 Kino o'chirish", callback_data="delete_movie_list"))
    markup.add(telebot.types.InlineKeyboardButton("👥 Foydalanuvchilar", callback_data="admin_users"))
    markup.add(telebot.types.InlineKeyboardButton("🔍 User qidirish (ID)", callback_data="search_user"))
    markup.add(telebot.types.InlineKeyboardButton("✉️ Xabar yuborish (Direct)", callback_data="direct_msg"))
    markup.add(telebot.types.InlineKeyboardButton("🔥 Top kinolar", callback_data="top_movies"))
    markup.add(telebot.types.InlineKeyboardButton("📢 Xabar yuborish (Broadcast)", callback_data="broadcast"))
    bot.send_message(message.chat.id, "Admin paneliga xush kelibsiz!", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "check_sub":
        if check_subscription(call.from_user.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "Tabriklaymiz! ✅\nBotdan foydalanishingiz mumkin.", reply_markup=get_main_menu())
        else:
            bot.answer_callback_query(call.id, "Siz hali barcha kanallarga a'zo bo'lmadingiz! ❌", show_alert=True)
        return

    if call.data.startswith("get_movie_"):
        file_id = call.data.replace("get_movie_", "")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM movies WHERE file_identifier = ?", (file_id,))
        res = cursor.fetchone()
        conn.close()
        title = res[0] if res else ""
        try:
            bot.send_document(call.message.chat.id, file_id, caption=title)
        except Exception as e:
            logger.error(f"Error sending movie from callback: {e}")
            bot.send_message(call.message.chat.id, "Faylni yuborishda xatolik.")
        bot.answer_callback_query(call.id)
        return

    if call.data.startswith("msg_"):
        target_id = call.data.replace("msg_", "")
        bot.answer_callback_query(call.id)
        msg = bot.send_message(call.message.chat.id, f"Foydalanuvchi {target_id} ga yubormoqchi bo'lgan xabaringizni kiriting:")
        bot.register_next_step_handler(msg, lambda m: send_direct_message(m, target_id))
        return

    # Faqat admin uchun ruxsat berilgan callbacklar
    if str(call.from_user.id) not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "Bu funksiya faqat admin uchun.")
        return

    if call.data == "stats":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM movies")
        movie_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        conn.close()
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"📊 **Statistika:**\n\n🎬 Kinolar soni: {movie_count}\n👥 Foydalanuvchilar: {user_count}", parse_mode="Markdown")
    
    elif call.data == "broadcast":
        msg = bot.send_message(call.message.chat.id, "Foydalanuvchilarga yubormoqchi bo'lgan xabaringizni kiriting:")
        bot.register_next_step_handler(msg, process_broadcast)

    elif call.data == "admin_users":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, join_date, search_count, last_active FROM users ORDER BY last_active DESC LIMIT 15")
        users_list = cursor.fetchall()
        conn.close()
        
        if not users_list:
            bot.send_message(call.message.chat.id, "Foydalanuvchilar topilmadi.")
        else:
            text = "👥 **Oxirgi 15 ta faol foydalanuvchi:**\n\n"
            for u in users_list:
                username = f"@{u[1]}" if u[1] else "No Username"
                text += f"🆔 `{u[0]}` | {username}\n📅 Join: {u[2]}\n🔄 Faollik: {u[4]} (Searching: {u[3]})\n\n"
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif call.data == "search_user":
        msg = bot.send_message(call.message.chat.id, "Qidirilayotgan foydalanuvchining ID raqamini kiriting:")
        bot.register_next_step_handler(msg, process_search_user)

    elif call.data == "direct_msg":
        msg = bot.send_message(call.message.chat.id, "Xabar yubormoqchi bo'lgan foydalanuvchining ID raqamini kiriting:")
        bot.register_next_step_handler(msg, process_direct_msg_id)

    elif call.data == "top_movies":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT code, title, views FROM movies ORDER BY views DESC LIMIT 10")
        top_list = cursor.fetchall()
        conn.close()
        
        if not top_list:
            bot.send_message(call.message.chat.id, "Kinolar topilmadi.")
        else:
            text = "🔥 **Eng ko'p ko'rilgan 10 ta kino:**\n\n"
            for i, m in enumerate(top_list, 1):
                text += f"{i}. `{m[0]}` | {m[1] or 'Nomsiz'} | 👀 {m[2]}\n"
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        bot.answer_callback_query(call.id)

    elif call.data == "delete_movie_list":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT code, title FROM movies ORDER BY id DESC LIMIT 10")
        movies = cursor.fetchall()
        conn.close()
        
        if not movies:
            bot.send_message(call.message.chat.id, "O'chirish uchun kinolar yo'q.")
        else:
            markup = telebot.types.InlineKeyboardMarkup()
            for m in movies:
                markup.add(telebot.types.InlineKeyboardButton(f"❌ {m[0]} - {m[1]}", callback_data=f"del_{m[0]}"))
            bot.send_message(call.message.chat.id, "O'chirmoqchi bo'lgan kinoni tanlang:", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call.data.startswith("del_"):
        movie_code = call.data.replace("del_", "")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movies WHERE code = ?", (movie_code,))
        conn.commit()
        conn.close()
        bot.send_message(call.message.chat.id, f"Kino (kod: {movie_code}) o'chirildi! ✅")
        bot.answer_callback_query(call.id)

    elif call.data == "list_movies":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT code, title FROM movies ORDER BY id DESC LIMIT 10")
        movies = cursor.fetchall()
        conn.close()
        
        if not movies:
            bot.send_message(call.message.chat.id, "Hozircha kinolar yo'q.")
        else:
            text = "🎬 **Oxirgi 10 ta kino:**\n" + "\n".join([f"- `{m[0]}` | {m[1] or 'Nomsiz'}" for m in movies])
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")

@bot.inline_handler(lambda query: True)
def inline_search(query):
    text = query.query.lower()
    if not text: return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, title, file_identifier, category FROM movies WHERE lower(title) LIKE ? LIMIT 10", (f"%{text}%",))
    results = cursor.fetchall()
    conn.close()
    
    inline_results = []
    for m in results:
        code, title, f_id, cat = m
        inline_results.append(telebot.types.InlineQueryResultCachedVideo(
            id=str(code),
            video_file_id=f_id,
            title=title or "Nomsiz kino",
            description=f"Kod: {code} | Kategoriya: {cat or 'Yo`q'}",
            caption=f"🎬 <b>{title or 'Nomsiz'}</b>\n🔑 Kod: {code}"
        ))
    
    bot.answer_inline_query(query.id, inline_results, cache_time=1)

def process_broadcast(message):
    if str(message.from_user.id) not in ADMIN_IDS: return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    
    count = 0
    fail = 0
    bot.send_message(message.chat.id, f"Xabar yuborish boshlandi ({len(users)} foydalanuvchi)...")
    
    for user_row in users:
        try:
            bot.copy_message(user_row[0], message.chat.id, message.message_id)
            count += 1
        except Exception as e:
            fail += 1
            logger.error(f"Failed to send broadcast to {user_row[0]}: {e}")
            
    bot.send_message(message.chat.id, f"Xabar yuborish yakunlandi! ✅\n\n✅ Muvaffaqiyatli: {count}\n❌ Xatolik: {fail}")

def process_search_user(message):
    if str(message.from_user.id) not in ADMIN_IDS: return
    user_id = message.text.strip()
    if not user_id.isdigit():
        bot.send_message(message.chat.id, "ID faqat raqamlardan iborat bo'lishi kerak.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    u = cursor.fetchone()
    conn.close()
    
    if not u:
        bot.send_message(message.chat.id, "Bunday ID dagi foydalanuvchi topilmadi.")
    else:
        # DB schema order: user_id, username, join_date, search_count, last_active
        res = f"🆔 **Foydalanuvchi ma'lumotlari:**\n\n"
        res += f"ID: `{u[0]}`\n"
        res += f"Username: @{u[1] if u[1] else 'Yo`q'}\n"
        res += f"Qo'shilgan: {u[2]}\n"
        # Since we added columns, let's be safe with indexing if they are newly added
        try:
            res += f"Qidiruvlar soni: {u[3]}\n"
            res += f"Oxirgi faollik: {u[4]}"
        except: pass
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("✉️ Xabar yuborish", callback_data=f"msg_{u[0]}"))
        bot.send_message(message.chat.id, res, parse_mode="Markdown", reply_markup=markup)

def process_direct_msg_id(message):
    if str(message.from_user.id) not in ADMIN_IDS: return
    user_id = message.text.strip()
    if not user_id.isdigit():
        bot.send_message(message.chat.id, "ID raqam bo'lishi kerak.")
        return
    
    msg = bot.send_message(message.chat.id, f"Foydalanuvchi {user_id} ga yubormoqchi bo'lgan xabaringizni kiriting:")
    bot.register_next_step_handler(msg, lambda m: send_direct_message(m, user_id))

def send_direct_message(message, target_id):
    if str(message.from_user.id) not in ADMIN_IDS: return
    try:
        bot.copy_message(target_id, message.chat.id, message.message_id)
        bot.send_message(message.chat.id, f"Xabar muvaffaqiyatli yuborildi! ✅ (ID: {target_id})")
    except Exception as e:
        bot.send_message(message.chat.id, f"Xabar yuborishda xatolik: {e}")

@bot.message_handler(commands=['add'])
def add_movie(message):
    # Security check
    if str(message.from_user.id) not in ADMIN_IDS:
        bot.reply_to(message, f"Ruxsat berilmagan. Sizning ID: `{message.from_user.id}`", parse_mode="Markdown")
        return

    try:
        # Expected format: /add <code> <file_path> [title]
        args = message.text.split(maxsplit=3)
        if len(args) < 3:
            bot.reply_to(message, "Foydalanish: /add <kod> <fayl_yo'li> [sarlavha]")
            return

        code = args[1]
        file_path = args[2]
        title = args[3] if len(args) > 3 else None

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO movies (code, file_identifier, title, type) VALUES (?, ?, ?, ?)", 
                       (code, file_path, title, 'path'))
        conn.commit()
        conn.close()

        logger.info(f"Admin kino qo'shdi: {code} -> {file_path}")

        bot.reply_to(message, f"Kino muvaffaqiyatli qo'shildi. ✅\nKodi: {code}\nNomi: {title or 'Nomsiz'}")

    except Exception as e:
        logger.error(f"Error in /add command: {e}")
        bot.reply_to(message, "Kinoni qo'shib bo'lmadi. Loglarni tekshiring.")

# --- Avtomatik Kino Qo'shish (Kanaldan yoki Admindan) ---

def save_auto_movie(message, file_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Keyingi kodni aniqlash (100dan boshlab)
        cursor.execute("SELECT code FROM movies ORDER BY CAST(code AS INTEGER) DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            try:
                new_code = str(int(row[0]) + 1)
            except:
                new_code = str(101)
        else:
            new_code = str(101)
        
        title = None
        category = "Boshqa"
        if message.caption:
            parts = message.caption.split("|")
            title = parts[0].strip()
            if len(parts) > 1: category = parts[1].strip()
        elif hasattr(message, 'document') and message.document:
            title = message.document.file_name

        cursor.execute(
            "INSERT OR REPLACE INTO movies (code, file_identifier, title, category, type) VALUES (?, ?, ?, ?, ?)", 
            (new_code, file_id, title, category, 'file_id')
        )
        conn.commit()
        conn.close()
        
        # Sarlavhani tahrirlash (Kod qo'shish) - faqat kanaldan kelsa
        if hasattr(message, 'chat') and message.chat.type in ['channel']:
            new_caption = f"{title or ''}".strip() + f"\n\n\U0001f511 Kod: {new_code}"
            try:
                bot.edit_message_caption(
                    chat_id=message.chat.id, 
                    message_id=message.message_id, 
                    caption=new_caption
                )
            except Exception as e:
                logger.warning(f"Sarlavhani tahrirlab bo'lmadi: {e}")

        logger.info(f"Kino saqlandi: kod={new_code}, file_id={file_id[:20]}...")
        return new_code
    except Exception as e:
        logger.error(f"Error auto saving movie: {e}", exc_info=True)
        return str(e)

@bot.message_handler(content_types=['video', 'document'])
def handle_docs_videos(message):
    # Faqat admin yuborsa saqlaydi
    if str(message.from_user.id) not in ADMIN_IDS:
        bot.reply_to(message, f"Kino saqlash uchun admin bo'lishingiz kerak.\nSizning ID: `{message.from_user.id}`", parse_mode="Markdown")
        return

    file_id = None
    if message.content_type == 'video':
        file_id = message.video.file_id
    elif message.content_type == 'document':
        file_id = message.document.file_id
    
    if file_id:
        code = save_auto_movie(message, file_id)
        # save_auto_movie returns code string or error string (never None now)
        if code and code.isdigit():
            bot.reply_to(message, f"Kino tizimga saqlandi! ✅\nKodi: `{code}`", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"Xatolik: Kinoni saqlab bo'lmadi.\n🔍 Sabab: `{code}`", parse_mode="Markdown")
    else:
        bot.reply_to(message, "Fayl topilmadi.")

@bot.channel_post_handler(content_types=['video', 'document'])
def handle_channel_movie(message):
    # Kanaldan kelgan kinolarni avtomatik saqlash
    file_id = None
    if message.content_type == 'video':
        file_id = message.video.file_id
    elif message.content_type == 'document':
        file_id = message.document.file_id
        
    if file_id:
        save_auto_movie(message, file_id)

@bot.channel_post_handler(func=lambda message: True)
def handle_any_channel_post(message):
    logger.info(f"Yangi xabar kanaldan keldi! Chat ID: {message.chat.id}, Title: {message.chat.title}")
    # Agar admin bo'lsa, xabar yuborishi ham mumkin
    try:
        for admin_id in ADMIN_IDS:
            bot.send_message(admin_id, f"📢 Kanaldan xabar keldi!\nKanal nomi: {message.chat.title}\nID: `{message.chat.id}`", parse_mode="Markdown")
    except:
        pass

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    register_user(message.from_user.id, message.from_user.username)
    # Majburiy obuna tekshiruvi
    if not check_subscription(message.from_user.id):
        bot.send_message(
            message.chat.id, 
            "Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling! 👇", 
            reply_markup=get_subscription_markup()
        )
        return

    code = message.text.strip()
    if code == "🔍 Qidirish":
        bot.send_message(message.chat.id, "Kino nomini yoki kodini yuboring.")
        return

    stat_inc()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Avval kod bo'yicha qidiramiz
    cursor.execute("SELECT file_identifier, type, title FROM movies WHERE code = ?", (code,))
    result = cursor.fetchone()
    
    # Agar kod bo'yicha topilmasa, nomi bo'yicha qidiramiz
    if not result:
        cursor.execute("SELECT file_identifier, type, title FROM movies WHERE title LIKE ?", (f"%{code}%",))
        results = cursor.fetchall()
        
        if len(results) == 1:
            result = results[0]
        elif len(results) > 1:
            markup = telebot.types.InlineKeyboardMarkup()
            for r in results[:10]: # Maksimal 10 ta natija
                markup.add(telebot.types.InlineKeyboardButton(r[2] or "Nomsiz kino", callback_data=f"get_movie_{r[0]}"))
            bot.send_message(message.chat.id, "Bir nechta kino topildi. Tanlang:", reply_markup=markup)
            conn.close()
            return
            
    conn.close()

    if result:
        file_id, f_type, f_title = result[:3]
        try:
            # Ko'rishlar sonini oshirish
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("UPDATE movies SET views = views + 1 WHERE file_identifier = ?", (file_id,))
            conn.commit()
            conn.close()
            
            if f_type == 'path':
                if os.path.exists(file_id):
                    with open(file_id, 'rb') as movie_file:
                        bot.send_document(message.chat.id, movie_file, caption=f_title)
                else:
                    logger.warning(f"File not found: {file_id}")
                    bot.reply_to(message, "Fayl serverda topilmadi.")
                    return
            else:
                bot.send_document(message.chat.id, file_id, caption=f_title)
            
            logger.info(f"Sent movie for code/title {code}")
        except Exception as e:
            logger.error(f"Error sending movie {code}: {e}")
            bot.reply_to(message, "Faylni yuborishda xatolik yuz berdi.")
    else:
        bot.reply_to(message, "Kino topilmadi. Kod yoki nomni to'g'ri kiriting.")

# --- Webhook and Flask Server ---

@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    if WEBHOOK_URL:
        bot.set_webhook(url=WEBHOOK_URL + '/' + BOT_TOKEN)
        return "Webhook set successfully!", 200
    else:
        return "WEBHOOK_URL not set in .env", 400

if __name__ == "__main__":
    # Ensure dependencies are installed
    install_dependencies()
    
    logger.info("Starting Flask server for Telegram Movie Bot...")
    
    # In production, set the webhook automatically if URL is provided
    if WEBHOOK_URL:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL + '/' + BOT_TOKEN)
        logger.info(f"Webhook {WEBHOOK_URL} ga o'rnatildi")
        # Start Flask server
        app.run(host='0.0.0.0', port=PORT, debug=False)
    else:
        logger.warning("WEBHOOK_URL topilmadi, Polling rejimida ishlanmoqda...")
        # Start Flask in background thread if needed, or just run polling
        # For simplicity in this demo, we'll just use polling if no webhook
        bot.remove_webhook()
        bot.infinity_polling()
