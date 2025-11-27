import os
import logging
import psycopg2
from datetime import datetime, timedelta
from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CallbackQueryHandler,
    ConversationHandler
)
from flask import Flask
import asyncio
from threading import Thread

# Log konfiguratsiyasi
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# PostgreSQL ulanishi
DATABASE_URL = "postgresql://avaz_user:XsjxSdMPWuRt2LUSVkss3YkJFlYKLqVS@dpg-d4bj9d8dl3ps739e98fg-a/avaz"

# Conversation states
PHONE, MENU, PREMIUM_SELECT, STARS_AMOUNT, GROUP_YEAR, GROUP_CONFIRM, WITHDRAW_AMOUNT, SUPPORT = range(8)

# Admin ID
ADMIN_ID = 7632409181

# Kanallar
CHANNELS = ["@paidworkuz", "@paidworkchat"]

# Flask app
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=5000)

# Ma'lumotlar bazasi funksiyalari
def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Users jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE,
                phone VARCHAR(20),
                username VARCHAR(100),
                first_name VARCHAR(100),
                balance INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                referral_count INTEGER DEFAULT 0,
                successful_referrals INTEGER DEFAULT 0,
                last_bonus_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Referrals jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT,
                referred_id BIGINT,
                earned_amount INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Transactions jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                type VARCHAR(50),
                amount INTEGER,
                status VARCHAR(50) DEFAULT 'pending',
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Withdrawals jadvali
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                amount INTEGER,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

def get_user(user_id):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Get user error: {e}")
        return None

