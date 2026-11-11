"""
sentinel2.py — REAL Sentinel-2 NDVI for a coordinate, automatically.

Source: Microsoft Planetary Computer STAC (free, keyless, anonymous signing).
Collection: sentinel-2-l2a (surface reflectance). We read only the small AOI
window of bands B04 (red) and B08 (NIR) plus SCL (scene classification for
cloud masking), then compute the true index:

        NDVI = (B08 − B04) / (B08 + B04)

L2A reflectance for processing baseline ≥ 04.00 carries a −1000 DN offset
(BOA_ADD_OFFSET); we apply it before the ratio (it does not cancel out).

This removes the proxy: coordinate mode now computes NDVI from raw bands, the
same way the production pipeline does. If the network/STAC is unavailable the
caller falls back to the VARI estimate.
"""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
import numpy as np
from PIL import Image, ImageFilter

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
_DROP_SCL = (0, 1, 3, 8, 9, 10, 11)   # nodata/saturated/shadow/cloud/cirrus/snow


@dataclass
class S2Result:
    scene_date: str
    cloud_cover: float
    active_mean_ndvi: float
    active_fraction: float
    idle_fraction: float
    valid_fraction: float
    ndvi_mean: float
    classified_png: Image.Image
    ndvi_png: Image.Image


def _closing(mask, size=9):
    im = Image.fromarray((mask * 255).astype("uint8"))
    im = im.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    return np.asarray(im) > 127


def _read_window(href, bbox_ll, out_shape=None, nearest=False):
    import rasterio
    from rasterio.windows import from_bounds
    from rasterio.warp import transform_bounds
    from rasterio.enums import Resampling
    with rasterio.open(href) as ds:
        b = transform_bounds("EPSG:4326", ds.crs, *bbox_ll)
        win = from_bounds(*b, transform=ds.transform)
        h = out_shape[0] if out_shape else max(1, int(round(win.height)))
        w = out_shape[1] if out_shape else max(1, int(round(win.width)))
        data = ds.read(1, window=win, out_shape=(h, w),
                       resampling=Resampling.nearest if nearest else Resampling.bilinear,
                       boundless=True, fill_value=0)
    return data


def _colorize_ndvi(ndvi, valid):
    """YlGn-style render of the real NDVI (for display)."""
    stops = [(0.0, (255, 255, 229)), (0.2, (217, 240, 163)), (0.4, (120, 198, 121)),
             (0.6, (49, 163, 84)), (0.8, (0, 104, 55)), (1.0, (0, 69, 41))]
    xs = np.array([s[0] for s in stops]); cols = np.array([s[1] for s in stops], float)
    v = np.clip(ndvi, 0, 1)
    rgb = np.stack([np.interp(v, xs, cols[:, c]) for c in range(3)], -1)
    rgb[~valid] = (120, 120, 130)
    return Image.fromarray(rgb.astype("uint8"))


def _classify(ndvi, valid):
    H, W = ndvi.shape
    out = np.full((H, W, 3), 200, np.uint8)
    out[valid & (ndvi < 0.25)] = (214, 199, 145)
    out[valid & (ndvi >= 0.25) & (ndvi < 0.45)] = (242, 221, 110)
    out[valid & (ndvi >= 0.45)] = (49, 140, 70)
    return Image.fromarray(out)


def fetch_ndvi(lat: float, lon: float, half_deg: float = 0.012,
               months_back: int = 4, max_cloud: int = 35) -> S2Result | None:
    """Return real-NDVI stats for the AOI around (lat, lon), or None if no
    usable scene / dependencies / network."""
    try:
        import planetary_computer
        from pystac_client import Client
    except Exception:
        return None

    bbox = [lon - half_deg, lat - half_deg, lon + half_deg, lat + half_deg]
    try:
        cat = Client.open(STAC, modifier=planetary_computer.sign_inplace)
        end = dt.date.today()
        start = end - dt.timedelta(days=months_back * 31)
        search = cat.search(collections=["sentinel-2-l2a"], bbox=bbox,
                            datetime=f"{start}/{end}",
                            query={"eo:cloud_cover": {"lt": max_cloud}})
        items = list(search.items())
        if not items:
            search = cat.search(collections=["sentinel-2-l2a"], bbox=bbox,
                                datetime=f"{start}/{end}")
            items = list(search.items())
        if not items:
            return None
        items.sort(key=lambda it: it.properties.get("eo:cloud_cover", 100))
        item = items[0]
    except Exception:
        return None

    try:
        red = _read_window(item.assets["B04"].href, bbox).astype("float32")
        nir = _read_window(item.assets["B08"].href, bbox).astype("float32")
        scl = _read_window(item.assets["SCL"].href, bbox,
                           out_shape=red.shape, nearest=True)
    except Exception:
        return None

    # L2A offset (baseline >= 04.00): reflectance = (DN - 1000) * 1e-4
    baseline = str(item.properties.get("s2:processing_baseline", "04.00"))
    try:
        offset = -1000.0 if float(baseline) >= 4.0 else 0.0
    except ValueError:
        offset = -1000.0
    nodata = (red <= 0)
    red = np.maximum(red + offset, 1.0)
    nir = np.maximum(nir + offset, 1.0)
    ndvi = (nir - red) / (nir + red)

    cloud = np.isin(scl, _DROP_SCL)
    water = (scl == 6)
    valid = (~cloud) & (~nodata)
    veg = valid & (~water)

    active = veg & (ndvi >= 0.45)
    bare = veg & (ndvi < 0.25)
    footprint = _closing(active, 9)
    idle = (footprint & bare).sum() / max(1, footprint.sum())

    vv = ndvi[veg]
    return S2Result(
        scene_date=item.datetime.date().isoformat(),
        cloud_cover=float(item.properties.get("eo:cloud_cover", float("nan"))),
        active_mean_ndvi=round(float(ndvi[active].mean()), 3) if active.any() else float("nan"),
        active_fraction=round(float(active.sum() / max(1, veg.sum())), 3),
        idle_fraction=round(float(idle), 3),
        valid_fraction=round(float(valid.mean()), 3),
        ndvi_mean=round(float(vv.mean()), 3) if vv.size else float("nan"),
        classified_png=_classify(ndvi, valid),
        ndvi_png=_colorize_ndvi(ndvi, valid),
    )


