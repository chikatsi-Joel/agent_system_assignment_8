"""
Analyst Agent — deep-reads one bank's scouted filing and extracts FilingInsight.

Produces structured insight with sentiment, risk flags, topics, and key metrics.
"""
import json
from pathlib import Path
from config import OUTPUTS_DIR
from agents.base_agent import BaseAgent, memory


SYSTEM = """You are a senior financial analyst specializing in bank 10-K/10-Q filings.
Given scouted filing data for one bank, produce a FilingInsight JSON with exactly these fields:
{
  "bankId": string,
  "bankName": string,
  "period": {"year": number, "quarter": number},
  "sentiment": "positive" | "neutral" | "cautious" | "negative",
  "sentimentScore": number between -1.0 and 1.0,
  "topics": [{"name": string, "sentiment": string, "excerpt": string}],  // 5-7 topics
  "riskFlags": [
    {"type": "credit"|"market"|"liquidity"|"operational"|"regulatory",
     "severity": "elevated"|"new"|"resolved"|"monitoring",
     "description": string,
     "quantifiedImpact": string}
  ],  // 4-6 risk flags
  "riskScores": {"credit": 1-5, "market": 1-5, "liquidity": 1-5, "operational": 1-5, "regulatory": 1-5},
  "keyStrengths": [string],  // top 3
  "keyWeaknesses": [string],  // top 3
  "forwardGuidance": string,
  "macroOutlook": string,
  "keyMetrics": {object of extracted numbers}
}
Respond ONLY with valid JSON. Be precise and cite numbers from the text."""


class AnalystAgent(BaseAgent):
    def __init__(self):
        super().__init__("AnalystAgent", SYSTEM)

    async def analyze(self, bank_id: str) -> dict:
        scouted = memory.read().get(f"scout_{bank_id}")
        if not scouted:
            raise ValueError(f"No scouted data for {bank_id} — run ScoutAgent first")

        prompt = (
            f"Produce a FilingInsight for {scouted.get('bankName', bank_id)}.\n\n"
            f"MD&A:\n{scouted['rawMda']}\n\n"
            f"Risk Disclosures:\n{scouted['rawRisk']}\n\n"
            f"Key Metrics (from filing): {json.dumps(scouted.get('keyMetrics', {}))}\n\n"
            f"Scout Summary — MDA: {scouted.get('rawMdaSummary', '')}\n"
            f"Scout Summary — Risk: {scouted.get('rawRiskSummary', '')}"
        )

        result_text = await self.call(
            prompt, context={"phase": "analyst", "bankId": bank_id}
        )

        try:
            insight = json.loads(result_text)
        except json.JSONDecodeError:
            cleaned = result_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            insight = json.loads(cleaned)

        out_path = OUTPUTS_DIR / "insights" / f"{bank_id}_insight.json"
        out_path.write_text(json.dumps(insight, indent=2), encoding="utf-8")
        memory.write(f"insight_{bank_id}", insight)
        return insight
