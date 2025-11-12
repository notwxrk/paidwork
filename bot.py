import os
import logging
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal

import aiohttp
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes, 
    MessageHandler, 
    filters,
    CallbackQueryHandler,
    ConversationHandler
)
import asyncpg
from PIL import Image, ImageDraw, ImageFont
import io
from flask import Flask, render_template_string

# Log konfiguratsiyasi
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask app for uptimerobot
app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string("Bot is running!")

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Database configuration
DATABASE_URL = "postgresql://mytaxi_user:oq0x7wzTfgKRRmc9k1PAkF1KxrNqxSNC@dpg-d49un63ipnbc739a95b0-a/mytaxi"

# Bot configuration
BOT_TOKEN = "8526778595:AAGP5ZINtNu6M2vYiZt2onz6bFRostthM8k"
ADMIN_ID = 7431672482
CHANNEL_USERNAME = "@gootaksi"
GROUP_USERNAME = "@gootaksi_chat"

# Conversation states
CAPTCHA, CHECK_SUBSCRIPTION, MENU, BUY_CAR, FILL_BALANCE, WITHDRAW_AMOUNT, WITHDRAW_CARD, SUPPORT, TASKS, TASK_CONFIRMATION = range(10)

# Car data
CARS = {
    "tico": {
        "name": "Tico",
        "daily_income": 5000,
        "duration": 100,
        "total_income": 500000,
        "price": 25000,
        "image": "https://i.ibb.co/bgjr7xNW/20251111-131622.png"
    },
    "damas": {
        "name": "Damas", 
        "daily_income": 10000,
        "duration": 100,
        "total_income": 1000000,
        "price": 75000,
        "image": "https://i.ibb.co/Xf3JgpGS/20251111-131901.png"
    },
    "nexia": {
        "name": "Nexia",
        "daily_income": 20000,
        "duration": 100,
        "total_income": 2000000,
        "price": 150000,
        "image": "https://i.ibb.co/tTVdQ70c/20251111-132004.png"
    },
    "cobalt": {
        "name": "Cobalt",
        "daily_income": 30000,
        "duration": 100,
        "total_income": 3000000,
        "price": 300000,
        "image": "https://i.ibb.co/3ywTRf7R/20251111-132135.png"
    },
    "gentra": {
        "name": "Gentra",
        "daily_income": 40000,
        "duration": 100,
        "total_income": 4000000,
        "price": 400000,
        "image": "https://i.ibb.co/9mc1RWkB/20251111-132318.png"
    },
    "malibu": {
        "name": "Malibu",
        "daily_income": 50000,
        "duration": 100,
        "total_income": 5000000,
        "price": 500000,
        "image": "https://i.ibb.co/Lzz0shFS/20251111-132601.png"
    }
}

# Database setup
async def init_db():
    logger.info("Database connection initialized")
    return await asyncpg.connect(DATABASE_URL)

