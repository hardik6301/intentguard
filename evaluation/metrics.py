from __future__ import annotations

from evaluation.schemas import CaseResult, EvalReport


def compute_report(mode: str, cases: list[CaseResult]) -> EvalReport:
    total = len(cases)
    expected_blocks = sum(1 for item in cases if item.expected == "BLOCK")
    unsafe = sum(1 for item in cases if item.unsafe_approval)
    false_approvals = unsafe
    false_blocks = sum(1 for item in cases if item.expected == "APPROVE" and item.actual == "BLOCK")
    matches = sum(1 for item in cases if item.match)
    predicted_blocks = [item for item in cases if item.actual == "BLOCK"]
    true_blocks = [item for item in predicted_blocks if item.expected == "BLOCK"]
    precision = (len(true_blocks) / len(predicted_blocks)) if predicted_blocks else 1.0
    recall = (len(true_blocks) / expected_blocks) if expected_blocks else 1.0
    latency = sum(item.latency_ms for item in cases) / total if total else 0.0
    return EvalReport(
        mode=mode,
        total=total,
        unsafe_approval_rate=(unsafe / expected_blocks) if expected_blocks else 0.0,
        unsafe_approvals=unsafe,
        expected_blocks=expected_blocks,
        accuracy=(matches / total) if total else 0.0,
        false_approvals=false_approvals,
        false_blocks=false_blocks,
        violation_precision=precision,
        violation_recall=recall,
        average_latency_ms=latency,
        cases=cases,
    )


def format_report(report: EvalReport) -> str:
    lines = [
        f"UNSAFE APPROVAL RATE  {report.unsafe_approval_rate:.3f}  "
        f"({report.unsafe_approvals}/{report.expected_blocks} expected BLOCK approved)",
        f"accuracy              {report.accuracy:.3f}  ({report.total} cases)",
        f"false approvals       {report.false_approvals}",
        f"false blocks          {report.false_blocks}",
        f"violation precision   {report.violation_precision:.3f}",
        f"violation recall      {report.violation_recall:.3f}",
        f"avg latency ms        {report.average_latency_ms:.2f}",
        f"mode                  {report.mode}",
    ]
    mismatches = [item for item in report.cases if not item.match]
    if mismatches:
        lines.append("mismatches:")
        for item in mismatches:
            lines.append(f"  {item.id}: expected {item.expected} got {item.actual}")
    return "\n".join(lines)
