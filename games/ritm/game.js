(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const ACTIONS = {
    clap: {
      id: "clap",
      name: "Хлопок",
      img: "assets/actions/clap.webp",
      color: "#4a7ff0",
      hint: "Хлопни в ладоши перед собой",
      how: "Две ладони вместе — хлоп!",
    },
    stomp: {
      id: "stomp",
      name: "Топ",
      img: "assets/actions/stomp.webp",
      color: "#ef5b6a",
      hint: "Топни ногой по полу",
      how: "Удар ногой об пол",
    },
    pat: {
      id: "pat",
      name: "Колени",
      img: "assets/actions/pat.webp",
      color: "#2ab269",
      hint: "Шлёпни ладонями по коленям",
      how: "Шлёп по коленям",
    },
    shoulder: {
      id: "shoulder",
      name: "Плечи",
      img: "assets/actions/shoulder.webp",
      color: "#9b6dff",
      hint: "Дотронься руками до плеч",
      how: "Руки → на плечи",
    },
    snap: {
      id: "snap",
      name: "Щелчок",
      img: "assets/actions/snap.webp",
      color: "#f0a020",
      hint: "Щёлкни пальцами",
      how: "Щелчок пальцами",
    },
    up: {
      id: "up",
      name: "Вверх",
      img: "assets/actions/up.webp",
      color: "#20b8d4",
      hint: "Подними обе руки вверх",
      how: "Обе руки к потолку",
    },
    rest: {
      id: "rest",
      name: "Пауза",
      img: "assets/actions/rest.webp",
      color: "#6a7f9c",
      hint: "Замри и только слушай музыку",
      how: "Стоим спокойно",
    },
  };

  const pic = (a, cls = "") =>
    `<img class="${cls}" src="${a.img}" alt="${a.name}" width="128" height="128" decoding="async" draggable="false">`;

  const ACTION_IDS = ["clap", "stomp", "pat", "shoulder", "snap", "up", "rest"];
  const SETS = {
    easy: ["clap", "stomp", "rest"],
    normal: ["clap", "stomp", "pat", "shoulder", "rest"],
    hard: ACTION_IDS.slice(),
  };

  const LOOKAHEAD = 0.12;
  const SCHEDULE_AHEAD = 0.28;
  const BEATS_PER_BAR = 4;
  const TIMELINE = 8;

  const ui = {
    setup: $("setup"),
    play: $("play"),
    done: $("done"),
    startBtn: $("startBtn"),
    pauseBtn: $("pauseBtn"),
    stopBtn: $("stopBtn"),
    fullBtn: $("fullBtn"),
    againBtn: $("againBtn"),
    backBtn: $("backBtn"),
    bpm: $("bpm"),
    bars: $("bars"),
    difficulty: $("difficulty"),
    style: $("style"),
    pattern: $("pattern"),
    stage: $("stage"),
    card: $("actionCard"),
    glyph: $("actionGlyph"),
    label: $("actionLabel"),
    hint: $("actionHint"),
    pulse: $("pulseRing"),
    timeline: $("timeline"),
    progress: $("progressBar"),
    beatChip: $("beatChip"),
    barChip: $("barChip"),
    bpmChip: $("bpmChip"),
    playMeta: $("playMeta"),
    upcoming: $("upcoming"),
  };

  const UPCOMING_COUNT = 4;

  let audioCtx = null;
  let master = null;
  let noiseBuf = null;
  let status = "idle";
  let bpm = 96;
  let secPerBeat = 60 / 96;
  let totalBeats = 128;
  let beatIndex = 0;
  let nextBeatTime = 0;
  let schedulerTimer = 0;
  let visualTimer = 0;
  let sequence = [];
  let currentAction = "clap";
  let style = "funk";
  let pausedAt = 0;
  let pauseOffset = 0;
  let startedAt = 0;

  function show(which) {
    ui.setup.hidden = which !== "setup";
    ui.play.hidden = which !== "play";
    ui.done.hidden = which !== "done";
    window.scrollTo(0, 0);
  }

  function selectedActions() {
    return [...document.querySelectorAll("#actionLegend .actionChip.on")].map(
      (el) => el.dataset.id
    );
  }

  function updateActionCount() {
    const selected = selectedActions();
    const body = selected.filter((id) => id !== "rest").length;
    const el = $("actionCount");
    if (!el) return;
    el.textContent =
      body === 0
        ? "Выберите хотя бы одно движение"
        : `Выбрано: ${selected.length} (${body} движений)`;
    el.style.color = body === 0 ? "#d04545" : "#6a82a8";
  }

  function setActionSelection(ids, markCustom = false) {
    const set = new Set(ids);
    document.querySelectorAll("#actionLegend .actionChip").forEach((chip) => {
      const on = set.has(chip.dataset.id);
      chip.classList.toggle("on", on);
      chip.setAttribute("aria-pressed", String(on));
      chip.querySelector(".mark").textContent = on ? "✓" : "";
    });
    if (markCustom && ui.difficulty) ui.difficulty.value = "custom";
    updateActionCount();
  }

  function fillLegend() {
    const box = $("actionLegend");
    const initial = new Set(SETS.normal);
    box.innerHTML = ACTION_IDS.map((id) => {
      const a = ACTIONS[id];
      const on = initial.has(id);
      return `<button type="button" class="actionChip ${on ? "on" : ""}" data-id="${id}" aria-pressed="${on}">
          <span class="mark" aria-hidden="true">${on ? "✓" : ""}</span>
          <div class="ico" style="background:${a.color}22">${pic(a)}</div>
          <strong>${a.name}</strong>
          <span>${a.how}</span>
        </button>`;
    }).join("");

    box.querySelectorAll(".actionChip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const willOn = !chip.classList.contains("on");
        chip.classList.toggle("on", willOn);
        chip.setAttribute("aria-pressed", String(willOn));
        chip.querySelector(".mark").textContent = willOn ? "✓" : "";
        if (ui.difficulty) ui.difficulty.value = "custom";
        updateActionCount();
      });
    });

    $("actionsAll")?.addEventListener("click", () => setActionSelection(ACTION_IDS, true));
    $("actionsNone")?.addEventListener("click", () => {
      // leave clap on so start isn't blocked awkwardly — actually user asked clear; keep clap
      setActionSelection(["clap"], true);
    });
    ui.difficulty?.addEventListener("change", () => {
      const v = ui.difficulty.value;
      if (v !== "custom" && SETS[v]) setActionSelection(SETS[v], false);
    });
    updateActionCount();
  }

  function ensureAudio() {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return false;
    if (!audioCtx) {
      audioCtx = new AC();
      master = audioCtx.createGain();
      master.gain.value = 0.55;
      const comp = audioCtx.createDynamicsCompressor();
      comp.threshold.value = -18;
      comp.knee.value = 10;
      comp.ratio.value = 4;
      comp.attack.value = 0.003;
      comp.release.value = 0.2;
      master.connect(comp);
      comp.connect(audioCtx.destination);
      noiseBuf = audioCtx.createBuffer(1, Math.ceil(audioCtx.sampleRate * 0.35), audioCtx.sampleRate);
      const data = noiseBuf.getChannelData(0);
      for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    }
    if (audioCtx.state === "suspended") audioCtx.resume();
    return true;
  }

  function osc(freq, t, len, amp, type = "triangle", endFreq = 0) {
    if (!audioCtx || !master) return;
    t = Math.max(t, audioCtx.currentTime);
    const o = audioCtx.createOscillator();
    const g = audioCtx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(Math.max(30, freq), t);
    if (endFreq > 0) o.frequency.exponentialRampToValueAtTime(endFreq, t + len);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(Math.max(0.0002, amp), t + 0.01);
    g.gain.exponentialRampToValueAtTime(0.0001, t + len);
    o.connect(g);
    g.connect(master);
    o.start(t);
    o.stop(t + len + 0.03);
  }

  function noiseHit(t, cut, len, amp) {
    if (!audioCtx || !noiseBuf) return;
    t = Math.max(t, audioCtx.currentTime);
    const src = audioCtx.createBufferSource();
    const filter = audioCtx.createBiquadFilter();
    const g = audioCtx.createGain();
    src.buffer = noiseBuf;
    filter.type = "highpass";
    filter.frequency.value = cut;
    g.gain.setValueAtTime(amp, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + len);
    src.connect(filter);
    filter.connect(g);
    g.connect(master);
    src.start(t);
    src.stop(t + len + 0.02);
  }

  function playDrum(kind, t) {
    if (kind === "kick") osc(140, t, 0.18, 0.28, "sine", 48);
    else if (kind === "snare") {
      noiseHit(t, 1600, 0.12, 0.16);
      osc(190, t, 0.07, 0.04, "triangle", 110);
    } else if (kind === "hat") noiseHit(t, 5500, 0.05, 0.07);
    else if (kind === "click") osc(1100, t, 0.04, 0.05, "sine", 700);
  }

  function playMusicBeat(i, t) {
    if (style === "off") return;
    const q = i % 4;
    const k = i % 8;
    if (style === "click") {
      playDrum(q === 0 ? "kick" : "click", t);
      return;
    }
    if (style === "funk") {
      if ([0, 2, 5].includes(k % 8) || q === 0) playDrum("kick", t);
      if (q === 2) playDrum("snare", t);
      playDrum("hat", t);
      if (q === 0 || q === 2) osc([98, 98, 123, 110][q], t, 0.14, 0.07, "triangle");
    } else if (style === "pop") {
      if (q === 0 || q === 2) playDrum(q === 0 ? "kick" : "snare", t);
      else playDrum("hat", t);
      osc([130.8, 164.8, 196, 174.6][q], t, 0.12, 0.035, "triangle");
    } else if (style === "latin") {
      playDrum("hat", t);
      if (q === 0 || q === 3) playDrum("kick", t);
      if (q === 2) playDrum("snare", t);
      osc([146.8, 174.6, 196, 220][q], t, 0.1, 0.04, "sine");
    } else if (style === "kids") {
      if (q === 0) playDrum("kick", t);
      if (q === 2) playDrum("snare", t);
      playDrum("hat", t);
      osc([261.6, 329.6, 392, 349.2][q], t, 0.11, 0.04, "sine");
    }
  }

  function cueActionSound(actionId, t) {
    if (actionId === "rest") return;
    osc(actionId === "stomp" ? 90 : 520, t, 0.05, 0.03, "sine");
  }

  function pickPool() {
    const selected = selectedActions();
    if (selected.length) return selected;
    return SETS.normal.slice();
  }

  function buildSequence() {
    const withRest = pickPool();
    const pool = withRest.filter((x) => x !== "rest");
    const allowRest = withRest.includes("rest");
    const total = totalBeats;
    const mode = ui.pattern.value;
    const seq = [];
    const restOr = (fallback) => (allowRest ? "rest" : fallback);

    const phrase = (len, seeds) => {
      const out = [];
      for (let i = 0; i < len; i++) out.push(seeds[i % seeds.length]);
      return out;
    };

    if (!pool.length) {
      sequence = Array.from({ length: total }, () => "clap");
      return;
    }

    if (mode === "call") {
      while (seq.length < total) {
        const call = pool[Math.floor(Math.random() * pool.length)];
        const answer = pool[Math.floor(Math.random() * pool.length)];
        seq.push(
          call,
          call,
          restOr(call),
          restOr(call),
          answer,
          answer,
          restOr(answer),
          restOr(answer)
        );
      }
    } else if (mode === "build") {
      const stages = [
        phrase(16, [pool[0], pool[0], pool[0], restOr(pool[0])]),
        phrase(16, [pool[0], pool[0], pool[1] || pool[0], pool[1] || pool[0]]),
        phrase(16, [pool[0], pool[1] || pool[0], pool[2] || pool[0], restOr(pool[0])]),
        phrase(16, withRest),
      ];
      for (const part of stages) seq.push(...part);
      while (seq.length < total) {
        seq.push(withRest[seq.length % withRest.length]);
      }
    } else {
      while (seq.length < total) {
        const a = pool[Math.floor(Math.random() * pool.length)];
        const b = pool[Math.floor(Math.random() * pool.length)];
        const cell =
          Math.random() > 0.35
            ? [a, a, b, b]
            : [a, b, a, restOr(a)];
        seq.push(...cell);
      }
    }
    sequence = seq.slice(0, total);
  }

  function renderTimeline(activeIndex) {
    const cells = [];
    for (let i = 0; i < TIMELINE; i++) {
      const idx = activeIndex + i;
      const id = sequence[idx] || "rest";
      const a = ACTIONS[id];
      const cls = i === 0 ? "active" : i === 1 ? "next" : "";
      const when = i === 0 ? "сейчас" : i === 1 ? "дальше" : `+${i}`;
      cells.push(
        `<div class="beatCell ${cls}">
          <div class="mini">${pic(a)}</div>
          <div class="name">${a.name}</div>
          <div class="when">${when}</div>
        </div>`
      );
    }
    ui.timeline.innerHTML = cells.join("");
  }

  function renderUpcoming(fromIndex) {
    const cards = [];
    for (let i = 1; i <= UPCOMING_COUNT; i++) {
      const id = sequence[fromIndex + i] || "rest";
      const a = ACTIONS[id] || ACTIONS.rest;
      const tag = i === 1 ? "Дальше" : `+${i}`;
      const cls = i === 1 ? "first" : "";
      cards.push(`
        <div class="card nextCard ${cls}">
          <div class="tag">${tag}</div>
          <div class="glyph" style="background:${a.color}18">${pic(a)}</div>
          <h2 class="label">${a.name}</h2>
          <p class="hint">${a.how || a.hint}</p>
        </div>`);
    }
    ui.upcoming.innerHTML = cards.join("");
  }

  function setCard(actionId, isCountdown, n, beatIndexForUpcoming) {
    ui.stage.classList.toggle("countdown", !!isCountdown);
    if (isCountdown) {
      ui.glyph.style.background = "#e8f0ff";
      ui.glyph.innerHTML = `<span style="font-family:var(--display);font-size:64px;font-weight:800;color:#355fbc">${n}</span>`;
      ui.label.textContent = n === 0 ? "Поехали!" : "Приготовьтесь";
      ui.hint.textContent = "Слушай долю";
      renderUpcoming(-1);
      return;
    }
    const a = ACTIONS[actionId] || ACTIONS.rest;
    currentAction = a.id;
    ui.glyph.style.background = `${a.color}18`;
    ui.glyph.innerHTML = pic(a);
    ui.label.textContent = a.name;
    ui.hint.textContent = a.hint;
    renderUpcoming(beatIndexForUpcoming ?? 0);
    ui.card.classList.remove("hit");
    void ui.card.offsetWidth;
    ui.card.classList.add("hit");
    ui.pulse.classList.remove("on");
    void ui.pulse.offsetWidth;
    ui.pulse.classList.add("on");
  }

  function updateHud(i) {
    const beatInBar = (i % BEATS_PER_BAR) + 1;
    const bar = Math.floor(i / BEATS_PER_BAR) + 1;
    ui.beatChip.textContent = String(beatInBar);
    ui.barChip.textContent = String(bar);
    ui.progress.style.width = `${Math.min(100, (i / Math.max(1, totalBeats)) * 100)}%`;
    renderTimeline(i);
  }

  function scheduleVisual(i, when) {
    const delay = Math.max(0, (when - audioCtx.currentTime) * 1000 - 8);
    const handle = setTimeout(() => {
      if (status !== "play") return;
      if (i < 0) {
        const n = -i;
        setCard(null, true, n);
        renderTimeline(0);
        return;
      }
      if (i >= totalBeats) {
        finish(true);
        return;
      }
      setCard(sequence[i], false, 0, i);
      updateHud(i);
    }, delay);
    return handle;
  }

  function scheduleBeat(i, when) {
    if (i < 0) {
      if (style !== "off") playDrum(i === -1 ? "kick" : "click", when);
      scheduleVisual(i, when);
      return;
    }
    playMusicBeat(i, when);
    if (style !== "off") cueActionSound(sequence[i], when);
    scheduleVisual(i, when);
  }

  function scheduler() {
    if (status !== "play" || !audioCtx) return;
    while (nextBeatTime < audioCtx.currentTime + SCHEDULE_AHEAD) {
      scheduleBeat(beatIndex, nextBeatTime);
      nextBeatTime += secPerBeat;
      beatIndex += 1;
      if (beatIndex > totalBeats) break;
    }
    schedulerTimer = setTimeout(scheduler, LOOKAHEAD * 1000);
  }

  function clearTimers() {
    clearTimeout(schedulerTimer);
    clearTimeout(visualTimer);
    schedulerTimer = 0;
    visualTimer = 0;
  }

  function start() {
    const bodyCount = selectedActions().filter((id) => id !== "rest").length;
    if (bodyCount === 0) {
      updateActionCount();
      $("actionLegend")?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    if (!ensureAudio()) {
      alert("В этом браузере звук недоступен.");
      return;
    }
    clearTimers();
    bpm = Number(ui.bpm.value);
    secPerBeat = 60 / bpm;
    const bars = Number(ui.bars.value);
    totalBeats = bars * BEATS_PER_BAR;
    style = ui.style.value;
    buildSequence();
    beatIndex = -3;
    status = "play";
    pauseOffset = 0;
    ui.pauseBtn.textContent = "Пауза";
    ui.bpmChip.textContent = String(bpm);
    const picked = selectedActions().filter((id) => id !== "rest").length;
    ui.playMeta.textContent = `${bpm} BPM · ${ui.style.options[ui.style.selectedIndex].text} · ${picked} действий`;
    show("play");
    startedAt = audioCtx.currentTime + 0.12;
    nextBeatTime = startedAt;
    master.gain.setTargetAtTime(0.55, audioCtx.currentTime, 0.02);
    scheduler();
  }

  function pauseToggle() {
    if (status === "paused") {
      ensureAudio();
      const resumeAt = audioCtx.currentTime + 0.1;
      nextBeatTime = resumeAt;
      status = "play";
      ui.pauseBtn.textContent = "Пауза";
      if (master) master.gain.setTargetAtTime(0.55, audioCtx.currentTime, 0.02);
      scheduler();
      return;
    }
    if (status !== "play") return;
    status = "paused";
    clearTimers();
    pausedAt = audioCtx ? audioCtx.currentTime : 0;
    if (master) master.gain.setTargetAtTime(0, audioCtx.currentTime, 0.02);
    ui.pauseBtn.textContent = "Продолжить";
    ui.hint.textContent = "Пауза";
  }

  function finish(completed) {
    clearTimers();
    status = "done";
    if (master && audioCtx) master.gain.setTargetAtTime(0, audioCtx.currentTime, 0.03);
    const played = Math.max(0, Math.min(totalBeats, beatIndex));
    const sec = Math.round(played * secPerBeat);
    const mm = Math.floor(sec / 60);
    const ss = String(sec % 60).padStart(2, "0");
    $("statBeats").textContent = String(played);
    $("statBpm").textContent = String(bpm);
    $("statTime").textContent = `${mm}:${ss}`;
    $("doneText").textContent = completed
      ? `Все ${totalBeats} долей прошли ровно под ${bpm} BPM. Можно ускорить темп или сменить рисунок ритма.`
      : `Остановились на доле ${played} из ${totalBeats}. Ритм уже в теле — повторите ещё раз.`;
    show("done");
  }

  ui.startBtn.addEventListener("click", start);
  ui.againBtn.addEventListener("click", start);
  ui.backBtn.addEventListener("click", () => {
    clearTimers();
    status = "idle";
    show("setup");
  });
  ui.pauseBtn.addEventListener("click", pauseToggle);
  ui.stopBtn.addEventListener("click", () => finish(false));
  ui.fullBtn.addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch (_) {}
  });
  document.addEventListener("fullscreenchange", () => {
    ui.fullBtn.textContent = document.fullscreenElement ? "Свернуть" : "На весь экран";
  });
  document.addEventListener("keydown", (e) => {
    if (ui.play.hidden || e.repeat) return;
    if (e.code === "Space" && !["SELECT", "BUTTON"].includes(document.activeElement?.tagName)) {
      e.preventDefault();
      pauseToggle();
    }
  });
  function hardSilence() {
    clearTimers();
    if (status === "play") status = "paused";
    ui.pauseBtn.textContent = "Продолжить";
    if (master && audioCtx) {
      try { master.gain.cancelScheduledValues(audioCtx.currentTime); } catch (_) {}
      master.gain.setValueAtTime(0, audioCtx.currentTime);
    }
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) hardSilence();
  });
  window.addEventListener("pagehide", hardSilence);
  window.addEventListener("beforeunload", hardSilence);

  fillLegend();
})();
