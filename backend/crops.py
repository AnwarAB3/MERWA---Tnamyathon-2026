# -*- coding: utf-8 -*-
"""
crops.py — محاصيل منطقة مكة المكرمة: معاملات المحصول (Kc)، والاحتياج المائي،
والموسم والتربة المناسبة، مع أيقونات بسيطة (SVG، بلا إيموجي) لعرضها للمزارع.

قيم Kc مأخوذة من جدول FAO-56 (Table 17، قيم منتصف الموسم التقريبية).
الاحتياج المائي الموسمي تقديري إرشادي لظروف جافة — يُعرض كمؤشّر لا كرقم نهائي.
المصدر: FAO-56 (Allen et al., 1998) + إرشادات الري في المناطق الجافة.

نوع التربة: sandy=رملية، loam=طميية، clay=طينية.
الموسم: 'cool'=زراعة شتوية (سبتمبر–فبراير)، 'warm'=زراعة صيفية (فبراير–مايو)،
'perennial'=دائم/أشجار.
"""
from __future__ import annotations

SOILS = {"sandy": "رملية", "loam": "طميية", "clay": "طينية"}


def _leaf(x=16, y=7):
    return (f'<path d="M{x} {y} q4 -5 9 -3 q-2 5 -9 3 z" fill="#3f9e52"/>'
            f'<path d="M{x} {y+2} v-5" stroke="#3f9e52" stroke-width="1.6" fill="none"/>')

# Simple, recognisable SVG icons (viewBox 0 0 32 32). No emoji.
ICONS = {
    "tomato": f'<svg viewBox="0 0 32 32" width="30" height="30"><circle cx="16" cy="19" r="10" fill="#e4452f"/><circle cx="12" cy="16" r="2.4" fill="#ff7a5c" opacity=".5"/>{_leaf(16,8)}</svg>',
    "cucumber": '<svg viewBox="0 0 32 32" width="30" height="30"><rect x="9" y="6" width="9" height="22" rx="4.5" transform="rotate(20 13 17)" fill="#3f8f3a"/><g fill="#8fd18a"><circle cx="12" cy="11" r="1"/><circle cx="15" cy="16" r="1"/><circle cx="18" cy="21" r="1"/></g></svg>',
    "squash": f'<svg viewBox="0 0 32 32" width="30" height="30"><path d="M16 27 c-7 0 -9 -6 -6 -11 c2 -3 4 -3 6 -3 c2 0 4 0 6 3 c3 5 1 11 -6 11 z" fill="#f0a93a"/>{_leaf(16,7)}</svg>',
    "eggplant": f'<svg viewBox="0 0 32 32" width="30" height="30"><path d="M20 10 c4 4 3 10 -1 14 c-4 4 -11 3 -12 -2 c-1 -6 6 -15 13 -12 z" fill="#6a3d9a"/>{_leaf(20,8)}</svg>',
    "pepper": f'<svg viewBox="0 0 32 32" width="30" height="30"><path d="M12 10 c6 -1 11 3 10 9 c-1 6 -7 9 -11 6 c-4 -3 -2 -7 -4 -10 c-1 -2 2 -5 5 -5 z" fill="#d93b3b"/>{_leaf(12,8)}</svg>',
    "okra": f'<svg viewBox="0 0 32 32" width="30" height="30"><path d="M16 5 c2 6 2 14 0 22 c-2 -8 -2 -16 0 -22 z" fill="#4e9e3f"/><path d="M13 10 q3 6 6 0" stroke="#2f7a2a" stroke-width="1.4" fill="none"/></svg>',
    "watermelon": '<svg viewBox="0 0 32 32" width="30" height="30"><circle cx="16" cy="16" r="11" fill="#2e8b3d"/><path d="M16 16 m-8 0 a8 8 0 0 0 16 0 z" fill="#e23b2e"/><g fill="#222"><circle cx="13" cy="20" r=".8"/><circle cx="19" cy="20" r=".8"/><circle cx="16" cy="22" r=".8"/></g></svg>',
    "melon": '<svg viewBox="0 0 32 32" width="30" height="30"><circle cx="16" cy="16" r="11" fill="#d8c25a"/><g stroke="#b29b3f" stroke-width="1" fill="none"><path d="M8 12 q8 4 16 0"/><path d="M7 17 q9 4 18 0"/><path d="M9 22 q7 3 14 0"/></g></svg>',
    "date": '<svg viewBox="0 0 32 32" width="30" height="30"><g stroke="#3f9e52" stroke-width="2" fill="none" stroke-linecap="round"><path d="M16 14 C10 8 8 8 5 9"/><path d="M16 14 C22 8 24 8 27 9"/><path d="M16 14 C12 7 12 5 13 3"/><path d="M16 14 C20 7 20 5 19 3"/></g><g fill="#a8622e"><ellipse cx="14" cy="20" rx="2" ry="3"/><ellipse cx="18" cy="20" rx="2" ry="3"/><ellipse cx="16" cy="24" rx="2" ry="3"/></g></svg>',
    "pomegranate": f'<svg viewBox="0 0 32 32" width="30" height="30"><circle cx="16" cy="18" r="10" fill="#c0392b"/><g fill="#8a1f16"><circle cx="13" cy="16" r="1.3"/><circle cx="18" cy="16" r="1.3"/><circle cx="16" cy="20" r="1.3"/></g><path d="M16 8 l-2 -4 h4 z" fill="#8a1f16"/></svg>',
    "grape": f'<svg viewBox="0 0 32 32" width="30" height="30"><g fill="#7a4fb0"><circle cx="16" cy="13" r="3"/><circle cx="12" cy="17" r="3"/><circle cx="20" cy="17" r="3"/><circle cx="16" cy="20" r="3"/><circle cx="13" cy="23" r="3"/><circle cx="19" cy="23" r="3"/></g>{_leaf(16,7)}</svg>',
    "fig": f'<svg viewBox="0 0 32 32" width="30" height="30"><path d="M16 10 c6 2 8 8 5 13 c-3 5 -11 5 -13 -1 c-2 -6 2 -14 8 -12 z" fill="#6b4b8a"/>{_leaf(16,8)}</svg>',
    "alfalfa": '<svg viewBox="0 0 32 32" width="30" height="30"><g stroke="#3f9e52" stroke-width="2" fill="none" stroke-linecap="round"><path d="M16 27 V12"/><path d="M16 16 C12 14 10 11 10 8"/><path d="M16 14 C20 12 22 9 22 6"/><path d="M16 19 C13 18 11 16 10 13"/></g><g fill="#6fc06a"><circle cx="10" cy="8" r="2"/><circle cx="22" cy="6" r="2"/><circle cx="10" cy="13" r="2"/></g></svg>',
    "sorghum": '<svg viewBox="0 0 32 32" width="30" height="30"><path d="M16 28 V11" stroke="#8a9a3a" stroke-width="2"/><ellipse cx="16" cy="8" rx="4" ry="6" fill="#c7a33a"/><g stroke="#5f7a2a" stroke-width="1.5"><path d="M16 18 l-5 -3"/><path d="M16 21 l5 -3"/></g></svg>',
    "generic": f'<svg viewBox="0 0 32 32" width="30" height="30"><path d="M16 28 V14" stroke="#3f9e52" stroke-width="2"/><path d="M16 18 C10 17 8 13 8 9 C13 9 16 12 16 16" fill="#6fc06a"/><path d="M16 15 C22 14 24 10 24 6 C19 6 16 9 16 13" fill="#8fd18a"/></svg>',
}

