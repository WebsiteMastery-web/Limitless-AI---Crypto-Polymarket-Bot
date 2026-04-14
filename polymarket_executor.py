import os, sys, json, time, logging, re, requests, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dotenv import load_dotenv
import anthropic

load_dotenv(Path("/root/limitless-ai/TradingAgents/.env"))

# ── Config ───────────────────────────────────────────────────────────────────
GAMMA_API_URL    = "https://gamma-api.polymarket.com/markets"
CLOB_API_URL     = "https://clob.polymarket.com"
POSITIONS_FILE   = Path("/root/limitless-ai/logs/polymarket_positions.json")
HEADLINE_FILE    = Path("/root/limitless-ai/logs/latest_headline.json")
LOG_DIR          = Path("/root/limitless-ai/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

POLYMARKET_PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY", "")
TELEGRAM_TOKEN         = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID       = os.getenv("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY      = os.getenv("ANTHROPIC_API_KEY", "")

MIN_EDGE_THRESHOLD  = 0.08
MAX_STAKE_PCT       = 0.10
DEFAULT_BANKROLL    = 100.0
MAX_OPEN_POSITIONS  = 5
MIN_CONFIDENCE      = 0.60
MIN_LAYERS          = 2

# ── Sport filter — any match → skip ──────────────────────────────────────────
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
        logging.FileHandler(LOG_DIR / "polymarket_executor.log"),
    ],
)
logger = logging.getLogger(__name__)


# ── Utilities ─────────────────────────────────────────────────────────────────

def tg_send(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")


def load_positions() -> List[Dict]:
    if not POSITIONS_FILE.exists():
        return []
    try:
        with open(POSITIONS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def save_positions(positions: List[Dict]):
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f, indent=2, default=str)


def get_open_position_count() -> int:
    return sum(1 for p in load_positions() if p.get("status") == "open")


def get_open_market_ids() -> set:
    return {p["market_id"] for p in load_positions() if p.get("status") == "open"}


def get_btc_price() -> float:
    """Fetch current BTC price from CoinGecko."""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=10,
        )
        return float(r.json()["bitcoin"]["usd"])
    except Exception:
        pass
    # Fallback: parse latest_headline.json
    try:
        data = json.loads(HEADLINE_FILE.read_text())
        m = re.search(r"\$([0-9,]+)", data.get("headline", ""))
        if m:
            return float(m.group(1).replace(",", ""))
    except Exception:
        pass
    return 0.0


