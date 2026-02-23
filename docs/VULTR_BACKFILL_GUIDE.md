# Run SPY Escalation Backfill on Vultr (Beginner Guide)

This guide walks you through running the slow escalation backfill on your Vultr server. You'll copy your project + data to the server, run the script, then copy the results back.

---

## What You Need Before Starting

1. **Vultr server** – Running and accessible via SSH
2. **Your laptop** – With the regime-engine project and `data/regime_cache.db`
3. **Terminal** – On Mac: open **Terminal** (Applications → Utilities → Terminal)

---

## Step 1: Get Your Vultr Server Details

1. Log in to [Vultr](https://my.vultr.com/)
2. Click your server in the list
3. Note:
   - **IP Address** (e.g. `123.45.67.89`)
   - **Username** (usually `root`)
   - **Password** (or you may use an SSH key)

---

## Step 2: Connect to Your Server (SSH)

Open Terminal on your Mac and run (replace with your IP and username):

```bash
ssh root@YOUR_SERVER_IP
```

Example: `ssh root@123.45.67.89`

- First time: type `yes` when asked about fingerprint
- Enter your password when prompted
- You're in when you see something like `root@vultr:~#`

---

## Step 3: Install Python and Git on the Server

Run these commands one at a time (copy-paste each line, press Enter):

```bash
apt update
apt install -y python3 python3-pip python3-venv git
```

Wait for each to finish before running the next.

---

## Step 4: Copy Your Project to the Server

**Option A – You use Git (project on GitHub):**

```bash
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/YOUR_USERNAME/regime-engine.git
cd regime-engine
```

**Option B – You don't use Git:** Copy the whole project from your Mac:

On your **Mac** (new Terminal):

```bash
cd /Users/sherifsaad/Documents
scp -r regime-engine root@YOUR_SERVER_IP:~/projects/
```

Then on the **server**:

```bash
cd ~/projects/regime-engine
```

---

## Step 5: Copy Your Database from Your Laptop

**On your Mac** (open a NEW Terminal window – don't close the SSH one):

```bash
cd /Users/sherifsaad/Documents/regime-engine

# Create data folder on server if needed (if you used Option B, it may already exist)
ssh root@YOUR_SERVER_IP "mkdir -p ~/projects/regime-engine/data"

scp data/regime_cache.db root@YOUR_SERVER_IP:~/projects/regime-engine/data/
```

Replace `YOUR_SERVER_IP` with your server's IP. Enter your password when asked.

This copies your database (with all SPY bars) to the server.

---

## Step 6: Set Up Python Environment on the Server

Switch back to your SSH terminal (the one connected to the server):

```bash
cd ~/projects/regime-engine

python3 -m venv .venv
source .venv/bin/activate

pip install -e .
```

Wait for `pip install` to finish. You should see `Successfully installed regime-engine`.

---

## Step 7: Run the Backfill

Still in the SSH terminal, with `.venv` activated:

**1day only (fastest, ~1–4 hours):**
```bash
python scripts/backfill_spy_signals_1day.py
```

**All timeframes – 15min, 1h, 4h, 1day, 1week (much longer):**
```bash
python scripts/backfill_spy_signals_1day.py --all
```

You should see something like:

```
DB: /path/to/regime_cache.db
Timeframes: 1day

--- 1day ---
Bars: 8321
  Wrote 8321 rows
```

Then it will run. **1day can take 1–4+ hours** depending on the server. `--all` will take longer (each TF is separate). Let it run. Do not close the terminal.

---

## Step 8: Copy the Results Back to Your Laptop

When the script finishes, you'll see:

```
Wrote rows: 8321
Saved: escalation_history (SPY 1day)
```

**On your Mac** (new Terminal window):

```bash
scp root@YOUR_SERVER_IP:~/projects/regime-engine/data/regime_cache.db /Users/sherifsaad/Documents/regime-engine/data/regime_cache.db
```

This overwrites your local DB with the one that now has `escalation_history` filled.

**Or**, if you only want the escalation table (smaller file):

On the server:
```bash
sqlite3 ~/projects/regime-engine/data/regime_cache.db ".dump escalation_history" > ~/escalation_history.sql
```

On your Mac:
```bash
scp root@YOUR_SERVER_IP:~/escalation_history.sql /Users/sherifsaad/Documents/regime-engine/
```

Then on your Mac, to import into your local DB:
```bash
cd /Users/sherifsaad/Documents/regime-engine
sqlite3 data/regime_cache.db < escalation_history.sql
```

---

## Troubleshooting

| Problem | Fix |
|--------|-----|
| `ssh: command not found` | Use Terminal (Mac has SSH built in) |
| `Permission denied` | Check your Vultr password; try resetting it in Vultr dashboard |
| `No such table: bars` | Your DB has no bars. Run fetch/backfill scripts first on your laptop, then copy the DB again. |
| `Not enough bars` | You need at least 400 bars. Ensure your DB has SPY 1day data. |
| Script seems stuck | It's slow. Wait. You can run `top` in another SSH session to see if Python is using CPU. |

---

## All Timeframes (15min, 1h, 4h, 1day, 1week)

Use `--all` to backfill all TFs:

```bash
python scripts/backfill_spy_signals_1day.py --all
```

You need bars in the DB for each TF first (from your scheduler or fetch scripts). If a TF has no bars or fewer than 400, it will be skipped.