# المحاصيل: الاسم، الأيقونة، Kc (منتصف الموسم)، فئة المياه، الاحتياج التقديري،
# الموسم، التربة المناسبة، وملاحظة قصيرة.
CROPS = [
    dict(id="tomato", name="طماطم", icon="tomato", kcb=1.10, water="med",
         mm=500, seasons={"cool"}, soils={"loam", "sandy"},
         note="محصول الموسم البارد الأهم؛ عائد جيد مع ريّ معتدل."),
    dict(id="cucumber", name="خيار", icon="cucumber", kcb=0.95, water="med",
         mm=450, seasons={"cool"}, soils={"loam", "sandy"},
         note="سريع النمو، مناسب للزراعة الشتوية."),
    dict(id="squash", name="كوسا", icon="squash", kcb=0.90, water="med",
         mm=400, seasons={"cool"}, soils={"loam", "sandy"},
         note="قليل الاحتياج نسبيًا ودورة قصيرة."),
    dict(id="eggplant", name="باذنجان", icon="eggplant", kcb=1.00, water="med",
         mm=500, seasons={"cool"}, soils={"loam", "clay"},
         note="يتحمّل الحرارة ويعطي طوال الموسم."),
    dict(id="pepper", name="فلفل", icon="pepper", kcb=1.00, water="med",
         mm=500, seasons={"cool"}, soils={"loam", "sandy"},
         note="قيمة تسويقية عالية مع ريّ منتظم."),
    dict(id="okra", name="بامية", icon="okra", kcb=1.05, water="med",
         mm=450, seasons={"warm", "cool"}, soils={"sandy", "loam"},
         note="يتحمّل الحرّ والجفاف النسبي."),
    dict(id="watermelon", name="بطيخ", icon="watermelon", kcb=0.95, water="med",
         mm=550, seasons={"warm"}, soils={"sandy"},
         note="يناسب التربة الرملية وموسم الدفء."),
    dict(id="melon", name="شمام", icon="melon", kcb=0.90, water="med",
         mm=500, seasons={"warm"}, soils={"sandy"},
         note="يفضّل التربة الرملية جيدة التصريف."),
    dict(id="fig", name="تين", icon="fig", kcb=0.95, water="low",
         mm=450, seasons={"perennial"}, soils={"sandy", "loam"},
         note="شجرة متحمّلة للجفاف وقليلة المياه."),
    dict(id="pomegranate", name="رمان", icon="pomegranate", kcb=0.85, water="low",
         mm=550, seasons={"perennial"}, soils={"loam", "sandy", "clay"},
         note="متحمّل للملوحة والجفاف، مناسب للمنطقة."),
    dict(id="date", name="نخيل التمر", icon="date", kcb=0.90, water="high",
         mm=1800, seasons={"perennial"}, soils={"sandy", "loam"},
         note="عائد مرتفع لكنه كثيف الاستهلاك للمياه."),
    dict(id="grape", name="عنب", icon="grape", kcb=0.80, water="med",
         mm=650, seasons={"perennial"}, soils={"loam", "sandy"},
         note="يجود في مرتفعات الطائف الأبرد."),
    dict(id="alfalfa", name="برسيم (علف)", icon="alfalfa", kcb=1.15, water="high",
         mm=1800, seasons={"perennial"}, soils={"loam", "clay"},
         note="عالي الاستهلاك للمياه؛ يُنصح بتقليصه للاستدامة."),
    dict(id="sorghum", name="ذرة رفيعة", icon="sorghum", kcb=1.00, water="med",
         mm=500, seasons={"warm"}, soils={"loam", "sandy", "clay"},
         note="علف يتحمّل الحرارة باحتياج معتدل."),
]
_BY_ID = {c["id"]: c for c in CROPS}

