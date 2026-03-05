"""Centralized constants: enums, AI config, game rules, and UI/engine text.

Enums and value classes live here to distinguish uses and avoid
hard-coded strings/numbers in the middle of logic.
"""

from enum import Enum

# -----------------------------------------------------------------------------
# Game rules (engine + game logic)
# -----------------------------------------------------------------------------


class GameRules:
    """Canastra game rule constants (players, hand size, scoring)."""

    NUM_PLAYERS = 4
    INITIAL_HAND_SIZE = 11
    MORTO_SIZE = 11
    FINAL_KNOCK_BONUS = 100
    DEAD_HAND_PENALTY = 100
    MIN_MELD_CARDS = 3
    MIN_NATURAL_CARDS = 2
    CANASTRA_MIN_CARDS = 7
    CLEAN_CANASTRA_POINTS = 200
    DIRTY_CANASTRA_POINTS = 100


# -----------------------------------------------------------------------------
# Turn / game phase and knock enums (used by engine and UI)
# -----------------------------------------------------------------------------


class TurnPhase(Enum):
    """Phase of the current player's turn."""

    DRAW = "comprar"
    LAY_DOWN = "baixar"
    DISCARD = "descartar"
    ENDED = "terminado"


class KnockType(Enum):
    """Type of knock (emptying hand)."""

    DIRECT = "direta"
    INDIRECT = "indireta"
    FINAL = "final"


class GameType(Enum):
    """Type of meld (sequence or triple)."""

    SEQUENCE = "sequencia"
    TRIPLE = "trinca"


# -----------------------------------------------------------------------------
# AI / MCTS config (used by game_helpers and benchmark_bot)
# -----------------------------------------------------------------------------


class AIConfig:
    """Constants for in-game AI and counterfactual suggestion."""

    # In-game AI (opponents + partner): minimal rollouts for speed
    AI_TURN_ROLLOUTS = 4
    AI_TURN_ROLLOUT_MAX_STEPS = 5
    # "Sugestão do bot" button: stronger and more expensive
    ISMCTS_COUNTERFACTUAL_ROLLOUTS = 48
    COUNTERFACTUAL_ROLLOUT_MAX_STEPS = 20
    # Shared rollout / abstraction
    ROLLOUT_MAX_STEPS = 15
    ABSTR_MAX_ADD_TO_GAME = 3
    ABSTR_MAX_DISCARD = 6
    # In rollouts, opponent takes discard when they can use it
    ROLLOUT_OPPONENT_TAKE_USEFUL_DISCARD_PROB = 0.6
    # Bias our team in rollouts to take the discard when we can use it
    ROLLOUT_OUR_TAKE_USEFUL_DISCARD_PROB = 0.6
    # Penalty for "dangerous" discard when alternatives are similar
    DISCARD_DANGER_PENALTY = 50.0

    # Early game: stock above this = opening phase (heuristics apply)
    EARLY_GAME_STOCK_THRESHOLD = 40
    # Fast rollout uses smaller abstraction
    ROLLOUT_ABSTRACT_ADD = 2
    ROLLOUT_ABSTRACT_DISCARD = 4
    # UCB exploration constant
    UCB_C = 1.4

    # Early-game action heuristic (positive = good)
    EARLY_DRAW_STOCK_BONUS = 12.0
    EARLY_DRAW_DISCARD_USE_BONUS = 25.0
    EARLY_DRAW_DISCARD_NO_USE_PENALTY = -10.0
    EARLY_ADD_TO_GAME_BONUS = 18.0
    EARLY_LAY_SEQUENCE_BONUS = 15.0
    EARLY_END_LAY_DOWN_PENALTY = -12.0

    # Discard connector/isolated heuristic (positive = good to discard)
    CONNECTOR_DISCARD_PENALTY = -12.0
    ISOLATED_DISCARD_BONUS = 12.0
    JOKER_DISCARD_PENALTY = -15.0
    TWO_DISCARD_PENALTY = -25.0
    LOW_CARD_DISCARD_BONUS = 5.0
    # Penalty for discarding a card that is part of a potential meld in hand
    # (same suit with 3+ cards, or same rank with 2+ cards)
    DISCARD_USEFUL_IN_HAND_PENALTY = 22.0
    # Bonus for discarding a duplicate (we have 2+ of same rank+suit); keep one
    DISCARD_DUPLICATE_BONUS = 18.0
    # Bonus for discarding the only card of that suit in hand (no sequence
    # potential in that suit)
    DISCARD_SINGLETON_SUIT_BONUS = 16.0
    # Prefer discarding a card that is "far" in rank from other same-suit cards
    # (e.g. A♣ when we have 3,6,9♣—9 is too far to connect). Negative = penalty
    # for discarding a card "close" to another (e.g. K♠ next to J♠—keep for run).
    DISCARD_FAR_IN_SUIT_BONUS = 14.0
    DISCARD_ADJACENT_IN_SUIT_PENALTY = 15.0

    # Early triple penalty (subtracted from score)
    EARLY_TRIPLE_WILD_PENALTY = 50.0
    EARLY_TRIPLE_NATURAL_PENALTY = 25.0

    # Heuristic state score bonuses for canastras
    CLEAN_CANASTRA_BONUS = 30.0
    DIRTY_CANASTRA_BONUS = 15.0

    # find_valid_game: meld size range
    MIN_MELD_SIZE = 3
    MAX_MELD_SIZE = 8

    # Display index for joker (not in sequence order)
    JOKER_DISPLAY_INDEX = 99


