// ======= State =======
let currentSteps = null;
let currentStepsRight = null;
let currentKind  = "text";
let currentAttr  = null;
let currentDirection = "right_to_left"; 
let currentIssueKind = "gibberish";
let hasDiff = false;

let programmaticScroll = false;
function withProgrammaticScroll(fn, unlockDelay = 160) {
  programmaticScroll = true;
  try { fn(); } finally { setTimeout(() => { programmaticScroll = false; }, unlockDelay); }
}

function computeCenterScrollTop(paneEl, anchorEl) {
  const paneRect = paneEl.getBoundingClientRect();
  const aRect    = anchorEl.getBoundingClientRect();
  const current  = paneEl.scrollTop;
  const delta    = (aRect.top + aRect.height / 2) - (paneRect.top + paneRect.height / 2);
  const target   = current + delta;
  return Math.max(0, Math.min(target, paneEl.scrollHeight - paneEl.clientHeight));
}

function jumpToAnchor(paneEl) {
  if (!paneEl) return;
  const anchor =
    paneEl.querySelector("#focusAnchor") ||
    paneEl.querySelector(".focusTarget") ||
    paneEl.querySelector(".editNewInline") ||
    paneEl.querySelector(".editOldInline");
  if (!anchor) return;

  if (!anchor.hasAttribute("tabindex")) anchor.setAttribute("tabindex", "-1");

  let attempts = 0;
  const MAX_ATTEMPTS = 6;

  const tryCenter = () => {
    attempts += 1;
    paneEl.classList.add("no-smooth");
    const target = computeCenterScrollTop(paneEl, anchor);
    withProgrammaticScroll(() => { paneEl.scrollTop = target; });
    setTimeout(() => paneEl.classList.remove("no-smooth"), 60);

    const paneMid   = paneEl.getBoundingClientRect().top + paneEl.clientHeight / 2;
    const aRect     = anchor.getBoundingClientRect();
    const anchorMid = aRect.top + aRect.height / 2;
    const error     = Math.abs(anchorMid - paneMid);

    if (error > 6 && attempts < MAX_ATTEMPTS) requestAnimationFrame(tryCenter);
    else { try { anchor.focus({ preventScroll: true }); } catch {} }
  };

  requestAnimationFrame(() => requestAnimationFrame(tryCenter));
}

// ======= Render current item =======
async function loadCurrent() {
  const issueType = document.getElementById("issueType").value || "gibberish";
  const r = await fetch(`/render?type=${encodeURIComponent(issueType)}`);
  if (!r.ok) {
    const t = await r.text();
    alert("Render failed: " + t);
    return;
  }
  const data = await r.json();
  if (data) console.log("RENDER →", data);

  const leftPane  = document.getElementById("leftPane");
  const rightPane = document.getElementById("rightPane");

  if ((data.count || 0) === 0) {
    leftPane.textContent = "";
    rightPane.textContent = "";
    document.getElementById("pos").textContent = "0/0";
    currentSteps = null;
    currentStepsRight = null;
    currentKind  = "text";
    currentAttr  = null;
    currentIssueKind = "gibberish";
    currentDirection = "right_to_left";
    return;
  }

  // render panes
  leftPane.innerHTML  = data.left  || "";
  rightPane.innerHTML = data.right || "";
  document.getElementById("pos").textContent = `${data.pos}/${data.count}`;

  // store state (render-kind vs issue-kind)
  currentSteps       = data.steps || null;
  currentStepsRight  = data.steps_right || null;
  currentKind        = data.kind || "text";                 // "text" | "attr" (for rendering)
  currentIssueKind   = data.issue_kind || "gibberish";      // real kind: "duplicate" | "gibberish" | "footnote"
  currentAttr        = data.attr || null;

  // Always treat RIGHT as the correct source → copy right → left
  currentDirection = "right_to_left";

  // Update button label to make direction explicit
  try { document.getElementById("acceptBtn").textContent = "Accept (Right → Left)"; } catch {}

  // focus
  jumpToAnchor(leftPane);
  jumpToAnchor(rightPane);
}

// ======= Helpers =======
function haveBothFiles() {
  const formEl = document.getElementById("uploadForm");
  const a = formEl.querySelector('input[name="original"]')?.files?.[0];
  const b = formEl.querySelector('input[name="modified"]')?.files?.[0];
  return !!(a && b);
}

// Run /diff with only=<kind>, then render
async function runDiff(kind) {
  if (!haveBothFiles()) {
    alert("Please choose both files first.");
    return;
  }
  const formEl = document.getElementById("uploadForm");
  const form = new FormData(formEl);
  // Respect selected kind on first compare
  if (kind && kind !== "all") {
    form.append("only", kind);
  } else {
    form.append("only", "all");
  }

  const res = await fetch("/diff", { method: "POST", body: form });
  if (!res.ok) {
    const msg = await res.text();
    alert("Compare failed: " + msg);
    return;
  }
  const info = await res.json();
  if (info) console.log("DIFF →", info);
  hasDiff = true;

  const pretty = (k) =>
    k === "footnote" ? "footnote attrs" :
    k === "duplicate" ? "duplicate" :
    k === "gibberish" ? "gibberish" : "any";

  if ((info.count || 0) === 0) {
    alert(`No ${pretty(kind)} issues found.`);
    document.getElementById("leftPane").textContent  = "";
    document.getElementById("rightPane").textContent = "";
    document.getElementById("pos").textContent = "0/0";
    currentSteps = null; currentStepsRight = null; currentKind = "text"; currentAttr = null;
    return;
  }

  if (kind) document.getElementById("issueType").value = kind;
  await loadCurrent();
}

