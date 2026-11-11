"""
fao56.py — The scientific core of مرواء (Mirwa).

NDVI -> Kc -> (ET0) -> ETc -> weekly crop water requirement, following
FAO Irrigation & Drainage Paper 56 (Allen et al., 1998) and the
reflectance-based crop-coefficient literature.

Nothing here is invented. Every coefficient is from a cited source; where a
coefficient is a modelling choice we expose it as a parameter and say so.

Citations
---------
* FAO-56: Allen R.G., Pereira L.S., Raes D., Smith M. (1998) "Crop
  evapotranspiration — Guidelines for computing crop water requirements".
  FAO Irrigation and Drainage Paper 56.
* Reflectance-based Kc / Kcb:
  - Allen R.G. & Pereira L.S. (2009) "Estimating crop coefficients from
    fraction of ground cover and height." Irrigation Science 28:17-34.
  - Calera A. et al. (2017) "Remote Sensing for Crop Water Management."
    Remote Sensing 9(10):1104.
  - SIMS model: Melton F. et al. (2012); the fraction-of-cover (fc) route.
"""
from __future__ import annotations
from dataclasses import dataclass


# --- NDVI -> crop coefficient -------------------------------------------------

def kcb_from_ndvi_sims(ndvi: float,
                       ndvi_min: float = 0.15,
                       ndvi_max: float = 0.90,
                       kcb_full: float = 1.10) -> float:
    """SIMS / Allen & Pereira (2009) fraction-of-cover route (default, most
    defensible).

        fc  = (NDVI - NDVI_min) / (NDVI_max - NDVI_min),  clipped to [0, 1]
        Kcb = Kcb_full * fc

    ndvi_min ~ bare soil (0.15), ndvi_max ~ full cover (0.90), Kcb_full ~ 1.10
    (FAO-56 mid-season basal coefficient for a dense field crop, rounded).
    These three are the modelling assumption and are cited, not tuned to a
    desired answer.
    """
    fc = (ndvi - ndvi_min) / (ndvi_max - ndvi_min)
    fc = max(0.0, min(1.0, fc))
    return kcb_full * fc


def kc_from_ndvi_linear(ndvi: float, a: float = 1.25, b: float = 0.10) -> float:
    """Simple linear route, kept for a sensitivity cross-check only.

        Kc ~ a*NDVI + b   with a,b inside the cited NDVI-Kc range
        (a ~ 1.1-1.5, b ~ -0.1..0.1; Calera et al. 2017 and references therein).
    """
    return max(0.0, a * ndvi + b)


def kc_single(ndvi: float, ke: float = 0.10, **sims_kw) -> float:
    """Single (dual-sum) crop coefficient used for water demand:

        Kc = Kcb(NDVI)  +  Ke

    Ke is the soil-evaporation term. For pivot/drip in arid, largely-covered
    fields it is small; 0.10 is a mid value (FAO-56 ch.7). Pass ke=0 for a
    transpiration-only (Kcb) lower bound.
    """
    return kcb_from_ndvi_sims(ndvi, **sims_kw) + ke


# --- ETc and water volumes ----------------------------------------------------

@dataclass
class FieldWater:
    ndvi: float
    kc: float
    et0_mm_day: float          # reference ET (measured/reanalysis)
    etc_mm_day: float          # crop ET = water demand, mm/day
    etc_mm_week: float         # weekly demand depth
    area_ha: float
    weekly_demand_m3: float     # weekly demand volume for the field
    net_irrig_mm_week: float    # = ETc - effective rainfall (Pe)
    net_irrig_m3_week: float


def etc(ndvi: float, et0_mm_day: float, area_ha: float,
        pe_mm_week: float = 0.0, ke: float = 0.10, **sims_kw) -> FieldWater:
    """Crop water requirement for one field for one week.

        ETc  = Kc(NDVI) * ET0                 [mm/day]
        weekly depth   = ETc * 7              [mm/week]
        weekly volume  = depth/1000 * area_m2 [m3]   (1 mm over 1 ha = 10 m3)
        net irrigation = ETc_week - Pe        (Pe ~ 0 in arid Makkah)
    """
    kc = kc_single(ndvi, ke=ke, **sims_kw)
    etc_day = kc * et0_mm_day
    etc_week = etc_day * 7.0
    area_m2 = area_ha * 10_000.0
    weekly_m3 = etc_week / 1000.0 * area_m2
    net_mm = max(0.0, etc_week - pe_mm_week)
    net_m3 = net_mm / 1000.0 * area_m2
    return FieldWater(ndvi, kc, et0_mm_day, etc_day, etc_week, area_ha,
                      weekly_m3, net_mm, net_m3)


def waste(net_irrig_m3_week: float, applied_m3_week: float) -> float:
    """Avoidable waste = applied - requirement (never negative here means
    the field is already at/under demand). 'applied' is ESTIMATED (no field
    meter in the prototype) — always label it as such."""
    return applied_m3_week - net_irrig_m3_week