WATER_LABEL = {"low": "منخفض", "med": "متوسط", "high": "مرتفع"}
WATER_COLOR = {"low": "#2f9e44", "med": "#C1551C", "high": "#c0392b"}


def season_of(month: int) -> str:
    """موسم الزراعة الغالب في السهول الحارّة بالمنطقة."""
    if month in (9, 10, 11, 12, 1, 2):
        return "cool"      # زراعة شتوية
    return "warm"          # زراعة صيفية


def season_label(month: int) -> str:
    return ("الخريف/الشتاء — موسم الخضار الشتوية" if season_of(month) == "cool"
            else "الربيع/الصيف — موسم المحاصيل الدافئة")


def current_crop_options():
    """خيارات 'المحصول المزروع حاليًا' للقائمة (تحدّد Kc)."""
    opts = [("generic", "غير محدّد / مختلط")]
    opts += [(c["id"], c["name"]) for c in CROPS]
    return opts


def kcb_max(crop_id: str) -> float:
    return _BY_ID.get(crop_id, {}).get("kcb", 1.05)


def crop_name(crop_id: str) -> str:
    return _BY_ID.get(crop_id, {}).get("name", "غير محدّد")


def water_m3_season(crop, area_ha: float) -> int:
    """احتياج تقديري موسمي لكامل الحقل (مم × 10 م³/هكتار/مم)."""
    return round(crop["mm"] * 10 * area_ha)


def recommend(area_ha: float, soil: str, month: int, top: int = 6):
    """ترشيح محاصيل مناسبة للموسم والتربة، مع تفضيل الأقل استهلاكًا للمياه."""
    season = season_of(month)
    scored = []
    for c in CROPS:
        in_season = (season in c["seasons"]) or ("perennial" in c["seasons"])
        if not in_season:
            continue
        score = 0
        reasons = []
        if season in c["seasons"]:
            score += 3; reasons.append("مناسب للموسم الحالي")
        elif "perennial" in c["seasons"]:
            score += 2; reasons.append("محصول دائم يُزرع على مدار العام")
        if soil in c["soils"]:
            score += 2; reasons.append(f"يلائم التربة ال{SOILS.get(soil, '')}")
        score += {"low": 3, "med": 2, "high": 0}[c["water"]]
        if c["water"] == "high":
            reasons.append("استهلاك مائي مرتفع — فكّر فيه بحذر")
        elif c["water"] == "low":
            reasons.append("قليل استهلاك المياه")
        scored.append((score, c, reasons))
    scored.sort(key=lambda t: t[0], reverse=True)
    out = []
    for score, c, reasons in scored[:top]:
        out.append({
            "name": c["name"], "icon": ICONS[c["icon"]],
            "water_cat": c["water"], "water_label": WATER_LABEL[c["water"]],
            "water_color": WATER_COLOR[c["water"]],
            "water_m3": water_m3_season(c, area_ha),
            "note": c["note"], "reasons": reasons,
        })
    return out
