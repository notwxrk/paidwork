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
        
        # Users jadvali
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
        
        # Video kodlari jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_codes (
                code VARCHAR(50) PRIMARY KEY,
                message_id INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Majburiy kanallar jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id VARCHAR(100) PRIMARY KEY,
                channel_username VARCHAR(255),
                channel_title VARCHAR(255),
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Statistics jadvali
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

# YANGI: Maxfiy kanaldan videoni copy qilish (forward emas)
async def send_video_from_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    try:
        # Database dan message_id ni olish
        result = get_message_id_by_code(code)
        if not result:
            await update.message.reply_text("❌ Noto'g'ri kod yoki video topilmadi.")
            return False
        
        message_id, description = result
        
        # Maxfiy kanaldan message ni olish
        message = await context.bot.get_message(SECRET_CHANNEL_ID, message_id)
        
        # Videoni copy qilish (forward emas)
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
    
    if not await check_subscription(update, context):
        return
    
    await update.message.reply_text(
        f"Salom {user.first_name}! 👋\n\n"
        f"Video kodini yuboring va men sizga maxfiy kanaldan videoni jo'nataman.\n\n"
        f"Masalan: 111"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message_text = update.message.text.strip()
    
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
        await query.edit_message_text("✅ Tabriklayman! Siz barcha kanallarga obuna bo'lgansiz. Botdan foydalanishingiz mumkin.")
    else:
        await query.answer("Iltimos, barcha kanallarga obuna bo'ling!", show_alert=True)

# Admin panel
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")],
        [InlineKeyboardButton("📢 Xabar tarqatish", callback_data="broadcast")],
        [InlineKeyboardButton("📺 Kanallar boshqaruvi", callback_data="manage_channels")],
        [InlineKeyboardButton("🎥 Video kod qo'shish", callback_data="add_video_code")]
    ]
    
    await update.message.reply_text(
        "👨‍💻 Admin Panel",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "stats":
        total_users, today_users = get_user_stats()
        await query.edit_message_text(
            f"📊 Bot Statistikalari:\n\n"
            f"👥 Jami foydalanuvchilar: {total_users}\n"
            f"📈 Bugun qo'shilganlar: {today_users}"
        )
    
    elif data == "broadcast":
        context.user_data['waiting_for_broadcast'] = True
        await query.edit_message_text(
            "📢 Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:"
        )
    
    elif data == "manage_channels":
        channels = get_all_channels()
        if not channels:
            text = "📺 Hozircha kanallar mavjud emas."
        else:
            text = "📺 Majburiy kanallar ro'yxati:\n\n"
            for i, (channel_id, channel_username, channel_title) in enumerate(channels, 1):
                text += f"{i}. {channel_title} (@{channel_username})\n"
        
        keyboard = [
            [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")],
            [InlineKeyboardButton("➖ Kanal o'chirish", callback_data="remove_channel")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "add_video_code":
        context.user_data['waiting_for_video_code'] = True
        await query.edit_message_text(
            "🎥 Video kodini va message_id ni kiriting:\n\n"
            "Format: `kod message_id [tavsif]`\n"
            "Masalan: `111 245 Bu mening birinchi videom`\n\n"
            "Message ID ni olish uchun: @RawDataBot dan foydalaning yoki kanaldagi xabarni forward qiling."
        )
    
    elif data == "add_channel":
        context.user_data['waiting_for_channel'] = True
        await query.edit_message_text(
            "📺 Yangi kanal qo'shish uchun kanal username ni kiriting (masalan: @channel_username):"
        )
    
    elif data == "remove_channel":
        channels = get_all_channels()
        if not channels:
            await query.edit_message_text("❌ O'chirish uchun kanal mavjud emas!")
            return
        
        keyboard = []
        for channel_id, channel_username, channel_title in channels:
            keyboard.append([InlineKeyboardButton(
                f"❌ {channel_title}", 
                callback_data=f"remove_{channel_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="manage_channels")])
        
        await query.edit_message_text(
            "O'chirmoqchi bo'lgan kanalni tanlang:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("remove_"):
        channel_id = data.replace("remove_", "")
        if remove_channel(channel_id):
            await query.edit_message_text("✅ Kanal muvaffaqiyatli o'chirildi!")
        else:
            await query.edit_message_text("❌ Kanal o'chirishda xatolik!")
    
    elif data == "back_to_main":
        await admin_panel(update, context)

async def handle_admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    
    message_text = update.message.text
    
    if context.user_data.get('waiting_for_broadcast'):
        del context.user_data['waiting_for_broadcast']
        users = get_all_users()
        success = 0
        failed = 0
        
        await update.message.reply_text(f"📢 Xabar {len(users)} ta foydalanuvchiga yuborilmoqda...")
        
        for user_id in users:
            try:
                await context.bot.send_message(chat_id=user_id, text=message_text)
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
    
    elif context.user_data.get('waiting_for_video_code'):
        parts = message_text.split(' ', 2)
        if len(parts) >= 2:
            code = parts[0]
            try:
                message_id = int(parts[1])
                description = parts[2] if len(parts) > 2 else ""
                
                if add_video_code(code, message_id, description):
                    await update.message.reply_text(
                        f"✅ Video kodi muvaffaqiyatli qo'shildi!\n\n"
                        f"Kod: {code}\n"
                        f"Message ID: {message_id}\n"
                        f"Tavsif: {description}"
                    )
                else:
                    await update.message.reply_text("❌ Video kodini qo'shishda xatolik!")
            except ValueError:
                await update.message.reply_text("❌ Message ID raqam bo'lishi kerak!")
        else:
            await update.message.reply_text(
                "❌ Noto'g'ri format!\n\n"
                "To'g'ri format: kod message_id [tavsif]\n"
                "Masalan: 111 245 Video tavsifi"
            )
        
        context.user_data['waiting_for_video_code'] = False
    
    elif context.user_data.get('waiting_for_channel'):
        channel_username = message_text.lstrip('@')
        try:
            chat = await context.bot.get_chat(f"@{channel_username}")
            if add_channel(str(chat.id), channel_username, chat.title):
                await update.message.reply_text(f"✅ Kanal muvaffaqiyatli qo'shildi: {chat.title}")
            else:
                await update.message.reply_text("❌ Kanal qo'shishda xatolik!")
        except Exception as e:
            await update.message.reply_text(f"❌ Kanal topilmadi yoki xatolik yuz berdi: {e}")
        context.user_data['waiting_for_channel'] = False

# Flask route lar
@app.route('/')
def home():
    return "Bot ishlamoqda!"

@app.route('/webhook', methods=['POST'])
def webhook():
    return "OK"

# Asosiy funksiya
def main():
    # Database ni ishga tushirish
    init_db()
    
    # Bot application yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handler lar
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="check_subscription"))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(stats|broadcast|manage_channels|add_video_code|add_channel|remove_channel|back_to_main|remove_.*)$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_actions))
    
    # Flask server ishga tushirish (Render uchun)
    from threading import Thread
    def run_flask():
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
    
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Bot ishga tushirish (polling)
    logger.info("Bot ishga tushmoqda...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
