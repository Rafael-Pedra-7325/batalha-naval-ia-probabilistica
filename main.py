"""
Modo de linha de comando (CLI) para jogar Batalha Naval contra a IA de Mapa de Calor
e visualizar a matriz de probabilidades diretamente no terminal.
"""

from ia import IAMapaDeCalor
from jogo import (
    AGUA,
    NAVIO,
    NAVIO_AFUNDADO,
    TAMANHO_TABULEIRO,
    TIRO_ACERTO,
    TIRO_AGUA,
    Tabuleiro,
)

SIMBOLOS = {
    AGUA: "·",
    NAVIO: "■",
    TIRO_AGUA: "o",
    TIRO_ACERTO: "X",
    NAVIO_AFUNDADO: "#",
}


def ler_coordenada(entrada: str):
    entrada = entrada.strip().upper()
    if len(entrada) < 2 or len(entrada) > 3:
        return None
    letra = entrada[0]
    numero = entrada[1:]
    if not ("A" <= letra <= "J") or not numero.isdigit():
        return None
    linha = ord(letra) - ord("A")
    coluna = int(numero) - 1
    if 0 <= linha < TAMANHO_TABULEIRO and 0 <= coluna < TAMANHO_TABULEIRO:
        return linha, coluna
    return None


def exibir_painel(tab_jogador: Tabuleiro, tab_ia: Tabuleiro, ia: IAMapaDeCalor) -> None:
    analise = ia.calcular_mapa_calor(
        tab_jogador.visao_publica(revelar_navios=False),
        tab_jogador.tamanhos_navios_restantes(),
    )
    chances = analise["chances_reais"]
    visao_inimigo = tab_ia.visao_publica(revelar_navios=False)

    print("\n" + "=" * 78)
    print(f"STATUS DA IA: {analise['status_ia']} | Alvo mais provável: {analise['melhor_alvo']} ({analise['pico_probabilidade']}%)")
    print("=" * 78)
    print("      SUA FROTA              RADAR INIMIGO           MAPA DE CALOR DA IA (%)")
    cabecalho = "   " + " ".join(f"{c+1:2d}" for c in range(10))
    print(f"{cabecalho}   | {cabecalho}   |    " + " ".join(f"{c+1:4d}" for c in range(10)))

    for r in range(TAMANHO_TABULEIRO):
        letra = chr(ord("A") + r)
        linha_jog = " ".join(f" {SIMBOLOS[tab_jogador.grade[r][c]]}" for c in range(10))
        linha_ia = " ".join(f" {SIMBOLOS[visao_inimigo[r][c]]}" for c in range(10))
        linha_calor = " ".join(f"{chances[r][c]:4.1f}" for c in range(10))
        print(f" {letra} {linha_jog}   |  {letra} {linha_ia}   |  {letra} {linha_calor}")
    print("=" * 78)


def jogar_terminal() -> None:
    print("⚓ BATALHA NAVAL — IA DE MAPA DE CALOR (MODO TERMINAL)")
    tab_jogador = Tabuleiro()
    tab_jogador.posicionar_aleatorio()

    tab_ia = Tabuleiro()
    tab_ia.posicionar_aleatorio()

    ia = IAMapaDeCalor(dificuldade="almirante")

    while True:
        exibir_painel(tab_jogador, tab_ia, ia)
        entrada = input("\nDigite a coordenada para disparar (ex: E5) ou 'SAIR': ")
        if entrada.strip().upper() == "SAIR":
            print("Partida encerrada.")
            break

        coord = ler_coordenada(entrada)
        if not coord:
            print("⚠️ Coordenada inválida! Use letras de A a J e números de 1 a 10.")
            continue

        res_jog = tab_ia.receber_tiro(*coord)
        if not res_jog["valido"]:
            print(f"⚠️ {res_jog['motivo']}")
            continue

        print(f"\n🎯 Você disparou em {res_jog['coordenada']}: {res_jog['resultado'].upper()}!")
        if res_jog["navio_afundado"]:
            print(f"💥 Você afundou o {res_jog['navio_afundado']['nome']} inimigo!")

        if res_jog["fim_de_jogo"]:
            exibir_painel(tab_jogador, tab_ia, ia)
            print("\n🏆 VITÓRIA! Você destruiu toda a frota inimiga!")
            break

        jogada_ia = ia.escolher_jogada(
            tab_jogador.visao_publica(revelar_navios=False),
            tab_jogador.tamanhos_navios_restantes(),
        )
        res_ia = tab_jogador.receber_tiro(jogada_ia["linha"], jogada_ia["coluna"])
        print(
            f"🤖 IA disparou em {res_ia['coordenada']} "
            f"(Probabilidade: {jogada_ia['probabilidade_alvo']}%): {res_ia['resultado'].upper()}!"
        )
        if res_ia["navio_afundado"]:
            print(f"🔥 A IA afundou seu {res_ia['navio_afundado']['nome']}!")

        if res_ia["fim_de_jogo"]:
            exibir_painel(tab_jogador, tab_ia, ia)
            print("\n💀 DERROTA! A IA afundou toda a sua frota.")
            break


if __name__ == "__main__":
    jogar_terminal()
