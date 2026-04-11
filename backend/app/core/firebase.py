"""
app/core/firebase.py — Firebase Admin SDK initialisation + token verification
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from fastapi import HTTPException, status

from app.core.config import FIREBASE_CRED_PATH

logger = logging.getLogger("firebase")

_firebase_app: Optional[firebase_admin.App] = None


def init_firebase() -> None:
    """Initialise the Firebase Admin SDK singleton. Fails gracefully."""
    global _firebase_app
    try:
        if os.path.exists(FIREBASE_CRED_PATH):
            cred = credentials.Certificate(FIREBASE_CRED_PATH)
            logger.info("Firebase: loading service-account from %s", FIREBASE_CRED_PATH)
        else:
            cred = credentials.ApplicationDefault()
            logger.warning("Firebase: credential not found at %s — using ADC.", FIREBASE_CRED_PATH)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialised.")
    except Exception as exc:
        logger.error("Firebase initialisation FAILED: %s", exc)
        _firebase_app = None


def get_firebase_app() -> Optional[firebase_admin.App]:
    return _firebase_app


def verify_firebase_token(token: str) -> Dict[str, Any]:
    """
    Verify a Firebase ID token.  
    Raises HTTP 401 on invalid tokens, HTTP 503 if SDK is unavailable.
    """
    if _firebase_app is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is currently unavailable.",
        )
    try:
        return firebase_auth.verify_id_token(token, app=_firebase_app)
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Firebase token has expired.")
    except firebase_auth.InvalidIdTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {exc}")
    except Exception as exc:
        logger.error("Token verification error: %s", exc)
        raise HTTPException(status_code=401, detail="Token verification failed.")
