/* sinyavka_geo — solo speedrun mode (no backend, no XP) */
(() => {
    const MAP = JSON.parse(document.getElementById('solo-data').textContent);
    const TOTAL_ROUNDS = 5;
    const ROUND_SECONDS = 60;

    const $ = (id) => document.getElementById(id);
    const introPanel = $('intro-panel');
    const gamePanel = $('game-panel');
    const resultPanel = $('result-panel');
    const overPanel = $('over-panel');
    const startBtn = $('start-btn');
    const nextBtn = $('next-btn');
    const replayBtn = $('replay-btn');
    const submitBtn = $('submit-guess');
    const timerEl = $('timer');
    const roundNum = $('round-num');
    const scoreTotalEl = $('score-total');

    let round = 0;
    let totalScore = 0;
    let actual = null;       // {lat, lng}
    let pendingGuess = null; // {lat, lng}
    let panoPlayer = null;
    let guessMap = null;
    let guessMarker = null;
    let resultMap = null;
    let resultObjects = [];
    let timerInterval = null;
    let timeLeft = 0;
    let roundEnded = false;

    let ymapsReady = false;
    const ymapsReadyCbs = [];
    function whenReady(cb) { if (ymapsReady) cb(); else ymapsReadyCbs.push(cb); }
    function markReady() { ymapsReady = true; ymapsReadyCbs.splice(0).forEach(c => c()); }
    if (window.ymaps) ymaps.ready(markReady);
    else {
        const wait = setInterval(() => {
            if (window.ymaps) { clearInterval(wait); ymaps.ready(markReady); }
        }, 100);
    }

    startBtn.addEventListener('click', () => { hide(introPanel); startRound(); });
    nextBtn.addEventListener('click', () => { hide(resultPanel); startRound(); });
    replayBtn.addEventListener('click', () => { resetAll(); hide(overPanel); startRound(); });

    submitBtn.addEventListener('click', () => {
        if (!pendingGuess || roundEnded) return;
        commitGuess();
    });

    function resetAll() {
        round = 0;
        totalScore = 0;
        scoreTotalEl.textContent = '0';
        document.querySelectorAll('#rounds-list li').forEach(li => {
            li.classList.remove('bg-amber-500/10', 'border-amber-500/30', 'text-amber-200', 'text-slate-200');
            li.classList.add('bg-slate-800/40', 'text-slate-500');
            li.querySelector('.round-points').textContent = '—';
        });
    }

    function startRound() {
        round += 1;
        if (round > TOTAL_ROUNDS) return endGame();
        roundNum.textContent = round;
        roundEnded = false;
        pendingGuess = null;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Поставь метку';
        show(gamePanel);
        whenReady(() => {
            pickPanoramaPoint().then(point => {
                actual = point;
                initPanorama(point);
                initGuessMap(true);
                startTimer(ROUND_SECONDS);
            });
        });
        markRoundActive(round);
    }

    function markRoundActive(n) {
        document.querySelectorAll('#rounds-list li').forEach(li => {
            const num = parseInt(li.dataset.round, 10);
            li.classList.remove('text-amber-200', 'border-amber-500/30', 'bg-amber-500/10');
            if (num === n) {
                li.classList.add('bg-amber-500/10', 'border', 'border-amber-500/30', 'text-amber-200');
                li.classList.remove('text-slate-500', 'text-slate-200');
            }
        });
    }

    function markRoundDone(n, pts) {
        const li = document.querySelector(`#rounds-list li[data-round="${n}"]`);
        if (!li) return;
        li.classList.remove('bg-amber-500/10', 'border-amber-500/30', 'text-amber-200', 'text-slate-500');
        li.classList.add('text-slate-200');
        li.querySelector('.round-points').textContent = `+${pts}`;
    }

    // pick a point from the pool, retry if no panorama nearby (up to N tries)
    function pickPanoramaPoint() {
        const pool = MAP.points.slice();
        // shuffle
        for (let i = pool.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [pool[i], pool[j]] = [pool[j], pool[i]];
        }
        return new Promise(resolve => {
            const tryNext = (idx) => {
                if (idx >= pool.length) {
                    // fallback: take first
                    return resolve({ lat: pool[0][0], lng: pool[0][1] });
                }
                const [lat, lng] = pool[idx];
                ymaps.panorama.locate([lat, lng]).then(
                    (panos) => {
                        if (panos && panos.length) resolve({ lat, lng, panorama: panos[0] });
                        else tryNext(idx + 1);
                    },
                    () => tryNext(idx + 1),
                );
            };
            tryNext(0);
        });
    }

    function initPanorama(point) {
        const target = $('pano');
        target.innerHTML = '';
        if (panoPlayer) { try { panoPlayer.destroy(); } catch (e) {} panoPlayer = null; }
        if (point.panorama) {
            panoPlayer = new ymaps.panorama.Player('pano', point.panorama, {
                direction: [Math.random() * 360, 0],
                controls: ['zoomControl'],
                hotkeysEnabled: true,
            });
        } else {
            ymaps.panorama.locate([point.lat, point.lng]).then(
                (panos) => {
                    if (panos && panos.length) {
                        panoPlayer = new ymaps.panorama.Player('pano', panos[0], {
                            direction: [Math.random() * 360, 0],
                            controls: ['zoomControl'],
                            hotkeysEnabled: true,
                        });
                    } else {
                        target.innerHTML = '<div class="absolute inset-0 grid place-items-center text-rose-400 text-sm text-center p-4">Здесь нет панорамы — но локация всё равно реальная. Угадай по карте.</div>';
                    }
                },
                () => {
                    target.innerHTML = '<div class="absolute inset-0 grid place-items-center text-rose-400 text-sm">Не удалось загрузить панораму.</div>';
                }
            );
        }
    }

    function initGuessMap(reset) {
        if (!guessMap) {
            const b = MAP.bounds;
            guessMap = new ymaps.Map('guess-map', {
                center: MAP.center,
                zoom: MAP.zoom,
                controls: ['zoomControl'],
            }, {
                restrictMapArea: [[b[0], b[1]], [b[2], b[3]]],
                suppressMapOpenBlock: true,
            });
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
        } else {
            if (guessMarker) { guessMap.geoObjects.remove(guessMarker); guessMarker = null; }
            guessMap.setCenter(MAP.center, MAP.zoom);
        }
    }

    function commitGuess() {
        roundEnded = true;
        stopTimer();
        const dist = haversine(pendingGuess.lat, pendingGuess.lng, actual.lat, actual.lng);
        // bonus for remaining time: up to +500 if guessed in first half
        const speedBonus = Math.max(0, Math.floor((timeLeft / ROUND_SECONDS) * 500));
        const base = pointsFromDistance(dist, MAP.max_distance_m);
        const pts = Math.min(5000, base + speedBonus);
        finishRound(dist, pts, speedBonus);
    }

    function autoMissRound() {
        roundEnded = true;
        // no guess => max distance, 0 points
        finishRound(MAP.max_distance_m, 0, 0);
    }

    function finishRound(dist, pts, speedBonus) {
        totalScore += pts;
        scoreTotalEl.textContent = String(totalScore);
        markRoundDone(round, pts);
        hide(gamePanel); show(resultPanel);
        $('result-distance').textContent = (dist / 1000).toFixed(2) + ' км';
        $('result-points').textContent = String(pts);
        $('result-headline').innerHTML = `Раунд ${round} · <span class="text-slate-400 text-sm">${speedBonus ? `+${speedBonus} за скорость` : 'без бонуса за скорость'}</span>`;
        nextBtn.textContent = round >= TOTAL_ROUNDS ? 'Показать финал →' : 'Следующий раунд →';
        whenReady(() => renderResultMap(dist));
    }

    function renderResultMap(dist) {
        if (!resultMap) {
            resultMap = new ymaps.Map('result-map', {
                center: [actual.lat, actual.lng],
                zoom: 10,
                controls: ['zoomControl'],
            }, { suppressMapOpenBlock: true });
        }
        resultObjects.forEach(o => resultMap.geoObjects.remove(o));
        resultObjects = [];

        const a = new ymaps.Placemark([actual.lat, actual.lng], { hintContent: 'Настоящая локация' }, { preset: 'islands#redStarIcon' });
        resultMap.geoObjects.add(a); resultObjects.push(a);
        const coords = [[actual.lat, actual.lng]];
        if (pendingGuess) {
            const g = new ymaps.Placemark([pendingGuess.lat, pendingGuess.lng], { hintContent: `Твоя метка — ${(dist/1000).toFixed(2)} км` }, { preset: 'islands#blueCircleDotIcon' });
            const line = new ymaps.Polyline([[pendingGuess.lat, pendingGuess.lng], [actual.lat, actual.lng]], {}, { strokeColor: '#22d3ee', strokeWidth: 2, strokeStyle: 'shortdash' });
            resultMap.geoObjects.add(g); resultMap.geoObjects.add(line);
            resultObjects.push(g, line);
            coords.push([pendingGuess.lat, pendingGuess.lng]);
        }
        if (coords.length > 1) {
            const lats = coords.map(c => c[0]), lngs = coords.map(c => c[1]);
            resultMap.setBounds([[Math.min(...lats), Math.min(...lngs)], [Math.max(...lats), Math.max(...lngs)]], { checkZoomRange: true, zoomMargin: 40 });
        }
    }

    function endGame() {
        hide(gamePanel); hide(resultPanel); show(overPanel);
        $('final-score').textContent = String(totalScore);
    }

    function startTimer(seconds) {
        stopTimer();
        timeLeft = seconds;
        timerEl.textContent = fmt(timeLeft);
        timerInterval = setInterval(() => {
            timeLeft -= 1;
            if (timeLeft <= 0) {
                stopTimer();
                timerEl.textContent = '00:00';
                if (!roundEnded) {
                    if (pendingGuess) commitGuess();
                    else autoMissRound();
                }
                return;
            }
            timerEl.textContent = fmt(timeLeft);
        }, 1000);
    }
    function stopTimer() { if (timerInterval) { clearInterval(timerInterval); timerInterval = null; } }
    function fmt(s) {
        const m = Math.floor(s / 60).toString().padStart(2, '0');
        const r = (s % 60).toString().padStart(2, '0');
        return `${m}:${r}`;
    }

    function haversine(lat1, lng1, lat2, lng2) {
        const R = 6371000, toRad = (d) => d * Math.PI / 180;
        const dphi = toRad(lat2 - lat1), dlmb = toRad(lng2 - lng1);
        const a = Math.sin(dphi/2)**2 + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dlmb/2)**2;
        return 2 * R * Math.asin(Math.sqrt(a));
    }
    function pointsFromDistance(dist, maxDist) {
        const ratio = dist / maxDist;
        const raw = 5000 * Math.exp(-10 * ratio);
        return Math.max(0, Math.min(5000, Math.round(raw)));
    }

    function show(el) { el.classList.remove('hidden'); }
    function hide(el) { el.classList.add('hidden'); }
})();
