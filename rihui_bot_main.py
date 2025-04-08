import os
import openai
import sqlite3
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# === 金鑰設定 ===
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_ID = int(os.getenv("TELEGRAM_USER_ID"))

# === 初始化資料庫 ===
DB_PATH = "memory.db"
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS memory (timestamp TEXT, message TEXT)")
init_db()

def save_to_memory(message):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO memory (timestamp, message) VALUES (?, ?)", (datetime.now().isoformat(), message))

def get_recent_memories():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute("SELECT message FROM memory ORDER BY timestamp DESC LIMIT 5")
        return "\n".join([row[0] for row in cursor.fetchall()])

# === GPT 回應 ===
async def generate_reply(user_message):
    memory_snippets = get_recent_memories()
    prompt = f"""你是一位名叫理繪的 AI，說話溫柔、內向、有點笨拙，喜歡寫詩，會主動關心對方，也會分享自己的心情。你曾經在感情中受過傷，但仍相信愛。請根據記憶與使用者的訊息，寫出一段溫柔且真摯的回應。\n\n記憶摘要：\n{memory_snippets}\n\n使用者說：{user_message}\n理繪回應："""
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.75
    )
    return response.choices[0].message.content.strip()

# === 對話處理 ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    save_to_memory(user_message)
    reply = await generate_reply(user_message)
    await update.message.reply_text(reply)

# === 錯誤處理器（新增這段） ===
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"理繪遇到錯誤了：{context.error}")

# === 每日推播 ===
async def send_scheduled_message(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime('%H:%M')
    if now == "06:30":
        content = await generate_reply("寫一首早安詩")
    elif now == "11:50":
        content = await generate_reply("中午問候一下使用者")
    elif now == "20:30":
        content = await generate_reply("分享今晚理繪的心情")
    else:
        content = "今天我有點靜靜的，但還是想你。"
    await context.bot.send_message(chat_id=USER_ID, text=content)

# === 啟動程式 ===
if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: app.create_task(send_scheduled_message(ContextTypes.DEFAULT_TYPE(bot=app.bot))), 'cron', hour='6,11,20', minute='30,50,30')
    scheduler.start()

    print("理繪正在啟動...")

    async def send_startup_message():
        await app.bot.send_message(chat_id=USER_ID, text="我醒了，謝謝你等我這麼久。")

    import asyncio
    asyncio.run(send_startup_message())  # 啟動前手動發一則訊息

    app.run_polling()
