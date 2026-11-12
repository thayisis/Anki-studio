"""Full offline round trips, including synthetic histology without private course files."""

import copy
import hashlib
import io
import json
import zipfile

import pymupdf as fitz
import pytest

from engine import parse_pdf, render_blocks
from exporter import build_apkg, fields_for, content_warnings
from manual_workflow import make_request, apply_corrections, chatgpt_prompt, card_id
from project import save_project, load_project
from test_regressions import pdf


def histology_pdf():
    """Invented fixture covering secretion, wrapped bullets and interleaved images."""
    with fitz.open() as doc:
        p = doc.new_page()
        for x, y, text in [
            (40, 40, "CARTE"),
            (40, 75, "Glandes exocrines : secretion de ver test."),
            (60, 110, "- Criteres de reconnaissance :"),
            (80, 140, "- Cellules sur une lame basale."),
            (80, 170, "- Cellules polarisees :"),
            (87, 185, "noyau basal, secretion apicale."),
            (60, 290, "Apres image : texte exact."),
            (40, 400, "CARTE"),
            (40, 440, "- Une cellule de test secrete une substance."),
            (40, 500, "CARTE CLOZE"),
            (40, 530, "Secretion"),
            (60, 560, "{{c1::Mucine}} et {{c2::test::indice}}."),
            (40, 620, "CARTE OCCLUSION"),
        ]:
            p.insert_text((x, y), text)
        for rect, color in [
            (fitz.Rect(60, 200, 150, 270), 80),
            (fitz.Rect(60, 320, 150, 380), 140),
            (fitz.Rect(60, 660, 150, 730), 200),
        ]:
            pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 90, 70), False)
            pix.clear_with(color)
            p.insert_image(rect, pixmap=pix)
        return doc.tobytes()


def setup():
    data = histology_pdf()
    digest = hashlib.sha256(data).hexdigest()
    cards = parse_pdf(data)
    request, states = make_request(cards, digest)
    return data, digest, cards, request, states


def response(request, replacements=None):
    answer = {k: v for k, v in request.items() if k != "cards"}
    answer["cards"] = [
        dict(id=c["id"], front=c["front"], move_source_title=False)
        for c in request["cards"]
    ]
    for i, front in (replacements or {}).items():
        answer["cards"][i]["front"] = front
    return answer


def apply(cards, digest, request, states, answer):
    return apply_corrections(
        cards, digest, request, states, json.dumps(answer, ensure_ascii=False)
    )


def test_histology_pdf_chatgpt_project_anki_preserves_every_existing_back_block(
    tmp_path,
):
    data, digest, cards, request, states = setup()
    baseline = copy.deepcopy(cards)
    assert (
        cards[1]["blocks"] == []
    )  # One explanatory bullet misclassified as the title.
    assert len(cards[0]["media"]) == 2
    assert any(b.get("continuation") for b in cards[0]["blocks"])
    answer = response(
        request,
        {
            0: "Quels criteres caracterisent les glandes exocrines ?",
            1: "Que secrete la cellule de test ?",
        },
    )
    corrected, changed = apply(cards, digest, request, states, answer)
    assert {0, 1} <= set(changed)
    for before, after in zip(baseline, corrected):
        assert after["media"] == before["media"]
        assert after["source_elements"] == before["source_elements"]
        original_blocks = before["blocks"]
        assert (
            after["blocks"][-len(original_blocks) :] == original_blocks
            if original_blocks
            else True
        )
        assert card_id(digest, before) == card_id(digest, after)
    assert len(corrected[1]["blocks"]) == 1
    assert corrected[1]["blocks"][0]["text"] == cards[1]["original_title"]
    assert corrected[2]["type"] == "CARTE CLOZE"
    assert fields_for(corrected[2]) == fields_for(cards[2])
    assert not any("Texte modifié" in w for c in corrected for w in content_warnings(c))
    archived = save_project(
        data,
        corrected,
        name="Histologie test",
        exchange=dict(request=request, states=states),
    )
    restored = load_project(archived)
    assert restored["data"] == data
    for c, restored_card in zip(corrected, restored["cards"]):
        assert fields_for(c) == fields_for(restored_card)
        assert c["media"] == restored_card["media"]
    assert restored["exchange"]["request"] == request
    # Masks remain a deliberate action; they never come from the LLM.
    io_card = restored["cards"][3]
    io_card["io"]["masks"] = [
        dict(id="histology", number=1, left=0.1, top=0.1, width=0.2, height=0.2)
    ]
    mixed = load_project(save_project(data, restored["cards"]))
    assert mixed["cards"][3]["io"]["masks"] == io_card["io"]["masks"]
    payload, report = build_apkg(mixed["cards"], set(), "Histologie test", digest)
    assert payload[:2] == b"PK"
    assert report["notes"] == 4 and report["cards"] == 5 and not report["excluded"]
    # Native builder verifies through an official Anki reimport before returning.
    assert cards == baseline


