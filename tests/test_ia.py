"""
Testes unitários para as regras de Batalha Naval, Mapa de Calor, Entropia e Clusters.
"""

import unittest

from ia import IAMapaDeCalor
from jogo import (
    AGUA,
    FROTA_PADRAO,
    NAVIO,
    NAVIO_AFUNDADO,
    TIRO_ACERTO,
    TIRO_AGUA,
    Tabuleiro,
)


class TestBatalhaNavalEIA(unittest.TestCase):
    def test_posicionamento_aleatorio_frota_completa(self):
        tab = Tabuleiro()
        tab.posicionar_aleatorio()
        self.assertEqual(len(tab.navios), len(FROTA_PADRAO))
        total_celulas_navio = sum(row.count(NAVIO) for row in tab.grade)
        esperado = sum(n["tamanho"] for n in FROTA_PADRAO)
        self.assertEqual(total_celulas_navio, esperado)

    def test_regra_nao_adjacente_bloqueia_vizinhos(self):
        tab = Tabuleiro(nao_adjacente=True)
        destroier = {"id": "destroier", "nome": "Destróier", "tamanho": 2, "codigo": "DT"}
        submarino = {"id": "submarino", "nome": "Submarino", "tamanho": 3, "codigo": "SB"}

        self.assertTrue(tab.posicionar_navio(destroier, 2, 2, horizontal=True))
        # Tentar posicionar na linha imediatamente abaixo (3, 2) deve falhar
        self.assertFalse(tab.posicionar_navio(submarino, 3, 2, horizontal=True))
        # Posicionar com 1 linha de folga (4, 2) deve funcionar
        self.assertTrue(tab.posicionar_navio(submarino, 4, 2, horizontal=True))

    def test_halo_exclusao_ia_apos_afundar_navio(self):
        ia = IAMapaDeCalor(dificuldade="almirante", nao_adjacente=True)
        grade = [[AGUA for _ in range(10)] for _ in range(10)]
        grade[4][4] = NAVIO_AFUNDADO
        grade[4][5] = NAVIO_AFUNDADO

        analise = ia.calcular_mapa_calor(grade, [3])
        # Vizinhos imediatos do navio afundado devem ter probabilidade 0.0
        self.assertEqual(analise["chances_reais"][3][4], 0.0)
        self.assertEqual(analise["chances_reais"][5][5], 0.0)
        self.assertEqual(analise["chances_reais"][4][3], 0.0)

    def test_entropia_diminui_com_informacao(self):
        ia = IAMapaDeCalor(dificuldade="almirante")
        grade_vazia = [[AGUA for _ in range(10)] for _ in range(10)]
        analise_inicial = ia.calcular_mapa_calor(grade_vazia, [5, 4, 3, 3, 2])

        grade_com_acerto = [[AGUA for _ in range(10)] for _ in range(10)]
        grade_com_acerto[5][5] = TIRO_ACERTO
        analise_caca = ia.calcular_mapa_calor(grade_com_acerto, [5, 4, 3, 3, 2])

        self.assertGreater(analise_inicial["entropia_bits"], analise_caca["entropia_bits"])

    def test_inferencia_alinhamento_horizontal_com_clusters(self):
        ia = IAMapaDeCalor(dificuldade="almirante")
        grade = [[AGUA for _ in range(10)] for _ in range(10)]
        # Cluster principal de 2 acertos em (5, 4) e (5, 5) + acerto isolado em (0, 0)
        grade[5][4] = TIRO_ACERTO
        grade[5][5] = TIRO_ACERTO
        grade[0][0] = TIRO_ACERTO

        jogada = ia.escolher_jogada(grade, [4, 3])
        self.assertIn((jogada["linha"], jogada["coluna"]), [(5, 3), (5, 6)])
        self.assertIn("ALVO TRAVADO", jogada["analise"]["status_ia"])


if __name__ == "__main__":
    unittest.main()
