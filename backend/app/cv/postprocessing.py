"""
Postprocessing: confidence scoring, duplicate suppression, and unit
calibration -- converting raw pixel-space detections into the values that
go directly into the final FloorPlan document.

Implements docs/DETECTION_PIPELINE.md Section 6 (confidence scoring) and
Section 8 (postprocessing/cleanup/unit calibration). Wall merging and
room-area filtering already happen inside detector.py itself (they're
prerequisite structural steps, not cleanup passes -- see detector.py's
module docstring for that boundary rationale); this module covers what's
left: scoring, cross-element association, deduplication, and calibration.
"""
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from app.cv.detector import (
    OpeningDetection,
    RoomCandidate,
    StairCandidate,
    WallCandidate,
    _segment_length,
)

# Tier 2 (classical heuristic) confidence ceiling for door/window/stair
# detections -- deliberately conservative per Section 6, since a heuristic
# detection is structurally plausible but meaningfully less reliable than a
# trained detector's own score would be.
TIER2_OPENING_CONFIDENCE_WITH_SWING = 0.55
TIER2_OPENING_CONFIDENCE_NO_SWING = 0.45
TIER2_STAIR_CONFIDENCE = 0.5

DEFAULT_ROOM_CONFIDENCE = 0.7  # fallback when no boundary walls could be matched
ROOM_BOUNDARY_MATCH_TOLERANCE_PX = 12.0

# Fallback calibration assumption when no OCR-matched dimension is found
# (Section 8): a plausible default overall building width, in the document's
# units. This is a deliberately visible, documented guess -- never presented
# as a confident measurement.
FALLBACK_ASSUMED_WIDTH_UNITS = 30.0


# --- Confidence scoring (Section 6) ------------------------------------------


def score_wall_confidence(wall: WallCandidate) -> float:
    """
    Confidence from how much of the wall's own length is actually backed by
    detected Hough-line evidence (total_hough_votes is the sum of merged
    segment lengths, which can be less than the wall's full start-to-end
    span if openings/gaps were bridged). A wall built from consistent,
    near-complete line evidence scores higher than one stitched together
    from sparse fragments.
    """
    wall_length = _segment_length(*wall.start, *wall.end)
    if wall_length <= 0:
        return 0.5
    coverage_ratio = min(1.0, wall.total_hough_votes / wall_length)
    return round(0.5 + 0.5 * coverage_ratio, 3)


def associate_room_boundary_walls(rooms: List[RoomCandidate], walls: List[WallCandidate]) -> None:
    """
    Mutates each room's `boundary_wall_ids` in place: for each edge of the
    room's polygon, find the wall whose centerline it most plausibly runs
    along (same orientation, small perpendicular distance), per Section 6's
    "how completely its boundary is composed of detected walls" rule.
    """
    for room in rooms:
        matched_ids: List[str] = []
        polygon = room.polygon_px
        n = len(polygon)
        for i in range(n):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % n]
            edge_orientation = "horizontal" if abs(p1[1] - p2[1]) < abs(p1[0] - p2[0]) else "vertical"
            edge_fixed = (p1[1] + p2[1]) / 2 if edge_orientation == "horizontal" else (p1[0] + p2[0]) / 2

            best_wall: Optional[WallCandidate] = None
            best_distance = ROOM_BOUNDARY_MATCH_TOLERANCE_PX
            for wall in walls:
                if wall.orientation != edge_orientation:
                    continue
                wall_fixed = (wall.start[1] + wall.end[1]) / 2 if edge_orientation == "horizontal" else (wall.start[0] + wall.end[0]) / 2
                distance = abs(wall_fixed - edge_fixed)
                if distance < best_distance:
                    best_distance = distance
                    best_wall = wall

            if best_wall is not None and best_wall.id not in matched_ids:
                matched_ids.append(best_wall.id)

        room.boundary_wall_ids = matched_ids


def score_room_confidence(room: RoomCandidate, walls_by_id: dict) -> float:
    """Mean confidence of the room's matched boundary walls, per Section 6."""
    if not room.boundary_wall_ids:
        return DEFAULT_ROOM_CONFIDENCE
    scores = [
        score_wall_confidence(walls_by_id[wid])
        for wid in room.boundary_wall_ids
        if wid in walls_by_id
    ]
    if not scores:
        return DEFAULT_ROOM_CONFIDENCE
    return round(float(np.mean(scores)), 3)


