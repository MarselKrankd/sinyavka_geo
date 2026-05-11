
(() => {

    const HIDE_PANO_MARKERS = true;

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

    const MAX_ZOOM = data.map.max_zoom || 15;

    let panoPlayer = null;
    let guessMap = null;
    let guessMarker = null;
    let boundsOverlay = null;
    let pendingGuess = null;
    let roundEnded = false;
    let timerInterval = null;
    let resultMap = null;
    let resultObjects = [];
    let currentRoundNumber = 0;
    let panoMissingReported = false;
    let ymapsReady = false;
    const ymapsReadyCbs = [];

    function whenYmapsReady(cb) {
        if (ymapsReady) return cb();
        ymapsReadyCbs.push(cb);
    }
    function markReady() { ymapsReady = true; ymapsReadyCbs.splice(0).forEach(c => c()); }
    if (window.ymaps) ymaps.ready(markReady);
    else {
        const wait = setInterval(() => {
            if (window.ymaps) { clearInterval(wait); ymaps.ready(markReady); }
        }, 100);
    }

    // ResizeObserver: when the guess-map wrapper grows on hover, kill the
    // black bars by asking ymaps to refit to the new container size.
    const wrapper = $('guess-map-wrapper');
    if (wrapper && 'ResizeObserver' in window) {
        const ro = new ResizeObserver(() => { if (guessMap) guessMap.container.fitToViewport(); });
        ro.observe(wrapper);
    }

    // MutationObserver that nukes Yandex panorama overlay clutter (address
    // bubbles, transition badges, hint balloons, "Open in Maps" link) every
    // time the panorama redraws. CSS handles the easy cases; this catches
    // dynamic additions and classes that don't fit our selector patterns.
    //
    // CRITICAL: never walk up to ancestors — the panorama Player wrapper's
    // textContent transitively contains every overlay's text, so a parent
    // walk would hide the panorama itself and leave a black box. Skip any
    // element that has a canvas/video descendant (that's the imagery).
    const HIDE_STYLE = 'display:none !important;visibility:hidden !important;opacity:0 !important;pointer-events:none !important;';
    function cleanPanoramaOverlays() {
        const pano = $('pano');
        if (!pano) return;
        // Defer until the panorama imagery exists: if we run before the canvas
        // is attached, the position-absolute fallback below would hide the
        // wrappers that the canvas is ABOUT to be appended into, and the user
        // would see a black box even though imagery loaded fine.
        if (!pano.querySelector('canvas')) return;
        pano.querySelectorAll('*').forEach(el => {
            const tag = el.tagName;
            if (tag === 'CANVAS' || tag === 'VIDEO' || tag === 'IMG') return;
            // Anything containing imagery — keep it, even if positioned absolute.
            if (el.querySelector('canvas, video')) return;
            // className may be SVGAnimatedString on SVG elements; getAttribute is safer.
            const cls = String(el.getAttribute && el.getAttribute('class') || el.className || '');
            // Whitelist zoom controls (the only UI we want to keep).
            if (/zoom/i.test(cls)) return;
            // 1) Class-based match — handles all the cases where Yandex puts
            //    a recognisable keyword in the class.
            const overlayRe = /marker|hint|tooltip|popup|balloon|toponym|address|copyright|panel|link-control|open-link|go-to-map/i;
            if (overlayRe.test(cls)) {
                el.style.cssText = HIDE_STYLE;
                return;
            }
            // 2) Position-based last-resort match — any absolutely-positioned
            //    element with no canvas/video descendant is a UI overlay (house
            //    number pill, transition pill, "open in maps" link, etc.).
            //    Since the canvas-ancestor check above already let through any
            //    structural wrapper that hosts the panorama image, the only
            //    things landing here are decorative overlays.
            const computed = getComputedStyle(el);
            if (computed.position === 'absolute' || computed.position === 'fixed') {
                // Skip elements that contain the zoom control as descendant.
                if (el.querySelector('[class*="zoom"]')) return;
                el.style.cssText = HIDE_STYLE;
            }
        });
    }
    const panoEl = $('pano');
    if (panoEl) {
        const panoObserver = new MutationObserver(cleanPanoramaOverlays);
        panoObserver.observe(panoEl, { childList: true, subtree: true });
        setInterval(cleanPanoramaOverlays, 1000);
    }

    $('copy-link')?.addEventListener('click', () => {
        navigator.clipboard.writeText(location.href).then(() => {
            const btn = $('copy-link');
            const old = btn.textContent;
            btn.textContent = '✓ Скопировано';
            setTimeout(() => (btn.textContent = old), 1500);
        });
    });

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

    startBtn?.addEventListener('click', () => {
        ws.send(JSON.stringify({ action: 'start' }));
        startBtn.disabled = true;
        startBtn.textContent = 'Запускаю...';
    });

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

    function renderPlayers(players) {
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
                    <div class="text-xs text-slate-500">LVL ${p.level} · <b class="text-brand-400">${p.score}</b> очков</div>
                </div>
            </li>
        `).join('');
    }

    function onState(msg) {
        renderPlayers(msg.players || []);
        const statusMap = { lobby: 'Лобби', in_game: 'Игра идёт', finished: 'Завершена' };
        roomStatus.textContent = statusMap[msg.room.status] || msg.room.status;
        if (msg.room.status === 'lobby') {
            show(lobbyPanel); hide(gamePanel); hide(resultPanel); hide(overPanel);
        }
    }

    function onRoundStarted(msg) {
        // The same round number can arrive twice if the server retried after a
        // pano_missing report — accept that, just reinit the panorama.
        const isRetry = msg.number === currentRoundNumber;
        currentRoundNumber = msg.number;
        if (!isRetry) panoMissingReported = false;

        roundEnded = false;
        pendingGuess = null;
        hide(lobbyPanel); hide(resultPanel); hide(overPanel); show(gamePanel);
        roundNum.textContent = msg.number;
        requestAnimationFrame(() => requestAnimationFrame(() => {
            whenYmapsReady(() => {
                initPanorama(msg.lat, msg.lng);
                initGuessMap();
            });
        }));
        if (!isRetry) startTimer(msg.duration);
        submitBtn.disabled = true;
        submitBtn.textContent = 'Поставь метку';
    }

    let resultCountdownInterval = null;
    function onRoundResult(msg) {
        roundEnded = true;
        stopTimer();
        hide(gamePanel);  // <-- must hide, or the panorama covers the result map
        show(resultPanel);
        const roundNumEl = $('result-round-num');
        if (roundNumEl) roundNumEl.textContent = msg.number ? `#${msg.number}` : '';
        requestAnimationFrame(() => requestAnimationFrame(() => {
            whenYmapsReady(() => renderResultMap(msg));
        }));
        $('result-list').innerHTML = msg.guesses.map((g, i) => {
            const colorHex = MARKER_COLORS[i % MARKER_COLORS.length].dot;
            return `
                <div class="flex items-center justify-between px-3 py-2 rounded-md ${i === 0 ? 'bg-amber-500/10 border border-amber-500/30' : 'bg-slate-800/40'}">
                    <span class="flex items-center gap-2 font-semibold">
                        <span class="inline-block w-3 h-3 rounded-full" style="background:${colorHex}"></span>
                        ${i+1}. ${escapeHtml(g.user)}
                    </span>
                    <span class="text-slate-400">${(g.distance_m/1000).toFixed(2)} км · <b class="text-brand-400">+${g.points}</b></span>
                </div>
            `;
        }).join('');
        // Countdown until next round_started (or game_over) arrives. Server
        // sleeps ROUND_REVEAL_SEC = 6 after broadcasting round_result.
        if (resultCountdownInterval) { clearInterval(resultCountdownInterval); }
        const cdEl = $('result-countdown');
        if (cdEl) {
            let left = 6;
            cdEl.textContent = String(left);
            resultCountdownInterval = setInterval(() => {
                left -= 1;
                cdEl.textContent = String(Math.max(0, left));
                if (left <= 0) { clearInterval(resultCountdownInterval); resultCountdownInterval = null; }
            }, 1000);
        }
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

    // Tracks the round whose panorama we're currently loading so a late-arriving
    // locate() callback for round N can't paint into round N+1's container.
    let activePanoRound = 0;

    function reportPanoMissing(label) {
        if (panoMissingReported) return;
        panoMissingReported = true;
        const target = $('pano');
        if (target) target.innerHTML = `<div class="absolute inset-0 grid place-items-center text-slate-500 text-sm">${label}</div>`;
        try { ws.send(JSON.stringify({ action: 'pano_missing' })); } catch (e) {}
    }

    function initPanorama(lat, lng) {
        const target = $('pano');
        target.innerHTML = '<div class="absolute inset-0 grid place-items-center text-slate-500 text-sm">Загружаю панораму…</div>';
        const round = currentRoundNumber;
        activePanoRound = round;

        // Hard timeout: if Yandex doesn't answer in 7s, treat as missing and
        // bounce to the next point. Without this the user gets stuck on
        // "Загружаю панораму" forever when the API is slow or the point has
        // no panorama and Yandex never resolves.
        const timeout = setTimeout(() => {
            if (activePanoRound !== round) return;
            console.warn('panorama locate timeout, asking server for another point');
            reportPanoMissing('Беру другую локацию…');
        }, 7000);

        ymaps.panorama.locate([lat, lng], { layer: 'yandex#panorama' }).then(
            (panoramas) => {
                clearTimeout(timeout);
                if (activePanoRound !== round) return;  // stale callback
                if (!panoramas.length) {
                    reportPanoMissing('Беру другую локацию…');
                    return;
                }
                if (panoPlayer) { try { panoPlayer.destroy(); } catch (e) {} panoPlayer = null; }
                target.innerHTML = '';
                // Authoritative way to suppress Yandex's address pills /
                // "14А" house-number badges / transition arrows: blank out
                // the marker accessors on the panorama PROTOTYPE before the
                // Player is constructed. Patching the prototype (not just
                // the current instance) means every future panorama the
                // user walks into — they're created via internal transitions
                // and share the same prototype — also returns empty markers.
                // Bonus: zeroing getConnections/getConnectionMarkers also
                // disables in-panorama walking, so the user can rotate the
                // camera but can't navigate to neighbours (and thus can't
                // surface new markers anyway).
                // Set HIDE_PANO_MARKERS = false at the top of this file to
                // roll back if something looks wrong.
                if (HIDE_PANO_MARKERS && panoramas[0]) {
                    try {
                        const proto = Object.getPrototypeOf(panoramas[0]);
                        proto.getMarkers = function() { return []; };
                        proto.getConnectionMarkers = function() { return []; };
                        proto.getConnections = function() { return []; };
                        proto.getConnectionArrows = function() { return []; };
                    } catch (e) {
                        // Fallback: at least scrub this one instance.
                        try { panoramas[0].getMarkers = () => []; } catch (e2) {}
                        try { panoramas[0].getConnectionMarkers = () => []; } catch (e2) {}
                        try { panoramas[0].getConnections = () => []; } catch (e2) {}
                        try { panoramas[0].getConnectionArrows = () => []; } catch (e2) {}
                    }
                }
                panoPlayer = new ymaps.panorama.Player('pano', panoramas[0], {
                    direction: [Math.random() * 360, 0],
                    controls: ['zoomControl'],
                    hotkeysEnabled: true,
                    suppressMapOpenBlock: true,
                });
                // Backstop: the CSS + DOM-walker cleaner catches anything
                // Yandex still injects (e.g. canvas-rendered labels we can't
                // intercept via API). Runs immediately + on a few delays.
                cleanPanoramaOverlays();
                setTimeout(cleanPanoramaOverlays, 100);
                setTimeout(cleanPanoramaOverlays, 500);
                setTimeout(cleanPanoramaOverlays, 1500);
            },
            (err) => {
                clearTimeout(timeout);
                if (activePanoRound !== round) return;
                console.error('panorama locate failed', err);
                reportPanoMissing('Беру другую локацию…');
            }
        );
    }

    function drawBoundsOverlay(map, bounds) {
        if (boundsOverlay) { map.geoObjects.remove(boundsOverlay); }
        // Polyline, not Polygon — Polygon fill defaults to opaque and covers tiles.
        boundsOverlay = new ymaps.Polyline(
            [
                [bounds[0], bounds[1]],
                [bounds[0], bounds[3]],
                [bounds[2], bounds[3]],
                [bounds[2], bounds[1]],
                [bounds[0], bounds[1]],
            ],
            { hintContent: 'Зона панорам' },
            {
                strokeColor: '#22d3ee',
                strokeWidth: 2,
                strokeStyle: 'dash',
                interactivityModel: 'default#transparent',
            },
        );
        map.geoObjects.add(boundsOverlay);
    }

    function initGuessMap() {
        const b = data.map.bounds;
        if (!guessMap) {
            // Construct WITHOUT restrictMapArea — when the option is set at
            // construction time inside a freshly-shown absolute-positioned
            // container, ymaps sometimes skips the initial tile fetch and
            // leaves the map as a solid pale-blue rectangle. We set the
            // restriction below, after the first fitToViewport call.
            guessMap = new ymaps.Map('guess-map', {
                center: data.map.center,
                zoom: data.map.zoom,
                type: 'yandex#map',
                controls: ['zoomControl'],
            }, {
                suppressMapOpenBlock: true,
                maxZoom: MAX_ZOOM,
                minZoom: 9,
            });
            drawBoundsOverlay(guessMap, b);
            guessMap.events.add('click', (e) => {
                if (roundEnded) return;
                const coords = e.get('coords');
                if (guessMarker) guessMap.geoObjects.remove(guessMarker);
                guessMarker = new ymaps.Placemark(coords, {}, {
                    draggable: true,
                    preset: 'islands#nightCircleDotIcon',
                });
                guessMarker.events.add('dragend', () => {
                    const c = guessMarker.geometry.getCoordinates();
                    pendingGuess = { lat: c[0], lng: c[1] };
                });
                guessMap.geoObjects.add(guessMarker);
                pendingGuess = { lat: coords[0], lng: coords[1] };
                submitBtn.disabled = false;
                submitBtn.textContent = 'Подтвердить метку';
            });
            // Force the tile layer to load: fit container, set bounds to the
            // playable area, then apply restrictMapArea. setBounds triggers a
            // tile request even when the construction-time center/zoom didn't.
            requestAnimationFrame(() => {
                guessMap.container.fitToViewport();
                guessMap.setBounds([[b[0], b[1]], [b[2], b[3]]], { checkZoomRange: true, zoomMargin: 5 });
                guessMap.options.set('restrictMapArea', [[b[0], b[1]], [b[2], b[3]]]);
                setTimeout(() => guessMap && guessMap.container.fitToViewport(), 250);
            });
        } else {
            guessMap.setCenter(data.map.center, data.map.zoom);
            if (guessMarker) { guessMap.geoObjects.remove(guessMarker); guessMarker = null; }
            pendingGuess = null;
            requestAnimationFrame(() => guessMap.container.fitToViewport());
        }
    }

    // Each player gets a different colour so guesses stay distinguishable
    // even when they cluster. Pairs of (preset, dot-hex) — the hex matches
    // the legend swatch we render next to each name in the result list.
    const MARKER_COLORS = [
        { preset: 'islands#blueCircleDotIconWithCaption',   dot: '#1e98ff' },
        { preset: 'islands#greenCircleDotIconWithCaption',  dot: '#56db40' },
        { preset: 'islands#violetCircleDotIconWithCaption', dot: '#b51eff' },
        { preset: 'islands#orangeCircleDotIconWithCaption', dot: '#ff931e' },
        { preset: 'islands#darkBlueCircleDotIconWithCaption', dot: '#177bc9' },
        { preset: 'islands#yellowCircleDotIconWithCaption', dot: '#ffd21e' },
    ];

    function renderResultMap(msg) {
        if (resultMap) {
            try { resultMap.destroy(); } catch (e) {}
            resultMap = null;
            resultObjects = [];
        }
        resultMap = new ymaps.Map('result-map', {
            center: [msg.actual.lat, msg.actual.lng],
            zoom: 11,
            type: 'yandex#map',
            controls: ['zoomControl'],
        }, {
            suppressMapOpenBlock: true,
            maxZoom: 15,
        });

        // Red star for the real point — same convention as solo.
        const actual = new ymaps.Placemark(
            [msg.actual.lat, msg.actual.lng],
            { hintContent: 'Настоящая локация', iconCaption: 'настоящая' },
            { preset: 'islands#redStarIcon' },
        );
        resultMap.geoObjects.add(actual);
        resultObjects.push(actual);

        const allCoords = [[msg.actual.lat, msg.actual.lng]];
        msg.guesses.forEach((g, i) => {
            if (!g.lat && !g.lng) return;
            const km = (g.distance_m / 1000).toFixed(2);
            const colour = MARKER_COLORS[i % MARKER_COLORS.length];
            const guess = new ymaps.Placemark(
                [g.lat, g.lng],
                { hintContent: `${g.user}: ${km} км · ${g.points} очков`, iconCaption: `${g.user} · ${km} км` },
                { preset: colour.preset },
            );
            const line = new ymaps.Polyline(
                [[g.lat, g.lng], [msg.actual.lat, msg.actual.lng]],
                { hintContent: `${km} км` },
                { strokeColor: colour.dot, strokeWidth: 2, strokeStyle: 'shortdash' },
            );
            resultMap.geoObjects.add(guess);
            resultMap.geoObjects.add(line);
            resultObjects.push(guess, line);
            allCoords.push([g.lat, g.lng]);
        });

        // Force a viewport fit so we don't render in a 0x0 container while
        // result-panel transitions in, then frame all the markers.
        requestAnimationFrame(() => {
            resultMap.container.fitToViewport();
            if (allCoords.length > 1) {
                const lats = allCoords.map(c => c[0]);
                const lngs = allCoords.map(c => c[1]);
                const bnds = [[Math.min(...lats), Math.min(...lngs)], [Math.max(...lats), Math.max(...lngs)]];
                resultMap.setBounds(bnds, { checkZoomRange: true, zoomMargin: 60 });
            }
            // One more refit after the result panel's layout settles.
            setTimeout(() => resultMap && resultMap.container.fitToViewport(), 250);
        });
    }

    submitBtn.addEventListener('click', () => {
        if (!pendingGuess || roundEnded) return;
        ws.send(JSON.stringify({ action: 'guess', lat: pendingGuess.lat, lng: pendingGuess.lng }));
        submitBtn.disabled = true;
        submitBtn.textContent = '✓ Метка отправлена';
        roundEnded = true;
    });

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

    function show(el) { el.classList.remove('hidden'); }
    function hide(el) { el.classList.add('hidden'); }
    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    }
})();
