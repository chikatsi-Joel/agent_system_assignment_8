"""
Writer Agent — synthesizes all bank insights into a Board-level narrative PRD.

Reads all FilingInsights from memory and produces:
1. A markdown PRD (outputs/prds/board_prd.md)
2. A structured dashboard payload (outputs/prds/dashboard_payload.json)
"""
import json
from config import OUTPUTS_DIR
from agents.base_agent import BaseAgent, memory
from config import BANKS


SYSTEM = """You are a senior strategy consultant writing for a Board of Directors.
Given cross-bank FilingInsights for Q3 2024, produce a structured analysis in JSON:
{
  "executiveSummary": string (3-4 sentences, board-level),
  "industryRiskRating": "LOW"|"MODERATE"|"ELEVATED"|"HIGH",
  "consensusThemes": [{"theme": string, "description": string, "banksAffected": [string]}],
  "divergentNarratives": [{"topic": string, "bearishBank": string, "bullishBank": string, "insight": string}],
  "riskHeatmap": {bankId: {"credit": 1-5, "market": 1-5, "liquidity": 1-5, "operational": 1-5, "regulatory": 1-5}},
  "sentimentMatrix": {bankId: {"score": -1.0 to 1.0, "label": string}},
  "topRisksAcrossIndustry": [{"risk": string, "severity": string, "affectedBanks": [string]}],
  "opportunities": [string],
  "prdRecommendations": [
    {"title": string, "rationale": string, "sourceBankId": string, "priority": "HIGH"|"MEDIUM"|"LOW"}
  ],
  "boardNarrative": string (comprehensive paragraph for boardroom presentation)
}
Respond ONLY with valid JSON. Write with authority and precision."""


class WriterAgent(BaseAgent):
    def __init__(self):
        super().__init__("WriterAgent", SYSTEM)

    async def synthesize(self) -> dict:
        mem = memory.read()
        insights = {
            bank_id: mem[f"insight_{bank_id}"]
            for bank_id in BANKS
            if f"insight_{bank_id}" in mem
        }

        if not insights:
            raise ValueError("No insights in memory — run AnalystAgent first")

        prompt = (
            f"Synthesize these {len(insights)} bank FilingInsights into a Board report:\n\n"
            + json.dumps(insights, indent=2)
        )

        result_text = await self.call(
            prompt, context={"phase": "writer", "banksCount": len(insights)}
        )

        try:
            synthesis = json.loads(result_text)
        except json.JSONDecodeError:
            cleaned = result_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            synthesis = json.loads(cleaned)

        # Write structured payload for dashboard
        payload_path = OUTPUTS_DIR / "prds" / "dashboard_payload.json"
        payload_path.write_text(json.dumps(synthesis, indent=2), encoding="utf-8")

        # Write markdown PRD
        prd = _render_prd(synthesis)
        prd_path = OUTPUTS_DIR / "prds" / "board_prd.md"
        prd_path.write_text(prd, encoding="utf-8")

        memory.write("synthesis", synthesis)
        return synthesis


def _render_prd(s: dict) -> str:
    banks_str = ", ".join(s.get("riskHeatmap", {}).keys())
    themes = "\n".join(
        f"- **{t['theme']}**: {t['description']}"
        for t in s.get("consensusThemes", [])
    )
    risks = "\n".join(
        f"- [{r['severity']}] {r['risk']} ({', '.join(r['affectedBanks'])})"
        for r in s.get("topRisksAcrossIndustry", [])
    )
    recs = "\n".join(
        f"- [{r['priority']}] **{r['title']}** — {r['rationale']}"
        for r in s.get("prdRecommendations", [])
    )
    return f"""# PRD: Multi-Bank Financial Intelligence — Q3 2024

## 1. Executive Summary
{s.get('executiveSummary', '')}

**Industry Risk Rating**: {s.get('industryRiskRating', 'N/A')}
**Banks Analyzed**: {banks_str}

## 2. Consensus Themes
{themes}

## 3. Top Industry Risks
{risks}

## 4. Recommendations
{recs}

## 5. Board Narrative
{s.get('boardNarrative', '')}
"""
