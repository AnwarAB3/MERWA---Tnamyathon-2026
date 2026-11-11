"""
report.py — assemble the per-field decision object for مرواء and run the
end-to-end proof-of-concept on one field.

Decision output (the artifact the deck needs):
  * weekly crop water requirement  (ETc, mm and m3)
  * recommended net irrigation
  * avoidable waste  (vs an irrigation-efficiency estimate — labelled)
  * idle / bare land in the scene
All numbers are labelled measured / modelled / estimated. Citations inline.
"""
from __future__ import annotations
import json
import datetime as dt
import numpy as np
from PIL import Image

import fao56
import power_et0
import ndvi_image

# --------------------------------------------------------------------------
# Cited reference figures (never invented). Each has a source string.
# --------------------------------------------------------------------------
CITATIONS = {
    "ag_share_water": {
        "value_pct": 84,
        "text": "Agriculture = 84% of KSA total water requirements; "
                "non-renewable groundwater = 90% of water supplied to agriculture.",
        "source": "Ministry of Environment, Water & Agriculture (MEWA), Water Agency.",
    },
    "ag_water_volume_2023": {
        "value_mm3_yr": 12298,
        "nonrenewable_mm3_yr": 9356,
        "text": "Agriculture used 12,298 million m3 in 2023 (largest consumer); "
                "non-renewable groundwater use 9,356 million m3 (-7% vs 2022).",
        "source": "GASTAT Water Accounts 2023 (via Arab News, 2024).",
    },
    "irrigation_efficiency": {
        "value_pct": 50,
        "best_practice_pct": 85,
        "text": "Irrigation often ~50% efficient vs ~85% global best practice "
                "(indicative, non-official — flag as unverified).",
        "source": "FEWS NET, Kingdom of Saudi Arabia country page.",
    },
    "ndvi_kc": {
        "text": "NDVI->Kcb via fraction-of-cover (SIMS); Kcb_full=1.10, "
                "NDVI_min=0.15, NDVI_max=0.90.",
        "source": "Allen & Pereira (2009); Calera et al. (2017); FAO-56.",
    },
    "et0": {
        "text": "ET0 = FAO-56 Penman-Monteith from NASA POWER daily reanalysis "
                "meteorology (observational, NOT a forecast).",
        "source": "Allen et al. (1998) FAO-56; NASA POWER (power.larc.nasa.gov).",
    },
}


