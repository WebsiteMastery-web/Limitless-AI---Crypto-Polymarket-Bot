import os
import json
import logging
from datetime import datetime
from tradingagents.agents.utils.agent_utils import build_instrument_context
from llm_router import call_pm

PM_DECISION_PROTOCOL = """As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision.

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction to enter or add to position
- **Overweight**: Favorable outlook, gradually increase exposure
- **Hold**: Maintain current position, no action needed
- **Underweight**: Reduce exposure, take partial profits
- **Sell**: Exit position or avoid entry

**Required Output Structure:**
1. **Rating**: State one of Buy / Overweight / Hold / Underweight / Sell.
2. **Executive Summary**: A concise action plan covering entry strategy, position sizing, key risk levels, and time horizon.
3. **Investment Thesis**: Detailed reasoning anchored in the analysts' debate and past reflections.

Be decisive and ground every conclusion in specific evidence from the analysts."""

_COST_LOG = "/root/limitless-ai/logs/token_costs.jsonl"
_logger = logging.getLogger(__name__)


def _log_cost(result):
    try:
        os.makedirs(os.path.dirname(_COST_LOG), exist_ok=True)
        with open(_COST_LOG, "a") as f:
            f.write(json.dumps({
                "ts": datetime.utcnow().isoformat(),
                "model": result.get("model"),
                "in_tok": result.get("usage", {}).get("prompt_tokens", 0),
                "out_tok": result.get("usage", {}).get("completion_tokens", 0),
                "cost_usd": result.get("cost_usd", 0),
                "ms": result.get("ms", 0),
                "type": "PM"
            }) + "\n")
    except Exception as e:
        _logger.warning(f"[PM] Cost log write failed: {e}")


def _build_legacy_prompt(instrument_context, trader_plan, past_memory_str, history):
    return f"""As the Portfolio Manager, synthesize the risk analysts' debate and deliver the final trading decision.

{instrument_context}

---

**Rating Scale** (use exactly one):
- **Buy**: Strong conviction to enter or add to position
- **Overweight**: Favorable outlook, gradually increase exposure
- **Hold**: Maintain current position, no action needed
- **Underweight**: Reduce exposure, take partial profits
- **Sell**: Exit position or avoid entry

**Context:**
- Trader's proposed plan: **{trader_plan}**
- Lessons from past decisions: **{past_memory_str}**

**Required Output Structure:**
1. **Rating**: State one of Buy / Overweight / Hold / Underweight / Sell.
2. **Executive Summary**: A concise action plan covering entry strategy, position sizing, key risk levels, and time horizon.
3. **Investment Thesis**: Detailed reasoning anchored in the analysts' debate and past reflections.

---

**Risk Analysts Debate History:**
{history}

---

Be decisive and ground every conclusion in specific evidence from the analysts."""


def create_portfolio_manager(llm, memory, config=None):
    def portfolio_manager_node(state) -> dict:

        instrument_context = build_instrument_context(state["company_of_interest"])

        history = state["risk_debate_state"]["history"]
        risk_debate_state = state["risk_debate_state"]
        market_research_report = state["market_report"]
        news_report = state["news_report"]
        fundamentals_report = state["fundamentals_report"]
        sentiment_report = state["sentiment_report"]
        trader_plan = state["investment_plan"]

        curr_situation = f"{market_research_report}\n\n{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}"
        past_memories = memory.get_memories(curr_situation, n_matches=2)

        past_memory_str = ""
        for i, rec in enumerate(past_memories, 1):
            past_memory_str += rec["recommendation"] + "\n\n"

        cfg = config or {}
        kb_context = cfg.get("kb_context", "")

        dynamic_signals = (
            f"Instrument: {instrument_context}\n\n"
            f"Trader's proposed plan: **{trader_plan}**\n"
            f"Lessons from past decisions: **{past_memory_str}**\n\n"
            f"---\n\n**Risk Analysts Debate History:**\n{history}\n\n---\n\n"
            f"Deliver your final rating and decision."
        )

        static_kb = f"### KNOWLEDGE BASE\n{kb_context}" if kb_context else ""

        try:
            result = call_pm(
                static_protocol=PM_DECISION_PROTOCOL,
                static_kb=static_kb,
                dynamic_signals=dynamic_signals,
                max_tokens=1000
            )
            content = result["content"]
            _log_cost(result)

            if result["model"] == "FALLBACK_HOLD":
                _logger.warning("[PM] Opus failed, falling back to LangChain")
                prompt = _build_legacy_prompt(instrument_context, trader_plan, past_memory_str, history)
                content = llm.invoke(prompt).content
        except Exception as e:
            _logger.warning(f"[PM] Router call failed ({e}), falling back to LangChain")
            prompt = _build_legacy_prompt(instrument_context, trader_plan, past_memory_str, history)
            content = llm.invoke(prompt).content

        new_risk_debate_state = {
            "judge_decision": content,
            "history": risk_debate_state["history"],
            "aggressive_history": risk_debate_state["aggressive_history"],
            "conservative_history": risk_debate_state["conservative_history"],
            "neutral_history": risk_debate_state["neutral_history"],
            "latest_speaker": "Judge",
            "current_aggressive_response": risk_debate_state["current_aggressive_response"],
            "current_conservative_response": risk_debate_state["current_conservative_response"],
            "current_neutral_response": risk_debate_state["current_neutral_response"],
            "count": risk_debate_state["count"],
        }

        return {
            "risk_debate_state": new_risk_debate_state,
            "final_trade_decision": content,
        }

    return portfolio_manager_node
