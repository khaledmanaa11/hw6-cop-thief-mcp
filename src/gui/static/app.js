const state = { runs: [], run: null, frames: [], index: 0, timer: null, fogSide: "COP", speed: 700 };

async function fetchRuns() {
  const res = await fetch("/api/runs");
  const data = await res.json();
  state.runs = data.runs || [];
  const sel = document.getElementById("runSelect");
  sel.innerHTML = '<option value="">— select a run —</option>';
  state.runs.forEach(r => {
    const opt = document.createElement("option");
    opt.value = r.name;
    opt.textContent = `${r.name} (${r.turns} turns, ${r.grid ? r.grid.join("x") : "?"})`;
    sel.appendChild(opt);
  });
}

async function loadRun(name) {
  const res = await fetch(`/api/runs/${encodeURIComponent(name)}`);
  if (!res.ok) { alert("Failed to load run: " + name); return; }
  state.run = await res.json();
  state.frames = state.run.frames || [];
  state.index = 0;
  const scrubber = document.getElementById("scrubber");
  scrubber.max = Math.max(0, state.frames.length - 1);
  render();
}

function currentFrame() { return state.frames[state.index] || null; }

function drawBoard(frame) {
  const canvas = document.getElementById("board");
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!frame) return;
  const grid = frame.board.grid;
  const rows = grid[0], cols = grid[1];
  const cw = canvas.width / cols, ch = canvas.height / rows;
  ctx.strokeStyle = "#555";
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) { ctx.strokeRect(c * cw, r * ch, cw, ch); }
  }
  (frame.board.barriers || []).forEach(([r, c]) => {
    ctx.fillStyle = "#444";
    ctx.fillRect(c * cw + 2, r * ch + 2, cw - 4, ch - 4);
  });
  const beliefs = frame.beliefs || {};
  ["COP", "THIEF"].forEach(side => {
    const b = beliefs[side];
    if (b && b.guess) {
      ctx.globalAlpha = 0.3;
      ctx.fillStyle = side === "COP" ? "#2196F3" : "#F44336";
      ctx.fillRect(b.guess[1] * cw + 4, b.guess[0] * ch + 4, cw - 8, ch - 8);
      ctx.globalAlpha = 1;
    }
  });
  ctx.font = `${Math.min(cw, ch) * 0.6}px sans-serif`;
  ctx.textAlign = "center"; ctx.textBaseline = "middle";
  if (frame.board.thief_pos) {
    const [tr, tc] = frame.board.thief_pos;
    ctx.fillStyle = "#F44336"; ctx.fillText("T", tc * cw + cw / 2, tr * ch + ch / 2);
  }
  if (frame.board.cop_pos) {
    const [cr, cc] = frame.board.cop_pos;
    ctx.fillStyle = "#2196F3"; ctx.fillText("C", cc * cw + cw / 2, cr * ch + ch / 2);
  }
}

function renderConversation(frame) {
  const ul = document.getElementById("conversation");
  ul.innerHTML = "";
  (frame.conversation || []).forEach(item => {
    const li = document.createElement("li");
    li.className = item.current ? "current" : "";
    li.textContent = `[${item.from}] ${item.text}`;
    ul.appendChild(li);
  });
}

function renderTelemetry(frame) {
  const el = document.getElementById("telemetry");
  const score = frame.score || {};
  const llm = frame.llm || {};
  const lines = [
    `Turn: ${frame.turn} | Side: ${frame.side} | Move: ${frame.move || "—"}`,
    `Moves left: ${frame.moves_left ?? "?"}`,
    `Confidence: ${frame.confidence || "—"} | Intent: ${frame.intent || "—"}`,
    score.available ? `Score — Cop: ${score.cop} | Thief: ${score.thief}` : "Score: not available",
    llm.latency_ms != null ? `LLM: ${llm.latency_ms}ms | in:${llm.input_tokens} out:${llm.output_tokens}` : "",
  ];
  el.innerHTML = lines.filter(Boolean).map(l => `<div>${l}</div>`).join("");
}

function renderFog(frame) {
  const el = document.getElementById("fogPanel");
  document.getElementById("fogLabel").textContent = state.fogSide;
  const fog = (frame.fog || {})[state.fogSide] || {};
  const lines = [
    `Mode: ${fog.mode || "?"}`,
    `Self: ${fog.self ? fog.self.join(",") : "?"}`,
    `Sees opponent: ${fog.sees_opponent ?? "?"}`,
    `Opponent hint: ${fog.opponent_hint || "?"}`,
    fog.opponent_pos ? `Opponent pos: ${fog.opponent_pos.join(",")}` : "",
  ];
  el.innerHTML = lines.filter(Boolean).map(l => `<div>${l}</div>`).join("");
}

function render() {
  const frame = currentFrame();
  if (!frame) return;
  drawBoard(frame);
  renderConversation(frame);
  renderTelemetry(frame);
  renderFog(frame);
  document.getElementById("scrubber").value = state.index;
}

document.getElementById("prevBtn").addEventListener("click", () => {
  if (state.index > 0) { state.index--; render(); }
});
document.getElementById("nextBtn").addEventListener("click", () => {
  if (state.index < state.frames.length - 1) { state.index++; render(); }
});
document.getElementById("playBtn").addEventListener("click", () => {
  if (state.timer) { clearInterval(state.timer); state.timer = null; return; }
  state.timer = setInterval(() => {
    if (state.index < state.frames.length - 1) { state.index++; render(); }
    else { clearInterval(state.timer); state.timer = null; }
  }, state.speed);
});
document.getElementById("scrubber").addEventListener("input", e => {
  state.index = parseInt(e.target.value); render();
});
document.getElementById("speedSlider").addEventListener("input", e => {
  state.speed = parseInt(e.target.value);
  if (state.timer) { clearInterval(state.timer); state.timer = null; }
});
document.getElementById("runSelect").addEventListener("change", e => {
  if (e.target.value) loadRun(e.target.value);
});
document.getElementById("refreshBtn").addEventListener("click", () => fetchRuns());
document.querySelectorAll(".fog-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    state.fogSide = btn.dataset.side;
    document.querySelectorAll(".fog-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    render();
  });
});

fetchRuns();
