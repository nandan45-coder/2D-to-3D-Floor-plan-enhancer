"""
Core structural detection: walls, rooms, door/window openings, stairs.

Implements docs/DETECTION_PIPELINE.md Sections 3-5. Operates entirely in
working-image pixel space (see preprocessing.py) -- no unit conversion
happens here; that's postprocessing.py's job (Section 8's calibration step).

--- Resolving Prompt 5's flagged open decision on Tier 1 (pretrained object
detector for doors/windows/stairs) ---

Tier 1 (a pretrained YOLOv8n architectural-symbol detector) is NOT
implemented here. Reason: general-purpose pretrained checkpoints (e.g.
COCO-trained YOLOv8n) do not include door/window/stair symbol classes at
all -- COCO's object categories are everyday objects (person, car, chair,
etc.), not 2D architectural drafting symbols. No pretrained checkpoint for
this specific narrow task could be reliably sourced/licensed within this
project's scope, which is exactly the uncertainty Prompt 5 flagged rather
than assumed away. Using a COCO-pretrained model here would not produce
meaningful detections and would add a heavy dependency (ultralytics + model
download) for no real benefit -- worse than the documented Tier 2 fallback,
not better. This module therefore implements Tier 2 (classical heuristics)
as the sole detection strategy for doors/windows/stairs, exactly as
Section 5 designed it to work standalone. The module boundary is kept
separate enough that a real Tier 1 model could be added later without
restructuring this file, should a suitable checkpoint become available.
"""
import math
import uuid
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple

import cv2
import numpy as np

from app.cv import preprocessing

Point = Tuple[float, float]

# --- Tunable constants (pixel space, working-resolution image) -------------

WALL_MORPH_KERNEL_LENGTH = 70  # must exceed the longest non-wall straight run (e.g. stair treads)

HOUGH_THRESHOLD = 40
HOUGH_MIN_LINE_LENGTH = 30
HOUGH_MAX_LINE_GAP = 8

AXIS_ANGLE_TOLERANCE_DEG = 10.0
SAME_LINE_OFFSET_TOLERANCE_PX = 8.0

NOISE_MERGE_TOLERANCE_PX = 6.0
MAX_OPENING_GAP_PX = 160.0

MIN_ROOM_AREA_PX = 2000.0

# Real walls render as thick lines; dimension lines/annotation underlines are
# thin (often 1px) and can otherwise survive the length-based morphology
# filter above if they happen to run the full length of the building. This
# thickness floor is what actually distinguishes the two.
MIN_WALL_THICKNESS_PX = 2.5

STAIR_MIN_SEGMENTS = 3
STAIR_MAX_SEGMENT_LENGTH_PX = 90.0
STAIR_SPACING_TOLERANCE_PX = 6.0
STAIR_MAX_LENGTH_RATIO = 1.8  # longest/shortest tread candidate in a cluster
STAIR_MAX_ALONG_EXTENT_PX = 220.0  # stairs are compact; text rows can span much wider
STAIR_SPACING_REGULARITY_TOLERANCE = 0.5  # max allowed (stdev / median) of consecutive gaps


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _segment_angle_deg(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def _segment_length(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


@dataclass
class RawSegment:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def length(self) -> float:
        return _segment_length(self.x1, self.y1, self.x2, self.y2)

    @property
    def angle_deg(self) -> float:
        return _segment_angle_deg(self.x1, self.y1, self.x2, self.y2)


@dataclass
class OpeningCandidate:
    wall_id: str
    gap_start: Point
    gap_end: Point
    orientation: Literal["horizontal", "vertical"]


@dataclass
class WallCandidate:
    id: str
    start: Point
    end: Point
    orientation: Literal["horizontal", "vertical"]
    thickness_px: float = 4.0
    wall_type: Literal["exterior", "interior"] = "interior"
    segment_count_merged: int = 1
    total_hough_votes: float = 0.0


@dataclass
class RoomCandidate:
    id: str
    polygon_px: List[Point]
    area_px: float
    boundary_wall_ids: List[str] = field(default_factory=list)


@dataclass
class OpeningDetection:
    id: str
    kind: Literal["door", "window"]
    wall_id: str
    position: float
    width_px: float
    swing_detected: bool = False


@dataclass
class StairCandidate:
    id: str
    polygon_px: List[Point]


# --- Wall detection -----------------------------------------------------------


def isolate_wall_mask(binary_image: np.ndarray) -> np.ndarray:
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (WALL_MORPH_KERNEL_LENGTH, 1))
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, WALL_MORPH_KERNEL_LENGTH))

    horiz = cv2.morphologyEx(binary_image, cv2.MORPH_OPEN, horiz_kernel)
    vert = cv2.morphologyEx(binary_image, cv2.MORPH_OPEN, vert_kernel)

    return cv2.bitwise_or(horiz, vert)


