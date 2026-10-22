import io
import time
from datetime import datetime

import pandas as pd
import streamlit as st

from scanner_engine import run_nifty500_demand_scanner

st.set_page_config(
    page_title="Nifty 500 Demand Zone Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .main-title {font-size: 2.15rem; font-weight: 750; margin-bottom: 0.1rem;}
    .sub-title {color: #9CA3AF; margin-bottom: 1.2rem;}
    div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.25); padding: 12px; border-radius: 10px;}
    .small-note {font-size: .85rem; color: #9CA3AF;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📈 Nifty 500 Demand Zone Scanner</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Scan fresh Rally-Base-Rally (RBR) and Drop-Base-Rally (DBR) demand zones across daily, weekly, monthly, quarterly, and half-yearly charts.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Scanner settings")
    timeframe_label = st.selectbox(
        "Timeframe",
        options=["All timeframes", "Daily + Weekly", "Daily", "Weekly", "Monthly", "Quarterly", "Half-Yearly"],
        index=0,
        help="All timeframes checks Daily, Weekly, Monthly, Quarterly, and Half-Yearly candles. Quarterly and Half-Yearly candles are aggregated from monthly OHLCV data. Confluence flags overlapping zones on different timeframes.",
    )
    timeframe_map = {
        "All timeframes": "all",
        "Daily + Weekly": "both",
        "Daily": "daily",
        "Weekly": "weekly",
        "Monthly": "monthly",
        "Quarterly": "quarterly",
        "Half-Yearly": "half-yearly",
    }
    proximity_pct = st.slider(
        "Price proximity to zone (%)", min_value=0.5, max_value=10.0,
        value=3.0, step=0.5,
        help="Return zones when CMP is inside the zone or up to this percentage above its proximal line.",
    ) / 100
    min_legout_strength = st.slider(
        "Minimum leg-out strength", min_value=1.0, max_value=3.0,
        value=1.3, step=0.1,
        help="Leg-out candle range divided by the average range of recent candles.",
    )
    max_zone_age = st.number_input(
        "Maximum zone age (candles)", min_value=0, max_value=500, value=0, step=5,
        help="Set to 0 to include zones of any age. Candle count depends on the selected timeframe.",
    )
    batch_size = st.select_slider("Download batch size", options=[10, 20, 30, 40, 50, 60], value=40)
    sector_lookback = st.selectbox("Sector momentum lookback", ["1mo", "3mo", "6mo"], index=0)
    run_scan = st.button("🔎 Run scanner", type="primary", use_container_width=True)
    st.caption("Data source: Yahoo Finance and Nifty Indices constituent list.")

if "scan_results" not in st.session_state:
    st.session_state.scan_results = None
if "scan_timestamp" not in st.session_state:
    st.session_state.scan_timestamp = None

if run_scan:
    progress_text = st.empty()
    progress_bar = st.progress(0, text="Preparing scan...")
    try:
        progress_text.info("Downloading the current Nifty 500 universe and sector data. The full scan can take several minutes.")
        progress_bar.progress(10, text="Loading scanner...")
        with st.spinner("Scanning stocks and detecting fresh demand zones..."):
            results = run_nifty500_demand_scanner(
                timeframe_choice=timeframe_map[timeframe_label],
                batch_size=int(batch_size),
                proximity_pct=float(proximity_pct),
                max_zone_age=int(max_zone_age),
                min_legout_strength=float(min_legout_strength),
                sector_lookback=sector_lookback,
            )
        progress_bar.progress(100, text="Scan complete")
        progress_text.empty()
        st.session_state.scan_results = results
        st.session_state.scan_timestamp = datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
        if results is None or results.empty:
            st.warning("No fresh demand zones found near the current market price with these settings.")
        else:
            st.success(f"Scan completed. Found {len(results)} qualifying zone(s).")
    except Exception as exc:
        progress_text.empty()
        st.error(f"The scan failed: {exc}")
        st.exception(exc)

results = st.session_state.scan_results

if results is None:
    st.info("Configure the scanner in the sidebar, then click **Run scanner**. A full Nifty 500 scan may take several minutes because market data is downloaded in batches.")
    st.markdown("### What the scanner looks for")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**RBR Demand**\n\nRally → Base → Rally")
    c2.markdown("**DBR Demand**\n\nDrop → Base → Rally")
    c3.markdown("**Fresh zones only**\n\nZones previously revisited are excluded by the detector.")
    st.stop()

if results.empty:
    st.caption(f"Last scan: {st.session_state.scan_timestamp or 'Unknown'}")
    st.stop()

# Ensure the display layer doesn't mutate the stored scan result.
display_df = results.copy()
if "Sector Rank" in display_df.columns:
    display_df["Sector Rank"] = pd.to_numeric(display_df["Sector Rank"], errors="coerce")
if "Quality Score" in display_df.columns:
    display_df["Quality Score"] = pd.to_numeric(display_df["Quality Score"], errors="coerce")

st.caption(f"Last scan: {st.session_state.scan_timestamp or 'Unknown'} · Selected timeframe: {timeframe_label}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Fresh zones", f"{len(display_df):,}")
m2.metric("Stocks identified", f"{display_df['Ticker'].nunique():,}" if "Ticker" in display_df else "N/A")
m3.metric("MTF confluence", f"{int(display_df['MTF Confluence'].fillna(False).astype(bool).sum()):,}" if "MTF Confluence" in display_df else "0")
m4.metric("Average quality", f"{display_df['Quality Score'].mean():.1f}/100" if "Quality Score" in display_df else "N/A")

st.divider()
st.subheader("Filter results")
f1, f2, f3, f4 = st.columns(4)
with f1:
    timeframe_options = sorted(display_df["Timeframe"].dropna().unique().tolist()) if "Timeframe" in display_df else []
    selected_timeframes = st.multiselect("Timeframe", timeframe_options, default=timeframe_options)
with f2:
    pattern_options = sorted(display_df["Pattern"].dropna().unique().tolist()) if "Pattern" in display_df else []
    selected_patterns = st.multiselect("Pattern", pattern_options, default=pattern_options)
with f3:
    sectors = sorted(display_df["Sector"].dropna().unique().tolist()) if "Sector" in display_df else []
    selected_sectors = st.multiselect("Sector", sectors, default=[])
with f4:
    only_confluence = st.checkbox("Only MTF confluence", value=False)

filtered = display_df.copy()
if "Timeframe" in filtered:
    filtered = filtered[filtered["Timeframe"].isin(selected_timeframes)]
if "Pattern" in filtered:
    filtered = filtered[filtered["Pattern"].isin(selected_patterns)]
if selected_sectors and "Sector" in filtered:
    filtered = filtered[filtered["Sector"].isin(selected_sectors)]
if only_confluence and "MTF Confluence" in filtered:
    filtered = filtered[filtered["MTF Confluence"].fillna(False).astype(bool)]

search = st.text_input("Search ticker or sector", placeholder="e.g. RELIANCE or BANK")
if search.strip():
    search_upper = search.strip().upper()
    mask = pd.Series(False, index=filtered.index)
    for col in ["Ticker", "Sector"]:
        if col in filtered:
            mask = mask | filtered[col].astype(str).str.upper().str.contains(search_upper, na=False)
    filtered = filtered[mask]

sort_by = st.selectbox(
    "Sort results by",
    options=[c for c in ["Quality Score", "Sector Rank", "Zone Age (candles)", "Vol Rank (%)"] if c in filtered.columns],
    index=0,
)
if sort_by:
    filtered = filtered.sort_values(sort_by, ascending=(sort_by == "Zone Age (candles)"), na_position="last")

st.subheader(f"Demand zones ({len(filtered):,})")
preferred_cols = [
    "Ticker", "Timeframe", "Pattern", "Quality Score", "MTF Confluence",
    "Proximal (Entry)", "Distal (SL)", "CMP", "Distance to Zone",
    "Zone Age (candles)", "Base Candles", "Sector", "Sector Perf (1mo)",
    "Sector Rank", "Vol Rank (%)", "Vol Status",
]
columns = [c for c in preferred_cols if c in filtered.columns]
columns += [c for c in filtered.columns if c not in columns]
st.dataframe(
    filtered[columns],
    use_container_width=True,
    hide_index=True,
    height=520,
    column_config={
        "Quality Score": st.column_config.ProgressColumn("Quality Score", min_value=0, max_value=100, format="%.1f"),
        "MTF Confluence": st.column_config.CheckboxColumn("MTF Confluence"),
        "Proximal (Entry)": st.column_config.NumberColumn("Proximal (Entry)", format="₹%.2f"),
        "Distal (SL)": st.column_config.NumberColumn("Distal (SL)", format="₹%.2f"),
        "CMP": st.column_config.NumberColumn("CMP", format="₹%.2f"),
    },
)

csv_data = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Download filtered results (CSV)",
    data=csv_data,
    file_name="nifty500_demand_zones.csv",
    mime="text/csv",
    type="primary",
)

left, right = st.columns(2)
with left:
    st.subheader("Zones by timeframe")
    if "Timeframe" in filtered:
        counts = filtered["Timeframe"].value_counts().rename_axis("Timeframe").reset_index(name="Zones")
        st.bar_chart(counts.set_index("Timeframe"))
with right:
    st.subheader("Zones by pattern")
    if "Pattern" in filtered:
        counts = filtered["Pattern"].value_counts().rename_axis("Pattern").reset_index(name="Zones")
        st.bar_chart(counts.set_index("Pattern"))

if "Sector" in filtered and not filtered.empty:
    st.subheader("Sector summary")
    aggregations = {"Ticker": "nunique"}
    if "Quality Score" in filtered:
        aggregations["Quality Score"] = "mean"
    sector_summary = filtered.groupby("Sector", dropna=False).agg(aggregations).reset_index()
    sector_summary = sector_summary.rename(columns={"Ticker": "Unique Stocks", "Quality Score": "Average Quality"})
    st.dataframe(sector_summary, use_container_width=True, hide_index=True)

st.markdown("<div class='small-note'>This scanner identifies technical patterns; it does not predict guaranteed rebounds or provide personalized investment advice. Verify price data and risk levels independently before trading.</div>", unsafe_allow_html=True)
