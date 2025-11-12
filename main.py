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
DATABASE_URL = "postgresql://paidwork_ci87_user:jIsry475iXGF6KN7B1LUvKBXaQShUdY0@dpg-d4a59vruibrs73c7j37g-a/paidwork_ci87"

# Bot configuration
BOT_TOKEN = "8526778595:AAGP5ZINtNu6M2vYiZt2onz6bFRostthM8k"
ADMIN_ID = 7431672482
CHANNEL_USERNAME = "@gootaksi"
GROUP_USERNAME = "@gootaksi_chat"

# Conversation states
CAPTCHA, CHECK_SUBSCRIPTION, MENU, BUY_CAR, FILL_BALANCE, WITHDRAW_AMOUNT, WITHDRAW_CARD, SUPPORT, TASKS, TASK_DETAIL, TASK_SUBMIT = range(11)

# Car data - YANGI NOMLAR
CARS = {
    "bmw": {
        "name": "BMW",
        "daily_income": 5000,
        "duration": 100,
        "total_income": 500000,
        "price": 25000,
        "image": "https://i.ibb.co/bgjr7xNW/20251111-131622.png"
    },
    "mercedes": {
        "name": "Mercedes Benz", 
        "daily_income": 10000,
        "duration": 100,
        "total_income": 1000000,
        "price": 75000,
        "image": "https://i.ibb.co/Xf3JgpGS/20251111-131901.png"
    },
    "nissan": {
        "name": "Nissan GTR",
        "daily_income": 20000,
        "duration": 100,
        "total_income": 2000000,
        "price": 150000,
        "image": "https://i.ibb.co/tTVdQ70c/20251111-132004.png"
    },
    "supra": {
        "name": "Supra",
        "daily_income": 30000,
        "duration": 100,
        "total_income": 3000000,
        "price": 300000,
        "image": "https://i.ibb.co/3ywTRf7R/20251111-132135.png"
    },
    "ferrari": {
        "name": "Ferrari",
        "daily_income": 40000,
        "duration": 100,
        "total_income": 4000000,
        "price": 400000,
        "image": "https://i.ibb.co/9mc1RWkB/20251111-132318.png"
    },
    "bugatti": {
        "name": "Bugatti",
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
                cash_points DECIMAL DEFAULT 30000,
                total_earned DECIMAL DEFAULT 0,
                referred_by BIGINT,
                created_at TIMESTAMP DEFAULT NOW(),
                last_bonus TIMESTAMP,
                last_income TIMESTAMP,
                referral_bonus_earned DECIMAL DEFAULT 0,
                is_admin BOOLEAN DEFAULT FALSE
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
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                title VARCHAR(255),
                description TEXT,
                reward DECIMAL,
                task_limit INTEGER DEFAULT 0,
                current_count INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                created_by BIGINT
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS user_tasks (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                task_id INTEGER,
                status VARCHAR(20) DEFAULT 'pending',
                screenshot_url TEXT,
                submitted_at TIMESTAMP DEFAULT NOW(),
                reviewed_at TIMESTAMP,
                reviewed_by BIGINT,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS mandatory_channels (
                id SERIAL PRIMARY KEY,
                channel_username VARCHAR(100),
                channel_name VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Admin userni yaratish
        await conn.execute(
            'INSERT INTO users (user_id, phone_number, is_admin) VALUES ($1, $2, $3) ON CONFLICT (user_id) DO UPDATE SET is_admin = $3',
            ADMIN_ID, 'admin', True
        )
        
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
        return dict(user) if user else None
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None
    finally:
        await conn.close()

async def is_admin(user_id: int) -> bool:
    user = await get_user(user_id)
    return user and user.get('is_admin', False)

# YANGI: Majburiy kanallarni olish
async def get_mandatory_channels():
    conn = await init_db()
    try:
        channels = await conn.fetch(
            'SELECT * FROM mandatory_channels WHERE is_active = TRUE'
        )
        return [dict(channel) for channel in channels]
    except Exception as e:
        logger.error(f"Error getting mandatory channels: {e}")
        return []
    finally:
        await conn.close()

# YANGI: Kanal va guruh a'zoligini tekshirish
async def check_channel_and_group_membership(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        # Majburiy kanallarni olish
        mandatory_channels = await get_mandatory_channels()
        
        # Agar majburiy kanal yo'q bo'lsa, default kanallarni tekshirish
        if not mandatory_channels:
            # Kanalni tekshirish
            try:
                channel_member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
                channel_ok = channel_member.status in ['member', 'administrator', 'creator']
            except:
                channel_ok = False
            
            # Guruhni tekshirish
            try:
                group_member = await context.bot.get_chat_member(GROUP_USERNAME, user_id)
                group_ok = group_member.status in ['member', 'administrator', 'creator']
            except:
                group_ok = False
            
            return channel_ok and group_ok
        else:
            # Majburiy kanallarni tekshirish
            for channel in mandatory_channels:
                try:
                    channel_member = await context.bot.get_chat_member(channel['channel_username'], user_id)
                    if channel_member.status not in ['member', 'administrator', 'creator']:
                        return False
                except Exception as e:
                    logger.error(f"Error checking channel {channel['channel_username']}: {e}")
                    return False
            return True
            
    except Exception as e:
        logger.error(f"Error checking membership for {user_id}: {e}")
        return False

# YANGI: Majburiy obuna tekshiruvi
async def check_subscription_required(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    return not await check_channel_and_group_membership(user_id, context)

# YANGI: Referal bonus berish funksiyasi
async def give_referral_bonus(referrer_id: int, referred_id: int, context: ContextTypes.DEFAULT_TYPE):
    conn = await init_db()
    try:
        # Tekshiramiz, oldin bonus berilganmi
        existing_referral = await conn.fetchrow(
            'SELECT * FROM referrals WHERE referrer_id = $1 AND referred_id = $2',
            referrer_id, referred_id
        )
        
        if existing_referral:
            logger.info(f"Referral bonus already paid: {referrer_id} -> {referred_id}")
            return
        
        # 500 so'm bonus
        await conn.execute(
            'UPDATE users SET balance = balance + 500, referral_bonus_earned = referral_bonus_earned + 500 WHERE user_id = $1',
            referrer_id
        )
        
        await conn.execute(
            'INSERT INTO referrals (referrer_id, referred_id, bonus_paid) VALUES ($1, $2, $3)',
            referrer_id, referred_id, True
        )
        
        # Foydalanuvchiga xabar
        try:
            await context.bot.send_message(
                referrer_id,
                "🎉 Tabriklaymiz! Muvaffaqiyatli taklif qildingiz!\n\n"
                "💰 +500 so'm bonus qo'shildi!\n"
                "👥 Do'stingiz botga muvaffaqiyatli qo'shildi!"
            )
        except Exception as e:
            logger.error(f"Error sending bonus message to {referrer_id}: {e}")
        
        logger.info(f"Referral bonus paid: {referrer_id} -> {referred_id}: 500 so'm")
        
    except Exception as e:
        logger.error(f"Error giving referral bonus: {e}")
    finally:
        await conn.close()

async def create_user(user_id: int, referred_by: int = None, context: ContextTypes.DEFAULT_TYPE = None):
    conn = await init_db()
    try:
        await conn.execute(
            'INSERT INTO users (user_id, cash_points) VALUES ($1, 30000)',
            user_id
        )
        
        # YANGI: Referal bonus berish
        if referred_by and context:
            await give_referral_bonus(referred_by, user_id, context)
        
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

# YANGI: Cash points qo'shish
async def add_cash_points(user_id: int, amount: float):
    conn = await init_db()
    try:
        await conn.execute(
            'UPDATE users SET cash_points = cash_points + $1 WHERE user_id = $2',
            amount, user_id
        )
        logger.info(f"Cash points added for user {user_id}: {amount}")
    except Exception as e:
        logger.error(f"Error adding cash points for user {user_id}: {e}")
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

# YANGI: Captcha yaratish
def generate_captcha():
    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    answer = num1 + num2
    return f"{num1} + {num2} = ?", answer

# Start command - YANGI: CAPTCHA BILAN BOSHLASH
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Start command received from user {user_id}")
    
    # Check referral
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            logger.info(f"Referral detected: {referred_by} -> {user_id}")
        except:
            pass
    
    user = await get_user(user_id)
    
    # YANGI: Agar user mavjud bo'lsa, kanal tekshirish
    if user:
        if await check_subscription_required(user_id, context):
            await ask_for_subscription(update, context)
            return CHECK_SUBSCRIPTION
        else:
            await show_main_menu(update, context)
            return MENU
    
    # YANGI: Captcha yaratish
    captcha_text, captcha_answer = generate_captcha()
    context.user_data['captcha_answer'] = captcha_answer
    context.user_data['referred_by'] = referred_by
    
    await update.message.reply_text(
        f"Assalomu alaykum! Goo Taksi botiga xush kelibsiz!\n\n"
        f"Botdan foydalanish uchun quyidagi masalani yeching:\n\n"
        f"🔢 {captcha_text}\n\n"
        f"Javobni raqamda yuboring:"
    )
    
    logger.info(f"User {user_id} not registered, asking for captcha")
    return CAPTCHA

# YANGI: Captcha tekshirish
async def handle_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    try:
        user_answer = int(update.message.text)
        correct_answer = context.user_data.get('captcha_answer')
        
        if user_answer == correct_answer:
            # Captcha to'g'ri
            referred_by = context.user_data.get('referred_by')
            await create_user(user_id, referred_by, context)
            
            await update.message.reply_text(
                "✅ Captcha muvaffaqiyatli yechildi!\n\n"
                "🎁 Sizga 30,000 CP (Cash Points) bonus berildi!\n\n"
                "Endi botdan to'liq foydalanish uchun quyidagi kanal va guruhga a'zo bo'ling:"
            )
            
            # Kanal tekshirish
            await ask_for_subscription(update, context)
            return CHECK_SUBSCRIPTION
        else:
            await update.message.reply_text("❌ Noto'g'ri javob! Qaytadan urinib ko'ring:")
            return CAPTCHA
            
    except ValueError:
        await update.message.reply_text("❌ Iltimos, faqat raqam kiriting!")
        return CAPTCHA

# YANGI: Kanalga a'zo bo'lishni so'rash funksiyasi
async def ask_for_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mandatory_channels = await get_mandatory_channels()
    
    if mandatory_channels:
        keyboard = []
        for channel in mandatory_channels:
            keyboard.append([InlineKeyboardButton(f"📢 {channel['channel_name']}", url=f"https://t.me/{channel['channel_username'][1:]}")])
        keyboard.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_membership")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        channel_list = "\n".join([f"📢 {channel['channel_name']}: {channel['channel_username']}" for channel in mandatory_channels])
        
        if update.message:
            await update.message.reply_text(
                f"❌ Kechirasiz, botimizdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz kerak:\n\n"
                f"{channel_list}\n\n"
                f"Iltimos, kanallarga a'zo bo'ling va 'Tekshirish' tugmasini bosing.",
                reply_markup=reply_markup
            )
        else:
            await update.callback_query.edit_message_text(
                f"❌ Kechirasiz, botimizdan foydalanish uchun quyidagi kanallarga obuna bo'lishingiz kerak:\n\n"
                f"{channel_list}\n\n"
                f"Iltimos, kanallarga a'zo bo'ling va 'Tekshirish' tugmasini bosing.",
                reply_markup=reply_markup
            )
    else:
        # Default kanallar
        keyboard = [
            [InlineKeyboardButton("📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("💬 Guruhga a'zo bo'lish", url=f"https://t.me/{GROUP_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ Tekshirish", callback_data="check_membership")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(
                f"❌ Kechirasiz, botimizdan foydalanish uchun ushbu kanallarga obuna bo'lishingiz kerak:\n\n"
                f"📢 Kanal: {CHANNEL_USERNAME}\n"
                f"💬 Guruh: {GROUP_USERNAME}\n\n"
                f"Iltimos, kanallarga a'zo bo'ling va 'Tekshirish' tugmasini bosing.",
                reply_markup=reply_markup
            )
        else:
            await update.callback_query.edit_message_text(
                f"❌ Kechirasiz, botimizdan foydalanish uchun ushbu kanallarga obuna bo'lishingiz kerak:\n\n"
                f"📢 Kanal: {CHANNEL_USERNAME}\n"
                f"💬 Guruh: {GROUP_USERNAME}\n\n"
                f"Iltimos, kanallarga a'zo bo'ling va 'Tekshirish' tugmasini bosing.",
                reply_markup=reply_markup
            )

async def check_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    logger.info(f"Membership check callback from user {user_id}")
    
    if await check_channel_and_group_membership(user_id, context):
        await query.edit_message_text("✅ Siz kanal va guruhga a'zo bo'lgansiz! Endi botdan to'liq foydalanishingiz mumkin.")
        await show_main_menu(update, context)
        return MENU
    else:
        await query.answer("Siz hali kanal yoki guruhga a'zo bo'lmagansiz!", show_alert=True)
        logger.info(f"User {user_id} failed channel/group check")

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
    
    # YANGI: 2 qatorli keyboard
    keyboard = [
        ["🚖 Mashinalar", "🚘 Mening Mashinam"],
        ["💸 Hisobim", "📥 Hisobni To'ldirish"],
        ["👥 Referal", "🎁 Kunlik bonus"],
        ["📃 Vazifalar", "💬 Qo'llab Quvvatlash"]
    ]
    
    text = (
        f"🏠 Asosiy menyu\n\n"
        f"💰 Balans: {user['balance']:,.0f} so'm\n"
        f"💎 Cash Points: {user['cash_points']:,.0f} CP\n"
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
        if await check_subscription_required(user_id, context):
            await ask_for_subscription(update, context)
            return CHECK_SUBSCRIPTION
        return await func(update, context)
    return wrapper

# Car section
@check_subscription
async def show_cars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Show cars requested by user {update.effective_user.id}")
    
    # YANGI: 2 qatorli keyboard
    keyboard = [
        [InlineKeyboardButton("BMW", callback_data="car_bmw"), InlineKeyboardButton("Mercedes Benz", callback_data="car_mercedes")],
        [InlineKeyboardButton("Nissan GTR", callback_data="car_nissan"), InlineKeyboardButton("Supra", callback_data="car_supra")],
        [InlineKeyboardButton("Ferrari", callback_data="car_ferrari"), InlineKeyboardButton("Bugatti", callback_data="car_bugatti")]
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

# My Cars section
@check_subscription
async def show_my_cars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"My cars requested by user {user_id}")
    
    cars = await get_user_cars(user_id)
    
    if not cars:
        await update.message.reply_text("🚫 Sizda hali mashinalar yo'q")
        return
    
    text = "🚘 Mening mashinalarim:\n\n"
    for car in cars:
        car_data = CARS[car['car_type']]
        
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
        
        text += (
            f"🚗 {car_data['name']}\n"
            f"💰 Kunlik: {car_data['daily_income']:,.0f} so'm\n"
            f"⏰ Qolgan vaqt: {days_left} kun {hours_left} soat\n"
            f"🕐 Keyingi daromad: {next_income_str}\n\n"
        )
    
    await update.message.reply_text(text)

# Balance section
@check_subscription
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    
    # YANGI: Mashina shart emas
    can_withdraw = float(user['balance']) >= 20000 and float(user['cash_points']) >= 0
    
    text = (
        f"💸 Hisobim\n\n"
        f"💰 Joriy balans: {user['balance']:,.0f} so'm\n"
        f"💎 Cash Points: {user['cash_points']:,.0f} CP\n"
        f"📈 Umumiy daromad: {user['total_earned']:,.0f} so'm\n"
        f"🚗 Faol mashinalar: {len(await get_user_cars(user_id))} ta"
    )
    
    # PUL YECHISH KNOPKASI BARCHA USERLARGA KO'RINADI
    keyboard = [[InlineKeyboardButton("💳 Pul yechish", callback_data="withdraw")]]
    
    if can_withdraw:
        text += f"\n\n💳 Minimal pul yechish: 20,000 so'm\n📉 Komissiya: 15%\n💎 Talab qilinadigan CP: 0"
    else:
        if float(user['balance']) < 20000:
            text += f"\n\n⚠️ Pul yechish uchun balansingiz kamida 20,000 so'm bo'lishi kerak!"
        elif float(user['cash_points']) < 0:
            text += f"\n\n⚠️ Pul yechish uchun Cash Points (CP) kamida 0 bo'lishi kerak!"
    
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
    
    # YANGI: Mashina shart emas
    
    # Tekshiramiz, minimal miqdor bormi
    if float(user['balance']) < 20000:
        await query.answer("❌ Balansingiz 20,000 so'mdan kam!", show_alert=True)
        return
    
    # Tekshiramiz, cash points bormi
    if float(user['cash_points']) < 0:
        await query.answer("❌ Cash Points (CP) yetarli emas! Do'stlaringizni taklif qiling yoki ularning hisobini to'ldirishlarini so'rang!", show_alert=True)
        return
    
    text = (
        f"💳 Pul yechish\n\n"
        f"💰 Mavjud balans: {user['balance']:,.0f} so'm\n"
        f"💎 Mavjud CP: {user['cash_points']:,.0f}\n"
        f"💸 Minimal yechish: 20,000 so'm\n"
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
        
        # Tekshiramiz, minimal miqdor bormi
        if amount < 20000:
            await update.message.reply_text("❌ Minimal yechish miqdori 20,000 so'm!")
            return WITHDRAW_AMOUNT
        
        # Tekshiramiz, balans yetarlimi
        if amount > float(user['balance']):
            await update.message.reply_text("❌ Balansingizda yetarli mablag' yo'q!")
            return WITHDRAW_AMOUNT
        
        # Tekshiramiz, cash points yetarlimi
        if float(user['cash_points']) < 0:
            await update.message.reply_text("❌ Cash Points (CP) yetarli emas! Do'stlaringizni taklif qiling yoki ularning hisobini to'ldirishlarini so'rang!")
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

# YANGI: Admin uchun so'rovni tasdiqlash/rad etish handler
async def handle_withdraw_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    # Faqat admin tasdiqlashi mumkin
    if not await is_admin(user_id):
        await query.answer("Sizda bu amalni bajarish uchun ruxsat yo'q!", show_alert=True)
        return
    
    data = query.data
    action, request_id = data.split('_')
    request_id = int(request_id)
    
    conn = await init_db()
    try:
        # So'rovni bazadan olamiz
        request = await conn.fetchrow(
            'SELECT * FROM transactions WHERE id = $1', request_id
        )
        
        if not request:
            await query.answer("❌ So'rov topilmadi!", show_alert=True)
            return
        
        if action == 'approve':
            # So'rovni tasdiqlaymiz
            await conn.execute(
                'UPDATE transactions SET status = $1 WHERE id = $2',
                'approved', request_id
            )
            
            # Foydalanuvchi balansidan pulni ayiramiz
            commission = float(request['amount']) * 0.15
            amount_to_deduct = float(request['amount'])
            
            await conn.execute(
                'UPDATE users SET balance = balance - $1 WHERE user_id = $2',
                amount_to_deduct, request['user_id']
            )
            
            # Foydalanuvchiga xabar
            await context.bot.send_message(
                request['user_id'],
                f"✅ Pul yechish so'rovingiz tasdiqlandi!\n\n"
                f"💰 {float(request['amount']) - commission:,.0f} so'm kartangizga o'tkazildi\n"
                f"📉 Komissiya (15%): {commission:,.0f} so'm\n"
                f"💳 Karta: {request['card_number']}\n\n"
                f"Pul muvaffaqiyatli tushirildi! 🎉"
            )
            
            # Admin ga tasdiqlash xabari
            await query.edit_message_text(
                f"✅ So'rov tasdiqlandi!\n\n"
                f"🆔 So'rov ID: {request_id}\n"
                f"👤 User ID: {request['user_id']}\n"
                f"💰 Miqdor: {request['amount']:,.0f} so'm\n"
                f"💳 Karta: {request['card_number']}\n\n"
                f"Pul muvaffaqiyatli tushirildi!"
            )
            
            logger.info(f"Withdrawal approved: {request_id} for user {request['user_id']}")
            
        elif action == 'reject':
            # So'rovni rad etamiz
            await conn.execute(
                'UPDATE transactions SET status = $1 WHERE id = $2',
                'rejected', request_id
            )
            
            # Foydalanuvchiga xabar
            await context.bot.send_message(
                request['user_id'],
                f"❌ Pul yechish so'rovingiz rad etildi!\n\n"
                f"Sabab: Admin tomonidan rad etildi\n"
                f"Iltimos, qaytadan urinib ko'ring yoki admin bilan bog'laning."
            )
            
            # Admin ga rad etish xabari
            await query.edit_message_text(
                f"❌ So'rov rad etildi!\n\n"
                f"🆔 So'rov ID: {request_id}\n"
                f"👤 User ID: {request['user_id']}\n"
                f"💰 Miqdor: {request['amount']:,.0f} so'm\n"
                f"💳 Karta: {request['card_number']}\n\n"
                f"So'rov rad etildi!"
            )
            
            logger.info(f"Withdrawal rejected: {request_id} for user {request['user_id']}")
        
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error processing withdrawal approval: {e}")
        await query.answer("❌ Xatolik yuz berdi!", show_alert=True)
    finally:
        await conn.close()

# Fill balance section - YANGI: Cash points qo'shish
@check_subscription
async def fill_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    
    text = (
        "📥 Hisobni to'ldirish\n\n"
        "Hisobingizni to'ldirish uchun admin bilan bog'laning:\n"
        f"👤 Admin: @GooTaksi_Admin\n\n"
        "Ish vaqti 7:00 23:00 gacha.\n\n"
        f"💎 Joriy Cash Points: {user['cash_points']:,.0f} CP\n\n"
        "⚠️ Eslatma: Do'stlaringiz hisobini to'ldirganida, ular to'ldirgan miqdorning 50% sizga Cash Points sifatida qo'shiladi!"
    )
    
    await update.message.reply_text(text)

# Referral section
@check_subscription
async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = await init_db()
    try:
        referrals_count = await conn.fetchval(
            'SELECT COUNT(*) FROM referrals WHERE referrer_id = $1', user_id
        )
        
        # Referal bonusini hisoblaymiz
        user = await get_user(user_id)
        referral_bonus = float(user['referral_bonus_earned']) if user['referral_bonus_earned'] else 0
        
    except Exception as e:
        logger.error(f"Error getting referral data for user {user_id}: {e}")
        referrals_count = 0
        referral_bonus = 0
    finally:
        await conn.close()
    
    referral_link = f"https://t.me/{(await context.bot.get_me()).username}?start={user_id}"
    
    text = (
        f"👥 Referal tizimi\n\n"
        f"📊 Jami takliflar: {referrals_count} ta\n"
        f"💰 Referal bonus: {referral_bonus:,.0f} so'm\n\n"
        f"🔗 Sizning referal havolangiz:\n{referral_link}\n\n"
        f"🎯 Taklif qilish shartlari:\n"
        f"• Har bir taklif uchun: 500 so'm bonus\n"
        f"• Do'stingiz hisob to'ldirsa: 50% Cash Points\n"
    )
    
    await update.message.reply_text(text)

# YANGI: Kunlik bonus - 3 soatda bir
@check_subscription
async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = await get_user(user_id)
    
    now = datetime.now()
    
    if user['last_bonus'] and (now - user['last_bonus']).total_seconds() < 10800:  # 3 soat = 10800 soniya
        next_bonus = user['last_bonus'] + timedelta(hours=3)
        time_left = next_bonus - now
        
        hours = int(time_left.total_seconds() // 3600)
        minutes = int((time_left.total_seconds() % 3600) // 60)
        
        await update.message.reply_text(
            f"⏰ Siz bonusni allaqachon olgansiz!\n"
            f"Keyingi bonus: {hours} soat {minutes} daqiqadan keyin"
        )
        return
    
    bonus_amount = random.randint(100, 300)
    
    conn = await init_db()
    try:
        await conn.execute(
            'UPDATE users SET balance = balance + $1, last_bonus = $2 WHERE user_id = $3',
            bonus_amount, now, user_id
        )
        logger.info(f"Daily bonus given to user {user_id}: {bonus_amount}")
    except Exception as e:
        logger.error(f"Error giving daily bonus to user {user_id}: {e}")
    finally:
        await conn.close()
    
    await update.message.reply_text(
        f"🎉 Tabriklaymiz! Kunlik bonus:\n"
        f"💰 {bonus_amount} so'm\n\n"
        f"Keyingi bonus: 3 soatdan keyin"
    )

# YANGI: Vazifalar bo'limi
@check_subscription
async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await init_db()
    try:
        tasks = await conn.fetch(
            'SELECT * FROM tasks WHERE is_active = TRUE AND (task_limit = 0 OR current_count < task_limit)'
        )
        
        if not tasks:
            await update.message.reply_text("📃 Hozircha aktiv vazifalar mavjud emas")
            return
        
        keyboard = []
        for task in tasks:
            task_data = dict(task)
            keyboard.append([InlineKeyboardButton(f"{task_data['title']} - {task_data['reward']:,.0f} so'm", callback_data=f"task_{task_data['id']}")])
        
        text = "📃 Vazifalar ro'yxati:\n\nQuyidagi vazifalardan birini tanlang:"
        
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Error showing tasks: {e}")
        await update.message.reply_text("❌ Vazifalarni yuklashda xatolik yuz berdi")
    finally:
        await conn.close()

@check_subscription
async def show_task_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    task_id = int(query.data.split('_')[1])
    
    conn = await init_db()
    try:
        task = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)
        
        if not task:
            await query.answer("❌ Vazifa topilmadi!", show_alert=True)
            return
        
        task_data = dict(task)
        
        text = (
            f"📃 {task_data['title']}\n\n"
            f"📝 {task_data['description']}\n\n"
            f"💰 Mukofot: {task_data['reward']:,.0f} so'm\n"
            f"👥 Limit: {task_data['task_limit'] if task_data['task_limit'] > 0 else 'Cheksiz'}\n"
            f"✅ Qatnashganlar: {task_data['current_count']}\n\n"
            f"Vazifani bajarganingizdan so'ng, screenshot yuboring."
        )
        
        keyboard = [
            [InlineKeyboardButton("🚀 Vazifani boshlash", callback_data=f"start_task_{task_id}")]
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Error showing task detail: {e}")
        await query.answer("❌ Xatolik yuz berdi!", show_alert=True)
    finally:
        await conn.close()

@check_subscription
async def start_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    task_id = int(query.data.split('_')[2])
    user_id = query.from_user.id
    
    # Tekshiramiz, user bu vazifani oldin boshlaganmi
    conn = await init_db()
    try:
        existing_task = await conn.fetchrow(
            'SELECT * FROM user_tasks WHERE user_id = $1 AND task_id = $2',
            user_id, task_id
        )
        
        if existing_task:
            await query.answer("❌ Siz bu vazifani allaqachon boshlagansiz!", show_alert=True)
            return
        
        # User task yaratamiz
        await conn.execute(
            'INSERT INTO user_tasks (user_id, task_id) VALUES ($1, $2)',
            user_id, task_id
        )
        
        task = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)
        task_data = dict(task)
        
        await query.edit_message_text(
            f"✅ Vazifa boshlandi: {task_data['title']}\n\n"
            f"Vazifani bajarganingizdan so'ng, screenshot yuboring.\n\n"
            f"Iltimos, screenshot ni yuboring:"
        )
        
        context.user_data['current_task_id'] = task_id
        logger.info(f"Task started: user {user_id}, task {task_id}")
        
        return TASK_SUBMIT
        
    except Exception as e:
        logger.error(f"Error starting task: {e}")
        await query.answer("❌ Xatolik yuz berdi!", show_alert=True)
        return MENU
    finally:
        await conn.close()

@check_subscription
async def handle_task_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    task_id = context.user_data.get('current_task_id')
    
    if not task_id:
        await update.message.reply_text("❌ Vazifa topilmadi! Iltimos, qaytadan boshlang.")
        await show_main_menu(update, context)
        return MENU
    
    # Tekshiramiz, photo yuborilganmi
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos, screenshot yuboring!")
        return TASK_SUBMIT
    
    # Eng katta o'lchamdagi fotoni olamiz
    photo = update.message.photo[-1]
    photo_file = await photo.get_file()
    
    conn = await init_db()
    try:
        # User task ni yangilaymiz
        await conn.execute(
            'UPDATE user_tasks SET screenshot_url = $1, status = $2 WHERE user_id = $3 AND task_id = $4',
            photo_file.file_path, 'submitted', user_id, task_id
        )
        
        task = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)
        task_data = dict(task)
        
        # Admin ga xabar yuboramiz
        keyboard = [
            [
                InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_task_{task_id}_{user_id}"),
                InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_task_{task_id}_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        admins = await conn.fetch('SELECT user_id FROM users WHERE is_admin = TRUE')
        for admin in admins:
            try:
                await context.bot.send_photo(
                    admin['user_id'],
                    photo=photo_file.file_id,
                    caption=(
                        f"🔄 Yangi vazifa topshirig'i:\n\n"
                        f"📃 Vazifa: {task_data['title']}\n"
                        f"👤 User: {user_id}\n"
                        f"💰 Mukofot: {task_data['reward']:,.0f} so'm\n"
                        f"⏰ Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                    ),
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Error sending task submission to admin {admin['user_id']}: {e}")
        
        await update.message.reply_text(
            "✅ Screenshot muvaffaqiyatli yuborildi!\n\n"
            "Admin tekshirgandan so'ng mukofot hisobingizga qo'shiladi."
        )
        
        logger.info(f"Task submission sent: user {user_id}, task {task_id}")
        
        await show_main_menu(update, context)
        return MENU
        
    except Exception as e:
        logger.error(f"Error handling task submission: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi! Iltimos, qaytadan urinib ko'ring.")
        return TASK_SUBMIT
    finally:
        await conn.close()

# YANGI: Vazifa tasdiqlash/rad etish handler
async def handle_task_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    # Faqat admin tasdiqlashi mumkin
    if not await is_admin(user_id):
        await query.answer("Sizda bu amalni bajarish uchun ruxsat yo'q!", show_alert=True)
        return
    
    data = query.data
    parts = data.split('_')
    action = parts[1]
    task_id = int(parts[2])
    target_user_id = int(parts[3])
    
    conn = await init_db()
    try:
        task = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)
        task_data = dict(task)
        user_task = await conn.fetchrow(
            'SELECT * FROM user_tasks WHERE user_id = $1 AND task_id = $2',
            target_user_id, task_id
        )
        
        if not user_task:
            await query.answer("❌ Vazifa topilmadi!", show_alert=True)
            return
        
        if action == 'approve':
            # Vazifani tasdiqlaymiz
            await conn.execute(
                'UPDATE user_tasks SET status = $1, reviewed_at = $2, reviewed_by = $3 WHERE user_id = $4 AND task_id = $5',
                'approved', datetime.now(), user_id, target_user_id, task_id
            )
            
            # Mukofotni beramiz
            reward = task_data['reward']
            await conn.execute(
                'UPDATE users SET balance = balance + $1 WHERE user_id = $2',
                reward, target_user_id
            )
            
            # Task count ni oshiramiz
            await conn.execute(
                'UPDATE tasks SET current_count = current_count + 1 WHERE id = $1',
                task_id
            )
            
            # Foydalanuvchiga xabar
            await context.bot.send_message(
                target_user_id,
                f"✅ Vazifangiz tasdiqlandi!\n\n"
                f"📃 Vazifa: {task_data['title']}\n"
                f"💰 Mukofot: {reward:,.0f} so'm\n\n"
                f"Mukofot hisobingizga qo'shildi! 🎉"
            )
            
            await query.edit_message_caption(
                f"✅ Vazifa tasdiqlandi!\n\n"
                f"📃 Vazifa: {task_data['title']}\n"
                f"👤 User: {target_user_id}\n"
                f"💰 Mukofot: {reward:,.0f} so'm\n\n"
                f"Mukofot foydalanuvchi hisobiga qo'shildi!"
            )
            
            logger.info(f"Task approved: user {target_user_id}, task {task_id}")
            
        elif action == 'reject':
            # Vazifani rad etamiz
            await conn.execute(
                'UPDATE user_tasks SET status = $1, reviewed_at = $2, reviewed_by = $3 WHERE user_id = $4 AND task_id = $5',
                'rejected', datetime.now(), user_id, target_user_id, task_id
            )
            
            # Foydalanuvchiga xabar
            await context.bot.send_message(
                target_user_id,
                f"❌ Vazifangiz rad etildi!\n\n"
                f"📃 Vazifa: {task_data['title']}\n"
                f"Sabab: Screenshot to'g'ri emas yoki vazifa shartlariga mos kelmadi.\n\n"
                f"Iltimos, qaytadan urinib ko'ring."
            )
            
            await query.edit_message_caption(
                f"❌ Vazifa rad etildi!\n\n"
                f"📃 Vazifa: {task_data['title']}\n"
                f"👤 User: {target_user_id}\n\n"
                f"Vazifa rad etildi!"
            )
            
            logger.info(f"Task rejected: user {target_user_id}, task {task_id}")
        
        await query.answer()
        
    except Exception as e:
        logger.error(f"Error processing task approval: {e}")
        await query.answer("❌ Xatolik yuz berdi!", show_alert=True)
    finally:
        await conn.close()

# Support
@check_subscription
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💬 Qo'llab Quvvatlash\n\n"
        "Savol yoki takliflaringiz bo'lsa, admin bilan bog'laning:\n"
        f"👤 Admin: @GooTaksi_Admin\n\n"
        "Yordam kerak bo'lsa, murojaat qiling!"
    )
    
    await update.message.reply_text(text)

# YANGI: Admin functions - Kengaytirilgan
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    # YANGI: 2 qatorli keyboard
    keyboard = [
        ["💰 Hisob to'ldirish", "📊 Statistika"],
        ["🔄 So'rovlar", "📃 Vazifalar boshqaruvi"],
        ["📢 Kanallar boshqaruvi", "👥 Adminlar boshqaruvi"],
        ["📢 Xabar tarqatish", "🔙 Asosiy menyu"]
    ]
    
    await update.message.reply_text(
        "👤 Admin panel",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    text = update.message.text
    
    if text == "💰 Hisob to'ldirish":
        await update.message.reply_text(
            "Foydalanuvchi hisobini to'ldirish uchun quyidagi formatda yozing:\n"
            "`/fill user_id amount`\n\n"
            "Misol: `/fill 123456789 50000`\n\n"
            "Eslatma: Foydalanuvchi hisobi to'lganda, uni taklif qilgan foydalanuvchiga 50% Cash Points beriladi!"
        )
    
    elif text == "🔄 So'rovlar":
        await show_withdraw_requests(update, context)
    
    elif text == "📊 Statistika":
        await show_stats(update, context)
    
    elif text == "📃 Vazifalar boshqaruvi":
        await manage_tasks(update, context)
    
    elif text == "📢 Kanallar boshqaruvi":
        await manage_channels(update, context)
    
    elif text == "👥 Adminlar boshqaruvi":
        await manage_admins(update, context)
    
    elif text == "📢 Xabar tarqatish":
        await update.message.reply_text(
            "Barcha foydalanuvchilarga xabar tarqatish uchun quyidagi formatda yozing:\n"
            "`/broadcast xabar matni`\n\n"
            "Misol: `/broadcast Yangi yangiliklar!`"
        )
    
    elif text == "🔙 Asosiy menyu":
        await show_main_menu(update, context)

async def fill_user_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    try:
        user_id = int(context.args[0])
        amount = float(context.args[1])
        
        await update_balance(user_id, amount)
        
        # YANGI: Referrer ga 50% cash points berish
        conn = await init_db()
        try:
            user = await get_user(user_id)
            if user and user['referred_by']:
                cash_points_bonus = amount * 0.5
                await add_cash_points(user['referred_by'], cash_points_bonus)
                
                # Referrer ga xabar
                try:
                    await context.bot.send_message(
                        user['referred_by'],
                        f"🎉 Tabriklaymiz! Taklif qilgan do'stingiz hisob to'ldirdi!\n\n"
                        f"💰 Sizga {cash_points_bonus:,.0f} CP bonus berildi!\n"
                        f"👤 Do'st: {user_id}\n"
                        f"💵 Miqdor: {amount:,.0f} so'm"
                    )
                except Exception as e:
                    logger.error(f"Error sending cash points message to {user['referred_by']}: {e}")
        except Exception as e:
            logger.error(f"Error giving cash points bonus: {e}")
        finally:
            await conn.close()
        
        # Notify user
        await context.bot.send_message(
            user_id,
            f"✅ Hisobingiz to'ldirildi!\n"
            f"💰 Miqdor: {amount:,.0f} so'm\n"
            f"💳 Yangi balans: {(await get_user(user_id))['balance']:,.0f} so'm"
        )
        
        await update.message.reply_text("✅ Hisob muvaffaqiyatli to'ldirildi!")
        logger.info(f"Admin filled balance for user {user_id}: {amount}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")
        logger.error(f"Error in admin fill balance: {e}")

async def show_withdraw_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await init_db()
    try:
        requests = await conn.fetch(
            'SELECT * FROM transactions WHERE type = $1 AND status = $2 ORDER BY created_at',
            'withdraw', 'pending'
        )
        
        if not requests:
            await update.message.reply_text("🔄 Hozircha so'rovlar yo'q")
            return
        
        text = "🔄 Pul yechish so'rovlari:\n\n"
        for req in requests:
            user = await get_user(req['user_id'])
            commission = float(req['amount']) * 0.15
            final_amount = float(req['amount']) - commission
            
            text += (
                f"🆔 So'rov ID: {req['id']}\n"
                f"👤 User: {req['user_id']}\n"
                f"💳 Karta: {req['card_number']}\n"
                f"💰 Miqdor: {req['amount']:,.0f} so'm\n"
                f"📉 Komissiya: {commission:,.0f} so'm\n"
                f"🎯 O'tkazish: {final_amount:,.0f} so'm\n"
                f"⏰ Vaqt: {req['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
                f"────────────────────\n"
            )
        
        await update.message.reply_text(text)
        
    except Exception as e:
        logger.error(f"Error showing withdraw requests: {e}")
        await update.message.reply_text(f"❌ Xato: {e}")
    finally:
        await conn.close()

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await init_db()
    try:
        total_users = await conn.fetchval('SELECT COUNT(*) FROM users')
        total_balance = await conn.fetchval('SELECT COALESCE(SUM(balance), 0) FROM users')
        total_cash_points = await conn.fetchval('SELECT COALESCE(SUM(cash_points), 0) FROM users')
        total_cars = await conn.fetchval('SELECT COUNT(*) FROM user_cars WHERE is_active = TRUE')
        total_withdrawals = await conn.fetchval(
            'SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = $1 AND status = $2',
            'withdraw', 'approved'
        )
        
        text = (
            f"📊 Bot statistikasi:\n\n"
            f"👥 Jami foydalanuvchilar: {total_users}\n"
            f"💰 Jami balans: {total_balance:,.0f} so'm\n"
            f"💎 Jami Cash Points: {total_cash_points:,.0f} CP\n"
            f"🚗 Faol mashinalar: {total_cars} ta\n"
            f"💸 Yechilgan pullar: {total_withdrawals:,.0f} so'm"
        )
        
        await update.message.reply_text(text)
        logger.info("Admin viewed statistics")
        
    except Exception as e:
        logger.error(f"Error showing statistics: {e}")
        await update.message.reply_text(f"❌ Xato: {e}")
    finally:
        await conn.close()

# YANGI: Vazifalar boshqaruvi
async def manage_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    keyboard = [
        ["➕ Yangi vazifa", "📃 Vazifalar ro'yxati"],
        ["✏️ Vazifani tahrirlash", "🗑️ Vazifani o'chirish"],
        ["🔙 Admin menyu"]
    ]
    
    await update.message.reply_text(
        "📃 Vazifalar boshqaruvi",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_task_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    text = update.message.text
    
    if text == "➕ Yangi vazifa":
        await update.message.reply_text(
            "Yangi vazifa qo'shish uchun quyidagi formatda yozing:\n"
            "`/add_task nomi|izoh|mukofot|limit`\n\n"
            "Misol: `/add_task Instagram obuna bo'lish|Instagram sahifamizga obuna bo'ling|5000|100`\n\n"
            "Eslatma: Limit 0 bo'lsa, cheksiz bo'ladi."
        )
    
    elif text == "📃 Vazifalar ro'yxati":
        await show_all_tasks(update, context)
    
    elif text == "✏️ Vazifani tahrirlash":
        await update.message.reply_text(
            "Vazifani tahrirlash uchun quyidagi formatda yozing:\n"
            "`/edit_task id|nom|izoh|mukofot|limit|faol`\n\n"
            "Misol: `/edit_task 1|Yangi nom|Yangi izoh|7000|50|true`"
        )
    
    elif text == "🗑️ Vazifani o'chirish":
        await update.message.reply_text(
            "Vazifani o'chirish uchun quyidagi formatda yozing:\n"
            "`/delete_task id`\n\n"
            "Misol: `/delete_task 1`"
        )
    
    elif text == "🔙 Admin menyu":
        await admin_menu(update, context)

# YANGI: Vazifa qo'shish command
async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    try:
        args = ' '.join(context.args).split('|')
        if len(args) < 4:
            await update.message.reply_text("❌ Noto'g'ri format! Format: /add_task nom|izoh|mukofot|limit")
            return
        
        title = args[0].strip()
        description = args[1].strip()
        reward = float(args[2].strip())
        task_limit = int(args[3].strip()) if len(args) > 3 else 0
        
        conn = await init_db()
        try:
            await conn.execute(
                'INSERT INTO tasks (title, description, reward, task_limit, created_by) VALUES ($1, $2, $3, $4, $5)',
                title, description, reward, task_limit, update.effective_user.id
            )
            
            await update.message.reply_text("✅ Yangi vazifa muvaffaqiyatli qo'shildi!")
            logger.info(f"New task added: {title}")
            
        except Exception as e:
            logger.error(f"Error adding task: {e}")
            await update.message.reply_text(f"❌ Xatolik: {e}")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# YANGI: Barcha vazifalarni ko'rsatish
async def show_all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await init_db()
    try:
        tasks = await conn.fetch('SELECT * FROM tasks ORDER BY id')
        
        if not tasks:
            await update.message.reply_text("📃 Hozircha vazifalar mavjud emas")
            return
        
        text = "📃 Barcha vazifalar:\n\n"
        for task in tasks:
            task_data = dict(task)
            status = "✅ Faol" if task_data['is_active'] else "❌ Nofaol"
            text += (
                f"🆔 {task_data['id']}: {task_data['title']}\n"
                f"💰 {task_data['reward']:,.0f} so'm | 👥 {task_data['current_count']}/{task_data['task_limit'] if task_data['task_limit'] > 0 else '∞'}\n"
                f"📝 {task_data['description'][:50]}...\n"
                f"📊 {status}\n"
                f"────────────────────\n"
            )
        
        await update.message.reply_text(text)
        
    except Exception as e:
        logger.error(f"Error showing all tasks: {e}")
        await update.message.reply_text(f"❌ Xatolik: {e}")
    finally:
        await conn.close()

# YANGI: Kanallar boshqaruvi
async def manage_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    keyboard = [
        ["➕ Kanal qo'shish", "📃 Kanallar ro'yxati"],
        ["🗑️ Kanalni o'chirish", "🔙 Admin menyu"]
    ]
    
    await update.message.reply_text(
        "📢 Kanallar boshqaruvi",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_channel_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    text = update.message.text
    
    if text == "➕ Kanal qo'shish":
        await update.message.reply_text(
            "Yangi majburiy kanal qo'shish uchun quyidagi formatda yozing:\n"
            "`/add_channel @username nomi`\n\n"
            "Misol: `/add_channel @gootaksi Goo Taksi Kanal`"
        )
    
    elif text == "📃 Kanallar ro'yxati":
        await show_all_channels(update, context)
    
    elif text == "🗑️ Kanalni o'chirish":
        await update.message.reply_text(
            "Kanalni o'chirish uchun quyidagi formatda yozing:\n"
            "`/delete_channel id`\n\n"
            "Misol: `/delete_channel 1`"
        )
    
    elif text == "🔙 Admin menyu":
        await admin_menu(update, context)

# YANGI: Kanal qo'shish command
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    try:
        if len(context.args) < 2:
            await update.message.reply_text("❌ Noto'g'ri format! Format: /add_channel @username nomi")
            return
        
        username = context.args[0].strip()
        channel_name = ' '.join(context.args[1:]).strip()
        
        if not username.startswith('@'):
            username = '@' + username
        
        conn = await init_db()
        try:
            await conn.execute(
                'INSERT INTO mandatory_channels (channel_username, channel_name) VALUES ($1, $2)',
                username, channel_name
            )
            
            await update.message.reply_text("✅ Yangi kanal muvaffaqiyatli qo'shildi!")
            logger.info(f"New channel added: {username}")
            
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            await update.message.reply_text(f"❌ Xatolik: {e}")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# YANGI: Kanal o'chirish command
async def delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    try:
        if not context.args:
            await update.message.reply_text("❌ Kanal ID sini kiriting! Format: /delete_channel id")
            return
        
        channel_id = int(context.args[0].strip())
        
        conn = await init_db()
        try:
            result = await conn.execute(
                'DELETE FROM mandatory_channels WHERE id = $1',
                channel_id
            )
            
            if result == "DELETE 0":
                await update.message.reply_text("❌ Kanal topilmadi!")
            else:
                await update.message.reply_text("✅ Kanal muvaffaqiyatli o'chirildi!")
                logger.info(f"Channel deleted: {channel_id}")
            
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")
            await update.message.reply_text(f"❌ Xatolik: {e}")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# YANGI: Barcha kanallarni ko'rsatish
async def show_all_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = await get_mandatory_channels()
    
    if not channels:
        await update.message.reply_text("📢 Hozircha majburiy kanallar mavjud emas")
        return
    
    text = "📢 Majburiy kanallar ro'yxati:\n\n"
    for channel in channels:
        text += (
            f"🆔 {channel['id']}: {channel['channel_name']}\n"
            f"🔗 {channel['channel_username']}\n"
            f"────────────────────\n"
        )
    
    await update.message.reply_text(text)

# YANGI: Adminlar boshqaruvi
async def manage_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    keyboard = [
        ["➕ Admin qo'shish", "📃 Adminlar ro'yxati"],
        ["🗑️ Adminni olib tashlash", "🔙 Admin menyu"]
    ]
    
    await update.message.reply_text(
        "👥 Adminlar boshqaruvi",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_admin_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    text = update.message.text
    
    if text == "➕ Admin qo'shish":
        await update.message.reply_text(
            "Yangi admin qo'shish uchun quyidagi formatda yozing:\n"
            "`/add_admin user_id`\n\n"
            "Misol: `/add_admin 123456789`"
        )
    
    elif text == "📃 Adminlar ro'yxati":
        await show_all_admins(update, context)
    
    elif text == "🗑️ Adminni olib tashlash":
        await update.message.reply_text(
            "Adminni olib tashlash uchun quyidagi formatda yozing:\n"
            "`/remove_admin user_id`\n\n"
            "Misol: `/remove_admin 123456789`"
        )
    
    elif text == "🔙 Admin menyu":
        await admin_menu(update, context)

# YANGI: Admin qo'shish command
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    try:
        if not context.args:
            await update.message.reply_text("❌ User ID ni kiriting! Format: /add_admin user_id")
            return
        
        new_admin_id = int(context.args[0].strip())
        
        conn = await init_db()
        try:
            # User mavjudligini tekshiramiz
            user = await get_user(new_admin_id)
            if not user:
                await update.message.reply_text("❌ Bu user ID botda mavjud emas!")
                return
            
            await conn.execute(
                'UPDATE users SET is_admin = TRUE WHERE user_id = $1',
                new_admin_id
            )
            
            await update.message.reply_text("✅ Yangi admin muvaffaqiyatli qo'shildi!")
            
            # Yangi admin ga xabar
            try:
                await context.bot.send_message(
                    new_admin_id,
                    "🎉 Tabriklaymiz! Siz admin sifatida tayinlandingiz!\n\n"
                    "Endi siz /admin buyrug'i orqali admin paneliga kirishingiz mumkin."
                )
            except Exception as e:
                logger.error(f"Error sending admin notification to {new_admin_id}: {e}")
            
            logger.info(f"New admin added: {new_admin_id}")
            
        except Exception as e:
            logger.error(f"Error adding admin: {e}")
            await update.message.reply_text(f"❌ Xatolik: {e}")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# YANGI: Admin olib tashlash command
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    try:
        if not context.args:
            await update.message.reply_text("❌ User ID ni kiriting! Format: /remove_admin user_id")
            return
        
        admin_id = int(context.args[0].strip())
        
        # O'zimizni olib tashlashni oldini olamiz
        if admin_id == update.effective_user.id:
            await update.message.reply_text("❌ O'zingizni adminlikdan olib tashlay olmaysiz!")
            return
        
        conn = await init_db()
        try:
            await conn.execute(
                'UPDATE users SET is_admin = FALSE WHERE user_id = $1',
                admin_id
            )
            
            await update.message.reply_text("✅ Admin muvaffaqiyatli olib tashlandi!")
            
            logger.info(f"Admin removed: {admin_id}")
            
        except Exception as e:
            logger.error(f"Error removing admin: {e}")
            await update.message.reply_text(f"❌ Xatolik: {e}")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# YANGI: Barcha adminlarni ko'rsatish
async def show_all_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = await init_db()
    try:
        admins = await conn.fetch('SELECT user_id FROM users WHERE is_admin = TRUE')
        
        text = "👥 Adminlar ro'yxati:\n\n"
        for admin in admins:
            admin_data = dict(admin)
            text += f"🆔 {admin_data['user_id']}\n────────────────────\n"
        
        await update.message.reply_text(text)
        
    except Exception as e:
        logger.error(f"Error showing all admins: {e}")
        await update.message.reply_text(f"❌ Xatolik: {e}")
    finally:
        await conn.close()

# YANGI: Xabar tarqatish command
async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id):
        return
    
    try:
        if not context.args:
            await update.message.reply_text("❌ Xabar matnini kiriting! Format: /broadcast xabar matni")
            return
        
        message = ' '.join(context.args)
        
        conn = await init_db()
        try:
            users = await conn.fetch('SELECT user_id FROM users')
            
            success_count = 0
            fail_count = 0
            
            for user in users:
                try:
                    await context.bot.send_message(
                        user['user_id'],
                        f"📢 Admin xabari:\n\n{message}"
                    )
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    logger.error(f"Error sending broadcast to {user['user_id']}: {e}")
            
            await update.message.reply_text(
                f"✅ Xabar tarqatish yakunlandi!\n\n"
                f"✅ Muvaffaqiyatli: {success_count} ta\n"
                f"❌ Muvaffaqiyatsiz: {fail_count} ta"
            )
            
            logger.info(f"Broadcast sent: {success_count} success, {fail_count} fail")
            
        except Exception as e:
            logger.error(f"Error getting users for broadcast: {e}")
            await update.message.reply_text(f"❌ Xatolik: {e}")
        finally:
            await conn.close()
            
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")

# Main function
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
                MessageHandler(filters.Regex("^📃 Vazifalar$"), show_tasks),
                MessageHandler(filters.Regex("^💬 Qo'llab Quvvatlash$"), support),
                CallbackQueryHandler(show_car_detail, pattern="^car_"),
                CallbackQueryHandler(buy_car_handler, pattern="^buy_"),
                CallbackQueryHandler(withdraw_money, pattern="^withdraw$"),
                CallbackQueryHandler(show_task_detail, pattern="^task_"),
                CallbackQueryHandler(start_task, pattern="^start_task_"),
            ],
            WITHDRAW_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_amount)
            ],
            WITHDRAW_CARD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_withdraw_card)
            ],
            TASK_SUBMIT: [
                MessageHandler(filters.PHOTO, handle_task_submission),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_task_submission)
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    application.add_handler(conv_handler)
    
    # YANGI: Admin uchun withdraw approval handler
    application.add_handler(CallbackQueryHandler(handle_withdraw_approval, pattern="^(approve|reject)_"))
    
    # YANGI: Vazifa approval handler
    application.add_handler(CallbackQueryHandler(handle_task_approval, pattern="^(approve|reject)_task_"))
    
    # Admin handlers
    application.add_handler(CommandHandler("admin", admin_menu))
    application.add_handler(CommandHandler("fill", fill_user_balance))
    application.add_handler(CommandHandler("add_task", add_task))
    application.add_handler(CommandHandler("add_channel", add_channel))
    application.add_handler(CommandHandler("delete_channel", delete_channel))
    application.add_handler(CommandHandler("add_admin", add_admin))
    application.add_handler(CommandHandler("remove_admin", remove_admin))
    application.add_handler(CommandHandler("broadcast", broadcast_message))
    application.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), handle_admin_commands))
    
    # YANGI: Admin management handlers
    application.add_handler(MessageHandler(filters.Regex("^(📃 Vazifalar boshqaruvi|📢 Kanallar boshqaruvi|👥 Adminlar boshqaruvi)$") & filters.User(ADMIN_ID), 
                                         lambda update, context: globals()[f"manage_{'tasks' if 'Vazifalar' in update.message.text else 'channels' if 'Kanallar' in update.message.text else 'admins'}"](update, context)))
    
    application.add_handler(MessageHandler(filters.Regex("^(➕ Yangi vazifa|📃 Vazifalar ro'yxati|✏️ Vazifani tahrirlash|🗑️ Vazifani o'chirish)$") & filters.User(ADMIN_ID), handle_task_management))
    application.add_handler(MessageHandler(filters.Regex("^(➕ Kanal qo'shish|📃 Kanallar ro'yxati|🗑️ Kanalni o'chirish)$") & filters.User(ADMIN_ID), handle_channel_management))
    application.add_handler(MessageHandler(filters.Regex("^(➕ Admin qo'shish|📃 Adminlar ro'yxati|🗑️ Adminni olib tashlash)$") & filters.User(ADMIN_ID), handle_admin_management))
    
    # Start the bot
    logger.info("Bot starting polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
