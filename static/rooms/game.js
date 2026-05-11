/* sinyavka_geo — room realtime client */
(() => {
    const data = JSON.parse(document.getElementById('room-data').textContent);
    const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${wsProto}://${location.host}/ws/rooms/${data.code}/`);

    const $ = (id) => document.getElementById(id);
    const lobbyPanel = $('lobby-panel');
    const gamePanel = $('game-panel');
    const resultPanel = $('result-panel');
    const overPanel = $('over-panel');
    const playersList = $('players');
    const chatLog = $('chat-log');
    const chatForm = $('chat-form');
    const chatInput = $('chat-input');
    const submitBtn = $('submit-guess');
    const startBtn = $('start-btn');
    const timerEl = $('timer');
    const roomStatus = $('room-status');
    const roundNum = $('round-num');
    const playerCount = $('player-count');

    let panorama = null;
    let guessMap = null;
    let guessMarker = null;
    let pendingGuess = null;
    let roundEnded = false;
    let timerInterval = null;
    let resultMap = null;

    // ---- copy link ----
    $('copy-link')?.addEventListener('click', () => {
        navigator.clipboard.writeText(location.href).then(() => {
            const btn = $('copy-link');
            const old = btn.textContent;
            btn.textContent = '✓ Скопировано';
            setTimeout(() => (btn.textContent = old), 1500);
        });
    });

    // ---- chat ----
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;
        ws.send(JSON.stringify({ action: 'chat', text }));
        chatInput.value = '';
    });

    function logChat(html) {
        const div = document.createElement('div');
        div.innerHTML = html;
        chatLog.appendChild(div);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    // ---- start button (host) ----
    startBtn?.addEventListener('click', () => {
        ws.send(JSON.stringify({ action: 'start' }));
        startBtn.disabled = true;
        startBtn.textContent = 'Запускаю...';
    });

    // ---- websocket ----
    ws.addEventListener('open', () => logChat('<span class="text-emerald-400">● подключено</span>'));
    ws.addEventListener('close', () => logChat('<span class="text-rose-400">● разрыв связи</span>'));
    ws.addEventListener('message', (ev) => {
        const msg = JSON.parse(ev.data);
        switch (msg.type) {
            case 'state': return onState(msg);
            case 'chat': return logChat(`<b class="text-brand-400">${escapeHtml(msg.user)}:</b> ${escapeHtml(msg.text)}`);
            case 'system': return logChat(`<span class="text-slate-500 text-xs">${escapeHtml(msg.text)}</span>`);
            case 'round_started': return onRoundStarted(msg);
            case 'guess_locked': return logChat(`<span class="text-amber-400 text-xs">🔒 ${escapeHtml(msg.user)} зафиксировал метку</span>`);
            case 'round_result': return onRoundResult(msg);
            case 'game_over': return onGameOver(msg);
            case 'error': return logChat(`<span class="text-rose-400">⚠ ${escapeHtml(msg.text)}</span>`);
        }
    });

    function onState(msg) {
        const players = msg.players || [];
        playerCount.textContent = `${players.length}/${document.querySelectorAll && players.length}`;
        playerCount.textContent = `${players.length} в комнате`;
        playersList.innerHTML = players.map(p => `
            <li class="flex items-center gap-2 text-sm">
                ${p.avatar
                    ? `<img src="${escapeHtml(p.avatar)}" class="w-7 h-7 rounded-full object-cover">`
                    : `<span class="w-7 h-7 rounded-full bg-brand-600 grid place-items-center text-xs font-bold text-slate-950">${escapeHtml((p.nickname||p.username).slice(0,1).toUpperCase())}</span>`}
                <div class="flex-1 min-w-0">
                    <div class="truncate">
                        ${escapeHtml(p.nickname || p.username)}
                        ${p.is_host ? '<span class="text-xs text-amber-400 ml-1">👑</span>' : ''}
                    </div>
                    <div class="text-xs text-slate-500">LVL ${p.level} · ${p.score} очков</div>
                </div>
            </li>
        `).join('');

        const statusMap = { lobby: 'Лобби', in_game: 'Игра идёт', finished: 'Завершена' };
        roomStatus.textContent = statusMap[msg.room.status] || msg.room.status;

        if (msg.room.status === 'finished') {
            // keep game-over panel as-is
        } else if (msg.room.status === 'lobby') {
            show(lobbyPanel); hide(gamePanel); hide(resultPanel); hide(overPanel);
        }
    }

    function onRoundStarted(msg) {
        roundEnded = false;
        pendingGuess = null;
        hide(lobbyPanel); hide(resultPanel); hide(overPanel); show(gamePanel);
        roundNum.textContent = msg.number;
        initPanorama(msg.lat, msg.lng);
        initGuessMap();
        startTimer(msg.duration);
        submitBtn.disabled = true;
        submitBtn.textContent = 'Поставь метку';
    }

    function onRoundResult(msg) {
        roundEnded = true;
        stopTimer();
        show(resultPanel);
        // build result map
        setTimeout(() => {
            if (!resultMap) {
                resultMap = new google.maps.Map($('result-map'), {
                    center: { lat: msg.actual.lat, lng: msg.actual.lng },
                    zoom: 10,
                    streetViewControl: false,
                    mapTypeControl: false,
                    fullscreenControl: false,
                    styles: darkMapStyle,
                });
            } else {
                resultMap.setCenter({ lat: msg.actual.lat, lng: msg.actual.lng });
            }
            // clear old overlays
            resultMap.__overlays?.forEach(o => o.setMap(null));
            resultMap.__overlays = [];
            const actual = new google.maps.Marker({
                position: { lat: msg.actual.lat, lng: msg.actual.lng },
                map: resultMap, label: '★',
                title: 'Настоящая локация',
            });
            resultMap.__overlays.push(actual);
            msg.guesses.forEach(g => {
                if (!g.lat && !g.lng) return;
                const m = new google.maps.Marker({
                    position: { lat: g.lat, lng: g.lng }, map: resultMap,
                    label: { text: g.user.slice(0,1).toUpperCase(), color: 'white' },
                    title: `${g.user}: ${(g.distance_m/1000).toFixed(2)} км / ${g.points} очков`,
                });
                resultMap.__overlays.push(m);
                const line = new google.maps.Polyline({
                    path: [{ lat: g.lat, lng: g.lng }, { lat: msg.actual.lat, lng: msg.actual.lng }],
                    geodesic: true, strokeColor: '#22d3ee', strokeOpacity: 0.7, strokeWeight: 2,
                    map: resultMap,
                });
                resultMap.__overlays.push(line);
            });
        }, 50);
        $('result-list').innerHTML = msg.guesses.map((g, i) => `
            <div class="flex items-center justify-between px-3 py-2 rounded-md ${i === 0 ? 'bg-amber-500/10 border border-amber-500/30' : 'bg-slate-800/40'}">
                <span class="font-semibold">${i+1}. ${escapeHtml(g.user)}</span>
                <span class="text-slate-400">${(g.distance_m/1000).toFixed(2)} км · <b class="text-brand-400">+${g.points}</b></span>
            </div>
        `).join('');
    }

    function onGameOver(msg) {
        hide(gamePanel); hide(resultPanel); show(overPanel);
        $('final-list').innerHTML = msg.leaderboard.map((p, i) => {
            const medal = ['🥇','🥈','🥉'][i] || `#${i+1}`;
            const xp = msg.xp_gains?.[p.user] || 0;
            return `
                <div class="flex items-center justify-between px-4 py-3 rounded-xl ${i===0 ? 'bg-amber-500/10 border border-amber-500/40' : 'bg-slate-800/60 border border-slate-700'}">
                    <div class="flex items-center gap-3">
                        <span class="text-2xl">${medal}</span>
                        <span class="font-semibold text-lg">${escapeHtml(p.user)}</span>
                    </div>
                    <div class="text-right">
                        <div class="font-bold text-brand-400">${p.score} очков</div>
                        <div class="text-xs text-slate-500">+${xp} XP</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    // ---- Street View ----
    function initPanorama(lat, lng) {
        const pos = { lat, lng };
        if (!panorama) {
            panorama = new google.maps.StreetViewPanorama($('pano'), {
                position: pos,
                pov: { heading: Math.random() * 360, pitch: 0 },
                addressControl: false,
                showRoadLabels: false,
                linksControl: true,
                panControl: true,
                zoomControl: true,
                fullscreenControl: false,
                motionTracking: false,
                motionTrackingControl: false,
            });
        } else {
            panorama.setPosition(pos);
            panorama.setPov({ heading: Math.random() * 360, pitch: 0 });
        }
    }

    // ---- guess map ----
    function initGuessMap() {
        const bounds = data.map.bounds;
        const restrictBounds = new google.maps.LatLngBounds(
            { lat: bounds[0], lng: bounds[1] },
            { lat: bounds[2], lng: bounds[3] },
        );
        if (!guessMap) {
            guessMap = new google.maps.Map($('guess-map'), {
                center: { lat: data.map.center[0], lng: data.map.center[1] },
                zoom: data.map.zoom,
                streetViewControl: false,
                mapTypeControl: false,
                fullscreenControl: false,
                rotateControl: false,
                disableDefaultUI: true,
                clickableIcons: false,
                restriction: { latLngBounds: restrictBounds, strictBounds: false },
                styles: darkMapStyle,
            });
            guessMap.addListener('click', (e) => {
                if (roundEnded) return;
                if (guessMarker) guessMarker.setMap(null);
                guessMarker = new google.maps.Marker({
                    position: e.latLng, map: guessMap, draggable: true,
                });
                pendingGuess = { lat: e.latLng.lat(), lng: e.latLng.lng() };
                guessMarker.addListener('dragend', (ev) => {
                    pendingGuess = { lat: ev.latLng.lat(), lng: ev.latLng.lng() };
                });
                submitBtn.disabled = false;
                submitBtn.textContent = 'Подтвердить метку';
            });
        } else {
            guessMap.setCenter({ lat: data.map.center[0], lng: data.map.center[1] });
            guessMap.setZoom(data.map.zoom);
            if (guessMarker) { guessMarker.setMap(null); guessMarker = null; }
            pendingGuess = null;
        }
    }

    submitBtn.addEventListener('click', () => {
        if (!pendingGuess || roundEnded) return;
        ws.send(JSON.stringify({ action: 'guess', lat: pendingGuess.lat, lng: pendingGuess.lng }));
        submitBtn.disabled = true;
        submitBtn.textContent = '✓ Метка отправлена';
        roundEnded = true;
    });

    // ---- timer ----
    function startTimer(seconds) {
        stopTimer();
        let left = seconds;
        timerEl.textContent = fmt(left);
        timerInterval = setInterval(() => {
            left -= 1;
            if (left <= 0) { stopTimer(); timerEl.textContent = '00:00'; return; }
            timerEl.textContent = fmt(left);
        }, 1000);
    }
    function stopTimer() { if (timerInterval) { clearInterval(timerInterval); timerInterval = null; } }
    function fmt(s) {
        const m = Math.floor(s / 60).toString().padStart(2, '0');
        const r = (s % 60).toString().padStart(2, '0');
        return `${m}:${r}`;
    }

    // ---- utils ----
    function show(el) { el.classList.remove('hidden'); }
    function hide(el) { el.classList.add('hidden'); }
    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }

    const darkMapStyle = [
        {elementType:'geometry',stylers:[{color:'#1f2937'}]},
        {elementType:'labels.text.fill',stylers:[{color:'#94a3b8'}]},
        {elementType:'labels.text.stroke',stylers:[{color:'#0f172a'}]},
        {featureType:'water',stylers:[{color:'#0e7490'}]},
        {featureType:'road',stylers:[{color:'#334155'}]},
        {featureType:'poi',stylers:[{visibility:'off'}]},
    ];
})();
