"""Build docs/BATTERY_LAB_EXPLAINED.pdf: the whole project explained simply, plus how to run it and change it.
Edit the text below and run:  python tools/make_guide.py"""
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
                                KeepTogether, ListFlowable, ListItem, Preformatted)

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "guide_img"
OUT = ROOT / "docs" / "BATTERY_LAB_EXPLAINED.pdf"

FONTS = Path("C:/Windows/Fonts")
pdfmetrics.registerFont(TTFont("Body", str(FONTS / "segoeui.ttf")))
pdfmetrics.registerFont(TTFont("Bold", str(FONTS / "segoeuib.ttf")))
pdfmetrics.registerFont(TTFont("Mono", str(FONTS / "consola.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Bold", italic="Body", boldItalic="Bold")

INK, BLUE, GREEN, AMBER, RED, GREY = (colors.HexColor(c) for c in ("#1e293b", "#2563eb", "#15803d", "#b45309", "#b91c1c", "#64748b"))
KID_BG, REAL_BG, CODE_BG, WARN_BG = (colors.HexColor(c) for c in ("#eff6ff", "#f8fafc", "#f1f5f9", "#fffbeb"))

S = {
    "title": ParagraphStyle("title", fontName="Bold", fontSize=30, leading=36, textColor=INK, alignment=TA_CENTER),
    "subtitle": ParagraphStyle("subtitle", fontName="Body", fontSize=14, leading=20, textColor=BLUE, alignment=TA_CENTER),
    "h1": ParagraphStyle("h1", fontName="Bold", fontSize=20, leading=26, textColor=INK, spaceBefore=4, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Bold", fontSize=13.5, leading=18, textColor=BLUE, spaceBefore=10, spaceAfter=4),
    "p": ParagraphStyle("p", fontName="Body", fontSize=10.5, leading=15, textColor=INK, spaceAfter=6),
    "small": ParagraphStyle("small", fontName="Body", fontSize=9, leading=12.5, textColor=GREY, spaceAfter=4),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=9.2, leading=12.5, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Bold", fontSize=9.2, leading=12.5, textColor=INK),
    "boxtitle": ParagraphStyle("boxtitle", fontName="Bold", fontSize=10.5, leading=14, spaceAfter=3),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.6, leading=11.5, textColor=INK),
}


def P(t, st="p"):
    return Paragraph(t, S[st])


def box(title, body, bg, colour):
    parts = [Paragraph(title, ParagraphStyle("bt", parent=S["boxtitle"], textColor=colour))]
    parts += [P(b) if isinstance(b, str) else b for b in (body if isinstance(body, list) else [body])]
    t = Table([[parts]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 3, colour),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return KeepTogether([t, Spacer(1, 8)])


kid = lambda *b: box("Simple version", list(b), KID_BG, BLUE)
real = lambda *b: box("The real details (for grown-ups)", list(b), REAL_BG, GREY)
warn = lambda title, *b: box(title, list(b), WARN_BG, AMBER)


def code(text):
    t = Table([[Preformatted(text.strip("\n"), S["code"])]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CODE_BG), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return KeepTogether([t, Spacer(1, 6)])


def steps(*items):
    return ListFlowable([ListItem(P(i), leftIndent=14, value=n + 1) for n, i in enumerate(items)],
                        bulletType="1", bulletFontName="Bold", bulletFontSize=10, leftIndent=16, spaceAfter=6)


def bullets(*items):
    return ListFlowable([ListItem(P(i), leftIndent=12) for i in items], bulletType="bullet", start="\u2022",
                        bulletFontSize=10, leftIndent=14, spaceAfter=4)


def table(rows, widths, head=True, pad=4):
    data = [[P(c, "cellb" if (head and r == 0) else "cell") for c in row] for r, row in enumerate(rows)]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("TOPPADDING", (0, 0), (-1, -1), pad), ("BOTTOMPADDING", (0, 0), (-1, -1), pad)]
    if head:
        st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")))
    t.setStyle(TableStyle(st))
    return KeepTogether([t, Spacer(1, 8)]) if len(rows) < 12 else t


def picture(name, caption, width=170):
    from reportlab.lib.utils import ImageReader
    w, h = ImageReader(str(IMG / name)).getSize()
    img = Image(str(IMG / name), width=width * mm, height=width * mm * h / w)
    img.hAlign = "CENTER"
    return KeepTogether([img, Spacer(1, 3), P(caption, "small"), Spacer(1, 6)])


def map_diagram():
    """The five parts and how they talk."""
    d = Drawing(170 * mm, 92 * mm)
    W = 170 * mm

    def node(x, y, w, h, title, sub, fill):
        d.add(Rect(x, y, w, h, rx=8, ry=8, fillColor=colors.HexColor(fill), strokeColor=INK, strokeWidth=0.8))
        d.add(String(x + w / 2, y + h - 17, title, fontName="Bold", fontSize=10.5, textAnchor="middle", fillColor=INK))
        for i, line in enumerate(sub):
            d.add(String(x + w / 2, y + h - 31 - 11 * i, line, fontName="Body", fontSize=8, textAnchor="middle", fillColor=INK))

    def arrow(x1, y1, x2, y2, label=""):
        d.add(Line(x1, y1, x2, y2, strokeColor=GREY, strokeWidth=1.3))
        import math
        a = math.atan2(y2 - y1, x2 - x1)
        d.add(Polygon([x2, y2, x2 - 7 * math.cos(a - 0.4), y2 - 7 * math.sin(a - 0.4),
                       x2 - 7 * math.cos(a + 0.4), y2 - 7 * math.sin(a + 0.4)], fillColor=GREY, strokeColor=GREY))
        if label:
            d.add(String((x1 + x2) / 2 + 4, (y1 + y2) / 2 + 3, label, fontName="Body", fontSize=7.5, fillColor=GREY))

    bw, bh = 52 * mm, 24 * mm
    node(0, 64 * mm, bw, bh, "1. Real battery data", ["measured in a real lab", "(CALCE, Panasonic)"], "#dcfce7")
    node(W / 2 - bw / 2, 64 * mm, bw, bh, "2. MATLAB + Simulink", ["the 'teacher' that learns", "how the battery behaves"], "#fef3c7")
    node(W - bw, 64 * mm, bw, bh, "3. Model file (.json)", ["the recipe it learned", "DATA/MODELS/"], "#fae8ff")
    node(W / 2 - bw / 2, 30 * mm, bw, bh, "4. Python backend", ["the 'pretend battery' that", "follows the recipe"], "#dbeafe")
    node(0, 0, bw, bh, "5. Dashboard", ["the screen you click on", "127.0.0.1:8000"], "#e0f2fe")
    node(W - bw, 0, bw, bh, "6. n8n robots", ["press the buttons for you", "localhost:5678"], "#ffe4e6")
    arrow(bw, 76 * mm, W / 2 - bw / 2, 76 * mm)
    arrow(W / 2 + bw / 2, 76 * mm, W - bw, 76 * mm)
    arrow(W - bw / 2, 64 * mm, W / 2 + bw / 2, 48 * mm)
    arrow(W / 2 - bw / 2, 38 * mm, bw / 2, bh)
    arrow(bw / 2 + 6 * mm, bh, W / 2 - bw / 2 + 6 * mm, 30 * mm)
    arrow(W - bw / 2, bh, W / 2 + bw / 2, 38 * mm)
    return d


def page_deco(c, doc):
    c.saveState()
    c.setFont("Body", 8)
    c.setFillColor(GREY)
    if doc.page > 1:
        c.drawString(20 * mm, 12 * mm, "Battery Lab, explained simply")
        c.drawRightString(190 * mm, 12 * mm, f"page {doc.page}")
    c.restoreState()


story = []
A = story.append

# ------------------------------------------------------------------ cover
A(Spacer(1, 55 * mm))
A(P("The Battery Lab", "title"))
A(Spacer(1, 6))
A(P("explained so simply that a five-year-old could follow it<br/>(and with all the real details for grown-ups)", "subtitle"))
A(Spacer(1, 25 * mm))
A(P("What it is, how it works, how to start it, how to change it, and what to do when something breaks.", "subtitle"))
A(Spacer(1, 60 * mm))
A(P("Project folder: D:\\rakshith-project &nbsp;&middot;&nbsp; Written 12 November 2026", "small"))
A(PageBreak())

# ------------------------------------------------------------------ contents
A(P("What is inside this book", "h1"))
A(table([["Part", "What you will learn"],
         ["1. The big idea", "What a battery is, and what this project does with it"],
         ["2. Words to know", "Little dictionary of the strange words"],
         ["3. The pieces", "The six parts of the project and how they talk to each other"],
         ["4. Where things live", "Which folder holds what"],
         ["5. Turning it on", "Step by step: start everything and check it works"],
         ["6. A tour of the dashboard", "Every page, what it shows, what to click"],
         ["7. The n8n robots", "The 11 helper workflows"],
         ["8. What is real and what is pretend", "Honest status: what is proven, what is not"],
         ["9. How to make changes", "Recipes for every kind of change, with the golden rules"],
         ["10. When something goes wrong", "Problems and fixes"],
         ["11. Cheat sheet", "All the commands on one page"]], [55, 115]))
A(PageBreak())

# ------------------------------------------------------------------ 1 big idea
A(P("1. The big idea", "h1"))
A(kid("A battery is like a <b>juice box</b> for electricity. You fill it up (charging), and things drink from it "
      "(discharging). Some juice boxes are big, some are small, and when they get old they hold less juice.",
      "Testing real batteries is slow and can be dangerous: you have to wait hours, and if you push them too hard they get "
      "hot. So we built a <b>pretend battery inside the computer</b> that behaves just like the real one. Then we can try "
      "anything, as fast as we like, and nothing catches fire.",
      "But a pretend battery is only useful if it tells the truth. So first we <b>taught it</b> using measurements from a "
      "real battery, and then we <b>tested it</b> on measurements it had never seen. It passed."))
A(P("What the project can do", "h2"))
A(bullets("<b>Pretend to be a battery</b>: give it a current, it tells you the voltage, charge level and temperature.",
          "<b>Run experiments</b>: steady drain, pulses, wiggles (ripple), charging - all mixed together if you like.",
          "<b>Keep the battery safe</b>: before doing something risky, it predicts what would happen and turns the current down "
          "if a limit would be broken. This is called <i>moderation</i>.",
          "<b>Be a battery brain (BMS)</b>: guess how full the battery is, how healthy it is, and how much power it can give.",
          "<b>Charge cleverly</b>: find the fastest safe way to charge, and say honestly when a wish is impossible.",
          "<b>Learn and improve</b>: try new versions of the model, and only keep a new one if it is really better.",
          "<b>Write reports</b>, and let <b>n8n robots</b> press the buttons automatically."))
A(real("This is a <b>virtual BMS development platform, not a certified battery controller</b>. The approved model is an "
       "equivalent-circuit model (ECM) with two RC pairs plus hysteresis ('2RC+H'), version 6, for the CALCE INR18650-20R "
       "lithium-ion (NMC) cell at 25 &deg;C. On four unseen drive cycles (US06 and BJDST, starting at 50 % and 80 %) its voltage "
       "error (RMSE) is 12.1 to 15.3 mV. It is weaker below 10 % charge. Every simulated result is labelled SIMULATED."))
A(PageBreak())

# ------------------------------------------------------------------ 2 words
A(P("2. Words to know", "h1"))
A(P("You will see these words everywhere. Here is what they mean, simply first and then exactly.", "p"))
A(table([["Word", "Simple meaning", "Exact meaning"],
         ["Battery cell", "One juice box", "A single electrochemical cell, here an 18650-size Li-ion cell (2 Ah)"],
         ["Pack", "Several juice boxes stuck together", "Cells in series (S) and parallel (P), e.g. 4S1P"],
         ["Voltage (V)", "How hard the juice pushes", "Cell terminal voltage; 2.5 V empty to 4.2 V full here"],
         ["Current (A)", "How fast the juice flows", "Amperes. In this project <b>positive = discharging</b>"],
         ["SOC", "How full the juice box is (0-100 %)", "State of charge, 0 to 1 in the code"],
         ["SOH", "How healthy / old the box is", "State of health: capacity now vs. when new"],
         ["Model", "The pretend battery's recipe", "Equations + numbers (parameters) in DATA/MODELS/*.json"],
         ["Calibrate", "Teach the pretend battery", "Fit the model's numbers to measured data"],
         ["Validate / test", "Check it tells the truth", "Compare against data it was NOT taught with"],
         ["RMSE (mV)", "How wrong it is, on average", "Root-mean-square voltage error in millivolts. Smaller is better"],
         ["Measured", "Really happened in a lab", "Data from instruments on a real cell"],
         ["Simulated", "Made up by a computer", "Output of a model. Always labelled SIMULATED"],
         ["Provisional", "Our best guess, not proven", "Not validated against real measurements"],
         ["BMS", "The battery's brain / babysitter", "Battery management system: monitors, estimates, protects"],
         ["EKF", "A smart guesser", "Extended Kalman filter: estimates SOC from voltage and current"],
         ["Moderation", "Saying 'not so much!'", "Predict a request; if a limit would break, permit a lower current"],
         ["Pulse / ripple", "A sudden gulp / a wiggle", "Short high-current step / periodic (sine, square, triangle) current"],
         ["Drive cycle", "A pretend car trip", "Standard current profile (US06, DST, FUDS, BJDST)"],
         ["Backend / API", "The kitchen behind the counter", "Python FastAPI server; the dashboard and n8n call its URLs"],
         ["Dashboard", "The window you look through", "Web page served by the backend at http://127.0.0.1:8000/"],
         ["n8n / workflow", "A robot with a to-do list", "Automation tool; each workflow calls backend URLs in order"],
         ["Webhook", "The robot's doorbell", "A URL that starts a workflow when something POSTs to it"],
         ["Docker / container", "A lunchbox that holds a program", "n8n runs inside a Docker container named 'n8n'"],
         ["Test (pytest)", "A quiz the code must pass", "Automatic checks in backend/tests; run before trusting a change"]],
        [30, 55, 85], pad=2.2))
A(PageBreak())

# ------------------------------------------------------------------ 3 pieces
A(P("3. The pieces and how they talk", "h1"))
A(kid("Think of a school. <b>Real data</b> is the textbook. <b>MATLAB</b> is the teacher who reads the textbook and writes "
      "down the lesson. The <b>model file</b> is the lesson notes. The <b>Python backend</b> is the student who follows the "
      "notes to answer questions. The <b>dashboard</b> is where you ask the student questions. And the <b>n8n robots</b> are "
      "classroom helpers who ask the student questions for you, on a schedule."))
A(map_diagram())
A(P("Follow the arrows: real data teaches MATLAB, MATLAB writes the model file, the backend reads it. The dashboard "
    "and the n8n robots both talk to the backend over the web (HTTP).", "small"))
A(Spacer(1, 4))
A(table([["Piece", "What it does", "Where"],
         ["1. Real data", "Measurements from real cells. Never changed.", "DATA/RAW_REFERENCE/, Panasonic .mat in the root"],
         ["2. MATLAB + Simulink", "Calibrates and validates the model; Simulink copy proves the maths is the same",
          "MATLAB Online (MATLAB Drive/battery_platform/liion); sources in MATLAB/liion/"],
         ["3. Model files", "The approved numbers, with how good they are and who approved them", "DATA/MODELS/LIION_..._v6.json"],
         ["4. Python backend", "Runs the model, experiments, BMS, charging, reports, database", "backend/bp/ (FastAPI)"],
         ["5. Dashboard", "14 pages to click through", "backend/static/index.html"],
         ["6. n8n", "11 workflows that call the backend", "Docker container 'n8n'; files in n8n/"]], [33, 72, 65]))
A(real("Why is there a Python copy of the MATLAB model? MATLAB only runs as MATLAB Online (in the browser), and a local "
       "program cannot call it. So calibration happens in MATLAB, the result is saved as JSON, and the backend uses a Python "
       "port that is <b>tested to give the same answers</b>: the test <font name='Mono'>backend/tests/test_equivalence.py</font> "
       "requires the same OCV table (within 2 microvolts) and the same test errors (within 0.02 mV).",
       "Golden rule of the design: <b>safety decisions (moderation) happen in the backend, at every simulation step</b>. "
       "n8n is never in that loop; it only starts jobs and records them."))
A(PageBreak())

# ------------------------------------------------------------------ 4 folders
A(P("4. Where things live", "h1"))
A(kid("The project is one big folder, <b>D:\\rakshith-project</b>. Inside are smaller folders, like drawers in a cupboard. "
      "Each drawer holds one kind of thing."))
A(table([["Folder / file", "What is in it", "Should you edit it?"],
         ["backend/bp/", "The Python code: model.py (pretend battery), constraints.py (limits + moderation), bms.py, "
          "charging.py, pack.py, ml.py, learning.py, experiments.py, live.py, reports.py, db.py, api.py", "Yes, carefully"],
         ["backend/static/index.html", "The whole dashboard (one file)", "Yes"],
         ["backend/tests/", "The quizzes (53 tests)", "Add tests when you add features"],
         ["DATA/RAW_REFERENCE/", "Original measured files + PROVENANCE.md (where they came from, checksums)", "<b>Never change</b>; only add"],
         ["DATA/PROCESSED/", "Parsed copies of the raw files", "Rebuilt by code"],
         ["DATA/MODELS/", "Model versions v2-v6 (+ ml/ for machine-learning models)", "Only via the learning tools"],
         ["DATA/DATABASE/platform.sqlite", "Database: experiments, results, logs, n8n runs", "No (use the app)"],
         ["DATA/REPORTS/", "Reports; generated/ has HTML/CSV; demo/ has the video", "Generated"],
         ["MATLAB/liion/", "MATLAB scripts (calibration, validation, Simulink)", "Yes, then rerun in MATLAB Online"],
         ["n8n/make_workflows.py", "Creates the 11 workflow files", "Yes (this, not the JSON)"],
         ["n8n/workflows/", "The 11 workflow files", "No: regenerate them"],
         ["n8n/push_workflows.py, run_webhooks.py", "Send workflows to n8n; test them live", "Run them"],
         ["tools/demo_video/", "Makes the narrated demo video", "Edit scenes.py to change the words"],
         ["tools/make_guide.py", "Makes this PDF", "Edit to change this book"],
         ["docs/", "README-style documents, API reference, this PDF", "Keep up to date"]], [48, 87, 35]))
A(PageBreak())

# ------------------------------------------------------------------ 5 start
A(P("5. Turning it on", "h1"))
A(kid("To play, you need two things switched on: the <b>kitchen</b> (backend) and, if you want robots, the <b>robot room</b> "
      "(n8n). Then you open the <b>window</b> (dashboard) in your web browser."))
A(P("Step 1 - start the backend", "h2"))
A(P("Open PowerShell (or a terminal) and type:"))
A(code(r"""cd D:\rakshith-project\backend
python -m uvicorn bp.api:app --host 0.0.0.0 --port 8000"""))
A(P("Leave this window open. When it says <i>Uvicorn running on http://0.0.0.0:8000</i>, it is ready. "
    "To stop it, press Ctrl+C in that window."))
A(warn("Why --host 0.0.0.0?", "n8n lives inside Docker, which is like a separate little computer. Without "
       "<font name='Mono'>--host 0.0.0.0</font> the backend only listens to this PC, and the n8n robots cannot reach it."))
A(P("Step 2 - open the dashboard", "h2"))
A(P("In Edge or Chrome go to <b>http://127.0.0.1:8000/</b>. The top line should say <i>backend ok</i> and name the model "
    "<i>LIION_INR18650-20R_ECM_2RC_H_v6 - APPROVED</i>. The list of all backend URLs is at http://127.0.0.1:8000/docs."))
A(P("Step 3 - n8n (only if you want the robots)", "h2"))
A(steps("Start <b>Docker Desktop</b> (n8n runs inside it). The container is set to restart by itself, so n8n usually starts "
        "on its own.",
        "Check it: open <b>http://localhost:5678</b>. You should see the n8n editor with workflows named 01 to 11.",
        "If it is not running: <font name='Mono'>docker start n8n</font>."))
A(P("Step 4 - check everything works", "h2"))
A(code(r"""cd D:\rakshith-project\backend
python -m pytest -q                 # expect: 53 passed

cd D:\rakshith-project
python n8n\run_webhooks.py          # expect: passed 15 / 15  (needs backend + n8n running)"""))
A(kid("If the quizzes say <b>passed</b>, everything is healthy. If something says <b>failed</b>, look at chapter 10."))
A(PageBreak())

# ------------------------------------------------------------------ 6 tour
A(P("6. A tour of the dashboard", "h1"))
A(P("The dashboard has 14 buttons along the top. Each one opens a page. Here is what each page is for.", "p"))
A(table([["Page", "Simple version", "What to click"],
         ["Overview", "The front door: is everything OK, which model is in charge", "Nothing; just read"],
         ["Battery configuration", "The battery's ID card: size, limits, chemistry", "Change values, <i>Save as new version</i>"],
         ["Datasets", "The library of real (and pretend) data", "Read the source and approval of each file"],
         ["Calibration & validation", "The report card: how close pretend is to real", "Pick a file, <i>Show</i>"],
         ["Experiment control", "Build an experiment from blocks", "Tick blocks, set numbers, <i>Start experiment</i>"],
         ["Live simulation", "Watch it happen, change things on the fly", "<i>Start</i>, <i>Run 10 steps</i>, <i>Apply current controls</i>"],
         ["Moderation centre", "Ask 'is this safe?' before doing it", "Set charge level and currents, <i>Predict and moderate</i>"],
         ["Performance analytics", "Compare experiments side by side", "Tick experiments, pick a metric, <i>Compare</i>"],
         ["BMS monitoring", "The battery brain at work", "<i>Run</i> (smart guesser), <i>Simulate</i> (balancing)"],
         ["Adaptive charging", "Find the fastest safe charge", "Set start, target, time, <i>Optimise</i>"],
         ["AI centre", "Machine-learning experiments", "<i>Train SOC regressor</i>, <i>Run Panasonic anomaly screen</i>"],
         ["Learning & validation centre", "Every model version and why it was kept or thrown away", "Read; recalibrate via API"],
         ["Historical explorer", "Find old experiments", "<i>Search</i>, click a row to select it"],
         ["Reports", "Make printable reports", "Select an experiment, then <i>Experiment report</i> or <i>Technical report</i>"]],
        [38, 70, 62]))
A(picture("validation.png", "Calibration & validation: the blue line is the real battery, the pink line is the pretend one. "
          "They sit on top of each other. The lower chart is the difference; it only gets big near empty."))
A(picture("control.png", "Experiment control: tick the blocks you want (charging, discharging, pulses, ripple), set the numbers, "
          "press Start experiment. The result is saved with the label SIMULATED.", 150))
A(picture("live.png", "Live simulation: voltage, current (asked for vs. allowed), charge level and temperature, updating as it runs."))
A(picture("moderation.png", "Moderation: a 4 A pulse at 1.5 % charge would push the voltage below the limit, so only 3.96 A is "
          "permitted. The decision is marked CRITICAL and logged."))
A(picture("bms.png", "BMS monitoring: the smart guesser (EKF) finds the right charge level on real data even when it starts "
          "30 % wrong; balancing evens out cells in a simulated pack."))
A(picture("charging.png", "Adaptive charging: 20 to 80 % in 30 minutes is INFEASIBLE (it would need 2.48 A, above the 2.2 A "
          "validated limit). The fastest safe time is 33.8 minutes.", 150))
A(PageBreak())

# ------------------------------------------------------------------ 7 n8n
A(P("7. The n8n robots", "h1"))
A(kid("n8n is a robot helper. Each <b>workflow</b> is a to-do list, like: 'ring the kitchen, ask for an experiment, ask for "
      "a check-up, write it in the diary'. You start a robot by ringing its <b>doorbell</b> (webhook). If something goes wrong, "
      "the robot writes it in the <b>problem diary</b> (the errors list) instead of hiding it."))
A(table([["#", "Robot", "Doorbell (POST to http://localhost:5678/webhook/...)", "What it asks the kitchen"],
         ["01", "Campaign initialization", "campaign-initialization", "Create a campaign (a group of experiments)"],
         ["02", "Experiment execution", "experiment-execution", "Run experiment, characterize it, run diagnostics"],
         ["03", "Constraint moderation", "constraint-moderation-events", "Read an experiment, ask 'is this request safe?'"],
         ["04", "Dataset discovery", "dataset-discovery", "Look for missing known files, fetch, check quality"],
         ["05", "Data cleaning", "data-cleaning", "Quality-check one dataset"],
         ["06", "Characterization", "characterization", "Work out an experiment's key numbers"],
         ["07", "BMS diagnostics", "bms-diagnostics", "Run the battery brain on an experiment"],
         ["08", "ML training", "ml-training", "Train a machine-learning model (if approved data exists)"],
         ["09", "Adaptive charging", "adaptive-charging", "Find the best charge plan"],
         ["10", "Report generation", "report-generation", "Make the experiment and technical reports"],
         ["11", "Error recovery", "error-recovery", "Record an error; re-run a failed experiment once"]], [9, 33, 58, 70]))
A(picture("n8n.png", "All 11 robots triggered live in the demo: every one answered HTTP 200.", 120))
A(real("Every workflow has the same shape: Webhook, then Prepare (adds an idempotency key so the same request twice does not do "
       "the work twice), then backend calls with 3 tries 5 s apart, then a record in the backend (/api/n8n/executions), then the "
       "answer. Any failure goes down the error branch to /api/errors and answers HTTP 500. Workflows hold no passwords; the "
       "backend address comes from the container's environment variable BP_API_URL=http://host.docker.internal:8000."))
A(PageBreak())

# ------------------------------------------------------------------ 8 status
A(P("8. What is real and what is pretend", "h1"))
A(kid("A good scientist never fibs. So every part of this project says clearly whether it is <b>proven</b> or just a "
      "<b>best guess</b>. Green means proven. Amber means 'best guess, be careful'. Red means 'we cannot do this yet'."))
A(table([["Part", "Status", "Why"],
         ["<font color='#15803d'><b>Li-ion NMC model (INR18650-20R)</b></font>", "VALIDATED",
          "Tested once on 4 unseen real drive cycles: 12.1-15.3 mV error. Weaker below 10 % charge."],
         ["<font color='#15803d'><b>Python engine vs MATLAB</b></font>", "EQUIVALENT", "Same answers within 0.02 mV (automatic test)"],
         ["<font color='#15803d'><b>Simulink model vs Python (v6)</b></font>", "EQUIVALENT", "Max difference 0.0062 mV"],
         ["<font color='#15803d'><b>Backend tests</b></font>", "53 / 53 PASS", "python -m pytest -q"],
         ["<font color='#15803d'><b>n8n workflows</b></font>", "15 / 15 PASS", "All 11 run live in n8n 2.42.6"],
         ["<font color='#b45309'><b>Ni-Cd model</b></font>", "PROVISIONAL",
          "The only Ni-Cd file is itself simulated, so there is nothing real to check against"],
         ["<font color='#b45309'><b>Thermal model</b></font>", "PROVISIONAL", "None of the data has temperature measurements"],
         ["<font color='#b45309'><b>Pack balancing</b></font>", "SIMULATED", "Uses the cell model; no pack measurements"],
         ["<font color='#b91c1c'><b>Li-ion NCA / LFP</b></font>", "NOT SUPPORTED", "No data to calibrate them with"],
         ["<font color='#b91c1c'><b>ML SOC regressor</b></font>", "REJECTED", "6.9 % error; the EKF is better, so the rule rejects it"]],
        [55, 30, 85]))
A(warn("To turn amber into green", "Get <b>real measurements</b>: a Ni-Cd cell test with current, voltage and temperature, or any "
       "cell test with a temperature sensor. Add them as described in recipe 9.4, then calibrate and validate. More code alone "
       "cannot make a guess into a proven fact."))
A(PageBreak())

# ------------------------------------------------------------------ 9 changes
A(P("9. How to make changes", "h1"))
A(kid("Changing the project is like changing a recipe in a cookbook. You can do it, but you follow the kitchen rules, and "
      "after every change you <b>taste the food</b> (run the tests) before serving it."))
A(P("The golden rules", "h2"))
A(steps("<b>Never change the original data</b> in DATA/RAW_REFERENCE. Only add new files, with a PROVENANCE note.",
        "<b>Pretend stays labelled pretend.</b> Never call simulated data 'measured' or 'experimental'.",
        "<b>Run the tests after every change</b>: <font name='Mono'>cd backend; python -m pytest -q</font>. 53 passed = good.",
        "<b>Models must earn their place.</b> Never hand-edit the 'approval' of a model file; use the learning tools.",
        "<b>Safety stays in the backend.</b> Never move moderation or limits into n8n.",
        "<b>Edit the maker, not the made thing</b>: change n8n/make_workflows.py, not n8n/workflows/*.json; change "
        "tools/demo_video/scenes.py, not the video.",
        "<b>Keep a copy before big changes</b> (copy the folder, or start using git: <font name='Mono'>git init</font>)."))

A(P("9.1 Change a battery's settings (size, limits for one profile)", "h2"))
A(kid("Like updating the battery's ID card. The old card is kept, the new one gets the next version number."))
A(steps("Dashboard - <b>Battery configuration</b>.", "Pick the profile, change the values (capacity, series/parallel, limits).",
        "Click <b>Save as new version</b>. Wrong values are refused with a message saying why.",
        "To try a variant without touching the original, click <b>Duplicate as...</b> and give it a new id."))
A(real("API: PUT /api/profiles/{id} (new version), POST /api/profiles/{id}/duplicate. Old versions: GET /api/profiles/{id}/versions."))

A(P("9.2 Change the safety limits of a whole chemistry", "h2"))
A(steps("Open <font name='Mono'>backend/bp/constraints.py</font> and find <font name='Mono'>LIMITS</font>.",
        "Change the number, e.g. <font name='Mono'>\"I_chg_warn\": 2.2</font>, <b>and update the matching 'source' text</b> "
        "to say where the new value comes from (datasheet, test, or ASSUMED).",
        "Restart the backend (Ctrl+C, then start it again).", "Run the tests."))
A(warn("Careful", "The 2.2 A charge and 4 A discharge limits are where the model was validated. Above them the model is "
       "guessing. Raise them only with real data or a verified datasheet."))

A(P("9.3 Change what the dashboard looks like or does", "h2"))
A(steps("Open <font name='Mono'>backend/static/index.html</font> (the whole dashboard is this one file).",
        "Pages are listed in <font name='Mono'>PAGES=[...]</font>; each page is a <font name='Mono'>&lt;section id=\"...\"&gt;</font>; "
        "buttons call small functions such as <font name='Mono'>runExp()</font> or <font name='Mono'>charge()</font>.",
        "Save, then refresh the browser (Ctrl+F5). No restart needed for this file."))

A(P("9.4 Add a new dataset (new real measurements)", "h2"))
A(kid("Putting a new book in the library: put it on the shelf, write down where it came from, and add it to the catalogue."))
A(steps("Make a folder, e.g. <font name='Mono'>DATA/RAW_REFERENCE/NICD/&lt;name&gt;/</font>, and copy the original files in, unchanged.",
        "Write a <font name='Mono'>PROVENANCE.md</font> next to them: source, date, licence/terms, and SHA-256 of each file "
        "(PowerShell: <font name='Mono'>Get-FileHash file.zip</font>). Copy the CALCE one as an example.",
        "Add an entry to <font name='Mono'>DATASETS</font> in <font name='Mono'>backend/bp/api.py</font> with id, name, chemistry, "
        "format, <b>source_type</b> (MEASURED or SIMULATED), path and approval.",
        "Only if it may be downloaded automatically: add its <font name='Mono'>url</font>, and add the site to "
        "<font name='Mono'>SOURCES_ALLOWLIST</font> (this is a decision for a person, not the robots).",
        "Restart the backend; check it on the <b>Datasets</b> page; run <b>Data cleaning</b> (or POST /api/datasets/{id}/clean).",
        "Reading a new file format needs a parser in <font name='Mono'>backend/bp/data.py</font> - plus a test."))

A(P("9.5 Teach the model again (recalibrate)", "h2"))
A(kid("Giving the student a new lesson. Afterwards there is an exam on questions they have never seen. "
      "If they do better, they keep the new lesson. If not, it is thrown away. Nobody can cheat."))
A(code(r"""# in PowerShell, with the backend running (takes minutes)
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/learning/recalibrate?structure=params"
#   structure = params | params+ocv_delta | ocv_delta_only

# undo: withdraw the newest approved model, the previous one is used again
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/learning/rollback"""))
A(real("Training uses SP2 DST only; selection uses FUDS; the one-time test uses US06 and BJDST. The new version is APPROVED only "
       "if it is better on validation, physically plausible (no parameter stuck at a bound) and within the test limit. The "
       "result is a new file DATA/MODELS/LIION_..._v7.json. The backend always uses the newest APPROVED file. A new version "
       "should also be checked in Simulink (9.6) before you rely on it."))

A(P("9.6 Change the MATLAB / Simulink side", "h2"))
A(steps("Edit the .m files in <font name='Mono'>MATLAB/liion/</font> on this PC.",
        "Upload them to MATLAB Drive, folder <font name='Mono'>battery_platform/liion</font> (drag and drop in the MATLAB "
        "Online file browser).",
        "In MATLAB Online run the matching script: RUN_LIION_CALIBRATION_VALIDATION, RUN_LIION_DRIVECYCLE_VALIDATION, "
        "RUN_SIMULINK_EQUIVALENCE, RUN_GENERATORS_THERMAL_CONSTRAINTS (or RUN_V6_SIMULINK_CHECK for the current model).",
        "Download any new model JSON / report into DATA/MODELS or DATA/REPORTS.",
        "Run the tests here: <font name='Mono'>test_equivalence.py</font> checks Python still matches MATLAB."))
A(warn("MATLAB Online tips", "After replacing a file in MATLAB Drive, wait about 30 seconds and run "
       "<font name='Mono'>clear all; rehash</font> before running scripts - the Drive sync can briefly show the old or an empty "
       "file. Avoid opening figures interactively; save them as PNG instead."))

A(P("9.7 Change an n8n robot", "h2"))
A(steps("Edit <font name='Mono'>n8n/make_workflows.py</font> (the WF list near the bottom describes all 11).",
        "Rebuild the files: <font name='Mono'>python n8n\\make_workflows.py</font>",
        "Check them: <font name='Mono'>cd backend; python -m pytest -q tests/test_n8n_workflows.py</font>",
        "Send them to n8n (updates in place, no duplicates). Get an API key in the n8n editor under Settings - n8n API, then:"))
A(code(r"""$env:N8N_API_KEY = "<your key>"
python n8n\push_workflows.py
python n8n\run_webhooks.py          # live test, expect 15 / 15"""))
A(warn("Two traps we already fell into", "1. Inside n8n expressions, never write two closing braces together, like "
       "<font name='Mono'>{a: 1}})</font> - n8n thinks the expression ended. Write <font name='Mono'>{a: 1} })</font>. "
       "The test now catches this.<br/>2. Do not re-import the JSON files into n8n; that makes duplicates. Use push_workflows.py."))

A(P("9.8 Add a new backend feature (a new URL)", "h2"))
A(steps("Add the function in the right module of <font name='Mono'>backend/bp/</font> (e.g. charging.py).",
        "Add the URL in <font name='Mono'>backend/bp/api.py</font>, next to similar ones, e.g. "
        "<font name='Mono'>@app.post(\"/api/charging/something\")</font>.",
        "Add a test in <font name='Mono'>backend/tests/</font> (copy a similar test).",
        "Refresh the API reference with the command below, and add a line to docs/API.md.",
        "Restart the backend and run all tests."))
A(code(r"""cd D:\rakshith-project
python tools\export_openapi.py"""))

A(P("9.9 Change the demo video", "h2"))
A(steps("Edit the words or the clicks in <font name='Mono'>tools/demo_video/scenes.py</font>. Write numbers and short names "
        "the way they should be <b>spoken</b> (e.g. 'n eight n', 'eighteen six fifty').",
        "Make sure the backend and n8n are running.",
        "Run <font name='Mono'>python tools\\demo_video\\make_video.py</font> (about 4 minutes). Try "
        "<font name='Mono'>--dry</font> first: it only takes screenshots so you can check the pages.",
        "The video is written to DATA/REPORTS/demo/BATTERY_PLATFORM_DEMO.mp4."))
A(real("Needs <font name='Mono'>pip install playwright piper-tts</font>, ffmpeg, Microsoft Edge, and the Piper voice files "
       "en_US-lessac-high.onnx + .onnx.json in %LOCALAPPDATA%\\piper-voices (from huggingface.co/rhasspy/piper-voices). The voice "
       "runs offline. Music is generated by ffmpeg, so there are no copyright issues."))

A(P("9.10 Change this book", "h2"))
A(P("Edit the text in <font name='Mono'>tools/make_guide.py</font> and run <font name='Mono'>python tools\\make_guide.py</font>. "
    "Pictures are in docs/guide_img/."))
A(PageBreak())

# ------------------------------------------------------------------ 10 troubleshooting
A(P("10. When something goes wrong", "h1"))
A(kid("Don't panic. Read the message - it usually says what is wrong. Then find it in this table."))
A(table([["What you see", "Why", "What to do"],
         ["Dashboard page will not open", "Backend is not running", "Start it (chapter 5, step 1)"],
         ["'Address already in use' / port 8000", "A backend is already running", "Use that one, or close it first"],
         ["'no approved Li-ion model in DATA/MODELS'", "Model files missing or none APPROVED", "Restore DATA/MODELS from your copy; or roll back"],
         ["n8n robot answers HTTP 500, status FAILED", "The backend said no (bad input, unknown id) or is not reachable",
          "Look at http://127.0.0.1:8000/api/errors and the backend window"],
         ["n8n robots time out / cannot connect", "Backend started without --host 0.0.0.0, or Docker stopped",
          "Restart backend with --host 0.0.0.0; start Docker Desktop; docker start n8n"],
         ["n8n: 'invalid syntax' in a node", "Two closing braces together in an expression", "See the trap in 9.7"],
         ["Two copies of each workflow in n8n", "Workflows were imported twice", "Delete the extra copies in the n8n editor; use push_workflows.py"],
         ["A test fails after your change", "The change broke something the test protects",
          "Read the test name and message; undo or fix; run again"],
         ["test_equivalence fails", "Python model no longer matches MATLAB", "Undo model.py changes, or re-export from MATLAB"],
         ["Adaptive charging says INFEASIBLE", "Not a bug: the wish breaks a limit", "Choose a longer time, or a smaller SOC range"],
         ["Model results look wrong below 10 % charge", "Known weakness of the model", "Treat results there with care"],
         ["MATLAB Online shows an empty .m file", "MATLAB Drive sync", "Wait 30 s, clear all; rehash, re-upload if needed"],
         ["Video voice missing / error about piper", "Voice files not found", "Put them in %LOCALAPPDATA%\\piper-voices (9.9)"]],
        [52, 55, 63]))
A(PageBreak())

# ------------------------------------------------------------------ 11 cheat sheet
A(P("11. Cheat sheet", "h1"))
A(table([["I want to...", "Do this"],
         ["Start the backend", "<font name='Mono'>cd backend; python -m uvicorn bp.api:app --host 0.0.0.0 --port 8000</font>"],
         ["Open the dashboard", "http://127.0.0.1:8000/"],
         ["See every backend URL", "http://127.0.0.1:8000/docs"],
         ["Open n8n", "http://localhost:5678 (start Docker Desktop first)"],
         ["Start n8n if stopped", "<font name='Mono'>docker start n8n</font>"],
         ["Run all tests", "<font name='Mono'>cd backend; python -m pytest -q</font>"],
         ["Test the robots live", "<font name='Mono'>python n8n\\run_webhooks.py</font>"],
         ["Rebuild robot files", "<font name='Mono'>python n8n\\make_workflows.py</font>"],
         ["Send robots to n8n", "<font name='Mono'>$env:N8N_API_KEY=\"...\"; python n8n\\push_workflows.py</font>"],
         ["Recalibrate the model", "POST http://127.0.0.1:8000/api/learning/recalibrate?structure=params"],
         ["Undo the newest model", "POST http://127.0.0.1:8000/api/learning/rollback"],
         ["Make the technical report", "Dashboard - Reports - Technical report (file in DATA/REPORTS/generated/)"],
         ["See n8n run history", "http://127.0.0.1:8000/api/n8n/executions"],
         ["See recorded errors", "http://127.0.0.1:8000/api/errors (newest first)"],
         ["Remake the demo video", "<font name='Mono'>python tools\\demo_video\\make_video.py</font>"],
         ["Remake this PDF", "<font name='Mono'>python tools\\make_guide.py</font>"]], [50, 120]))
A(Spacer(1, 10))
A(P("Other documents", "h2"))
A(bullets("README.md - short overview and status table", "docs/ARCHITECTURE.md - how the parts connect, in detail",
          "docs/API.md and docs/openapi.json - every backend URL", "docs/N8N.md - n8n setup and test record",
          "DATA/REPORTS/platform_results.md - all results in one place",
          "DATA/RAW_REFERENCE/LITHIUM_ION/CALCE_INR18650-20R/PROVENANCE.md - where the real data came from"))
A(Spacer(1, 14))
A(kid("That's everything! You now know what the Battery Lab is, how to turn it on, how to play with it, how to change it "
      "safely, and how to fix it. Remember: taste the food (run the tests) after every change, and never fib about what is real."))

doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
                        title="The Battery Lab, explained simply", author="Battery Lab project", subject="Project guide")
doc.build(story, onFirstPage=page_deco, onLaterPages=page_deco)
print("wrote", OUT)
