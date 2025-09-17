<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>XML Proofing — Side by Side</title>
  <link rel="stylesheet" href="/static/styles.css">
  <script src="/static/script.js" defer></script>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script>
</head>
<body>
  <div class="top">
    <form id="uploadForm">
      <!-- LEFT is Input (problem) ; RIGHT is Versioning (source) -->
      <label>Input (problem): <input type="file" name="original" required></label>
      <label>Versioning (source): <input type="file" name="modified" required></label>
      <button type="submit">Compare</button>
    </form>

    <div class="controls">
      <label>Issue type:
        <select id="issueType">
          <option value="gibberish">Gibberish</option>
          <option value="duplicate">Duplicates</option>
          <option value="footnote">Footnote attrs</option>
          <option value="all">All (debug)</option>
        </select>
      </label>
      <button id="prevBtn" type="button">Prev</button>
      <span id="pos">0/0</span>
      <button id="nextBtn" type="button">Next</button>
      <button id="acceptBtn" type="button">Accept</button>
      <button id="rejectBtn" type="button">Reject</button>
      <button id="applyBtn" type="button">Apply & Download</button>
    </div>
  </div>

  <div id="panes" class="panes" aria-label="Side by side diff panes">
    <div id="leftWrap" class="pane" style="flex-basis:50%;">
      <div class="pane-title">Input (problem)</div>
      <pre id="leftPane"></pre>
    </div>

    <div id="splitter" class="splitter" role="separator" aria-orientation="vertical"
         aria-label="Resize panes" aria-valuemin="20" aria-valuemax="80" aria-valuenow="50" tabindex="0"></div>

    <div id="rightWrap" class="pane" style="flex-basis:50%;">
      <div class="pane-title">Versioning (source)</div>
      <pre id="rightPane"></pre>
    </div>
  </div>
</body>
</html>
