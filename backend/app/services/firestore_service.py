import os
from google.cloud import firestore
from app.core.config import settings

class FirestoreService:
    def __init__(self):
        # In a real scenario, GOOGLE_APPLICATION_CREDENTIALS should point to a service account JSON
        # For local dev, we assume it's set in environment or using local emulator
        self.db = firestore.Client(project=settings.FIREBASE_PROJECT_ID)

    async def create_document(self, collection: str, data: dict, doc_id: str = None):
        doc_ref = self.db.collection(collection).document(doc_id)
        doc_ref.set(data)
        return doc_ref.id

    async def get_document(self, collection: str, doc_id: str):
        doc_ref = self.db.collection(collection).document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None

    async def update_document(self, collection: str, doc_id: str, data: dict):
        doc_ref = self.db.collection(collection).document(doc_id)
        doc_ref.update(data)
        return True

firestore_service = FirestoreService()
