const COLORS = ["#ef4444", "#3b82f6", "#22c55e", "#f59e0b"];
const DEFAULT_NAMES = ["Красный", "Синий", "Зелёный", "Жёлтый"];
const DROP_RADIUS_PCT = 5.2;

const PIP_MAP = {
  1: [4],
  2: [0, 8],
  3: [0, 4, 8],
  4: [0, 2, 6, 8],
  5: [0, 2, 4, 6, 8],
  6: [0, 2, 3, 5, 6, 8],
};

const state = {
  cells: [],
  players: [],
  current: 0,
  diceCount: 2,
  diceMode: "mixed", // dots | digits | mixed
  moveMode: "buttons", // buttons | drag
  specials: true,
  phase: "setup", // setup | ready | rolled | moving | won
  lastRoll: [],
  lastSum: 0,
  stepsLeft: 0,
  moveDir: 1,
  allowSpecial: false,
  busy: false,
  drag: null,
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

async function loadCells() {
  const res = await fetch("./cells.json");
  const data = await res.json();
  state.cells = data.cells;
}

function bindSetup() {
  const namesList = $("#namesList");

  function renderNames(n) {
    namesList.innerHTML = "";
    for (let i = 0; i < n; i++) {
      const row = document.createElement("div");
      row.className = "name-row";
      row.innerHTML = `
        <span class="swatch" style="background:${COLORS[i]}"></span>
        <input type="text" maxlength="16" value="${DEFAULT_NAMES[i]}" data-i="${i}" aria-label="Имя игрока ${i + 1}" />
      `;
      namesList.appendChild(row);
    }
  }

  function bindChips(rootId, onPick) {
    const root = $(rootId);
    root.addEventListener("click", (e) => {
      const btn = e.target.closest(".chip, .level");
      if (!btn) return;
      $$(".chip, .level", root).forEach((b) => b.classList.toggle("active", b === btn));
      onPick(btn.dataset.value);
    });
  }

  renderNames(1);
  bindChips("#playerCount", (v) => renderNames(Number(v)));
  bindChips("#diceCount", (v) => {
    state.diceCount = Number(v);
  });
  bindChips("#diceMode", (v) => {
    state.diceMode = v;
  });
  bindChips("#moveMode", (v) => {
    state.moveMode = v;
  });

  $("#startBtn").addEventListener("click", () => {
    applySetupFromUI();
    startPlay();
  });
}

function applySetupFromUI() {
  const n = Number($("#playerCount .chip.active")?.dataset.value || 1);
  state.diceCount = Number($("#diceCount .chip.active")?.dataset.value || 2);
  state.diceMode = $("#diceMode .level.active")?.dataset.value || "mixed";
  state.moveMode = $("#moveMode .level.active")?.dataset.value || "buttons";
  state.specials = $("#specialCells")?.checked !== false;
  const inputs = $$("#namesList input");
  state.players = Array.from({ length: n }, (_, i) => ({
    name: (inputs[i]?.value || DEFAULT_NAMES[i]).trim() || DEFAULT_NAMES[i],
    color: COLORS[i],
    pos: 0,
    index: i,
  }));
  state.current = 0;
  state.phase = "ready";
}

function applyDefaultSetup() {
  state.diceCount = 2;
  state.diceMode = "mixed";
  state.moveMode = "buttons";
  state.specials = true;
  state.players = [
    {
      name: DEFAULT_NAMES[0],
      color: COLORS[0],
      pos: 0,
      index: 0,
    },
  ];
  state.current = 0;
  state.phase = "ready";
}

function startPlay() {
  $("#setupScreen").classList.add("hidden");
  $("#playScreen").classList.remove("hidden");
  $("#winModal").classList.add("hidden");
  clearMoveMode();
  hideSpecialFx();
  renderTokens();
  renderRoster();
  updateTurnUI();
  resetDiceUI();
  log(state.moveMode === "buttons" ? "Бросай кубики и посчитай ответ!" : "Бросай кубики — потом тащи фишку!");
  $("#rollBtn").disabled = false;
  $("#answerBox").classList.add("hidden");
}

function cellXY(pos) {
  if (pos <= 0) {
    const c = state.cells[0];
    return { x: c.x - 2.2, y: c.y - 1.5 };
  }
  const c = state.cells[Math.min(pos, 100) - 1];
  return { x: c.x, y: c.y };
}

function renderTokens() {
  const box = $("#tokens");
  box.innerHTML = "";
  const groups = {};
  state.players.forEach((p) => {
    const key = String(p.pos);
    groups[key] = groups[key] || [];
    groups[key].push(p);
  });
  state.players.forEach((p) => {
    const el = document.createElement("div");
    el.className = `token p${p.index}`;
    el.dataset.n = String(p.index + 1);
    el.dataset.player = String(p.index);
    el.id = `token-${p.index}`;
    el.setAttribute("aria-label", `Фишка игрока ${p.name}`);
    el.innerHTML = pawnSvg(p.index + 1);
    const { x, y } = cellXY(p.pos);
    const stack = groups[String(p.pos)];
    const idx = stack.indexOf(p);
    const ox = (idx - (stack.length - 1) / 2) * 1.6;
    const oy = (idx - (stack.length - 1) / 2) * -1.4;
    el.style.left = `${x + ox}%`;
    el.style.top = `${y + oy}%`;
    el.style.zIndex = String(2 + p.index + idx);
    if (state.phase === "moving" && state.moveMode === "drag" && p.index === state.current) {
      el.classList.add("movable");
      el.setAttribute("role", "button");
      el.tabIndex = 0;
    }
    box.appendChild(el);
  });
}

function pawnSvg(num) {
  return `
    <svg viewBox="0 0 56 84" aria-hidden="true">
      <defs>
        <linearGradient id="pg${num}" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="var(--pawn-dark)"/>
          <stop offset="35%" stop-color="var(--pawn)"/>
          <stop offset="70%" stop-color="var(--pawn-light)"/>
          <stop offset="100%" stop-color="var(--pawn)"/>
        </linearGradient>
        <linearGradient id="ph${num}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--pawn-light)"/>
          <stop offset="55%" stop-color="var(--pawn)"/>
          <stop offset="100%" stop-color="var(--pawn-dark)"/>
        </linearGradient>
      </defs>
      <ellipse cx="28" cy="78" rx="17" ry="4.5" fill="rgba(0,0,0,.3)"/>
      <ellipse cx="28" cy="72" rx="16" ry="6" fill="url(#pg${num})"/>
      <ellipse cx="28" cy="70.5" rx="13" ry="4" fill="var(--pawn-light)" opacity=".35"/>
      <path d="M20 68 C21 48 22 38 24 30 H32 C34 38 35 48 36 68 Z" fill="url(#pg${num})"/>
      <path d="M24 66 C25 48 25.5 40 26.5 32 H29.5 C30.5 40 31 48 32 66 Z" fill="#fff" opacity=".22"/>
      <circle cx="28" cy="22" r="12" fill="url(#ph${num})"/>
      <circle cx="24" cy="18" r="3.5" fill="#fff" opacity=".45"/>
      <text x="28" y="26" text-anchor="middle" font-size="12" font-weight="800" font-family="Nunito,sans-serif" fill="#fff">${num}</text>
    </svg>`;
}

function bounceToken(playerIndex) {
  const el = $(`#token-${playerIndex}`);
  if (!el) return;
  el.classList.remove("bounce");
  void el.offsetWidth;
  el.classList.add("bounce");
}

function renderRoster() {
  const ul = $("#roster");
  ul.classList.toggle("solo", state.players.length < 2);
  ul.innerHTML = state.players
    .map(
      (p, i) => `
    <li class="${i === state.current ? "active" : ""}" data-i="${i}" title="${escapeHtml(p.name)}">
      <span class="dot" style="background:${p.color}"></span>
      <span class="name">${escapeHtml(p.name)}</span>
      <span class="pos">${p.pos === 0 ? "старт" : p.pos}</span>
    </li>`
    )
    .join("");
}

function updateTurnUI() {
  const p = state.players[state.current];
  $("#turnName").textContent = p.name;
  $("#turnName").style.color = p.color;
  $("#turnSwatch").style.background = p.color;
  $("#turnPos").textContent = p.pos === 0 ? "старт" : `${p.pos}`;
  renderRoster();
}

function resetDiceUI() {
  const row = $("#diceRow");
  row.innerHTML = "";
  const specs = planDiceFaces();
  specs.forEach((spec, i) => {
    if (i > 0) {
      const plus = document.createElement("span");
      plus.className = "dice-plus";
      plus.textContent = "+";
      plus.setAttribute("aria-hidden", "true");
      row.appendChild(plus);
    }
    const die = document.createElement("div");
    die.className = `die ${spec.type}`;
    die.dataset.type = spec.type;
    if (spec.type === "digit") {
      die.textContent = "?";
    } else {
      die.innerHTML = `<div class="pips-grid">${Array.from({ length: 9 }, () => `<span class="pip"></span>`).join("")}</div>`;
    }
    row.appendChild(die);
  });
}

function planDiceFaces() {
  const n = state.diceCount;
  if (state.diceMode === "dots") return Array.from({ length: n }, () => ({ type: "pips" }));
  if (state.diceMode === "digits") return Array.from({ length: n }, () => ({ type: "digit" }));
  if (n === 1) return [{ type: Math.random() < 0.5 ? "digit" : "pips" }];
  return [{ type: "digit" }, { type: "pips" }];
}

function setDieValue(el, value) {
  if (el.dataset.type === "digit") {
    el.textContent = String(value);
    return;
  }
  const pips = $$(".pip", el);
  const on = new Set(PIP_MAP[value] || []);
  pips.forEach((pip, i) => pip.classList.toggle("on", on.has(i)));
}

function rollValues(count) {
  return Array.from({ length: count }, () => 1 + Math.floor(Math.random() * 6));
}

function nextTargetPos() {
  const player = state.players[state.current];
  if (state.moveDir > 0) return Math.min(100, player.pos + 1);
  return Math.max(0, player.pos - 1);
}

function updateMoveUI() {
  const box = $("#moveBox");
  const hint = $("#cellHint");
  const stepBtn = $("#stepBtn");
  if (state.phase !== "moving" || state.stepsLeft <= 0) {
    box.classList.add("hidden");
    hint.classList.add("hidden");
    return;
  }

  const target = nextTargetPos();
  const buttons = state.moveMode === "buttons";
  const forward = state.moveDir > 0;

  $("#moveSteps").textContent = `Шагов: ${state.stepsLeft}`;
  $("#moveHint").textContent = buttons
    ? "Жми кнопку — один шаг"
    : "Перетащи фишку на подсветку";

  stepBtn.textContent = forward ? "Дальше →" : "← Назад";
  stepBtn.classList.toggle("back", !forward);
  stepBtn.classList.toggle("hidden", !buttons);

  box.classList.remove("hidden");
  $("#diceStage").classList.add("hidden");
  $("#answerBox").classList.add("hidden");

  const { x, y } = cellXY(target);
  hint.style.left = `${x}%`;
  hint.style.top = `${y}%`;
  hint.classList.toggle("back", !forward);
  hint.classList.remove("hidden");

  log(
    buttons
      ? `${forward ? "Дальше" : "Назад"} · осталось ${state.stepsLeft}`
      : `Тащи на ${target === 0 ? "старт" : target} · осталось ${state.stepsLeft}`
  );
}

function clearMoveMode() {
  state.stepsLeft = 0;
  state.moveDir = 1;
  state.drag = null;
  $("#moveBox").classList.add("hidden");
  $("#cellHint").classList.add("hidden");
  $("#diceStage").classList.remove("hidden");
}

function hideSpecialFx() {
  $("#specialGlow").classList.add("hidden");
  $("#specialGlow").className = "special-glow hidden";
  $("#fxBurst").classList.add("hidden");
  $("#fxBurst").className = "fx-burst hidden";
}

function showSpecialGlow(pos, kind) {
  const glow = $("#specialGlow");
  const { x, y } = cellXY(pos);
  glow.style.left = `${x}%`;
  glow.style.top = `${y}%`;
  glow.className = `special-glow ${kind === "green" ? "good" : "bad"}`;
}

function showFxBurst(pos, kind) {
  const fx = $("#fxBurst");
  const { x, y } = cellXY(pos);
  fx.style.left = `${x}%`;
  fx.style.top = `${y}%`;
  fx.className = `fx-burst ${kind === "green" ? "good" : "bad"}`;
  window.setTimeout(() => {
    fx.classList.add("hidden");
  }, 850);
}

function beginManualMove(steps, dir = 1, reason = "", { fromDice = false } = {}) {
  const player = state.players[state.current];
  let left = steps;

  if (fromDice) state.allowSpecial = true;

  if (dir > 0 && player.pos >= 100) {
    win(player);
    return;
  }

  if (dir > 0) left = Math.min(left, 100 - player.pos);
  else left = Math.min(left, player.pos);

  if (left <= 0) {
    finishTurnAfterMove();
    return;
  }

  state.phase = "moving";
  state.stepsLeft = left;
  state.moveDir = dir;
  state.busy = false;
  $("#answerBox").classList.add("hidden");
  $("#rollBtn").disabled = true;
  if (reason) log(reason);
  renderTokens();
  updateMoveUI();
}

async function animateAutoHop(player, toPos) {
  const from = player.pos;
  const steps = [];
  if (toPos > from) {
    for (let p = from + 1; p <= toPos; p++) steps.push(p);
  } else if (toPos < from) {
    for (let p = from - 1; p >= toPos; p--) steps.push(p);
  }
  for (const pos of steps) {
    player.pos = pos;
    renderTokens();
    bounceToken(player.index);
    updateTurnUI();
    await wait(220);
  }
}

async function applySpecialHop(kind) {
  const player = state.players[state.current];
  const from = player.pos;
  const dir = kind === "green" ? 1 : -1;
  const to =
    dir > 0 ? Math.min(100, from + 2) : Math.max(0, from - 2);

  state.busy = true;
  clearMoveMode();
  showSpecialGlow(from, kind);
  log(kind === "green" ? "Зелёная! +2 вперёд 🌟" : "Фиолетовая… −2 назад 😮");
  await wait(550);

  await animateAutoHop(player, to);
  showFxBurst(to, kind);
  hideSpecialFx();
  updateTurnUI();
  state.busy = false;

  if (player.pos >= 100) {
    win(player);
    return;
  }

  endTurn();
}

async function finishTurnAfterMove() {
  clearMoveMode();
  renderTokens();
  updateTurnUI();

  if (state.phase === "won") return;

  const player = state.players[state.current];
  if (player.pos >= 100) {
    win(player);
    return;
  }

  if (state.specials && state.allowSpecial) {
    const cell = state.cells[player.pos - 1];
    if (cell?.kind === "green") {
      state.allowSpecial = false;
      await applySpecialHop("green");
      return;
    }
    if (cell?.kind === "purple") {
      state.allowSpecial = false;
      await applySpecialHop("purple");
      return;
    }
  }

  endTurn();
}

function endTurn() {
  state.allowSpecial = false;
  if (state.phase === "won") return;
  nextPlayer();
  resetDiceUI();
  $("#rollBtn").disabled = false;
  state.phase = "ready";
}

function commitStep() {
  if (state.phase !== "moving" || state.busy || state.stepsLeft <= 0) return;

  const player = state.players[state.current];
  const target = nextTargetPos();
  player.pos = target;
  state.stepsLeft -= 1;
  updateTurnUI();
  renderTokens();
  bounceToken(player.index);

  if (player.pos >= 100) {
    clearMoveMode();
    win(player);
    return;
  }

  if (state.stepsLeft <= 0) {
    finishTurnAfterMove();
    return;
  }

  updateMoveUI();
}

function pointerToBoardPct(clientX, clientY) {
  const board = $("#board");
  const rect = board.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  return {
    x: ((clientX - rect.left) / rect.width) * 100,
    y: ((clientY - rect.top) / rect.height) * 100,
  };
}

function distPct(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function bindBoardInput() {
  const board = $("#board");

  $("#stepBtn").addEventListener("click", () => {
    if (state.phase !== "moving" || state.moveMode !== "buttons" || state.busy) return;
    commitStep();
  });

  board.addEventListener("pointerdown", (e) => {
    if (state.phase !== "moving" || state.busy || state.moveMode !== "drag") return;

    const token = e.target.closest(".token.movable");
    if (!token) return;
    const playerIndex = Number(token.dataset.player);
    if (playerIndex !== state.current) return;

    e.preventDefault();
    const pct = pointerToBoardPct(e.clientX, e.clientY);
    if (!pct) return;

    const left = parseFloat(token.style.left) || 0;
    const top = parseFloat(token.style.top) || 0;
    state.drag = {
      playerIndex,
      pointerId: e.pointerId,
      offsetX: pct.x - left,
      offsetY: pct.y - top,
      homeLeft: left,
      homeTop: top,
    };
    token.classList.add("dragging");

    const onMove = (ev) => {
      const drag = state.drag;
      if (!drag || drag.pointerId !== ev.pointerId) return;
      const el = $(`#token-${drag.playerIndex}`);
      if (!el) return;
      const p = pointerToBoardPct(ev.clientX, ev.clientY);
      if (!p) return;
      el.style.left = `${p.x - drag.offsetX}%`;
      el.style.top = `${p.y - drag.offsetY}%`;
    };

    const onUp = (ev) => {
      const drag = state.drag;
      if (!drag || drag.pointerId !== ev.pointerId) return;
      const el = $(`#token-${drag.playerIndex}`);
      state.drag = null;
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      document.removeEventListener("pointercancel", onUp);
      if (!el) return;
      el.classList.remove("dragging");

      const p = pointerToBoardPct(ev.clientX, ev.clientY);
      const targetXY = cellXY(nextTargetPos());
      if (p && distPct(p, targetXY) <= DROP_RADIUS_PCT) {
        commitStep();
        return;
      }
      el.style.left = `${drag.homeLeft}%`;
      el.style.top = `${drag.homeTop}%`;
      log("Поставь фишку на подсветку 🙂");
    };

    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
    document.addEventListener("pointercancel", onUp);
  });
}

function bindPlay() {
  $("#rollBtn").addEventListener("click", onRoll);
  $("#checkBtn").addEventListener("click", onCheck);
  $("#answerInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") onCheck();
  });
  $("#restartBtn").addEventListener("click", () => {
    clearMoveMode();
    hideSpecialFx();
    $("#winModal").classList.add("hidden");
    applySetupFromUI();
    if (!state.players.length) applyDefaultSetup();
    startPlay();
  });
  $("#settingsBtn").addEventListener("click", () => {
    clearMoveMode();
    hideSpecialFx();
    $("#winModal").classList.add("hidden");
    $("#playScreen").classList.add("hidden");
    $("#setupScreen").classList.remove("hidden");
    state.phase = "setup";
  });
  $("#winAgain").addEventListener("click", () => {
    clearMoveMode();
    hideSpecialFx();
    $("#winModal").classList.add("hidden");
    applyDefaultSetup();
    startPlay();
  });

  const pad = $("#numpad");
  for (let i = 1; i <= 12; i++) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = String(i);
    b.addEventListener("click", () => {
      $("#answerInput").value = String(i);
      $("#answerInput").focus();
    });
    pad.appendChild(b);
  }

  bindBoardInput();
}

