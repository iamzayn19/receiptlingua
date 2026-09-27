from pathlib import Path

from receiptlingua.pipeline.preprocess import loading

FIXTURES = Path(__file__).parent / "fixtures"


def test_loads_clean_receipt():
    result = loading.load_image(FIXTURES / "receipt_clean.png")
    assert result.ok
    assert result.error is None
    assert result.image is not None
    assert result.image.shape[2] == 3
    assert result.format == "PNG"
    assert result.width and result.height


def test_loads_all_valid_synthetic_fixtures():
    for name in [
        "receipt_clean.png",
        "receipt_rotated.png",
        "receipt_low_contrast.png",
        "receipt_dark.png",
        "receipt_noisy.png",
        "receipt_perspective.png",
    ]:
        result = loading.load_image(FIXTURES / name)
        assert result.ok, f"{name} failed to load: {result.error}"


def test_rejects_zero_byte_file():
    result = loading.load_image(FIXTURES / "corrupt_zero_byte.png")
    assert not result.ok
    assert result.error == loading.ERR_EMPTY_FILE


def test_rejects_truncated_file():
    result = loading.load_image(FIXTURES / "corrupt_truncated.png")
    assert not result.ok
    assert result.error == loading.ERR_DECODE_FAILED


def test_rejects_non_image_with_image_extension():
    result = loading.load_image(FIXTURES / "corrupt_not_an_image.png")
    assert not result.ok
    assert result.error == loading.ERR_DECODE_FAILED


def test_rejects_decompression_bomb_header():
    result = loading.load_image(FIXTURES / "corrupt_decompression_bomb.png")
    assert not result.ok
    assert result.error in (
        loading.ERR_DECODE_FAILED,
        loading.ERR_DIMENSIONS_TOO_LARGE,
        loading.ERR_DECOMPRESSION_BOMB,
    )


def test_rejects_missing_file():
    result = loading.load_image(FIXTURES / "does_not_exist.png")
    assert not result.ok
    assert result.error == loading.ERR_UNREADABLE


def test_never_raises_on_garbage_bytes(tmp_path):
    garbage = tmp_path / "garbage.png"
    garbage.write_bytes(bytes(range(256)) * 4)
    result = loading.load_image(garbage)
    assert not result.ok


def test_custom_max_pixels_rejects_moderately_large_declared_image(tmp_path):
    # A real, valid, small image should still be rejected if the caller
    # sets a tighter max_pixels than its actual pixel count.
    result = loading.load_image(FIXTURES / "receipt_clean.png", max_pixels=10)
    assert not result.ok
    assert result.error == loading.ERR_DECOMPRESSION_BOMB
