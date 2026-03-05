"""Game logic helper functions for Canastra."""

import random
from itertools import combinations

from card import (
    RANK_ORDER_SEQUENCE,
    SUIT_SYMBOLS,
    Card,
    Rank,
    Suit,
    create_canastra_deck,
)
from constants import ActionDescriptions, ActionKind, AIConfig, GameTypeStr
from engine import Engine, TurnPhase
from game import can_form_sequence, can_form_triple


def _visible_cards_multiset(engine: Engine, observer_index: int) -> list[tuple]:
    """All cards visible to observer: their hand, discard, all melds.
    As (rank, suit)."""
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
    full = create_canastra_deck()
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


def _collect_add_to_game_actions(engine: Engine, player) -> list[tuple]:
    """All legal add_to_game actions for current player."""
    team_players = engine.get_team_players(player.team)
    out = []
    for card in list(player.hand):
        for p in team_players:
            for gi, game in enumerate(p.games):
                if game.can_add(card):
                    out.append((
                        ActionKind.ADD_TO_GAME, engine.players.index(p), gi,
                        card.rank, card.suit,
                    ))
                    break
    return out


def _actions_draw(engine: Engine) -> list[tuple]:
    """Legal actions in DRAW phase."""
    actions = []
    if engine.stock:
        actions.append((ActionKind.DRAW_STOCK,))
    if engine.discard_pile:
        actions.append((ActionKind.DRAW_DISCARD,))
    return actions


def _actions_lay_down(engine: Engine) -> list[tuple]:
    """Legal actions in LAY_DOWN phase."""
    player = engine.get_current_player()
    actions = _collect_add_to_game_actions(engine, player)
    game_result = find_valid_game(player, player.hand)
    if game_result:
        gt, suit, cards = game_result
        if gt == GameTypeStr.SEQUENCE:
            actions.append(
                (ActionKind.LAY_SEQUENCE, suit, [(c.rank, c.suit) for c in cards])
            )
        else:
            triple_tuples = [(c.rank, c.suit) for c in cards]
            actions.append((ActionKind.LAY_TRIPLE, triple_tuples))
    actions.append((ActionKind.END_LAY_DOWN,))
    return actions


def _actions_discard(engine: Engine) -> list[tuple]:
    """Legal actions in DISCARD phase."""
    player = engine.get_current_player()
    return [(ActionKind.DISCARD, i) for i in range(len(player.hand))]


def _get_legal_actions(engine: Engine) -> list[tuple]:
    """Enumerate legal actions for current player.
    Each action is a tuple to pass to _apply_action."""
    if engine.turn_phase == TurnPhase.DRAW:
        return _actions_draw(engine)
    if engine.turn_phase == TurnPhase.LAY_DOWN:
        return _actions_lay_down(engine)
    if engine.turn_phase == TurnPhase.DISCARD:
        return _actions_discard(engine)
    return []


def _get_abstract_actions(
    engine: Engine,
    rng: random.Random,
    max_add_to_game: int = AIConfig.ABSTR_MAX_ADD_TO_GAME,
    max_discard: int = AIConfig.ABSTR_MAX_DISCARD,
) -> list[tuple]:
    """Small set of actions (abstraction) so we don't expand every meld arrangement."""
    if engine.turn_phase == TurnPhase.DRAW:
        return _actions_draw(engine)
    if engine.turn_phase == TurnPhase.LAY_DOWN:
        player = engine.get_current_player()
        add_actions = _collect_add_to_game_actions(engine, player)
        if len(add_actions) > max_add_to_game:
            add_actions = list(rng.sample(add_actions, max_add_to_game))
        actions = add_actions.copy()
        game_result = find_valid_game(player, player.hand)
        if game_result:
            gt, suit, cards = game_result
            if gt == GameTypeStr.SEQUENCE:
                actions.append((
                    ActionKind.LAY_SEQUENCE, suit, [(c.rank, c.suit) for c in cards],
                ))
            else:
                triple_tuples = [(c.rank, c.suit) for c in cards]
                actions.append((ActionKind.LAY_TRIPLE, triple_tuples))
        actions.append((ActionKind.END_LAY_DOWN,))
        return actions
    if engine.turn_phase == TurnPhase.DISCARD:
        actions = _actions_discard(engine)
        if len(actions) > max_discard:
            actions = list(rng.sample(actions, max_discard))
        return actions
    return []


