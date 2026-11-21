"""
Servidor Web Flask para o jogo Batalha Naval.
Suporta:
1. Modo Solo contra IA de Mapa de Calor;
2. Modo Demonstração IA vs IA;
3. Modo Multiplayer Online (2 Celulares / Dispositivos) via Código de Sala em memória.
"""

import random
import string
import threading
import time
import uuid
from typing import Dict, Optional

from flask import Flask, jsonify, render_template, request

from ia import IAMapaDeCalor
from jogo import FROTA_PADRAO, Tabuleiro

app = Flask(__name__)

# Armazenamento em memória para partidas Solo e Salas PvP (thread-safe)
LOCK_ESTADO = threading.Lock()
PARTIDAS: Dict[str, Dict] = {}
SALAS_PVP: Dict[str, Dict] = {}

MAX_PARTIDAS_MEMORIA = 200
TTL_SALA_SEGUNDOS = 7200  # 2 horas


def _limpar_memoria_antiga() -> None:
    """Remove partidas solo excedentes e salas PvP expiradas."""
    while len(PARTIDAS) >= MAX_PARTIDAS_MEMORIA:
        chave_mais_antiga = next(iter(PARTIDAS))
        PARTIDAS.pop(chave_mais_antiga, None)

    agora = time.time()
    expiradas = [
        cod
        for cod, sala in SALAS_PVP.items()
        if (agora - sala["atualizado_em"]) > TTL_SALA_SEGUNDOS
    ]
    for cod in expiradas:
        SALAS_PVP.pop(cod, None)

    while len(SALAS_PVP) >= MAX_PARTIDAS_MEMORIA:
        chave_mais_antiga = next(iter(SALAS_PVP))
        SALAS_PVP.pop(chave_mais_antiga, None)


def _gerar_codigo_sala() -> str:
    """Gera um código curto e fácil de digitar no celular (ex: K8P4)."""
    caracteres = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(100):
        codigo = "".join(random.choices(caracteres, k=4))
        if codigo not in SALAS_PVP:
            return codigo
    return str(uuid.uuid4())[:6].upper()


# =============================================================================
# SERIALIZAÇÃO E LÓGICA — MODO SOLO / IA vs IA
# =============================================================================
def _serializar_estado(partida: Dict, revelar_ia: bool = False) -> Dict:
    tab_jogador: Tabuleiro = partida["tabuleiro_jogador"]
    tab_ia: Tabuleiro = partida["tabuleiro_ia"]
    ia: IAMapaDeCalor = partida["ia"]

    analise_atual = ia.calcular_mapa_calor(
        tab_jogador.visao_publica(revelar_navios=False),
        tab_jogador.tamanhos_navios_restantes(),
    )

    return {
        "modo": "solo",
        "game_id": partida["game_id"],
        "dificuldade": ia.dificuldade,
        "nao_adjacente": partida["nao_adjacente"],
        "encerrado": partida["encerrado"],
        "vencedor": partida["vencedor"],
        "turnos": partida["turnos"],
        "tabuleiro_jogador": tab_jogador.visao_publica(revelar_navios=True),
        "tabuleiro_ia": tab_ia.visao_publica(revelar_navios=revelar_ia),
        "frota_jogador": tab_jogador.resumo_frota(revelar_posicoes=True),
        "frota_ia": tab_ia.resumo_frota(revelar_posicoes=revelar_ia),
        "mapa_calor": {
            "intensidade": analise_atual["intensidade"],
            "chances_reais": analise_atual["chances_reais"],
            "status_ia": analise_atual["status_ia"],
            "hits_ativos": analise_atual["hits_ativos"],
            "pico_probabilidade": analise_atual["pico_probabilidade"],
            "melhor_alvo": analise_atual["melhor_alvo"],
            "entropia_bits": analise_atual["entropia_bits"],
        },
        "estatisticas": partida["estatisticas"],
    }