def test_stable_ids_small_batches_and_no_images_in_chatgpt_json():
    data, digest, cards, request, states = setup()
    first, _ = make_request(cards, digest, [0, 1])
    again, _ = make_request(parse_pdf(data), digest, [0, 1])
    assert first == again
    assert [c["id"] for c in first["cards"]] == [c["id"] for c in request["cards"][:2]]
    text = json.dumps(request, ensure_ascii=False)
    assert "base64" not in text and ".png" not in text and "source_elements" not in text
    assert len(text.encode()) < len(data)
    prompt = chatgpt_prompt(request)
    assert "Histologie" in prompt and "move_source_title" in prompt
    assert "réécrire le verso" in prompt
    other = make_request(cards, hashlib.sha256(b"other").hexdigest())[0]
    assert other["cards"][0]["id"] != request["cards"][0]["id"]


@pytest.mark.parametrize(
    "defect",
    [
        "document",
        "request",
        "missing",
        "duplicate",
        "unknown",
        "back",
        "html",
        "empty",
        "boolean",
        "cloze",
        "duplicate_key",
    ],
)
def test_bad_response_is_atomic_and_never_rewrites_a_back(defect):
    _, digest, cards, request, states = setup()
    before = copy.deepcopy(cards)
    answer = response(request, {0: "Une question correcte ?"})
    if defect == "document":
        answer["document_id"] = "other"
    if defect == "request":
        answer["request_id"] = "stale"
    if defect == "missing":
        answer["cards"].pop()
    if defect == "duplicate":
        answer["cards"][1]["id"] = answer["cards"][0]["id"]
    if defect == "unknown":
        answer["cards"][1]["id"] = "invented"
    if defect == "back":
        answer["cards"][1]["back"] = "rewritten"
    if defect == "html":
        answer["cards"][1]["front"] = "<img src=x>"
    if defect == "empty":
        answer["cards"][1]["front"] = " "
    if defect == "boolean":
        answer["cards"][1]["move_source_title"] = "false"
    if defect == "cloze":
        answer["cards"][2]["front"] = "{{c1::invented}}"
    text = json.dumps(answer)
    if defect == "duplicate_key":
        text = text.replace('"schema":', '"schema":"bad","schema":', 1)
    with pytest.raises(ValueError):
        apply_corrections(cards, digest, request, states, text)
    assert cards == before


def test_stale_edits_replay_and_independent_batches():
    _, digest, cards, _, _ = setup()
    a, states_a = make_request(cards, digest, [0])
    b, states_b = make_request(cards, digest, [1])
    corrected, _ = apply(cards, digest, a, states_a, response(a, {0: "Question A ?"}))
    corrected, _ = apply(
        corrected, digest, b, states_b, response(b, {0: "Question B ?"})
    )
    assert (
        corrected[0]["title"] == "Question A ?"
        and corrected[1]["title"] == "Question B ?"
    )
    with pytest.raises(ValueError, match="modifiée"):
        apply(corrected, digest, a, states_a, response(a, {0: "Question A ?"}))
    new, states = make_request(corrected, digest)
    unchanged, _ = apply(corrected, digest, new, states, response(new))
    assert unchanged[0]["blocks"] == corrected[0]["blocks"]
    assert unchanged[1]["blocks"] == corrected[1]["blocks"]


