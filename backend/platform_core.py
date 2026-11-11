"""
platform_core.py — glue between the UI (Streamlit) and the FAO-56 engine.

Responsibilities:
  * parse a Google-Earth coordinate (DMS or decimal)
  * auto-fetch a true-colour satellite image for a coordinate (keyless, Esri)
  * best-effort reverse-geocode for the "confirm location" step
  * a quick greenness (VARI) NDVI estimate from an RGB image (coordinate mode)
  * build BOTH an actionable report (farmer + Saudi Water Authority) and the
    full technical breakdown from the engine.

Everything is labelled measured / modelled / estimate. Nothing is invented.
"""
from __future__ import annotations
import io
import re
import math
from dataclasses import dataclass, asdict
import numpy as np
import requests
from PIL import Image, ImageFilter

import fao56
import power_et0
import ndvi_image
import crops

UA = {"User-Agent": "mirwa-hackathon-prototype/1.0 (satellite irrigation PoC)"}

# ----------------------------------------------------------------------------- coordinates
_DMS = re.compile(
    r"""(\d{1,3})\s*[°:\s]\s*(\d{1,2})\s*['’:\s]\s*([\d.]+)\s*["”]?\s*([NSEW])""",
    re.I | re.X,
)

def parse_coord(text: str):
    """Return (lat, lon) from DMS (21°12'43.12\"N 39°39'51.46\"E) or decimal
    (21.2120, 39.6643). Raises ValueError if it can't."""
    text = (text or "").strip()
    hits = _DMS.findall(text)
    if len(hits) >= 2:
        def dec(h):
            deg, mn, sec, hemi = h
            v = float(deg) + float(mn) / 60 + float(sec) / 3600
            return -v if hemi.upper() in ("S", "W") else v
        vals = {}
        for h in hits:
            (vals.__setitem__("lat", dec(h)) if h[3].upper() in ("N", "S")
             else vals.__setitem__("lon", dec(h)))
        if "lat" in vals and "lon" in vals:
            return round(vals["lat"], 6), round(vals["lon"], 6)
    nums = re.findall(r"[-+]?\d+\.\d+", text)
    if len(nums) >= 2:
        return round(float(nums[0]), 6), round(float(nums[1]), 6)
    raise ValueError("تعذّر قراءة الإحداثيات. مثال: 21°12'43.12\"N 39°39'51.46\"E")


