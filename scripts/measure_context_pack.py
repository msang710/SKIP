#!/usr/bin/env python3
"""Measure selected record input against a compiled Context Pack."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).with_name("intent_context.py")


def invoke(command: str, args: list[str]) -> tuple[int, dict]:
    process = subprocess.run(
        [sys.executable, str(SCRIPT), command, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{command} returned invalid JSON: {exc}") from exc
    return process.returncode, result


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--record-root")
    command.add_argument("--project", required=True)
    command.add_argument("--goal")
    command.add_argument("--artifacts")
    command.add_argument("--stage", required=True)
    command.add_argument("--now", action="store_true")
    command.add_argument("--date")
    command.add_argument("--max-chars", type=int, default=12_000)
    return command


def main() -> int:
    options = parser().parse_args()
    shared = ["--project", options.project]
    for flag, value in (
        ("--record-root", options.record_root),
        ("--goal", options.goal),
        ("--artifacts", options.artifacts),
        ("--date", options.date),
    ):
        if value:
            shared.extend([flag, value])
    if options.now:
        shared.append("--now")
    select_code, manifest = invoke("select", shared)
    if select_code:
        print(json.dumps({"status": "FAIL", "selection": manifest}, ensure_ascii=False, indent=2))
        return select_code
    context_code, pack = invoke(
        "context", [*shared, "--stage", options.stage, "--max-chars", str(options.max_chars)]
    )
    if context_code:
        print(json.dumps({"status": "FAIL", "selection": manifest, "context": pack}, ensure_ascii=False, indent=2))
        return context_code
    metrics = pack["metrics"]
    input_chars = metrics["selected_input_chars"]
    input_bytes = metrics["selected_input_bytes"]
    expansion_paths = sorted({item["path"] for item in pack["required_expansions"] if item.get("path")})
    baseline_reads = metrics["selected_document_count"]
    candidate_reads = len(expansion_paths)
    report = {
        "status": "PASS",
        "project_id": pack["selection"]["project_id"],
        "goal": pack["selection"]["goal"],
        "stage": pack["stage"],
        "semantic": {
            "context_status": pack["status"],
            "review_verdict": pack["review_verdict"],
            "implementation_gate": pack["implementation_gate"],
            "source_verification": pack["selection"]["source_verification"],
        },
        "baseline": {
            "documents": manifest["documents"],
            "chars": input_chars,
            "bytes": input_bytes,
            "document_count": metrics["selected_document_count"],
        },
        "candidate": {
            "chars": metrics["pack_chars"],
            "bytes": metrics["pack_bytes"],
            "required_expansions": pack["required_expansions"],
            "agent_document_reads": candidate_reads,
        },
        "reduction": {
            "chars_percent": round((1 - metrics["pack_chars"] / input_chars) * 100, 2) if input_chars else 0,
            "bytes_percent": round((1 - metrics["pack_bytes"] / input_bytes) * 100, 2) if input_bytes else 0,
            "chars_hypothesis_50_percent": metrics["pack_chars"] <= input_chars * 0.5,
            "bytes_hypothesis_60_percent": metrics["pack_bytes"] <= input_bytes * 0.4,
            "document_reads_percent": round((1 - candidate_reads / baseline_reads) * 100, 2) if baseline_reads else 0,
            "document_reads_hypothesis_60_percent": candidate_reads <= baseline_reads * 0.4,
        },
        "exact_tokens": "EVIDENCE_PENDING",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
