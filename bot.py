import logging
import os
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

BOT_TOKEN = "8149969315:AAHTSrPCbzhRhz0CFxvKnWIYemjvbgs2hZw"
GROQ_KEY = "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"
ADMIN_TG = "SU_57_T_90M"
PORT = int(os.environ.get("PORT", 8080))
LIMITS = {"free": 3, "pro": 999999, "biz": 999999}
users = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

def run_http():
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

def ask_ai(prompt):
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "max_tokens": 1500,
              "messages": [
                  {"role": "system", "content": "Ты эксперт по маркетплейсам Wildberries и Ozon. Отвечай на русском."},
                  {"role": "user", "content": prompt}
              ]}, timeout=30)
    data = r.json()
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    raise Exception(str(data))

def get_user(uid):
    if uid not in users:
        users[uid] = {"plan": "free", "today_count": 0, "today_date": ""}
    return users[uid]

def check_limit(uid):
    from datetime import date
    u = get_user(uid)
    today = str(date.today())
    if u["today_date"] != today:
        u["today_count"] = 0
        u["today_date"] = today
    return u["today_count"] < LIMITS.get(u["plan"], 3)

def use_limit(uid):
    get_user(uid)["today_count"] += 1

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Аудит карточки", callback_data="audit")],
        [InlineKeyboardButton("⭐ Анализ отзывов", callback_data="reviews")],
        [InlineKeyboardButton("📝 Описание товара", callback_data="description")],
        [InlineKeyboardButton("🔑 SEO ключевые слова", callback_data="keywords")],
        [InlineKeyboardButton("🎯 Оффер и УТП", callback_data="offer")],
        [InlineKeyboardButton("💰 Расчёт прибыли", callback_data="finance")],
        [InlineKeyboardButton("⭐ Тарифы", callback_data="plans")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "Продавец"
    await update.message.reply_text(
        f"👋 Привет, {name}!\n\n🚀 *Продажник.AI* — помощник для продавцов WB и Ozon.\n\nВыбери инструмент:",
        parse_mode="Markdown", reply_markup=kb_main())

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери инструмент:", reply_markup=kb_main())

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = query.data
    msgs = {
        "audit": "🔍 *Аудит карточки*\n\nОтправь ссылку на товар с WB или Ozon.",
        "reviews": "⭐ *Анализ отзывов*\n\nСкопируй и отправь отзывы покупателей.",
        "description": "📝 *Описание товара*\n\nНапиши название товара и характеристики.",
        "keywords": "🔑 *SEO*\n\nНапиши название своего товара.",
        "offer": "🎯 *Оффер*\n\nНапиши: что продаёшь, преимущество, целевую аудиторию.",
        "finance": "💰 *Расчёт прибыли*\n\nЧерез запятую:\nЦена, Себестоимость, Продаж/мес, Комиссия%, Логистика\n\nПример: *2490, 890, 150, 15, 80*",
    }
    if d in msgs:
        context.user_data["mode"] = d
        await query.message.reply_text(msgs[d], parse_mode="Markdown")
    elif d == "plans":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Про — 990 ₽/мес", url=f"https://t.me/{ADMIN_TG}")],
            [InlineKeyboardButton("💎 Бизнес — 2990 ₽/мес", url=f"https://t.me/{ADMIN_TG}")],
        ])
        await query.message.reply_text(
            "⭐ *Тарифы*\n\n🆓 Старт — бесплатно — 3/день\n⭐ Про — 990₽/мес — безлимит\n💎 Бизнес — 2990₽/мес — всё+наставник",
            parse_mode="Markdown", reply_markup=kb)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    mode = context.user_data.get("mode", "")
    if not mode:
        await update.message.reply_text("Выбери инструмент /menu")
        return
    if not check_limit(uid):
        await update.message.reply_text(
            "❌ Лимит 3/день исчерпан. Подключи Про!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⭐ Про", callback_data="plans")]]))
        return
    msg = await update.message.reply_text("⏳ Анализирую, подожди 15-20 секунд...")
    try:
        if mode == "audit":
            if not text.startswith("http"):
                await msg.edit_text("❌ Отправь ссылку с https://")
                return
            p = "Ozon" if "ozon" in text else "Wildberries"
            prompt = f"Аудит карточки на {p}: {text}\n\nОцени (0-100):\n1.ЗАГОЛОВОК\n2.ОПИСАНИЕ\n3.ФОТО\n4.SEO\n5.ЦЕНА\n6.ОТЗЫВЫ\n\nИтог: X/100\nПЛАН ДЕЙСТВИЙ (топ-5):"
        elif mode == "reviews":
            prompt = f"Анализ отзывов:\n{text}\n\n1.ЖАЛОБЫ(топ-5)\n2.ХВАЛЯТ(топ-5)\n3.КАК ПОДНЯТЬ РЕЙТИНГ\n4.ШАБЛОН ОТВЕТА"
        elif mode == "description":
            prompt = f"Продающее описание WB/Ozon.\nТовар: {text}\n\n1.ЗАГОЛОВОК\n2.ВЫГОДЫ(5)\n3.ОПИСАНИЕ(150 слов)\n4.ПРИЗЫВ"
        elif mode == "keywords":
            prompt = f"SEO WB/Ozon.\nТовар: {text}\n\n1.ЗАГОЛОВОК(до 100 символов)\n2.ВЫСОКОЧАСТОТНЫЕ(15)\n3.СРЕДНЕЧАСТОТНЫЕ(15)\n4.СОВЕТЫ"
        elif mode == "offer":
            prompt = f"Оффер и УТП.\nИнфо: {text}\n\n1.УТП\n2.ЗАГОЛОВОК\n3.ВЫГОДЫ(5)\n4.ОФФЕР WB\n5.ОФФЕР Telegram"
        elif mode == "finance":
            parts = [p.strip() for p in text.split(",")]
            if len(parts) < 3:
                await msg.edit_text("❌ Формат: 2490, 890, 150, 15, 80")
                return
            price, cost, qty = float(parts[0]), float(parts[1]), float(parts[2])
            comm = float(parts[3]) if len(parts) > 3 else 15
            log = float(parts[4]) if len(parts) > 4 else 80
            rev = price * qty
            exp = (rev * comm / 100) + (log * qty) + (cost * qty)
            profit = rev - exp
            margin = (profit / rev * 100) if rev > 0 else 0
            prompt = f"Финансы:\nВыручка:{rev:,.0f}₽ Расходы:{exp:,.0f}₽ Прибыль:{profit:,.0f}₽ Маржа:{margin:.1f}%\n\n1.ОЦЕНКА\n2.ПРОБЛЕМЫ\n3.ТОП-5 способов увеличить прибыль"
        else:
            await msg.edit_text("Выбери /menu")
            return
        result = ask_ai(prompt)
        use_limit(uid)
        context.user_data["mode"] = ""
        if len(result) > 3500:
            result = result[:3500] + "..."
        await msg.edit_text(f"{result}\n\n─────────\n/menu — другие инструменты")
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text("❌ Ошибка. Попробуй снова /menu")

def main():
    threading.Thread(target=run_http, daemon=True).start()
    logger.info(f"HTTP on port {PORT}")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
