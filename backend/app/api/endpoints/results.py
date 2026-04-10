from fastapi import APIRouter, HTTPException
from app.services.firestore_service import firestore_service
from shared.schemas import InvestigationTask

router = APIRouter()

@router.get("/{task_id}", response_model=InvestigationTask)
async def get_results(task_id: str):
    """Fetch completed results for an investigation."""
    doc = await firestore_service.get_document("investigations", task_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Investigation results not found")
    
    if doc.get("status") != "completed":
        return {"id": task_id, "status": doc.get("status"), "message": "Results pending completion"}
        
    return doc
