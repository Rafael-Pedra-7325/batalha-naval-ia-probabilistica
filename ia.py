"""
Motor de Inteligência Artificial baseado em Inferência Probabilística (Mapa de Calor).
Inclui:
- Função de Densidade de Probabilidade (PDF) sobre configurações válidas;
- Paridade Dinâmica (malha adaptativa baseada no menor navio restante);
- Agrupamento de Clusters de Impacto para finalizar alvos sem dispersar fogo;
- Dedução automática de halo de exclusão quando `nao_adjacente=True`;
- Cálculo de Entropia de Shannon (incerteza do radar em bits).
"""

import math
import random
from collections import deque
from typing import Dict, List, Set, Tuple

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

    def __init__(
        self,
        dificuldade: str = "almirante",
        tamanho: int = TAMANHO_TABULEIRO,
        nao_adjacente: bool = False,
    ):
        self.dificuldade = dificuldade.lower()
        self.tamanho = tamanho
        self.nao_adjacente = nao_adjacente

    def _celulas_bloqueadas_por_afundados(
        self, grade_observada: List[List[int]]
    ) -> Set[Tuple[int, int]]:
        """
        Quando a regra `nao_adjacente` está ativa, nenhuma embarcação restante
        pode ocupar as 8 células ao redor de um navio já afundado.
        """
        bloqueadas: Set[Tuple[int, int]] = set()
        if not self.nao_adjacente:
            return bloqueadas

        for r in range(self.tamanho):
            for c in range(self.tamanho):
                if grade_observada[r][c] == NAVIO_AFUNDADO:
                    for dr in (-1, 0, 1):
                        for dc in (-1, 0, 1):
                            nr, nc = r + dr, c + dc
                            if 0 <= nr < self.tamanho and 0 <= nc < self.tamanho:
                                if grade_observada[nr][nc] == AGUA:
                                    bloqueadas.add((nr, nc))
        return bloqueadas

    def _agrupar_clusters_hits(
        self, hits_ativos: List[Tuple[int, int]]
    ) -> List[Set[Tuple[int, int]]]:
        """Agrupa impactos ativos ortogonalmente conectados em clusters distintos."""
        nao_visitados = set(hits_ativos)
        clusters: List[Set[Tuple[int, int]]] = []

        while nao_visitados:
            inicio = next(iter(nao_visitados))
            cluster: Set[Tuple[int, int]] = set()
            fila = deque([inicio])
            nao_visitados.remove(inicio)

            while fila:
                r, c = fila.popleft()
                cluster.add((r, c))
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    viz = (r + dr, c + dc)
                    if viz in nao_visitados:
                        nao_visitados.remove(viz)
                        fila.append(viz)

            clusters.append(cluster)

        clusters.sort(key=len, reverse=True)
        return clusters

    def _posicionamento_valido(
        self,
        grade_observada: List[List[int]],
        bloqueadas_halo: Set[Tuple[int, int]],
        linha: int,
        coluna: int,
        tamanho_navio: int,
        horizontal: bool,
    ) -> Tuple[bool, List[Tuple[int, int]]]:
        """
        Verifica se um navio de `tamanho_navio` pode ocupar a posição dada.
        """
        celulas: List[Tuple[int, int]] = []

        for i in range(tamanho_navio):
            r = linha if horizontal else linha + i
            c = coluna + i if horizontal else coluna

            if r >= self.tamanho or c >= self.tamanho:
                return False, []

            estado = grade_observada[r][c]
            if estado in (TIRO_AGUA, NAVIO_AFUNDADO) or (r, c) in bloqueadas_halo:
                return False, []

            celulas.append((r, c))

        return True, celulas

    def calcular_mapa_calor(
        self,
        grade_observada: List[List[int]],
        tamanhos_restantes: List[int],
    ) -> Dict:
        """
        Calcula o mapa de densidade de probabilidade para cada célula (10x10),
        aplicando paridade adaptativa e foco por cluster de impacto.
        """
        pesos = [[0.0 for _ in range(self.tamanho)] for _ in range(self.tamanho)]
        bloqueadas_halo = self._celulas_bloqueadas_por_afundados(grade_observada)

        hits_ativos = [
            (r, c)
            for r in range(self.tamanho)
            for c in range(self.tamanho)
            if grade_observada[r][c] == TIRO_ACERTO
        ]
        modo_caca = len(hits_ativos) > 0
        clusters = self._agrupar_clusters_hits(hits_ativos)
        cluster_foco = clusters[0] if clusters else set()

        for tamanho_navio in tamanhos_restantes:
            for r in range(self.tamanho):
                for c in range(self.tamanho):
                    for horizontal in (True, False):
                        valido, celulas = self._posicionamento_valido(
                            grade_observada,
                            bloqueadas_halo,
                            r,
                            c,
                            tamanho_navio,
                            horizontal,
                        )
                        if not valido:
                            continue

                        if modo_caca:
                            set_celulas = set(celulas)
                            hits_no_foco = len(set_celulas & cluster_foco)
                            hits_totais = sum(
                                1 for cr, cc in celulas if grade_observada[cr][cc] == TIRO_ACERTO
                            )

                            if hits_no_foco > 0:
                                peso = 25.0 ** hits_no_foco
                            elif hits_totais > 0:
                                peso = 6.0 ** hits_totais
                            else:
                                peso = 0.002
                        else:
                            peso = 1.0

                        for pr, pc in celulas:
                            if grade_observada[pr][pc] == AGUA and (pr, pc) not in bloqueadas_halo:
                                pesos[pr][pc] += peso

        # Paridade Dinâmica no Modo Patrulha (padrão xadrez adaptativo ao menor navio vivo)
        if not modo_caca and tamanhos_restantes:
            menor_navio = min(tamanhos_restantes)
            if menor_navio > 1:
                for r in range(self.tamanho):
                    for c in range(self.tamanho):
                        if pesos[r][c] > 0 and (r + c) % menor_navio == 0:
                            pesos[r][c] *= 1.35

        # Zera células já atacadas ou excluídas pelo halo de não-adjacência
        for r in range(self.tamanho):
            for c in range(self.tamanho):
                if grade_observada[r][c] != AGUA or (r, c) in bloqueadas_halo:
                    pesos[r][c] = 0.0

        soma_total = sum(sum(linha) for linha in pesos)
        max_peso = max((max(linha) for linha in pesos), default=0.0)

        intensidade = [[0.0 for _ in range(self.tamanho)] for _ in range(self.tamanho)]
        chances_reais = [[0.0 for _ in range(self.tamanho)] for _ in range(self.tamanho)]

        melhor_coord = (0, 0)
        melhor_chance = 0.0
        entropia = 0.0

        for r in range(self.tamanho):
            for c in range(self.tamanho):
                if max_peso > 0:
                    intensidade[r][c] = round((pesos[r][c] / max_peso) * 100.0, 1)
                if soma_total > 0 and pesos[r][c] > 0:
                    prob_bruta = pesos[r][c] / soma_total
                    entropia -= prob_bruta * math.log2(prob_bruta)
                    chance = round(prob_bruta * 100.0, 1)
                    chances_reais[r][c] = chance
                    if chance > melhor_chance:
                        melhor_chance = chance
                        melhor_coord = (r, c)

        if len(cluster_foco) >= 2:
            status_ia = "ALVO TRAVADO (Inferência de Eixo)"
        elif len(hits_ativos) >= 1:
            status_ia = f"CAÇA ATIVA ({len(clusters)} alvo{'s' if len(clusters) > 1 else ''})"
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
            "entropia_bits": round(max(entropia, 0.0), 2),
        }

    def escolher_jogada(
        self,
        grade_observada: List[List[int]],
        tamanhos_restantes: List[int],
    ) -> Dict:
        """
        Escolhe a próxima coordenada de disparo de acordo com o nível de dificuldade.
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
            if random.random() < 0.55:
                _, linha, coluna = random.choice(candidatos)
            else:
                _, linha, coluna = candidatos[0]
        elif self.dificuldade == "comandante":
            top_k = candidatos[: min(3, len(candidatos))]
            pesos_top = [max(item[0], 0.1) for item in top_k]
            escolhido = random.choices(top_k, weights=pesos_top, k=1)[0]
            _, linha, coluna = escolhido
        else:
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
                "entropia_bits": analise["entropia_bits"],
            },
        }
