#!/root/limitless-ai/TradingAgents/venv/bin/python3
"""
Health monitoring system for Limitless AI trading platform.
Runs 8 comprehensive checks and logs results to health_status.json.
"""

import os
import sys
import json
import anthropic
import requests
import time
from datetime import datetime
from pathlib import Path
LOG_DIR = "/root/limitless-ai/logs"
KB_DIR = "/root/limitless-ai/knowledge_base"
STATUS_FILE = os.path.join(LOG_DIR, "health_status.json")


env_file = Path("/root/limitless-ai/TradingAgents/.env")
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value)

def ensure_log_dir():
    """Ensure logs directory exists."""
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)


def check_mirofish_receiver():
    """CHECK 1: MiroFish receiver health."""
    try:
        resp = requests.get("http://localhost:9876/health", timeout=3)
        if resp.status_code == 200:
            return True, "MiroFish receiver responding on port 9876"
        return False, f"MiroFish returned {resp.status_code}"
    except Exception as e:
        return False, f"MiroFish unreachable: {str(e)}"


def check_dashboard():
    """CHECK 2: Dashboard health."""
    try:
        resp = requests.get("http://localhost:8888/api/health", timeout=3)
        if resp.status_code == 200:
            return True, "Dashboard responding on port 8888"
        return False, f"Dashboard returned {resp.status_code}"
    except Exception as e:
        return False, f"Dashboard unreachable: {str(e)}"


def check_alpaca_api():
    """CHECK 3: Alpaca API connectivity."""
    try:
        from alpaca.trading.client import TradingClient
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            return False, "Alpaca API keys not configured"
        client = TradingClient(api_key, secret_key, paper=True)
        client.get_account()
        return True, "Alpaca API credentials valid"
    except ImportError:
        return False, "alpaca-trade-api not installed"
    except Exception as e:
        return False, f"Alpaca API error: {str(e)}"


def check_anthropic_api():
    """CHECK 4: Anthropic API health."""
    try:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return False, "ANTHROPIC_API_KEY not set"

        client = anthropic.Anthropic(api_key=api_key)
        # Quick health check — count models endpoint
        resp = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=5
        )
        if resp.status_code == 200:
            return True, "Anthropic API responding"
        return False, f"Anthropic returned {resp.status_code}"
    except Exception as e:
        return False, f"Anthropic unreachable: {str(e)}"


def check_knowledge_base():
    """CHECK 5: Knowledge base files present and recent."""
    required_files = [
        "macro_context.md",
        "micro_context.md",
        "risk_parameters.md",
        "backtest_results.md",
        "strategy_notes.md"
    ]

    now = time.time()
    max_age_seconds = 8 * 24 * 3600  # 8 days

    missing = []
    stale = []

    for fname in required_files:
        fpath = os.path.join(KB_DIR, fname)
        if not os.path.exists(fpath):
            missing.append(fname)
        else:
            size = os.path.getsize(fpath)
            age_seconds = now - os.path.getmtime(fpath)
            if size < 1024:
                missing.append(f"{fname} (< 1KB)")
            elif age_seconds > max_age_seconds:
                stale.append(f"{fname} ({age_seconds / 86400:.1f} days old)")

    if missing or stale:
        msg = ""
        if missing:
            msg += f"Missing/small: {', '.join(missing)}. "
        if stale:
            msg += f"Stale: {', '.join(stale)}. "
        msg += "Run: python3 update_knowledge_base.py --full"
        return False, msg.strip()

    return True, "All 5 KB files present and recent"


def check_crontab():
    """CHECK 6: Crontab entry for run_cron.sh exists."""
    try:
        result = os.popen("crontab -l 2>/dev/null | grep -c run_cron.sh").read().strip()
        if int(result) > 0:
            return True, "Cron entry for run_cron.sh found"
        return False, "run_cron.sh not in crontab"
    except Exception as e:
        return False, f"Crontab check failed: {str(e)}"


def check_pipeline_log():
    """CHECK 7: Pipeline log exists with recent entries."""
    log_file = "/root/limitless-ai/logs/pipeline_runs.jsonl"
    if not os.path.exists(log_file):
        return False, f"Pipeline log missing: {log_file}"

    try:
        now = time.time()
        max_age = 6 * 3600  # 6 hours

        with open(log_file, 'r') as f:
            last_line = None
            for line in f:
                last_line = line

        if not last_line:
            return False, "Pipeline log exists but is empty"

        entry = json.loads(last_line)
        timestamp = entry.get("timestamp")
        if timestamp:
            entry_time = datetime.fromisoformat(timestamp).timestamp()
            age = now - entry_time
            if age < max_age:
                return True, f"Last pipeline run {age/3600:.1f} hours ago"
            return False, f"Last run {age/3600:.1f} hours ago (> 6h)"
        return False, "No timestamp in last pipeline entry"
    except Exception as e:
        return False, f"Pipeline log parse error: {str(e)}"


