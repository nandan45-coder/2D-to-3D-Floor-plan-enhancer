"""
OCR service: text extraction, classification (room label vs. dimension vs.
other), and association to detected geometry.

Implements docs/DETECTION_PIPELINE.md Section 7.

Dual backend, exactly as designed: EasyOCR primary (handles rotated text
natively, needed for angled dimension labels), Tesseract/pytesseract offline
fallback (no model weight download required). See `get_ocr_backend_name()`
docstring for how this sandbox's own network constraints affected which
path was actually exercised during development -- documented honestly in
DEVELOPMENT_STATUS.md rather than silently assumed.
"""
import re
from dataclasses import dataclass
from typing import List, Literal, Optional, Tuple

import numpy as np

Point = Tuple[float, float]

# Extensible room-type keyword list, per Section 7 -- maintained here as
# actual code (not hardcoded inline in the classification function) so it's
# easy to extend without touching pipeline logic.
ROOM_TYPE_KEYWORDS = {
    "bedroom": "bedroom", "bed room": "bedroom", "master bedroom": "bedroom",
    "bathroom": "bathroom", "bath room": "bathroom", "bath": "bathroom", "wc": "bathroom",
    "kitchen": "kitchen",
    "living room": "living_room", "lounge": "living_room", "family room": "living_room",
    "dining room": "dining_room", "dining": "dining_room",
    "closet": "closet", "wardrobe": "closet",
    "garage": "garage",
    "hallway": "hallway", "hall": "hallway", "corridor": "hallway",
    "office": "office", "study": "office",
    "laundry": "laundry",
    "studio": "studio",
    "entry": "entry", "foyer": "entry",
}

