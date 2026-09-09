from __future__ import annotations

import json
import os
from threading import Lock
from typing import Any

import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from shared.config import get_settings
from shared.logging import get_logger

_init_lock = Lock()
_firebase_initialized = False
logger = get_logger(__name__)


def _log_credential_metadata(label: str, data: dict[str, Any]) -> None:
    logger.debug(
        "%s credential metadata project_id=%s client_email=%s type=%s has_private_key=%s",
        label,
        data.get("project_id"),
        data.get("client_email"),
        data.get("type"),
        bool(data.get("private_key")),
    )


def initialize_firebase() -> None:
    global _firebase_initialized
    if _firebase_initialized:
        return

    with _init_lock:
        if _firebase_initialized:
            return

        settings = get_settings()
        cred_dict = settings.firebase_credentials_dict()
        app_options: dict[str, Any] = {}
        if settings.project_id:
            app_options["projectId"] = settings.project_id

        credential_source = "default"
        if cred_dict:
            credential_source = "inline-json"
            _log_credential_metadata("Inline JSON", cred_dict)
        elif settings.firebase_credentials and os.path.exists(settings.firebase_credentials):
            credential_source = settings.firebase_credentials
            try:
                with open(settings.firebase_credentials, "r", encoding="utf-8") as handle:
                    file_data = json.load(handle)
                _log_credential_metadata("File", file_data)
            except Exception as exc:
                logger.warning(
                    "Could not read Firebase credential file path=%s error=%s",
                    settings.firebase_credentials,
                    exc,
                )
        elif settings.firebase_credentials:
            logger.warning(
                "Firebase credential file not found path=%s",
                settings.firebase_credentials,
            )

        logger.debug(
            "Initializing Firebase app project_id=%s credential_source=%s",
            settings.project_id,
            credential_source,
        )

        if cred_dict:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred, options=app_options)
        elif settings.firebase_credentials and os.path.exists(settings.firebase_credentials):
            cred = credentials.Certificate(settings.firebase_credentials)
            firebase_admin.initialize_app(cred, options=app_options)
        else:
            firebase_admin.initialize_app(options=app_options)

        _firebase_initialized = True


def verify_id_token(token: str) -> dict[str, Any]:
    initialize_firebase()
    decoded = firebase_auth.verify_id_token(token)
    logger.debug(
        "Verified Firebase token uid=%s email=%s",
        decoded.get("uid"),
        decoded.get("email"),
    )
    return decoded
