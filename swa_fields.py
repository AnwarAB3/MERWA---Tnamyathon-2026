# -*- coding: utf-8 -*-
"""
swa_fields.py — compute monitoring records for a set of groundwater-irrigated
fields across Makkah region, for the Saudi Water Authority dashboard.

For each field: real Sentinel-2 NDVI, NASA POWER ET0, OpenLandMap soil, then
FAO-56 ETc -> weekly & annual consumptive use, avoidable waste, idle land.
Also saves an Esri true-colour thumbnail per field.

    python mirwa/swa_fields.py
Outputs: mirwa/screenshots/swa/fields.json  + fieldN.jpg thumbnails
"""
import sys, json, io
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

import platform_core as pc
import power_et0, sentinel2, soil as soil_api, fao56, crops

OUT = Path(__file__).resolve().parent / "screenshots" / "swa"
OUT.mkdir(parents=True, exist_ok=True)
EFF, BEST = 0.50, 0.85

# Only the fields the user actually provided (coordinate + crop). No invented sites.
FIELDS = [
    dict(id="f1", name="مزرعة الساحل",       lat=21.2120, lon=39.6643, area=50, crop="tomato"),
    dict(id="f2", name="مزرعة بابايا الليث", lat=20.5833, lon=40.4932, area=20, crop="papaya"),
    dict(id="f3", name="مزرعة نخيل رهاط",     lat=22.0788, lon=40.0282, area=40, crop="date"),
]


def compute(f):
    rec = dict(f)
    try:
        et = power_et0.fetch_et0(f["lat"], f["lon"])
        rec["et0"] = round(et.et0_mean_mm_day, 2)
        rec["elev"] = round(et.elevation_m)
    except Exception as e:
        rec["et0"] = None
    s2 = None
    try:
        s2 = sentinel2.fetch_ndvi(f["lat"], f["lon"])
    except Exception:
        pass
    if s2 and s2.active_mean_ndvi == s2.active_mean_ndvi:
        rec["ndvi"] = round(s2.active_mean_ndvi, 3)
        rec["scene"] = s2.scene_date
        rec["idle_pct"] = round(s2.idle_fraction * 100)
        rec["active_pct"] = round(s2.active_fraction * 100)
    else:
        rec["ndvi"] = None
    try:
        sl = soil_api.detect_soil(f["lat"], f["lon"])
        rec["soil_ar"] = sl.name_ar if sl else None
        rec["soil_bucket"] = sl.bucket if sl else None
    except Exception:
        rec["soil_ar"] = None
    # water
    if rec.get("ndvi") and rec.get("et0"):
        kcb = crops.kcb_max(f["crop"])
        fw = fao56.etc(rec["ndvi"], rec["et0"], f["area"], kcb_full=kcb)
        net = fw.net_irrig_m3_week
        rec["week_m3"] = round(net)
        rec["annual_m3"] = round(net * 52)
        rec["applied_m3"] = round(net / EFF)
        rec["avoid_m3"] = round(net / EFF - net / BEST)
        rec["over_pct"] = round((net / EFF - net) / (net / EFF) * 100)
        rec["kc"] = round(fw.kc, 2)
        rec["status"] = "over" if net / EFF > net * 1.15 else "ok"
    rec["crop_ar"] = crops.crop_name(f["crop"])
    # thumbnail
    try:
        tc, _ = pc.fetch_truecolor(f["lat"], f["lon"], half_deg=0.02)
        if tc:
            tc.save(OUT / f"{f['id']}.jpg", "JPEG", quality=82)
            rec["thumb"] = f"{f['id']}.jpg"
    except Exception:
        pass
    return rec


if __name__ == "__main__":
    out = []
    for f in FIELDS:
        print("computing", f["name"], "...", flush=True)
        r = compute(f)
        print("   ndvi", r.get("ndvi"), "et0", r.get("et0"), "soil", r.get("soil_ar"),
              "week_m3", r.get("week_m3"), flush=True)
        out.append(r)
    (OUT / "fields.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print("saved", OUT / "fields.json")
