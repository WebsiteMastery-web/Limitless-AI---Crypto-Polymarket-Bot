import os, json, uuid
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from tradingagents.execution.telegram_notifier import notify_cron_pending

load_dotenv('/root/limitless-ai/TradingAgents/.env')

TRADE_LOG_DIR = '/root/limitless-ai/logs/trades'
os.makedirs(TRADE_LOG_DIR, exist_ok=True)


def validate_alpaca_symbol(symbol):
    """Convert symbol to Alpaca format (BTC/USD). yfinance uses BTC-USD, Alpaca needs BTC/USD."""
    if "-" in symbol:
        return symbol.replace("-", "/")
    return symbol


def get_trading_client():
    return TradingClient(
        os.getenv('ALPACA_API_KEY'),
        os.getenv('ALPACA_SECRET_KEY'),
        paper=True
    )


def place_paper_trade(symbol, direction, quantity, limit_price, stop_loss_price,
                      reasoning_chain, confidence_score, trigger_layer,
                      mirofish_output=None, trade_id=None, cron_mode=False,
                      trailing_stop_pct=None):
    if os.getenv('PAPER_TRADING', 'True').lower() != 'true':
        raise RuntimeError('PAPER_TRADING is not True. Refusing to execute.')
    if not trade_id:
        trade_id = str(uuid.uuid4())[:8].upper()
    timestamp = datetime.utcnow().isoformat()
    symbol = validate_alpaca_symbol(symbol)
    print('')
    print('=' * 70)
    print('  LIMITLESS AI  |  TRADE #' + trade_id)
    print('=' * 70)
    print('  Asset:         ' + str(symbol))
    print('  Direction:     ' + str(direction))
    print('  Entry Price:   ' + str(limit_price))
    print('  Stop-Loss:     ' + str(stop_loss_price))
    print('  Quantity:      ' + str(quantity))
    print('  Confidence:    ' + str(confidence_score) + '/100')
    print('  Trigger Layer: ' + str(trigger_layer))
    print('')
    print('--- REASONING CHAIN ---')
    print(str(reasoning_chain)[:2000])
    print('=' * 70)
    if cron_mode:
        logger.info('CRON MODE: BUY/SELL signal detected - logging as CRON_PENDING for manual review.')
        _log_trade(trade_id, symbol, direction, limit_price, stop_loss_price,
                   quantity, confidence_score, trigger_layer, mirofish_output, timestamp, 'CRON_PENDING', None,
                   trailing_stop_pct=trailing_stop_pct)
        notify_cron_pending(symbol, direction, limit_price, stop_loss_price,
                            quantity, confidence_score, mirofish_output, trade_id)
        return None
    decision = input('  [C]onfirm / [R]eject: ').strip().upper()
    if decision != 'C':
        _log_trade(trade_id, symbol, direction, limit_price, stop_loss_price,
                   quantity, confidence_score, trigger_layer, reasoning_chain,
                   mirofish_output, timestamp, 'REJECTED', None,
                   trailing_stop_pct=trailing_stop_pct)
        return None
    client = get_trading_client()
    side = OrderSide.BUY if direction.upper() == 'BUY' else OrderSide.SELL
    order_data = LimitOrderRequest(
        symbol=symbol,
        qty=quantity,
        side=side,
        time_in_force=TimeInForce.GTC,
        limit_price=limit_price
    )
    order = client.submit_order(order_data)
    order_id = str(order.id)
    _log_trade(trade_id, symbol, direction, limit_price, stop_loss_price,
               quantity, confidence_score, trigger_layer, reasoning_chain,
               mirofish_output, timestamp, 'OPEN', order_id,
               trailing_stop_pct=trailing_stop_pct)
    logger.info('Trade ' + trade_id + ' executed. Order ID: ' + order_id)
    return order


def _log_trade(trade_id, symbol, direction, entry_price, stop_loss,
               quantity, confidence_score, trigger_layer, reasoning_chain,
               mirofish_output, timestamp, status, order_id,
               trailing_stop_pct=None):
    record = {
        'trade_id': trade_id, 'timestamp': timestamp, 'asset': symbol,
        'direction': direction, 'entry_price': entry_price, 'exit_price': None,
        'stop_loss': stop_loss, 'quantity': quantity, 'outcome_pct': None,
        'confidence_score': confidence_score, 'trigger_layer': trigger_layer,
        'reasoning_chain': str(reasoning_chain), 'mirofish_output': mirofish_output,
        'order_id': order_id, 'status': status,
        'confirmed_by_user': status != 'REJECTED', 'trailing_stop_pct': trailing_stop_pct, 'notes': ''
    }
    log_path = TRADE_LOG_DIR + '/' + trade_id + '_' + symbol.replace('/', '') + '_' + timestamp[:10] + '.json'
    with open(log_path, 'w') as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    logger.info('Trade logged: ' + log_path)


def get_open_orders():
    client = get_trading_client()
    return client.get_orders()
