# Limitless AI Trading System — VPS Status

**Last Updated:** 2026-04-02T17:19:47.630798

## VPS Details
- **IP Address:** 167.71.25.250
- **SSH:** `ssh -i ~/.ssh/limitless_key root@167.71.25.250`

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
Check your OpenRouter account at https://openrouter.ai/account/billing

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
