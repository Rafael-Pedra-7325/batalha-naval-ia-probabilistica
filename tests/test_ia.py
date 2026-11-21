"""
Testes unitários para as regras de Batalha Naval e para o motor de Mapa de Calor da IA.
"""

import unittest

from ia import IAMapaDeCalor
from jogo import AGUA, NAVIO, NAVIO_AFUNDADO, TIRO_ACERTO, TIRO_AGUA, FROTA_PADRAO, Tabuleiro


class TestBatalhaNavalEIA(unittest.TestCase):
    def test_posicionamento_aleatorio_frota_completa(self):
        tab = Tabuleiro()
        tab.posicionar_aleatorio()
        self.assertEqual(len(tab.navios), len(FROTA_PADRAO))
        total_celulas_navio = sum(
            row.count(NAVIO) for row in tab.grade
        )
        esperado = sum(n["tamanho"] for n in FROTA_PADRAO)
        self.assertEqual(total_celulas_navio, esperado)

    def test_afundamento_e_fim_de_jogo(self):
        tab = Tabuleiro()
        destroier = {"id": "destroier", "nome": "Destróier", "tamanho": 2, "codigo": "DT"}
        self.assertTrue(tab.posicionar_navio(destroier, 0, 0, horizontal=True))

        res1 = tab.receber_tiro(0, 0)
        self.assertTrue(res1["valido"])
        self.assertEqual(res1["resultado"], "acerto")
        self.assertFalse(res1["fim_de_jogo"])

        res2 = tab.receber_tiro(0, 1)
        self.assertTrue(res2["valido"])
        self.assertEqual(res2["resultado"], "afundado")
        self.assertTrue(res2["fim_de_jogo"])
        self.assertEqual(tab.grade[0][0], NAVIO_AFUNDADO)
        self.assertEqual(tab.grade[0][1], NAVIO_AFUNDADO)

    def test_mapa_calor_zera_celulas_ja_atacadas(self):
        ia = IAMapaDeCalor(dificuldade="almirante")
        grade = [[AGUA for _ in range(10)] for _ in range(10)]
        grade[4][4] = TIRO_AGUA
        grade[0][0] = TIRO_ACERTO

        analise = ia.calcular_mapa_calor(grade, [5, 4, 3, 3, 2])
        self.assertEqual(analise["intensidade"][4][4], 0.0)
        self.assertEqual(analise["intensidade"][0][0], 0.0)

    def test_inferencia_caca_ativa_concentra_probabilidade_nos_vizinhos(self):
        ia = IAMapaDeCalor(dificuldade="almirante")
        grade = [[AGUA for _ in range(10)] for _ in range(10)]
        # Simula um acerto isolado no centro (4, 4)
        grade[4][4] = TIRO_ACERTO

        analise = ia.calcular_mapa_calor(grade, [4, 3])
        chances = analise["chances_reais"]

        # Células adjacentes ao impacto devem ter probabilidade muito maior que cantos distantes
        prob_vizinho = chances[4][5]
        prob_canto_distante = chances[0][0]
        self.assertGreater(prob_vizinho, prob_canto_distante * 10)
        self.assertIn("CAÇA ATIVA", analise["status_ia"])

    def test_inferencia_alinhamento_horizontal(self):
        ia = IAMapaDeCalor(dificuldade="almirante")
        grade = [[AGUA for _ in range(10)] for _ in range(10)]
        # Dois acertos consecutivos na horizontal: (5, 4) e (5, 5)
        grade[5][4] = TIRO_ACERTO
        grade[5][5] = TIRO_ACERTO

        jogada = ia.escolher_jogada(grade, [4, 3])
        # A IA deve deduzir o eixo horizontal e atirar em (5, 3) ou (5, 6)
        self.assertIn((jogada["linha"], jogada["coluna"]), [(5, 3), (5, 6)])
        self.assertIn("ALVO TRAVADO", jogada["analise"]["status_ia"])


if __name__ == "__main__":
    unittest.main()
