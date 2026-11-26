import json
import os
import re
from dotenv import load_dotenv
from openai import OpenAI
from schemas import FaultTriageResult

load_dotenv()

DEFAULT_FREE_MODEL = "openrouter/free"

SYSTEM_PROMPT = """
You are triaging overnight Tesla vehicle fault reports. Classify every message into one of three urgency tags: "safety_urgent", "soon", or "routine".

CRITICAL SAFETY RULES:
1. Ignore customer tone completely. Phrases like "no rush at all," "not dramatic," "happy to wait," or "probably nothing" carry zero weight.
2. Always assign "safety_urgent" if vehicle_alert_code is one of the six critical safety codes:
   - BRK_a001, BRK_w003, ABS_w002, ESP_w003, EPAS_a191, EPAS_w202
3. Always assign "safety_urgent" if the message describes physical brake or steering symptoms (soft, spongy, or sinking brake pedal; grinding when braking; steering wheel tugging/pulling; heavy steering), even when vehicle_alert_code is "NONE".
4. Do NOT assign "safety_urgent" for dramatic words on non-safety systems (heaters, charge ports, app/screen glitches, or noisy wipers) UNLESS a wiper stalls mid-sweep or fails to park out of the driver's forward line of sight ("safety_urgent").
5. Truncated / cut-off notes: Evaluate all visible text and alert codes. If any safety code, brake/steering symptom, or forward-visibility hazard appears before the cutoff—or if the cutoff interrupts a description of brake/steering feel—assign "safety_urgent". Otherwise, classify by the confirmed subsystem.

First explain the physical mechanical risk in one concise sentence, then assign urgency and fix_path.
Return valid JSON with keys: "mechanical_risk", "urgency", "fix_path".
""".strip()


def get_openrouter_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENROUTER_API_KEY in environment or .env file.")

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/imamfatah-idstar/morning-fault-queue",
            "X-Title": "Morning Fault Queue Triage",
        },
    )


def _extract_json_payload(text: str) -> dict:
    """Extract a JSON object from raw model text (handles markdown code fences)."""
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if brace_match:
            cleaned = brace_match.group(0)
    return json.loads(cleaned)


def classify_fault_report(client: OpenAI, report: dict) -> FaultTriageResult:
    model = os.getenv("OPENROUTER_MODEL", DEFAULT_FREE_MODEL)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(report, ensure_ascii=False)},
    ]

    result: FaultTriageResult
    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            temperature=0.0,
            messages=messages,
            response_format=FaultTriageResult,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("Empty parsed response from structured output endpoint.")
        result = parsed
    except Exception:
        # Fallback for free-tier models that do not support strict json_schema response_format
        completion = client.chat.completions.create(
            model=model,
            temperature=0.0,
            messages=messages,
        )
        raw_content = completion.choices[0].message.content or ""
        payload = _extract_json_payload(raw_content)
        result = FaultTriageResult.model_validate(payload)

    # Re-validate with report's alert code and message text so deterministic
    # safety overrides always apply even if the model omitted them.
    return FaultTriageResult(
        mechanical_risk=result.mechanical_risk,
        urgency=result.urgency,
        fix_path=result.fix_path,
        vehicle_alert_code=report.get("vehicle_alert_code") or result.vehicle_alert_code,
        source_text=report.get("message") or result.source_text,
    )
