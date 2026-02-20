import html as html_lib
import io
import uuid
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client, Client

st.set_page_config(page_title="Futures Trading Journal", layout="wide")

# ── Supabase client ──────────────────────────────────────────────────────────
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

# ── Constants ─────────────────────────────────────────────────────────────────
ACCOUNT_TYPES = ["Evaluation Account Data", "Funded Account Data"]

INSTRUMENTS = {"NQ": 20, "MNQ": 2, "ES": 50, "MES": 5}
INSTRUMENT_ORDER = list(INSTRUMENTS.keys())
SESSIONS = ["NY", "London", "Pre-market"]
MARKET_CONDITIONS = ["Not set", "Trend", "Range", "Volatile", "News", "Mixed/Unsure"]
TRADE_GRADES = ["Not set", "A", "B", "C", "D"]
TRADE_TYPES = ["Not set", "Continuation model", "Reversal", "Turtle soup model"]
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

# ── Auth ──────────────────────────────────────────────────────────────────────

def show_auth():
    st.title("Futures Trading Journal")
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
                st.error(f"Login failed: {e}")

    with tab_signup:
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password (min 6 chars)", type="password", key="signup_password")
        if st.button("Sign up"):
            try:
                res = supabase.auth.sign_up({"email": email, "password": password})
                st.success("Account created! Check your email to confirm, then log in.")
            except Exception as e:
                st.error(f"Sign up failed: {e}")


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


def format_money(value) -> str:
    v = to_float(value)
    if v is None:
        return ""
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}"


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
    per_point = INSTRUMENTS.get(instrument)
    if per_point is None:
        return metrics
    if entry is None or stop is None or exit_price is None or contracts is None:
        return metrics

    if direction == "Long":
        points = exit_price - entry
    else:
        points = entry - exit_price

    commission_val = commission or 0
    slippage_val = slippage or 0
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
    sb.storage.from_("trade-images").upload(filename, file.getbuffer(), {"content-type": f"image/{ext}"})
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


