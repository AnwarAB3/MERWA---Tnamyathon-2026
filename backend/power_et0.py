"""
power_et0.py — Reference evapotranspiration ET0 (FAO-56 Penman-Monteith)
from NASA POWER daily point data.

We do NOT forecast weather. We pull observed / reanalysis daily meteorology
(NASA POWER, free, no API key) and compute ET0 with the FAO-56 PM equation
exactly as in the paper (Allen et al., 1998, eq. 6). This is the honest
"satellite + observational ET0" framing, not "zero weather data".

NASA POWER: https://power.larc.nasa.gov/   (Community = AG)
Parameters used (units returned by the API, confirmed in the response header):
  T2M, T2M_MAX, T2M_MIN  [C]   air temperature at 2 m
  RH2M                   [%]   relative humidity at 2 m
  WS2M                   [m/s] wind speed at 2 m (already at 2 m -> no scaling)
  ALLSKY_SFC_SW_DWN      [MJ/m^2/day] incoming solar radiation Rs
  PS                     [kPa] surface pressure
Elevation z comes from the POWER geometry (3rd coordinate).
"""
from __future__ import annotations
import math
import datetime as dt
from dataclasses import dataclass
import requests

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = "T2M,T2M_MAX,T2M_MIN,RH2M,WS2M,ALLSKY_SFC_SW_DWN,PS"


@dataclass
class ET0Result:
    lat: float
    lon: float
    elevation_m: float
    start: str
    end: str
    n_days: int
    et0_mean_mm_day: float
    et0_min_mm_day: float
    et0_max_mm_day: float
    tmean_mean_c: float
    rh_mean_pct: float
    per_day: list   # list of (date, et0_mm_day)


def _svp(t_c: float) -> float:
    """Saturation vapour pressure [kPa] at temperature t (FAO-56 eq. 11)."""
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


def _extraterrestrial_ra(lat_deg: float, doy: int) -> float:
    """Extraterrestrial radiation Ra [MJ/m^2/day] (FAO-56 eqs. 21-25)."""
    phi = math.radians(lat_deg)
    dr = 1.0 + 0.033 * math.cos(2 * math.pi / 365 * doy)       # eq.23
    decl = 0.409 * math.sin(2 * math.pi / 365 * doy - 1.39)    # eq.24
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(decl))))  # eq.25
    gsc = 0.0820  # MJ/m^2/min solar constant
    ra = (24 * 60 / math.pi) * gsc * dr * (
        ws * math.sin(phi) * math.sin(decl)
        + math.cos(phi) * math.cos(decl) * math.sin(ws))       # eq.21
    return ra


def et0_penman_monteith_day(tmax, tmin, rh_mean, u2, rs, ps, lat, elev, doy):
    """FAO-56 Penman-Monteith reference ET0 [mm/day] for one day (eq. 6)."""
    tmean = (tmax + tmin) / 2.0
    es = (_svp(tmax) + _svp(tmin)) / 2.0           # eq.12
    ea = rh_mean / 100.0 * es                       # from RHmean (eq.19 form)
    delta = 4098 * _svp(tmean) / (tmean + 237.3) ** 2   # eq.13
    gamma = 0.000665 * ps                            # eq.8 (P in kPa)

    ra = _extraterrestrial_ra(lat, doy)
    rso = (0.75 + 2e-5 * elev) * ra                  # eq.37 clear-sky
    rns = (1 - 0.23) * rs                            # eq.38 (albedo 0.23)
    sigma = 4.903e-9                                 # MJ K^-4 m^-2 day^-1
    tmaxk = tmax + 273.16
    tmink = tmin + 273.16
    cloud = 1.35 * min(rs / rso, 1.0) - 0.35 if rso > 0 else 0.05
    rnl = sigma * ((tmaxk ** 4 + tmink ** 4) / 2.0) * (0.34 - 0.14 * math.sqrt(max(ea, 0.0))) * cloud  # eq.39
    rn = rns - rnl
    g = 0.0                                          # daily G ~ 0 (eq.42)

    num = 0.408 * delta * (rn - g) + gamma * (900.0 / (tmean + 273.0)) * u2 * (es - ea)
    den = delta + gamma * (1 + 0.34 * u2)
    return max(0.0, num / den)


