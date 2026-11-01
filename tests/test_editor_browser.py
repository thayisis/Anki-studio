"""Real Chromium Pointer Events / emulated touch, not physical Safari or Pencil."""

import base64
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from threading import Thread
from pathlib import Path
import shutil
import pytest
import pymupdf as fitz


@pytest.fixture
def browser_editor():
    from playwright.sync_api import sync_playwright

    executable = shutil.which("chromium")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(
            SimpleHTTPRequestHandler,
            directory=str(Path(__file__).resolve().parents[1] / "io_editor"),
        ),
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    with sync_playwright() as p:
        executable = executable or p.chromium.executable_path
        if not Path(executable).exists():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            pytest.skip("Chromium unavailable")
        browser = p.chromium.launch(
            executable_path=executable,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            viewport={"width": 1024, "height": 900},
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
        page = context.new_page()
        page.add_init_script(
            "window.events=[];addEventListener('message',e=>{if(e.data.type==='streamlit:setComponentValue')events.push(e.data.value)});"
        )
        page.goto(f"http://127.0.0.1:{server.server_port}/index.html")
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 800, 600), False)
        pix.clear_with(190)
        image = "data:image/png;base64," + base64.b64encode(pix.tobytes("png")).decode()
        args = dict(
            editor_id="test",
            canvas_hash="fixture",
            image_url=image,
            width=800,
            height=600,
            masks=[],
            state_token="initial",
        )
        page.evaluate("args=>postMessage({type:'streamlit:render',args},'*')", args)
        page.wait_for_selector("body[data-ready=true]")
        yield page, context, args
        context.close()
        browser.close()
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def acknowledge(page, args):
    page.evaluate(
        """args=>new Promise(resolve=>{
        function done(e){if(e.data.type==='streamlit:setFrameHeight'){
          removeEventListener('message',done);resolve();}}
        addEventListener('message',done);postMessage({type:'streamlit:render',args},'*');
    })""",
        args,
    )


def click_commit(page, selector):
    before = page.evaluate("events.filter(e=>e.kind==='commit').length")
    page.locator(selector).click()
    page.wait_for_function(
        "n=>events.filter(e=>e.kind==='commit').length>n", arg=before, timeout=4000
    )


def last_masks(page):
    return page.evaluate("events.filter(e=>e.kind==='commit').at(-1)?.masks || []")


def xy(page, x, y):
    r = page.locator("#overlay").bounding_box()
    return r["x"] + x * r["width"], r["y"] + y * r["height"]


def touch_drag(page, context, start, end, expect_commit=True):
    before = page.evaluate("events.filter(e=>e.kind==='commit').length")
    client = context.new_cdp_session(page)
    client.send(
        "Input.dispatchTouchEvent",
        {
            "type": "touchStart",
            "touchPoints": [{"x": start[0], "y": start[1], "id": 1}],
        },
    )
    for n in range(1, 9):
        client.send(
            "Input.dispatchTouchEvent",
            {
                "type": "touchMove",
                "touchPoints": [
                    {
                        "x": start[0] + (end[0] - start[0]) * n / 8,
                        "y": start[1] + (end[1] - start[1]) * n / 8,
                        "id": 1,
                    }
                ],
            },
        )
    client.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    client.detach()
    if expect_commit:
        page.wait_for_function(
            "n=>events.filter(e=>e.kind==='commit').length>n", arg=before, timeout=4000
        )