def build_confluence_combo_stats(df: pd.DataFrame, pnl_col: str) -> pd.DataFrame:
    rows = []
    for _, row in df.iterrows():
        raw = str(row.get("confluences", "") or "")
        tags = [tag.strip() for tag in raw.split(",") if tag.strip()]
        if not tags:
            continue
        combo = " + ".join(sorted(tags))
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
    confluence_html = "\n".join(confluence_items)
    reason = html_lib.escape(safe_str(row.get("setup_tag")))

    return f"""<!doctype html>
<html><head><meta charset="utf-8"/>
<style>
@page{{size:A4;margin:12mm}}
body{{font-family:Arial,Helvetica,sans-serif;margin:0;padding:0;color:#000}}
.toolbar{{display:flex;gap:10px;align-items:center;padding:8px 0}}
.toolbar button{{padding:6px 10px;border:1px solid #000;background:#fff;cursor:pointer}}
@media print{{.toolbar{{display:none}}}}
.sheet{{width:210mm;min-height:297mm;box-sizing:border-box;padding:0}}
.grid{{display:grid;gap:6mm}}
.box{{border:2px solid #000;box-sizing:border-box}}
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
<div class="toolbar"><button onclick="window.print()">Print (A4)</button></div>
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

def render_section(user_id: str, account_type: str) -> None:
    form_key = account_type.replace(" ", "_").lower()

    df_raw = load_trades(user_id, account_type)

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

            st.markdown("**Confluences (check all that apply)**")
            conf_cols = st.columns(4)
            selected_confluences = []
            for idx, name in enumerate(CONFLUENCES):
                if conf_cols[idx % 4].checkbox(name, key=f"{form_key}_conf_{idx}"):
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
                strategy = adv1[1].text_input("Strategy name", key=f"{form_key}_strategy")
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
        if entry <= 0 or stop <= 0 or exit_price <= 0:
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
                "trade_type": trade_type if trade_type != "Not set" else None,
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
        st.info("No trades yet. Add your first trade above.")
        return

    df = prepare_df(df_raw)

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
    components.html(sheet_html, height=1250, scrolling=True)

    # ── Dashboard ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Dashboard")
    df_view = df.copy()
    df_view.columns = [str(c).strip() for c in df_view.columns]

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

    df_view = df_view[
        (df_view["date"] >= pd.to_datetime(start_date))
        & (df_view["date"] <= pd.to_datetime(end_date))
        & (df_view["instrument"].isin(instrument_filter))
        & (df_view["session"].isin(session_filter))
        & (df_view["direction"].isin(direction_filter))
    ]

    pnl_view = st.radio("PnL view", ["Net (after fees)", "Gross"], horizontal=True, key=f"{form_key}_pnl_view")
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
        st.info("No trades match your filters.")
        return

    wins_df = df_view[df_view[pnl_col] > 0]
    losses_df = df_view[df_view[pnl_col] < 0]
    wins = len(wins_df)
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    avg_r = df_view["r_multiple"].dropna().mean() if "r_multiple" in df_view.columns else 0
    total_pnl = df_view[pnl_col].sum()
    avg_win = wins_df[pnl_col].mean() if wins > 0 else 0
    avg_loss = losses_df[pnl_col].mean() if len(losses_df) > 0 else 0
    loss_sum = losses_df[pnl_col].sum() if len(losses_df) > 0 else 0
    profit_factor = wins_df[pnl_col].sum() / abs(loss_sum) if loss_sum != 0 else None
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss) if total_trades > 0 else 0
    largest_win = df_view[pnl_col].max()
    largest_loss = df_view[pnl_col].min()
    avg_duration = df_view["duration_minutes"].dropna().mean() if "duration_minutes" in df_view.columns else 0
    plan_rate = (df_view["followed_plan"] == "Yes").mean() * 100 if "followed_plan" in df_view.columns else 0
    revenge_rate = (df_view["revenge_trade"] == "Yes").mean() * 100 if "revenge_trade" in df_view.columns else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total trades", total_trades)
    m2.metric("Win rate", f"{win_rate:.1f}%")
    m3.metric("Average R", f"{avg_r:.2f}" if avg_r else "n/a")
    m4.metric("Total PnL", f"${total_pnl:,.2f}")

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Avg win", f"${avg_win:,.2f}")
    m6.metric("Avg loss", f"${avg_loss:,.2f}")
    m7.metric("Profit factor", f"{profit_factor:.2f}" if profit_factor is not None else "n/a")
    m8.metric("Expectancy", f"${expectancy:,.2f}")

    m9, m10, m11, m12 = st.columns(4)
    m9.metric("Largest win", f"${largest_win:,.2f}")
    m10.metric("Largest loss", f"${largest_loss:,.2f}")
    m11.metric("Avg duration", f"{avg_duration:.1f} min" if avg_duration else "n/a")
    m12.metric("Plan adherence", f"{plan_rate:.1f}%")

    chart_df = df_view.sort_values("date").copy()
    chart_df["equity"] = chart_df[pnl_col].cumsum()
    chart_df["peak"] = chart_df["equity"].cummax()
    chart_df["drawdown"] = chart_df["equity"] - chart_df["peak"]

    st.subheader("Equity curve")
    st.line_chart(chart_df.set_index("date")["equity"], height=260, use_container_width=True)
    st.subheader("Drawdown")
    st.line_chart(chart_df.set_index("date")["drawdown"], height=200, use_container_width=True)

    st.markdown("---")
    st.subheader("Daily PnL")
    st.bar_chart(chart_df.groupby("date")[pnl_col].sum(), use_container_width=True)

    st.subheader("Calendar heatmap")
    render_calendar_heatmap(chart_df, pnl_col)

    st.markdown("---")
    st.subheader("Breakdowns")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("PnL by instrument")
        st.bar_chart(chart_df.groupby("instrument")[pnl_col].sum().reindex(INSTRUMENT_ORDER), use_container_width=True)
    with c2:
        st.subheader("PnL by session")
        st.bar_chart(chart_df.groupby("session")[pnl_col].sum().reindex(SESSIONS), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("PnL by direction")
        st.bar_chart(chart_df.groupby("direction")[pnl_col].sum(), use_container_width=True)
    with c4:
        st.subheader("PnL by trade grade")
        if "trade_grade" in chart_df.columns:
            st.bar_chart(chart_df.groupby("trade_grade")[pnl_col].sum(), use_container_width=True)

    c5, c6 = st.columns(2)
    with c5:
        chart_df["day"] = chart_df["date"].dt.day_name()
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        st.subheader("PnL by day of week")
        st.bar_chart(chart_df.groupby("day")[pnl_col].sum().reindex(day_order).dropna(), use_container_width=True)
    with c6:
        chart_df["month"] = chart_df["date"].dt.to_period("M").astype(str)
        st.subheader("PnL by month")
        st.bar_chart(chart_df.groupby("month")[pnl_col].sum(), use_container_width=True)

    if "entry_hour" in chart_df.columns:
        hour_df = chart_df.dropna(subset=["entry_hour"])
        if len(hour_df) > 0:
            st.subheader("Time of day breakdown")
            st.bar_chart(hour_df.groupby("entry_hour")[pnl_col].sum(), use_container_width=True)

    st.markdown("---")
    st.subheader("Setup & confluence performance")
    tag_df = explode_tags(chart_df, "setup_tag")
    if len(tag_df) > 0:
        st.dataframe(
            tag_df.groupby("setup_tag")[pnl_col].agg(["sum", "mean", "count"])
            .rename(columns={"sum": "Total PnL", "mean": "Avg PnL", "count": "Trades"})
            .sort_values("Total PnL", ascending=False),
            use_container_width=True
        )

    conf_df = explode_tags(chart_df, "confluences")
    if len(conf_df) > 0:
        conf_stats = (
            conf_df.groupby("confluences")[pnl_col]
            .agg(["sum", "mean", "count"])
            .rename(columns={"sum": "Total PnL", "mean": "Avg PnL", "count": "Trades"})
            .sort_values("Total PnL", ascending=False)
        )
        conf_stats["Win rate %"] = conf_df.groupby("confluences")[pnl_col].apply(lambda s: (s > 0).mean() * 100)
        st.dataframe(conf_stats, use_container_width=True)

    st.markdown("---")
    st.subheader("Top & bottom trades")
    display_cols = ["date", "instrument", "direction", "session", "entry_price", "exit_price", pnl_col, "r_multiple", "setup_tag"]
    display_cols = [c for c in display_cols if c in chart_df.columns]
    c_top, c_bot = st.columns(2)
    with c_top:
        st.subheader("Top 10")
        st.dataframe(chart_df.sort_values(pnl_col, ascending=False).head(10)[display_cols], use_container_width=True, hide_index=True)
    with c_bot:
        st.subheader("Bottom 10")
        st.dataframe(chart_df.sort_values(pnl_col, ascending=True).head(10)[display_cols], use_container_width=True, hide_index=True)

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
    show_auth()
else:
    st.title("Futures Trading Journal")
    col_title, col_logout = st.columns([8, 1])
    with col_logout:
        if st.button("Log out"):
            supabase.auth.sign_out()
            st.session_state.clear()
            st.rerun()

    tabs = st.tabs(ACCOUNT_TYPES)
    for tab, account_type in zip(tabs, ACCOUNT_TYPES):
        with tab:
            render_section(user.id, account_type)
