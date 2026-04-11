import asyncio
from typing import Dict, Any

TASKS: Dict[str, Dict[str, Any]] = {}
BOT_STATE: Dict[int, str] = {} # chat_id -> active_module
TASK_LOCK = asyncio.Lock()
