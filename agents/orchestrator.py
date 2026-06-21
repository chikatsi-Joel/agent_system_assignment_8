"""
Orchestrator — coordinates the multi-agent fan-out pipeline.

Phase 2: Fan-out architecture
  Scout × 5 banks  ──┐
  (parallel)         ├── Analyst × 5 banks ──┐
                     │   (parallel)           ├── Writer ── Evaluator
                     ┘                        ┘

The orchestrator never calls Claude directly; it routes and tracks agents.
"""
import asyncio
import time
import json
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from agents.scout import ScoutAgent
from agents.analyst import AnalystAgent
from agents.writer import WriterAgent
from agents.evaluator import EvaluatorAgent
from agents.base_agent import memory, logger
from config import BANKS, OUTPUTS_DIR

console = Console()


class Orchestrator:
    def __init__(self):
        self.scout = ScoutAgent()
        self.analyst = AnalystAgent()
        self.writer = WriterAgent()
        self.evaluator = EvaluatorAgent()
        self.timeline: list[dict] = []

    def _record(self, phase: str, duration_s: float, detail: str = ""):
        self.timeline.append({"phase": phase, "duration_s": round(duration_s, 2), "detail": detail})
        logger.log({"agent": "Orchestrator", "phase": phase, "duration_s": round(duration_s, 2), "detail": detail})

    async def run_fan_out(self) -> dict:
        """Full fan-out pipeline: Scout → Analyst → Writer → Evaluator."""
        console.rule("[bold blue]Phase 2: Multi-Agent Fan-Out Pipeline")
        total_start = time.perf_counter()

        # ── Phase A: Fan-out Scout across all banks in parallel ──────────────
        console.print("\n[cyan]► Scout phase: fetching all banks in parallel...[/cyan]")
        t0 = time.perf_counter()
        scout_results = await asyncio.gather(
            *[self.scout.scout(bank_id) for bank_id in BANKS],
            return_exceptions=True,
        )
        scout_duration = time.perf_counter() - t0
        self._record("scout_fanout", scout_duration, f"{len(BANKS)} banks parallel")

        errors = [r for r in scout_results if isinstance(r, Exception)]
        if errors:
            console.print(f"[red]Scout errors: {errors}[/red]")
        console.print(f"[green]✓ Scout complete in {scout_duration:.1f}s — {len(BANKS) - len(errors)}/{len(BANKS)} succeeded[/green]")

        # ── Phase B: Fan-out Analyst across all banks in parallel ────────────
        console.print("\n[cyan]► Analyst phase: analyzing all banks in parallel...[/cyan]")
        t0 = time.perf_counter()
        analyst_results = await asyncio.gather(
            *[self.analyst.analyze(bank_id) for bank_id in BANKS],
            return_exceptions=True,
        )
        analyst_duration = time.perf_counter() - t0
        self._record("analyst_fanout", analyst_duration, f"{len(BANKS)} banks parallel")

        errors = [r for r in analyst_results if isinstance(r, Exception)]
        console.print(f"[green]✓ Analyst complete in {analyst_duration:.1f}s — {len(BANKS) - len(errors)}/{len(BANKS)} succeeded[/green]")

        # ── Phase C: Writer synthesizes all insights ─────────────────────────
        console.print("\n[cyan]► Writer phase: synthesizing board report...[/cyan]")
        t0 = time.perf_counter()
        synthesis = await self.writer.synthesize()
        writer_duration = time.perf_counter() - t0
        self._record("writer", writer_duration, "cross-bank synthesis")
        console.print(f"[green]✓ Writer complete in {writer_duration:.1f}s[/green]")

        # ── Phase D: Evaluator scores architecture ────────────────────────────
        console.print("\n[cyan]► Evaluator phase: scoring architecture (iteration 1)...[/cyan]")
        t0 = time.perf_counter()
        evaluation_1 = await self.evaluator.evaluate(iteration=1)
        eval_duration = time.perf_counter() - t0
        self._record("evaluator_iter1", eval_duration)
        score_1 = evaluation_1.get("overallScore", "?")
        console.print(f"[green]✓ Evaluator complete — Score: {score_1}/10  Readiness: {evaluation_1.get('productionReadiness')}[/green]")

        # ── Phase E: Apply improvements and re-evaluate (improvement loop) ───
        console.print("\n[yellow]► Improvement loop: applying evaluator feedback...[/yellow]")
        improvements = self.evaluator.apply_improvements(evaluation_1)
        console.print(f"  Applied improvements to: {list(improvements.keys())}")

        console.print("\n[cyan]► Re-running writer with improvements, then re-evaluating...[/cyan]")
        t0 = time.perf_counter()
        # Re-synthesize incorporating improvement context
        synthesis_v2 = await self._improved_synthesis(improvements)
        evaluation_2 = await self.evaluator.evaluate(iteration=2)
        loop_duration = time.perf_counter() - t0
        self._record("improvement_loop", loop_duration, "iteration 2")
        score_2 = evaluation_2.get("overallScore", "?")
        delta = self.evaluator.score_delta()
        console.print(f"[green]✓ Improvement loop complete — Score: {score_2}/10  Delta: {delta:+.1f}[/green]")

        total_duration = time.perf_counter() - total_start
        self._record("total", total_duration)

        result = {
            "timeline": self.timeline,
            "totalDuration_s": round(total_duration, 2),
            "score_v1": score_1,
            "score_v2": score_2,
            "scoreDelta": delta,
            "synthesis": synthesis,
            "evaluation_v1": evaluation_1,
            "evaluation_v2": evaluation_2,
        }
        memory.write("orchestrator_run", result)

        # Save timeline
        (OUTPUTS_DIR / "prds" / "timeline.json").write_text(
            json.dumps(self.timeline, indent=2), encoding="utf-8"
        )
        return result

    async def _improved_synthesis(self, improvements: dict) -> dict:
        """Re-run writer with improved context injected."""
        writer_v2 = WriterAgent()
        # Temporarily enhance the writer's system prompt
        improvement_context = improvements.get("writer", "")
        if improvement_context:
            writer_v2.system_prompt = writer_v2.system_prompt + f"\n\nIMPROVEMENT DIRECTIVE: {improvement_context}"
        result = await writer_v2.synthesize()
        memory.write("synthesis_v2", result)
        return result
