"""Input validation helpers."""
import os
import re
import uuid
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def safe_filename(filename: str) -> str:
    return secure_filename(filename)


def validate_session(session_id: str) -> bool:
    try:
        uuid.UUID(session_id)
        return True
    except (ValueError, AttributeError):
        return False