# -----------------------------------------------------------------------------
# Action kind strings (first element of action tuples in game_helpers)
# -----------------------------------------------------------------------------


class ActionKind:
    """First element of legal action tuples."""

    DRAW_STOCK = "draw_stock"
    DRAW_DISCARD = "draw_discard"
    END_LAY_DOWN = "end_lay_down"
    DISCARD = "discard"
    LAY_SEQUENCE = "lay_sequence"
    LAY_TRIPLE = "lay_triple"
    ADD_TO_GAME = "add_to_game"


# -----------------------------------------------------------------------------
# Game type strings (detect_game_type / find_valid_game return values)
# -----------------------------------------------------------------------------


class GameTypeStr:
    """String identifiers for game type in helpers (not the GameType enum)."""

    SEQUENCE = "sequence"
    TRIPLE = "triple"
    BOTH = "both"


# -----------------------------------------------------------------------------
# Bot suggestion descriptions (Portuguese, for _action_description)
# -----------------------------------------------------------------------------


class ActionDescriptions:
    """Short Portuguese descriptions for the "Sugestão do bot" UI."""

    DRAW_STOCK = "Comprar do Monte"
    DRAW_DISCARD_N = "Comprar do Lixo ({n} cartas)"
    END_LAY_DOWN_PHASE = "Terminar fase de baixar"
    DISCARD_JOKER = "Descartar 🃏"
    DISCARD_CARD = "Descartar carta"
    LAY_SEQUENCE_OF = "Baixar sequência de {sym}"
    LAY_TRIPLE = "Baixar trinca"
    ADD_JOKER_TO_GAME = "Adicionar 🃏 a um jogo"
    ADD_CARD_TO_GAME = "Adicionar {rank}{sym} a um jogo"


# -----------------------------------------------------------------------------
# Engine log messages (game log / history)
# -----------------------------------------------------------------------------


class EngineLog:
    """Templates for engine game log messages (Portuguese)."""

    GAME_STARTED = "{display_name} começa o jogo"
    DREW_FROM_STOCK = "{display_name} comprou do monte"
    DREW_FROM_DISCARD = "{display_name} comprou do lixo"
    CARD_NOT_IN_HAND = "Carta {card} não está na mão"
    LAID_DOWN_SEQUENCE = "{display_name} baixou sequência de {suit} com {n} cartas"
    LAID_DOWN_TRIPLE = "{display_name} baixou trinca com {n} cartas"
    ADDED_TO_GAME = "{player_display} adicionou {card} ao jogo {game_idx}"
    ADDED_TO_GAME_OF = (
        "{player_display} adicionou {card} ao jogo {game_idx} de {target_display}"
    )
    DISCARDED = "{display_name} descartou {card}"
    DIRECT_KNOCK = "{display_name} bateu DIRETA e pegou o morto"
    INDIRECT_KNOCK = "{display_name} bateu INDIRETA"
    PICKED_UP_DEAD_HAND = "{display_name} pegou o morto"
    TURN_OF = "Vez de {display_name}"
    POINTS_COUNT_HEADER = "=== CONTAGEM DE PONTOS ==="
    TEAM_FINAL_KNOCK_BONUS = "Time {team}: +100 pontos (Batida Final)"
    GAMES_AND_HAND = "{player_name}: Jogos {games_points}, Mão -{hand_points}"
    TEAM_NO_DEAD_HAND_PENALTY = "Time {team}: -100 pontos (Não pegou o morto)"
    TEAM_TOTAL_POINTS = "Time {team} total: {points} pontos"


class GameMode:
    """Game mode: 1v1 (2 players) or doubles (4 players)."""

    ONE_VS_ONE = "1v1"
    DOUBLES = "doubles"

    @classmethod
    def num_players(cls, mode: str) -> int:
        return 2 if mode == cls.ONE_VS_ONE else 4


