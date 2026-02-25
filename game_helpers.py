"""Game logic helper functions for Canastra."""

import random
from itertools import combinations
from typing import Optional

from card import Card, Rank, Suit
from engine import Engine, TurnPhase
from game import can_form_sequence, can_form_triple

# In-game AI (opponents + partner): minimal rollouts for speed
AI_TURN_ROLLOUTS = 4
AI_TURN_ROLLOUT_MAX_STEPS = 5
# "Sugestão do bot" button: stronger and more expensive
ISMCTS_COUNTERFACTUAL_ROLLOUTS = 48
COUNTERFACTUAL_ROLLOUT_MAX_STEPS = 20
# Shared rollout / abstraction
ROLLOUT_MAX_STEPS = 15  # default for rollouts
ABSTR_MAX_ADD_TO_GAME = 3  # max "add to game" actions in abstract set
ABSTR_MAX_DISCARD = 6  # max discard options in abstract set
# In rollouts, opponent takes discard when they can use it (model learns not to feed them)
ROLLOUT_OPPONENT_TAKE_USEFUL_DISCARD_PROB = 0.6
# Bias our team in rollouts to take the discard when we can use it (more realistic sim)
ROLLOUT_OUR_TAKE_USEFUL_DISCARD_PROB = 0.6
# Penalty (in score units) for choosing a "dangerous" discard when alternatives are similar
DISCARD_DANGER_PENALTY = 50.0


def _create_full_deck():
    """Return a full Canastra deck (2 decks + 4 jokers) as list of Card."""
    deck = []
    for _ in range(4):
        deck.append(Card(Rank.JOKER))
    ranks = [r for r in Rank if r != Rank.JOKER]
    suits = [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]
    for _ in range(2):
        for rank in ranks:
            for suit in suits:
                deck.append(Card(rank, suit))
    return deck


def _visible_cards_multiset(engine: Engine, observer_index: int) -> list[tuple]:
    """All cards visible to observer: their hand, discard, all melds. As (rank, suit)."""
    out = []
    obs = engine.players[observer_index]
    for c in obs.hand:
        out.append((c.rank, c.suit))
    for c in engine.discard_pile:
        out.append((c.rank, c.suit))
    for p in engine.players:
        for g in p.games:
            for c in g.cards:
                out.append((c.rank, c.suit))
    return out


def _unknown_cards(engine: Engine, observer_index: int) -> list[Card]:
    """Cards not visible to observer (stock + opponents' hands). One copy per card."""
    full = _create_full_deck()
    visible = _visible_cards_multiset(engine, observer_index)
    # Remove one copy per visible (rank, suit)
    for r, s in visible:
        for i, c in enumerate(full):
            if c.rank == r and c.suit == s:
                full.pop(i)
                break
    return full


def _determinize(engine: Engine, observer_index: int, rng: random.Random) -> Engine:
    """Clone engine and assign unknown cards to stock and opponent hands."""
    clone = engine.copy()
    unknown = _unknown_cards(clone, observer_index)
    rng.shuffle(unknown)
    idx = 0
    # Refill stock
    n_stock = len(clone.stock)
    clone.stock = []
    for _ in range(n_stock):
        if idx < len(unknown):
            clone.stock.append(unknown[idx])
            idx += 1
    # Refill each opponent's hand
    obs_team = clone.players[observer_index].team
    for i, p in enumerate(clone.players):
        if i == observer_index:
            continue
        if p.team == obs_team:
            continue
        n_hand = len(p.hand)
        p.hand = []
        for _ in range(n_hand):
            if idx < len(unknown):
                p.hand.append(unknown[idx])
                idx += 1
    return clone


def _get_legal_actions(engine: Engine) -> list[tuple]:
    """Enumerate legal actions for current player. Each action is a tuple to pass to _apply_action."""
    player = engine.get_current_player()
    actions = []

    if engine.turn_phase == TurnPhase.DRAW:
        if engine.stock:
            actions.append(("draw_stock",))
        if engine.discard_pile:
            actions.append(("draw_discard",))
        return actions if actions else []

    if engine.turn_phase == TurnPhase.LAY_DOWN:
        team_players = [p for p in engine.players if p.team == player.team]
        for card in list(player.hand):
            for p in team_players:
                for gi, game in enumerate(p.games):
                    if game.can_add(card):
                        owner_idx = engine.players.index(p)
                        actions.append(
                            ("add_to_game", owner_idx, gi, card.rank, card.suit)
                        )

        game_result = find_valid_game(player, player.hand)
        if game_result:
            gt, suit, cards = game_result
            if gt == "sequence":
                actions.append(("lay_sequence", suit, [(c.rank, c.suit) for c in cards]))
            else:
                actions.append(("lay_triple", [(c.rank, c.suit) for c in cards]))

        actions.append(("end_lay_down",))
        return actions

    if engine.turn_phase == TurnPhase.DISCARD:
        for i, c in enumerate(player.hand):
            actions.append(("discard", i))
        return actions

    return []


