import base64
import calendar
import csv
import html as html_lib
import hashlib
import io
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import quote_plus

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client

BRAND_NAME = "Tradylo"
BRAND_TAGLINE = "Trading Journal"
LOGO_PATH = Path("assets/tradylo-logo.png")

st.set_page_config(
    page_title=BRAND_NAME,
    layout="wide",
    page_icon=str(LOGO_PATH),
    initial_sidebar_state="expanded",
)
st.markdown("""
<style>
/* Brand accents */
:root{
  --accent-purple: rgba(124,58,237,1);
  --accent-blue: rgba(56,189,248,1);
  --accent-grad: linear-gradient(135deg, rgba(124,58,237,0.24) 0%, rgba(56,189,248,0.18) 52%, rgba(14,17,23,0.0) 100%);
  --panel-bg: rgba(255,255,255,0.045);
  --panel-brd: rgba(255,255,255,0.08);
  --tz-muted: rgba(148,163,184,0.92);
  --tz-title: rgba(230,237,243,0.98);
}

/* Main background glow (subtle, doesn't fight dark theme) */
div[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(1200px 600px at 16% 8%, rgba(124,58,237,0.18) 0%, rgba(14,17,23,0) 55%),
    radial-gradient(900px 520px at 74% 18%, rgba(56,189,248,0.10) 0%, rgba(14,17,23,0) 60%),
    radial-gradient(900px 520px at 50% 100%, rgba(124,58,237,0.10) 0%, rgba(14,17,23,0) 55%),
    #0E1117;
}

/* Section/card surfaces */
.metric-card,
.calendar-card,
div[data-testid="stMetric"],
div[data-testid="stExpander"] > div,
div[data-testid="stPlotlyChart"],
div[data-testid="stVegaLiteChart"],
div[data-testid="stChart"],
div[data-testid="stDataFrame"]{
  background-image: var(--accent-grad);
  background-blend-mode: soft-light;
}

/* Metric cards (used in demo + logged-in) */
.metric-grid {display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:10px 0 12px;}
.metric-card {background: rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:14px;
  padding:12px 14px; box-shadow: 0 10px 30px rgba(0,0,0,0.18); }
.metric-label {font-size:12px;color:var(--tz-muted);letter-spacing:.06em;text-transform:uppercase}
.metric-value {font-size:22px;font-weight:700;color:var(--tz-title);margin-top:2px}
.metric-sub {font-size:12px;color:rgba(148,163,184,0.9);margin-top:6px}
@media (max-width: 1200px) {.metric-grid {grid-template-columns:repeat(2,minmax(0,1fr));}}
@media (max-width: 768px) {.metric-grid {grid-template-columns:1fr;}}

/* PnL calendar (used in demo + logged-in) */
.calendar-card {border-radius:16px;border:1px solid rgba(255,255,255,0.08); padding:14px; box-shadow: 0 12px 36px rgba(0,0,0,0.22);}
.calendar-wrap {display:grid;grid-template-columns:1fr 150px;gap:12px;align-items:start}
.calendar-grid {display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px}
.calendar-weeks {display:flex;flex-direction:column;gap:8px}
.cal-head {text-align:center;font-size:11px;color:rgba(148,163,184,0.9);text-transform:uppercase;letter-spacing:.10em}
.cal-cell {border-radius:12px;padding:10px 10px 12px;min-height:92px;border:1px solid rgba(255,255,255,0.10);
  display:flex;flex-direction:column;gap:6px; box-shadow: inset 0 0 0 1px rgba(0,0,0,0.06);}
.cal-cell:hover {transform: translateY(-1px); transition: transform 120ms ease;}
.cal-off {opacity:0.32}
.cal-day {font-size:12px;color:rgba(148,163,184,0.95)}
.cal-pnl {font-size:15px;font-weight:700;color:rgba(230,237,243,0.98);margin-top:auto}
.cal-trades {font-size:11px;color:rgba(148,163,184,0.92)}
.cal-week {background: rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.10);border-radius:14px;
  padding:10px 10px 12px;display:flex;flex-direction:column;gap:4px}
.cal-week-label {font-size:11px;color:rgba(148,163,184,0.9);text-transform:uppercase;letter-spacing:.10em}
.cal-week-total {font-size:14px;font-weight:700;color:rgba(230,237,243,0.98)}
.cal-week-trades {font-size:11px;color:rgba(148,163,184,0.92)}
@media (max-width: 900px) {.calendar-wrap {grid-template-columns:1fr;}}

/* Buttons: give a bit more "product" feel */
.stButton > button{
  border-radius: 12px !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  background: rgba(255,255,255,0.05) !important;
}
.stButton > button:hover{
  border-color: rgba(124,58,237,0.35) !important;
  background: rgba(124,58,237,0.10) !important;
}

/* Sidebar (Tradezella-ish) */
section[data-testid="stSidebar"] > div {
  background: radial-gradient(1200px 420px at 20% 0%, rgba(124,58,237,0.28) 0%, rgba(14,17,23,0.0) 55%),
              radial-gradient(900px 380px at 60% 40%, rgba(56,189,248,0.12) 0%, rgba(14,17,23,0.0) 65%),
              #0B0F14;
  border-right: 1px solid rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] .stButton > button {
  border-radius: 12px !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"] {
  border-radius: 12px;
  padding: 6px 8px;
  margin: 2px 0;
}
section[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"]:hover {
  background: rgba(255,255,255,0.06);
}
section[data-testid="stSidebar"] div[role="radiogroup"] label[data-baseweb="radio"] input:checked + div {
  background: rgba(124,58,237,0.18);
  border-radius: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(124,58,237,0.30);
}
section[data-testid="stSidebar"] .sidebar-usercard {
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.08);
}
section[data-testid="stSidebar"] .sidebar-usercard .small {
  color: rgba(148,163,184,0.95);
  font-size: 12px;
}
section[data-testid="stSidebar"] .sidebar-usercard .value {
  color: rgba(230,237,243,0.96);
  font-size: 13px;
  font-weight: 600;
  word-break: break-word;
}

 .brand-row {display:flex;align-items:center;gap:12px;margin:6px 0 12px;}
 .brand-row.center {justify-content:center;text-align:center;flex-direction:column;}
 .brand-row.hero {gap:16px;margin:10px 0 18px;}
 .brand-logo {width:140px;height:140px;border-radius:26px;object-fit:contain;background:rgba(255,255,255,0.04);
              border:1px solid rgba(255,255,255,0.08);padding:6px;}
 .brand-name {font-size:40px;font-weight:700;color:var(--text-color);margin:0;line-height:1.1;}
 .brand-tagline {font-size:13px;color:rgba(148, 163, 184, 0.9);letter-spacing:.08em;text-transform:uppercase;}
 .brand-row.center .brand-logo {width:220px;height:220px;border-radius:32px;padding:12px;}
 .brand-row.center .brand-name {font-size:56px;}
 .brand-row.hero .brand-logo {width:350px;height:350px;border-radius:40px;padding:14px;}
 .brand-row.hero .brand-name {font-size:48px;}
div[data-testid="stMetric"] {
  background: rgba(255,255,255,0.06);
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.10);
}
div[data-testid="stMetric"] * { color: inherit !important; }

div[data-testid="stExpander"] > div {
  background: rgba(255,255,255,0.04);
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.08);
}

.stTextInput input, 
.stTextArea textarea, 
.stNumberInput input,
.stSelectbox div {
  color: inherit !important;
}
</style>
""", unsafe_allow_html=True)

# ── Supabase client ──────────────────────────────────────────────────────────
def get_secret_required(name: str, fallback_names: Optional[list] = None) -> str:
    names = [name] + (fallback_names or [])
    for n in names:
        try:
            v = st.secrets[n]
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
        except Exception:
            continue
    raise KeyError(f"Missing required secret: {name}")

try:
    SUPABASE_URL = get_secret_required("SUPABASE_URL", ["SUPABASE_PROJECT_URL"])
    # Accept legacy names to reduce “invalid api key” confusion when users follow older guides.
    SUPABASE_KEY = get_secret_required("SUPABASE_KEY", ["SUPABASE_ANON_KEY", "SUPABASE_PUBLIC_ANON_KEY"])
except KeyError:
    st.error("App misconfigured: missing Supabase secrets.")
    st.caption("Set `SUPABASE_URL` and `SUPABASE_KEY` in Streamlit Community Cloud → App → Settings → Secrets, then restart the app.")
    st.stop()


def _extract_supabase_ref_from_url(url: str) -> str:
    # https://<ref>.supabase.co
    s = ("" if url is None else str(url)).strip()
    m = re.search(r"https?://([a-z0-9-]+)\\.supabase\\.co", s, flags=re.I)
    return (m.group(1) if m else "").strip()


