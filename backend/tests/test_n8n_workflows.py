"""Static checks of the 11 importable n8n workflows against the real API routes."""
import json, re
from pathlib import Path
import pytest
from bp.api import app

WF_DIR = Path(__file__).resolve().parents[2] / "n8n" / "workflows"
FILES = sorted(WF_DIR.glob("*.json"))
ROUTES = [(m, re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", r.path) + "$"))
          for r in app.routes if hasattr(r, "methods") for m in r.methods]


def test_eleven_workflows():
    assert [f.name[:2] for f in FILES] == [f"{i:02d}" for i in range(1, 12)]


@pytest.mark.parametrize("f", FILES, ids=lambda f: f.name)
def test_workflow_is_consistent(f):
    wf = json.loads(f.read_text())
    names = [n["name"] for n in wf["nodes"]]
    assert len(names) == len(set(names))
    for src, outs in wf["connections"].items():
        assert src in names
        for branch in outs["main"]:
            for c in branch:
                assert c["node"] in names
    types = {n["type"] for n in wf["nodes"]}
    assert {"n8n-nodes-base.webhook", "n8n-nodes-base.respondToWebhook"} <= types
    text = f.read_text().lower()
    assert "password" not in text and "apikey" not in text and "bearer" not in text
    def strings(o):
        if isinstance(o, str):
            yield o
        elif isinstance(o, (dict, list)):
            for v in (o.values() if isinstance(o, dict) else o):
                yield from strings(v)
    for v in strings(wf["nodes"]):   # n8n ends an expression at the first '}}': a stray one is a runtime syntax error
        if v.startswith("="):
            assert v.count("{{") == v.count("}}"), v
    for n in wf["nodes"]:
        if n["type"] != "n8n-nodes-base.httpRequest":
            continue
        url = n["parameters"]["url"]
        assert url.startswith("={{ $env.BP_API_URL }}")
        path = re.sub(r"\{\{.*?\}\}", "X", url.replace("={{ $env.BP_API_URL }}", ""))
        assert any(m == n["parameters"]["method"] and rx.match(path) for m, rx in ROUTES), (n["name"], path)
        assert n["retryOnFail"] and n["onError"] == "continueErrorOutput"
        if n["name"] != "Report error":
            assert wf["connections"][n["name"]]["main"][1][0]["node"] == "Report error"