def test_source_cloze_in_front_cannot_be_deleted_or_renumbered():
    data = pdf(
        [
            (40, 40, "CARTE CLOZE"),
            (40, 70, "{{c1::Exact}} concept"),
            (70, 110, "- Answer."),
        ]
    )
    cards = parse_pdf(data)
    request, states = make_request(cards, "x")
    assert "{{c1::Exact}}" in cards[0]["front"]
    with pytest.raises(ValueError, match="Cloze"):
        apply(cards, "x", request, states, response(request, {0: "New concept"}))


def test_fenced_json_and_non_ai_project_roundtrip(tmp_path):
    data, digest, cards, request, states = setup()
    corrected, _ = apply_corrections(
        cards,
        digest,
        request,
        states,
        "```json\n" + json.dumps(response(request)) + "\n```",
    )
    assert corrected
    loaded = load_project(save_project(data, cards, name="Sans IA"))
    assert loaded["exchange"] is None
    payload, plan = build_apkg(loaded["cards"], set(), loaded["name"], digest)
    assert plan["included"] == [
        0,
        2,
    ]  # Empty answer and missing masks are listed, never silently exported.
    assert payload[:2] == b"PK"


def test_definition_moves_once_and_original_suffix_is_not_duplicated():
    data = pdf(
        [
            (40, 40, "CARTE"),
            (40, 70, "Concept : est une definition."),
            (60, 110, "- Autre texte."),
        ]
    )
    cards = parse_pdf(data)
    assert cards[0]["definition_moved"]
    req, states = make_request(cards, "x")
    answer = response(req, {0: "Comment definir le concept ?"})
    answer["cards"][0]["move_source_title"] = True
    changed, _ = apply(cards, "x", req, states, answer)
    back = render_blocks(changed[0]["blocks"])
    assert back.count("est une definition.") == 1
    assert back.count("Concept") == 1
    restored = load_project(save_project(data, changed))
    assert fields_for(restored["cards"][0]) == fields_for(changed[0])


def test_project_rejects_damage_versions_duplicate_paths_and_forged_source():
    data, _, cards, _, _ = setup()
    payload = save_project(data, cards)

    def altered(change):
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            files = {n: z.read(n) for n in z.namelist()}
        change(files)
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            for n, b in files.items():
                z.writestr(n, b)
        return out.getvalue()

    def version(files):
        manifest = json.loads(files["project.json"])
        manifest["format"] = "future"
        files["project.json"] = json.dumps(manifest)

    def source(files):
        files["source.pdf"] += b"changed"

    def media(files):
        name = next(n for n in files if n.startswith("media/"))
        files[name] = b"bad"

    def provenance(files):
        m = json.loads(files["project.json"])
        m["cards"][0]["source_elements"][0]["text"] = "forged"
        files["project.json"] = json.dumps(m)

    def traversal(files):
        files["../unsafe"] = b"bad"

    for change in (version, source, media, provenance, traversal):
        with pytest.raises(ValueError):
            load_project(altered(change))
    with pytest.raises(ValueError):
        load_project(b"not a zip")


def test_project_can_resume_the_pending_chatgpt_exchange_after_restart():
    data, digest, cards, req, states = setup()
    restored = load_project(
        save_project(data, cards, exchange=dict(request=req, states=states))
    )
    updated, _ = apply(
        restored["cards"],
        digest,
        restored["exchange"]["request"],
        restored["exchange"]["states"],
        response(req, {1: "Question apres reprise ?"}),
    )
    assert updated[1]["title"] == "Question apres reprise ?"


