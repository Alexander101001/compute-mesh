#!/usr/bin/env python3
"""Compute-mesh node agent — runs 24/7 on Oracle VMs.
- Heartbeat: commits status/<hostname>.json to this repo every 15 min + Telegram ping every 6h.
- Jobs: every 60s, git pull; run any /jobs/pending/*.sh (oldest first), move to jobs/done,
  report stdout tail to Telegram.
Config via env: MESH_REPO, MESH_TOKEN (telegram bot), MESH_ADMIN (telegram chat id).
"""
import os, json, subprocess, time, socket, pathlib, urllib.request, datetime

REPO_DIR = pathlib.Path(os.environ.get("MESH_REPO", str(pathlib.Path.home() / "compute-mesh")))
HOST = socket.gethostname()
BOT = os.environ.get("MESH_TOKEN", "")
ADMIN = os.environ.get("MESH_ADMIN", "")

def tg(msg):
    if not BOT or not ADMIN:
        return
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{BOT}/sendMessage",
            json.dumps({"chat_id": ADMIN, "text": msg[:4000]}).encode(), timeout=15)
    except Exception:
        pass

def sh(cmd, cwd=None):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=(1800 if "bash" in cmd else 120))

def stats():
    load = os.getloadavg()
    mem = sh("free -m").stdout.splitlines()[1].split()
    disk = sh("df -h /").stdout.splitlines()[1].split()
    return {"host": HOST, "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "load": load, "mem_mb": {"total": mem[1], "used": mem[2]},
            "disk": {"size": disk[1], "used": disk[2], "pct": disk[4]}}

def heartbeat():
    s = stats()
    p = REPO_DIR / "status" / f"{HOST}.json"
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(s, indent=2))
    sh("git add -A && git commit -q -m 'status' || true", cwd=REPO_DIR)
    sh("git pull -q --rebase --autostash; git push -q", cwd=REPO_DIR)
    tg(f"🛰 mesh heartbeat {HOST}: load {s['load'][0]:.1f}, mem {s['mem_mb']['used']}M, disk {s['disk']['pct']}")

def run_jobs():
    sh("git pull -q --rebase --autostash || true", cwd=REPO_DIR)
    pend = sorted((REPO_DIR / "jobs" / "pending").glob("*.sh"))
    for job in pend:
        tg(f"▶ {HOST} running job {job.name}")
        r = sh(f"bash {job}", cwd=REPO_DIR)
        done = REPO_DIR / "jobs" / "done" / (job.stem + f".{int(time.time())}")
        done.parent.mkdir(exist_ok=True)
        job.rename(str(done) + ".sh")
        pathlib.Path(str(done) + ".log").write_text((r.stdout + "\n--- STDERR ---\n" + r.stderr)[-8000:])
        sh("git add -A && git commit -q -m 'job done' && git push -q || true", cwd=REPO_DIR)
        tail = (r.stdout or "")[-700:]
        tg(f"✅ {job.name} done on {HOST} (exit {r.returncode})\n{tail}")

last_hb = 0
tg(f"🟢 mesh node online: {HOST}")
while True:
    try:
        run_jobs()
        if time.time() - last_hb > 6 * 3600:
            heartbeat(); last_hb = time.time()
        elif int(time.time() / 900) != int((time.time() - 60) / 900):
            # lightweight 15-min status push without telegram spam
            s = stats(); (REPO_DIR / "status" / f"{HOST}.json").write_text(json.dumps(s, indent=2))
            sh("git add status* status/*.json; git commit -q -m status; git pull -q --rebase --autostash; git push -q || true", cwd=REPO_DIR)
    except Exception as e:
        tg(f"⚠ {HOST} node error: {e}")
    time.sleep(60)