def run_field(lat: float, lon: float, ndvi_image_path: str,
              area_ha: float = 50.0, place_label: str = "",
              out_dir: str = ".") -> dict:
    # 1) ET0 — live, measured/reanalysis
    et = power_et0.fetch_et0(lat, lon)

    # 2) NDVI — proxy recovered from the Sentinel-2 NDVI composite
    stats = ndvi_image.analyse(ndvi_image_path)
    ndvi_active = round(stats.active_crop_mean_ndvi, 3)

    # 3) ETc for the measured active-crop NDVI + a vigour sensitivity band
    def demand(ndvi):
        return fao56.etc(ndvi, et.et0_mean_mm_day, area_ha, pe_mm_week=0.0)

    d_main = demand(ndvi_active)
    d_low = demand(0.45)   # sparse / early crop
    d_high = demand(0.75)  # vigorous full-cover pivot

    # 4) Waste illustration from cited irrigation efficiency (field level)
    eff = CITATIONS["irrigation_efficiency"]["value_pct"] / 100.0        # 0.50
    best = CITATIONS["irrigation_efficiency"]["best_practice_pct"] / 100.0  # 0.85
    applied_now = d_main.net_irrig_m3_week / eff          # gross at ~50% eff
    applied_best = d_main.net_irrig_m3_week / best        # gross at best practice
    avoidable_m3_wk = applied_now - applied_best          # reachable saving
    avoidable_pct = (1 - eff / best) * 100

    report = {
        "field": {
            "lat": lat, "lon": lon, "place": place_label,
            "elevation_m": round(et.elevation_m, 1),
            "area_ha": area_ha,
            "area_note": "representative pivot area; use drawn boundary in production",
        },
        "satellite_ndvi": {
            "source": "Sentinel-2 NDVI composite (proxy recovered from colour ramp; "
                      "production uses raw B4/B8: NDVI=(B8-B4)/(B8+B4))",
            "active_crop_mean_ndvi": ndvi_active,
            "scene_active_crop_pct": round(stats.active_fraction * 100, 1),
            "scene_bare_fallow_pct": round(stats.bare_fraction * 100, 1),
            "scene_sparse_other_pct": round(
                (1 - stats.active_fraction - stats.bare_fraction) * 100, 1),
            "idle_land_note": "scene-level bare/fallow share (fully-tan pivots + "
                              "harvested sectors); per-field idle area needs the "
                              "field boundary",
        },
        "et0_measured": {
            "mm_day": round(et.et0_mean_mm_day, 2),
            "range_mm_day": [round(et.et0_min_mm_day, 2), round(et.et0_max_mm_day, 2)],
            "window": f"{et.start}..{et.end} ({et.n_days} days)",
            "tmean_c": round(et.tmean_mean_c, 1), "rh_pct": round(et.rh_mean_pct, 0),
            "label": "measured/reanalysis (NASA POWER)",
        },
        "water_demand_modelled": {
            "kc": round(d_main.kc, 3),
            "etc_mm_day": round(d_main.etc_mm_day, 2),
            "etc_mm_week": round(d_main.etc_mm_week, 1),
            "weekly_demand_m3": round(d_main.weekly_demand_m3),
            "weekly_demand_m3_per_ha": round(d_main.weekly_demand_m3 / area_ha),
            "sensitivity": {
                "ndvi0.45_sparse_m3_wk": round(d_low.weekly_demand_m3),
                "ndvi0.75_vigorous_m3_wk": round(d_high.weekly_demand_m3),
            },
            "label": "modelled (NDVI->Kc->ETc, FAO-56)",
        },
        "waste_estimate": {
            "method": "gross applied = net demand / irrigation efficiency",
            "efficiency_now_pct": 50, "best_practice_pct": 85,
            "est_applied_now_m3_wk": round(applied_now),
            "est_applied_best_m3_wk": round(applied_best),
            "avoidable_m3_wk": round(avoidable_m3_wk),
            "avoidable_pct_of_applied": round(avoidable_pct, 1),
            "label": "ESTIMATE — no field flow-meter; efficiency figure indicative",
        },
        "citations": CITATIONS,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
    }

    # classified NDVI image for the deck (real asset from the provided scene)
    _write_classification_png(ndvi_image_path, f"{out_dir}/ndvi_classified.png")
    with open(f"{out_dir}/field_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def _write_classification_png(src_path: str, out_path: str):
    """Active crop (green) / sparse (yellow) / bare-fallow (tan) / off (grey)."""
    ndvi = ndvi_image.recover_ndvi(src_path)
    H, W = ndvi.shape
    out = np.full((H, W, 3), 200, np.uint8)      # grey = off-ramp
    valid = ~np.isnan(ndvi)
    out[valid & (ndvi < 0.25)] = (214, 199, 145)          # bare / fallow
    out[valid & (ndvi >= 0.25) & (ndvi < 0.45)] = (242, 221, 110)  # sparse
    out[valid & (ndvi >= 0.45)] = (49, 140, 70)           # active crop
    Image.fromarray(out).save(out_path)


def pretty(report: dict) -> str:
    f = report["field"]; s = report["satellite_ndvi"]
    e = report["et0_measured"]; w = report["water_demand_modelled"]
    wa = report["waste_estimate"]
    L = []
    L.append("=" * 68)
    L.append("  مرواء (MIRWA) — per-field water decision  [PROOF OF CONCEPT]")
    L.append("=" * 68)
    L.append(f"Field   : {f['lat']}, {f['lon']}  {f['place']}  (elev {f['elevation_m']} m)")
    L.append(f"Area    : {f['area_ha']} ha  ({f['area_note']})")
    L.append("")
    L.append("SATELLITE  (Sentinel-2 NDVI composite — proxy, see note)")
    L.append(f"  active-crop mean NDVI : {s['active_crop_mean_ndvi']}")
    L.append(f"  scene cover           : active {s['scene_active_crop_pct']}% | "
             f"bare/fallow {s['scene_bare_fallow_pct']}% | "
             f"sparse {s['scene_sparse_other_pct']}%")
    L.append("")
    L.append(f"ET0  [measured, NASA POWER, {e['window']}]")
    L.append(f"  {e['mm_day']} mm/day (range {e['range_mm_day'][0]}-{e['range_mm_day'][1]}) "
             f"| Tmean {e['tmean_c']} C, RH {e['rh_pct']:.0f}%")
    L.append("")
    L.append("WATER DEMAND  [modelled, FAO-56: NDVI -> Kc -> ETc]")
    L.append(f"  Kc = {w['kc']}  ->  ETc = {w['etc_mm_day']} mm/day = "
             f"{w['etc_mm_week']} mm/week")
    L.append(f"  >> THIS FIELD NEEDS ~{w['weekly_demand_m3']:,} m3 THIS WEEK "
             f"({w['weekly_demand_m3_per_ha']:,} m3/ha)")
    L.append(f"  vigour band: sparse(NDVI .45) {w['sensitivity']['ndvi0.45_sparse_m3_wk']:,} "
             f"- vigorous(NDVI .75) {w['sensitivity']['ndvi0.75_vigorous_m3_wk']:,} m3/wk")
    L.append("")
    L.append("AVOIDABLE WASTE  [ESTIMATE — no field meter]")
    L.append(f"  at ~{wa['efficiency_now_pct']}% efficiency, est. applied "
             f"~{wa['est_applied_now_m3_wk']:,} m3/wk")
    L.append(f"  reaching {wa['best_practice_pct']}% best practice saves "
             f"~{wa['avoidable_m3_wk']:,} m3/wk  (~{wa['avoidable_pct_of_applied']}% of applied)")
    L.append("=" * 68)
    L.append("measured = NASA POWER | modelled = FAO-56 | estimate = national/efficiency")
    return "\n".join(L)


if __name__ == "__main__":
    rep = run_field(
        lat=21.2120, lon=39.6643,
        ndvi_image_path="../../photo_2_2026-11-11_21-19-04.jpg",
        area_ha=50.0,
        place_label="Makkah region (low coastal, ~45 m)",
        out_dir=".",
    )
    print(pretty(rep))
