import asyncio
import logging
import time
import uuid
import os
import random
import json
import httpx
from typing import Any, Dict, Optional, List
from pathlib import Path
from app.core.state import TASKS, TASK_LOCK

logger = logging.getLogger(__name__)

UA_FILE_PATH = Path(__file__).resolve().parents[2] / "data" / "user_agents.json"
_CACHED_UA: Optional[List[str]] = None

def _load_user_agents() -> List[str]:
    global _CACHED_UA
    if _CACHED_UA is not None:
        return _CACHED_UA
    if UA_FILE_PATH.exists():
        with UA_FILE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list) and data:
                _CACHED_UA = [str(item) for item in data]
                return _CACHED_UA
    _CACHED_UA = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"]
    return _CACHED_UA

def _pick_user_agent() -> str:
    return random.choice(_load_user_agents())

def _normalize_url(target: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(target)
    if not parsed.scheme: return f"https://{target}"
    return target

def _httpx_client(proxy: Optional[str] = None, timeout: int = 12) -> httpx.AsyncClient:
    proxies = None
    if proxy:
        if "://" not in proxy: proxy = f"socks5://{proxy}"
        proxies = proxy
        
    return httpx.AsyncClient(
        proxies=proxies,
        timeout=timeout,
        headers={"User-Agent": _pick_user_agent()},
        follow_redirects=True,
        verify=False
    )
