"""
Google Sheets writer for Nifty Option Chain data
--------------------------------------------------
Writes 3 tabs into a Google Sheet every time the scheduler fires:

  Tab 1 – "Summary"    : PCR, Max Pain, commentary, expected range
  Tab 2 – "OI Chain"   : Full option chain (all strikes, CE left / PE right)
  Tab 3 – "Key Levels" : Top support & resistance strikes

SETUP (one-time, ~5 minutes)
==============================
1. Go to https://console.cloud.google.com/ → New project
2. Enable "Google Sheets API" and "Google Drive API"
3. IAM & Admin → Service Accounts → Create service account
4. Keys → Add Key → JSON  →  save the downloaded file as
       nifty_option_chain/credentials.json
5. Open your target Google Sheet → Share → paste the service-account email
   (looks like  xxx@yyy.iam.gserviceaccount.com)  with Editor access
6. Copy the Spreadsheet ID from the URL:
       https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit
7. Set the two environment variables (or hard-code them below):
       export NIFTY_SPREADSHEET_ID="<your-spreadsheet-id>"
       export GOOGLE_CREDENTIALS_PATH="/path/to/credentials.json"

Then run:
    python scheduler.py          # 8 PM IST daily
    python scheduler.py --once   # test right now
"""

import os
import logging

log = logging.getLogger(__name__)

# ─── Config  (override via environment variables) ─────────────────────────────

SPREADSHEET_ID      = os.getenv("NIFTY_SPREADSHEET_ID", "")
CREDENTIALS_PATH    = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ─── Activity colour palette (RGB 0-1 floats) ─────────────────────────────────

ACTIVITY_COLORS = {
    "Long Buildup":   {"red": 0.714, "green": 0.882, "blue": 0.804},  # soft green
    "Short Covering": {"red": 0.788, "green": 0.855, "blue": 0.973},  # soft blue
    "Short Buildup":  {"red": 0.957, "green": 0.800, "blue": 0.800},  # soft red
    "Long Unwinding": {"red": 0.988, "green": 0.898, "blue": 0.804},  # soft orange
}