def score_opening_confidence(opening: OpeningDetection) -> float:
    """Tier 2 fixed ceiling, per Section 6 -- slightly higher when a swing/leaf line was found."""
    return TIER2_OPENING_CONFIDENCE_WITH_SWING if opening.swing_detected else TIER2_OPENING_CONFIDENCE_NO_SWING


def score_stair_confidence(_stair: StairCandidate) -> float:
    """Tier 2 fixed ceiling, per Section 6."""
    return TIER2_STAIR_CONFIDENCE


# --- Duplicate suppression (Section 8) ---------------------------------------


def suppress_duplicate_openings(openings: List[OpeningDetection]) -> List[OpeningDetection]:
    """
    Collapses openings on the same wall whose position+width ranges
    overlap significantly into a single detection (highest-confidence
    kept), per Section 8's door/window non-max suppression step. Not
    expected to trigger often given detector.py's wall-clustering fix, but
    kept as a defensive/general-purpose safeguard per the design doc.
    """
    by_wall: dict = {}
    for opening in openings:
        by_wall.setdefault(opening.wall_id, []).append(opening)

    kept: List[OpeningDetection] = []
    for wall_openings in by_wall.values():
        wall_openings_sorted = sorted(wall_openings, key=lambda o: o.position)
        suppressed_indices = set()
        for i in range(len(wall_openings_sorted)):
            if i in suppressed_indices:
                continue
            for j in range(i + 1, len(wall_openings_sorted)):
                if j in suppressed_indices:
                    continue
                a, b = wall_openings_sorted[i], wall_openings_sorted[j]
                if abs(a.position - b.position) < 0.05:  # same normalized position => same physical opening
                    score_a = score_opening_confidence(a)
                    score_b = score_opening_confidence(b)
                    suppressed_indices.add(j if score_a >= score_b else i)
        kept.extend(
            wall_openings_sorted[i] for i in range(len(wall_openings_sorted)) if i not in suppressed_indices
        )
    return kept


# --- Unit calibration (Section 8) --------------------------------------------


@dataclass
class CalibrationResult:
    pixels_per_unit: float
    source: str  # "ocr_dimension_match" | "fallback_default_assumption"
    note: Optional[str]


def calibrate_scale(
    dimension_matches: List[Tuple[float, float]],  # (stated_value, pixel_length) pairs
    fallback_reference_px_length: Optional[float],
) -> CalibrationResult:
    """
    Preferred path: median of (pixel_length / stated_value) across every
    OCR-matched dimension. Fallback path: assume `fallback_reference_px_length`
    (typically the longest detected exterior wall run) represents a plausible
    default building width -- a visible, documented guess, never silent.
    """
    if dimension_matches:
        ratios = [
            pixel_length / stated_value
            for stated_value, pixel_length in dimension_matches
            if stated_value > 0
        ]
        if ratios:
            return CalibrationResult(
                pixels_per_unit=float(np.median(ratios)),
                source="ocr_dimension_match",
                note=None,
            )

    if fallback_reference_px_length and fallback_reference_px_length > 0:
        pixels_per_unit = fallback_reference_px_length / FALLBACK_ASSUMED_WIDTH_UNITS
        return CalibrationResult(
            pixels_per_unit=pixels_per_unit,
            source="fallback_default_assumption",
            note=(
                f"No OCR-matched dimension label was found. Scale was estimated by assuming the "
                f"longest detected exterior wall represents {FALLBACK_ASSUMED_WIDTH_UNITS:.0f} units "
                f"-- this is a rough default, not a measurement. Please verify/correct dimensions "
                f"in the 2D editor."
            ),
        )

    # No walls at all to reference -- last-resort identity scale, heavily flagged.
    return CalibrationResult(
        pixels_per_unit=1.0,
        source="fallback_default_assumption",
        note=(
            "No dimension label and no wall geometry were available to establish a scale. "
            "Coordinates are in raw, uncalibrated pixel units and are almost certainly wrong -- "
            "manual correction is required before this FloorPlan can be considered usable."
        ),
    )


def px_to_units(value_px: float, pixels_per_unit: float) -> float:
    if pixels_per_unit <= 0:
        return value_px
    return value_px / pixels_per_unit


def point_px_to_units(point_px: Tuple[float, float], pixels_per_unit: float) -> Tuple[float, float]:
    return (px_to_units(point_px[0], pixels_per_unit), px_to_units(point_px[1], pixels_per_unit))
