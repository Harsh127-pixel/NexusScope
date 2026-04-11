import asyncio
import logging
import time
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.state import TASKS, TASK_LOCK
from app.api.endpoints.theater1 import _onion_crawler
from app.api.endpoints.theater2 import _domain_lookup, _ip_lookup, _scrape_web, _phone_lookup
from app.api.endpoints.theater3 import _image_metadata, _username_lookup, _email_lookup

router = APIRouter()
logger = logging.getLogger(__name__)

class InvestigationRequest(BaseModel):
    target: str
    module: Optional[str] = None
    type: Optional[str] = None
    proxy: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)

class CreateInvestigationResponse(BaseModel):
    task_id: str

@router.get("/investigations/{task_id}")
async def get_investigation(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return TASKS[task_id]

@router.post("/investigations", response_model=CreateInvestigationResponse)
async def create_investigation(payload: InvestigationRequest, background_tasks: BackgroundTasks):
    module = payload.module or payload.type or "scraper"
    task_id = str(uuid.uuid4())
    
    async with TASK_LOCK:
        TASKS[task_id] = {
            "id": task_id,
            "module": module,
            "target": payload.target,
            "status": "pending",
            "created_at": time.time(),
            "result": None,
            "error": None,
            "options": payload.options,
            "proxy": payload.proxy
        }
    
    background_tasks.add_task(_execute_task, task_id)
    return CreateInvestigationResponse(task_id=task_id)

async def _execute_task(task_id: str):
    task = TASKS[task_id]
    task["status"] = "processing"
    module = task["module"]
    target = task["target"]
    options = task.get("options", {})
    proxy = task.get("proxy")
    
    try:
        if module == "domain": result = await _domain_lookup(target)
        elif module == "ip": result = await _ip_lookup(target)
        elif module == "darkweb": result = await _onion_crawler(target)
        elif module == "username": result = await _username_lookup(target, proxy, options.get("timeout", 12))
        elif module == "metadata": result = await _image_metadata(target, proxy, options.get("timeout", 12))
        elif module == "scraper": result = await _scrape_web(target, proxy, options.get("timeout", 12), options.get("use_playwright", False))
        elif module == "phone": result = await _phone_lookup(target)
        elif module == "email": result = await _email_lookup(target)
        else: raise ValueError(f"Unknown module: {module}")
        
        task["status"] = "completed"
        task["result"] = result
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
