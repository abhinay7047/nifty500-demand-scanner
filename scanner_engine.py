# =============================================================================
# Nifty 500 Demand Zone Scanner  (Colab / Jupyter notebook version)
# =============================================================================
# Scans all ~500 Nifty 500 stocks (daily and/or weekly) for Rally-Base-Rally
# (RBR) and Drop-Base-Rally (DBR) demand zones -- areas where price rallied
# hard off a base and is expected to bounce if it returns there -- and
# flags zones where the current market price (CMP) is inside or within a
# configurable proximity of the zone's proximal line (from above).
#
# Only FRESH zones are returned: a zone is fresh if price has never
# re-entered it since it formed -- the current approach is the first test.
# Zones that have already been retested are skipped automatically.
#
# Run this as a single Colab cell (no command-line args needed -- just
# edit the CONFIG values below).
# =============================================================================

# ---- Install dependencies (uncomment the first time you run this in Colab) --
# !pip install pandas yfinance requests -q

import io
import time
import pandas as pd
import yfinance as yf

# =============================================================================
# CONFIG -- edit these values directly, then just run the cell
# =============================================================================
TIMEFRAME = "all"        # "daily", "weekly", "monthly", "both" (daily+weekly), or "all" (all 3)
BATCH_SIZE = 40         # tickers per yfinance batch call (30-60 is a safe range)
PROXIMITY_PCT = 0.03    # flag zones within this % of the proximal line (0.03 = 3%)
MAX_ZONE_AGE = 0        # only show zones formed within this many candles (0 = no limit)
MIN_LEGOUT_STRENGTH = 1.3   # legout candle range must be >= this many times the recent
                             # average candle range (filters out weak/noise legouts)
SECTOR_LOOKBACK = "1mo"     # window for sector momentum: "1mo", "3mo", "6mo"
OUTPUT_CSV = "nifty500_demand_zones.csv"
# =============================================================================

# NSE Industry -> Nifty Sector Index on Yahoo Finance proxy for momentum
SECTOR_INDEX_MAP = {
    "INFORMATION TECHNOLOGY": "^CNXIT",
    "FINANCIAL SERVICES": "^NSEBANK",
    "HEALTHCARE": "^CNXPHARMA",
    "HEALTHCARE SERVICES": "^CNXPHARMA",
    "PHARMA": "^CNXPHARMA",
    "FAST MOVING CONSUMER GOODS": "^CNXFMCG",
    "CONSUMER GOODS": "^CNXFMCG",
    "CONSUMER DURABLES": "^CNXFMCG",
    "AUTOMOBILE AND AUTO COMPONENTS": "^CNXAUTO",
    "AUTOMOBILE": "^CNXAUTO",
    "METALS & MINING": "^CNXMETAL",
    "METALS": "^CNXMETAL",
    "OIL GAS & CONSUMABLE FUELS": "^CNXENERGY",
    "ENERGY": "^CNXENERGY",
    "POWER": "^CNXENERGY",
    "REAL ESTATE": "^CNXREALTY",
    "REALTY": "^CNXREALTY",
    "CONSTRUCTION": "^CNXINFRA",
    "CONSTRUCTION MATERIALS": "^CNXINFRA",
    "CEMENT & CEMENT PRODUCTS": "^CNXINFRA",
    "MEDIA": "^CNXMEDIA",
    "TELECOMMUNICATION": "^CNXMEDIA",
}