def _executar_rodada(partida: Dict, linha: int, coluna: int) -> Dict:
    """Executa a jogada do lado aliado e o contra-ataque da IA."""
    tab_ia: Tabuleiro = partida["tabuleiro_ia"]
    tab_jogador: Tabuleiro = partida["tabuleiro_jogador"]
    ia: IAMapaDeCalor = partida["ia"]

    resultado_jogador = tab_ia.receber_tiro(linha, coluna)
    if not resultado_jogador["valido"]:
        return {"erro": resultado_jogador["motivo"], "status_code": 400}

    partida["turnos"] += 1
    partida["estatisticas"]["tiros_jogador"] += 1
    if resultado_jogador["resultado"] in ("acerto", "afundado"):
        partida["estatisticas"]["acertos_jogador"] += 1

    if resultado_jogador["fim_de_jogo"]:
        partida["encerrado"] = True
        partida["vencedor"] = "jogador"
        estado = _serializar_estado(partida, revelar_ia=True)
        estado["acao_jogador"] = resultado_jogador
        estado["acao_ia"] = None
        return estado

    visao_ia = tab_jogador.visao_publica(revelar_navios=False)
    restantes_jogador = tab_jogador.tamanhos_navios_restantes()
    decisao_ia = ia.escolher_jogada(visao_ia, restantes_jogador)

    resultado_ia = tab_jogador.receber_tiro(decisao_ia["linha"], decisao_ia["coluna"])
    resultado_ia["probabilidade_alvo"] = decisao_ia["probabilidade_alvo"]

    partida["estatisticas"]["tiros_ia"] += 1
    if resultado_ia["resultado"] in ("acerto", "afundado"):
        partida["estatisticas"]["acertos_ia"] += 1

    if resultado_ia["fim_de_jogo"]:
        partida["encerrado"] = True
        partida["vencedor"] = "ia"

    estado = _serializar_estado(partida, revelar_ia=partida["encerrado"])
    estado["acao_jogador"] = resultado_jogador
    estado["acao_ia"] = resultado_ia
    return estado


