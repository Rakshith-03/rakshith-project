"""Refresh docs/openapi.json from the backend's routes. Run after adding or changing an API route:  python tools/export_openapi.py"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from bp.api import app

spec = app.openapi()
(ROOT / "docs" / "openapi.json").write_text(json.dumps(spec, indent=1))
print("wrote docs/openapi.json:", sum(len(v) for v in spec["paths"].values()), "routes")
