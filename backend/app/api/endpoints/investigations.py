from fastapi import APIRouter, HTTPException, BackgroundTasks
from shared.schemas import InvestigationCreate, InvestigationTask, TaskStatus
from app.services.firestore_service import firestore_service
from celery import Celery
import os
import uuid
import time

router = APIRouter()
celery_app = Celery("nexus", broker=os.getenv("REDIS_URL", "redis://redis:6379/0"))

@router.post("/", response_model=InvestigationTask)
async def start_investigation(payload: InvestigationCreate):
    task_id = str(uuid.uuid4())
    
    task_data = {
        "id": task_id,
        "target": payload.target,
        "type": payload.type,
        "status": TaskStatus.PENDING,
        "created_at": time.time(),
        "results": None
    }
    
    # Save to Firestore
    await firestore_service.create_document("investigations", task_data, task_id)
    
    # Dispatch Task to Celery
    task_map = {
        "dns": "tasks.perform_dns_lookup",
        "web": "tasks.scrape_web_intelligence",
        "image": "tasks.analyze_image_metadata"
    }
    
    target_task = task_map.get(payload.type.value)
    if target_task:
        celery_app.send_task(target_task, args=[payload.target], task_id=task_id)
    
    return task_data

@router.get("/{task_id}", response_model=InvestigationTask)
async def get_investigation_status(task_id: str):
    doc = await firestore_service.get_document("investigations", task_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return doc