HEADER_BG   = {"red": 0.157, "green": 0.318, "blue": 0.510}   # dark navy
HEADER_FG   = {"red": 1.0,   "green": 1.0,   "blue": 1.0}     # white
ATM_BG      = {"red": 1.0,   "green": 0.949, "blue": 0.800}   # light gold


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_client():
    """Authenticate and return a gspread client."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError(
            "Missing libraries.  Run:  pip install gspread google-auth"
        )

    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"Credentials file not found: {CREDENTIALS_PATH}\n"
            "See the SETUP section at the top of google_sheets.py"
        )

    creds = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_or_create_ws(spreadsheet, name: str, rows: int = 300, cols: int = 20):
    """Return existing worksheet or create a fresh one."""
    import gspread
    try:
        ws = spreadsheet.worksheet(name)
        ws.clear()
        return ws
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)


def _format_range(ws, range_a1: str, fmt: dict):
    """Apply a cell format dict to a range."""
    ws.format(range_a1, fmt)


def _bold_center(ws, range_a1: str):
    _format_range(ws, range_a1, {
        "textFormat": {"bold": True},
        "horizontalAlignment": "CENTER",
    })


def _header_style(ws, range_a1: str):
    _format_range(ws, range_a1, {
        "backgroundColor": HEADER_BG,
        "textFormat": {
            "bold": True,
            "foregroundColor": HEADER_FG,
        },
        "horizontalAlignment": "CENTER",
    })


def _apply_activity_colors(ws, sheet_id: int, data_rows: list, ce_col: int, pe_col: int):
    """
    Batch-apply conditional background colours to the CE Activity and PE Activity
    columns using the Sheets API batchUpdate (avoids N individual format calls).

    ce_col / pe_col : 0-based column index
    data_rows       : list of row dicts from oi_chain
    """
    requests_body = []
    for row_idx, item in enumerate(data_rows, start=2):   # row 1 = header
        for col_idx, side in ((ce_col, "ce"), (pe_col, "pe")):
            activity = item[side].get("activity", "")
            color    = ACTIVITY_COLORS.get(activity)
            if not color:
                continue
            requests_body.append({
                "repeatCell": {
                    "range": {
                        "sheetId":          sheet_id,
                        "startRowIndex":    row_idx - 1,
                        "endRowIndex":      row_idx,
                        "startColumnIndex": col_idx,
                        "endColumnIndex":   col_idx + 1,
                    },
                    "cell": {
                        "userEnteredFormat": {"backgroundColor": color}
                    },
                    "fields": "userEnteredFormat.backgroundColor",
                }
            })

    if requests_body:
        ws.spreadsheet.batch_update({"requests": requests_body})


def _highlight_atm_row(ws, sheet_id: int, atm_row_idx: int, total_cols: int):
    """Highlight the ATM row with a gold background."""
    ws.spreadsheet.batch_update({"requests": [{
        "repeatCell": {
            "range": {
                "sheetId":          sheet_id,
                "startRowIndex":    atm_row_idx - 1,
                "endRowIndex":      atm_row_idx,
                "startColumnIndex": 0,
                "endColumnIndex":   total_cols,
            },
            "cell": {
                "userEnteredFormat": {"backgroundColor": ATM_BG}
            },
            "fields": "userEnteredFormat.backgroundColor",
        }
    }]})


# ─── Tab writers ──────────────────────────────────────────────────────────────

def _write_summary(ws, data: dict):
    meta  = data["meta"]
    pcr   = data["pcr"]
    rng   = data["range"]
    mp    = data["max_pain"]
    sr    = data["support_resistance"]
    act   = data["activity_summary"]
    spot  = meta["spot"]

    gap_to_mp = round(mp - spot, 1)
    if abs(gap_to_mp) <= 50:
        mp_comment = "Spot near Max Pain → rangebound / choppy expected"
    elif gap_to_mp > 0:
        mp_comment = f"Spot {gap_to_mp} pts below Max Pain → gravitational pull UP"
    else:
        mp_comment = f"Spot {abs(gap_to_mp)} pts above Max Pain → gravitational pull DOWN"

    rows = [
        ["NIFTY OPTION CHAIN ANALYSIS", ""],
        ["Generated At",  meta["generated_at"]],
        ["NSE Timestamp", meta["timestamp"]],
        ["Nearest Expiry",meta["expiry"]],
        [""],
        ["Spot Price",    meta["spot"]],
        ["ATM Strike",    meta["atm"]],
        [""],
        ["─── PUT-TO-CALL RATIO ───", ""],
        ["PCR (OI)",      pcr["pcr_oi"]],
        ["PCR (Volume)",  pcr["pcr_vol"]],
        ["Total Call OI", pcr["total_call_oi"]],
        ["Total Put  OI", pcr["total_put_oi"]],
        ["PCR Commentary", pcr["commentary"]],
        [""],
        ["─── OI ACTIVITY SUMMARY ───", ""],
        ["Dominant Activity", act["dominant"]],
    ]
    for label, cnt in sorted(act["counts"].items(), key=lambda x: -x[1]):
        rows.append([f"  {label}", cnt])

    rows += [
        [""],
        ["─── MAX PAIN ───", ""],
        ["Max Pain Strike", mp],
        ["Max Pain Comment", mp_comment],
        [""],
        ["─── EXPECTED RANGE ───", ""],
        ["ATM IV (%)",     rng["iv_atm"]],
        ["DTE (days)",     rng["dte"]],
        ["1-SD Lower",     rng["one_sd_lower"]],
        ["1-SD Upper",     rng["one_sd_upper"]],
        ["OI Support",     rng["oi_support"]],
        ["OI Resistance",  rng["oi_resistance"]],
        [""],
        ["─── TOP RESISTANCE (Call OI) ───", ""],
        ["Strike", "Open Interest"],
    ]
    for strike, oi in sr["resistances"]:
        rows.append([strike, oi])
    rows += [
        [""],
        ["─── TOP SUPPORT (Put OI) ───", ""],
        ["Strike", "Open Interest"],
    ]
    for strike, oi in sr["supports"]:
        rows.append([strike, oi])

    ws.update(rows, "A1")
    _header_style(ws, "A1:B1")
    _bold_center(ws, "A9:B9")
    _bold_center(ws, "A16:B16")
    _bold_center(ws, "A20:B20")
    _bold_center(ws, "A23:B23")


def _write_oi_chain(ws, data: dict):
    """
    Full option chain — mirroring NSE's own display:

    CE Activity | CE IV | CE Chg% | CE LTP | CE Chg OI | CE OI | STRIKE | PE OI | PE Chg OI | PE LTP | PE Chg% | PE IV | PE Activity
    """
    HEADERS = [
        "CE Activity", "CE IV", "CE Chg%", "CE LTP", "CE ΔOI", "CE OI",
        "STRIKE",
        "PE OI", "PE ΔOI", "PE LTP", "PE Chg%", "PE IV", "PE Activity",
    ]

    rows = [HEADERS]
    atm_row_idx = None

    for idx, item in enumerate(data["oi_chain"], start=2):
        ce = item["ce"]
        pe = item["pe"]
        row = [
            ce["activity"],
            ce["iv"],
            ce["chg_price"],
            ce["ltp"],
            ce["chg_oi"],
            ce["oi"],
            item["strike"],
            pe["oi"],
            pe["chg_oi"],
            pe["ltp"],
            pe["chg_price"],
            pe["iv"],
            pe["activity"],
        ]
        rows.append(row)
        if item["atm"]:
            atm_row_idx = idx

    ws.update(rows, "A1")

    # Style header row
    _header_style(ws, f"A1:M1")

    # Freeze header row
    ws.spreadsheet.batch_update({"requests": [{
        "updateSheetProperties": {
            "properties": {
                "sheetId": ws.id,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    }]})

    # Highlight ATM row
    if atm_row_idx:
        _highlight_atm_row(ws, ws.id, atm_row_idx, total_cols=13)

    # Colour-code CE Activity (col 0) and PE Activity (col 12)
    _apply_activity_colors(ws, ws.id, data["oi_chain"], ce_col=0, pe_col=12)


def _write_key_levels(ws, data: dict):
    sr   = data["support_resistance"]
    meta = data["meta"]
    rng  = data["range"]
    mp   = data["max_pain"]

    rows = [
        ["KEY LEVELS — NIFTY", ""],
        ["As of", meta["generated_at"]],
        ["Spot",  meta["spot"]],
        ["ATM",   meta["atm"]],
        [""],
        ["Type", "Strike", "Open Interest", "Role"],
    ]

    for strike, oi in sr["resistances"]:
        role = "Max Resistance" if strike == sr["resistances"][0][0] else "Resistance"
        rows.append(["RESISTANCE", strike, oi, role])

    rows.append([""])

    for strike, oi in sr["supports"]:
        role = "Max Support" if strike == sr["supports"][0][0] else "Support"
        rows.append(["SUPPORT", strike, oi, role])

    rows += [
        [""],
        ["Max Pain",      mp,               "", "Gravitational target"],
        ["OI Support",    rng["oi_support"], "", "Put OI anchor"],
        ["OI Resistance", rng["oi_resistance"], "", "Call OI anchor"],
        ["1-SD Lower",    rng["one_sd_lower"],  "", f"IV={rng['iv_atm']}%"],
        ["1-SD Upper",    rng["one_sd_upper"],  "", f"DTE={rng['dte']}d"],
    ]

    ws.update(rows, "A1")
    _header_style(ws, "A1:D1")
    _bold_center(ws, "A6:D6")


# ─── Main entry point ─────────────────────────────────────────────────────────

def write_to_sheet(data: dict, spreadsheet_id: str = "", credentials_path: str = ""):
    """
    Write analysis data to Google Sheets.

    Parameters
    ----------
    data             : dict returned by nifty_option_chain.get_structured_data()
    spreadsheet_id   : overrides NIFTY_SPREADSHEET_ID env var
    credentials_path : overrides GOOGLE_CREDENTIALS_PATH env var
    """
    sid   = spreadsheet_id   or SPREADSHEET_ID
    creds = credentials_path or CREDENTIALS_PATH

    if not sid:
        log.error(
            "NIFTY_SPREADSHEET_ID not set.  "
            "Set the environment variable or pass spreadsheet_id= to write_to_sheet()."
        )
        return

    log.info("Connecting to Google Sheets …")
    try:
        # Temporarily override module-level CREDENTIALS_PATH if caller passed one
        original = os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
        if credentials_path:
            os.environ["GOOGLE_CREDENTIALS_PATH"] = credentials_path

        gc = _get_client()
        sh = gc.open_by_key(sid)

        if credentials_path:
            os.environ["GOOGLE_CREDENTIALS_PATH"] = original

    except Exception as exc:
        log.error("Could not connect to Google Sheets: %s", exc)
        return

    log.info("Writing Summary tab …")
    _write_summary(_get_or_create_ws(sh, "Summary",   rows=80,  cols=4),  data)

    log.info("Writing OI Chain tab (%d strikes) …", len(data["oi_chain"]))
    _write_oi_chain(_get_or_create_ws(sh, "OI Chain", rows=len(data["oi_chain"]) + 5, cols=14), data)

    log.info("Writing Key Levels tab …")
    _write_key_levels(_get_or_create_ws(sh, "Key Levels", rows=40, cols=5), data)

    log.info("Google Sheets updated: https://docs.google.com/spreadsheets/d/%s", sid)
