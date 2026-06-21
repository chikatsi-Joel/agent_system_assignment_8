"""Base agent with logging, memory, and timing utilities."""
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
import anthropic

from config import LOG_FILE, MEMORY_FILE, MODEL, MAX_TOKENS, ANTHROPIC_API_KEY


class AgentLogger:
    """Writes structured JSONL logs for every agent call."""

    def __init__(self, log_path: Path = LOG_FILE):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, record: dict[str, Any]) -> None:
        record["logged_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


logger = AgentLogger()


class SharedMemory:
    """JSON file–backed shared memory for inter-agent context."""

    def __init__(self, path: Path = MEMORY_FILE):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")

    def read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, key: str, value: Any) -> None:
        data = self.read()
        data[key] = value
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def update(self, updates: dict) -> None:
        data = self.read()
        data.update(updates)
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")


memory = SharedMemory()


class BaseAgent:
    """Async agent with built-in timing, logging, and memory."""

    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    async def call(self, user_message: str, context: dict | None = None) -> str:
        """Make one Claude API call, log it, return the text."""
        start = time.perf_counter()
        messages = [{"role": "user", "content": user_message}]

        try:
            response = await self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=self.system_prompt,
                messages=messages,
            )
            result = response.content[0].text
            elapsed = round(time.perf_counter() - start, 3)
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            logger.log({
                "agent": self.name,
                "status": "success",
                "elapsed_s": elapsed,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "context": context or {},
            })
            return result

        except Exception as exc:
            elapsed = round(time.perf_counter() - start, 3)
            logger.log({
                "agent": self.name,
                "status": "error",
                "error": str(exc),
                "elapsed_s": elapsed,
                "context": context or {},
            })
            raise