def _extract_ref_from_jwt(jwt_token: str) -> str:
    tok = ("" if jwt_token is None else str(jwt_token)).strip()
    parts = tok.split(".")
    if len(parts) < 2:
        return ""
    payload_b64 = parts[1]
    # Base64url padding
    payload_b64 += "=" * (-len(payload_b64) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8"))
        return ("" if payload.get("ref") is None else str(payload.get("ref"))).strip()
    except Exception:
        return ""


# Helpful sanity check: if URL and key belong to different Supabase projects, auth will always fail.
_url_ref = _extract_supabase_ref_from_url(SUPABASE_URL)
_key_ref = _extract_ref_from_jwt(SUPABASE_KEY)
if _url_ref and _key_ref and _url_ref != _key_ref:
    st.error("Supabase secrets mismatch: your URL and anon key are from different projects.")
    st.caption(f"URL project ref: `{_url_ref}` · Key project ref: `{_key_ref}`")
    st.caption("Fix Streamlit secrets: set `SUPABASE_URL` and `SUPABASE_KEY` from the SAME Supabase project (Settings → API).")
    st.stop()

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

# ── Constants ─────────────────────────────────────────────────────────────────
ACCOUNT_TYPES = ["Evaluation Account Data", "Funded Account Data", "Live Account Data"]

INSTRUMENTS = {"NQ": 20, "MNQ": 2, "ES": 50, "MES": 5, "GC": 100, "MGC": 10}
INSTRUMENT_ORDER = list(INSTRUMENTS.keys())

# Forex support (simple USD-account assumptions)
# - `contracts` is treated as lots (1 lot = 100k base) for forex pairs.
# - Pip value for USDJPY is computed from entry price (pip = 0.01).
FOREX_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
INSTRUMENT_ORDER = INSTRUMENT_ORDER + FOREX_PAIRS
SESSIONS = ["NY", "London", "Asia", "Pre-market"]
MARKET_CONDITIONS = ["Not set", "Trend", "Range", "Volatile", "News", "Mixed/Unsure"]
TRADE_GRADES = ["Not set", "A++", "A+", "A", "B+", "B", "C", "D"]
TRADE_TYPES = ["Not set", "Continuation model", "Reversal", "Other"]
TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
CONFLUENCES = [
    "V shape", "1/2/3/5 minute IVFG", "15/30 minute or 1 hour IVFG",
    "Breaker block", "Unicorn breaker", "Clear draws on liquidity",
    "Session high/low sweep", "RELS/REH for draw on liquidity", "Order block",
    "HTF FVG", "BPR tap", "1st presented FVG tap", "LRLR",
    "Very cheap RR trade", "SMT", "AMD", "Manipulation leg",
]

NUMERIC_COLUMNS = [
    "entry_price", "stop_loss", "take_profit", "exit_price", "contracts",
    "emotion_score", "account_size", "risk_percent_planned", "commission",
    "slippage", "pnl_override", "max_favorable_price", "max_adverse_price",
    "points", "pnl_gross", "pnl_net", "pnl_per_contract", "r_multiple",
    "target_r", "mfe_points", "mae_points", "mfe_r", "mae_r", "missed_pnl",
    "risk_dollars", "risk_percent_actual", "duration_minutes",
]

COMPUTED_COLUMNS = [
    "points", "pnl_gross", "pnl_net", "pnl_per_contract", "r_multiple",
    "target_r", "mfe_points", "mae_points", "mfe_r", "mae_r", "missed_pnl",
    "risk_dollars", "risk_percent_actual", "duration_minutes",
]

# ── Monetization / entitlements (feature-flagged) ─────────────────────────────

FREE_TRADE_LIMIT = 15


def get_secret(key: str, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return default


def truthy(value) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "y", "on")


# Keep this OFF while we're building so signups/users aren't impacted.
# When you're ready to launch pricing, set `PAYWALL_ENABLED=true` in Streamlit secrets.
PAYWALL_ENABLED = truthy(get_secret("PAYWALL_ENABLED", "false"))

AFFILIATES_ENABLED = truthy(get_secret("AFFILIATES_ENABLED", "false"))
STRIPE_ENABLED = truthy(get_secret("STRIPE_ENABLED", "false"))
SUPPORT_CONTACT_EMAIL = str(get_secret("SUPPORT_CONTACT_EMAIL", "") or "").strip()
PUBLIC_CONTACT_EMAIL = str(get_secret("PUBLIC_CONTACT_EMAIL", "support@tradylojournal.com") or "").strip()
ADMIN_EMAILS = str(get_secret("ADMIN_EMAILS", "") or "").strip()
TRIAL_DAYS = int(str(get_secret("TRIAL_DAYS", "0") or "0").strip() or 0)

# Pricing (prepared only; not displayed publicly until you say go)
REFUND_WINDOW_DAYS = 1
PRICING_PLANS_USD = {
    "monthly": {"label": "Monthly", "usd_per_month": 19, "billing_months": 1},
    "quarterly": {"label": "3-month", "usd_per_month": 16, "billing_months": 3},
    "yearly": {"label": "Yearly", "usd_per_month": 14, "billing_months": 12},
}


def is_admin_email(email: str) -> bool:
    email = safe_str(email).strip().lower()
    if not email:
        return False
    allow = []
    for v in [SUPPORT_CONTACT_EMAIL, ADMIN_EMAILS]:
        s = safe_str(v).strip()
        if not s:
            continue
        allow.extend([x.strip().lower() for x in s.split(",") if x.strip()])
    return email in set(allow)


def invoke_edge_function(function_name: str, payload: dict) -> tuple[bool, str]:
    """
    Call a Supabase Edge Function. Uses anon key headers to satisfy gateway requirements.
    Returns (ok, response_text).
    """
    try:
        import urllib.request

        url = f"{SUPABASE_URL}/functions/v1/{function_name}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        # These headers are safe for Edge Function invocation (do NOT use service role in Streamlit).
        req.add_header("apikey", SUPABASE_KEY)
        req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return True, body
    except Exception as e:
        return False, safe_str(e)


def admin_create_test_commission(affiliate_user_id: str, amount_cents: int = 1900, pct: int = 20) -> tuple[bool, str]:
    """
    Insert a single pending commission row for pipeline testing.
    Uses service-role only when the admin explicitly triggers it.
    """
    try:
        service_key = str(get_secret("SUPABASE_SERVICE_ROLE_KEY", "") or "").strip()
        if not service_key:
            return False, "Missing SUPABASE_SERVICE_ROLE_KEY in Streamlit secrets."
        sb_admin = create_client(SUPABASE_URL, service_key)
        inv = f"inv_test_manual_{uuid.uuid4().hex[:8]}"
        commission_cents = int(round(amount_cents * (pct / 100.0)))
        row = {
            "affiliate_user_id": affiliate_user_id,
            "referred_user_id": affiliate_user_id,
            "stripe_invoice_id": inv,
            "stripe_customer_id": f"cus_test_{uuid.uuid4().hex[:8]}",
            "amount_cents": int(amount_cents),
            "commission_cents": int(commission_cents),
            "currency": "usd",
            "status": "pending",
            "available_at": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
        }
        sb_admin.table("affiliate_commissions").insert(row).execute()
        return True, f"Created test commission {inv} (${amount_cents/100:.2f} -> ${commission_cents/100:.2f})."
    except Exception as e:
        return False, safe_str(e)


def admin_upsert_affiliate_code(affiliate_user_id: str, code: str, commission_percent: float, is_active: bool) -> tuple[bool, str]:
    """
    Admin helper: create/update an affiliate code for a given Supabase Auth user UUID.
    Uses service-role (must be present in Streamlit secrets).
    """
    try:
        service_key = str(get_secret("SUPABASE_SERVICE_ROLE_KEY", "") or "").strip()
        if not service_key:
            return False, "Missing SUPABASE_SERVICE_ROLE_KEY in Streamlit secrets."
        affiliate_user_id = safe_str(affiliate_user_id).strip()
        code = safe_str(code).strip().upper()
        if not affiliate_user_id or not re.match(r"^[0-9a-fA-F-]{36}$", affiliate_user_id):
            return False, "Affiliate user UUID must be a valid UUID."
        if not code or len(code) < 4:
            return False, "Code must be at least 4 characters."
        pct = float(commission_percent)
        if pct <= 0 or pct > 80:
            return False, "Commission percent must be between 0 and 80."

        sb_admin = create_client(SUPABASE_URL, service_key)
        sb_admin.table("affiliate_codes").upsert(
            {
                "code": code,
                "affiliate_user_id": affiliate_user_id,
                "commission_percent": pct,
                "is_active": bool(is_active),
            },
            on_conflict="code",
        ).execute()
        return True, f"Saved affiliate code `{code}`."
    except Exception as e:
        return False, safe_str(e)


def admin_get_billing_config() -> tuple[bool, dict]:
    """
    Admin helper: read billing_config singleton row (id=1).
    Uses service-role (must be present in Streamlit secrets).
    Returns (ok, data_or_error).
    """
    try:
        service_key = str(get_secret("SUPABASE_SERVICE_ROLE_KEY", "") or "").strip()
        if not service_key:
            return False, {"error": "Missing SUPABASE_SERVICE_ROLE_KEY in Streamlit secrets."}
        sb_admin = create_client(SUPABASE_URL, service_key)
        res = sb_admin.table("billing_config").select("*").eq("id", 1).maybe_single().execute()
        return True, res.data or {}
    except Exception as e:
        return False, {"error": safe_str(e)}


def admin_start_affiliate_promo_window(days: int = 30, promo_pct: float = 30.0, default_pct: float = 20.0) -> tuple[bool, str]:
    """
    Admin helper: starts (or restarts) a global affiliate promo window.
    During this window, webhook commissions are bumped up to promo_pct (if higher than code/default).
    Uses service-role; requires `sql/billing_config.sql` to have been run once.
    """
    try:
        service_key = str(get_secret("SUPABASE_SERVICE_ROLE_KEY", "") or "").strip()
        if not service_key:
            return False, "Missing SUPABASE_SERVICE_ROLE_KEY in Streamlit secrets."
        sb_admin = create_client(SUPABASE_URL, service_key)
        start = datetime.utcnow()
        end = start + timedelta(days=int(days))
        sb_admin.table("billing_config").upsert(
            {
                "id": 1,
                "affiliate_promo_start_at": start.isoformat() + "Z",
                "affiliate_promo_end_at": end.isoformat() + "Z",
                "promo_commission_percent": float(promo_pct),
                "default_commission_percent": float(default_pct),
                "updated_at": datetime.utcnow().isoformat() + "Z",
            },
            on_conflict="id",
        ).execute()
        return True, f"Promo window started: {start.strftime('%Y-%m-%d %H:%M UTC')} → {end.strftime('%Y-%m-%d %H:%M UTC')}."
    except Exception as e:
        return False, safe_str(e)


def admin_grandfather_existing_users(cutoff_utc: Optional[datetime] = None) -> tuple[bool, str]:
    """
    Admin helper: mark all users created at/before cutoff_utc as grandfathered (unlimited trades).
    This is intended to be clicked once at launch time (or whenever you decide).
    Uses Supabase Auth Admin API (service role key required).
    """
    try:
        service_key = str(get_secret("SUPABASE_SERVICE_ROLE_KEY", "") or "").strip()
        if not service_key:
            return False, "Missing SUPABASE_SERVICE_ROLE_KEY in Streamlit secrets."

        sb_admin = create_client(SUPABASE_URL, service_key)

        cutoff = cutoff_utc or datetime.utcnow()
        cutoff_iso = cutoff.isoformat() + "Z"

        # List users via Auth Admin API (auth schema is not exposed via PostgREST).
        user_ids: List[str] = []
        page = 1
        per_page = 200
        while True:
            resp = sb_admin.auth.admin.list_users(page=page, per_page=per_page)  # type: ignore[attr-defined]
            users = getattr(resp, "users", None) or (resp.get("users") if isinstance(resp, dict) else None)  # type: ignore[union-attr]
            if not users:
                break
            for u in users:
                uid = safe_str(getattr(u, "id", "") if not isinstance(u, dict) else u.get("id", "")).strip()
                created_at = safe_str(getattr(u, "created_at", "") if not isinstance(u, dict) else u.get("created_at", "")).strip()
                if not uid:
                    continue
                # created_at is ISO; lexicographic compare is safe for same format.
                if created_at and created_at > cutoff_iso:
                    continue
                user_ids.append(uid)
            if len(users) < per_page:
                break
            page += 1

        if not user_ids:
            return True, f"No users found at/before {cutoff_iso}."

        rows = [{"user_id": uid, "plan": "grandfathered", "trade_limit": None} for uid in user_ids]
        # Chunk to avoid request size limits.
        updated = 0
        chunk_size = 200
        for i in range(0, len(rows), chunk_size):
            chunk = rows[i : i + chunk_size]
            sb_admin.table("entitlements").upsert(chunk, on_conflict="user_id").execute()
            updated += len(chunk)

        return True, f"Grandfathered {updated} users (cutoff {cutoff_iso})."
    except Exception as e:
        return False, safe_str(e)


def insert_support_request(user_id: str, email: str, subject: str, message: str, page: str) -> bool:
    try:
        sb = authed_supabase()
        sb.table("support_requests").insert(
            {
                "user_id": user_id,
                "email": safe_str(email).strip(),
                "subject": safe_str(subject).strip(),
                "message": safe_str(message).strip(),
                "page": safe_str(page).strip(),
            }
        ).execute()
        return True
    except Exception:
        return False


def insert_suggestion(user_id: str, email: str, title: str, suggestion: str) -> bool:
    try:
        sb = authed_supabase()
        sb.table("feature_suggestions").insert(
            {
                "user_id": user_id,
                "email": safe_str(email).strip(),
                "title": safe_str(title).strip(),
                "suggestion": safe_str(suggestion).strip(),
            }
        ).execute()
        return True
    except Exception:
        return False


# ── Public Pages (landing + legal) ───────────────────────────────────────────

DATA_DIR = Path("data")
WAITLIST_CSV = DATA_DIR / "waitlist.csv"
CONTACT_CSV = DATA_DIR / "contact_messages.csv"


def ensure_data_dir() -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return


def is_valid_email(email: str) -> bool:
    email = safe_str(email).strip()
    if not email:
        return False
    # Basic sanity check; avoid being overly strict.
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def append_csv_row(path: Path, header: list, row: dict) -> bool:
    try:
        ensure_data_dir()
        exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            if not exists:
                w.writeheader()
            w.writerow(row)
        return True
    except Exception:
        return False


def insert_waitlist_email(email: str, source: str = "landing") -> bool:
    email = safe_str(email).strip().lower()
    if not is_valid_email(email):
        return False

    # Prefer Supabase if the table exists; otherwise fall back to CSV.
    try:
        sb = authed_supabase()
        sb.table("waitlist_emails").insert({"email": email, "source": source}).execute()
        return True
    except Exception:
        ts = datetime.utcnow().isoformat()
        return append_csv_row(
            WAITLIST_CSV,
            header=["created_at", "email", "source"],
            row={"created_at": ts, "email": email, "source": source},
        )


def insert_public_contact(email: str, subject: str, message: str, page: str = "contact") -> bool:
    email = safe_str(email).strip().lower()
    if email and not is_valid_email(email):
        return False

    payload = {
        "email": email,
        "subject": safe_str(subject).strip(),
        "message": safe_str(message).strip(),
        "page": safe_str(page).strip(),
    }

    try:
        sb = authed_supabase()
        sb.table("public_contact_messages").insert(payload).execute()
        return True
    except Exception:
        ts = datetime.utcnow().isoformat()
        return append_csv_row(
            CONTACT_CSV,
            header=["created_at", "email", "subject", "message", "page"],
            row={"created_at": ts, **payload},
        )


def render_public_footer() -> None:
    st.markdown("---")
    st.markdown(
        f"""
        <div style="display:flex;gap:18px;flex-wrap:wrap;font-size:13px;color:rgba(148,163,184,0.95);">
          <a href="?page=terms" style="color:inherit;text-decoration:none;">Terms of Service</a>
          <a href="?page=privacy" style="color:inherit;text-decoration:none;">Privacy Policy</a>
          <a href="?page=refunds" style="color:inherit;text-decoration:none;">Refund Policy</a>
          <a href="?page=contact" style="color:inherit;text-decoration:none;">Contact</a>
          <span style="opacity:0.75;">·</span>
          <span style="opacity:0.95;">Tradylo Journal is analytics software. It does not provide trading signals or investment advice.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

def build_demo_trades(seed: int = 42) -> pd.DataFrame:
    """
    Generate a deterministic demo dataset for the public preview (no login required).
    Never touches Supabase.
    """
    import random

    random.seed(seed)
    today = datetime.utcnow().date()
    days = 75
    n_trades = 140

    instruments = ["MNQ", "NQ", "MES", "ES", "GC", "MGC"]
    sessions = ["NY", "London", "Asia"]
    directions = ["Long", "Short"]

    def pick_time(session: str) -> str:
        if session == "Asia":
            h = random.choice([1, 2, 3, 4, 5, 6, 7])
        elif session == "London":
            h = random.choice([7, 8, 9, 10, 11])
        else:
            h = random.choice([13, 14, 15, 16, 17])
        m = random.choice([0, 15, 30, 45])
        return f"{h:02d}:{m:02d}"

    def pick_confluences() -> str:
        k = random.choice([1, 2, 2, 3])
        picks = random.sample(CONFLUENCES, k=min(k, len(CONFLUENCES)))
        # Include some "Other" style tags in demo
        if random.random() < 0.25:
            picks.append(random.choice(["News catalyst", "Macro level", "Higher timeframe bias"]))
        return ", ".join(picks)

    rows = []
    for i in range(n_trades):
        d = today - timedelta(days=random.randint(0, days))
        session = random.choice(sessions)
        direction = random.choice(directions)
        instrument = random.choice(instruments)
        contracts = random.choice([1, 1, 2, 2, 3, 5])

        # Stronger positive expectancy for a clean-looking demo curve.
        pnl_gross = random.gauss(85, 95)
        # Occasional pullbacks, but avoid huge cliffs in the demo preview.
        if random.random() < 0.06:
            pnl_gross -= random.uniform(120, 320)
        if random.random() < 0.10:
            pnl_gross += random.uniform(120, 420)

        commission = round(random.uniform(2.0, 8.0), 2)
        slippage = round(random.uniform(0.0, 3.0), 2)
        pnl_net = float(pnl_gross) - commission - slippage
        r_multiple = random.gauss(0.25, 1.1)

        # Grade based loosely on pnl/r
        grade = "B"
        if pnl_net > 220 or r_multiple > 2.0:
            grade = random.choice(["A+", "A", "A++"])
        elif pnl_net > 80 or r_multiple > 1.2:
            grade = "A"
        elif pnl_net < -220 or r_multiple < -1.6:
            grade = random.choice(["C", "D"])
        elif pnl_net < -80 or r_multiple < -0.7:
            grade = "C"
        else:
            grade = random.choice(["B+", "B"])

        rows.append(
            {
                "id": f"demo-{i+1}",
                "date": pd.to_datetime(d),
                "entry_time": pick_time(session),
                "instrument": instrument,
                "direction": direction,
                "contracts": contracts,
                "session": session,
                "trade_grade": grade,
                "confluences": pick_confluences(),
                "notes": random.choice(
                    [
                        "Clean execution, followed plan.",
                        "Could have sized smaller here.",
                        "Nice patience — waited for confirmation.",
                        "Missed partials; review exit rules.",
                        "",
                    ]
                ),
                "pnl_gross": round(float(pnl_gross), 2),
                "pnl_net": round(float(pnl_net), 2),
                "r_multiple": round(float(r_multiple), 2),
            }
        )
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["pnl_gross"] = pd.to_numeric(df["pnl_gross"], errors="coerce").fillna(0.0)
    df["pnl_net"] = pd.to_numeric(df["pnl_net"], errors="coerce").fillna(0.0)
    df["r_multiple"] = pd.to_numeric(df["r_multiple"], errors="coerce")
    return df.sort_values(["date", "entry_time"], ascending=True)


def render_demo_dashboard() -> None:
    render_brand_header(center=False, hero=False)
    st.title("Demo dashboard")
    st.caption("This is a public preview using sample data (no login required).")

    df = build_demo_trades()
    pnl_col = "pnl_net"

    daily_df = (
        df.groupby(df["date"].dt.date, as_index=False)[pnl_col]
        .agg(pnl="sum", trades="count")
        .rename(columns={"date": "date"})
    )
    daily_df["date"] = pd.to_datetime(daily_df["date"])

    wins_df = df[df[pnl_col] > 0]
    losses_df = df[df[pnl_col] < 0]
    total_trades = len(df)
    win_rate = float((df[pnl_col] > 0).mean() * 100.0) if total_trades else 0.0
    total_pnl = float(df[pnl_col].sum()) if total_trades else 0.0
    avg_rr = float(df["r_multiple"].dropna().mean()) if "r_multiple" in df.columns else 0.0
    profit_factor = (float(wins_df[pnl_col].sum()) / abs(float(losses_df[pnl_col].sum()))) if not losses_df.empty else None

    daily_equity = daily_df.sort_values("date").copy()
    daily_equity["equity"] = daily_equity["pnl"].cumsum()
    daily_equity["equity_smooth"] = daily_equity["equity"].rolling(5, min_periods=1).mean()
    daily_equity["peak"] = daily_equity["equity"].cummax()
    daily_equity["drawdown"] = daily_equity["equity"] - daily_equity["peak"]
    max_dd = abs(float(daily_equity["drawdown"].min())) if not daily_equity.empty else 0.0

    cards = [
        ("Net PnL", format_money(total_pnl), f"{total_trades} trades"),
        ("Win %", f"{win_rate:.2f}%", None),
        ("Profit Factor", f"{profit_factor:.2f}" if profit_factor is not None else "n/a", None),
        ("Avg RR", f"{avg_rr:.2f}" if pd.notna(avg_rr) else "n/a", None),
        ("Max Drawdown", format_money(-max_dd), None),
    ]
    render_metric_cards(cards)

    st.markdown("---")
    c1, c2, c3 = st.columns([2.2, 1.2, 1.2])
    with c1:
        st.subheader("Equity curve")
        curve = (
            alt.Chart(daily_equity)
            .mark_area(
                interpolate="monotone",
                line={"color": "#A78BFA", "width": 2.6},
                color=alt.Gradient(
                    gradient="linear",
                    stops=[
                        alt.GradientStop(color="rgba(124,58,237,0.45)", offset=0),
                        alt.GradientStop(color="rgba(56,189,248,0.12)", offset=1),
                    ],
                    x1=0, x2=1, y1=0, y2=0,
                ),
            )
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("equity_smooth:Q", title=None),
                tooltip=[
                    alt.Tooltip("date:T", title="Date"),
                    alt.Tooltip("equity:Q", title="Equity", format=",.2f"),
                ],
            )
            .properties(height=280)
        )
        st.altair_chart(style_altair_chart(curve), use_container_width=True)

    with c2:
        st.subheader("Daily PnL")
        daily_df["pos"] = daily_df["pnl"] >= 0
        bars = (
            alt.Chart(daily_df)
            .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("date:T", title=None),
                y=alt.Y("pnl:Q", title=None),
                color=alt.condition("datum.pos", alt.value("#22C55E"), alt.value("#EF4444")),
                tooltip=["date:T", alt.Tooltip("pnl:Q", format=",.2f"), "trades:Q"],
            )
            .properties(height=280)
        )
        st.altair_chart(style_altair_chart(bars), use_container_width=True)

    with c3:
        st.subheader("Zylo score")
        # compute_zylo_score expects daily_df with 'pnl' field; we already named it,
        # but pnl_col must refer to the column on df_view.
        zylo = compute_zylo_score(df, daily_df, pnl_col)
        st.markdown(f"**Your Zylo Score:** `{zylo['overall']:.2f}`")
        render_zylo_radar(zylo["components"])

    st.markdown("---")
    st.subheader("Breakdowns")
    b1, b2 = st.columns(2)
    with b1:
        inst = df.groupby("instrument", as_index=False)[pnl_col].sum().sort_values(pnl_col, ascending=False)
        inst["pos"] = inst[pnl_col] >= 0
        inst_chart = (
            alt.Chart(inst)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("instrument:N", sort="-y", title=None),
                y=alt.Y(f"{pnl_col}:Q", title=None),
                color=alt.condition("datum.pos", alt.value("#60A5FA"), alt.value("#F87171")),
                tooltip=["instrument:N", alt.Tooltip(f"{pnl_col}:Q", format=",.2f")],
            )
            .properties(height=240)
        )
        st.altair_chart(style_altair_chart(inst_chart), use_container_width=True)
    with b2:
        ses = df.groupby("session", as_index=False)[pnl_col].sum().sort_values(pnl_col, ascending=False)
        ses["pos"] = ses[pnl_col] >= 0
        ses_chart = (
            alt.Chart(ses)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("session:N", sort="-y", title=None),
                y=alt.Y(f"{pnl_col}:Q", title=None),
                color=alt.condition("datum.pos", alt.value("#60A5FA"), alt.value("#F87171")),
                tooltip=["session:N", alt.Tooltip(f"{pnl_col}:Q", format=",.2f")],
            )
            .properties(height=240)
        )
        st.altair_chart(style_altair_chart(ses_chart), use_container_width=True)

    st.markdown("---")
    st.subheader("PnL calendar")
    render_pnl_calendar(df[["date", pnl_col]].copy(), pnl_col)

    st.markdown("---")
    st.subheader("Recent trades")
    recent = df.sort_values(["date", "entry_time"], ascending=False).head(10).copy()
    recent["PnL"] = recent[pnl_col].apply(format_money)
    st.dataframe(
        recent[["date", "entry_time", "instrument", "direction", "session", "trade_grade", "r_multiple", "PnL"]],
        use_container_width=True,
        hide_index=True,
    )
    render_public_footer()


def render_tour_page() -> None:
    render_brand_header(center=False, hero=False)
    st.title("Product tour")
    st.caption("A quick look at what Tradylo Journal does before you create an account.")

    st.markdown("### What you'll get")
    st.markdown(
        "- A clean dashboard with equity curve + daily PnL\n"
        "- PnL calendar with day drill-down\n"
        "- Analytics by instrument, session, time, and confluence\n"
        "- Journaling + screenshots + notes"
    )

    st.markdown("---")
    st.subheader("Preview: dashboard + calendar")
    st.info("Below is the same demo data used in the public dashboard preview.")
    df = build_demo_trades()
    pnl_col = "pnl_net"
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("**Equity curve (preview)**")
        chart_df = df.sort_values("date").copy()
        chart_df["equity"] = chart_df[pnl_col].cumsum()
        curve = (
            alt.Chart(chart_df)
            .mark_area(line={"color": "#A78BFA", "width": 2}, color="rgba(124,58,237,0.25)")
            .encode(x="date:T", y="equity:Q")
            .properties(height=220)
        )
        st.altair_chart(style_altair_chart(curve), use_container_width=True)
    with c2:
        st.markdown("**PnL calendar (preview)**")
        render_pnl_calendar(df[["date", pnl_col]].copy(), pnl_col)

    st.markdown("---")
    st.subheader("Preview: analytics")
    b1, b2, b3 = st.columns(3)
    with b1:
        st.markdown("**By instrument**")
        inst = df.groupby("instrument", as_index=False)[pnl_col].sum().sort_values(pnl_col, ascending=False).head(6)
        inst_chart = alt.Chart(inst).mark_bar().encode(x="instrument:N", y=f"{pnl_col}:Q").properties(height=180)
        st.altair_chart(style_altair_chart(inst_chart), use_container_width=True)
    with b2:
        st.markdown("**By session**")
        ses = df.groupby("session", as_index=False)[pnl_col].sum().sort_values(pnl_col, ascending=False)
        ses_chart = alt.Chart(ses).mark_bar().encode(x="session:N", y=f"{pnl_col}:Q").properties(height=180)
        st.altair_chart(style_altair_chart(ses_chart), use_container_width=True)
    with b3:
        st.markdown("**Zylo score**")
        daily_df = df.groupby(df["date"].dt.date, as_index=False)[pnl_col].sum().rename(columns={pnl_col: "pnl"})
        zylo = compute_zylo_score(df, daily_df, pnl_col)
        st.markdown(f"**Score:** `{zylo['overall']:.2f}`")
        render_zylo_radar(zylo["components"])

    st.markdown("---")
    st.subheader("Ready?")
    ref = safe_str(st.session_state.get("ref_code")).strip()
    auth_url = "?view=auth" + (f"&ref={quote_plus(ref)}" if ref else "")
    try:
        st.link_button("Create account / Log in", auth_url, use_container_width=True)
    except Exception:
        st.markdown(f"[Create account / Log in]({auth_url})")
    render_public_footer()


def render_public_sidebar(active: str) -> str:
    """
    Returns the selected public page label.
    """
    ref = safe_str(st.session_state.get("ref_code")).strip()
    auth_url = "?view=auth" + (f"&ref={quote_plus(ref)}" if ref else "")

    with st.sidebar:
        # A compact brand header in the sidebar for the public shell.
        render_brand_header(center=True)
        st.markdown("---")
        options = ["Home", "Demo", "Terms", "Privacy", "Refunds", "Contact"]
        if active not in options:
            active = "Home"
        idx = options.index(active)
        choice = st.radio("Menu", options, index=idx, label_visibility="collapsed", key="public_nav")
        st.markdown("---")
        try:
            st.link_button("Log in / Sign up", auth_url, use_container_width=True)
        except Exception:
            st.markdown(f"[Log in / Sign up]({auth_url})")
        st.caption("-> Access is free for life for now - won't last long.")
        st.caption("Payments not enabled yet.")
    return st.session_state.get("public_nav", active)


def render_landing_page() -> None:
    # Sidebar handles the brand in the public shell; keep the main landing clean.
    ref = safe_str(st.session_state.get("ref_code")).strip()
    auth_url = "?view=auth" + (f"&ref={quote_plus(ref)}" if ref else "")

    top = st.container()
    with top:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            st.title("Tradylo Journal")
            st.write("A trading journal and performance analytics app for traders.")
        with c2:
            st.markdown(" ")
            st.markdown(" ")
            try:
                st.link_button("Log in / Sign up", auth_url, use_container_width=True)
            except Exception:
                st.markdown(f"[Log in / Sign up]({auth_url})")
            st.caption("-> Access is free for life for now - won't last long.")
        with c3:
            st.markdown(" ")
            st.markdown(" ")
            try:
                st.link_button("View demo", "?page=demo", use_container_width=True)
            except Exception:
                st.markdown("[View demo](?page=demo)")

    st.markdown("**Features**")
    st.markdown(
        "- Trade logging\n"
        "- Confluence tagging\n"
        "- Session stats\n"
        "- Screenshots\n"
        "- Notes + journaling\n"
        "- Performance metrics & analytics"
    )

    st.info("Payments not enabled yet.")
    st.caption("Tip: best experienced on a laptop or iPad. Mobile support is improving.")

    st.markdown("---")
    st.subheader("Join the waitlist")
    with st.form("waitlist_form", clear_on_submit=True):
        email = st.text_input("Email", placeholder="you@email.com")
        submitted = st.form_submit_button("Join waitlist")
    if submitted:
        ok = insert_waitlist_email(email, source="public_landing")
        if ok:
            st.success("You're on the waitlist. We'll email you when it's ready.")
        else:
            st.error("Please enter a valid email address.")

    st.markdown("---")
    st.caption("Already have an account? Use the button at the top to log in or sign up.")

    render_public_footer()


def render_terms_page() -> None:
    render_brand_header(center=True)
    st.title("Terms of Service")
    st.write("Last updated: (placeholder)")
    st.markdown(
        """
**Software-only**
Tradylo Journal is provided as analytics software for tracking and reviewing your trading activity.

**No financial advice**
We do not provide trading signals, investment advice, brokerage services, or recommendations. You are responsible for all trading decisions and outcomes.

**User responsibility**
You agree that any data you enter or upload is accurate to the best of your ability. You are responsible for securing your account credentials.

**Acceptable use**
Do not abuse the service, attempt to access other users’ data, reverse engineer, or disrupt the platform.
        """
    )
    render_public_footer()


def render_privacy_page() -> None:
    render_brand_header(center=True)
    st.title("Privacy Policy")
    st.write("Last updated: (placeholder)")
    st.markdown(
        f"""
**What we collect**
- Account email address (for authentication)
- Trading journal data you enter (trades, tags, notes, screenshots)
- Basic usage/diagnostic data required to operate the app

**How we use it**
To provide the journal, analytics, and support.

**Cookies**
Streamlit and Supabase may use cookies/local storage for authentication sessions. We do not use advertising cookies.

**Contact**
For privacy questions, contact: {PUBLIC_CONTACT_EMAIL}
        """
    )
    render_public_footer()


def render_refund_page() -> None:
    render_brand_header(center=True)
    st.title("Refund Policy")
    st.write("Last updated: (placeholder)")
    st.markdown(
        f"""
**Payments not enabled yet**
This policy will apply once subscriptions are enabled.

**Refund window**
Once payments are enabled: refunds will be available within **{REFUND_WINDOW_DAYS} day(s)** of purchase, subject to verification and abuse prevention.
        """
    )
    render_public_footer()


def render_contact_page() -> None:
    render_brand_header(center=True)
    st.title("Contact")
    st.write(f"For support, email: {PUBLIC_CONTACT_EMAIL}")

    st.subheader("Send a message")
    with st.form("public_contact_form", clear_on_submit=True):
        email = st.text_input("Your email (optional)", placeholder="you@email.com")
        subject = st.text_input("Subject", placeholder="What do you need help with?")
        message = st.text_area("Message", height=160, placeholder="Describe your issue or question.")
        sent = st.form_submit_button("Send")
    if sent:
        if email and not is_valid_email(email):
            st.error("Please enter a valid email, or leave it blank.")
        elif not message.strip():
            st.error("Please enter a message.")
        else:
            ok = insert_public_contact(email, subject, message, page="public_contact")
            if ok:
                st.success("Message sent. We'll get back to you soon.")
            else:
                st.error("Could not send message right now. Please try again later.")

    render_public_footer()


def render_public_router() -> None:
    page = get_query_param("page").strip().lower()
    view = get_query_param("view").strip().lower()
    ref = get_query_param("ref").strip()
    if ref:
        st.session_state["ref_code"] = ref

    # Public sidebar menu (Tradezella-like pre-login shell)
    active = "Home"
    if view == "auth":
        active = "Home"
    elif page == "demo":
        active = "Demo"
    elif page == "terms":
        active = "Terms"
    elif page == "privacy":
        active = "Privacy"
    elif page in ("refunds", "refund", "refund-policy"):
        active = "Refunds"
    elif page == "contact":
        active = "Contact"

    choice = render_public_sidebar(active)

    # IMPORTANT: If the URL is stuck on `?view=auth` (user clicked login once),
    # we still want the public menu to work. Only show auth when Home is selected.
    if view == "auth" and choice == "Home":
        show_auth()
        return

    if choice == "Demo":
        render_demo_dashboard()
        return
    # (Tour removed; Demo is the product preview.)
    if choice == "Terms":
        render_terms_page()
        return
    if choice == "Privacy":
        render_privacy_page()
        return
    if choice == "Refunds":
        render_refund_page()
        return
    if choice == "Contact":
        render_contact_page()
        return

    render_landing_page()


def _stripe_price_id_for_plan(plan: str) -> Optional[str]:
    """
    Supports multi-plan pricing.
    Back-compat: STRIPE_PRICE_ID is treated as monthly if plan-specific ids aren't provided.
    """
    plan = safe_str(plan).strip().lower()
    # Preferred per-plan keys
    if plan in ("monthly", "month"):
        return get_secret("STRIPE_PRICE_ID_MONTHLY") or get_secret("STRIPE_PRICE_ID")
    if plan in ("quarterly", "3-month", "3month", "three-month", "three_month"):
        return get_secret("STRIPE_PRICE_ID_QUARTERLY")
    if plan in ("yearly", "annual", "year"):
        return get_secret("STRIPE_PRICE_ID_YEARLY")
    return None


def create_stripe_checkout_session(
    user_id: str,
    user_email: str,
    plan: str = "monthly",
    *,
    force_when_disabled: bool = False,
) -> Optional[str]:
    """
    Returns a Stripe Checkout URL, or None if Stripe isn't configured.
    This is only used when STRIPE_ENABLED=true and Stripe secrets exist.
    """
    if not STRIPE_ENABLED and not force_when_disabled:
        return None

    stripe_secret = get_secret("STRIPE_SECRET_KEY")
    price_id = _stripe_price_id_for_plan(plan)
    success_url = get_secret("STRIPE_SUCCESS_URL")
    cancel_url = get_secret("STRIPE_CANCEL_URL")
    if not (stripe_secret and price_id and success_url and cancel_url):
        return None

    try:
        import stripe  # type: ignore
    except Exception:
        return None

    try:
        stripe.api_key = stripe_secret
        subscription_data: Dict[str, Any] = {}
        # Optional free trial that still requires card details up front.
        # Stripe will automatically charge at the end of the trial.
        if TRIAL_DAYS and TRIAL_DAYS > 0:
            subscription_data["trial_period_days"] = int(TRIAL_DAYS)
            # If payment method is missing at trial end, cancel (avoids past_due surprises).
            subscription_data["trial_settings"] = {"end_behavior": {"missing_payment_method": "cancel"}}

        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=user_email or None,
            client_reference_id=user_id,
            metadata={"user_id": user_id},
            allow_promotion_codes=True,
            # Collect card details even when trialing.
            payment_method_collection="always" if (TRIAL_DAYS and TRIAL_DAYS > 0) else "if_required",
            subscription_data=subscription_data or None,
        )
        return getattr(session, "url", None)
    except Exception:
        return None


def get_query_param(name: str) -> str:
    try:
        # Streamlit >= 1.30
        v = st.query_params.get(name)
        if isinstance(v, list):
            return safe_str(v[0])
        return safe_str(v)
    except Exception:
        try:
            v = st.experimental_get_query_params().get(name, [""])
            return safe_str(v[0] if isinstance(v, list) and v else v)
        except Exception:
            return ""


def resolve_affiliate(code: str) -> Optional[str]:
    if not code:
        return None
    try:
        sb = authed_supabase()
        res = (
            sb.table("affiliate_codes")
            .select("affiliate_user_id,is_active")
            .eq("code", code)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        row = res.data[0]
        if not row.get("is_active", True):
            return None
        return safe_str(row.get("affiliate_user_id")) or None
    except Exception:
        return None


def maybe_record_referral(user_id: str) -> None:
    """
    If the user landed with ?ref=CODE, store a one-time referral row.
    Safe to call on every run; no-ops if already recorded or tables aren't present.
    """
    if not AFFILIATES_ENABLED:
        return
    code = get_query_param("ref").strip() or safe_str(st.session_state.get("ref_code")).strip()
    if not code:
        return

    # Remember for the session so navigation doesn't lose it.
    st.session_state["ref_code"] = code

    try:
        sb = authed_supabase()
        existing = (
            sb.table("referrals")
            .select("referred_user_id")
            .eq("referred_user_id", user_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return

        affiliate_user_id = resolve_affiliate(code)
        if not affiliate_user_id:
            return
        if affiliate_user_id == user_id:
            return

        sb.table("referrals").insert(
            {"referred_user_id": user_id, "affiliate_user_id": affiliate_user_id, "code": code}
        ).execute()
    except Exception:
        # Fail open; referrals should never block the app.
        return


# ── Strategies (feature-tolerant) ─────────────────────────────────────────────

def load_strategies(user_id: str) -> list:
    try:
        sb = authed_supabase()
        res = sb.table("strategies").select("name,description").eq("user_id", user_id).order("name").execute()
        return res.data or []
    except Exception:
        return []


def upsert_strategy(user_id: str, name: str, description: str) -> bool:
    name = safe_str(name).strip()
    if not name:
        return False
    try:
        sb = authed_supabase()
        existing = sb.table("strategies").select("id").eq("user_id", user_id).eq("name", name).limit(1).execute()
        if existing.data:
            sb.table("strategies").update({"description": description}).eq("user_id", user_id).eq("name", name).execute()
        else:
            sb.table("strategies").insert({"user_id": user_id, "name": name, "description": description}).execute()
        return True
    except Exception:
        return False


def render_strategy_creation_page(user_id: str) -> None:
    st.subheader("Strategy/model creation")
    st.caption("Create reusable strategy templates you can pick from when logging trades.")

    with st.form("strategy_create_form", clear_on_submit=False):
        name = st.text_input("Strategy name", placeholder="e.g. London Sweep + Reversal")
        description = st.text_area("What is the strategy?", height=160, placeholder="Rules, checklist, entries/exits, invalidation…")
        submitted = st.form_submit_button("Save strategy")
    if submitted:
        ok = upsert_strategy(user_id, name, description)
        if ok:
            st.success("Saved.")
        else:
            st.error("Could not save strategy yet. If this is your first time using it, the `strategies` table may not be set up in Supabase.")

    st.markdown("---")
    st.markdown("**Your strategies**")
    rows = load_strategies(user_id)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No strategies saved yet.")


# ── Affiliates (feature-tolerant) ─────────────────────────────────────────────

PUBLIC_APP_URL = str(get_secret("PUBLIC_APP_URL", "https://TradyloTradingJournal.streamlit.app") or "").strip()


def generate_affiliate_code() -> str:
    # Short, human shareable. Collisions are unlikely; we retry on insert.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = uuid.uuid4().hex.upper()
    # Use parts of uuid mapped into alphabet for a consistent length.
    code = "".join(alphabet[int(raw[i], 16) % len(alphabet)] for i in range(10))
    return f"TRADYLO-{code}"


def load_my_affiliate_codes(user_id: str) -> list:
    try:
        sb = authed_supabase()
        res = sb.table("affiliate_codes").select("code,commission_percent,is_active,created_at").eq("affiliate_user_id", user_id).order("created_at", desc=True).execute()
        return res.data or []
    except Exception:
        return []


def create_affiliate_code(user_id: str, commission_percent: float = 20.0) -> Optional[str]:
    try:
        sb = authed_supabase()
        for _ in range(5):
            code = generate_affiliate_code()
            try:
                sb.table("affiliate_codes").insert(
                    {"code": code, "affiliate_user_id": user_id, "commission_percent": commission_percent, "is_active": True}
                ).execute()
                return code
            except Exception:
                continue
        return None
    except Exception:
        return None


def load_referrals_for_affiliate(user_id: str) -> pd.DataFrame:
    try:
        sb = authed_supabase()
        res = sb.table("referrals").select("referred_user_id,code,created_at").eq("affiliate_user_id", user_id).order("created_at", desc=True).execute()
        return pd.DataFrame(res.data or [])
    except Exception:
        return pd.DataFrame()


def render_affiliates_page(user_id: str) -> None:
    st.subheader("Affiliates")
    st.caption("Affiliate tracking is only active when enabled, and commissions are applied only once payments are enabled.")

    if not AFFILIATES_ENABLED:
        st.warning("Affiliates are currently disabled. Turn on `AFFILIATES_ENABLED = true` in Streamlit secrets to record referrals.")
    # Admin-only setup (so normal users don't see scary SQL).
    user_obj = st.session_state.get("user")
    email = safe_str(user_obj.get("email")) if isinstance(user_obj, dict) else safe_str(getattr(user_obj, "email", ""))
    admin_emails = []
    for v in [SUPPORT_CONTACT_EMAIL, get_secret("ADMIN_EMAILS", "")]:
        s = safe_str(v).strip()
        if not s:
            continue
        admin_emails.extend([x.strip().lower() for x in s.split(",") if x.strip()])
    is_admin = safe_str(email).strip().lower() in set(admin_emails)

    if is_admin:
        with st.expander("Admin setup (paste in Supabase SQL Editor)", expanded=False):
            st.caption("Step 1: Create/update the affiliate tables + policies (run once).")
            st.code(
                "\n".join(
                    [
                        "-- Affiliate / referral tracking (Stripe commission is handled via webhook later)",
                        "create table if not exists public.affiliate_codes (",
                        "  code text primary key,",
                        "  affiliate_user_id uuid not null references auth.users(id) on delete cascade,",
                        "  commission_percent numeric not null default 20,",
                        "  is_active boolean not null default true,",
                        "  created_at timestamptz not null default now()",
                        ");",
                        "",
                        "create table if not exists public.referrals (",
                        "  referred_user_id uuid primary key references auth.users(id) on delete cascade,",
                        "  affiliate_user_id uuid not null references auth.users(id) on delete cascade,",
                        "  code text not null references public.affiliate_codes(code) on delete restrict,",
                        "  created_at timestamptz not null default now()",
                        ");",
                        "",
                        "alter table public.affiliate_codes enable row level security;",
                        "alter table public.referrals enable row level security;",
                        "",
                        "-- SELECT: allow users to read active codes, and also read codes assigned to them.",
                        "drop policy if exists \"affiliate_codes_select_authed\" on public.affiliate_codes;",
                        "create policy \"affiliate_codes_select_authed\"",
                        "  on public.affiliate_codes",
                        "  for select",
                        "  to authenticated",
                        "  using (is_active = true or auth.uid() = affiliate_user_id);",
                        "",
                        "-- OWNER-ONLY: remove user self-management; only admin/service-role should insert/update/delete.",
                        "drop policy if exists \"affiliate_codes_manage_own\" on public.affiliate_codes;",
                        "",
                        "drop policy if exists \"referrals_select_own\" on public.referrals;",
                        "create policy \"referrals_select_own\"",
                        "  on public.referrals",
                        "  for select",
                        "  to authenticated",
                        "  using (auth.uid() = referred_user_id);",
                        "",
                        "drop policy if exists \"referrals_select_affiliate\" on public.referrals;",
                        "create policy \"referrals_select_affiliate\"",
                        "  on public.referrals",
                        "  for select",
                        "  to authenticated",
                        "  using (auth.uid() = affiliate_user_id);",
                        "",
                        "drop policy if exists \"referrals_insert_self\" on public.referrals;",
                        "create policy \"referrals_insert_self\"",
                        "  on public.referrals",
                        "  for insert",
                        "  to authenticated",
                        "  with check (",
                        "    auth.uid() = referred_user_id",
                        "    and affiliate_user_id <> referred_user_id",
                        "  );",
                        "",
                        "select pg_notify('pgrst','reload schema');",
                    ]
                ),
                language="sql",
            )

            st.caption("Step 1b (optional now, required later): Affiliate promo window config (run once).")
            st.code(
                "\n".join(
                    [
                        "create table if not exists public.billing_config (",
                        "  id integer primary key,",
                        "  affiliate_promo_start_at timestamptz,",
                        "  affiliate_promo_end_at timestamptz,",
                        "  promo_commission_percent numeric not null default 30,",
                        "  default_commission_percent numeric not null default 20,",
                        "  created_at timestamptz not null default now(),",
                        "  updated_at timestamptz not null default now()",
                        ");",
                        "",
                        "insert into public.billing_config (id) values (1) on conflict (id) do nothing;",
                        "",
                        "alter table public.billing_config enable row level security;",
                        "drop policy if exists \"billing_config_select_authed\" on public.billing_config;",
                        "create policy \"billing_config_select_authed\"",
                        "  on public.billing_config",
                        "  for select",
                        "  to authenticated",
                        "  using (true);",
                        "",
                        "select pg_notify('pgrst','reload schema');",
                    ]
                ),
                language="sql",
            )

            st.caption("Step 2: Assign ONE affiliate code (admin insert). Replace the UUID with the affiliate's Supabase Auth user id.")
            st.code(
                "\n".join(
                    [
                        "insert into public.affiliate_codes (code, affiliate_user_id, commission_percent, is_active)",
                        "values ('HARVEY20', 'AFFILIATE_USER_UUID_HERE', 20, true)",
                        "on conflict (code) do update set",
                        "  affiliate_user_id = excluded.affiliate_user_id,",
                        "  commission_percent = excluded.commission_percent,",
                        "  is_active = excluded.is_active;",
                    ]
                ),
                language="sql",
            )

        with st.expander("Admin: assign / update affiliate code (no SQL)", expanded=False):
            st.caption("Use this to create/update a code for any user UUID. (Owner-only)")
            with st.form("admin_affiliate_code_form", clear_on_submit=False):
                auid = st.text_input("Affiliate user UUID", placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
                code = st.text_input("Code", placeholder="DODGY1010").upper()
                pct = st.number_input("Commission %", min_value=1.0, max_value=80.0, value=20.0, step=1.0)
                active = st.checkbox("Active", value=True)
                saved = st.form_submit_button("Save code")
            if saved:
                ok, msg = admin_upsert_affiliate_code(auid, code, pct, active)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    codes = load_my_affiliate_codes(user_id)
    if not codes:
        if not is_admin:
            st.info("No affiliate code is assigned to your account yet. Contact support to be added as an affiliate.")
            return
        st.info("No affiliate code is assigned to your account yet. Use the admin tools above to assign one.")
        return

    active = next((c for c in codes if c.get("is_active", True)), codes[0])
    code = safe_str(active.get("code"))
    link = f"{PUBLIC_APP_URL}/?ref={quote_plus(code)}"

    st.markdown("**Your affiliate link**")
    st.code(link)

    st.markdown("---")
    st.markdown("**Your referrals**")
    df_ref = load_referrals_for_affiliate(user_id)
    if df_ref.empty:
        st.info("No referrals yet.")
    else:
        st.dataframe(df_ref, use_container_width=True, hide_index=True)


def get_entitlement(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Returns entitlement row for the user, or None if the table isn't set up yet.
    We deliberately fail open (no paywall) until the DB table + RLS policies exist.
    """
    try:
        sb = authed_supabase()
        res = sb.table("entitlements").select("*").eq("user_id", user_id).limit(1).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception:
        return None


def ensure_entitlement(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Creates a default free entitlement if missing.
    If the entitlements table isn't ready, returns None (paywall disabled).
    """
    existing = get_entitlement(user_id)
    if existing is not None:
        return existing

    try:
        sb = authed_supabase()
        row = {
            "user_id": user_id,
            "plan": "free",
            "trade_limit": FREE_TRADE_LIMIT,
        }
        # Insert only; avoid requiring UPDATE permissions under RLS.
        sb.table("entitlements").insert(row).execute()
        return get_entitlement(user_id)
    except Exception:
        return None


def is_unlimited(entitlement: Optional[Dict[str, Any]]) -> bool:
    if not entitlement:
        # If we can't read entitlements, fail open so we don't break the app.
        return True
    plan = safe_str(entitlement.get("plan")).lower()
    if plan in ("pro", "grandfathered", "lifetime"):
        return True
    limit = entitlement.get("trade_limit")
    return limit is None


def count_total_trades(user_id: str) -> Optional[int]:
    """
    Count trades across ALL account types. Returns None if count isn't available.
    """
    try:
        sb = authed_supabase()
        # Supabase returns `count` when count="exact" is provided.
        res = sb.table("trades").select("id", count="exact").eq("user_id", user_id).execute()
        if hasattr(res, "count") and res.count is not None:
            return int(res.count)
        # Fallback: count returned rows (may be capped by API limits, but better than crashing).
        return len(res.data or [])
    except Exception:
        return None


def enforce_trade_limit_or_warn(user_id: str) -> bool:
    """
    Returns True if saving a trade is allowed; otherwise shows UI and returns False.
    """
    if not PAYWALL_ENABLED:
        return True

    ent = ensure_entitlement(user_id)
    if is_unlimited(ent):
        return True

    limit = ent.get("trade_limit") if ent else FREE_TRADE_LIMIT
    try:
        limit = int(limit)
    except Exception:
        limit = FREE_TRADE_LIMIT

    current = count_total_trades(user_id)
    if current is None:
        # Fail open if count can't be determined (keeps app usable).
        return True

    if current >= limit:
        st.error(f"Free plan limit reached ({limit} trades). Upgrade to continue adding trades.")
        # Optional Stripe integration (kept behind STRIPE_ENABLED + secrets).
        user_email = safe_str(st.session_state.get("user", {}).get("email")) if isinstance(st.session_state.get("user"), dict) else safe_str(getattr(st.session_state.get("user"), "email", ""))
        checkout_url = create_stripe_checkout_session(user_id, user_email)
        if checkout_url:
            try:
                st.link_button("Upgrade to Pro", checkout_url)
            except Exception:
                st.markdown(f"[Upgrade to Pro]({checkout_url})")
        else:
            st.button("Upgrade to Pro (coming soon)", disabled=True)
        return False

    return True


# ── User Settings (feature-flagged) ───────────────────────────────────────────

CURRENCY_CHOICES = {
    "USD ($)": {"code": "USD", "symbol": "$"},
    "EUR (€)": {"code": "EUR", "symbol": "€"},
    "GBP (£)": {"code": "GBP", "symbol": "£"},
}


def load_user_settings(user_id: str) -> Optional[Dict[str, Any]]:
    try:
        sb = authed_supabase()
        res = sb.table("user_settings").select("*").eq("user_id", user_id).limit(1).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception:
        return None


def upsert_user_settings(user_id: str, settings: Dict[str, Any]) -> bool:
    try:
        sb = authed_supabase()
        row = {"user_id": user_id}
        row.update(settings)
        # Prefer update; if it doesn't exist, insert.
        existing = load_user_settings(user_id)
        if existing:
            sb.table("user_settings").update(settings).eq("user_id", user_id).execute()
        else:
            sb.table("user_settings").insert(row).execute()
        return True
    except Exception:
        return False


def apply_settings_to_session(user_id: str) -> None:
    # Defaults (always available even if DB table not created yet).
    if "currency_symbol" not in st.session_state:
        st.session_state["currency_symbol"] = "$"
    if "currency_code" not in st.session_state:
        st.session_state["currency_code"] = "USD"

    settings = load_user_settings(user_id)
    if not settings:
        return

    sym = safe_str(settings.get("currency_symbol"))
    if sym:
        st.session_state["currency_symbol"] = sym
    code = safe_str(settings.get("currency_code"))
    if code:
        st.session_state["currency_code"] = code


# ── Journal (feature-flagged) ────────────────────────────────────────────────

JOURNAL_ENABLED = truthy(get_secret("JOURNAL_ENABLED", "false"))


def load_journal_entry(user_id: str, entry_date: str) -> Optional[str]:
    try:
        sb = authed_supabase()
        res = (
            sb.table("journal_entries")
            .select("content")
            .eq("user_id", user_id)
            .eq("entry_date", entry_date)
            .limit(1)
            .execute()
        )
        if res.data:
            return safe_str(res.data[0].get("content"))
        return ""
    except Exception as e:
        st.session_state["_journal_last_error"] = f"{type(e).__name__}: {e}"
        return None


def upsert_journal_entry(user_id: str, entry_date: str, content: str) -> bool:
    try:
        sb = authed_supabase()
        existing = (
            sb.table("journal_entries")
            .select("entry_date")
            .eq("user_id", user_id)
            .eq("entry_date", entry_date)
            .limit(1)
            .execute()
        )
        if existing.data:
            sb.table("journal_entries").update({"content": content}).eq("user_id", user_id).eq("entry_date", entry_date).execute()
        else:
            sb.table("journal_entries").insert({"user_id": user_id, "entry_date": entry_date, "content": content}).execute()
        return True
    except Exception as e:
        st.session_state["_journal_last_error"] = f"{type(e).__name__}: {e}"
        return False


def render_journal_page(user_id: str) -> None:
    st.subheader("Journal")
    st.caption("Daily notes automatically synced to your selected date.")

    follow_today = st.toggle("Follow today", value=True, key="journal_follow_today")
    today = datetime.now().date()
    if follow_today:
        selected_date = today
    else:
        selected_date = st.date_input("Date", today, key="journal_date")

    date_str = selected_date.strftime("%Y-%m-%d")
    state_key = f"journal_content_{date_str}"
    last_key = f"journal_last_saved_{date_str}"

    if state_key not in st.session_state:
        existing = load_journal_entry(user_id, date_str)
        if existing is None:
            st.warning("Journal storage isn't set up yet. Run `sql/journal.sql` in the SAME Supabase project as your app's `SUPABASE_URL` secret.")
            # Only show debug details to the app owner to avoid leaking backend info publicly.
            user_obj = st.session_state.get("user")
            email = ""
            if isinstance(user_obj, dict):
                email = safe_str(user_obj.get("email"))
            else:
                email = safe_str(getattr(user_obj, "email", ""))
            if email.lower() == "omalleyjp402@gmail.com":
                details = safe_str(st.session_state.get("_journal_last_error"))
                if details:
                    with st.expander("Debug details (owner only)", expanded=False):
                        st.code(details)
                        st.caption(f"Supabase URL in app: {SUPABASE_URL}")
            existing = ""
        st.session_state[state_key] = existing
        st.session_state[last_key] = existing

    content = st.text_area(
        f"Entry for {date_str}",
        key=state_key,
        height=280,
        placeholder="Plan, emotions, lessons, what worked, what didn’t…",
    )

    auto = st.toggle("Auto-save", value=True, key="journal_autosave")
    save_clicked = st.button("Save now", key="journal_save")

    if (auto and content != st.session_state.get(last_key, "")) or save_clicked:
        ok = upsert_journal_entry(user_id, date_str, content)
        if ok:
            st.session_state[last_key] = content
            if save_clicked:
                st.success("Saved.")
        else:
            st.error("Could not save journal entry yet (database table/policies may not be set up).")

# ── Auth ──────────────────────────────────────────────────────────────────────

def show_auth():
    render_brand_header(center=True)
    tab_login, tab_signup = st.tabs(["Log in", "Sign up"])

    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Log in"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state["user"] = res.user
                st.session_state["access_token"] = res.session.access_token
                st.rerun()
            except Exception as e:
                msg = safe_str(e)
                if "Invalid API key" in msg or "invalid api key" in msg:
                    st.error("Login failed: Invalid Supabase API key.")
                    st.caption("Fix: In Streamlit Community Cloud → App → Settings → Secrets, set `SUPABASE_URL` (Project URL) and `SUPABASE_KEY` (Anon public key) from Supabase → Settings → API.")
                else:
                    st.error(f"Login failed: {e}")

    with tab_signup:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password (min 6 chars)", type="password", key="signup_password")
        if st.button("Sign up"):
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                st.success("Account created! You can log in now.")
            except Exception as e:
                st.error(f"Sign up failed: {e}")
        st.caption("No confirmation email? Check spam/junk. If it still doesn't arrive, your email provider may be blocking it—reach out and we can resend or adjust SMTP settings.")


def get_user():
    return st.session_state.get("user")


def get_token():
    return st.session_state.get("access_token")


def authed_supabase():
    token = get_token()
    if token:
        supabase.postgrest.auth(token)
    return supabase

# ── Helpers ───────────────────────────────────────────────────────────────────

def to_float(value):
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value):
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def safe_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value)

def get_currency_symbol() -> str:
    return safe_str(st.session_state.get("currency_symbol")) or "$"


def format_money(value) -> str:
    v = to_float(value)
    if v is None:
        return ""
    sign = "-" if v < 0 else ""
    sym = get_currency_symbol()
    return f"{sign}{sym}{abs(v):,.2f}"


def format_price(value) -> str:
    v = to_float(value)
    if v is None:
        return ""
    return f"{v:,.2f}"


def normalize_instrument(value):
    if value is None:
        return None
    v = str(value).strip().upper()
    return v if v else None


def normalize_direction(value):
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in ("long", "l", "buy", "bull"):
        return "Long"
    if v in ("short", "s", "sell", "bear"):
        return "Short"
    return value


def normalize_time_input(value):
    if value is None:
        return None
    try:
        return value.strftime("%H:%M")
    except AttributeError:
        pass
    v = str(value).strip()
    if not v:
        return None
    try:
        return datetime.strptime(v, "%H:%M").strftime("%H:%M")
    except ValueError:
        pass
    try:
        return datetime.strptime(v, "%H:%M:%S").strftime("%H:%M")
    except ValueError:
        pass
    if v.isdigit() and len(v) in (3, 4):
        if len(v) == 3:
            v = f"0{v}"
        return f"{v[:2]}:{v[2:]}"
    return None


def parse_time_hour(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return datetime.strptime(str(value), "%H:%M").hour
    except (TypeError, ValueError):
        return None


def compute_duration_minutes(date_str, entry_time_str, exit_time_str):
    if not date_str or not entry_time_str or not exit_time_str:
        return None
    try:
        date_val = datetime.strptime(str(date_str), "%Y-%m-%d").date()
        entry_t = datetime.strptime(str(entry_time_str), "%H:%M").time()
        exit_t = datetime.strptime(str(exit_time_str), "%H:%M").time()
    except ValueError:
        return None
    entry_dt = datetime.combine(date_val, entry_t)
    exit_dt = datetime.combine(date_val, exit_t)
    if exit_dt < entry_dt:
        exit_dt += timedelta(days=1)
    return (exit_dt - entry_dt).total_seconds() / 60


def compute_metrics(instrument, direction, entry, stop, exit_price, take_profit,
                    contracts, commission, slippage, max_favorable, max_adverse,
                    account_size, date_str, entry_time_str, exit_time_str):
    metrics = {col: None for col in COMPUTED_COLUMNS}
    if not instrument or not direction:
        return metrics
    instrument = normalize_instrument(instrument)
    per_point = INSTRUMENTS.get(instrument)
    if entry is None or stop is None or exit_price is None or contracts is None:
        return metrics

    if direction == "Long":
        points = exit_price - entry
    else:
        points = entry - exit_price

    commission_val = commission or 0
    slippage_val = slippage or 0

    # Forex support (USD account assumptions)
    if instrument in FOREX_PAIRS:
        pip_size = 0.01 if instrument.endswith("JPY") else 0.0001
        pips = points / pip_size if pip_size else 0.0
        lots = contracts if contracts else 1

        # Pip value per lot:
        # - XXXUSD pairs: ~$10 per pip per standard lot
        # - USDJPY: (0.01 * 100k) / price => 1000/price USD per pip
        if instrument == "USDJPY":
            ref_price = entry if entry and entry > 0 else exit_price
            pip_value = (1000.0 / ref_price) if ref_price else 0.0
        else:
            pip_value = 10.0

        pnl_gross = float(pips) * float(pip_value) * float(lots)
        pnl_net = pnl_gross - float(commission_val) - float(slippage_val)
        pnl_per_contract = pnl_net / float(lots) if lots else None

        risk_pips = abs(entry - stop) / pip_size if (entry is not None and stop is not None and pip_size) else None
        risk_dollars = (risk_pips * pip_value * lots) if risk_pips is not None else None
        r_multiple = (pnl_net / risk_dollars) if (risk_dollars and risk_dollars != 0) else None

        target_r = None
        if take_profit is not None and risk_pips not in (None, 0):
            if direction == "Long":
                target_pips = (take_profit - entry) / pip_size
            else:
                target_pips = (entry - take_profit) / pip_size
            target_r = target_pips / risk_pips

        mfe_points = mae_points = mfe_r = mae_r = missed_pnl = None
        if max_favorable is not None:
            mfe_points = ((max_favorable - entry) if direction == "Long" else (entry - max_favorable)) / pip_size
        if max_adverse is not None:
            mae_points = ((entry - max_adverse) if direction == "Long" else (max_adverse - entry)) / pip_size
        if mfe_points is not None and risk_pips not in (None, 0):
            mfe_r = mfe_points / risk_pips
        if mae_points is not None and risk_pips not in (None, 0):
            mae_r = mae_points / risk_pips
        if mfe_points is not None:
            missed_pnl = (mfe_points - pips) * pip_value * lots

        risk_percent_actual = None
        if account_size not in (None, 0) and risk_dollars is not None:
            risk_percent_actual = (risk_dollars / account_size) * 100

        duration_minutes = compute_duration_minutes(date_str, entry_time_str, exit_time_str)

        metrics.update({
            # Store pips in `points` for forex rows (keeps charts/stats meaningful).
            "points": pips, "pnl_gross": pnl_gross, "pnl_net": pnl_net,
            "pnl_per_contract": pnl_per_contract, "r_multiple": r_multiple,
            "target_r": target_r, "mfe_points": mfe_points, "mae_points": mae_points,
            "mfe_r": mfe_r, "mae_r": mae_r, "missed_pnl": missed_pnl,
            "risk_dollars": risk_dollars, "risk_percent_actual": risk_percent_actual,
            "duration_minutes": duration_minutes,
        })
        return metrics

    if per_point is None:
        return metrics

    pnl_gross = points * per_point * contracts
    pnl_net = pnl_gross - commission_val - slippage_val
    pnl_per_contract = pnl_net / contracts if contracts else None
    risk_points = abs(entry - stop)
    risk_dollars = risk_points * per_point * contracts
    r_multiple = points / risk_points if risk_points != 0 else None

    target_r = None
    if take_profit is not None and risk_points != 0:
        if direction == "Long":
            target_points = take_profit - entry
        else:
            target_points = entry - take_profit
        target_r = target_points / risk_points

    mfe_points = mae_points = mfe_r = mae_r = missed_pnl = None
    if max_favorable is not None:
        mfe_points = (max_favorable - entry) if direction == "Long" else (entry - max_favorable)
        mfe_r = mfe_points / risk_points if risk_points != 0 else None
    if max_adverse is not None:
        mae_points = (entry - max_adverse) if direction == "Long" else (max_adverse - entry)
        mae_r = mae_points / risk_points if risk_points != 0 else None
    if mfe_points is not None:
        missed_pnl = (mfe_points - points) * per_point * contracts

    risk_percent_actual = None
    if account_size not in (None, 0):
        risk_percent_actual = (risk_dollars / account_size) * 100

    duration_minutes = compute_duration_minutes(date_str, entry_time_str, exit_time_str)

    metrics.update({
        "points": points, "pnl_gross": pnl_gross, "pnl_net": pnl_net,
        "pnl_per_contract": pnl_per_contract, "r_multiple": r_multiple,
        "target_r": target_r, "mfe_points": mfe_points, "mae_points": mae_points,
        "mfe_r": mfe_r, "mae_r": mae_r, "missed_pnl": missed_pnl,
        "risk_dollars": risk_dollars, "risk_percent_actual": risk_percent_actual,
        "duration_minutes": duration_minutes,
    })
    return metrics


def parse_custom_confluences(raw: str) -> list:
    if not raw:
        return []
    cleaned = raw.replace(";", ",").replace("\n", ",")
    tags = []
    for token in cleaned.split(","):
        name = token.strip()
        if name:
            tags.append(name)
    seen = set()
    unique = []
    for tag in tags:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(tag)
    return unique


def render_metric_cards(cards: list) -> None:
    blocks = []
    for label, value, sub in cards:
        label_html = html_lib.escape(str(label))
        value_html = html_lib.escape(str(value))
        sub_html = html_lib.escape(str(sub)) if sub else ""
        sub_block = f"<div class='metric-sub'>{sub_html}</div>" if sub_html else ""
        blocks.append(
            "<div class='metric-card'>"
            f"<div class='metric-label'>{label_html}</div>"
            f"<div class='metric-value'>{value_html}</div>"
            f"{sub_block}"
            "</div>"
        )
    st.markdown(f"<div class='metric-grid'>{''.join(blocks)}</div>", unsafe_allow_html=True)


def style_altair_chart(chart):
    return (
        chart.configure_view(strokeOpacity=0)
        .configure_axis(gridColor="rgba(148, 163, 184, 0.15)", labelColor="rgba(148, 163, 184, 0.9)",
                        titleColor="rgba(148, 163, 184, 0.9)")
    )


def clamp01(x: float) -> float:
    try:
        x = float(x)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, x))


def scale_linear(value: float, lo: float, hi: float) -> float:
    if hi == lo:
        return 0.0
    return clamp01((value - lo) / (hi - lo)) * 100.0


def compute_zylo_score(df_view: pd.DataFrame, daily_df: pd.DataFrame, pnl_col: str) -> Dict[str, Any]:
    """
    A Tradezella-inspired score, but with our own transparent math.
    Returns overall score (0-100) and component scores (0-100).
    """
    total_trades = len(df_view)
    wins = int((df_view[pnl_col] > 0).sum()) if total_trades else 0
    win_rate = (wins / total_trades * 100.0) if total_trades else 0.0

    wins_df = df_view[df_view[pnl_col] > 0]
    losses_df = df_view[df_view[pnl_col] < 0]
    avg_win = float(wins_df[pnl_col].mean()) if not wins_df.empty else 0.0
    avg_loss = float(losses_df[pnl_col].mean()) if not losses_df.empty else 0.0
    win_loss_ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else 0.0

    loss_sum = float(losses_df[pnl_col].sum()) if not losses_df.empty else 0.0
    profit_factor = (float(wins_df[pnl_col].sum()) / abs(loss_sum)) if loss_sum != 0 else 0.0

    # Equity / drawdown
    chart_df = df_view.sort_values("date").copy()
    chart_df["equity"] = chart_df[pnl_col].cumsum()
    chart_df["peak"] = chart_df["equity"].cummax()
    chart_df["drawdown"] = chart_df["equity"] - chart_df["peak"]
    max_drawdown = abs(float(chart_df["drawdown"].min())) if not chart_df.empty else 0.0
    total_pnl = float(df_view[pnl_col].sum()) if total_trades else 0.0
    recovery_factor = (total_pnl / max_drawdown) if max_drawdown not in (0.0, None) else 0.0

    # Consistency: percent green days among trading days (not calendar days)
    consistency = 0.0
    if daily_df is not None and not daily_df.empty:
        consistency = float((daily_df["pnl"] > 0).mean() * 100.0)

    # Component scaling (tunable later)
    # We keep the radar to 5 axes (pentagon) as requested.
    scores = {
        "Win %": scale_linear(win_rate, 35, 70),
        "Profit Factor": scale_linear(profit_factor, 1.0, 2.5),
        "Avg Win/Loss": scale_linear(win_loss_ratio, 0.8, 2.5),
        "Consistency": scale_linear(consistency, 40, 75),
        # Max Drawdown: lower is better (scale inverse using ratio to total pnl when possible)
        "Max Drawdown": 0.0,
    }

    dd_ratio = None
    if abs(total_pnl) > 0:
        dd_ratio = max_drawdown / abs(total_pnl)
    # If dd_ratio is small -> good. Cap at 1.5.
    if dd_ratio is None:
        scores["Max Drawdown"] = 100.0 if max_drawdown == 0 else 0.0
    else:
        scores["Max Drawdown"] = (1.0 - clamp01(dd_ratio / 1.5)) * 100.0

    # Weighted overall
    weights = {
        "Win %": 0.24,
        "Profit Factor": 0.22,
        "Avg Win/Loss": 0.18,
        "Consistency": 0.18,
        "Max Drawdown": 0.18,
    }
    overall = sum(scores[k] * weights.get(k, 0) for k in scores.keys())
    overall = max(0.0, min(100.0, float(overall)))

    return {
        "overall": overall,
        "components": scores,
        "raw": {
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win_loss": win_loss_ratio,
            "consistency": consistency,
            "max_drawdown": max_drawdown,
        },
    }


def render_zylo_radar(components: Dict[str, float]) -> None:
    """
    Pentagon radar chart (0-100) on a dark background with purple fill.
    """
    # SVG fallback (no Plotly dependency). Keeps the app robust on Streamlit Cloud rebuilds.
    labels = ["Win %", "Profit Factor", "Avg Win/Loss", "Consistency", "Max Drawdown"]
    values = [max(0.0, min(100.0, float(components.get(k, 0.0)))) for k in labels]

    # Geometry
    size = 320
    cx = cy = size / 2
    outer = 120.0
    rings = 4
    import math

    def pt(i: int, r: float) -> tuple[float, float]:
        # Start at top (270deg) and go clockwise
        ang = (-90.0 + i * (360.0 / len(labels))) * math.pi / 180.0
        return (cx + r * math.cos(ang), cy + r * math.sin(ang))

    # Grid rings
    grid_paths = []
    for k in range(1, rings + 1):
        rr = outer * (k / rings)
        ring = [pt(i, rr) for i in range(len(labels))]
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in ring) + " Z"
        grid_paths.append(d)

    # Axes
    axes = []
    for i in range(len(labels)):
        x, y = pt(i, outer)
        axes.append((cx, cy, x, y))

    # Data polygon
    poly = [pt(i, outer * (values[i] / 100.0)) for i in range(len(labels))]
    poly_d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in poly) + " Z"

    # Label positions
    label_nodes = []
    for i, lab in enumerate(labels):
        x, y = pt(i, outer + 28)
        anchor = "middle"
        # slight tweak for left/right
        if x < cx - 30:
            anchor = "end"
        elif x > cx + 30:
            anchor = "start"
        label_nodes.append((x, y, anchor, lab))

    svg = f"""
    <svg width="100%" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width="{size}" height="{size}" fill="rgba(0,0,0,0)"/>
      <g>
        {"".join([f'<path d="{d}" fill="none" stroke="rgba(148,163,184,0.20)" stroke-width="1"/>' for d in grid_paths])}
        {"".join([f'<line x1="{x1}" y1="{y1}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="rgba(148,163,184,0.20)" stroke-width="1"/>' for x1,y1,x2,y2 in axes])}
      </g>
      <path d="{poly_d}" fill="rgba(124,58,237,0.35)" stroke="#A78BFA" stroke-width="2"/>
      {"".join([f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#C4B5FD"/>' for x,y in poly])}
      <g font-family="system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial" font-size="12" fill="rgba(230,237,243,0.95)">
        {"".join([f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{a}" dominant-baseline="middle">{html_lib.escape(t)}</text>' for x,y,a,t in label_nodes])}
      </g>
    </svg>
    """
    st.markdown(svg, unsafe_allow_html=True)


def _max_drawdown(equity: pd.Series) -> float:
    if equity is None or len(equity) == 0:
        return 0.0
    eq = pd.to_numeric(equity, errors="coerce").fillna(0.0)
    peak = eq.cummax()
    dd = eq - peak
    return float(abs(dd.min())) if len(dd) else 0.0


def _profit_factor(pnl: pd.Series) -> Optional[float]:
    pnl = pd.to_numeric(pnl, errors="coerce").fillna(0.0)
    wins = pnl[pnl > 0].sum()
    losses = pnl[pnl < 0].sum()
    if losses == 0:
        return None if wins == 0 else float("inf")
    return float(wins / abs(losses))


def summarize_performance(df_view: pd.DataFrame, pnl_col: str) -> Dict[str, Any]:
    dfp = df_view.copy()
    dfp[pnl_col] = pd.to_numeric(dfp[pnl_col], errors="coerce").fillna(0.0)
    total_trades = int(len(dfp))
    wins = int((dfp[pnl_col] > 0).sum()) if total_trades else 0
    win_rate = (wins / total_trades * 100.0) if total_trades else 0.0
    total_pnl = float(dfp[pnl_col].sum()) if total_trades else 0.0

    wins_df = dfp[dfp[pnl_col] > 0]
    losses_df = dfp[dfp[pnl_col] < 0]
    avg_win = float(wins_df[pnl_col].mean()) if not wins_df.empty else 0.0
    avg_loss = float(losses_df[pnl_col].mean()) if not losses_df.empty else 0.0
    pf = _profit_factor(dfp[pnl_col])

    # Daily breakdown for best/worst day (trading days)
    # Use an explicit "day" column to avoid pandas naming differences across versions.
    day_series = pd.to_datetime(dfp.get("date"), errors="coerce")
    daily = dfp.assign(day=day_series.dt.date).groupby("day", as_index=False)[pnl_col].sum()
    daily = daily.rename(columns={pnl_col: "pnl"})
    best_day = None
    worst_day = None
    if not daily.empty:
        best_row = daily.sort_values("pnl", ascending=False).iloc[0]
        worst_row = daily.sort_values("pnl", ascending=True).iloc[0]
        best_day = {"day": str(best_row.get("day")), "pnl": float(best_row.get("pnl", 0.0))}
        worst_day = {"day": str(worst_row.get("day")), "pnl": float(worst_row.get("pnl", 0.0))}

    # Max drawdown on equity curve (trade-by-trade)
    equity = dfp.sort_values("date")[pnl_col].cumsum()
    max_dd = _max_drawdown(equity)

    return {
        "total_trades": total_trades,
        "wins": wins,
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": pf,
        "max_drawdown": max_dd,
        "best_day": best_day,
        "worst_day": worst_day,
    }


def build_report_card_png(
    title: str,
    subtitle: str,
    metrics: list[tuple[str, str]],
    logo_path: Path,
    footer: str = "",
) -> Optional[bytes]:
    """
    Generate a shareable "certificate-like" report card image (PNG).
    Returns PNG bytes, or None if Pillow isn't available.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except Exception:
        return None

    W, H = 1400, 800
    img = Image.new("RGBA", (W, H), (14, 17, 23, 255))
    draw = ImageDraw.Draw(img)

    # Background gradient
    for y in range(H):
        t = y / max(1, H - 1)
        # Purple -> deep -> blue
        r = int(14 + (124 - 14) * max(0.0, 1.0 - t * 1.3))
        g = int(17 + (58 - 17) * max(0.0, 1.0 - t * 1.3))
        b = int(23 + (237 - 23) * max(0.0, 1.0 - (1.0 - t) * 1.1) * 0.22)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))
    # Accent glow blobs
    draw.ellipse((-120, -160, 560, 520), fill=(124, 58, 237, 55))
    draw.ellipse((840, -220, 1560, 520), fill=(56, 189, 248, 35))
    draw.ellipse((260, 420, 1140, 1180), fill=(124, 58, 237, 25))

    # Panel
    pad = 64
    panel = (pad, pad, W - pad, H - pad)
    draw.rounded_rectangle(panel, radius=34, fill=(16, 20, 30, 210), outline=(255, 255, 255, 30), width=2)

    # Fonts (fallback to default if truetype not available)
    def fnt(size: int):
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size=size)
        except Exception:
            return ImageFont.load_default()

    font_title = fnt(58)
    font_sub = fnt(26)
    font_k = fnt(22)
    font_v = fnt(34)
    font_footer = fnt(18)

    # Logo
    x0, y0 = panel[0] + 38, panel[1] + 34
    if logo_path.exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((110, 110))
            lx, ly = logo.size
            # logo tile with border
            tile = Image.new("RGBA", (lx + 32, ly + 32), (255, 255, 255, 0))
            td = ImageDraw.Draw(tile)
            td.rounded_rectangle((0, 0, lx + 32, ly + 32), radius=20, fill=(255, 255, 255, 18), outline=(255, 255, 255, 40), width=2)
            tile.paste(logo, (16, 16), logo)
            img.alpha_composite(tile, (x0, y0))
            x_text = x0 + lx + 64
        except Exception:
            x_text = x0
    else:
        x_text = x0

    # Header text
    draw.text((x_text, y0 + 6), title, font=font_title, fill=(230, 237, 243, 245))
    draw.text((x_text, y0 + 78), subtitle, font=font_sub, fill=(148, 163, 184, 235))

    # Metric grid (2 rows x 4 cols)
    grid_top = panel[1] + 190
    grid_left = panel[0] + 38
    grid_right = panel[2] - 38
    cols = 4
    rows = int((len(metrics) + cols - 1) / cols)
    card_w = int((grid_right - grid_left - (cols - 1) * 18) / cols)
    card_h = 140

    for idx, (k, v) in enumerate(metrics):
        r = idx // cols
        c = idx % cols
        x = grid_left + c * (card_w + 18)
        y = grid_top + r * (card_h + 18)
        rect = (x, y, x + card_w, y + card_h)
        draw.rounded_rectangle(rect, radius=24, fill=(255, 255, 255, 10), outline=(255, 255, 255, 26), width=2)
        # Key
        draw.text((x + 18, y + 16), k.upper(), font=font_k, fill=(148, 163, 184, 235))
        # Value
        draw.text((x + 18, y + 58), v, font=font_v, fill=(230, 237, 243, 245))

    # Footer
    if footer:
        draw.text((panel[0] + 38, panel[3] - 44), footer, font=font_footer, fill=(148, 163, 184, 220))

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def compute_streaks(daily_pnl: pd.DataFrame) -> Dict[str, Any]:
    """
    daily_pnl: columns [date (datetime64[ns]), pnl (float)]
    Streaks are based on trading days/weeks present in data.
    """
    out: Dict[str, Any] = {}
    if daily_pnl is None or daily_pnl.empty:
        return {"daily": {"current": 0, "record": 0}, "weekly": {"current": 0, "record": 0}}

    d = daily_pnl.copy()
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d["pnl"] = pd.to_numeric(d["pnl"], errors="coerce").fillna(0.0)
    d = d.sort_values("date")

    # Daily streak (consecutive trading days with pnl > 0)
    wins = (d["pnl"] > 0).tolist()
    current = 0
    for w in reversed(wins):
        if w:
            current += 1
        else:
            break
    record = 0
    run = 0
    for w in wins:
        if w:
            run += 1
            record = max(record, run)
        else:
            run = 0
    out["daily"] = {"current": current, "record": record}

    # Weekly streak (consecutive weeks with total weekly pnl > 0)
    wk = d.set_index("date")["pnl"].resample("W-SUN").sum().reset_index()
    wk["win"] = wk["pnl"] > 0
    wlist = wk["win"].tolist()
    wcur = 0
    for w in reversed(wlist):
        if w:
            wcur += 1
        else:
            break
    wrec = 0
    run = 0
    for w in wlist:
        if w:
            run += 1
            wrec = max(wrec, run)
        else:
            run = 0
    out["weekly"] = {"current": wcur, "record": wrec}
    return out


def render_reports_page(df_view: pd.DataFrame, pnl_col: str, account_type: str) -> None:
    st.title("Report Cards")
    st.caption("Shareable weekly + monthly summaries. (You can download as PNG.)")

    dfp = df_view.copy()
    dfp["date"] = pd.to_datetime(dfp["date"], errors="coerce").dt.normalize()
    dfp = dfp.dropna(subset=["date"])
    dfp[pnl_col] = pd.to_numeric(dfp[pnl_col], errors="coerce").fillna(0.0)
    if dfp.empty:
        st.info("No trades yet.")
        return

    daily = dfp.groupby("date", as_index=False)[pnl_col].sum().rename(columns={pnl_col: "pnl"})
    daily = daily.sort_values("date")

    tab_week, tab_month = st.tabs(["Weekly", "Monthly"])

    def render_period(title: str, period_df: pd.DataFrame, subtitle: str) -> None:
        stats = summarize_performance(period_df, pnl_col)
        pf = stats["profit_factor"]
        pf_txt = "∞" if pf == float("inf") else (f"{pf:.2f}" if isinstance(pf, (int, float)) else "n/a")

        metrics = [
            ("Total PnL", format_money(stats["total_pnl"])),
            ("Trades", str(stats["total_trades"])),
            ("Win Rate", f"{stats['win_rate']:.1f}%"),
            ("Profit Factor", pf_txt),
            ("Avg Win", format_money(stats["avg_win"])),
            ("Avg Loss", format_money(stats["avg_loss"])),
            ("Max Drawdown", format_money(-abs(stats["max_drawdown"]))),
            ("Best Day", format_money(stats["best_day"]["pnl"]) if stats["best_day"] else "—"),
        ]

        # On-screen cards
        cols = st.columns(4)
        for i, (k, v) in enumerate(metrics[:8]):
            cols[i % 4].metric(k, v)

        # Shareable certificate
        st.markdown("---")
        st.subheader("Shareable card")
        footer = f"{BRAND_NAME} · {account_type} · Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        png = build_report_card_png(
            title=f"{BRAND_NAME} {title}",
            subtitle=subtitle,
            metrics=metrics[:8],
            logo_path=LOGO_PATH,
            footer=footer,
        )
        if png:
            st.image(png, use_container_width=True)
            st.download_button(
                "Download PNG",
                data=png,
                file_name=f"{BRAND_NAME.lower()}_{title.lower().replace(' ','_')}_{account_type.lower().replace(' ','_')}.png",
                mime="image/png",
                use_container_width=True,
            )
        else:
            st.info("PNG export requires Pillow. Add `pillow` to requirements to enable it.")

    with tab_week:
        wk = daily.set_index("date")["pnl"].resample("W-SUN").sum().reset_index()
        wk = wk.sort_values("date")
        wk["start"] = wk["date"] - pd.to_timedelta(6, unit="D")
        wk["label"] = wk.apply(lambda r: f"{r['start'].strftime('%b %d')} - {r['date'].strftime('%b %d, %Y')}", axis=1)
        labels = wk["label"].tolist()
        default_idx = len(labels) - 1
        choice = st.selectbox("Select week", labels, index=max(0, default_idx))
        row = wk[wk["label"] == choice].iloc[0]
        start = row["start"]
        end = row["date"]
        period_trades = dfp[(dfp["date"] >= start) & (dfp["date"] <= end)].copy()
        render_period("Weekly Report", period_trades, subtitle=choice)

    with tab_month:
        mo = daily.set_index("date")["pnl"].resample("M").sum().reset_index()
        mo = mo.sort_values("date")
        mo["label"] = mo["date"].dt.strftime("%B %Y")
        labels = mo["label"].tolist()
        default_idx = len(labels) - 1
        choice = st.selectbox("Select month", labels, index=max(0, default_idx))
        row = mo[mo["label"] == choice].iloc[0]
        end = row["date"]
        start = (end - pd.offsets.MonthBegin(1)).normalize()
        period_trades = dfp[(dfp["date"] >= start) & (dfp["date"] <= end)].copy()
        render_period("Monthly Report", period_trades, subtitle=choice)


def render_streaks_page(df_view: pd.DataFrame, pnl_col: str) -> None:
    st.title("Streaks & Milestones")
    st.caption("Built from your trading days and weekly net PnL.")

    dfp = df_view.copy()
    dfp["date"] = pd.to_datetime(dfp["date"], errors="coerce").dt.normalize()
    dfp = dfp.dropna(subset=["date"])
    dfp[pnl_col] = pd.to_numeric(dfp[pnl_col], errors="coerce").fillna(0.0)
    if dfp.empty:
        st.info("No trades yet.")
        return

    daily = dfp.groupby("date", as_index=False)[pnl_col].sum().rename(columns={pnl_col: "pnl"}).sort_values("date")
    streaks = compute_streaks(daily.rename(columns={"date": "date", "pnl": "pnl"}))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Daily Win Streak", streaks["daily"]["current"], f"Record: {streaks['daily']['record']}")
    c2.metric("Weekly Win Streak", streaks["weekly"]["current"], f"Record: {streaks['weekly']['record']}")

    stats = summarize_performance(dfp, pnl_col)
    c3.metric("Best Day", format_money(stats["best_day"]["pnl"]) if stats["best_day"] else "—", stats["best_day"]["day"] if stats["best_day"] else "")
    c4.metric("Worst Day", format_money(stats["worst_day"]["pnl"]) if stats["worst_day"] else "—", stats["worst_day"]["day"] if stats["worst_day"] else "")

    st.markdown("---")
    st.subheader("Milestones")
    wk = daily.set_index("date")["pnl"].resample("W-SUN").sum().reset_index()
    mo = daily.set_index("date")["pnl"].resample("M").sum().reset_index()

    best_week = wk.sort_values("pnl", ascending=False).head(1)
    best_month = mo.sort_values("pnl", ascending=False).head(1)
    cols = st.columns(3)
    if not best_week.empty:
        end = best_week.iloc[0]["date"]
        start = end - pd.to_timedelta(6, unit="D")
        cols[0].metric("Best Week", format_money(float(best_week.iloc[0]["pnl"])), f"{start.strftime('%b %d')} – {end.strftime('%b %d')}")
    else:
        cols[0].metric("Best Week", "—")
    if not best_month.empty:
        end = best_month.iloc[0]["date"]
        cols[1].metric("Best Month", format_money(float(best_month.iloc[0]["pnl"])), end.strftime("%B %Y"))
    else:
        cols[1].metric("Best Month", "—")
    cols[2].metric("Max Drawdown", format_money(-abs(stats["max_drawdown"])))

    st.markdown("---")
    st.subheader("Daily PnL (trading days)")
    dd = daily.copy()
    dd["pos"] = dd["pnl"] >= 0
    chart = (
        alt.Chart(dd)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("date:T", axis=alt.Axis(title=None, format="%b %d")),
            y=alt.Y("pnl:Q", axis=alt.Axis(title=None), scale=alt.Scale(zero=False)),
            color=alt.condition("datum.pos", alt.value("#22c55e"), alt.value("#ef4444")),
            tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("pnl:Q", title="PnL", format=",.2f")],
        )
        .properties(height=260)
    )
    st.altair_chart(style_altair_chart(chart), use_container_width=True)

def render_pnl_calendar(df: pd.DataFrame, pnl_col: str) -> None:
    if df.empty:
        st.info("No daily PnL yet.")
        return
    daily = (
        df.groupby("date", as_index=False)[pnl_col]
        .agg(pnl="sum", trades="count")
        .rename(columns={pnl_col: "pnl"})
    )
    daily["date"] = pd.to_datetime(daily["date"]).dt.date
    daily["month"] = pd.to_datetime(daily["date"]).dt.to_period("M")
    months = sorted(daily["month"].unique())
    if not months:
        st.info("No calendar data yet.")
        return

    month_labels = [m.to_timestamp().strftime("%B %Y") for m in months]
    month_choice = st.selectbox("Month", month_labels, index=len(month_labels) - 1)
    selected_period = months[month_labels.index(month_choice)]
    year, month = selected_period.year, selected_period.month
    month_df = daily[daily["month"] == selected_period]
    month_daily = {row["date"]: (row["pnl"], row["trades"]) for _, row in month_df.iterrows()}
    max_abs = max((abs(v[0]) for v in month_daily.values()), default=0) or 1

    month_total = month_df["pnl"].sum() if not month_df.empty else 0
    green_days = (month_df["pnl"] > 0).sum() if not month_df.empty else 0
    red_days = (month_df["pnl"] < 0).sum() if not month_df.empty else 0
    flat_days = (month_df["pnl"] == 0).sum() if not month_df.empty else 0

    stats_cols = st.columns([2, 3])
    with stats_cols[0]:
        st.markdown(f"**{month_choice}**")
    with stats_cols[1]:
        st.markdown(
            f"**Monthly stats:** {format_money(month_total)} · "
            f"{green_days} green · {red_days} red · {flat_days} flat"
        )

    def pnl_color(value):
        if value == 0:
            return "rgba(148, 163, 184, 0.08)"
        ratio = min(abs(value) / max_abs, 1)
        alpha = 0.18 + (0.6 * ratio)
        if value > 0:
            return f"rgba(34, 197, 94, {alpha:.3f})"
        return f"rgba(239, 68, 68, {alpha:.3f})"

    cal = calendar.Calendar(firstweekday=6)
    weeks = cal.monthdatescalendar(year, month)
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    header_html = "".join([f"<div class='cal-head'>{d}</div>" for d in day_names])
    cell_html = []
    week_html = []
    week_date_map = {}
    week_idx = 1
    for week in weeks:
        week_total = 0
        week_trades = 0
        week_dates = []
        for day in week:
            in_month = day.month == month
            value, trades = month_daily.get(day, (0, 0)) if in_month else (0, 0)
            if in_month:
                week_total += value
                week_trades += trades
                week_dates.append(day)
            bg = pnl_color(value) if in_month else "rgba(148, 163, 184, 0.04)"
            pnl_text = format_money(value) if in_month and value != 0 else ""
            trades_text = f"{trades} trades" if in_month and trades else ""
            day_class = "cal-cell" + ("" if in_month else " cal-off")
            link_date = day.strftime("%Y-%m-%d")
            # NOTE: We intentionally avoid clickable <a href> links here.
            # Streamlit treats this as a full navigation and can create a new session,
            # which would log users out (because auth is stored in session_state).
            cell_html.append(
                "<div class='{cls}' style='background:{bg};'>"
                "<div class='cal-day'>{day}</div>"
                "<div class='cal-pnl'>{pnl}</div>"
                "<div class='cal-trades'>{trades}</div>"
                "</div>".format(
                    cls=day_class,
                    bg=bg,
                    day=day.day,
                    pnl=pnl_text,
                    trades=trades_text,
                )
            )
        week_label = f"Week {week_idx}"
        week_total_text = format_money(week_total) if week_total != 0 else "$0"
        week_date_map[str(week_idx)] = [d.strftime("%Y-%m-%d") for d in week_dates]
        week_html.append(
            "<div class='cal-week'>"
            f"<div class='cal-week-label'>{week_label}</div>"
            f"<div class='cal-week-total'>{week_total_text}</div>"
            f"<div class='cal-week-trades'>{week_trades} trades</div>"
            "</div>"
        )
        week_idx += 1

    st.markdown(
        "<div class='calendar-card'>"
        "<div class='calendar-wrap'>"
        "<div class='calendar-grid'>{header}{cells}</div>"
        "<div class='calendar-weeks'>{weeks}</div>"
        "</div>"
        "</div>".format(
            header=header_html,
            cells="".join(cell_html),
            weeks="".join(week_html),
        ),
        unsafe_allow_html=True,
    )
    st.session_state["calendar_week_date_map"] = week_date_map


def load_logo_data():
    if LOGO_PATH.exists():
        data = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")
        return f"data:image/png;base64,{data}"
    return None


def apply_brand_watermark(logo_uri: str) -> None:
    # Disabled: a watermark on metric cards/charts makes values harder to read.
    # We keep branding via headers + sidebar styling instead.
    return


def render_brand_header(center: bool = False, hero: bool = False) -> None:
    logo_uri = load_logo_data()
    apply_brand_watermark(logo_uri)
    if center:
        row_class = "brand-row center"
    elif hero:
        row_class = "brand-row hero"
    else:
        row_class = "brand-row"
    if logo_uri:
        st.markdown(
            f"""
            <div class="{row_class}">
                <img src="{logo_uri}" class="brand-logo" alt="{BRAND_NAME} logo"/>
                <div>
                    <div class="brand-name">{BRAND_NAME}</div>
                    <div class="brand-tagline">{BRAND_TAGLINE}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="{row_class}">
                <div>
                    <div class="brand-name">{BRAND_NAME}</div>
                    <div class="brand-tagline">{BRAND_TAGLINE}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ── Supabase data helpers ─────────────────────────────────────────────────────

def load_trades(user_id: str, account_type: str) -> pd.DataFrame:
    sb = authed_supabase()
    res = sb.table("trades").select("*").eq("user_id", user_id).eq("account_type", account_type).execute()
    if res.data:
        df = pd.DataFrame(res.data)
        df = df.drop(columns=["user_id", "account_type", "created_at"], errors="ignore")
        return df
    return pd.DataFrame()


def save_trade(user_id: str, account_type: str, row: dict):
    sb = authed_supabase()
    row = row.copy()
    row["user_id"] = user_id
    row["account_type"] = account_type
    # Clean NaN/None for json
    for k, v in row.items():
        if isinstance(v, float) and pd.isna(v):
            row[k] = None
    sb.table("trades").upsert(row).execute()


def delete_trade(trade_id: str):
    sb = authed_supabase()
    sb.table("trades").delete().eq("id", trade_id).execute()


def update_trade(row: dict):
    sb = authed_supabase()
    row = row.copy()
    trade_id = row.pop("id")
    for k, v in row.items():
        if isinstance(v, float) and pd.isna(v):
            row[k] = None
    sb.table("trades").update(row).eq("id", trade_id).execute()


def upload_image(user_id: str, file) -> str:
    sb = authed_supabase()
    ext = file.name.split(".")[-1].lower()
    filename = f"{user_id}/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex}.{ext}"
    # Streamlit's UploadedFile.getbuffer() returns a memoryview; Supabase expects bytes.
    payload = file.getvalue() if hasattr(file, "getvalue") else bytes(file.getbuffer())
    content_type_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }
    content_type = content_type_map.get(ext, "application/octet-stream")
    sb.storage.from_("trade-images").upload(filename, payload, {"content-type": content_type})
    return filename


def get_image_url(path: str) -> str:
    sb = authed_supabase()
    res = sb.storage.from_("trade-images").create_signed_url(path, 3600)
    return res.get("signedURL") or res.get("signed_url", "")

# ── Analytics helpers ─────────────────────────────────────────────────────────

def prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")
    for col in NUMERIC_COLUMNS:
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")
    cleaned["entry_hour"] = cleaned["entry_time"].apply(parse_time_hour) if "entry_time" in cleaned.columns else None
    return cleaned


def collect_tags(df: pd.DataFrame, column: str) -> list:
    tags = set()
    for value in df[column].fillna("").astype(str):
        for tag in value.split(","):
            tag_clean = tag.strip()
            if tag_clean:
                tags.add(tag_clean)
    return sorted(tags)


def explode_tags(df: pd.DataFrame, column: str) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        raw = str(row.get(column, "") or "")
        tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
        if not tags:
            continue
        for tag in tags:
            new_row = row.copy()
            new_row[column] = tag
            rows.append(new_row)
    return pd.DataFrame(rows)


def build_confluence_combo_stats(df: pd.DataFrame, pnl_col: str, min_confluences: int = 1) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        raw = str(row.get("confluences", "") or "")
        tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
        tags = sorted(set(tags))
        if len(tags) < min_confluences:
            continue
        combo = " + ".join(tags)
        rows.append({"combo": combo, "pnl": row.get(pnl_col)})
    if not rows:
        return pd.DataFrame()
    combo_df = pd.DataFrame(rows)
    stats = (
        combo_df.groupby("combo")["pnl"]
        .agg(["sum", "mean", "count"])
        .rename(columns={"sum": "Total PnL", "mean": "Avg PnL", "count": "Trades"})
        .sort_values("Total PnL", ascending=False)
    )
    stats["Win rate %"] = combo_df.groupby("combo")["pnl"].apply(lambda s: (s > 0).mean() * 100)
    return stats


def render_calendar_heatmap(df: pd.DataFrame, pnl_col: str) -> None:
    if df.empty:
        st.info("No daily PnL yet.")
        return
    daily = df.groupby("date")[pnl_col].sum().reset_index()
    daily["month"] = daily["date"].dt.to_period("M").astype(str)
    months = sorted(daily["month"].unique())
    month_choice = st.selectbox("Heatmap month", months, index=len(months) - 1)
    month_df = daily[daily["month"] == month_choice].copy()
    if month_df.empty:
        st.info("No data for this month.")
        return
    month_df["week"] = month_df["date"].dt.isocalendar().week.astype(int)
    month_df["weekday"] = month_df["date"].dt.day_name()
    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    pivot = (
        month_df.pivot_table(index="week", columns="weekday", values=pnl_col, aggfunc="sum")
        .reindex(columns=weekday_order).fillna(0)
    )
    try:
        import matplotlib  # noqa: F401
        styled = pivot.style.background_gradient(cmap="RdYlGn").format("{:.2f}")
        st.dataframe(styled, use_container_width=True)
    except Exception:
        st.dataframe(pivot.round(2), use_container_width=True)

# ── A4 trade sheet ────────────────────────────────────────────────────────────

def build_a4_trade_sheet_html(row: pd.Series) -> str:
    date_val = row.get("date")
    date_text = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else safe_str(date_val)
    date = html_lib.escape(date_text)
    instrument_raw = safe_str(row.get("instrument")).strip().upper()
    instrument = html_lib.escape(instrument_raw)
    direction = html_lib.escape(safe_str(row.get("direction")))
    entry_time = html_lib.escape(safe_str(row.get("entry_time")))
    contracts = to_int(row.get("contracts"))
    contracts_str = str(contracts) if contracts is not None else ""
    size_label = "micros" if instrument_raw in ("MNQ", "MES") else "minis"
    trade_type = html_lib.escape(safe_str(row.get("trade_type")))
    strategy = html_lib.escape(safe_str(row.get("strategy")))
    entry = format_price(row.get("entry_price"))
    stop = format_price(row.get("stop_loss"))
    exit_price = format_price(row.get("exit_price"))
    take_profit = format_price(row.get("take_profit"))
    target_r = to_float(row.get("target_r"))
    rr_text = f"1:{target_r:.2f}" if target_r is not None else ""
    pnl = to_float(row.get("pnl_override")) or to_float(row.get("pnl_net"))
    pnl_text = format_money(pnl)
    followed_plan = html_lib.escape(safe_str(row.get("followed_plan")))
    revenge_trade = html_lib.escape(safe_str(row.get("revenge_trade")))
    emotion = to_int(row.get("emotion_score"))
    emotion_text = str(emotion) if emotion is not None else ""
    selected_confluences = {t.strip() for t in safe_str(row.get("confluences")).split(",") if t.strip()}
    confluence_items = []
    for name in CONFLUENCES:
        checked = "x" if name in selected_confluences else ""
        confluence_items.append(
            f"<div class='conf-item'><span class='cb'>{checked}</span><span class='conf-name'>{html_lib.escape(name)}</span></div>"
        )
    extra_confluences = sorted(c for c in selected_confluences if c not in set(CONFLUENCES))
    for name in extra_confluences:
        confluence_items.append(
            "<div class='conf-item'>"
            "<span class='cb'>x</span>"
            f"<span class='conf-name'>{html_lib.escape(f'Other: {name}')}</span>"
            "</div>"
        )
    confluence_html = "\n".join(confluence_items)
    reason = html_lib.escape(safe_str(row.get("setup_tag")))

    return f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<style>
@page{{size:A4;margin:12mm}}
html,body{{background:#fff}}
body{{font-family:Arial,Helvetica,sans-serif;margin:0;padding:0;color:#000}}
.toolbar{{display:flex;gap:10px;align-items:center;padding:6px 0;margin:0 0 6px 0}}
.toolbar .toolbar-inner{{display:flex;gap:10px;align-items:center;background:#fff;border:2px solid #000;border-radius:10px;padding:8px 10px}}
.toolbar button{{padding:6px 10px;border:2px solid #000;background:#fff;color:#000;cursor:pointer;border-radius:10px;font-weight:700}}
@media print{{.toolbar{{display:none}}}}
.sheet{{width:210mm;min-height:297mm;box-sizing:border-box;padding:0;background:#fff}}
.grid{{display:grid;gap:6mm}}
.box{{border:2px solid #000;box-sizing:border-box;background:#fff}}
.box-title{{font-weight:700;text-align:center;padding:3mm 2mm;border-bottom:2px solid #000;letter-spacing:.5px}}
.row{{display:grid;gap:6mm;grid-template-columns:1fr 1fr}}
.kv{{display:grid;grid-template-columns:38mm 1fr;border-top:2px solid #000}}
.kv:first-of-type{{border-top:0}}
.kv .k{{padding:3mm;border-right:2px solid #000;font-weight:700}}
.kv .v{{padding:3mm}}
.topline{{display:grid;grid-template-columns:1fr 1fr}}
.topline>div{{padding:4mm}}
.topline>div:first-child{{border-right:2px solid #000}}
.conf-list{{column-count:2;column-gap:6mm;padding:3mm}}
.conf-item{{break-inside:avoid;display:grid;grid-template-columns:6mm 1fr;gap:2mm;align-items:start;margin-bottom:2mm}}
.cb{{display:inline-block;width:5mm;height:5mm;border:2px solid #000;line-height:5mm;font-size:11px;text-align:center}}
.conf-name{{font-size:12px}}
.trade-mgmt{{display:grid;grid-template-columns:1fr 1fr}}
.trade-mgmt .k{{padding:3mm;border-top:2px solid #000;border-right:2px solid #000;font-weight:700}}
.trade-mgmt .v{{padding:3mm;border-top:2px solid #000}}
.trade-mgmt .k:nth-child(1),.trade-mgmt .v:nth-child(2){{border-top:0}}
.analysis-lines{{padding:0}}
.analysis-line{{display:grid;grid-template-columns:55mm 1fr;border-top:2px solid #000}}
.analysis-line:first-child{{border-top:0}}
.analysis-line .k{{padding:3mm;border-right:2px solid #000;font-weight:700}}
.analysis-line .v{{padding:3mm}}
.feedback{{display:grid;grid-template-columns:1fr 1fr;border-top:2px solid #000}}
.feedback .k{{padding:3mm;border-right:2px solid #000;font-weight:700}}
.feedback .v{{padding:3mm}}
</style></head><body>
<div class="toolbar"><div class="toolbar-inner"><button onclick="window.print()">Print (A4)</button></div></div>
<div class="sheet grid">
<div class="box"><div class="topline">
<div><b>DATE:</b> {date}</div><div><b>SYMBOL:</b> {instrument}</div>
</div></div>
<div class="row">
<div class="box"><div class="box-title">TRADING SETUP</div>
<div class="kv"><div class="k">POSITION:</div><div class="v">{direction}</div></div>
<div class="kv"><div class="k">TIME:</div><div class="v">{entry_time}</div></div>
<div class="kv"><div class="k">LOT SIZE:</div><div class="v">{contracts_str} {size_label}</div></div>
<div class="kv"><div class="k">TYPE:</div><div class="v">{trade_type}</div></div>
<div class="kv"><div class="k">STRATEGY:</div><div class="v">{strategy}</div></div>
</div>
<div class="box"><div class="box-title">CONFLUENCES</div>
<div class="conf-list">{confluence_html}</div></div>
</div>
<div class="box"><div class="box-title">TRADE MANAGEMENT</div>
<div class="trade-mgmt">
<div class="k">ENTRY:</div><div class="v">{entry}</div>
<div class="k">STOP LOSS:</div><div class="v">{stop}</div>
<div class="k">EXIT:</div><div class="v">{exit_price}</div>
<div class="k">TAKE PROFIT:</div><div class="v">{take_profit}</div>
<div class="k">R/R:</div><div class="v">{rr_text}</div>
<div class="k">PROFIT/LOSS:</div><div class="v">{pnl_text}</div>
</div></div>
<div class="box"><div class="box-title">TRADE ANALYSIS</div>
<div class="analysis-lines">
<div class="analysis-line"><div class="k">REASON FOR TRADE:</div><div class="v">{reason}</div></div>
<div class="analysis-line"><div class="k">ASSUMPTIONS BEFORE TRADE:</div><div class="v"></div></div>
</div></div>
<div class="box"><div class="box-title">FEEDBACK</div>
<div class="feedback">
<div class="k">DISCIPLINED (PLAN):</div><div class="v">{followed_plan}</div>
<div class="k">REVENGE TRADE:</div><div class="v">{revenge_trade}</div>
</div>
<div class="analysis-line"><div class="k">EMOTION SCORE:</div><div class="v">{emotion_text}</div></div>
</div>
</div></body></html>"""

# ── Main section renderer ─────────────────────────────────────────────────────

def render_section(user_id: str, account_type: str, section: str) -> None:
    form_key = account_type.replace(" ", "_").lower()

    df_raw = load_trades(user_id, account_type)

    if section == "New Trade":
        # ── Add new trade form ────────────────────────────────────────────────────
        with st.expander("Add new trade", expanded=True):
            with st.form(f"{form_key}_form", clear_on_submit=True):
                st.markdown("**Core trade info**")
                row1 = st.columns(4)
                date_val = row1[0].date_input("Date", key=f"{form_key}_date")
                use_times = row1[1].checkbox("Use entry/exit times", value=False, key=f"{form_key}_use_times")
                with row1[2]:
                    ec = st.columns(2)
                    entry_time = ec[0].selectbox("Entry time (15m)", TIME_OPTIONS, index=TIME_OPTIONS.index("09:30"), key=f"{form_key}_entry_time")
                    entry_time_custom = ec[1].text_input("Entry time (HH:MM)", placeholder="15:44", key=f"{form_key}_entry_time_custom")
                with row1[3]:
                    xc = st.columns(2)
                    exit_time = xc[0].selectbox("Exit time (15m)", TIME_OPTIONS, index=TIME_OPTIONS.index("10:00"), key=f"{form_key}_exit_time")
                    exit_time_custom = xc[1].text_input("Exit time (HH:MM)", placeholder="16:02", key=f"{form_key}_exit_time_custom")
    
                row2 = st.columns(4)
                instrument = row2[0].selectbox("Instrument", INSTRUMENT_ORDER, key=f"{form_key}_instrument")
                direction = row2[1].radio("Direction", ["Long", "Short"], key=f"{form_key}_direction")
                contracts = row2[2].number_input("Contracts", min_value=1, step=1, value=1, key=f"{form_key}_contracts")
                session = row2[3].selectbox("Session", SESSIONS, key=f"{form_key}_session")
    
                row2b = st.columns(4)
                trade_type = row2b[0].selectbox("Trade type", TRADE_TYPES, key=f"{form_key}_trade_type")
                other_trade_type = ""
                if trade_type == "Other":
                    other_trade_type = row2b[1].text_input(
                        "Other trade type",
                        placeholder="Type your trade type…",
                        key=f"{form_key}_trade_type_other",
                    )
                else:
                    row2b[1].markdown("")

                strategies = load_strategies(user_id)
                strategy_names = [r.get("name") for r in strategies if r.get("name")]
                strategy_choice = row2b[2].selectbox(
                    "Model / strategy",
                    ["Not set", "Custom…"] + strategy_names,
                    key=f"{form_key}_strategy_choice",
                )
                if strategy_choice == "Custom…":
                    strategy = row2b[3].text_input(
                        "Custom model/strategy",
                        placeholder="Type your model/strategy…",
                        key=f"{form_key}_strategy",
                    )
                elif strategy_choice == "Not set":
                    strategy = ""
                    row2b[3].markdown("")
                else:
                    strategy = strategy_choice
                    row2b[3].markdown("")
    
                st.markdown("**Confluences (check all that apply)**")
                conf_cols = st.columns(4)
                selected_confluences = []
                for idx, name in enumerate(CONFLUENCES):
                    if conf_cols[idx % 4].checkbox(name, key=f"{form_key}_conf_{idx}"):
                        selected_confluences.append(name)
                other_cols = st.columns([1, 3])
                with other_cols[0]:
                    other_conf = st.checkbox("Other (custom)", key=f"{form_key}_conf_other")
                with other_cols[1]:
                    other_conf_text = st.text_input(
                        "Custom confluences (comma-separated)",
                        placeholder="Liquidity sweep, VWAP reclaim",
                        key=f"{form_key}_conf_other_text",
                        help="Type one or more, separated by commas.",
                    )
                if other_conf or other_conf_text.strip():
                    for name in parse_custom_confluences(other_conf_text):
                        if name not in selected_confluences:
                            selected_confluences.append(name)
    
                row3 = st.columns(4)
                entry = row3[0].number_input("Entry price", min_value=0.0, step=0.25, format="%.2f", key=f"{form_key}_entry")
                stop = row3[1].number_input("Stop loss", min_value=0.0, step=0.25, format="%.2f", key=f"{form_key}_stop")
                take_profit = row3[2].number_input("Take profit", min_value=0.0, step=0.25, format="%.2f", key=f"{form_key}_take_profit")
                exit_price = row3[3].number_input("Exit price", min_value=0.0, step=0.25, format="%.2f", key=f"{form_key}_exit")
    
                row4 = st.columns(4)
                emotion = row4[0].slider("Emotion score (1–10)", 1, 10, 5, key=f"{form_key}_emotion")
                followed_plan = row4[1].selectbox("Followed plan?", ["Yes", "No"], key=f"{form_key}_followed_plan")
                revenge_trade = row4[2].selectbox("Revenge trade?", ["No", "Yes"], key=f"{form_key}_revenge_trade")
                trade_grade = row4[3].selectbox("Trade grade", TRADE_GRADES, key=f"{form_key}_grade")
    
                notes = st.text_area("Notes", key=f"{form_key}_notes")
    
                with st.expander("Advanced (optional)", expanded=False):
                    adv1 = st.columns(4)
                    setup_tag = adv1[0].text_input("Setup / tag (comma-separated)", key=f"{form_key}_setup")
                    adv1[1].markdown("Model/strategy is set above.")
                    market_condition = adv1[2].selectbox("Market condition", MARKET_CONDITIONS, key=f"{form_key}_market")
                    account_size = adv1[3].number_input("Account size ($)", min_value=0.0, step=100.0, format="%.2f", key=f"{form_key}_account_size")
    
                    adv2 = st.columns(4)
                    risk_percent_planned = adv2[0].number_input("Planned risk %", min_value=0.0, step=0.1, format="%.2f", key=f"{form_key}_risk_planned")
                    commission = adv2[1].number_input("Commission/fees ($)", min_value=0.0, step=1.0, format="%.2f", key=f"{form_key}_commission")
                    slippage = adv2[2].number_input("Slippage ($)", min_value=0.0, step=1.0, format="%.2f", key=f"{form_key}_slippage")
                    max_favorable_price = adv2[3].number_input("Max favorable price (MFE)", min_value=0.0, step=0.25, format="%.2f", key=f"{form_key}_mfe")
    
                    adv3 = st.columns(4)
                    max_adverse_price = adv3[0].number_input("Max adverse price (MAE)", min_value=0.0, step=0.25, format="%.2f", key=f"{form_key}_mae")
                    use_pnl_override = adv3[1].checkbox("Use P&L override", value=False, key=f"{form_key}_use_pnl_override")
                    pnl_override = adv3[2].number_input("P&L override ($)", min_value=-1_000_000.0, max_value=1_000_000.0, step=1.0, format="%.2f", key=f"{form_key}_pnl_override")
    
                uploaded_files = st.file_uploader(
                    "Upload trade images (optional)",
                    type=["png", "jpg", "jpeg", "gif"],
                    accept_multiple_files=True,
                    key=f"{form_key}_images",
                )
    
                submitted = st.form_submit_button("Save trade")
    
        if submitted:
            if not enforce_trade_limit_or_warn(user_id):
                # Paywall message already shown; keep rendering the rest of the page.
                submitted = False
            elif entry <= 0 or stop <= 0 or exit_price <= 0:
                st.error("Entry, stop loss, and exit price must be greater than 0.")
            else:
                entry_time_str = entry_time if use_times else None
                exit_time_str = exit_time if use_times else None
                if use_times:
                    custom_entry = normalize_time_input(entry_time_custom)
                    custom_exit = normalize_time_input(exit_time_custom)
                    if entry_time_custom and custom_entry is None:
                        st.error("Entry time must be HH:MM.")
                        return
                    if exit_time_custom and custom_exit is None:
                        st.error("Exit time must be HH:MM.")
                        return
                    if custom_entry:
                        entry_time_str = custom_entry
                    if custom_exit:
                        exit_time_str = custom_exit
    
                tp_value = to_float(take_profit) if take_profit > 0 else None
                max_fav = to_float(max_favorable_price) if max_favorable_price > 0 else None
                max_adv = to_float(max_adverse_price) if max_adverse_price > 0 else None
                account_size_val = to_float(account_size) if account_size > 0 else None
    
                # Upload images to Supabase storage
                saved_image_paths = []
                if uploaded_files:
                    for f in uploaded_files:
                        try:
                            path = upload_image(user_id, f)
                            saved_image_paths.append(path)
                        except Exception as e:
                            st.warning(f"Image upload failed: {e}")
    
                metrics = compute_metrics(
                    instrument=instrument, direction=direction,
                    entry=float(entry), stop=float(stop), exit_price=float(exit_price),
                    take_profit=tp_value, contracts=int(contracts),
                    commission=float(commission), slippage=float(slippage),
                    max_favorable=max_fav, max_adverse=max_adv,
                    account_size=account_size_val,
                    date_str=date_val.strftime("%Y-%m-%d"),
                    entry_time_str=entry_time_str, exit_time_str=exit_time_str,
                )
    
                row = {
                    "id": uuid.uuid4().hex,
                    "date": date_val.strftime("%Y-%m-%d"),
                    "entry_time": entry_time_str,
                    "exit_time": exit_time_str,
                    "instrument": instrument,
                    "direction": direction,
                    "entry_price": round(float(entry), 2),
                    "stop_loss": round(float(stop), 2),
                    "take_profit": round(float(tp_value), 2) if tp_value is not None else None,
                    "exit_price": round(float(exit_price), 2),
                    "contracts": int(contracts),
                    "session": session,
                    "emotion_score": int(emotion),
                    "followed_plan": followed_plan,
                    "revenge_trade": revenge_trade,
                    "setup_tag": setup_tag,
                    "strategy": strategy,
                    "trade_type": (
                        safe_str(other_trade_type).strip()
                        if trade_type == "Other"
                        else (trade_type if trade_type != "Not set" else None)
                    ),
                    "confluences": ",".join(selected_confluences),
                    "market_condition": market_condition if market_condition != "Not set" else None,
                    "trade_grade": trade_grade if trade_grade != "Not set" else None,
                    "account_size": account_size_val,
                    "risk_percent_planned": to_float(risk_percent_planned) if risk_percent_planned > 0 else None,
                    "commission": float(commission),
                    "slippage": float(slippage),
                    "pnl_override": float(pnl_override) if use_pnl_override else None,
                    "max_favorable_price": round(float(max_fav), 2) if max_fav is not None else None,
                    "max_adverse_price": round(float(max_adv), 2) if max_adv is not None else None,
                    "notes": notes,
                    "images": ";".join(saved_image_paths),
                }
                row.update(metrics)
    
                try:
                    save_trade(user_id, account_type, row)
                    st.success("Trade saved!")
                    st.session_state[f"{form_key}_last_saved_id"] = row["id"]
                    df_raw = load_trades(user_id, account_type)
                except Exception as e:
                    st.error(f"Failed to save trade: {e}")
    
    if df_raw.empty:
        if section in ("Dashboard", "Analytics", "PnL Calendar"):
            st.info("No trades yet. Add your first trade above.")
        return

    df = prepare_df(df_raw)

    if section == "New Trade":
        # ── A4 sheet ──────────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("A4 trade sheet (printable)")
        sheet_df = df.sort_values(["date", "entry_time"], ascending=[False, False], na_position="last")
        trade_ids = sheet_df["id"].tolist()
        label_map = {}
        for _, r in sheet_df.iterrows():
            d = r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else safe_str(r["date"])
            t = safe_str(r.get("entry_time"))
            label_map[r["id"]] = f"{d} {t} | {safe_str(r.get('instrument'))} | {safe_str(r.get('direction'))} | {safe_str(r.get('contracts'))}"
    
        last_saved = st.session_state.get(f"{form_key}_last_saved_id")
        default_idx = trade_ids.index(last_saved) if last_saved in trade_ids else 0
        selected_id = st.selectbox("Select trade to print", trade_ids, index=default_idx,
                                    format_func=lambda x: label_map.get(x, x), key=f"{form_key}_a4_id")
        selected_row = sheet_df[sheet_df["id"] == selected_id].iloc[0]
        sheet_html = build_a4_trade_sheet_html(selected_row)
        st.download_button("Download trade sheet HTML (A4)", sheet_html.encode("utf-8"),
                            file_name="trade_sheet.html", mime="text/html", key=f"{form_key}_a4_dl")
        with st.expander("Preview (optional)", expanded=False):
            # The preview is a white A4 page; keep it collapsed by default so it doesn't dominate the dark UI.
            components.html(sheet_html, height=820, scrolling=True)
    
    # ── Dashboard + Analytics + Calendar ─────────────────────────────────────
    if section in ("Dashboard", "Analytics", "PnL Calendar"):
            st.markdown(
                """
            <style>
            :root {
                --tz-bg: var(--background-color);
                --tz-card: var(--secondary-background-color);
                --tz-border: rgba(148, 163, 184, 0.25);
                --tz-muted: rgba(148, 163, 184, 0.95);
                --tz-title: var(--text-color);
                --tz-accent: #7C3AED;
                --tz-accent-2: #3B82F6;
            }
            /* Keep this light: global CSS handles the actual visuals.
               We only keep the variables here for any downstream styling. */
            </style>
            """,
            unsafe_allow_html=True,
        )

    df_view = df.copy()
    df_view.columns = [str(c).strip() for c in df_view.columns]
    show_filters = section in ("Dashboard", "Analytics", "PnL Calendar", "Reports", "Streaks & Milestones")
    if show_filters:
        with st.expander("Filters", expanded=False):
            fp = f"{form_key}_filter_"
            min_date = df_view["date"].min().date()
            max_date = df_view["date"].max().date()
            date_range = st.date_input("Date range", (min_date, max_date), key=f"{fp}date")
            start_date, end_date = (date_range if isinstance(date_range, (tuple, list)) and len(date_range) == 2
                                    else (date_range, date_range))
            instrument_filter = st.multiselect("Instrument", INSTRUMENT_ORDER, default=INSTRUMENT_ORDER, key=f"{fp}instrument")
            session_filter = st.multiselect("Session", SESSIONS, default=SESSIONS, key=f"{fp}session")
            direction_filter = st.multiselect("Direction", ["Long", "Short"], default=["Long", "Short"], key=f"{fp}direction")

        pnl_view = st.radio("PnL view", ["Net (after fees)", "Gross"], horizontal=True, key=f"{form_key}_pnl_view")
    else:
        min_date = df_view["date"].min().date()
        max_date = df_view["date"].max().date()
        start_date, end_date = min_date, max_date
        instrument_filter = INSTRUMENT_ORDER
        session_filter = SESSIONS
        direction_filter = ["Long", "Short"]
        pnl_view = "Net (after fees)"

    df_view = df_view[
        (df_view["date"] >= pd.to_datetime(start_date))
        & (df_view["date"] <= pd.to_datetime(end_date))
        & (df_view["instrument"].isin(instrument_filter))
        & (df_view["session"].isin(session_filter))
        & (df_view["direction"].isin(direction_filter))
    ]

    pnl_col = "pnl_net" if pnl_view.startswith("Net") else "pnl_gross"
    if pnl_col not in df_view.columns:
        df_view[pnl_col] = 0
    df_view[pnl_col] = pd.to_numeric(df_view[pnl_col], errors="coerce").fillna(0)

    if "pnl_override" in df_view.columns:
        df_view["pnl_override"] = pd.to_numeric(df_view["pnl_override"], errors="coerce")
        df_view["pnl_effective"] = df_view["pnl_override"].where(df_view["pnl_override"].notna(), df_view[pnl_col])
        pnl_col = "pnl_effective"
    else:
        df_view["pnl_effective"] = df_view[pnl_col]

    total_trades = len(df_view)
    if total_trades == 0:
        if section in ("Dashboard", "Analytics", "PnL Calendar", "Reports", "Streaks & Milestones"):
            st.info("No trades match your filters.")
        return

    wins_df = df_view[df_view[pnl_col] > 0]
    losses_df = df_view[df_view[pnl_col] < 0]
    wins = len(wins_df)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    avg_r = df_view["r_multiple"].dropna().mean() if "r_multiple" in df_view.columns else None
    total_pnl = df_view[pnl_col].sum()
    avg_win = wins_df[pnl_col].mean() if wins > 0 else 0
    avg_loss = losses_df[pnl_col].mean() if len(losses_df) > 0 else 0
    loss_sum = losses_df[pnl_col].sum() if len(losses_df) > 0 else 0
    profit_factor = wins_df[pnl_col].sum() / abs(loss_sum) if loss_sum != 0 else None
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss) if total_trades > 0 else 0
    largest_win = df_view[pnl_col].max()
    largest_loss = df_view[pnl_col].min()
    avg_duration = df_view["duration_minutes"].dropna().mean() if "duration_minutes" in df_view.columns else None
    plan_rate = (df_view["followed_plan"] == "Yes").mean() * 100 if "followed_plan" in df_view.columns else 0
    revenge_rate = (df_view["revenge_trade"] == "Yes").mean() * 100 if "revenge_trade" in df_view.columns else 0

    cards = [
        ("Total trades", total_trades, None),
        ("Win rate", f"{win_rate:.1f}%", f"Wins: {wins}"),
        ("Average R", f"{avg_r:.2f}" if avg_r is not None else "n/a", None),
        ("Total PnL", format_money(total_pnl), pnl_view),
        ("Avg win", format_money(avg_win), None),
        ("Avg loss", format_money(avg_loss), None),
        ("Profit factor", f"{profit_factor:.2f}" if profit_factor is not None else "n/a", None),
        ("Expectancy", format_money(expectancy), None),
        ("Largest win", format_money(largest_win), None),
        ("Largest loss", format_money(largest_loss), None),
        ("Avg duration", f"{avg_duration:.1f} min" if avg_duration is not None else "n/a", None),
        ("Plan adherence", f"{plan_rate:.1f}%", f"Revenge: {revenge_rate:.1f}%"),
    ]

    chart_df = df_view.sort_values("date").copy()
    # Normalize to day granularity for smoother curves and correct daily aggregation.
    chart_df["date"] = pd.to_datetime(chart_df["date"]).dt.normalize()
    chart_df["equity"] = chart_df[pnl_col].cumsum()
    chart_df["peak"] = chart_df["equity"].cummax()
    chart_df["drawdown"] = chart_df["equity"] - chart_df["peak"]
    chart_df["day"] = chart_df["date"].dt.day_name()
    chart_df["month"] = chart_df["date"].dt.to_period("M").astype(str)

    daily_df = chart_df.groupby("date", as_index=False)[pnl_col].sum().rename(columns={pnl_col: "pnl"})
    daily_df = daily_df.sort_values("date").copy()
    daily_df["equity"] = daily_df["pnl"].cumsum()
    daily_df["equity_smooth"] = daily_df["equity"].rolling(5, min_periods=1).mean()
    daily_df["peak"] = daily_df["equity"].cummax()
    daily_df["drawdown"] = daily_df["equity"] - daily_df["peak"]
    instrument_df = chart_df.groupby("instrument", as_index=False)[pnl_col].sum().rename(columns={pnl_col: "pnl"})
    instrument_df["instrument"] = pd.Categorical(instrument_df["instrument"], categories=INSTRUMENT_ORDER, ordered=True)
    instrument_df = instrument_df.sort_values("instrument")
    session_df = chart_df.groupby("session", as_index=False)[pnl_col].sum().rename(columns={pnl_col: "pnl"})
    session_df["session"] = pd.Categorical(session_df["session"], categories=SESSIONS, ordered=True)
    session_df = session_df.sort_values("session")

    # ── Reports / Streaks (keep fast: run before building charts) ────────────
    if section == "Reports":
        render_reports_page(df_view, pnl_col, account_type)
        return
    if section == "Streaks & Milestones":
        render_streaks_page(df_view, pnl_col)
        return

    equity_chart = (
        alt.Chart(daily_df)
        .mark_area(
            interpolate="monotone",
            line={"color": "#7C3AED", "strokeWidth": 2},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="rgba(124, 58, 237, 0.35)", offset=0),
                    alt.GradientStop(color="rgba(59, 130, 246, 0.02)", offset=1),
                ],
                x1=1,
                x2=1,
                y1=1,
                y2=0,
            ),
        )
        .encode(
            x=alt.X("date:T", axis=alt.Axis(title=None, format="%b %d")),
            y=alt.Y("equity_smooth:Q", axis=alt.Axis(title=None), scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("equity:Q", title="Equity", format=",.2f"),
                alt.Tooltip("pnl:Q", title="Daily PnL", format=",.2f"),
            ],
        )
        .properties(height=280)
    )

    daily_chart = (
        alt.Chart(daily_df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("date:T", axis=alt.Axis(title=None, format="%b %d")),
            y=alt.Y("pnl:Q", axis=alt.Axis(title=None), scale=alt.Scale(zero=False)),
            color=alt.condition(alt.datum.pnl >= 0, alt.value("#22c55e"), alt.value("#ef4444")),
            tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("pnl:Q", title="PnL", format=",.2f")],
        )
        .properties(height=280)
    )

    instr_chart = (
        alt.Chart(instrument_df)
        .mark_bar()
        .encode(
            y=alt.Y("instrument:N", sort=INSTRUMENT_ORDER, axis=alt.Axis(title=None)),
            x=alt.X("pnl:Q", axis=alt.Axis(title=None)),
            color=alt.value("#8FC9FF"),
            tooltip=[alt.Tooltip("instrument:N", title="Instrument"), alt.Tooltip("pnl:Q", title="PnL", format=",.2f")],
        )
        .properties(height=220)
    )

    session_chart = (
        alt.Chart(session_df)
        .mark_bar()
        .encode(
            y=alt.Y("session:N", sort=SESSIONS, axis=alt.Axis(title=None)),
            x=alt.X("pnl:Q", axis=alt.Axis(title=None)),
            color=alt.value("#8FC9FF"),
            tooltip=[alt.Tooltip("session:N", title="Session"), alt.Tooltip("pnl:Q", title="PnL", format=",.2f")],
        )
        .properties(height=220)
    )

    drawdown_chart = (
        alt.Chart(daily_df)
        .mark_area(
            line={"color": "#ef4444", "strokeWidth": 1.5},
            color="rgba(239, 68, 68, 0.18)",
        )
        .encode(
            x=alt.X("date:T", axis=alt.Axis(title=None, format="%b %d")),
            y=alt.Y("drawdown:Q", axis=alt.Axis(title=None), scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("drawdown:Q", title="Drawdown", format=",.2f")],
        )
        .properties(height=200)
    )

    if section == "Dashboard":
        st.subheader("Dashboard")
        render_metric_cards(cards)

        c_score, c_recent = st.columns([1.2, 1])
        with c_score:
            st.markdown("**Zylo score**")
            zylo = compute_zylo_score(df_view, daily_df, pnl_col)
            score = float(zylo["overall"])
            st.markdown(f"**{score:.2f}** / 100")
            try:
                st.progress(min(1.0, max(0.0, score / 100.0)))
            except Exception:
                pass
            render_zylo_radar(zylo["components"])

        with c_recent:
            st.markdown("**Recent trades**")
            recent = (
                df_view.sort_values(["date", "entry_time"], ascending=[False, False], na_position="last")
                .head(10)
                .copy()
            )
            recent["Date"] = recent["date"].dt.strftime("%Y-%m-%d")
            recent["PnL"] = recent[pnl_col].apply(format_money)
            show_cols = []
            for col in ("Date", "instrument", "direction", "contracts", "session", "trade_grade", "PnL"):
                if col in recent.columns:
                    show_cols.append(col)
            if show_cols:
                st.dataframe(
                    recent[show_cols].rename(columns={"instrument": "Instrument", "direction": "Dir", "contracts": "Size", "session": "Session", "trade_grade": "Grade"}),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No trades yet.")

        c_eq, c_daily = st.columns([2, 1])
        with c_eq:
            st.markdown("**Equity curve**")
            st.altair_chart(style_altair_chart(equity_chart), use_container_width=True)
        with c_daily:
            st.markdown("**Daily P&L**")
            st.altair_chart(style_altair_chart(daily_chart), use_container_width=True)

        st.markdown("**Performance by instrument & session**")
        c1, c2 = st.columns(2)
        with c1:
            st.altair_chart(style_altair_chart(instr_chart), use_container_width=True)
        with c2:
            st.altair_chart(style_altair_chart(session_chart), use_container_width=True)

        st.markdown("---")
        st.subheader("Drawdown")
        st.altair_chart(style_altair_chart(drawdown_chart), use_container_width=True)

    if section == "PnL Calendar":
        st.subheader("PnL calendar")
        if not daily_df.empty:
            best_row = daily_df.loc[daily_df["pnl"].idxmax()]
            worst_row = daily_df.loc[daily_df["pnl"].idxmin()]
            best_date = best_row["date"].strftime("%Y-%m-%d")
            worst_date = worst_row["date"].strftime("%Y-%m-%d")
            st.markdown(f"**Biggest winning day:** {best_date} — {format_money(best_row['pnl'])}")
            st.markdown(f"**Biggest losing day:** {worst_date} — {format_money(worst_row['pnl'])}")
        render_pnl_calendar(chart_df, pnl_col)

        # Weekly details (click a week on the right)
        week_map = st.session_state.get("calendar_week_date_map") or {}
        week_clicked = get_query_param("week").strip()
        week_keys = list(week_map.keys())
        if week_keys:
            default_week = week_clicked if week_clicked in week_keys else week_keys[0]
            selected_week = st.selectbox("Select week", week_keys, index=week_keys.index(default_week), key=f"{form_key}_week_select")
            week_dates = week_map.get(selected_week, [])
            week_trades_df = chart_df[chart_df["date"].dt.strftime("%Y-%m-%d").isin(week_dates)].copy()
            if week_trades_df.empty:
                st.info("No trades in this week.")
            else:
                avg_rr = week_trades_df["r_multiple"].dropna().mean() if "r_multiple" in week_trades_df.columns else None
                wins_w = week_trades_df[week_trades_df[pnl_col] > 0][pnl_col].sum()
                losses_w = week_trades_df[week_trades_df[pnl_col] < 0][pnl_col].sum()
                pf_w = (wins_w / abs(losses_w)) if losses_w != 0 else None
                cards_w = [
                    ("Week PnL", format_money(float(week_trades_df[pnl_col].sum())), None),
                    ("Avg RR", f"{float(avg_rr):.2f}" if avg_rr is not None and pd.notna(avg_rr) else "n/a", None),
                    ("Profit factor", f"{float(pf_w):.2f}" if pf_w is not None else "n/a", None),
                ]
                render_metric_cards(cards_w)

        # Day details (click a day on the calendar or pick below)
        st.markdown("---")
        st.markdown("**Day details**")
        clicked = get_query_param("day").strip()
        available_days = sorted({d.strftime("%Y-%m-%d") for d in pd.to_datetime(chart_df["date"]).dt.date})
        default_day = clicked if clicked in available_days else (available_days[-1] if available_days else "")
        selected_day = st.selectbox("Select day", available_days, index=(available_days.index(default_day) if default_day in available_days else 0))

        day_dt = pd.to_datetime(selected_day).date() if selected_day else None
        if day_dt is not None:
            day_trades = chart_df[chart_df["date"].dt.date == day_dt].copy()
            if day_trades.empty:
                st.info("No trades on this day.")
            else:
                day_total = float(day_trades[pnl_col].sum())
                day_wins = int((day_trades[pnl_col] > 0).sum())
                st.markdown(f"**Total PnL:** {format_money(day_total)} · **Trades:** {len(day_trades)} · **Wins:** {day_wins}")

                # Journal notes for the day (if available)
                j = load_journal_entry(user_id, selected_day)
                if j is not None and j.strip():
                    with st.expander("Journal notes", expanded=False):
                        st.write(j)

                # Trade cards / table
                cols = ["entry_time", "instrument", "direction", "contracts", "session", "trade_grade", "r_multiple", pnl_col, "notes"]
                show = [c for c in cols if c in day_trades.columns]
                view = day_trades.sort_values(["entry_time"], ascending=True, na_position="last").copy()
                if "r_multiple" in view.columns:
                    view["r_multiple"] = pd.to_numeric(view["r_multiple"], errors="coerce").round(2)
                view["PnL"] = view[pnl_col].apply(format_money)
                rename = {
                    "entry_time": "Time",
                    "instrument": "Instrument",
                    "direction": "Side",
                    "contracts": "Size",
                    "session": "Session",
                    "trade_grade": "Grade",
                    "r_multiple": "RR",
                    "notes": "Notes",
                }
                out_cols = []
                for c in show:
                    if c == pnl_col:
                        continue
                    out_cols.append(c)
                df_out = view[out_cols + ["PnL"]].rename(columns=rename)
                st.dataframe(df_out, use_container_width=True, hide_index=True)

                # Images (if any)
                images = []
                for _, r in day_trades.iterrows():
                    imgs = safe_str(r.get("images", ""))
                    for p in imgs.split(";"):
                        if p.strip():
                            images.append((p.strip(), r))
                if images:
                    st.markdown("**Screenshots**")
                    img_cols = st.columns(3)
                    for i, (path, r) in enumerate(images[:12]):
                        try:
                            url = get_image_url(path)
                            cap = f"{safe_str(r.get('instrument'))} {safe_str(r.get('direction'))} {safe_str(r.get('entry_time'))}"
                            img_cols[i % 3].image(url, caption=cap, use_column_width=True)
                        except Exception:
                            img_cols[i % 3].warning("Could not load image")

    if section == "Analytics":
        st.subheader("Analytics")
        a_day, a_conf, a_overall = st.tabs(
            ["Day & Time Analysis", "Confluence Analytics", "Overall Performance"]
        )

        with a_day:
            day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            day_perf = (
                chart_df.groupby("day")[pnl_col]
                .agg(["sum", "mean", "count"])
                .rename(columns={"sum": "Total PnL", "mean": "Avg PnL", "count": "Trades"})
            )
            day_perf["Win rate %"] = chart_df.groupby("day")[pnl_col].apply(lambda s: (s > 0).mean() * 100)
            day_perf = day_perf.reindex(day_order)

            hour_df = chart_df.dropna(subset=["entry_hour"])
            hour_perf = (
                hour_df.groupby("entry_hour")[pnl_col]
                .agg(["sum", "mean", "count"])
                .rename(columns={"sum": "Total PnL", "mean": "Avg PnL", "count": "Trades"})
            )
            hour_perf["Win rate %"] = hour_df.groupby("entry_hour")[pnl_col].apply(lambda s: (s > 0).mean() * 100)

            time_cards = []
            if not day_perf.empty and day_perf["Trades"].sum() > 0:
                best_day = day_perf["Total PnL"].idxmax()
                worst_day = day_perf["Total PnL"].idxmin()
                time_cards.extend([
                    ("Best day", str(best_day), f"{format_money(day_perf.loc[best_day, 'Total PnL'])} | {day_perf.loc[best_day, 'Win rate %']:.1f}% win"),
                    ("Worst day", str(worst_day), f"{format_money(day_perf.loc[worst_day, 'Total PnL'])} | {day_perf.loc[worst_day, 'Win rate %']:.1f}% win"),
                ])
            if not hour_perf.empty:
                best_hour = hour_perf["Total PnL"].idxmax()
                worst_hour = hour_perf["Total PnL"].idxmin()
                time_cards.extend([
                    ("Best hour", f"{int(best_hour):02d}:00", f"{format_money(hour_perf.loc[best_hour, 'Total PnL'])} | {hour_perf.loc[best_hour, 'Win rate %']:.1f}% win"),
                    ("Worst hour", f"{int(worst_hour):02d}:00", f"{format_money(hour_perf.loc[worst_hour, 'Total PnL'])} | {hour_perf.loc[worst_hour, 'Win rate %']:.1f}% win"),
                ])

            if time_cards:
                render_metric_cards(time_cards)
            else:
                st.info("No time/day data yet.")

            day_display = day_perf.reset_index().rename(columns={"day": "Day"})
            hour_display = hour_perf.reset_index().rename(columns={"entry_hour": "Hour"})
            if not hour_display.empty:
                hour_display["Hour"] = hour_display["Hour"].apply(lambda h: f"{int(h):02d}:00")
            for df_perf in (day_display, hour_display):
                if not df_perf.empty:
                    df_perf["Total PnL"] = df_perf["Total PnL"].round(2)
                    df_perf["Avg PnL"] = df_perf["Avg PnL"].round(2)
                    df_perf["Win rate %"] = df_perf["Win rate %"].round(1)
                    df_perf["Trades"] = df_perf["Trades"].fillna(0).astype(int)

            c_day, c_hour = st.columns(2)
            with c_day:
                st.markdown("**Day of week breakdown**")
                st.dataframe(day_display, use_container_width=True, hide_index=True)
            with c_hour:
                st.markdown("**Hour breakdown**")
                st.dataframe(hour_display, use_container_width=True, hide_index=True)

        with a_conf:
            conf_df = explode_tags(chart_df, "confluences")
            if conf_df.empty:
                st.info("No confluence data yet.")
            else:
                conf_stats = (
                    conf_df.groupby("confluences")[pnl_col]
                    .agg(["sum", "mean", "count"])
                    .rename(columns={"sum": "Total PnL", "mean": "Avg PnL", "count": "Trades"})
                )
                conf_stats["Win rate %"] = conf_df.groupby("confluences")[pnl_col].apply(lambda s: (s > 0).mean() * 100)
                conf_stats = conf_stats.sort_values("Win rate %", ascending=False)
                conf_stats = conf_stats[conf_stats["Trades"] >= 2]
                if conf_stats.empty:
                    st.info("Not enough confluence data yet.")
                else:
                    top_win = conf_stats.head(3).copy()
                    top_loss = conf_stats.sort_values("Win rate %", ascending=True).head(3).copy()
                    for df_stats in (top_win, top_loss):
                        df_stats["Total PnL"] = df_stats["Total PnL"].round(2)
                        df_stats["Avg PnL"] = df_stats["Avg PnL"].round(2)
                        df_stats["Win rate %"] = df_stats["Win rate %"].round(1)
                        df_stats["Trades"] = df_stats["Trades"].astype(int)

                    c_top, c_bot = st.columns(2)
                    with c_top:
                        st.markdown("**Top 3 win rate confluences**")
                        st.dataframe(top_win, use_container_width=True)
                    with c_bot:
                        st.markdown("**Top 3 lose rate confluences**")
                        st.dataframe(top_loss, use_container_width=True)

        with a_overall:
            st.markdown("**Highlights**")

            # Most profitable month
            month_perf = chart_df.groupby("month")[pnl_col].sum().sort_values(ascending=False)
            best_month = safe_str(month_perf.index[0]) if not month_perf.empty else ""
            best_month_pnl = float(month_perf.iloc[0]) if not month_perf.empty else 0.0

            # Most profitable R-multiple band
            rr_best_label = ""
            rr_best_pnl = 0.0
            rr_df = chart_df.dropna(subset=["r_multiple"]).copy()
            if not rr_df.empty:
                rr_df["r_bucket"] = pd.cut(
                    rr_df["r_multiple"],
                    bins=[-1e9, -2, -1, 0, 1, 2, 3, 1e9],
                    labels=["<= -2R", "-2R to -1R", "-1R to 0R", "0R to 1R", "1R to 2R", "2R to 3R", ">= 3R"],
                )
                rr_perf = rr_df.groupby("r_bucket")[pnl_col].sum().sort_values(ascending=False)
                if not rr_perf.empty:
                    rr_best_label = safe_str(rr_perf.index[0])
                    rr_best_pnl = float(rr_perf.iloc[0])

            hi_cards = []
            if best_month:
                hi_cards.append(("Best month", best_month, format_money(best_month_pnl)))
            if rr_best_label:
                hi_cards.append(("Best RR band", rr_best_label, format_money(rr_best_pnl)))
            if hi_cards:
                render_metric_cards(hi_cards)
            else:
                st.info("Not enough data yet for monthly/RR highlights.")

            st.markdown("---")

            context_df = chart_df.copy()
            context_df["time_label"] = context_df["entry_time"].fillna(
                context_df["entry_hour"].apply(lambda h: f"{int(h):02d}:00" if pd.notna(h) else "n/a")
            )
            context_df["confluence_combo"] = context_df["confluences"].apply(
                lambda raw: " + ".join(sorted({t.strip() for t in str(raw or "").split(",") if t.strip()})) or "No confluence"
            )
            context_stats = (
                context_df.groupby(["day", "time_label", "direction", "confluence_combo"])[pnl_col]
                .agg(["sum", "mean", "count"])
                .rename(columns={"sum": "Total PnL", "mean": "Avg PnL", "count": "Trades"})
            )
            context_stats["Win rate %"] = context_df.groupby(
                ["day", "time_label", "direction", "confluence_combo"]
            )[pnl_col].apply(lambda s: (s > 0).mean() * 100)
            context_stats = context_stats[context_stats["Trades"] >= 2]

            if not context_stats.empty:
                best_win = context_stats.sort_values(["Win rate %", "Total PnL"], ascending=[False, False]).iloc[0]
                best_pnl = context_stats.sort_values("Total PnL", ascending=False).iloc[0]
                best_win_label = f"{best_win.name[0]} at {best_win.name[1]} going {best_win.name[2]} with {best_win.name[3]}"
                best_pnl_label = f"{best_pnl.name[0]} at {best_pnl.name[1]} going {best_pnl.name[2]} with {best_pnl.name[3]}"
                st.markdown(
                    f"**Best win rate context:** {best_win_label} "
                    f"({best_win['Win rate %']:.1f}% win, {int(best_win['Trades'])} trades, {format_money(best_win['Total PnL'])})"
                )
                st.markdown(
                    f"**Best total PnL context:** {best_pnl_label} "
                    f"({int(best_pnl['Trades'])} trades, {format_money(best_pnl['Total PnL'])})"
                )
            else:
                st.info("Not enough combined data yet for context analysis.")

            st.markdown("---")
            st.markdown("**Top setup tags**")
            tag_df = explode_tags(chart_df, "setup_tag")
            if not tag_df.empty:
                tag_stats = (
                    tag_df.groupby("setup_tag")[pnl_col]
                    .agg(["sum", "mean", "count"])
                    .rename(columns={"sum": "Total PnL", "mean": "Avg PnL", "count": "Trades"})
                    .sort_values("Total PnL", ascending=False)
                )
                st.dataframe(tag_stats.head(5), use_container_width=True)
            else:
                st.info("No setup tag data yet.")

            st.markdown("**Top confluence combos**")
            combo_stats = build_confluence_combo_stats(chart_df, pnl_col, min_confluences=2)
            if not combo_stats.empty:
                combo_stats = combo_stats[combo_stats["Trades"] >= 2]
            if combo_stats.empty:
                st.info("No confluence combo data yet.")
            else:
                combo_stats["Total PnL"] = combo_stats["Total PnL"].round(2)
                combo_stats["Avg PnL"] = combo_stats["Avg PnL"].round(2)
                combo_stats["Win rate %"] = combo_stats["Win rate %"].round(1)
                combo_stats["Trades"] = combo_stats["Trades"].astype(int)

                best_win = combo_stats.sort_values(["Win rate %", "Total PnL"], ascending=[False, False]).head(3)
                worst_win = combo_stats.sort_values(["Win rate %", "Total PnL"], ascending=[True, True]).head(3)
                top_pnl = combo_stats.sort_values("Total PnL", ascending=False).head(3)

                c_best, c_worst = st.columns(2)
                with c_best:
                    st.markdown("**Best win rate combos**")
                    st.dataframe(best_win, use_container_width=True)
                with c_worst:
                    st.markdown("**Worst win rate combos**")
                    st.dataframe(worst_win, use_container_width=True)

                st.markdown("**Top PnL combos**")
                st.dataframe(top_pnl, use_container_width=True)

    if section == "New Trade":
        # ── Trade images ──────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("Trade images")
        image_paths = []
        for _, row in df_view.iterrows():
            imgs = safe_str(row.get("images", ""))
            for p in imgs.split(";"):
                if p.strip():
                    image_paths.append((p.strip(), f"{safe_str(row.get('date'))} | {safe_str(row.get('instrument'))} | {safe_str(row.get('direction'))}"))

        if not image_paths:
            st.info("No images uploaded yet.")
        else:
            st.caption(f"Showing latest 12 of {len(image_paths)} images")
            cols = st.columns(4)
            for i, (path, caption) in enumerate(image_paths[-12:]):
                try:
                    url = get_image_url(path)
                    cols[i % 4].image(url, caption=caption, use_column_width=True)
                except Exception:
                    cols[i % 4].warning(f"Could not load image")

        # ── All trades table ──────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("All trades")
        st.dataframe(df_view, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", df_view.to_csv(index=False).encode("utf-8"),
                            file_name=f"{form_key}_trades.csv", mime="text/csv", key=f"{form_key}_dl")

        # ── Edit / delete ─────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("Edit or delete trades")
        editable = df_raw.copy()
        editable["delete"] = False
        edited = st.data_editor(editable, disabled=COMPUTED_COLUMNS + ["id", "images"],
                                 use_container_width=True, hide_index=True, key=f"{form_key}_editor")
        if st.button("Apply edits and deletions", key=f"{form_key}_apply"):
            to_delete = edited[edited["delete"] == True]["id"].tolist()
            for tid in to_delete:
                delete_trade(tid)
            to_update = edited[edited["delete"] != True].drop(columns=["delete"])
            for _, r in to_update.iterrows():
                row_dict = r.to_dict()
                if "entry_time" in row_dict:
                    row_dict["entry_time"] = normalize_time_input(row_dict["entry_time"])
                if "exit_time" in row_dict:
                    row_dict["exit_time"] = normalize_time_input(row_dict["exit_time"])
                metrics = compute_metrics(
                    instrument=normalize_instrument(row_dict.get("instrument")),
                    direction=normalize_direction(row_dict.get("direction")),
                    entry=to_float(row_dict.get("entry_price")),
                    stop=to_float(row_dict.get("stop_loss")),
                    exit_price=to_float(row_dict.get("exit_price")),
                    take_profit=to_float(row_dict.get("take_profit")),
                    contracts=to_int(row_dict.get("contracts")),
                    commission=to_float(row_dict.get("commission")),
                    slippage=to_float(row_dict.get("slippage")),
                    max_favorable=to_float(row_dict.get("max_favorable_price")),
                    max_adverse=to_float(row_dict.get("max_adverse_price")),
                    account_size=to_float(row_dict.get("account_size")),
                    date_str=row_dict.get("date"),
                    entry_time_str=row_dict.get("entry_time"),
                    exit_time_str=row_dict.get("exit_time"),
                )
                row_dict.update(metrics)
                update_trade(row_dict)
            st.success("Changes saved. Refresh to see updated data.")

# ── App entry point ───────────────────────────────────────────────────────────

user = get_user()

if not user:
    render_public_router()
else:
    maybe_record_referral(user.id)
    apply_settings_to_session(user.id)
    render_brand_header(center=False, hero=True)

    section_options = [
        "Dashboard",
        "New Trade",
        "Analytics",
        "PnL Calendar",
        "Reports",
        "Streaks & Milestones",
        "Journal",
        "Strategy/Model Creation",
        "Affiliates",
    ]

    # Keep a single source of truth for navigation to avoid "jumping" between widgets.
    def _sync_nav_from_top() -> None:
        st.session_state["nav_section"] = st.session_state.get("top_nav_section", section_options[0])
        st.session_state["sidebar_nav_section"] = st.session_state["nav_section"]

    def _sync_nav_from_sidebar() -> None:
        st.session_state["nav_section"] = st.session_state.get("sidebar_nav_section", section_options[0])
        st.session_state["top_nav_section"] = st.session_state["nav_section"]

    def _request_nav(section_name: str) -> None:
        """
        Request navigation to a section on the *next* rerun.
        We can't set widget-backed keys (like top_nav_section) after the widget is created
        in the same run, otherwise Streamlit raises StreamlitAPIException.
        """
        st.session_state["_nav_request"] = section_name
        st.rerun()

    # Query param can deep-link to a section (used by some Stripe URLs).
    section_param = get_query_param("section").strip()
    if "nav_section" not in st.session_state:
        st.session_state["nav_section"] = section_param if section_param in section_options else section_options[0]
    if section_param and section_param in section_options:
        st.session_state["nav_section"] = section_param

    # Apply any pending navigation request *before* we create navigation widgets.
    pending = safe_str(st.session_state.pop("_nav_request", "")).strip()
    if pending and pending in section_options:
        st.session_state["nav_section"] = pending
        st.session_state["top_nav_section"] = pending
        st.session_state["sidebar_nav_section"] = pending

    # Initialize widget keys to the canonical nav value.
    if "top_nav_section" not in st.session_state:
        st.session_state["top_nav_section"] = st.session_state["nav_section"]
    if "sidebar_nav_section" not in st.session_state:
        st.session_state["sidebar_nav_section"] = st.session_state["nav_section"]

    # Mobile-friendly navigation fallback (sidebar can be hidden/collapsed on small screens).
    nav_cols = st.columns([3, 2, 2])
    with nav_cols[0]:
        st.caption("Navigation")
    with nav_cols[1]:
        top_add = st.button("+ Add Trade", type="primary", use_container_width=True, key="top_add_trade")
    with nav_cols[2]:
        st.selectbox(
            "Go to",
            section_options,
            label_visibility="collapsed",
            key="top_nav_section",
            on_change=_sync_nav_from_top,
        )
    if top_add:
        _request_nav("New Trade")

    with st.sidebar:
        st.markdown("### Navigation")
        add_trade = st.button("+ Add Trade", type="primary", use_container_width=True, key="sidebar_add_trade")
        if add_trade:
            _request_nav("New Trade")

        st.radio(
            "Go to",
            section_options,
            key="sidebar_nav_section",
            label_visibility="collapsed",
            on_change=_sync_nav_from_sidebar,
        )

        with st.expander("Settings", expanded=False):
            labels = list(CURRENCY_CHOICES.keys())
            code_to_label = {v["code"]: k for k, v in CURRENCY_CHOICES.items()}
            default_label = code_to_label.get(safe_str(st.session_state.get("currency_code")), labels[0])
            if "currency_choice" not in st.session_state:
                st.session_state["currency_choice"] = default_label

            choice = st.selectbox("Currency", labels, key="currency_choice")
            sym = CURRENCY_CHOICES[choice]["symbol"]
            code = CURRENCY_CHOICES[choice]["code"]
            st.session_state["currency_symbol"] = sym
            st.session_state["currency_code"] = code

            last = st.session_state.get("_settings_last_currency")
            current = f"{code}:{sym}"
            if last != current:
                ok = upsert_user_settings(user.id, {"currency_code": code, "currency_symbol": sym})
                st.session_state["_settings_last_currency"] = current
                if not ok:
                    st.caption("Settings storage isn't set up yet. Run `sql/user_settings.sql` in Supabase to persist.")

            st.markdown("---")
            st.markdown("**Support**")
            if SUPPORT_CONTACT_EMAIL:
                st.caption(f"Email: {SUPPORT_CONTACT_EMAIL}")
            with st.form("support_form", clear_on_submit=True):
                support_email = st.text_input("Your email", value=safe_str(getattr(user, "email", "")), key="support_email")
                subject = st.text_input("Subject", placeholder="What do you need help with?", key="support_subject")
                message = st.text_area("Message", placeholder="Describe the issue (what you clicked, what happened, any error).", height=120, key="support_message")
                sent = st.form_submit_button("Send support request")
            if sent:
                ok = insert_support_request(user.id, support_email, subject, message, section)
                if ok:
                    st.success("Sent. We'll get back to you soon.")
                else:
                    st.warning("Support storage isn't set up yet. Run the support SQL in Supabase, or contact support by email.")

            st.markdown("---")
            st.markdown("**Suggestions**")
            with st.form("suggestions_form", clear_on_submit=True):
                sug_email = st.text_input("Your email", value=safe_str(getattr(user, "email", "")), key="sug_email")
                title = st.text_input("Title", placeholder="Short idea name", key="sug_title")
                suggestion = st.text_area("Suggestion", placeholder="What should we add/change?", height=120, key="sug_body")
                sug_sent = st.form_submit_button("Submit suggestion")
            if sug_sent:
                ok = insert_suggestion(user.id, sug_email, title, suggestion)
                if ok:
                    st.success("Thanks — suggestion submitted!")
                else:
                    st.warning("Suggestions storage isn't set up yet. Run the suggestions SQL in Supabase.")

            # Admin: payouts runner (safer than terminal; defaults to dry-run).
            if is_admin_email(safe_str(getattr(user, "email", ""))):
                st.markdown("---")
                st.markdown("**Admin: Affiliate Payouts**")
                dry = st.toggle("Dry run (recommended)", value=True, key="admin_payouts_dry")
                if not dry:
                    st.warning("Live payouts will attempt Stripe transfers. Only switch this on when live Stripe is ready.")
                colx, coly = st.columns([1, 1])
                with colx:
                    if st.button("Create test commission", use_container_width=True, key="admin_make_test_commission"):
                        ok, msg = admin_create_test_commission(user.id, amount_cents=1900, pct=20)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(f"Could not create test commission: {msg}")
                    st.caption("Creates a pending commission row (for testing only).")
                with coly:
                    st.markdown(" ")
                    st.markdown(" ")
                if st.button("Run payouts now", use_container_width=True, key="admin_run_payouts"):
                    ok, body = invoke_edge_function("affiliate-payouts", {"dry_run": bool(dry)})
                    if ok:
                        st.code(body, language="json")
                    else:
                        st.error(f"Payout run failed: {body}")

                st.markdown("---")
                st.markdown("**Admin: Affiliate Promo Window**")
                ok_cfg, cfg = admin_get_billing_config()
                if ok_cfg and cfg:
                    st.caption(
                        "Current window: "
                        f"{safe_str(cfg.get('affiliate_promo_start_at') or 'not set')} → "
                        f"{safe_str(cfg.get('affiliate_promo_end_at') or 'not set')}"
                    )
                    st.caption(
                        f"Promo %: {safe_str(cfg.get('promo_commission_percent') or 30)} • "
                        f"Default %: {safe_str(cfg.get('default_commission_percent') or 20)}"
                    )
                elif ok_cfg:
                    st.caption("Promo window: not set yet.")
                else:
                    st.caption(f"Promo window status: {safe_str(cfg.get('error') or '')}")

                if st.button("Start 30-day promo (30% then 20%)", use_container_width=True, key="admin_start_aff_promo"):
                    ok, msg = admin_start_affiliate_promo_window(days=30, promo_pct=30.0, default_pct=20.0)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(
                            f"Could not start promo window: {msg}\n\n"
                            "Make sure you ran `sql/billing_config.sql` in the SAME Supabase project."
                        )

                st.markdown("---")
                st.markdown("**Admin: Stripe Test Checkout Links**")
                st.caption("Creates real Stripe Checkout Sessions using your `STRIPE_SECRET_KEY` (use test keys while testing).")
                # Show detected price ids (helps prevent secret typos).
                detected = {
                    "monthly": bool(_stripe_price_id_for_plan("monthly")),
                    "quarterly": bool(_stripe_price_id_for_plan("quarterly")),
                    "yearly": bool(_stripe_price_id_for_plan("yearly")),
                }
                st.caption(
                    "Price IDs set: "
                    f"monthly={detected['monthly']} • quarterly={detected['quarterly']} • yearly={detected['yearly']}"
                )
                plan = st.selectbox(
                    "Plan",
                    ["monthly", "quarterly", "yearly"],
                    index=0,
                    key="admin_stripe_plan",
                    help="Uses STRIPE_PRICE_ID_MONTHLY / QUARTERLY / YEARLY (monthly falls back to STRIPE_PRICE_ID).",
                )
                if st.button("Create Checkout Link", use_container_width=True, key="admin_create_checkout"):
                    user_obj = st.session_state.get("user")
                    email_val = (
                        safe_str(user_obj.get("email"))
                        if isinstance(user_obj, dict)
                        else safe_str(getattr(user_obj, "email", ""))
                    )
                    url = create_stripe_checkout_session(
                        user.id,
                        email_val,
                        plan=plan,
                        force_when_disabled=True,
                    )
                    if url:
                        st.code(url)
                        try:
                            st.link_button("Open Checkout", url, use_container_width=True)
                        except Exception:
                            st.markdown(f"[Open Checkout]({url})")
                    else:
                        # Distinguish missing secrets vs missing dependency (common on deploy).
                        try:
                            import stripe  # type: ignore  # noqa: F401

                            stripe_ok = True
                        except Exception:
                            stripe_ok = False

                        if not stripe_ok:
                            st.error(
                                "Stripe Python SDK isn't installed in the Streamlit environment yet. "
                                "We added it to `requirements.txt`; wait for Streamlit to redeploy, then try again."
                            )
                            st.caption("If it still fails after redeploy: check Streamlit logs for pip install errors.")
                        else:
                            st.error(
                                "Could not create a Checkout link. Make sure these Streamlit secrets exist:\n\n"
                                "- STRIPE_SECRET_KEY\n"
                                "- STRIPE_SUCCESS_URL\n"
                                "- STRIPE_CANCEL_URL\n"
                                "- STRIPE_PRICE_ID_MONTHLY (or STRIPE_PRICE_ID)\n"
                                "- STRIPE_PRICE_ID_QUARTERLY\n"
                            "- STRIPE_PRICE_ID_YEARLY\n"
                        )

                st.markdown("---")
                st.markdown("**Admin: Grandfather Existing Users**")
                st.caption(
                    "This marks all accounts that exist right now as `grandfathered` (unlimited trades) so they keep access after paywall launch."
                )
                confirm = st.checkbox("I understand this grants unlimited access to existing users.", value=False, key="admin_grandfather_confirm")
                if st.button("Grandfather all current users", use_container_width=True, key="admin_grandfather_now", disabled=not confirm):
                    ok, msg = admin_grandfather_existing_users(datetime.utcnow())
                    if ok:
                        st.success(msg)
                    else:
                        st.error(
                            f"Grandfathering failed: {msg}\n\n"
                            "Make sure `SUPABASE_SERVICE_ROLE_KEY` is set in Streamlit secrets."
                        )

            st.markdown("---")
            if st.button("Log out", key="sidebar_logout"):
                supabase.auth.sign_out()
                st.session_state.clear()
                st.rerun()

        # Account card (bottom-ish)
        user_obj = st.session_state.get("user")
        email = ""
        if isinstance(user_obj, dict):
            email = safe_str(user_obj.get("email"))
        else:
            email = safe_str(getattr(user_obj, "email", ""))
        if email:
            st.markdown(
                f"""
                <div class="sidebar-usercard">
                  <div class="small">Signed in as</div>
                  <div class="value">{html_lib.escape(email)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    section = st.session_state.get("nav_section", section_options[0])

    if section == "Journal":
        render_journal_page(user.id)
    elif section == "Strategy/Model Creation":
        render_strategy_creation_page(user.id)
    elif section == "Affiliates":
        render_affiliates_page(user.id)
    else:
        tabs = st.tabs(ACCOUNT_TYPES)
        for tab, account_type in zip(tabs, ACCOUNT_TYPES):
            with tab:
                render_section(user.id, account_type, section)