def _resolve_cards_from_hand(player, card_tuples: list[tuple]) -> list[Card] | None:
    """Resolve (rank, suit) tuples to Card list from player hand.
    Returns None if any missing."""
    remaining = list(player.hand)
    cards = []
    for r, s in card_tuples:
        c = next((x for x in remaining if x.rank == r and x.suit == s), None)
        if c is None:
            return None
        cards.append(c)
        remaining.remove(c)
    return cards


def _apply_action(engine: Engine, action: tuple) -> bool:
    """Apply one action to engine. Returns True if successful."""
    player = engine.get_current_player()
    kind = action[0]

    if kind == ActionKind.DRAW_STOCK:
        return engine.draw_from_stock() is None
    if kind == ActionKind.DRAW_DISCARD:
        return engine.draw_from_discard() is None
    if kind == ActionKind.END_LAY_DOWN:
        engine.end_lay_down_phase()
        return True

    if kind == ActionKind.LAY_SEQUENCE:
        _, suit, card_tuples = action
        cards = _resolve_cards_from_hand(player, card_tuples)
        return cards is not None and engine.lay_down_sequence(suit, cards) is None
    if kind == ActionKind.LAY_TRIPLE:
        _, card_tuples = action
        cards = _resolve_cards_from_hand(player, card_tuples)
        return cards is not None and engine.lay_down_triple(cards) is None

    if kind == ActionKind.ADD_TO_GAME:
        _, owner_idx, game_idx, rank, suit = action
        card = next((c for c in player.hand if c.rank == rank and c.suit == suit), None)
        if card is None:
            return False
        return engine.add_to_game(
            game_idx, card, target_player=engine.players[owner_idx],
        ) is None
    if kind == ActionKind.DISCARD:
        _, hand_idx = action
        if hand_idx >= len(player.hand):
            return False
        return engine.discard(player.hand[hand_idx]) is None
    return False


def _current_player_can_use_discard_top(engine: Engine) -> bool:
    """True if in DRAW phase, discard pile has a card, and current player can
    add that card to one of their melds (so taking the pile is useful)."""
    if engine.turn_phase != TurnPhase.DRAW or not engine.discard_pile:
        return False
    top_card = engine.discard_pile[-1]
    player = engine.get_current_player()
    return any(game.can_add(top_card) for game in player.games)


def _danger_team_can_use(engine: Engine, card: Card) -> float:
    """Danger from discarding a card our team could add to a meld."""
    player = engine.get_current_player()
    team_players = engine.get_team_players(player.team)
    if any(game.can_add(card) for p in team_players for game in p.games):
        return 0.9
    return 0.0


def _danger_pile_match(engine: Engine, card: Card) -> float:
    """Danger from discarding same rank as pile top (next player may take pile)."""
    if not engine.discard_pile:
        return 0.0
    top = engine.discard_pile[-1]
    if top.rank == card.rank or (top.rank == Rank.JOKER and card.rank == Rank.TWO):
        return 0.5
    return 0.0


def _discard_danger(engine: Engine, action: tuple) -> float:
    """Return a danger score for a discard action (0 = safe, 1 = very bad).
    Wildcards (Joker, 2) are always dangerous to discard."""
    if not action or action[0] != ActionKind.DISCARD:
        return 0.0
    player = engine.get_current_player()
    hand_idx = action[1]
    if hand_idx >= len(player.hand):
        return 0.0
    card = player.hand[hand_idx]
    if card.rank == Rank.JOKER:
        return 1.0
    if card.rank == Rank.TWO:
        return 0.85
    return max(
        _danger_team_can_use(engine, card),
        _danger_pile_match(engine, card),
    )


def _is_early_game(engine: Engine) -> bool:
    """True when there are still many cards in the stock (opening phase)."""
    return len(engine.stock) > AIConfig.EARLY_GAME_STOCK_THRESHOLD


