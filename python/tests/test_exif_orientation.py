from pathlib import Path

import numpy as np
from PIL import Image

from receiptlingua.pipeline.preprocess import exif_orientation as exif

FIXTURES = Path(__file__).parent / "fixtures"


def _write_with_orientation(tmp_path: Path, orientation: int) -> Path:
    base = Image.open(FIXTURES / "receipt_clean.png").convert("RGB")
    out = tmp_path / f"oriented_{orientation}.jpg"
    exif_bytes = Image.Exif()
    exif_bytes[exif._ORIENTATION_TAG] = orientation
    base.save(out, "JPEG", exif=exif_bytes)
    return out


def test_read_exif_orientation_defaults_to_1_when_absent():
    assert exif.read_exif_orientation(FIXTURES / "receipt_clean.png") == 1


def test_read_exif_orientation_reads_tag(tmp_path):
    path = _write_with_orientation(tmp_path, 6)
    assert exif.read_exif_orientation(path) == 6


def test_normalize_orientation_matches_apply_orientation(tmp_path):
    for orientation in range(1, 9):
        path = _write_with_orientation(tmp_path, orientation)
        raw = np.asarray(Image.open(path).convert("RGB"))

        via_file = exif.normalize_orientation_from_path(path)
        via_tag = exif.apply_orientation(raw, orientation)

        assert via_file.shape == via_tag.shape
        assert np.array_equal(via_file, via_tag)


def test_apply_orientation_identity_is_noop():
    arr = np.zeros((5, 7, 3), dtype=np.uint8)
    result = exif.apply_orientation(arr, 1)
    assert result is arr


def test_apply_orientation_180_flip_roundtrips():
    arr = np.arange(2 * 3 * 3, dtype=np.uint8).reshape(2, 3, 3)
    flipped = exif.apply_orientation(arr, 3)
    restored = exif.apply_orientation(flipped, 3)
    assert np.array_equal(arr, restored)


def test_read_exif_orientation_never_raises_on_corrupt_file():
    assert exif.read_exif_orientation(FIXTURES / "corrupt_truncated.png") == 1
    assert exif.read_exif_orientation(FIXTURES / "corrupt_not_an_image.png") == 1
    assert exif.read_exif_orientation(FIXTURES / "does_not_exist.png") == 1
