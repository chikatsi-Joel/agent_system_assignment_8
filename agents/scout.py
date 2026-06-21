"""
Scout Agent — retrieves and pre-processes raw filing data for one bank.

In production this would call EDGAR. Here it reads simulated filings.
Outputs a cleaned FilingRaw dict to shared memory.
"""
import json
from config import DATA_DIR
from agents.base_agent import BaseAgent, memory


SYSTEM = """You are a financial data scout. Your job is to extract and structure raw filing metadata.
Given a raw 10-K/10-Q filing, extract:
- filingId: "{bankId}-{year}-Q{quarter}"
- bankId, bankName, period, type
- mdaWordCount: approximate word count of MD&A section
- riskWordCount: approximate word count of risk disclosures
- topEntities: up to 10 key named entities (products, metrics, proper nouns) mentioned
- rawMdaSummary: one-sentence summary of MD&A focus
- rawRiskSummary: one-sentence summary of risk disclosure focus

Respond ONLY with valid JSON."""


class ScoutAgent(BaseAgent):
    def __init__(self):
        super().__init__("ScoutAgent", SYSTEM)

    async def scout(self, bank_id: str) -> dict:
        filings = json.loads((DATA_DIR / "simulated_filings.json").read_text())["filings"]
        filing = next(f for f in filings if f["bankId"] == bank_id)

        prompt = (
            f"Extract filing metadata for {filing['bankName']}:\n\n"
            f"MD&A:\n{filing['mda']}\n\n"
            f"Risk Disclosures:\n{filing['risk_disclosures']}"
        )

        result_text = await self.call(
            prompt, context={"phase": "scout", "bankId": bank_id}
        )

        try:
            meta = json.loads(result_text)
        except json.JSONDecodeError:
            cleaned = result_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            meta = json.loads(cleaned)

        # Attach raw text so downstream agents can use it
        meta["rawMda"] = filing["mda"]
        meta["rawRisk"] = filing["risk_disclosures"]
        meta["keyMetrics"] = filing.get("keyMetrics", {})

        memory.write(f"scout_{bank_id}", meta)
        return meta
