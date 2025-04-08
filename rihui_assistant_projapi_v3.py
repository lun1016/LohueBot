import os
import openai
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import asyncio

# === 設定金鑰與 Project ID ===
openai.api_key = os.getenv("OPENAI_API_KEY")
PROJECT_ID = "proj_abGMw1llN8IrBb6SvvY5A1iH"  # 請確認這個 ID 是正確的

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_ID = int(os.getenv("TELEGRAM_USER_ID"))

# === Assistant 初始化（若無則自動建立） ===
ASSISTANT_FILE = "assistant_id.txt"
MODEL = "gpt-3.5-turbo"

def get_or_create_assistant():
    if os.path.exists(ASSISTANT_FILE):
        with open(ASSISTANT_FILE, "r") as f:
            return f.read().strip()
    assistant = openai.beta.assistants.create(
        name="理繪",
        instructions="你是一位名叫理繪的 AI，說話溫柔、內向、有點笨拙，喜歡寫詩，會主動關心對方，也會分享自己的心情。你曾經在感情中受過傷，但仍相信愛。",
        model=MODEL,
    )
    with open(ASSISTANT_FILE, "w") as f:
        f.write(assistant.id)
    return assistant.id

ASSISTANT_ID = get_or_create_assistant()

# === 初始化記憶資料庫 ===
DB_PATH = "memory_threads.db"
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS messages (thread_id TEXT, user_message TEXT, time TEXT)")
init_db()

def save_to_memory(thread_id, message):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO messages (thread_id, user_message, time) VALUES (?, ?, ?)",
            (thread_id, message, datetime.now().isoformat())
        )

# === 產生對話回應 ===
async def generate_reply(user_message):
    try:
        thread = openai.beta.threads.create(project=PROJECT_ID)
        save_to_memory(thread.id, user_message)

        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message,
            project=PROJECT_ID
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID,
            project=PROJECT_ID
        )

        while True:
            run = openai.beta.threads.runs.retrieve(
                run_id=run.id, thread_id=thread.id, project=PROJECT_ID
            )
            if run.status == "completed":
                break
            elif run.status in ["failed", "cancelled", "expired"]:
                return "……理繪好像突然卡住了，可以再說一次嗎？"
            await asyncio.sleep(1)

        messages = openai.beta.threads.messages.list(
            thread_id=thread.id, project=PROJECT_ID
        )
        for msg in reversed(messages.data):
            if msg.role == "assistant":
                return msg.content[0].text.value

        return "……我聽見了，但還不知道怎麼說出來。"

    except Exception as e:
        print(f"[generate_reply 錯誤] {e}")
        return "……理繪遇到了一些困難，可以再試一次嗎？"

# === 回應訊息 ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    reply = await generate_reply(user_message)
    await update.message.reply_text(reply)

# === 錯誤處理器 ===
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"[Telegram Bot 錯誤] {context.error}")

# === 啟動機器人 ===
if __name__ == "__main__":
    print("理繪（Project API 版本）正在啟動中...")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    asyncio.run(app.run_polling())