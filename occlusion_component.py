"""Local, dependency-free Streamlit component. No third-party asset requests."""

import base64
from pathlib import Path
import streamlit.components.v1 as components

_component = components.declare_component(
    "anki_occlusion_editor", path=str(Path(__file__).with_name("io_editor"))
)


def editor(card, editor_id, key):
    from occlusion import fingerprint

    state = card["io"]
    canvas = state["canvas"]
    raw = dict(card["media"])[canvas["name"]]
    return _component(
        editor_id=editor_id,
        canvas_hash=canvas["sha256"],
        image_url="data:image/png;base64," + base64.b64encode(raw).decode(),
        width=canvas["width"],
        height=canvas["height"],
        masks=state["masks"],
        state_token=fingerprint(card),
        ack_event=state.get("last_event"),
        default=None,
        key=key,
    )
