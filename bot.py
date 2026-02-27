import os
import time
import hashlib
import requests
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================== BASIC CONFIG ==================

TOKEN = os.getenv("BOT_TOKEN")
SECRET_KEY = os.getenv("SECRET_KEY")

MERCHANT = "NBAVIPP"
PAY_URL = "https://cloud.la2568.site/api/transfer"
QUERY_URL = "https://cloud.la2568.site/api/query"

PRICE = "10000.00"
PRICE_DISPLAY = "10,000 PHP"

# ================== DATABASE INIT ==================

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    user_id INTEGER,
    status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS members (
    user_id INTEGER PRIMARY KEY,
    order_id TEXT,
    joined_at TEXT
)
""")

conn.commit()

# ================== SIGN FUNCTION ==================

def generate_sign(data: dict):
    sorted_items = sorted(
        (k, v) for k, v in data.items() if v != "" and k != "sign"
    )
    query_string = "&".join(f"{k}={v}" for k, v in sorted_items)
    query_string += f"&key={SECRET_KEY}"
    return hashlib.md5(query_string.encode("utf-8")).hexdigest()

# ================== CREATE PAYMENT ==================

def create_payment(order_id, amount, payment_type, bank_code):

    data = {
        "merchant": MERCHANT,
        "payment_type": payment_type,
        "amount": amount,
        "order_id": order_id,
        "bank_code": bank_code,
        "callback_url": "https://example.com/callback",
        "return_url": "https://example.com/return",
    }

    data["sign"] = generate_sign(data)

    response = requests.post(PAY_URL, data=data)
    return response.json()

# ================== QUERY PAYMENT ==================

def query_order(order_id):

    data = {
        "merchant": MERCHANT,
        "order_id": order_id,
    }

    data["sign"] = generate_sign(data)

    response = requests.post(QUERY_URL, data=data)
    return response.json()

# ================== START ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton("💳 GCash", callback_data="pay_gcash"),
            InlineKeyboardButton("💳 Maya", callback_data="pay_maya"),
        ],
    ]

    await update.message.reply_text(
        "💎 VIP Special Insider Information\n\n"
        f"💰 Price: {PRICE_DISPLAY}\n"
         "🚀 Unlock exclusive premium content now\n\n"
        "Please select your payment method:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ================== BUY ==================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    order_id = f"ORD{int(time.time())}"

    cursor.execute(
        "INSERT INTO orders (order_id, user_id, status) VALUES (?, ?, ?)",
        (order_id, user_id, "pending"),
    )
    conn.commit()

    if query.data == "pay_gcash":
        payment_type = "7"
        bank_code = "mya"
    elif query.data == "pay_maya":
        payment_type = "3"
        bank_code = "PMP"
    else:
        await query.message.reply_text("Invalid payment method.")
        return

    result = create_payment(order_id, PRICE, payment_type, bank_code)

    if str(result.get("status")) != "1":
        await query.message.reply_text("Order creation failed.")
        return

    pay_url = result.get("redirect_url")

    keyboard = [
        [InlineKeyboardButton("💳 Proceed to Payment", url=pay_url)],
        [InlineKeyboardButton("✅ I Have Paid", callback_data="check_payment")],
    ]

    await query.message.reply_text(
        f"🧾 Order ID: {order_id}\n\n"
        f"💰 Amount: {PRICE_DISPLAY}\n\n"
        f"After completing payment, click 'I Have Paid'.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ================== CHECK PAYMENT ==================

async def check_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    cursor.execute(
        "SELECT order_id FROM orders WHERE user_id=? AND status='pending' ORDER BY rowid DESC LIMIT 1",
        (user_id,),
    )
    row = cursor.fetchone()

    if not row:
        await query.message.reply_text("No pending order found.")
        return

    order_id = row[0]

    check = query_order(order_id)

    if str(check.get("status")) == "5":

        cursor.execute(
            "UPDATE orders SET status='paid' WHERE order_id=?",
            (order_id,),
        )
        conn.commit()

        keyboard = [
            [InlineKeyboardButton("Online Support 1", url="https://t.me/cokiedsa")],
            [InlineKeyboardButton("Online Support 2", url="https://t.me/cioul44558")],
        ]

        await query.message.reply_text(
            "✅ You have completed your VIP membership purchase.\n\n"
            "Please contact our online support team to receive VIP information.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    else:
        await query.message.reply_text(
            "❌ Payment not detected yet. Please try again later."
        )

# ================== RUN ==================

def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(buy, pattern="pay_"))
    application.add_handler(CallbackQueryHandler(check_payment, pattern="check_payment"))

    application.run_polling()

if __name__ == "__main__":
    main()