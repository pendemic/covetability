from __future__ import annotations

from io import BytesIO


def compute_phash(image_bytes: bytes) -> str:
    import imagehash
    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as image:
        return str(imagehash.phash(image))


def hamming_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()
