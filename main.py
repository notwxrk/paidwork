import os
import logging
import asyncio
from datetime import datetime, date
from flask import Flask
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.error import BadRequest

# Flask app yaratish
app = Flask(__name__)

# Log konfiguratsiyasi
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database ulanish
DATABASE_URL = "postgresql://avaz_user:XsjxSdMPWuRt2LUSVkss3YkJFlYKLqVS@dpg-d4bj9d8dl3ps739e98fg-a/avaz"

# Bot token va admin ID
BOT_TOKEN = "8529981140:AAFz8vuEwdC8OZ0t3eOSyrsjDU8MNTyRVws"
ADMIN_ID = 7632409181

# MAXFIY KANAL ID
SECRET_CHANNEL_ID = -1002274010185

# Database funksiyalari
def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                joined_date DATE DEFAULT CURRENT_DATE,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_codes (
                code VARCHAR(50) PRIMARY KEY,
                message_id INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id VARCHAR(100) PRIMARY KEY,
                channel_username VARCHAR(255),
                channel_title VARCHAR(255),
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS statistics (
                date DATE PRIMARY KEY,
                new_users INTEGER DEFAULT 0,
                total_users INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

def add_user(user_id, username, first_name, last_name):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute('SELECT user_id FROM users WHERE user_id = %s', (user_id,))
        existing_user = cursor.fetchone()
        
        if not existing_user:
            cursor.execute(
                'INSERT INTO users (user_id, username, first_name, last_name) VALUES (%s, %s, %s, %s)',
                (user_id, username, first_name, last_name)
            )
            today = date.today()
            cursor.execute('SELECT date FROM statistics WHERE date = %s', (today,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO statistics (date, new_users, total_users) VALUES (%s, 1, 1)', (today,))
            else:
                cursor.execute('UPDATE statistics SET new_users = new_users + 1, total_users = total_users + 1 WHERE date = %s', (today,))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Add user error: {e}")

def add_video_code(code, message_id, description):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO video_codes (code, message_id, description) VALUES (%s, %s, %s)',
            (code, message_id, description)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Add video code error: {e}")
        return False

def get_message_id_by_code(code):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('SELECT message_id, description FROM video_codes WHERE code = %s', (code,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Get message_id error: {e}")
        return None

def get_all_channels():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('SELECT channel_id, channel_username, channel_title FROM channels')
        channels = cursor.fetchall()
        cursor.close()
        conn.close()
        return channels
    except Exception as e:
        logger.error(f"Get channels error: {e}")
        return []

def add_channel(channel_id, channel_username, channel_title):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO channels (channel_id, channel_username, channel_title) VALUES (%s, %s, %s)',
            (channel_id, channel_username, channel_title)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Add channel error: {e}")
        return False

def remove_channel(channel_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM channels WHERE channel_id = %s', (channel_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Remove channel error: {e}")
        return False

def get_user_stats():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE joined_date = %s', (date.today(),))
        today_users = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return total_users, today_users
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        return 0, 0

def get_all_users():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE is_active = TRUE')
        users = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return users
    except Exception as e:
        logger.error(f"Get all users error: {e}")
        return []

# Maxfiy kanaldan videoni copy qilish
async def send_video_from_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    try:
        result = get_message_id_by_code(code)
        if not result:
            await update.message.reply_text("❌ Noto'g'ri kod yoki video topilmadi.")
            return False
        
        message_id, description = result
        
        message = await context.bot.get_message(SECRET_CHANNEL_ID, message_id)
        
        if message.video:
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=message.video.file_id,
                caption=description or message.caption,
                reply_to_message_id=update.message.message_id
            )
        elif message.document:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=message.document.file_id,
                caption=description or message.caption,
                reply_to_message_id=update.message.message_id
            )
        else:
            await update.message.reply_text("❌ Ushbu xabarda video topilmadi.")
            return False
            
        return True
        
    except BadRequest as e:
        logger.error(f"Send video error: {e}")
        await update.message.reply_text("❌ Video topilmadi yoki xatolik yuz berdi.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")
        return False

# Bot funksiyalari
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    add_user(user_id, user.username, user.first_name, user.last_name)
    
    # Faqat obuna tekshirish
    if not await check_subscription(update, context):
        return

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text.strip()
    
    # Admin commandlarni tekshirish
    if message_text.startswith('/'):
        return
    
    # Majburiy kanallarga obuna bo'lishni tekshirish
    if not await check_subscription(update, context):
        return
    
    # Video kodini tekshirish va maxfiy kanaldan videoni yuborish
    await send_video_from_channel(update, context, message_text)

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    channels = get_all_channels()
    
    if not channels:
        return True
    
    not_subscribed = []
    
    for channel_id, channel_username, channel_title in channels:
        try:
            member = await context.bot.get_chat_member(channel_id, user_id)
            if member.status in ['left', 'kicked']:
                not_subscribed.append((channel_username, channel_title))
        except Exception as e:
            logger.error(f"Check subscription error: {e}")
            not_subscribed.append((channel_username, channel_title))
    
    if not_subscribed:
        keyboard = []
        for channel_username, channel_title in not_subscribed:
            keyboard.append([InlineKeyboardButton(
                f"📢 {channel_title}", 
                url=f"https://t.me/{channel_username.lstrip('@')}"
            )])
        
        keyboard.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_subscription")])
        
        await update.message.reply_text(
            "Kechirasiz, botdan foydalanishdan oldin quyidagi kanallarga obuna boʻlishingiz kerak: !",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return False
    
    return True

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if await check_subscription(update, context):
        await query.edit_message_text("✅ Tabriklayman! Siz barcha kanallarga obuna bo'lgansiz. Endi videolarni olishingiz mumkin.")
    else:
        await query.answer("Iltimos, barcha kanallarga obuna bo'ling!", show_alert=True)

# YANGI: Qisqa admin commandlari

# /stats - Statistika
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    total_users, today_users = get_user_stats()
    await update.message.reply_text(
        f"📊 Bot Statistikalari:\n\n"
        f"👥 Jami foydalanuvchilar: {total_users}\n"
        f"📈 Bugun qo'shilganlar: {today_users}"
    )

# /message - Multimedia xabar tarqatish
async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    # Reply qilingan xabarni tekshirish
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "📢 Xabar tarqatish uchun:\n\n"
            "1. Xabaringizni yozing (matn, rasm, video)\n"
            "2. Shu xabarga /message deb reply qiling"
        )
        return
    
    users = get_all_users()
    success = 0
    failed = 0
    
    original_message = update.message.reply_to_message
    await update.message.reply_text(f"📢 Xabar {len(users)} ta foydalanuvchiga yuborilmoqda...")
    
    for user_id in users:
        try:
            # Xabar turiga qarab yuborish
            if original_message.text:
                await context.bot.send_message(
                    chat_id=user_id, 
                    text=original_message.text,
                    entities=original_message.entities
                )
            elif original_message.photo:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=original_message.photo[-1].file_id,
                    caption=original_message.caption,
                    caption_entities=original_message.caption_entities
                )
            elif original_message.video:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=original_message.video.file_id,
                    caption=original_message.caption,
                    caption_entities=original_message.caption_entities
                )
            elif original_message.document:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=original_message.document.file_id,
                    caption=original_message.caption,
                    caption_entities=original_message.caption_entities
                )
            elif original_message.audio:
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=original_message.audio.file_id,
                    caption=original_message.caption,
                    caption_entities=original_message.caption_entities
                )
            else:
                # Agar boshqa tur bo'lsa, forward qilamiz
                await context.bot.forward_message(
                    chat_id=user_id,
                    from_chat_id=original_message.chat_id,
                    message_id=original_message.message_id
                )
            
            success += 1
        except Exception as e:
            failed += 1
            logger.error(f"Broadcast error for user {user_id}: {e}")
        
        await asyncio.sleep(0.1)
    
    await update.message.reply_text(
        f"📊 Xabar tarqatish natijasi:\n\n"
        f"✅ Muvaffaqiyatli: {success}\n"
        f"❌ Xatolik: {failed}"
    )

# /addchannel - Kanal qo'shish
async def addchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("❌ Kanal username kiriting: /addchannel @username")
        return
    
    channel_username = context.args[0].lstrip('@')
    try:
        chat = await context.bot.get_chat(f"@{channel_username}")
        if add_channel(str(chat.id), channel_username, chat.title):
            await update.message.reply_text(f"✅ Kanal qo'shildi: {chat.title}")
        else:
            await update.message.reply_text("❌ Kanal qo'shishda xatolik!")
    except Exception as e:
        await update.message.reply_text(f"❌ Kanal topilmadi: {e}")

# /delchannel - Kanal o'chirish
async def delchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    if not context.args:
        await update.message.reply_text("❌ Kanal username kiriting: /delchannel @username")
        return
    
    channel_username = context.args[0].lstrip('@')
    channels = get_all_channels()
    
    for channel_id, username, title in channels:
        if username == channel_username:
            if remove_channel(channel_id):
                await update.message.reply_text(f"✅ Kanal o'chirildi: {title}")
                return
            else:
                await update.message.reply_text("❌ Kanal o'chirishda xatolik!")
                return
    
    await update.message.reply_text("❌ Kanal topilmadi!")

# /listchannel - Kanallar ro'yxati
async def listchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    channels = get_all_channels()
    if not channels:
        await update.message.reply_text("📺 Kanallar yo'q")
        return
    
    text = "📺 Majburiy kanallar:\n\n"
    for i, (channel_id, channel_username, channel_title) in enumerate(channels, 1):
        text += f"{i}. {channel_title} (@{channel_username})\n"
    
    await update.message.reply_text(text)

# /addvideo - Video kod qo'shish
async def addvideo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Format: /addvideo kod message_id [tavsif]")
        return
    
    code = context.args[0]
    try:
        message_id = int(context.args[1])
        description = ' '.join(context.args[2:]) if len(context.args) > 2 else ""
        
        if add_video_code(code, message_id, description):
            await update.message.reply_text(
                f"✅ Video qo'shildi!\n"
                f"Kod: {code}\n"
                f"Message ID: {message_id}\n"
                f"Tavsif: {description}"
            )
        else:
            await update.message.reply_text("❌ Video qo'shishda xatolik!")
    except ValueError:
        await update.message.reply_text("❌ Message ID raqam bo'lishi kerak!")

# Flask route lar
@app.route('/')
def home():
    return "Bot ishlamoqda!"

@app.route('/webhook', methods=['POST'])
def webhook():
    return "OK"

# Asosiy funksiya
def main():
    init_db()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handler lar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("message", message))
    application.add_handler(CommandHandler("addchannel", addchannel))
    application.add_handler(CommandHandler("delchannel", delchannel))
    application.add_handler(CommandHandler("listchannel", listchannel))
    application.add_handler(CommandHandler("addvideo", addvideo))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="check_subscription"))
    
    # Flask server ishga tushirish
    from threading import Thread
    def run_flask():
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
    
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    logger.info("Bot ishga tushmoqda...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