def detect_wall_segments(wall_mask: np.ndarray) -> List[RawSegment]:
    lines = cv2.HoughLinesP(
        wall_mask, 1, np.pi / 180,
        threshold=HOUGH_THRESHOLD,
        minLineLength=HOUGH_MIN_LINE_LENGTH,
        maxLineGap=HOUGH_MAX_LINE_GAP,
    )
    if lines is None:
        return []
    return [RawSegment(float(x1), float(y1), float(x2), float(y2)) for (x1, y1, x2, y2) in lines[:, 0, :]]


def detect_fine_segments_for_leaf_search(binary_image: np.ndarray) -> List[RawSegment]:
    """
    A more permissive Hough pass over the full (non-morphology-filtered)
    binary image, specifically for door swing-leaf detection in
    detect_openings(). A door's swing/leaf line is typically much shorter
    than the minimum wall-segment length (HOUGH_MIN_LINE_LENGTH) and would
    be missed entirely if this reused the standard wall-detection
    parameters -- which is a real, meaningful difference, not just a minor
    tuning tweak, since it directly determines door-vs-window classification.
    """
    lines = cv2.HoughLinesP(
        binary_image, 1, np.pi / 180,
        threshold=15, minLineLength=10, maxLineGap=3,
    )
    if lines is None:
        return []
    return [RawSegment(float(x1), float(y1), float(x2), float(y2)) for (x1, y1, x2, y2) in lines[:, 0, :]]


def _classify_orientation(segment: RawSegment) -> Optional[Literal["horizontal", "vertical"]]:
    angle = segment.angle_deg % 180
    if angle <= AXIS_ANGLE_TOLERANCE_DEG or angle >= 180 - AXIS_ANGLE_TOLERANCE_DEG:
        return "horizontal"
    if 90 - AXIS_ANGLE_TOLERANCE_DEG <= angle <= 90 + AXIS_ANGLE_TOLERANCE_DEG:
        return "vertical"
    return None


def _cluster_by_proximity(segments: List[RawSegment], perp_key, tolerance: float) -> List[List[RawSegment]]:
    """
    Groups segments whose perp_key values are within `tolerance` of their
    neighbor in sorted (chained) order -- i.e. real single-linkage proximity
    clustering, not bucket-rounding. Bucket-rounding (e.g. `round(x / tol)`)
    incorrectly splits two genuinely close values that happen to straddle a
    bucket boundary (e.g. 682.0 and 684.3 with tolerance 8 can round to
    different buckets despite being only 2.3px apart) -- this chained
    approach doesn't have that failure mode.
    """
    if not segments:
        return []
    segs_sorted = sorted(segments, key=perp_key)
    groups: List[List[RawSegment]] = [[segs_sorted[0]]]
    for seg in segs_sorted[1:]:
        if abs(perp_key(seg) - perp_key(groups[-1][-1])) <= tolerance:
            groups[-1].append(seg)
        else:
            groups.append([seg])
    return groups