@dataclass
class TSPoint:
    date: str
    ndvi_mean: float
    ndvi_active: float
    cloud: float


def _scene_stats(item, bbox, res=72):
    """Fast low-res mean NDVI for one scene (for the time-series)."""
    try:
        red = _read_window(item.assets["B04"].href, bbox, out_shape=(res, res)).astype("float32")
        nir = _read_window(item.assets["B08"].href, bbox, out_shape=(res, res)).astype("float32")
        scl = _read_window(item.assets["SCL"].href, bbox, out_shape=(res, res), nearest=True)
    except Exception:
        return None
    baseline = str(item.properties.get("s2:processing_baseline", "04.00"))
    try:
        offset = -1000.0 if float(baseline) >= 4.0 else 0.0
    except ValueError:
        offset = -1000.0
    nodata = (red <= 0)
    red = np.maximum(red + offset, 1.0)
    nir = np.maximum(nir + offset, 1.0)
    ndvi = (nir - red) / (nir + red)
    cloud = np.isin(scl, _DROP_SCL)
    veg = (~cloud) & (~nodata) & (scl != 6)
    if veg.sum() < 20:
        return None
    active = veg & (ndvi >= 0.45)
    return (float(ndvi[veg].mean()),
            float(ndvi[active].mean()) if active.any() else float(ndvi[veg].mean()))


def fetch_timeseries(lat: float, lon: float, half_deg: float = 0.012,
                     months_back: int = 12, max_cloud: int = 20,
                     max_scenes: int = 16):
    """Real NDVI phenology: least-cloudy scene per date over the window.
    Returns a date-sorted list[TSPoint] (may be empty / None if unavailable)."""
    try:
        import planetary_computer
        from pystac_client import Client
    except Exception:
        return None
    bbox = [lon - half_deg, lat - half_deg, lon + half_deg, lat + half_deg]
    try:
        cat = Client.open(STAC, modifier=planetary_computer.sign_inplace)
        end = dt.date.today()
        start = end - dt.timedelta(days=months_back * 31)
        items = list(cat.search(collections=["sentinel-2-l2a"], bbox=bbox,
                                datetime=f"{start}/{end}",
                                query={"eo:cloud_cover": {"lt": max_cloud}}).items())
        if len(items) < 4:
            items = list(cat.search(collections=["sentinel-2-l2a"], bbox=bbox,
                                    datetime=f"{start}/{end}",
                                    query={"eo:cloud_cover": {"lt": 60}}).items())
    except Exception:
        return None
    if not items:
        return None
    # least-cloudy scene per date
    best = {}
    for it in items:
        d = it.datetime.date()
        c = it.properties.get("eo:cloud_cover", 100)
        if d not in best or c < best[d].properties.get("eo:cloud_cover", 100):
            best[d] = it
    dates = sorted(best)
    if len(dates) > max_scenes:                 # sample evenly
        idx = np.linspace(0, len(dates) - 1, max_scenes).round().astype(int)
        dates = [dates[i] for i in sorted(set(idx))]

    from concurrent.futures import ThreadPoolExecutor

    def one(d):
        it = best[d]
        s = _scene_stats(it, bbox)
        if s is None:
            return None
        return TSPoint(d.isoformat(), round(s[0], 3), round(s[1], 3),
                       float(it.properties.get("eo:cloud_cover", float("nan"))))

    with ThreadPoolExecutor(max_workers=6) as ex:       # network I/O bound
        results = list(ex.map(one, dates))
    return [p for p in results if p is not None]


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "ts":
        ts = fetch_timeseries(21.2120, 39.6643)
        for p in ts:
            print(p.date, "ndvi_mean", p.ndvi_mean, "active", p.ndvi_active, "cloud", round(p.cloud))
        sys.exit()
    r = fetch_ndvi(21.2120, 39.6643)
    if r is None:
        print("no scene / unavailable")
    else:
        print(f"scene {r.scene_date}  cloud {r.cloud_cover:.0f}%  valid {r.valid_fraction*100:.0f}%")
        print(f"active NDVI {r.active_mean_ndvi}  active frac {r.active_fraction}  "
              f"idle {r.idle_fraction}  ndvi_mean {r.ndvi_mean}")