def _get_abstract_actions(
    engine: Engine,
    rng: random.Random,
    max_add_to_game: int = ABSTR_MAX_ADD_TO_GAME,
    max_discard: int = ABSTR_MAX_DISCARD,
) -> list[tuple]:
    """Small set of actions (abstraction) so we don't expand every meld arrangement."""
    player = engine.get_current_player()
    actions = []

    if engine.turn_phase == TurnPhase.DRAW:
        if engine.stock:
            actions.append(("draw_stock",))
        if engine.discard_pile:
            actions.append(("draw_discard",))
        return actions

    if engine.turn_phase == TurnPhase.LAY_DOWN:
        team_players = [p for p in engine.players if p.team == player.team]
        add_actions = []
        for card in list(player.hand):
            for p in team_players:
                for gi, game in enumerate(p.games):
                    if game.can_add(card):
                        add_actions.append(
                            (
                                "add_to_game",
                                engine.players.index(p),
                                gi,
                                card.rank,
                                card.suit,
                            )
                        )
                        break
        if len(add_actions) > max_add_to_game:
            add_actions = list(rng.sample(add_actions, max_add_to_game))
        actions.extend(add_actions)

        game_result = find_valid_game(player, player.hand)
        if game_result:
            gt, suit, cards = game_result
            if gt == "sequence":
                actions.append(
                    ("lay_sequence", suit, [(c.rank, c.suit) for c in cards])
                )
            else:
                actions.append(("lay_triple", [(c.rank, c.suit) for c in cards]))
        actions.append(("end_lay_down",))
        return actions

    if engine.turn_phase == TurnPhase.DISCARD:
        for i in range(len(player.hand)):
            actions.append(("discard", i))
        if len(actions) > max_discard:
            actions = list(rng.sample(actions, max_discard))
        return actions

    return []


def _apply_action(engine: Engine, action: tuple) -> bool:
    """Apply one action to engine. Returns True if successful."""
    player = engine.get_current_player()
    kind = action[0]
    if kind == "draw_stock":
        err = engine.draw_from_stock()
        return err is None
    if kind == "draw_discard":
        err = engine.draw_from_discard()
        return err is None
    if kind == "end_lay_down":
        engine.end_lay_down_phase()
        return True
    if kind == "lay_sequence":
        _, suit, card_tuples = action
        remaining = list(player.hand)
        cards = []
        for r, s in card_tuples:
            c = next((x for x in remaining if x.rank == r and x.suit == s), None)
            if c is None:
                return False
            cards.append(c)
            remaining.remove(c)
        err = engine.lay_down_sequence(suit, cards)
        return err is None
    if kind == "lay_triple":
        _, card_tuples = action
        remaining = list(player.hand)
        cards = []
        for r, s in card_tuples:
            c = next((x for x in remaining if x.rank == r and x.suit == s), None)
            if c is None:
                return False
            cards.append(c)
            remaining.remove(c)
        err = engine.lay_down_triple(cards)
        return err is None
    if kind == "add_to_game":
        _, owner_idx, game_idx, rank, suit = action
        card = next((c for c in player.hand if c.rank == rank and c.suit == suit), None)
        if card is None:
            return False
        target = engine.players[owner_idx]
        err = engine.add_to_game(game_idx, card, target_player=target)
        return err is None
    if kind == "discard":
        _, hand_idx = action
        if hand_idx >= len(player.hand):
            return False
        card = player.hand[hand_idx]
        err = engine.discard(card)
        return err is None
    return False


def _current_player_can_use_discard_top(engine: Engine) -> bool:
    """True if in DRAW phase, discard pile has a card, and current player can
    add that card to one of their melds (so taking the pile is useful)."""
    if engine.turn_phase != TurnPhase.DRAW or not engine.discard_pile:
        return False
    top_card = engine.discard_pile[-1]
    player = engine.get_current_player()
    return any(game.can_add(top_card) for game in player.games)


