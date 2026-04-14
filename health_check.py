#!/usr/bin/env python3
"""
Limitless AI — System Health Check
Runs a complete diagnostic and prints a PASS/FAIL/WARN report.
"""
import os
import sys
import json
import glob
import time
import re
import requests
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE           = Path("/root/limitless-ai")
LOGS           = BASE / "logs"
MIROFISH_DIR   = LOGS / "mirofish"
PIPELINE_FILE  = LOGS / "pipeline_runs.jsonl"
POSITIONS_FILE = LOGS / "polymarket_positions.json"
PERF_FILE      = LOGS / "polymarket_paper_performance.json"
BACKTEST_FILE  = LOGS / "backtest_summary.json"
CONFIG_FILE    = BASE / "TradingAgents" / "limitless_config.py"
ENV_FILE       = BASE / "TradingAgents" / ".env"
PM_BET_FILE    = BASE / "polymarket_paper_bet.py"

# ── Result accumulators ───────────────────────────────────────────────────────
passes, warns, fails = [], [], []
lines = []          # display lines collected per section
criticals = []      # critical items for bottom summary

def p(text=""):
    lines.append(text)

def now_utc():
    return datetime.now(timezone.utc)

def minutes_since(path):
    mtime = os.path.getmtime(path)
    return (time.time() - mtime) / 60

