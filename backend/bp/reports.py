"""Report generation: per-experiment HTML (with plots) + CSV, and a project technical report compiled from DATA/REPORTS."""
import base64, csv, html, io, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .data import ROOT
from .db import connect, now
from .experiments import get_experiment, timeseries

OUT = ROOT / "DATA" / "REPORTS" / "generated"


def _png(fig):
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=90, bbox_inches="tight"); plt.close(fig)
    return base64.b64encode(b.getvalue()).decode()


def _table(d):
    return "<table>" + "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(f'{v:.6g}' if isinstance(v, float) else str(v))}</td></tr>"
                               for k, v in d.items()) + "</table>"


def experiment_report(eid):
    c = connect(); e = get_experiment(eid, c); ts = timeseries(eid, "main", c)
    OUT.mkdir(parents=True, exist_ok=True)
    csv_path = OUT / f"{eid}.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f); keys = ["t", "I_req", "I", "V", "z", "T", "h", "dVdt", "dIdt", "dTdt"]
        w.writerow(keys + ["source_type"])
        for i in range(len(ts["t"])):
            w.writerow([ts[k][i] for k in keys] + [ts["label"]])
    fig, ax = plt.subplots(4, 1, figsize=(9, 9), sharex=True)
    t = np.array(ts["t"])
    ax[0].plot(t, ts["V"]); ax[0].set_ylabel("V (cell)")
    ax[1].plot(t, ts["I_req"], "--", label="requested"); ax[1].plot(t, ts["I"], label="applied"); ax[1].legend(); ax[1].set_ylabel("I (A, +dis)")
    ax[2].plot(t, np.array(ts["z"]) * 100); ax[2].set_ylabel("SOC %")
    ax[3].plot(t, ts["T"]); ax[3].set_ylabel("T degC (PROVISIONAL)"); ax[3].set_xlabel("s")
    for a in ax: a.grid(alpha=.3)
    img = _png(fig)
    feats = e["features"].get("main", {})
    body = f"""<h1>Experiment report {html.escape(eid)}</h1>
<p><b>Data type:</b> {html.escape(e['label'])}. Not a measurement. Generated {now()}.</p>
<h2>Configuration</h2><pre>{html.escape(json.dumps(e['config'], indent=1)[:6000])}</pre>
<h2>Response</h2><img src="data:image/png;base64,{img}">
<h2>Characterization (cell level)</h2>{_table(feats)}
<h2>Constraint events</h2>{''.join(f"<p>{html.escape(x['constraint_name'])}: {x['severity']}</p>" for x in e['constraint_events']) or '<p>None (all NORMAL)</p>'}
<h2>Moderation events</h2>{_table({f"t={m['t']:.0f}s": f"{m['requested_A']:.3f} A -> {m['permitted_A']:.3f} A: {m['reason']}" for m in e['moderation_events']}) if e['moderation_events'] else '<p>None</p>'}
<h2>Charging</h2><pre>{html.escape(json.dumps(e['charging'], indent=1)[:4000])}</pre>
<p><i>Thermal values come from a PROVISIONAL model (no temperature data was available for calibration). This is a virtual BMS
development platform, not a certified battery controller.</i></p>"""
    path = OUT / f"{eid}.html"
    path.write_text(_page(f"Report {eid}", body), encoding="utf-8")
    c.execute("INSERT OR REPLACE INTO reports VALUES (?,?,?,?,?)", (f"R_{eid}", eid, "experiment", str(path), now())); c.commit()
    return {"html": str(path), "csv": str(csv_path)}


def _page(title, body):
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>"
            "body{font:14px/1.5 system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;color:#222}"
            "table{border-collapse:collapse;margin:8px 0}th,td{border:1px solid #ccc;padding:3px 8px;text-align:left}"
            "th{background:#f3f3f3}pre{background:#f7f7f7;padding:8px;overflow:auto}img{max-width:100%}</style></head>"
            f"<body>{body}</body></html>")


def technical_report():
    """Lecturer-ready technical report compiled from the validation reports (markdown shown verbatim, in order)."""
    src = ROOT / "DATA" / "REPORTS"
    order = ["nicd_inspection.md", "liion_inspection.md", "matlab_drive_inventory.md",
             "liion_validation_run_20261112_013326.md", "liion_drivecycle_validation_20261112_015732.md",
             "simulink_equivalence_20261112_020624.md", "generators_thermal_constraints_tests.md",
             "platform_results.md"]
    parts = [f"<h1>Multi-chemistry battery characterization and software BMS: technical report</h1><p>Compiled {now()} "
             "from the project's dated reports. Each section states its data type (MEASURED / CALCULATED / ESTIMATED / "
             "SIMULATED / PROVISIONAL).</p>"]
    for n in order:
        p = src / n
        if p.exists():
            parts.append(f"<h2>{html.escape(n)}</h2><pre style='white-space:pre-wrap'>{html.escape(p.read_text(encoding='utf-8'))}</pre>")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "TECHNICAL_REPORT.html"
    path.write_text(_page("Technical report", "".join(parts)), encoding="utf-8")
    return {"html": str(path)}
