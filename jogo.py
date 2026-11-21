"""
Módulo de domínio do jogo Batalha Naval.
Gerencia o tabuleiro 10x10, posicionamento da frota (com suporte opcional à regra
de navios não-adjacentes), disparos e condições de vitória.
"""

import random
from typing import Dict, List, Optional, Tuple

TAMANHO_TABULEIRO = 10

# Códigos de estado das células
AGUA = 0
NAVIO = 1
TIRO_AGUA = 2
TIRO_ACERTO = 3
NAVIO_AFUNDADO = 4

FROTA_PADRAO = [
    {"id": "porta_avioes", "nome": "Porta-Aviões", "tamanho": 5, "codigo": "PA"},
    {"id": "encouracado", "nome": "Encouraçado", "tamanho": 4, "codigo": "EN"},
    {"id": "cruzador", "nome": "Cruzador", "tamanho": 3, "codigo": "CR"},
    {"id": "submarino", "nome": "Submarino", "tamanho": 3, "codigo": "SB"},
    {"id": "destroier", "nome": "Destróier", "tamanho": 2, "codigo": "DT"},
]


def coordenada_para_texto(linha: int, coluna: int) -> str:
    """Converte índices (0..9, 0..9) para notação naval (ex: A1, J10)."""
    letra = chr(ord("A") + linha)
    return f"{letra}{coluna + 1}"


