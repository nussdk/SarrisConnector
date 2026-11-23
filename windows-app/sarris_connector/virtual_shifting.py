"""Virtual shifting engine — ported from SHIFTR's `Calculations.cpp`.

MyWhoosh sends a selected gear ratio (chainring:sprocket, 0.75–5.49). We
calculate the total resistance force (gravity + rolling + drag) at the
current grade/speed, apply the relative gear ratio, and convert the result
into an ANT+ FE-C action (basic resistance, track resistance grade, or
target power) that the :class:`AntMaster` sends to the M2.

No external shifter/controller is needed — MyWhoosh supplies the gear
selection directly.

The math follows SHIFTR's `refs/shiftr/lib/Calculations/src/Calculations.cpp`
and `VirtualShifting.md` (read-only reference clones).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .translator import TranslationAction

# Default gear ratio: 34T chainring / 14T sprocket = 2.4286 (Zwift Gear 12).
DEFAULT_GEAR_RATIO = 34.0 / 14.0

# Zwift virtual gear ratios (chainring:sprocket).
ZWIFT_GEAR_RATIOS = [
    0.75, 0.87, 0.99, 1.11, 1.23, 1.38, 1.53, 1.68, 1.86, 2.04,
    2.22, 2.40, 2.61, 2.82, 3.03, 3.24, 3.49, 3.74, 3.99, 4.24,
    4.54, 4.84, 5.14, 5.49,
]

# Physics constants (SHIFTR defaults).
GRAVITY = 9.81  # m/s^2
ROLLING_RESISTANCE_COEFFICIENT = 0.00415  # asphalt road
WIND_RESISTANCE_COEFFICIENT = 0.51  # kg/m, road bike + touring position
WHEEL_DIAMETER = 0.7  # m


class VirtualShiftingMode:
    BASIC_RESISTANCE = "basic_resistance"   # set_basic_resistance (0-200 = 0-100%)
    TRACK_RESISTANCE = "track_resistance"   # equivalent grade (FTMS sim params)
    TARGET_POWER = "target_power"           # set_target_power (W)


@dataclass
class RiderProfile:
    """Rider + bike parameters used for resistance calculations."""

    total_weight_kg: float = 80.0  # rider + bike
    difficulty_pct: float = 100.0  # 0-200%
    max_resistance_n: float = 200.0  # trainer max force in N (M2 ~200N)


class VirtualShifter:
    """Convert a selected gear ratio into ANT+ FE-C actions.

    :param profile: rider/bike parameters.
    :param mode: one of ``VirtualShiftingMode`` constants.
    """

    def __init__(
        self,
        profile: Optional[RiderProfile] = None,
        mode: str = VirtualShiftingMode.BASIC_RESISTANCE,
    ) -> None:
        self.profile = profile or RiderProfile()
        self.mode = mode
        self.default_gear_ratio = DEFAULT_GEAR_RATIO
        # Live telemetry, updated by the bridge from ANT+ data / FTMS sim params.
        self.grade_pct: float = 0.0
        self.speed_ms: float = 0.0
        self.cadence_rpm: float = 0.0
        self.last_gear_ratio: Optional[float] = None

    # ------------------------------------------------------------------
    # Telemetry updates (called by the bridge)
    # ------------------------------------------------------------------

    def update_grade(self, grade_pct: float) -> None:
        self.grade_pct = grade_pct

    def update_speed(self, speed_ms: float) -> None:
        self.speed_ms = speed_ms

    def update_cadence(self, cadence_rpm: float) -> None:
        self.cadence_rpm = cadence_rpm

    # ------------------------------------------------------------------
    # Physics (ported from SHIFTR Calculations.cpp)
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_gravitational_resistance(total_weight: float, grade: float) -> float:
        return GRAVITY * math.sin(math.atan(grade / 100.0)) * total_weight

    @staticmethod
    def _calculate_rolling_resistance(total_weight: float) -> float:
        return GRAVITY * total_weight * ROLLING_RESISTANCE_COEFFICIENT

    @staticmethod
    def _calculate_wind_resistance(bicycle_speed: float) -> float:
        return 0.5 * WIND_RESISTANCE_COEFFICIENT * (bicycle_speed + 0.0) ** 2

    def _calculate_geared_resistance(
        self, total_weight: float, grade: float, speed: float, gear_ratio: float
    ) -> float:
        relative_ratio = gear_ratio / self.default_gear_ratio

        wind = self._calculate_wind_resistance(speed)
        gravity = self._calculate_gravitational_resistance(total_weight, grade)
        rolling = self._calculate_rolling_resistance(total_weight)

        # Apply difficulty to gravitational and wind resistance.
        difficulty = self.profile.difficulty_pct / 100.0
        gravity = gravity * difficulty
        wind = wind * difficulty

        geared_total = self._calculate_geared_value(gravity + rolling, relative_ratio) + wind
        return geared_total

    @staticmethod
    def _calculate_geared_value(original: float, ratio: float) -> float:
        if original < 0:
            return original * (1.0 / ratio)
        return original * ratio

    @staticmethod
    def _calculate_speed(cadence_rpm: float, wheel_diameter: float, gear_ratio: float) -> float:
        return ((cadence_rpm * gear_ratio) * (wheel_diameter * math.pi)) / 60.0

    # ------------------------------------------------------------------
    # Public API: gear selection -> ANT+ actions
    # ------------------------------------------------------------------

    def set_gear_ratio(self, gear_ratio: float) -> list[TranslationAction]:
        """MyWhoosh selected a gear ratio. Return ANT+ FE-C actions to apply."""
        self.last_gear_ratio = gear_ratio
        total_weight = self.profile.total_weight_kg

        speed = self._calculate_speed(self.cadence_rpm, WHEEL_DIAMETER, gear_ratio)
        geared_force_n = self._calculate_geared_resistance(
            total_weight, self.grade_pct, speed, gear_ratio
        )

        if self.mode == VirtualShiftingMode.BASIC_RESISTANCE:
            return self._basic_resistance_actions(geared_force_n)
        if self.mode == VirtualShiftingMode.TRACK_RESISTANCE:
            return self._track_resistance_actions(geared_force_n)
        if self.mode == VirtualShiftingMode.TARGET_POWER:
            return self._target_power_actions(geared_force_n, speed)
        return []

    def _basic_resistance_actions(self, force_n: float) -> list[TranslationAction]:
        max_n = self.profile.max_resistance_n
        if force_n < 0:
            pct = 0.0
        elif max_n > 0 and force_n <= max_n:
            pct = round(force_n / max_n * 200.0)
        else:
            pct = 200.0
        pct = max(0.0, min(100.0, pct / 2.0))  # 0-200 scale -> 0-100%
        return [TranslationAction(kind="resistance", value=pct)]

    def _track_resistance_actions(self, force_n: float) -> list[TranslationAction]:
        # Derive the equivalent grade that would produce this force (gravity only).
        total_weight = self.profile.total_weight_kg
        wind = self._calculate_wind_resistance(self.speed_ms)
        rolling = self._calculate_rolling_resistance(total_weight)
        difficulty = self.profile.difficulty_pct / 100.0
        wind = wind * difficulty

        theoretical_gravity = force_n - wind - rolling
        if total_weight > 0 and GRAVITY > 0:
            # G = atan(asin(F_gravity / W / g)) * 100
            ratio = theoretical_gravity / total_weight / GRAVITY
            ratio = max(-1.0, min(1.0, ratio))
            calculated_grade = (math.degrees(math.asin(ratio)) * 100) - 1.0
        else:
            calculated_grade = 0.0
        return [TranslationAction(kind="grade", value=calculated_grade)]

    def _target_power_actions(self, force_n: float, speed_ms: float) -> list[TranslationAction]:
        if force_n < 0:
            force_n = 0.0
        # Use speed at default gear ratio for the trainer-reported speed.
        trainer_speed = self._calculate_speed(self.cadence_rpm, WHEEL_DIAMETER, self.default_gear_ratio)
        power_w = force_n * trainer_speed
        power_w = max(0.0, power_w)
        return [TranslationAction(kind="target_power", value=round(power_w))]

    def gear_for_index(self, gear_index: int) -> Optional[float]:
        """Map a zero-based gear index to a Zwift gear ratio."""
        if 0 <= gear_index < len(ZWIFT_GEAR_RATIOS):
            return ZWIFT_GEAR_RATIOS[gear_index]
        return None