def get_geopolitical_summary() -> str:
    """
    Fetch top world/politics headlines from Google News RSS (no API key).
    Falls back to latest_headline.json if RSS unavailable.
    Returns up to 300 chars of headline context.
    """
    try:
        r = requests.get(
            "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZxYUdjU0FtVnVHZ0pWVXlnQVAB",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            titles = []
            for item in root.findall(".//item")[:8]:
                title = item.findtext("title") or ""
                if title:
                    titles.append(title.split(" - ")[0].strip())
            if titles:
                summary = "; ".join(titles)
                logger.info(f"News context fetched: {summary[:100]}")
                return summary[:600]
    except Exception as e:
        logger.debug(f"News RSS fetch failed: {e}")

    # Fallback
    try:
        data = json.loads(HEADLINE_FILE.read_text())
        return data.get("headline", "")
    except Exception:
        return ""


def get_position_summary() -> Dict:
    positions = load_positions()
    if not positions:
        return {
            "total_positions": 0, "open_positions": 0, "resolved_positions": 0,
            "total_staked": 0.0, "total_pnl": 0.0, "win_rate": 0.0,
        }
    open_pos  = [p for p in positions if p.get("status") == "open"]
    resolved  = [p for p in positions if p.get("status") == "resolved"]
    total_pnl = sum(p.get("pnl_usdc", 0) for p in resolved if p.get("pnl_usdc") is not None)
    wins      = sum(1 for p in resolved if p.get("win") is True)
    return {
        "total_positions":    len(positions),
        "open_positions":     len(open_pos),
        "resolved_positions": len(resolved),
        "total_staked":       round(sum(p.get("stake_usdc", 0) for p in positions), 2),
        "total_pnl":          round(total_pnl, 2),
        "win_rate":           round(wins / len(resolved), 4) if resolved else 0.0,
    }


# ── Market scanning ───────────────────────────────────────────────────────────

def is_sports_market(question: str) -> bool:
    q = question.lower()
    return any(term in q for term in SPORT_TERMS)


def scan_markets(min_volume: float = 5000, limit: int = 100) -> List[Dict]:
    """
    Fetch active Polymarket markets ordered by 24h volume.
    Apply sport filter and volume floor.
    """
    try:
        params = {
            "active":    "true",
            "closed":    "false",
            "limit":     limit,
            "order":     "volume24hr",
            "ascending": "false",
        }
        r = requests.get(GAMMA_API_URL, params=params, timeout=20)
        if r.status_code != 200:
            logger.warning(f"Gamma API {r.status_code}")
            return []

        results = []
        for m in r.json():
            question = (m.get("question") or m.get("title") or "").strip()
            if not question:
                continue

            if is_sports_market(question):
                continue

            volume = float(m.get("volume24hr") or m.get("volume") or 0)
            if volume < min_volume:
                continue

            # Extract YES price
            yes_price = None
            outcome_prices = m.get("outcomePrices")
            if outcome_prices:
                try:
                    prices = json.loads(outcome_prices) if isinstance(outcome_prices, str) else outcome_prices
                    yes_price = float(prices[0])
                except Exception:
                    pass

            if yes_price is None:
                for tok in m.get("tokens", []):
                    if tok.get("outcome", "").upper() == "YES":
                        yes_price = float(tok.get("price", 0))
                        break

            if yes_price is None or not (0.01 <= yes_price <= 0.99):
                continue

            slug = m.get("slug") or m.get("market_slug") or ""
            results.append({
                "market_id":      str(m.get("id") or m.get("condition_id") or ""),
                "question":       question,
                "slug":           slug,
                "yes_price":      round(yes_price, 4),
                "volume":         volume,
                "end_date":       m.get("endDate") or m.get("end_date_iso") or "",
                "clob_token_ids": m.get("clobTokenIds") or [],
            })

        logger.info(f"Scanned {len(results)} eligible markets (vol>={min_volume}, no sports)")
        return results

    except Exception as e:
        logger.error(f"scan_markets failed: {e}")
        return []


# ── LLM classification ────────────────────────────────────────────────────────

def _llm_call(model: str, system: str, user: str, timeout: int = 25) -> Optional[str]:
    if not ANTHROPIC_API_KEY:
        logger.warning("No ANTHROPIC_API_KEY set")
        return None
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        model_name = model.split("/")[-1] if "/" in model else model
        response = client.messages.create(
            model=model_name,
            max_tokens=120,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"LLM call error ({model}): {e}")
    return None


def _parse_assessment(raw: str) -> Optional[Dict]:
    direction  = None
    confidence = None
    key_reason = ""
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("DIRECTION:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("YES_FAVORED", "NO_FAVORED", "NOT_RELEVANT"):
                direction = val
        elif line.startswith("CONFIDENCE:"):
            val = line.split(":", 1)[1].strip().upper()
            if val in ("LOW", "MEDIUM", "HIGH"):
                confidence = val
        elif line.startswith("KEY_REASON:"):
            key_reason = line.split(":", 1)[1].strip()
    if direction and confidence:
        return {"direction": direction, "confidence": confidence, "key_reason": key_reason}
    return None


def assess_market(
    market: Dict,
    btc_price: float,
    regime: str,
    geo_summary: str = "",
    edgar_summary: str = "",
) -> Optional[Dict]:
    """
    One LLM call per market using classification (not probability estimation).
    Returns {"direction", "confidence", "key_reason"} or None.
    """
    today     = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yes_price = market["yes_price"]
    question  = market["question"]

    system_prompt = (
        "You classify news events against prediction market questions. "
        "You determine if current context makes YES or NO more likely. "
        "You are NOT estimating precise probabilities — you are classifying direction. "
        "Respond ONLY in the exact format specified. Nothing else."
    )

    geo_ctx   = geo_summary[:300] if geo_summary else "No recent geopolitical data."
    edgar_ctx = edgar_summary[:200] if edgar_summary else "No congressional data."

    user_prompt = (
        f"Current context:\n"
        f"- BTC price: {btc_price:.0f} USD\n"
        f"- Market regime: {regime}\n"
        f"- Date: {today}\n"
        f"- Recent geopolitical context: {geo_ctx}\n"
        f"- Congressional activity: {edgar_ctx}\n\n"
        f"Market question: '{question}'\n"
        f"Current market YES price: {yes_price:.2f} ({yes_price*100:.0f}% implied probability)\n\n"
        f"Does current context suggest this market is MORE LIKELY to resolve YES or NO "
        f"compared to the current market price? Or is context NOT RELEVANT?\n\n"
        f"DIRECTION: [YES_FAVORED/NO_FAVORED/NOT_RELEVANT]\n"
        f"CONFIDENCE: [LOW/MEDIUM/HIGH]\n"
        f"KEY_REASON: [one sentence]"
    )

    for model in ["claude-haiku-4-5-20251001"]:
        raw = _llm_call(model, system_prompt, user_prompt)
        if raw:
            parsed = _parse_assessment(raw)
            if parsed:
                logger.info(
                    f"  [{parsed['direction']} / {parsed['confidence']}] "
                    f"{question[:55]}"
                )
                return parsed
        time.sleep(0.5)

    logger.warning(f"Assessment failed for: {question[:60]}")
    return None


# ── Edge calculation ──────────────────────────────────────────────────────────

def calculate_edge(yes_price: float, direction: str, confidence: str) -> Tuple[float, float, str]:
    """Returns (system_yes_probability, edge, side)."""
    bump = 0.12 if confidence == "HIGH" else 0.08

    if direction == "YES_FAVORED":
        system_yes = min(yes_price + bump, 0.99)
        side = "YES"
    elif direction == "NO_FAVORED":
        system_yes = max(yes_price - bump, 0.01)
        side = "NO"
    else:
        return (yes_price, 0.0, "NONE")

    edge = abs(system_yes - yes_price)
    return (round(system_yes, 4), round(edge, 4), side)


# ── Position resolution ───────────────────────────────────────────────────────

def resolve_expired_positions() -> List[Dict]:
    positions = load_positions()
    resolved  = []
    for pos in positions:
        if pos.get("status") != "open":
            continue
        try:
            r = requests.get(f"{GAMMA_API_URL}/{pos.get('market_id')}", timeout=15)
            if r.status_code != 200:
                continue
            market = r.json()
            if not market.get("active", True) and market.get("resolution"):
                resolution = market["resolution"]
                won = pos.get("side") == resolution
                pos.update({
                    "status":         "resolved",
                    "actual_outcome": resolution,
                    "win":            won,
                    "resolved_at":    datetime.now(timezone.utc).isoformat(),
                })
                resolved.append(pos)
                emoji = "✅" if won else "❌"
                tg_send(
                    f"{emoji} *Polymarket Resolved*\n"
                    f"{pos.get('market_question','')[:70]}\n"
                    f"Side: {pos['side']} | Result: {resolution} | Win: {won}"
                )
                logger.info(f"Resolved: {pos['id']} won={won}")
        except Exception as e:
            logger.warning(f"Resolve check error for {pos.get('id')}: {e}")
    if resolved:
        save_positions(positions)
    return resolved


# ── CLOB order (live mode) ────────────────────────────────────────────────────

def place_real_order(
    market_id: str, token_id: str, side: str,
    size_usdc: float, price: float, private_key: str,
) -> Optional[str]:
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.constants import POLYGON
        from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
        from eth_account import Account
        from eth_account.messages import encode_defunct

        acct = Account.from_key(private_key)
        ts   = requests.get(f"{CLOB_API_URL}/time", timeout=10).json().get("time", int(time.time()))
        sig  = acct.sign_message(encode_defunct(text=str(ts))).signature.hex()
        auth = requests.post(
            f"{CLOB_API_URL}/auth/api-key",
            json={"address": acct.address, "signature": sig, "timestamp": ts},
            timeout=15,
        ).json()
        creds  = ApiCreds(
            api_key=auth.get("apiKey", ""), api_secret=auth.get("secret", ""),
            api_passphrase=auth.get("passphrase", ""),
        )
        client = ClobClient(host=CLOB_API_URL, chain_id=POLYGON, key=private_key, creds=creds)
        order  = OrderArgs(token_id=token_id, price=price, size=round(size_usdc / price, 4), side=side)
        resp   = client.post_order(client.create_order(order), OrderType.GTC)
        return str(resp.get("orderID") or resp.get("id") or "UNKNOWN")
    except ImportError:
        logger.warning("py-clob-client not installed")
        return None
    except Exception as e:
        logger.error(f"CLOB order failed: {e}")
        return None


# ── Main entry point ──────────────────────────────────────────────────────────

def execute_polymarket_bets(
    system_decision: str,
    system_confidence: float,
    layers_aligned: int,
    bankroll_usdc: float = 100.0,
    dry_run: bool = True,
    geopolitical_summary: str = "",
    edgar_summary: str = "",
) -> List[Dict]:
    """
    Main entry point called from run_paper_trade.py after pipeline decision.

    Uses classification-based LLM assessment per market.
    BTC confidence/direction is NOT directly mapped to market YES/NO —
    each market is independently assessed against current context.
    """
    logger.info(
        f"Polymarket executor: decision={system_decision} conf={system_confidence:.1%} "
        f"layers={layers_aligned} dry_run={dry_run}"
    )

    if system_decision.upper() == "HOLD":
        logger.info("HOLD signal — skipping Polymarket")
        return []

    if system_confidence < MIN_CONFIDENCE:
        logger.info(f"Confidence {system_confidence:.1%} below minimum {MIN_CONFIDENCE:.1%}")
        return []

    if layers_aligned < MIN_LAYERS:
        logger.info(f"Layers {layers_aligned} below minimum {MIN_LAYERS}")
        return []

    # Resolve expired positions first
    resolved = resolve_expired_positions()
    if resolved:
        logger.info(f"Resolved {len(resolved)} positions")

    open_count = get_open_position_count()
    if open_count >= MAX_OPEN_POSITIONS:
        logger.info(f"Max open positions ({MAX_OPEN_POSITIONS}) reached")
        return []

    # Regime from system decision
    sig    = system_decision.upper()
    regime = "BULL" if sig == "BUY" else ("BEAR" if sig == "SELL" else "SIDEWAYS")

    btc_price = get_btc_price()
    logger.info(f"BTC price: ${btc_price:,.0f} | Regime: {regime}")

    if not geopolitical_summary:
        geopolitical_summary = get_geopolitical_summary()

    markets = scan_markets(min_volume=5000, limit=100)
    if not markets:
        logger.info("No eligible markets found")
        return []

    open_ids         = get_open_market_ids()
    slots_available  = MAX_OPEN_POSITIONS - open_count
    positions_opened = []

    for market in markets:
        if len(positions_opened) >= slots_available:
            break

        if market["market_id"] in open_ids:
            continue

        assessment = assess_market(
            market, btc_price, regime,
            geopolitical_summary, edgar_summary,
        )
        if not assessment:
            continue

        direction  = assessment["direction"]
        confidence = assessment["confidence"]
        key_reason = assessment["key_reason"]

        if direction == "NOT_RELEVANT":
            continue

        if confidence == "LOW":
            logger.info(f"  LOW confidence skip: {market['question'][:55]}")
            continue

        system_yes, edge, side = calculate_edge(market["yes_price"], direction, confidence)

        if edge < MIN_EDGE_THRESHOLD:
            logger.info(f"  Edge {edge:.1%} < threshold: {market['question'][:55]}")
            continue

        # Half-Kelly stake, capped
        stake = round(min(bankroll_usdc * edge * 0.5, bankroll_usdc * MAX_STAKE_PCT), 2)
        stake = max(stake, 5.0)

        token_ids = market.get("clob_token_ids", [])
        token_id  = (
            token_ids[0] if side == "YES"
            else (token_ids[1] if len(token_ids) > 1 else (token_ids[0] if token_ids else ""))
        )

        if dry_run:
            order_id = "DRY_RUN"
        else:
            if not POLYMARKET_PRIVATE_KEY:
                logger.warning("POLYMARKET_PRIVATE_KEY not set")
                order_id = "NO_KEY"
            else:
                price_for_order = market["yes_price"] if side == "YES" else (1 - market["yes_price"])
                order_id = place_real_order(
                    market["market_id"], token_id, "BUY",
                    stake, price_for_order, POLYMARKET_PRIVATE_KEY,
                )
                if order_id is None:
                    continue

        slug    = market.get("slug", "")
        new_pos = {
            "id":                       f"pm_{int(time.time())}",
            "market_id":                market["market_id"],
            "market_question":          market["question"],
            "market_slug":              slug,
            "market_url":               f"https://polymarket.com/market/{slug}" if slug else "",
            "side":                     side,
            "direction_classification": direction,
            "system_yes_probability":   system_yes,
            "market_yes_price":         market["yes_price"],
            "edge":                     edge,
            "confidence":               confidence,
            "key_reason":               key_reason,
            "btc_price_at_assessment":  btc_price,
            "regime_at_assessment":     regime,
            "stake_usdc":               stake,
            "order_id":                 order_id,
            "status":                   "open",
            "opened_at":                datetime.now(timezone.utc).isoformat(),
            "resolved_at":              None,
            "actual_outcome":           None,
            "win":                      None,
        }

        positions = load_positions()
        positions.append(new_pos)
        save_positions(positions)
        positions_opened.append(new_pos)
        open_ids.add(market["market_id"])

        mode = "DRY RUN" if dry_run else "LIVE BET"
        tg_send(
            f"{'🔵' if dry_run else '🟢'} *Polymarket [{mode}]*\n"
            f"{market['question'][:70]}\n"
            f"Side: *{side}* | Edge: *{edge:.1%}* | {confidence}\n"
            f"{key_reason[:100]}\n"
            f"BTC: ${btc_price:,.0f} | Regime: {regime}"
        )
        logger.info(
            f"Opened: {new_pos['id']} {side} edge={edge:.1%} conf={confidence} "
            f"'{market['question'][:50]}'"
        )

        time.sleep(1)  # Rate-limit LLM calls

    logger.info(f"Polymarket cycle complete: {len(positions_opened)} position(s) opened")
    return positions_opened


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Polymarket Executor — Limitless AI")
    parser.add_argument("--scan",            action="store_true", help="Scan markets (no LLM)")
    parser.add_argument("--check-positions", action="store_true", help="Resolve expired positions")
    parser.add_argument("--summary",         action="store_true", help="Print position summary")
    parser.add_argument("--test-bet",        action="store_true", help="Dry-run BUY 70%% 3 layers")
    args = parser.parse_args()

    if args.scan:
        markets = scan_markets(min_volume=5000, limit=100)
        print(f"\nPolymarket Scan | {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"Found {len(markets)} eligible markets:\n")
        for m in markets:
            print(f"  [{m['yes_price']:.0%} YES] {m['question'][:70]}")
            print(f"        Vol: ${m['volume']:,.0f} | Slug: {m['slug']}")

    elif args.check_positions:
        resolved = resolve_expired_positions()
        print(f"Resolved {len(resolved)} positions")
        for r in resolved:
            print(f"  {r['id']} win={r.get('win')} outcome={r.get('actual_outcome')}")

    elif args.summary:
        s = get_position_summary()
        print(f"\nPosition Summary")
        print(f"  Total: {s['total_positions']} | Open: {s['open_positions']} | Resolved: {s['resolved_positions']}")
        print(f"  PnL: ${s['total_pnl']:.2f} | Win rate: {s['win_rate']:.1%}")

    elif args.test_bet:
        result = execute_polymarket_bets("BUY", 0.70, 3, 100.0, dry_run=True)
        print(f"\nDry-run complete. {len(result)} position(s) opened:")
        for r in result:
            print(f"  {r['side']} edge={r['edge']:.1%} {r['confidence']} — {r['market_question'][:60]}")

    else:
        parser.print_help()