def build_walls(segments: List[RawSegment]) -> Tuple[List[WallCandidate], List[OpeningCandidate]]:
    horiz_segments = [s for s in segments if _classify_orientation(s) == "horizontal"]
    vert_segments = [s for s in segments if _classify_orientation(s) == "vertical"]

    horiz_key = lambda s: (s.y1 + s.y2) / 2
    vert_key = lambda s: (s.x1 + s.x2) / 2

    horiz_groups = _cluster_by_proximity(horiz_segments, horiz_key, SAME_LINE_OFFSET_TOLERANCE_PX)
    vert_groups = _cluster_by_proximity(vert_segments, vert_key, SAME_LINE_OFFSET_TOLERANCE_PX)

    walls: List[WallCandidate] = []
    openings: List[OpeningCandidate] = []

    def _process_group(segs: List[RawSegment], orientation: Literal["horizontal", "vertical"]):
        if orientation == "horizontal":
            segs_sorted = sorted(segs, key=lambda s: min(s.x1, s.x2))
            fixed_coord = float(np.mean([s.y1 for s in segs] + [s.y2 for s in segs]))
        else:
            segs_sorted = sorted(segs, key=lambda s: min(s.y1, s.y2))
            fixed_coord = float(np.mean([s.x1 for s in segs] + [s.x2 for s in segs]))

        def along(seg: RawSegment) -> Tuple[float, float]:
            if orientation == "horizontal":
                return min(seg.x1, seg.x2), max(seg.x1, seg.x2)
            return min(seg.y1, seg.y2), max(seg.y1, seg.y2)

        run_start, run_end = along(segs_sorted[0])
        run_votes = segs_sorted[0].length
        run_count = 1
        pending_gaps: List[Tuple[float, float]] = []

        def flush_run(end_coord: float):
            nonlocal run_start
            if orientation == "horizontal":
                start_pt, end_pt = (run_start, fixed_coord), (end_coord, fixed_coord)
            else:
                start_pt, end_pt = (fixed_coord, run_start), (fixed_coord, end_coord)

            wall_id = _new_id("wall")
            walls.append(WallCandidate(
                id=wall_id, start=start_pt, end=end_pt, orientation=orientation,
                segment_count_merged=run_count, total_hough_votes=run_votes,
            ))
            for gap_a, gap_b in pending_gaps:
                if orientation == "horizontal":
                    g_start, g_end = (gap_a, fixed_coord), (gap_b, fixed_coord)
                else:
                    g_start, g_end = (fixed_coord, gap_a), (fixed_coord, gap_b)
                openings.append(OpeningCandidate(wall_id=wall_id, gap_start=g_start, gap_end=g_end, orientation=orientation))
            pending_gaps.clear()

        for seg in segs_sorted[1:]:
            seg_start, seg_end = along(seg)
            gap = seg_start - run_end

            if gap <= NOISE_MERGE_TOLERANCE_PX:
                run_end = max(run_end, seg_end)
                run_votes += seg.length
                run_count += 1
            elif gap <= MAX_OPENING_GAP_PX:
                pending_gaps.append((run_end, seg_start))
                run_end = max(run_end, seg_end)
                run_votes += seg.length
                run_count += 1
            else:
                flush_run(run_end)
                run_start, run_end = seg_start, seg_end
                run_votes = seg.length
                run_count = 1

        flush_run(run_end)

    for segs in horiz_groups:
        _process_group(segs, "horizontal")
    for segs in vert_groups:
        _process_group(segs, "vertical")

    return walls, openings


def estimate_wall_thickness(wall: WallCandidate, binary_image: np.ndarray) -> float:
    mx = (wall.start[0] + wall.end[0]) / 2
    my = (wall.start[1] + wall.end[1]) / 2
    h, w = binary_image.shape[:2]
    mx_i, my_i = int(round(mx)), int(round(my))

    max_probe = 25
    if wall.orientation == "horizontal":
        thickness = 0
        for dy in range(-max_probe, max_probe + 1):
            y = my_i + dy
            if 0 <= y < h and 0 <= mx_i < w and binary_image[y, mx_i] > 0:
                thickness += 1
    else:
        thickness = 0
        for dx in range(-max_probe, max_probe + 1):
            x = mx_i + dx
            if 0 <= x < w and 0 <= my_i < h and binary_image[my_i, x] > 0:
                thickness += 1

    return float(thickness) if thickness > 0 else 4.0


def classify_exterior_interior(walls: List[WallCandidate]) -> None:
    """
    Mutates each wall's `wall_type` in place. A wall is "exterior" if its own
    fixed (perpendicular) coordinate sits on the building's overall bounding
    extent -- e.g. a vertical wall is exterior if its x sits at the global
    min/max x, regardless of how far its y-range happens to extend. Checking
    both axes indiscriminately (an earlier version of this function did)
    misclassifies an interior wall that merely spans most of the building's
    height/width, which is common in simple rectangular layouts.
    """
    if not walls:
        return
    all_x = [p[0] for w in walls for p in (w.start, w.end)]
    all_y = [p[1] for w in walls for p in (w.start, w.end)]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    tol = SAME_LINE_OFFSET_TOLERANCE_PX * 1.5

    for wall in walls:
        if wall.orientation == "vertical":
            fixed_coord = (wall.start[0] + wall.end[0]) / 2
            on_boundary = abs(fixed_coord - min_x) <= tol or abs(fixed_coord - max_x) <= tol
        else:
            fixed_coord = (wall.start[1] + wall.end[1]) / 2
            on_boundary = abs(fixed_coord - min_y) <= tol or abs(fixed_coord - max_y) <= tol
        wall.wall_type = "exterior" if on_boundary else "interior"


