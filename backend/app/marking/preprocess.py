"""Scan preprocessing: PDF -> 300-DPI page images, auto-rotate, deskew,
contrast enhancement, resize. See PROJECT_SPEC.md, "THE MARKING ENGINE" step 1.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image

DPI = 300
MAX_LONGEST_SIDE = 1568


def pdf_to_images(pdf_path: str | Path, dpi: int = DPI) -> list[Image.Image]:
    """Render every page of a PDF to a PIL image at the given DPI."""
    return convert_from_path(str(pdf_path), dpi=dpi)


def _pil_to_cv2(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)


def _cv2_to_pil(image: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))


def _row_projection_score(gray: np.ndarray) -> float:
    """Variance of the horizontal row-ink-projection: high when dark text rows
    alternate with light whitespace rows, i.e. when text lines are horizontal.
    Used to pick the best rotation/skew angle without OCR.
    """
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return float(binary.sum(axis=1).var())


def correct_orientation(image: np.ndarray) -> np.ndarray:
    """Rotate the page in 90-degree steps to whichever orientation maximises
    the row-projection score, correcting sideways (90/270-degree) scans.

    Note: a pure projection-profile heuristic cannot distinguish right-side-up
    from upside-down (0 vs 180 both score equally well); only sideways
    rotation is corrected here.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    best_k = 0
    best_score = -1.0
    for k in range(4):
        score = _row_projection_score(np.rot90(gray, k))
        if score > best_score:
            best_score = score
            best_k = k
    if best_k == 0:
        return image
    return np.rot90(image, best_k).copy()


def _estimate_skew_angle(gray: np.ndarray, max_angle: float, step: float) -> float:
    h, w = gray.shape
    center = (w / 2, h / 2)
    best_angle = 0.0
    best_score = _row_projection_score(gray)
    angle = -max_angle
    while angle <= max_angle + 1e-9:
        if angle != 0:
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                gray, matrix, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE
            )
            score = _row_projection_score(rotated)
            if score > best_score:
                best_score = score
                best_angle = angle
        angle += step
    return best_angle


def deskew(image: np.ndarray, max_angle: float = 15.0, step: float = 0.5) -> np.ndarray:
    """Correct small skew angles (up to max_angle degrees) by searching for
    the rotation that maximises the row-projection score. The angle search
    runs on a downscaled copy for speed; the found angle is then applied to
    the full-resolution image.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scale = 600 / max(gray.shape)
    search_gray = (
        cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1
        else gray
    )
    angle = _estimate_skew_angle(search_gray, max_angle=max_angle, step=step)
    if angle == 0.0:
        return image
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def enhance_contrast(
    image: np.ndarray, clip_limit: float = 2.0, tile_grid_size: tuple[int, int] = (8, 8)
) -> np.ndarray:
    """Apply CLAHE (contrast-limited adaptive histogram equalization) to the
    lightness channel only, to boost faint handwriting without distorting color.
    """
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge((l_channel, a_channel, b_channel))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def resize_longest_side(image: np.ndarray, max_side: int = MAX_LONGEST_SIDE) -> np.ndarray:
    """Downscale (never upscale) so the longest side is at most max_side px."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return image
    scale = max_side / longest
    new_size = (round(w * scale), round(h * scale))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def preprocess_page(image: Image.Image, max_side: int = MAX_LONGEST_SIDE) -> Image.Image:
    """Full per-page pipeline: auto-rotate, deskew, CLAHE, resize."""
    cv_image = _pil_to_cv2(image)
    cv_image = correct_orientation(cv_image)
    cv_image = deskew(cv_image)
    cv_image = enhance_contrast(cv_image)
    cv_image = resize_longest_side(cv_image, max_side=max_side)
    return _cv2_to_pil(cv_image)


def preprocess_pdf(
    pdf_path: str | Path, dpi: int = DPI, max_side: int = MAX_LONGEST_SIDE
) -> list[Image.Image]:
    """PDF -> preprocessed page images, in page order."""
    pages = pdf_to_images(pdf_path, dpi=dpi)
    return [preprocess_page(page, max_side=max_side) for page in pages]
