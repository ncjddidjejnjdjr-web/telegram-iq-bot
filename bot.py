import os
import random
import logging
import threading

from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from questions import QUESTIONS


# =========================
# تنظیمات
# =========================

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

CHANNEL_LINK = "https://t.me/+kSSmM7hw2Dg3YWZk"


# =========================
# لاگ
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================
# سرور Health برای Render
# =========================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        return


def run_health_server():
    port = int(os.getenv("PORT", "10000"))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler,
    )

    logger.info("Health server running on port %s", port)

    server.serve_forever()


# =========================
# اطلاع به ادمین
# =========================

async def notify_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user

    username = f"@{user.username}" if user.username else "ندارد"
    full_name = user.full_name or "ندارد"

    message = (
        "👤 کاربر جدید\n\n"
        f"🆔 User ID: {user.id}\n"
        f"👤 Username: {username}\n"
        f"📛 Name: {full_name}"
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
        )

        logger.info(
            "Admin notification sent to %s for user %s",
            ADMIN_ID,
            user.id,
        )

    except Exception as e:
        logger.error(
            "Admin notification error: %s",
            e,
        )


# =========================
# فرستادن سؤال
# =========================

async def send_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    old_question = context.user_data.get("last_question")

    available_questions = [
        q for q in QUESTIONS
        if q != old_question
    ]

    if not available_questions:
        available_questions = QUESTIONS

    question = random.choice(available_questions)

    context.user_data["last_question"] = question

    text = question["question"]
    options = question["options"]
    correct_answer = question["answer"]

    keyboard = []

    for i, option in enumerate(options):
        keyboard.append([
            InlineKeyboardButton(
                option,
                callback_data=f"answer:{i}:{correct_answer}",
            )
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=reply_markup,
        )

    elif update.callback_query:
        await update.callback_query.message.edit_text(
            text,
            reply_markup=reply_markup,
        )


# =========================
# /start
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    context.user_data.clear()

    # اطلاع به ادمین
    await notify_admin(update, context)

    await update.message.reply_text(
        "🧠 برای ورود به کانال، "
        "اول این سؤال را درست جواب بده:"
    )

    await send_question(update, context)


# =========================
# بررسی جواب
# =========================

async def answer_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    try:
        _, selected, correct = query.data.split(":")

        selected = int(selected)
        correct = int(correct)

    except Exception:
        await query.message.reply_text(
            "⚠️ خطایی رخ داد. دوباره /start را بزن."
        )
        return

    # =========================
    # جواب درست
    # =========================

    if selected == correct:

        keyboard = [
            [
                InlineKeyboardButton(
                    "📢 ورود به کانال",
                    url=CHANNEL_LINK,
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ بررسی عضویت",
                    callback_data="check_membership",
                )
            ],
        ]

        await query.message.edit_text(
            "✅ پاسخ درست بود!\n\n"
            "حالا ابتدا وارد کانال شو و "
            "سپس روی «بررسی عضویت» بزن.",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

        return

    # =========================
    # جواب غلط
    # =========================

    await query.answer(
        "❌ پاسخ اشتباه بود! سؤال جدید آمد.",
        show_alert=False,
    )

    await send_question(update, context)


# =========================
# بررسی عضویت کانال
# =========================

async def check_membership(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id,
        )

        if member.status in [
            "member",
            "administrator",
            "creator",
        ]:

            await query.message.edit_text(
                "🎉 عضویت شما تأیید شد!\n\n"
                "خوش آمدید."
            )

        else:

            keyboard = [
                [
                    InlineKeyboardButton(
                        "📢 ورود به کانال",
                        url=CHANNEL_LINK,
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔄 بررسی دوباره",
                        callback_data="check_membership",
                    )
                ],
            ]

            await query.message.edit_text(
                "❌ هنوز عضویت شما تأیید نشده است.\n\n"
                "ابتدا وارد کانال شوید و "
                "سپس دوباره بررسی کنید.",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    except Exception as e:

        logger.error(
            "Membership check error: %s",
            e,
        )

        await query.message.edit_text(
            "⚠️ بررسی عضویت انجام نشد.\n"
            "مطمئن شوید ربات در کانال ادمین است."
        )


# =========================
# اجرای ربات
# =========================

def main():

    if not TOKEN:
        raise ValueError(
            "BOT_TOKEN تنظیم نشده است."
        )

    # اجرای سرور HTTP برای Render
    threading.Thread(
        target=run_health_server,
        daemon=True,
    ).start()

    application = Application.builder().token(TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CallbackQueryHandler(
            answer_question,
            pattern=r"^answer:"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            check_membership,
            pattern=r"^check_membership$"
        )
    )

    print("Bot is running...")

    application.run_polling()


if __name__ == "__main__":
    main()