def test_unchanged_parent_front_keeps_back_and_context_exactly():
    _, digest, cards, _, _ = setup()
    cards[0]["context"] = ["Histologie"]
    cards[0]["front"] = "Histologie — " + cards[0]["title_html"]
    request, states = make_request(cards, digest, [0])
    corrected, changed = apply(cards, digest, request, states, response(request))
    assert corrected == cards and changed == []


def test_project_pending_batch_after_corrected_title_and_manual_body_edits():
    data, digest, cards, req, states = setup()
    cards, _ = apply(
        cards,
        digest,
        req,
        states,
        response(req, {0: "Question initiale ?", 1: "Question seule ?"}),
    )
    # Existing manual edits also need to survive project round trips.
    cards[0]["blocks"][-1]["indent"] = 35.0
    req, states = make_request(cards, digest)
    restored = load_project(
        save_project(data, cards, exchange=dict(request=req, states=states))
    )
    corrected, changed = apply(
        restored["cards"],
        digest,
        req,
        states,
        response(req, {0: "Question apres reprise ?"}),
    )
    assert corrected[0]["blocks"] == restored["cards"][0]["blocks"]
    assert changed == [0]


def test_optional_real_histology_manual_roundtrip_preserves_all_49_images():
    import os
    from pathlib import Path

    path = (
        Path(os.environ.get("ANKI_REFERENCE_DIR", "tests/private-pdfs"))
        / "Anki 2 HISTO.pdf"
    )
    if not path.exists():
        pytest.skip("Private histology PDF unavailable in this environment")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    cards = parse_pdf(data)
    req, states = make_request(cards, digest)
    assert len(cards) == 16 and sum(len(c["media"]) for c in cards) == 49
    corrected, _ = apply(
        cards,
        digest,
        req,
        states,
        response(
            req,
            {
                0: "Quels sont les criteres de reconnaissance des glandes exocrines ?",
                1: "Quel mode de secretion merocrine est decrit dans le cours ?",
                2: "Quel mode de secretion apocrine est decrit dans le cours ?",
            },
        ),
    )
    restored = load_project(save_project(data, corrected))
    for before, after in zip(cards, restored["cards"]):
        assert before["media"] == after["media"]
        assert fields_for(after)[1].endswith(fields_for(before)[1])
    payload, report = build_apkg(restored["cards"], set(), "Histologie", digest)
    assert report["notes"] == report["cards"] == 16 and not report["excluded"]
    assert payload[:2] == b"PK"


def test_project_keeps_subsequent_manual_edits_to_a_restored_definition_heading():
    data, digest, cards, req, states = setup()
    cards, _ = apply(cards, digest, req, states, response(req, {0: "Question ?"}))
    assert cards[0]["blocks"][0].get("restored_source_title")
    cards[0]["blocks"][0]["text"] = "Titre source corrige manuellement"
    restored = load_project(save_project(data, cards))
    assert (
        restored["cards"][0]["blocks"][0]["text"] == "Titre source corrige manuellement"
    )
    assert fields_for(restored["cards"][0]) == fields_for(cards[0])


def test_corrupt_pending_exchange_is_rejected_at_project_load():
    data, _, cards, req, states = setup()
    req.pop("schema")
    with pytest.raises(ValueError, match="Échange"):
        load_project(
            save_project(data, cards, exchange=dict(request=req, states=states))
        )


def test_project_size_limit_applies_before_download_and_on_import(monkeypatch):
    import project

    data, _, cards, _, _ = setup()
    payload = save_project(data, cards)
    monkeypatch.setattr(project, "MAX_PROJECT", 100)
    with pytest.raises(ValueError, match="volumineux"):
        save_project(data, cards)
    with pytest.raises(ValueError, match="volumineux"):
        load_project(payload)


def test_project_duplicate_archive_entries_are_rejected():
    data, _, cards, _, _ = setup()
    payload = save_project(data, cards)
    out = io.BytesIO(payload)
    with pytest.warns(UserWarning, match="Duplicate"):
        with zipfile.ZipFile(out, "a") as archive:
            archive.writestr("source.pdf", data)
    with pytest.raises(ValueError, match="répétées"):
        load_project(out.getvalue())