def _early_game_action_heuristic(engine: Engine, action: tuple, our_team: int) -> float:
    """Heuristic bonus/penalty for an action in early game (positive = good).
    Used to bias the challenger toward sensible opening play."""
    if not action or not _is_early_game(engine):
        return 0.0
    player = engine.get_current_player()
    if player.team != our_team:
        return 0.0
    kind = action[0]

    if kind == ActionKind.DRAW_STOCK:
        return AIConfig.EARLY_DRAW_STOCK_BONUS
    if kind == ActionKind.DRAW_DISCARD:
        if _current_player_can_use_discard_top(engine):
            return AIConfig.EARLY_DRAW_DISCARD_USE_BONUS
        return AIConfig.EARLY_DRAW_DISCARD_NO_USE_PENALTY

    if kind == ActionKind.ADD_TO_GAME:
        return AIConfig.EARLY_ADD_TO_GAME_BONUS
    if kind == ActionKind.LAY_SEQUENCE:
        return AIConfig.EARLY_LAY_SEQUENCE_BONUS
    if kind == ActionKind.LAY_TRIPLE:
        return 0.0  # trincas handled by _early_trinca_penalty
    if kind == ActionKind.END_LAY_DOWN:
        if _collect_add_to_game_actions(engine, player):
            return AIConfig.EARLY_END_LAY_DOWN_PENALTY
        return 0.0

    if kind == ActionKind.DISCARD:
        # Connector/isolated handled in effective_mean for all discard phases
        return 0.0

    return 0.0


def _discard_useful_card_penalty(engine: Engine, action: tuple) -> float:
    """Penalty for discarding a card that is useful in our hand (potential meld).
    E.g. discarding J♥ when we have 6♥, 9♥, J♥, K♥ (same-suit group) is bad.
    Returns a positive value to subtract from score (higher = worse to discard)."""
    if not action or action[0] != ActionKind.DISCARD:
        return 0.0
    player = engine.get_current_player()
    hand_idx = action[1]
    if hand_idx >= len(player.hand):
        return 0.0
    card = player.hand[hand_idx]
    if card.rank in (Rank.JOKER, Rank.TWO):
        return 0.0  # already handled by _discard_danger / connector heuristic
    hand = player.hand
    same_suit = sum(1 for c in hand if c.suit == card.suit and c.rank != Rank.JOKER)
    same_rank = sum(1 for c in hand if c.rank == card.rank)
    penalty = 0.0
    if same_suit >= 3:
        penalty += AIConfig.DISCARD_USEFUL_IN_HAND_PENALTY
    if same_rank >= 2:
        penalty += AIConfig.DISCARD_USEFUL_IN_HAND_PENALTY
    return penalty


def _discard_duplicate_bonus(engine: Engine, action: tuple) -> float:
    """Bonus for discarding a card we have a duplicate of (same rank and suit).
    No need to keep both—e.g. two 7♣; discard one, keep the other for melds.
    In a 2-deck game we can hold two 8♥, two 7♣, etc. Do NOT give this bonus for
    wildcards (2, Joker)—they are too valuable to discard even when duplicated.
    Positive = good to discard this card."""
    if not action or action[0] != ActionKind.DISCARD:
        return 0.0
    player = engine.get_current_player()
    hand_idx = action[1]
    if hand_idx >= len(player.hand):
        return 0.0
    card = player.hand[hand_idx]
    if card.rank in (Rank.JOKER, Rank.TWO):
        return 0.0
    hand = player.hand
    same_card = sum(
        1 for c in hand
        if c.rank == card.rank and c.suit == card.suit
    )
    if same_card >= 2:
        return AIConfig.DISCARD_DUPLICATE_BONUS
    return 0.0


def _discard_singleton_suit_bonus(engine: Engine, action: tuple) -> float:
    """Bonus for discarding a card that is the only one of its suit in hand.
    E.g. K♦ when we have many spades and only one diamond—discard the diamond,
    keep the spade run potential. Positive = good to discard this card."""
    if not action or action[0] != ActionKind.DISCARD:
        return 0.0
    player = engine.get_current_player()
    hand_idx = action[1]
    if hand_idx >= len(player.hand):
        return 0.0
    card = player.hand[hand_idx]
    if card.rank in (Rank.JOKER, Rank.TWO):
        return 0.0
    hand = player.hand
    same_suit = sum(1 for c in hand if c.suit == card.suit and c.rank != Rank.JOKER)
    if same_suit == 1:
        return AIConfig.DISCARD_SINGLETON_SUIT_BONUS
    return 0.0


