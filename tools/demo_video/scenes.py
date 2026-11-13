"""Scenes for the project demo video: what the narrator says and what the browser does meanwhile.
kind "page": a dashboard page (show(id)) + JS actions; kind "card": a title card (tools/demo_video/card.html)."""

SCENES = [
    {"kind": "card", "title": "Multi-chemistry Battery Lab", "sub": "Characterization and software BMS platform",
     "lines": ["MATLAB / Simulink reference model", "Python FastAPI backend and dashboard", "n8n orchestration"],
     "say": "This is the multi-chemistry battery characterization and software B M S platform. It is a virtual development "
            "platform, not a certified battery controller, and every simulated result is labelled as simulated."},
    {"kind": "card", "title": "Data and calibration", "sub": "Measured data first",
     "lines": ["CALCE INR18650-20R: measured, used for calibration and testing",
               "Panasonic NCR18650B: 92 measured cells",
               "Ni-Cd: the only file is simulated, so Ni-Cd stays PROVISIONAL"],
     "say": "The model is built on measured data. The CALCE cell tests, on the I N R eighteen six fifty, twenty R cell, are used for calibration and for a "
            "one-time test on unseen drive cycles. The only nickel cadmium file is simulated, so nickel cadmium is provisional, not validated."},
    {"kind": "page", "page": "overview", "actions": [],
     "say": "The dashboard runs on the Fast A P I backend. The overview shows the approved model, version six, and its status."},
    {"kind": "page", "page": "config", "actions": [],
     "say": "Battery configuration holds versioned cell and pack profiles with their voltage, current and temperature limits."},
    {"kind": "page", "page": "datasets", "actions": [],
     "say": "Every dataset is listed with its source and type. Original files are never changed; quality checks run on parsed copies."},
    {"kind": "page", "page": "validation", "scroll": False,
     "actions": ["overlay()", "wait:800", "$('va-metrics').scrollIntoView({behavior:'smooth', block:'start'})"],
     "say": "Calibration and validation. Here the simulated voltage is overlaid on a measured drive cycle the model never saw "
            "during calibration. On these unseen cycles the error is about twelve to fifteen millivolts. It grows near empty, below ten percent charge."},
    {"kind": "page", "page": "control",
     "actions": ["$('pu-on').checked = true", "$('ri-on').checked = true", "$('pu-n').value = 8", "wait:800", "runExp()"],
     "say": "Experiment control combines discharge, charge, pulse and ripple generators. Starting an experiment runs the "
            "approved model and stores the result with its label and provenance."},
    {"kind": "page", "page": "live", "actions": ["live('start')", "wait:1500", "live('run')", "wait:2500", "live('run')"],
     "say": "In live simulation, changes are applied at the next step boundary while the run continues. The charts show "
            "current, voltage, state of charge and temperature."},
    {"kind": "page", "page": "moderation", "actions": ["mod()"],
     "say": "The moderation centre predicts whether a requested pulse would break a limit, and permits a reduced current "
            "instead. Moderation runs in the backend, at the simulation step, never in n eight n."},
    {"kind": "page", "page": "bms", "actions": ["ekf()", "wait:2500", "balance()"],
     "say": "B M S monitoring. An extended Kalman filter estimates state of charge on measured CALCE cycles, recovering from a "
            "thirty percent start error. Below, pack balancing compares passive and active methods on a simulated pack."},
    {"kind": "page", "page": "charging", "actions": ["charge()"],
     "say": "Adaptive charging checks feasibility first. Twenty to eighty percent in thirty minutes is rejected, because it "
            "would need more than the validated current limit. It does not pretend; it tells you the fastest safe time."},
    {"kind": "page", "page": "ai", "actions": ["train('soc_regressor')"],
     "say": "The A I centre trains models with a split by file. This state of charge regressor is rejected by the acceptance "
            "rule, because the Kalman filter is more accurate. Models are only approved when they earn it."},
    {"kind": "page", "page": "learning", "actions": [],
     "say": "The learning centre records every recalibration. Versions three, four and five were rejected; version six was "
            "approved on validation data and confirmed in Simulink to within six micro volts."},
    {"kind": "page", "page": "reports", "actions": ["techrep()"],
     "say": "Reports are generated as H T M L and C S V, including a full technical report."},
    {"kind": "n8n", "title": "n8n orchestration", "sub": "11 workflows, triggered live via webhooks",
     "say": "Finally, n eight n. Eleven workflows orchestrate the backend over H T T P, with retries, idempotency keys and an "
            "error branch. Here each one is triggered live through its webhook."},
    {"kind": "card", "title": "Status", "sub": "Done, with honest limits",
     "lines": ["Li-ion NMC model: VALIDATED on unseen drive cycles",
               "Python engine and Simulink: equivalent to MATLAB",
               "53 backend tests and 15 live n8n checks: PASS",
               "Ni-Cd and thermal: PROVISIONAL until real measurements exist"],
     "say": "To sum up: the lithium ion model is validated, the Python and Simulink models match MATLAB, all tests pass, and "
            "n eight n runs every workflow. Nickel cadmium and thermal stay provisional until real measurements exist. Thanks for watching."},
]
