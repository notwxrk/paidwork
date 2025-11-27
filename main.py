import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import psycopg2
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
from flask import Flask, request

# Konfiguratsiya
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Flask app
app = Flask(__name__)

# Log konfiguratsiyasi
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Konstanta holatlar
PHONE, STARS_AMOUNT, GROUP_YEAR, GROUP_USERNAME, SUPPORT_MESSAGE = range(5)

# Premium narxlari
PREMIUM_PRICES = {
    '1': 55000,
    '3': 160000,
    '6': 220000,
    '12': 389000
}

# Stars narxi (1 star = 220 so'm)
STAR_PRICE = 220

# Kanallar ro'yxati
CHANNELS = [
    {'username': '@paidworkuz', 'chat_id': '@paidworkuz'},
    {'username': '@paidworkchat', 'chat_id': '@paidworkchat'}
]

# Ma'lumotlar bazasi ulanishi
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

# Ma'lumotlar bazasini yaratish
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Users jadvali
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                phone VARCHAR(20),
                full_name VARCHAR(255),
                username VARCHAR(255),
                balance INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                referral_count INTEGER DEFAULT 0,
                successful_referrals INTEGER DEFAULT 0,
                last_bonus_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Premium buyurtmalar jadvali
        cur.execute('''
            CREATE TABLE IF NOT EXISTS premium_orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                months INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Stars buyurtmalar jadvali
        cur.execute('''
            CREATE TABLE IF NOT EXISTS stars_orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                total_amount INTEGER NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Gruh sotish buyurtmalari
        cur.execute('''
            CREATE TABLE IF NOT EXISTS group_orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                group_year VARCHAR(50) NOT NULL,
                group_username VARCHAR(255),
                card_number VARCHAR(16),
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Pul yechish so'rovlari
        cur.execute('''
            CREATE TABLE IF NOT EXISTS withdrawal_requests (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Referral sistema
        cur.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id SERIAL PRIMARY KEY,
                referrer_id BIGINT NOT NULL,
                referred_id BIGINT NOT NULL,
                earned_amount INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        cur.close()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

# User ma'lumotlarini tekshirish
async def get_user(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return user
    except Exception as e:
        logger.error(f"Get user error: {e}")
        return None

# Yangi user qo'shish
async def add_user(user_id, phone, full_name, username):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO users (user_id, phone, full_name, username) 
            VALUES (%s, %s, %s, %s) 
            ON CONFLICT (user_id) DO NOTHING
        ''', (user_id, phone, full_name, username))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Add user error: {e}")
        return False

# Kanal a'zoligini tekshirish
async def check_subscription(user_id):
    try:
        for channel in CHANNELS:
            member = await app.bot.get_chat_member(channel['chat_id'], user_id)
            if member.status in ['left', 'kicked']:
                return False
        return True
    except Exception as e:
        logger.error(f"Subscription check error: {e}")
        return False

# Start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # User ma'lumotlarini bazadan olish
    db_user = await get_user(user_id)
    
    if not db_user or not db_user[2]:  # Telefon raqami yo'q
        await request_phone(update, context)
        return PHONE
    
    # Kanal a'zoligini tekshirish
    is_subscribed = await check_subscription(user_id)
    if not is_subscribed:
        await show_channels(update, context)
        return
    
    await show_main_menu(update, context)

# Telefon raqam so'rash
async def request_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("📞 Telefon raqamni yuborish", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "👋 Botdan foydalanish uchun telefon raqamingizni yuboring:",
        reply_markup=reply_markup
    )

# Telefon raqam qabul qilish
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    phone_number = contact.phone_number
    
    # Telefon raqam formati tekshirish
    if not (phone_number.startswith('+998') or phone_number.startswith('+7')):
        await update.message.reply_text(
            "❌ Faqat +998 yoki +7 formatidagi raqamlar qabul qilinadi. Iltimos, qaytadan urinib ko'ring.",
            reply_markup=ReplyKeyboardRemove()
        )
        await request_phone(update, context)
        return PHONE
    
    # User ma'lumotlarini saqlash
    user = update.effective_user
    success = await add_user(
        user.id, 
        phone_number, 
        f"{user.first_name} {user.last_name or ''}".strip(),
        user.username
    )
    
    if success:
        await update.message.reply_text(
            "✅ Telefon raqamingiz muvaffaqiyatli qabul qilindi!",
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Kanal a'zoligini tekshirish
        is_subscribed = await check_subscription(user.id)
        if not is_subscribed:
            await show_channels(update, context)
            return
        
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.")
        return PHONE

# Kanallarni ko'rsatish
async def show_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels_text = "📢 Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:\n\n"
    for channel in CHANNELS:
        channels_text += f"🔹 {channel['username']}\n"
    
    channels_text += "\nObuna bo'lgach, /start buyrug'ini bosing."
    
    keyboard = []
    for channel in CHANNELS:
        keyboard.append([InlineKeyboardButton(f"📢 {channel['username']}", url=f"https://t.me/{channel['username'][1:]}")])
    
    keyboard.append([InlineKeyboardButton("✅ Obuna bo'ldim", callback_data="check_subscription")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(channels_text, reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text(channels_text, reply_markup=reply_markup)

# Asosiy menyu
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    welcome_text = """✳️ Xush kelibsiz!
🚀 Telegram Premium sotib olishingiz
🆔️ Balki eski yildagi gruhingizni ham sotishingiz mumkin!
⚡️ Qulay imkoniyatlar:
👥️ Do'stlaringizni taklif va qushimcha daromad olishingiz mumkun 
So'ngi yangiliklar @Paidworkuz
👇 Quyidagi Tugmalar orqali xizmatdan foydalaning!"""

    keyboard = [
        ["🫟 Premium", "🌟 Stars"],
        ["🆔️ Gruh Sotish", "🎁 Mukofot"],
        ["👥️ Takliflar", "💸 Pul Yechish"],
        ["📃 Hizmatlar", "💬 Qo'llab Quvvatlash"]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    if update.message:
        await update.message.reply_photo(
            photo="https://i.ibb.co/j7bY2t8/premiumtg.jpg",
            caption=welcome_text,
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.message.reply_photo(
            photo="https://i.ibb.co/j7bY2t8/premiumtg.jpg",
            caption=welcome_text,
            reply_markup=reply_markup
        )

# Premium bo'limi
async def premium_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """🫟 Telegram Premium Xizmat turini tanlang:
💎 Premium tariflari
1 oylik Obuna Account kirib olib beriladi

🔹 1 oy — 55,000.00 so'm
🔹 3 oy — 160,000.00 so'm
🔹 6 oy — 220,000.00 so'm
🔹 12 oy — 389,000.00 so'm

✅ Xariddan so'ng Premium 5 daqiqa ichida yoqiladi."""

    keyboard = [
        [InlineKeyboardButton("1 oy - 55,000 so'm", callback_data="premium_1")],
        [InlineKeyboardButton("3 oy - 160,000 so'm", callback_data="premium_3")],
        [InlineKeyboardButton("6 oy - 220,000 so'm", callback_data="premium_6")],
        [InlineKeyboardButton("12 oy - 389,000 so'm", callback_data="premium_12")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_photo(
        photo="https://i.ibb.co/j7bY2t8/premiumtg.jpg",
        caption=text,
        reply_markup=reply_markup
    )

# Stars bo'limi
async def stars_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """✨ Qancha Stars olmoqchisiz? ✨

💬 Iltimos, sonini raqam bilan kiriting!  
🔹 Minimal: 25 ⭐  
🔹 Maksimal: 10 000 ⭐  

⚡️ Qanchalik ko'p olsangiz, shunchalik tezroq yulduzlar osmonga chiqadi!"""

    await update.message.reply_photo(
        photo="https://i.ibb.co/kVVMVsR3/starstg.jpg",
        caption=text
    )
    
    return STARS_AMOUNT

# Stars miqdorini qabul qilish
async def handle_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        
        if amount < 25 or amount > 10000:
            await update.message.reply_text("❌ Iltimos, 25 dan 10,000 gacha bo'lgan son kiriting!")
            return STARS_AMOUNT
        
        total_price = amount * STAR_PRICE
        
        text = f"""💎 Yulduzlaringiz tayyor! 💎

📦 Siz {amount}⭐ Stars tanladingiz.  
💰 To'lov summasi: {total_price:,.2f} so'm

🔗 To'lovni amalga oshirish uchun pastdagi tugmani bosing:  

⚡️ To'lov tasdiqlangach, Stars darhol hisobingizga qo'shiladi!

💳 Karta raqami: `8600 1626 2672 7277`"""

        keyboard = [
            [InlineKeyboardButton("💳 To'lov qildim", callback_data=f"stars_paid_{amount}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Stars buyurtmasini saqlash
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO stars_orders (user_id, amount, total_amount) VALUES (%s, %s, %s)',
            (update.effective_user.id, amount, total_price)
        )
        conn.commit()
        cur.close()
        conn.close()
        
        await update.message.reply_text(text, reply_markup=reply_markup)
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("❌ Iltimos, faqat raqam kiriting!")
        return STARS_AMOUNT

# Gruh sotish bo'limi
async def group_sell_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """🆔️ Eski yoki keraksiz Gruhingizni Soting

Muhim eslatma:
• Gruh tarixi barchaga ko'rinishi kerak
• Kamida 5 ta post bo'lsa qimmatroq sotib olamiz
• Yili ko'rinmaydigan va umuman post yo'q gruh olmaymiz

💰 Narxlar:
• 2024 > may oyigacha: 40,000 So'm
• 2023 > 95,000 So'm  
• 2022 > 120,000 So'm
• 2021 > 130,000 So'm
• 2015-2020 > 150,000 So'm

Quyidagi tugmalar orqali yilni tanlang:"""

    keyboard = [
        [InlineKeyboardButton("2024", callback_data="group_2024"), 
         InlineKeyboardButton("2023", callback_data="group_2023")],
        [InlineKeyboardButton("2022", callback_data="group_2022"), 
         InlineKeyboardButton("2021", callback_data="group_2021")],
        [InlineKeyboardButton("2015-2020", callback_data="group_2015_2020")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_photo(
        photo="https://i.ibb.co/GvppxQfj/group.jpg",
        caption=text,
        reply_markup=reply_markup
    )

# Mukofot bo'limi
async def bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Userning oxirgi mukofot olish vaqtini tekshirish
    cur.execute('SELECT last_bonus_time FROM users WHERE user_id = %s', (user_id,))
    user_data = cur.fetchone()
    
    if user_data and user_data[0]:
        last_bonus_time = user_data[0]
        next_bonus_time = last_bonus_time + timedelta(hours=6)
        
        if datetime.now() < next_bonus_time:
            time_left = next_bonus_time - datetime.now()
            hours_left = int(time_left.total_seconds() // 3600)
            minutes_left = int((time_left.total_seconds() % 3600) // 60)
            
            text = f"""🎁 Mukofot

❌ Siz hozir mukofot ola olmaysiz

⏰ Keyingi mukofot: {hours_left} soat {minutes_left} daqiqadan keyin

💡 Har 6 soatda bir 500-1,000 so'm oralig'ida mukofot olishingiz mumkin!"""
            
            await update.message.reply_photo(
                photo="https://i.ibb.co/k6VqhYQQ/mukofot.jpg",
                caption=text
            )
            return
    
    # Mukofot berish
    import random
    bonus_amount = random.randint(500, 1000)
    
    # Balansni yangilash
    cur.execute(
        'UPDATE users SET balance = balance + %s, total_earned = total_earned + %s, last_bonus_time = %s WHERE user_id = %s',
        (bonus_amount, bonus_amount, datetime.now(), user_id)
    )
    conn.commit()
    
    text = f"""🎉 Tabriklaymiz!

💰 Siz {bonus_amount} so'm mukofot oldingiz!

💳 Hisobingiz: {bonus_amount} so'm

⏰ Keyingi mukofot: 6 soatdan keyin

💡 Har 6 soatda bir yangi mukofot olishingiz mumkin!"""

    keyboard = [[InlineKeyboardButton("💸 Mukofot Olish", callback_data="get_bonus")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_photo(
        photo="https://i.ibb.co/k6VqhYQQ/mukofot.jpg",
        caption=text,
        reply_markup=reply_markup
    )
    
    cur.close()
    conn.close()

# Takliflar bo'limi
async def referrals_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # User ma'lumotlarini olish
    cur.execute(
        'SELECT referral_count, successful_referrals, balance FROM users WHERE user_id = %s',
        (user_id,)
    )
    user_data = cur.fetchone()
    
    if user_data:
        referral_count = user_data[0] or 0
        successful_refs = user_data[1] or 0
        balance = user_data[2] or 0
        
        # Taklif havolasi
        referral_link = f"https://t.me/{(await context.bot.get_me()).username}?start={user_id}"
        
        # Qolgan takliflar soni
        next_reward = 30 if successful_refs < 30 else (successful_refs // 5 + 1) * 5
        remaining_refs = next_reward - successful_refs
        
        text = f"""👥️ Takliflar

🔗 Sizning taklif havolangiz:
`{referral_link}`

📊 Statistika:
• Jami taklif qilganlar: {referral_count} ta
• Muvaffaqiyatli savdo qilganlar: {successful_refs} ta
• Takliflar orqali topilgan: {balance:,} so'm

🎁 Sovg'alar:
• 30 ta taklif uchun: 1 oylik Telegram Premium
• Keyingi sovg'a: {next_reward} ta taklif uchun
• Qolgan: {remaining_refs} ta

💡 Har bir taklif qilgan do'stingiz savdo qilsa, siz 9% mukofot olasiz!"""

        await update.message.reply_photo(
            photo="https://i.ibb.co/QvR43j12/taklif.jpg",
            caption=text
        )
    
    cur.close()
    conn.close()

# Pul yechish bo'limi
async def withdrawal_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # User ma'lumotlarini olish
    cur.execute(
        'SELECT balance FROM users WHERE user_id = %s',
        (user_id,)
    )
    user_data = cur.fetchone()
    
    # Savdolar sonini tekshirish
    cur.execute(
        'SELECT COUNT(*) FROM (SELECT user_id FROM premium_orders WHERE user_id = %s AND status = %s UNION SELECT user_id FROM stars_orders WHERE user_id = %s AND status = %s) as orders',
        (user_id, 'completed', user_id, 'completed')
    )
    successful_orders = cur.fetchone()[0]
    
    balance = user_data[0] if user_data else 0
    
    text = f"""💸 Pul Yechish

💰 Jami balans: {balance:,} so'm
💳 Minimal yechish miqdori: 5,000 so'm
✅ Muvaffaqiyatli savdolar: {successful_orders} ta

{"❌ Pul yechish uchun kamida 1 ta muvaffaqiyatli savdo qilishingiz kerak!" if successful_orders == 0 else "✅ Pul yechish so'rovi yuborishingiz mumkin!"}"""

    keyboard = []
    if successful_orders > 0 and balance >= 5000:
        keyboard.append([InlineKeyboardButton("💸 Pul Yechish", callback_data="request_withdrawal")])
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_photo(
        photo="https://i.ibb.co/twJkPGQt/pulyechish.jpg",
        caption=text,
        reply_markup=reply_markup
    )
    
    cur.close()
    conn.close()

# Hizmatlar bo'limi
async def services_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """📃 Hizmatlar

1. TikTok Monetization Hisob Yaratib sozlab berish va maslahatlar - 50,000 So'm
2. Hisob ochib berish - 30,000 So'm  
3. Mukammal Bot Yaratib Berish - 50,000 So'mdan boshlanadi (bot turiga qarab)
4. YouTube America Kanal Sozlamasi va 24/7 Yordam - 30,000 So'm

📞 Murojaat uchun: @notwxrk"""

    await update.message.reply_photo(
        photo="https://i.ibb.co/LzFYNNfM/hizmatlar.jpg",
        caption=text
    )

# Qo'llab quvvatlash
async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """💬 Qo'llab Quvvatlash

Agar sizda savollar yoki muammolar bo'lsa, quyidagi admin bilan bog'lanishingiz mumkin:

👨‍💻 Admin: @notwxrk

📞 Yordam olish uchun xabar yuboring!"""

    await update.message.reply_text(text)

# Callback query handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "check_subscription":
        is_subscribed = await check_subscription(user_id)
        if is_subscribed:
            await show_main_menu(update, context)
        else:
            await show_channels(update, context)
    
    elif data == "back_to_main":
        await show_main_menu(update, context)
    
    elif data.startswith("premium_"):
        months = data.split("_")[1]
        amount = PREMIUM_PRICES[months]
        
        text = f"""🛒 Xarid jarayoni

Siz hozir o'zingiz uchun "{months} oylik" Telegram Premium sotib olmoqdasiz. 💎
💰 To'lov summasi: {amount:,.2f} UZS

📌 Xaridni yakunlash uchun quyidagi tugma orqali to'lovni amalga oshiring.

💳 Karta raqami: `8600 1626 2672 7277`"""

        keyboard = [
            [InlineKeyboardButton("💳 Click Orqali To'lash", callback_data=f"premium_pay_{months}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Premium buyurtmasini saqlash
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO premium_orders (user_id, months, amount) VALUES (%s, %s, %s)',
            (user_id, months, amount)
        )
        conn.commit()
        cur.close()
        conn.close()
        
        await query.message.edit_caption(caption=text, reply_markup=reply_markup)
    
    elif data.startswith("premium_pay_"):
        months = data.split("_")[2]
        amount = PREMIUM_PRICES[months]
        
        # Admin ga xabar yuborish
        admin_text = f"""🛒 Yangi Premium buyurtma!

👤 Foydalanuvchi: @{query.from_user.username or 'Noma'lum'}
🆔 ID: {user_id}
📦 Mahsulot: {months} oylik Premium
💰 Summa: {amount:,.2f} so'm

✅ To'lovni tasdiqlang yoki rad eting."""

        keyboard = [
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_premium_{query.message.message_id}_{user_id}_{months}")],
            [InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_premium_{query.message.message_id}_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(ADMIN_ID, admin_text, reply_markup=reply_markup)
        
        await query.message.edit_caption(
            caption="✅ To'lov so'rovingiz qabul qilindi! Admin tomonidan tekshirilmoqda...",
            reply_markup=None
        )
    
    elif data.startswith("stars_paid_"):
        amount = int(data.split("_")[2])
        total_price = amount * STAR_PRICE
        
        # Admin ga xabar yuborish
        admin_text = f"""⭐ Yangi Stars buyurtma!

👤 Foydalanuvchi: @{query.from_user.username or 'Noma'lum'}
🆔 ID: {user_id}
📦 Miqdor: {amount} Stars
💰 Summa: {total_price:,.2f} so'm

✅ To'lovni tasdiqlang yoki rad eting."""

        keyboard = [
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_stars_{query.message.message_id}_{user_id}_{amount}")],
            [InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_stars_{query.message.message_id}_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(ADMIN_ID, admin_text, reply_markup=reply_markup)
        
        await query.message.edit_text(
            "✅ To'lov so'rovingiz qabul qilindi! Admin tomonidan tekshirilmoqda...",
            reply_markup=None
        )
    
    elif data.startswith("group_"):
        year = data.split("_")[1]
        if year == "2015":
            year = "2015-2020"
            price = 150000
        else:
            prices = {'2024': 40000, '2023': 95000, '2022': 120000, '2021': 130000}
            price = prices[year]
        
        text = f"""🆔️ Gruh Sotish - {year}

💰 Narx: {price:,} so'm
💳 Karta raqami: `8600 1626 2672 7277`

📝 Gruh linkini @notwxrk ga yuboring va to'lov qilganingizdan so'ng \"Bajarildi\" tugmasini bosing."""

        keyboard = [
            [InlineKeyboardButton("✅ Bajarildi", callback_data=f"group_done_{year}")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_caption(caption=text, reply_markup=reply_markup)
    
    elif data.startswith("group_done_"):
        year = data.split("_")[2]
        
        # Admin ga xabar yuborish
        admin_text = f"""🆔️ Yangi Gruh Sotish buyurtmasi!

👤 Foydalanuvchi: @{query.from_user.username or 'Noma'lum'}
🆔 ID: {user_id}
📅 Yil: {year}
💰 Narx: {prices[year] if year != '2015-2020' else 150000:,} so'm

✅ Gruhni tekshirib, to'lovni tasdiqlang."""

        keyboard = [
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_group_{query.message.message_id}_{user_id}_{year}")],
            [InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_group_{query.message.message_id}_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(ADMIN_ID, admin_text, reply_markup=reply_markup)
        
        await query.message.edit_caption(
            caption="✅ So'rovingiz qabul qilindi! Admin gruhni tekshirib, to'lovni tasdiqlaydi.",
            reply_markup=None
        )
    
    elif data == "get_bonus":
        await bonus_handler(update, context)
    
    elif data == "request_withdrawal":
        user_id = query.from_user.id
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # User balansini tekshirish
        cur.execute('SELECT balance FROM users WHERE user_id = %s', (user_id,))
        user_data = cur.fetchone()
        
        if user_data and user_data[0] >= 5000:
            # Pul yechish so'rovini yaratish
            cur.execute(
                'INSERT INTO withdrawal_requests (user_id, amount) VALUES (%s, %s)',
                (user_id, user_data[0])
            )
            conn.commit()
            
            # Admin ga xabar
            admin_text = f"""💸 Yangi Pul Yechish so'rovi!

👤 Foydalanuvchi: @{query.from_user.username or 'Noma'lum'}
🆔 ID: {user_id}
💰 Miqdor: {user_data[0]:,} so'm

✅ To'lovni amalga oshiring va tasdiqlang."""

            keyboard = [
                [InlineKeyboardButton("✅ To'lov qilindi", callback_data=f"confirm_withdrawal_{user_id}")],
                [InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_withdrawal_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(ADMIN_ID, admin_text, reply_markup=reply_markup)
            
            await query.message.edit_caption(
                caption="✅ Pul yechish so'rovingiz qabul qilindi! Admin to'lovni amalga oshiradi.",
                reply_markup=None
            )
        
        cur.close()
        conn.close()

# Admin komandalari
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Xabar matnini kiriting!\nMasalan: /broadcast Salom hammaga!")
        return
    
    message_text = ' '.join(context.args)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute('SELECT user_id FROM users')
    users = cur.fetchall()
    
    success_count = 0
    fail_count = 0
    
    for user in users:
        try:
            await context.bot.send_message(user[0], message_text)
            success_count += 1
        except Exception as e:
            logger.error(f"Broadcast error for user {user[0]}: {e}")
            fail_count += 1
    
    cur.close()
    conn.close()
    
    await update.message.reply_text(
        f"📊 Broadcast natijasi:\n✅ Muvaffaqiyatli: {success_count}\n❌ Xatolik: {fail_count}"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Siz admin emassiz!")
        return
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Jami foydalanuvchilar
    cur.execute('SELECT COUNT(*) FROM users')
    total_users = cur.fetchone()[0]
    
    # Bugun qo'shilgan foydalanuvchilar
    cur.execute('SELECT COUNT(*) FROM users WHERE created_at::date = CURRENT_DATE')
    today_users = cur.fetchone()[0]
    
    # Balans statistikasi
    cur.execute('SELECT SUM(balance), SUM(total_earned) FROM users')
    balance_stats = cur.fetchone()
    total_balance = balance_stats[0] or 0
    total_earned = balance_stats[1] or 0
    
    # Buyurtmalar statistikasi
    cur.execute("SELECT COUNT(*) FROM premium_orders WHERE status = 'completed'")
    premium_orders = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM stars_orders WHERE status = 'completed'")
    stars_orders = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM group_orders WHERE status = 'completed'")
    group_orders = cur.fetchone()[0]
    
    text = f"""📊 Bot Statistikasi

👥 Foydalanuvchilar:
• Jami: {total_users} ta
• Bugun: {today_users} ta

💰 Balanslar:
• Jami balans: {total_balance:,} so'm
• Jami topilgan: {total_earned:,} so'm

🛒 Buyurtmalar:
• Premium: {premium_orders} ta
• Stars: {stars_orders} ta  
• Gruh sotish: {group_orders} ta"""

    await update.message.reply_text(text)
    
    cur.close()
    conn.close()

# Xatolik handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

# Flask server
@app.route('/')
def home():
    return "Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    # Webhook uchun endpoint
    return 'OK'

# Asosiy funksiya
def main():
    # Ma'lumotlar bazasini ishga tushirish
    init_db()
    
    # Bot application yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for stars
    stars_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🌟 Stars$'), stars_handler)],
        states={
            STARS_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stars_amount)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    # Handlerlar
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(stars_conv)
    
    # Message handlerlar
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.Regex('^🫟 Premium$'), premium_handler))
    application.add_handler(MessageHandler(filters.Regex('^🆔️ Gruh Sotish$'), group_sell_handler))
    application.add_handler(MessageHandler(filters.Regex('^🎁 Mukofot$'), bonus_handler))
    application.add_handler(MessageHandler(filters.Regex('^👥️ Takliflar$'), referrals_handler))
    application.add_handler(MessageHandler(filters.Regex('^💸 Pul Yechish$'), withdrawal_handler))
    application.add_handler(MessageHandler(filters.Regex('^📃 Hizmatlar$'), services_handler))
    application.add_handler(MessageHandler(filters.Regex('^💬 Qo'llab Quvvatlash$'), support_handler))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Xatolik handler
    application.add_error_handler(error_handler)
    
    # Botni ishga tushirish
    print("Bot ishga tushdi...")
    application.run_polling()

if __name__ == '__main__':
    main()
