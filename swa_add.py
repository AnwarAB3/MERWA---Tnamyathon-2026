# -*- coding: utf-8 -*-
"""Compute only the new fields and merge into existing fields.json."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
import swa_fields as sf

OUT = sf.OUT
data = json.loads((OUT / "fields.json").read_text(encoding="utf-8"))
by_id = {r["id"]: r for r in data}

NEW = [f for f in sf.FIELDS if f["id"] in ("f6", "f7")]
for f in NEW:
    print("computing", f["name"], "...", flush=True)
    r = sf.compute(f)
    print("   ndvi", r.get("ndvi"), "et0", r.get("et0"), "soil", r.get("soil_ar"),
          "week_m3", r.get("week_m3"), flush=True)
    by_id[r["id"]] = r

# keep original order f1..f7
order = ["f1", "f2", "f3", "f4", "f5", "f6", "f7"]
out = [by_id[i] for i in order if i in by_id]
(OUT / "fields.json").write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
print("saved", OUT / "fields.json")
