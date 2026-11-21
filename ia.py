"""
Motor de Inteligência Artificial baseado em Inferência Probabilística (Mapa de Calor).
Calcula a distribuição de densidade de probabilidade de todos os posicionamentos
possíveis dos navios restantes do oponente.
"""

import random
from typing import Dict, List, Tuple

from jogo import (
    AGUA,
    NAVIO_AFUNDADO,
    TAMANHO_TABULEIRO,
    TIRO_ACERTO,
    TIRO_AGUA,
    coordenada_para_texto,
)


class IAMapaDeCalor:
    """IA que utiliza Função de Densidade de Probabilidade para jogar Batalha Naval."""

    def __init__(self, dificuldade: str = "almirante", tamanho: int = TAMANHO_TABULEIRO):
        self.dificuldade = dificuldade.lower()
        self.tamanho = tamanho

    def _posicionamento_valido(
        self,
        grade_observada: List[List[int]],
        linha: int,
        coluna: int,
        tamanho_navio: int,
        horizontal: bool,
    ) -> Tuple[bool, int, List[Tuple[int, int]]]:
        """
        Verifica se um navio de `tamanho_navio` pode ocupar a posição dada.
        Retorna (valido, quantidade_de_hits_cobertos, lista_de_celulas).
        """
        celulas: List[Tuple[int, int]] = []
        hits_cobertos = 0

        for i in range(tamanho_navio):
            r = linha if horizontal else linha + i
            c = coluna + i if horizontal else coluna

            if r >= self.tamanho or c >= self.tamanho:
                return False, 0, []

            estado = grade_observada[r][c]
            # Tiros na água (2) e navios já afundados (4) bloqueiam qualquer navio restante
            if estado in (TIRO_AGUA, NAVIO_AFUNDADO):
                return False, 0, []

            if estado == TIRO_ACERTO:
                hits_cobertos += 1

            celulas.append((r, c))

        return True, hits_cobertos, celulas

    def calcular_mapa_calor(
        self,
        grade_observada: List[List[int]],
        tamanhos_restantes: List[int],
    ) -> Dict:
        """
        Calcula o mapa de densidade de probabilidade para cada célula (10x10).
        Retorna intensidades normalizadas (0..100), chances reais (%) e telemetria.
        """
        pesos = [[0.0 for _ in range(self.tamanho)] for _ in range(self.tamanho)]

        hits_ativos = [
            (r, c)
            for r in range(self.tamanho)
            for c in range(self.tamanho)
            if grade_observada[r][c] == TIRO_ACERTO
        ]
        modo_caca = len(hits_ativos) > 0

        for tamanho_navio in tamanhos_restantes:
            for r in range(self.tamanho):
                for c in range(self.tamanho):
                    for horizontal in (True, False):
                        valido, hits_cobertos, celulas = self._posicionamento_valido(
                            grade_observada, r, c, tamanho_navio, horizontal
                        )
                        if not valido:
                            continue

                        if modo_caca:
                            # Se existem hits não afundados, configurações que não passam
                            # por nenhum hit recebem peso mínimo; configurações que cruzam
                            # múltiplos hits alinhados recebem peso exponencial.
                            if hits_cobertos == 0:
                                peso = 0.01
                            else:
                                peso = 15.0 ** hits_cobertos
                        else:
                            # Modo Patrulha: todas as configurações válidas têm peso base igual
                            peso = 1.0

                        for pr, pc in celulas:
                            if grade_observada[pr][pc] == AGUA:
                                pesos[pr][pc] += peso

        # Zera explicitamente células já atacadas
        for r in range(self.tamanho):
            for c in range(self.tamanho):
                if grade_observada[r][c] != AGUA:
                    pesos[r][c] = 0.0

        soma_total = sum(sum(linha) for linha in pesos)
        max_peso = max((max(linha) for linha in pesos), default=0.0)

        intensidade = [[0.0 for _ in range(self.tamanho)] for _ in range(self.tamanho)]
        chances_reais = [[0.0 for _ in range(self.tamanho)] for _ in range(self.tamanho)]

        melhor_coord = (0, 0)
        melhor_chance = 0.0

        for r in range(self.tamanho):
            for c in range(self.tamanho):
                if max_peso > 0:
                    intensidade[r][c] = round((pesos[r][c] / max_peso) * 100.0, 1)
                if soma_total > 0:
                    chance = round((pesos[r][c] / soma_total) * 100.0, 1)
                    chances_reais[r][c] = chance
                    if chance > melhor_chance:
                        melhor_chance = chance
                        melhor_coord = (r, c)

        if len(hits_ativos) >= 2:
            status_ia = "ALVO TRAVADO (Inferência de Eixo)"
        elif len(hits_ativos) == 1:
            status_ia = "CAÇA ATIVA (Rastreando Impacto)"
        else:
            status_ia = "VARREDURA PROBABILÍSTICA (Patrulha)"

        return {
            "intensidade": intensidade,
            "chances_reais": chances_reais,
            "pesos_brutos": pesos,
            "status_ia": status_ia,
            "hits_ativos": len(hits_ativos),
            "pico_probabilidade": melhor_chance,
            "melhor_alvo": coordenada_para_texto(*melhor_coord) if max_peso > 0 else "-",
        }

    def escolher_jogada(
        self,
        grade_observada: List[List[int]],
        tamanhos_restantes: List[int],
    ) -> Dict:
        """
        Escolhe a próxima coordenada de disparo de acordo com o nível de dificuldade
        e retorna a jogada juntamente com o mapa de calor atualizado.
        """
        analise = self.calcular_mapa_calor(grade_observada, tamanhos_restantes)
        pesos = analise["pesos_brutos"]

        candidatos: List[Tuple[float, int, int]] = []
        for r in range(self.tamanho):
            for c in range(self.tamanho):
                if grade_observada[r][c] == AGUA:
                    candidatos.append((pesos[r][c], r, c))

        if not candidatos:
            raise ValueError("Não há coordenadas disponíveis para disparo.")

        candidatos.sort(key=lambda item: item[0], reverse=True)

        if self.dificuldade == "recruta":
            # 55% aleatório, 45% probabilístico
            if random.random() < 0.55:
                _, linha, coluna = random.choice(candidatos)
            else:
                _, linha, coluna = candidatos[0]
        elif self.dificuldade == "comandante":
            # Escolhe com ponderação entre os 3 melhores alvos
            top_k = candidatos[: min(3, len(candidatos))]
            pesos_top = [max(item[0], 0.1) for item in top_k]
            escolhido = random.choices(top_k, weights=pesos_top, k=1)[0]
            _, linha, coluna = escolhido
        else:
            # "almirante": Sempre ataca o pico máximo de densidade (desempate aleatório)
            maior_peso = candidatos[0][0]
            melhores = [
                (r, c) for peso, r, c in candidatos if abs(peso - maior_peso) < 1e-6
            ]
            linha, coluna = random.choice(melhores)

        return {
            "linha": linha,
            "coluna": coluna,
            "coordenada": coordenada_para_texto(linha, coluna),
            "probabilidade_alvo": analise["chances_reais"][linha][coluna],
            "analise": {
                "intensidade": analise["intensidade"],
                "chances_reais": analise["chances_reais"],
                "status_ia": analise["status_ia"],
                "hits_ativos": analise["hits_ativos"],
                "pico_probabilidade": analise["pico_probabilidade"],
                "melhor_alvo": analise["melhor_alvo"],
            },
        }
