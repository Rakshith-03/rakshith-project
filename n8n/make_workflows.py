"""Generate the 11 importable n8n workflows. n8n only orchestrates backend HTTP endpoints: no battery physics, no control
loop. Every workflow: Webhook trigger -> prepare (idempotency key, IDs) -> backend call(s) with retries -> record the
execution in the backend -> respond; any backend failure takes the error output -> POST /api/errors -> respond 500.
Base URL comes from the environment variable BP_API_URL (no credentials are stored in the workflows).
Run: python n8n/make_workflows.py"""
import json, uuid
from pathlib import Path

OUT = Path(__file__).parent / "workflows"
API = "={{ $env.BP_API_URL }}"


CUR = {"slug": ""}


def node(name, type_, params, x, y, **extra):
    return {"parameters": params, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, CUR["slug"] + "/" + name)), "name": name, "type": type_, "typeVersion": extra.pop("v", 1),
            "position": [x, y], **extra}


def http(name, method, path, x, y, body=None, idem=False):
    p = {"method": method, "url": f"{API}{path}", "options": {"timeout": 600000}}
    if idem:
        p |= {"sendHeaders": True, "headerParameters": {"parameters": [
            {"name": "Idempotency-Key", "value": "={{ $('Prepare').item.json.idempotency_key }}"}]}}
    if body is not None:
        p |= {"sendBody": True, "specifyBody": "json", "jsonBody": body}
    return node(name, "n8n-nodes-base.httpRequest", p, x, y, v=4.2, retryOnFail=True, maxTries=3,
                waitBetweenTries=5000, onError="continueErrorOutput")


