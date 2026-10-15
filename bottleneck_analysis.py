"""
Project 3: Operational Efficiency & Supply Chain Bottleneck Analysis
---------------------------------------------------------------------
Exploratory data analysis of order-fulfilment logs to find where time is lost
and to measure OTIF (On-Time In-Full).

Usage
-----
    python bottleneck_analysis.py                    # synthetic sample data
    python bottleneck_analysis.py --input logs.csv   # your own delivery logs

Expected CSV columns:
    order_id, warehouse, region, carrier,
    order_ts, picked_ts, packed_ts, shipped_ts, delivered_ts, promised_ts,
    qty_ordered, qty_shipped

Outputs (folder `output/`):
    fulfilment_enriched.csv  and  PNG charts
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # render to files; no display required
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

OUTPUT_DIR = Path("output")
SEED = 42
sns.set_theme(style="whitegrid")

TS_COLS = ["order_ts", "picked_ts", "packed_ts", "shipped_ts", "delivered_ts", "promised_ts"]


# --------------------------------------------------------------------------
# 1. Synthetic data generator (built-in bottlenecks to discover)
# --------------------------------------------------------------------------
def generate_sample_data(n: int = 3000) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)

    warehouses = rng.choice(["Nairobi", "Mombasa", "Kisumu"], n, p=[0.5, 0.3, 0.2])
    regions = rng.choice(["Central", "Coast", "Western", "North"], n, p=[0.35, 0.25, 0.25, 0.15])
    carriers = rng.choice(["SwiftHaul", "RapidTrans", "EcoMove"], n, p=[0.4, 0.35, 0.25])

    order_ts = pd.Timestamp("2026-01-01") + pd.to_timedelta(rng.integers(0, 24 * 150, n), unit="h")

    # Hidden bottlenecks: Mombasa picking is slow; EcoMove waits long for pickup; North transit is long
    pick_h = rng.gamma(2.0, 2.0, n) + np.where(warehouses == "Mombasa", 6, 0)
    pack_h = rng.gamma(2.0, 1.5, n)
    wait_h = rng.gamma(2.0, 3.0, n) + np.where(carriers == "EcoMove", 10, 0)
    transit_base = pd.Series(regions).map({"Central": 14, "Coast": 22, "Western": 26, "North": 40}).to_numpy()
    transit_h = transit_base + rng.gamma(2.0, 4.0, n)

    picked = order_ts + pd.to_timedelta(pick_h, unit="h")
    packed = picked + pd.to_timedelta(pack_h, unit="h")
    shipped = packed + pd.to_timedelta(wait_h, unit="h")
    delivered = shipped + pd.to_timedelta(transit_h, unit="h")
    promised = order_ts + pd.to_timedelta(pd.Series(regions).map(
        {"Central": 48, "Coast": 60, "Western": 72, "North": 96}).to_numpy(), unit="h")

    qty_ordered = rng.integers(1, 20, n)
    short = rng.random(n) < 0.07  # 7% of orders shipped short
    qty_shipped = np.where(short, np.maximum(qty_ordered - rng.integers(1, 4, n), 0), qty_ordered)

    return pd.DataFrame({
        "order_id": np.arange(1, n + 1), "warehouse": warehouses, "region": regions, "carrier": carriers,
        "order_ts": order_ts, "picked_ts": picked, "packed_ts": packed, "shipped_ts": shipped,
        "delivered_ts": delivered, "promised_ts": promised,
        "qty_ordered": qty_ordered, "qty_shipped": qty_shipped,
    })


# --------------------------------------------------------------------------
# 2. Clean + feature engineering
# --------------------------------------------------------------------------
def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in TS_COLS:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    df = df.drop_duplicates(subset="order_id")
    before = len(df)
    df = df.dropna(subset=TS_COLS)
    # Remove impossible sequences (a later stage timestamped before an earlier one)
    ordered = (df["order_ts"] <= df["picked_ts"]) & (df["picked_ts"] <= df["packed_ts"]) \
        & (df["packed_ts"] <= df["shipped_ts"]) & (df["shipped_ts"] <= df["delivered_ts"])
    df = df[ordered]
    print(f"Rows kept after cleaning: {len(df):,} of {before:,}")

    hours = lambda a, b: (df[b] - df[a]).dt.total_seconds() / 3600
    df["pick_hrs"] = hours("order_ts", "picked_ts")
    df["pack_hrs"] = hours("picked_ts", "packed_ts")
    df["dispatch_wait_hrs"] = hours("packed_ts", "shipped_ts")
    df["transit_hrs"] = hours("shipped_ts", "delivered_ts")
    df["total_hrs"] = hours("order_ts", "delivered_ts")

    df["on_time"] = df["delivered_ts"] <= df["promised_ts"]
    df["in_full"] = df["qty_shipped"] >= df["qty_ordered"]
    df["otif"] = df["on_time"] & df["in_full"]
    df["order_week"] = df["order_ts"].dt.to_period("W").dt.start_time
    return df


# --------------------------------------------------------------------------
# 3. Analysis
# --------------------------------------------------------------------------
STAGES = ["pick_hrs", "pack_hrs", "dispatch_wait_hrs", "transit_hrs"]


def report(df: pd.DataFrame) -> None:
    print("\n=== KPI SUMMARY ===")
    print(f"Orders analysed : {len(df):,}")
    print(f"On-time %       : {df['on_time'].mean() * 100:5.1f}")
    print(f"In-full %       : {df['in_full'].mean() * 100:5.1f}")
    print(f"OTIF %          : {df['otif'].mean() * 100:5.1f}")
    print(f"Avg lead time   : {df['total_hrs'].mean():5.1f} hrs (P90 {df['total_hrs'].quantile(.9):.1f})")

    stage_share = df[STAGES].mean()
    print("\n=== AVERAGE HOURS BY STAGE ===")
    print(pd.DataFrame({"avg_hrs": stage_share.round(1), "share_%": (stage_share / stage_share.sum() * 100).round(1)}))

    for dim in ["warehouse", "carrier", "region"]:
        print(f"\n=== BY {dim.upper()} ===")
        print(df.groupby(dim).agg(
            orders=("order_id", "count"),
            avg_total_hrs=("total_hrs", "mean"),
            otif_pct=("otif", lambda s: s.mean() * 100),
        ).round(1).sort_values("avg_total_hrs", ascending=False))


# --------------------------------------------------------------------------
# 4. Charts
# --------------------------------------------------------------------------
def make_charts(df: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    # 1. Stage breakdown
    fig, ax = plt.subplots(figsize=(7, 4))
    df[STAGES].mean().rename(lambda s: s.replace("_hrs", "").replace("_", " ").title()).plot.bar(ax=ax, color="#2dd4bf")
    ax.set(title="Average hours spent per fulfilment stage", ylabel="Hours")
    plt.xticks(rotation=0); fig.tight_layout(); fig.savefig(OUTPUT_DIR / "01_stage_breakdown.png", dpi=150); plt.close(fig)

    # 2. Distribution of total lead time by warehouse
    fig, ax = plt.subplots(figsize=(7, 4))
    sns.boxplot(data=df, x="warehouse", y="total_hrs", ax=ax, color="#60a5fa")
    ax.set(title="Order-to-delivery time by warehouse", ylabel="Hours")
    fig.tight_layout(); fig.savefig(OUTPUT_DIR / "02_lead_time_by_warehouse.png", dpi=150); plt.close(fig)

    # 3. Pick time heatmap: warehouse x carrier dispatch wait
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    sns.heatmap(df.pivot_table(index="warehouse", columns="region", values="total_hrs"), annot=True, fmt=".0f", cmap="YlOrRd", ax=axes[0])
    axes[0].set_title("Avg total hours: warehouse x region")
    sns.heatmap(df.pivot_table(index="carrier", columns="warehouse", values="dispatch_wait_hrs"), annot=True, fmt=".1f", cmap="YlOrRd", ax=axes[1])
    axes[1].set_title("Avg dispatch wait (hrs): carrier x warehouse")
    fig.tight_layout(); fig.savefig(OUTPUT_DIR / "03_bottleneck_heatmaps.png", dpi=150); plt.close(fig)

    # 4. OTIF by carrier
    fig, ax = plt.subplots(figsize=(7, 4))
    (df.groupby("carrier")["otif"].mean() * 100).sort_values().plot.barh(ax=ax, color="#2dd4bf")
    ax.axvline(95, color="red", ls="--", label="95% target"); ax.legend()
    ax.set(title="OTIF % by carrier", xlabel="OTIF %")
    fig.tight_layout(); fig.savefig(OUTPUT_DIR / "04_otif_by_carrier.png", dpi=150); plt.close(fig)

    # 5. Weekly OTIF trend
    weekly = df.groupby("order_week")["otif"].mean() * 100
    fig, ax = plt.subplots(figsize=(8, 4))
    weekly.plot(ax=ax, marker="o", color="#60a5fa")
    ax.set(title="Weekly OTIF % trend", ylabel="OTIF %", xlabel="")
    fig.tight_layout(); fig.savefig(OUTPUT_DIR / "05_weekly_otif_trend.png", dpi=150); plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Supply chain bottleneck EDA")
    parser.add_argument("--input", help="CSV of delivery logs")
    args = parser.parse_args()

    raw = pd.read_csv(args.input) if args.input else generate_sample_data()
    df = prepare(raw)
    report(df)
    make_charts(df)

    OUTPUT_DIR.mkdir(exist_ok=True)
    df.to_csv(OUTPUT_DIR / "fulfilment_enriched.csv", index=False)
    print(f"\nSaved enriched data and charts to {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
