# Limitless AI Trading System — Deployment Status

## Service Ports
- **MiroFish Receiver:** `localhost:9876/health`
- **Pipeline API:** `localhost:8888/api/health`
- **Alpaca API:** Paper trading (configured in .env)

## Cron Schedule
```
# Hourly pipeline
0 * * * * /bin/bash /root/limitless-ai/run_cron.sh

# Weekly KB update — Sunday 02:00 UTC
0 2 * * 0 python3 update_knowledge_base.py --full

# Weekly performance report — Monday 08:00 UTC
0 8 * * 1 python3 performance_tracker.py --full
```

## Knowledge Base
Run: `python3 health_monitor.py`

## Recent Decisions
See `logs/pipeline_runs.jsonl` for trade history.

## Troubleshooting

### Services Not Responding
```bash
systemctl status mirofish
systemctl restart mirofish
```

### Low Disk Space
```bash
df -h
du -sh logs/
```

### Cron Not Running
```bash
crontab -l
```
