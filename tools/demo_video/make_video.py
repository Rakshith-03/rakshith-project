"""Record the project demo video: narrated (local Piper neural voice), dashboard + n8n recorded in Edge via Playwright,
synthesized background music ducked under the voice, muxed with ffmpeg.
Needs: backend on :8000, n8n on :5678, ffmpeg on PATH, `pip install playwright piper-tts` + the voice file below
(Playwright uses the installed Edge, no browser download).
Run:  python tools/demo_video/make_video.py [--dry] [--work DIR]
Out:  DATA/REPORTS/demo/BATTERY_PLATFORM_DEMO.mp4   (--dry: screenshots only, in WORK/shots)"""
import argparse, json, subprocess, sys, time, urllib.request, wave
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from scenes import SCENES

DASH, N8N, API = "http://127.0.0.1:8000/", "http://localhost:5678/webhook/", "http://127.0.0.1:8000"
W, H, PAD = 1920, 1080, 1.0   # PAD: silence after each narration line (s)
# Piper neural voice, runs locally (narration text never leaves the PC). Voice files (~114 MB):
# https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0/en/en_US/lessac/high -> %LOCALAPPDATA%/piper-voices/
VOICE = Path.home() / "AppData" / "Local" / "piper-voices" / "en_US-lessac-high.onnx"
_voice = None


def tts(text, out):
    global _voice
    from piper import PiperVoice, SynthesisConfig
    _voice = _voice or PiperVoice.load(str(VOICE))
    with wave.open(str(out), "wb") as w:   # length_scale > 1: slightly slower, clearer delivery
        _voice.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=1.08, noise_scale=0.5, noise_w_scale=0.6))
    with wave.open(str(out)) as w:
        return w.getnframes() / w.getframerate()


