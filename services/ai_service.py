"""
AI Root Cause Analysis — Hugging Face Inference Providers (router).

Why a hosted API instead of a local model: the target deployment is a
t3.micro (1 vCPU / 1GB RAM), which cannot reliably load or run an LLM
locally — there isn't enough memory headroom alongside Flask + Postgres.
Routing inference through Hugging Face keeps the EC2 box doing nothing
heavier than an HTTPS call.

Semantic search has been removed entirely. "Have we seen this before?" is
now answered with a plain SQL lookup against a `category` tag the model
assigns to each incident — grounded in real stored data, not an embedding
similarity guess.
"""

import json
import logging
import re
import requests
from database.connection import execute_query
from config import Config

logger = logging.getLogger(__name__)

# Bug 5 fixed: cap error_log before sending to HF API to avoid exceeding
# the model's context window and wasting tokens on oversized inputs.
_ERROR_LOG_MAX_CHARS = 8000

CATEGORIES = [
    "DB_CONNECTION_POOL", "MEMORY_LEAK", "CPU_OVERLOAD", "DISK_EXHAUSTION",
    "NETWORK_FAILURE", "AUTH_FAILURE", "API_INTEGRATION", "CONFIGURATION_ERROR",
    "DEPLOYMENT_ISSUE", "APPLICATION_BUG", "OTHER",
]

SYSTEM_PROMPT = f"""You are a senior Site Reliability Engineer performing root cause analysis on a production incident.

Given an incident title and a pasted error log, respond with ONLY a single valid JSON object — no markdown fences, no commentary before or after. Use exactly this shape:

{{
  "summary": "2-3 sentence plain-English explanation of what's happening and why",
  "rootCauses": [
    {{
      "cause": "specific technical root cause",
      "confidence": 92,
      "severity": "critical|high|medium|low",
      "fix": "numbered, actionable remediation steps as a single string with \\n between steps",
      "service": "the component or service responsible"
    }}
  ],
  "fiveWhys": {{
    "why1": "Why did the symptom occur? → answer",
    "why2": "→ answer",
    "why3": "→ answer",
    "why4": "→ answer",
    "why5": "→ root cause answer"
  }},
  "affectedServices": ["Service A", "Service B"],
  "category": "ONE_OF:{','.join(CATEGORIES)}"
}}

Rules:
- List 1-3 root causes ordered by confidence (highest first), confidence is an integer 0-100.
- Base every claim on what's actually in the error log. Do not invent stack traces or services that aren't implied by the input.
- "category" must be exactly one value from the provided list, uppercase, no other text.
- Output valid JSON only.
"""


def _call_hf_api(title: str, error_log: str) -> dict:
    # Bug 7 fixed: raise a clear error class that analyze_incident catches
    if not Config.HF_API_TOKEN:
        raise ValueError("HF_API_TOKEN is not configured")

    # Bug 5 fixed: truncate oversized error logs
    if len(error_log) > _ERROR_LOG_MAX_CHARS:
        logger.warning(f"error_log truncated from {len(error_log)} to {_ERROR_LOG_MAX_CHARS} chars")
        error_log = error_log[:_ERROR_LOG_MAX_CHARS] + "\n... [truncated]"

    payload = {
        "model": Config.HF_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Incident title: {title}\n\nError log:\n{error_log}"},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
    }
    headers = {
        "Authorization": f"Bearer {Config.HF_API_TOKEN}",
        "Content-Type": "application/json",
    }

    resp = requests.post(
        Config.HF_API_URL, headers=headers, json=payload, timeout=Config.HF_TIMEOUT_SECONDS
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _parse_json(raw: str) -> dict:
    # Bug 15 fixed: use regex to robustly strip all markdown fence variants
    # (``` ```json  ``` json  etc.) before parsing
    text = re.sub(r"```(?:json)?\s*", "", raw).strip()
    return json.loads(text)


def _normalize(parsed: dict) -> dict:
    category = (parsed.get("category") or "OTHER").upper().strip()
    if category not in CATEGORIES:
        category = "OTHER"

    root_causes = parsed.get("rootCauses") or []
    for rc in root_causes:
        rc["confidence"] = max(0, min(100, int(rc.get("confidence", 0))))
        rc["severity"] = (rc.get("severity") or "medium").lower()

    return {
        "summary": parsed.get("summary", ""),
        "root_causes": root_causes,
        "five_whys": parsed.get("fiveWhys", {}),
        "affected_services": parsed.get("affectedServices", []),
        "category": category,
    }


def _recurrence_lookup(user_id: int, category: str, exclude_incident_id: int) -> dict:
    """Non-semantic 'have we seen this before' check: count past incidents
    for this user tagged with the same category, and surface the most
    recent fix that was applied for it."""
    count_row = execute_query(
        """
        SELECT COUNT(*) AS n
        FROM root_causes rc
        JOIN incidents i ON i.id = rc.incident_id
        WHERE i.user_id = %s AND rc.category = %s AND rc.incident_id != %s
        """,
        (user_id, category, exclude_incident_id),
        fetch="one",
    )
    count = count_row["n"] if count_row else 0

    historical_solution = None
    if count:
        prev = execute_query(
            """
            SELECT rc.root_causes
            FROM root_causes rc
            JOIN incidents i ON i.id = rc.incident_id
            WHERE i.user_id = %s AND rc.category = %s AND rc.incident_id != %s
            ORDER BY rc.created_at DESC LIMIT 1
            """,
            (user_id, category, exclude_incident_id),
            fetch="one",
        )
        if prev and prev.get("root_causes"):
            top = prev["root_causes"][0] if isinstance(prev["root_causes"], list) and prev["root_causes"] else None
            if top:
                historical_solution = f"Previously resolved by: {top.get('fix', '')}"

    return {"recurrence_count": count, "historical_solution": historical_solution}


def analyze_incident(incident_id: int, user_id: int, title: str, error_log: str) -> dict:
    try:
        raw = _call_hf_api(title, error_log)
        parsed = _parse_json(raw)
        normalized = _normalize(parsed)
    except (requests.RequestException, KeyError) as e:
        logger.error(f"HF API call failed: {e}")
        return {"success": False, "error": "AI analysis service is unavailable. Please try again."}
    except (json.JSONDecodeError, ValueError) as e:
        # Bug 7 fixed: ValueError now catches missing HF_API_TOKEN too
        logger.error(f"AI response error: {e}")
        return {"success": False, "error": "AI analysis failed. Please check configuration and try again."}

    recurrence = _recurrence_lookup(user_id, normalized["category"], incident_id)

    row = execute_query(
        """
        INSERT INTO root_causes
            (incident_id, summary, root_causes, five_whys, affected_services,
             category, recurrence_count, historical_solution)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING *
        """,
        (
            incident_id,
            normalized["summary"],
            json.dumps(normalized["root_causes"]),
            json.dumps(normalized["five_whys"]),
            json.dumps(normalized["affected_services"]),
            normalized["category"],
            recurrence["recurrence_count"],
            recurrence["historical_solution"],
        ),
        fetch="one",
    )

    return {
        "success": True,
        "analysis": {
            "id": row["id"],
            "incident_id": incident_id,
            "summary": row["summary"],
            "root_causes": row["root_causes"],
            "five_whys": row["five_whys"],
            "affected_services": row["affected_services"],
            "category": row["category"],
            "recurrence_count": row["recurrence_count"],
            "historical_solution": row["historical_solution"],
            "created_at": row["created_at"].isoformat()+"Z",
        },
    }
