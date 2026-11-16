from __future__ import annotations

import csv
import io
import os
import secrets
import re
import shlex
import subprocess
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg
from flask import (
    Flask,
    abort,
    jsonify,
    make_response,
    render_template,
    request,
    send_from_directory,
)
from PIL import Image, ImageOps
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from werkzeug.utils import secure_filename

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_AVAILABLE = True
except Exception:
    HEIF_AVAILABLE = False

ENV_FILE = Path(
    os.environ.get(
        "ECC_ENV_FILE",
        str(Path(__file__).resolve().parent.parent / ".env"),
    )
)
APP_ROOT = Path(__file__).resolve().parent
SITE_ROOT = APP_ROOT.parent


def load_env_file(path: Path) -> None:
    if not path.is_file():
        required = {"DB_NAME", "DB_USER", "DB_PASSWORD"}
        if required.issubset(os.environ):
            return
        raise RuntimeError(f"Configuration file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load_env_file(ENV_FILE)

DB_SETTINGS = {
    "dbname": os.environ["DB_NAME"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "port": os.environ.get("DB_PORT", "5432"),
}
OPERATOR = os.environ.get("APP_ACTOR", "local-operator")
PHOTO_DATA_ROOT = Path(
    os.environ.get(
        "PHOTO_DATA_ROOT",
        str(Path(__file__).resolve().parent.parent / "data" / "photos"),
    )
)
GUEST_SITE_URL = os.environ.get("GUEST_SITE_URL", "http://127.0.0.1:8080/")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://127.0.0.1:8081/")
MAX_PHOTO_BYTES = int(os.environ.get("MAX_PHOTO_BYTES", str(40 * 1024 * 1024)))
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}

CONTENT_DEFAULTS = {
    "event_title": "Example Community Gathering",
    "event_subtitle": "An example self-hosted event",
    "welcome_text": "Welcome to our celebration.",
    "couple_intro": "Use the private Event Command Center to edit and publish this example event site.",
    "venue_text": "Venue details will appear here.",
    "schedule_text": "The day’s schedule will appear here.",
    "dress_text": "Dress guidance will appear here.",
    "faq_text": "Frequently asked questions will appear here.",
    "travel_text": "Travel information will appear here.",
    "parking_text": "Parking guidance will appear here.",
    "accommodation_text": "Accommodation guidance will appear here.",
    "gift_text": "Event contribution or gift guidance may appear here.",
    "guest_only_text": "Additional public guest information will appear here.",
    "contact_text": "Contact and help information will appear here.",
}

INVITATION_DEFAULTS = {
    "invitation_subject": "Invitation — Example Community Gathering",
    "invitation_message": "You are invited to our event. Please use the link below for information and to RSVP.",
    "event_site_link": GUEST_SITE_URL,
}

GUEST_VIEWS = {"home", "guest-info", "rsvp", "gallery", "contact"}
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "")
OPERATOR_PROXY_KEY = os.environ.get("OPERATOR_PROXY_KEY", "")
if (
    len(app.secret_key) < 32
    or len(OPERATOR_PROXY_KEY) < 32
    or app.secret_key == OPERATOR_PROXY_KEY
    or app.secret_key.startswith("REPLACE_")
    or OPERATOR_PROXY_KEY.startswith("REPLACE_")
):
    raise RuntimeError("Set APP_SECRET_KEY and OPERATOR_PROXY_KEY to independent random values (at least 32 characters each).")
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024


def database_connection():
    return psycopg.connect(**DB_SETTINGS, row_factory=dict_row)


def json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_value(item) for item in value]
    return value


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with database_connection() as connection:
        rows = connection.execute(sql, params).fetchall()
    return [json_value(dict(row)) for row in rows]


def fetch_one(sql: str, params: tuple = ()) -> dict | None:
    with database_connection() as connection:
        row = connection.execute(sql, params).fetchone()
    return json_value(dict(row)) if row else None


def log_activity(connection, event_type: str, summary: str, metadata: dict | None = None) -> None:
    connection.execute(
        """
        INSERT INTO activity_log (event_type, actor, summary, metadata_json)
        VALUES (%s, %s, %s, %s)
        """,
        (event_type, OPERATOR, summary, Jsonb(metadata or {})),
    )


def ensure_photo_directories() -> None:
    for folder in (PHOTO_DATA_ROOT / "originals", PHOTO_DATA_ROOT / "display", PHOTO_DATA_ROOT / "thumbnails"):
        folder.mkdir(parents=True, exist_ok=True)


