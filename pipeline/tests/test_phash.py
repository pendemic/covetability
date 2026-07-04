from io import BytesIO

from PIL import Image

from app.contract import PHASH_HAMMING_MAX
from app.ingestion.phash import compute_phash, hamming_distance


def png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (32, 32), color)
    handle = BytesIO()
    image.save(handle, format="PNG")
    return handle.getvalue()


def test_compute_phash_is_stable_for_identical_images() -> None:
    first = compute_phash(png_bytes((255, 0, 0)))
    second = compute_phash(png_bytes((255, 0, 0)))

    assert hamming_distance(first, second) == 0


def test_compute_phash_distinguishes_different_images() -> None:
    red = compute_phash(png_bytes((255, 0, 0)))
    checker = Image.new("RGB", (32, 32), (255, 255, 255))
    for x in range(16):
        for y in range(16):
            checker.putpixel((x, y), (0, 0, 0))
    handle = BytesIO()
    checker.save(handle, format="PNG")

    assert hamming_distance(red, compute_phash(handle.getvalue())) > PHASH_HAMMING_MAX
