# -*- coding: utf-8 -*-
"""
soil.py — automatic soil type from OpenLandMap (keyless).

Reads the OpenLandMap "USDA soil texture class" layer (250 m, 10 cm depth)
directly from its public cloud-optimized GeoTIFF with a single windowed
range-request (rasterio /vsicurl), and maps the USDA class to the three
irrigation buckets the platform uses: رملية / طميية / طينية.

Layer: OpenLandMap SOL_TEXTURE-CLASS_USDA-TT_M v0.2 (predicted250m).
Source: OpenLandMap / OpenGeoHub (openlandmap.org). No API key.
"""
from __future__ import annotations
from dataclasses import dataclass

# USDA texture class COG (b10 = 0–10 cm root zone)
COG = ("/vsicurl/http://s3.eu-central-1.wasabisys.com/openlandmap/"
       "predicted250m/sol_texture.class_usda.tt_m_250m_b10..10cm_1950..2017_v0.2.tif")

# 12 USDA classes -> Arabic name + irrigation bucket (sandy/loam/clay)
USDA = {
    1:  ("طينية",             "clay",            "clay"),
    2:  ("طينية غرينية",       "silty clay",      "clay"),
    3:  ("طينية رملية",        "sandy clay",      "clay"),
    4:  ("طميية طينية",        "clay loam",       "loam"),
    5:  ("طميية طينية غرينية",  "silty clay loam", "loam"),
    6:  ("طميية طينية رملية",   "sandy clay loam", "loam"),
    7:  ("طميية",             "loam",            "loam"),
    8:  ("طميية غرينية",       "silt loam",       "loam"),
    9:  ("طميية رملية",        "sandy loam",      "sandy"),
    10: ("غرينية",            "silt",            "loam"),
    11: ("رملية طميية",       "loamy sand",      "sandy"),
    12: ("رملية",             "sand",            "sandy"),
}


@dataclass
class Soil:
    cls: int
    name_ar: str      # full USDA texture name in Arabic
    name_en: str
    bucket: str       # sandy | loam | clay  (used by the engine / crops)
    source: str = "OpenLandMap (USDA texture class, 250 m)"


def detect_soil(lat: float, lon: float, timeout: int = 40) -> Soil | None:
    """Return the soil type at (lat, lon) from OpenLandMap, or None if the
    read fails / the point has no data."""
    try:
        import rasterio
        from rasterio.warp import transform
        with rasterio.open(COG) as ds:
            xs, ys = transform("EPSG:4326", ds.crs, [lon], [lat])
            val = int(list(ds.sample([(xs[0], ys[0])]))[0][0])
        if val not in USDA:
            return None
        ar, en, bucket = USDA[val]
        return Soil(val, ar, en, bucket)
    except Exception:
        return None


if __name__ == "__main__":
    for name, (la, lo) in {"field": (21.2120, 39.6643),
                            "Khurmah": (21.92, 42.05)}.items():
        s = detect_soil(la, lo)
        print(name, "->", s)