def get_nifty500_universe():
    """
    Fetch the live list of Nifty 500 symbols AND their Industry sector.
    Now uses the official and actively updated niftyindices.com source.
    """
    import requests
    import io

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,application/csv,text/html,*/*",
    }

    df = None
    try:
        # The official, up-to-date source for Nifty Indices
        url = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        print("we are fatching data from nse")
    except Exception as e:
        print(f"Primary fetch failed ({e}). Attempting fallback to NSE archives...")
        try:
            url_fallback = "https://archives.nseindia.com/content/equities/ind_nifty500list.csv"
            resp = requests.get(url_fallback, headers=headers, timeout=15)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
        except Exception as e2:
            print(f"Fallback fetch also failed ({e2}). Please check your internet connection.")
            return [], {}

    # yfinance requires '.NS' for National Stock Exchange of India tickers
    df["Symbol"] = df["Symbol"].astype(str).str.strip() + ".NS"
    tickers = df["Symbol"].tolist()

    sector_col = "Industry" if "Industry" in df.columns else None

    # Clean up sector names for mapping (uppercase, stripped)
    if sector_col:
        df[sector_col] = df[sector_col].astype(str).str.upper().str.strip()
        sector_map = dict(zip(df["Symbol"], df[sector_col]))
    else:
        sector_map = {}

    return tickers, sector_map

def get_nifty500_universe():
    """
    Fetch the live list of Nifty 500 symbols AND their Industry sector.
    Now uses the official and actively updated niftyindices.com source.
    """
    import requests
    import io

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/csv,application/csv,text/html,*/*",
    }

    df = None
    try:
        # The official, up-to-date source for Nifty Indices
        url = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
    except Exception as e:
        print(f"Primary fetch failed ({e}). Attempting fallback to NSE archives...")
        try:
            url_fallback = "https://archives.nseindia.com/content/equities/ind_nifty500list.csv"
            resp = requests.get(url_fallback, headers=headers, timeout=15)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
        except Exception as e2:
            print(f"Fallback fetch also failed ({e2}). Please check your internet connection.")
            return [], {}

    # yfinance requires '.NS' for National Stock Exchange of India tickers
    df["Symbol"] = df["Symbol"].astype(str).str.strip() + ".NS"
    tickers = df["Symbol"].tolist()

    sector_col = "Industry" if "Industry" in df.columns else None

    # Clean up sector names for mapping (uppercase, stripped)
    if sector_col:
        df[sector_col] = df[sector_col].astype(str).str.upper().str.strip()
        sector_map = dict(zip(df["Symbol"], df[sector_col]))
    else:
        sector_map = {}

    return tickers, sector_map


def get_sector_performance(lookback="1mo"):
    """
    Fetch performance of the major Nifty Sector Indices over `lookback` and rank
    them. Returns {sector_name: {"perf_pct": float, "rank": int}}, where
    rank 1 = strongest-performing sector.
    """
    index_tickers = list(set(SECTOR_INDEX_MAP.values()))
    try:
        data = yf.download(
            index_tickers, period=lookback, interval="1d",
            group_by="ticker", threads=True, progress=False, auto_adjust=True,
        )
    except Exception as e:
        print(f"Sector Index fetch failed ({e}); sector performance will be omitted.")
        return {}

    perf = {}
    for ind_name, ticker in SECTOR_INDEX_MAP.items():
        try:
            if isinstance(data.columns, pd.MultiIndex):
                closes = data[ticker]["Close"].dropna()
            else:
                closes = data["Close"].dropna()
            if len(closes) < 2:
                continue
            pct = (closes.iloc[-1] / closes.iloc[0] - 1) * 100
            perf[ind_name] = float(pct)
        except Exception:
            continue

    # Rank sectors by performance, strongest = rank 1
    # Ensures duplicate scores (due to mapping to the same index) get the same rank
    ranked = sorted(perf.items(), key=lambda kv: kv[1], reverse=True)
    results = {}
    current_rank = 1
    last_pct = None

    for i, (name, pct) in enumerate(ranked):
        if last_pct is not None and pct < last_pct:
            current_rank += 1
        results[name] = {"perf_pct": round(pct, 2), "rank": current_rank}
        last_pct = pct

    return results


def calculate_zone_quality(legout_strength_ratio, base_avg_range, legout_range,
                           zone_age, num_base, max_base_candles=4, max_age_for_score=60):
    """
    Composite 0-100 quality score for a zone, blending four factors that
    traders commonly use to judge zone reliability:

    - Legout Strength (40 pts): how explosive the move out of the base was,
      relative to normal volatility. Ratio of 2.5x+ average range = full marks.
    - Base Tightness (30 pts): how small the base candles are relative to
      the legout -- a tight, controlled base implies a cleaner imbalance.
    - Freshness/Age (20 pts): newer zones score higher; decays linearly out
      to `max_age_for_score` candles old.
    - Base Candle Count (10 pts): fewer base candles = a sharper, more
      decisive reversal (1-candle base scores highest).
    """
    legout_score = min(legout_strength_ratio / 2.5, 1.0) * 40

    if legout_range > 0:
        tightness = 1.0 - min(base_avg_range / legout_range, 1.0)
    else:
        tightness = 0.0
    tightness_score = tightness * 30

    age_score = max(0.0, 1.0 - (zone_age / max_age_for_score)) * 20

    base_count_score = ((max_base_candles - num_base + 1) / max_base_candles) * 10

    total = legout_score + tightness_score + age_score + base_count_score
    return round(min(total, 100.0), 1)


