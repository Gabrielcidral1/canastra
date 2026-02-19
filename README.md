# Canastra Brasileiro

Jogo de Canastra brasileiro implementado em Python com interface Streamlit.

## Como Executar

```bash
python main.py
```

Ou diretamente com Streamlit:

```bash
streamlit run app.py
```

## Regras do Jogo

### Definições

- **JOGOS**: Formados por 3 ou mais cartas do mesmo naipe em sequência (o Ás pode estar antes do 2 ou depois do K).
- **TRINCA/LAVADEIRA**: Formados por 3 ou mais cartas do mesmo número (o curinga pode ser utilizado).
- **CURINGA**: A carta número 2 substitui qualquer outra carta. Cada jogo aceita apenas um curinga.
- **MONTE**: Pilha de cartas que sobraram após serem distribuídas.
- **MORTO**: Duas pilhas de 11 cartas, uma por time, concedida ao jogador que acabar com as cartas da mão.
- **LIXO**: Cartas descartadas, todas visíveis.
- **CANASTRA**: Jogo de 7+ cartas:
  - **Limpa**: Sem curinga
  - **Suja**: Com curinga

### Ações

- **COMPRAR**: Comprar 1 carta do Monte ou todas do Lixo
- **BAIXAR JOGO**: Baixar um jogo na mesa
- **BATER**: Quando acabam as cartas da mão:
  - **Direta**: Última carta baixada, recebe o morto
  - **Indireta**: Última carta descartada, usa morto na próxima rodada
  - **Final**: Encerra a partida (precisa de canastra suja)

### Pontuação

- Batida Final: +100 pontos
- Pontos por carta: 10 pontos
- Canastra Suja: +100 pontos
- Canastra Limpa: +200 pontos
- Não pegar o morto: -100 pontos
- Cartas da mão: pontos negativos

## Interface

A interface Streamlit permite:
- Ver sua mão e selecionar cartas
- Comprar do monte ou lixo
- Baixar sequências ou trincas
- Adicionar cartas a jogos existentes
- Descartar cartas
- Ver log do jogo e status dos outros jogadores

## Estrutura do Projeto

```
canastra/
├── __init__.py              # Inicialização do pacote
├── card.py                  # Representação de cartas
├── game.py                  # Regras e validação de jogos
├── engine.py                # Engine do jogo
├── app.py                   # Interface Streamlit
├── main.py                  # Ponto de entrada
└── README.md                # Este arquivo
```
