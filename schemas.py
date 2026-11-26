from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator

CRITICAL_SAFETY_CODES = {
    "BRK_a001",
    "BRK_w003",
    "ABS_w002",
    "ESP_w003",
    "EPAS_a191",
    "EPAS_w202",
}

BRAKE_STEERING_KEYWORDS = (
    "soft brake",
    "spongy brake",
    "sinking brake",
    "brake pedal",
    "grinding when braking",
    "steering wheel tugging",
    "steering wheel pulling",
    "heavy steering",
)

WIPER_HAZARD_KEYWORDS = (
    "wiper stalls mid-sweep",
    "stalls mid-sweep",
    "fails to park",
    "mid-sweep",
)


class FaultTriageResult(BaseModel):
    """Structured triage output with deterministic safety overrides."""

    mechanical_risk: str = Field(
        description="One concise sentence explaining the physical mechanical risk."
    )
    urgency: Literal["safety_urgent", "soon", "routine"]
    fix_path: str = Field(
        description="Recommended service or diagnostic action."
    )
    vehicle_alert_code: Optional[str] = Field(
        default=None,
        description="Echoed vehicle alert code from the report, if present.",
    )
    source_text: Optional[str] = Field(
        default=None,
        description="Optional report text used for deterministic safety verification.",
    )

    @model_validator(mode="after")
    def enforce_safety_overrides(self) -> "FaultTriageResult":
        """Enforce critical safety codes, wiper-parking, and soft-brake rules."""
        code = (self.vehicle_alert_code or "").strip()
        if code in CRITICAL_SAFETY_CODES:
            self.urgency = "safety_urgent"
            return self

        combined = f"{self.mechanical_risk} {self.source_text or ''}".lower()
        if any(kw in combined for kw in BRAKE_STEERING_KEYWORDS):
            self.urgency = "safety_urgent"
            return self

        if any(kw in combined for kw in WIPER_HAZARD_KEYWORDS):
            self.urgency = "safety_urgent"
            return self

        return self