async function onRoll() {
  if (state.busy || state.phase === "won" || state.phase === "moving") return;
  state.busy = true;
  $("#rollBtn").disabled = true;
  $("#answerBox").classList.add("hidden");
  $("#hintText").textContent = "";
  $("#hintText").className = "hint";

  const diceEls = $$("#diceRow .die");
  const values = rollValues(diceEls.length);

  diceEls.forEach((d) => d.classList.add("rolling"));
  const scramble = setInterval(() => {
    diceEls.forEach((d) => setDieValue(d, 1 + Math.floor(Math.random() * 6)));
  }, 70);

  await wait(900);
  clearInterval(scramble);
  diceEls.forEach((d, i) => {
    d.classList.remove("rolling");
    setDieValue(d, values[i]);
  });

  state.lastRoll = values;
  state.lastSum = values.reduce((a, b) => a + b, 0);
  state.phase = "rolled";

  $("#answerInput").value = "";
  $("#answerBox").classList.remove("hidden");
  $("#answerInput").focus();
  log("Посчитай и введи ответ");
  state.busy = false;
}

async function onCheck() {
  if (state.busy || state.phase !== "rolled") return;
  const raw = $("#answerInput").value.trim();
  const ans = Number(raw);
  if (!raw || Number.isNaN(ans)) {
    $("#hintText").textContent = "Введи число";
    $("#hintText").className = "hint bad";
    return;
  }

  if (ans !== state.lastSum) {
    $("#hintText").textContent = "Почти! Ещё раз 💪";
    $("#hintText").className = "hint bad";
    $("#answerInput").select();
    return;
  }

  $("#hintText").textContent = "Верно! 🎉";
  $("#hintText").className = "hint ok";
  $("#checkBtn").disabled = true;
  await wait(280);
  $("#checkBtn").disabled = false;

  const tip =
    state.moveMode === "buttons"
      ? `Верно! Жми «Дальше» · ${state.lastSum}`
      : `Верно! Тащи фишку · ${state.lastSum}`;
  beginManualMove(state.lastSum, 1, tip, { fromDice: true });
}

function nextPlayer() {
  state.current = (state.current + 1) % state.players.length;
  updateTurnUI();
  log(`Ход: ${state.players[state.current].name}`);
}

function win(player) {
  state.phase = "won";
  clearMoveMode();
  hideSpecialFx();
  $("#rollBtn").disabled = true;
  $("#winTitle").textContent = "Победа!";
  $("#winText").textContent = `${player.name} первым дошёл до домика!`;
  $("#winModal").classList.remove("hidden");
  log(`🏆 ${player.name} победил!`);
}

function log(msg) {
  $("#log").textContent = msg;
}

function wait(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function main() {
  await loadCells();
  bindSetup();
  bindPlay();
  applyDefaultSetup();
  startPlay();
}

main().catch((err) => {
  console.error(err);
  alert("Не удалось загрузить карту игры. Обновите страницу.");
});
