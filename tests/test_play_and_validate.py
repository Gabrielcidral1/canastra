"""Automated play and invariant checks to catch bugs without manual reporting.

Run with: pytest tests/test_play_and_validate.py -v
Or: python -m pytest tests/test_play_and_validate.py -v

These tests run full games (AI vs AI or mixed) and after every turn assert
that engine invariants hold: card count, valid melds, phase and index in range.
Any violation fails the test with a clear message.
"""

import random

from card import create_canastra_deck
from engine import Engine, TurnPhase
from game import Game
from game_helpers import _apply_action, _get_legal_actions, play_ai_turn

DECK_SIZE = len(create_canastra_deck())


def _collect_all_cards(engine: Engine) -> list:
    """Return all cards in the engine (hands, stock, discard, games, dead_hands)."""
    cards = []
    cards.extend(engine.stock)
    cards.extend(engine.discard_pile)
    for p in engine.players:
        cards.extend(p.hand)
        for g in p.games:
            cards.extend(g.cards)
    for _team, pile in engine.dead_hands.items():
        cards.extend(pile)
    return cards


def validate_engine_invariants(engine: Engine, *, after_turn: int = -1) -> None:
    """Assert engine invariants. Raises AssertionError with message on failure.

    - Total cards in the game equals DECK_SIZE (108).
    - current_player_index in valid range.
    - turn_phase is a valid TurnPhase.
    - Every meld (Game) on every player is valid (re-validate structure).
    """
    all_cards = _collect_all_cards(engine)
    assert len(all_cards) == DECK_SIZE, (
        f"Card count mismatch: got {len(all_cards)}, expected {DECK_SIZE} "
        f"(after_turn={after_turn}, phase={engine.turn_phase.value}, "
        f"stock={len(engine.stock)}, discard={len(engine.discard_pile)})"
    )

    assert 0 <= engine.current_player_index < engine.num_players, (
        f"Invalid current_player_index={engine.current_player_index} "
        f"(num_players={engine.num_players}, after_turn={after_turn})"
    )

    assert engine.turn_phase in TurnPhase, (
        f"Invalid turn_phase={engine.turn_phase} (after_turn={after_turn})"
    )

    for pi, p in enumerate(engine.players):
        for gi, g in enumerate(p.games):
            try:
                Game(g.game_type, list(g.cards), g.suit)
            except ValueError as e:
                raise AssertionError(
                    f"Invalid meld: player {pi} game {gi} "
                    f"({g.game_type.value}, {len(g.cards)} cards): {e} "
                    f"(after_turn={after_turn})"
                ) from e


def _play_one_turn_random(engine: Engine, rng: random.Random) -> None:
    """Play one full turn for current player using random legal actions."""
    idx = engine.current_player_index
    while not engine.game_over and engine.current_player_index == idx:
        actions = _get_legal_actions(engine)
        if not actions:
            break
        action = rng.choice(actions)
        _apply_action(engine, action)


def test_play_full_game_all_ai_invariants_hold():
    """Run one full game with all players using play_ai_turn;
    validate after every turn."""
    engine = Engine(num_players=4)
    engine.start_new_game()
    turn = 0
    max_turns = 350
    while not engine.game_over and turn < max_turns:
        play_ai_turn(engine)
        validate_engine_invariants(engine, after_turn=turn)
        turn += 1
    # Game may not finish within limit (AI can be slow);
    # we only require no invariant failure
    assert turn > 0


def test_play_multiple_games_mixed_bots_invariants_hold():
    """Run several games (AI + random bots), validate after every turn."""
    num_games = 3
    max_turns_per_game = 250
    for seed in range(num_games):
        rng = random.Random(seed)
        engine = Engine(num_players=4)
        engine.start_new_game()
        turn = 0
        while not engine.game_over and turn < max_turns_per_game:
            current = engine.get_current_player()
            if current.team == 0:
                play_ai_turn(engine)
            else:
                _play_one_turn_random(engine, rng)
            validate_engine_invariants(engine, after_turn=turn)
            turn += 1


def test_play_full_game_random_only_invariants_hold():
    """Run one full game with random legal moves only; validate after every turn."""
    rng = random.Random(123)
    engine = Engine(num_players=4)
    engine.start_new_game()
    turn = 0
    max_turns = 400
    while not engine.game_over and turn < max_turns:
        _play_one_turn_random(engine, rng)
        validate_engine_invariants(engine, after_turn=turn)
        turn += 1
    # Same as AI test: we only require no invariant failure during play
    assert turn > 0


def test_validate_engine_invariants_on_fresh_game():
    """Sanity: a freshly started game passes invariant checks."""
    engine = Engine(num_players=4)
    engine.start_new_game()
    validate_engine_invariants(engine, after_turn=0)