def _rank_distance(r1: Rank, r2: Rank) -> int:
    """Distance in sequence order (2..K, A). Joker not in sequence."""
    if r1 == Rank.JOKER or r2 == Rank.JOKER:
        return 99
    if r1 not in RANK_ORDER_SEQUENCE or r2 not in RANK_ORDER_SEQUENCE:
        return 99
    return abs(RANK_ORDER_SEQUENCE.index(r1) - RANK_ORDER_SEQUENCE.index(r2))


def _discard_far_or_adjacent_in_suit_bonus(engine: Engine, action: tuple) -> float:
    """Prefer discarding a card that is far in rank from other same-suit cards
    (e.g. A♣ when we have 3,6,9♣—connecting card 9♣ is too far). Penalize
    discarding a card within 2 steps of another same-suit (e.g. K♠ with J♠—
    keep for run). Positive = good to discard."""
    if not action or action[0] != ActionKind.DISCARD:
        return 0.0
    player = engine.get_current_player()
    hand_idx = action[1]
    if hand_idx >= len(player.hand):
        return 0.0
    card = player.hand[hand_idx]
    if card.rank in (Rank.JOKER, Rank.TWO):
        return 0.0
    hand = player.hand
    same_suit_others = [
        c for i, c in enumerate(hand)
        if i != hand_idx and c.suit == card.suit and c.rank != Rank.JOKER
    ]
    if not same_suit_others:
        return 0.0
    min_dist = min(_rank_distance(card.rank, c.rank) for c in same_suit_others)
    if min_dist >= 3:
        return AIConfig.DISCARD_FAR_IN_SUIT_BONUS
    if min_dist <= 2:
        return -AIConfig.DISCARD_ADJACENT_IN_SUIT_PENALTY
    return 0.0


def _discard_connector_isolated_bonus(engine: Engine, action: tuple) -> float:
    """Heuristic for discard choice: connector ranks (6–10) help opponent melds;
    isolated cards (J,Q,K,A) are safer to discard. Positive = good to discard.
    Connector in a 2-or-fewer suit (e.g. two 7♣—no point keeping both) gets no
    penalty; full penalty only when the card is part of a 3+ same-suit group.
    Duplicate bonus (_discard_duplicate_bonus) is the main reason to prefer
    discarding when we have two of the same card. Overridden by
    _discard_useful_card_penalty when part of a potential meld."""
    if not action or action[0] != ActionKind.DISCARD:
        return 0.0
    player = engine.get_current_player()
    hand_idx = action[1]
    if hand_idx >= len(player.hand):
        return 0.0
    card = player.hand[hand_idx]
    hand = player.hand
    same_suit = sum(1 for c in hand if c.suit == card.suit and c.rank != Rank.JOKER)
    # Connector ranks (6–10): riskier to discard when part of a run (3+ same suit)
    if card.rank in (Rank.SIX, Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN):
        if same_suit >= 3:
            return AIConfig.CONNECTOR_DISCARD_PENALTY
        return 0.0
    # Isolated/safe: J,Q,K,A harder for opponents to use immediately
    if card.rank in (Rank.JACK, Rank.QUEEN, Rank.KING, Rank.ACE):
        return AIConfig.ISOLATED_DISCARD_BONUS
    if card.rank == Rank.JOKER:
        return AIConfig.JOKER_DISCARD_PENALTY
    if card.rank == Rank.TWO:
        return AIConfig.TWO_DISCARD_PENALTY  # wildcard, useful to others
    # Low (3,4,5): slight preference over connectors
    return AIConfig.LOW_CARD_DISCARD_BONUS


def _early_triple_penalty(engine: Engine, action: tuple) -> float:
    """Penalty for choosing lay_triple in early game (triples rarely good
    early, especially with wildcards). Returns a score penalty to subtract
    (higher = worse action)."""
    if not action or action[0] != ActionKind.LAY_TRIPLE:
        return 0.0
    if not _is_early_game(engine):
        return 0.0
    card_tuples = action[1]
    uses_wildcards = any(
        r == Rank.JOKER or r == Rank.TWO for r, _ in card_tuples
    )
    if uses_wildcards:
        return AIConfig.EARLY_TRIPLE_WILD_PENALTY
    return AIConfig.EARLY_TRIPLE_NATURAL_PENALTY