def _discard_danger(engine: Engine, action: tuple) -> float:
    """Return a danger score for a discard action (0 = safe, 1 = very bad).
    Used to avoid blunders: don't feed jokers or pile-top matches to next player;
    don't discard a card we could add to our team's melds."""
    if not action or action[0] != "discard":
        return 0.0
    player = engine.get_current_player()
    hand_idx = action[1]
    if hand_idx >= len(player.hand):
        return 0.0
    card = player.hand[hand_idx]
    danger = 0.0
    # Blunder: discarding a card we could add to one of our melds (e.g. 5♣ when we have 6♣-7♣)
    team_players = [p for p in engine.players if p.team == player.team]
    for p in team_players:
        for game in p.games:
            if game.can_add(card):
                danger = max(danger, 0.9)
                break
    if card.rank == Rank.JOKER:
        danger = 1.0  # joker is very useful to anyone
    elif engine.discard_pile:
        top = engine.discard_pile[-1]
        if top.rank == card.rank or (top.rank == Rank.JOKER and card.rank == Rank.TWO):
            danger = max(danger, 0.5)  # same rank on pile: next player may take pile and use it
    return danger


def _is_early_game(engine: Engine) -> bool:
    """True when there are still many cards in the stock (opening phase)."""
    return len(engine.stock) > 40


def _early_trinca_penalty(engine: Engine, action: tuple) -> float:
    """Penalty for choosing lay_triple in early game (trincas are rarely good early, especially with wildcards).
    Returns a score penalty to subtract (higher = worse action)."""
    if not action or action[0] != "lay_triple":
        return 0.0
    if not _is_early_game(engine):
        return 0.0
    card_tuples = action[1]
    uses_wildcards = any(
        r == Rank.JOKER or r == Rank.TWO for r, _ in card_tuples
    )
    if uses_wildcards:
        return 50.0  # early trinca with jokers/2s is especially bad
    return 25.0  # early trinca without wildcards still discouraged


def _heuristic_state_score(engine: Engine, our_team: int) -> float:
    """Score non-terminal state: team meld value minus team hand value,
    plus small bonus for canastras (encourages building melds)."""
    total = 0.0
    for p in engine.players:
        if p.team == our_team:
            total += p.get_games_value() - p.get_hand_value()
            if p.has_clean_canastra():
                total += 30.0
            if p.has_dirty_canastra():
                total += 15.0
    return total


def _rollout_action_bias(
    engine: Engine, our_team: int, actions: list, rng: random.Random
) -> tuple:
    """Choose an action for rollout: bias both sides to take discard when they
    can use it, so simulations are more realistic and bad discards get punished."""
    player = engine.get_current_player()
    draw_discard = ("draw_discard",)
    if draw_discard not in actions:
        return rng.choice(actions)
    can_use = _current_player_can_use_discard_top(engine)
    if player.team == our_team:
        if can_use and rng.random() < ROLLOUT_OUR_TAKE_USEFUL_DISCARD_PROB:
            return draw_discard
    else:
        if can_use and rng.random() < ROLLOUT_OPPONENT_TAKE_USEFUL_DISCARD_PROB:
            return draw_discard
    return rng.choice(actions)


def _fast_rollout(
    engine: Engine,
    our_team: int,
    rng: random.Random,
    max_steps: int | None = None,
) -> float:
    """Short rollout with heuristic score if not terminal (fast policy).
    Rollout policy biases opponents to take the discard when they can use it,
    so bad discards are punished by the simulation rather than a hard rule."""
    steps = max_steps if max_steps is not None else ROLLOUT_MAX_STEPS
    for _ in range(steps):
        if engine.game_over:
            our_players = [p for p in engine.players if p.team == our_team]
            return float(our_players[0].points) if our_players else 0.0
        actions = _get_abstract_actions(
            engine, rng, max_add_to_game=2, max_discard=4
        )
        if not actions:
            return _heuristic_state_score(engine, our_team)
        action = _rollout_action_bias(engine, our_team, actions, rng)
        _apply_action(engine, action)
    return _heuristic_state_score(engine, our_team)


def _ucb(mean: float, n: int, N: int, c: float = 1.4) -> float:
    """UCB for action selection (progressive widening)."""
    if n == 0:
        return float("inf")
    return mean + c * (float(N + 1) ** 0.5) / (n ** 0.5)


