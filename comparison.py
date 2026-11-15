"""Pixel comparison helpers; independent of Qt and pipeline execution."""
import numpy as np


def absolute_difference(reference, processed):
    """Return uint8 absolute differences without overflow or implicit alignment.

    Grayscale pixels are repeated across RGB channels when comparing gray and RGB.
    Dimensions must match; zero values indicate equality at that pixel/channel.
    """
    for image in (reference, processed):
        if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
            raise ValueError("Difference view requires uint8 images")
        if image.ndim not in (2, 3) or not image.size or image.ndim == 3 and image.shape[2] != 3:
            raise ValueError("Difference view supports nonempty grayscale or RGB images")
    if reference.shape[:2] != processed.shape[:2]:
        raise ValueError("Difference view requires matching image dimensions; no automatic alignment is performed")
    if reference.ndim != processed.ndim:
        if reference.ndim == 2:
            reference = reference[:, :, None]
        if processed.ndim == 2:
            processed = processed[:, :, None]
    return np.abs(reference.astype(np.int16) - processed.astype(np.int16)).astype(np.uint8)
