# مرواء (Mirwa) — Proof-of-Concept engine

Satellite-based per-field **weekly crop water requirement** via FAO-56
(`NDVI → Kc → ET₀ → ETc`), plus avoidable-waste and idle-land estimates.
This folder is the **PoC / computational core** (the "hardest part" the judges
want proven). The map UI and auto-fetch of raw Sentinel-2 bands are the next
build step (see *What is real vs. pending*).

## Run it

```bash
cd mirwa/backend
python report.py          # end-to-end on the demo field; prints the decision
python power_et0.py       # just the ET0 (live NASA POWER call)
python ndvi_image.py ../../photo_2_2026-11-11_21-19-04.jpg   # just NDVI stats
```

Outputs written to `mirwa/backend/`: `field_report.json`, `ndvi_classified.png`.

## Result on the tested field (coords `21.2120°N, 39.6643°E`, Makkah region)

| Quantity | Value | Label |
|---|---|---|
| ET₀ (reference ET) | **5.69 mm/day** (30-day mean, range 5.04–6.53) | measured — NASA POWER reanalysis |
| Active-crop NDVI | **0.584** | proxy — recovered from the Sentinel-2 NDVI composite |
| Kc (FAO-56, SIMS) | 0.737 | modelled |
| ETc (water demand) | **4.19 mm/day = 29.3 mm/week** | modelled — FAO-56 |
| **Weekly demand, 50 ha pivot** | **≈ 14,700 m³/week** (293 m³/ha) | modelled |
| Vigour band | 10,700 (NDVI 0.45) – 19,500 (NDVI 0.75) m³/wk | modelled |
| Scene cover | active 49.5% · bare/fallow 31.4% · sparse 19.1% | measured from composite |
| Avoidable waste | ≈ 12,100 m³/wk (~41% of applied) if 50%→85% efficiency | **estimate** — no field meter |

`ndvi_classified.png` is the deck asset: green = active crop, yellow = sparse,
tan = bare/fallow. The half-green/half-tan pivots and fully-tan circles are the
idle-land story made visible.

## What is real vs. pending (honesty — matches the deck)

- **Real / measured:** ET₀ from NASA POWER (observed reanalysis meteorology for
  the exact coordinates — *not* a forecast). Scene NDVI classification.
- **Real / modelled:** the full FAO-56 chain and ETc number. Cross-checked
  against an independent Hargreaves ET₀ (3.8 mm/day); PM reads higher because of
  the large vapour-pressure deficit + wind (arid advection), which is expected
  and correct — verified component-by-component.
- **Proxy (pending raw-band access):** NDVI is recovered by inverting the
  colour ramp of the NDVI image you exported (good to ~±0.05–0.1). Production
  computes NDVI numerically from raw Sentinel-2 `B4/B8` via Google Earth Engine
  or Sentinel Hub — the one credential/blocker from the handoff still to wire.
- **Estimate (no field meter):** "applied water" and waste use a cited, *indicative*
  irrigation-efficiency figure (~50%, FEWS NET), not a flow-meter.

## ⚠ Two things to decide (flagged for the deck)

1. **Location vs. the deck's "الطائف (Taif)".** These coordinates are at
   **~45 m elevation, ~32 °C** — low **coastal** Makkah region (بحرة / وادي فاطمة
   area between Jeddah and Makkah), **not** the Taif highlands (~1,900 m, cool)
   named on slides 2/3/5/6. Both are in منطقة مكة المكرمة (region alignment is
   fine), but the wording should match the field actually used, or run a true
   Taif field. ET₀ (and therefore the water number) differs a lot between hot
   lowland and cool highland.
2. **Pivot area (50 ha)** is a representative placeholder; the real number comes
   from the farmer's drawn boundary. All volumes scale linearly with area, and
   per-ha figures are given so the assumption is transparent.

## Citations
- FAO-56: Allen, Pereira, Raes, Smith (1998).
- NDVI→Kc: Allen & Pereira (2009); Calera et al. (2017); SIMS.
- ET₀ meteorology: NASA POWER (power.larc.nasa.gov).
- Water context: MEWA (ag = 84% of water; 90% non-renewable); GASTAT Water
  Accounts 2023 (ag 12,298 Mm³/yr); FEWS NET (≈50% irrigation efficiency, indicative).

