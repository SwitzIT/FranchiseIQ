"""
Chat route — v7.0 (NEW)
========================
An LLM-powered assistant that answers questions about the CURRENT
session's prediction results — "why is candidate 3 ranked above candidate
7", "what's my best district", "summarize my top picks for a memo" — by
grounding every answer in the actual computed data (top_picks, kpis,
model_metrics), not by inventing numbers.

This route previously didn't exist at all, despite being referenced in
routes/__init__.py and called (in a broken way — unauthenticated, wrong
variable name) from the frontend. Both sides are fixed as of this version.

Env vars:
    ANTHROPIC_API_KEY   required — chat returns a clear 503 if unset,
                        rather than crashing the whole app at import time
    CLAUDE_MODEL        default "claude-sonnet-5"
"""
import os
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.services import get_key, session_exists
from app.services.llm_chat_providers import get_chat_reply
from app.auth import get_current_user
from app.utils import get_logger

log = get_logger("routes.chat")
router = APIRouter(tags=["Chat"])

MAX_HISTORY_MESSAGES = 10
MAX_MESSAGE_CHARS = 2000


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str


SYSTEM_PROMPT_BASE = """You are the FranchiseIQ Assistant, built into a franchise \
location-intelligence tool. You help the user understand THEIR specific \
analysis results — top location picks, scores, KPIs, and existing store \
performance — not general franchising advice.

Rules you must follow:
- Only state numbers, names, and facts that appear in the DATA CONTEXT below. \
Never invent or estimate a figure that isn't there.
- If the answer isn't in the provided data, say so plainly and suggest what \
the user could do to get it (e.g. "run a prediction first", "that candidate \
isn't in your current top picks").
- Keep answers focused on their results and decisions, not a technical \
walkthrough of the underlying scoring methodology.
- Be concise — this is a chat widget, not a report. A few sentences or a \
short list, not an essay, unless the user explicitly asks for something \
long-form like a memo.
- Currency is Indian Rupees; write large figures the way the app does, e.g. \
"₹1.34 Cr" style is fine if that's how the data is phrased, otherwise plain \
₹ figures are fine too.
"""


def _build_data_context(session_id: str | None) -> str:
    """Condenses the current session's results into a compact, LLM-readable
    summary. Deliberately excludes raw geometry/high-volume fields — only
    what a person would actually want explained or summarized."""
    if not session_id or not session_exists(session_id):
        return "No active analysis session. The user hasn't run a prediction yet."

    country = get_key(session_id, "country")
    state = get_key(session_id, "state")
    results = get_key(session_id, "results")

    if not results:
        return (
            f"Session is set to {country}/{state}, but no prediction has been "
            f"run yet in this session — the user needs to click Predict first."
        )

    kpis = results.get("kpis", {})
    model_metrics = results.get("model_metrics", {})
    top_picks = results.get("top_picks", [])

    picks_summary = []
    for i, p in enumerate(top_picks[:15]):  # cap — keep context bounded
        picks_summary.append({
            "rank": i + 1,
            "name": p.get("name"),
            "score": p.get("score"),
            "verdict": p.get("verdict"),
            "predicted_revenue": p.get("revenue"),
            "population": p.get("population"),
            "top_positive_drivers": p.get("top_positive_drivers"),
            "top_negative_drivers": p.get("top_negative_drivers"),
            "caution_reasons": p.get("caution_reasons") or None,
            "nearby_store_avg_sales": p.get("nearby_store_avg_sales"),
            "comparable_stores": p.get("comparable_stores"),
        })

    context = {
        "region": f"{country} / {state}",
        "kpis": kpis,
        "model_metrics": {
            "r2_test": model_metrics.get("r2_test"),
            "mae_test": model_metrics.get("mae_test"),
            "note": "R2 is the fraction of sales variance explained by location "
                    "signals alone — the rest comes from execution, staff, "
                    "marketing, etc. that this data can't capture.",
        },
        "top_picks": picks_summary,
    }
    return json.dumps(context, indent=2, default=str)


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, current_user: str = Depends(get_current_user)):
    # Trim + validate history
    history = body.messages[-MAX_HISTORY_MESSAGES:]
    for m in history:
        if len(m.content) > MAX_MESSAGE_CHARS:
            raise HTTPException(400, f"Message too long (max {MAX_MESSAGE_CHARS} chars).")

    # Both providers require the conversation to start with a "user"
    # message. The frontend's hardcoded greeting is role "assistant" and
    # may be the first item in history — drop any leading assistant-only
    # messages.
    while history and history[0].role == "assistant":
        history = history[1:]
    if not history:
        raise HTTPException(400, "No user message to respond to.")

    data_context = _build_data_context(body.session_id)
    system_prompt = SYSTEM_PROMPT_BASE + "\n\nDATA CONTEXT (this is the user's actual current data):\n" + data_context

    reply_text = get_chat_reply(
        history=[{"role": m.role, "content": m.content} for m in history],
        system_prompt=system_prompt,
    )

    log.info(f"[Chat] user={current_user} session={body.session_id} "
             f"history_len={len(history)} reply_len={len(reply_text)}")

    return ChatResponse(reply=reply_text)