def _heuristic_state_score(engine: Engine, our_team: int) -> float:
    """Score non-terminal state: team meld value minus team hand value,
    plus small bonus for canastras (encourages building melds)."""
    total = 0.0
    for p in engine.players:
        if p.team == our_team:
            total += p.get_games_value() - p.get_hand_value()
            if p.has_clean_canastra():
                total += AIConfig.CLEAN_CANASTRA_BONUS
            if p.has_dirty_canastra():
                total += AIConfig.DIRTY_CANASTRA_BONUS
    return total


def _rollout_action_bias(
    engine: Engine, our_team: int, actions: list, rng: random.Random
) -> tuple:
    """Choose an action for rollout: bias both sides to take discard when they
    can use it, so simulations are more realistic and bad discards get punished."""
    player = engine.get_current_player()
    draw_discard = (ActionKind.DRAW_DISCARD,)
    if draw_discard not in actions:
        return rng.choice(actions)
    can_use = _current_player_can_use_discard_top(engine)
    if player.team == our_team:
        if can_use and rng.random() < AIConfig.ROLLOUT_OUR_TAKE_USEFUL_DISCARD_PROB:
            return draw_discard
    else:
        if can_use and rng.random() < (
            AIConfig.ROLLOUT_OPPONENT_TAKE_USEFUL_DISCARD_PROB
        ):
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
    steps = max_steps if max_steps is not None else AIConfig.ROLLOUT_MAX_STEPS
    for _ in range(steps):
        if engine.game_over:
            our_players = engine.get_team_players(our_team)
            return float(our_players[0].points) if our_players else 0.0
        actions = _get_abstract_actions(
            engine, rng,
            max_add_to_game=AIConfig.ROLLOUT_ABSTRACT_ADD,
            max_discard=AIConfig.ROLLOUT_ABSTRACT_DISCARD,
        )
        if not actions:
            return _heuristic_state_score(engine, our_team)
        action = _rollout_action_bias(engine, our_team, actions, rng)
        _apply_action(engine, action)
    return _heuristic_state_score(engine, our_team)


def _ucb(mean: float, n: int, n_total: int, c: float | None = None) -> float:
    """UCB for action selection (progressive widening)."""
    if n == 0:
        return float("inf")
    c_val = c if c is not None else AIConfig.UCB_C
    return mean + c_val * (float(n_total + 1) ** 0.5) / (n ** 0.5)


def _is_mcts_choose(
    engine: Engine,
    our_team: int,
    total_rollouts: int,
    rng: random.Random,
    use_abstract_actions: bool = True,
    rollout_max_steps: int | None = None,
    discourage_early_triple: bool = True,
    use_early_heuristic: bool = True,
) -> tuple | None:
    """IS-MCTS with progressive widening: fixed total rollouts,
    UCB selects which action to try."""
    if use_abstract_actions:
        actions = _get_abstract_actions(engine, rng)
    else:
        actions = _get_legal_actions(engine)
    if not actions:
        return None
    if len(actions) == 1:
        return actions[0]

    steps = (
        rollout_max_steps if rollout_max_steps is not None
        else AIConfig.ROLLOUT_MAX_STEPS
    )
    scores: list[list[float]] = [[] for _ in range(len(actions))]
    n_total = 0
    for _ in range(total_rollouts):
        if n_total < len(actions):
            ai = n_total % len(actions)
        else:
            means = [
                sum(scores[i]) / len(scores[i]) if scores[i] else 0.0
                for i in range(len(actions))
            ]
            ucb_vals = [
                _ucb(means[i], len(scores[i]), n_total)
                for i in range(len(actions))
            ]
            ai = int(max(range(len(actions)), key=lambda i: ucb_vals[i]))
        action = actions[ai]
        clone = _determinize(engine, engine.current_player_index, rng)
        if _apply_action(clone, action):
            s = _fast_rollout(clone, our_team, rng, max_steps=steps)
            scores[ai].append(s)
        n_total += 1

    # Choose action with best mean score, minus penalties, plus heuristic bonuses
    def effective_mean(i: int) -> float:
        mean_val = sum(scores[i]) / max(1, len(scores[i]))
        penalty = AIConfig.DISCARD_DANGER_PENALTY * _discard_danger(engine, actions[i])
        if discourage_early_triple:
            penalty += _early_triple_penalty(engine, actions[i])
        bonus = (
            _early_game_action_heuristic(engine, actions[i], our_team)
            if use_early_heuristic
            else 0.0
        )
        # Discard heuristics: connector/isolated + useful-in-hand penalty +
        # prefer duplicates
        if use_early_heuristic and actions[i] and actions[i][0] == ActionKind.DISCARD:
            bonus += _discard_connector_isolated_bonus(engine, actions[i])
            penalty += _discard_useful_card_penalty(engine, actions[i])
            bonus += _discard_duplicate_bonus(engine, actions[i])
            bonus += _discard_singleton_suit_bonus(engine, actions[i])
            bonus += _discard_far_or_adjacent_in_suit_bonus(engine, actions[i])
        return mean_val - penalty + bonus

    best_ai = max(range(len(actions)), key=effective_mean)
    return actions[best_ai]


