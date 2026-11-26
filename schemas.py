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

DEFERRED_FIX_PHRASES = (
    "next service",
    "standard service",
    "next available",
    "when convenient",
    "routine",
)

URGENT_BRAKE_FIX = (
    "HOLD VEHICLE / DO NOT DRIVE: Immediate bay dispatch — inspect hydraulic "
    "brake system, fluid level, booster, and ABS/ESP fault codes before release."
)
URGENT_STEERING_FIX = (
    "HOLD VEHICLE / DO NOT DRIVE: Immediate bay dispatch — inspect EPAS "
    "steering rack, power assist, and steering linkage integrity before release."
)
URGENT_WIPER_FIX = (
    "HOLD FOR IMMEDIATE SAFETY REPAIR: Priority bay dispatch — inspect wiper "
    "motor, linkage, and park switch to restore forward visibility before release."
)
URGENT_GENERIC_FIX = (
    "HOLD VEHICLE / IMMEDIATE BAY DISPATCH: Perform urgent safety inspection "
    "and resolve critical fault before release."
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
        """Enforce critical safety codes, wiper-parking, soft-brake rules, and urgent fix_path."""
        code = (self.vehicle_alert_code or "").strip()
        combined = f"{self.mechanical_risk} {self.source_text or ''}".lower()

        is_brake = code in {"BRK_a001", "BRK_w003", "ABS_w002", "ESP_w003"} or any(
            kw in combined
            for kw in ("soft brake", "spongy brake", "sinking brake", "brake pedal", "grinding when braking")
        )
        is_steering = code in {"EPAS_a191", "EPAS_w202"} or any(
            kw in combined for kw in ("steering wheel tugging", "steering wheel pulling", "heavy steering")
        )
        is_wiper = any(kw in combined for kw in WIPER_HAZARD_KEYWORDS)

        if code in CRITICAL_SAFETY_CODES or is_brake or is_steering or is_wiper:
            self.urgency = "safety_urgent"

        if self.urgency == "safety_urgent":
            fix_lower = self.fix_path.lower()
            if not fix_lower.strip() or any(p in fix_lower for p in DEFERRED_FIX_PHRASES):
                if is_steering:
                    self.fix_path = URGENT_STEERING_FIX
                elif is_wiper:
                    self.fix_path = URGENT_WIPER_FIX
                elif is_brake:
                    self.fix_path = URGENT_BRAKE_FIX
                else:
                    self.fix_path = URGENT_GENERIC_FIX

        return self
