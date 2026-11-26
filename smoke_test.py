import os
from triage_reader import classify_fault_report, get_openrouter_client
from schemas import FaultTriageResult

ADVERSARIAL_CASES = [
    {
        "id": "MSG-10002",
        "vehicle_alert_code": "NONE",
        "message": "No rush at all, probably nothing, but the brake pedal feels a bit soft and spongy when stopping.",
        "expected_urgency": {"safety_urgent"},
    },
    {
        "id": "MSG-10048",
        "vehicle_alert_code": "ABS_w002",
        "message": "Happy to wait until next month, just saw ABS_w002 pop up briefly.",
        "expected_urgency": {"safety_urgent"},
    },
    {
        "id": "MSG-10068",
        "vehicle_alert_code": "NONE",
        "message": "Not dramatic, just annoying: driver wiper stalls mid-sweep in the rain.",
        "expected_urgency": {"safety_urgent"},
    },
    {
        "id": "MSG-10297",
        "vehicle_alert_code": "ABS_w002",
        "message": "Customer reports ABS_w002 appeared on highway and brake feel started to...",
        "expected_urgency": {"safety_urgent"},
    },
    {
        "id": "MSG-10021",
        "vehicle_alert_code": "NONE",
        "message": "Charge port latch is acting up and won't always click shut on first...",
        "expected_urgency": {"routine", "soon"},
    },
]


def run_offline_validator_checks() -> None:
    """Verify Pydantic safety overrides without making network calls."""
    r1 = FaultTriageResult(
        mechanical_risk="Reduced hydraulic braking pressure.",
        urgency="routine",
        fix_path="Inspect brake lines.",
        vehicle_alert_code="ABS_w002",
    )
    assert r1.urgency == "safety_urgent", f"Expected safety_urgent, got {r1.urgency}"

    r2 = FaultTriageResult(
        mechanical_risk="Soft brake pedal indicates possible air or leak in hydraulic circuit.",
        urgency="soon",
        fix_path="Bleed and inspect brakes.",
        vehicle_alert_code="NONE",
    )
    assert r2.urgency == "safety_urgent", f"Expected safety_urgent, got {r2.urgency}"

    r3 = FaultTriageResult(
        mechanical_risk="Wiper stalls mid-sweep in forward line of sight.",
        urgency="routine",
        fix_path="Inspect wiper motor.",
        vehicle_alert_code="NONE",
    )
    assert r3.urgency == "safety_urgent", f"Expected safety_urgent, got {r3.urgency}"

    r4 = FaultTriageResult(
        mechanical_risk="Charge port latch misalignment.",
        urgency="routine",
        fix_path="Adjust charge port latch.",
        vehicle_alert_code="NONE",
    )
    assert r4.urgency == "routine", f"Expected routine, got {r4.urgency}"
    print("Offline Pydantic validator checks: PASSED (4/4)")


def run_live_smoke_tests() -> None:
    client = get_openrouter_client()
    for case in ADVERSARIAL_CASES:
        report = {
            "id": case["id"],
            "vehicle_alert_code": case["vehicle_alert_code"],
            "message": case["message"],
        }
        result = classify_fault_report(client, report)
        ok = result.urgency in case["expected_urgency"]
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {case['id']}: urgency={result.urgency} | {result.mechanical_risk}")
        if not ok:
            raise AssertionError(
                f"{case['id']} expected {case['expected_urgency']}, got {result.urgency}"
            )
    print("Live OpenRouter smoke tests: PASSED (5/5)")


if __name__ == "__main__":
    run_offline_validator_checks()
    if os.getenv("OPENROUTER_API_KEY"):
        run_live_smoke_tests()
    else:
        print("Skipping live OpenRouter smoke tests: OPENROUTER_API_KEY is not set.")