// ======= UI wiring =======
document.getElementById("issueType").addEventListener("change", async (e) => {
  const v = e.target.value;
  if (!v) {
    document.getElementById("leftPane").textContent  = "";
    document.getElementById("rightPane").textContent = "";
    document.getElementById("pos").textContent = "0/0";
    currentSteps = null; currentStepsRight = null; currentKind = "text"; currentAttr = null;
    return;
  }
  // If we haven't compared yet, run initial diff once. Otherwise just re-render with new filter.
  if (!hasDiff) {
    await runDiff(v);
  } else {
    // Ask server to recompute issues for this specific kind using current trees
    await fetch("/set_filter", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ only: v }) });
    await loadCurrent();
  }
});

// ======= Navigation & actions =======
document.getElementById("nextBtn").onclick = async () => {
  await fetch("/navigate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dir: "next" }) });
  await loadCurrent();
};

document.getElementById("prevBtn").onclick = async () => {
  await fetch("/navigate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dir: "prev" }) });
  await loadCurrent();
};

// Accept click
document.getElementById("acceptBtn").onclick = async () => {
  if (!currentSteps) return;
  const sendKind = (currentIssueKind === "footnote") ? "attr" : currentIssueKind;
  await fetch("/accept", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      steps: currentSteps,
      steps_right: currentStepsRight,
      kind: sendKind,
      attr: currentAttr,
      direction: currentDirection
    })
  });
  // Always recompute issues to reflect any structural changes and refresh panes
  try { await fetch("/recompute", { method: "POST" }); } catch {}
  await loadCurrent();
};

document.getElementById("rejectBtn").onclick = async () => {
  await fetch("/reject", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
  // After reject, wrap to next item (1 after last becomes 1)
  await fetch("/navigate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dir: "next_wrap" }) });
  await loadCurrent();
};

document.getElementById("applyBtn").onclick = async () => {
  const r = await fetch("/apply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
  if (!r.ok) {
    alert("Apply failed");
    return;
  }
  const data = await r.json();

  // 🔁 Even if nothing *new* applied now, still allow download
  if (!data.download_left && !data.download_right) {
    alert("No output produced.");
    return;
  }

  if (data.applied_left === 0 && data.applied_right === 0 && data.note === "already_applied_only") {
    // Optional soft info, no blocking
    console.info("Nothing new to apply; downloading current buffers.");
  }

  if (data.download_left)  window.open(data.download_left,  "_blank");
  if (data.download_right) window.open(data.download_right, "_blank");

  // Recompute after apply as well
  try { await fetch("/recompute", { method: "POST" }); } catch {}
  await loadCurrent();
};
// ======= Splitter =======
(function splitterInit(){
  const panes    = document.getElementById("panes");
  const leftWrap = document.getElementById("leftWrap");
  const rightWrap= document.getElementById("rightWrap");
  const splitter = document.getElementById("splitter");

  let dragging = false, startX = 0, startLeftWidth = 0;
  function pct(total, px) { return Math.max(20, Math.min(80, (px / total) * 100)); }

  splitter.addEventListener("mousedown", (e) => {
    dragging = true; startX = e.clientX;
    startLeftWidth = leftWrap.getBoundingClientRect().width;
    document.body.classList.add("resizing"); e.preventDefault();
  });
  window.addEventListener("mousemove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - startX, total = panes.getBoundingClientRect().width;
    const leftPct = pct(total, startLeftWidth + dx);
    leftWrap.style.flexBasis = leftPct + "%";
    rightWrap.style.flexBasis = (100 - leftPct) + "%";
    splitter.setAttribute("aria-valuenow", Math.round(leftPct));
  });
  window.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false; document.body.classList.remove("resizing");
  });

  splitter.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    const total = panes.getBoundingClientRect().width;
    const leftRect = leftWrap.getBoundingClientRect();
    let leftPct = Math.max(20, Math.min(80, (leftRect.width / total) * 100));
    leftPct += (e.key === "ArrowRight" ? 2 : -2);
    leftPct = Math.max(20, Math.min(80, leftPct));
    leftWrap.style.flexBasis = leftPct + "%";
    rightWrap.style.flexBasis = (100 - leftPct) + "%";
    splitter.setAttribute("aria-valuenow", Math.round(leftPct));
    e.preventDefault();
  });
})();

// ======= Instant preview =======
(function instantPreview(){
  const formEl = document.getElementById("uploadForm");
  if (!formEl) return;

  const leftPane  = document.getElementById("leftPane");
  const rightPane = document.getElementById("rightPane");

  const originalInput = formEl.querySelector('input[name="original"]');
  const modifiedInput = formEl.querySelector('input[name="modified"]');

  function previewFile(inputEl, paneEl) {
    if (!inputEl || !paneEl || !inputEl.files || !inputEl.files[0]) return;
    const file = inputEl.files[0];
    const reader = new FileReader();
    reader.onload = () => {
      paneEl.textContent = reader.result || "";
      document.getElementById("pos").textContent = "—/—";
      // New files selected invalidate prior diff state
      hasDiff = false;
    };
    reader.readAsText(file);
  }

  originalInput?.addEventListener("change", () => previewFile(originalInput, leftPane));
  modifiedInput?.addEventListener("change", () => previewFile(modifiedInput, rightPane));
})();
