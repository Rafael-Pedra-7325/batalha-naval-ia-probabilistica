"""
Servidor Web Flask para o jogo Batalha Naval com IA de Mapa de Calor.
Inclui suporte à regra opcional de navios não-adjacentes e ao modo demonstração IA vs IA.
"""

import uuid
from typing import Dict

from flask import Flask, jsonify, render_template, request

from ia import IAMapaDeCalor
from jogo import FROTA_PADRAO, Tabuleiro

app = Flask(__name__)

PARTIDAS: Dict[str, Dict] = {}
MAX_PARTIDAS_MEMORIA = 200


def _limpar_partidas_antigas() -> None:
    while len(PARTIDAS) >= MAX_PARTIDAS_MEMORIA:
        chave_mais_antiga = next(iter(PARTIDAS))
        PARTIDAS.pop(chave_mais_antiga, None)


def _serializar_estado(partida: Dict, revelar_ia: bool = False) -> Dict:
    tab_jogador: Tabuleiro = partida["tabuleiro_jogador"]
    tab_ia: Tabuleiro = partida["tabuleiro_ia"]
    ia: IAMapaDeCalor = partida["ia"]

    analise_atual = ia.calcular_mapa_calor(
        tab_jogador.visao_publica(revelar_navios=False),
        tab_jogador.tamanhos_navios_restantes(),
    )

    return {
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
    """Executa a jogada do lado aliado (humano ou IA aliada) e o contra-ataque inimigo."""
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

    _limpar_partidas_antigas()
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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
