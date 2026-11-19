# -*- coding: utf-8 -*-
"""
مرواء (Mirwa) — منصة ترشيد ريّ الحقول من صور الأقمار الاصطناعية.

طريقتان للبدء: إدخال إحداثية الحقل (نسحب الصور والمناخ تلقائيًا)، أو رفع صور
الحقل الجاهزة (ومعها حقل نموذجي جاهز للتجربة). المخرجات تقرير عملي للمزارع
وللهيئة السعودية للمياه، مع تفاصيل تقنية كاملة عند الطلب.
"""
import sys
import io
import json
import base64
import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
from PIL import Image

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE / "backend"))
ROOT = BASE.parent

import platform_core as pc
import power_et0
import ndvi_image
import sentinel2
import fao56
import crops
import soil as soil_api

st.set_page_config(page_title="مرواء — منصة ترشيد الري", page_icon="💧", layout="wide")
MONTH = dt.date.today().month
DEFAULT_COORD = "21°12'43.12\"N 39°39'51.46\"E"
SAMPLE_TC = BASE / "data" / "sample_truecolor.jpg"
SAMPLE_NDVI = BASE / "data" / "sample_ndvi.jpg"
SAMPLE_FC = BASE / "data" / "sample_falsecolor.jpg"

# ----------------------------------------------------------------- styling (modern, RTL, green identity)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&family=Space+Grotesk:wght@500;600;700&display=swap');
:root{
  --bg:#0e1712; --surface:#15231a; --surface-2:#1a2a20; --ink:#e9f1e9; --muted:#9bb0a2;
  --line:#243528; --green:#4bbf6e; --green-2:#5fcf7f; --lime:#9ad549; --sky:#5aa6e8;
  --good:#5fcf7f; --warn:#e6a94a; --crit:#e06a60;
  --hero-1:#123a22; --hero-2:#1f7a3f;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 12px 34px rgba(0,0,0,.4); --r:18px;
  --fdisplay:"Space Grotesk","Cairo",system-ui,sans-serif;
  --fbody:"Cairo",system-ui,"Segoe UI",sans-serif;
}
html, body, [class*="css"], .stApp, button, input, textarea, select { font-family:var(--fbody) !important; }
.stApp { direction: rtl; background:var(--bg); color:var(--ink); }
[data-testid="stHeader"]{ background:transparent; }
[data-testid="stSidebar"]{ background:var(--surface); }
code, kbd{ background:var(--surface-2); color:var(--lime); }
.block-container { padding-top: 1.3rem; max-width: 1180px; }
h1,h2,h3,h4,p,span,div,label,li { text-align: right; }
.num,.var .v,.kpi .v,.rec .n{font-family:var(--fdisplay);font-variant-numeric:tabular-nums;letter-spacing:-.01em}

/* tabs */
.stTabs [data-baseweb="tab-list"]{ direction: rtl; gap:6px; border-bottom:1px solid var(--line); }
.stTabs [data-baseweb="tab"]{ font-weight:700; color:var(--muted); }
.stTabs [aria-selected="true"]{ color:var(--green) !important; }
.stTabs [data-baseweb="tab-highlight"]{ background:var(--green) !important; }

/* inputs */
.stTextInput input,.stNumberInput input,[data-baseweb="select"]>div{
  border-radius:12px !important; border-color:var(--line) !important; }
.stTextInput label,.stNumberInput label,.stSelectbox label{ font-weight:700; color:var(--ink); }

/* buttons: pill, green primary */
.stButton>button, .stDownloadButton>button{
  width:100%; border-radius:999px; font-weight:800; font-size:15.5px; padding:12px 18px;
  border:1px solid var(--line); background:var(--surface); color:var(--green); transition:.15s; box-shadow:var(--shadow); }