class DisplayNameTemplates:
    """Templates for player display names in log and UI."""

    PLAYER_N = "Jogador {n}"
    OPPONENT_N = "Oponente {n}"
    OPPONENT = "Oponente"  # single opponent in 1v1


# -----------------------------------------------------------------------------
# Engine error messages (returned by engine methods)
# -----------------------------------------------------------------------------


class EngineErrors:
    """User-facing error strings returned by engine."""

    DRAW_ONLY_IN_DRAW_PHASE = "Só é possível comprar na fase de compra"
    DISCARD_PILE_EMPTY = "Lixo está vazio"
    LAY_DOWN_ONLY_IN_LAY_PHASE = "Só é possível baixar jogos na fase de baixar"
    ADD_ONLY_IN_LAY_PHASE = "Só é possível adicionar cartas na fase de baixar"
    ADD_ONLY_OWN_TEAM = "Só é possível adicionar cartas aos jogos do seu time"
    INVALID_GAME_INDEX = "Índice de jogo inválido"
    DISCARD_ONLY_IN_DISCARD_PHASE = "Só é possível descartar na fase de descartar"
    FINISH_NEEDS_CLEAN_CANASTRA = (
        "Só é possível encerrar o jogo (bater) com canastra limpa "
        "(7+ cartas do mesmo naipe sem curingas)."
    )


# -----------------------------------------------------------------------------
# Game validation messages (game.py – ValueError messages)
# -----------------------------------------------------------------------------


class GameValidation:
    """Validation error messages for Game (sequence/triple rules)."""

    GAME_MIN_CARDS = "Game must have at least 3 cards"
    SEQUENCE_NEEDS_SUIT = "Sequence needs a suit"
    ONLY_ONE_WILDCARD = "Only one wildcard per game"
    SEQUENCE_NEEDS_TWO_NATURAL = (
        "Sequence needs at least 2 natural cards of the same suit"
    )
    SEQUENCE_SAME_SUIT = "All cards in sequence must be of the same suit"
    SEQUENCE_NO_DUPLICATES = "Sequência não pode ter cartas repetidas do mesmo naipe"
    SEQUENCE_WILDCARD_NEEDS_TWO = (
        "Sequence with wildcard needs at least 2 natural cards"
    )
    WILDCARD_ONE_GAP = "Wildcard cannot fill more than one gap"
    CARDS_NOT_VALID_SEQUENCE = "Cards do not form a valid sequence"
    TRIPLE_SAME_NUMBER = "Triple must have cards of the same number"
    TRIPLE_TWO_NATURAL = "Triple needs at least 2 natural cards of the same number"
    TRIPLE_ONLY_ACE_THREE_KING = "Trincas só podem ser feitas com Ás, 3 ou Rei"
    CANNOT_ADD_CARD_TO_GAME = "Não é possível adicionar {card} a este jogo"


# -----------------------------------------------------------------------------
# UI text (app.py and related) – Portuguese strings
# -----------------------------------------------------------------------------


class AppConfig:
    """App-level constants (Streamlit UI behavior)."""

    LAST_LOG_MESSAGES = 10
    NEXT_PLAYER_DELAY_SEC = 2


