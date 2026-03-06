import os, asyncio, sqlite3
from datetime import date
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineQueryResultCachedVideo, ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.client.default import DefaultBotProperties

# ===== CONFIG =====
BOT_TOKEN = "8261009487:AAEtxUClb4p0uFiMZNiynYuhZqH_CUNlj0o"  # Sizning token
ADMINS = [689757167, 8318430634]           # 2 ta admin
CHANNEL_ID = -1003537169311                # Kino kanali IDsi

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ===== DATABASE =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "movies.db")
db = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS movies (
    code INTEGER PRIMARY KEY,
    title TEXT,
    category TEXT,
    file_id TEXT,
    views INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS stats (
    day TEXT PRIMARY KEY,
    searches INTEGER DEFAULT 0
)
""")
db.commit()

# ===== MENULAR =====
def get_admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📊 Statistika")]],
        resize_keyboard=True
    )

def get_user_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔍 Qidirish")]],
        resize_keyboard=True
    )

# ===== UTILS =====
def next_code():
    cur.execute("SELECT MAX(code) FROM movies")
    last = cur.fetchone()[0]
    return last + 1 if last else 101

def stat_inc():
    today = str(date.today())
    cur.execute("INSERT OR IGNORE INTO stats(day) VALUES (?)", (today,))
    cur.execute("UPDATE stats SET searches = searches + 1 WHERE day=?", (today,))
    db.commit()

# ===== CHANNEL POST HANDLER =====
@dp.channel_post(F.video)
async def save_channel_video(post: types.Message):
    # caption: "Kino nomi | Kategoriya"
    if not post.caption:
        return
    parts = post.caption.split("|")
    title = parts[0].strip()
    category = parts[1].strip() if len(parts) > 1 else "Boshqa"

    code = next_code()
    cur.execute(
        "INSERT INTO movies(code, title, category, file_id) VALUES (?, ?, ?, ?)",
        (code, title, category, post.video.file_id)
    )
    db.commit()
    print(f"Kino qo‘shildi: {code} | {title} | {category}")

# ===== START =====
@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer(
        "🎬 Kino botga xush kelibsiz!\n"
        "🔑 Kino kodini yoki nomini yozing.",
        reply_markup=get_user_menu()
    )

# ===== SEARCH =====
@dp.message()
async def search_movie(m: types.Message):
    text = m.text.strip().lower()
    stat_inc()

    cur.execute("""
        SELECT code, title, file_id FROM movies
        WHERE code=? OR lower(title)=?
    """, (text, text))
    movie = cur.fetchone()
    if movie:
        cur.execute("UPDATE movies SET views=views+1 WHERE code=?", (movie[0],))
        db.commit()
        await bot.send_video(
            m.chat.id,
            movie[2],
            caption=f"🎬 <b>{movie[1]}</b>\n🔑 Kod: {movie[0]}"
        )
    else:
        await m.answer("😔 Kino topilmadi")

# ===== INLINE SEARCH =====
@dp.inline_query()
async def inline_search(q: types.InlineQuery):
    text = q.query.lower()
    cur.execute("""
        SELECT title, file_id, code FROM movies
        WHERE lower(title) LIKE ?
        ORDER BY code DESC LIMIT 10
    """, (f"%{text}%",))
    results = [
        InlineQueryResultCachedVideo(
            id=str(code),
            video_file_id=file_id,
            title=title,
            description=f"Kod: {code}"
        )
        for title, file_id, code in cur.fetchall()
    ]
    await q.answer(results, cache_time=1)

# ===== ADMIN STAT =====
@dp.message(F.text == "📊 Statistika")
async def stats(m: types.Message):
    if m.from_user.id not in ADMINS:
        return
    cur.execute("SELECT COUNT(*) FROM movies")
    movies = cur.fetchone()[0]
    cur.execute("SELECT SUM(searches) FROM stats")
    searches = cur.fetchone()[0] or 0
    await m.answer(f"📊 <b>Bot statistikasi</b>\n🎬 Kinolar: {movies}\n🔍 Qidiruvlar: {searches}")

# ===== RUN =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())




