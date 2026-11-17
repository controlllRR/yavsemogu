(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const COLORS = [
    null,
    { name: "Красный", hex: "#ef3f36", number: 1 },
    { name: "Жёлтый", hex: "#e9b607", number: 2 },
    { name: "Синий", hex: "#246bdb", number: 3 },
    { name: "Зелёный", hex: "#2ab269", number: 4 },
  ];

  const ui = {
    setup: $("setup"),
    game: $("game"),
    results: $("results"),
    modeCups: $("modeCups"),
    modeTap: $("modeTap"),
    modeNote: $("modeNote"),
    speed: $("speed"),
    count: $("count"),
    beep: $("beep"),
    countdown: $("countdown"),
    start: $("start"),
    stage: $("stage"),
    cue: $("cue"),
    cueNum: $("cueNum"),
    cueCaption: $("cueCaption"),
    progress: $("progressBar"),
    counter: $("counter"),
    pause: $("pause"),
    finish: $("finish"),
    fullscreen: $("fullscreen"),
    modeLabel: $("modeLabel"),
    tapSection: $("tapSection"),
    cupsInfo: $("cupsInfo"),
    errorChip: $("errorChip"),
    errorLive: $("errorLive"),
    streakChip: $("streakChip"),
    streakLive: $("streakLive"),
    streakBanner: $("streakBanner"),
    gradeBadge: $("gradeBadge"),
  };

  let mode = "cups";
  let status = "idle";
  let total = 20;
  let shown = 0;
  let errors = 0;
  let prev = 0;
  let current = 0;
  let timings = [];
  let timer = null;
  let nextAt = 0;
  let remaining = 0;
  let activeCallback = null;
  let cueStarted = 0;
  let pausedAt = 0;
  let remainingReaction = 0;
  let audioCtx = null;
  let countdownNext = 0;
  let streak = 0;
  let bestStreak = 0;
  let bannerTimer = 0;

  function setMode(next) {
    if (status === "play" || status === "countdown") return;
    mode = next;
    const cups = mode === "cups";
    ui.modeCups.classList.toggle("active", cups);
    ui.modeTap.classList.toggle("active", !cups);
    ui.modeCups.setAttribute("aria-pressed", String(cups));
    ui.modeTap.setAttribute("aria-pressed", String(!cups));
    ui.modeNote.innerHTML = cups
      ? "<strong>Как в занятии:</strong> экран показывает команды, ребёнок касается стаканчиков. Программа не видит стол, поэтому правильность здесь не проверяется."
      : "<strong>Интерактивный режим:</strong> ребёнок нажимает кнопки, программа считает ошибки, серию и среднее время реакции. Автосмена по таймеру здесь не нужна.";
    ui.speed.disabled = !cups;
  }

  ui.modeCups.addEventListener("click", () => setMode("cups"));
  ui.modeTap.addEventListener("click", () => setMode("tap"));

  function show(which) {
    ui.setup.hidden = which !== "setup";
    ui.game.hidden = which !== "game";
    ui.results.hidden = which !== "results";
    window.scrollTo(0, 0);
  }

  function clearScheduled() {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    activeCallback = null;
  }

  function schedule(ms, fn) {
    clearScheduled();
    remaining = ms;
    nextAt = performance.now() + ms;
    activeCallback = fn;
    timer = setTimeout(() => {
      timer = null;
      const f = activeCallback;
      activeCallback = null;
      f && f();
    }, ms);
  }

  function tone(high = false) {
    if (!ui.beep.checked) return;
    try {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      audioCtx ??= new AC();
      if (audioCtx.state === "suspended") audioCtx.resume();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.value = high ? 720 : 480;
      gain.gain.setValueAtTime(0.05, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.12);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.13);
    } catch (_) {}
  }

  function pick() {
    const available = [1, 2, 3, 4].filter((x) => x !== prev);
    const val = available[Math.floor(Math.random() * available.length)];
    prev = val;
    return val;
  }

  function bumpCueAnim() {
    ui.cue.style.animation = "none";
    void ui.cue.offsetWidth;
    ui.cue.style.animation = "";
  }

  function updateHud() {
    ui.counter.innerHTML = `<em>Сигнал</em>${shown} / ${total}`;
    ui.progress.style.width = `${(shown / Math.max(1, total)) * 100}%`;
    ui.errorLive.textContent = String(errors);
    ui.streakLive.textContent = String(streak);
  }

  function showStreakBanner(text) {
    clearTimeout(bannerTimer);
    ui.streakBanner.textContent = text;
    ui.streakBanner.classList.add("show");
    bannerTimer = setTimeout(() => ui.streakBanner.classList.remove("show"), 900);
  }

  function flashStage(ok) {
    ui.stage.classList.remove("flashOk", "flashBad");
    void ui.stage.offsetWidth;
    ui.stage.classList.add(ok ? "flashOk" : "flashBad");
  }

  function start() {
    clearScheduled();
    total = parseInt(ui.count.value, 10);
    shown = 0;
    errors = 0;
    prev = 0;
    timings = [];
    current = 0;
    cueStarted = 0;
    streak = 0;
    bestStreak = 0;
    status = "countdown";
    ui.pause.textContent = "Пауза";
    ui.tapSection.hidden = mode !== "tap";
    ui.cupsInfo.hidden = mode !== "cups";
    ui.errorChip.hidden = mode !== "tap";
    ui.streakChip.hidden = mode !== "tap";
    ui.modeLabel.textContent = mode === "cups" ? "Со стаканчиками" : "Ответы на экране";
    ui.progress.style.width = "0%";
    updateHud();
    show("game");
    if (ui.countdown.checked) {
      countdownNext = 3;
      countdownStep();
    } else {
      status = "play";
      nextCue();
    }
  }

  function countdownStep() {
    if (status !== "countdown") return;
    ui.stage.className = "stage wait";
    ui.stage.style.background = "#273650";
    ui.cueNum.className = "waitNum";
    ui.cueNum.textContent = String(countdownNext);
    ui.cueNum.style.color = "";
    ui.cueNum.style.textShadow = "";
    ui.cueCaption.className = "waitCaption";
    ui.cueCaption.textContent = "Приготовьтесь";
    ui.cueCaption.style.color = "";
    bumpCueAnim();
    tone(countdownNext === 1);
    countdownNext--;
    schedule(850, () => {
      if (countdownNext > 0) countdownStep();
      else {
        status = "play";
        nextCue();
      }
    });
  }

  function paintCue(c) {
    const dark = c.number === 2;
    ui.stage.className = "stage";
    ui.stage.style.background = c.hex;
    ui.cueNum.className = "cueNum";
    ui.cueNum.textContent = String(c.number);
    ui.cueNum.style.color = dark ? "#17233a" : "#ffffff";
    ui.cueNum.style.textShadow = dark ? "none" : "";
    ui.cueCaption.className = "cueCaption";
    ui.cueCaption.textContent = c.name;
    ui.cueCaption.style.color = dark ? "#17233a" : "#ffffff";
    ui.cueCaption.style.textShadow = dark ? "none" : "";
    bumpCueAnim();
  }

  function nextCue() {
    if (status !== "play") return;
    if (shown >= total) {
      finish(true);
      return;
    }
    current = pick();
    shown++;
    paintCue(COLORS[current]);
    updateHud();
    cueStarted = performance.now();
    tone();
    if (mode === "cups") schedule(Number(ui.speed.value), nextCue);
  }

  function answer(number, btn) {
    if (status !== "play" || mode !== "tap" || !current) return;
    if (number !== current) {
      errors++;
      streak = 0;
      updateHud();
      flashStage(false);
      if (btn) {
        btn.classList.remove("wrong");
        void btn.offsetWidth;
        btn.classList.add("wrong");
      }
      tone(true);
      return;
    }
    timings.push(performance.now() - cueStarted);
    streak++;
    bestStreak = Math.max(bestStreak, streak);
    updateHud();
    flashStage(true);
    if (btn) {
      btn.classList.remove("correct");
      void btn.offsetWidth;
      btn.classList.add("correct");
    }
    if (streak === 3 || streak === 5 || streak === 10) {
      showStreakBanner(streak === 10 ? "Огонь! ×10" : `Серия ×${streak}!`);
    }
    current = 0;
    ui.cueCaption.textContent = "Верно!";
    schedule(200, nextCue);
  }

  function pause() {
    if (status === "paused") {
      status = pausedAt;
      ui.pause.textContent = "Пауза";
      if (mode === "tap" && status === "play" && cueStarted) {
        cueStarted = performance.now() - remainingReaction;
      }
      const cb = activeCallback;
      if (cb) schedule(remaining, cb);
      else if (status === "play" && current) paintCue(COLORS[current]);
      return;
    }
    if (status !== "play" && status !== "countdown") return;
    pausedAt = status;
    status = "paused";
    remaining = timer === null ? 0 : Math.max(0, nextAt - performance.now());
    if (mode === "tap") remainingReaction = performance.now() - cueStarted;
    clearTimeout(timer);
    timer = null;
    ui.pause.textContent = "Продолжить";
    ui.stage.className = "stage wait";
    ui.stage.style.background = "#273650";
    ui.cueNum.className = "waitNum";
    ui.cueNum.textContent = "Ⅱ";
    ui.cueNum.style.color = "";
    ui.cueCaption.className = "waitCaption";
    ui.cueCaption.textContent = "Пауза";
    ui.cueCaption.style.color = "";
  }

  function resumeIfNeeded() {
    if (status === "paused" && pausedAt === "play" && current) {
      paintCue(COLORS[current]);
    }
  }

  ui.pause.addEventListener("click", () => {
    if (status === "paused") {
      resumeIfNeeded();
      pause();
    } else pause();
  });

  function gradeLabel(accuracy) {
    if (accuracy >= 95) return "Супер! Почти идеально";
    if (accuracy >= 80) return "Отличный результат";
    if (accuracy >= 60) return "Хорошая тренировка";
    return "Ещё немного практики — и будет легче";
  }

  function finish(completed) {
    const was = mode;
    clearScheduled();
    status = "done";
    ui.tapSection.hidden = true;
    ui.cupsInfo.hidden = true;
    const count = shown;
    const avg = timings.length
      ? Math.round(timings.reduce((s, n) => s + n, 0) / timings.length)
      : 0;
    const correct = timings.length;
    const attempts = correct + errors;
    const accuracy = attempts ? Math.round((correct / attempts) * 100) : 0;

    $("resultTitle").textContent = completed ? "Игра окончена!" : "Тренировка остановлена";
    if (was === "cups") {
      $("resultText").textContent =
        "Программа показывала команды. Поскольку ребёнок касался настоящих стаканчиков, правильность ответов не проверялась.";
      ui.gradeBadge.hidden = true;
    } else {
      $("resultText").textContent = gradeLabel(accuracy) + ". Можно ускорить смену или добавить сигналов.";
      ui.gradeBadge.hidden = false;
      ui.gradeBadge.textContent = `Точность ${accuracy}%`;
    }
    $("statCount").textContent = String(count);
    $("statErrors").textContent = was === "tap" ? String(errors) : "—";
    $("statTime").textContent = was === "tap" && avg ? `${(avg / 1000).toFixed(2)} с` : "—";
    $("statStreak").textContent = was === "tap" ? String(bestStreak) : "—";
    show("results");
  }

  ui.start.addEventListener("click", start);
  ui.finish.addEventListener("click", () => finish(false));
  $("again").addEventListener("click", start);
  $("back").addEventListener("click", () => {
    clearScheduled();
    status = "idle";
    show("setup");
  });

  ui.fullscreen.addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (document.documentElement.requestFullscreen) {
        await document.documentElement.requestFullscreen();
      }
    } catch (_) {}
  });
  document.addEventListener("fullscreenchange", () => {
    ui.fullscreen.textContent = document.fullscreenElement ? "Свернуть" : "На весь экран";
  });

  document.querySelectorAll("[data-answer]").forEach((btn) => {
    btn.addEventListener("click", () => answer(Number(btn.dataset.answer), btn));
  });

  document.addEventListener("keydown", (e) => {
    if (ui.game.hidden || e.repeat) return;
    if (
      e.code === "Space" &&
      !["INPUT", "BUTTON", "SELECT"].includes(document.activeElement?.tagName)
    ) {
      e.preventDefault();
      if (status === "paused") resumeIfNeeded();
      pause();
    }
    if (mode === "tap" && ["1", "2", "3", "4"].includes(e.key)) {
      answer(Number(e.key), document.querySelector(`[data-answer="${e.key}"]`));
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden && (status === "play" || status === "countdown")) pause();
  });
})();
