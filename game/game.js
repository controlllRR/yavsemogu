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
  specials: true,
  phase: "setup", // setup | ready | rolled | moving | won
  lastRoll: [],
  lastSum: 0,
  stepsLeft: 0,
  moveDir: 1, // 1 вперёд, -1 назад
  allowSpecial: false, // спецклетки только после хода по кубикам, не после бонуса
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
    syncModeAvailability();
  });
  bindChips("#diceMode", (v) => {
    state.diceMode = v;
  });

  function syncModeAvailability() {
    // no-op visual for now; mixed with 1 die = digit or dots randomly
  }

  $("#startBtn").addEventListener("click", () => {
    const n = Number($("#playerCount .chip.active").dataset.value);
    state.diceCount = Number($("#diceCount .chip.active").dataset.value);
    state.diceMode = $("#diceMode .level.active").dataset.value;
    state.specials = $("#specialCells").checked;
    const inputs = $$("#namesList input");
    state.players = Array.from({ length: n }, (_, i) => ({
      name: (inputs[i]?.value || DEFAULT_NAMES[i]).trim() || DEFAULT_NAMES[i],
      color: COLORS[i],
      pos: 0, // 0 = start before cell 1; cells are 1..100
      index: i,
    }));
    state.current = 0;
    state.phase = "ready";
    startPlay();
  });
}

function startPlay() {
  $("#setupScreen").classList.add("hidden");
  $("#playScreen").classList.remove("hidden");
  $("#winModal").classList.add("hidden");
  clearMoveMode();
  renderTokens();
  renderRoster();
  updateTurnUI();
  resetDiceUI();
  log("Бросай кубики, посчитай ответ — потом сам ходи фишкой!");
  $("#rollBtn").disabled = false;
  $("#answerBox").classList.add("hidden");
}

function cellXY(pos) {
  // pos 0 = just before start (near cell 1, slightly left)
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
    if (state.phase === "moving" && p.index === state.current) {
      el.classList.add("movable");
      el.setAttribute("role", "button");
      el.tabIndex = 0;
    }
    box.appendChild(el);
  });
}

/** Classic conical board-game pawn (halma-style). */
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
  ul.innerHTML = state.players
    .map(
      (p, i) => `
    <li class="${i === state.current ? "active" : ""}" data-i="${i}">
      <span class="dot" style="background:${p.color}"></span>
      <span>${escapeHtml(p.name)}</span>
      <span class="pos">${p.pos === 0 ? "старт" : p.pos}</span>
    </li>`
    )
    .join("");
}

function updateTurnUI() {
  const p = state.players[state.current];
  $("#turnName").textContent = p.name;
  $("#turnName").style.color = p.color;
  $("#turnPos").textContent = p.pos === 0 ? "на старте" : `клетка ${p.pos}`;
  renderRoster();
}