def detect_game_type(cards):
    """Detect what type of game the selected cards can form.
    Returns: (game_type, suit) where game_type is GameTypeStr.SEQUENCE, TRIPLE,
    BOTH, or None.
    """
    if len(cards) < AIConfig.MIN_MELD_SIZE:
        return (None, None)

    can_be_triple = can_form_triple(cards)
    valid_sequence_suits = []

    # Check which suits can form a sequence
    for suit in [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]:
        if can_form_sequence(cards, suit):
            valid_sequence_suits.append(suit)

    if can_be_triple and valid_sequence_suits:
        return (
            GameTypeStr.BOTH,
            valid_sequence_suits[0] if len(valid_sequence_suits) == 1 else None,
        )
    elif can_be_triple:
        return (GameTypeStr.TRIPLE, None)
    elif valid_sequence_suits:
        return (GameTypeStr.SEQUENCE, valid_sequence_suits[0])
    else:
        return (None, None)


def _first_valid_game_from_cards(cards: list[Card]):
    """If these cards form a valid game, return (type, suit, cards); else None."""
    if len(cards) < AIConfig.MIN_MELD_SIZE:
        return None
    for suit in [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]:
        if can_form_sequence(cards, suit):
            return (GameTypeStr.SEQUENCE, suit, cards)
        if can_form_triple(cards):
            return (GameTypeStr.TRIPLE, None, cards)
    return None


def find_valid_game(player, hand):
    """Try to find a valid game from player's hand."""
    for size in range(
        AIConfig.MIN_MELD_SIZE,
        min(AIConfig.MAX_MELD_SIZE, len(hand) + 1),
    ):
        for combo in combinations(hand, size):
            result = _first_valid_game_from_cards(list(combo))
            if result is not None:
                return result
    return None


def _action_description(engine: Engine, action: tuple) -> str:
    """Return a short Portuguese description of the action for the UI."""
    kind = action[0]
    if kind == ActionKind.DRAW_STOCK:
        return ActionDescriptions.DRAW_STOCK
    if kind == ActionKind.DRAW_DISCARD:
        return ActionDescriptions.DRAW_DISCARD_N.format(n=len(engine.discard_pile))
    if kind == ActionKind.END_LAY_DOWN:
        return ActionDescriptions.END_LAY_DOWN_PHASE
    if kind == ActionKind.DISCARD:
        _, hand_idx = action
        player = engine.get_current_player()
        if hand_idx < len(player.hand):
            c = player.hand[hand_idx]
            if c.rank == Rank.JOKER:
                return ActionDescriptions.DISCARD_JOKER
            sym = SUIT_SYMBOLS.get(c.suit, c.suit.value)
            return f"Descartar {c.rank.value}{sym}"
        return ActionDescriptions.DISCARD_CARD
    if kind == ActionKind.LAY_SEQUENCE:
        _, suit, _ = action
        sym = SUIT_SYMBOLS.get(suit, getattr(suit, "value", ""))
        return ActionDescriptions.LAY_SEQUENCE_OF.format(sym=sym)
    if kind == ActionKind.LAY_TRIPLE:
        return ActionDescriptions.LAY_TRIPLE
    if kind == ActionKind.ADD_TO_GAME:
        _, owner_idx, game_idx, rank, suit = action
        if rank == Rank.JOKER:
            return ActionDescriptions.ADD_JOKER_TO_GAME
        sym = SUIT_SYMBOLS.get(suit, getattr(suit, "value", ""))
        return ActionDescriptions.ADD_CARD_TO_GAME.format(rank=rank.value, sym=sym)
    return ""