def detect_walls(
    binary_image: np.ndarray,
) -> Tuple[List[WallCandidate], List[OpeningCandidate], List[Tuple[Point, Point]]]:
    """
    Returns (walls, opening_candidates, thin_line_candidates). The third
    list holds runs that were long and straight enough to survive the
    isolation morphology but too thin to be a real wall (filtered by
    MIN_WALL_THICKNESS_PX) -- exactly what a real dimension line looks like
    (long, thin, straight). Rather than simply discarding this filtered-out
    signal, it's returned so the assembly step can offer it to
    ocr_service.associate_dimensions() as candidate geometry to match
    dimension text against.
    """
    wall_mask = isolate_wall_mask(binary_image)
    segments = detect_wall_segments(wall_mask)
    walls, openings = build_walls(segments)

    for wall in walls:
        wall.thickness_px = estimate_wall_thickness(wall, binary_image)

    thin_walls = [w for w in walls if w.thickness_px < MIN_WALL_THICKNESS_PX]
    thin_line_candidates = [(w.start, w.end) for w in thin_walls]

    thin_wall_ids = {w.id for w in thin_walls}
    walls = [w for w in walls if w.id not in thin_wall_ids]
    openings = [o for o in openings if o.wall_id not in thin_wall_ids]

    classify_exterior_interior(walls)
    return walls, openings, thin_line_candidates


# --- Room detection -----------------------------------------------------------


def render_wall_mask_solid(walls: List[WallCandidate], shape: Tuple[int, int]) -> np.ndarray:
    height, width = shape
    mask = np.zeros((height, width), dtype=np.uint8)
    for wall in walls:
        pt1 = (int(round(wall.start[0])), int(round(wall.start[1])))
        pt2 = (int(round(wall.end[0])), int(round(wall.end[1])))
        thickness = max(2, int(round(wall.thickness_px)))
        cv2.line(mask, pt1, pt2, color=255, thickness=thickness)
    return mask


def detect_rooms(walls: List[WallCandidate], shape: Tuple[int, int]) -> List[RoomCandidate]:
    if not walls:
        return []

    wall_mask = render_wall_mask_solid(walls, shape)
    inverted = cv2.bitwise_not(wall_mask)

    contours, hierarchy = cv2.findContours(inverted, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return []
    hierarchy = hierarchy[0]

    height, width = shape
    rooms: List[RoomCandidate] = []

    for idx, contour in enumerate(contours):
        # RETR_CCOMP gives a 2-level hierarchy: top-level white regions (real
        # rooms AND the exterior background), and holes within them (which,
        # for a closed wall skeleton, is the wall silhouette itself viewed as
        # a hole in the background -- not a room). Only top-level contours
        # (no parent) are real room candidates; nested ones are hierarchy
        # artifacts, not additional rooms.
        parent_idx = hierarchy[idx][3]
        if parent_idx != -1:
            continue

        area = cv2.contourArea(contour)
        if area < MIN_ROOM_AREA_PX:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        touches_border = x <= 1 or y <= 1 or (x + w) >= width - 1 or (y + h) >= height - 1
        if touches_border and area > 0.5 * width * height:
            continue

        epsilon = 0.01 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) < 3:
            continue

        polygon = [(float(pt[0][0]), float(pt[0][1])) for pt in approx]
        rooms.append(RoomCandidate(id=_new_id("room"), polygon_px=polygon, area_px=float(area)))

    return rooms


# --- Door / window detection (Tier 2 heuristic) -------------------------------


def _has_nearby_leaf_line(gap_point: Point, segments: List[RawSegment], search_radius: float = 30.0) -> bool:
    gx, gy = gap_point
    for seg in segments:
        orientation = _classify_orientation(seg)
        if orientation is not None:
            continue
        mx, my = (seg.x1 + seg.x2) / 2, (seg.y1 + seg.y2) / 2
        if math.hypot(mx - gx, my - gy) <= search_radius:
            return True
    return False