function resetDiceUI() {
  const row = $("#diceRow");
  row.innerHTML = "";
  const specs = planDiceFaces();
  specs.forEach((spec) => {
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
  if (state.phase !== "moving" || state.stepsLeft <= 0) {
    box.classList.add("hidden");
    hint.classList.add("hidden");
    return;
  }

  const target = nextTargetPos();
  const dirWord = state.moveDir > 0 ? "вперёд" : "назад";
  $("#moveTitle").textContent =
    state.moveDir > 0 ? "Перетащи фишку вперёд" : "Перетащи фишку назад";
  $("#moveSteps").textContent = `Осталось шагов: ${state.stepsLeft}`;
  box.classList.remove("hidden");

  const { x, y } = cellXY(target);
  hint.style.left = `${x}%`;
  hint.style.top = `${y}%`;
  hint.classList.toggle("back", state.moveDir < 0);
  hint.classList.remove("hidden");
  hint.setAttribute("aria-label", `Следующая клетка: ${target === 0 ? "старт" : target}`);

  log(
    `${state.players[state.current].name}: поставь фишку на ${
      target === 0 ? "старт" : `клетку ${target}`
    } (${dirWord}). Осталось ${state.stepsLeft} ${pluralSteps(state.stepsLeft)}.`
  );
}

function clearMoveMode() {
  state.stepsLeft = 0;
  state.moveDir = 1;
  state.drag = null;
  $("#moveBox").classList.add("hidden");
  $("#cellHint").classList.add("hidden");
}

function beginManualMove(steps, dir = 1, reason = "", { fromDice = false } = {}) {
  const player = state.players[state.current];
  let left = steps;

  if (fromDice) state.allowSpecial = true;

  // Если уже у финиша и идём вперёд — ход не нужен
  if (dir > 0 && player.pos >= 100) {
    win(player);
    return;
  }

  // Обрезаем шаги, если до финиша меньше
  if (dir > 0) {
    left = Math.min(left, 100 - player.pos);
  } else {
    left = Math.min(left, player.pos);
  }

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

function finishTurnAfterMove() {
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
      beginManualMove(2, 1, `Зелёная клетка! Перетащи ещё на 2 ${pluralSteps(2)} вперёд 🌟`);
      return;
    }
    if (cell?.kind === "purple") {
      state.allowSpecial = false;
      beginManualMove(2, -1, `Фиолетовая клетка… перетащи на 2 ${pluralSteps(2)} назад 😮`);
      return;
    }
  }

  state.allowSpecial = false;
  nextPlayer();
  resetDiceUI();
  $("#rollBtn").disabled = false;
  state.phase = "ready";
}

function commitStep() {
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
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return Math.hypot(dx, dy);
}

function bindTokenDrag() {
  const board = $("#board");

  const onMove = (e) => {
    const drag = state.drag;
    if (!drag || drag.pointerId !== e.pointerId) return;
    const token = $(`#token-${drag.playerIndex}`);
    if (!token) return;
    const pct = pointerToBoardPct(e.clientX, e.clientY);
    if (!pct) return;
    token.style.left = `${pct.x - drag.offsetX}%`;
    token.style.top = `${pct.y - drag.offsetY}%`;
  };

  const onUp = (e) => {
    const drag = state.drag;
    if (!drag || drag.pointerId !== e.pointerId) return;
    const token = $(`#token-${drag.playerIndex}`);
    state.drag = null;
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onUp);
    document.removeEventListener("pointercancel", onUp);
    if (!token) return;
    token.classList.remove("dragging");

    const pct = pointerToBoardPct(e.clientX, e.clientY);
    const targetPos = nextTargetPos();
    const targetXY = cellXY(targetPos);

    if (pct && distPct(pct, targetXY) <= DROP_RADIUS_PCT) {
      commitStep();
      return;
    }

    token.style.left = `${drag.homeLeft}%`;
    token.style.top = `${drag.homeTop}%`;
    log("Поставь фишку ровно на подсвеченную клетку 🙂");
  };

  board.addEventListener("pointerdown", (e) => {
    if (state.phase !== "moving" || state.busy) return;
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
    $("#playScreen").classList.add("hidden");
    $("#setupScreen").classList.remove("hidden");
    state.phase = "setup";
  });
  $("#winAgain").addEventListener("click", () => {
    clearMoveMode();
    $("#winModal").classList.add("hidden");
    $("#playScreen").classList.add("hidden");
    $("#setupScreen").classList.remove("hidden");
    state.phase = "setup";
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

  bindTokenDrag();
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
  const types = diceEls.map((d) => d.dataset.type);

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
  log(`Выпало: ${describeRoll(values, types)}. Посчитай и введи ответ!`);
  state.busy = false;
}

function describeRoll(values, types) {
  return values
    .map((v, i) => (types[i] === "digit" ? `цифра ${v}` : `${v} ${pluralPoints(v)}`))
    .join(" + ");
}

function pluralPoints(n) {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return "точка";
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return "точки";
  return "точек";
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
    $("#hintText").textContent = "Почти! Посчитай ещё раз 💪";
    $("#hintText").className = "hint bad";
    $("#answerInput").select();
    return;
  }

  $("#hintText").textContent = "Верно! Теперь ходи фишкой 🎉";
  $("#hintText").className = "hint ok";
  $("#checkBtn").disabled = true;
  await wait(350);
  $("#checkBtn").disabled = false;

  beginManualMove(
    state.lastSum,
    1,
    `Верно! Перетащи фишку ${state.lastSum} ${pluralSteps(state.lastSum)} — по одной клетке.`,
    { fromDice: true }
  );
}

function pluralSteps(n) {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return "шаг";
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return "шага";
  return "шагов";
}

function nextPlayer() {
  state.current = (state.current + 1) % state.players.length;
  updateTurnUI();
  log(`Ход: ${state.players[state.current].name}`);
}

function win(player) {
  state.phase = "won";
  clearMoveMode();
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
}

main().catch((err) => {
  console.error(err);
  alert("Не удалось загрузить карту игры. Обновите страницу.");
});