async def create_tables():
    conn = await init_db()
    try:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                phone_number VARCHAR(20),
                balance DECIMAL DEFAULT 0,
                total_earned DECIMAL DEFAULT 0,
                referred_by BIGINT,
                created_at TIMESTAMP DEFAULT NOW(),
                last_bonus TIMESTAMP,
                last_income TIMESTAMP,
                is_banned BOOLEAN DEFAULT FALSE,
                referral_bonus_earned DECIMAL DEFAULT 0
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_cars (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                car_type VARCHAR(50),
                purchase_date TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                last_income_date TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount DECIMAL,
                type VARCHAR(20),
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW(),
                card_number VARCHAR(50),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT,
                referred_id BIGINT,
                bonus_paid BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (referrer_id) REFERENCES users(user_id),
                FOREIGN KEY (referred_id) REFERENCES users(user_id)
            )
        ''')
        
        # YANGI: Vazifalar jadvali
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255),
                description TEXT,
                reward DECIMAL,
                task_limit INTEGER,
                completed_count INTEGER DEFAULT 0,
                task_url VARCHAR(500),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                created_by BIGINT
            )
        ''')
        
        # YANGI: User vazifa jadvali
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_tasks (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                task_id INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                screenshot_url VARCHAR(500),
                submitted_at TIMESTAMP DEFAULT NOW(),
                approved_at TIMESTAMP,
                approved_by BIGINT,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        ''')
        
        # YANGI: Majburiy kanallar jadvali
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS required_channels (
                id SERIAL PRIMARY KEY,
                channel_username VARCHAR(100),
                channel_name VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                added_by BIGINT,
                added_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # YANGI: Adminlar jadvali
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                added_by BIGINT,
                added_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
    finally:
        await conn.close()

# User management
async def get_user(user_id: int) -> Optional[dict]:
    conn = await init_db()
    try:
        user = await conn.fetchrow(
            'SELECT * FROM users WHERE user_id = $1', user_id
        )
        logger.info(f"User data retrieved for user_id: {user_id}")
        return dict(user) if user else None
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None
    finally:
        await conn.close()

# YANGI: Admin tekshirish
async def is_admin(user_id: int) -> bool:
    conn = await init_db()
    try:
        admin = await conn.fetchrow(
            'SELECT * FROM admins WHERE user_id = $1', user_id
        )
        return admin is not None or user_id == ADMIN_ID
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False
    finally:
        await conn.close()

# YANGI: Majburiy kanallarni olish
async def get_required_channels():
    conn = await init_db()
    try:
        channels = await conn.fetch(
            'SELECT * FROM required_channels WHERE is_active = TRUE'
        )
        return [dict(channel) for channel in channels]
    except Exception as e:
        logger.error(f"Error getting required channels: {e}")
        return []
    finally:
        await conn.close()

# YANGI: Kanal va guruh a'zoligini tekshirish
async def check_channel_and_group_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        required_channels = await get_required_channels()
        
        for channel in required_channels:
            try:
                channel_member = await context.bot.get_chat_member(channel['channel_username'], user_id)
                if channel_member.status not in ['member', 'administrator', 'creator']:
                    return False
            except Exception as e:
                logger.error(f"Error checking channel membership for {channel['channel_username']}: {e}")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Error checking membership for {user_id}: {e}")
        return False

# YANGI: Majburiy obuna tekshiruvi
async def check_subscription_required(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    return not await check_channel_and_group_membership(user_id, context)

# YANGI: Referal bonus berish funksiyasi (Kunlik bonus olganda)
async def give_referral_bonus(referred_id: int, context: ContextTypes.DEFAULT_TYPE):
    conn = await init_db()
    try:
        # Referalni topamiz
        referral = await conn.fetchrow(
            'SELECT * FROM referrals WHERE referred_id = $1 AND bonus_paid = FALSE',
            referred_id
        )
        
        if not referral:
            return
        
        referrer_id = referral['referrer_id']
        
        # 500 so'm bonus
        await conn.execute(
            'UPDATE users SET balance = balance + 500, referral_bonus_earned = referral_bonus_earned + 500 WHERE user_id = $1',
            referrer_id
        )
        
        await conn.execute(
            'UPDATE referrals SET bonus_paid = TRUE WHERE id = $1',
            referral['id']
        )
        
        # Foydalanuvchiga xabar
        try:
            await context.bot.send_message(
                referrer_id,
                "🎉 Tabriklaymiz! Sizning taklif do'stingiz kunlik bonus oldi!\n\n"
                "💰 +500 so'm bonus qo'shildi!\n"
                "👥 Do'stingiz botdan foydalanyapti!"
            )
        except Exception as e:
            logger.error(f"Error sending bonus message to {referrer_id}: {e}")
        
        logger.info(f"Referral bonus paid: {referrer_id} -> {referred_id}: 500 so'm")
        
    except Exception as e:
        logger.error(f"Error giving referral bonus: {e}")
    finally:
        await conn.close()

async def create_user(user_id: int, referred_by: int = None):
    conn = await init_db()
    try:
        await conn.execute(
            'INSERT INTO users (user_id, referred_by) VALUES ($1, $2)',
            user_id, referred_by
        )
        
        # Referalni qayd etamiz (bonus keyin beriladi)
        if referred_by:
            await conn.execute(
                'INSERT INTO referrals (referrer_id, referred_id, bonus_paid) VALUES ($1, $2, $3)',
                referred_by, user_id, False
            )
        
        logger.info(f"New user created: {user_id}")
    except Exception as e:
        logger.error(f"Error creating user {user_id}: {e}")
    finally:
        await conn.close()

async def update_balance(user_id: int, amount: float):
    conn = await init_db()
    try:
        await conn.execute(
            'UPDATE users SET balance = balance + $1 WHERE user_id = $2',
            amount, user_id
        )
        logger.info(f"Balance updated for user {user_id}: {amount}")
    except Exception as e:
        logger.error(f"Error updating balance for user {user_id}: {e}")
    finally:
        await conn.close()

# Car management
async def get_user_cars(user_id: int) -> List[dict]:
    conn = await init_db()
    try:
        cars = await conn.fetch(
            'SELECT * FROM user_cars WHERE user_id = $1 AND is_active = TRUE',
            user_id
        )
        logger.info(f"Retrieved {len(cars)} cars for user {user_id}")
        return [dict(car) for car in cars]
    except Exception as e:
        logger.error(f"Error getting cars for user {user_id}: {e}")
        return []
    finally:
        await conn.close()

async def buy_car(user_id: int, car_type: str):
    car = CARS[car_type]
    conn = await init_db()
    try:
        # Check balance - To'liq tekshirish
        user = await get_user(user_id)
        if float(user['balance']) < car['price']:
            logger.warning(f"Insufficient balance for user {user_id}: {user['balance']} < {car['price']}")
            return False, "Not enough balance"
        
        # Balansni to'g'ri ayiramiz
        await conn.execute(
            'UPDATE users SET balance = balance - $1 WHERE user_id = $2',
            car['price'], user_id
        )
        
        expires_at = datetime.now() + timedelta(days=car['duration'])
        await conn.execute(
            'INSERT INTO user_cars (user_id, car_type, expires_at, last_income_date) VALUES ($1, $2, $3, $4)',
            user_id, car_type, expires_at, datetime.now()
        )
        
        logger.info(f"Car purchased: {car_type} for user {user_id}")
        return True, "Car purchased successfully"
    except Exception as e:
        logger.error(f"Error buying car for user {user_id}: {e}")
        return False, "Error purchasing car"
    finally:
        await conn.close()

# YANGI: Daromadni hisoblash funksiyasi (24 soatdan keyin)
async def calculate_and_update_income(user_id: int):
    """Mashinalardan avtomatik daromadni hisoblaydi (24 soatdan keyin)"""
    conn = await init_db()
    try:
        # Barcha mashinalarni olamiz
        cars = await conn.fetch(
            '''SELECT * FROM user_cars 
               WHERE user_id = $1 AND is_active = TRUE 
               AND expires_at > NOW()''',
            user_id
        )
        
        total_income = 0
        car_details = []
        notifications = []
        
        for car in cars:
            car_data = CARS[car['car_type']]
            
            # 24 soat o'tganini tekshiramiz
            if car['last_income_date'] and (datetime.now() - car['last_income_date']).total_seconds() >= 86400:
                # Kunlik daromadni hisoblaymiz
                daily_income = car_data['daily_income']
                total_income += daily_income
                
                # last_income_date ni yangilaymiz
                await conn.execute(
                    'UPDATE user_cars SET last_income_date = NOW() WHERE id = $1',
                    car['id']
                )
                notifications.append(f"🎉 {car_data['name']} dan: {daily_income:,.0f} so'm")
            
            # Qolgan vaqtni hisoblaymiz
            time_left = car['expires_at'] - datetime.now()
            days_left = time_left.days
            hours_left = time_left.seconds // 3600
            
            # Keyingi daromad vaqtini hisoblaymiz
            next_income_time = car['last_income_date'] + timedelta(hours=24) if car['last_income_date'] else datetime.now() + timedelta(hours=24)
            time_until_next_income = next_income_time - datetime.now()
            
            if time_until_next_income.total_seconds() > 0:
                hours_until = int(time_until_next_income.total_seconds() // 3600)
                minutes_until = int((time_until_next_income.total_seconds() % 3600) // 60)
                next_income_str = f"{hours_until} soat {minutes_until} daqiqa"
            else:
                next_income_str = "Hozir"
            
            car_details.append({
                'name': car_data['name'],
                'daily_income': car_data['daily_income'],
                'days_left': days_left,
                'hours_left': hours_left,
                'next_income': next_income_str
            })
        
        # Agar daromad bo'lsa, balansga qo'shamiz
        if total_income > 0:
            await conn.execute(
                'UPDATE users SET balance = balance + $1, total_earned = total_earned + $1 WHERE user_id = $2',
                total_income, user_id
            )
            
            logger.info(f"Auto income updated for user {user_id}: {total_income}")
        
        # Keyingi daromad vaqtini hisoblaymiz
        next_income_time = None
        for car in cars:
            if car['last_income_date']:
                car_next_income = car['last_income_date'] + timedelta(hours=24)
                if next_income_time is None or car_next_income < next_income_time:
                    next_income_time = car_next_income
        
        return total_income, car_details, notifications, next_income_time
        
    except Exception as e:
        logger.error(f"Error calculating income for user {user_id}: {e}")
        return 0, [], [], None
    finally:
        await conn.close()

# YANGI: Captcha generatsiya qilish
def generate_captcha():
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    answer = num1 + num2
    question = f"{num1} + {num2} = ?"
    return question, answer

# Start command - YANGI: CAPTCHA BILAN BOSHLANADI
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Start command received from user {user_id}")
    
    # Check if user is banned
    user = await get_user(user_id)
    if user and user.get('is_banned'):
        await update.message.reply_text("❌ Siz bloklangansiz! Admin bilan bog'laning.")
        return ConversationHandler.END
    
    # Check referral
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            logger.info(f"Referral detected: {referred_by} -> {user_id}")
        except:
            pass
    
    # Agar user mavjud bo'lsa, kanal tekshirish
    if user:
        if await check_subscription_required(user_id, context):
            await ask_for_subscription(update, context)
            return CHECK_SUBSCRIPTION
        else:
            await show_main_menu(update, context)
            return MENU
    
    # Agar user mavjud bo'lmasa, captcha so'rash
    question, answer = generate_captcha()
    context.user_data['captcha_answer'] = answer
    context.user_data['referred_by'] = referred_by
    
    await update.message.reply_text(
        f"Assalomu alaykum! Goo Taksi botiga xush kelibsiz!\n\n"
        f"Botdan foydalanish uchun quyidagi savolga javob bering:\n\n"
        f"🔒 {question}"
    )
    
    logger.info(f"User {user_id} not registered, asking captcha: {question}")
    return CAPTCHA

# YANGI: Captcha tekshirish
async def handle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_answer = update.message.text.strip()
    
    try:
        correct_answer = str(context.user_data['captcha_answer'])
        
        if user_answer == correct_answer:
            referred_by = context.user_data.get('referred_by')
            await create_user(user_id, referred_by)
            
            await update.message.reply_text(
                "✅ Captcha muvaffaqiyatli topshirildi!\n\n"
                "Endi botdan to'liq foydalanish uchun quyidagi kanallarga a'zo bo'ling:"
            )
            
            # Kanal tekshirish
            await ask_for_subscription(update, context)
            return CHECK_SUBSCRIPTION
        else:
            # Yangi captcha generatsiya qilish
            question, answer = generate_captcha()
            context.user_data['captcha_answer'] = answer
            
            await update.message.reply_text(
                f"❌ Noto'g'ri javob! Iltimos, qaytadan urinib ko'ring:\n\n"
                f"🔒 {question}"
            )
            return CAPTCHA
            
    except Exception as e:
        logger.error(f"Error handling captcha for user {user_id}: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi. Iltimos, /start ni bosing.")
        return ConversationHandler.END

# YANGI: Kanalga a'zo bo'lishni so'rash funksiyasi
async def ask_for_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    required_channels = await get_required_channels()
    
    if not required_channels:
        # Agar kanal yo'q bo'lsa, to'g'ridan-to'g'ri menyuga o'tkazish
        await show_main_menu(update, context)
        return MENU
    
    keyboard = []
    for channel in required_channels:
        keyboard.append([InlineKeyboardButton(f"📢 {channel['channel_name']}", url=f"https://t.me/{channel['channel_username'][1:]}")])
    
    keyboard.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_membership")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    channel_list = "\n".join([f"📢 {channel['channel_name']}" for channel in required_channels])
    
    if update.message:
        await update.message.reply_text(
            f"❌ Kechirasiz, botimizdan foydalanish uchun ushbu kanallarga obuna bo'lishingiz kerak:\n\n"
            f"{channel_list}\n\n"
            f"Iltimos, kanallarga a'zo bo'ling va 'Tekshirish' tugmasini bosing.",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.edit_message_text(
            f"❌ Kechirasiz, botimizdan foydalanish uchun ushbu kanallarga obuna bo'lishingiz kerak:\n\n"
            f"{channel_list}\n\n"
            f"Iltimos, kanallarga a'zo bo'ling va 'Tekshirish' tugmasini bosing.",
            reply_markup=reply_markup
        )

async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logger.info(f"Membership check callback from user {user_id}")
    
    if await check_channel_and_group_membership(user_id, context):
        await query.edit_message_text("✅ Siz barcha kanallarga a'zo bo'lgansiz! Endi botdan to'liq foydalanishingiz mumkin.")
        await show_main_menu(update, context)
        return MENU
    else:
        await query.answer("Siz hali barcha kanallarga a'zo bo'lmagansiz!", show_alert=True)
        logger.info(f"User {user_id} failed channel check")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # YANGI: Har doim kanal a'zoligini tekshirish
    if await check_subscription_required(user_id, context):
        await ask_for_subscription(update, context)
        return CHECK_SUBSCRIPTION
    
    user = await get_user(user_id)
    
    # Avtomatik daromadni hisoblaymiz (24 soatdan keyin)
    daily_income, car_details, notifications, next_income_time = await calculate_and_update_income(user_id)
    
    # Referral count
    conn = await init_db()
    try:
        referrals_count = await conn.fetchval(
            'SELECT COUNT(*) FROM referrals WHERE referrer_id = $1', user_id
        )
    except Exception as e:
        logger.error(f"Error getting referral data for user {user_id}: {e}")
        referrals_count = 0
    finally:
        await conn.close()
    
    keyboard = [
        ["🚖 Mashinalar", "🚘 Mening Mashinam"],
        ["💸 Hisobim", "📥 Hisobni To'ldirish"],
        ["👥 Referal", "🎁 Kunlik bonus"],
        ["⚡️ Vazifalar", "💬 Qo'llab Quvvatlash"]  # YANGI: Vazifalar knopkasi
    ]
    
    text = (
        f"🏠 Asosiy menyu\n\n"
        f"💰 Balans: {user['balance']:,.0f} so'm\n"
        f"📈 Kunlik daromad: {daily_income:,.0f} so'm\n"
        f"👥 Referallar: {referrals_count} ta"
    )
    
    # Notifikatsiyalarni qo'shamiz
    if notifications:
        text += f"\n\n{' '.join(notifications)}"
    
    # Keyingi daromad vaqtini ko'rsatamiz
    if next_income_time:
        time_left = next_income_time - datetime.now()
        if time_left.total_seconds() > 0:
            hours_left = int(time_left.total_seconds() // 3600)
            minutes_left = int((time_left.total_seconds() % 3600) // 60)
            text += f"\n\n⏰ Keyingi daromad: {hours_left} soat {minutes_left} daqiqadan keyin"
    
    # Mashinalar vaqt qoldig'ini ko'rsatamiz
    if car_details:
        text += f"\n\n⏰ Mashinalar holati:"
        for car in car_details:
            text += f"\n🚗 {car['name']}: {car['days_left']} kun {car['hours_left']} soat qoldi"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    
    logger.info(f"Main menu shown for user {user_id}")

# YANGI: Har bir command uchun obuna tekshirish decorator
def check_subscription(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        # Check if user is banned
        user = await get_user(user_id)
        if user and user.get('is_banned'):
            await update.message.reply_text("❌ Siz bloklangansiz! Admin bilan bog'laning.")
            return ConversationHandler.END
        
        if await check_subscription_required(user_id, context):
            await ask_for_subscription(update, context)
            return CHECK_SUBSCRIPTION
        return await func(update, context)
    return wrapper

# ==================== VAZIFALAR BO'LIMI ====================

# YANGI: Vazifalar menyusi
@check_subscription
async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Tasks menu requested by user {user_id}")
    
    conn = await init_db()
    try:
        # Faol vazifalarni olish
        tasks = await conn.fetch(
            'SELECT * FROM tasks WHERE is_active = TRUE AND (task_limit IS NULL OR completed_count < task_limit)'
        )
        
        if not tasks:
            await update.message.reply_text("📭 Hozircha aktiv vazifalar mavjud emas")
            return
        
        text = "⚡️ Mavjud Vazifalar:\n\n"
        keyboard = []
        
        for task in tasks:
            task_dict = dict(task)
            # User bu vazifani bajarganmi tekshiramiz
            user_task = await conn.fetchrow(
                'SELECT * FROM user_tasks WHERE user_id = $1 AND task_id = $2',
                user_id, task_dict['id']
            )
            
            status = "✅ Bajarilgan" if user_task and user_task['status'] == 'approved' else "🔄 Jarayonda" if user_task else "🆕 Yangi"
            
            text += (
                f"📝 {task_dict['title']}\n"
                f"💰 Mukofot: {task_dict['reward']:,.0f} so'm\n"
                f"📊 Holat: {status}\n"
                f"🔗 Havola: {task_dict['task_url']}\n\n"
            )
            
            if not user_task or user_task['status'] != 'approved':
                keyboard.append([InlineKeyboardButton(f"📝 {task_dict['title']}", callback_data=f"task_{task_dict['id']}")])
        
        if not keyboard:
            await update.message.reply_text("📭 Siz barcha vazifalarni bajarib bo'lgansiz!")
            return
        
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")])
        
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            
    except Exception as e:
        logger.error(f"Error showing tasks for user {user_id}: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi")
    finally:
        await conn.close()

# YANGI: Vazifa bajarish
@check_subscription
async def start_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    task_id = int(query.data.split('_')[1])
    
    conn = await init_db()
    try:
        # Vazifani olish
        task = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)
        if not task:
            await query.answer("❌ Vazifa topilmadi", show_alert=True)
            return
        
        task_dict = dict(task)
        
        # User bu vazifani bajarganmi tekshiramiz
        user_task = await conn.fetchrow(
            'SELECT * FROM user_tasks WHERE user_id = $1 AND task_id = $2',
            user_id, task_id
        )
        
        if user_task and user_task['status'] == 'approved':
            await query.answer("❌ Siz bu vazifani allaqachon bajarib bo'lgansiz", show_alert=True)
            return
        
        # Agar oldin boshlagan bo'lsa, holatni ko'rsatamiz
        if user_task and user_task['status'] == 'pending':
            await query.answer("🔄 Siz bu vazifani tasdiqlashni kutayapsiz", show_alert=True)
            return
        
        # Yangi vazifa boshlash
        await conn.execute(
            'INSERT INTO user_tasks (user_id, task_id, status) VALUES ($1, $2, $3)',
            user_id, task_id, 'pending'
        )
        
        text = (
            f"📝 Vazifa: {task_dict['title']}\n\n"
            f"📋 Tavsif: {task_dict['description']}\n"
            f"💰 Mukofot: {task_dict['reward']:,.0f} so'm\n\n"
            f"🔗 Havola: {task_dict['task_url']}\n\n"
            f"Vazifani bajarib bo'lganingizdan so'ng, screenshot yuboring va '📃 Tasdiqlash' tugmasini bosing."
        )
        
        keyboard = [
            [InlineKeyboardButton("🔗 Havolaga o'tish", url=task_dict['task_url'])],
            [InlineKeyboardButton("📃 Tasdiqlash", callback_data=f"confirm_task_{task_id}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_tasks")]
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Error starting task for user {user_id}: {e}")
        await query.answer("❌ Xatolik yuz berdi", show_alert=True)
    finally:
        await conn.close()

# YANGI: Vazifa tasdiqlash
@check_subscription
async def confirm_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    task_id = int(query.data.split('_')[2])
    
    context.user_data['current_task_id'] = task_id
    
    await query.edit_message_text(
        "📸 Iltimos, vazifa bajarilganligini tasdiqlovchi screenshot yuboring:\n\n"
        "⚠️ Eslatma: Screenshot aniq va tushunarli bo'lishi kerak!"
    )
    
    return TASK_CONFIRMATION

# YANGI: Screenshot qabul qilish
@check_subscription
async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    task_id = context.user_data.get('current_task_id')
    
    if not task_id:
        await update.message.reply_text("❌ Xatolik: Vazifa topilmadi")
        await show_main_menu(update, context)
        return MENU
    
    conn = await init_db()
    try:
        # Screenshotni saqlaymiz (faqat file_id ni saqlaymiz)
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.document:
            file_id = update.message.document.file_id
        else:
            await update.message.reply_text("❌ Iltimos, rasm yuboring!")
            return TASK_CONFIRMATION
        
        # User taskni yangilaymiz
        await conn.execute(
            'UPDATE user_tasks SET screenshot_url = $1 WHERE user_id = $2 AND task_id = $3',
            file_id, user_id, task_id
        )
        
        # Vazifani olish
        task = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)
        task_dict = dict(task)
        
        # Adminlarga xabar berish
        admins = await conn.fetch('SELECT user_id FROM admins')
        admin_ids = [admin['user_id'] for admin in admins] + [ADMIN_ID]
        
        for admin_id in admin_ids:
            try:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_task_{task_id}_{user_id}"),
                        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_task_{task_id}_{user_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=file_id,
                    caption=(
                        f"🔄 Yangi vazifa tasdiqlash so'rovi:\n\n"
                        f"📝 Vazifa: {task_dict['title']}\n"
                        f"👤 User ID: {user_id}\n"
                        f"💰 Mukofot: {task_dict['reward']:,.0f} so'm\n\n"
                        f"Tasdiqlaysizmi?"
                    ),
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error sending task confirmation to admin {admin_id}: {e}")
        
        await update.message.reply_text(
            "✅ Screenshot qabul qilindi! Adminlar tekshiradi va tez orada javob beradi.\n\n"
            "🔔 Eslatma: Agar screenshot noto'g'ri bo'lsa, mukofot berilmaydi!"
        )
        
        await show_main_menu(update, context)
        return MENU
        
    except Exception as e:
        logger.error(f"Error handling screenshot for user {user_id}: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi")
    finally:
        await conn.close()

# YANGI: Vazifa tasdiqlash/rad etish (admin)
async def handle_task_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    if not await is_admin(user_id):
        await query.answer("Sizda bu amalni bajarish uchun ruxsat yo'q!", show_alert=True)
        return
    
    data = query.data
    action, task_id, target_user_id = data.split('_')[1], int(data.split('_')[3]), int(data.split('_')[4])
    
    conn = await init_db()
    try:
        # Vazifani olish
        task = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)
        if not task:
            await query.answer("❌ Vazifa topilmadi!", show_alert=True)
            return
        
        task_dict = dict(task)
        
        if action == 'approve':
            # Vazifani tasdiqlaymiz
            await conn.execute(
                'UPDATE user_tasks SET status = $1, approved_at = $2, approved_by = $3 WHERE user_id = $4 AND task_id = $5',
                'approved', datetime.now(), user_id, target_user_id, task_id
            )
            
            # Mukofot beramiz
            await conn.execute(
                'UPDATE users SET balance = balance + $1 WHERE user_id = $2',
                task_dict['reward'], target_user_id
            )
            
            # Vazifa counterini yangilaymiz
            await conn.execute(
                'UPDATE tasks SET completed_count = completed_count + 1 WHERE id = $1',
                task_id
            )
            
            # Foydalanuvchiga xabar
            await context.bot.send_message(
                target_user_id,
                f"✅ Tabriklaymiz! Vazifa tasdiqlandi!\n\n"
                f"📝 {task_dict['title']}\n"
                f"💰 +{task_dict['reward']:,.0f} so'm mukofot qo'shildi!\n"
                f"💳 Yangi balans: {(await get_user(target_user_id))['balance']:,.0f} so'm"
            )
            
            await query.edit_message_text(f"✅ Vazifa tasdiqlandi! User {target_user_id} ga {task_dict['reward']:,.0f} so'm mukofot berildi.")
            
        elif action == 'reject':
            # Vazifani rad etamiz
            await conn.execute(
                'UPDATE user_tasks SET status = $1 WHERE user_id = $2 AND task_id = $3',
                'rejected', target_user_id, task_id
            )
            
            # Foydalanuvchiga xabar
            await context.bot.send_message(
                target_user_id,
                f"❌ Vazifa tasdiqlanmadi!\n\n"
                f"📝 {task_dict['title']}\n"
                f"ℹ️ Sabab: Screenshot noto'g'ri yoki aniq emas\n"
                f"🔄 Iltimos, qaytadan urinib ko'ring"
            )
            
            await query.edit_message_text(f"❌ Vazifa rad etildi! User {target_user_id} ga xabar yuborildi.")
        
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error processing task approval: {e}")
        await query.answer("❌ Xatolik yuz berdi!", show_alert=True)
    finally:
        await conn.close()

# ==================== CAR SECTION ====================

@check_subscription
async def show_cars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Show cars requested by user {update.effective_user.id}")
    keyboard = [
        [InlineKeyboardButton("Tico", callback_data="car_tico")],
        [InlineKeyboardButton("Damas", callback_data="car_damas")],
        [InlineKeyboardButton("Nexia", callback_data="car_nexia")],
        [InlineKeyboardButton("Cobalt", callback_data="car_cobalt")],
        [InlineKeyboardButton("Gentra", callback_data="car_gentra")],
        [InlineKeyboardButton("Malibu", callback_data="car_malibu")]
    ]
    
    text = (
        "🚖 Mashinalar bo'limiga xush kelibsiz!\n\n"
        "Har bir tanlagan mashinangiz sizga kunlik foyda olib keladi. Bu qanday ishlaydi ? siz mashina harid qilganingizda mashina darhol ish boshlaydi va sizga kunlik foyda olib keladi.\n"
        "Quyidagi mashinalardan birini tanlang:"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

@check_subscription
async def show_car_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    car_type = query.data.split('_')[1]
    car = CARS[car_type]
    logger.info(f"Car detail requested: {car_type} by user {query.from_user.id}")
    
    text = (
        f"🚗 {car['name']}\n\n"
        f"💰 Kunlik daromad: {car['daily_income']:,.0f} so'm\n"
        f"⏰ Ish muddati: {car['duration']} kun\n"
        f"🎯 Jami daromad: {car['total_income']:,.0f} so'm\n"
        f"💵 Narxi: {car['price']:,.0f} so'm"
    )
    
    keyboard = [
        [InlineKeyboardButton("🛒 Harid qilish", callback_data=f"buy_{car_type}")]
    ]
    
    # Send car image with caption
    await query.message.reply_photo(
        photo=car['image'],
        caption=text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await query.delete_message()

@check_subscription
async def buy_car_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    car_type = query.data.split('_')[1]
    logger.info(f"Car purchase attempted: {car_type} by user {user_id}")
    
    success, message = await buy_car(user_id, car_type)
    
    if success:
        await query.answer("✅ Mashina muvaffaqiyatli sotib olindi!", show_alert=True)
        await show_main_menu(update, context)
    else:
        await query.answer(f"❌ {message}", show_alert=True)

# ==================== BALANCE SECTION ====================

@check_subscription
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    
    # YANGI: Mashina majburiy emas
    can_withdraw = float(user['balance']) >= 20000  # YANGI: Minimal 20,000 so'm
    
    text = (
        f"💸 Hisobim\n\n"
        f"💰 Joriy balans: {user['balance']:,.0f} so'm\n"
        f"📈 Umumiy daromad: {user['total_earned']:,.0f} so'm"
    )
    
    # PUL YECHISH KNOPKASI BARCHA USERLARGA KO'RINADI
    keyboard = [[InlineKeyboardButton("💳 Pul yechish", callback_data="withdraw")]]
    
    if can_withdraw:
        text += f"\n\n💳 Minimal pul yechish: 20,000 so'm\n📉 Komissiya: 15%"
    else:
        text += f"\n\n⚠️ Pul yechish uchun balansingiz kamida 20,000 so'm bo'lishi kerak!"
    
    # Message turini tekshirish
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    logger.info(f"Balance shown for user {user_id}")

@check_subscription
async def withdraw_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user = await get_user(user_id)
    
    # YANGI: Mashina majburiy emas, faqat balans tekshiramiz
    if float(user['balance']) < 20000:  # YANGI: Minimal 20,000 so'm
        await query.answer("❌ Balansingiz 20,000 so'mdan kam!", show_alert=True)
        return
    
    text = (
        f"💳 Pul yechish\n\n"
        f"💰 Mavjud balans: {user['balance']:,.0f} so'm\n"
        f"💸 Minimal yechish: 20,000 so'm\n"  # YANGI: 20,000 so'm
        f"📉 Komissiya: 15%\n\n"
        f"Yechish uchun miqdorni kiriting (so'mda):"
    )
    
    await query.message.reply_text(text)
    await query.answer()
    logger.info(f"Withdrawal initiated by user {user_id}")
    return WITHDRAW_AMOUNT

@check_subscription
async def handle_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    
    try:
        amount = float(update.message.text)
        
        # YANGI: Mashina majburiy emas, faqat balans tekshiramiz
        
        # Tekshiramiz, minimal miqdor bormi
        if amount < 20000:  # YANGI: Minimal 20,000 so'm
            await update.message.reply_text("❌ Minimal yechish miqdori 20,000 so'm!")
            return WITHDRAW_AMOUNT
        
        # Tekshiramiz, balans yetarlimi
        if amount > float(user['balance']):
            await update.message.reply_text("❌ Balansingizda yetarli mablag' yo'q!")
            return WITHDRAW_AMOUNT
        
        context.user_data['withdraw_amount'] = amount
        
        commission = amount * 0.15
        final_amount = amount - commission
        
        text = (
            f"💳 Pul yechish tasdiqlash\n\n"
            f"💰 Yechish miqdori: {amount:,.0f} so'm\n"
            f"📉 Komissiya (15%): {commission:,.0f} so'm\n"
            f"🎯 Olinadigan summa: {final_amount:,.0f} so'm\n\n"
            f"UzCard/Humo kartangiz raqamini kiriting:"
        )
        
        await update.message.reply_text(text)
        logger.info(f"Withdrawal amount set for user {user_id}: {amount}")
        return WITHDRAW_CARD
        
    except ValueError:
        await update.message.reply_text("❌ Iltimos, raqam kiriting!")
        return WITHDRAW_AMOUNT

@check_subscription
async def handle_withdraw_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    card_number = update.message.text
    amount = context.user_data['withdraw_amount']
    
    # YANGI: Mashina majburiy emas
    
    # Save withdrawal request
    conn = await init_db()
    try:
        result = await conn.fetchrow(
            'INSERT INTO transactions (user_id, amount, type, card_number) VALUES ($1, $2, $3, $4) RETURNING id',
            user_id, amount, 'withdraw', card_number
        )
        
        request_id = result['id']
        commission = amount * 0.15
        final_amount = amount - commission
        
        # Admin ga so'rov yuborish inline keyboard bilan
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes", callback_data=f"approve_{request_id}"),
                InlineKeyboardButton("❌ No", callback_data=f"reject_{request_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            ADMIN_ID,
            f"🔄 Yangi pul yechish so'rovi:\n\n"
            f"🆔 So'rov ID: {request_id}\n"
            f"👤 User ID: {user_id}\n"
            f"💳 Karta: {card_number}\n"
            f"💰 Miqdor: {amount:,.0f} so'm\n"
            f"📉 Komissiya (15%): {commission:,.0f} so'm\n"
            f"🎯 Olinadigan: {final_amount:,.0f} so'm\n"
            f"⏰ Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Pul tushirildimi?",
            reply_markup=reply_markup
        )
        
        logger.info(f"Withdrawal request submitted by user {user_id}: {amount} to card {card_number}")
    except Exception as e:
        logger.error(f"Error processing withdrawal for user {user_id}: {e}")
    finally:
        await conn.close()
    
    await update.message.reply_text(
        "✅ Pul yechish so'rovingiz qabul qilindi!\n"
        "Admin 24 soat ichida ko'rib chiqadi."
    )
    
    await show_main_menu(update, context)
    return MENU

# ==================== DAILY BONUS (4 SOATDA) ====================

@check_subscription
async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    
    now = datetime.now()
    
    # YANGI: 4 soatda bir bonus
    if user['last_bonus'] and (now - user['last_bonus']).total_seconds() < 14400:  # 4 soat = 14400 soniya
        next_bonus = user['last_bonus'] + timedelta(hours=4)
        time_left = next_bonus - now
        
        hours = int(time_left.total_seconds() // 3600)
        minutes = int((time_left.total_seconds() % 3600) // 60)
        
        await update.message.reply_text(
            f"⏰ Siz bonusni allaqachon olgansiz!\n"
            f"Keyingi bonus: {hours} soat {minutes} daqiqadan keyin"
        )
        return
    
    bonus_amount = random.randint(100, 200)  # YANGI: 100-200 so'm
    
    conn = await init_db()
    try:
        await conn.execute(
            'UPDATE users SET balance = balance + $1, last_bonus = $2 WHERE user_id = $3',
            bonus_amount, now, user_id
        )
        
        # YANGI: Referal bonus berish (agar taklif qilgan bo'lsa)
        await give_referral_bonus(user_id, context)
        
        logger.info(f"Daily bonus given to user {user_id}: {bonus_amount}")
    except Exception as e:
        logger.error(f"Error giving daily bonus to user {user_id}: {e}")
    finally:
        await conn.close()
    
    await update.message.reply_text(
        f"🎉 Tabriklaymiz! 4 soatlik bonus:\n"
        f"💰 {bonus_amount} so'm\n\n"
        f"Keyingi bonus: 4 soatdan keyin"
    )

# ==================== ADMIN FUNCTIONS ====================

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    keyboard = [
        ["💰 Hisob to'ldirish", "📊 Statistika"],
        ["🔄 So'rovlar", "⚡️ Vazifa qo'shish"],
        ["📢 Kanallar", "👥 Adminlar"],
        ["🚫 Ban", "🔙 Asosiy menyu"]
    ]
    
    await update.message.reply_text(
        "👤 Admin panel",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# YANGI: Kanallar boshqaruvi
async def manage_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    conn = await init_db()
    try:
        channels = await conn.fetch('SELECT * FROM required_channels')
        
        text = "📢 Majburiy Kanallar:\n\n"
        keyboard = []
        
        for channel in channels:
            status = "✅ Aktiv" if channel['is_active'] else "❌ Noaktiv"
            text += f"📢 {channel['channel_name']} ({channel['channel_username']}) - {status}\n"
            
            if channel['is_active']:
                keyboard.append([InlineKeyboardButton(f"❌ {channel['channel_name']} ni o'chirish", callback_data=f"disable_channel_{channel['id']}")])
            else:
                keyboard.append([InlineKeyboardButton(f"✅ {channel['channel_name']} ni yoqish", callback_data=f"enable_channel_{channel['id']}")])
        
        keyboard.append([InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add_channel")])
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
        
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Error managing channels: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi")
    finally:
        await conn.close()

# YANGI: Adminlar boshqaruvi
async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:  # Faqat asosiy admin
        return
    
    conn = await init_db()
    try:
        admins = await conn.fetch('''
            SELECT u.user_id, u.created_at, a.added_at 
            FROM admins a 
            JOIN users u ON a.user_id = u.user_id
        ''')
        
        text = "👥 Adminlar ro'yxati:\n\n"
        keyboard = []
        
        for admin in admins:
            text += f"👤 {admin['user_id']} - {admin['added_at'].strftime('%Y-%m-%d')}\n"
            keyboard.append([InlineKeyboardButton(f"❌ {admin['user_id']} ni olib tashlash", callback_data=f"remove_admin_{admin['user_id']}")])
        
        keyboard.append([InlineKeyboardButton("➕ Admin qo'shish", callback_data="add_admin")])
        keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_admin")])
        
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Error managing admins: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi")
    finally:
        await conn.close()

# YANGI: Ban boshqaruvi
async def manage_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    await update.message.reply_text(
        "🚫 Foydalanuvchini ban qilish yoki bandan olish uchun quyidagi formatda yozing:\n\n"
        "Ban qilish: `/ban user_id`\n"
        "Bandan olish: `/unban user_id`\n\n"
        "Misol: `/ban 123456789`"
    )

# YANGI: Vazifa qo'shish
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    await update.message.reply_text(
        "⚡️ Yangi vazifa qo'shish uchun quyidagi formatda yozing:\n\n"
        "`/addtask title|description|reward|limit|url`\n\n"
        "Misol: `/addtask Telegram kanalga a'zo bo'lish|@gootaksi kanaliga a'zo bo'ling|500|100|https://t.me/gootaksi`\n\n"
        "ℹ️ Eslatma: limit ixtiyoriy, agar cheksiz bo'lsa, 0 yozing"
    )

# YANGI: Vazifa qo'shish command
async def add_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    try:
        data = ' '.join(context.args).split('|')
        if len(data) < 4:
            await update.message.reply_text("❌ Noto'g'ri format! Iltimos, formatga rioya qiling.")
            return
        
        title = data[0].strip()
        description = data[1].strip()
        reward = float(data[2].strip())
        task_limit = int(data[3].strip()) if len(data) > 3 and data[3].strip() != '0' else None
        task_url = data[4].strip() if len(data) > 4 else ""
        
        conn = await init_db()
        try:
            await conn.execute(
                'INSERT INTO tasks (title, description, reward, task_limit, task_url, created_by) VALUES ($1, $2, $3, $4, $5, $6)',
                title, description, reward, task_limit, task_url, update.effective_user.id
            )
            
            await update.message.reply_text("✅ Vazifa muvaffaqiyatli qo'shildi!")
            logger.info(f"New task added by admin {update.effective_user.id}: {title}")
            
        except Exception as e:
            logger.error(f"Error adding task: {e}")
            await update.message.reply_text("❌ Xatolik yuz berdi")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# YANGI: Ban command
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    try:
        user_id = int(context.args[0])
        
        conn = await init_db()
        try:
            await conn.execute(
                'UPDATE users SET is_banned = TRUE WHERE user_id = $1',
                user_id
            )
            
            await update.message.reply_text(f"✅ User {user_id} ban qilindi!")
            logger.info(f"User {user_id} banned by admin {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            await update.message.reply_text("❌ Xatolik yuz berdi")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# YANGI: Unban command
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    try:
        user_id = int(context.args[0])
        
        conn = await init_db()
        try:
            await conn.execute(
                'UPDATE users SET is_banned = FALSE WHERE user_id = $1',
                user_id
            )
            
            await update.message.reply_text(f"✅ User {user_id} bandan olindi!")
            logger.info(f"User {user_id} unbanned by admin {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            await update.message.reply_text("❌ Xatolik yuz berdi")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# YANGI: Admin qo'shish command
async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:  # Faqat asosiy admin
        return
    
    try:
        user_id = int(context.args[0])
        
        conn = await init_db()
        try:
            # User mavjudligini tekshiramiz
            user = await get_user(user_id)
            if not user:
                await update.message.reply_text("❌ User topilmadi!")
                return
            
            # Admin qo'shamiz
            await conn.execute(
                'INSERT INTO admins (user_id, added_by) VALUES ($1, $2)',
                user_id, update.effective_user.id
            )
            
            await update.message.reply_text(f"✅ User {user_id} admin qilindi!")
            logger.info(f"User {user_id} added as admin by {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error adding admin: {e}")
            await update.message.reply_text("❌ Xatolik yuz berdi yoki admin allaqachon mavjud")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# YANGI: Admin olib tashlash command
async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:  # Faqat asosiy admin
        return
    
    try:
        user_id = int(context.args[0])
        
        if user_id == ADMIN_ID:
            await update.message.reply_text("❌ Asosiy adminni olib tashlab bo'lmaydi!")
            return
        
        conn = await init_db()
        try:
            await conn.execute(
                'DELETE FROM admins WHERE user_id = $1',
                user_id
            )
            
            await update.message.reply_text(f"✅ User {user_id} admindan olib tashlandi!")
            logger.info(f"User {user_id} removed from admins by {update.effective_user.id}")
            
        except Exception as e:
            logger.error(f"Error removing admin: {e}")
            await update.message.reply_text("❌ Xatolik yuz berdi")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# ==================== MAIN FUNCTION ====================

def main():
    logger.info("Starting bot initialization...")
    
    # Create tables
    asyncio.get_event_loop().run_until_complete(create_tables())
    
    # Start Flask server in background for uptimerobot
    import threading
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server started for uptimerobot")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for user registration
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CAPTCHA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha),
            ],
            CHECK_SUBSCRIPTION: [
                CallbackQueryHandler(check_membership_callback, pattern="^check_membership$")
            ],
            MENU: [
                MessageHandler(filters.Regex("^🚖 Mashinalar$"), show_cars),
                MessageHandler(filters.Regex("^🚘 Mening Mashinam$"), show_my_cars),
                MessageHandler(filters.Regex("^💸 Hisobim$"), show_balance),
                MessageHandler(filters.Regex("^📥 Hisobni To'ldirish$"), fill_balance),
                MessageHandler(filters.Regex("^👥 Referal$"), show_referral),
                MessageHandler(filters.Regex("^🎁 Kunlik bonus$"), daily_bonus),
                MessageHandler(filters.Regex("^⚡️ Vazifalar$"), show_tasks),
                MessageHandler(filters.Regex("^💬 Qo'llab Quvvatlash$"), support),
                CallbackQueryHandler(show_car_detail, pattern="^car_"),
                CallbackQueryHandler(buy_car_handler, pattern="^buy_"),
                CallbackQueryHandler(withdraw_money, pattern="^withdraw$"),
                CallbackQueryHandler(show_tasks, pattern="^back_to_tasks$"),
                CallbackQueryHandler(start_task, pattern="^task_"),
                CallbackQueryHandler(confirm_task, pattern="^confirm_task_"),
                CallbackQueryHandler(show_main_menu, pattern="^back_to_menu$"),
            ],
            WITHDRAW_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)
            ],
            WITHDRAW_CARD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_card)
            ],
            TASK_CONFIRMATION: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_screenshot)
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    application.add_handler(conv_handler)
    
    # YANGI: Admin uchun handlerlar
    application.add_handler(CallbackQueryHandler(handle_withdraw_approval, pattern="^(approve|reject)_"))
    application.add_handler(CallbackQueryHandler(handle_task_approval, pattern="^(approve|reject)_task_"))
    
    # Admin handlers
    application.add_handler(CommandHandler("admin", admin_menu))
    application.add_handler(CommandHandler("fill", fill_user_balance))
    application.add_handler(CommandHandler("addtask", add_task_command))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    application.add_handler(CommandHandler("addadmin", add_admin_command))
    application.add_handler(CommandHandler("removeadmin", remove_admin_command))
    application.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), handle_admin_commands))
    
    # Start the bot
    logger.info("Bot starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
