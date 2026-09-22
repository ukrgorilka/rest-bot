(() => {
  'use strict';

  const tg = window.Telegram?.WebApp;
  tg?.ready();
  tg?.expand();

  const screen = document.getElementById('screen');
  const balanceEl = document.getElementById('balance');
  const initData = tg?.initData || '';

  const MINES_LEVELS = [
    { id: 'easy', name: 'Лёгкая', icon: '🟢', rows: 9, cols: 9, mines: 10, reward: 250 },
    { id: 'medium', name: 'Средняя', icon: '🟡', rows: 16, cols: 16, mines: 40, reward: 1000 },
    { id: 'hard', name: 'Сложная', icon: '🔴', rows: 16, cols: 24, mines: 80, reward: 2500 },
    { id: 'insane', name: 'Безумная', icon: '💀', rows: 20, cols: 30, mines: 150, reward: 6000 },
  ];

  const SNAKE_LEVELS = [
    { id: 'easy', name: 'Лёгкая', icon: '🟢', cols: 10, rows: 10, stepMs: 180, reward: 10 },
    { id: 'medium', name: 'Средняя', icon: '🟡', cols: 15, rows: 15, stepMs: 145, reward: 25 },
    { id: 'hard', name: 'Сложная', icon: '🔴', cols: 20, rows: 16, stepMs: 115, reward: 50 },
    { id: 'insane', name: 'Безумная', icon: '💀', cols: 26, rows: 20, stepMs: 90, reward: 100 },
  ];

  const state = {
    tab: 'home',
    profile: null,
    game: null,
    runToken: 0,
    busy: false,
    settings: {
      music: true,
      sound: true,
      vibrate: true,
      volume: 0.45,
      track: 'city',
    },
    audio: null,
  };

  function esc(value) {
    return String(value ?? '').replace(/[&<>"']/g, (m) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[m]);
  }

  function notify(text) {
    try { tg?.showAlert(String(text)); } catch (_) {}
  }

  function vibrate(pattern = 20) {
    if (!state.settings.vibrate) return;
    try { tg?.HapticFeedback?.impactOccurred('light'); } catch (_) {}
    try { navigator.vibrate?.(pattern); } catch (_) {}
  }

  async function api(path, data = {}) {
    if (!initData) {
      throw new Error('Открой Mini App через кнопку бота в Telegram.');
    }
    let response;
    try {
      response = await fetch(path, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({ ...data, initData }),
      });
    } catch (_) {
      throw new Error('Сервер Mini App недоступен.');
    }
    let result;
    try {
      result = await response.json();
    } catch (_) {
      throw new Error('Сервер вернул некорректный ответ.');
    }
    if (!response.ok || !result.ok) {
      const errors = {
        already_claimed: 'Бонус уже получен сегодня.',
        too_fast: 'Игра завершилась слишком быстро.',
        invalid_game: 'Сессия игры устарела. Запусти игру заново.',
        unknown_difficulty: 'Неизвестный уровень сложности.',
      };
      throw new Error(errors[result.error] || result.error || 'Ошибка Mini App.');
    }
    return result;
  }

  function saveSettings() {
    try {
      localStorage.setItem('nya_mini_settings', JSON.stringify(state.settings));
    } catch (_) {}
  }

  function loadSettings() {
    try {
      Object.assign(state.settings, JSON.parse(localStorage.getItem('nya_mini_settings') || '{}'));
    } catch (_) {}
  }

  function updateHeader() {
    balanceEl.textContent = `🪙 ${Number(state.profile?.balance || 0).toLocaleString('ru-RU')}`;
  }

  function setBalance(value) {
    if (!state.profile) state.profile = {};
    state.profile.balance = Number(value || 0);
    updateHeader();
  }

  async function loadProfile(silent = false) {
    try {
      const data = await api('/api/mini/profile');
      state.profile = data;
      updateHeader();
      if (!silent && state.tab === 'home') render();
      return data;
    } catch (error) {
      if (!silent) {
        screen.innerHTML = `<section class="card"><h2>⚠️ Mini App</h2><p class="muted">${esc(error.message)}</p><button class="btn" id="retry">Повторить</button></section>`;
        document.getElementById('retry').onclick = () => loadProfile();
      }
      throw error;
    }
  }

  async function finishGame(gameId, score, won = false) {
    try {
      const data = await api('/api/mini/game/finish', {
        game_id: gameId,
        score: Math.max(0, Math.floor(Number(score) || 0)),
        won: !!won,
      });
      if (state.profile) state.profile.balance = Number(state.profile.balance || 0) + Number(data.reward || 0);
      updateHeader();
      return data;
    } catch (error) {
      notify(error.message);
      return null;
    }
  }

  async function startGame(game, difficulty = 'easy') {
    if (state.busy) return null;
    state.busy = true;
    try {
      const data = await api('/api/mini/game/start', { game, difficulty });
      return data.game_id;
    } catch (error) {
      notify(error.message);
      return null;
    } finally {
      state.busy = false;
    }
  }

  function stopGame() {
    state.runToken += 1;
    if (state.game?.cleanup) {
      try { state.game.cleanup(); } catch (_) {}
    }
    state.game = null;
    document.onkeydown = null;
    screen.ontouchstart = null;
    screen.ontouchend = null;
  }

  function tab(name) {
    stopGame();
    state.tab = name;
    render();
  }

  function render() {
    document.querySelectorAll('nav button').forEach((button) => {
      button.classList.toggle('active', button.dataset.tab === state.tab);
    });
    if (state.tab === 'home') renderHome();
    else if (state.tab === 'games') renderGames();
    else if (state.tab === 'rating') renderRating();
    else renderProfile();
  }

  function renderHome() {
    const p = state.profile || {};
    const exp = Number(p.exp || 0);
    const next = Math.max(1, Number(p.next_exp || 1));
    const progress = Math.max(0, Math.min(100, (exp / next) * 100));
    screen.innerHTML = `
      <section class="hero">
        <h1>😼 Привет, ${esc(p.user?.name || 'игрок')}!</h1>
        <div class="muted">Nya Mini Games</div>
        <div class="grid" style="margin-top:12px">
          <div class="stat"><b>🪙 ${Number(p.balance || 0).toLocaleString('ru-RU')}</b><span class="muted">коинов</span></div>
          <div class="stat"><b>⭐ ${Number(p.stars || 0)}</b><span class="muted">Stars</span></div>
        </div>
      </section>
      <section class="card">
        <div class="row"><b>⭐ Уровень ${Number(p.level || 1)}</b><span>${exp}/${next} XP</span></div>
        <div class="progress"><i style="width:${progress}%"></i></div>
      </section>
      <section class="card">
        <div class="row"><h2>🎁 Сегодня</h2><span class="muted">Серия: ${Number(p.streak || 0)}</span></div>
        <button class="btn" id="bonus">Забрать бонус</button>
      </section>
      <section class="card">
        <div class="grid">
          <button class="btn secondary" id="play">🎮 Играть</button>
          <button class="btn secondary" id="prof">👤 Профиль</button>
        </div>
      </section>`;

    document.getElementById('bonus').onclick = claimBonus;
    document.getElementById('play').onclick = () => tab('games');
    document.getElementById('prof').onclick = () => tab('profile');
  }

  function renderGames() {
    screen.innerHTML = `
      <section class="hero">
        <h1>🎮 Игры</h1>
        <div class="muted">Результаты и награды сохраняются в аккаунте.</div>
      </section>
      <div class="game-grid">
        <div class="game-card" id="gmines"><div class="ico">💣</div><b>Сапёр</b><span class="muted small">4 уровня</span></div>
        <div class="game-card" id="gsnake"><div class="ico">🐍</div><b>Змейка</b><span class="muted small">4 уровня</span></div>
        <div class="game-card" id="g2048"><div class="ico">🔢</div><b>2048</b><span class="muted small">Свайпы + кнопки</span></div>
        <div class="game-card" id="greaction"><div class="ico">⚡</div><b>Реакция</b><span class="muted small">Проверь скорость</span></div>
        <div class="game-card" id="gshoot"><div class="ico">🎯</div><b>Тир</b><span class="muted small">10 попаданий</span></div>
        <div class="game-card" id="gsettings"><div class="ico">⚙️</div><b>Настройки</b><span class="muted small">Музыка и эффекты</span></div>
      </div>`;

    document.getElementById('gmines').onclick = () => chooseDifficulty('mines');
    document.getElementById('gsnake').onclick = () => chooseDifficulty('snake');
    document.getElementById('g2048').onclick = game2048;
    document.getElementById('greaction').onclick = reaction;
    document.getElementById('gshoot').onclick = shooter;
    document.getElementById('gsettings').onclick = settings;
  }

  function chooseDifficulty(game) {
    const list = game === 'mines' ? MINES_LEVELS : SNAKE_LEVELS;
    const title = game === 'mines' ? '💣 Сапёр' : '🐍 Змейка';
    screen.innerHTML = `
      <section class="card">
        <div class="row"><h2>${title}</h2><button class="btn secondary back-inline" id="diffBack">← Игры</button></div>
        <p class="muted">Выбери уровень перед запуском.</p>
        <div class="level-grid">
          ${list.map((level) => `
            <button class="level-card" data-level="${level.id}">
              <strong>${level.icon} ${level.name}</strong>
              <span>${level.cols}×${level.rows}${game === 'mines' ? ` · ${level.mines} мин` : ` · +${level.reward} 🪙 за яблоко`}</span>
              <em>${game === 'mines' ? `🏆 ${level.reward.toLocaleString('ru-RU')} 🪙` : `⚡ ${level.stepMs} мс`}</em>
            </button>`).join('')}
        </div>
      </section>`;
    document.getElementById('diffBack').onclick = () => tab('games');
    screen.querySelectorAll('.level-card').forEach((button) => {
      button.onclick = () => game === 'mines' ? mines(button.dataset.level) : snake(button.dataset.level);
    });
  }

  async function renderRating() {
    screen.innerHTML = `<section class="card"><h2>🏆 Рейтинг</h2><p class="muted">Загрузка…</p></section>`;
    try {
      const data = await api('/api/mini/leaderboard');
      if (state.tab !== 'rating') return;
      screen.innerHTML = `
        <section class="hero"><h1>🏆 Рейтинг</h1><div class="muted">По XP аккаунта</div></section>
        <section class="card"><div class="list">
          ${data.rows.map((row, index) => `
            <div class="rank"><b>${index + 1}</b><span>${esc(row.name)}<small>${Number(row.level || 1)} ур.</small></span><strong>${Number(row.exp || 0).toLocaleString('ru-RU')} XP</strong></div>`).join('') || '<p class="muted">Пока никого нет.</p>'}
        </div></section>`;
    } catch (error) {
      screen.innerHTML = `<section class="card"><h2>🏆 Рейтинг</h2><p class="muted">${esc(error.message)}</p></section>`;
    }
  }

  function renderProfile() {
    const p = state.profile || {};
    screen.innerHTML = `
      <section class="hero">
        <h1>👤 ${esc(p.user?.name || 'Игрок')}</h1>
        <div class="muted">${p.user?.username ? '@' + esc(p.user.username) : 'Nya Mini Games'}</div>
        <div class="grid" style="margin-top:12px">
          <div class="stat"><b>🪙 ${Number(p.balance || 0).toLocaleString('ru-RU')}</b><span class="muted">баланс</span></div>
          <div class="stat"><b>⭐ ${Number(p.level || 1)}</b><span class="muted">уровень</span></div>
        </div>
      </section>
      <section class="card">
        <div class="row"><b>📈 XP</b><span>${Number(p.exp || 0)}/${Number(p.next_exp || 1)}</span></div>
        <div class="progress"><i style="width:${Math.min(100, Number(p.exp || 0) / Math.max(1, Number(p.next_exp || 1)) * 100)}%"></i></div>
        <div class="muted small" style="margin-top:8px">🎮 Игр: ${Number(p.games_played || 0)} · 🏆 Побед: ${Number(p.game_wins || 0)} · 🔥 Серия: ${Number(p.streak || 0)}</div>
      </section>
      <section class="card">
        <h2>📊 Активность</h2>
        <div class="grid">
          <div class="stat"><b>${Number(p.activity?.day || 0)}</b><span class="muted">сегодня</span></div>
          <div class="stat"><b>${Number(p.activity?.week || 0)}</b><span class="muted">неделя</span></div>
          <div class="stat"><b>${Number(p.activity?.month || 0)}</b><span class="muted">месяц</span></div>
          <div class="stat"><b>${Number(p.activity?.all || 0)}</b><span class="muted">всё время</span></div>
        </div>
      </section>
      <section class="card">
        <button class="btn" id="profileSettings">⚙️ Настройки профиля</button>
      </section>`;
    document.getElementById('profileSettings').onclick = settings;
  }

  async function claimBonus() {
    const button = document.getElementById('bonus');
    if (!button) return;
    button.disabled = true;
    try {
      const data = await api('/api/mini/bonus');
      setBalance(Number(state.profile?.balance || 0) + Number(data.reward || 0));
      state.profile.streak = data.streak;
      button.textContent = `✅ +${Number(data.reward).toLocaleString('ru-RU')} 🪙`;
      vibrate();
    } catch (error) {
      button.disabled = false;
      button.textContent = error.message;
    }
  }

  function mineNeighbors(index, rows, cols) {
    const r = Math.floor(index / cols);
    const c = index % cols;
    const result = [];
    for (let dr = -1; dr <= 1; dr++) {
      for (let dc = -1; dc <= 1; dc++) {
        if (!dr && !dc) continue;
        const nr = r + dr;
        const nc = c + dc;
        if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) result.push(nr * cols + nc);
      }
    }
    return result;
  }

  async function mines(levelId = 'easy') {
    stopGame();
    const level = MINES_LEVELS.find((item) => item.id === levelId) || MINES_LEVELS[0];
    const gameId = await startGame('mines', level.id);
    if (!gameId) return;

    let bombs = new Set();
    let opened = new Set();
    let flags = new Set();
    let numbers = new Map();
    let firstClick = true;
    let ended = false;
    let mode = 'dig';
    const token = state.runToken;

    function makeBoard(safeIndex) {
      bombs = new Set();
      while (bombs.size < level.mines) {
        const candidate = Math.floor(Math.random() * level.rows * level.cols);
        if (candidate === safeIndex) continue;
        bombs.add(candidate);
      }
      numbers = new Map();
      for (let i = 0; i < level.rows * level.cols; i++) {
        if (bombs.has(i)) continue;
        numbers.set(i, mineNeighbors(i, level.rows, level.cols).filter((n) => bombs.has(n)).length);
      }
    }

    function floodFill(start) {
      const queue = [start];
      const seen = new Set();
      while (queue.length) {
        const index = queue.shift();
        if (seen.has(index) || flags.has(index) || bombs.has(index)) continue;
        seen.add(index);
        opened.add(index);
        if ((numbers.get(index) || 0) === 0) {
        for (const n of mineNeighbors(index, level.rows, level.cols)) {
          if (!seen.has(n) && !bombs.has(n)) queue.push(n);
        }
      }
      }
    }

    function endBoard(message, won) {
      if (ended) return;
      ended = true;
      renderBoard(message, true);
      finishGame(gameId, opened.size, won).then((data) => {
        if (!data) return;
        const result = document.getElementById('mineResult');
        if (result) result.textContent = won ? `🏆 Победа! +${Number(data.reward || 0).toLocaleString('ru-RU')} 🪙` : `💥 Мина! Получено: ${Number(data.reward || 0)} 🪙`;
      });
    }

    function handleCell(index, action) {
      if (ended || !state.game || token !== state.runToken) return;
      if (firstClick) {
        makeBoard(index);
        firstClick = false;
      }
      if (action === 'flag') {
        if (opened.has(index)) return;
        flags.has(index) ? flags.delete(index) : flags.add(index);
        renderBoard('', false);
        return;
      }
      if (flags.has(index)) return;
      if (bombs.has(index)) {
        opened.add(index);
        endBoard('💥 Мина!', false);
        return;
      }
      floodFill(index);
      if (opened.size >= level.rows * level.cols - level.mines) {
        endBoard('🏆 Поле очищено!', true);
        return;
      }
      renderBoard('', false);
    }

    function bindCells() {
      screen.querySelectorAll('.cell[data-i]').forEach((button) => {
        const index = Number(button.dataset.i);
        let pressTimer = null;
        let longHandled = false;
        let suppressClick = false;
        button.addEventListener('contextmenu', (event) => {
          event.preventDefault();
          handleCell(index, 'flag');
        });
        button.addEventListener('pointerdown', (event) => {
          if (event.pointerType === 'mouse') {
            if (event.button === 2) return;
            handleCell(index, mode);
            return;
          }
          longHandled = false;
          suppressClick = false;
          pressTimer = setTimeout(() => {
            longHandled = true;
            suppressClick = true;
            handleCell(index, 'flag');
            vibrate(10);
          }, 450);
        }, { passive: false });
        button.addEventListener('pointerup', (event) => {
          if (event.pointerType === 'mouse') return;
          if (pressTimer) clearTimeout(pressTimer);
          if (!longHandled) {
            suppressClick = true;
            handleCell(index, mode);
          }
        }, { passive: false });
        button.addEventListener('pointercancel', () => {
          if (pressTimer) clearTimeout(pressTimer);
          suppressClick = true;
        });
        button.addEventListener('click', (event) => {
          if (suppressClick) {
            event.preventDefault();
            event.stopPropagation();
            suppressClick = false;
          }
        });
      });
    }

    function renderBoard(message = '', final = false) {
      if (token !== state.runToken) return;
      const cells = [];
      for (let i = 0; i < level.rows * level.cols; i++) {
        const isOpen = opened.has(i);
        const isMine = bombs.has(i) && final;
        const text = flags.has(i) ? '🚩' : (isMine ? '💥' : (isOpen ? (numbers.get(i) || '') : ''));
        cells.push(`<button class="cell ${isOpen ? 'open' : ''} ${isMine ? 'mine' : ''}" data-i="${i}">${text}</button>`);
      }
      screen.innerHTML = `
        <section class="card mine-wrap">
          <div class="row"><h2>💣 Сапёр</h2><button class="btn secondary" id="mineBack">← Уровни</button></div>
          <div class="row"><span class="muted">${level.cols}×${level.rows} · ${level.mines} мин</span><span class="muted">${mode === 'dig' ? '⛏ Копать' : '🚩 Флаг'}</span></div>
          <div class="grid" style="margin-top:8px">
            <button class="btn ${mode === 'dig' ? '' : 'secondary'}" id="digMode">⛏ Копать</button>
            <button class="btn ${mode === 'flag' ? '' : 'secondary'}" id="flagMode">🚩 Флаг</button>
          </div>
          <div class="board" style="grid-template-columns:repeat(${level.cols}, minmax(0,1fr))">${cells.join('')}</div>
          <p id="mineResult" class="muted">${esc(message)}</p>
        </section>`;
      document.getElementById('mineBack').onclick = () => { stopGame(); chooseDifficulty('mines'); };
      document.getElementById('digMode').onclick = () => { mode = 'dig'; renderBoard(); };
      document.getElementById('flagMode').onclick = () => { mode = 'flag'; renderBoard(); };
      if (!final) bindCells();
    }

    state.game = { cleanup: () => {} };
    renderBoard('Первый клик безопасный. Удачи!');
  }

  async function snake(levelId = 'easy') {
    stopGame();
    const level = SNAKE_LEVELS.find((item) => item.id === levelId) || SNAKE_LEVELS[0];
    const gameId = await startGame('snake', level.id);
    if (!gameId) return;

    const token = state.runToken;
    let snakeBody = [{ x: Math.floor(level.cols / 2), y: Math.floor(level.rows / 2) }];
    let direction = { x: 1, y: 0 };
    let queued = { x: 1, y: 0 };
    let food = null;
    let score = 0;
    let running = true;
    let timer = null;

    screen.innerHTML = `
      <section class="card">
        <div class="row"><h2>🐍 Змейка</h2><button class="btn secondary" id="snakeBack">← Уровни</button></div>
        <div class="row"><span class="muted">${level.name} · ${level.cols}×${level.rows}</span><b id="snakeScore">0</b></div>
        <canvas id="snakeCanvas" class="snake-canvas"></canvas>
        <div class="pad" id="snakePad">
          <span></span><button data-dir="up">⬆️</button><span></span>
          <button data-dir="left">⬅️</button><button data-dir="down">⬇️</button><button data-dir="right">➡️</button>
        </div>
        <p id="snakeResult" class="muted"></p>
      </section>`;

    const canvas = document.getElementById('snakeCanvas');
    const ctx = canvas.getContext('2d');
    const scoreEl = document.getElementById('snakeScore');

    function fitCanvas() {
      const width = Math.max(260, Math.min(680, canvas.clientWidth || canvas.parentElement.clientWidth - 32));
      const aspect = level.rows / level.cols;
      const height = Math.max(220, Math.round(width * aspect));
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.aspectRatio = `${level.cols}/${level.rows}`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      canvas._cssWidth = width;
      canvas._cssHeight = height;
    }

    function placeFood() {
      const occupied = new Set(snakeBody.map((part) => `${part.x}:${part.y}`));
      const free = [];
      for (let y = 0; y < level.rows; y += 1) {
        for (let x = 0; x < level.cols; x += 1) {
          if (!occupied.has(`${x}:${y}`)) free.push({ x, y });
        }
      }
      if (!free.length) {
        food = null;
        endSnake(true);
        return;
      }
      food = free[Math.floor(Math.random() * free.length)];
    }

    function changeDirection(next) {
      const opposite = direction.x + next.x === 0 && direction.y + next.y === 0;
      if (!opposite) queued = next;
    }

    function drawSnake() {
      if (token !== state.runToken) return;
      const width = canvas._cssWidth || canvas.clientWidth;
      const height = canvas._cssHeight || canvas.clientHeight;
      const cellW = width / level.cols;
      const cellH = height / level.rows;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#11131c';
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = 'rgba(255,255,255,.035)';
      ctx.lineWidth = 1;
      for (let x = 1; x < level.cols; x++) { ctx.beginPath(); ctx.moveTo(x * cellW, 0); ctx.lineTo(x * cellW, height); ctx.stroke(); }
      for (let y = 1; y < level.rows; y++) { ctx.beginPath(); ctx.moveTo(0, y * cellH); ctx.lineTo(width, y * cellH); ctx.stroke(); }
      if (food) {
        ctx.fillStyle = '#ff6f91';
        ctx.beginPath();
        ctx.arc((food.x + 0.5) * cellW, (food.y + 0.5) * cellH, Math.min(cellW, cellH) * 0.32, 0, Math.PI * 2);
        ctx.fill();
      }
      snakeBody.forEach((part, index) => {
        ctx.fillStyle = index === 0 ? '#b98cff' : '#62e6a8';
        const pad = Math.max(1, Math.min(cellW, cellH) * 0.08);
        ctx.fillRect(part.x * cellW + pad, part.y * cellH + pad, cellW - pad * 2, cellH - pad * 2);
      });
      scoreEl.textContent = `🍎 ${score}`;
    }

    async function endSnake(won = false) {
      if (!running) return;
      running = false;
      if (timer) clearInterval(timer);
      const result = await finishGame(gameId, score, won);
      document.getElementById('snakeResult').textContent = result ? (won ? `🏆 Поле заполнено · +${Number(result.reward || 0).toLocaleString('ru-RU')} 🪙` : `Игра окончена · +${Number(result.reward || 0).toLocaleString('ru-RU')} 🪙`) : 'Игра окончена.';
    }

    function tick() {
      if (!running || token !== state.runToken) return;
      direction = queued;
      const head = { x: snakeBody[0].x + direction.x, y: snakeBody[0].y + direction.y };
      const hitWall = head.x < 0 || head.y < 0 || head.x >= level.cols || head.y >= level.rows;
      const hitSelf = snakeBody.some((part, index) => index > 0 && part.x === head.x && part.y === head.y);
      if (hitWall || hitSelf) { endSnake(); return; }
      snakeBody.unshift(head);
      if (food && head.x === food.x && head.y === food.y) {
        score += 1;
        placeFood();
        vibrate(8);
      } else {
        snakeBody.pop();
      }
      drawSnake();
    }

    const keyHandler = (event) => {
      const mapping = {
        ArrowUp: { x: 0, y: -1 }, ArrowDown: { x: 0, y: 1 },
        ArrowLeft: { x: -1, y: 0 }, ArrowRight: { x: 1, y: 0 },
      };
      if (mapping[event.key]) {
        event.preventDefault();
        changeDirection(mapping[event.key]);
      }
    };
    document.onkeydown = keyHandler;
    document.getElementById('snakePad').querySelectorAll('button').forEach((button) => {
      button.onclick = () => {
        const dir = button.dataset.dir;
        changeDirection({ up: { x: 0, y: -1 }, down: { x: 0, y: 1 }, left: { x: -1, y: 0 }, right: { x: 1, y: 0 } }[dir]);
        vibrate(8);
      };
    });
    document.getElementById('snakeBack').onclick = () => { stopGame(); chooseDifficulty('snake'); };
    window.addEventListener('resize', fitCanvas);
    state.game = { cleanup: () => { running = false; if (timer) clearInterval(timer); window.removeEventListener('resize', fitCanvas); document.onkeydown = null; } };
    fitCanvas();
    placeFood();
    drawSnake();
    timer = setInterval(tick, level.stepMs);
  }

  async function game2048() {
    stopGame();
    const gameId = await startGame('2048');
    if (!gameId) return;
    const token = state.runToken;
    let board = Array(16).fill(0);
    let score = 0;
    let ended = false;
    let touchStart = null;

    function addTile() {
      const free = board.map((value, index) => value ? -1 : index).filter((index) => index >= 0);
      if (!free.length) return;
      const index = free[Math.floor(Math.random() * free.length)];
      board[index] = Math.random() < 0.9 ? 2 : 4;
    }

    function slide(line) {
      const values = line.filter(Boolean);
      const result = [];
      for (let i = 0; i < values.length; i++) {
        if (i + 1 < values.length && values[i] === values[i + 1]) {
          const merged = values[i] * 2;
          result.push(merged);
          score += merged;
          i++;
        } else result.push(values[i]);
      }
      while (result.length < 4) result.push(0);
      return result;
    }

    function canMove() {
      if (board.some((v) => !v)) return true;
      for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) {
        const i = r * 4 + c;
        if (c < 3 && board[i] === board[i + 1]) return true;
        if (r < 3 && board[i] === board[i + 4]) return true;
      }
      return false;
    }

    function updateTiles() {
      if (token !== state.runToken) return;
      const tileBox = document.getElementById('tiles');
      tileBox.innerHTML = board.map((value) => `<div class="tile ${value ? `tile-${value}` : ''}">${value || ''}</div>`).join('');
      document.getElementById('score2048').textContent = `🏆 ${score}`;
    }

    async function finish2048(won = false) {
      if (ended) return;
      ended = true;
      const result = await finishGame(gameId, score, won);
      const text = document.getElementById('result2048');
      if (text) text.textContent = won ? `🏆 2048! +${Number(result?.reward || 0).toLocaleString('ru-RU')} 🪙` : `Игра окончена · +${Number(result?.reward || 0).toLocaleString('ru-RU')} 🪙`;
    }

    async function move(dir) {
      if (ended) return;
      const before = board.join(',');
      let rows = Array.from({ length: 4 }, (_, r) => board.slice(r * 4, r * 4 + 4));
      if (dir === 'up' || dir === 'down') rows = Array.from({ length: 4 }, (_, c) => rows.map((row) => row[c]));
      rows = rows.map((line) => {
        const reverse = dir === 'right' || dir === 'down';
        if (reverse) line.reverse();
        const result = slide(line);
        if (reverse) result.reverse();
        return result;
      });
      if (dir === 'up' || dir === 'down') {
        board = Array(16).fill(0);
        rows.forEach((line, c) => line.forEach((value, r) => { board[r * 4 + c] = value; }));
      } else {
        board = rows.flat();
      }
      if (board.join(',') !== before) {
        addTile();
        updateTiles();
        if (board.includes(2048)) { await finish2048(true); return; }
        if (!canMove()) await finish2048(false);
      }
    }

    screen.innerHTML = `
      <section class="card">
        <div class="row"><h2>🔢 2048</h2><button class="btn secondary" id="b2048">← Игры</button></div>
        <div class="row"><span id="score2048">🏆 0</span><span class="muted">Собери 2048</span></div>
        <div class="tiles" id="tiles"></div>
        <div class="pad" id="pad2048">
          <span></span><button data-dir="up">⬆️</button><span></span>
          <button data-dir="left">⬅️</button><button data-dir="down">⬇️</button><button data-dir="right">➡️</button>
        </div>
        <p id="result2048" class="muted"></p>
      </section>`;
    document.getElementById('b2048').onclick = () => tab('games');
    const keyHandler = (event) => {
      const direction = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right' }[event.key];
      if (direction) { event.preventDefault(); move(direction); }
    };
    document.onkeydown = keyHandler;
    document.getElementById('pad2048').querySelectorAll('button').forEach((button) => {
      button.onclick = () => move(button.dataset.dir);
    });
    screen.ontouchstart = (event) => {
      const point = event.changedTouches?.[0];
      if (point) touchStart = { x: point.clientX, y: point.clientY };
    };
    screen.ontouchend = (event) => {
      if (!touchStart) return;
      const point = event.changedTouches?.[0];
      if (!point) return;
      const dx = point.clientX - touchStart.x;
      const dy = point.clientY - touchStart.y;
      touchStart = null;
      if (Math.max(Math.abs(dx), Math.abs(dy)) < 25) return;
      move(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up'));
    };
    state.game = { cleanup: () => { ended = true; document.onkeydown = null; screen.ontouchstart = null; screen.ontouchend = null; } };
    addTile(); addTile(); updateTiles();
  }

  async function reaction() {
    stopGame();
    const gameId = await startGame('reaction');
    if (!gameId) return;
    const token = state.runToken;
    let ready = false;
    let started = 0;
    let finished = false;
    let timer = null;

    screen.innerHTML = `
      <section class="card">
        <div class="row"><h2>⚡ Реакция</h2><button class="btn secondary" id="reactionBack">← Игры</button></div>
        <div class="reaction" id="reactionBox">Жди сигнал…</div>
        <p id="reactionResult" class="muted"></p>
      </section>`;
    const box = document.getElementById('reactionBox');
    document.getElementById('reactionBack').onclick = () => tab('games');

    function finishEarly() {
      if (finished) return;
      finished = true;
      if (timer) clearTimeout(timer);
      box.textContent = 'Слишком рано! 😿';
      document.getElementById('reactionResult').textContent = 'Победа не засчитана.';
      setTimeout(() => { if (token === state.runToken) tab('games'); }, 600);
    }

    timer = setTimeout(() => {
      if (token !== state.runToken || finished) return;
      ready = true;
      started = performance.now();
      box.textContent = 'ЖМИ!';
      box.classList.add('ready');
      vibrate(15);
    }, 1000 + Math.random() * 2200);

    box.onclick = async () => {
      if (finished) return;
      if (!ready) { finishEarly(); return; }
      finished = true;
      const ms = Math.max(1, Math.round(performance.now() - started));
      if (timer) clearTimeout(timer);
      const score = Math.max(1, Math.min(500, 500 - ms));
      const result = await finishGame(gameId, score, true);
      box.textContent = `${ms} мс`;
      document.getElementById('reactionResult').textContent = result ? `🏆 +${Number(result.reward || 0).toLocaleString('ru-RU')} 🪙` : 'Результат сохранён.';
    };

    state.game = { cleanup: () => { finished = true; if (timer) clearTimeout(timer); } };
  }

  async function shooter() {
    stopGame();
    const gameId = await startGame('shooter');
    if (!gameId) return;
    const token = state.runToken;
    let hits = 0;
    let ended = false;
    let timer = null;

    screen.innerHTML = `
      <section class="card">
        <div class="row"><h2>🎯 Тир</h2><button class="btn secondary" id="shootBack">← Игры</button></div>
        <p>Попаданий: <b id="hits">0</b>/10</p>
        <div class="target-field" id="targetField"><button class="target" id="target">🎯</button></div>
        <p id="shootResult" class="muted"></p>
      </section>`;
    document.getElementById('shootBack').onclick = () => tab('games');
    const field = document.getElementById('targetField');
    const target = document.getElementById('target');

    function moveTarget() {
      const margin = 5;
      const maxX = Math.max(0, field.clientWidth - target.offsetWidth - margin * 2);
      const maxY = Math.max(0, field.clientHeight - target.offsetHeight - margin * 2);
      target.style.left = `${margin + Math.random() * maxX}px`;
      target.style.top = `${margin + Math.random() * maxY}px`;
    }

    async function finish() {
      if (ended) return;
      ended = true;
      if (timer) clearTimeout(timer);
      const result = await finishGame(gameId, hits, hits >= 10);
      target.disabled = true;
      document.getElementById('shootResult').textContent = result ? `🏆 ${hits}/10 · +${Number(result.reward || 0).toLocaleString('ru-RU')} 🪙` : `${hits}/10`;
    }

    target.onclick = () => {
      if (ended || token !== state.runToken) return;
      hits += 1;
      document.getElementById('hits').textContent = hits;
      vibrate(6);
      if (hits >= 10) { finish(); return; }
      moveTarget();
      if (timer) clearTimeout(timer);
      timer = setTimeout(moveTarget, 850);
    };
    moveTarget();
    state.game = { cleanup: () => { ended = true; if (timer) clearTimeout(timer); target.onclick = null; } };
  }

  function settings() {
    stopGame();
    screen.innerHTML = `
      <section class="card settings">
        <div class="row"><h2>⚙️ Настройки профиля</h2><button class="btn secondary" id="settingsBack">← Назад</button></div>
        <label>Музыка <input id="music" type="checkbox" ${state.settings.music ? 'checked' : ''}></label>
        <label>Звуки <input id="sound" type="checkbox" ${state.settings.sound ? 'checked' : ''}></label>
        <label>Вибрация <input id="vibrate" type="checkbox" ${state.settings.vibrate ? 'checked' : ''}></label>
        <label>Громкость <input id="volume" type="range" min="0" max="1" step=".05" value="${state.settings.volume}"></label>
        <label>Трек <select id="track"><option value="city">Разговор с городом</option><option value="moog">Moog City 2</option><option value="doki">DokiDoki</option><option value="plenka">When You Find Me</option></select></label>
        <button class="btn" id="musicTest">▶️ Проверить музыку</button>
      </section>`;

    const music = document.getElementById('music');
    const sound = document.getElementById('sound');
    const vibrateInput = document.getElementById('vibrate');
    const volume = document.getElementById('volume');
    const track = document.getElementById('track');

    track.value = state.settings.track;
    document.getElementById('settingsBack').onclick = () => tab('profile');
    music.onchange = () => { state.settings.music = music.checked; saveSettings(); state.settings.music ? playMusic() : stopAudio(); };
    sound.onchange = () => { state.settings.sound = sound.checked; saveSettings(); };
    vibrateInput.onchange = () => { state.settings.vibrate = vibrateInput.checked; saveSettings(); };
    volume.oninput = () => { state.settings.volume = Number(volume.value); if (state.audio) state.audio.volume = state.settings.volume; saveSettings(); };
    track.onchange = () => { state.settings.track = track.value; saveSettings(); if (state.settings.music) playMusic(); };
    document.getElementById('musicTest').onclick = playMusic;
  }

  async function playMusic() {
    if (!state.settings.music) return;
    stopAudio();
    const audio = new Audio(`/api/mini/music/${encodeURIComponent(state.settings.track)}`);
    audio.loop = true;
    audio.volume = Math.max(0, Math.min(1, Number(state.settings.volume) || 0));
    state.audio = audio;
    try { await audio.play(); } catch (_) { notify('Нажми «Проверить музыку» ещё раз, если Telegram заблокировал автозапуск.'); }
  }

  function stopAudio() {
    if (!state.audio) return;
    try { state.audio.pause(); state.audio.src = ''; } catch (_) {}
    state.audio = null;
  }

  function boot() {
    loadSettings();
    document.querySelectorAll('nav button').forEach((button) => {
      button.onclick = () => tab(button.dataset.tab);
    });
    loadProfile().catch(() => {});
  }

  window.tab = tab;
  window.mines = mines;
  window.snake = snake;
  window.game2048 = game2048;
  window.reaction = reaction;
  window.shooter = shooter;
  window.settings = settings;
  window.chooseDifficulty = chooseDifficulty;

  boot();
})();