## The platform (Streamlit) — `mirwa/app.py`

The main UI. Two ways in, one actionable report.

```bash
pip install streamlit folium streamlit-folium numpy pillow requests \
            rasterio pystac-client planetary-computer
streamlit run mirwa/app.py
# open http://localhost:8501   (also wired as preview server "mirwa-streamlit")
```

**Input modes**
1. **Coordinate** — paste a Google-Earth coordinate (DMS `21°12'43.12"N 39°39'51.46"E`
   or decimal). The app geocodes it (confirms *منطقة مكة المكرمة*), shows it on a
   satellite map to **confirm**, then **auto-fetches** everything: the true-colour
   image (Esri, keyless), **real Sentinel-2 bands** B04/B08 for the field window
   (Microsoft Planetary Computer STAC, keyless) → true `NDVI=(B8−B4)/(B8+B4)`,
   cloud-masked via SCL, and the climate (NASA POWER, live). Example run: scene
   2026-11-01, 0 % cloud, active NDVI 0.69. If the satellite fetch is unavailable
   it falls back to a VARI estimate from the true-colour image (clearly flagged).
2. **Upload** — drop in the true-colour / false-colour / **NDVI** / moisture images
   (or tick the sample field). NDVI is recovered from the real composite; this is
   the precise path (matches the backend: 14,657 m³/wk, waste 12,070, idle 31%).

**Output — written for the reader, not the engineer**
- A plain-language **traffic-light** status (over-irrigating / optimal / under).
- **👨‍🌾 تقرير المزارع:** one headline recommendation ("اسقِ هذا الأسبوع ≈ X م³"),
  water+cost saving, idle-land opportunity, and a one-line "why".
- **🏛️ تقرير الهيئة السعودية للمياه:** consumptive use (ETc), avoidable abstraction,
  % over-need, annualized draw, groundwater framing.
- **🔬 التفاصيل التقنية** (collapsed expander): every input, the ET₀ breakdown, the
  full `NDVI→fc→Kcb→Kc→ETc` chain, the equations, and the sources.

Idle land is measured **inside the cultivated footprint only** (not the surrounding
desert), so a green pivot never reads as "mostly idle". Screenshots in
`mirwa/screenshots/`.

> Honesty carried through the UI: ET₀ = measured (NASA POWER), NDVI in coordinate
> mode = **measured from real Sentinel-2 raw bands** (B4/B8, Planetary Computer,
> cloud-masked), NDVI in upload mode = recovered from the user's NDVI composite,
> the FAO-56 chain = modelled, applied-water/waste = estimate (no field meter).

### Earlier static prototype — `mirwa/frontend/index.html`
A self-contained HTML version of the decision screen (Leaflet + JS FAO-56 engine,
live NASA POWER). Kept as a lightweight alternative; run with
`python -m http.server 8777 --directory mirwa/frontend`.

## Files
```
mirwa/
  app.py             Streamlit platform (coordinate + upload modes, actionable report)
mirwa/backend/
  fao56.py           NDVI→Kc→ETc, weekly demand, waste   (cited)
  power_et0.py       FAO-56 Penman-Monteith ET0 from NASA POWER (live)
  ndvi_image.py      recover NDVI from the composite; scene classification
  sentinel2.py       REAL Sentinel-2 NDVI (B4/B8) via Planetary Computer, cloud-masked
  platform_core.py   coord parse (DMS), Esri auto-fetch, geocode, VARI, report builder
  report.py          assemble + run the per-field decision (CLI)
mirwa/frontend/
  index.html         earlier static prototype (RTL, Leaflet, JS FAO-56 engine)
  truecolor.jpg  ndvi_classified.png  ndvi_raw.jpg   (demo-field imagery)
mirwa/screenshots/   Streamlit report screenshots (farmer, SWA, coordinate, technical)
mirwa/
  prototype_slide4.jpg   screenshot of the static prototype for the deck
```
