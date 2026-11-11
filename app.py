# -*- coding: utf-8 -*-
"""
مرواء (Mirwa) — منصة ترشيد ريّ الحقول من صور الأقمار الاصطناعية.

طريقتان للبدء: إدخال إحداثية الحقل (نسحب الصور والمناخ تلقائيًا)، أو رفع صور
الحقل الجاهزة (ومعها حقل نموذجي جاهز للتجربة). المخرجات تقرير عملي للمزارع
وللهيئة السعودية للمياه، مع تفاصيل تقنية كاملة عند الطلب.
"""
import sys
import io
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

st.set_page_config(page_title="مرواء — منصة ترشيد الري", page_icon="💧", layout="wide")
MONTH = dt.date.today().month
DEFAULT_COORD = "21°12'43.12\"N 39°39'51.46\"E"
SAMPLE_TC = BASE / "data" / "sample_truecolor.jpg"
SAMPLE_NDVI = BASE / "data" / "sample_ndvi.jpg"
SAMPLE_FC = BASE / "data" / "sample_falsecolor.jpg"

# ----------------------------------------------------------------- styling (RTL, minimal)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800;900&display=swap');
html, body, [class*="css"], .stApp, button, input, textarea, select { font-family:'Cairo',sans-serif !important; }
.stApp { direction: rtl; background:#f6f8fb; }
.block-container { padding-top: 1.1rem; max-width: 1060px; }
h1,h2,h3,h4,p,span,div,label,li { text-align: right; }
.stTabs [data-baseweb="tab-list"]{ direction: rtl; gap:4px; }
.stTabs [data-baseweb="tab"]{ font-weight:700; }

.head{background:#0a2d6e;color:#fff;border-radius:18px;padding:18px 24px;margin-bottom:18px}
.head h1{margin:0;font-size:26px;font-weight:900}
.head p{margin:6px 0 0;font-size:14px;opacity:.9;font-weight:400;max-width:720px}

/* buttons: full width, consistent, no offset */
.stButton>button, .stDownloadButton>button{
  width:100%; border-radius:12px; font-weight:800; font-size:16px; padding:12px 16px;
  border:1px solid #d6deea; background:#fff; color:#0a2d6e; transition:.15s; }
.stButton>button:hover{ border-color:#0a2d6e; }
.stButton>button[kind="primary"]{ background:#0a2d6e; color:#fff; border:0; }
.stButton>button[kind="primary"]:hover{ background:#0b347f; }

/* big choice cards */
.choice{background:#fff;border:1px solid #e2e8f1;border-radius:18px;padding:26px 22px 8px;
  text-align:center;min-height:210px;box-shadow:0 2px 14px rgba(10,45,110,.05)}
.choice svg{margin-bottom:10px}
.choice h3{margin:0 0 6px;font-size:20px;color:#0a2d6e;text-align:center}
.choice p{margin:0 auto;font-size:13.5px;color:#5c6b86;max-width:300px;text-align:center}

.panel{background:#fff;border:1px solid #e2e8f1;border-radius:16px;padding:16px 18px;margin-bottom:14px}
.rec{background:#0a2d6e;color:#fff;border-radius:14px;padding:18px 22px;margin:4px 0 16px}
.rec .l{font-size:13px;opacity:.85}
.rec .n{font-size:26px;font-weight:900;margin-top:6px;line-height:1.35}

/* big variables */
.vargrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:2px 0 14px}
.var{background:#f3f6fb;border:1px solid #e4ebf4;border-radius:13px;padding:12px 14px}
.var .k{font-size:12.5px;color:#5c6b86;font-weight:600}
.var .v{font-size:18px;color:#0a2d6e;font-weight:900;margin-top:3px}

/* crop list */
.cropgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;margin-top:6px}
.crop{display:flex;gap:12px;align-items:center;background:#fff;border:1px solid #e6edf6;border-radius:13px;padding:11px 13px}
.crop .b{flex:1}
.crop .n{font-weight:800;color:#15233d;font-size:15px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.crop .m{font-size:12px;color:#5c6b86;margin-top:3px;line-height:1.6}
.wb{font-size:10.5px;font-weight:800;color:#fff;padding:2px 8px;border-radius:999px}

.card{background:#fff;border:1px solid #e6edf6;border-radius:13px;padding:14px 16px;margin-bottom:10px}
.card .t{font-weight:800;color:#0a2d6e;font-size:15px;margin-bottom:4px}
.card .v{font-size:14px;color:#1f2d45;line-height:1.85}
.note{font-size:12px;color:#5c6b86;line-height:1.8}
.tag{font-size:10.5px;font-weight:800;padding:2px 9px;border-radius:999px;color:#fff}
.tm{background:#1565c0}.tc{background:#2f9e44}.te{background:#C1551C}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="head">
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


ICON_PIN = ('<svg width="54" height="54" viewBox="0 0 24 24" fill="none" stroke="#0a2d6e" '
            'stroke-width="1.7"><path d="M12 21c4-5 7-8.5 7-12a7 7 0 1 0-14 0c0 3.5 3 7 7 12z"/>'
            '<circle cx="12" cy="9" r="2.6"/></svg>')
ICON_IMG = ('<svg width="54" height="54" viewBox="0 0 24 24" fill="none" stroke="#0a2d6e" '
            'stroke-width="1.7"><rect x="3" y="4" width="18" height="16" rx="2"/>'
            '<circle cx="8.5" cy="9.5" r="1.6"/><path d="M4 18l5-5 4 4 3-3 4 4"/></svg>')


# ----------------------------------------------------------------- shared controls / renderers
def soil_crop_controls(prefix):
    c1, c2 = st.columns(2)
    soil_label = c1.selectbox("نوع تربة الحقل", list(crops.SOILS.values()),
                              key=prefix + "soil")
    soil = next(k for k, v in crops.SOILS.items() if v == soil_label)
    opts = crops.current_crop_options()
    names = [n for _, n in opts]
    name = c2.selectbox("المحصول المزروع حاليًا", names, key=prefix + "crop",
                        help="يحدّد معامل المحصول Kc في حساب الاحتياج المائي. "
                             "أمّا مؤشر الخضرة NDVI فيبقى مقيسًا من القمر الصناعي، "
                             "لا يُدخل يدويًا.")
    cid = opts[names.index(name)][0]
    return soil, cid, crops.kcb_max(cid)


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


def render_report(rep, area_ha, soil, truecolor=None, ndvi_classified=None, ndvi_raw=None):
    s = rep.simple
    msg = f"حالة الحقل: {s['status_ar']} — {rep.place}"
    (st.error if s["status"] == "over" else st.success if s["status"] == "ok" else st.warning)(msg)

    tab_f, tab_w = st.tabs(["تقرير المزارع", "تقرير الهيئة السعودية للمياه"])

    with tab_f:
        f = s["farmer"]
        st.markdown(f'<div class="rec"><div class="l">التوصية لهذا الأسبوع</div>'
                    f'<div class="n">{f["headline"]}</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="card"><div class="t">عوامل حقلك</div></div>',
                    unsafe_allow_html=True)
        render_variables(s["variables"])
        render_crop_list(area_ha, soil, MONTH)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="card"><div class="t">توفير الماء والتكلفة</div>'
                        f'<div class="v">{f["save"]}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="card"><div class="t">أرض غير مستغلّة</div>'
                        f'<div class="v">{f["idle"]}</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card"><div class="t">كيف حُسب هذا الرقم؟</div>'
                    f'<div class="v">{f["why"]}</div></div>', unsafe_allow_html=True)

    with tab_w:
        w = s["swa"]
        m1, m2, m3 = st.columns(3)
        m1.metric("الاستهلاك الفعلي (ETc) أسبوعيًا", f"{w['consumptive_week']:,} م³")
        m2.metric("هدر يمكن تفاديه أسبوعيًا", f"{w['avoidable_week_m3']:,} م³",
                  f"-{w['avoidable_pct']:.0f}%")
        m3.metric("الري فوق حاجة المحصول", f"{w['over_pct']:.0f}%")
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


# ================================================================= entry state machine
if "entry" not in st.session_state:
    st.session_state.entry = None


def landing():
    st.markdown("<h3 style='text-align:center'>اختر كيف تبدأ بتحليل حقلك</h3>",
                unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
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


def coordinate_flow():
    st.subheader("موقع الحقل")
    col_in, col_area = st.columns([2, 1])
    coord = col_in.text_input("أدخل إحداثية حقلك (من خرائط جوجل أو Google Earth)",
                              value=DEFAULT_COORD)
    area = col_area.number_input("مساحة المحور (هكتار)", 1.0, 2000.0, 50.0, 5.0)
    if st.button("ابحث عن الموقع", type="primary", use_container_width=True):
        try:
            lat, lon = pc.parse_coord(coord)
            with st.spinner("نحدّد الموقع ونسحب صورة القمر الصناعي…"):
                place = pc.reverse_geocode(lat, lon)
                tc, _ = pc.fetch_truecolor(lat, lon)
            st.session_state.loc = dict(lat=lat, lon=lon, place=place, area=area)
            st.session_state.tc = (lambda b: (tc.save(b, "JPEG"), b.getvalue())[1])(io.BytesIO()) if tc else None
            st.session_state.analyzed_coord = False
        except Exception as ex:
            st.error(str(ex))

    if "loc" in st.session_state:
        loc = st.session_state.loc
        st.markdown("##### أكّد موقع الحقل")
        cmap, cinfo = st.columns([1.2, 1])
        with cmap:
            try:
                import folium
                from streamlit_folium import st_folium
                m = folium.Map(location=[loc["lat"], loc["lon"]], zoom_start=14,
                               tiles=None, control_scale=True)
                folium.TileLayer(
                    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/"
                          "World_Imagery/MapServer/tile/{z}/{y}/{x}",
                    attr="Esri").add_to(m)
                folium.Marker([loc["lat"], loc["lon"]]).add_to(m)
                folium.Circle([loc["lat"], loc["lon"]],
                              radius=(loc["area"] * 10000 / 3.14159) ** 0.5,
                              color="#ffcc00", fill=False).add_to(m)
                st_folium(m, height=300, use_container_width=True)
            except Exception:
                if st.session_state.get("tc"):
                    st.image(st.session_state.tc, use_container_width=True)
        with cinfo:
            st.markdown(f"**الموقع:** {loc['place']}")
            st.markdown(f"**الإحداثية:** {loc['lat']:.5f}, {loc['lon']:.5f}")
            if st.session_state.get("tc"):
                st.image(st.session_state.tc, caption="الصورة المسحوبة تلقائيًا",
                         use_container_width=True)
            if st.button("نعم، هذا حقلي — حلّله الآن", type="primary",
                         use_container_width=True):
                st.session_state.analyzed_coord = True

        if st.session_state.get("analyzed_coord"):
            soil, cid, kcb = soil_crop_controls("co_")
            with st.spinner("نقرأ مؤشر NDVI من Sentinel‑2 والمناخ ونحسب الاحتياج…"):
                et = get_et0(loc["lat"], loc["lon"])
                s2 = get_s2(loc["lat"], loc["lon"])
            ndvi_cls = ndvi_raw = None
            if s2 is not None and s2.active_mean_ndvi == s2.active_mean_ndvi:
                ndvi, idle_pct = float(s2.active_mean_ndvi), round(s2.idle_fraction * 100)
                src = f"Sentinel‑2 خام B4/B8 — مشهد {s2.scene_date}، غيوم {s2.cloud_cover:.0f}%"
                ndvi_cls, ndvi_raw = s2.classified_png, s2.ndvi_png
                st.success(f"قرأنا مؤشر NDVI حقيقيًا من نطاقات Sentinel‑2 "
                           f"(مشهد {s2.scene_date}، تغطية صافية {s2.valid_fraction*100:.0f}%).")
            else:
                ndvi, idle_pct, src = 0.58, 20, "تقدير من اللون الحقيقي — تعذّر سحب Sentinel‑2"
                if st.session_state.get("tc"):
                    img = Image.open(io.BytesIO(st.session_state["tc"])).convert("RGB")
                    e, _a, idl = pc.vari_estimate(img)
                    ndvi, idle_pct = float(e), round(idl * 100)
                st.warning("تعذّر سحب Sentinel‑2 الآن — عرضنا تقديرًا من اللون الحقيقي.")
            rep = pc.build_report(loc["lat"], loc["lon"], loc["place"], loc["area"],
                                  ndvi, src, idle_pct, et, kcb_max=kcb, soil=soil,
                                  current_crop_id=cid, month=MONTH)
            st.divider()
            render_report(rep, loc["area"], soil, truecolor=st.session_state.get("tc"),
                          ndvi_classified=ndvi_cls, ndvi_raw=ndvi_raw)
            render_timeseries(loc["lat"], loc["lon"], loc["area"])


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
    coord = colB.text_input("إحداثية الموقع (لجلب المناخ ET₀)", value=DEFAULT_COORD, key="u_coord")
    soil, cid, kcb = soil_crop_controls("up_")

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
                      ndvi_classified=r["cls"], ndvi_raw=r["raw"])
        render_timeseries(r["lat"], r["lon"], r["area"])


# ----------------------------------------------------------------- route
if st.session_state.entry is None:
    landing()
else:
    if st.button("رجوع إلى البداية"):
        for k in ("loc", "tc", "analyzed_coord", "upload_result"):
            st.session_state.pop(k, None)
        st.session_state.entry = None
        st.rerun()
    st.write("")
    (coordinate_flow if st.session_state.entry == "coord" else upload_flow)()

st.divider()
st.caption("مرواء — نموذج أولي · تنمية ثون 2026 · المحور البيئي والاستدامة · منطقة مكة المكرمة")