def post(slug, body):
    req = urllib.request.Request(N8N + slug, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, time.time() - t
    except urllib.error.HTTPError as e:
        return e.code, time.time() - t


def n8n_calls():
    eid = json.load(urllib.request.urlopen(API + "/api/experiments"))[0]["id"]
    cfg = {"duration_s": 300, "initial_soc": 0.8, "discharging": {"enabled": True, "current_A": 2.0}}
    return [("01 Campaign initialization", "campaign-initialization", {"name": "demo video"}),
            ("02 Experiment execution", "experiment-execution", {"config": cfg}),
            ("03 Constraint moderation", "constraint-moderation-events", {"experiment_id": eid}),
            ("04 Dataset discovery", "dataset-discovery", {}),
            ("05 Data cleaning", "data-cleaning", {"dataset_id": "CALCE_SP2_US06"}),
            ("06 Characterization", "characterization", {"experiment_id": eid}),
            ("07 BMS diagnostics", "bms-diagnostics", {"experiment_id": eid}),
            ("08 ML training", "ml-training", {"task": "soc_regressor"}),
            ("09 Adaptive charging", "adaptive-charging", {"initial_soc": 0.2, "target_soc": 0.8, "target_time_s": 2700}),
            ("10 Report generation", "report-generation", {"experiment_id": eid}),
            ("11 Error recovery", "error-recovery", {"experiment_id": eid, "error": "demo"})]


def run_scene(page, sc, until, dashboard_loaded):
    if sc["kind"] in ("card", "n8n"):
        page.goto((HERE / "card.html").as_uri())
        page.evaluate("([t,s,l]) => card(t,s,l)", [sc["title"], sc["sub"], sc.get("lines", [])])
        if sc["kind"] == "n8n":
            page.wait_for_timeout(2500)
            for name, slug, body in n8n_calls():
                code, dt = post(slug, body)
                ok = code == 200
                page.evaluate("([x,c]) => add(x,c)", [f"{name}<span class=t>HTTP {code} &middot; {dt:.1f} s</span>",
                                                      "pass" if ok else "fail"])
                page.wait_for_timeout(350)
        return False
    if not dashboard_loaded:
        page.goto(DASH); page.wait_for_load_state("networkidle")
    page.evaluate("p => { show(p); window.scrollTo(0,0) }", sc["page"])
    page.wait_for_timeout(1200)
    for a in sc["actions"]:
        if a.startswith("wait:"):
            page.wait_for_timeout(int(a[5:])); continue
        try:
            page.evaluate(f"async () => {{ await ({a}) }}")
        except Exception as e:
            print("  action failed:", a, str(e)[:120])
        page.wait_for_timeout(600)
    left = until - time.time()          # slow scroll through the rest of the page while the narration finishes
    hgt = page.evaluate("document.documentElement.scrollHeight") - H
    if sc.get("scroll", True) and hgt > 50 and left > 2:
        steps = int(left * 10)
        for i in range(1, steps + 1):
            page.evaluate(f"window.scrollTo(0, {hgt * min(1, i / steps * 1.15):.0f})")
            page.wait_for_timeout(100)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--mux-only", action="store_true", help="re-mix audio onto the last recording in --work")
    ap.add_argument("--work", default=str(ROOT / "DATA" / "REPORTS" / "demo" / "work"))
    a = ap.parse_args()
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    if a.mux_only:
        tl = json.loads((work / "timeline.json").read_text())
        return mux(work, max(work.glob("*.webm"), key=lambda f: f.stat().st_mtime), tl["starts"], tl["total"])
    durs = []
    for i, sc in enumerate(SCENES):
        durs.append(3.0 if a.dry else tts(sc["say"], work / f"say_{i:02d}.wav"))
        print(f"scene {i:02d} {sc.get('page', sc['kind'])}: {durs[-1]:.1f}s", flush=True)

    from playwright.sync_api import sync_playwright
    starts = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        ctx = b.new_context(viewport={"width": W, "height": H},
                            **({} if a.dry else {"record_video_dir": str(work), "record_video_size": {"width": W, "height": H}}))
        page = ctx.new_page(); t0 = time.time()
        page.goto((HERE / "card.html").as_uri())
        loaded = False
        for i, sc in enumerate(SCENES):
            s = time.time(); starts.append(s - t0)
            loaded = run_scene(page, sc, s + durs[i] + PAD, loaded) or loaded
            if a.dry:
                (work / "shots").mkdir(exist_ok=True); page.screenshot(path=str(work / "shots" / f"{i:02d}.png"))
            rest = s + durs[i] + PAD - time.time()
            if rest > 0:
                page.wait_for_timeout(rest * 1000)
        total = time.time() - t0 + 1.5
        page.wait_for_timeout(1500)
        video = None if a.dry else Path(page.video.path())
        ctx.close(); b.close()
    if a.dry:
        print("dry run: screenshots in", work / "shots"); return
    (work / "timeline.json").write_text(json.dumps({"starts": starts, "durs": durs, "total": total}, indent=1))
    mux(work, video, starts, total)


def mux(work, video, starts, total):
    # narration: each line at its scene start. Music: soft synthesized pad, chords A - F#m - D - E crossfaded with
    # overlapping Hann envelopes (4 shifted 16 s windows sum to a constant), so no clicks at chord changes; ducked under the voice.
    ins, chains = ["-i", str(video)], []
    for i, s in enumerate(starts):
        ins += ["-i", str(work / f"say_{i:02d}.wav")]
        chains.append(f"[{i + 1}:a]aresample=48000,adelay={int(s * 1000 + 300)}:all=1[v{i}]")
    n = len(starts)
    chords = [(220.0, 277.18, 329.63), (185.0, 220.0, 277.18), (146.83, 220.0, 293.66), (164.81, 207.65, 246.94)]
    pad = "+".join(f"(0.5-0.5*cos(2*PI*(t-{4 * j})/16))*(" + "+".join(f"sin(2*PI*{f}*t)" for f in c) + ")"
                   for j, c in enumerate(chords))
    bgm = f"aevalsrc='0.012*({pad})*(0.8+0.2*sin(2*PI*0.2*t))|0.012*({pad})*(0.8+0.2*sin(2*PI*0.2*t+1))':s=48000:d={total:.2f}"
    graph = ";".join(chains) + ";" + "".join(f"[v{i}]" for i in range(n)) + \
        f"amix=inputs={n}:normalize=0,apad,atrim=0:{total:.2f},loudnorm=I=-16:TP=-2,aresample=48000,asplit=2[voice][key];" \
        f"{bgm},lowpass=f=1800,afade=t=in:d=3,afade=t=out:st={total - 4:.2f}:d=4[m];" \
        "[m][key]sidechaincompress=threshold=0.01:ratio=20:attack=10:release=800[duck];" \
        "[voice][duck]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]"
    out = ROOT / "DATA" / "REPORTS" / "demo" / "BATTERY_PLATFORM_DEMO.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *ins, "-filter_complex", graph,
                    "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                    "-r", "30", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)], check=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