def ensure_schema() -> None:
    ensure_photo_directories()
    with database_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS content_draft (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS content_live (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS publication_history (
                id BIGSERIAL PRIMARY KEY,
                published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                operator TEXT NOT NULL,
                change_note TEXT NOT NULL DEFAULT '',
                content_json JSONB NOT NULL,
                restored_from BIGINT NULL REFERENCES publication_history(id)
            );
            CREATE TABLE IF NOT EXISTS guest_submissions (
                id BIGSERIAL PRIMARY KEY,
                submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                source_ip TEXT NOT NULL DEFAULT '',
                payload_json JSONB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS guest_parties (
                id BIGSERIAL PRIMARY KEY,
                source_submission_id BIGINT NULL REFERENCES guest_submissions(id),
                party_name TEXT NOT NULL,
                contact_name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                guest_response TEXT NOT NULL DEFAULT 'unsure',
                workflow_state TEXT NOT NULL DEFAULT 'new',
                plus_one_requested BOOLEAN NOT NULL DEFAULT FALSE,
                plus_one_name TEXT NOT NULL DEFAULT '',
                plus_one_status TEXT NOT NULL DEFAULT 'not_applicable',
                party_note TEXT NOT NULL DEFAULT '',
                host_notes TEXT NOT NULL DEFAULT '',
                duplicate_review_state TEXT NOT NULL DEFAULT 'clear',
                invitation_status TEXT NOT NULL DEFAULT 'not_prepared',
                invitation_prepared_at TIMESTAMPTZ NULL,
                invitation_sent_at TIMESTAMPTZ NULL,
                deleted_at TIMESTAMPTZ NULL,
                deleted_reason TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS guest_attendees (
                id BIGSERIAL PRIMARY KEY,
                party_id BIGINT NOT NULL REFERENCES guest_parties(id) ON DELETE CASCADE,
                attendee_name TEXT NOT NULL,
                attendance_status TEXT NOT NULL DEFAULT 'attending',
                dietary_requirement TEXT NOT NULL DEFAULT '',
                allergy_information TEXT NOT NULL DEFAULT '',
                allergy_severity TEXT NOT NULL DEFAULT 'none',
                accessibility_note TEXT NOT NULL DEFAULT '',
                private_note TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS photo_triage (
                asset_path TEXT PRIMARY KEY,
                category TEXT NOT NULL DEFAULT 'unsure',
                comment TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS run_sheet_items (
                id BIGSERIAL PRIMARY KEY,
                start_time TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '',
                owner TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0,
                done BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS checklist_items (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'not_started',
                due_date TEXT NOT NULL DEFAULT '',
                owner TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS budget_items (
                id BIGSERIAL PRIMARY KEY,
                item TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                vendor TEXT NOT NULL DEFAULT '',
                estimated NUMERIC(12,2) NOT NULL DEFAULT 0,
                actual NUMERIC(12,2) NOT NULL DEFAULT 0,
                payment_status TEXT NOT NULL DEFAULT 'not_due',
                due_date TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS vendors (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                service TEXT NOT NULL DEFAULT '',
                contact_name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                notes TEXT NOT NULL DEFAULT '',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS activity_log (
                id BIGSERIAL PRIMARY KEY,
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                summary TEXT NOT NULL,
                metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
            );

            ALTER TABLE guest_parties ADD COLUMN IF NOT EXISTS invitation_status TEXT NOT NULL DEFAULT 'not_prepared';
            ALTER TABLE guest_parties ADD COLUMN IF NOT EXISTS invitation_prepared_at TIMESTAMPTZ NULL;
            ALTER TABLE guest_parties ADD COLUMN IF NOT EXISTS invitation_sent_at TIMESTAMPTZ NULL;

            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS photo_id TEXT NULL;
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS original_filename TEXT NOT NULL DEFAULT '';
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS display_path TEXT NOT NULL DEFAULT '';
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS thumbnail_path TEXT NOT NULL DEFAULT '';
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS alt_text TEXT NOT NULL DEFAULT '';
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS show_in_gallery BOOLEAN NOT NULL DEFAULT FALSE;
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS source_kind TEXT NOT NULL DEFAULT 'legacy';
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS mime_type TEXT NOT NULL DEFAULT '';
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS file_size BIGINT NOT NULL DEFAULT 0;
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS width INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS height INTEGER NOT NULL DEFAULT 0;
            ALTER TABLE photo_triage ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
            CREATE UNIQUE INDEX IF NOT EXISTS photo_triage_photo_id_unique
                ON photo_triage(photo_id) WHERE photo_id IS NOT NULL;
            """
        )

        old_welcome = None
        existing_site_content = connection.execute("SELECT to_regclass('public.site_content') AS name").fetchone()
        if existing_site_content and existing_site_content["name"]:
            old_welcome = connection.execute("SELECT value FROM site_content WHERE key='welcome_text'").fetchone()

        defaults = dict(CONTENT_DEFAULTS)
        if old_welcome and old_welcome["value"]:
            defaults["welcome_text"] = old_welcome["value"]
        for key, value in defaults.items():
            connection.execute(
                "INSERT INTO content_draft (key,value) VALUES (%s,%s) ON CONFLICT (key) DO NOTHING",
                (key, value),
            )
            connection.execute(
                "INSERT INTO content_live (key,value) VALUES (%s,%s) ON CONFLICT (key) DO NOTHING",
                (key, value),
            )

        settings = {
            "client_access_state": "not_configured",
            **INVITATION_DEFAULTS,
        }
        for key, value in settings.items():
            connection.execute(
                "INSERT INTO app_settings (key,value) VALUES (%s,%s) ON CONFLICT (key) DO NOTHING",
                (key, value),
            )

        if not connection.execute("SELECT 1 FROM publication_history LIMIT 1").fetchone():
            live = {
                row["key"]: row["value"]
                for row in connection.execute("SELECT key,value FROM content_live").fetchall()
            }
            connection.execute(
                "INSERT INTO publication_history (operator,change_note,content_json) VALUES (%s,%s,%s)",
                (OPERATOR, "Initial live content imported.", Jsonb(live)),
            )


def read_content(table: str) -> dict[str, str]:
    if table not in {"content_draft", "content_live"}:
        raise ValueError("Invalid content table")
    with database_connection() as connection:
        rows = connection.execute(f"SELECT key,value FROM {table} ORDER BY key").fetchall()
    return {row["key"]: row["value"] for row in rows}


def media_url(relative_path: str) -> str:
    clean = str(relative_path or "").replace("\\", "/").lstrip("/")
    return f"/media/gallery/{clean}"


def read_gallery() -> list[dict]:
    rows = fetch_all(
        """
        SELECT photo_id,original_filename,display_path,thumbnail_path,comment,alt_text,display_order,width,height
        FROM photo_triage
        WHERE source_kind='upload' AND show_in_gallery=TRUE
        ORDER BY display_order, created_at, asset_path
        """
    )
    gallery = []
    for row in rows:
        if not row.get("display_path") or not row.get("thumbnail_path"):
            continue
        gallery.append(
            {
                **row,
                "caption": row.get("comment", ""),
                "display_url": media_url(row["display_path"]),
                "thumbnail_url": media_url(row["thumbnail_path"]),
            }
        )
    return gallery


def photo_library() -> list[dict]:
    rows = fetch_all(
        """
        SELECT photo_id,asset_path,original_filename,display_path,thumbnail_path,comment,alt_text,
               display_order,show_in_gallery,mime_type,file_size,width,height,created_at,updated_at
        FROM photo_triage
        WHERE source_kind='upload'
        ORDER BY display_order, created_at DESC, asset_path
        """
    )
    for row in rows:
        row["thumbnail_url"] = media_url(row.get("thumbnail_path", ""))
        row["display_url"] = media_url(row.get("display_path", ""))
    return rows


def duplicate_count() -> int:
    row = fetch_one(
        """
        SELECT COUNT(*) AS count FROM (
            SELECT lower(email) marker FROM guest_parties
            WHERE deleted_at IS NULL AND email <> '' GROUP BY lower(email) HAVING COUNT(*) > 1
            UNION ALL
            SELECT regexp_replace(phone,'\\D','','g') marker FROM guest_parties
            WHERE deleted_at IS NULL AND phone <> ''
            GROUP BY regexp_replace(phone,'\\D','','g') HAVING COUNT(*) > 1
        ) duplicates
        """
    )
    return int(row["count"] if row else 0)


def read_settings(keys: list[str]) -> dict[str, str]:
    if not keys:
        return {}
    rows = fetch_all("SELECT key,value FROM app_settings WHERE key = ANY(%s)", (keys,))
    return {row["key"]: row["value"] for row in rows}


def run_fixed_command(env_key: str) -> dict:
    command_text = os.environ.get(env_key, "").strip()
    if not command_text:
        return {"configured": False, "ok": False, "output": "Not configured"}
    try:
        command = shlex.split(command_text)
        if not command or not Path(command[0]).is_absolute():
            return {"configured": True, "ok": False, "output": "An absolute executable path is required."}
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    except Exception as exc:
        return {"configured": True, "ok": False, "output": str(exc)}
    output = (result.stdout or result.stderr or "").strip()
    return {"configured": True, "ok": result.returncode == 0, "output": output[:1000]}


def client_access_state() -> dict:
    stored = fetch_one("SELECT key,value,updated_at FROM app_settings WHERE key='client_access_state'") or {
        "key": "client_access_state",
        "value": "not_configured",
        "updated_at": "",
    }
    configured = bool(os.environ.get("CLIENT_ACCESS_OPEN_COMMAND") and os.environ.get("CLIENT_ACCESS_CLOSE_COMMAND"))
    return {**stored, "configured": configured}


def dashboard_state() -> dict:
    parties = fetch_all(
        """
        SELECT p.*,
               COALESCE((SELECT json_agg(a ORDER BY a.id) FROM guest_attendees a WHERE a.party_id=p.id),'[]'::json) AS attendees
        FROM guest_parties p
        ORDER BY (p.deleted_at IS NOT NULL), p.updated_at DESC, p.id DESC
        """
    )
    active = [party for party in parties if not party["deleted_at"]]
    confirmed_attendees = sum(
        1
        for party in active
        for attendee in party["attendees"]
        if attendee.get("attendance_status") == "attending"
    )
    severe_allergies = sum(
        1
        for party in active
        for attendee in party["attendees"]
        if attendee.get("allergy_severity") == "severe"
    )
    draft = read_content("content_draft")
    live = read_content("content_live")
    budget = fetch_all("SELECT * FROM budget_items ORDER BY id DESC")
    photos = photo_library()
    invitation_settings = read_settings(list(INVITATION_DEFAULTS))
    return {
        "content": {"draft": draft, "live": live, "has_pending_changes": draft != live},
        "publication_history": fetch_all(
            "SELECT id,published_at,operator,change_note,restored_from FROM publication_history ORDER BY id DESC LIMIT 50"
        ),
        "metrics": {
            "parties": len(active),
            "responses_received": sum(1 for party in active if party["guest_response"] in {"attending", "not_attending"}),
            "attending_parties": sum(1 for party in active if party["guest_response"] == "attending"),
            "confirmed_attendees": confirmed_attendees,
            "unsure": sum(1 for party in active if party["guest_response"] == "unsure"),
            "not_attending": sum(1 for party in active if party["guest_response"] == "not_attending"),
            "needs_follow_up": sum(1 for party in active if party["workflow_state"] == "needs_follow_up"),
            "pending_plus_ones": sum(1 for party in active if party["plus_one_status"] == "pending"),
            "severe_allergies": severe_allergies,
            "possible_duplicates": duplicate_count(),
            "new_submissions": sum(1 for party in active if party["workflow_state"] == "new"),
            "budget_estimated": sum(float(item["estimated"]) for item in budget),
            "budget_actual": sum(float(item["actual"]) for item in budget),
            "gallery_photos": sum(1 for photo in photos if photo["show_in_gallery"]),
            "invitations_prepared": sum(1 for party in active if party["invitation_status"] == "prepared"),
            "invitations_sent": sum(1 for party in active if party["invitation_status"] == "sent"),
        },
        "parties": parties,
        "photos": photos,
        "run_sheet": fetch_all("SELECT * FROM run_sheet_items ORDER BY sort_order,start_time,id"),
        "checklist": fetch_all(
            "SELECT * FROM checklist_items ORDER BY CASE status WHEN 'in_progress' THEN 0 WHEN 'not_started' THEN 1 ELSE 2 END,due_date,id"
        ),
        "budget": budget,
        "vendors": fetch_all("SELECT * FROM vendors ORDER BY name,id"),
        "activity": fetch_all("SELECT * FROM activity_log ORDER BY id DESC LIMIT 40"),
        "client_access": client_access_state(),
        "invitations": {"settings": {**INVITATION_DEFAULTS, **invitation_settings}},
        "system": {
            "operator": OPERATOR,
            "database": DB_SETTINGS["dbname"],
            "guest_url": GUEST_SITE_URL,
            "dashboard_url": DASHBOARD_URL,
            "heif_available": HEIF_AVAILABLE,
        },
    }


if os.environ.get("ECC_SKIP_SCHEMA") != "1":
    ensure_schema()


PUBLIC_READ_PATHS = {"/", "/guest-info", "/rsvp", "/gallery", "/contact", "/api/content", "/api/gallery"}
PUBLIC_WRITE_PATHS = {"/rsvp", "/api/rsvp"}


@app.before_request
def operator_boundary():
    path = request.path
    if request.method in {"GET", "HEAD"} and (
        path in PUBLIC_READ_PATHS or path.startswith("/static/") or path.startswith("/media/gallery/")
    ):
        return None
    if request.method == "POST" and path in PUBLIC_WRITE_PATHS:
        return None
    if not secrets.compare_digest(request.headers.get("X-ECC-Operator-Key", ""), OPERATOR_PROXY_KEY):
        abort(403)
    # Browser-origin check for privileged requests; prevents ordinary cross-site form POSTs.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("Origin")
        if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
            abort(403)
        if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
            abort(403)
    return None


@app.after_request
def add_headers(response):
    if request.path.startswith("/api/") or request.path.startswith("/dashboard") or request.path.startswith("/preview"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


def render_guest_site(initial_view: str, *, content_table: str = "content_live", preview_mode: bool = False, rsvp_result: dict | None = None):
    safe_view = initial_view if initial_view in GUEST_VIEWS else "home"
    return render_template(
        "guest-site.html",
        content=read_content(content_table),
        gallery=read_gallery(),
        initial_view=safe_view,
        preview_mode=preview_mode,
        rsvp_result=rsvp_result or {},
    )


@app.get("/")
def home():
    return render_guest_site("home")


@app.get("/guest-info")
def guest_info():
    return render_guest_site("guest-info")


@app.get("/gallery")
def gallery():
    return render_guest_site("gallery")


@app.get("/contact")
def contact():
    return render_guest_site("contact")


@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html", guest_site_url=GUEST_SITE_URL)


@app.get("/preview")
def preview():
    return render_guest_site("home", content_table="content_draft", preview_mode=True)


def clean_choice(value: Any, allowed: set[str], fallback: str) -> str:
    return str(value) if value in allowed else fallback


def clean_rsvp_payload(source: dict) -> dict:
    attendee_value = source.get("attendee_names", [])
    if isinstance(attendee_value, str):
        attendee_names = [name.strip() for name in attendee_value.splitlines() if name.strip()]
    elif isinstance(attendee_value, list):
        attendee_names = [str(name).strip() for name in attendee_value if str(name).strip()]
    else:
        attendee_names = []
    return {
        "party_name": str(source.get("party_name", "")).strip()[:250],
        "contact_name": str(source.get("contact_name", "")).strip()[:250],
        "email": str(source.get("email", "")).strip()[:250],
        "phone": str(source.get("phone", "")).strip()[:100],
        "guest_response": clean_choice(source.get("guest_response"), {"attending", "not_attending", "unsure"}, "unsure"),
        "attendee_names": attendee_names[:30],
        "dietary_note": str(source.get("dietary_note", "")).strip()[:2000],
        "allergy_note": str(source.get("allergy_note", "")).strip()[:2000],
        "plus_one_requested": source.get("plus_one_requested") in {True, "true", "yes", "on", "1"},
        "plus_one_name": str(source.get("plus_one_name", "")).strip()[:250],
        "party_note": str(source.get("party_note", "")).strip()[:4000],
    }


def save_rsvp(payload: dict, source_ip: str) -> int:
    with database_connection() as connection:
        submission = connection.execute(
            "INSERT INTO guest_submissions (source_ip,payload_json) VALUES (%s,%s) RETURNING id",
            (source_ip, Jsonb(payload)),
        ).fetchone()
        party = connection.execute(
            """
            INSERT INTO guest_parties (
                source_submission_id,party_name,contact_name,email,phone,guest_response,workflow_state,
                plus_one_requested,plus_one_name,plus_one_status,party_note
            ) VALUES (%s,%s,%s,%s,%s,%s,'new',%s,%s,%s,%s) RETURNING id
            """,
            (
                submission["id"],
                payload["party_name"],
                payload["contact_name"],
                payload["email"],
                payload["phone"],
                payload["guest_response"],
                payload["plus_one_requested"],
                payload["plus_one_name"],
                "pending" if payload["plus_one_requested"] else "not_applicable",
                payload["party_note"],
            ),
        ).fetchone()
        names = payload["attendee_names"] or [payload["contact_name"]]
        allergy_severity = "moderate" if payload["allergy_note"] else "none"
        for name in names:
            connection.execute(
                """
                INSERT INTO guest_attendees (
                    party_id,attendee_name,attendance_status,dietary_requirement,allergy_information,allergy_severity
                ) VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (
                    party["id"],
                    name,
                    "attending" if payload["guest_response"] == "attending" else payload["guest_response"],
                    payload["dietary_note"],
                    payload["allergy_note"],
                    allergy_severity,
                ),
            )
        if payload["email"]:
            duplicate_rows = connection.execute(
                "SELECT id FROM guest_parties WHERE id<>%s AND deleted_at IS NULL AND lower(email)=lower(%s)",
                (party["id"], payload["email"]),
            ).fetchall()
            if duplicate_rows:
                ids = [party["id"], *[row["id"] for row in duplicate_rows]]
                connection.execute(
                    "UPDATE guest_parties SET duplicate_review_state='possible',updated_at=NOW() WHERE id = ANY(%s)",
                    (ids,),
                )
        log_activity(connection, "rsvp_received", f"New RSVP received from {payload['party_name']}", {"party_id": party["id"]})
    return int(party["id"])


@app.route("/rsvp", methods=["GET", "POST"])
def rsvp():
    if request.method == "GET":
        return render_guest_site("rsvp")
    payload = clean_rsvp_payload(request.form)
    if not payload["party_name"] or not payload["contact_name"]:
        return render_guest_site(
            "rsvp",
            rsvp_result={"ok": False, "message": "Party name and primary contact are required."},
        ), 400
    save_rsvp(payload, request.headers.get("X-Real-IP", request.remote_addr or ""))
    return render_guest_site(
        "rsvp",
        rsvp_result={"ok": True, "message": "Your RSVP has been received and is waiting for host review."},
    )


@app.post("/api/rsvp")
def api_rsvp():
    payload = clean_rsvp_payload(request.get_json(silent=True) or {})
    if not payload["party_name"] or not payload["contact_name"]:
        return jsonify({"ok": False, "error": "Party name and primary contact are required."}), 400
    party_id = save_rsvp(payload, request.headers.get("X-Real-IP", request.remote_addr or ""))
    return jsonify({"ok": True, "party_id": party_id, "message": "Your RSVP has been received and is waiting for host review."})


@app.get("/api/content")
def public_content():
    return jsonify(read_content("content_live"))


@app.get("/api/gallery")
def public_gallery():
    return jsonify({"ok": True, "photos": read_gallery()})


@app.get("/media/gallery/<path:filename>")
def gallery_media(filename: str):
    clean = filename.replace("\\", "/").lstrip("/")
    if not (clean.startswith("display/") or clean.startswith("thumbnails/")):
        abort(404)
    candidate = (PHOTO_DATA_ROOT / clean).resolve()
    root = PHOTO_DATA_ROOT.resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        abort(404)
    operator_request = secrets.compare_digest(
        request.headers.get("X-ECC-Operator-Key", ""), OPERATOR_PROXY_KEY
    )
    if not operator_request:
        published = fetch_one(
            "SELECT 1 AS allowed FROM photo_triage WHERE source_kind='upload' "
            "AND show_in_gallery=TRUE AND (display_path=%s OR thumbnail_path=%s) LIMIT 1",
            (clean, clean),
        )
        if not published:
            abort(404)
    return send_from_directory(PHOTO_DATA_ROOT, clean, conditional=True, max_age=86400)


@app.get("/api/dashboard/state")
def api_dashboard_state():
    return jsonify(dashboard_state())


@app.post("/api/content/draft")
def save_draft():
    payload = request.get_json(silent=True) or {}
    fields = payload.get("fields", {})
    allowed = set(CONTENT_DEFAULTS)
    clean = {key: str(value).strip()[:12000] for key, value in fields.items() if key in allowed}
    if not clean:
        return jsonify({"ok": False, "error": "No valid content fields supplied."}), 400
    with database_connection() as connection:
        for key, value in clean.items():
            connection.execute(
                """
                INSERT INTO content_draft (key,value,updated_at) VALUES (%s,%s,NOW())
                ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()
                """,
                (key, value),
            )
        log_activity(connection, "draft_saved", f"Draft content saved ({len(clean)} fields)", {"fields": sorted(clean)})
    return jsonify({"ok": True, "saved_at": datetime.now().astimezone().isoformat()})


@app.post("/api/content/publish")
def publish_content():
    payload = request.get_json(silent=True) or {}
    note = str(payload.get("change_note", "")).strip()[:500]
    with database_connection() as connection:
        draft = {row["key"]: row["value"] for row in connection.execute("SELECT key,value FROM content_draft").fetchall()}
        for key, value in draft.items():
            connection.execute(
                """
                INSERT INTO content_live (key,value,updated_at) VALUES (%s,%s,NOW())
                ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()
                """,
                (key, value),
            )
        publication = connection.execute(
            "INSERT INTO publication_history (operator,change_note,content_json) VALUES (%s,%s,%s) RETURNING id,published_at",
            (OPERATOR, note, Jsonb(draft)),
        ).fetchone()
        log_activity(connection, "content_published", f"Website content published as version {publication['id']}", {"publication_id": publication["id"]})
    return jsonify({"ok": True, "publication": json_value(dict(publication))})


@app.post("/api/content/discard")
def discard_draft():
    with database_connection() as connection:
        connection.execute("DELETE FROM content_draft")
        connection.execute("INSERT INTO content_draft (key,value,updated_at) SELECT key,value,NOW() FROM content_live")
        log_activity(connection, "draft_discarded", "Draft reset to current live content")
    return jsonify({"ok": True})


@app.post("/api/content/restore/<int:publication_id>")
def restore_publication(publication_id: int):
    with database_connection() as connection:
        target = connection.execute("SELECT content_json FROM publication_history WHERE id=%s", (publication_id,)).fetchone()
        if not target:
            return jsonify({"ok": False, "error": "Publication not found."}), 404
        content = target["content_json"]
        connection.execute("DELETE FROM content_draft")
        connection.execute("DELETE FROM content_live")
        for key, value in content.items():
            connection.execute("INSERT INTO content_draft (key,value) VALUES (%s,%s)", (key, str(value)))
            connection.execute("INSERT INTO content_live (key,value) VALUES (%s,%s)", (key, str(value)))
        publication = connection.execute(
            """
            INSERT INTO publication_history (operator,change_note,content_json,restored_from)
            VALUES (%s,%s,%s,%s) RETURNING id,published_at
            """,
            (OPERATOR, f"Restored publication {publication_id}", Jsonb(content), publication_id),
        ).fetchone()
        log_activity(
            connection,
            "publication_restored",
            f"Restored publication {publication_id} as version {publication['id']}",
            {"restored_from": publication_id, "publication_id": publication["id"]},
        )
    return jsonify({"ok": True, "publication": json_value(dict(publication))})


@app.post("/api/parties/save")
def save_party():
    payload = request.get_json(silent=True) or {}
    party_id = payload.get("id")
    party_name = str(payload.get("party_name", "")).strip()[:250]
    if not party_name:
        return jsonify({"ok": False, "error": "Party name is required."}), 400
    guest_response = clean_choice(payload.get("guest_response"), {"attending", "not_attending", "unsure"}, "unsure")
    workflow_state = clean_choice(payload.get("workflow_state"), {"new", "reviewed", "needs_follow_up", "confirmed", "closed"}, "new")
    plus_one_status = clean_choice(payload.get("plus_one_status"), {"not_applicable", "pending", "approved", "declined"}, "not_applicable")
    attendees = payload.get("attendees", []) if isinstance(payload.get("attendees", []), list) else []
    with database_connection() as connection:
        if party_id:
            row = connection.execute(
                """
                UPDATE guest_parties SET party_name=%s,contact_name=%s,email=%s,phone=%s,guest_response=%s,
                    workflow_state=%s,plus_one_requested=%s,plus_one_name=%s,plus_one_status=%s,party_note=%s,
                    host_notes=%s,duplicate_review_state=%s,updated_at=NOW() WHERE id=%s RETURNING id
                """,
                (
                    party_name,
                    str(payload.get("contact_name", ""))[:250],
                    str(payload.get("email", ""))[:250],
                    str(payload.get("phone", ""))[:100],
                    guest_response,
                    workflow_state,
                    bool(payload.get("plus_one_requested")),
                    str(payload.get("plus_one_name", ""))[:250],
                    plus_one_status,
                    str(payload.get("party_note", ""))[:4000],
                    str(payload.get("host_notes", ""))[:4000],
                    clean_choice(payload.get("duplicate_review_state"), {"clear", "possible", "resolved"}, "clear"),
                    int(party_id),
                ),
            ).fetchone()
            if not row:
                return jsonify({"ok": False, "error": "Party not found."}), 404
            connection.execute("DELETE FROM guest_attendees WHERE party_id=%s", (party_id,))
            saved_id = int(party_id)
            action = "updated"
        else:
            row = connection.execute(
                """
                INSERT INTO guest_parties (party_name,contact_name,email,phone,guest_response,workflow_state,plus_one_requested,
                    plus_one_name,plus_one_status,party_note,host_notes,duplicate_review_state)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
                """,
                (
                    party_name,
                    str(payload.get("contact_name", ""))[:250],
                    str(payload.get("email", ""))[:250],
                    str(payload.get("phone", ""))[:100],
                    guest_response,
                    workflow_state,
                    bool(payload.get("plus_one_requested")),
                    str(payload.get("plus_one_name", ""))[:250],
                    plus_one_status,
                    str(payload.get("party_note", ""))[:4000],
                    str(payload.get("host_notes", ""))[:4000],
                    clean_choice(payload.get("duplicate_review_state"), {"clear", "possible", "resolved"}, "clear"),
                ),
            ).fetchone()
            saved_id = row["id"]
            action = "created"
        for attendee in attendees:
            name = str(attendee.get("attendee_name", "")).strip()[:250]
            if not name:
                continue
            connection.execute(
                """
                INSERT INTO guest_attendees (party_id,attendee_name,attendance_status,dietary_requirement,allergy_information,
                    allergy_severity,accessibility_note,private_note) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    saved_id,
                    name,
                    clean_choice(attendee.get("attendance_status"), {"attending", "not_attending", "unsure"}, "attending"),
                    str(attendee.get("dietary_requirement", ""))[:1000],
                    str(attendee.get("allergy_information", ""))[:1000],
                    clean_choice(attendee.get("allergy_severity"), {"none", "mild", "moderate", "severe"}, "none"),
                    str(attendee.get("accessibility_note", ""))[:1000],
                    str(attendee.get("private_note", ""))[:1000],
                ),
            )
        log_activity(connection, f"party_{action}", f"Guest party {party_name} {action}", {"party_id": saved_id})
    return jsonify({"ok": True, "id": saved_id})


@app.post("/api/parties/<int:party_id>/delete")
def delete_party(party_id: int):
    payload = request.get_json(silent=True) or {}
    with database_connection() as connection:
        row = connection.execute(
            """
            UPDATE guest_parties SET deleted_at=NOW(),deleted_reason=%s,updated_at=NOW()
            WHERE id=%s RETURNING party_name
            """,
            (str(payload.get("reason", ""))[:500], party_id),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Party not found."}), 404
        log_activity(connection, "party_deleted", f"Guest party {row['party_name']} moved to Deleted Records", {"party_id": party_id})
    return jsonify({"ok": True})


@app.post("/api/parties/<int:party_id>/restore")
def restore_party(party_id: int):
    with database_connection() as connection:
        row = connection.execute(
            "UPDATE guest_parties SET deleted_at=NULL,deleted_reason='',updated_at=NOW() WHERE id=%s RETURNING party_name",
            (party_id,),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Party not found."}), 404
        log_activity(connection, "party_restored", f"Guest party {row['party_name']} restored", {"party_id": party_id})
    return jsonify({"ok": True})


def canonical_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


CSV_ALIASES = {
    "party": "party_name",
    "party_name": "party_name",
    "household": "party_name",
    "household_name": "party_name",
    "contact": "contact_name",
    "contact_name": "contact_name",
    "primary_contact": "contact_name",
    "name": "contact_name",
    "email": "email",
    "email_address": "email",
    "phone": "phone",
    "phone_number": "phone",
    "response": "guest_response",
    "rsvp": "guest_response",
    "guest_response": "guest_response",
    "attendees": "attendee_names",
    "attendee_names": "attendee_names",
    "guest_names": "attendee_names",
    "notes": "party_note",
    "note": "party_note",
    "party_note": "party_note",
}


@app.get("/api/parties/import-template.csv")
def import_template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["party_name", "contact_name", "email", "phone", "guest_response", "attendee_names", "party_note"])
    writer.writerow(["Smith household", "Jane Smith", "jane@example.com", "021 000 0000", "unsure", "Jane Smith | Robert Smith", ""])
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=event-command-center-guest-import-template.csv"
    return response


@app.post("/api/parties/import-csv")
def import_parties_csv():
    upload = request.files.get("csv_file")
    if not upload or not upload.filename:
        return jsonify({"ok": False, "error": "Choose a CSV file."}), 400
    raw = upload.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        return jsonify({"ok": False, "error": "CSV file is larger than 2 MB."}), 400
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify({"ok": False, "error": "CSV must use UTF-8 text."}), 400
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return jsonify({"ok": False, "error": "CSV header row is missing."}), 400
    header_map = {header: CSV_ALIASES.get(canonical_header(header), canonical_header(header)) for header in reader.fieldnames}
    created = 0
    skipped = 0
    errors: list[str] = []
    with database_connection() as connection:
        for line_number, source_row in enumerate(reader, start=2):
            if line_number > 5001:
                errors.append("Import stopped after 5,000 rows.")
                break
            row = {header_map[key]: (value or "").strip() for key, value in source_row.items() if key}
            party_name = row.get("party_name", "")[:250]
            contact_name = row.get("contact_name", "")[:250]
            if not party_name:
                skipped += 1
                if len(errors) < 25:
                    errors.append(f"Line {line_number}: party_name is required.")
                continue
            response_value = row.get("guest_response", "unsure").lower().replace(" ", "_")
            guest_response = response_value if response_value in {"attending", "not_attending", "unsure"} else "unsure"
            party = connection.execute(
                """
                INSERT INTO guest_parties (party_name,contact_name,email,phone,guest_response,workflow_state,party_note)
                VALUES (%s,%s,%s,%s,%s,'new',%s) RETURNING id
                """,
                (party_name, contact_name, row.get("email", "")[:250], row.get("phone", "")[:100], guest_response, row.get("party_note", "")[:4000]),
            ).fetchone()
            attendee_text = row.get("attendee_names", "")
            names = [name.strip() for name in re.split(r"[|;\n]+", attendee_text) if name.strip()]
            if not names and contact_name:
                names = [contact_name]
            for name in names[:30]:
                connection.execute(
                    "INSERT INTO guest_attendees (party_id,attendee_name,attendance_status) VALUES (%s,%s,%s)",
                    (party["id"], name[:250], "attending" if guest_response == "attending" else guest_response),
                )
            created += 1
        log_activity(connection, "guest_csv_imported", f"Guest CSV import created {created} parties", {"created": created, "skipped": skipped})
    return jsonify({"ok": True, "created": created, "skipped": skipped, "errors": errors})


def normalise_image_mode(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        return image.convert("RGBA")
    return image.convert("RGB")


def safe_photo_file(relative_path: str) -> Path:
    root = PHOTO_DATA_ROOT.resolve()
    candidate = (PHOTO_DATA_ROOT / str(relative_path).replace("\\", "/").lstrip("/")).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Unsafe photo path")
    return candidate


def process_photo_upload(upload) -> dict:
    original_name = secure_filename(upload.filename or "")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_PHOTO_EXTENSIONS:
        raise ValueError("Unsupported format. Use JPG, PNG, WebP, HEIC or HEIF.")
    if extension in {".heic", ".heif"} and not HEIF_AVAILABLE:
        raise ValueError("HEIC/HEIF support is not installed on this server.")

    photo_id = uuid.uuid4().hex
    original_relative = f"originals/{photo_id}{extension}"
    display_relative = f"display/{photo_id}.webp"
    thumbnail_relative = f"thumbnails/{photo_id}.webp"
    original_path = safe_photo_file(original_relative)
    display_path = safe_photo_file(display_relative)
    thumbnail_path = safe_photo_file(thumbnail_relative)
    original_path.parent.mkdir(parents=True, exist_ok=True)
    display_path.parent.mkdir(parents=True, exist_ok=True)
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

    upload.save(original_path)
    file_size = original_path.stat().st_size
    if file_size > MAX_PHOTO_BYTES:
        original_path.unlink(missing_ok=True)
        raise ValueError(f"{original_name} is larger than the {MAX_PHOTO_BYTES // (1024 * 1024)} MB per-photo limit.")

    try:
        with Image.open(original_path) as opened:
            opened.load()
            image = ImageOps.exif_transpose(opened)
            width, height = image.size
            display = normalise_image_mode(image.copy())
            display.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            display.save(display_path, "WEBP", quality=86, method=6)
            thumbnail = normalise_image_mode(image.copy())
            thumbnail.thumbnail((560, 420), Image.Resampling.LANCZOS)
            thumbnail.save(thumbnail_path, "WEBP", quality=80, method=6)
    except Exception:
        original_path.unlink(missing_ok=True)
        display_path.unlink(missing_ok=True)
        thumbnail_path.unlink(missing_ok=True)
        raise

    return {
        "photo_id": photo_id,
        "asset_path": original_relative,
        "original_filename": original_name,
        "display_path": display_relative,
        "thumbnail_path": thumbnail_relative,
        "mime_type": upload.mimetype or "",
        "file_size": file_size,
        "width": width,
        "height": height,
    }


@app.post("/api/photos/upload")
def upload_photos():
    uploads = [item for item in request.files.getlist("photos") if item and item.filename]
    if not uploads:
        return jsonify({"ok": False, "error": "Choose one or more photographs."}), 400
    if len(uploads) > 100:
        return jsonify({"ok": False, "error": "Upload a maximum of 100 photographs at a time."}), 400
    saved: list[dict] = []
    errors: list[str] = []
    for upload in uploads:
        record = None
        try:
            record = process_photo_upload(upload)
            with database_connection() as connection:
                connection.execute(
                    """
                    INSERT INTO photo_triage (
                        asset_path,photo_id,original_filename,display_path,thumbnail_path,category,comment,alt_text,
                        display_order,show_in_gallery,source_kind,mime_type,file_size,width,height,created_at,updated_at
                    ) VALUES (%s,%s,%s,%s,%s,'private','','',0,FALSE,'upload',%s,%s,%s,%s,NOW(),NOW())
                    """,
                    (
                        record["asset_path"],
                        record["photo_id"],
                        record["original_filename"],
                        record["display_path"],
                        record["thumbnail_path"],
                        record["mime_type"],
                        record["file_size"],
                        record["width"],
                        record["height"],
                    ),
                )
                log_activity(connection, "photo_uploaded", f"Photo uploaded: {record['original_filename']}", {"photo_id": record["photo_id"]})
            saved.append(record)
        except Exception as exc:
            if record:
                for key in ("asset_path", "display_path", "thumbnail_path"):
                    try:
                        safe_photo_file(record[key]).unlink(missing_ok=True)
                    except Exception:
                        pass
            errors.append(f"{upload.filename}: {exc}")
    if not saved:
        return jsonify({"ok": False, "error": errors[0] if errors else "No photographs were saved.", "errors": errors}), 400
    return jsonify({"ok": True, "saved": len(saved), "errors": errors})


@app.post("/api/photos/save")
def save_photo():
    payload = request.get_json(silent=True) or {}
    photo_id = str(payload.get("photo_id", "")).strip()
    if not photo_id:
        return jsonify({"ok": False, "error": "Photo ID is required."}), 400
    try:
        display_order = int(payload.get("display_order", 0) or 0)
    except (TypeError, ValueError):
        display_order = 0
    show_in_gallery = bool(payload.get("show_in_gallery"))
    caption = str(payload.get("caption", payload.get("comment", ""))).strip()[:1000]
    alt_text = str(payload.get("alt_text", "")).strip()[:500]
    with database_connection() as connection:
        row = connection.execute(
            """
            UPDATE photo_triage SET category=%s,comment=%s,alt_text=%s,display_order=%s,
                show_in_gallery=%s,updated_at=NOW()
            WHERE photo_id=%s AND source_kind='upload' RETURNING original_filename
            """,
            ("gallery" if show_in_gallery else "private", caption, alt_text, display_order, show_in_gallery, photo_id),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Photo not found."}), 404
        log_activity(
            connection,
            "photo_updated",
            f"Photo updated: {row['original_filename']}",
            {"photo_id": photo_id, "show_in_gallery": show_in_gallery},
        )
    return jsonify({"ok": True})


@app.post("/api/photos/<photo_id>/delete")
def delete_photo(photo_id: str):
    with database_connection() as connection:
        row = connection.execute(
            """
            SELECT asset_path,display_path,thumbnail_path,original_filename
            FROM photo_triage WHERE photo_id=%s AND source_kind='upload'
            """,
            (photo_id,),
        ).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Photo not found."}), 404
        for key in ("asset_path", "display_path", "thumbnail_path"):
            if row[key]:
                safe_photo_file(row[key]).unlink(missing_ok=True)
        connection.execute("DELETE FROM photo_triage WHERE photo_id=%s", (photo_id,))
        log_activity(connection, "photo_deleted", f"Photo permanently deleted: {row['original_filename']}", {"photo_id": photo_id})
    return jsonify({"ok": True})


@app.post("/api/invitations/settings")
def save_invitation_settings():
    payload = request.get_json(silent=True) or {}
    clean = {
        "invitation_subject": str(payload.get("invitation_subject", "")).strip()[:300],
        "invitation_message": str(payload.get("invitation_message", "")).strip()[:12000],
        "event_site_link": str(payload.get("event_site_link", "")).strip()[:1000],
    }
    with database_connection() as connection:
        for key, value in clean.items():
            connection.execute(
                """
                INSERT INTO app_settings (key,value,updated_at) VALUES (%s,%s,NOW())
                ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()
                """,
                (key, value),
            )
        log_activity(connection, "invitation_settings_saved", "Invitation email settings saved")
    return jsonify({"ok": True})


def clean_party_ids(payload: dict) -> list[int]:
    result = []
    for value in payload.get("party_ids", []):
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(result))[:5000]


@app.post("/api/invitations/prepare")
def prepare_invitations():
    payload = request.get_json(silent=True) or {}
    ids = clean_party_ids(payload)
    if not ids:
        return jsonify({"ok": False, "error": "Select at least one guest party."}), 400
    with database_connection() as connection:
        candidates = connection.execute(
            """
            SELECT id,email,party_name,invitation_status
            FROM guest_parties
            WHERE id = ANY(%s) AND deleted_at IS NULL AND email<>''
            ORDER BY id
            """,
            (ids,),
        ).fetchall()
        recipients = [dict(row) for row in candidates if EMAIL_PATTERN.match(row["email"] or "")]
        valid_ids = [row["id"] for row in recipients]
        if not valid_ids:
            return jsonify({"ok": False, "error": "The selected records do not contain valid email addresses."}), 400
        rows = connection.execute(
            """
            UPDATE guest_parties SET invitation_status=CASE WHEN invitation_status='sent' THEN 'sent' ELSE 'prepared' END,
                invitation_prepared_at=COALESCE(invitation_prepared_at,NOW()),updated_at=NOW()
            WHERE id = ANY(%s) RETURNING id,invitation_status
            """,
            (valid_ids,),
        ).fetchall()
        statuses = {row["id"]: row["invitation_status"] for row in rows}
        for recipient in recipients:
            recipient["invitation_status"] = statuses.get(recipient["id"], recipient["invitation_status"])
        log_activity(
            connection,
            "invitations_prepared",
            f"Prepared invitation email for {len(recipients)} guest parties",
            {"party_ids": valid_ids},
        )
    return jsonify({"ok": True, "recipients": recipients})


@app.post("/api/invitations/status")
def set_invitation_status():
    payload = request.get_json(silent=True) or {}
    ids = clean_party_ids(payload)
    status = clean_choice(payload.get("status"), {"not_prepared", "prepared", "sent"}, "not_prepared")
    if not ids:
        return jsonify({"ok": False, "error": "Select at least one guest party."}), 400
    with database_connection() as connection:
        connection.execute(
            """
            UPDATE guest_parties SET invitation_status=%s,
                invitation_prepared_at=CASE WHEN %s IN ('prepared','sent') THEN COALESCE(invitation_prepared_at,NOW()) ELSE NULL END,
                invitation_sent_at=CASE WHEN %s='sent' THEN NOW() ELSE NULL END,
                updated_at=NOW()
            WHERE id = ANY(%s) AND deleted_at IS NULL
            """,
            (status, status, status, ids),
        )
        log_activity(connection, "invitation_status_changed", f"Invitation status set to {status} for {len(ids)} parties", {"party_ids": ids, "status": status})
    return jsonify({"ok": True})


@app.post("/api/client-access/<action>")
def client_access_action(action: str):
    if action not in {"open", "close", "status"}:
        return jsonify({"ok": False, "error": "Invalid client-access action."}), 400
    env_key = {
        "open": "CLIENT_ACCESS_OPEN_COMMAND",
        "close": "CLIENT_ACCESS_CLOSE_COMMAND",
        "status": "CLIENT_ACCESS_STATUS_COMMAND",
    }[action]
    result = run_fixed_command(env_key)
    if not result["configured"]:
        return jsonify({"ok": False, "error": "Client-access command is not configured."}), 503
    if not result["ok"]:
        return jsonify({"ok": False, "error": result["output"] or "Client-access command failed."}), 500
    if action in {"open", "close"}:
        state = action
    else:
        status_text = result["output"].strip().lower()
        closed_markers = ("closed", "stopped", "inactive", "not running", "down")
        open_markers = ("open", "running", "active", "connected", "up")
        if any(marker in status_text for marker in closed_markers):
            state = "closed"
        elif any(marker in status_text for marker in open_markers):
            state = "open"
        else:
            state = "status_checked"
    with database_connection() as connection:
        connection.execute(
            """
            INSERT INTO app_settings (key,value,updated_at) VALUES ('client_access_state',%s,NOW())
            ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()
            """,
            (state,),
        )
        log_activity(connection, "client_access_action", f"Client access action: {action}", {"output": result["output"]})
    return jsonify({"ok": True, "state": state, "output": result["output"]})


def save_simple(table: str, fields: list[str], required: str, event_name: str):
    payload = request.get_json(silent=True) or {}
    item_id = payload.get("id")
    if not str(payload.get(required, "")).strip():
        return jsonify({"ok": False, "error": f"{required.replace('_', ' ').title()} is required."}), 400
    values = []
    for field in fields:
        value = payload.get(field, "")
        if field == "sort_order":
            try:
                value = int(value or 0)
            except (TypeError, ValueError):
                value = 0
        elif field == "done":
            value = bool(value)
        elif field in {"estimated", "actual"}:
            try:
                value = float(value or 0)
            except (TypeError, ValueError):
                value = 0
        else:
            value = str(value).strip()[:4000]
        values.append(value)
    with database_connection() as connection:
        if item_id:
            assignments = ",".join(f"{field}=%s" for field in fields)
            row = connection.execute(
                f"UPDATE {table} SET {assignments},updated_at=NOW() WHERE id=%s RETURNING id",
                (*values, int(item_id)),
            ).fetchone()
            if not row:
                return jsonify({"ok": False, "error": "Item not found."}), 404
            saved_id = row["id"]
            verb = "updated"
        else:
            columns = ",".join(fields)
            placeholders = ",".join(["%s"] * len(fields))
            row = connection.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id", tuple(values)
            ).fetchone()
            saved_id = row["id"]
            verb = "created"
        log_activity(connection, f"{event_name}_{verb}", f"{event_name.replace('_',' ').title()} {verb}", {"id": saved_id})
    return jsonify({"ok": True, "id": saved_id})


def delete_simple(table: str, item_id: int, event_name: str):
    with database_connection() as connection:
        row = connection.execute(f"DELETE FROM {table} WHERE id=%s RETURNING id", (item_id,)).fetchone()
        if not row:
            return jsonify({"ok": False, "error": "Item not found."}), 404
        log_activity(connection, f"{event_name}_deleted", f"{event_name.replace('_',' ').title()} deleted", {"id": item_id})
    return jsonify({"ok": True})


@app.post("/api/run-sheet/save")
def save_run_sheet():
    return save_simple("run_sheet_items", ["start_time", "title", "details", "owner", "sort_order", "done"], "title", "run_sheet_item")


@app.post("/api/run-sheet/<int:item_id>/delete")
def delete_run_sheet(item_id):
    return delete_simple("run_sheet_items", item_id, "run_sheet_item")


@app.post("/api/checklist/save")
def save_checklist():
    return save_simple("checklist_items", ["title", "status", "due_date", "owner", "notes"], "title", "checklist_item")


@app.post("/api/checklist/<int:item_id>/delete")
def delete_checklist(item_id):
    return delete_simple("checklist_items", item_id, "checklist_item")


@app.post("/api/budget/save")
def save_budget():
    return save_simple("budget_items", ["item", "category", "vendor", "estimated", "actual", "payment_status", "due_date", "notes"], "item", "budget_item")


@app.post("/api/budget/<int:item_id>/delete")
def delete_budget(item_id):
    return delete_simple("budget_items", item_id, "budget_item")


@app.post("/api/vendors/save")
def save_vendor():
    return save_simple("vendors", ["name", "service", "contact_name", "email", "phone", "status", "notes"], "name", "vendor")


@app.post("/api/vendors/<int:item_id>/delete")
def delete_vendor(item_id):
    return delete_simple("vendors", item_id, "vendor")


@app.get("/health")
def health():
    with database_connection() as connection:
        connection.execute("SELECT 1").fetchone()
    return jsonify(
        {
            "status": "ok",
            "database": DB_SETTINGS["dbname"],
            "service": "event-command-center",
            "schema": "v2-complete",
            "photo_root": str(PHOTO_DATA_ROOT),
            "heif": HEIF_AVAILABLE,
        }
    )