.stButton>button:hover{ border-color:var(--green); color:var(--green); }
.stButton>button[kind="primary"]{ background:linear-gradient(135deg,#2f9e55,#1f7a3f); color:#fff; border:0;
  box-shadow:0 8px 22px rgba(31,122,63,.35); }
.stButton>button[kind="primary"]:hover{ background:linear-gradient(135deg,#37b061,#248a47); color:#fff; }

/* metrics -> KPI cards */
[data-testid="stMetric"]{ background:var(--surface);border:1px solid var(--line);border-radius:16px;
  padding:14px 16px;box-shadow:var(--shadow); }
[data-testid="stMetricLabel"]{ color:var(--muted);font-weight:700; }
[data-testid="stMetricValue"]{ font-family:var(--fdisplay);font-weight:800;color:var(--ink); }

/* expander */
[data-testid="stExpander"]{ border:1px solid var(--line);border-radius:14px;background:var(--surface);box-shadow:var(--shadow); }

/* hero */
.head{background:linear-gradient(120deg,var(--hero-1),var(--hero-2));color:#fff;border-radius:var(--r);
  padding:22px 26px;margin-bottom:18px;box-shadow:var(--shadow);position:relative;overflow:hidden;
  border:1px solid rgba(143,207,73,.14)}
.head:after{content:"";position:absolute;inset-inline-start:-40px;top:-60px;width:240px;height:240px;
  border-radius:50%;background:rgba(143,207,73,.10)}
.head .hi{font-size:12.5px;font-weight:700;opacity:.9;letter-spacing:.02em}
.head h1{margin:2px 0 0;font-size:30px;font-weight:900;font-family:var(--fdisplay)}
.head p{margin:8px 0 0;font-size:14px;opacity:.94;font-weight:500;max-width:740px;line-height:1.8}

/* big choice cards */
.choice{background:var(--surface);border:1px solid var(--line);border-radius:var(--r);padding:28px 22px 10px;
  text-align:center;min-height:216px;box-shadow:var(--shadow)}
.choice svg{margin-bottom:10px}
.choice h3{margin:0 0 6px;font-size:20px;color:var(--ink);text-align:center;font-weight:800}
.choice p{margin:0 auto;font-size:13.5px;color:var(--muted);max-width:300px;text-align:center;line-height:1.8}

.panel{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:16px 18px;margin-bottom:14px;box-shadow:var(--shadow)}
.rec{background:linear-gradient(120deg,var(--hero-1),var(--hero-2));color:#fff;border-radius:16px;padding:18px 22px;margin:4px 0 16px;box-shadow:var(--shadow);border:1px solid rgba(143,207,73,.14)}
.rec .l{font-size:13px;opacity:.9;font-weight:700}
.rec .n{font-size:25px;font-weight:800;margin-top:6px;line-height:1.4}

/* variable tiles */
.vargrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:2px 0 14px}
.var{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:13px 15px;box-shadow:var(--shadow)}
.var .k{font-size:12px;color:var(--muted);font-weight:700}
.var .v{font-size:19px;color:var(--ink);font-weight:800;margin-top:4px}

/* crop list */
.cropgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(236px,1fr));gap:12px;margin-top:6px}
.crop{display:flex;gap:12px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 14px;box-shadow:var(--shadow)}
.crop .b{flex:1}
.crop .n{font-weight:800;color:var(--ink);font-size:15px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.crop .m{font-size:12px;color:var(--muted);margin-top:3px;line-height:1.7}
.wb{font-size:10.5px;font-weight:800;color:#fff;padding:2px 8px;border-radius:999px}

.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:15px 17px;margin-bottom:10px;box-shadow:var(--shadow)}
.card .t{font-weight:800;color:var(--green);font-size:15px;margin-bottom:5px}
.card .v{font-size:14px;color:var(--ink);line-height:1.9}
.note{font-size:12px;color:var(--muted);line-height:1.8}
.tag{font-size:10.5px;font-weight:800;padding:2px 9px;border-radius:999px;color:#fff}
.tm{background:var(--sky)}.tc{background:var(--green-2)}.te{background:var(--warn)}

/* ===== SWA monitoring dashboard ===== */
.swatop{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:2px 0 16px}
.swatop .hi{font-size:12.5px;color:var(--muted);font-weight:700}
.swatop h2{font-size:21px;font-weight:800;margin:1px 0 0;font-family:var(--fdisplay)}
.pill{display:inline-flex;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--line);
  border-radius:999px;padding:7px 14px;font-weight:700;font-size:12.5px;color:var(--ink);box-shadow:var(--shadow)}
.kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:13px;margin-bottom:18px}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:15px 17px;box-shadow:var(--shadow)}
.kpi .k{font-size:11.5px;color:var(--muted);font-weight:700}
.kpi .v{font-size:25px;font-weight:800;margin-top:4px;color:var(--ink)}
.kpi .v small{font-size:12px;color:var(--muted);font-weight:700}
.kpi .d{font-size:11px;font-weight:700;margin-top:3px}
.kpi .d.good{color:var(--good)} .kpi .d.warn{color:var(--warn)} .kpi .d.crit{color:var(--crit)}
.fgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(244px,1fr));gap:14px}
.fcard{border:1px solid var(--line);border-radius:16px;overflow:hidden;background:var(--surface);box-shadow:var(--shadow)}
.thumb{position:relative;height:124px;background:#2a3a2a center/cover no-repeat}
.thumb .scrim{position:absolute;inset:0;background:linear-gradient(180deg,rgba(8,20,12,.05),rgba(8,20,12,.5))}
.cropbadge{position:absolute;top:9px;inset-inline-start:9px;z-index:2;display:inline-flex;align-items:center;gap:6px;
  background:rgba(255,255,255,.94);border-radius:999px;padding:3px 11px 3px 4px;font-size:11.5px;font-weight:800;color:#15241b}
.cropbadge .ic{width:25px;height:25px;border-radius:50%;background:#fff;display:grid;place-items:center}
.cropbadge .ic svg{width:20px;height:20px}
.sdot{position:absolute;top:11px;inset-inline-end:11px;z-index:2;width:11px;height:11px;border-radius:50%;
  border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.15)}
.sdot.over{background:var(--crit)} .sdot.ok{background:var(--good)} .sdot.idle{background:var(--muted)}
.finfo{padding:12px 14px}
.finfo .fname{font-size:14.5px;font-weight:800;color:var(--ink)}
.finfo .fplace{font-size:11px;color:var(--muted);font-weight:600;margin-top:1px}
.frow{display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-top:10px}
.frow .k{font-size:10px;color:var(--muted);font-weight:700}
.frow .v{font-size:13.5px;font-weight:800;margin-top:1px;color:var(--ink)}
.wbar{height:6px;border-radius:4px;background:var(--surface-2);margin-top:11px;overflow:hidden}
.wbar i{display:block;height:100%;border-radius:4px;background:var(--warn)}
.wbartxt{font-size:10.5px;color:var(--muted);font-weight:700;margin-top:5px}
.swatbl{width:100%;border-collapse:collapse;font-size:12.5px;margin-top:4px}
.swatbl th,.swatbl td{text-align:right;padding:9px 8px;border-bottom:1px solid var(--line);color:var(--ink)}
.swatbl th{font-size:11px;color:var(--muted);font-weight:700}
.gw{background:linear-gradient(100deg,#0b3d6b,#135089);color:#fff;border-radius:var(--r);padding:20px 22px;margin-top:4px;
  display:grid;grid-template-columns:repeat(4,1fr);gap:18px;box-shadow:var(--shadow)}
.gw .g .k{font-size:12px;opacity:.82;font-weight:600}
.gw .g .v{font-size:23px;font-weight:800;margin-top:3px;font-family:var(--fdisplay)}
.gw .g .s{font-size:11px;opacity:.82;margin-top:2px;line-height:1.6}
@media (max-width:900px){.kpis{grid-template-columns:repeat(2,1fr)}.gw{grid-template-columns:1fr 1fr}}
</style>
""", unsafe_allow_html=True)

def render_hero():
    st.markdown("""
<div class="head">
  <div class="hi">تنمية‑ثون 2026 · المحور البيئي والاستدامة · منطقة مكة المكرمة</div>
  <h1>مِرواء</h1>
  <p>منصة تقدّر الاحتياج المائي الفعلي لكل حقل من صور الأقمار الاصطناعية وفق منهجية
  FAO‑56، فتعرف كم يحتاج حقلك من الماء هذا الأسبوع، وكم يمكن أن توفّر.</p>
</div>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------- cached fetchers
@st.cache_data(show_spinner=False)
def get_et0(lat, lon):
    return power_et0.fetch_et0(lat, lon)

@st.cache_data(show_spinner=False)
def get_s2(lat, lon):
    try:
        return sentinel2.fetch_ndvi(lat, lon)
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def get_field(lat, lon):
    try:
        return sentinel2.fetch_field(lat, lon)
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def get_ts(lat, lon):
    try:
        return sentinel2.fetch_timeseries(lat, lon)
    except Exception:
        return None

@st.cache_data(show_spinner=False)
def get_et0_series(lat, lon, s_iso, e_iso):
    return power_et0.fetch_et0_series(lat, lon,
                                      dt.date.fromisoformat(s_iso),
                                      dt.date.fromisoformat(e_iso))


def classified_png(path):
    ndvi = ndvi_image.recover_ndvi(path)
    H, W = ndvi.shape
    out = np.full((H, W, 3), 200, np.uint8)
    valid = ~np.isnan(ndvi)
    out[valid & (ndvi < 0.25)] = (214, 199, 145)
    out[valid & (ndvi >= 0.25) & (ndvi < 0.45)] = (242, 221, 110)
    out[valid & (ndvi >= 0.45)] = (49, 140, 70)
    return Image.fromarray(out)


ICON_PIN = ('<svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#4bbf6e" '
            'stroke-width="1.7"><path d="M12 21c4-5 7-8.5 7-12a7 7 0 1 0-14 0c0 3.5 3 7 7 12z"/>'
            '<circle cx="12" cy="9" r="2.6"/></svg>')
ICON_IMG = ('<svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#4bbf6e" '
            'stroke-width="1.7"><rect x="3" y="4" width="18" height="16" rx="2"/>'
            '<circle cx="8.5" cy="9.5" r="1.6"/><path d="M4 18l5-5 4 4 3-3 4 4"/></svg>')
ICON_GRID = ('<svg width="52" height="52" viewBox="0 0 24 24" fill="none" stroke="#4bbf6e" '
             'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
             '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/>'
             '<rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>')


# ----------------------------------------------------------------- shared controls / renderers
@st.cache_data(show_spinner=False)
def get_soil(lat, lon):
    try:
        return soil_api.detect_soil(lat, lon)
    except Exception:
        return None


def soil_crop_controls(prefix, lat=None, lon=None):
    c1, c2 = st.columns(2)
    buckets = list(crops.SOILS.values())            # رملية / طميية / طينية
    detected = get_soil(lat, lon) if (lat is not None and lon is not None) else None
    idx = 0
    if detected:
        try:
            idx = buckets.index(crops.SOILS[detected.bucket])
        except Exception:
            idx = 0
    soil_label = c1.selectbox("نوع تربة الحقل", buckets, index=idx, key=prefix + "soil")
    s = next(k for k, v in crops.SOILS.items() if v == soil_label)
    if detected:
        c1.caption(f"اكتُشف تلقائيًا من OpenLandMap: {detected.name_ar} "
                   f"(تصنيف USDA) — يمكنك تعديله")
    elif lat is not None:
        c1.caption("تعذّر الكشف التلقائي للتربة الآن — اختر يدويًا")
    opts = crops.current_crop_options()
    names = [n for _, n in opts]
    name = c2.selectbox("المحصول المزروع حاليًا", names, key=prefix + "crop",
                        help="يحدّد معامل المحصول Kc في حساب الاحتياج المائي. "
                             "أمّا مؤشر الخضرة NDVI فيبقى مقيسًا من القمر الصناعي، "
                             "لا يُدخل يدويًا.")
    cid = opts[names.index(name)][0]
    return s, cid, crops.kcb_max(cid)


def render_variables(v):
    cells = "".join(f'<div class="var"><div class="k">{k}</div>'
                    f'<div class="v">{val}</div></div>' for k, val in v.items())
    st.markdown(f'<div class="vargrid">{cells}</div>', unsafe_allow_html=True)


def render_crop_list(area_ha, soil, month):
    recs = crops.recommend(area_ha, soil, month)
    cards = ""
    for r in recs:
        reasons = "، ".join(r["reasons"])
        cards += (
            f'<div class="crop"><div>{r["icon"]}</div><div class="b">'
            f'<div class="n">{r["name"]}'
            f'<span class="wb" style="background:{r["water_color"]}">مياه {r["water_label"]}</span></div>'
            f'<div class="m">احتياج تقديري ≈ {r["water_m3"]:,} م³ للموسم · {reasons}</div>'
            f'</div></div>')
    st.markdown('<div class="card"><div class="t">محاصيل مقترحة لأرضك</div>'
                '<div class="note">مرتّبة حسب ملاءمتها للموسم الحالي ونوع تربتك، '
                'مع تفضيل الأقل استهلاكًا للمياه. القيم تقديرية إرشادية.</div></div>',
                unsafe_allow_html=True)
    st.markdown(f'<div class="cropgrid">{cards}</div>', unsafe_allow_html=True)


def render_report(rep, area_ha, soil, truecolor=None, ndvi_classified=None,
                  ndvi_raw=None, key=""):
    s = rep.simple
    net_week = s["swa"]["consumptive_week"]          # the measured water DEMAND (m³/week)
    applied = float(st.session_state.get(f"applied_{key}", 0.0) or 0.0)
    _bn = {"over": st.error, "ok": st.success, "under": st.warning}.get(s["status"], st.info)
    _bn(f"حالة الحقل: {s['status_ar']} — {rep.place}")

    tab_f, tab_w = st.tabs(["تقرير المزارع", "تقرير الهيئة السعودية للمياه"])

    with tab_f:
        f = s["farmer"]
        st.markdown(f'<div class="rec"><div class="l">التوصية لهذا الأسبوع</div>'
                    f'<div class="n">{f["headline"]}</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="card"><div class="t">عوامل حقلك</div></div>',
                    unsafe_allow_html=True)
        render_variables(s["variables"])
        render_crop_list(area_ha, soil, MONTH)
        st.number_input(
            "كم تسقي حقلك فعليًا هذا الأسبوع؟ (م³) — اختياري، لحساب الموفّر",
            min_value=0.0, step=100.0, key=f"applied_{key}",
            help="الاحتياج المائي أعلاه محسوب من القمر الصناعي. أدخل كمية ريّك الفعلية "
                 "لنقارنها بالحاجة ونحسب كم يمكن أن توفّر.")
        c1, c2 = st.columns(2)
        with c1:
            if applied > 0:
                best = net_week / pc.BEST
                avoid = max(0.0, applied - best)
                over = max(0.0, applied - net_week)
                over_txt = (f"تسقي فوق حاجة المحصول بـ ≈ {round(over):,} م³ "
                            f"({over / applied * 100:.0f}٪). " if over > 0
                            else "ريّك قريب من حاجة المحصول. ")
                body = (f"تسقي ≈ {round(applied):,} م³/أسبوع والحاجة ≈ {net_week:,} م³. "
                        f"{over_txt}بكفاءة ريّ 85٪ يكفي ≈ {round(best):,} م³، "
                        f"فتوفّر ≈ {round(avoid):,} م³/أسبوع وتقلّل فاتورة الضخّ.")
            else:
                body = ("أدخل كمية ريّك الفعلية أعلاه لنحسب الموفّر. الاحتياج المائي "
                        "محسوب بالفعل؛ الموفّر إضافة تعتمد على ريّك الفعلي.")
            st.markdown(f'<div class="card"><div class="t">توفير الماء والتكلفة</div>'
                        f'<div class="v">{body}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="card"><div class="t">أرض غير مستغلّة</div>'
                        f'<div class="v">{f["idle"]}</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card"><div class="t">كيف حُسب هذا الرقم؟</div>'
                    f'<div class="v">{f["why"]}</div></div>', unsafe_allow_html=True)

    with tab_w:
        w = s["swa"]
        m1, m2, m3 = st.columns(3)
        m1.metric("الاستهلاك الفعلي (ETc) أسبوعيًا", f"{w['consumptive_week']:,} م³")
        if applied > 0:
            best = net_week / pc.BEST
            avoid = max(0.0, applied - best)
            over = max(0.0, applied - net_week)
            m2.metric("هدر يمكن تفاديه أسبوعيًا", f"{round(avoid):,} م³",
                      f"-{avoid / applied * 100:.0f}%")
            m3.metric("الري فوق حاجة المحصول", f"{over / applied * 100:.0f}%")
        else:
            m2.metric("هدر يمكن تفاديه أسبوعيًا", "—")
            m3.metric("الري فوق حاجة المحصول", "—")
            m2.caption("يُحسب بعد إدخال الريّ الفعلي في تبويب المزارع.")
        st.markdown(f'<div class="card"><div class="t">قراءة لإدارة المياه</div>'
                    f'<div class="v">الاستهلاك السنوي التقديري لهذا الحقل نحو '
                    f'<b>{w["consumptive_annual_est"]:,} م³</b> عند الري المتصل. '
                    f'{w["note"]}</div></div>', unsafe_allow_html=True)

    imgs = [(truecolor, "صورة لون حقيقي"), (ndvi_raw, "مؤشر NDVI"),
            (ndvi_classified, "تصنيف الغطاء: نشِط / ضعيف / بور")]
    imgs = [(im, cap) for im, cap in imgs if im is not None]
    if imgs:
        cols = st.columns(len(imgs))
        for col, (im, cap) in zip(cols, imgs):
            col.image(im, caption=cap, use_container_width=True)

    with st.expander("التفاصيل التقنية — الأرقام والمعادلات والمصادر"):
        t = rep.technical
        st.markdown("**المدخلات**")
        st.table({"القيمة": t["inputs"]})
        st.markdown("**ET₀ المرجعي (مقيس من بيانات رصدية)**")
        st.table({"القيمة": t["et0"]})
        st.markdown("**سلسلة الحساب (NDVI ← Kc ← ETc) وفق FAO‑56**")
        st.table({"القيمة": t["chain"]})
        st.markdown("**المعادلات**")
        for e in t["equations"]:
            st.markdown(f"- `{e}`")
        st.markdown("**المصادر**")
        for sc in t["sources"]:
            st.markdown(f"- {sc}")
        st.caption("مقيس = بيانات رصدية (قمر صناعي ومناخ) · محسوب = نموذج FAO‑56 · "
                   "الاستهلاك والهدر تقديريان بلا عدّاد ميداني.")


def render_timeseries(lat, lon, area_ha):
    with st.expander("سلسلة NDVI عبر السنة — كيف يتغيّر الاحتياج مع نمو المحصول والموسم"):
        st.caption("نقرأ عدة مشاهد Sentinel‑2 حقيقية خلال العام، ومن كل مشهد نحسب "
                   "Kc ثم الاحتياج المائي مع ET₀ شهري من NASA POWER.")
        if not st.checkbox("احسب السلسلة الزمنية (نحو نصف دقيقة)", key="ts_on"):
            return
        with st.spinner("نقرأ مشاهد Sentinel‑2 عبر السنة ونحسب الاحتياج…"):
            ts = get_ts(lat, lon)
            if not ts:
                st.info("تعذّر حساب السلسلة الآن."); return
            ts = [p for p in ts if p.ndvi_active == p.ndvi_active]
            s = (dt.date.fromisoformat(ts[0].date) - dt.timedelta(days=20)).isoformat()
            e = (dt.date.fromisoformat(ts[-1].date) + dt.timedelta(days=5)).isoformat()
            et0s = get_et0_series(lat, lon, s, e)
            rows = []
            for p in ts:
                et0 = power_et0.et0_around(et0s, p.date)
                kc = fao56.kc_single(p.ndvi_active)
                wk = kc * et0 * 7 / 1000 * area_ha * 10_000
                rows.append({"date": p.date, "ndvi": p.ndvi_active,
                             "et0": round(et0, 2), "kc": round(kc, 2),
                             "water_m3": round(wk)})
        df = pd.DataFrame(rows)
        df["d"] = pd.to_datetime(df["date"])
        base = alt.Chart(df).encode(x=alt.X("d:T", title="التاريخ"))
        line_n = base.mark_line(point=True, color="#2f9e44", strokeWidth=3).encode(
            y=alt.Y("ndvi:Q", scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(title="NDVI", titleColor="#2f9e44")))
        line_w = base.mark_line(point=True, color="#1565c0", strokeDash=[4, 4]).encode(
            y=alt.Y("water_m3:Q", axis=alt.Axis(title="م³/أسبوع", titleColor="#1565c0")))
        st.altair_chart(alt.layer(line_n, line_w).resolve_scale(y="independent"),
                        use_container_width=True)
        disp = df[["date", "ndvi", "et0", "kc", "water_m3"]].rename(columns={
            "date": "التاريخ", "ndvi": "NDVI", "et0": "ET₀", "kc": "Kc", "water_m3": "م³/أسبوع"})
        st.dataframe(disp, use_container_width=True, hide_index=True)
        st.caption(f"{len(rows)} مشاهد حقيقية · كل القيم محسوبة لا مُدخلة يدويًا.")


# ================================================================= SWA monitoring dashboard
SWA_DIR = BASE / "screenshots" / "swa"


@st.cache_data(show_spinner=False)
def load_swa_fields():
    fp = SWA_DIR / "fields.json"
    if not fp.exists():
        return []
    data = json.loads(fp.read_text(encoding="utf-8"))
    for f in data:
        thumb = SWA_DIR / f.get("thumb", "")
        if thumb.exists():
            b = base64.b64encode(thumb.read_bytes()).decode()
            f["thumb_uri"] = f"data:image/jpeg;base64,{b}"
        else:
            f["thumb_uri"] = ""
    return data


def _nf(x):
    return "—" if x is None else f"{int(round(x)):,}"


def swa_flow():
    import streamlit.components.v1 as components
    fields = load_swa_fields()
    if not fields:
        st.info("لا توجد بيانات حقول بعد. شغّل swa_fields.py لحساب الحقول."); return
    # feed the real artifact dashboard its data (thumbnails inlined as data URIs)
    payload = [{
        "name": f["name"], "lat": f["lat"], "lon": f["lon"], "area": f["area"],
        "crop": f.get("crop"), "crop_ar": f.get("crop_ar"), "ndvi": f.get("ndvi"),
        "soil_ar": f.get("soil_ar"), "week_m3": f.get("week_m3"),
        "annual_m3": f.get("annual_m3"), "applied_m3": f.get("applied_m3"),
        "avoid_m3": f.get("avoid_m3"), "status": f.get("status", "idle"),
        "thumb": f.get("thumb_uri", ""),
        # extra metrics for the per-field detail view
        "et0": f.get("et0"), "kc": f.get("kc"), "scene": f.get("scene"),
        "elev": f.get("elev"), "idle_pct": f.get("idle_pct"),
        "active_pct": f.get("active_pct"), "over_pct": f.get("over_pct"),
    } for f in fields]
    tmpl = (BASE / "frontend" / "swa_dashboard.html").read_text(encoding="utf-8")
    html = ("<!doctype html>\n<meta charset='utf-8'>\n"
            + tmpl.replace("__FIELDS__", json.dumps(payload, ensure_ascii=False)))
    components.html(html, height=1080, scrolling=True)


# ================================================================= entry state machine
if "entry" not in st.session_state:
    st.session_state.entry = None


def landing():
    st.markdown("<h3 style='text-align:center'>اختر كيف تبدأ</h3>",
                unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        st.markdown(f'<div class="choice">{ICON_PIN}<h3>أدخل إحداثيات حقلك</h3>'
                    '<p>الصق إحداثية من خرائط جوجل، ونتكفّل بسحب صور القمر الصناعي '
                    'والمناخ وحساب الاحتياج تلقائيًا.</p></div>', unsafe_allow_html=True)
        if st.button("البدء بالإحداثيات", key="pick_coord", type="primary",
                     use_container_width=True):
            st.session_state.entry = "coord"; st.rerun()
    with c2:
        st.markdown(f'<div class="choice">{ICON_IMG}<h3>ارفع صور حقلك</h3>'
                    '<p>ارفع صور حقلك من EO Browser، أو جرّب فورًا على الحقل '
                    'النموذجي الجاهز المرفق في المنصة.</p></div>', unsafe_allow_html=True)
        if st.button("البدء برفع الصور", key="pick_upload", type="primary",
                     use_container_width=True):
            st.session_state.entry = "upload"; st.rerun()
    with c3:
        st.markdown(f'<div class="choice">{ICON_GRID}<h3>لوحة الهيئة السعودية للمياه</h3>'
                    '<p>مراقبة كل الحقول المرويّة من المياه الجوفية في المنطقة: '
                    'استهلاكها ومؤشراتها ومحاصيلها في لوحة واحدة.</p></div>',
                    unsafe_allow_html=True)
        if st.button("فتح لوحة المراقبة", key="pick_swa", type="primary",
                     use_container_width=True):
            st.session_state.entry = "swa"; st.rerun()


# quick-pick farms for testers (label, coordinate string)
FARM_PRESETS = [
    ("مزرعة الساحل · طماطم", "21°12'43.12\"N 39°39'51.46\"E"),
    ("بابايا الليث · بابايا", "20°35'00.01\"N 40°29'35.58\"E"),
    ("نخيل رهاط · تمر", "22°04'43.66\"N 40°01'41.40\"E"),
]


def _pick_coord(c):
    """Load a preset coordinate and auto-run the search on the next rerun."""
    st.session_state.coord_val = c
    st.session_state._auto_search = True


def _ge_url(lat, lon):
    """Open the exact point in Google Earth (web), tilted view."""
    return f"https://earth.google.com/web/@{lat},{lon},0a,1600d,35y,0h,0t,0r"


def render_field_map(lat, lon, fld=None, height=380, key="fmap"):
    """Satellite map at the farm. If fld is given, overlay its detected boundary."""
    try:
        import folium
        from streamlit_folium import st_folium
    except Exception:
        if st.session_state.get("tc"):
            st.image(st.session_state.tc, use_container_width=True)
        return
    m = folium.Map(location=[lat, lon], zoom_start=15, tiles=None, control_scale=True)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/"
              "World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="قمر صناعي").add_to(m)
    folium.Marker([lat, lon], tooltip="موقع الحقل").add_to(m)
    if fld is not None and getattr(fld, "overlay_datauri", ""):
        folium.raster_layers.ImageOverlay(
            image=fld.overlay_datauri, bounds=fld.overlay_bounds,
            opacity=0.9, interactive=False, cross_origin=False, zindex=1).add_to(m)
        try:
            m.fit_bounds(fld.overlay_bounds)
        except Exception:
            pass
    st_folium(m, height=height, use_container_width=True,
              returned_objects=[], key=key)


def coordinate_flow():
    st.subheader("موقع الحقل")
    st.session_state.setdefault("coord_val", DEFAULT_COORD)
    coord = st.text_input("أدخل إحداثية حقلك (من خرائط جوجل أو Google Earth)",
                          key="coord_val")
    st.caption("أو جرّب حقلًا جاهزًا بنقرة واحدة:")
    pcols = st.columns(len(FARM_PRESETS))
    for i, (label, c) in enumerate(FARM_PRESETS):
        pcols[i].button(label, key=f"preset_{i}", use_container_width=True,
                        on_click=_pick_coord, args=(c,))
    cb1, cb2 = st.columns(2)
    search = cb1.button("ابحث عن الموقع", type="primary", use_container_width=True)
    if st.session_state.pop("_auto_search", False):
        search = True
    try:
        _la, _lo = pc.parse_coord(coord)
        cb2.link_button("افتح في Google Earth", _ge_url(_la, _lo),
                        use_container_width=True)
    except Exception:
        cb2.button("افتح في Google Earth", disabled=True, use_container_width=True)

    if search:
        try:
            lat, lon = pc.parse_coord(coord)
            with st.spinner("نحدّد الموقع ونسحب صورة القمر الصناعي…"):
                place = pc.reverse_geocode(lat, lon)
                tc, _ = pc.fetch_truecolor(lat, lon)
            st.session_state.loc = dict(lat=lat, lon=lon, place=place)
            st.session_state.tc = (lambda b: (tc.save(b, "JPEG"), b.getvalue())[1])(io.BytesIO()) if tc else None
            st.session_state.analyzed_coord = False
        except Exception as ex:
            st.error(str(ex))

    if "loc" in st.session_state:
        loc = st.session_state.loc
        st.markdown("##### أكّد موقع الحقل")
        st.caption(f"{loc['place']} · {loc['lat']:.5f}, {loc['lon']:.5f}")
        if not st.session_state.get("analyzed_coord"):
            render_field_map(loc["lat"], loc["lon"], fld=None, height=360, key="m_confirm")
            if st.button("نعم، هذا حقلي — حلّله الآن", type="primary",
                         use_container_width=True):
                st.session_state.analyzed_coord = True
                st.rerun()

        if st.session_state.get("analyzed_coord"):
            soil, cid, kcb = soil_crop_controls("co_", loc["lat"], loc["lon"])
            with st.spinner("نقرأ مؤشر NDVI من Sentinel‑2 ونقيس مساحة الحقل وحدوده…"):
                et = get_et0(loc["lat"], loc["lon"])
                fld = get_field(loc["lat"], loc["lon"])
            ndvi_cls = ndvi_raw = None
            if fld is not None and fld.area_ha and fld.area_ha == fld.area_ha:
                area_ha, idle_pct = fld.area_ha, fld.empty_pct
                ndvi = fld.active_mean_ndvi
                src = f"Sentinel‑2 خام B4/B8 — مشهد {fld.scene_date}"
                ndvi_cls, ndvi_raw = fld.classified_png, fld.ndvi_png
                st.markdown('<div class="rec"><div class="l">قياس الحقل من القمر الصناعي</div>'
                            f'<div class="n">المساحة المقدَّرة ≈ {area_ha:g} هكتار · '
                            f'المزروع {fld.used_pct}٪ · الفارغ {fld.empty_pct}٪</div></div>',
                            unsafe_allow_html=True)
                render_variables({
                    "مساحة الحقل (مقيسة)": f"{area_ha:g} هكتار",
                    "المساحة المزروعة": f"{fld.used_ha:g} هـ ({fld.used_pct}٪)",
                    "الأرض الفارغة": f"{fld.empty_ha:g} هـ ({fld.empty_pct}٪)",
                    "مشهد القمر": fld.scene_date,
                })
                render_field_map(loc["lat"], loc["lon"], fld=fld, height=420, key="m_result")
                st.caption("الحدّ الأصفر على الخريطة هو حدود الحقل المكتشفة من مؤشر NDVI "
                           "(Sentinel‑2، ~10م/بكسل). المساحة = بكسلات الحقل × مساحة البكسل؛ "
                           "المزروع مقابل الفارغ من عتبة الخضرة داخل الحدّ.")
                if area_ha > 150:
                    st.info("هذه النقطة داخل منطقة زراعية متّصلة واسعة؛ الحدّ والمساحة يمثّلان "
                            "الكتلة المزروعة المتّصلة حول النقطة، لا حقلاً مفردًا. حرّك الدبوس "
                            "إلى حقلك المحدّد لقياس أدق.")
                else:
                    st.success(f"قِيست مساحة الحقل وحدوده من Sentinel‑2 "
                               f"(مشهد {fld.scene_date}، تغطية صافية {fld.valid_fraction*100:.0f}٪).")
            else:
                st.warning("تعذّر قياس الحقل من Sentinel‑2 الآن — أدخل مساحة الحقل يدويًا كبديل.")
                area_ha = st.number_input("مساحة الحقل (هكتار)", 1.0, 2000.0, 20.0, 5.0,
                                          key="co_area_fb")
                ndvi, idle_pct, src = 0.58, 20, "تقدير من اللون الحقيقي — تعذّر سحب Sentinel‑2"
                if st.session_state.get("tc"):
                    img = Image.open(io.BytesIO(st.session_state["tc"])).convert("RGB")
                    e, _a, idl = pc.vari_estimate(img)
                    ndvi, idle_pct = float(e), round(idl * 100)
                render_field_map(loc["lat"], loc["lon"], fld=None, height=360, key="m_fb")

            rep = pc.build_report(loc["lat"], loc["lon"], loc["place"], area_ha,
                                  ndvi, src, idle_pct, et, kcb_max=kcb, soil=soil,
                                  current_crop_id=cid, month=MONTH)
            st.divider()
            render_report(rep, area_ha, soil, truecolor=st.session_state.get("tc"),
                          ndvi_classified=ndvi_cls, ndvi_raw=ndvi_raw, key="co")
            render_timeseries(loc["lat"], loc["lon"], area_ha)


def upload_flow():
    st.subheader("صور الحقل")
    use_own = st.toggle("أريد رفع صوري بدلاً من الحقل النموذجي")
    up_ndvi = up_tc = None
    if use_own:
        c1, c2, c3, c4 = st.columns(4)
        up_tc = c1.file_uploader("لون حقيقي", type=["jpg", "jpeg", "png"])
        c2.file_uploader("لون زائف (NIR)", type=["jpg", "jpeg", "png"])
        up_ndvi = c3.file_uploader("مؤشر NDVI (إلزامي)", type=["jpg", "jpeg", "png"])
        c4.file_uploader("مؤشر الرطوبة", type=["jpg", "jpeg", "png"])
    else:
        st.info("جاهز للتجربة: يُعرض الآن الحقل النموذجي في منطقة مكة المكرمة. "
                "اضبط العوامل بالأسفل ثم اضغط «حلّل الحقل».")
        c1, c2, c3 = st.columns(3)
        c1.image(str(SAMPLE_TC), caption="لون حقيقي", use_container_width=True)
        c2.image(str(SAMPLE_NDVI), caption="مؤشر NDVI", use_container_width=True)
        c3.image(str(SAMPLE_FC), caption="لون زائف", use_container_width=True)

    colA, colB = st.columns([1, 2])
    area = colA.number_input("مساحة المحور (هكتار)", 1.0, 2000.0, 50.0, 5.0, key="u_area")
    coord = colB.text_input("إحداثية الموقع (لجلب المناخ ET₀ والتربة)", value=DEFAULT_COORD, key="u_coord")
    try:
        _ula, _ulo = pc.parse_coord(coord)
    except Exception:
        _ula = _ulo = None
    soil, cid, kcb = soil_crop_controls("up_", _ula, _ulo)

    if st.button("حلّل الحقل", type="primary", use_container_width=True):
        try:
            if use_own:
                if up_ndvi is None:
                    st.error("ارفع صورة مؤشر NDVI على الأقل."); st.stop()
                tmp = BASE / "backend" / "_uploaded_ndvi.png"
                Image.open(up_ndvi).convert("RGB").save(tmp)
                ndvi_path = str(tmp)
                tc_bytes = up_tc.getvalue() if up_tc else None
                raw_bytes = up_ndvi.getvalue()
            else:
                ndvi_path = str(SAMPLE_NDVI)
                tc_bytes = SAMPLE_TC.read_bytes()
                raw_bytes = SAMPLE_NDVI.read_bytes()
            with st.spinner("نحلّل مؤشر NDVI ونسحب المناخ ونحسب الاحتياج…"):
                stats = ndvi_image.analyse(ndvi_path)
                lat, lon = pc.parse_coord(coord)
                et = get_et0(lat, lon)
                place = pc.reverse_geocode(lat, lon)
                rep = pc.build_report(lat, lon, place, area,
                                      round(stats.active_crop_mean_ndvi, 3),
                                      "مؤشر NDVI من مركّب Sentinel‑2 مرفوع",
                                      round(stats.bare_fraction * 100), et,
                                      kcb_max=kcb, soil=soil, current_crop_id=cid, month=MONTH)
                cls = classified_png(ndvi_path)
            st.session_state.upload_result = {
                "rep": rep, "tc": tc_bytes, "cls": cls, "raw": raw_bytes,
                "lat": lat, "lon": lon, "area": area, "soil": soil}
        except Exception as ex:
            st.error(f"تعذّرت المحاكاة: {ex}")

    if "upload_result" in st.session_state:
        r = st.session_state.upload_result
        st.divider()
        render_report(r["rep"], r["area"], r["soil"], truecolor=r["tc"],
                      ndvi_classified=r["cls"], ndvi_raw=r["raw"], key="up")
        render_timeseries(r["lat"], r["lon"], r["area"])


# ----------------------------------------------------------------- route
if st.session_state.entry is None:
    render_hero()
    landing()
else:
    back = st.columns([1, 5])[0]
    if back.button("رجوع إلى البداية"):
        for k in ("loc", "tc", "analyzed_coord", "upload_result"):
            st.session_state.pop(k, None)
        st.session_state.entry = None
        st.rerun()
    # the dashboard carries its own full header + rail, so skip the hero there
    if st.session_state.entry != "swa":
        render_hero()
    st.write("")
    {"coord": coordinate_flow, "upload": upload_flow, "swa": swa_flow}[st.session_state.entry]()

st.divider()
st.caption("مرواء — نموذج أولي · تنمية ثون 2026 · المحور البيئي والاستدامة · منطقة مكة المكرمة")
