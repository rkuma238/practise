"""
Nifty Option Chain Analyser
----------------------------
Fetches live NSE option-chain data and generates a human-readable market
commentary covering:

  • Put-to-Call Ratio  (OI-based & Volume-based)
  • Max Pain level
  • Key Support & Resistance zones
  • OI change interpretation  (Long Buildup / Short Buildup /
                                Long Unwinding / Short Covering)
  • Expected intraday / weekly trading range

Usage (standalone):
    python nifty_option_chain.py

The scheduler (scheduler.py) calls run() automatically at 8 PM IST every day.
"""

import json
import math
import time
import datetime
import requests


# ─── NSE session ──────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/option-chain",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
}

NSE_BASE = "https://www.nseindia.com"
OC_URL   = f"{NSE_BASE}/api/option-chain-indices?symbol=NIFTY"


def _nse_session() -> requests.Session:
    """Return a requests.Session pre-warmed with NSE cookies."""
    session = requests.Session()
    session.headers.update(HEADERS)
    # Warm up – NSE needs a browser-like cookie handshake
    for warm_url in [NSE_BASE, f"{NSE_BASE}/option-chain"]:
        try:
            session.get(warm_url, timeout=10)
            time.sleep(1)
        except requests.RequestException:
            pass
    return session


def fetch_option_chain(retries: int = 3) -> dict:
    """Fetch raw option-chain JSON from NSE.  Returns the parsed dict."""
    session = _nse_session()
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(OC_URL, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            print(f"  [Attempt {attempt}/{retries}] Fetch failed: {exc}")
            if attempt < retries:
                time.sleep(3 * attempt)
    raise RuntimeError("Unable to fetch option-chain data after all retries.")


# ─── Data helpers ──────────────────────────────────────────────────────────────

def nearest_expiry_data(raw: dict) -> tuple[list, float, str]:
    """
    Returns (option_rows, spot_price, expiry_date) for the nearest expiry.
    Each row is the raw NSE dict item { 'strikePrice', 'CE': {...}, 'PE': {...} }.
    """
    records      = raw["records"]
    all_data     = records.get("data", [])
    expiry_dates = records.get("expiryDates", [])
    spot         = float(records.get("underlyingValue", 0))
    timestamp    = records.get("timestamp", "")

    if not expiry_dates:
        raise ValueError("No expiry dates found in option-chain data.")

    nearest = expiry_dates[0]
    rows = [r for r in all_data if r.get("expiryDate") == nearest]
    return rows, spot, nearest, timestamp


def atm_strike(spot: float, rows: list) -> int:
    """Return the ATM strike closest to spot."""
    strikes = [r["strikePrice"] for r in rows]
    return min(strikes, key=lambda s: abs(s - spot))


# ─── Core metrics ──────────────────────────────────────────────────────────────

def pcr(rows: list) -> dict:
    """Put-to-Call ratio (OI-based & Volume-based)."""
    total_call_oi = total_put_oi = 0
    total_call_vol = total_put_vol = 0

    for r in rows:
        ce = r.get("CE", {})
        pe = r.get("PE", {})
        total_call_oi  += ce.get("openInterest", 0)
        total_put_oi   += pe.get("openInterest", 0)
        total_call_vol += ce.get("totalTradedVolume", 0)
        total_put_vol  += pe.get("totalTradedVolume", 0)

    pcr_oi  = round(total_put_oi  / total_call_oi,  2) if total_call_oi  else 0
    pcr_vol = round(total_put_vol / total_call_vol, 2) if total_call_vol else 0

    return {
        "pcr_oi":       pcr_oi,
        "pcr_vol":      pcr_vol,
        "total_call_oi": total_call_oi,
        "total_put_oi":  total_put_oi,
    }


def max_pain(rows: list) -> int:
    """
    Max-Pain strike: the strike price at which aggregate option-buyer losses
    are maximised (i.e. aggregate option-writer losses are minimised).
    """
    strikes = sorted(r["strikePrice"] for r in rows)
    oi_map_ce = {r["strikePrice"]: r.get("CE", {}).get("openInterest", 0) for r in rows}
    oi_map_pe = {r["strikePrice"]: r.get("PE", {}).get("openInterest", 0) for r in rows}

    min_pain   = float("inf")
    pain_strike = strikes[0]

    for target in strikes:
        pain = 0
        for s in strikes:
            # Loss to call buyers when spot = target
            if target > s:
                pain += (target - s) * oi_map_ce.get(s, 0)
            # Loss to put buyers when spot = target
            if target < s:
                pain += (s - target) * oi_map_pe.get(s, 0)
        if pain < min_pain:
            min_pain    = pain
            pain_strike = target

    return pain_strike


def support_resistance(rows: list, top_n: int = 3) -> dict:
    """
    Identify top-N support levels (max Put OI) and
    resistance levels (max Call OI).
    """
    call_oi = [(r["strikePrice"], r.get("CE", {}).get("openInterest", 0)) for r in rows]
    put_oi  = [(r["strikePrice"], r.get("PE", {}).get("openInterest", 0)) for r in rows]

    resistances = sorted(call_oi, key=lambda x: x[1], reverse=True)[:top_n]
    supports    = sorted(put_oi,  key=lambda x: x[1], reverse=True)[:top_n]

    return {
        "resistances": [(s, oi) for s, oi in resistances],
        "supports":    [(s, oi) for s, oi in supports],
    }


def oi_activity(rows: list, spot: float, window: int = 10) -> list:
    """
    Classify OI activity for strikes within ±window strikes of ATM:

      Price ↑ + OI ↑  → Long Buildup   (bulls adding longs)
      Price ↑ + OI ↓  → Short Covering  (bears covering shorts)
      Price ↓ + OI ↑  → Short Buildup  (bears adding shorts)
      Price ↓ + OI ↓  → Long Unwinding  (bulls exiting longs)

    We use `changeinOpenInterest` and `change` (price change) from NSE data.
    """
    atm = atm_strike(spot, rows)
    strikes_sorted = sorted(r["strikePrice"] for r in rows)
    atm_idx = strikes_sorted.index(atm)
    nearby = strikes_sorted[max(0, atm_idx - window): atm_idx + window + 1]

    activities = []
    for r in rows:
        if r["strikePrice"] not in nearby:
            continue
        for opt_type in ("CE", "PE"):
            d = r.get(opt_type, {})
            if not d:
                continue
            chg_oi    = d.get("changeinOpenInterest", 0)
            chg_price = d.get("change", 0)
            label = _classify_activity(chg_oi, chg_price)
            activities.append({
                "strike":    r["strikePrice"],
                "type":      opt_type,
                "oi":        d.get("openInterest", 0),
                "chg_oi":    chg_oi,
                "chg_price": chg_price,
                "activity":  label,
                "ltp":       d.get("lastPrice", 0),
            })
    return activities


def _classify_activity(chg_oi: float, chg_price: float) -> str:
    if chg_oi >= 0 and chg_price >= 0:
        return "Long Buildup"
    if chg_oi < 0 and chg_price >= 0:
        return "Short Covering"
    if chg_oi >= 0 and chg_price < 0:
        return "Short Buildup"
    return "Long Unwinding"


def expected_range(rows: list, spot: float) -> dict:
    """
    Estimate a 1-SD expected range using the ATM implied volatility and
    days-to-expiry.  Also returns a simpler OI-anchor range.
    """
    atm = atm_strike(spot, rows)
    atm_row = next((r for r in rows if r["strikePrice"] == atm), {})

    # ATM IV (average of CE and PE ATM IV)
    ce_iv = atm_row.get("CE", {}).get("impliedVolatility", 0)
    pe_iv = atm_row.get("PE", {}).get("impliedVolatility", 0)
    iv    = (ce_iv + pe_iv) / 2 if (ce_iv and pe_iv) else (ce_iv or pe_iv)

    # Compute DTE from the record timestamp (approximate, uses today's date)
    dte = 7  # default fallback (weekly expiry)
    one_sd_move = spot * (iv / 100) * math.sqrt(dte / 365) if iv else 0

    # OI-anchor range: support = max Put OI strike, resistance = max Call OI strike
    sr = support_resistance(rows, top_n=1)
    oi_support    = sr["supports"][0][0]    if sr["supports"]    else spot - 200
    oi_resistance = sr["resistances"][0][0] if sr["resistances"] else spot + 200

    return {
        "iv_atm":        round(iv, 2),
        "dte":           dte,
        "one_sd_lower":  round(spot - one_sd_move, 2),
        "one_sd_upper":  round(spot + one_sd_move, 2),
        "oi_support":    oi_support,
        "oi_resistance": oi_resistance,
    }


# ─── Commentary generator ──────────────────────────────────────────────────────

def _pcr_commentary(pcr_oi: float) -> str:
    if pcr_oi >= 1.5:
        return (
            f"PCR(OI) = {pcr_oi} — Extremely high Put writing, market extremely oversold. "
            "Strong contrarian BUY signal; sharp short-covering rally likely."
        )
    if pcr_oi >= 1.2:
        return (
            f"PCR(OI) = {pcr_oi} — Bullish bias. Puts significantly outnumber calls; "
            "writing community expects support to hold."
        )
    if pcr_oi >= 0.9:
        return (
            f"PCR(OI) = {pcr_oi} — Near neutral zone (0.9–1.2). Market indecisive; "
            "wait for directional cues."
        )
    if pcr_oi >= 0.7:
        return (
            f"PCR(OI) = {pcr_oi} — Bearish bias. Call writing dominant; "
            "resistance likely to cap upside."
        )
    return (
        f"PCR(OI) = {pcr_oi} — Very bearish / overbought territory. "
        "High call writing suggests limited upside; risk of sharp correction."
    )


def _activity_summary(activities: list) -> str:
    counts = {}
    for a in activities:
        counts[a["activity"]] = counts.get(a["activity"], 0) + 1
    dominant = max(counts, key=counts.get) if counts else "Unknown"
    lines = [f"  {k}: {v} strikes" for k, v in sorted(counts.items(), key=lambda x: -x[1])]
    detail = "\n".join(lines)

    explanations = {
        "Long Buildup":   "Bulls aggressively adding fresh longs → upward momentum likely.",
        "Short Covering": "Bears squaring off shorts → price may spike up quickly.",
        "Short Buildup":  "Bears building fresh short positions → downside pressure building.",
        "Long Unwinding": "Bulls exiting positions → upside capped; watch for weakness.",
    }
    return (
        f"Dominant OI Activity: {dominant}\n"
        f"{detail}\n"
        f"Interpretation: {explanations.get(dominant, '')}"
    )


def _range_commentary(rng: dict, spot: float, mp: int) -> str:
    lines = []
    if rng["iv_atm"]:
        lines.append(
            f"ATM IV = {rng['iv_atm']}%  |  1-SD Range ({rng['dte']}-day): "
            f"{rng['one_sd_lower']} – {rng['one_sd_upper']}"
        )
    lines.append(
        f"OI Anchor Range: Support @ {rng['oi_support']}  |  Resistance @ {rng['oi_resistance']}"
    )
    lines.append(f"Max Pain Level  : {mp}")

    gap_to_mp = round(mp - spot, 1)
    if abs(gap_to_mp) <= 50:
        lines.append("Spot is near Max Pain → expect rangebound / choppy action.")
    elif gap_to_mp > 0:
        lines.append(
            f"Spot is {gap_to_mp} pts BELOW Max Pain → gravitational pull upward; "
            "call writers may defend max-pain level."
        )
    else:
        lines.append(
            f"Spot is {abs(gap_to_mp)} pts ABOVE Max Pain → gravitational pull downward; "
            "put writers may defend max-pain level."
        )
    return "\n".join(lines)


# ─── Main report ───────────────────────────────────────────────────────────────

def generate_report(raw: dict) -> str:
    rows, spot, expiry, timestamp = nearest_expiry_data(raw)

    pcr_data   = pcr(rows)
    mp         = max_pain(rows)
    sr         = support_resistance(rows, top_n=3)
    activities = oi_activity(rows, spot, window=10)
    rng        = expected_range(rows, spot)

    sep = "═" * 65

    lines = [
        "",
        sep,
        "  NIFTY OPTION CHAIN ANALYSIS",
        f"  Generated : {datetime.datetime.now().strftime('%d-%b-%Y %H:%M')} IST",
        f"  NSE Timestamp : {timestamp}",
        f"  Nearest Expiry: {expiry}",
        sep,
        "",
        f"  Spot Price : {spot}",
        f"  ATM Strike : {atm_strike(spot, rows)}",
        "",
        "── PUT-TO-CALL RATIO ──────────────────────────────────────────",
        f"  PCR (OI)    : {pcr_data['pcr_oi']}",
        f"  PCR (Volume): {pcr_data['pcr_vol']}",
        f"  Total Call OI : {pcr_data['total_call_oi']:,}",
        f"  Total Put  OI : {pcr_data['total_put_oi']:,}",
        "",
        "  " + _pcr_commentary(pcr_data["pcr_oi"]),
        "",
        "── OI ACTIVITY (near ATM strikes) ─────────────────────────────",
        _activity_summary(activities),
        "",
        "── KEY LEVELS ─────────────────────────────────────────────────",
        "  Resistance levels (top Call OI):",
    ]
    for strike, oi in sr["resistances"]:
        lines.append(f"    {strike:>8}  →  OI {oi:>10,}")
    lines.append("  Support levels (top Put OI):")
    for strike, oi in sr["supports"]:
        lines.append(f"    {strike:>8}  →  OI {oi:>10,}")
    lines += [
        "",
        "── EXPECTED RANGE ─────────────────────────────────────────────",
        _range_commentary(rng, spot, mp),
        "",
        "── NOTABLE STRIKE ACTIVITY ────────────────────────────────────",
    ]

    # Show top 5 most active strikes by OI change
    notable = sorted(
        [a for a in activities if abs(a["chg_oi"]) > 0],
        key=lambda x: abs(x["chg_oi"]),
        reverse=True,
    )[:8]
    for n in notable:
        direction = "▲" if n["chg_price"] >= 0 else "▼"
        lines.append(
            f"  {n['strike']:>8} {n['type']}  LTP={n['ltp']:>7.2f}  "
            f"ΔOI={n['chg_oi']:>+8,}  ΔPrice={n['chg_price']:>+6.2f}{direction}  "
            f"→ {n['activity']}"
        )

    lines += [
        "",
        sep,
        "  Disclaimer: For educational purposes only. Not investment advice.",
        sep,
        "",
    ]
    return "\n".join(lines)


# ─── Entry point ───────────────────────────────────────────────────────────────

def run():
    """Fetch data and print the full report.  Called by the scheduler."""
    print(f"[{datetime.datetime.now():%H:%M:%S}] Fetching Nifty option chain data …")
    try:
        raw    = fetch_option_chain()
        report = generate_report(raw)
        print(report)
    except Exception as exc:
        print(f"ERROR: {exc}")


if __name__ == "__main__":
    run()