class UIText:
    """User-facing strings for the Streamlit UI."""

    class Sidebar:
        TITLE = "## 🎴 Canastra"
        BOT_DIFFICULTY_LABEL = "Dificuldade dos bots"
        BOT_DIFFICULTY_EASY = "Fácil"
        BOT_DIFFICULTY_MEDIUM = "Médio"
        BOT_DIFFICULTY_HARD = "Difícil"
        SCORE_HEADER = "📊 Placar"
        POINTS_SUFFIX = " pontos"
        INFO_HEADER = "ℹ️ Informações"
        CURRENT_PLAYER_LABEL = "**Jogador Atual**: "
        PHASE_LABEL = "**Fase**: "
        STOCK_LABEL = "**Monte**: "
        DISCARD_LABEL = "**Lixo**: "
        CARDS_SUFFIX = " cartas"
        LOG_HEADER = "📝 Log do Jogo"
        RULES_EXPANDER = "📖 Regras do Jogo"

    class GameOver:
        TIE = "Empate! Nós {our_pts} x Eles {other_pts} pontos."
        WON = "🎉 Time {winner_name} venceu com {points} pontos!"
        GAME_OVER_PREFIX = "**Jogo encerrado.** "

    class Teams:
        US = "Nós"
        THEM = "Eles"

    class LayDown:
        TITLE = "#### Baixar Novo Jogo"
        INVALID_CARDS = "⚠️ As cartas selecionadas não formam um jogo válido"
        GAME_TYPE_LABEL = "Tipo de jogo:"
        OPTION_SEQUENCE = "Sequência"
        OPTION_TRIPLE = "Trinca"
        SUIT_LABEL = "Naipe:"
        BUTTON_SEQUENCE = "Baixar Sequência"
        BUTTON_TRIPLE = "Baixar Trinca"
        INVALID_SEQUENCE = "Cartas não formam uma sequência válida"
        INVALID_TRIPLE = "Cartas não formam uma trinca válida"
        SELECTED_HEADING = "**Cartas selecionadas**"
        ONE_SELECTED = "**{n} carta selecionada:**"
        N_SELECTED = "**{n} cartas selecionadas:**"
        HINT_SELECT = (
            "💡 Clique nas cartas da sua mão para selecioná-las e baixar um jogo"
        )
        HINT_FINISH = (
            "💡 Você pode baixar mais jogos ou terminar a fase quando terminar."
        )
        BUTTON_END_PHASE = "✅ Terminar Fase de Baixar"
        ADD_TO_GAME_HEADING = "#### Adicionar a um jogo do time"
        CARD_CANNOT_ADD = "Esta carta não pode ser adicionada a nenhum jogo do time."
        CLICK_GAME_TO_ADD = "Clique no jogo ao qual deseja adicionar a carta:"
        ADD_BUTTON_PREFIX = "➕ Adicionar à "

    class Discard:
        PROMPT = "**Selecione uma carta para descartar:**"
        BUTTON_PREFIX = "🗑️ Descartar "
        HINT = "Selecione uma carta para descartar"

    class ModeSelection:
        TITLE = "Modo de jogo"
        ONE_VS_ONE = "1 vs 1 (2 jogadores)"
        DOUBLES = "Duplas (4 jogadores)"
        BUTTON_START = "Iniciar jogo"

    class Actions:
        DRAW_STOCK = "🃏 Comprar do Monte"
        DRAW_DISCARD = "🗑️ Comprar do Lixo ({n} cartas)"
        CONFIRM_NEW_GAME = "Tem certeza? O jogo atual será perdido."
        BUTTON_NEW_GAME_YES = "Sim, novo jogo"
        BUTTON_CANCEL = "Cancelar"
        BUTTON_NEW_GAME = "🔄 Novo Jogo"
        NEW_GAME_HELP = "Iniciar um novo jogo (o atual será perdido)."
        BOT_SUGGESTION = "🤖 Sugestão do bot"
        BOT_SUGGESTION_HELP = (
            "Calcula o que o bot jogaria (pode demorar alguns segundos)."
        )
        BOT_WOULD_PLAY = "🤖 O bot jogaria: **{desc}**"
        SPINNER = "Calculando..."
        ACTIONS_HEADING = "### 🎮 Ações"
        LAST_MOVE = "▶ **Última jogada:** {msg}"
        NEXT_PLAYER_SOON = "⏳ Próximo jogador em 2 segundos..."
        NEXT_PLAYER_SOON_BRIEF = "⏳ Próximo jogador..."

    class Hand:
        HEADING = "### 👤 Sua Mão"
        EMPTY = "Mão vazia"

    class Table:
        STOCK_HEADING = "#### 🃏 Monte"
        DISCARD_HEADING = "#### 🗑️ Lixeira"
        EMPTY = "Vazio"
        OUR_MELDS = "#### 🃏 Jogos Baixados (Nós)"
        THEIR_MELDS = "#### 🃏 Jogos Baixados (Eles)"

    class PlayerAreas:
        OPPONENT_1 = "### 👥 Oponente 1"
        OPPONENT_2 = "### 👥 Oponente 2"
        PARTNER = "### 🤝 Parceiro"
        OPPONENT = "### 👤 Oponente"  # 1v1 single opponent

    class DisplayNames:
        YOU = "Você"
        PARTNER = "Parceiro"
        OPPONENT = "Oponente"  # single opponent in 1v1

    @staticmethod
    def game_over_tie(our_pts: int, other_pts: int) -> str:
        return UIText.GameOver.TIE.format(
            our_pts=our_pts,
            other_pts=other_pts,
        )

    @staticmethod
    def game_over_won(winner_name: str, points: int) -> str:
        return UIText.GameOver.WON.format(
            winner_name=winner_name,
            points=points,
        )

    @staticmethod
    def selected_count(n: int) -> str:
        if n == 1:
            return UIText.LayDown.ONE_SELECTED.format(n=n)
        return UIText.LayDown.N_SELECTED.format(n=n)


# -----------------------------------------------------------------------------
# Rules: loaded from rules.md via rules_loader.py
# -----------------------------------------------------------------------------