def detect_demand_zones(df, ticker, timeframe="Daily", max_base_candles=4,
                         proximity_pct=0.03, max_zone_age=0, min_legout_strength=1.3):
    """
    Identifies Demand Zones (RBR / DBR) and checks if CMP is near/inside the zone.
    Includes Volatility Rank categorization for Options Traders.
    """
    if df is None or len(df) < 25: # Need slightly more data for Volatility rolling windows
        return []

    # Flatten MultiIndex columns if present (yfinance sometimes returns these)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.copy()
    df["Range"] = df["High"] - df["Low"]
    df["Body"] = (df["Close"] - df["Open"]).abs()

    # --- VOLATILITY RANK CALCULATION ---
    # Calculate 20-period annualized historical volatility
    df["Returns"] = df["Close"].pct_change()
    df["Vol_20"] = df["Returns"].rolling(window=20).std() * (252 ** 0.5)

    # Calculate rank based on the lookback period (min/max of the Volatility)
    current_vol = df["Vol_20"].iloc[-1]
    min_vol = df["Vol_20"].min()
    max_vol = df["Vol_20"].max()

    if pd.isna(current_vol) or max_vol == min_vol:
        vol_rank = 50.0 # Fallback if data is flat/missing
    else:
        vol_rank = ((current_vol - min_vol) / (max_vol - min_vol)) * 100

    # Categorize into High, Intermediate, Low (Standard Options IVR thresholds)
    if vol_rank > 70:
        vol_status = "High"
    elif vol_rank < 30:
        vol_status = "Low"
    else:
        vol_status = "Intermediate"
    # -----------------------------------

    # Candle definitions
    df["Is_Base"] = df["Body"] <= (0.50 * df["Range"])
    df["Is_Bear_Leg"] = (df["Body"] > (0.50 * df["Range"])) & (df["Close"] < df["Open"])
    df["Is_Bull_Leg"] = (df["Body"] > (0.50 * df["Range"])) & (df["Close"] > df["Open"])

    cmp_price = float(df["Close"].iloc[-1])
    active_zones = []

    # Iterate over recent price action (excluding the last unclosed candle)
    for i in range(5, len(df) - 1):
        if not df["Is_Bull_Leg"].iloc[i]:
            continue

        baseline_window = df["Range"].iloc[max(0, i - 20):i]
        if len(baseline_window) < 5:
            continue

        avg_range = baseline_window.mean()
        legout_range = df["Range"].iloc[i]
        legout_strength_ratio = (legout_range / avg_range) if avg_range > 0 else 0

        if legout_strength_ratio < min_legout_strength:
            continue

        for num_base in range(1, max_base_candles + 1):
            base_start_idx = i - num_base
            if base_start_idx < 1:
                break

            base_candles = df.iloc[base_start_idx:i]
            if not base_candles["Is_Base"].all():
                continue

            leg_in_idx = base_start_idx - 1
            is_dbr = df["Is_Bear_Leg"].iloc[leg_in_idx]
            is_rbr = df["Is_Bull_Leg"].iloc[leg_in_idx]

            if not (is_dbr or is_rbr):
                continue

            proximal_line = float(max(base_candles["Open"].max(), base_candles["Close"].max()))
            distal_line = float(base_candles["Low"].min())
            pattern_type = "RBR Demand" if is_rbr else "DBR Demand"

            subsequent_candles = df.iloc[i + 1:]
            if len(subsequent_candles) > 0 and subsequent_candles["Low"].min() < distal_line:
                continue

            prior_candles = df.iloc[i + 1: len(df) - 1]
            zone_already_tested = (
                len(prior_candles) > 0 and prior_candles["Low"].min() <= proximal_line
            )
            if zone_already_tested:
                continue

            zone_age = (len(df) - 1) - i
            if max_zone_age and zone_age > max_zone_age:
                continue

            upper_bound = proximal_line * (1 + proximity_pct)
            if distal_line <= cmp_price <= upper_bound:
                quality_score = calculate_zone_quality(
                    legout_strength_ratio=legout_strength_ratio,
                    base_avg_range=float(base_candles["Range"].mean()),
                    legout_range=float(legout_range),
                    zone_age=zone_age,
                    num_base=num_base,
                    max_base_candles=max_base_candles,
                )
                active_zones.append({
                    "Ticker": ticker,
                    "Timeframe": timeframe,
                    "Pattern": pattern_type,
                    "Base Candles": num_base,
                    "Zone Age (candles)": zone_age,
                    "Quality Score": quality_score,
                    "MTF Confluence": False,
                    "Proximal (Entry)": round(proximal_line, 2),
                    "Distal (SL)": round(distal_line, 2),
                    "CMP": round(cmp_price, 2),
                    "Distance to Zone": f"{((proximal_line - cmp_price) / cmp_price * 100):.2f}%",
                    "Vol Rank (%)": round(vol_rank, 1),
                    "Vol Status": vol_status, # <--- Added for options traders
                })
                break

    return active_zones