def age_label(mins):
    if mins < 60:
        return "%dmin ago" % int(mins)
    h = int(mins // 60)
    m = int(mins % 60)
    return ("%dh %dmin ago" % (h, m)) if m else ("%dh ago" % h)


# ══════════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE
# ══════════════════════════════════════════════════════════════════════════════
p("║ INFRASTRUCTURE")

# 1. MIROFISH RECEIVER --------------------------------------------------------
try:
    r = requests.get("http://localhost:9876/health", timeout=5)
    if r.status_code == 200:
        passes.append("MiroFish receiver")
        p("║  \u2705 MiroFish receiver: running")
    else:
        fails.append("MiroFish receiver (HTTP %d)" % r.status_code)
        p("║  \u274c MiroFish receiver: bad status %d" % r.status_code)
        criticals.append("MiroFish receiver returned HTTP %d — restart service" % r.status_code)
except Exception:
    fails.append("MiroFish receiver (not responding)")
    p("║  \u274c MiroFish receiver: not responding")
    criticals.append("MiroFish receiver down — cd /root/limitless-ai && nohup python3 mirofish_receiver.py &")

# 2. HEADLINES QUALITY --------------------------------------------------------
POISON_STRINGS = [
    "FINAL TRADING DECISION", "OVERWEIGHT", "EXECUTIVE SUMMARY",
    "RATING:", "Action Plan", "Entry", "Portfolio",
]
try:
    rh = requests.get("http://localhost:9876/latest_headlines", timeout=5)
    if rh.status_code == 200:
        hdata = rh.json()
        headline = hdata.get("primary_headline", "")
        found_poison = [s for s in POISON_STRINGS if s.lower() in headline.lower()]
        if found_poison:
            fails.append("Headlines (reading PM output)")
            short = headline[:48].replace("\n", " ")
            p("║  \u274c Headlines: reading PM output (not news!)")
            p('║     \u2192 "%s..."' % short)
            criticals.append("Headlines poisoned with PM output — fix latest_headline.json: run a Tavily fetch to cache real news, or fix mirofish_receiver.py get_enriched_context() fallback")
        else:
            passes.append("Headlines quality")
            short = (headline[:48].replace("\n", " ")) if headline else "(empty — no news cached yet)"
            p("║  \u2705 Headlines: clean (no PM strings detected)")
            p('║     \u2192 "%s"' % short[:50])
    else:
        warns.append("Headlines (endpoint error %d)" % rh.status_code)
        p("║  \u26a0\ufe0f  Headlines: endpoint returned %d" % rh.status_code)
except Exception as e:
    warns.append("Headlines (could not reach endpoint)")
    p("║  \u26a0\ufe0f  Headlines: could not reach /latest_headlines")

# 3. MIROFISH BTC FILE AGE ----------------------------------------------------
all_mf_files = sorted(
    glob.glob(str(MIROFISH_DIR / "mirofish_*.json")),
    key=os.path.getmtime, reverse=True
)
btc_files = [f for f in all_mf_files if "polymarket_mirofish" not in f]
if btc_files:
    latest_btc = btc_files[0]
    mins_btc = minutes_since(latest_btc)
    fname_btc = os.path.basename(latest_btc)
    if mins_btc <= 90:
        passes.append("MiroFish BTC file")
        p("║  \u2705 MiroFish BTC: %s (%s)" % (fname_btc, age_label(mins_btc)))
    elif mins_btc <= 180:
        warns.append("MiroFish BTC file (%s old)" % age_label(mins_btc))
        p("║  \u26a0\ufe0f  MiroFish BTC: %s — may have missed a run" % age_label(mins_btc))
    else:
        fails.append("MiroFish BTC file (%s old)" % age_label(mins_btc))
        p("║  \u274c MiroFish BTC: %s old — Task Scheduler down?" % age_label(mins_btc))
        criticals.append("MiroFish BTC stale (%s) — check Task Scheduler on Windows PC" % age_label(mins_btc))
else:
    fails.append("MiroFish BTC file (none found)")
    p("║  \u274c MiroFish BTC: no mirofish_*.json files found")
    criticals.append("No MiroFish BTC files — Task Scheduler never ran mirofish_sender.py")

# 3b. MIROFISH BTC AGENT INPUT QUALITY ----------------------------------------
# Check whether the agents were actually fed real news or PM output
if btc_files:
    try:
        with open(btc_files[0]) as _f:
            _btc_data = json.load(_f)
        _news_art = _btc_data.get("news_article", "") or ""
        _file_poison = [s for s in POISON_STRINGS if s.lower() in _news_art.lower()]
        if _file_poison:
            fails.append("MiroFish BTC agents fed PM output (not real news)")
            _short_art = _news_art[:46].replace("\n", " ")
            p("║  \u274c Agent input: PM output fed instead of news!")
            p('║     \u2192 "%s..."' % _short_art)
            criticals.append("MiroFish BTC agents scored PM trading decisions not news — populate latest_headline.json with Tavily news BEFORE mirofish_sender.py runs on the PC")
        else:
            _art_preview = _news_art[:40].replace("\n"," ") if _news_art else "(no news_article field)"
            passes.append("MiroFish BTC agent inputs (news content)")
            p("║  \u2705 Agent input clean: \"%s\"" % _art_preview)
    except Exception:
        pass

# 4. MIROFISH POLYMARKET FILE AGE ---------------------------------------------
pm_files = sorted(
    glob.glob(str(MIROFISH_DIR / "polymarket_mirofish_*.json")),
    key=os.path.getmtime, reverse=True
)
if pm_files:
    latest_pm = pm_files[0]
    mins_pm = minutes_since(latest_pm)
    fname_pm = os.path.basename(latest_pm)
    if mins_pm <= 180:
        passes.append("MiroFish Polymarket file")
        p("║  \u2705 MiroFish Polymarket: %s (%s)" % (fname_pm, age_label(mins_pm)))
    elif mins_pm <= 360:
        warns.append("MiroFish Polymarket file (%s old)" % age_label(mins_pm))
        p("║  \u26a0\ufe0f  MiroFish Polymarket: %s old" % age_label(mins_pm))
    else:
        fails.append("MiroFish Polymarket file (%s old)" % age_label(mins_pm))
        p("║  \u274c MiroFish Polymarket: %s old" % age_label(mins_pm))
        criticals.append("MiroFish Polymarket stale (%s) — check polymarket mirofish Task Scheduler" % age_label(mins_pm))
else:
    fails.append("MiroFish Polymarket file (none found)")
    p("║  \u274c MiroFish Polymarket: no files found")
    criticals.append("No MiroFish Polymarket files — mirofish sender never ran polymarket mode")


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
p("")
p("║ PIPELINE")

pipeline_entries = []
if PIPELINE_FILE.exists():
    with open(PIPELINE_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    pipeline_entries.append(json.loads(line))
                except Exception:
                    pass

# 5. PIPELINE LAST RUN --------------------------------------------------------
if pipeline_entries:
    last_run = pipeline_entries[-1]
    ts_str = last_run.get("timestamp", "")
    try:
        last_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        mins_pipeline = (now_utc() - last_dt).total_seconds() / 60
        decision = last_run.get("decision", "?")
        age = age_label(mins_pipeline)
        if mins_pipeline <= 300:
            passes.append("Pipeline last run")
            p("║  \u2705 Last run: %s (%s)" % (age, decision))
        elif mins_pipeline <= 600:
            warns.append("Pipeline last run (%s ago)" % age)
            p("║  \u26a0\ufe0f  Last run: %s (%s) — cron slow?" % (age, decision))
        else:
            fails.append("Pipeline last run (%s ago)" % age)
            p("║  \u274c Last run: %s (%s) — CRON IS DEAD" % (age, decision))
            criticals.append("Pipeline cron dead (last ran %s) — check crontab -l on VPS and venv activation" % age)
    except Exception:
        warns.append("Pipeline (could not parse timestamp)")
        p("║  \u26a0\ufe0f  Last run: could not parse timestamp")
else:
    fails.append("Pipeline (no runs logged)")
    p("║  \u274c Pipeline: no entries in pipeline_runs.jsonl")
    criticals.append("No pipeline runs — cron never set up or pipeline always crashes on startup")

# 6. PIPELINE DECISION RATE ---------------------------------------------------
recent = pipeline_entries[-20:] if len(pipeline_entries) >= 20 else pipeline_entries
actionable = [e for e in recent if e.get("decision") in ("BUY", "SELL", "STRONG_BUY", "STRONG_SELL")]
total_recent = len(recent)
action_count = len(actionable)
action_pct = int(action_count / total_recent * 100) if total_recent else 0
if action_count == 0 and total_recent > 0:
    warns.append("Pipeline action rate: 0%% (%d/%d runs)" % (action_count, total_recent))
    p("║  \u26a0\ufe0f  Action rate: %d/%d runs = 0%% (risk manager blocking all?)" % (action_count, total_recent))
    criticals.append("0%% action rate — risk_manager.py may be blocking all signals, check confidence thresholds")
elif total_recent == 0:
    p("║  \u26a0\ufe0f  Action rate: no pipeline runs to assess")
else:
    passes.append("Pipeline action rate (%d%%)" % action_pct)
    p("║  \u2705 Action rate: %d/%d runs = %d%% actionable" % (action_count, total_recent, action_pct))

# 7. MODEL ROUTING STRINGS ----------------------------------------------------
minimax_found = []
for fpath, label in [(CONFIG_FILE, "limitless_config.py"), (ENV_FILE, ".env")]:
    try:
        content = open(fpath).read()
        if "minimax01" in content:
            minimax_found.append(label)
    except Exception:
        pass

# Find current PM model in polymarket_paper_bet.py
pm_model = "unknown"
try:
    pb_content = open(PM_BET_FILE).read()
    m = re.search(r'"(minimax/[^"]+)"', pb_content)
    if m:
        pm_model = m.group(1)
    else:
        m2 = re.search(r'for model in \[([^\]]+)\]', pb_content)
        if m2:
            first_model = re.search(r'"([^"]+)"', m2.group(1))
            if first_model:
                pm_model = first_model.group(1)
except Exception:
    pass

if minimax_found:
    fails.append("Model routing: 'minimax01' found in " + ", ".join(minimax_found))
    p("║  \u274c Model routing: 'minimax01' found in %s" % ", ".join(minimax_found))
    criticals.append("Old 'minimax01' model string in " + ", ".join(minimax_found) + " — replace with current model ID")
else:
    passes.append("Model routing (no minimax01)")
    p("║  \u2705 Model routing: clean (PM using: %s)" % pm_model[:35])


# ══════════════════════════════════════════════════════════════════════════════
# POLYMARKET
# ══════════════════════════════════════════════════════════════════════════════
p("")
p("║ POLYMARKET")

positions = []
if POSITIONS_FILE.exists():
    try:
        with open(POSITIONS_FILE) as f:
            positions = json.load(f)
    except Exception:
        pass

# 8. PAPER BET LAST RUN -------------------------------------------------------
today_utc = now_utc().strftime("%Y-%m-%d")
if positions:
    opened_dates = []
    for pos in positions:
        oa = pos.get("opened_at", "")
        if oa:
            opened_dates.append(oa[:10])
    if opened_dates:
        latest_date = max(opened_dates)
        count_today = sum(1 for d in opened_dates if d == today_utc)
        if latest_date == today_utc:
            passes.append("Paper bets ran today")
            p("║  \u2705 Paper bets: ran today (%d new positions)" % count_today)
        else:
            # compute hours ago from most recent opened_at
            try:
                most_recent_oa = max(
                    (pos.get("opened_at","") for pos in positions if pos.get("opened_at","")),
                    default=""
                )
                last_bet_dt = datetime.fromisoformat(most_recent_oa.replace("Z", "+00:00"))
                if last_bet_dt.tzinfo is None:
                    last_bet_dt = last_bet_dt.replace(tzinfo=timezone.utc)
                hours_ago = (now_utc() - last_bet_dt).total_seconds() / 3600
                if hours_ago <= 24:
                    warns.append("Paper bets (yesterday, %.0fh ago)" % hours_ago)
                    p("║  \u26a0\ufe0f  Paper bets: last run %s (%.0fh ago — yesterday)" % (latest_date, hours_ago))
                elif hours_ago <= 48:
                    warns.append("Paper bets (%.0fh ago)" % hours_ago)
                    p("║  \u26a0\ufe0f  Paper bets: last run %.0fh ago" % hours_ago)
                else:
                    fails.append("Paper bets (%.0fh ago)" % hours_ago)
                    p("║  \u274c Paper bets: no run in %.0fh — cron dead?" % hours_ago)
                    criticals.append("Paper bets stale (%.0fh ago) — check polymarket cron: crontab -l" % hours_ago)
            except Exception:
                warns.append("Paper bets (date parse error)")
                p("║  \u26a0\ufe0f  Paper bets: last date was %s" % latest_date)
    else:
        fails.append("Paper bets (no dated positions)")
        p("║  \u274c Paper bets: no dated positions found")
else:
    fails.append("Paper bets (no positions file)")
    p("║  \u274c Paper bets: polymarket_positions.json missing")
    criticals.append("polymarket_positions.json missing — run: python3 polymarket_paper_bet.py")

# 9. MIROFISH INTEGRATION IN PAPER BETS ---------------------------------------
recent_pos = positions[-10:] if len(positions) >= 10 else positions
mf_count = sum(1 for pos in recent_pos if pos.get("mirofish_yes_probability") is not None)
total_checked = len(recent_pos)
if mf_count == 0:
    fails.append("MiroFish integration: 0/%d bets have mirofish_yes_probability" % total_checked)
    p("║  \u274c MiroFish integration: 0/%d recent bets have mirofish data" % total_checked)
    criticals.append("MiroFish data not saved to paper bets — polymarket_paper_bet.py run_assess() calls get_mirofish_data() but never stores mirofish_yes_probability in the position dict. Add it.")
elif mf_count < 5:
    warns.append("MiroFish integration: only %d/%d bets" % (mf_count, total_checked))
    p("║  \u26a0\ufe0f  MiroFish integration: only %d/%d recent bets" % (mf_count, total_checked))
else:
    passes.append("MiroFish integration (%d/%d)" % (mf_count, total_checked))
    p("║  \u2705 MiroFish integrated in %d/%d recent bets" % (mf_count, total_checked))

# 10. PAPER BET ACCURACY -------------------------------------------------------
if PERF_FILE.exists():
    try:
        with open(PERF_FILE) as f:
            perf = json.load(f)
        resolved_ct = perf.get("resolved", 0)
        win_rate    = perf.get("win_rate", 0)
        ready       = perf.get("ready_for_real_money", False)
        passes.append("Paper accuracy tracking (%d resolved)" % resolved_ct)
        if resolved_ct >= 5:
            p("║  \U0001f4ca Accuracy: %d resolved | win rate %.0f%% | ready=%s" % (
                resolved_ct, win_rate * 100, "YES" if ready else "NO (need 30 at 55%+)"))
        else:
            p("║  \U0001f4ca Accuracy: %d resolved — need 30 at 55%%+ for live money" % resolved_ct)
    except Exception:
        p("║  \U0001f4ca Accuracy: could not read performance file")
else:
    resolved_local = sum(1 for pos in positions if pos.get("status") == "resolved") if positions else 0
    passes.append("Paper accuracy tracking (%d resolved)" % resolved_local)
    p("║  \U0001f4ca Accuracy: %d resolved bets — need 30 at 55%%+ for live money" % resolved_local)


# ══════════════════════════════════════════════════════════════════════════════
# BACKTESTS
# ══════════════════════════════════════════════════════════════════════════════
p("")
p("║ BACKTESTS")

if BACKTEST_FILE.exists():
    try:
        with open(BACKTEST_FILE) as f:
            bt = json.load(f)
        total_bt    = bt.get("total_backtests", 0)
        win_rate_bt = bt.get("win_rate", 0)
        expectancy  = bt.get("expectancy_per_trade", 0)
        ready_bt    = bt.get("ready_for_saas", False)
        if total_bt >= 250:
            passes.append("Backtests (%d runs, %.0f%% win rate)" % (total_bt, win_rate_bt * 100))
            p("║  \u2705 Backtest: %d runs | win rate %.0f%% | E=%.2f/trade" % (
                total_bt, win_rate_bt * 100, expectancy))
            p("║     Ready for SaaS: %s" % ("YES \u2705" if ready_bt else "NO — below threshold"))
        else:
            warns.append("Backtests: only %d/250 runs" % total_bt)
            p("║  \u26a0\ufe0f  Backtest: only %d/250 runs | win rate %.0f%% | E=%.2f" % (
                total_bt, win_rate_bt * 100, expectancy))
            p("║     ready_for_saas=%s flagged but ONLY %d runs — NOT statistically valid" % (
                "YES" if ready_bt else "NO", total_bt))
            criticals.append("Only %d/250 backtests complete — run full suite before any SaaS claims" % total_bt)
    except Exception:
        fails.append("Backtests (parse error)")
        p("║  \u274c Backtest: could not parse backtest_summary.json")
else:
    fails.append("Backtests (not run)")
    p("║  \u274c Backtest: not run — HIGHEST PRIORITY")
    criticals.insert(0, "250 backtests NOT run — run python3 run_backtest.py before any live or SaaS deployment")


# ══════════════════════════════════════════════════════════════════════════════
# RENDER OUTPUT
# ══════════════════════════════════════════════════════════════════════════════
WIDTH = 54   # inner width (between the two ║ borders)
ts_display = now_utc().strftime("%Y-%m-%d %H:%M UTC")

def render_line(raw):
    """Take a raw line (starting with ║) and pad/truncate to WIDTH."""
    if raw.startswith("╠") or raw.startswith("╚") or raw.startswith("╔"):
        return raw  # already formatted
    inner = raw[1:] if raw.startswith("║") else raw
    if len(inner) > WIDTH:
        inner = inner[:WIDTH - 1] + "…"
    return "║" + inner.ljust(WIDTH) + "║"

print("╔" + "═" * WIDTH + "╗")
print("║" + "  LIMITLESS AI — SYSTEM HEALTH".center(WIDTH) + "║")
print("║" + ("  " + ts_display).center(WIDTH) + "║")
print("╠" + "═" * WIDTH + "╣")

current_section = None
for raw in lines:
    stripped = raw.strip()
    if not stripped:
        continue
    if stripped == "║ INFRASTRUCTURE" or stripped == "║ PIPELINE" or stripped == "║ POLYMARKET" or stripped == "║ BACKTESTS":
        if current_section is not None:
            print("╠" + "═" * WIDTH + "╣")
        current_section = stripped
        # Print section header
        section_name = stripped[2:]  # remove "║ "
        print("║" + (" " + section_name).ljust(WIDTH) + "║")
    else:
        print(render_line(raw))

# ── Summary ──────────────────────────────────────────────────────────────────
print("╠" + "═" * WIDTH + "╣")
summary = "  SUMMARY: %d PASS  %d WARN  %d FAIL" % (len(passes), len(warns), len(fails))
print("║" + summary.ljust(WIDTH) + "║")

if criticals:
    print("║" + "  CRITICAL FIXES (priority order):".ljust(WIDTH) + "║")
    for i, c in enumerate(criticals, 1):
        prefix = "  %d. " % i
        cont   = "     "   # continuation indent
        words  = c.split()
        cur    = prefix
        for word in words:
            candidate = cur + word
            if len(candidate) > WIDTH and cur.strip():
                print("║" + cur.rstrip().ljust(WIDTH) + "║")
                cur = cont + word + " "
            else:
                cur = candidate + " "
        if cur.strip():
            print("║" + cur.rstrip().ljust(WIDTH) + "║")

print("╚" + "═" * WIDTH + "╝")

sys.exit(1 if fails else 0)
