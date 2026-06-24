import re
import logging
from email_validator import validate_email, EmailNotValidError
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from database.connection import execute_query

logger = logging.getLogger(__name__)

PASSWORD_MIN_LENGTH = 8


class User(UserMixin):
    """Thin wrapper so Flask-Login can manage sessions for a DB row."""

    def __init__(self, row: dict):
        self.id = str(row["id"])
        self.name = row["name"]
        self.email = row["email"]


def get_user_by_id(user_id) -> "User | None":
    row = execute_query("SELECT id, name, email FROM users WHERE id = %s", (user_id,), fetch="one")
    return User(row) if row else None


# ── validation ───────────────────────────────────────────────────────────────

def _validate_password(password: str) -> list[str]:
    errors = []
    if not password or len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
        return errors
    if not re.search(r"[A-Za-z]", password):
        errors.append("Password must contain at least one letter")
    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one number")
    return errors


def validate_signup(data: dict) -> dict:
    """Returns {field: [errors]} — empty dict means valid."""
    errors: dict[str, list[str]] = {}

    name = (data.get("name") or "").strip()
    if len(name) < 2:
        errors["name"] = ["Name must be at least 2 characters"]

    email = (data.get("email") or "").strip()
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError as e:
        errors["email"] = [str(e)]

    password = data.get("password") or ""
    pw_errors = _validate_password(password)
    if pw_errors:
        errors["password"] = pw_errors

    confirm = data.get("confirm_password") or ""
    if password and confirm and password != confirm:
        errors.setdefault("confirm_password", []).append("Passwords do not match")

    return errors


# ── account operations ──────────────────────────────────────────────────────

def signup(data: dict) -> dict:
    errors = validate_signup(data)
    if errors:
        return {"success": False, "errors": errors}

    name  = data["name"].strip()
    email = data["email"].strip().lower()

    existing = execute_query("SELECT id FROM users WHERE email = %s", (email,), fetch="one")
    if existing:
        return {"success": False, "errors": {"email": ["An account with this email already exists"]}}

    password_hash = generate_password_hash(data["password"])
    row = execute_query(
        "INSERT INTO users (name, email, password_hash) VALUES (%s,%s,%s) RETURNING id, name, email",
        (name, email, password_hash),
        fetch="one",
    )
    return {"success": True, "user": User(row)}


def login(email: str, password: str) -> dict:
    email = (email or "").strip().lower()
    if not email or not password:
        return {"success": False, "error": "Email and password are required"}

    row = execute_query(
        "SELECT id, name, email, password_hash FROM users WHERE email = %s", (email,), fetch="one"
    )
    if not row or not check_password_hash(row["password_hash"], password):
        return {"success": False, "error": "Invalid email or password"}

    return {"success": True, "user": User(row)}
