import logging
import re
import uuid
import time
import httpx
import os
from app.core.state import TASKS, BOT_STATE
from app.api.endpoints.investigations import _execute_task
from fastapi import APIRouter, Request, BackgroundTasks, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "REPLACE_WITH_BOT_TOKEN")

class TelegramWebhookAck(BaseModel):
    status: str
    message: str

def get_menu_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "🌐 Domain Intel", "callback_data": "set_mod:domain"}, {"text": "📡 IP Intel", "callback_data": "set_mod:ip"}],
            [{"text": "🕷️ Dark Web", "callback_data": "set_mod:darkweb"}, {"text": "👤 Username Recon", "callback_data": "set_mod:username"}],
            [{"text": "📧 Email OSINT", "callback_data": "set_mod:email"}, {"text": "🖼️ Metadata", "callback_data": "set_mod:metadata"}],
            [{"text": "🔴 DEEP SEARCH (LeakDB)", "callback_data": "set_mod:deepsearch"}],
        ]
    }

async def _send_telegram(chat_id: int, text: str, reply_markup: dict = None):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(url, json=payload)

async def _process_update(update: dict):
    # Handle Callback Queries (Buttons)
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb["data"]
        if data.startswith("set_mod:"):
            mod = data.split(":")[1]
            BOT_STATE[chat_id] = mod
            await _send_telegram(chat_id, f"✅ <b>Module set to: {mod.upper()}</b>\n\nPlease send the target (e.g., domain name, IP, or username) to begin.")
        return

    message = update.get("message") or update.get("edited_message")
    if not message or "chat" not in message: return
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    # 1. Greetings / Start / Commands
    if text.lower() in ["/start", "hi", "hello", "help", "menu"]:
        BOT_STATE.pop(chat_id, None)
        welcome = (
            "🛡️ <b>NexusScope Terminal OSINT Bot</b>\n\n"
            "Select a specialized intelligence theater below or just send a target for auto-inference."
        )
        await _send_telegram(chat_id, welcome, get_menu_keyboard())
        return

    # /api — show API info and token
    if text.lower() == "/api":
        await _send_telegram(chat_id,
            "🔑 <b>NexusScope API Access</b>\n\n"
            f"Your API Token:\n<code>{TELEGRAM_BOT_TOKEN}</code>\n\n"
            "<b>Deep Search endpoint:</b>\n"
            "<code>POST /api/v1/deepsearch/search</code>\n\n"
            "<b>Example body:</b>\n"
            '<code>{"target": "user@email.com", "limit": 100}</code>\n\n'
            "📖 Full docs at: <a href='https://nexusscope.vercel.app/docs'>API Docs</a>"
        )
        return

    # Handle explicit slash commands: /mod <target>
    cmd_match = re.match(r"^/(ip|domain|darkweb|username|metadata|email|deepsearch|phone)\s+(.+)$", text, re.I)
    if cmd_match:
        active_mod = cmd_match.group(1).lower()
        text = cmd_match.group(2).strip()
    else:
        active_mod = BOT_STATE.get(chat_id)
    
    # Auto-inference if no active session
    if not active_mod:
        if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", text): active_mod = "ip"
        elif "@" in text and "." in text: active_mod = "email"
        elif text.endswith(".onion"): active_mod = "darkweb"
        elif text.startswith("@"):
            active_mod = "username"
            text = text[1:]
        elif "." in text and " " not in text: active_mod = "domain"
        else: active_mod = "scraper"
    
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {
        "id": task_id, "module": active_mod, "target": text, "status": "queued",
        "created_at": time.time(), "result": None, "error": None, "options": {"timeout": 15}
    }
    
    frontend_url = f"https://nexusscope.vercel.app/results/{task_id}"
    await _send_telegram(chat_id, f"🔍 <b>Investigation Initialized</b>\nTheatre: <code>{active_mod.upper()}</code>\nTarget: <code>{text}</code>\n\n🕒 Processing... <a href='{frontend_url}'>View Live</a>")
    
    try:
        await _execute_task(task_id)
        task = TASKS[task_id]
        if task["status"] == "completed":
            await _send_telegram(chat_id, f"✅ <b>Mission Success</b>\nTarget: <code>{text}</code>\n\nFull report ready at:\n👉 <a href='{frontend_url}'>Launch Dashboard</a>", get_menu_keyboard())
        else:
            await _send_telegram(chat_id, f"❌ <b>Investigation Suspended</b>\nReason: {task.get('error', 'Unknown Error')}", get_menu_keyboard())
    except Exception as e:
        await _send_telegram(chat_id, f"⚠️ <b>Fatal Error</b>\n{str(e)}", get_menu_keyboard())

@router.post("/webhook/telegram", response_model=TelegramWebhookAck)
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        update = await request.json()
        background_tasks.add_task(_process_update, update)
        return TelegramWebhookAck(status="accepted", message="Update queued")
    except:
        return TelegramWebhookAck(status="error", message="Malformed payload")