def get_counterfactual_action(engine: Engine) -> tuple[tuple | None, str]:
    """What the bot would play in the current state. Returns (action, description).
    Use when it is the human's turn to show a counterfactual suggestion.
    Uses full legal actions and more rollouts for a stronger,
    more expensive suggestion."""
    if engine.game_over:
        return (None, "")
    player = engine.get_current_player()
    if not player.is_human:
        return (None, "")
    rng = random.Random()
    best = _is_mcts_choose(
        engine,
        player.team,
        AIConfig.ISMCTS_COUNTERFACTUAL_ROLLOUTS,
        rng,
        use_abstract_actions=False,
        rollout_max_steps=AIConfig.COUNTERFACTUAL_ROLLOUT_MAX_STEPS,
    )
    if best is None:
        return (None, "")
    return (best, _action_description(engine, best))


def play_ai_turn(
    engine: Engine,
    rollouts: int | None = None,
    rollout_max_steps: int | None = None,
    discourage_early_triple: bool = True,
    use_early_heuristic: bool = True,
) -> None:
    """Play one turn for the current AI player.

    Uses AIConfig.AI_TURN_ROLLOUTS and AIConfig.AI_TURN_ROLLOUT_MAX_STEPS by default.
    Pass rollouts/rollout_max_steps for config (e.g. control vs challenger).
    By default uses early-game heuristics: prefer sequences over triples early
    (discourage_early_triple) and bias toward draw safe / extend melds
    (use_early_heuristic). Set either to False to disable.
    """
    player = engine.get_current_player()
    rng = random.Random()
    n_rollouts = rollouts if rollouts is not None else AIConfig.AI_TURN_ROLLOUTS
    n_steps = (
        rollout_max_steps if rollout_max_steps is not None
        else AIConfig.AI_TURN_ROLLOUT_MAX_STEPS
    )
    best = _is_mcts_choose(
        engine,
        player.team,
        n_rollouts,
        rng,
        use_abstract_actions=True,
        rollout_max_steps=n_steps,
        discourage_early_triple=discourage_early_triple,
        use_early_heuristic=use_early_heuristic,
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


def _rank_display_index(rank: Rank) -> int:
    """Index for display order (Ace high). Joker not in RANK_ORDER_SEQUENCE."""
    if rank in RANK_ORDER_SEQUENCE:
        return RANK_ORDER_SEQUENCE.index(rank)
    return AIConfig.JOKER_DISPLAY_INDEX


def _place_joker_in_first_gap(
    suit_cards: list[Card], ranks: list[float], joker: Card,
) -> bool:
    """Insert joker into first gap in suit_cards. Mutates suit_cards and ranks.
    Returns True if placed."""
    for i in range(len(ranks) - 1):
        if ranks[i + 1] - ranks[i] > 1:
            suit_cards.insert(i + 1, joker)
            ranks.insert(i + 1, ranks[i] + 0.5)
            return True
    return False


def organize_hand(hand):
    """Organize hand by suit with jokers in gaps."""
    jokers = [c for c in hand if c.rank == Rank.JOKER]
    non_jokers = [c for c in hand if c.rank != Rank.JOKER]
    organized_hand = []
    for suit in [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]:
        suit_cards = [c for c in non_jokers if c.suit == suit]
        suit_cards.sort(key=lambda c: _rank_display_index(c.rank))
        if suit_cards and jokers:
            ranks = [_rank_display_index(c.rank) for c in suit_cards]
            for joker in list(jokers):
                if _place_joker_in_first_gap(suit_cards, ranks, joker):
                    jokers.remove(joker)
                else:
                    break
        organized_hand.extend(suit_cards)
    organized_hand.extend(jokers)
    return organized_hand
