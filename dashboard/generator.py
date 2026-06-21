"""
Dashboard generator — reads synthesis + evaluation from memory and produces
a self-contained HTML file for the Board of Directors.
"""
import json
from pathlib import Path
from config import OUTPUTS_DIR, DASHBOARD_DIR
from agents.base_agent import memory


def generate() -> Path:
    mem = memory.read()
    synthesis = mem.get("synthesis_v2") or mem.get("synthesis", {})
    eval1 = mem.get("evaluation_iter1", {})
    eval2 = mem.get("evaluation_iter2", {})
    run = mem.get("orchestrator_run", {})

    # Gather per-bank insight data
    from config import BANKS
    insights = {b: mem.get(f"insight_{b}", {}) for b in BANKS}

    payload = {
        "synthesis": synthesis,
        "eval1": eval1,
        "eval2": eval2,
        "insights": insights,
        "run": run,
    }

    html = _build_html(payload)
    out = DASHBOARD_DIR / "board_dashboard.html"
    out.write_text(html, encoding="utf-8")
    return out


def _build_html(p: dict) -> str:
    s = p["synthesis"]
    eval1 = p["eval1"]
    eval2 = p["eval2"]
    insights = p["insights"]
    run = p["run"]

    score1 = eval1.get("overallScore", "—")
    score2 = eval2.get("overallScore", "—")
    readiness = eval2.get("productionReadiness", eval1.get("productionReadiness", "—"))
    industry_risk = s.get("industryRiskRating", "—")
    exec_summary = s.get("executiveSummary", "Analysis in progress.")
    board_narrative = s.get("boardNarrative", "")
    total_time = run.get("totalDuration_s", "—")

    # Risk heatmap data
    heatmap = s.get("riskHeatmap", {})
    risk_types = ["credit", "market", "liquidity", "operational", "regulatory"]
    bank_labels = json.dumps(list(heatmap.keys()))
    heatmap_datasets = json.dumps([
        {
            "label": rt.capitalize(),
            "data": [heatmap.get(b, {}).get(rt, 3) for b in heatmap],
            "backgroundColor": [
                "rgba(239,68,68,0.7)", "rgba(249,115,22,0.7)", "rgba(234,179,8,0.7)",
                "rgba(99,102,241,0.7)", "rgba(20,184,166,0.7)"
            ][i],
        }
        for i, rt in enumerate(risk_types)
    ])

    # Sentiment matrix
    sent_matrix = s.get("sentimentMatrix", {})
    sent_labels = json.dumps(list(sent_matrix.keys()))
    sent_scores = json.dumps([v.get("score", 0) for v in sent_matrix.values()])
    sent_labels_display = json.dumps([v.get("label", "") for v in sent_matrix.values()])

    # Architecture eval dimensions
    dims = eval2.get("dimensions") or eval1.get("dimensions", {})
    dim_labels = json.dumps(list(dims.keys()))
    dim_scores = json.dumps([v.get("score", 0) for v in dims.values()])

    # Top improvements
    improvements = eval1.get("topImprovements", [])
    improvements_html = "".join(
        f'<li class="mb-2"><span class="font-semibold text-indigo-300">P{imp.get("priority","?")}:</span> '
        f'{imp.get("change","")} <span class="text-xs text-slate-400">({imp.get("effort","")} effort, +{imp.get("expectedScoreGain",0)} pts)</span></li>'
        for imp in improvements[:5]
    )

    # Consensus themes
    themes = s.get("consensusThemes", [])
    themes_html = "".join(
        f'<div class="bg-slate-700 rounded p-3 mb-2">'
        f'<span class="font-semibold text-teal-300">{t.get("theme","")}</span>'
        f'<p class="text-sm text-slate-300 mt-1">{t.get("description","")}</p>'
        f'<p class="text-xs text-slate-500 mt-1">Affects: {", ".join(t.get("banksAffected",[]))}</p>'
        f'</div>'
        for t in themes
    )

    # Top risks table
    top_risks = s.get("topRisksAcrossIndustry", [])
    risks_html = "".join(
        f'<tr class="border-b border-slate-700">'
        f'<td class="py-2 pr-4 text-slate-200">{r.get("risk","")}</td>'
        f'<td class="py-2 pr-4"><span class="px-2 py-0.5 rounded text-xs font-semibold '
        f'{"bg-red-700" if r.get("severity")=="CRITICAL" else "bg-orange-700" if r.get("severity")=="HIGH" else "bg-yellow-700"}">'
        f'{r.get("severity","")}</span></td>'
        f'<td class="py-2 text-slate-400 text-sm">{", ".join(r.get("affectedBanks",[]))}</td>'
        f'</tr>'
        for r in top_risks
    )

    # Per-bank cards
    bank_cards = ""
    bank_colors = {"jpmorgan": "blue", "bofa": "red", "citi": "yellow", "wells_fargo": "green", "goldman": "purple"}
    for bank_id, ins in insights.items():
        if not ins:
            continue
        color = bank_colors.get(bank_id, "slate")
        sent = ins.get("sentiment", "neutral")
        sent_color = {"positive": "green", "neutral": "yellow", "cautious": "orange", "negative": "red"}.get(sent, "slate")
        strengths = ins.get("keyStrengths", [])[:2]
        weaknesses = ins.get("keyWeaknesses", [])[:2]
        risk_scores = ins.get("riskScores", {})
        max_risk = max(risk_scores.values()) if risk_scores else 0
        max_risk_type = max(risk_scores, key=risk_scores.get) if risk_scores else "—"
        bank_cards += f"""
        <div class="bg-slate-800 border border-slate-600 rounded-xl p-4">
          <div class="flex justify-between items-center mb-3">
            <h3 class="font-bold text-{color}-300">{ins.get("bankName", bank_id)}</h3>
            <span class="px-2 py-0.5 rounded text-xs bg-{sent_color}-800 text-{sent_color}-200">{sent}</span>
          </div>
          <p class="text-xs text-slate-400 mb-3">{ins.get("forwardGuidance","")[:120]}...</p>
          <div class="mb-2">
            <p class="text-xs font-semibold text-green-400 mb-1">Strengths</p>
            {"".join(f'<p class="text-xs text-slate-300">• {s}</p>' for s in strengths)}
          </div>
          <div class="mb-3">
            <p class="text-xs font-semibold text-red-400 mb-1">Risks</p>
            {"".join(f'<p class="text-xs text-slate-300">• {w}</p>' for w in weaknesses)}
          </div>
          <div class="text-xs text-slate-500">Top risk: <span class="text-red-400">{max_risk_type} ({max_risk}/5)</span></div>
        </div>"""

    # PRD recommendations
    prds = s.get("prdRecommendations", [])
    prd_html = "".join(
        f'<div class="flex items-start gap-3 mb-3">'
        f'<span class="shrink-0 mt-0.5 px-2 py-0.5 rounded text-xs font-bold '
        f'{"bg-red-700" if r.get("priority")=="HIGH" else "bg-yellow-700" if r.get("priority")=="MEDIUM" else "bg-slate-600"}">'
        f'{r.get("priority","")}</span>'
        f'<div><p class="font-semibold text-slate-200 text-sm">{r.get("title","")}</p>'
        f'<p class="text-xs text-slate-400">{r.get("rationale","")}</p></div>'
        f'</div>'
        for r in prds[:5]
    )

    readiness_color = {
        "PRODUCTION_READY": "green", "STAGING": "teal", "PROTOTYPE": "yellow", "NOT_READY": "red"
    }.get(readiness, "slate")

    risk_color = {
        "LOW": "green", "MODERATE": "yellow", "ELEVATED": "orange", "HIGH": "red"
    }.get(industry_risk, "slate")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Board Intelligence Dashboard — Q3 2024 Multi-Bank Analysis</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Inter', system-ui, sans-serif; }}
  .glass {{ background: rgba(30,41,59,0.8); backdrop-filter: blur(12px); }}
