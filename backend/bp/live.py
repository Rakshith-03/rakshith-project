"""Live simulation sessions. The model advances in steps requested by the client; control changes are queued and take
effect at the NEXT step boundary (recorded with the simulation time at which they applied). Nothing changes mid-step."""
import uuid
import numpy as np
from . import generators as gen
from .model import Stepper
from .constraints import moderate, monitor
from .experiments import cell_model, limits_for, characterize, _store_run, sample_step
from .db import connect, dumps, now

SESSIONS = {}


class LiveSession:
    def __init__(self, profile, cfg):
        self.id = "LIVE_" + uuid.uuid4().hex[:8]
        self.profile, self.cfg = profile, cfg
        self.m = cell_model(profile); self.L = limits_for(profile)
        self.reset()

    def reset(self):
        p, c = self.profile, self.cfg
        self.s = Stepper(self.m, c.get("initial_soc", p["initial_soc"]), c.get("h0", -1.0),
                         c.get("T_init", p["T_init"]), c.get("T_amb", p["T_amb"]))
        self.t = 0.0; self.state = "RUNNING"; self.pending = []; self.changes = []; self.mod_log = []
        self.buf = {k: [] for k in ("t", "I_req", "I", "V", "z", "T", "h")}

    def update(self, changes):
        self.pending.append(changes)
        return {"queued": changes, "applies_at_s": self.t, "note": "applied at the next step boundary"}

    def _requested(self, t0, n, dt):
        c = self.cfg
        t = t0 + np.arange(n) * dt
        tt, I = gen.build({**c.get("load", {}), "duration_s": t[-1] + dt, "dt_s": dt})
        k = np.searchsorted(tt, t - 1e-9)
        base = I[k] + (c.get("discharge_A", 0.0) - c.get("charge_A", 0.0))
        lp = c.get("load", {}).get("pulse")
        keep = base if not lp else base - gen.build({"duration_s": t[-1] + dt, "dt_s": dt,
                                                     "pulse": {**lp, "base_A": 0.0, "pulse_A": lp["pulse_A"] - lp["base_A"]}})[1][k]
        return t, base / self.profile["n_parallel"], keep / self.profile["n_parallel"]

    def step(self, seconds=10.0):
        if self.state != "RUNNING":
            return {"state": self.state, "t": self.t}
        for ch in self.pending:
            for key, val in ch.items():
                if isinstance(val, dict) and isinstance(self.cfg.get(key), dict):
                    self.cfg[key] = {**self.cfg[key], **val}
                else:
                    self.cfg[key] = val
            self.changes.append({"t_s": self.t, "change": ch})
        self.pending = []
        dt = sample_step(self.cfg); n = max(1, int(round(seconds / dt)))
        t, I_req, keep = self._requested(self.t, n, dt)
        I = I_req
        if self.cfg.get("mode") == "auto":
            hor = max(n, int(self.cfg.get("horizon_s", 30.0) / dt))
            th, Ih, kh = self._requested(self.t, hor, dt)
            r = moderate(self.m, self.s.state(), th, Ih, self.L, I_keep=kh)
            if r["action"] != "none":
                I = r["I_perm"][:n]
                self.mod_log.append({"t_s": self.t, "requested_A": r["requested_peak_A"],
                                     "permitted_A": r["permitted_peak_A"], "reason": r["reason"]})
        new = {k: [] for k in self.buf}
        for k in range(n):
            V, _ = self.s.step(float(I[k]), dt)
            for key, val in (("t", t[k]), ("I_req", I_req[k]), ("I", I[k]), ("V", V), ("z", self.s.z), ("T", self.s.T), ("h", self.s.h)):
                new[key].append(float(val)); self.buf[key].append(float(val))
        self.t = float(t[-1] + dt)
        return {"state": self.state, "t": self.t, "samples": new, "moderation": self.mod_log[-1:] if self.mod_log else [],
                "label": "SIMULATED (" + self.m["id"] + ")"}

    def stop(self, save=True):
        self.state = "STOPPED"
        if not save or not self.buf["t"]:
            return {"state": self.state}
        a = {k: np.array(v) for k, v in self.buf.items()}
        c = connect(); eid = "EXP_" + now().replace("-", "").replace(":", "").replace("T", "_") + "_" + self.id[-6:]
        label = "SIMULATED live session (" + self.m["id"] + ")"
        c.execute("INSERT INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (eid, None, self.profile["id"], self.profile.get("version", 1), self.profile["chemistry"], "live",
                   self.cfg.get("mode", "manual"), "COMPLETED", label, now(), now(), None))
        c.execute("INSERT INTO experiment_configurations VALUES (?,?)",
                  (eid, dumps({"cfg": self.cfg, "profile": self.profile, "changes": self.changes})))
        _store_run(c, eid, "main", a["t"], a["I_req"], a, label)
        f = characterize(a["t"], a["V"], a["I"], a["T"], a["z"], self.m["Q"], self.cfg.get("load", {}).get("ripple"))
        c.execute("INSERT INTO extracted_features VALUES (?,?,?,?)", (eid, "main", dumps(f), now()))
        rows_c, overall = monitor(a["t"], a["V"], a["I"], a["T"], a["z"], self.L)
        for r in rows_c:
            if r["severity"] not in ("NORMAL", "NOT MONITORED"):
                c.execute("INSERT INTO constraint_events (experiment_id,run,constraint_name,severity,payload,created_at) "
                          "VALUES (?,?,?,?,?,?)", (eid, "main", r["constraint"], r["severity"], dumps(r), now()))
        for e in self.mod_log:
            c.execute("INSERT INTO moderation_events (experiment_id,t,requested_A,permitted_A,reason,payload,created_at) "
                      "VALUES (?,?,?,?,?,?,?)", (eid, e["t_s"], e["requested_A"], e["permitted_A"], e["reason"], dumps(e), now()))
        c.commit()
        return {"state": self.state, "experiment_id": eid, "overall_severity": overall, "features": f,
                "changes_applied": self.changes}