def workflow(num, slug, title, steps, prepare_js):
    nodes = [node("Webhook", "n8n-nodes-base.webhook", {"httpMethod": "POST", "path": slug, "responseMode": "responseNode",
                                                       "options": {}}, 0, 0, v=2, webhookId=str(uuid.uuid5(uuid.NAMESPACE_DNS, slug))),
             node("Prepare", "n8n-nodes-base.code", {"jsCode": prepare_js}, 220, 0, v=2)]
    conn = {"Webhook": {"main": [[{"node": "Prepare", "type": "main", "index": 0}]]}}
    prev = "Prepare"; x = 440
    for s in steps:
        nodes.append(s | {"position": [x, 0]})
        conn[prev] = conn.get(prev, {"main": [[]]})
        conn[prev]["main"][0].append({"node": s["name"], "type": "main", "index": 0})
        prev = s["name"]; x += 220
    record = http("Record execution", "POST", "/api/n8n/executions", x, 0,
                  body=f'={{{{ JSON.stringify({{workflow: "{num}_{slug}", execution_id: $execution.id, '
                       f'idempotency_key: $("Prepare").item.json.idempotency_key, status: "SUCCESS", result: $json}}) }}}}')
    # respond with the output of the last step that ran (an IF false branch skips the later steps)
    last_run = "[" + ", ".join(f"'{s['name']}'" for s in reversed(steps)) + "].map(n => $(n)).find(n => n.isExecuted).item.json"
    respond = node("Respond", "n8n-nodes-base.respondToWebhook", {"respondWith": "json",
                   "responseBody": "={{ JSON.stringify(" + last_run + ") }}", "options": {}}, x + 220, 0, v=1.1)
    err = http("Report error", "POST", "/api/errors", x, 220,
               body=f'={{{{ JSON.stringify({{source: "n8n {num}_{slug}", execution_id: $execution.id, '
                    f'experiment_id: $("Prepare").item.json.experiment_id || null, error: $json.error || $json}}) }}}}')
    err_resp = node("Respond error", "n8n-nodes-base.respondToWebhook", {"respondWith": "json", "responseBody":
                    '={{ JSON.stringify({status: "FAILED", detail: $json}) }}', "options": {"responseCode": 500}}, x + 220, 220, v=1.1)
    nodes += [record, respond, err, err_resp]
    conn.setdefault(prev, {"main": [[]]})["main"][0].append({"node": "Record execution", "type": "main", "index": 0})
    conn["Record execution"] = {"main": [[{"node": "Respond", "type": "main", "index": 0}], []]}
    conn["Report error"] = {"main": [[{"node": "Respond error", "type": "main", "index": 0}], []]}
    for n in nodes:   # IF nodes: the false output also ends in "Record execution" so the webhook always responds
        if n["type"] == "n8n-nodes-base.if":
            m = conn[n["name"]]["main"]
            while len(m) < 2:
                m.append([])
            m[1] = [{"node": "Record execution", "type": "main", "index": 0}]
    for n in nodes:   # every HTTP node routes its error output (index 1) to the error branch
        if n["type"] == "n8n-nodes-base.httpRequest" and n["name"] != "Report error":
            conn.setdefault(n["name"], {"main": [[]]})
            m = conn[n["name"]]["main"]
            while len(m) < 2:
                m.append([])
            m[1] = [{"node": "Report error", "type": "main", "index": 0}]
    for n in nodes:   # deterministic, workflow-specific node IDs
        n["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, slug + "/" + n["name"]))
    wf = {"name": f"{num} {title}", "nodes": nodes, "connections": conn, "active": False,
          "settings": {"executionOrder": "v1", "saveDataErrorExecution": "all"}, "meta": {"generatedBy": "make_workflows.py"},
          "pinData": {}}
    OUT.mkdir(exist_ok=True)
    (OUT / f"{num}_{slug.replace('-', '_')}.json").write_text(json.dumps(wf, indent=2))
    return wf


IDEM = ("const b = $json.body || {};\n"
        "const key = b.idempotency_key || $execution.id;\n"
        "return [{ json: { ...b, idempotency_key: key } }];")
NEED = lambda field: (f"const b = $json.body || {{}};\nif (!b.{field}) throw new Error('{field} is required');\n"
                      f"return [{{ json: {{ ...b, idempotency_key: b.idempotency_key || $execution.id }} }}];")

WF = [
    ("01", "campaign-initialization", "Campaign initialization",
     [http("Create campaign", "POST", "/api/campaigns", 0, 0, idem=True,
           body="={{ JSON.stringify({name: $json.name, experiments: $json.experiments || []}) }}")],
     IDEM + "\n// experiments[] = [{profile_id, config}] validated by the backend; the campaign ID is created there"),
    ("02", "experiment-execution", "Automated experiment execution",
     [http("Run experiment", "POST", "/api/experiments", 0, 0, idem=True,
           body="={{ JSON.stringify({profile_id: $json.profile_id || 'INR18650-20R', config: $json.config}) }}"),
      http("Characterize", "POST", "/api/experiments/{{ $json.id }}/characterize", 0, 0),
      http("Diagnostics", "POST", "/api/experiments/{{ $('Run experiment').item.json.id }}/diagnostics", 0, 0)],
     NEED("config")),
    ("03", "constraint-moderation-events", "Constraint moderation events",
     [http("Get experiment", "GET", "/api/experiments/{{ $json.experiment_id }}", 0, 0),
      http("Evaluate request", "POST", "/api/moderate", 0, 0,
           body="={{ JSON.stringify({profile_id: $json.config.profile.id, state: $('Prepare').item.json.state || {}, "
                "request: $('Prepare').item.json.request || {base_A: 1, pulse_A: 2} }) }}")],
     NEED("experiment_id") + "\n// the moderation decision is computed by the backend; n8n only records and forwards it"),
    ("04", "dataset-discovery", "Dataset discovery and import",
     [http("List sources", "GET", "/api/datasets/sources", 0, 0),
      node("Missing known datasets", "n8n-nodes-base.code", {"jsCode":
           "const missing = $json.known.filter(k => k.url && !k.present);\n"
           "return missing.length ? missing.map(k => ({json: k})) : [{json: {id: null, note: 'all known datasets present'}}];"}, 0, 0, v=2),
      node("Any missing?", "n8n-nodes-base.if", {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"},
           "conditions": [{"leftValue": "={{ $json.id }}", "rightValue": "", "operator": {"type": "string", "operation": "notEmpty",
           "singleValue": True}}], "combinator": "and"}, "options": {}}, 0, 0, v=2),
      http("Fetch allow-listed", "POST", "/api/datasets/{{ $json.id }}/fetch", 0, 0),
      http("Quality check", "POST", "/api/datasets/{{ $('Missing known datasets').item.json.id }}/clean", 0, 0)],
     IDEM + "\n// only allow-listed public sources (backend-enforced); new sources need an operator decision"),
    ("05", "data-cleaning", "Data cleaning and approval",
     [http("Quality check", "POST", "/api/datasets/{{ $json.dataset_id }}/clean", 0, 0)], NEED("dataset_id")),
    ("06", "characterization", "Automatic characterization",
     [http("Characterize", "POST", "/api/experiments/{{ $json.experiment_id }}/characterize", 0, 0),
      http("Get experiment", "GET", "/api/experiments/{{ $('Prepare').item.json.experiment_id }}", 0, 0)], NEED("experiment_id")),
    ("07", "bms-diagnostics", "Automatic BMS diagnostics",
     [http("Diagnostics", "POST", "/api/experiments/{{ $json.experiment_id }}/diagnostics", 0, 0)], NEED("experiment_id")),
    ("08", "ml-training", "Automatic ML training",
     [http("Check datasets", "GET", "/api/datasets", 0, 0),
      node("Approved data present?", "n8n-nodes-base.code", {"jsCode":
           "const ok = $input.all().some(i => String(i.json.approval).startsWith('APPROVED') && String(i.json.id).startsWith('CALCE_SP2'));\n"
           "if (!ok) throw new Error('no approved CALCE SP2 data');\nreturn [{json: {task: $('Prepare').item.json.task || 'soc_regressor'}}];"},
           0, 0, v=2),
      http("Train and evaluate", "POST", "/api/ml/train", 0, 0, body="={{ JSON.stringify({task: $json.task}) }}")],
     IDEM + "\n// split by file, acceptance rule and registry are enforced by the backend"),
    ("09", "adaptive-charging", "Adaptive charging optimization",
     [http("Optimize", "POST", "/api/charging/optimize", 0, 0,
           body="={{ JSON.stringify({profile_id: $json.profile_id || 'INR18650-20R', initial_soc: $json.initial_soc, "
                "target_soc: $json.target_soc, target_time_s: $json.target_time_s, health: $json.health || {} }) }}")],
     NEED("target_soc")),
    ("10", "report-generation", "Report generation",
     [http("Experiment report", "POST", "/api/experiments/{{ $json.experiment_id }}/report", 0, 0),
      http("Technical report", "POST", "/api/reports/technical", 0, 0)], NEED("experiment_id")),
    ("11", "error-recovery", "Error recovery",
     [http("Record error", "POST", "/api/errors", 0, 0,
           body="={{ JSON.stringify({source: $json.workflow || 'n8n', experiment_id: $json.experiment_id || null, error: $json.error}) }}"),
      node("Retry allowed?", "n8n-nodes-base.if", {"conditions": {"options": {"caseSensitive": True, "typeValidation": "loose"},
           "conditions": [{"leftValue": "={{ $json.retry_allowed }}", "rightValue": True, "operator": {"type": "boolean",
           "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, 0, 0, v=2),
      http("Get failed experiment", "GET", "/api/experiments/{{ $('Prepare').item.json.experiment_id }}", 0, 0),
      http("Re-run once", "POST", "/api/experiments", 0, 0, idem=True,
           body="={{ JSON.stringify({profile_id: $json.config.profile.id, config: $json.config.cfg}) }}")],
     IDEM + "\n// completed experiments are never re-run (backend returns retry_allowed=false); the retry reuses an idempotency key"),
]

if __name__ == "__main__":
    for w in WF:
        CUR["slug"] = w[1]
        workflow(*w)
    print("wrote", len(list(OUT.glob("*.json"))), "workflows to", OUT)
