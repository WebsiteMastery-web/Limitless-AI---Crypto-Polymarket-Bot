#!/usr/bin/env python3
import os, sys, json, time, glob, logging, re, argparse, requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv(Path("/root/limitless-ai/TradingAgents/.env"))

GAMMA_API_URL  = "https://gamma-api.polymarket.com/markets"
LOG_DIR        = Path("/root/limitless-ai/logs")
POSITIONS_FILE = LOG_DIR / "polymarket_positions.json"
PAPER_LOG_FILE = LOG_DIR / "polymarket_paper_log.txt"
PERF_FILE      = LOG_DIR / "polymarket_paper_performance.json"
MIROFISH_DIR   = LOG_DIR / "mirofish"
LOG_DIR.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY", "")
MIN_EDGE_THRESHOLD   = 0.08
TARGET_MAX_POSITIONS = 50
BATCH_SIZE           = 5
BATCH_DELAY          = 1.5
MAX_FETCH            = 500

SPORT_TERMS = [
    "win on", " vs.", " vs ", " fc ", "nba", "nfl", "mlb", "nhl", "fifa",
    "tennis", "golf", "cricket", "soccer", "basketball", "baseball", "hockey",
    "football", "grand prix", "super bowl", "championship", "playoff",
    "league", "tournament", "match", "score", " game ", "coach", "roster",
    "draft", " cup ", "world series", "formula 1", "f1 ", "ufc", "mma",
    "boxing", "wrestling", "olympics", "athlete", "player contract",
    "spread:", "point spread", "over/under", "moneyline", "handicap",
    "innings", "quarters", "halftime", "overtime", "season record",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "polymarket_paper_bet.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_positions():
    if not POSITIONS_FILE.exists():
        return []
    try:
        with open(POSITIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_positions(positions):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2, default=str)


def get_all_market_ids():
    return {p["market_id"] for p in load_positions() if p.get("market_id")}


def get_btc_price():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=10,
        )
        return float(r.json()["bitcoin"]["usd"])
    except Exception:
        return 0.0


def is_sports_market(q):
    return any(t in q.lower() for t in SPORT_TERMS)


def fetch_markets(max_total=500, min_volume=1000):
    results, limit, offset = [], 50, 0
    while offset < max_total:
        try:
            r = requests.get(GAMMA_API_URL, params={
                "active": "true", "closed": "false", "limit": limit,
                "offset": offset, "order": "volume24hr", "ascending": "false",
            }, timeout=20)
            if r.status_code != 200:
                logger.warning("Gamma API %s at offset %s", r.status_code, offset)
                break
            page = r.json()
            if not page:
                break
            for m in page:
                q = (m.get("question") or m.get("title") or "").strip()
                if not q or is_sports_market(q):
                    continue
                vol = float(m.get("volume24hr") or m.get("volume") or 0)
                if vol < min_volume:
                    continue
                yp = None
                op = m.get("outcomePrices")
                if op:
                    try:
                        prices = json.loads(op) if isinstance(op, str) else op
                        yp = float(prices[0])
                    except Exception:
                        pass
                if yp is None:
                    for tok in m.get("tokens", []):
                        if tok.get("outcome", "").upper() == "YES":
                            yp = float(tok.get("price", 0))
                            break
                if yp is None or not (0.01 <= yp <= 0.99):
                    continue
                slug = m.get("slug") or m.get("market_slug") or ""
                results.append({
                    "market_id": str(m.get("id") or m.get("condition_id") or ""),
                    "question": q, "slug": slug,
                    "yes_price": round(yp, 4), "volume": vol,
                    "end_date": m.get("endDate") or "",
                })
            if len(page) < limit:
                break
            offset += limit
            time.sleep(0.3)
        except Exception as e:
            logger.error("fetch_markets offset=%s: %s", offset, e)
            break
    logger.info("Fetched %s eligible markets", len(results))
    return results