def _is_mcts_choose(
    engine: Engine,
    our_team: int,
    total_rollouts: int,
    rng: random.Random,
    use_abstract_actions: bool = True,
    rollout_max_steps: int | None = None,
    discourage_early_trinca: bool = False,
) -> tuple | None:
    """IS-MCTS with progressive widening: fixed total rollouts, UCB selects which action to try."""
    if use_abstract_actions:
        actions = _get_abstract_actions(engine, rng)
    else:
        actions = _get_legal_actions(engine)
    if not actions:
        return None
    if len(actions) == 1:
        return actions[0]

    steps = rollout_max_steps if rollout_max_steps is not None else ROLLOUT_MAX_STEPS
    scores: list[list[float]] = [[] for _ in range(len(actions))]
    N = 0
    for _ in range(total_rollouts):
        if N < len(actions):
            ai = N % len(actions)
        else:
            means = [
                sum(scores[i]) / len(scores[i]) if scores[i] else 0.0
                for i in range(len(actions))
            ]
            ucb_vals = [
                _ucb(means[i], len(scores[i]), N) for i in range(len(actions))
            ]
            ai = int(max(range(len(actions)), key=lambda i: ucb_vals[i]))
        action = actions[ai]
        clone = _determinize(engine, engine.current_player_index, rng)
        if _apply_action(clone, action):
            s = _fast_rollout(clone, our_team, rng, max_steps=steps)
            scores[ai].append(s)
        N += 1

    # Choose action with best mean score, minus penalties for bad choices
    def effective_mean(i: int) -> float:
        mean_val = sum(scores[i]) / max(1, len(scores[i]))
        penalty = DISCARD_DANGER_PENALTY * _discard_danger(engine, actions[i])
        if discourage_early_trinca:
            penalty += _early_trinca_penalty(engine, actions[i])
        return mean_val - penalty

    best_ai = max(range(len(actions)), key=effective_mean)
    return actions[best_ai]


def detect_game_type(cards):
    """Detect what type of game the selected cards can form.
    Returns: (game_type, suit) where game_type is "sequence", "triple", "both", or None
    """
    if len(cards) < 3:
        return (None, None)

    can_be_triple = can_form_triple(cards)
    valid_sequence_suits = []

    # Check which suits can form a sequence
    for suit in [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]:
        if can_form_sequence(cards, suit):
            valid_sequence_suits.append(suit)

    if can_be_triple and valid_sequence_suits:
        return (
            "both",
            valid_sequence_suits[0] if len(valid_sequence_suits) == 1 else None,
        )
    elif can_be_triple:
        return ("triple", None)
    elif valid_sequence_suits:
        # If only one suit works, return it; otherwise return first
        return ("sequence", valid_sequence_suits[0])
    else:
        return (None, None)


def find_valid_game(player, hand):
    """Try to find a valid game from player's hand."""
    for suit in [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]:
        for i in range(len(hand) - 2):
            for j in range(i + 1, len(hand) - 1):
                for k in range(j + 1, len(hand)):
                    cards = [hand[i], hand[j], hand[k]]
                    if can_form_sequence(cards, suit):
                        return ("sequence", suit, cards)
                    if can_form_triple(cards):
                        return ("triple", None, cards)

    for suit in [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]:
        for combo_size in range(4, min(8, len(hand) + 1)):
            for combo in combinations(hand, combo_size):
                cards = list(combo)
                if can_form_sequence(cards, suit):
                    return ("sequence", suit, cards)
                if can_form_triple(cards):
                    return ("triple", None, cards)
    return None


# Suit symbols for counterfactual description (no UI dependency)
_SUIT_SYMBOLS = {
    Suit.CLUBS: "♣",
    Suit.DIAMONDS: "♦",
    Suit.HEARTS: "♥",
    Suit.SPADES: "♠",
}