def fetch_batch(tickers, period, interval):
    """
    Download OHLC data for a batch of tickers in ONE yfinance call
    """
    try:
        data = yf.download(
            tickers,
            period=period,
            interval=interval,
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=True,
        )
    except Exception as e:
        print(f"  Batch download failed ({e}), skipping this batch.")
        return {}

    results = {}

    if isinstance(data.columns, pd.MultiIndex):
        available = set(data.columns.get_level_values(0))
        for t in tickers:
            if t not in available:
                continue
            sub = data[t].dropna(how="all")
            if not sub.empty:
                results[t] = sub
    else:
        if len(tickers) == 1 and not data.empty:
            results[tickers[0]] = data.dropna(how="all")

    return results


def add_mtf_confluence(df_results):
    """
    Marks MTF Confluence when a zone overlaps a zone for the same ticker
    on any other timeframe (Daily, Weekly, or Monthly).
    """
    if df_results.empty or "Timeframe" not in df_results.columns:
        return df_results

    df_results = df_results.copy()
    df_results["MTF Confluence"] = False

    for ticker in df_results["Ticker"].unique():
        ticker_rows = df_results[df_results["Ticker"] == ticker]
        rows = list(ticker_rows.iterrows())

        for i, (idx_a, row_a) in enumerate(rows):
            lo_a = min(row_a["Distal (SL)"], row_a["Proximal (Entry)"])
            hi_a = max(row_a["Distal (SL)"], row_a["Proximal (Entry)"])

            for idx_b, row_b in rows[i + 1:]:
                if row_a["Timeframe"] == row_b["Timeframe"]:
                    continue

                lo_b = min(row_b["Distal (SL)"], row_b["Proximal (Entry)"])
                hi_b = max(row_b["Distal (SL)"], row_b["Proximal (Entry)"])

                if lo_a <= hi_b and lo_b <= hi_a:
                    df_results.loc[idx_a, "MTF Confluence"] = True
                    df_results.loc[idx_b, "MTF Confluence"] = True

    return df_results


def run_nifty500_demand_scanner(timeframe_choice="both", batch_size=40,
                              proximity_pct=0.03, max_zone_age=0,
                              min_legout_strength=1.3, sector_lookback="1mo"):
    tickers, sector_map = get_nifty500_universe()
    print(f"Scanning {len(tickers)} Nifty 500 stocks ({timeframe_choice}, fresh zones only)...")

    print("Fetching sector index performance...")
    sector_perf = get_sector_performance(lookback=sector_lookback)
    if sector_perf:
        ranked_preview = sorted(sector_perf.items(), key=lambda kv: kv[1]["rank"])

        # Deduplicate names just for the preview printout
        seen_ranks = set()
        unique_top = []
        for name, d in ranked_preview:
            if d["rank"] not in seen_ranks:
                seen_ranks.add(d["rank"])
                unique_top.append(f"{name} ({d['perf_pct']:+.1f}%)")
            if len(unique_top) == 3: break

        preview = ", ".join(unique_top)
        print(f"  Top sectors ({sector_lookback}): {preview}")

    timeframe_specs = []
    if timeframe_choice in ["daily", "both", "all"]:
        timeframe_specs.append(("1d", "Daily", "1y"))
    if timeframe_choice in ["weekly", "both", "all"]:
        timeframe_specs.append(("1wk", "Weekly", "2y"))
    if timeframe_choice in ["monthly", "all"]:
        timeframe_specs.append(("1mo", "Monthly", "10y"))

    start_time = time.time()
    results = []

    for interval, label, period in timeframe_specs:
        num_batches = (len(tickers) + batch_size - 1) // batch_size
        for b in range(num_batches):
            batch = tickers[b * batch_size:(b + 1) * batch_size]
            print(f"  [{label}] batch {b + 1}/{num_batches} ({len(batch)} tickers)...")
            batch_data = fetch_batch(batch, period=period, interval=interval)

            for ticker, df in batch_data.items():
                zones = detect_demand_zones(
                    df, ticker, timeframe=label,
                    proximity_pct=proximity_pct, max_zone_age=max_zone_age,
                    min_legout_strength=min_legout_strength,
                )
                if not zones:
                    continue

                # Attach sector context to each zone
                sector_name = sector_map.get(ticker, "Unknown")
                sinfo = sector_perf.get(sector_name, {})
                for z in zones:
                    z["Sector"] = sector_name
                    z[f"Sector Perf ({sector_lookback})"] = sinfo.get("perf_pct")
                    z["Sector Rank"] = sinfo.get("rank")

                results.extend(zones)

            time.sleep(1)  # be polite to Yahoo's API between batches

    df_results = pd.DataFrame(results)

    if timeframe_choice in ("both", "all"):
        df_results = add_mtf_confluence(df_results)

    print(f"\nScan completed in {round(time.time() - start_time, 2)} seconds.")

    return df_results
