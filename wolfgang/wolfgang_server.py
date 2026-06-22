#!/usr/bin/env python3
"""Wolfgang — lightweight personal AI assistant backend.
Runs on Petri (Mac Studio M4 Max). Talks to local Ollama + Whisper.
"""

import os
import json
import tempfile
import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
import httpx
from duckduckgo_search import DDGS

WOLFGANG_DIR = Path("/Users/crespo/wolfgang")
MEMORY_FILE = WOLFGANG_DIR / "wolfgang.txt"
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen2.5:7b"
PORT = 7861

SYSTEM_PROMPT = """You are Wolfgang, Alex's personal AI assistant.
You have access to Alex's persistent memory file (loaded below as MEMORY).
This file contains notes about Alex's projects, preferences, decisions, and life context.
Use it to give informed, personal responses.

You can search the web when you need current information.
Be concise, direct, and helpful. No fluff.
Alex prefers lowercase and minimal formatting.

When you learn something new about Alex, his projects, or his preferences, mention that you'll note it down.
"""

app = FastAPI(title="Wolfgang")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://crespo.world",
        "http://crespo.world",
        "http://localhost:8000",
        "http://localhost:5500",
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    response: str
    transcript: str | None = None


def load_memory() -> str:
    if MEMORY_FILE.exists():
        return MEMORY_FILE.read_text(encoding="utf-8")
    return ""


def save_memory_append(user_msg: str, assistant_msg: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n[{timestamp}] Alex: {user_msg}\n[{timestamp}] Wolfgang: {assistant_msg}\n"
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(entry)


def web_search(query: str, max_results: int = 5) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No search results found."
        lines = []
        for r in results:
            lines.append(f"- {r.get('title', 'Untitled')}: {r.get('href', '')}")
            body = r.get("body", "")
            if body:
                lines.append(f"  {body[:200]}")
        return "\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    memory = load_memory()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    system = (
        f"{SYSTEM_PROMPT}\n\n"
        f"=== ALEX'S MEMORY FILE ===\n{memory}\n=== END MEMORY ===\n\n"
        f"Current date/time: {now}"
    )

    messages = [{"role": "system", "content": system}]
    for h in req.history[-20:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": req.message})

    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information. Use when the user asks about recent events, weather, news, prices, or anything that requires up-to-date data.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query",
                        }
                    },
                    "required": ["query"],
                },
            },
        }
    ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        payload = {
            "model": MODEL,
            "messages": messages,
            "tools": tools,
            "stream": False,
        }

        r = await client.post(OLLAMA_URL, json=payload)
        r.raise_for_status()
        data = r.json()

        msg = data.get("message", {})
        tool_calls = msg.get("tool_calls")

        if tool_calls:
            messages.append(msg)

            for tc in tool_calls:
                fn = tc.get("function", {})
                if fn.get("name") == "web_search":
                    args = fn.get("arguments", {})
                    query = args.get("query", req.message)
                    results = web_search(query)
                    messages.append(
                        {
                            "role": "tool",
                            "content": f"Search results for '{query}':\n{results}",
                        }
                    )

            r2 = await client.post(OLLAMA_URL, json={
                "model": MODEL,
                "messages": messages,
                "stream": False,
            })
            r2.raise_for_status()
            data2 = r2.json()
            response_text = data2.get("message", {}).get("content", "")
        else:
            response_text = msg.get("content", "")

    save_memory_append(req.message, response_text)

    return ChatResponse(response=response_text)


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    import whisper

    global _whisper_model
    if "_whisper_model" not in globals() or _whisper_model is None:
        _whisper_model = whisper.load_model("base")

    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = _whisper_model.transcribe(tmp_path)
        return {"text": result["text"].strip()}
    finally:
        os.unlink(tmp_path)


@app.get("/file", response_class=PlainTextResponse)
async def get_file():
    return load_memory()


if __name__ == "__main__":
    import uvicorn

    WOLFGANG_DIR.mkdir(parents=True, exist_ok=True)
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text(
            "# Wolfgang Memory\n"
            "# This file is loaded as context for every conversation.\n"
            "# Conversation turns are appended automatically.\n\n",
            encoding="utf-8",
        )
    uvicorn.run(app, host="0.0.0.0", port=PORT)