def _action_description(engine: Engine, action: tuple) -> str:
    """Return a short Portuguese description of the action for the UI."""
    kind = action[0]
    if kind == "draw_stock":
        return "Comprar do Monte"
    if kind == "draw_discard":
        n = len(engine.discard_pile)
        return f"Comprar do Lixo ({n} cartas)"
    if kind == "end_lay_down":
        return "Terminar fase de baixar"
    if kind == "discard":
        _, hand_idx = action
        player = engine.get_current_player()
        if hand_idx < len(player.hand):
            c = player.hand[hand_idx]
            if c.rank == Rank.JOKER:
                return "Descartar 🃏"
            sym = _SUIT_SYMBOLS.get(c.suit, c.suit.value)
            return f"Descartar {c.rank.value}{sym}"
        return "Descartar carta"
    if kind == "lay_sequence":
        _, suit, _ = action
        sym = _SUIT_SYMBOLS.get(suit, suit.value if hasattr(suit, "value") else "")
        return f"Baixar sequência de {sym}"
    if kind == "lay_triple":
        return "Baixar trinca"
    if kind == "add_to_game":
        _, owner_idx, game_idx, rank, suit = action
        if rank == Rank.JOKER:
            return "Adicionar 🃏 a um jogo"
        sym = _SUIT_SYMBOLS.get(suit, suit.value if hasattr(suit, "value") else "")
        return f"Adicionar {rank.value}{sym} a um jogo"
    return ""


def get_counterfactual_action(engine: Engine) -> tuple[tuple | None, str]:
    """What the bot would play in the current state. Returns (action, description).
    Use when it is the human's turn to show a counterfactual suggestion.
    Uses full legal actions and more rollouts for a stronger, more expensive suggestion."""
    if engine.game_over:
        return (None, "")
    player = engine.get_current_player()
    if not player.is_human:
        return (None, "")
    rng = random.Random()
    best = _is_mcts_choose(
        engine,
        player.team,
        ISMCTS_COUNTERFACTUAL_ROLLOUTS,
        rng,
        use_abstract_actions=False,
        rollout_max_steps=COUNTERFACTUAL_ROLLOUT_MAX_STEPS,
    )
    if best is None:
        return (None, "")
    return (best, _action_description(engine, best))


def play_ai_turn(
    engine: Engine,
    rollouts: Optional[int] = None,
    rollout_max_steps: Optional[int] = None,
    discourage_early_trinca: bool = False,
) -> None:
    """Play one turn for the current AI player.

    Uses module constants AI_TURN_ROLLOUTS and AI_TURN_ROLLOUT_MAX_STEPS by default.
    Pass rollouts/rollout_max_steps for config (e.g. control vs challenger).
    Pass discourage_early_trinca=True to prefer sequences over trincas early and avoid using jokers in trincas early.
    """
    player = engine.get_current_player()
    rng = random.Random()
    n_rollouts = rollouts if rollouts is not None else AI_TURN_ROLLOUTS
    n_steps = rollout_max_steps if rollout_max_steps is not None else AI_TURN_ROLLOUT_MAX_STEPS
    best = _is_mcts_choose(
        engine,
        player.team,
        n_rollouts,
        rng,
        use_abstract_actions=True,
        rollout_max_steps=n_steps,
        discourage_early_trinca=discourage_early_trinca,
    )
    if best is not None:
        _apply_action(engine, best)
        return
    if (
        engine.turn_phase == TurnPhase.DRAW
        and not engine.stock
        and not engine.discard_pile
    ):
        engine.game_over = True
        engine._calculate_final_points()


def organize_hand(hand):
    """Organize hand by suit with jokers in gaps."""
    # Ace high for display ordering (A after K)
    rank_order = {
        Rank.TWO: 2,
        Rank.THREE: 3,
        Rank.FOUR: 4,
        Rank.FIVE: 5,
        Rank.SIX: 6,
        Rank.SEVEN: 7,
        Rank.EIGHT: 8,
        Rank.NINE: 9,
        Rank.TEN: 10,
        Rank.JACK: 11,
        Rank.QUEEN: 12,
        Rank.KING: 13,
        Rank.ACE: 14,
    }

    jokers = [c for c in hand if c.rank == Rank.JOKER]
    non_jokers = [c for c in hand if c.rank != Rank.JOKER]

    organized_hand = []
    for suit in [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]:
        suit_cards = [c for c in non_jokers if c.suit == suit]
        suit_cards.sort(key=lambda c: rank_order.get(c.rank, 14))

        if suit_cards and jokers:
            ranks = [rank_order.get(c.rank, 14) for c in suit_cards]
            for joker in jokers[:]:
                placed = False
                for i in range(len(ranks) - 1):
                    if ranks[i + 1] - ranks[i] > 1:
                        suit_cards.insert(i + 1, joker)
                        ranks.insert(i + 1, ranks[i] + 0.5)
                        jokers.remove(joker)
                        placed = True
                        break
                if not placed:
                    break

        organized_hand.extend(suit_cards)

    organized_hand.extend(jokers)
    return organized_hand
