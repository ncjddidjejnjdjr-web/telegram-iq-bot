import os
import random
import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from questions import QUESTIONS


TOKEN = os.getenv("BOT_TOKEN")

# لینک کانال
CHANNEL_LINK = "https://t.me/+kSSmM7hw2Dg3YWZk"

# بعد از این تعداد پاسخ غلط، دور جدید شروع می‌شود.
MAX_WRONG = 3

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def new_game(context, user_id):
    """شروع یک دور جدید برای کاربر."""
    context.user_data["used_questions"] = []
    context.user_data["wrong_answers"] = 0
    context.user_data["passed"] = False


def get_next_question(context):
    """یک سؤال استفاده‌نشده انتخاب می‌کند."""
    used = context.user_data.get("used_questions", [])

    available = [
        i for i in range(len(QUESTIONS))
        if i not in used
    ]

    # اگر همه سؤال‌ها استفاده شده باشند، دور جدید
    if not available:
        context.user_data["used_questions"] = []
        available = list(range(len(QUESTIONS)))

    question_index = random.choice(available)
    context.user_data["used_questions"].append(question_index)

    return question_index


def question_keyboard(question_index):
    question = QUESTIONS[question_index]

    buttons = []

    for i, option in enumerate(question["options"]):
        buttons.append([
            InlineKeyboardButton(
                option,
                callback_data=f"answer:{question_index}:{i}"
            )
        ])

    return InlineKeyboardMarkup(buttons)


async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question_index = get_next_question(context)
    question = QUESTIONS[question_index]

    text = (
        "🧠 **آزمون هوش**\n\n"
        f"{question['question']}\n\n"
        "یکی از گزینه‌ها را انتخاب کن:"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=question_keyboard(question_index),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            text=text,
            reply_markup=question_keyboard(question_index),
            parse_mode="Markdown",
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # اطلاعات عمومی کاربر فقط داخل session بات نگهداری می‌شود.
    context.user_data["user_id"] = user.id
    context.user_data["username"] = user.username
    context.user_data["first_name"] = user.first_name

    new_game(context, user.id)

    await update.message.reply_text(
        "🔐 **گارد کانال**\n\n"
        "برای دسترسی به کانال، ابتدا آزمون را حل کن.\n\n"
        "هر پاسخ اشتباه یک سؤال جدید می‌آورد.",
        parse_mode="Markdown",
    )

    await send_question(update, context)


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, question_index, selected = query.data.split(":")
        question_index = int(question_index)
        selected = int(selected)
    except (ValueError, AttributeError):
        return

    question = QUESTIONS[question_index]

    if selected == question["answer"]:
        context.user_data["passed"] = True

        keyboard = [
            [
                InlineKeyboardButton(
                    "📢 عضویت در کانال",
                    url=CHANNEL_LINK
                )
            ],
            [
                InlineKeyboardButton(
                    "✅ بررسی عضویت",
                    callback_data="check_membership"
                )
            ],
        ]

        await query.edit_message_text(
            "✅ **پاسخ درست بود!**\n\n"
            "حالا در کانال عضو شو و سپس روی «بررسی عضویت» بزن.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    else:
        context.user_data["wrong_answers"] += 1

        wrong = context.user_data["wrong_answers"]

        if wrong >= MAX_WRONG:
            new_game(context, update.effective_user.id)

            await query.edit_message_text(
                "❌ **تعداد خطاها به حد مجاز رسید.**\n\n"
                "آزمون از ابتدا شروع شد.",
                parse_mode="Markdown",
            )

            await send_question(update, context)
            return

        await query.edit_message_text(
            f"❌ پاسخ اشتباه بود.\n\n"
            f"تعداد خطا: {wrong}/{MAX_WRONG}\n\n"
            "سؤال بعدی:",
        )

        await send_question(update, context)


async def check_membership(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()

    if not context.user_data.get("passed"):
        await query.answer(
            "ابتدا آزمون را کامل کن.",
            show_alert=True
        )
        return

    user_id = update.effective_user.id

    try:
        member = await context.bot.get_chat_member(
            chat_id=CHANNEL_LINK,
            user_id=user_id
        )

        if member.status in ["member", "administrator", "creator"]:
            await query.edit_message_text(
                "🎉 **عضویت تأیید شد!**\n\n"
                "دسترسی شما تأیید شد.",
                parse_mode="Markdown",
            )
        else:
            await query.answer(
                "هنوز عضویت شما تأیید نشده است.",
                show_alert=True
            )

    except Exception as e:
        logger.error("Membership check failed: %s", e)

        await query.answer(
            "بررسی عضویت انجام نشد. مطمئن شو بات ادمین کانال است.",
            show_alert=True
        )


def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set."
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        CallbackQueryHandler(
            answer,
            pattern=r"^answer:"
        )
    )
    app.add_handler(
        CallbackQueryHandler(
            check_membership,
            pattern=r"^check_membership$"
        )
    )

    logger.info("Bot started.")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
