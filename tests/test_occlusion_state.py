import pytest
from engine import parse_pdf
from occlusion import (
    apply_editor_event,
    review_group,
    confirm_note,
    export_issue,
    groups,
    fingerprint,
)
from test_regressions import pdf


def card():
    return parse_pdf(pdf([(40, 40, "CARTE OCCLUSION")], image=True))[0]


def event(c, kind, seq, **extra):
    return dict(
        editor_id="test",
        canvas_hash=c["io"]["canvas"]["sha256"],
        event_id=str(seq),
        kind=kind,
        masks=c["io"]["masks"],
        **extra,
    )


def reviewed(c, masks=None):
    masks = masks or [
        dict(id="one", number=1, left=0.1, top=0.1, width=0.2, height=0.2)
    ]
    payload = event(c, "commit", 1)
    payload["masks"] = masks
    c, ok = apply_editor_event(c, payload, "test")
    assert ok
    for n in groups(c):
        c, ok = apply_editor_event(
            c, event(c, "preview", "p" + str(n), number=n), "test"
        )
        assert ok
        review_group(c, n, True)
    confirm_note(c)
    return c


def test_no_initial_masks_no_automatic_validation_and_no_static_substitution():
    c = card()
    assert c["io"]["masks"] == [] and c["io"]["reviewed"] == []
    assert "Dessiner" in export_issue(c)
    assert dict(c["media"])[c["io"]["canvas"]["name"]].startswith(b"\x89PNG")


def test_every_generated_card_requires_preview_and_explicit_review():
    c = card()
    payload = event(c, "commit", 1)
    payload["masks"] = [
        dict(id=str(n), number=n, left=0.1 * n, top=0.1, width=0.1, height=0.1)
        for n in (1, 2)
    ]
    c, _ = apply_editor_event(c, payload, "test")
    with pytest.raises(ValueError):
        review_group(c, 1, True)
    with pytest.raises(ValueError):
        confirm_note(c)
    c, _ = apply_editor_event(c, event(c, "preview", 2, number=1), "test")
    review_group(c, 1, True)
    with pytest.raises(ValueError):
        confirm_note(c)
    c, _ = apply_editor_event(c, event(c, "preview", 3, number=2), "test")
    review_group(c, 2, True)
    confirm_note(c)
    assert export_issue(c) is None


def test_edit_start_invalidates_approval_before_pointer_up_and_changed_masks_reset_groups():
    c = reviewed(card())
    before = fingerprint(c)
    c, _ = apply_editor_event(c, event(c, "editing", 7), "test")
    assert c["io"]["draft"] and c["io"]["reviewed"] == [] and export_issue(c)
    payload = event(c, "commit", 8)
    payload["masks"][0]["left"] = 0.4
    c, _ = apply_editor_event(c, payload, "test")
    assert not c["io"]["draft"] and fingerprint(c) != before and export_issue(c)


def test_wrong_canvas_card_session_and_replayed_events_are_ignored():
    c = card()
    payload = event(c, "editing", 1)
    assert not apply_editor_event(c, payload, "another-card")[1]
    payload["canvas_hash"] = "wrong"
    assert not apply_editor_event(c, payload, "test")[1]
    payload = event(c, "editing", 2)
    c, _ = apply_editor_event(c, payload, "test")
    assert not apply_editor_event(c, payload, "test")[1]


def test_source_image_or_text_change_invalidates_native_export():
    c = reviewed(card())
    c["front"] = "Edited title"
    assert export_issue(c)
    c = reviewed(card())
    name = c["io"]["canvas"]["name"]
    c["media"] = [(n, b"changed" if n == name else raw) for n, raw in c["media"]]
    assert "Image originale" in export_issue(c)


def test_reviewed_native_export_works_without_inventing_a_title():
    c = reviewed(card())
    assert c["front"] == "" and export_issue(c) is None


def test_coalesced_commit_and_preview_keeps_drawn_geometry_but_never_approves_it():
    c = card()
    payload = event(c, "preview", "session:2", number=1)
    payload["masks"] = [
        dict(id="new", number=1, left=0.2, top=0.1, width=0.2, height=0.1)
    ]
    c, ok = apply_editor_event(c, payload, "test")
    assert ok and len(c["io"]["masks"]) == 1 and c["io"]["previewed"] == [1]
    assert c["io"]["reviewed"] == [] and export_issue(c)
    stale = event(c, "commit", "session:1")
    stale["masks"] = []
    assert not apply_editor_event(c, stale, "test")[1]
