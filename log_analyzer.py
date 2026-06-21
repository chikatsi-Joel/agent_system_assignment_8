"""
Log Analyzer — reads agent_runs.jsonl and produces a structured analysis report.

Answers:
  - Which agent was slowest?
  - Where did errors occur?
  - What was the total token cost?
  - How does fan-out compare to sequential?
  - What patterns emerge from the improvement loop?
"""
import json
from pathlib import Path
from config import LOGS_DIR, OUTPUTS_DIR
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def analyze() -> dict:
    log_path = LOGS_DIR / "agent_runs.jsonl"
    if not log_path.exists():
        console.print("[red]No log file found. Run the pipeline first.[/red]")
        return {}

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    records = [json.loads(l) for l in lines if l.strip()]

    # Group by agent
    by_agent: dict[str, list] = {}
    for r in records:
        name = r.get("agent", "unknown")
        by_agent.setdefault(name, []).append(r)

    # Per-agent stats
    agent_stats = {}
    for name, calls in by_agent.items():
        successes = [c for c in calls if c.get("status") == "success"]
        errors = [c for c in calls if c.get("status") == "error"]
        elapsed = [c.get("elapsed_s", 0) for c in successes]
        in_tok = sum(c.get("input_tokens", 0) for c in successes)
        out_tok = sum(c.get("output_tokens", 0) for c in successes)
        agent_stats[name] = {
            "calls": len(calls),
            "successes": len(successes),
            "errors": len(errors),
            "avgElapsed": round(sum(elapsed) / len(elapsed), 2) if elapsed else 0,
            "maxElapsed": round(max(elapsed), 2) if elapsed else 0,
            "totalInputTokens": in_tok,
            "totalOutputTokens": out_tok,
            "estimatedCostUSD": round((in_tok / 1_000_000) * 3 + (out_tok / 1_000_000) * 15, 4),
        }

    # Phase timing (orchestrator logs)
    orchestrator_events = by_agent.get("Orchestrator", [])
    phase_times = {e.get("phase"): e.get("duration_s") for e in orchestrator_events if "phase" in e}

    # Token totals
    total_input = sum(s["totalInputTokens"] for s in agent_stats.values())
    total_output = sum(s["totalOutputTokens"] for s in agent_stats.values())
    total_cost = sum(s["estimatedCostUSD"] for s in agent_stats.values())
    total_calls = len([r for r in records if r.get("status") == "success"])
    error_count = len([r for r in records if r.get("status") == "error"])

    report = {
        "totalCalls": len(records),
        "successfulCalls": total_calls,
        "errorCount": error_count,
        "errorRate": round(error_count / len(records), 3) if records else 0,
        "totalInputTokens": total_input,
        "totalOutputTokens": total_output,
        "estimatedTotalCostUSD": round(total_cost, 4),
        "agentStats": agent_stats,
        "phaseTimings": phase_times,
        "bottleneck": max(agent_stats, key=lambda k: agent_stats[k]["avgElapsed"]) if agent_stats else None,
        "mostExpensiveAgent": max(agent_stats, key=lambda k: agent_stats[k]["estimatedCostUSD"]) if agent_stats else None,
    }

    out = OUTPUTS_DIR / "prds" / "log_analysis.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    _print_report(report)
    return report


def _print_report(r: dict):
    console.rule("[bold yellow]Log Analysis Report")

    table = Table(title="Agent Performance", box=box.ROUNDED, style="slate")
    table.add_column("Agent", style="cyan")
    table.add_column("Calls", justify="right")
    table.add_column("Errors", justify="right", style="red")
    table.add_column("Avg Elapsed (s)", justify="right")
    table.add_column("Input Tokens", justify="right")
    table.add_column("Output Tokens", justify="right")
    table.add_column("Est. Cost $", justify="right", style="green")

    for name, s in r["agentStats"].items():
        table.add_row(
            name,
            str(s["calls"]),
            str(s["errors"]),
            str(s["avgElapsed"]),
            f'{s["totalInputTokens"]:,}',
            f'{s["totalOutputTokens"]:,}',
            f'${s["estimatedCostUSD"]:.4f}',
        )

    console.print(table)

    console.print(f"\n[bold]Summary[/bold]")
    console.print(f"  Total calls:        {r['totalCalls']}")
    console.print(f"  Success rate:       {(1-r['errorRate'])*100:.1f}%")
    console.print(f"  Total input tokens: {r['totalInputTokens']:,}")
    console.print(f"  Total output tokens:{r['totalOutputTokens']:,}")
    console.print(f"  Est. total cost:    [green]${r['estimatedTotalCostUSD']:.4f}[/green]")
    console.print(f"  Bottleneck agent:   [yellow]{r.get('bottleneck','?')}[/yellow]")
    console.print(f"  Phase timings:      {r.get('phaseTimings',{})}")
