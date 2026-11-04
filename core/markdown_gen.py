"""
Markdown generators for dual-representation artifacts.
Generates human-readable analysis.md and plan.md alongside structured JSON.
"""
from typing import Dict, List, Any


def generate_analysis_md(context_data: dict, output_path: str):
    """Generate analysis.md from context.json data."""
    lines = []
    lines.append(f"# Analysis Report")
    lines.append(f"")
    lines.append(f"## Issue Summary")
    lines.append(f"")
    lines.append(f"{context_data.get('issue_summary', 'No summary available')}")
    lines.append(f"")
    lines.append(f"## Affected Files")
    lines.append(f"")
    for f in context_data.get('affected_files', []):
        lines.append(f"- {f}")
    if not context_data.get('affected_files'):
        lines.append(f"*None identified*")
    lines.append(f"")
    lines.append(f"## Required Changes")
    lines.append(f"")
    for change in context_data.get('required_changes', []):
        lines.append(f"- {change}")
    if not context_data.get('required_changes'):
        lines.append(f"*None identified*")
    lines.append(f"")
    lines.append(f"## Extracted Symbols")
    lines.append(f"")
    lines.append(f"| Name | Type | File | Line |")
    lines.append(f"|------|------|------|------|")
    for sym in context_data.get('extracted_symbols', []):
        lines.append(f"| {sym.get('name', '')} | {sym.get('type', '')} | {sym.get('file', '')} | {sym.get('line', '')} |")
    if not context_data.get('extracted_symbols'):
        lines.append(f"| *None* | *None* | *None* | *None* |")
    lines.append(f"")
    lines.append(f"## Dependency Graph")
    lines.append(f"")
    dep_graph = context_data.get('dependency_graph', {})
    if dep_graph:
        for node, deps in dep_graph.items():
            lines.append(f"- **{node}**: {', '.join(deps) if deps else 'no dependencies'}")
    else:
        lines.append(f"*No dependencies mapped*")
    lines.append(f"")
    lines.append(f"## Database Schema")
    lines.append(f"")
    db_schema = context_data.get('database_schema')
    if db_schema:
        lines.append(f"```json")
        lines.append(f"{_format_json(db_schema)}")
        lines.append(f"```")
    else:
        lines.append(f"*No database schema introspected*")
    lines.append(f"")
    lines.append(f"## Token Budget")
    lines.append(f"")
    lines.append(f"- Used: {context_data.get('token_budget_used', 0)}")
    lines.append(f"- Remaining: {context_data.get('token_budget_remaining', 0)}")
    lines.append(f"")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def generate_plan_md(plan_data: List[dict], output_path: str):
    """Generate plan.md from plan.json data."""
    lines = []
    lines.append(f"# Resolution Plan")
    lines.append(f"")
    lines.append(f"## Execution Steps")
    lines.append(f"")
    lines.append(f"| Step | Action | Target File | Description | Tokens | Depends On |")
    lines.append(f"|------|--------|-------------|-------------|--------|------------|")
    for step in plan_data:
        step_id = step.get('step_id', '')
        action = step.get('action', '')
        target = step.get('target_file', '')
        desc = step.get('description', '')
        tokens = step.get('estimated_tokens', 0)
        deps = ', '.join(str(d) for d in step.get('depends_on', [])) or '-'
        lines.append(f"| {step_id} | {action} | {target} | {desc} | {tokens} | {deps} |")
    lines.append(f"")
    lines.append(f"## Sign-Off Checklist")
    lines.append(f"")
    lines.append(f"- [ ] Architectural strategy reviewed")
    lines.append(f"- [ ] All affected files identified")
    lines.append(f"- [ ] Token budget approved")
    lines.append(f"- [ ] Workspace boundaries validated")
    lines.append(f"- [ ] Ready to proceed to Stage 3 (Apply)")
    lines.append(f"")
    lines.append(f"## Token Budget")
    lines.append(f"")
    lines.append(f"- Total estimated: {sum(s.get('estimated_tokens', 0) for s in plan_data)}")
    lines.append(f"")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _format_json(data: Any, indent: int = 2) -> str:
    import json
    return json.dumps(data, indent=indent, default=str)
