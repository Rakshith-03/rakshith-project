"""Live test: trigger all 11 n8n workflows via their webhooks (n8n on :5678, backend on :8000). See docs/N8N.md.
Run: python n8n/run_webhooks.py"""
import json, time, urllib.request, urllib.error

N8N, API = "http://localhost:5678/webhook/", "http://localhost:8000"


def call(url, body=None, timeout=900):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="GET" if body is None else "POST")
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null"), time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null"), time.time() - t


CFG = {"duration_s": 300, "initial_soc": 0.8, "discharging": {"enabled": True, "current_A": 2.0}}
results = []
RUN = "n8n-" + str(int(time.time()))


def wf(name, slug, body, expect=200, check=None):
    code, out, dt = call(N8N + slug, body)
    ok = code == expect and (check is None or check(out))
    results.append((name, code, round(dt, 1), ok, json.dumps(out)[:200]))
    print(("PASS" if ok else "FAIL"), name, code, f"{dt:.1f}s", json.dumps(out)[:200], flush=True)
    return out


n_before = len(call(API + "/api/n8n/executions")[1])
e_before = len(call(API + "/api/errors")[1]) if call(API + "/api/errors")[0] == 200 else None

c = wf("01 campaign (1 experiment, idem key)", "campaign-initialization",
       {"name": "n8n-run", "idempotency_key": RUN + "-cmp", "experiments": [{"config": CFG}]},
       check=lambda o: o["status"] == "COMPLETED" and len(o["experiments"]) == 1)
wf("01 campaign replay (same key)", "campaign-initialization",
   {"name": "n8n-run", "idempotency_key": RUN + "-cmp", "experiments": [{"config": CFG}]},
   check=lambda o: o.get("idempotent_replay") is True and o["id"] == c["id"])
e = wf("02 experiment execution", "experiment-execution", {"config": CFG, "idempotency_key": RUN + "-exp"},
       check=lambda o: "soc" in json.dumps(o).lower())
eid = call(API + "/api/experiments")[1][0]["id"]
wf("02 missing config -> rejected", "experiment-execution", {}, expect=500)
wf("03 constraint moderation", "constraint-moderation-events",
   {"experiment_id": eid, "state": {"soc": 0.015, "T": 25}, "request": {"base_A": 2, "pulse_A": 4, "pulse_s": 10, "interval_s": 60, "horizon_s": 600}},
   check=lambda o: "permit" in json.dumps(o).lower())
wf("04 dataset discovery", "dataset-discovery", {})
wf("05 data cleaning", "data-cleaning", {"dataset_id": "CALCE_SP2_US06"})
wf("06 characterization", "characterization", {"experiment_id": eid}, check=lambda o: o.get("id") == eid)
wf("07 BMS diagnostics", "bms-diagnostics", {"experiment_id": eid})
wf("07 unknown experiment -> error branch", "bms-diagnostics", {"experiment_id": "NO_SUCH_EXP"}, expect=500,
   check=lambda o: o.get("status") == "FAILED")
wf("08 ML training", "ml-training", {"task": "soc_regressor"}, check=lambda o: "approval" in o)
wf("09 adaptive charging 30 min", "adaptive-charging", {"initial_soc": 0.2, "target_soc": 0.8, "target_time_s": 1800},
   check=lambda o: "INFEASIBLE" in json.dumps(o).upper())
wf("09 adaptive charging 45 min", "adaptive-charging", {"initial_soc": 0.2, "target_soc": 0.8, "target_time_s": 2700},
   check=lambda o: "INFEASIBLE" not in json.dumps(o).upper())
wf("10 report generation", "report-generation", {"experiment_id": eid})
wf("11 error recovery (completed exp, no re-run)", "error-recovery",
   {"experiment_id": eid, "workflow": "test", "error": "simulated failure"}, check=lambda o: o.get("retry_allowed") is False)

n_after = len(call(API + "/api/n8n/executions")[1])
print("executions recorded by backend:", n_before, "->", n_after)
print("passed", sum(r[3] for r in results), "/", len(results))
