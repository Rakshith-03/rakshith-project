"""SQLite store with full provenance. JSON columns hold structured payloads; every row records when it was written."""
import json, sqlite3, time
from .data import ROOT

DB_PATH = ROOT / "DATA" / "DATABASE" / "platform.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chemistry_profiles (id TEXT PRIMARY KEY, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS battery_profiles (id TEXT PRIMARY KEY, name TEXT, chemistry TEXT, status TEXT,
    current_version INTEGER, created_at TEXT);
CREATE TABLE IF NOT EXISTS battery_parameter_versions (profile_id TEXT, version INTEGER, payload TEXT, created_at TEXT,
    PRIMARY KEY (profile_id, version));
CREATE TABLE IF NOT EXISTS battery_configurations (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT,
    profile_id TEXT, profile_version INTEGER, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS datasets (id TEXT PRIMARY KEY, name TEXT, chemistry TEXT, format TEXT, source_type TEXT,
    path TEXT, sha256 TEXT, approval TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS dataset_sources (id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id TEXT, url TEXT,
    licence_note TEXT, retrieved_at TEXT);
CREATE TABLE IF NOT EXISTS dataset_cleaning_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id TEXT, step TEXT,
    detail TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS dataset_quality_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, dataset_id TEXT, payload TEXT,
    created_at TEXT);
CREATE TABLE IF NOT EXISTS model_calibrations (id INTEGER PRIMARY KEY AUTOINCREMENT, model_id TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS model_validation_results (id INTEGER PRIMARY KEY AUTOINCREMENT, model_id TEXT, status TEXT,
    payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS campaigns (id TEXT PRIMARY KEY, name TEXT, status TEXT, payload TEXT, created_at TEXT,
    idempotency_key TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, campaign_id TEXT, profile_id TEXT, profile_version INTEGER,
    chemistry TEXT, type TEXT, mode TEXT, status TEXT, label TEXT, created_at TEXT, finished_at TEXT,
    idempotency_key TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS experiment_configurations (experiment_id TEXT PRIMARY KEY, payload TEXT);
CREATE TABLE IF NOT EXISTS simulation_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT, engine TEXT,
    model_id TEXT, label TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS time_series_data (experiment_id TEXT, run TEXT, t_s REAL, I_req REAL, I REAL, V REAL, z REAL,
    temp_C REAL, h REAL, source_type TEXT);
CREATE INDEX IF NOT EXISTS ts_exp ON time_series_data (experiment_id, run);
CREATE TABLE IF NOT EXISTS extracted_features (experiment_id TEXT, run TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS bms_estimates (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS diagnostic_events (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT, severity TEXT,
    constraint_name TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS constraint_events (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT, run TEXT,
    constraint_name TEXT, severity TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS moderation_events (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT, t REAL,
    requested_A REAL, permitted_A REAL, reason TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS cell_measurements (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT, cell INTEGER,
    payload TEXT, source_type TEXT);
CREATE TABLE IF NOT EXISTS balancing_results (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS ml_datasets (id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS ml_models (id TEXT PRIMARY KEY, task TEXT, version INTEGER, approval TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS ml_evaluation_metrics (id INTEGER PRIMARY KEY AUTOINCREMENT, model_id TEXT, split TEXT,
    metric TEXT, value REAL);
CREATE TABLE IF NOT EXISTS charging_optimizations (id INTEGER PRIMARY KEY AUTOINCREMENT, experiment_id TEXT, payload TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, experiment_id TEXT, kind TEXT, path TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS n8n_workflow_executions (id INTEGER PRIMARY KEY AUTOINCREMENT, workflow TEXT, execution_id TEXT,
    idempotency_key TEXT, status TEXT, payload TEXT, created_at TEXT);
"""


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def connect(path=None):
    p = path or DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def dumps(x):
    return json.dumps(x, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


def rows(c, sql, *args):
    out = []
    for r in c.execute(sql, args).fetchall():
        d = dict(r)
        if "payload" in d and d["payload"]:
            d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out
