"""
Main runner — demonstrates all phases of the Financial Intelligence Platform.

Phase 1:  Single-agent baseline (monolithic)
Phase 2:  Multi-agent fan-out (Scout → Analyst → Writer → Evaluator)
Phase 3:  Improvement loop (Evaluator v2 after applying recommendations)
Phase 4:  Board dashboard generation
Phase 5:  Log analysis

Usage:
  python run.py              # full pipeline
  python run.py --phase 1   # single-agent only
  python run.py --phase 2   # multi-agent only
  python run.py --dashboard # regenerate dashboard from cached results
  python run.py --logs      # analyze logs only
"""
import asyncio
import sys
import json
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich import box

from config import ANTHROPIC_API_KEY, OUTPUTS_DIR, LOGS_DIR

console = Console()

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║    FINANCIAL INTELLIGENCE PLATFORM — MULTI-AGENT SYSTEM     ║
║    10-K/10-Q Analysis · 5 Major US Banks · Q3 2024         ║
╚══════════════════════════════════════════════════════════════╝
"""


def check_api_key():
    if not ANTHROPIC_API_KEY:
        console.print("[red]ERROR: ANTHROPIC_API_KEY not set.[/red]")
        console.print("Set it via environment or a .env file:")
        console.print("  ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)
    console.print(f"[green]✓ API key loaded ({ANTHROPIC_API_KEY[:12]}...)[/green]")


async def run_phase1():
    console.rule("[bold green]Phase 1: Single-Agent Baseline")
    console.print("[dim]Feeding ALL 5 banks to one agent — our performance benchmark[/dim]\n")

    from agents.single_agent import SingleAgent
    agent = SingleAgent()
    start = time.perf_counter()
    result = await agent.analyze()
    elapsed = time.perf_counter() - start

    console.print(f"[green]✓ Single agent complete in {elapsed:.1f}s[/green]")
    console.print(f"  Sentiment detected: {list(result.get('sentiment', {}).items())[:3]}")
    console.print(f"  Macro themes: {result.get('macroThemes', [])[:3]}")
    console.print(f"\n[dim]Limitation: one long context → slower, less specialized, harder to scale[/dim]")
    return result, elapsed


async def run_phase2():
    from agents.orchestrator import Orchestrator
    orch = Orchestrator()
    result = await orch.run_fan_out()

    console.rule("[bold blue]Phase 2 Results Summary")
    console.print(f"  Architecture score v1: [yellow]{result['score_v1']}[/yellow]/10")
    console.print(f"  Architecture score v2: [green]{result['score_v2']}[/green]/10")
    delta = result.get('scoreDelta')
    if delta is not None:
        console.print(f"  Score delta (improvement loop): [green]+{delta:.1f}[/green]")
    console.print(f"  Total pipeline time:   {result['totalDuration_s']}s")
    return result


def run_dashboard():
    console.rule("[bold magenta]Board Dashboard Generation")
    from dashboard.generator import generate
    path = generate()
    console.print(f"[green]✓ Dashboard written to: {path}[/green]")
    console.print(f"  Open in browser: file:///{path.as_posix()}")
    return path


def run_logs():
    console.rule("[bold yellow]Log Analysis")
    from log_analyzer import analyze
    return analyze()


def print_write_up():
    console.rule("[bold white]Post-Mortem Write-Up")
    write_up = """
WHAT WE BUILT:
  A 4-specialist multi-agent pipeline that:
  • Scout agent: retrieves + structures raw 10-K/10-Q filing data per bank
  • Analyst agent: extracts FilingInsight (sentiment, risk flags, topics, metrics)
  • Writer agent: synthesizes 5-bank board narrative + PRD recommendations
  • Evaluator agent: scores architecture 1-10, drives improvement loop

FAN-OUT STRATEGY:
  All 5 Scout calls run in parallel (asyncio.gather) → all 5 Analyst calls
  run in parallel. This reduces wall-clock time from ~5× sequential to ~1×.
  The bottleneck becomes the slowest single bank, not the sum of all banks.

WHAT BROKE:
  • JSON parsing: Claude occasionally wraps output in markdown fences despite
    instructions. Fixed with a strip-and-retry pattern in each agent.
  • Memory contention: parallel agents writing to the same JSON file required
    sequential writes (Python's GIL saved us, but this is fragile at scale).
  • Evaluator cold-start: evaluator needs synthesis to exist first — strict
    ordering dependency breaks naive parallel execution.

WHAT TO CHANGE:
  1. Replace JSON file memory with Redis or a proper message queue (e.g. BullMQ)
  2. Add structured output via tool use / JSON schema enforcement
  3. Implement retry + exponential backoff on API rate limits
  4. Add streaming for Writer agent (board can see results live)
  5. Move from asyncio.gather to a proper task graph with dependency resolution
  6. Add vector embeddings (pgvector) for semantic cross-quarter search

PRODUCTION READINESS:
  NOT YET. Current rating: PROTOTYPE → STAGING with the following blockers:
  • No persistent database (insights lost on restart)
  • No authentication on the dashboard
  • No test suite for agent output validation
  • EDGAR rate limiter not wired (would violate SEC ToS at scale)
  • Evaluator improvement loop is one shot, not continuous

WOULD I PUT THIS IN ENTERPRISE PRODUCTION?
  With 8-12 weeks of engineering: YES. The core architecture is sound.
  The fan-out pattern scales linearly to 50+ banks. The evaluator loop
  creates a self-improving system. The board dashboard is genuinely useful.
  The blockers are infrastructure, not fundamental design.
"""
    console.print(write_up)


async def main():
    console.print(BANNER)
    args = sys.argv[1:]

    check_api_key()
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "insights").mkdir(exist_ok=True)
    (OUTPUTS_DIR / "prds").mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)

    if "--logs" in args:
        run_logs()
        return

    if "--dashboard" in args:
        run_dashboard()
        return

    phase = None
    if "--phase" in args:
        idx = args.index("--phase")
        phase = int(args[idx + 1]) if idx + 1 < len(args) else None

    # Phase 1: Baseline
    if phase in (None, 1):
        result1, elapsed1 = await run_phase1()

    # Phase 2+: Multi-agent fan-out + evaluator + improvement loop
    if phase in (None, 2):
        result2 = await run_phase2()

    # Phase 4: Dashboard
    if phase is None:
        run_dashboard()

    # Phase 5: Log analysis
    if phase is None:
        run_logs()
        print_write_up()

    console.rule("[bold green]Pipeline Complete")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Open dashboard/board_dashboard.html in your browser")
    console.print("  2. Review outputs/prds/board_prd.md for the PRD")
    console.print("  3. Check outputs/prds/evaluation_iter*.json for arch scores")
    console.print("  4. Inspect logs/agent_runs.jsonl for full execution trace")


if __name__ == "__main__":
    asyncio.run(main())
