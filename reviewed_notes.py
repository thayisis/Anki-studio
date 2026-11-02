"""Explicit reviewed partitions, never a guessed semantic rewrite of arbitrary PDFs.

Only a complete passage and note type match applies a recipe. Whitespace can
vary with PDF wrapping; the actual source characters are never replaced by the
recipe's transcription. All backs are constructed from extracted elements.
"""

import json
from pathlib import Path
import re

RECIPES = json.loads(
    Path(__file__).with_name("reviewed_passages.json").read_text(encoding="utf-8")
)


def normalized(value):
    return " ".join(value.split())


def recipe_for(kind, passage):
    return next(
        (
            r
            for r in RECIPES
            if r["type"] == kind and normalized(r["source"]) == normalized(passage)
        ),
        None,
    )


def without_cloze(value):
    """Remove annotation only; preserve each original deletion's literal content."""
    return re.sub(r"{{c[1-9]\d*::([^{}]*?)(?:::[^{}]*?)?}}", r"\1", value)
