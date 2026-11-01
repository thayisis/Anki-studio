"""Review preview of explicit, nonnested Cloze markup (native Anki does export rendering)."""

import re


def preview_cloze(value, answer=False, active_number=1):
    def replace(match):
        text = match[2].split("::", 1)[0]
        hint = match[2].split("::", 1)[1] if "::" in match[2] else "…"
        if int(match[1]) != active_number:
            return text
        return (
            '<span style="color:#1455a0;font-weight:bold">'
            + (text if answer else "[" + hint + "]")
            + "</span>"
        )

    return re.sub(r"{{c([1-9]\d*)::([^{}]+?)}}", replace, value, flags=re.S)
