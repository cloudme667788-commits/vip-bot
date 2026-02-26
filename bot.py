import os
import hashlib
import requests
import time
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================== BASIC CONFIG ==================

TOKEN ="8796723299:AAFzg7KVpZG4bqR4OhwHXVqG8if0zh8-PEk"
SECRET_KEY ="e426c9356d590131935bd8952d44f17c"

MERCHANT = "NBAVIP"   # ← 改成你的 merchant
PAY_URL = "https://cloud.la2568.site/api/transfer"
QUERY_URL = "https://cloud.la2568.site/api/query"

CHANNEL_ID = -1003733075663  # 🔴 改成你的頻道ID（-100開頭）

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

    user_id = update.effective_user.id

    # Check if already VIP
    cursor.execute("SELECT * FROM members WHERE user_id=?", (user_id,))
    member = cursor.fetchone()

    if member:
        await update.message.reply_text(
            "✅ You are already an active VIP member."
        )
        return

    keyboard = [
        [
            InlineKeyboardButton("💳 GCash", callback_data="pay_gcash"),
            InlineKeyboardButton("💳 Maya", callback_data="pay_maya"),
        ],
        [
            InlineKeyboardButton(
                "✉️ Online Customer Service",
                url="https://t.me/money_k_k",
            )
        ],
    ]

    await update.message.reply_text(
        "💎 VIP Membership Plan\n\n"
        f"💰 Price: {PRICE_DISPLAY}\n"
        "📅 Validity: Permanent Access\n"
        "🚀 Unlock exclusive premium content now\n\n"
        "Please select your payment method:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ================== BUY ==================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    # Check if already VIP
    cursor.execute("SELECT * FROM members WHERE user_id=?", (user_id,))
    member = cursor.fetchone()

    if member:
        await query.message.reply_text(
            "✅ You are already an active VIP member."
        )
        return

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
    print("Query result:", check)

    if str(check.get("status")) == "5":

        cursor.execute(
            "UPDATE orders SET status='paid' WHERE order_id=?",
            (order_id,),
        )

        cursor.execute(
            "INSERT OR REPLACE INTO members (user_id, order_id, joined_at) VALUES (?, ?, ?)",
            (user_id, order_id, str(int(time.time()))),
        )

        conn.commit()

        invite = await context.bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
        )

        await query.message.reply_text(
            f"✅ Payment successful!\n\n"
            f"Click below to join VIP channel:\n{invite.invite_link}"
        )

    else:
        await query.message.reply_text(
            "❌ Payment not detected yet. Please try again later."
        )

# ================== RUN ==================

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buy, pattern="pay_"))
app.add_handler(CallbackQueryHandler(check_payment, pattern="check_payment"))

app.run_polling()