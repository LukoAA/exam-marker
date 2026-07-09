import cv2
import numpy as np
import pytest
from PIL import Image

from app.marking import preprocess


def _make_lined_image(width: int = 300, height: int = 400) -> np.ndarray:
    """A synthetic "scanned page": white background with horizontal black
    bars simulating lines of text, separated by whitespace gaps. Oriented
    correctly, this has a strongly periodic row-ink profile.
    """
    image = np.full((height, width, 3), 255, dtype=np.uint8)
    line_height = 12
    gap = 10
    y = 20
    while y + line_height < height - 20:
        cv2.rectangle(image, (20, y), (width - 20, y + line_height), (0, 0, 0), thickness=-1)
        y += line_height + gap
    return image


@pytest.fixture
def sample_pdf(tmp_path):
    page1 = Image.fromarray(cv2.cvtColor(_make_lined_image(), cv2.COLOR_BGR2RGB))
    page2 = Image.fromarray(cv2.cvtColor(_make_lined_image(), cv2.COLOR_BGR2RGB))
    pdf_path = tmp_path / "sample.pdf"
    page1.save(pdf_path, "PDF", save_all=True, append_images=[page2])
    return pdf_path


def test_pdf_to_images_returns_one_pil_image_per_page(sample_pdf):
    pages = preprocess.pdf_to_images(sample_pdf, dpi=100)

    assert len(pages) == 2
    for page in pages:
        assert isinstance(page, Image.Image)
        assert page.size[0] > 0 and page.size[1] > 0


def test_correct_orientation_fixes_sideways_scan():
    original = _make_lined_image()
    sideways = np.rot90(original, 1).copy()

    corrected = preprocess.correct_orientation(sideways)

    assert corrected.shape[:2] == original.shape[:2]
    gray_corrected = cv2.cvtColor(corrected, cv2.COLOR_BGR2GRAY)
    gray_sideways = cv2.cvtColor(sideways, cv2.COLOR_BGR2GRAY)
    assert preprocess._row_projection_score(gray_corrected) > preprocess._row_projection_score(
        gray_sideways
    )


def test_correct_orientation_leaves_upright_page_unchanged():
    original = _make_lined_image()

    corrected = preprocess.correct_orientation(original)

    assert corrected.shape == original.shape


def test_deskew_improves_row_projection_score():
    original = _make_lined_image()
    h, w = original.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), 7, 1.0)
    skewed = cv2.warpAffine(original, matrix, (w, h), borderMode=cv2.BORDER_REPLICATE)

    deskewed = preprocess.deskew(skewed)

    score_before = preprocess._row_projection_score(cv2.cvtColor(skewed, cv2.COLOR_BGR2GRAY))
    score_after = preprocess._row_projection_score(cv2.cvtColor(deskewed, cv2.COLOR_BGR2GRAY))
    assert score_after > score_before


def test_enhance_contrast_increases_intensity_spread():
    low_contrast = np.full((100, 100, 3), 128, dtype=np.uint8)
    rng = np.random.default_rng(42)
    noise = rng.integers(-8, 9, size=low_contrast.shape, dtype=np.int16)
    low_contrast = np.clip(low_contrast.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    enhanced = preprocess.enhance_contrast(low_contrast)

    assert enhanced.std() > low_contrast.std()


def test_resize_longest_side_downscales_to_max():
    large = np.zeros((3300, 2550, 3), dtype=np.uint8)

    resized = preprocess.resize_longest_side(large, max_side=1568)

    assert max(resized.shape[:2]) == 1568
    assert resized.shape[0] > resized.shape[1]


def test_resize_longest_side_does_not_upscale_small_images():
    small = np.zeros((400, 300, 3), dtype=np.uint8)

    resized = preprocess.resize_longest_side(small, max_side=1568)

    assert resized.shape == small.shape


def test_preprocess_page_end_to_end():
    rotated = np.rot90(_make_lined_image(), 1).copy()
    image = Image.fromarray(cv2.cvtColor(rotated, cv2.COLOR_BGR2RGB))

    result = preprocess.preprocess_page(image)

    assert isinstance(result, Image.Image)
    assert result.mode == "RGB"
    assert max(result.size) <= preprocess.MAX_LONGEST_SIDE


def test_preprocess_pdf_end_to_end(sample_pdf):
    results = preprocess.preprocess_pdf(sample_pdf, dpi=100)

    assert len(results) == 2
    for page in results:
        assert isinstance(page, Image.Image)
        assert max(page.size) <= preprocess.MAX_LONGEST_SIDE