</style>
</head>
<body class="min-h-screen p-6">

<!-- Header -->
<div class="max-w-7xl mx-auto">
  <div class="flex justify-between items-start mb-8">
    <div>
      <h1 class="text-3xl font-bold text-white">Multi-Bank Intelligence Dashboard</h1>
      <p class="text-slate-400 mt-1">Q3 2024 · JPMorgan · BofA · Citi · Wells Fargo · Goldman Sachs</p>
    </div>
    <div class="text-right">
      <p class="text-xs text-slate-500">Generated by Multi-Agent Pipeline</p>
      <p class="text-xs text-slate-500">Total runtime: {total_time}s</p>
      <p class="text-xs text-slate-500">Pipeline: Scout→Analyst→Writer→Evaluator</p>
    </div>
  </div>

  <!-- KPI Strip -->
  <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
    <div class="glass rounded-xl p-4 border border-slate-700">
      <p class="text-xs text-slate-400">Banks Analyzed</p>
      <p class="text-3xl font-bold text-white mt-1">5</p>
    </div>
    <div class="glass rounded-xl p-4 border border-slate-700">
      <p class="text-xs text-slate-400">Industry Risk</p>
      <p class="text-2xl font-bold text-{risk_color}-400 mt-1">{industry_risk}</p>
    </div>
    <div class="glass rounded-xl p-4 border border-slate-700">
      <p class="text-xs text-slate-400">Arch Score v1</p>
      <p class="text-3xl font-bold text-yellow-400 mt-1">{score1}<span class="text-sm text-slate-500">/10</span></p>
    </div>
    <div class="glass rounded-xl p-4 border border-slate-700">
      <p class="text-xs text-slate-400">Arch Score v2</p>
      <p class="text-3xl font-bold text-green-400 mt-1">{score2}<span class="text-sm text-slate-500">/10</span></p>
    </div>
    <div class="glass rounded-xl p-4 border border-slate-700">
      <p class="text-xs text-slate-400">Prod Readiness</p>
      <p class="text-lg font-bold text-{readiness_color}-400 mt-1">{readiness.replace("_"," ")}</p>
    </div>
  </div>

  <!-- Executive Summary -->
  <div class="glass rounded-xl p-6 border border-slate-700 mb-6">
    <h2 class="text-lg font-semibold text-white mb-3">Executive Summary</h2>
    <p class="text-slate-300 leading-relaxed">{exec_summary}</p>
  </div>

  <!-- Charts Row -->
  <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">

    <!-- Risk Heatmap -->
    <div class="glass rounded-xl p-6 border border-slate-700 md:col-span-2">
      <h2 class="text-lg font-semibold text-white mb-4">Risk Heatmap — Bank × Risk Type (1–5 scale)</h2>
      <canvas id="riskChart" height="220"></canvas>
    </div>

    <!-- Sentiment Matrix -->
    <div class="glass rounded-xl p-6 border border-slate-700">
      <h2 class="text-lg font-semibold text-white mb-4">Sentiment Matrix</h2>
      <canvas id="sentChart" height="220"></canvas>
    </div>
  </div>

  <!-- Architecture Radar -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
    <div class="glass rounded-xl p-6 border border-slate-700">
      <h2 class="text-lg font-semibold text-white mb-4">Architecture Evaluation (v2)</h2>
      <canvas id="radarChart" height="260"></canvas>
    </div>

    <!-- Improvement Loop -->
    <div class="glass rounded-xl p-6 border border-slate-700">
      <h2 class="text-lg font-semibold text-white mb-4">Top Improvement Recommendations</h2>
      <ul class="text-sm text-slate-300">
        {improvements_html or '<li class="text-slate-500">No improvements logged yet.</li>'}
      </ul>
      <div class="mt-4 pt-4 border-t border-slate-700">
        <p class="text-xs text-slate-400">Score progression</p>
        <div class="flex items-center gap-3 mt-2">
          <span class="text-2xl font-bold text-yellow-400">{score1}</span>
          <span class="text-slate-500 text-lg">→</span>
          <span class="text-2xl font-bold text-green-400">{score2}</span>
          <span class="text-sm text-{'green' if isinstance(score2,int) and isinstance(score1,int) and score2>score1 else 'slate'}-400">
            ({'+' if isinstance(score2,int) and isinstance(score1,int) and score2>=score1 else ''}{score2-score1 if isinstance(score2,int) and isinstance(score1,int) else '?'})
          </span>
        </div>
      </div>
    </div>
  </div>

  <!-- Bank Cards -->
  <h2 class="text-xl font-semibold text-white mb-4">Per-Bank Insights</h2>
  <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-6">
    {bank_cards}
  </div>

  <!-- Consensus Themes + Top Risks -->
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
    <div class="glass rounded-xl p-6 border border-slate-700">
      <h2 class="text-lg font-semibold text-white mb-4">Consensus Themes</h2>
      {themes_html or '<p class="text-slate-500">Processing...</p>'}
    </div>
    <div class="glass rounded-xl p-6 border border-slate-700">
      <h2 class="text-lg font-semibold text-white mb-4">Top Industry Risks</h2>
      <table class="w-full text-sm">
        <thead><tr class="text-slate-400 text-xs border-b border-slate-700">
          <th class="text-left py-2 pr-4">Risk</th><th class="text-left py-2 pr-4">Severity</th><th class="text-left py-2">Banks</th>
        </tr></thead>
        <tbody>{risks_html or '<tr><td colspan="3" class="text-slate-500 py-2">Processing...</td></tr>'}</tbody>
      </table>
    </div>
  </div>

  <!-- PRD Recommendations -->
  <div class="glass rounded-xl p-6 border border-slate-700 mb-6">
    <h2 class="text-lg font-semibold text-white mb-4">PRD Recommendations</h2>
    {prd_html or '<p class="text-slate-500">Processing...</p>'}
  </div>

  <!-- Board Narrative -->
  <div class="glass rounded-xl p-6 border border-slate-700 mb-6">
    <h2 class="text-lg font-semibold text-white mb-3">Board Narrative</h2>
    <p class="text-slate-300 leading-relaxed">{board_narrative}</p>
  </div>

  <!-- Verdict -->
  <div class="glass rounded-xl p-6 border border-indigo-700 mb-6 bg-indigo-950/30">
    <h2 class="text-lg font-semibold text-indigo-300 mb-2">Architecture Verdict</h2>
    <p class="text-slate-300">{eval2.get("verdict") or eval1.get("verdict","Evaluation pending.")}</p>
  </div>

  <p class="text-center text-xs text-slate-600 pb-6">
    Financial Intelligence Platform · Multi-Agent Architecture · lecon_8 · 2024
  </p>