def check_disk_space():
    """CHECK 8: Disk space on /root."""
    try:
        result = os.popen("df /root --output=avail -m | tail -1").read().strip()
        free_mb = int(result)
        if free_mb >= 500:
            return True, f"Free disk space: {free_mb}MB"
        return False, f"Low disk: {free_mb}MB (< 500MB threshold)"
    except Exception as e:
        return False, f"Disk check failed: {str(e)}"


def run_health_check():
    """Run all 8 health checks and return results dict."""
    ensure_log_dir()

    checks = [
        ("MiroFish receiver", check_mirofish_receiver),
        ("Dashboard", check_dashboard),
        ("Alpaca API", check_alpaca_api),
        ("OpenRouter API", check_anthropic_api),
        ("Knowledge base", check_knowledge_base),
        ("Crontab", check_crontab),
        ("Pipeline log", check_pipeline_log),
        ("Disk space", check_disk_space),
    ]

    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    print("=" * 60)
    print("HEALTH CHECK REPORT")
    print("=" * 60)

    for name, check_func in checks:
        passed, message = check_func()
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} — {name}: {message}")

        results["checks"][name] = {
            "passed": passed,
            "message": message
        }

    print("=" * 60)

    return results


def write_status_file(results):
    """Write health status to JSON file."""
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"Health status saved to {STATUS_FILE}")
    except Exception as e:
        print(f"Error writing status file: {e}")


def update_status_md():
    """Generate STATUS.md with human-readable quick reference."""
    vps_ip = "167.71.25.250"
    status_md = f"""# Limitless AI Trading System — VPS Status

**Last Updated:** {datetime.utcnow().isoformat()}

## VPS Details
- **IP Address:** {vps_ip}
- **SSH:** `ssh -i ~/.ssh/limitless_key root@{vps_ip}`

## Service Ports
- **MiroFish Receiver:** http://localhost:9876/health
- **Dashboard API:** http://localhost:8888/api/health
- **Alpaca API:** Paper trading (configured in .env)
- **OpenRouter API:** LLM inference

## Cron Schedule
```
# Every 4 hours (ready to switch to hourly when win rate > 55%)
0 */4 * * * /bin/bash /root/limitless-ai/run_cron.sh

# Weekly KB update — Sunday 02:00 UTC
0 2 * * 0 cd /root/limitless-ai && source TradingAgents/venv/bin/activate && python3 update_knowledge_base.py --full

# Weekly performance report — Monday 08:00 UTC
0 8 * * 1 cd /root/limitless-ai && source TradingAgents/venv/bin/activate && python3 performance_tracker.py --full
```

## Switch to Hourly Cron
When backtesting shows win rate > 55%, change the cron entry from:
```
0 */4 * * * /bin/bash /root/limitless-ai/run_cron.sh
```
to:
```
0 * * * * /bin/bash /root/limitless-ai/run_cron.sh
```

Then run: `crontab -e` and save.

## Knowledge Base Status
Run: `python3 /root/limitless-ai/health_monitor.py`

## Recent Pipeline Decisions
See `/root/limitless-ai/pipeline_runs.jsonl` for trade history.

## OpenRouter Spend
Check your Anthropic account at https://console.anthropic.com

## Troubleshooting

### Services Not Responding
```bash
# Check MiroFish
systemctl status mirofish
systemctl restart mirofish

# Check Dashboard
ps aux | grep dashboard_api
pkill -f dashboard_api
cd /root/limitless-ai && nohup python dashboard_api.py > logs/dashboard.log 2>&1 &
```

### Low Disk Space
```bash
df -h /root
du -sh /root/limitless-ai/logs/
```

### Cron Not Running
```bash
crontab -l
grep CRON /var/log/syslog | tail -20
```
"""

    try:
        with open("/root/limitless-ai/STATUS.md", 'w') as f:
            f.write(status_md)
        print(f"STATUS.md updated")
    except Exception as e:
        print(f"Error writing STATUS.md: {e}")


if __name__ == "__main__":
    results = run_health_check()
    write_status_file(results)

    if "--update-status" in sys.argv:
        update_status_md()

    # Exit with failure code if any check failed
    all_passed = all(check["passed"] for check in results["checks"].values())
    sys.exit(0 if all_passed else 1)