def test_touch_draw_move_resize_preview_zoom_and_responsive_coordinates(browser_editor):
    page, context, args = browser_editor
    assert page.locator("svg rect").count() == 0
    touch_drag(page, context, xy(page, 0.1, 0.1), xy(page, 0.4, 0.35))
    m = last_masks(page)[0]
    assert m["left"] == pytest.approx(0.1, abs=0.005) and m["width"] == pytest.approx(
        0.3, abs=0.005
    )
    assert page.evaluate("events[0].kind") == "editing"
    page.locator("#select").click()
    touch_drag(page, context, xy(page, 0.25, 0.225), xy(page, 0.35, 0.275))
    m = last_masks(page)[0]
    assert m["left"] == pytest.approx(0.2, abs=0.005) and m["top"] == pytest.approx(
        0.15, abs=0.005
    )
    handle = page.locator(".handle[data-handle=se]").bounding_box()
    start = (handle["x"] + handle["width"] / 2, handle["y"] + handle["height"] / 2)
    touch_drag(page, context, start, xy(page, 0.6, 0.5))
    m = last_masks(page)[0]
    assert m["width"] == pytest.approx(0.4, abs=0.005) and m["height"] == pytest.approx(
        0.35, abs=0.005
    )
    page.locator("#question").click()
    assert (
        page.locator("svg rect[data-mask]").first.get_attribute("fill-opacity") == "1"
    )
    page.wait_for_function("events.at(-1)?.kind==='preview'", timeout=4000)
    page.locator("#answer").click()
    assert page.locator("svg rect[data-mask]").first.get_attribute("fill") == "none"
    assert page.locator("#image").get_attribute("src") == args["image_url"]
    page.set_viewport_size({"width": 768, "height": 1024})
    page.locator("#zoom").evaluate(
        "el=>{el.value='2';el.dispatchEvent(new Event('input'))}"
    )
    assert last_masks(page)[0] == m
    assert (
        page.locator("#stage").bounding_box()["width"]
        > page.locator("#viewport").bounding_box()["width"]
    )
    page.locator("#pan").click()
    viewport = page.locator("#viewport").bounding_box()
    touch_drag(
        page,
        context,
        (viewport["x"] + 300, viewport["y"] + 180),
        (viewport["x"] + 100, viewport["y"] + 180),
        expect_commit=False,
    )
    page.wait_for_function(
        "document.getElementById('viewport').scrollLeft>20", timeout=4000
    )
    assert last_masks(page)[0] == m


def test_pen_pointer_events_cancel_undo_redo_and_grouping(browser_editor):
    page, context, args = browser_editor
    start, end = xy(page, 0.2, 0.1), xy(page, 0.5, 0.3)

    def pen(kind, point):
        before = page.evaluate("events.filter(e=>e.kind==='commit').length")
        page.dispatch_event(
            "#overlay",
            kind,
            dict(
                pointerId=7,
                pointerType="pen",
                isPrimary=True,
                button=0,
                clientX=point[0],
                clientY=point[1],
                bubbles=True,
            ),
        )
        if kind in ("pointerup", "pointercancel"):
            page.wait_for_function(
                "n=>events.filter(e=>e.kind==='commit').length>n",
                arg=before,
                timeout=4000,
            )

    pen("pointerdown", start)
    pen("pointermove", end)
    pen("pointerup", end)
    assert len(last_masks(page)) == 1
    # Reproduce the real server canonicalization / acknowledgement round trip.
    snapshot = last_masks(page)
    canonical = [
        {**m, **{k: round(m[k], 8) for k in ("left", "top", "width", "height")}}
        for m in snapshot
    ]
    ack = page.evaluate("events.filter(e=>e.kind==='commit').at(-1).event_id")
    acknowledge(
        page, {**args, "masks": canonical, "state_token": "ack", "ack_event": ack}
    )
    assert page.locator("#undo").is_enabled()
    click_commit(page, "#undo")
    assert last_masks(page) == []
    click_commit(page, "#redo")
    assert len(last_masks(page)) == 1
    before = last_masks(page)
    pen("pointerdown", xy(page, 0.6, 0.1))
    pen("pointermove", xy(page, 0.8, 0.3))
    pen("pointercancel", xy(page, 0.8, 0.3))
    assert last_masks(page) == before
    pen("pointerdown", xy(page, 0.6, 0.1))
    pen("pointermove", xy(page, 0.8, 0.3))
    pen("pointerup", xy(page, 0.8, 0.3))
    assert len(last_masks(page)) == 2
    # An acknowledgement from before this second rectangle may arrive late.
    acknowledge(
        page, {**args, "masks": canonical, "state_token": "stale", "ack_event": ack}
    )
    assert page.locator("svg rect[data-mask]:not([data-handle])").count() == 2
    page.locator("#number").fill("1")
    page.locator("#number").dispatch_event("change")
    assert {m["number"] for m in last_masks(page)} == {1}
    click_commit(page, "#remove")
    assert len(last_masks(page)) == 1
