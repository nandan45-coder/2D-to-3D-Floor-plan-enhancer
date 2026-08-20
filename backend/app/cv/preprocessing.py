"""
Image preprocessing for the floor plan detection pipeline.

Implements Section 2 of docs/DETECTION_PIPELINE.md: load/rasterize, resize
to a working resolution, grayscale, denoise, binarize, deskew.

Pure functions/classes only -- no FastAPI, no I/O beyond reading the given
file path, so this is independently testable and reusable outside the API
layer (per Prompt 6's implementation constraints).
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import cv2
import numpy as np

# --- Limits from docs/DETECTION_PIPELINE.md Section 1 -----------------------
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
WORKING_LONG_EDGE_MAX = 3000  # px
WORKING_LONG_EDGE_MIN = 800  # px
PDF_RASTER_DPI = 200


class UnsupportedFileError(ValueError):
    """Raised when a file's extension isn't in SUPPORTED_EXTENSIONS."""


@dataclass
class PreprocessResult:
    """
    Output of the full preprocessing pipeline.

    `working_image` is grayscale, denoised, binarized, and deskewed -- the
    image every downstream detection step operates on. `scale_factor` is the
    factor applied to go from the original loaded image to `working_image`'s
    resolution (working_size = original_size * scale_factor); detector
    outputs stay in working-image pixel space throughout the pipeline, and
    this factor is retained only for reference/debugging, per the "keep
    everything in working-resolution pixel space, convert once at the end"
    approach used in postprocessing.py's unit calibration step.
    """
    working_image: np.ndarray  # binarized, deskewed, single-channel uint8 (0/255)
    grayscale_image: np.ndarray  # grayscale, pre-binarization (used by OCR)
    scale_factor: float
    rotation_deg_applied: float
    original_size: tuple  # (width, height) of the originally loaded image
    working_size: tuple  # (width, height) of working_image


def _load_pdf_first_page(path: Path) -> np.ndarray:
    """Rasterize the first page of a PDF to a BGR numpy image via PyMuPDF."""
    import fitz  # PyMuPDF -- imported lazily so it's only required for PDF input

    doc = fitz.open(str(path))
    try:
        if doc.page_count < 1:
            raise UnsupportedFileError(f"PDF '{path}' has no pages.")
        page = doc.load_page(0)
        zoom = PDF_RASTER_DPI / 72.0  # PDF points are 72 DPI by definition
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
        img = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, pixmap.n
        )
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    finally:
        doc.close()


def load_image(path: Union[str, Path]) -> np.ndarray:
    """
    Load a PNG/JPG/PDF from disk into a BGR numpy image (first page only for
    PDFs, per docs/DETECTION_PIPELINE.md Section 1's documented limitation).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(
            f"Unsupported file extension '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    if ext == ".pdf":
        return _load_pdf_first_page(path)

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Failed to decode image at '{path}' (corrupt or unreadable).")
    return image


def resize_to_working_resolution(image: np.ndarray) -> tuple:
    """
    Resize so the long edge is within [WORKING_LONG_EDGE_MIN, WORKING_LONG_EDGE_MAX],
    preserving aspect ratio. Returns (resized_image, scale_factor).
    """
    height, width = image.shape[:2]
    long_edge = max(height, width)

    if long_edge > WORKING_LONG_EDGE_MAX:
        scale = WORKING_LONG_EDGE_MAX / long_edge
    elif long_edge < WORKING_LONG_EDGE_MIN:
        scale = WORKING_LONG_EDGE_MIN / long_edge
    else:
        scale = 1.0

    if scale == 1.0:
        return image.copy(), 1.0

    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    resized = cv2.resize(image, new_size, interpolation=interpolation)
    return resized, scale


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def denoise(gray_image: np.ndarray) -> np.ndarray:
    """
    Denoise a grayscale image. Uses a lighter median blur for large images to
    keep runtime reasonable (fastNlMeansDenoising is accurate but slow on
    large working images), per docs/DETECTION_PIPELINE.md Section 2 step 4.
    """
    height, width = gray_image.shape[:2]
    if height * width > 1_500_000:  # ~1500x1000 and up
        return cv2.medianBlur(gray_image, 3)
    return cv2.fastNlMeansDenoising(gray_image, h=10, templateWindowSize=7, searchWindowSize=21)


def binarize(gray_image: np.ndarray) -> np.ndarray:
    """
    Adaptive thresholding rather than a single global Otsu threshold, since
    floor plan scans commonly have uneven lighting (Section 2 step 5).
    Output convention: walls/lines are WHITE (255) on a BLACK (0) background,
    which is what cv2's Hough/contour/morphology functions expect.
    """
    binary = cv2.adaptiveThreshold(
        gray_image,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,  # dark lines on light paper -> white lines on black
        blockSize=25,
        C=10,
    )
    return binary


def estimate_skew_angle(binary_image: np.ndarray) -> float:
    """
    Estimate the dominant skew angle (degrees) from the binarized image using
    a Hough-line dominant-angle vote, per Section 2 step 6. Returns 0.0 if no
    reliable estimate can be made (e.g. too few line features) -- deskewing
    is best-effort, never a hard failure.
    """
    lines = cv2.HoughLinesP(
        binary_image, 1, np.pi / 180, threshold=80, minLineLength=binary_image.shape[1] // 8, maxLineGap=10
    )
    if lines is None or len(lines) == 0:
        return 0.0

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        # Fold into [-45, 45) since floor plan walls are expected near-axis-aligned
        # (per the axis-aligned assumption documented in DETECTION_PIPELINE.md).
        folded = ((angle + 45) % 90) - 45
        angles.append(folded)

    if not angles:
        return 0.0

    # Median is robust to the mix of horizontal/vertical wall angles present.
    return float(np.median(angles))


def deskew(binary_image: np.ndarray, angle_deg: float) -> np.ndarray:
    if abs(angle_deg) < 0.1:
        return binary_image
    height, width = binary_image.shape[:2]
    center = (width / 2, height / 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    return cv2.warpAffine(
        binary_image, rotation_matrix, (width, height),
        flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0,
    )


def preprocess(path: Union[str, Path]) -> PreprocessResult:
    """Run the full preprocessing pipeline end to end."""
    original = load_image(path)
    original_size = (original.shape[1], original.shape[0])  # (width, height)

    resized, scale_factor = resize_to_working_resolution(original)
    gray = to_grayscale(resized)
    denoised = denoise(gray)
    binary = binarize(denoised)

    skew_angle = estimate_skew_angle(binary)
    deskewed = deskew(binary, skew_angle)
    gray_deskewed = deskew(gray, skew_angle)  # keep grayscale in sync, for OCR use

    working_size = (deskewed.shape[1], deskewed.shape[0])

    return PreprocessResult(
        working_image=deskewed,
        grayscale_image=gray_deskewed,
        scale_factor=scale_factor,
        rotation_deg_applied=skew_angle,
        original_size=original_size,
        working_size=working_size,
    )
