/* Dependency-free Streamlit v1 component. Pointer Events cover mouse, touch and pen. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id),
    svg = $("overlay"),
    NS = "http://www.w3.org/2000/svg";
  const uid = () =>
    globalThis.crypto?.randomUUID?.() ||
    Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
  const instance = uid();
  let lastCommitSeq = 0;
  let seq = 0,
    args = null,
    masks = [],
    selected = null,
    mode = "draw",
    view = "edit",
    active = 1,
    gesture = null,
    history = [],
    future = [],
    serverToken = null;
  const clone = (x) => JSON.parse(JSON.stringify(x)),
    clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const numbers = () =>
    [...new Set(masks.map((m) => m.number))].sort((a, b) => a - b);
  function message(type, data) {
    window.parent.postMessage(
      Object.assign({ isStreamlitMessage: true, type }, data),
      "*",
    );
  }
  function send(kind, extra = {}) {
    if (!args) return;
    seq += 1;
    if (kind === "commit") lastCommitSeq = seq;
    message("streamlit:setComponentValue", {
      value: {
        editor_id: args.editor_id,
        canvas_hash: args.canvas_hash,
        event_id: instance + ":" + seq,
        kind,
        masks: clone(masks),
        ...extra,
      },
      dataType: "json",
    });
  }
  function sameGeometry(a, b) {
    return (
      a.length === b.length &&
      a.every((m, i) => {
        const n = b[i];
        return (
          m.id === n.id &&
          m.number === n.number &&
          ["left", "top", "width", "height"].every(
            (k) => Math.abs(m[k] - n[k]) < 1e-7,
          )
        );
      })
    );
  }
  function frame() {
    message("streamlit:setFrameHeight", {
      height:
        Math.ceil(
          document.querySelector("main").getBoundingClientRect().height,
        ) + 6,
    });
  }
  function node(tag, attrs) {
    const n = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, String(v)));
    svg.appendChild(n);
    return n;
  }
  function selectedMask() {
    return masks.find((m) => m.id === selected);
  }
  function scale() {
    if (!args || gesture) return;
    const width =
      Math.min(args.width, Math.max(100, $("viewport").clientWidth - 2)) *
      Number($("zoom").value);
    $("stage").style.width = width + "px";
    draw();
    frame();
  }
  function draw() {
    svg.textContent = "";
    const box = svg.getBoundingClientRect(),
      w = Math.max(1, box.width),
      h = Math.max(1, box.height);
    for (const m of masks) {
      const preview = view === "question",
        isActive = m.number === active;
      const r = node("rect", {
        x: m.left,
        y: m.top,
        width: m.width,
        height: m.height,
        fill:
          view === "original" || view === "answer"
            ? "none"
            : preview
              ? isActive
                ? "#c62828"
                : "#ffeba2"
              : "#1a73e8",
        "fill-opacity": preview ? 1 : 0.24,
        stroke: m.id === selected ? "#174ea6" : "#555",
        "stroke-width": 2,
        "data-mask": m.id,
      });
      if (view === "original" || view === "answer")
        r.setAttribute("stroke", "none");
      if (view === "edit")
        node("text", {
          x: m.left + 3 / w,
          y: m.top + 16 / h,
          "font-size": 14 / h,
          class: "label",
        }).textContent = String(m.number);
    }
    const m = selectedMask();
    if (m && view === "edit" && mode !== "pan") {
      const handles = {
        nw: [m.left, m.top],
        n: [m.left + m.width / 2, m.top],
        ne: [m.left + m.width, m.top],
        e: [m.left + m.width, m.top + m.height / 2],
        se: [m.left + m.width, m.top + m.height],
        s: [m.left + m.width / 2, m.top + m.height],
        sw: [m.left, m.top + m.height],
        w: [m.left, m.top + m.height / 2],
      };
      for (const [key, [x, y]] of Object.entries(handles)) {
        node("rect", {
          x: x - 22 / w,
          y: y - 22 / h,
          width: 44 / w,
          height: 44 / h,
          fill: "transparent",
          "data-handle": key,
          "data-mask": m.id,
        });
        node("rect", {
          x: x - 7 / w,
          y: y - 7 / h,
          width: 14 / w,
          height: 14 / h,
          class: "handle",
          "data-handle": key,
          "data-mask": m.id,
        });
      }
    }
    $("remove").disabled = !m || view !== "edit";
    $("undo").disabled = !history.length;
    $("redo").disabled = !future.length;
    $("number").disabled = !m || view !== "edit";
    if (m) $("number").value = m.number;
    const nums = numbers();
    if (!nums.includes(active)) active = nums[0] || 1;
    const sel = $("active");
    sel.textContent = "";
    for (const n of nums) {
      const o = document.createElement("option");
      o.value = n;
      o.textContent = String(n);
      sel.appendChild(o);
    }
    sel.value = String(active);
    $("question").disabled = !nums.length;
    $("answer").disabled = !nums.length;
    for (const key of ["draw", "select", "pan"])
      $(key).setAttribute(
        "aria-pressed",
        String(mode === key && view === "edit"),
      );
    $("viewport").classList.toggle("pan", mode === "pan" || view !== "edit");
    $("status").textContent =
      `${masks.length} rectangle(s) · ${nums.length} carte(s) Anki. ` +
      (view === "question"
        ? `Carte ${active} masquée ; valider ensuite sous l’éditeur.`
        : view === "answer"
          ? "Réponses révélées."
          : view === "original"
            ? "Image originale, pixels inchangés."
            : "Toute modification annule la validation.");
  }
  function point(e, box = svg.getBoundingClientRect()) {
    return {
      x: clamp((e.clientX - box.left) / box.width),
      y: clamp((e.clientY - box.top) / box.height),
    };
  }
  function commit(before) {
    if (JSON.stringify(before) !== JSON.stringify(masks)) {
      history.push(before);
      if (history.length > 100) history.shift();
      future = [];
    }
    send("commit");
    draw();
  }
  svg.addEventListener("pointerdown", (e) => {
    if (
      gesture ||
      mode === "pan" ||
      view !== "edit" ||
      (e.pointerType === "mouse" && e.button !== 0)
    )
      return;
    const box = svg.getBoundingClientRect(),
      p = point(e, box),
      handle = e.target.getAttribute("data-handle"),
      id = e.target.getAttribute("data-mask");
    if (!handle && mode === "select" && !id) {
      selected = null;
      draw();
      return;
    }
    const before = clone(masks);
    let action = handle ? "resize" : mode === "select" ? "move" : "draw";
    if (action === "draw") {
      if (masks.length >= 500) {
        $("status").textContent = "Maximum : 500 rectangles.";
        return;
      }
      const existing = numbers();
      const n = (existing.length ? existing[existing.length - 1] : 0) + 1;
      if (n > 99) {
        $("status").textContent =
          "Maximum : 99 numéros. Regrouper ou supprimer des zones.";
        return;
      }
      selected = uid();
      masks.push({
        id: selected,
        number: n,
        left: p.x,
        top: p.y,
        width: 0,
        height: 0,
      });
    } else selected = id;
    const m = selectedMask();
    if (!m) return;
    gesture = {
      id: e.pointerId,
      action,
      handle,
      start: p,
      box,
      before,
      original: clone(m),
    };
    // Invalidate before the drag finishes; a pending edit cannot reuse a prior approval.
    send("editing");
    try {
      svg.setPointerCapture(e.pointerId);
    } catch (_) {}
    e.preventDefault();
    draw();
  });
  svg.addEventListener("pointermove", (e) => {
    if (!gesture || e.pointerId !== gesture.id) return;
    e.preventDefault();
    const g = gesture,
      p = point(e, g.box),
      m = selectedMask(),
      o = g.original;
    if (g.action === "draw") {
      m.left = Math.min(g.start.x, p.x);
      m.top = Math.min(g.start.y, p.y);
      m.width = Math.abs(p.x - g.start.x);
      m.height = Math.abs(p.y - g.start.y);
    }
    if (g.action === "move") {
      m.left = clamp(o.left + p.x - g.start.x, 0, 1 - o.width);
      m.top = clamp(o.top + p.y - g.start.y, 0, 1 - o.height);
    }
    if (g.action === "resize") {
      const minW = Math.min(8 / g.box.width, o.width),
        minH = Math.min(8 / g.box.height, o.height);
      let l = o.left,
        t = o.top,
        r = l + o.width,
        b = t + o.height;
      if (g.handle.includes("w")) l = clamp(p.x, 0, r - minW);
      if (g.handle.includes("e")) r = clamp(p.x, l + minW, 1);
      if (g.handle.includes("n")) t = clamp(p.y, 0, b - minH);
      if (g.handle.includes("s")) b = clamp(p.y, t + minH, 1);
      Object.assign(m, { left: l, top: t, width: r - l, height: b - t });
    }
    draw();
  });
  function finish(e, cancel = false) {
    if (!gesture || e.pointerId !== gesture.id) return;
    const g = gesture;
    gesture = null;
    try {
      svg.releasePointerCapture(e.pointerId);
    } catch (_) {}
    const m = selectedMask();
    if (
      cancel ||
      !m ||
      m.width * g.box.width < 8 ||
      m.height * g.box.height < 8
    ) {
      masks = g.before;
      if (!masks.some((x) => x.id === selected)) selected = null;
    }
    commit(g.before);
  }
  svg.addEventListener("pointerup", (e) => finish(e));
  svg.addEventListener("pointercancel", (e) => finish(e, true));
  svg.addEventListener("lostpointercapture", (e) => {
    if (gesture) finish(e, true);
  });
  function editAction(fn) {
    if (gesture) return;
    const before = clone(masks);
    send("editing");
    fn();
    view = "edit";
    commit(before);
  }
  for (const key of ["draw", "select", "pan"])
    $(key).onclick = () => {
      if (gesture) return;
      mode = key;
      view = "edit";
      draw();
    };
  $("remove").onclick = () =>
    editAction(() => {
      masks = masks.filter((m) => m.id !== selected);
      selected = null;
    });
  $("clear").onclick = () => {
    if (
      masks.length &&
      window.confirm("Effacer toutes les zones ? Leur validation sera annulée.")
    )
      editAction(() => {
        masks = [];
        selected = null;
      });
  };
  $("undo").onclick = () => {
    if (history.length && !gesture) {
      send("editing");
      future.push(clone(masks));
      masks = history.pop();
      selected = null;
      view = "edit";
      send("commit");
      draw();
    }
  };
  $("redo").onclick = () => {
    if (future.length && !gesture) {
      send("editing");
      history.push(clone(masks));
      masks = future.pop();
      selected = null;
      view = "edit";
      send("commit");
      draw();
    }
  };
  $("number").onchange = () => {
    const m = selectedMask(),
      n = Number($("number").value);
    if (m && Number.isInteger(n) && n >= 1 && n <= 99)
      editAction(() => {
        m.number = n;
      });
    else draw();
  };
  function preview() {
    if (gesture) return;
    view = "question";
    draw();
    if (numbers().length) send("preview", { number: active });
  }
  $("question").onclick = preview;
  $("active").onchange = () => {
    active = Number($("active").value);
    preview();
  };
  $("answer").onclick = () => {
    if (gesture) return;
    view = "answer";
    draw();
  };
  $("original").onclick = () => {
    if (gesture) return;
    view = "original";
    draw();
  };
  $("zoom").oninput = scale;
  $("image").onload = () => {
    document.body.dataset.ready = "true";
    scale();
  };
  window.addEventListener("resize", () => {
    if (!gesture) scale();
  });
  window.addEventListener("message", (e) => {
    if (e.source !== window.parent || e.data?.type !== "streamlit:render")
      return;
    const next = e.data.args;
    if (!next || !/^data:image\/png;base64,/.test(next.image_url)) return;
    if (!args || args.editor_id !== next.editor_id) {
      args = next;
      masks = clone(next.masks || []);
      selected = null;
      gesture = null;
      history = [];
      future = [];
      view = "edit";
      mode = "draw";
      $("image").src = next.image_url;
      serverToken = next.state_token;
    } else {
      args = next;
      if (next.state_token !== serverToken && !gesture) {
        // A late server render must not replace a newer local gesture. Tiny
        // canonical rounding differences must not erase undo/selection either.
        const ack = next.ack_event || "";
        const prefix = instance + ":";
        const latest =
          lastCommitSeq === 0 ||
          (ack.startsWith(prefix) &&
            Number(ack.slice(prefix.length)) >= lastCommitSeq);
        if (latest && !sameGeometry(next.masks || [], masks)) {
          masks = clone(next.masks || []);
          selected = null;
          history = [];
          future = [];
        }
        serverToken = next.state_token;
      }
      draw();
    }
    frame();
  });
  message("streamlit:componentReady", { apiVersion: 1 });
  frame();
})();
