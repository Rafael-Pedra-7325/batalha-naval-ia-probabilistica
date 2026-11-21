(() => {
    const TAMANHO = 10;
    const LETRAS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"];
    const FROTA = window.FROTA_PADRAO || [];

    // Estado global da interface
    const estado = {
        gameId: null,
        mostrarCalor: true,
        somAtivo: true,
        bloqueado: false,
        ultimaJogadaIA: null,
        dadosJogo: null,
        // Estado da fase de posicionamento (Setup)
        setup: {
            navioSelecionadoId: FROTA[0]?.id || null,
            horizontal: true,
            posicionados: {}, // { id: { id, linha, coluna, horizontal, tamanho } }
        },
    };

    // Sintetizador de Sonar / Efeitos via Web Audio API (sem arquivos externos)
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
            osc.frequency.exponentialRampToValueAtTime(440, agora + 0.18);
            gain.gain.setValueAtTime(0.08, agora);
            gain.gain.exponentialRampToValueAtTime(0.001, agora + 0.2);
            osc.start(agora);
            osc.stop(agora + 0.2);
        } else if (tipo === "agua") {
            osc.type = "triangle";
            osc.frequency.setValueAtTime(220, agora);
            osc.frequency.exponentialRampToValueAtTime(90, agora + 0.22);
            gain.gain.setValueAtTime(0.1, agora);
            gain.gain.exponentialRampToValueAtTime(0.001, agora + 0.24);
            osc.start(agora);
            osc.stop(agora + 0.24);
        } else if (tipo === "acerto" || tipo === "afundado") {
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(tipo === "afundado" ? 130 : 180, agora);
            osc.frequency.exponentialRampToValueAtTime(42, agora + (tipo === "afundado" ? 0.55 : 0.32));
            gain.gain.setValueAtTime(0.18, agora);
            gain.gain.exponentialRampToValueAtTime(0.001, agora + (tipo === "afundado" ? 0.58 : 0.35));
            osc.start(agora);
            osc.stop(agora + (tipo === "afundado" ? 0.58 : 0.35));
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
    const elOrientacaoLabel = document.getElementById("orientacao-label");

    // Utilitário para construir a estrutura 11x11 (coordenadas + células)
    function construirEstruturaGrid(container, onCellClick, onCellHover) {
        container.innerHTML = "";
        // Canto superior esquerdo vazio
        const canto = document.createElement("div");
        canto.className = "grid-coord";
        container.appendChild(canto);

        // Cabeçalho 1..10
        for (let c = 0; c < TAMANHO; c++) {
            const colHead = document.createElement("div");
            colHead.className = "grid-coord";
            colHead.textContent = c + 1;
            container.appendChild(colHead);
        }

        // Linhas A..J
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
                if (onCellClick) {
                    cell.addEventListener("click", () => onCellClick(r, c));
                }
                if (onCellHover) {
                    cell.addEventListener("mouseenter", () => onCellHover(r, c));
                }
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
        Object.values(estado.setup.posicionados).forEach((p) => {
            if (p.id === navioId) return;
            obterCelulasNavio(p.linha, p.coluna, p.tamanho, p.horizontal).forEach(([r, c]) => {
                ocupadas.add(`${r},${c}`);
            });
        });

        const candidatas = obterCelulasNavio(linha, coluna, tamanho, horizontal);
        for (const [r, c] of candidatas) {
            if (r < 0 || r >= TAMANHO || c < 0 || c >= TAMANHO) return false;
            if (ocupadas.has(`${r},${c}`)) return false;
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

        // Seleciona automaticamente o próximo navio ainda não posicionado
        const proximo = FROTA.find((n) => !estado.setup.posicionados[n.id]);
        if (proximo) {
            estado.setup.navioSelecionadoId = proximo.id;
        }

        renderizarDoca();
        atualizarGridSetup();
    }

    function gerarFrotaAleatoriaSetup() {
        estado.setup.posicionados = {};
        for (const navio of FROTA) {
            let colocado = false;
            let tentativas = 0;
            while (!colocado && tentativas < 500) {
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
        }
        tocarSom("sonar");
        renderizarDoca();
        atualizarGridSetup();
    }

    // =========================================================================
    // FASE 2: COMBATE E RENDERIZAÇÃO DO MAPA DE CALOR
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

    function renderizarCombate() {
        const d = estado.dadosJogo;
        if (!d) return;

        // Telemetria superior
        document.getElementById("ia-status").textContent = d.mapa_calor.status_ia;
        document.getElementById("ia-melhor-alvo").textContent =
            `${d.mapa_calor.melhor_alvo} (${d.mapa_calor.pico_probabilidade}%)`;
        document.getElementById("hud-turnos").textContent = d.turnos;

        const st = d.estatisticas;
        const precJog = st.tiros_jogador ? Math.round((st.acertos_jogador / st.tiros_jogador) * 100) : 0;
        const precIA = st.tiros_ia ? Math.round((st.acertos_ia / st.tiros_ia) * 100) : 0;
        document.getElementById("hud-precisao").textContent = `${precJog}% / ${precIA}%`;

        // Renderiza Grid do Jogador + Overlay de Mapa de Calor da IA
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
            else if (val === 4) cell.classList.add("sunk", "shot");

            if (
                estado.ultimaJogadaIA &&
                estado.ultimaJogadaIA.linha === r &&
                estado.ultimaJogadaIA.coluna === c
            ) {
                cell.classList.add("last-ai-shot");
            }

            // Aplica gradiente térmico nas células ainda não atacadas
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
            else if (val === 4) cell.classList.add("sunk", "shot");
        });

        // Pills de status das frotas
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

    async function iniciarNovaBatalha() {
        const dificuldade = document.getElementById("select-dificuldade").value;
        const frotaArray = Object.values(estado.setup.posicionados).map((p) => ({
            id: p.id,
            linha: p.linha,
            coluna: p.coluna,
            horizontal: p.horizontal,
        }));

        const resp = await fetch("/api/novo-jogo", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                dificuldade,
                frota_jogador: frotaArray.length === FROTA.length ? frotaArray : null,
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
        adicionarLog(
            `[SISTEMA] Batalha iniciada no modo ${dificuldade.toUpperCase()}. Mapa de calor calibrado.`
        );

        elSecaoSetup.classList.add("hidden");
        elSecaoCombate.classList.remove("hidden");
        tocarSom("sonar");
        renderizarCombate();
    }

    async function dispararContraIA(r, c) {
        if (estado.bloqueado || !estado.dadosJogo || estado.dadosJogo.encerrado) return;
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
            if (!resp.ok) {
                estado.bloqueado = false;
                return;
            }

            estado.dadosJogo = dados;
            const aj = dados.acao_jogador;
            const aia = dados.acao_ia;

            // Som e log do jogador
            tocarSom(aj.resultado);
            let msgJog = `[TURNO ${String(dados.turnos).padStart(2, "0")}] Você disparou em ${aj.coordenada} → ${aj.resultado.toUpperCase()}`;
            if (aj.navio_afundado) msgJog += ` (${aj.navio_afundado.nome} inimigo destruído!)`;
            adicionarLog(msgJog, aj.resultado !== "agua" ? "player-hit" : "");

            // Log da IA se houve contra-ataque
            if (aia) {
                estado.ultimaJogadaIA = { linha: aia.linha, coluna: aia.coluna };
                let msgIA = `[IA • ${aia.probabilidade_alvo}% prob.] Disparou em ${aia.coordenada} → ${aia.resultado.toUpperCase()}`;
                if (aia.navio_afundado) msgIA += ` (Seu ${aia.navio_afundado.nome} foi afundado!)`;
                adicionarLog(msgIA, aia.resultado !== "agua" ? "ai-hit" : "");
            }

            renderizarCombate();

            if (dados.encerrado) {
                exibirModalFim(dados);
            }
        } finally {
            estado.bloqueado = false;
            document.getElementById("turno-indicador").textContent = "SUA VEZ DE ATACAR";
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
            ? "Você superou o motor de inferência probabilística e afundou toda a esquadra inimiga."
            : "A Inteligência Artificial mapeou sua formação através da densidade de probabilidade.";

        document.getElementById("modal-stats").innerHTML = `
            <div>Turnos Totais: <strong>${dados.turnos}</strong></div>
            <div>Sua Precisão: <strong>${precJog}%</strong> (${st.acertos_jogador}/${st.tiros_jogador})</div>
            <div>Precisão da IA: <strong>${precIA}%</strong> (${st.acertos_ia}/${st.tiros_ia})</div>
        `;
        document.getElementById("modal-fim").classList.remove("hidden");
    }

    // =========================================================================
    // EVENTOS E INICIALIZAÇÃO
    // =========================================================================
    construirEstruturaGrid(elGridSetup, clicarCelulaSetup, atualizarGridSetup);
    elGridSetup.addEventListener("mouseleave", () => atualizarGridSetup());

    construirEstruturaGrid(elGridJogador, null, null);
    construirEstruturaGrid(elGridInimigo, dispararContraIA, null);

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

    elBtnIniciar.addEventListener("click", iniciarNovaBatalha);

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
        document.getElementById("modal-fim").classList.add("hidden");
        elSecaoCombate.classList.add("hidden");
        elSecaoSetup.classList.remove("hidden");
        gerarFrotaAleatoriaSetup();
    }

    document.getElementById("btn-reiniciar-setup").addEventListener("click", voltarParaSetup);
    document.getElementById("btn-modal-novo").addEventListener("click", voltarParaSetup);

    // Inicia já com uma frota aleatória pronta na doca para facilitar o início imediato
    gerarFrotaAleatoriaSetup();
})();
