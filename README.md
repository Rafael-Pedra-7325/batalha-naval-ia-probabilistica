# ⚓ Batalha Naval — IA de Mapa de Calor (Inferência Probabilística)

Implementação moderna do clássico **Batalha Naval (10x10)** onde a Inteligência Artificial não utiliza regras fixas simples, mas sim um motor de **Densidade de Probabilidade (Inferência Bayesiana)** que recalcula a cada turno todas as configurações possíveis para os navios restantes.

## 🧠 Como a IA Funciona

1. **Varredura Probabilística (Modo Patrulha):** Quando não há impactos ativos, a IA simula todas as posições horizontais e verticais válidas para cada navio ainda não afundado e soma a frequência de ocupação de cada célula. Naturalmente, o centro do tabuleiro e áreas abertas concentram maior densidade.
2. **Caça Ativa & Alvo Travado (Inferência de Alinhamento):** Ao acertar uma embarcação (`acerto`), a IA descarta configurações que não explicam o impacto e aplica pesos exponenciais às posições que atravessam os acertos ativos. Com dois acertos alinhados, a IA deduz automaticamente a orientação (horizontal ou vertical) do navio.
3. **Modo Raio-X em Tempo Real:** A interface permite visualizar o **Mapa de Calor** da IA diretamente sobre a sua frota, exibindo o gradiente térmico e a porcentagem exata de probabilidade calculada para cada coordenada.

## 🚀 Executando Localmente

```bash
# 1. Crie e ative um ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Inicie a aplicação web
python app.py
