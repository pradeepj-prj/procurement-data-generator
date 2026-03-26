"""FastAPI REST endpoint for the procurement GraphRAG."""

from __future__ import annotations

import argparse
import asyncio
import json
import queue
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from graphrag.config import GraphRAGConfig, get_backend
from graphrag.llm.genai_hub import GenAIHubClient
from graphrag.llm.router import IntentRouter

# ── Globals ──────────────────────────────────────────────────────────────────

_router: IntentRouter | None = None
_agent: Any | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize backend + LLM + agent on startup."""
    global _router, _agent
    config = GraphRAGConfig.from_env()
    backend = get_backend(config)
    llm = GenAIHubClient(config)
    _router = IntentRouter(backend, llm)

    # Agent mode (optional — requires langgraph)
    try:
        from graphrag.llm.agent import create_procurement_agent

        _agent = create_procurement_agent(backend, config)
        print("Agent mode: available", file=sys.stderr)
    except ImportError:
        _agent = None
        print("Agent mode: unavailable (install with: pip install -e '.[graphrag-agent]')", file=sys.stderr)
    except Exception as exc:
        _agent = None
        print(f"Agent mode: failed to initialize ({exc})", file=sys.stderr)

    yield


app = FastAPI(
    title="Procurement GraphRAG",
    description="Natural language Q&A over the procurement knowledge graph",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    question: str
    stream: bool = False
    include_trace: bool = False
    mode: Literal["router", "agent"] = "router"
    history: list[dict[str, str]] | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]
    query_pattern: str
    context_snippet: str
    trace: dict[str, Any] | None = None


# ── Agent SSE bridge ─────────────────────────────────────────────────────────


async def _stream_agent_events(
    agent: Any, question: str, include_trace: bool,
    history: list[dict[str, str]] | None = None,
) -> AsyncGenerator[str, None]:
    """Bridge the sync ``stream_agent_steps`` generator to async SSE events."""
    from graphrag.llm.agent import stream_agent_steps

    q: queue.Queue[dict | None] = queue.Queue()
    loop = asyncio.get_event_loop()

    def _run_sync() -> None:
        try:
            for event in stream_agent_steps(agent, question, history=history):
                q.put(event)
        except Exception as exc:
            q.put({"event": "error", "message": str(exc)})
        finally:
            q.put(None)  # sentinel

    fut = loop.run_in_executor(None, _run_sync)

    while True:
        event = await loop.run_in_executor(None, q.get)
        if event is None:
            break
        if event.get("event") == "answer" and not include_trace:
            event.pop("trace", None)
        yield f"data: {json.dumps(event)}\n\n"

    yield f"data: {json.dumps({'event': 'done'})}\n\n"
    await fut


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent_available": _agent is not None}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse | StreamingResponse:
    # ── Agent mode ──────────────────────────────────────────────────────
    if req.mode == "agent":
        if _agent is None:
            raise HTTPException(
                400,
                "Agent mode requires langgraph. "
                "Install with: pip install -e '.[graphrag-agent]'",
            )

        if req.stream:
            return StreamingResponse(
                _stream_agent_events(
                    _agent, req.question, req.include_trace, history=req.history
                ),
                media_type="text/event-stream",
            )

        from graphrag.llm.agent import run_agent_with_trace

        result, trace = run_agent_with_trace(
            _agent, req.question, history=req.history
        )
        if req.include_trace:
            result["trace"] = trace.to_dict()
        return ChatResponse(**result)

    # ── Router mode ─────────────────────────────────────────────────────
    assert _router is not None, "Router not initialized"

    if req.stream:
        intent = _router.classify(req.question)
        context = _router.retrieve(intent)

        from graphrag.llm.prompts import build_rag_messages

        messages = build_rag_messages(req.question, context)

        if req.include_trace:
            from graphrag.observability.trace import (
                QueryTrace,
                Span,
                _now_ms,
            )

            trace = QueryTrace(question=req.question)
            trace.intent = {
                "pattern": intent.pattern,
                "entity_id": intent.entity_id,
            }

            async def generate_with_trace() -> AsyncGenerator[str, None]:
                gen_span = Span(name="generate", start_ms=_now_ms())
                tokens: list[str] = []
                for token in _router._llm.chat_stream(messages):
                    tokens.append(token)
                    yield f"data: {token}\n\n"
                gen_span.end_ms = _now_ms()
                full_response = "".join(tokens)
                gen_span.metadata = {
                    "model": getattr(_router._llm, "model_name", "unknown"),
                    "estimated_response_tokens": len(full_response) // 4,
                    "latency_ms": round(gen_span.duration_ms, 2),
                }
                trace.spans.append(gen_span)
                trace.total_ms = gen_span.duration_ms
                trace.context_snippet = context[:500]
                yield f"data: {json.dumps({'trace': trace.to_dict()})}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_with_trace(), media_type="text/event-stream"
            )

        async def generate() -> AsyncGenerator[str, None]:
            for token in _router._llm.chat_stream(messages):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    # Non-streaming router
    if req.include_trace:
        result, trace = _router.answer_with_trace(req.question)
        result["trace"] = trace.to_dict()
        return ChatResponse(**result)

    result = _router.answer(req.question)
    return ChatResponse(**result)


# ── Static file serving (UI) ────────────────────────────────────────────────

_ui_dist = Path(__file__).parent.parent / "ui" / "dist"
if _ui_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_ui_dist), html=True), name="ui")


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Procurement GraphRAG API")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    uvicorn.run(
        "graphrag.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