def get_mirofish_data(market_id):
    """Find MiroFish assessment for a given market_id.

    Files are named by timestamp (polymarket_mirofish_YYYYMMDD_HHMMSS.json),
    NOT by market_id. The market_id lives inside data['results'][N]['market_id']
    as a string. We scan all recent files and search through their results arrays.
    Both market_id values are normalized to strings before comparison.
    """
    if not MIROFISH_DIR.exists():
        logger.debug(f"MiroFish: directory {MIROFISH_DIR} not found for market {market_id}")
        return None

    all_files = sorted(
        glob.glob(str(MIROFISH_DIR / "polymarket_mirofish_*.json")),
        key=os.path.getmtime,
        reverse=True
    )

    if not all_files:
        logger.debug(f"MiroFish: no polymarket_mirofish_*.json files found for market {market_id}")
        return None

    max_age_seconds = 24 * 3600  # 24 hours
    target_id = str(market_id)  # normalize to string for comparison

    for fpath in all_files:
        file_age = time.time() - os.path.getmtime(fpath)
        if file_age > max_age_seconds:
            # Files sorted newest-first; all remaining are also too old
            logger.debug(f"MiroFish: market {market_id} not found in files <24h old")
            break
        try:
            with open(fpath) as f:
                data = json.load(f)
            results = data.get("results", [])
            for r in results:
                if str(r.get("market_id", "")) == target_id:
                    logger.debug(f"MiroFish: found market {market_id} in {os.path.basename(fpath)}")
                    return r
        except Exception as e:
            logger.warning(f"MiroFish: error reading {os.path.basename(fpath)}: {e}")
            continue

    logger.debug(f"MiroFish: market_id {market_id} not found in any recent files ({len(all_files)} checked)")
    return None


def _llm_call(system, user, timeout=60):
    if not ANTHROPIC_API_KEY:
        logger.warning("No ANTHROPIC_API_KEY")
        return None
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=350,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning("LLM anthropic: %s", e)
    return None


def parse_batch_response(raw, n):
    results = [None] * n
    if not raw:
        return results
    for line in raw.splitlines():
        m = re.match(r"M(\d+):\s*(.+)", line.strip(), re.IGNORECASE)
        if not m:
            continue
        idx = int(m.group(1)) - 1
        if not (0 <= idx < n):
            continue
        parts = [p.strip() for p in m.group(2).split("|")]
        d  = parts[0].upper() if parts else ""
        c  = parts[1].upper() if len(parts) > 1 else ""
        r2 = parts[2].strip() if len(parts) > 2 else ""
        if d not in ("YES_FAVORED", "NO_FAVORED", "NOT_RELEVANT"):
            d = "YES_FAVORED" if "YES" in d else ("NO_FAVORED" if "NO" in d else "NOT_RELEVANT")
        if c not in ("LOW", "MEDIUM", "HIGH"):
            c = "HIGH" if "HIGH" in c else ("MEDIUM" if "MED" in c else "LOW")
        results[idx] = {"direction": d, "confidence": c, "key_reason": r2[:120]}
    return results


def assess_batch(batch, btc_price, regime, today):
    sys_p = ("You are a prediction market analyst. Assess each market question against "
             "current context. Determine if YES or NO is more likely vs the current price. "
             "Respond ONLY in the exact format shown - nothing else.")
    mlines, mnotes = [], []
    for i, mkt in enumerate(batch, 1):
        mlines.append("MARKET %d: '%s' (YES price: %.0f%%)" % (i, mkt["question"], mkt["yes_price"] * 100))
        mf = get_mirofish_data(mkt["market_id"])
        if mf:
            yp2 = mf.get("yes_probability") or mf.get("mirofish_yes_probability", 0)
            mnotes.append(
                "Note for Market %d: MiroFish simulation (100 agents, Mistral 7B) "
                "assessed %.0f%% YES probability from retail crowd." % (i, yp2 * 100)
            )
    mf_txt = ("\n" + "\n".join(mnotes)) if mnotes else ""
    fmt = "\n".join("M%d: DIRECTION | CONFIDENCE | REASON" % i for i in range(1, len(batch) + 1))
    up = (
        "Assess these %d prediction market questions against current context.\n\n"
        "Current context:\n- BTC price: %s USD\n- Regime: %s\n- Date: %s\n"
        "%s\n\n%s\n\n"
        "For each market, respond with DIRECTION (YES_FAVORED/NO_FAVORED/NOT_RELEVANT), "
        "CONFIDENCE (LOW/MEDIUM/HIGH), and KEY_REASON (max 10 words).\n\n"
        "Respond in this format:\n%s"
    ) % (len(batch), "{:,.0f}".format(btc_price), regime, today, mf_txt, "\n".join(mlines), fmt)
    raw = _llm_call(sys_p, up)
    logger.debug("Batch raw: %s", raw)
    return parse_batch_response(raw, len(batch))


def calculate_edge(yes_price, direction, confidence):
    bump = 0.12 if confidence == "HIGH" else 0.08
    if direction == "YES_FAVORED":
        sy = round(min(yes_price + bump, 0.99), 4)
        return (sy, round(sy - yes_price, 4), "YES")
    elif direction == "NO_FAVORED":
        sy = round(max(yes_price - bump, 0.01), 4)
        return (sy, round(yes_price - sy, 4), "NO")
    return (yes_price, 0.0, "NONE")