def reverse_geocode(lat: float, lon: float) -> str:
    """Best-effort place name (OpenStreetMap Nominatim). Falls back to a
    coordinate string. No user data is sent — only the queried point."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 10,
                    "accept-language": "ar"},
            headers=UA, timeout=12)
        d = r.json()
        return d.get("display_name") or f"{lat:.4f}, {lon:.4f}"
    except Exception:
        return f"{lat:.4f}, {lon:.4f}"


def fetch_truecolor(lat: float, lon: float, half_deg: float = 0.03):
    """Auto-fetch a true-colour satellite image (Esri World Imagery, keyless).
    Returns (PIL.Image, bbox) or (None, bbox) on failure."""
    bbox = (lon - half_deg, lat - half_deg, lon + half_deg, lat + half_deg)
    url = ("https://services.arcgisonline.com/arcgis/rest/services/"
           "World_Imagery/MapServer/export"
           f"?bbox={bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
           "&bboxSR=4326&imageSR=4326&size=700,700&format=jpg&f=image")
    try:
        r = requests.get(url, timeout=25)
        if r.headers.get("content-type", "").startswith("image"):
            return Image.open(io.BytesIO(r.content)).convert("RGB"), bbox
    except Exception:
        pass
    return None, bbox


# ----------------------------------------------------------------------------- NDVI estimate from RGB
def _closing(mask: np.ndarray, size: int = 15) -> np.ndarray:
    im = Image.fromarray((mask * 255).astype("uint8"))
    im = im.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    return np.asarray(im) > 127


def vari_estimate(img: Image.Image):
    """Rough vegetation estimate from a true-colour image using VARI
    (Visible Atmospherically Resistant Index) = (G-R)/(G+R-B).

    Returns (ndvi_active_estimate, active_fraction, idle_in_field_fraction).
    IMPORTANT: idle is measured ONLY inside the cultivated footprint (the
    farmed cluster), NOT across the surrounding desert — otherwise a green
    pivot in the desert would wrongly read as mostly "idle". This is a PROXY
    for coordinate mode; upload mode uses the real NDVI band."""
    a = np.asarray(img).astype(float)
    g, r, b = a[..., 1], a[..., 0], a[..., 2]
    vari = np.clip((g - r) / (g + r - b + 1e-6), -1, 1)
    active = vari > 0.07
    bare = vari < 0.02
    frac_a = float(active.mean())
    vari_a = float(vari[active].mean()) if active.any() else 0.0
    # map mean active VARI (~0.05–0.35) to an approximate NDVI (~0.45–0.80)
    ndvi_est = float(np.clip(0.42 + 1.1 * vari_a, 0.30, 0.82))
    footprint = _closing(active, 15)                 # cultivated cluster only
    idle = (footprint & bare).sum() / max(1, footprint.sum())
    return round(ndvi_est, 3), round(frac_a, 3), round(float(idle), 3)


# ----------------------------------------------------------------------------- the report
@dataclass
class Report:
    lat: float
    lon: float
    place: str
    area_ha: float
    ndvi: float
    ndvi_source: str            # "رفع صورة NDVI" | "تقدير من اللون الحقيقي (VARI)"
    idle_pct: float
    et0: dict                   # from power_et0 (as dict) or manual
    simple: dict                # actionable (farmer + SWA)
    technical: dict


# irrigation efficiency (indicative, FEWS NET) and water context (cited)
EFF = 0.50
BEST = 0.85


def build_report(lat, lon, place, area_ha, ndvi, ndvi_source, idle_pct,
                 et0_result, kcb_max=1.10, soil="sandy",
                 current_crop_id="generic", month=11) -> Report:
    et0 = et0_result.et0_mean_mm_day
    # crop type sets the crop coefficient ceiling (Kcb_max); NDVI stays measured
    fw = fao56.etc(ndvi, et0, area_ha, pe_mm_week=0.0, kcb_full=kcb_max)  # engine
    net_m3 = fw.net_irrig_m3_week
    net_mm = fw.net_irrig_mm_week
    applied_m3 = net_m3 / EFF                                # typical over-application
    applied_best_m3 = net_m3 / BEST
    avoid_m3 = applied_m3 - applied_best_m3
    avoid_pct = (1 - EFF / BEST) * 100
    over_pct = (applied_m3 - net_m3) / applied_m3 * 100      # share above crop need
    idle_ha = area_ha * idle_pct / 100.0

    # status (traffic light) — farmers over-apply by design in the problem
    if applied_m3 > net_m3 * 1.15:
        status, status_ar = "over", "ريّ زائد عن حاجة المحصول"
    elif applied_m3 < net_m3 * 0.9:
        status, status_ar = "under", "ريّ أقل من الحاجة"
    else:
        status, status_ar = "ok", "الري مطابق للحاجة"

    daily_m3 = net_m3 / 7.0
    annual_m3 = net_m3 * 52                                   # continuous-crop upper estimate

    simple = {
        "status": status,
        "status_ar": status_ar,
        "variables": {
            "مساحة الأرض": f"{area_ha:g} هكتار",
            "نوع التربة": crops.SOILS.get(soil, soil),
            "الموسم الحالي": crops.season_label(month),
            "الاحتياج المائي الأسبوعي": f"{round(net_m3):,} م³",
            "المحصول الحالي": crops.crop_name(current_crop_id),
        },
        "farmer": {
            "headline": f"اسقِ هذا الأسبوع ≈ {round(net_m3):,} م³"
                        f"  (≈ {net_mm:.0f} مم عمق ريّ، ≈ {round(daily_m3):,} م³/يوم).",
            "save": f"المعتاد في مثل هذه الحقول ≈ {round(applied_m3):,} م³/أسبوع؛ "
                    f"بالالتزام بحاجة المحصول توفّر ≈ {round(avoid_m3):,} م³/أسبوع "
                    f"وتقلّل فاتورة الضخّ.",
            "idle": f"≈ {idle_pct:.0f}٪ من حقلك ظاهر كأرض غير مزروعة/مراحة "
                    f"(≈ {idle_ha:.0f} هكتار) — فرصة لمحصول إضافي ضمن حدٍّ مائي.",
            "why": f"حُسبت الحاجة من خضرة المحصول (NDVI {ndvi:.2f}) ومناخ موقعك "
                   f"هذا الشهر — تتحدّث تلقائيًا مع كل صورة قمر جديدة.",
        },
        "swa": {
            "consumptive_week": round(net_m3),
            "consumptive_annual_est": round(annual_m3),
            "avoidable_week_m3": round(avoid_m3),
            "avoidable_pct": round(avoid_pct, 0),
            "over_pct": round(over_pct, 0),
            "note": "الاستهلاك الفعلي (ETc) لهذا الحقل قابل للتجميع إقليميًا لإدارة "
                    "السحب الجوفي. 90٪ من مياه الري في المملكة جوفية غير متجددة "
                    "(وزارة البيئة والمياه والزراعة).",
        },
    }

    technical = {
        "inputs": {
            "مؤشر NDVI (مقيس)": f"{ndvi:.3f}  ({ndvi_source})",
            "المحصول الحالي": f"{crops.crop_name(current_crop_id)} (Kcb_max = {kcb_max:.2f})",
            "نوع التربة": crops.SOILS.get(soil, soil),
            "مساحة الحقل": f"{area_ha:g} هكتار",
            "ارتفاع الموقع": f"{et0_result.elevation_m:.0f} م",
        },
        "et0": {
            "ET₀ (المتوسط)": f"{et0:.2f} مم/يوم",
            "المدى": f"{et0_result.et0_min_mm_day:.2f} – {et0_result.et0_max_mm_day:.2f} مم/يوم",
            "النافذة": f"{et0_result.start} → {et0_result.end} ({et0_result.n_days} يومًا)",
            "متوسط الحرارة": f"{et0_result.tmean_mean_c:.1f}°م",
            "الرطوبة": f"{et0_result.rh_pct if hasattr(et0_result,'rh_pct') else et0_result.rh_mean_pct:.0f}٪",
            "الطريقة": "FAO-56 Penman-Monteith من بيانات NASA POWER الرصدية (ليست تنبؤية)",
        },
        "chain": {
            "fc (كسر الغطاء)": f"({ndvi:.2f}−0.15)/(0.90−0.15) = "
                               f"{max(0,min(1,(ndvi-0.15)/0.75)):.2f}",
            f"Kcb = {kcb_max:.2f} × fc": f"{fao56.kcb_from_ndvi_sims(ndvi, kcb_full=kcb_max):.3f}",
            "Kc = Kcb + Ke(0.10)": f"{fw.kc:.3f}",
            "ETc = Kc × ET₀": f"{fw.kc:.3f} × {et0:.2f} = {fw.etc_mm_day:.2f} مم/يوم",
            "الاحتياج الأسبوعي": f"{fw.etc_mm_week:.1f} مم = {round(fw.weekly_demand_m3):,} م³",
            "الهدر": f"المطبّق≈{round(applied_m3):,} − الاحتياج {round(net_m3):,} "
                     f"(كفاءة {int(EFF*100)}٪→{int(BEST*100)}٪)",
        },
        "equations": [
            "NDVI = (B8 − B4) / (B8 + B4)",
            "fc = (NDVI − NDVI_min)/(NDVI_max − NDVI_min),  NDVI_min=0.15, NDVI_max=0.90",
            "Kcb = Kcb_full · fc  (Kcb_full = 1.10)   [Allen & Pereira 2009; Calera 2017]",
            "ET₀ = [0.408·Δ·(Rn−G) + γ·900/(T+273)·u₂·(es−ea)] / [Δ + γ·(1+0.34·u₂)]  (FAO-56 eq.6)",
            "ETc = Kc · ET₀    (FAO-56)",
            "الحجم = ETc(مم) /1000 × المساحة(م²);  1 مم على 1 هكتار = 10 م³",
        ],
        "sources": [
            "FAO-56: Allen, Pereira, Raes, Smith (1998).",
            "NDVI→Kc: Allen & Pereira (2009); Calera et al. (2017); SIMS.",
            "ET₀ المناخ: NASA POWER (power.larc.nasa.gov) — بيانات رصدية.",
            "سياق المياه: وزارة البيئة والمياه والزراعة؛ الهيئة العامة للإحصاء (2023)؛ "
            "كفاءة الري ~50٪ (FEWS NET، مؤشّري).",
        ],
    }

    return Report(lat, lon, place, area_ha, ndvi, ndvi_source, idle_pct,
                  et0=_et0_to_dict(et0_result), simple=simple, technical=technical)


def _et0_to_dict(r):
    return {"mean": r.et0_mean_mm_day, "min": r.et0_min_mm_day,
            "max": r.et0_max_mm_day, "elev": r.elevation_m,
            "window": f"{r.start}..{r.end}", "n": r.n_days,
            "tmean": r.tmean_mean_c, "rh": r.rh_mean_pct, "per_day": r.per_day}
