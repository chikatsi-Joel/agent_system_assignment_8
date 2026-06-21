"""
Evaluator Agent — scores the multi-agent architecture and drives the improvement loop.

Scores 1-10 across 8 dimensions and writes improvement recommendations back
into agent system prompts. Re-runs produce measurable score delta.
"""
import json
import asyncio
from pathlib import Path
from config import OUTPUTS_DIR, MEMORY_DIR
from agents.base_agent import BaseAgent, memory, logger


SYSTEM = """You are a principal AI architect with deep experience designing production multi-agent systems.
Evaluate this financial intelligence platform's architecture and produce a JSON report:
{
  "overallScore": 1-10,
  "dimensions": {
    "agentSpecialization": {"score": 1-10, "rationale": string, "recommendation": string},
    "fanOutEfficiency": {"score": 1-10, "rationale": string, "recommendation": string},
    "memoryDesign": {"score": 1-10, "rationale": string, "recommendation": string},
    "outputQuality": {"score": 1-10, "rationale": string, "recommendation": string},
    "errorResilience": {"score": 1-10, "rationale": string, "recommendation": string},
    "costEfficiency": {"score": 1-10, "rationale": string, "recommendation": string},
    "scalability": {"score": 1-10, "rationale": string, "recommendation": string},
    "boardReadiness": {"score": 1-10, "rationale": string, "recommendation": string}
  },
  "topImprovements": [
    {"priority": 1-5, "change": string, "expectedScoreGain": number, "effort": "LOW"|"MEDIUM"|"HIGH"}
  ],
  "promptImprovements": {
    "scout": string,  // improved system prompt fragment
    "analyst": string,
    "writer": string
  },
  "productionReadiness": "NOT_READY"|"PROTOTYPE"|"STAGING"|"PRODUCTION_READY",
  "verdict": string  // 2-3 sentence overall assessment
}
Be specific and brutally honest. Score conservatively — 10 means production-ready at scale."""


class EvaluatorAgent(BaseAgent):
    def __init__(self):
        super().__init__("EvaluatorAgent", SYSTEM)
        self.improvement_log: list[dict] = []

    async def evaluate(self, iteration: int = 1) -> dict:
        mem = memory.read()
        synthesis = mem.get("synthesis", {})
        insights_available = [k for k in mem if k.startswith("insight_")]
        log_summary = _read_log_summary()

        architecture_desc = {
            "architecture": "Multi-agent fan-out: Orchestrator → [ScoutAgent × 5 banks in parallel] → [AnalystAgent × 5 banks in parallel] → WriterAgent → EvaluatorAgent",
            "agentCount": 4,
            "specialists": ["Scout (EDGAR retrieval)", "Analyst (FilingInsight extraction)", "Writer (Board synthesis)", "Evaluator (architecture scoring)"],
            "memoryMechanism": "JSON file (shared_context.json) + per-bank files in outputs/",
            "loggingMechanism": "JSONL append (logs/agent_runs.jsonl)",
            "fanOutStrategy": "asyncio.gather over all banks in parallel for Scout and Analyst phases",
            "banksAnalyzed": len(insights_available),
            "logStats": log_summary,
            "sampleInsight": list(insights_available)[:1],
            "synthesisProduced": bool(synthesis),
            "dashboardGenerated": (OUTPUTS_DIR / "dashboard_payload.json").exists() or (OUTPUTS_DIR / "prds" / "dashboard_payload.json").exists(),
        }

        prompt = (
            f"Evaluate this multi-agent financial intelligence platform (iteration {iteration}):\n\n"
            f"Architecture:\n{json.dumps(architecture_desc, indent=2)}\n\n"
            f"Sample synthesis output:\n{json.dumps(synthesis, indent=2)[:3000]}"
        )

        result_text = await self.call(
            prompt, context={"phase": "evaluator", "iteration": iteration}
        )

        try:
            evaluation = json.loads(result_text)
        except json.JSONDecodeError:
            cleaned = result_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            evaluation = json.loads(cleaned)

        evaluation["iteration"] = iteration
        out_path = OUTPUTS_DIR / "prds" / f"evaluation_iter{iteration}.json"
        out_path.write_text(json.dumps(evaluation, indent=2), encoding="utf-8")

        self.improvement_log.append({
            "iteration": iteration,
            "overallScore": evaluation.get("overallScore"),
            "productionReadiness": evaluation.get("productionReadiness"),
        })
        memory.write(f"evaluation_iter{iteration}", evaluation)
        memory.write("latest_evaluation", evaluation)
        return evaluation

    def apply_improvements(self, evaluation: dict) -> dict[str, str]:
        """Extract improved prompts from evaluation and save them for the next run."""
        improvements = evaluation.get("promptImprovements", {})
        improvement_path = MEMORY_DIR / "prompt_improvements.json"
        improvement_path.write_text(json.dumps(improvements, indent=2), encoding="utf-8")
        logger.log({
            "agent": "EvaluatorAgent",
            "status": "improvements_applied",
            "improvements": list(improvements.keys()),
            "overallScore": evaluation.get("overallScore"),
        })
        return improvements

    def score_delta(self) -> float | None:
        if len(self.improvement_log) < 2:
            return None
        return self.improvement_log[-1]["overallScore"] - self.improvement_log[0]["overallScore"]


def _read_log_summary() -> dict:
    from config import LOG_FILE
    if not LOG_FILE.exists():
        return {}
    lines = LOG_FILE.read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(l) for l in lines if l.strip()]
    successes = sum(1 for r in records if r.get("status") == "success")
    errors = sum(1 for r in records if r.get("status") == "error")
    total_input = sum(r.get("input_tokens", 0) for r in records)
    total_output = sum(r.get("output_tokens", 0) for r in records)
    avg_elapsed = (
        sum(r.get("elapsed_s", 0) for r in records) / len(records) if records else 0
    )
    return {
        "totalCalls": len(records),
        "successes": successes,
        "errors": errors,
        "totalInputTokens": total_input,
        "totalOutputTokens": total_output,
        "avgElapsedSec": round(avg_elapsed, 2),
    }