def run_assess():
    logger.info("=== Polymarket Paper Bet - ASSESS MODE ===")
    today     = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    btc_price = get_btc_price()
    regime    = "NEUTRAL"
    logger.info("BTC: $%s | Date: %s", "{:,.0f}".format(btc_price), today)

    all_markets = fetch_markets(max_total=MAX_FETCH, min_volume=1000)
    ft          = len(all_markets)
    tracked     = get_all_market_ids()
    markets     = [m for m in all_markets if m["market_id"] not in tracked]
    logger.info("New markets: %d (skipped %d tracked)", len(markets), ft - len(markets))

    if not markets:
        logger.info("No new markets.")
        _append_log(ft, 0, len(load_positions()), 0)
        return

    batches   = [markets[i:i + BATCH_SIZE] for i in range(0, len(markets), BATCH_SIZE)]
    positions = load_positions()
    new_pos   = []
    llm_calls = 0
    logger.info("Processing %d batches", len(batches))

    for bi, batch in enumerate(batches):
        if len(new_pos) >= TARGET_MAX_POSITIONS:
            logger.info("Reached target %d.", TARGET_MAX_POSITIONS)
            break
        logger.info("Batch %d/%d", bi + 1, len(batches))
        assessments = assess_batch(batch, btc_price, regime, today)
        llm_calls  += 1

        for mkt, asmt in zip(batch, assessments):
            if not asmt:
                continue
            d, c, kr = asmt["direction"], asmt["confidence"], asmt["key_reason"]
            if d == "NOT_RELEVANT":
                continue
            if c == "LOW":
                logger.info("  LOW skip: %s", mkt["question"][:55])
                continue
            sy, edge, side = calculate_edge(mkt["yes_price"], d, c)
            if edge < MIN_EDGE_THRESHOLD:
                logger.info("  Edge %.1f%% < threshold: %s", edge * 100, mkt["question"][:55])
                continue
            slug = mkt.get("slug", "")
            p = {
                "id":                      "paper_%d" % int(time.time() * 1000),
                "market_id":               mkt["market_id"],
                "market_question":         mkt["question"],
                "market_slug":             slug,
                "market_url":              ("https://polymarket.com/market/" + slug) if slug else "",
                "side":                    side,
                "direction":               d,
                "system_yes_probability":  sy,
                "yes_price_at_entry":      mkt["yes_price"],
                "edge":                    edge,
                "confidence":              c,
                "key_reason":              kr,
                "btc_price_at_assessment": btc_price,
                "regime_at_assessment":    regime,
                "paper":                   True,
                "order_id":                "PAPER",
                "status":                  "open",
                "opened_at":               datetime.now(timezone.utc).isoformat(),
                "resolved_at":             None,
                "actual_outcome":          None,
                "win":                     None,
            }
            positions.append(p)
            new_pos.append(p)
            logger.info("  +PAPER %s edge=%.1f%% %s - %s", side, edge * 100, c, mkt["question"][:55])

        save_positions(positions)
        if bi < len(batches) - 1 and len(new_pos) < TARGET_MAX_POSITIONS:
            time.sleep(BATCH_DELAY)

    total_open = sum(1 for p in positions if p.get("status") == "open")
    _append_log(ft, len(new_pos), total_open, llm_calls)
    logger.info("Done. Fetched:%d New:%d Open:%d LLM:%d", ft, len(new_pos), total_open, llm_calls)


def _append_log(fetched, new_count, total_open, llm_calls):
    dt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(PAPER_LOG_FILE, "a") as f:
        f.write("[%s] Assessment complete. Fetched: %d. New positions: %d. "
                "Total open: %d. LLM calls: %d (batched 5/call). Cost: ~$0 (Minimax free)\n"
                % (dt, fetched, new_count, total_open, llm_calls))


def run_check_outcomes():
    logger.info("=== Polymarket Paper Bet - CHECK OUTCOMES MODE ===")
    positions  = load_positions()
    open_paper = [p for p in positions if p.get("status") == "open" and p.get("paper")]
    logger.info("Checking %d open paper positions", len(open_paper))
    checked = 0
    for pos in open_paper:
        mid = pos.get("market_id")
        if not mid:
            continue
        try:
            r = requests.get("%s/%s" % (GAMMA_API_URL, mid), timeout=15)
            if r.status_code != 200:
                continue
            mkt = r.json()
            if not mkt.get("closed", False):
                continue
            winner = None
            op = mkt.get("outcomePrices")
            if op:
                try:
                    prices = json.loads(op) if isinstance(op, str) else op
                    winner = "YES" if float(prices[0]) >= 0.99 else "NO"
                except Exception:
                    pass
            if winner is None:
                res = mkt.get("resolution")
                if res:
                    winner = res.upper()
            if winner is None:
                continue
            won = (pos.get("side") == winner)
            pos.update({
                "status":         "resolved",
                "resolved_at":    datetime.now(timezone.utc).isoformat(),
                "actual_outcome": winner,
                "win":            won,
            })
            checked += 1
            logger.info("  %s: %s", "WIN" if won else "LOSS", pos.get("market_question", "")[:60])
        except Exception as e:
            logger.warning("Error %s: %s", mid, e)
        time.sleep(0.5)
    if checked:
        save_positions(positions)
        logger.info("Resolved %d positions", checked)
    _generate_performance_report([p for p in load_positions() if p.get("paper")])


