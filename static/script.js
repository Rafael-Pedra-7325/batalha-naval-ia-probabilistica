(() => {
    const TAMANHO = 10;
    const LETRAS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"];
    const FROTA = window.FROTA_PADRAO || [];

    const estado = {
        gameId: null,
        mostrarCalor: true,
        somAtivo: true,
        bloqueado: false,
        modoDemo: false,
        demoTimer: null,
        ultimaJogadaIA: null,
        dadosJogo: null,
        setup: {
            navioSelecionadoId: FROTA[0]?.id || null,
            horizontal: true,
            naoAdjacente: false,
            posicionados: {},
        },
    };

    // Sintetizador de Sonar / Efeitos via Web Audio API
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    function tocarSom(tipo) {
        if (!estado.somAtivo) return;
        if (audioCtx.state === "suspended") audioCtx.resume();

        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);

        const agora = audioCtx.currentTime;
        if (tipo === "sonar") {
            osc.type = "sine";
            osc.frequency.setValueAtTime(880, agora);
            osc.frequency.exponentialRampToValueAtTime(440, agora + 0.16);
            gain.gain.setValueAtTime(0.06, agora);
            gain.gain.exponentialRampToValueAtTime(0.001, agora + 0.18);
            osc.start(agora);
            osc.stop(agora + 0.18);
        } else if (tipo === "agua") {
            osc.type = "triangle";
            osc.frequency.setValueAtTime(220, agora);
            osc.frequency.exponentialRampToValueAtTime(90, agora + 0.18);
            gain.gain.setValueAtTime(0.08, agora);
            gain.gain.exponentialRampToValueAtTime(0.001, agora + 0.2);
            osc.start(agora);
            osc.stop(agora + 0.2);
        } else if (tipo === "acerto" || tipo === "afundado") {
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(tipo === "afundado" ? 130 : 180, agora);
            osc.frequency.exponentialRampToValueAtTime(42, agora + (tipo === "afundado" ? 0.45 : 0.28));
            gain.gain.setValueAtTime(0.14, agora);
            gain.gain.exponentialRampToValueAtTime(0.001, agora + (tipo === "afundado" ? 0.48 : 0.3));
            osc.start(agora);
            osc.stop(agora + (tipo === "afundado" ? 0.48 : 0.3));
        }
    }

    // Elementos DOM
    const elSecaoSetup = document.getElementById("secao-setup");
    const elSecaoCombate = document.getElementById("secao-combate");
    const elListaDoca = document.getElementById("lista-doca");
    const elGridSetup = document.getElementById("grid-setup");
    const elGridJogador = document.getElementById("grid-jogador");
    const elGridInimigo = document.getElementById("grid-inimigo");
    const elBtnIniciar = document.getElementById("btn-iniciar-batalha");
    const elBtnDemo = document.getElementById("btn-demo-ia");
    const elChkNaoAdjacente = document.getElementById("chk-nao-adjacente");
    const elOrientacaoLabel = document.getElementById("orientacao-label");

    function pararDemo() {
        estado.modoDemo = false;
        if (estado.demoTimer) {
            clearInterval(estado.demoTimer);
            estado.demoTimer = null;
        }
        elBtnDemo.classList.remove("active");
        elBtnDemo.textContent = "🤖 Assistir IA vs IA";
    }

    function construirEstruturaGrid(container, onCellClick, onCellHover) {
        container.innerHTML = "";
        const canto = document.createElement("div");
        canto.className = "grid-coord";
        container.appendChild(canto);

        for (let c = 0; c < TAMANHO; c++) {
            const colHead = document.createElement("div");
            colHead.className = "grid-coord";
            colHead.textContent = c + 1;
            container.appendChild(colHead);
        }

        for (let r = 0; r < TAMANHO; r++) {
            const rowHead = document.createElement("div");
            rowHead.className = "grid-coord";
            rowHead.textContent = LETRAS[r];
            container.appendChild(rowHead);

            for (let c = 0; c < TAMANHO; c++) {
                const cell = document.createElement("div");
                cell.className = "cell";
                cell.dataset.r = r;
                cell.dataset.c = c;
                if (onCellClick) cell.addEventListener("click", () => onCellClick(r, c));
                if (onCellHover) cell.addEventListener("mouseenter", () => onCellHover(r, c));
                container.appendChild(cell);
            }
        }
    }

    // =========================================================================
    // FASE 1: POSICIONAMENTO TÁTICO (SETUP)
    // =========================================================================
    function renderizarDoca() {
        elListaDoca.innerHTML = "";
        FROTA.forEach((navio) => {
            const colocado = Boolean(estado.setup.posicionados[navio.id]);
            const selecionado = estado.setup.navioSelecionadoId === navio.id;

            const item = document.createElement("div");
            item.className = `dock-item ${selecionado ? "selected" : ""} ${colocado ? "placed" : ""}`;

            const info = document.createElement("div");
            info.innerHTML = `<strong>${navio.nome}</strong><div style="font-size:0.74rem;color:var(--text-muted)">${navio.tamanho} células</div>`;

            const blocos = document.createElement("div");
            blocos.className = "ship-blocks";
            for (let i = 0; i < navio.tamanho; i++) {
                const b = document.createElement("span");
                b.className = "ship-block";
                blocos.appendChild(b);
            }

            item.appendChild(info);
            item.appendChild(blocos);
            item.addEventListener("click", () => {
                estado.setup.navioSelecionadoId = navio.id;
                renderizarDoca();
            });
            elListaDoca.appendChild(item);
        });

        const totalColocados = Object.keys(estado.setup.posicionados).length;
        elBtnIniciar.disabled = totalColocados !== FROTA.length;
        elOrientacaoLabel.textContent = `Orientação: ${estado.setup.horizontal ? "HORIZONTAL" : "VERTICAL"}`;
    }

    function obterCelulasNavio(linha, coluna, tamanho, horizontal) {
        const lista = [];
        for (let i = 0; i < tamanho; i++) {
            const r = horizontal ? linha : linha + i;
            const c = horizontal ? coluna + i : coluna;
            lista.push([r, c]);
        }
        return lista;
    }

    function podePosicionarSetup(navioId, linha, coluna, tamanho, horizontal) {
        const ocupadas = new Set();
        const haloBloqueado = new Set();

        Object.values(estado.setup.posicionados).forEach((p) => {
            if (p.id === navioId) return;
            obterCelulasNavio(p.linha, p.coluna, p.tamanho, p.horizontal).forEach(([r, c]) => {
                ocupadas.add(`${r},${c}`);
                if (estado.setup.naoAdjacente) {
                    for (let dr = -1; dr <= 1; dr++) {
                        for (let dc = -1; dc <= 1; dc++) {
                            haloBloqueado.add(`${r + dr},${c + dc}`);
                        }
                    }
                }
            });
        });

        const candidatas = obterCelulasNavio(linha, coluna, tamanho, horizontal);
        for (const [r, c] of candidatas) {
            if (r < 0 || r >= TAMANHO || c < 0 || c >= TAMANHO) return false;
            const chave = `${r},${c}`;
            if (ocupadas.has(chave)) return false;
            if (estado.setup.naoAdjacente && haloBloqueado.has(chave)) return false;
        }
        return true;
    }

    function atualizarGridSetup(hoverR = null, hoverC = null) {
        const celulas = elGridSetup.querySelectorAll(".cell");
        const mapaNavios = new Set();

        Object.values(estado.setup.posicionados).forEach((p) => {
            obterCelulasNavio(p.linha, p.coluna, p.tamanho, p.horizontal).forEach(([r, c]) => {
                mapaNavios.add(`${r},${c}`);
            });
        });

        let previewSet = new Set();
        let previewValido = false;
        const navioAtual = FROTA.find((n) => n.id === estado.setup.navioSelecionadoId);

        if (navioAtual && hoverR !== null && hoverC !== null) {
            previewValido = podePosicionarSetup(
                navioAtual.id,
                hoverR,
                hoverC,
                navioAtual.tamanho,
                estado.setup.horizontal
            );
            obterCelulasNavio(
                hoverR,
                hoverC,
                navioAtual.tamanho,
                estado.setup.horizontal
            ).forEach(([r, c]) => previewSet.add(`${r},${c}`));
        }

        celulas.forEach((cell) => {
            const r = Number(cell.dataset.r);
            const c = Number(cell.dataset.c);
            const chave = `${r},${c}`;
            cell.className = "cell";

            if (mapaNavios.has(chave)) cell.classList.add("ship");
            if (previewSet.has(chave)) {
                cell.classList.add(previewValido ? "preview-valid" : "preview-invalid");
            }
        });
    }

    function clicarCelulaSetup(r, c) {
        const navioAtual = FROTA.find((n) => n.id === estado.setup.navioSelecionadoId);
        if (!navioAtual) return;

        if (!podePosicionarSetup(navioAtual.id, r, c, navioAtual.tamanho, estado.setup.horizontal)) {
            tocarSom("agua");
            return;
        }

        estado.setup.posicionados[navioAtual.id] = {
            id: navioAtual.id,
            linha: r,
            coluna: c,
            horizontal: estado.setup.horizontal,
            tamanho: navioAtual.tamanho,
        };
        tocarSom("sonar");

        const proximo = FROTA.find((n) => !estado.setup.posicionados[n.id]);
        if (proximo) estado.setup.navioSelecionadoId = proximo.id;

        renderizarDoca();
        atualizarGridSetup();
    }

    function gerarFrotaAleatoriaSetup() {
        estado.setup.posicionados = {};
        for (const navio of FROTA) {
            let colocado = false;
            let tentativas = 0;
            while (!colocado && tentativas < 600) {
                tentativas++;
                const horizontal = Math.random() < 0.5;
                const r = Math.floor(Math.random() * TAMANHO);
                const c = Math.floor(Math.random() * TAMANHO);
                if (podePosicionarSetup(navio.id, r, c, navio.tamanho, horizontal)) {
                    estado.setup.posicionados[navio.id] = {
                        id: navio.id,
                        linha: r,
                        coluna: c,
                        horizontal,
                        tamanho: navio.tamanho,
                    };
                    colocado = true;
                }
            }
            if (!colocado) {
                gerarFrotaAleatoriaSetup();
                return;
            }
        }
        tocarSom("sonar");
        renderizarDoca();
        atualizarGridSetup();
    }

    // =========================================================================
    // FASE 2: COMBATE, CONTORNO DE NAVIOS AFUNDADOS & MAPA DE CALOR
    // =========================================================================
    function corMapaCalor(intensidade) {
        if (intensidade <= 0) return "";
        if (intensidade < 25) {
            return `rgba(14, 116, 144, ${0.22 + (intensidade / 25) * 0.25})`;
        }
        if (intensidade < 55) {
            return `rgba(16, 185, 129, ${0.38 + ((intensidade - 25) / 30) * 0.25})`;
        }
        if (intensidade < 80) {
            return `rgba(245, 158, 11, ${0.55 + ((intensidade - 55) / 25) * 0.25})`;
        }
        return `rgba(239, 68, 68, ${0.72 + ((intensidade - 80) / 20) * 0.22})`;
    }

    function construirMapaConexoesAfundados(frota) {
        const conexoes = new Map();
        frota.forEach((navio) => {
            if (!navio.afundado || !navio.posicoes) return;
            const setPos = new Set(navio.posicoes.map(([r, c]) => `${r},${c}`));
            navio.posicoes.forEach(([r, c]) => {
                conexoes.set(`${r},${c}`, {
                    top: setPos.has(`${r - 1},${c}`),
                    bottom: setPos.has(`${r + 1},${c}`),
                    left: setPos.has(`${r},${c - 1}`),
                    right: setPos.has(`${r},${c + 1}`),
                });
            });
        });
        return conexoes;
    }

    function aplicarClassesConexaoSunk(cell, r, c, mapaConexoes) {
        const conn = mapaConexoes.get(`${r},${c}`);
        if (!conn) return;
        if (conn.top) cell.classList.add("sunk-conn-top");
        if (conn.bottom) cell.classList.add("sunk-conn-bottom");
        if (conn.left) cell.classList.add("sunk-conn-left");
        if (conn.right) cell.classList.add("sunk-conn-right");
    }

    function renderizarCombate() {
        const d = estado.dadosJogo;
        if (!d) return;

        document.getElementById("ia-status").textContent = d.mapa_calor.status_ia;
        document.getElementById("ia-melhor-alvo").textContent =
            `${d.mapa_calor.melhor_alvo} (${d.mapa_calor.pico_probabilidade}%)`;
        document.getElementById("ia-entropia").textContent = `${d.mapa_calor.entropia_bits.toFixed(2)} bits`;
        document.getElementById("hud-turnos").textContent = d.turnos;

        const st = d.estatisticas;
        const precJog = st.tiros_jogador ? Math.round((st.acertos_jogador / st.tiros_jogador) * 100) : 0;
        const precIA = st.tiros_ia ? Math.round((st.acertos_ia / st.tiros_ia) * 100) : 0;
        document.getElementById("hud-precisao").textContent = `${precJog}% / ${precIA}%`;

        const conexoesJog = construirMapaConexoesAfundados(d.frota_jogador);
        const conexoesIA = construirMapaConexoesAfundados(d.frota_ia);

        // Renderiza Grid Aliado + Overlay de Mapa de Calor
        const celulasJog = elGridJogador.querySelectorAll(".cell");
        celulasJog.forEach((cell) => {
            const r = Number(cell.dataset.r);
            const c = Number(cell.dataset.c);
            const val = d.tabuleiro_jogador[r][c];
            const intensidade = d.mapa_calor.intensidade[r][c];
            const chanceReal = d.mapa_calor.chances_reais[r][c];

            cell.className = "cell";
            cell.style.background = "";
            cell.innerHTML = "";
            cell.title = `${LETRAS[r]}${c + 1} — Probabilidade IA: ${chanceReal}%`;

            if (val === 1) cell.classList.add("ship");
            else if (val === 2) cell.classList.add("miss", "shot");
            else if (val === 3) cell.classList.add("hit", "shot");
            else if (val === 4) {
                cell.classList.add("sunk", "shot");
                aplicarClassesConexaoSunk(cell, r, c, conexoesJog);
            }

            if (
                estado.ultimaJogadaIA &&
                estado.ultimaJogadaIA.linha === r &&
                estado.ultimaJogadaIA.coluna === c
            ) {
                cell.classList.add("last-ai-shot");
            }

            if (estado.mostrarCalor && (val === 0 || val === 1) && intensidade > 0) {
                cell.style.background = corMapaCalor(intensidade);
                if (chanceReal >= 1.0) {
                    const span = document.createElement("span");
                    span.className = "heat-label";
                    span.textContent = `${chanceReal.toFixed(0)}%`;
                    cell.appendChild(span);
                }
            }
        });

        // Renderiza Grid Inimigo
        const celulasIA = elGridInimigo.querySelectorAll(".cell");
        celulasIA.forEach((cell) => {
            const r = Number(cell.dataset.r);
            const c = Number(cell.dataset.c);
            const val = d.tabuleiro_ia[r][c];

            cell.className = "cell";
            if (val === 1) cell.classList.add("ship");
            else if (val === 2) cell.classList.add("miss", "shot");
            else if (val === 3) cell.classList.add("hit", "shot");
            else if (val === 4) {
                cell.classList.add("sunk", "shot");
                aplicarClassesConexaoSunk(cell, r, c, conexoesIA);
            }
        });

        renderizarPillsFrota("status-frota-jogador", d.frota_jogador);
        renderizarPillsFrota("status-frota-ia", d.frota_ia);
    }

    function renderizarPillsFrota(containerId, frota) {
        const el = document.getElementById(containerId);
        el.innerHTML = "";
        frota.forEach((n) => {
            const pill = document.createElement("span");
            pill.className = `ship-pill ${n.afundado ? "sunk" : ""}`;
            pill.textContent = `${n.nome} (${n.tamanho})`;
            el.appendChild(pill);
        });
    }

    function adicionarLog(texto, classe = "") {
        const logContainer = document.getElementById("combat-log");
        const linha = document.createElement("div");
        linha.className = `log-line ${classe}`;
        linha.textContent = texto;
        logContainer.prepend(linha);
    }

    function processarRespostaTurno(dados, rotuloAliado = "Você") {
        estado.dadosJogo = dados;
        const aj = dados.acao_jogador;
        const aia = dados.acao_ia;

        if (aj) {
            tocarSom(aj.resultado);
            const probStr = aj.probabilidade_alvo ? ` • ${aj.probabilidade_alvo}% prob.` : "";
            let msgJog = `[TURNO ${String(dados.turnos).padStart(2, "0")}] ${rotuloAliado}${probStr} disparou em ${aj.coordenada} → ${aj.resultado.toUpperCase()}`;
            if (aj.navio_afundado) msgJog += ` (${aj.navio_afundado.nome} inimigo destruído!)`;
            adicionarLog(msgJog, aj.resultado !== "agua" ? "player-hit" : "");
        }

        if (aia) {
            estado.ultimaJogadaIA = { linha: aia.linha, coluna: aia.coluna };
            let msgIA = `[IA • ${aia.probabilidade_alvo}% prob.] Disparou em ${aia.coordenada} → ${aia.resultado.toUpperCase()}`;
            if (aia.navio_afundado) msgIA += ` (Frota aliada perdeu: ${aia.navio_afundado.nome}!)`;
            adicionarLog(msgIA, aia.resultado !== "agua" ? "ai-hit" : "");
        }

        renderizarCombate();

        if (dados.encerrado) {
            pararDemo();
            exibirModalFim(dados);
        }
    }

    async function iniciarNovaBatalha(isDemo = false) {
        pararDemo();
        const dificuldade = document.getElementById("select-dificuldade").value;
        const frotaArray = !isDemo
            ? Object.values(estado.setup.posicionados).map((p) => ({
                  id: p.id,
                  linha: p.linha,
                  coluna: p.coluna,
                  horizontal: p.horizontal,
              }))
            : null;

        const resp = await fetch("/api/novo-jogo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                dificuldade,
                nao_adjacente: estado.setup.naoAdjacente,
                frota_jogador: frotaArray && frotaArray.length === FROTA.length ? frotaArray : null,
            }),
        });

        const dados = await resp.json();
        if (!resp.ok) {
            alert(dados.erro || "Erro ao iniciar partida.");
            return;
        }

        estado.gameId = dados.game_id;
        estado.dadosJogo = dados;
        estado.ultimaJogadaIA = null;
        estado.bloqueado = false;

        document.getElementById("combat-log").innerHTML = "";
        document.getElementById("titulo-frota-aliada").innerHTML = isDemo
            ? '🤖 IA ALIADA (ALMIRANTE) <span class="sub-tag">(Alvo do Mapa de Calor)</span>'
            : '🛡️ SUA FROTA <span class="sub-tag">(Visão da IA)</span>';
        document.getElementById("turno-indicador").textContent = isDemo
            ? "SIMULAÇÃO IA vs IA ATIVA"
            : "SUA VEZ DE ATACAR";

        const regraTexto = dados.nao_adjacente ? " • Regra: Sem Adjacência" : "";
        adicionarLog(
            `[SISTEMA] ${isDemo ? "Simulação IA vs IA" : "Batalha"} iniciada (${dificuldade.toUpperCase()}${regraTexto}).`
        );

        elSecaoSetup.classList.add("hidden");
        elSecaoCombate.classList.remove("hidden");
        tocarSom("sonar");
        renderizarCombate();

        if (isDemo) {
            iniciarLoopDemo();
        }
    }

    function iniciarLoopDemo() {
        estado.modoDemo = true;
        elBtnDemo.classList.add("active");
        elBtnDemo.textContent = "⏸ Pausar IA vs IA";

        estado.demoTimer = setInterval(async () => {
            if (!estado.modoDemo || estado.bloqueado || !estado.dadosJogo || estado.dadosJogo.encerrado) {
                return;
            }
            estado.bloqueado = true;
            try {
                const resp = await fetch("/api/turno-auto", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ game_id: estado.gameId }),
                });
                const dados = await resp.json();
                if (resp.ok) {
                    processarRespostaTurno(dados, "IA Aliada");
                }
            } finally {
                estado.bloqueado = false;
            }
        }, 320);
    }

    async function dispararContraIA(r, c) {
        if (estado.modoDemo || estado.bloqueado || !estado.dadosJogo || estado.dadosJogo.encerrado) return;
        if (estado.dadosJogo.tabuleiro_ia[r][c] !== 0) return;

        estado.bloqueado = true;
        document.getElementById("turno-indicador").textContent = "IA CALCULANDO DENSIDADE...";

        try {
            const resp = await fetch("/api/atirar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    game_id: estado.gameId,
                    linha: r,
                    coluna: c,
                }),
            });

            const dados = await resp.json();
            if (!resp.ok) return;

            processarRespostaTurno(dados, "Você");
        } finally {
            estado.bloqueado = false;
            if (!estado.modoDemo) {
                document.getElementById("turno-indicador").textContent = "SUA VEZ DE ATACAR";
            }
        }
    }

    function exibirModalFim(dados) {
        const vitoria = dados.vencedor === "jogador";
        const st = dados.estatisticas;
        const precJog = st.tiros_jogador ? Math.round((st.acertos_jogador / st.tiros_jogador) * 100) : 0;
        const precIA = st.tiros_ia ? Math.round((st.acertos_ia / st.tiros_ia) * 100) : 0;

        document.getElementById("modal-icone").textContent = vitoria ? "🏆" : "💀";
        document.getElementById("modal-titulo").textContent = vitoria
            ? "SUPREMACIA NAVAL ALCANÇADA!"
            : "FROTA NEUTRALIZADA PELA IA";
        document.getElementById("modal-mensagem").textContent = vitoria
            ? "A frota inimiga foi completamente localizada e destruída."
            : "O motor de densidade probabilística mapeou toda a formação aliada.";

        document.getElementById("modal-stats").innerHTML = `
            <div>Turnos Totais: <strong>${dados.turnos}</strong></div>
            <div>Precisão Aliada: <strong>${precJog}%</strong> (${st.acertos_jogador}/${st.tiros_jogador})</div>
            <div>Precisão IA Inimiga: <strong>${precIA}%</strong> (${st.acertos_ia}/${st.tiros_ia})</div>
            <div>Entropia Final: <strong>${dados.mapa_calor.entropia_bits.toFixed(2)} bits</strong></div>
        `;
        document.getElementById("modal-fim").classList.remove("hidden");
    }

    // =========================================================================
    // EVENTOS E INICIALIZAÇÃO
    // =========================================================================
    construirEstruturaGrid(elGridSetup, clicarCelulaSetup, atualizarGridSetup);
    elGridSetup.addEventListener("mouseleave", () => atualizarGridSetup());
    elGridSetup.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        estado.setup.horizontal = !estado.setup.horizontal;
        renderizarDoca();
        atualizarGridSetup();
    });

    construirEstruturaGrid(elGridJogador, null, null);
    construirEstruturaGrid(elGridInimigo, dispararContraIA, null);

    elChkNaoAdjacente.addEventListener("change", (e) => {
        estado.setup.naoAdjacente = e.target.checked;
        gerarFrotaAleatoriaSetup();
    });

    document.getElementById("btn-girar").addEventListener("click", () => {
        estado.setup.horizontal = !estado.setup.horizontal;
        renderizarDoca();
        atualizarGridSetup();
    });

    document.addEventListener("keydown", (e) => {
        if (e.key.toLowerCase() === "r" && !elSecaoSetup.classList.contains("hidden")) {
            estado.setup.horizontal = !estado.setup.horizontal;
            renderizarDoca();
            atualizarGridSetup();
        }
    });

    document.getElementById("btn-aleatorio").addEventListener("click", gerarFrotaAleatoriaSetup);

    document.getElementById("btn-limpar").addEventListener("click", () => {
        estado.setup.posicionados = {};
        estado.setup.navioSelecionadoId = FROTA[0]?.id || null;
        renderizarDoca();
        atualizarGridSetup();
    });

    elBtnIniciar.addEventListener("click", () => iniciarNovaBatalha(false));

    elBtnDemo.addEventListener("click", () => {
        if (estado.modoDemo) {
            pararDemo();
            document.getElementById("turno-indicador").textContent = "SIMULAÇÃO PAUSADA";
        } else if (!elSecaoCombate.classList.contains("hidden") && estado.dadosJogo && !estado.dadosJogo.encerrado) {
            iniciarLoopDemo();
        } else {
            iniciarNovaBatalha(true);
        }
    });

    document.getElementById("btn-toggle-calor").addEventListener("click", (e) => {
        estado.mostrarCalor = !estado.mostrarCalor;
        e.currentTarget.classList.toggle("active", estado.mostrarCalor);
        e.currentTarget.innerHTML = estado.mostrarCalor
            ? '<span class="dot-live"></span> Raio-X IA: ON'
            : "Raio-X IA: OFF";
        renderizarCombate();
    });

    document.getElementById("btn-toggle-som").addEventListener("click", (e) => {
        estado.somAtivo = !estado.somAtivo;
        e.currentTarget.classList.toggle("active", estado.somAtivo);
        e.currentTarget.textContent = estado.somAtivo ? "🔊 Sonar" : "🔇 Mudo";
    });

    function voltarParaSetup() {
        pararDemo();
        document.getElementById("modal-fim").classList.add("hidden");
        elSecaoCombate.classList.add("hidden");
        elSecaoSetup.classList.remove("hidden");
        gerarFrotaAleatoriaSetup();
    }

    document.getElementById("btn-reiniciar-setup").addEventListener("click", voltarParaSetup);
    document.getElementById("btn-modal-novo").addEventListener("click", voltarParaSetup);

    gerarFrotaAleatoriaSetup();
})();
