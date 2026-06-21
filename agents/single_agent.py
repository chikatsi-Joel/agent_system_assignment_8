"""
Phase 1 — Single-Agent Baseline.

One monolithic agent receives ALL five banks' filings and produces
a combined analysis report. This is the benchmark we beat in Phase 2.
"""
import json
import asyncio
from pathlib import Path
from config import DATA_DIR, OUTPUTS_DIR
from agents.base_agent import BaseAgent, memory, logger


SYSTEM = """You are a senior bank analyst specializing in 10-K/10-Q filing analysis.
Given raw filing excerpts for multiple banks, produce a structured JSON report with:
- sentiment: "positive" | "neutral" | "cautious" | "negative" per bank
- keyRisks: top 3 risks per bank (list of strings)
- keyStrengths: top 3 strengths per bank (list of strings)
- macroThemes: shared themes across all banks (list of strings)
- riskHeatmap: object mapping bankId -> {credit, market, liquidity, operational, regulatory} each scored 1-5 (5=highest risk)
- crossBankInsight: one paragraph narrative comparing all banks

Respond ONLY with valid JSON. No markdown fences."""


class SingleAgent(BaseAgent):
    def __init__(self):
        super().__init__("SingleAgent", SYSTEM)

    async def analyze(self) -> dict:
        filings = json.loads((DATA_DIR / "simulated_filings.json").read_text())["filings"]

        # Feed ALL filings in one big prompt — the key limitation of single-agent
        combined = "\n\n".join(
            f"=== {f['bankName']} ({f['type']} Q{f['period']['quarter']} {f['period']['year']}) ===\n"
            f"MD&A:\n{f['mda']}\n\nRisk Disclosures:\n{f['risk_disclosures']}"
            for f in filings
        )

        prompt = (
            f"Analyze the following {len(filings)} bank filings and return a structured JSON report:\n\n"
            + combined
        )

        result_text = await self.call(prompt, context={"phase": "single_agent", "banks": len(filings)})

        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            # Strip accidental markdown fences
            cleaned = result_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(cleaned)

        out_path = OUTPUTS_DIR / "insights" / "single_agent_result.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        memory.write("single_agent_result", result)
        return result