</div>

<script>
// Risk Heatmap — Grouped Bar
const riskCtx = document.getElementById('riskChart').getContext('2d');
new Chart(riskCtx, {{
  type: 'bar',
  data: {{ labels: {bank_labels}, datasets: {heatmap_datasets} }},
  options: {{
    responsive: true, plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ min: 0, max: 5, ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }}
    }}
  }}
}});

// Sentiment Bar
const sentCtx = document.getElementById('sentChart').getContext('2d');
new Chart(sentCtx, {{
  type: 'bar',
  data: {{
    labels: {sent_labels},
    datasets: [{{
      label: 'Sentiment Score',
      data: {sent_scores},
      backgroundColor: {sent_scores}.map(v => v > 0.2 ? 'rgba(34,197,94,0.7)' : v < -0.2 ? 'rgba(239,68,68,0.7)' : 'rgba(234,179,8,0.7)'),
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ min: -1, max: 1, ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#1e293b' }} }}
    }}
  }}
}});

// Architecture Radar
const radarCtx = document.getElementById('radarChart').getContext('2d');
new Chart(radarCtx, {{
  type: 'radar',
  data: {{
    labels: {dim_labels},
    datasets: [{{
      label: 'Architecture Score',
      data: {dim_scores},
      backgroundColor: 'rgba(99,102,241,0.25)',
      borderColor: 'rgba(99,102,241,0.9)',
      pointBackgroundColor: 'rgba(99,102,241,1)',
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
    scales: {{
      r: {{
        min: 0, max: 10,
        ticks: {{ color: '#94a3b8', backdropColor: 'transparent' }},
        grid: {{ color: '#1e293b' }},
        pointLabels: {{ color: '#94a3b8', font: {{ size: 10 }} }}
      }}
    }}
  }}
}});
</script>
</body>
</html>"""