# Matches patterns like: 12'-6", 24', 3.5m, 10 ft, 150cm, 24 ft
DIMENSION_PATTERN = re.compile(
    r"""^\s*
    (\d+(?:\.\d+)?)
    \s*
    (?:'-?(\d+(?:\.\d+)?)\"?)?   # optional feet-inches suffix like '-6"
    \s*
    (ft|feet|m|meters?|cm|in|inches|'|")?
    \s*$""",
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class TextBlock:
    text: str
    center: Point
    bbox_min: Point
    bbox_max: Point
    confidence: float  # 0-1, from the OCR engine


@dataclass
class ClassifiedText:
    block: TextBlock
    kind: Literal["dimension", "room_label", "other"]
    dimension_value: Optional[float] = None  # populated if kind == "dimension"
    room_type: Optional[str] = None  # populated if kind == "room_label" and matched a keyword


_easyocr_reader = None
_backend_used: Optional[str] = None


def get_ocr_backend_name() -> Optional[str]:
    """
    Returns which backend was actually used on the most recent call to
    extract_text_blocks(), or None if it hasn't run yet. Exposed mainly for
    tests/debugging and for DEVELOPMENT_STATUS.md reporting -- lets us state
    plainly which path was exercised rather than assuming.
    """
    return _backend_used


def _try_easyocr(image: np.ndarray) -> Optional[List[TextBlock]]:
    """
    Attempts EasyOCR. Returns None (never raises) if the import fails or the
    reader can't be constructed -- e.g. no network access for first-run
    weight download, which is a realistic constraint in sandboxed/offline
    environments and exactly why Tesseract exists as a fallback.
    """
    global _easyocr_reader
    try:
        import easyocr  # type: ignore
    except ImportError:
        return None

    try:
        if _easyocr_reader is None:
            _easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        raw_results = _easyocr_reader.readtext(image)
    except Exception:
        # Covers weight-download failures, corrupt cache, etc. -- any
        # failure here means "fall back to Tesseract", not "crash the pipeline".
        return None

    blocks: List[TextBlock] = []
    for quad, text, confidence in raw_results:
        xs = [p[0] for p in quad]
        ys = [p[1] for p in quad]
        blocks.append(TextBlock(
            text=text.strip(),
            center=(float(np.mean(xs)), float(np.mean(ys))),
            bbox_min=(float(min(xs)), float(min(ys))),
            bbox_max=(float(max(xs)), float(max(ys))),
            confidence=float(confidence),
        ))
    return blocks


def _try_tesseract(image: np.ndarray) -> Optional[List[TextBlock]]:
    """
    Offline fallback via pytesseract. Returns None if the binary/module
    isn't available.

    Tesseract's `image_to_data` returns per-WORD boxes, but real floor plan
    labels are frequently multi-word ("Living Room", "Master Bedroom"). A
    per-word block would fragment "Living Room" into "Living" and "Room"
    individually, neither of which matches the "living room" keyword phrase
    on its own. This groups words sharing the same (block, paragraph, line)
    -- metadata Tesseract already provides -- into one merged line-level
    TextBlock before returning, which is the correct general fix (not
    specific to any one input).
    """
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError:
        return None

    try:
        data = pytesseract.image_to_data(image, output_type=Output.DICT)
    except Exception:
        return None

    n = len(data.get("text", []))
    lines: dict = {}  # (block_num, par_num, line_num) -> list of word indices

    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(i)

    blocks: List[TextBlock] = []
    for indices in lines.values():
        for sub_indices in _split_on_large_gaps(indices, data):
            blocks.append(_merge_word_indices_into_block(sub_indices, data))

    return blocks


def _split_on_large_gaps(indices: List[int], data: dict) -> List[List[int]]:
    """
    Tesseract's own line grouping trusts row alignment alone, so two
    genuinely separate labels that happen to sit at the same y-height (e.g.
    two different room names on the same row of a floor plan) can get
    merged into one "line". This splits a line's word indices back apart
    wherever the horizontal gap between consecutive words is much larger
    than a normal inter-word space, using each word's own height as the
    scale reference so the threshold adapts to font size/image resolution.
    """
    if len(indices) <= 1:
        return [indices]

    indices_sorted = sorted(indices, key=lambda i: data["left"][i])
    heights = [data["height"][i] for i in indices_sorted]
    median_height = float(np.median(heights)) if heights else 20.0
    gap_threshold = max(50.0, 2.5 * median_height)

    groups: List[List[int]] = [[indices_sorted[0]]]
    for idx in indices_sorted[1:]:
        prev_idx = groups[-1][-1]
        prev_right = data["left"][prev_idx] + data["width"][prev_idx]
        gap = data["left"][idx] - prev_right
        if gap > gap_threshold:
            groups.append([idx])
        else:
            groups[-1].append(idx)

    return groups


def _merge_word_indices_into_block(indices: List[int], data: dict) -> TextBlock:
    words = [data["text"][i].strip() for i in indices]
    joined_text = " ".join(words)

    xs_min = [data["left"][i] for i in indices]
    ys_min = [data["top"][i] for i in indices]
    xs_max = [data["left"][i] + data["width"][i] for i in indices]
    ys_max = [data["top"][i] + data["height"][i] for i in indices]

    confidences = []
    for i in indices:
        try:
            c = float(data["conf"][i])
            if c >= 0:
                confidences.append(c / 100.0)
        except (ValueError, TypeError):
            continue
    confidence = float(np.mean(confidences)) if confidences else 0.5

    bbox_min = (float(min(xs_min)), float(min(ys_min)))
    bbox_max = (float(max(xs_max)), float(max(ys_max)))
    center = ((bbox_min[0] + bbox_max[0]) / 2, (bbox_min[1] + bbox_max[1]) / 2)

    return TextBlock(text=joined_text, center=center, bbox_min=bbox_min, bbox_max=bbox_max, confidence=confidence)


def extract_text_blocks(image: np.ndarray) -> List[TextBlock]:
    """
    Runs OCR once over the full image (Section 7 step 1). Tries EasyOCR
    first, falls back to Tesseract. Sets the module-level backend-used flag
    so callers/tests can report which path actually ran.
    """
    global _backend_used

    result = _try_easyocr(image)
    if result is not None:
        _backend_used = "easyocr"
        return result

    result = _try_tesseract(image)
    if result is not None:
        _backend_used = "tesseract"
        return result

    _backend_used = "none"
    return []


def _parse_dimension_value(text: str) -> Optional[float]:
    """Parses a dimension-looking string into a single numeric value in its own stated unit."""
    match = DIMENSION_PATTERN.match(text)
    if not match:
        return None
    whole, inches_part = match.group(1), match.group(2)
    try:
        value = float(whole)
    except ValueError:
        return None
    if inches_part:
        try:
            value += float(inches_part) / 12.0  # feet-inches -> decimal feet
        except ValueError:
            pass
    return value


def classify_text_block(block: TextBlock) -> ClassifiedText:
    """Section 7 step 2: dimension pattern match, else room-keyword match, else 'other'."""
    text = block.text.strip()
    if not text:
        return ClassifiedText(block=block, kind="other")

    dimension_value = _parse_dimension_value(text)
    if dimension_value is not None:
        return ClassifiedText(block=block, kind="dimension", dimension_value=dimension_value)

    lowered = text.lower()
    for keyword, room_type in ROOM_TYPE_KEYWORDS.items():
        if keyword in lowered:
            return ClassifiedText(block=block, kind="room_label", room_type=room_type)

    return ClassifiedText(block=block, kind="other")


def classify_text_blocks(blocks: List[TextBlock]) -> List[ClassifiedText]:
    return [classify_text_block(b) for b in blocks]


def associate_room_labels(rooms: List, classified_texts: List[ClassifiedText]) -> None:
    """
    Section 7 step 3: point-in-polygon test assigning each room-label text
    block to the room whose polygon contains its center point. Mutates each
    room dict's 'name'/'room_type' in place. `rooms` is a list of dicts with
    at least {'polygon_px': [(x,y),...]} -- kept as plain dicts here (not
    the detector's RoomCandidate dataclass) so this function stays usable
    from the assembly step without a tighter coupling than necessary.
    """
    from shapely.geometry import Point as ShapelyPoint
    from shapely.geometry import Polygon as ShapelyPolygon

    room_labels = [ct for ct in classified_texts if ct.kind == "room_label"]

    for room in rooms:
        polygon_px = room["polygon_px"]
        if len(polygon_px) < 3:
            continue
        try:
            shapely_poly = ShapelyPolygon(polygon_px)
        except Exception:
            continue

        for label in room_labels:
            point = ShapelyPoint(label.block.center)
            if shapely_poly.contains(point):
                room["name"] = label.block.text.strip()
                room["room_type"] = label.room_type
                break


def associate_dimensions(
    classified_texts: List[ClassifiedText],
    candidate_lines: List[Tuple[Point, Point]],
    search_radius: float = 40.0,
) -> List[dict]:
    """
    Section 7 step 4: for each dimension-classified text block, look for a
    nearby candidate line (a long thin line distinct from wall lines) to use
    as the annotation's start/end. Falls back to a short span centered on
    the text's own bounding box (lower confidence) if none is found.

    Returns a list of plain dicts ready to become DimensionAnnotation
    elements: {value, start, end, confidence, matched_to_geometry}.
    """
    results: List[dict] = []
    dimension_texts = [ct for ct in classified_texts if ct.kind == "dimension"]

    for dim in dimension_texts:
        center = dim.block.center
        best_line: Optional[Tuple[Point, Point]] = None
        best_distance = search_radius

        for line_start, line_end in candidate_lines:
            line_mid = ((line_start[0] + line_end[0]) / 2, (line_start[1] + line_end[1]) / 2)
            distance = ((line_mid[0] - center[0]) ** 2 + (line_mid[1] - center[1]) ** 2) ** 0.5
            if distance < best_distance:
                best_distance = distance
                best_line = (line_start, line_end)

        if best_line is not None:
            start, end = best_line
            confidence = dim.block.confidence
            matched = True
        else:
            # Fallback: a short span centered on the text's own bbox, lower confidence.
            half_width = max(10.0, (dim.block.bbox_max[0] - dim.block.bbox_min[0]) / 2)
            start = (center[0] - half_width, center[1])
            end = (center[0] + half_width, center[1])
            confidence = dim.block.confidence * 0.6
            matched = False

        results.append({
            "value": dim.dimension_value,
            "start": start,
            "end": end,
            "label": dim.block.text.strip(),
            "confidence": round(confidence, 3),
            "matched_to_geometry": matched,
        })

    return results