def detect_openings(
    walls: List[WallCandidate],
    opening_candidates: List[OpeningCandidate],
    all_segments: List[RawSegment],
) -> List[OpeningDetection]:
    wall_by_id = {w.id: w for w in walls}
    detections: List[OpeningDetection] = []

    for opening in opening_candidates:
        wall = wall_by_id.get(opening.wall_id)
        if wall is None:
            continue

        gap_width = _segment_length(*opening.gap_start, *opening.gap_end)
        midpoint = ((opening.gap_start[0] + opening.gap_end[0]) / 2, (opening.gap_start[1] + opening.gap_end[1]) / 2)
        has_leaf = _has_nearby_leaf_line(opening.gap_start, all_segments) or _has_nearby_leaf_line(opening.gap_end, all_segments)

        if has_leaf:
            kind: Literal["door", "window"] = "door"
        elif wall.wall_type == "exterior":
            kind = "window"
        else:
            kind = "door"

        wall_length = _segment_length(*wall.start, *wall.end)
        if wall_length <= 0:
            continue

        if wall.orientation == "horizontal":
            position = (midpoint[0] - wall.start[0]) / wall_length if wall.end[0] >= wall.start[0] else (wall.start[0] - midpoint[0]) / wall_length
        else:
            position = (midpoint[1] - wall.start[1]) / wall_length if wall.end[1] >= wall.start[1] else (wall.start[1] - midpoint[1]) / wall_length
        position = min(1.0, max(0.0, position))

        detections.append(OpeningDetection(
            id=_new_id(kind), kind=kind, wall_id=wall.id, position=position,
            width_px=gap_width, swing_detected=has_leaf,
        ))

    return detections


# --- Stair detection (Tier 2 heuristic) ----------------------------------------


def detect_stairs(binary_image: np.ndarray, wall_mask: np.ndarray) -> List[StairCandidate]:
    non_wall = cv2.bitwise_and(binary_image, cv2.bitwise_not(wall_mask))

    lines = cv2.HoughLinesP(
        non_wall, 1, np.pi / 180, threshold=15, minLineLength=15, maxLineGap=3,
    )
    if lines is None:
        return []

    candidates = [RawSegment(float(x1), float(y1), float(x2), float(y2)) for (x1, y1, x2, y2) in lines[:, 0, :]]
    short_segments = [s for s in candidates if s.length <= STAIR_MAX_SEGMENT_LENGTH_PX]

    horiz = [s for s in short_segments if _classify_orientation(s) == "horizontal"]
    vert = [s for s in short_segments if _classify_orientation(s) == "vertical"]

    stairs: List[StairCandidate] = []

    for group, perp_key in ((horiz, lambda s: (s.y1 + s.y2) / 2), (vert, lambda s: (s.x1 + s.x2) / 2)):
        # Hough frequently reports one physical drawn line as several
        # overlapping/duplicate segments. Merge those near-duplicates into a
        # single representative segment per physical line FIRST -- otherwise
        # the near-zero gaps between duplicate fragments corrupt the
        # spacing-regularity check below (mixing ~0px gaps with the real
        # ~10px tread spacing).
        merged = _merge_duplicate_line_fragments(group, perp_key)
        if len(merged) < STAIR_MIN_SEGMENTS:
            continue

        cluster_groups = _cluster_by_proximity(merged, perp_key, STAIR_SPACING_TOLERANCE_PX * 3)
        for cluster in cluster_groups:
            if len(cluster) >= STAIR_MIN_SEGMENTS and _is_plausible_stair_cluster(cluster, perp_key):
                stairs.append(_stair_from_cluster(cluster))

    return stairs


def _merge_duplicate_line_fragments(
    segments: List[RawSegment], perp_key, tolerance: float = 3.0,
) -> List[RawSegment]:
    """Collapse near-duplicate Hough fragments of the same physical line into one segment."""
    if not segments:
        return []
    groups = _cluster_by_proximity(segments, perp_key, tolerance)
    merged: List[RawSegment] = []
    for group in groups:
        xs = [p for seg in group for p in (seg.x1, seg.x2)]
        ys = [p for seg in group for p in (seg.y1, seg.y2)]
        avg_perp = float(np.mean([perp_key(seg) for seg in group]))
        if max(xs) - min(xs) >= max(ys) - min(ys):
            merged.append(RawSegment(min(xs), avg_perp, max(xs), avg_perp))
        else:
            merged.append(RawSegment(avg_perp, min(ys), avg_perp, max(ys)))
    return merged


