import argparse
import csv
import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any

from schemas import FaultTriageResult
from triage_reader import classify_fault_report, get_openrouter_client


def load_messages(input_path: Path) -> List[Dict[str, Any]]:
    raw = input_path.read_text(encoding="utf-8")
    if input_path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in raw.splitlines() if line.strip()]
    data = json.loads(raw)
    if isinstance(data, dict) and "messages" in data:
        return data["messages"]
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array of messages in {input_path}")
    return data


def _offline_fallback_classify(report: Dict[str, Any]) -> FaultTriageResult:
    """Deterministic local classification when running with --offline (no API key)."""
    code = (report.get("vehicle_alert_code") or "NONE").strip()
    msg = (report.get("message") or "").lower()

    if any(k in msg for k in ("charge port", "heater", "screen", "app", "cabin", "trim", "usb")):
        urgency = "routine"
        fix_path = "Schedule standard service inspection."
        risk = "Non-safety comfort or convenience subsystem issue."
    elif any(k in msg for k in ("rattle", "sensor", "mirror", "window", "camera")):
        urgency = "soon"
        fix_path = "Schedule diagnostic check at next available slot."
        risk = "Secondary convenience or driver-assist sensor degradation."
    else:
        urgency = "routine"
        fix_path = "Inspect reported component during next service visit."
        risk = "General vehicle maintenance item."

    return FaultTriageResult(
        mechanical_risk=risk,
        urgency=urgency,
        fix_path=fix_path,
        vehicle_alert_code=code,
        source_text=report.get("message", ""),
    )


def verify_csv(output_path: Path, expected_rows: int) -> None:
    with output_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if len(rows) != expected_rows:
        raise AssertionError(f"Expected {expected_rows} rows in {output_path}, found {len(rows)}")

    required_cols = ("id", "urgency", "fix_path")
    for idx, row in enumerate(rows, start=1):
        for col in required_cols:
            val = (row.get(col) or "").strip()
            if not val:
                raise AssertionError(f"Row {idx} has blank '{col}' in {output_path}")
        if row["urgency"] not in {"safety_urgent", "soon", "routine"}:
            raise AssertionError(f"Row {idx} has invalid urgency: {row['urgency']}")
        if row["urgency"] == "safety_urgent":
            fix_lower = row["fix_path"].lower()
            if any(p in fix_lower for p in ("next service", "standard service", "next available")):
                raise AssertionError(
                    f"Row {idx} ({row['id']}) is safety_urgent but has deferred fix_path: {row['fix_path']}"
                )

    print(f"CSV verification PASSED: {len(rows)} rows, 0 blank fields in {output_path}")


def run_batch(
    input_path: Path,
    output_path: Path,
    offline: bool = False,
    delay_seconds: float = 0.0,
) -> None:
    messages = load_messages(input_path)
    if not messages:
        raise ValueError(f"No messages found in {input_path}")

    client = None if offline else get_openrouter_client()
    results = []

    for idx, report in enumerate(messages, start=1):
        msg_id = str(report.get("id", f"ROW-{idx}"))
        if offline:
            triage = _offline_fallback_classify(report)
        else:
            # Simple retry on transient rate limits
            for attempt in range(3):
                try:
                    triage = classify_fault_report(client, report)
                    break
                except Exception as exc:
                    if attempt == 2:
                        raise RuntimeError(f"Failed on {msg_id}: {exc}") from exc
                    time.sleep(2.0 * (attempt + 1))

        results.append(
            {
                "id": msg_id,
                "urgency": triage.urgency,
                "fix_path": triage.fix_path,
            }
        )
        if delay_seconds > 0 and not offline:
            time.sleep(delay_seconds)

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "urgency", "fix_path"])
        writer.writeheader()
        writer.writerows(results)

    print(f"Wrote {len(results)} rows to {output_path}")
    verify_csv(output_path, expected_rows=len(messages))


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-classify overnight Tesla fault reports.")
    parser.add_argument("--input", type=Path, default=Path("overnight_messages.json"))
    parser.add_argument("--output", type=Path, default=Path("triage_results.csv"))
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Run deterministic local classification without calling OpenRouter (for testing).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Optional delay in seconds between API requests.",
    )
    args = parser.parse_args()

    if not args.offline and not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Add it to .env or pass --offline to test locally."
        )

    run_batch(args.input, args.output, offline=args.offline, delay_seconds=args.delay)


if __name__ == "__main__":
    main()
