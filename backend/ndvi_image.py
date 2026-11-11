"""
ndvi_image.py — recover an approximate NDVI raster from a pre-rendered
Sentinel-2 NDVI composite (the YlGn colour ramp exported from EO Browser /
Sentinel Hub), and detect idle / bare land.

HONESTY: this is a PROXY. In the production pipeline NDVI is computed
numerically from the raw Sentinel-2 bands:  NDVI = (B8 - B4) / (B8 + B4).
Here we do not yet have raw-band (GEE / Sentinel Hub) access, so for the
proof-of-concept we invert the colour ramp of the NDVI image the user
exported. Recovered NDVI is good to ~±0.05-0.1, enough to demonstrate the
NDVI -> Kc -> ETc chain end to end. We never present it as raw-band NDVI.

The YlGn ramp (ColorBrewer, the standard NDVI palette) maps NDVI 0->1 to
cream -> dark green. We invert by nearest colour on the ramp.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from PIL import Image, ImageFilter

# ColorBrewer YlGn control points, assumed to span NDVI 0.0 -> 1.0 linearly
# (EO Browser / Sentinel Hub default NDVI visualisation).
_YLGN = [
    (0.000, (255, 255, 229)),
    (0.125, (247, 252, 185)),
    (0.250, (217, 240, 163)),
    (0.375, (173, 221, 142)),
    (0.500, (120, 198, 121)),
    (0.625, (65, 171, 93)),
    (0.750, (35, 132, 67)),
    (0.875, (0, 104, 55)),
    (1.000, (0, 69, 41)),
]


def _ramp_lut(n: int = 256):
    """Dense NDVI->RGB lookup by linear interpolation of the control points."""
    xs = np.array([p[0] for p in _YLGN])
    cols = np.array([p[1] for p in _YLGN], float)
    ndvi = np.linspace(0, 1, n)
    rgb = np.empty((n, 3))
    for c in range(3):
        rgb[:, c] = np.interp(ndvi, xs, cols[:, c])
    return ndvi, rgb


@dataclass
class NDVIStats:
    n_valid: int
    ndvi_mean_all: float
    active_crop_mean_ndvi: float   # mean NDVI where NDVI >= active_thr
    active_fraction: float         # share of valid pixels that are active crop
    bare_fraction: float           # share with NDVI < bare_thr
    idle_in_field_fraction: float  # bare pixels INSIDE the cultivated footprint
    hist: dict                     # coarse NDVI histogram


def recover_ndvi(path: str, max_colour_dist: float = 55.0) -> np.ndarray:
    """Return a float NDVI array (NaN where the pixel is off-ramp, e.g. map
    labels / roads / water)."""
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(float)
    H, W, _ = a.shape
    flat = a.reshape(-1, 3)

    ndvi_lut, rgb_lut = _ramp_lut(256)
    # nearest ramp colour for every pixel (chunked to bound memory)
    out = np.full(flat.shape[0], np.nan)
    step = 200_000
    for i in range(0, flat.shape[0], step):
        chunk = flat[i:i + step][:, None, :]            # (k,1,3)
        d = np.sqrt(((chunk - rgb_lut[None, :, :]) ** 2).sum(2))  # (k,256)
        j = d.argmin(1)
        best = d[np.arange(d.shape[0]), j]
        val = ndvi_lut[j]
        # mask blue-ish text / off-ramp pixels
        px = flat[i:i + step]
        blue_text = (px[:, 2] > px[:, 0] + 15) & (px[:, 2] > px[:, 1] + 10)
        val[(best > max_colour_dist) | blue_text] = np.nan
        out[i:i + step] = val
    return out.reshape(H, W)


def _closing(mask: np.ndarray, size: int = 9) -> np.ndarray:
    """Binary morphological closing (dilate then erode) to turn scattered
    active-crop pixels into a solid cultivated footprint that encloses the
    bare centres / fallow halves of the pivots."""
    im = Image.fromarray((mask * 255).astype("uint8"))
    im = im.filter(ImageFilter.MaxFilter(size)).filter(ImageFilter.MinFilter(size))
    return np.asarray(im) > 127


def analyse(path: str, active_thr: float = 0.45, bare_thr: float = 0.25) -> NDVIStats:
    ndvi = recover_ndvi(path)
    valid = ~np.isnan(ndvi)
    v = ndvi[valid]
    active = valid & (ndvi >= active_thr)
    bare = valid & (ndvi < bare_thr)

    footprint = _closing(active, 11)          # cultivated extent
    idle = footprint & bare & valid           # bare land inside cultivation
    idle_frac = idle.sum() / max(1, footprint.sum())

    bins = np.arange(0, 1.01, 0.1)
    hcount, _ = np.histogram(v, bins=bins)
    hist = {f"{bins[i]:.1f}-{bins[i+1]:.1f}": int(hcount[i]) for i in range(len(hcount))}

    return NDVIStats(
        n_valid=int(valid.sum()),
        ndvi_mean_all=float(v.mean()),
        active_crop_mean_ndvi=float(ndvi[active].mean()) if active.any() else float("nan"),
        active_fraction=float(active.sum() / valid.sum()),
        bare_fraction=float(bare.sum() / valid.sum()),
        idle_in_field_fraction=float(idle_frac),
        hist=hist,
    )


if __name__ == "__main__":
    import sys
    s = analyse(sys.argv[1] if len(sys.argv) > 1 else "../../photo_2_2026-11-11_21-19-04.jpg")
    print(s)
