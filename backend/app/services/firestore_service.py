import os
from google.cloud import firestore
from app.core.config import settings

class MockFirestoreDb:
    def collection(self, *args, **kwargs):
        return MockCollection()

class MockCollection:
    def document(self, *args, **kwargs):
        return MockDocument()

class MockDocument:
    def set(self, data):
        pass
    def get(self):
        return MockDocSnapshot()
    def update(self, data):
        pass

class MockDocSnapshot:
    @property
    def exists(self):
        return False
    def to_dict(self):
        return {}

class FirestoreService:
    def __init__(self):
        try:
            self.db = firestore.Client(project=settings.FIREBASE_PROJECT_ID)
        except Exception as e:
            print(f"WARN: Starting without real Firestore credentials. Using mock DB. Details: {e}")
            self.db = MockFirestoreDb()

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