def create_user(user_id, phone, username, first_name):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (user_id, phone, username, first_name) 
            VALUES (%s, %s, %s, %s)
        ''', (user_id, phone, username, first_name))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Create user error: {e}")
        return False

def update_balance(user_id, amount):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = balance + %s WHERE user_id = %s', (amount, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Update balance error: {e}")
        return False

# Start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user:
        # User allaqachon ro'yxatdan o'tgan
        if await check_subscription(update, context):
            await show_menu(update, context)
        return
    
    # Yangi user
    keyboard = [[KeyboardButton("📱 Telefon raqamni jo'natish", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "👋 Assalomu alaykum! Botdan foydalanish uchun telefon raqamingizni tasdiqlang:",
        reply_markup=reply_markup
    )
    return PHONE

# Telefon raqamni qabul qilish
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone_number = contact.phone_number
    
    # Telefon raqamni tekshirish
    if not (phone_number.startswith('+998') or phone_number.startswith('+7')):
        await update.message.reply_text(
            "❌ Faqat +998 (O'zbekiston) yoki +7 (Rossiya) raqamlari qabul qilinadi.",
            reply_markup=ReplyKeyboardRemove()
        )
        return await start(update, context)
    
    # User ma'lumotlarini saqlash
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    if create_user(user_id, phone_number, username, first_name):
        await update.message.reply_text(
            "✅ Telefon raqamingiz muvaffaqiyatli qabul qilindi!",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Kanallarga obunani tekshirish
        if await check_subscription(update, context):
            await show_menu(update, context)
    else:
        await update.message.reply_text(
            "❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.",
            reply_markup=ReplyKeyboardRemove()
        )

# Kanallarga obunani tekshirish
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    for channel in CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked']:
                await send_subscription_request(update, context)
                return False
        except Exception as e:
            logger.error(f"Subscription check error for {channel}: {e}")
            await send_subscription_request(update, context)
            return False
    
    return True

async def send_subscription_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = []
    for channel in CHANNELS:
        buttons.append([InlineKeyboardButton(f"📢 {channel}", url=f"https://t.me/{channel[1:]}")])
    
    buttons.append([InlineKeyboardButton("✅ Tasdiqlash", callback_data="check_subscription")])
    
    keyboard = InlineKeyboardMarkup(buttons)
    
    if update.message:
        await update.message.reply_text(
            "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=keyboard
        )
    else:
        await update.callback_query.message.reply_text(
            "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=keyboard
        )

# Asosiy menyu
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_images = {
        'premium': 'https://i.ibb.co/j7bY2t8/premiumtg.jpg',
        'stars': 'https://i.ibb.co/kVVMVsR3/starstg.jpg',
        'group': 'https://i.ibb.co/GvppxQfj/group.jpg',
        'reward': 'https://i.ibb.co/k6VqhYQQ/mukofot.jpg',
        'withdraw': 'https://i.ibb.co/twJkPGQt/pulyechish.jpg',
        'referral': 'https://i.ibb.co/QvR43j12/taklif.jpg',
        'services': 'https://i.ibb.co/LzFYNNfM/hizmatlar.jpg'
    }
    
    keyboard = [
        ['🫟 Premium', '🌟 Stars'],
        ['🆔️ Gruh Sotish', '🎁 Mukofot'],
        ['👥️ Takliflar', '💸 Pul Yechish'],
        ['📃 Hizmatlar', '💬 Qo\'llab Quvvatlash']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    welcome_text = """✳️ Xush kelibsiz!
🚀 Telegram Premium sotib olishingiz
🆔️ Balki eski yildagi gruhingizni ham sotishingiz mumkin!
⚡️ Qulay imkoniyatlar:
👥️ Do'stlaringizni taklif va qushimcha daromad olishingiz mumkun 
So'ngi yangiliklar @Paidworkuz
👇Quyidagi Tugmalar orqali xizmatdan foydalaning!"""
    
    if update.callback_query:
        await update.callback_query.message.reply_photo(
            photo=menu_images['premium'],
            caption=welcome_text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_photo(
            photo=menu_images['premium'],
            caption=welcome_text,
            reply_markup=reply_markup
        )
    
    return MENU

# Premium bo'limi
async def premium_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    premium_plans = [
        {"period": "1 oy", "price": 55000},
        {"period": "3 oy", "price": 160000},
        {"period": "6 oy", "price": 220000},
        {"period": "12 oy", "price": 389000}
    ]
    
    keyboard = []
    for plan in premium_plans:
        keyboard.append([InlineKeyboardButton(
            f"{plan['period']} - {plan['price']:,} so'm", 
            callback_data=f"premium_{plan['period']}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """🫟 Telegram Premium Xizmat turini tanlang:
💎 Premium tariflari
1 oylik Obuna Account kirib olib beriladi

🔹 1 oy — 55,000.00 so'm
🔹 3 oy — 160,000.00 so'm
🔹 6 oy — 220,000.00 so'm
🔹 12 oy — 389,000.00 so'm

✅ Xariddan so'ng Premium 5 daqiqa ichida yoqiladi."""
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    return PREMIUM_SELECT

# Stars bo'limi
async def stars_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """✨ Qancha Stars olmoqchisiz? ✨

💬 Iltimos, sonini raqam bilan kiriting!  
🔹 Minimal: 25 ⭐  
🔹 Maksimal: 10 000 ⭐  

⚡️ Qanchalik ko'p olsangiz, shunchalik tezroq yulduzlar osmonga chiqadi!"""
    
    await update.message.reply_text(text)
    return STARS_AMOUNT

# Gruh sotish bo'limi
async def group_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("2024", callback_data="group_2024"), 
         InlineKeyboardButton("2023", callback_data="group_2023")],
        [InlineKeyboardButton("2022", callback_data="group_2022"), 
         InlineKeyboardButton("2021", callback_data="group_2021")],
        [InlineKeyboardButton("2015-2020", callback_data="group_2015_2020")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """🆔️ Eski yoki keraksiz Gruhingizni Soting
Muhim eslatma gruh tarixi barchaga korinishi kerak 
va kamida 5 ta post bolsa qimmatroq sotib olamiz 
yili kurinmaydigan va umuman post yo'q gruh olmaymiz

2024 > may oyigacha 40.000 Som 
2023 > 95.000 Som 
2022 > 120.000 Som 
2021 > 130.000 Som 
2015 - 2020 > 150.000 Som 

Quyidagi Knopkalar Orqali yilni tanlang"""
    
    await update.message.reply_text(text, reply_markup=reply_markup)
    return GROUP_YEAR

# Mukofot bo'limi
async def bonus_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user:
        last_bonus_time = user[9] if user[9] else datetime.now() - timedelta(hours=7)
        time_diff = datetime.now() - last_bonus_time
        
        if time_diff.total_seconds() >= 6 * 3600:  # 6 soat
            import random
            bonus_amount = random.randint(500, 1000)
            
            # Bonusni yangilash
            try:
                conn = psycopg2.connect(DATABASE_URL)
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE users SET balance = balance + %s, last_bonus_time = %s WHERE user_id = %s',
                    (bonus_amount, datetime.now(), user_id)
                )
                conn.commit()
                cursor.close()
                conn.close()
                
                keyboard = [[InlineKeyboardButton("💸 Mukofot Olish", callback_data="get_bonus")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"🎉 Tabriklaymiz! Siz {bonus_amount} so'm mukofot oldingiz!",
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Bonus error: {e}")
                await update.message.reply_text("❌ Xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")
        else:
            hours_left = 6 - (time_diff.total_seconds() / 3600)
            await update.message.reply_text(
                f"⏰ Siz mukofotni soat {hours_left:.1f} soatdan keyin olishingiz mumkin."
            )
    
    return MENU

# Takliflar bo'limi
async def referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user:
        referral_link = f"https://t.me/{(await context.bot.get_me()).username}?start={user_id}"
        
        text = f"""👥️ Takliflar

🔗 Sizning taklif havolangiz:
{referral_link}

📊 Statistika:
• Jami taklif qilganlar: {user[7]} kishi
• Muvaffaqiyatli savdo qilganlar: {user[8]} kishi
• Jami daromad: {user[6]:,} so'm

🎁 Sovg'alar:
• 30 ta taklif - 1 oylik Telegram Premium
• Keyingi sovg'a uchun: {user[8]}/10 muvaffaqiyatli savdo

⚕️ Eslatma: Taklif qilgan do'stlaringizning 5 tasi bot orqali savdo qilishi kerak."""
        
        await update.message.reply_text(text)
    
    return MENU

# Pul yechish bo'limi
async def withdraw_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if user:
        text = f"""💸 Pul Yechish

💰 Jami balans: {user[5]:,} so'm
💳 Pul yechish miqdori: 5,000 so'mdan

📋 Talablar:
• Balansda kamida 5,000 so'm bo'lishi kerak
• Kamida 1 ta muvaffaqiyatli savdo qilgan bo'lishingiz kerak

💬 Pul yechish uchun miqdorni kiriting:"""
        
        await update.message.reply_text(text)
        return WITHDRAW_AMOUNT
    
    return MENU

# Hizmatlar bo'limi
async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """📃 Hizmatlar

1. Tiktok Monetization Hisob Yaratib sozlab berish va maslahatlar - 50,000 So'm
2. Hisob ochib berish - 30,000 So'm  
3. Mukammal Bot Yaratib Berish - 50,000 So'mdan boshlanadi (bot turiga qarab)
4. YouTube America Kanal Sozlamasi va 24/7 Yordam - 30,000 So'm

📞 Murojaat uchun: @notwxrk"""
    
    await update.message.reply_text(text)
    return MENU

# Qo'llab quvvatlash
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "💬 Qo'llab quvvatlash xizmati uchun @notwxrk ga murojaat qiling."
    await update.message.reply_text(text)
    return MENU

# Callback query handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "check_subscription":
        if await check_subscription(update, context):
            await show_menu(update, context)
    
    elif data == "back_to_menu":
        await show_menu(update, context)
    
    elif data.startswith("premium_"):
        period = data.replace("premium_", "")
        prices = {
            "1 oy": 55000,
            "3 oy": 160000,
            "6 oy": 220000,
            "12 oy": 389000
        }
        
        price = prices.get(period, 0)
        
        text = f"""🛒 Xarid jarayoni
Siz hozir o'zingiz uchun "{period}" Telegram Premium sotib olmoqdasiz. 💎
💰 To'lov summasi: {price:,} UZS
📌 Xaridni yakunlash uchun quyidagi tugma orqali to'lovni amalga oshiring."""

        keyboard = [[InlineKeyboardButton("✳️ Click Orqali To'lash", callback_data=f"pay_premium_{period}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
    
    elif data.startswith("pay_premium_"):
        period = data.replace("pay_premium_", "")
        # To'lov logikasini qo'shish kerak
        await query.edit_message_text("✅ To'lov muvaffaqiyatli amalga oshirildi! Admin siz bilan tez orada bog'lanadi.")
        
        # Admin ga xabar yuborish
        admin_text = f"🆔 Yangi Premium buyurtma!\nUser: @{query.from_user.username}\nID: {query.from_user.id}\nDavomiylik: {period}"
        await context.bot.send_message(ADMIN_ID, admin_text)

# Admin komandalari
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Sizda bu komanda uchun ruxsat yo'q.")
        return
    
    if not context.args:
        await update.message.reply_text("📝 Xabar yuborish uchun: /broadcast <xabar matni>")
        return
    
    message = " ".join(context.args)
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users')
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        sent = 0
        failed = 0
        
        for user in users:
            try:
                await context.bot.send_message(user[0], f"📢 {message}")
                sent += 1
            except Exception as e:
                failed += 1
                logger.error(f"Broadcast error for user {user[0]}: {e}")
        
        await update.message.reply_text(f"✅ Xabar yuborildi: {sent}\n❌ Xatolik: {failed}")
    
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Sizda bu komanda uchun ruxsat yo'q.")
        return
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Jami foydalanuvchilar
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        # Bugun qo'shilgan foydalanuvchilar
        cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURRENT_DATE')
        today_users = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        text = f"""📊 Bot statistika:
👥 Jami foydalanuvchilar: {total_users}
📈 Bugun qo'shilgan: {today_users}"""
        
        await update.message.reply_text(text)
    
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await update.message.reply_text("❌ Statistika olishda xatolik.")

# Asosiy funksiya
def main():
    # Bot tokenini environment dan olish
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    # Ma'lumotlar bazasini ishga tushirish
    init_db()
    
    # Flask serverini ishga tushirish
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    # Bot application yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PHONE: [MessageHandler(filters.CONTACT, handle_contact)],
            MENU: [
                MessageHandler(filters.Regex('^🫟 Premium$'), premium_service),
                MessageHandler(filters.Regex('^🌟 Stars$'), stars_service),
                MessageHandler(filters.Regex('^🆔️ Gruh Sotish$'), group_sale),
                MessageHandler(filters.Regex('^🎁 Mukofot$'), bonus_reward),
                MessageHandler(filters.Regex('^👥️ Takliflar$'), referrals),
                MessageHandler(filters.Regex('^💸 Pul Yechish$'), withdraw_money),
                MessageHandler(filters.Regex('^📃 Hizmatlar$'), services),
                MessageHandler(filters.Regex('^💬 Qo\'llab Quvvatlash$'), support),
            ],
            PREMIUM_SELECT: [CallbackQueryHandler(handle_callback)],
            STARS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stars_amount)],
            GROUP_YEAR: [CallbackQueryHandler(handle_group_year)],
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CommandHandler('stats', stats))
    
    # Botni ishga tushirish
    application.run_polling()

async def handle_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        
        if amount < 25 or amount > 10000:
            await update.message.reply_text("❌ Iltimos, 25 dan 10,000 gacha bo'lgan son kiriting!")
            return STARS_AMOUNT
        
        # Narxni hisoblash (100 stars = 22,000 so'm)
        price = int((amount / 100) * 22000)
        
        text = f"""💎 Yulduzlaringiz tayyor! 💎

📦 Siz {amount}⭐ Stars tanladingiz.  
💰 To'lov summasi: {price:,} so'm

🔗 To'lovni amalga oshirish uchun pastdagi tugmani bosing:  

⚡️ To'lov tasdiqlangach, Stars darhol hisobingizga qo'shiladi!

💳 Karta raqam: 8600 1626 2662 7277"""

        keyboard = [[InlineKeyboardButton("📸 Skrinshot yuborish", callback_data=f"send_stars_screenshot_{amount}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)
        return MENU
    
    except ValueError:
        await update.message.reply_text("❌ Iltimos, faqat raqam kiriting!")
        return STARS_AMOUNT

async def handle_group_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    year_prices = {
        "2024": 40000,
        "2023": 95000,
        "2022": 120000,
        "2021": 130000,
        "2015_2020": 150000
    }
    
    year = query.data.replace("group_", "")
    price = year_prices.get(year, 0)
    
    text = f"""🆔️ Gruh Sotish

📅 Tanlangan yil: {year.replace('_', '-')}
💰 Narx: {price:,} so'm

💳 To'lov qilish uchun karta raqam: 8600 1626 2662 7277

📝 Gruh linkini @notwxrk ga yuboring va 'Bajarildi' tugmasini bosing."""

    keyboard = [
        [InlineKeyboardButton("✅ Bajarildi", callback_data=f"group_done_{year}")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

if __name__ == '__main__':
    main()
