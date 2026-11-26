import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from schemas import FaultTriageResult

load_dotenv()

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
""".strip()


def get_openrouter_client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENROUTER_API_KEY in environment or .env file.")

    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/Imamabdulfatah/morning-fault-queue",
            "X-Title": "Morning Fault Queue Triage",
        },
    )


def classify_fault_report(client: OpenAI, report: dict) -> FaultTriageResult:
    model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")

    completion = client.beta.chat.completions.parse(
        model=model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(report, ensure_ascii=False)},
        ],
        response_format=FaultTriageResult,
    )

    # Pydantic's post-parse @model_validator runs automatically on .parsed
    # to enforce the 6 safety codes, hidden wiper-parking rule, and soft-brake rule.
    return completion.choices[0].message.parsed
