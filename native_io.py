"""Native Image Occlusion format study: rectangular-mask serialization only.

This is not a production export path and never rasterizes a mask into an image.
A note must use the official Anki Image Occlusion stock model and backend, not
an ordinary genanki Cloze model with an image substituted for real masks.
"""

import math


def native_rectangles(masks):
    """Validate normalized source-image coordinates and emit native shape clozes.

    Each item has number, left, top, width, height. Same-number shapes share a
    card. This initial rectangle study limits ordinals to 1..99 deliberately.
    """
    if not masks:
        raise ValueError(
            "Aucun masque : ne pas exporter une image statique comme Occlusion."
        )
    result = []
    for mask in masks:
        n = mask["number"]
        if type(n) is not int or not 1 <= n <= 99:
            raise ValueError("Numéro de masque hors plage 1..99.")
        coords = [float(mask[k]) for k in ("left", "top", "width", "height")]
        if not all(math.isfinite(x) for x in coords):
            raise ValueError("Coordonnées de masque non finies.")
        left, top, width, height = coords
        if (
            left < 0
            or top < 0
            or width <= 0
            or height <= 0
            or left + width > 1
            or top + height > 1
        ):
            raise ValueError("Le masque doit rester dans l’image, en coordonnées 0..1.")
        properties = ":".join(
            f"{key}={value:.8g}"
            for key, value in zip(("left", "top", "width", "height"), coords)
        )
        result.append(
            "{{c" + str(n) + "::image-occlusion:rect:" + properties + ":oi=1}}"
        )
    return " ".join(result)