def fetch_et0(lat: float, lon: float,
              start: dt.date | None = None,
              end: dt.date | None = None,
              timeout: int = 60) -> ET0Result:
    """Fetch daily meteorology from NASA POWER and return averaged ET0.

    Default window: a ~30-day period ending ~9 days ago (POWER has a short
    latency), representative of the current season at the site.
    """
    if end is None:
        end = dt.date.today() - dt.timedelta(days=9)
    if start is None:
        start = end - dt.timedelta(days=29)
    url = (f"{POWER_URL}?parameters={PARAMS}&community=AG"
           f"&longitude={lon}&latitude={lat}"
           f"&start={start:%Y%m%d}&end={end:%Y%m%d}&format=JSON")
    d = requests.get(url, timeout=timeout).json()
    elev = d["geometry"]["coordinates"][2]
    pp = d["properties"]["parameter"]
    days = sorted(pp["T2M"].keys())

    per_day, tmeans, rhs = [], [], []
    for day in days:
        tmax = pp["T2M_MAX"][day]; tmin = pp["T2M_MIN"][day]
        rh = pp["RH2M"][day];      u2 = pp["WS2M"][day]
        rs = pp["ALLSKY_SFC_SW_DWN"][day]; ps = pp["PS"][day]
        if any(v <= -900 for v in (tmax, tmin, rh, u2, rs, ps)):   # skip fill values
            continue
        doy = dt.datetime.strptime(day, "%Y%m%d").timetuple().tm_yday
        e0 = et0_penman_monteith_day(tmax, tmin, rh, u2, rs, ps, lat, elev, doy)
        per_day.append((day, round(e0, 3)))
        tmeans.append((tmax + tmin) / 2.0); rhs.append(rh)

    et0s = [e for _, e in per_day]
    n = len(et0s)
    return ET0Result(
        lat, lon, elev, f"{start:%Y%m%d}", f"{end:%Y%m%d}", n,
        sum(et0s) / n, min(et0s), max(et0s),
        sum(tmeans) / n, sum(rhs) / n, per_day)


def fetch_et0_series(lat: float, lon: float, start: dt.date, end: dt.date,
                     timeout: int = 60) -> dict:
    """Return {YYYYMMDD: ET0 mm/day} over an arbitrary range (for ETc-over-time)."""
    url = (f"{POWER_URL}?parameters={PARAMS}&community=AG"
           f"&longitude={lon}&latitude={lat}"
           f"&start={start:%Y%m%d}&end={end:%Y%m%d}&format=JSON")
    d = requests.get(url, timeout=timeout).json()
    elev = d["geometry"]["coordinates"][2]
    pp = d["properties"]["parameter"]
    out = {}
    for day in sorted(pp["T2M"].keys()):
        vals = (pp["T2M_MAX"][day], pp["T2M_MIN"][day], pp["RH2M"][day],
                pp["WS2M"][day], pp["ALLSKY_SFC_SW_DWN"][day], pp["PS"][day])
        if any(v <= -900 for v in vals):
            continue
        doy = dt.datetime.strptime(day, "%Y%m%d").timetuple().tm_yday
        out[day] = et0_penman_monteith_day(*vals, lat, elev, doy)
    return out


def et0_around(series: dict, date_iso: str, window: int = 15) -> float:
    """Mean ET0 within +/- window days of a scene date (falls back to overall mean)."""
    target = dt.datetime.strptime(date_iso, "%Y-%m-%d").date()
    vals = [v for k, v in series.items()
            if abs((dt.datetime.strptime(k, "%Y%m%d").date() - target).days) <= window]
    if not vals:
        vals = list(series.values())
    return sum(vals) / len(vals) if vals else float("nan")


if __name__ == "__main__":
    r = fetch_et0(21.2120, 39.6643)
    print(f"ET0 at {r.lat},{r.lon}  elev {r.elevation_m} m  "
          f"[{r.start}..{r.end}, {r.n_days} days]")
    print(f"  ET0 mean {r.et0_mean_mm_day:.2f} mm/day "
          f"(range {r.et0_min_mm_day:.2f}-{r.et0_max_mm_day:.2f})")
    print(f"  Tmean {r.tmean_mean_c:.1f} C  RH {r.rh_mean_pct:.0f}%")