def _is_plausible_stair_cluster(cluster: List[RawSegment], perp_key) -> bool:
    """
    Rejects false positives (e.g. scattered OCR text strokes that happen to
    sit near the same y-level) by requiring what an actual stair tread
    pattern has and generic text doesn't: similar segment lengths, roughly
    regular spacing between consecutive treads, and a compact along-axis
    footprint (stairs are a few feet wide; a row of text can span much
    further across a floor plan).
    """
    lengths = [seg.length for seg in cluster]
    if max(lengths) / max(min(lengths), 1e-6) > STAIR_MAX_LENGTH_RATIO:
        return False

    xs = [p for seg in cluster for p in (seg.x1, seg.x2)]
    ys = [p for seg in cluster for p in (seg.y1, seg.y2)]
    along_extent = (max(xs) - min(xs)) if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else (max(ys) - min(ys))
    if along_extent > STAIR_MAX_ALONG_EXTENT_PX:
        return False

    perp_positions = sorted(perp_key(seg) for seg in cluster)
    gaps = [b - a for a, b in zip(perp_positions, perp_positions[1:])]
    if len(gaps) >= 2:
        median_gap = float(np.median(gaps))
        if median_gap <= 0:
            return False
        stdev_gap = float(np.std(gaps))
        if (stdev_gap / median_gap) > STAIR_SPACING_REGULARITY_TOLERANCE:
            return False

    return True


