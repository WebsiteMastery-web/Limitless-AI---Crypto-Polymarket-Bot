from datetime import datetime

MAX_SIGNAL_CHARS = 200

def compress_signal(text: str, max_chars: int = MAX_SIGNAL_CHARS) -> str:
    if not text or len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"

def count_tokens_approx(text: str) -> int:
    return len(text) // 4

def log_context_size(label: str, context: str) -> None:
    print(f"[Tokens:{label}] ~{count_tokens_approx(context)} tokens ({len(context)} chars)")