class Tabuleiro:
    """Representa o tabuleiro e a frota de um jogador."""

    def __init__(self, tamanho: int = TAMANHO_TABULEIRO, nao_adjacente: bool = False):
        self.tamanho = tamanho
        self.nao_adjacente = nao_adjacente
        self.grade: List[List[int]] = [
            [AGUA for _ in range(tamanho)] for _ in range(tamanho)
        ]
        self.navios: List[Dict] = []

    def limpar(self) -> None:
        """Reinicia o tabuleiro e remove todos os navios."""
        self.grade = [
            [AGUA for _ in range(self.tamanho)] for _ in range(self.tamanho)
        ]
        self.navios = []

    def dentro_dos_limites(self, linha: int, coluna: int) -> bool:
        return 0 <= linha < self.tamanho and 0 <= coluna < self.tamanho

    def _tem_vizinho_ocupado(self, linha: int, coluna: int) -> bool:
        """Verifica se há algum navio nas 8 células adjacentes."""
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = linha + dr, coluna + dc
                if self.dentro_dos_limites(nr, nc) and self.grade[nr][nc] != AGUA:
                    return True
        return False

    def pode_posicionar(
        self, linha: int, coluna: int, tamanho_navio: int, horizontal: bool
    ) -> bool:
        """Verifica se um navio cabe e respeita as regras de colisão/adjacência."""
        for i in range(tamanho_navio):
            r = linha if horizontal else linha + i
            c = coluna + i if horizontal else coluna
            if not self.dentro_dos_limites(r, c):
                return False
            if self.grade[r][c] != AGUA:
                return False
            if self.nao_adjacente and self._tem_vizinho_ocupado(r, c):
                return False
        return True

    def posicionar_navio(
        self,
        navio_info: Dict,
        linha: int,
        coluna: int,
        horizontal: bool,
    ) -> bool:
        """Posiciona um navio específico no tabuleiro se a posição for válida."""
        tamanho_navio = navio_info["tamanho"]
        if not self.pode_posicionar(linha, coluna, tamanho_navio, horizontal):
            return False

        posicoes: List[Tuple[int, int]] = []
        for i in range(tamanho_navio):
            r = linha if horizontal else linha + i
            c = coluna + i if horizontal else coluna
            self.grade[r][c] = NAVIO
            posicoes.append((r, c))

        self.navios.append(
            {
                "id": navio_info["id"],
                "nome": navio_info["nome"],
                "tamanho": tamanho_navio,
                "codigo": navio_info["codigo"],
                "horizontal": horizontal,
                "posicoes": posicoes,
                "atingidos": set(),
                "afundado": False,
            }
        )
        return True

    def posicionar_frota_personalizada(self, lista_navios: List[Dict]) -> bool:
        """
        Valida e posiciona uma frota completa enviada pelo frontend.
        Espera itens com: {'id', 'linha', 'coluna', 'horizontal'}.
        """
        self.limpar()
        catalogo = {n["id"]: n for n in FROTA_PADRAO}

        if len(lista_navios) != len(FROTA_PADRAO):
            self.limpar()
            return False

        ids_vistos = set()
        for item in lista_navios:
            navio_id = item.get("id")
            if navio_id not in catalogo or navio_id in ids_vistos:
                self.limpar()
                return False
            ids_vistos.add(navio_id)

            linha = int(item.get("linha", -1))
            coluna = int(item.get("coluna", -1))
            horizontal = bool(item.get("horizontal", True))

            if not self.posicionar_navio(catalogo[navio_id], linha, coluna, horizontal):
                self.limpar()
                return False

        return True

    def posicionar_aleatorio(self) -> None:
        """Posiciona toda a frota padrão aleatoriamente no tabuleiro."""
        self.limpar()
        for navio_info in FROTA_PADRAO:
            colocado = False
            tentativas = 0
            while not colocado and tentativas < 600:
                tentativas += 1
                horizontal = random.choice([True, False])
                linha = random.randint(0, self.tamanho - 1)
                coluna = random.randint(0, self.tamanho - 1)
                colocado = self.posicionar_navio(
                    navio_info, linha, coluna, horizontal
                )
            if not colocado:
                self.posicionar_aleatorio()
                return

    def receber_tiro(self, linha: int, coluna: int) -> Dict:
        """Processa um disparo na coordenada (linha, coluna) e retorna o resultado."""
        if not self.dentro_dos_limites(linha, coluna):
            return {"valido": False, "motivo": "Coordenada fora do tabuleiro."}

        estado_atual = self.grade[linha][coluna]
        if estado_atual in (TIRO_AGUA, TIRO_ACERTO, NAVIO_AFUNDADO):
            return {"valido": False, "motivo": "Esta coordenada já foi atacada."}

        coord_texto = coordenada_para_texto(linha, coluna)

        if estado_atual == AGUA:
            self.grade[linha][coluna] = TIRO_AGUA
            return {
                "valido": True,
                "resultado": "agua",
                "linha": linha,
                "coluna": coluna,
                "coordenada": coord_texto,
                "navio_afundado": None,
                "fim_de_jogo": False,
            }

        self.grade[linha][coluna] = TIRO_ACERTO
        navio_atingido: Optional[Dict] = None

        for navio in self.navios:
            if (linha, coluna) in navio["posicoes"]:
                navio["atingidos"].add((linha, coluna))
                navio_atingido = navio
                break

        if navio_atingido and len(navio_atingido["atingidos"]) == navio_atingido["tamanho"]:
            navio_atingido["afundado"] = True
            for r, c in navio_atingido["posicoes"]:
                self.grade[r][c] = NAVIO_AFUNDADO

            fim_de_jogo = all(n["afundado"] for n in self.navios)
            return {
                "valido": True,
                "resultado": "afundado",
                "linha": linha,
                "coluna": coluna,
                "coordenada": coord_texto,
                "navio_afundado": {
                    "id": navio_atingido["id"],
                    "nome": navio_atingido["nome"],
                    "tamanho": navio_atingido["tamanho"],
                    "codigo": navio_atingido["codigo"],
                    "posicoes": [list(p) for p in navio_atingido["posicoes"]],
                },
                "fim_de_jogo": fim_de_jogo,
            }

        return {
            "valido": True,
            "resultado": "acerto",
            "linha": linha,
            "coluna": coluna,
            "coordenada": coord_texto,
            "navio_afundado": None,
            "fim_de_jogo": False,
        }

    def tamanhos_navios_restantes(self) -> List[int]:
        """Retorna os tamanhos dos navios que ainda não foram afundados."""
        return [n["tamanho"] for n in self.navios if not n["afundado"]]

    def visao_publica(self, revelar_navios: bool = False) -> List[List[int]]:
        """
        Retorna a matriz do tabuleiro.
        Se revelar_navios=False, oculta navios intactos (1) como água (0).
        """
        matriz = []
        for r in range(self.tamanho):
            linha = []
            for c in range(self.tamanho):
                valor = self.grade[r][c]
                if valor == NAVIO and not revelar_navios:
                    linha.append(AGUA)
                else:
                    linha.append(valor)
            matriz.append(linha)
        return matriz

    def resumo_frota(self, revelar_posicoes: bool = False) -> List[Dict]:
        """Retorna o status de cada navio para exibição na HUD."""
        resumo = []
        for n in self.navios:
            item = {
                "id": n["id"],
                "nome": n["nome"],
                "tamanho": n["tamanho"],
                "codigo": n["codigo"],
                "afundado": n["afundado"],
                "acertos": len(n["atingidos"]),
            }
            if revelar_posicoes or n["afundado"]:
                item["posicoes"] = [list(p) for p in n["posicoes"]]
            resumo.append(item)
        return resumo
