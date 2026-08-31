"""
LLM chat provider abstraction — v7.2
=====================================
Supports two backends, selected via the CHAT_PROVIDER env var:

    CHAT_PROVIDER=anthropic     (default) — paid, higher quality
    CHAT_PROVIDER=huggingface   — free, lower quality, NOT guaranteed
                                   uptime/rate limits (Hugging Face's own
                                   docs say: "do not build customer-facing
                                   products on the free tier" — fine for
                                   an internal tool, worth knowing)

Env vars:
    CHAT_PROVIDER       "anthropic" | "huggingface", default "anthropic"

    # Anthropic path
    ANTHROPIC_API_KEY
    CLAUDE_MODEL        default "claude-sonnet-5"

    # Hugging Face path
    HF_TOKEN            get one free at https://huggingface.co/settings/tokens
                        (create it as an "Inference" type token)
    HF_MODEL            default "openai/gpt-oss-120b:fastest" — the exact
                        example HF's own current "Getting Started" guide
                        uses. The ":fastest" suffix picks whichever backend
                        provider (Cerebras/Together/Groq/etc.) is quickest
                        for this model right now — you don't need to know
                        or pick a specific provider yourself. ":cheapest"
                        and ":auto" are the other built-in selectors.

v7.2 — IMPORTANT FIX: Hugging Face retired `api-inference.huggingface.co`
in favor of `router.huggingface.co`. The old `huggingface_hub.
InferenceClient` (pinned to an older SDK version, chosen specifically to
dodge a different flagged bug in the newest release) was still pointed at
the dead domain internally, causing every request to fail with a DNS
NXDOMAIN error that looked like a local network problem but wasn't. Fixed
by calling the new router endpoint directly via the `openai` SDK (HF's own
current docs recommend exactly this — it's a documented OpenAI-compatible
REST endpoint, not something built on huggingface_hub's internal routing
at all, so it's not exposed to the same kind of SDK-version/endpoint
mismatch that caused this).
"""
import os
from fastapi import HTTPException
from app.utils import get_logger

log = get_logger("llm_chat_providers")

CHAT_PROVIDER = os.getenv("CHAT_PROVIDER", "anthropic").strip().lower()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")
HF_MODEL = os.getenv("HF_MODEL", "openai/gpt-oss-120b:fastest")
HF_ROUTER_BASE_URL = "https://router.huggingface.co/v1"


def get_chat_reply(history: list[dict], system_prompt: str) -> str:
    """history: list of {"role": "user"|"assistant", "content": str},
    already trimmed and validated to start with a user message.
    Returns the assistant's reply text, or raises HTTPException on any
    configuration/upstream failure — never lets an SDK exception leak
    past this function unhandled."""
    if CHAT_PROVIDER == "huggingface":
        return _huggingface_reply(history, system_prompt)
    elif CHAT_PROVIDER == "anthropic":
        return _anthropic_reply(history, system_prompt)
    else:
        raise HTTPException(
            500,
            f"Unknown CHAT_PROVIDER='{CHAT_PROVIDER}'. Must be 'anthropic' or 'huggingface'.",
        )


def _anthropic_reply(history: list[dict], system_prompt: str) -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(
            503,
            "Chat is set to use Anthropic (CHAT_PROVIDER=anthropic) but "
            "ANTHROPIC_API_KEY is not set. Either set that key, or switch "
            "to the free Hugging Face path with CHAT_PROVIDER=huggingface.",
        )
    try:
        import anthropic
    except ImportError:
        raise HTTPException(503, "The 'anthropic' package isn't installed on the backend.")

    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1000,
            system=system_prompt,
            messages=history,
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
    except Exception as e:
        log.error(f"[Chat/Anthropic] request failed: {e}")
        raise HTTPException(502, f"Anthropic chat request failed: {str(e)}")


def _huggingface_reply(history: list[dict], system_prompt: str) -> str:
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        raise HTTPException(
            503,
            "Chat is set to use Hugging Face (CHAT_PROVIDER=huggingface) but "
            "HF_TOKEN is not set. Get a free token at "
            "https://huggingface.co/settings/tokens (create it as an "
            "'Inference' type token) and set it in your environment.",
        )
    try:
        from openai import OpenAI
    except ImportError:
        raise HTTPException(503, "The 'openai' package isn't installed on the backend.")

    # v7.2 — Hugging Face's OpenAI-compatible router, NOT huggingface_hub's
    # InferenceClient. See module docstring for why this changed.
    client = OpenAI(base_url=HF_ROUTER_BASE_URL, api_key=hf_token)

    messages = [{"role": "system", "content": system_prompt}] + history

    try:
        completion = client.chat.completions.create(
            model=HF_MODEL,
            messages=messages,
            max_tokens=1000,
        )
        return completion.choices[0].message.content or ""
    except Exception as e:
        # Common real-world cases worth surfacing clearly rather than a raw
        # stack trace: model/provider combo not currently available, rate
        # limited, or a cold-start timeout on an unpopular model.
        log.error(f"[Chat/HuggingFace] request failed (model={HF_MODEL}): {e}")
        raise HTTPException(
            502,
            f"Hugging Face chat request failed ({HF_MODEL}): {str(e)}. "
            f"If this persists, try a different provider suffix (e.g. "
            f"':together' or ':cerebras' instead of ':fastest') or check "
            f"https://huggingface.co/{HF_MODEL.split(':')[0]} for which "
            f"providers currently serve this model.",
        )