# -*- coding: utf-8 -*-
"""
make_timeseries.py — build the NDVI time-series PoC asset (deck slides 5-6).

Pulls a real multi-date Sentinel-2 NDVI series for a field, pairs each date
with month-matched ET0 (NASA POWER), computes Kc and weekly crop-water demand,
and renders a dual-axis chart PNG + a JSON of the data.

Labels are kept in English so matplotlib (no Arabic shaping) stays clean; the
deck provides the Arabic caption.

    python mirwa/make_timeseries.py            # demo field
    python mirwa/make_timeseries.py 21.21 39.66 50
"""
import sys
import json
import datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

import sentinel2
import power_et0
import fao56

OUT = Path(__file__).resolve().parent / "screenshots"
OUT.mkdir(exist_ok=True)


def build(lat=21.2120, lon=39.6643, area_ha=50.0, months_back=12):
    print(f"fetching Sentinel-2 NDVI series for {lat},{lon} ...")
    ts = sentinel2.fetch_timeseries(lat, lon, months_back=months_back)
    if not ts:
        print("no series available"); return None
    ts = [p for p in ts if p.ndvi_active == p.ndvi_active]     # drop NaN
    print(f"  {len(ts)} scenes")

    start = dt.datetime.strptime(ts[0].date, "%Y-%m-%d").date() - dt.timedelta(days=20)
    end = dt.datetime.strptime(ts[-1].date, "%Y-%m-%d").date() + dt.timedelta(days=5)
    print("fetching NASA POWER ET0 series ...")
    et0_series = power_et0.fetch_et0_series(lat, lon, start, end)

    rows = []
    for p in ts:
        et0 = power_et0.et0_around(et0_series, p.date)
        kc = fao56.kc_single(p.ndvi_active)
        etc_day = kc * et0
        weekly_m3 = etc_day * 7 / 1000 * area_ha * 10_000
        rows.append({"date": p.date, "ndvi": p.ndvi_active, "cloud": round(p.cloud),
                     "et0": round(et0, 2), "kc": round(kc, 2),
                     "etc_mm_day": round(etc_day, 2), "weekly_m3": round(weekly_m3)})

    data = {"lat": lat, "lon": lon, "area_ha": area_ha, "rows": rows}
    (OUT / "ndvi_timeseries.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    _plot(rows, lat, lon, area_ha)
    return data


def _plot(rows, lat, lon, area_ha):
    dates = [dt.datetime.strptime(r["date"], "%Y-%m-%d") for r in rows]
    ndvi = [r["ndvi"] for r in rows]
    water = [r["weekly_m3"] for r in rows]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    fig, ax1 = plt.subplots(figsize=(10, 5.2), dpi=150)
    fig.patch.set_facecolor("white")

    c_ndvi, c_water = "#2f9e44", "#1565c0"
    ax1.plot(dates, ndvi, "-o", color=c_ndvi, lw=2.4, ms=6, label="NDVI (active crop)")
    ax1.set_ylabel("NDVI", color=c_ndvi, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=c_ndvi)
    ax1.set_ylim(0, 1.0)
    ax1.grid(True, alpha=.25)

    ax2 = ax1.twinx()
    ax2.plot(dates, water, "--s", color=c_water, lw=2, ms=5,
             label=f"Weekly water demand ({area_ha:g} ha)")
    ax2.set_ylabel("Weekly crop-water demand  (m³)", color=c_water, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor=c_water)
    ax2.set_ylim(0, max(water) * 1.25)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    fig.autofmt_xdate(rotation=30)

    fig.suptitle("Mirwa — Sentinel-2 NDVI time series  →  crop-water demand (FAO-56)",
                 fontweight="bold", fontsize=13, y=0.98)
    ax1.set_title(f"Field {lat:.4f}°N, {lon:.4f}°E · Makkah region · "
                  f"ETc = Kc(NDVI) × ET0(NASA POWER)", fontsize=9.5, color="#5a6b85")

    l1, la1 = ax1.get_legend_handles_labels()
    l2, la2 = ax2.get_legend_handles_labels()
    ax1.legend(l1 + l2, la1 + la2, loc="upper left", fontsize=9, framealpha=.9)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    path = OUT / "ndvi_timeseries.png"
    fig.savefig(path, bbox_inches="tight")
    print("saved", path)


if __name__ == "__main__":
    a = sys.argv[1:]
    lat = float(a[0]) if len(a) > 0 else 21.2120
    lon = float(a[1]) if len(a) > 1 else 39.6643
    area = float(a[2]) if len(a) > 2 else 50.0
    d = build(lat, lon, area)
    if d:
        for r in d["rows"]:
            print(r["date"], "NDVI", r["ndvi"], "ET0", r["et0"], "weekly_m3", f"{r['weekly_m3']:,}")
