"""Update the 11 workflows already in n8n from n8n/workflows/*.json (matched by name), then re-activate them.
Updating in place avoids the duplicates a re-import would create. Workflows not yet in n8n are created.
Needs an n8n API key (n8n editor -> Settings -> n8n API):   set N8N_API_KEY=...   then   python n8n/push_workflows.py"""
import json, os, sys, urllib.request
from pathlib import Path

BASE = os.environ.get("N8N_URL", "http://localhost:5678") + "/api/v1/workflows"
KEY = os.environ.get("N8N_API_KEY") or sys.exit("set N8N_API_KEY first (n8n editor -> Settings -> n8n API)")


def req(method, url, body=None):
    r = urllib.request.Request(url, None if body is None else json.dumps(body).encode(), method=method,
                               headers={"X-N8N-API-KEY": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(r) as x:
        return json.loads(x.read() or b"null")


ids = {w["name"]: w["id"] for w in req("GET", BASE + "?limit=250")["data"]}
for f in sorted((Path(__file__).parent / "workflows").glob("*.json")):
    wf = json.loads(f.read_text())
    body = {k: wf[k] for k in ("name", "nodes", "connections", "settings")}
    if wf["name"] in ids:
        wid = ids[wf["name"]]
        req("POST", f"{BASE}/{wid}/deactivate")
        req("PUT", f"{BASE}/{wid}", body)
    else:
        wid = req("POST", BASE, body)["id"]
    print(wf["name"], "->", "active" if req("POST", f"{BASE}/{wid}/activate").get("active") else "NOT active")