def _stair_from_cluster(cluster: List[RawSegment]) -> StairCandidate:
    xs = [p for s in cluster for p in (s.x1, s.x2)]
    ys = [p for s in cluster for p in (s.y1, s.y2)]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    polygon = [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
    return StairCandidate(id=_new_id("stair"), polygon_px=polygon)


# --- Full pipeline orchestration ------------------------------------------
#
# Lives here rather than a separate pipeline.py module, per the "minimum
# file changes" constraint -- Prompt 6's Files/Folders list names
# preprocessing.py, detector.py, postprocessing.py, and ocr_service.py
# specifically and doesn't add a fifth orchestration file. detector.py is
# the natural home since it's already the module that knows about every
# structural element type; postprocessing/OCR are imported here rather than
# the other way around to avoid a circular import (postprocessing.py
# already imports several detector.py types).


def run_detection_pipeline(image_path, project_id: str) -> dict:
    """
    Full pipeline: preprocess -> detect walls/rooms/openings/stairs -> OCR
    -> associate -> score confidence -> calibrate units -> assemble ->
    validate. Returns a plain dict ready to hand to
    app.floorplan.validator.parse_floorplan() (the caller is expected to do
    that validation step -- see backend/tests/test_detection.py for the
    pattern), keeping this function's return type framework-agnostic.

    Every element in the returned dict has source="ai_detection" and a
    populated confidence, per Prompt 6's completion criteria.
    """
    from app.cv import postprocessing
    from app.ocr import ocr_service

    preprocessed = preprocessing.preprocess(image_path)
    working_image = preprocessed.working_image

    walls, opening_candidates, thin_line_candidates = detect_walls(working_image)
    rooms = detect_rooms(walls, working_image.shape)
    postprocessing.associate_room_boundary_walls(rooms, walls)

    wall_mask = isolate_wall_mask(working_image)
    stairs = detect_stairs(working_image, wall_mask)

    # Door/window classification needs a finer-grained segment search
    # (including short leaf-line fragments) than wall detection uses --
    # see detect_fine_segments_for_leaf_search's docstring.
    all_segments = detect_fine_segments_for_leaf_search(working_image)
    opening_detections = detect_openings(walls, opening_candidates, all_segments)
    opening_detections = postprocessing.suppress_duplicate_openings(opening_detections)

    text_blocks = ocr_service.extract_text_blocks(preprocessed.grayscale_image)
    classified_texts = ocr_service.classify_text_blocks(text_blocks)

    room_dicts = [{"id": r.id, "polygon_px": r.polygon_px} for r in rooms]
    ocr_service.associate_room_labels(room_dicts, classified_texts)
    room_names_by_id = {rd["id"]: rd for rd in room_dicts}

    dimension_results = ocr_service.associate_dimensions(classified_texts, thin_line_candidates)

    # --- Unit calibration ---
    matched_dimensions = [
        (d["value"], _segment_length(*d["start"], *d["end"]))
        for d in dimension_results
        if d["matched_to_geometry"] and d["value"]
    ]
    exterior_wall_lengths = [
        _segment_length(*w.start, *w.end) for w in walls if w.wall_type == "exterior"
    ]
    fallback_reference = max(exterior_wall_lengths) if exterior_wall_lengths else None
    calibration = postprocessing.calibrate_scale(matched_dimensions, fallback_reference)
    ppu = calibration.pixels_per_unit

    def pt(p: Point) -> dict:
        u = postprocessing.point_px_to_units(p, ppu)
        return {"x": round(u[0], 3), "y": round(u[1], 3)}

    # --- Assemble schema-shaped collections ---
    walls_by_id = {w.id: w for w in walls}

    assembled_rooms = []
    for r in rooms:
        rd = room_names_by_id.get(r.id, {})
        assembled_rooms.append({
            "id": r.id,
            "confidence": postprocessing.score_room_confidence(r, walls_by_id),
            "source": "ai_detection",
            "metadata": {},
            "name": rd.get("name") or "Unnamed Room",
            "polygon": [pt(p) for p in r.polygon_px],
            "room_type": rd.get("room_type"),
        })

    assembled_walls = []
    for w in walls:
        assembled_walls.append({
            "id": w.id,
            "confidence": postprocessing.score_wall_confidence(w),
            "source": "ai_detection",
            "metadata": {},
            "start": pt(w.start),
            "end": pt(w.end),
            "thickness": round(postprocessing.px_to_units(w.thickness_px, ppu), 3),
            "height": None,  # not visible in a 2D plan view -- see DETECTION_PIPELINE.md Section 5
            "wall_type": w.wall_type,
        })

    assembled_doors = []
    assembled_windows = []
    for o in opening_detections:
        entry = {
            "id": o.id,
            "confidence": postprocessing.score_opening_confidence(o),
            "source": "ai_detection",
            "metadata": {},
            "wall_id": o.wall_id,
            "position": round(o.position, 3),
            "width": round(postprocessing.px_to_units(o.width_px, ppu), 3),
            "height": None,  # not visible in a 2D plan view
        }
        if o.kind == "door":
            entry["swing"] = "left" if o.swing_detected else None
            assembled_doors.append(entry)
        else:
            entry["sill_height"] = None  # not visible in a 2D plan view
            assembled_windows.append(entry)

    assembled_stairs = []
    for s in stairs:
        assembled_stairs.append({
            "id": s.id,
            "confidence": postprocessing.score_stair_confidence(s),
            "source": "ai_detection",
            "metadata": {},
            "polygon": [pt(p) for p in s.polygon_px],
            "step_count": None,
            "direction": None,
        })

    assembled_dimensions = []
    for d in dimension_results:
        if d["value"] is None:
            continue
        assembled_dimensions.append({
            "id": _new_id("dim"),
            "confidence": d["confidence"],
            "source": "ai_detection",
            "metadata": {},
            "start": pt(d["start"]),
            "end": pt(d["end"]),
            "value": d["value"],
            "label": d["label"],
        })

    notes_parts = []
    if calibration.note:
        notes_parts.append(calibration.note)
    if preprocessed.working_size[0] < preprocessing.WORKING_LONG_EDGE_MIN or preprocessed.working_size[1] < preprocessing.WORKING_LONG_EDGE_MIN:
        notes_parts.append("Source image was below the minimum usable resolution and was upscaled; detection confidence may be reduced.")

    floorplan_dict = {
        "project_id": project_id,
        "units": "feet",  # calibration determines the pixel:unit ratio; unit label itself is not detected (Section 8)
        "rooms": assembled_rooms,
        "walls": assembled_walls,
        "doors": assembled_doors,
        "windows": assembled_windows,
        "stairs": assembled_stairs,
        "dimensions": assembled_dimensions,
        "furniture": [],  # out of scope for Phase 2, per DETECTION_PIPELINE.md Section 9
        "metadata": {
            "building_name": None,
            "detection_version": "phase2-tier2-v1",
            "source_image_reference": str(image_path),
            "notes": " ".join(notes_parts) if notes_parts else None,
            "extra": {
                "calibration_source": calibration.source,
                "ocr_backend": ocr_service.get_ocr_backend_name(),
            },
        },
    }

    return floorplan_dict