# =============================================================================
# SERIALIZAÇÃO — MODO MULTIPLAYER ONLINE (2 APARELHOS)
# =============================================================================
def _identificar_papel(sala: Dict, token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    if sala["tokens"].get("p1") == token:
        return "p1"
    if sala["tokens"].get("p2") == token:
        return "p2"
    return None


def _serializar_estado_pvp(sala: Dict, papel: str) -> Dict:
    adversario = "p2" if papel == "p1" else "p1"
    tab_proprio: Tabuleiro = sala["tabuleiros"][papel]
    tab_oponente: Tabuleiro = sala["tabuleiros"][adversario]
    ia_assistente: IAMapaDeCalor = sala["ia_assistente"]

    fase = sala["fase"]
    oponente_conectado = sala["tokens"]["p2"] is not None
    eu_pronto = sala["prontos"][papel]
    oponente_pronto = sala["prontos"][adversario]

    # Calcula o mapa de calor sobre o radar inimigo como Assistente Tático
    restantes_oponente = (
        tab_oponente.tamanhos_navios_restantes()
        if tab_oponente.navios
        else [n["tamanho"] for n in FROTA_PADRAO]
    )
    analise_radar = ia_assistente.calcular_mapa_calor(
        tab_oponente.visao_publica(revelar_navios=False),
        restantes_oponente,
    )

    revelar_oponente = fase == "encerrado"
    vencedor_relativo = None
    if sala["vencedor"] == papel:
        vencedor_relativo = "jogador"
    elif sala["vencedor"] == adversario:
        vencedor_relativo = "oponente"

    st_eu = sala["estatisticas"][papel]
    st_op = sala["estatisticas"][adversario]

    return {
        "modo": "pvp",
        "codigo_sala": sala["codigo"],
        "papel": papel,
        "fase": fase,
        "nao_adjacente": sala["nao_adjacente"],
        "oponente_conectado": oponente_conectado,
        "eu_pronto": eu_pronto,
        "oponente_pronto": oponente_pronto,
        "eh_minha_vez": (fase == "combate" and sala["turno_de"] == papel),
        "encerrado": fase == "encerrado",
        "vencedor": vencedor_relativo,
        "turnos": sala["turnos"],
        "tabuleiro_jogador": tab_proprio.visao_publica(revelar_navios=True),
        "tabuleiro_ia": tab_oponente.visao_publica(revelar_navios=revelar_oponente),
        "frota_jogador": tab_proprio.resumo_frota(revelar_posicoes=True),
        "frota_ia": tab_oponente.resumo_frota(revelar_posicoes=revelar_oponente),
        "mapa_calor": {
            "intensidade": analise_radar["intensidade"],
            "chances_reais": analise_radar["chances_reais"],
            "status_ia": analise_radar["status_ia"],
            "hits_ativos": analise_radar["hits_ativos"],
            "pico_probabilidade": analise_radar["pico_probabilidade"],
            "melhor_alvo": analise_radar["melhor_alvo"],
            "entropia_bits": analise_radar["entropia_bits"],
        },
        "estatisticas": {
            "tiros_jogador": st_eu["tiros"],
            "acertos_jogador": st_eu["acertos"],
            "tiros_ia": st_op["tiros"],
            "acertos_ia": st_op["acertos"],
        },
        "ultimo_evento": sala["ultimo_evento"],
    }


# =============================================================================
# ROTAS WEB & API SOLO
# =============================================================================
@app.route("/")
def index():
    return render_template("index.html", frota_padrao=FROTA_PADRAO)


@app.route("/api/novo-jogo", methods=["POST"])
def novo_jogo():
    dados = request.get_json(silent=True) or {}
    dificuldade = dados.get("dificuldade", "almirante")
    if dificuldade not in ("recruta", "comandante", "almirante"):
        dificuldade = "almirante"

    nao_adjacente = bool(dados.get("nao_adjacente", False))
    frota_customizada = dados.get("frota_jogador")

    tab_jogador = Tabuleiro(nao_adjacente=nao_adjacente)
    if frota_customizada:
        sucesso = tab_jogador.posicionar_frota_personalizada(frota_customizada)
        if not sucesso:
            return (
                jsonify(
                    {
                        "erro": "Posicionamento inválido. Verifique sobreposições ou a regra de não-adjacência."
                    }
                ),
                400,
            )
    else:
        tab_jogador.posicionar_aleatorio()

    tab_ia = Tabuleiro(nao_adjacente=nao_adjacente)
    tab_ia.posicionar_aleatorio()

    ia = IAMapaDeCalor(dificuldade=dificuldade, nao_adjacente=nao_adjacente)

    with LOCK_ESTADO:
        _limpar_memoria_antiga()
        game_id = str(uuid.uuid4())
        partida = {
            "game_id": game_id,
            "nao_adjacente": nao_adjacente,
            "tabuleiro_jogador": tab_jogador,
            "tabuleiro_ia": tab_ia,
            "ia": ia,
            "encerrado": False,
            "vencedor": None,
            "turnos": 0,
            "estatisticas": {
                "tiros_jogador": 0,
                "acertos_jogador": 0,
                "tiros_ia": 0,
                "acertos_ia": 0,
            },
        }
        PARTIDAS[game_id] = partida
        return jsonify(_serializar_estado(partida, revelar_ia=False))


@app.route("/api/atirar", methods=["POST"])
def atirar():
    dados = request.get_json(silent=True) or {}
    game_id = dados.get("game_id")

    with LOCK_ESTADO:
        if not game_id or game_id not in PARTIDAS:
            return jsonify({"erro": "Partida não encontrada. Inicie uma nova batalha."}), 404

        partida = PARTIDAS[game_id]
        if partida["encerrado"]:
            return jsonify({"erro": "Esta partida já foi encerrada."}), 400

        try:
            linha = int(dados.get("linha"))
            coluna = int(dados.get("coluna"))
        except (TypeError, ValueError):
            return jsonify({"erro": "Coordenadas inválidas."}), 400

        resposta = _executar_rodada(partida, linha, coluna)
        if "erro" in resposta:
            return jsonify({"erro": resposta["erro"]}), resposta.get("status_code", 400)
        return jsonify(resposta)


@app.route("/api/turno-auto", methods=["POST"])
def turno_auto():
    """Executa um turno completo de demonstração IA Aliada (Almirante) vs IA Inimiga."""
    dados = request.get_json(silent=True) or {}
    game_id = dados.get("game_id")

    with LOCK_ESTADO:
        if not game_id or game_id not in PARTIDAS:
            return jsonify({"erro": "Partida não encontrada."}), 404

        partida = PARTIDAS[game_id]
        if partida["encerrado"]:
            return jsonify(_serializar_estado(partida, revelar_ia=True))

        tab_ia: Tabuleiro = partida["tabuleiro_ia"]
        ia_aliada = IAMapaDeCalor(
            dificuldade="almirante", nao_adjacente=partida["nao_adjacente"]
        )
        decisao_aliada = ia_aliada.escolher_jogada(
            tab_ia.visao_publica(revelar_navios=False),
            tab_ia.tamanhos_navios_restantes(),
        )

        resposta = _executar_rodada(
            partida, decisao_aliada["linha"], decisao_aliada["coluna"]
        )
        if "erro" in resposta:
            return jsonify({"erro": resposta["erro"]}), resposta.get("status_code", 400)
        if resposta.get("acao_jogador"):
            resposta["acao_jogador"]["probabilidade_alvo"] = decisao_aliada["probabilidade_alvo"]
        return jsonify(resposta)


# =============================================================================
# ROTAS API — MULTIPLAYER ONLINE (2 CELULARES / DISPOSITIVOS)
# =============================================================================
@app.route("/api/pvp/criar", methods=["POST"])
def pvp_criar():
    dados = request.get_json(silent=True) or {}
    nao_adjacente = bool(dados.get("nao_adjacente", False))

    with LOCK_ESTADO:
        _limpar_memoria_antiga()
        codigo = _gerar_codigo_sala()
        token_p1 = str(uuid.uuid4())

        sala = {
            "codigo": codigo,
            "nao_adjacente": nao_adjacente,
            "fase": "aguardando_oponente",
            "tokens": {"p1": token_p1, "p2": None},
            "tabuleiros": {
                "p1": Tabuleiro(nao_adjacente=nao_adjacente),
                "p2": Tabuleiro(nao_adjacente=nao_adjacente),
            },
            "prontos": {"p1": False, "p2": False},
            "turno_de": "p1",
            "turnos": 0,
            "vencedor": None,
            "ia_assistente": IAMapaDeCalor(
                dificuldade="almirante", nao_adjacente=nao_adjacente
            ),
            "estatisticas": {
                "p1": {"tiros": 0, "acertos": 0},
                "p2": {"tiros": 0, "acertos": 0},
            },
            "evento_id": 0,
            "ultimo_evento": None,
            "atualizado_em": time.time(),
        }
        SALAS_PVP[codigo] = sala

        payload = _serializar_estado_pvp(sala, "p1")
        payload["player_token"] = token_p1
        return jsonify(payload)


@app.route("/api/pvp/entrar", methods=["POST"])
def pvp_entrar():
    dados = request.get_json(silent=True) or {}
    codigo = str(dados.get("codigo_sala", "")).strip().upper()
    token_existente = dados.get("player_token")

    with LOCK_ESTADO:
        if not codigo or codigo not in SALAS_PVP:
            return jsonify({"erro": "Sala não encontrada. Verifique o código informado."}), 404

        sala = SALAS_PVP[codigo]
        sala["atualizado_em"] = time.time()

        # Reconexão caso o jogador já pertença à sala
        papel_existente = _identificar_papel(sala, token_existente)
        if papel_existente:
            payload = _serializar_estado_pvp(sala, papel_existente)
            payload["player_token"] = token_existente
            return jsonify(payload)

        if sala["tokens"]["p2"] is not None:
            return jsonify({"erro": "Esta sala já está cheia (2 jogadores conectados)."}), 400

        token_p2 = str(uuid.uuid4())
        sala["tokens"]["p2"] = token_p2
        if sala["fase"] == "aguardando_oponente":
            sala["fase"] = "posicionamento"

        payload = _serializar_estado_pvp(sala, "p2")
        payload["player_token"] = token_p2
        return jsonify(payload)


@app.route("/api/pvp/posicionar", methods=["POST"])
def pvp_posicionar():
    dados = request.get_json(silent=True) or {}
    codigo = str(dados.get("codigo_sala", "")).strip().upper()
    token = dados.get("player_token")
    frota_customizada = dados.get("frota_jogador")

    with LOCK_ESTADO:
        if codigo not in SALAS_PVP:
            return jsonify({"erro": "Sala não encontrada ou expirada."}), 404

        sala = SALAS_PVP[codigo]
        papel = _identificar_papel(sala, token)
        if not papel:
            return jsonify({"erro": "Sessão inválida para esta sala."}), 403

        if sala["fase"] not in ("aguardando_oponente", "posicionamento"):
            return jsonify({"erro": "A fase de posicionamento já foi encerrada."}), 400

        tab = Tabuleiro(nao_adjacente=sala["nao_adjacente"])
        if not frota_customizada or not tab.posicionar_frota_personalizada(frota_customizada):
            return (
                jsonify(
                    {
                        "erro": "Posicionamento inválido. Verifique sobreposições ou a regra de não-adjacência."
                    }
                ),
                400,
            )

        sala["tabuleiros"][papel] = tab
        sala["prontos"][papel] = True
        sala["atualizado_em"] = time.time()

        if sala["prontos"]["p1"] and sala["prontos"]["p2"]:
            sala["fase"] = "combate"
            sala["turno_de"] = "p1"

        return jsonify(_serializar_estado_pvp(sala, papel))


@app.route("/api/pvp/atirar", methods=["POST"])
def pvp_atirar():
    dados = request.get_json(silent=True) or {}
    codigo = str(dados.get("codigo_sala", "")).strip().upper()
    token = dados.get("player_token")

    with LOCK_ESTADO:
        if codigo not in SALAS_PVP:
            return jsonify({"erro": "Sala não encontrada ou expirada."}), 404

        sala = SALAS_PVP[codigo]
        papel = _identificar_papel(sala, token)
        if not papel:
            return jsonify({"erro": "Sessão inválida para esta sala."}), 403

        if sala["fase"] != "combate":
            return jsonify({"erro": "A partida ainda não está em fase de combate."}), 400

        if sala["turno_de"] != papel:
            return jsonify({"erro": "Aguarde! Ainda é a vez do seu adversário."}), 400

        try:
            linha = int(dados.get("linha"))
            coluna = int(dados.get("coluna"))
        except (TypeError, ValueError):
            return jsonify({"erro": "Coordenadas inválidas."}), 400

        adversario = "p2" if papel == "p1" else "p1"
        tab_oponente: Tabuleiro = sala["tabuleiros"][adversario]

        resultado = tab_oponente.receber_tiro(linha, coluna)
        if not resultado["valido"]:
            return jsonify({"erro": resultado["motivo"]}), 400

        sala["atualizado_em"] = time.time()
        sala["turnos"] += 1
        sala["estatisticas"][papel]["tiros"] += 1
        if resultado["resultado"] in ("acerto", "afundado"):
            sala["estatisticas"][papel]["acertos"] += 1

        sala["evento_id"] += 1
        sala["ultimo_evento"] = {
            "id": sala["evento_id"],
            "atacante": papel,
            "resultado": resultado["resultado"],
            "coordenada": resultado["coordenada"],
            "linha": resultado["linha"],
            "coluna": resultado["coluna"],
            "navio_afundado": resultado["navio_afundado"],
            "turno": sala["turnos"],
        }

        if resultado["fim_de_jogo"]:
            sala["fase"] = "encerrado"
            sala["vencedor"] = papel
        else:
            sala["turno_de"] = adversario

        return jsonify(_serializar_estado_pvp(sala, papel))


@app.route("/api/pvp/estado", methods=["POST"])
def pvp_estado():
    dados = request.get_json(silent=True) or {}
    codigo = str(dados.get("codigo_sala", "")).strip().upper()
    token = dados.get("player_token")

    with LOCK_ESTADO:
        if codigo not in SALAS_PVP:
            return jsonify({"erro": "Sala não encontrada ou expirada."}), 404

        sala = SALAS_PVP[codigo]
        papel = _identificar_papel(sala, token)
        if not papel:
            return jsonify({"erro": "Sessão inválida para esta sala."}), 403

        return jsonify(_serializar_estado_pvp(sala, papel))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
