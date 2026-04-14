#!/usr/bin/env python3
"""Script to update run_backtest.py with new functionality"""

import re
import sys

# Read the file
with open("/root/limitless-ai/run_backtest.py", "r") as f:
    content = f.read()

# 1. Replace get_price_4h_later function with get_next_day_price
old_func = r"""def get_price_4h_later\(ticker: str, decision_dt: datetime\) -> Optional\[float\]:
    \"\"\"Fetch price exactly 4 hours after decision time.\"\"\"
    future_dt = decision_dt \+ timedelta\(hours=4\)
    return get_price_at_time\(ticker, future_dt\)"""

new_func = '''def get_next_day_price(ticker: str, decision_date: datetime) -> tuple:
    """
    Fetch next day closing price (D to D+1).
    Returns: (price_next_day: float, price_fetch_date: str) or (None, None)
    """
    try:
        # Get the next calendar day
        next_day = decision_date.date() + timedelta(days=1)
        
        # Fetch daily data for that date
        start = next_day
        end = next_day + timedelta(days=2)
        
        data = yf.download(
            ticker,
            start=start,
            end=end,
            interval="1d",
            progress=False,
            auto_adjust=True
        )
        
        if not data.empty:
            close_col = data['Close']
            if hasattr(close_col, 'iloc'):
                close_val = close_col.iloc[0]
                if hasattr(close_val, 'item'):
                    return float(close_val.item()), next_day.strftime("%Y-%m-%d")
                return float(close_val), next_day.strftime("%Y-%m-%d")
        return None, None
    except Exception as e:
        logger.debug(f"Next day price fetch error for {decision_date}: {e}")
        return None, None'''

content = re.sub(old_func, new_func, content)

# 2. Replace determine_outcome function
old_outcome = r"""def determine_outcome\(
    decision: str, price_at_decision: float, price_4h: float
\) -> tuple:
    \"\"\"
    Determine WIN/LOSS/NEUTRAL/MISSED_BUY/CORRECT_HOLD outcome based on decision and price movement.
    Returns: \(outcome, correct, pct_change\)
    \"\"\"
    if price_at_decision is None or price_4h is None:
        return \(\"PRICE_UNAVAILABLE\", None, 0.0\)

    pct_change = \(\(price_4h - price_at_decision\) / price_at_decision\) * 100

    decision_upper = decision.upper\(\)

    if decision_upper == \"BUY\":
        if price_4h > price_at_decision:
            return \(\"WIN\", True, pct_change\)
        else:
            return \(\"LOSS\", False, pct_change\)
    elif decision_upper == \"SELL\":
        if price_4h < price_at_decision:
            return \(\"WIN\", True, pct_change\)
        else:
            return \(\"LOSS\", False, pct_change\)
    else:  # HOLD - evaluate directionally
        if pct_change >= 2.0:
            # Price went up significantly - HOLD was wrong, should have bought
            return \(\"MISSED_BUY\", False, pct_change\)
        elif pct_change <= -2.0:
            # Price went down - HOLD was correct
            return \(\"CORRECT_HOLD\", True, pct_change\)
        else:
            # Price stayed within +/- 2% - truly neutral
            return \(\"NEUTRAL\", None, pct_change\)"""

new_outcome = '''def determine_outcome_d1(
    decision: str, price_at_decision: float, price_next_day: float
) -> tuple:
    """
    Determine WIN/LOSS outcome based on D to D+1 price movement.
    Returns: (outcome: str, outcome_pct: float or None)
    
    WIN/LOSS logic:
    - BUY + positive change = WIN (outcome_pct = positive change)
    - BUY + non-positive change = LOSS (outcome_pct = negative change)
    - SELL + negative change = WIN (outcome_pct = abs of negative change)
    - SELL + non-negative change = LOSS (outcome_pct = negative change)
    - HOLD or BLOCKED = N/A (outcome_pct = None)
    """
    if price_at_decision is None or price_next_day is None:
        return ("N/A", None)
    
    pct_change = ((price_next_day - price_at_decision) / price_at_decision) * 100
    
    decision_upper = decision.upper()
    
    if decision_upper == "BUY":
        if pct_change > 0:
            return ("WIN", pct_change)
        else:
            return ("LOSS", pct_change)
    elif decision_upper == "SELL":
        if pct_change < 0:
            return ("WIN", abs(pct_change))
        else:
            return ("LOSS", -pct_change)
    else:
        # HOLD, BLOCKED, or any other decision
        return ("N/A", None)'''

content = re.sub(old_outcome, new_outcome, content)

# Write the modified content
with open("/root/limitless-ai/run_backtest.py", "w") as f:
    f.write(content)

print("First set of replacements done")
