"""Study tests, not a claim that lecture Occlusions are already supported in the app."""

import json
import os
from pathlib import Path
import subprocess

import pymupdf as fitz
import pytest

from native_io import native_rectangles


@pytest.mark.parametrize(
    "masks",
    [
        [],
        [{"number": 0, "left": 0, "top": 0, "width": 0.1, "height": 0.1}],
        [{"number": 1, "left": -0.1, "top": 0, "width": 0.1, "height": 0.1}],
        [{"number": 1, "left": 0.9, "top": 0, "width": 0.2, "height": 0.1}],
        [{"number": 1, "left": 0, "top": 0, "width": 0, "height": 0.1}],
        [{"number": 1, "left": 0, "top": 0, "width": float("nan"), "height": 0.1}],
    ],
)
def test_invalid_masks_never_become_static_image_exports(masks):
    with pytest.raises(ValueError):
        native_rectangles(masks)


def test_genuine_native_occlusion_roundtrip(tmp_path):
    interpreter = os.environ.get("ANKI_TEST_PYTHON")
    if not interpreter:
        pytest.skip("Official Anki interpreter unavailable")
    masks = [
        dict(number=1, left=0.1, top=0.1, width=0.3, height=0.2),
        dict(number=2, left=0.5, top=0.5, width=0.2, height=0.2),
    ]
    spec = dict(masks=masks, occlusions=native_rectangles(masks))
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 80), False)
    image.clear_with(180)
    image.save(str(tmp_path / "synthetic.png"))
    run = subprocess.run(
        [
            interpreter,
            str(Path(__file__).with_name("native_occlusion_probe.py")),
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert run.returncode == 0, run.stdout + "\n" + run.stderr
    assert '"roundtrip": true' in run.stdout
    assert '"stock_kind": 6' in run.stdout
