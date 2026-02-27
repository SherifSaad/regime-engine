# Vultr Run Plan — 1600 Symbols

**Purpose:** Run compute on Vultr, track progress, survive SSH disconnect.

---

## 1. Deploy (one-time)

```bash
# From Mac: upload project
scp -r regime-engine root@VULTR_IP:~/

# SSH in
ssh root@VULTR_IP

# Setup (venv required — system pip is externally managed)
cd ~/regime-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[perf]"
```

---

## 2. Run compute (survives SSH disconnect)

```bash
cd ~/regime-engine
source .venv/bin/activate
screen -S compute
PYTHONUNBUFFERED=1 python3 scripts/vultr_run_compute.py --workers 16 2>&1 | tee compute.log
```

Press **Ctrl+A** then **D** to detach. Process keeps running.

---

## 3. Live progress

Open a second SSH session, then:

```bash
tail -f ~/regime-engine/compute.log
```

---

## 4. Reattach to see output

```bash
screen -r compute
```

---

## 5. Status

```bash
cd ~/regime-engine && source .venv/bin/activate && python3 scripts/vultr_run_compute.py --status
```

---

## 6. Resume / retry

- **Resume** (skip completed, run pending only): `--resume`
- **Retry failed** (clear failed, run all not-completed): run **without** `--resume`

```bash
# Resume after interrupt
python3 scripts/vultr_run_compute.py --workers 16 --resume

# Retry all failed (e.g. after fixing deps)
python3 scripts/vultr_run_compute.py --workers 16
```

---

## 7. Transfer to Mac

```bash
rsync -avz --progress root@VULTR_IP:~/regime-engine/data/assets/ \
  /Users/sherifsaad/Documents/regime-engine/data/assets/
```

---

## 8. Quick reference

| Command | Purpose |
|---------|---------|
| `tail -f ~/regime-engine/compute.log` | Live progress |
| `screen -r compute` | Reattach to compute session |
| `python3 scripts/vultr_run_compute.py --status` | Done/failed counts |
| `ps aux \| grep -E "vultr_run\|compute_asset" \| grep -v grep` | What's running |