def _generate_performance_report(pp):
    resolved = [p for p in pp if p.get("status") == "resolved"]
    open_p   = [p for p in pp if p.get("status") == "open"]
    wins     = [p for p in resolved if p.get("win") is True]
    losses   = [p for p in resolved if p.get("win") is False]
    wr       = len(wins) / len(resolved) if resolved else 0.0
    aew      = sum(p.get("edge", 0) for p in wins)   / len(wins)   if wins   else 0.0
    ael      = sum(p.get("edge", 0) for p in losses) / len(losses) if losses else 0.0
    hc       = [p for p in resolved if p.get("confidence") == "HIGH"]
    mc       = [p for p in resolved if p.get("confidence") == "MEDIUM"]
    hwr      = sum(1 for p in hc if p.get("win")) / len(hc) if hc else 0.0
    mwr      = sum(1 for p in mc if p.get("win")) / len(mc) if mc else 0.0
    bc, wc   = None, None
    if wins:
        b  = max(wins, key=lambda p: p.get("edge", 0))
        bc = {"question": b.get("market_question", ""), "edge": b.get("edge", 0), "outcome": "WIN"}
    if losses:
        w  = max(losses, key=lambda p: p.get("edge", 0))
        wc = {"question": w.get("market_question", ""), "edge": w.get("edge", 0), "outcome": "LOSS"}
    ready  = len(resolved) >= 30 and wr >= 0.55
    report = {
        "generated_at":               datetime.now(timezone.utc).isoformat(),
        "total_positions":            len(pp),
        "resolved":                   len(resolved),
        "open":                       len(open_p),
        "wins":                       len(wins),
        "losses":                     len(losses),
        "win_rate":                   round(wr, 4),
        "avg_edge_wins":              round(aew, 4),
        "avg_edge_losses":            round(ael, 4),
        "high_confidence_win_rate":   round(hwr, 4),
        "medium_confidence_win_rate": round(mwr, 4),
        "best_call":                  bc,
        "worst_call":                 wc,
        "ready_for_real_money":       ready,
    }
    with open(PERF_FILE, "w") as f:
        json.dump(report, f, indent=2)
    print("\nPOLYMARKET PAPER PERFORMANCE")
    print("Total: %d | Resolved: %d | Open: %d" % (len(pp), len(resolved), len(open_p)))
    print("Win rate: %.1f%% (need 55%%+ over 30+ resolved for real USDC)" % (wr * 100))
    print("High confidence: %.1f%% | Medium: %.1f%%" % (hwr * 100, mwr * 100))
    print("Ready for real money: %s" % ("YES" if ready else "NO"))
    logger.info("Perf report saved to %s", PERF_FILE)


CRON_LINES = [
    "# Polymarket paper betting - 06:00 UTC daily",
    "0 6 * * * cd /root/limitless-ai && source TradingAgents/venv/bin/activate && python3 polymarket_paper_bet.py >> logs/polymarket_paper_log.txt 2>&1",
    "# Check outcomes - 07:00 UTC daily",
    "0 7 * * * cd /root/limitless-ai && source TradingAgents/venv/bin/activate && python3 polymarket_paper_bet.py --check-outcomes >> logs/polymarket_paper_log.txt 2>&1",
]


def setup_cron():
    import subprocess
    res      = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = res.stdout if res.returncode == 0 else ""
    to_add   = [l for l in CRON_LINES if l not in existing]
    if not to_add:
        print("Cron jobs already installed.")
        return
    nc = existing.rstrip("\n") + "\n" + "\n".join(to_add) + "\n"
    p2 = subprocess.run(["crontab", "-"], input=nc, text=True)
    if p2.returncode == 0:
        print("Added %d cron job(s)." % len([l for l in to_add if not l.startswith("#")]))
    else:
        print("Failed to write crontab.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Polymarket Paper Betting Engine — Limitless AI")
    parser.add_argument("--check-outcomes", action="store_true",
                        help="Resolve closed markets and print performance report")
    parser.add_argument("--setup-cron",    action="store_true",
                        help="Install cron jobs for automated runs")
    args = parser.parse_args()
    if args.setup_cron:
        setup_cron()
    elif args.check_outcomes:
        run_check_outcomes()
    else:
        run_assess()
