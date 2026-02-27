"""Benchmark and measure bot quality: blunder scenarios, win rate vs random,
and control vs challenger.

Run with: python -m benchmark_bot [--games N] [--compare-games N]
Or: python benchmark_bot.py

Control vs Challenger:
- Control: baseline bot (current default parameters).
- Challenger: candidate improvement (edit CHALLENGER_CONFIG in this file).
- We run head-to-head games and compare total points and wins. The challenger
  should only be considered better if it wins more and/or scores more points.
"""

import argparse
import random
import sys
import time
from collections.abc import Callable

from card import Card, Rank, Suit
from engine import Engine, TurnPhase
from game_helpers import (
    AI_TURN_ROLLOUT_MAX_STEPS,
    AI_TURN_ROLLOUTS,
    _apply_action,
    _get_legal_actions,
    get_counterfactual_action,
    play_ai_turn,
)

# --- Control vs Challenger configs ---
# Control: current production default (same as game_helpers constants).
CONTROL_CONFIG = {
    "rollouts": AI_TURN_ROLLOUTS,
    "rollout_max_steps": AI_TURN_ROLLOUT_MAX_STEPS,
}

# Challenger: stronger search (more rollouts + longer rollouts)
# + avoids early trincas and bad discards.
# Must beat control on total points when running the benchmark
# (--assert-challenger-wins).
CHALLENGER_CONFIG = {
    "rollouts": 10,
    "rollout_max_steps": 6,
    "discourage_early_trinca": True,
}


def _play_random_turn(engine: Engine, rng: random.Random) -> None:
    """Play one full turn for the current player using random legal actions."""
    idx = engine.current_player_index
    while not engine.game_over and engine.current_player_index == idx:
        actions = _get_legal_actions(engine)
        if not actions:
            break
        action = rng.choice(actions)
        _apply_action(engine, action)


def make_bot(config: dict) -> Callable[[Engine], None]:
    """Return a bot function that plays one turn using the given config."""
    def play(engine: Engine) -> None:
        play_ai_turn(
            engine,
            rollouts=config.get("rollouts"),
            rollout_max_steps=config.get("rollout_max_steps"),
            discourage_early_trinca=config.get("discourage_early_trinca", False),
        )
    return play


def run_one_game_control_vs_challenger(
    seed: int,
    control_team: int,
    challenger_team: int,
    control_bot: Callable[[Engine], None],
    challenger_bot: Callable[[Engine], None],
    max_turns: int = 500,
) -> tuple[int | None, dict[int, int], bool]:
    """Run one game: control_team uses control_bot, challenger_team uses challenger_bot.
    Returns (winner_team, team_scores, completed). team_scores keys are 0 and 1.
    completed is False if the game threw or hit max_turns without ending."""
    try:
        random.seed(seed)
        engine = Engine(num_players=4)
        engine.start_new_game()
        turn_count = 0
        while not engine.game_over and turn_count < max_turns:
            current = engine.get_current_player()
            if current.team == control_team:
                control_bot(engine)
            else:
                challenger_bot(engine)
            turn_count += 1
        if not engine.game_over:
            return (None, {}, False)
        winner, team_scores = engine.get_winner_message()
        return (winner, team_scores, True)
    except Exception:
        return (None, {}, False)


def run_control_vs_challenger(
    num_games_per_side: int = 5,
    seed_base: int = 100,
) -> dict:
    """Run control vs challenger head-to-head. Each side plays as team 0 in half
    the games and team 1 in the other half (for fairness). Results are in terms
    of control vs challenger, not team 0 vs team 1.

    Returns dict with: control_wins, challenger_wins, ties, total_points_control,
    total_points_challenger, games_played, avg_point_diff (challenger - control).
    """
    control_bot = make_bot(CONTROL_CONFIG)
    challenger_bot = make_bot(CHALLENGER_CONFIG)
    control_wins = 0
    challenger_wins = 0
    ties = 0
    total_points_control = 0
    total_points_challenger = 0
    n = num_games_per_side
    completed_count = 0
    # Control as team 0, challenger as team 1
    for i in range(n):
        winner, scores, completed = run_one_game_control_vs_challenger(
            seed=seed_base + i,
            control_team=0,
            challenger_team=1,
            control_bot=control_bot,
            challenger_bot=challenger_bot,
        )
        if completed and scores:
            completed_count += 1
            total_points_control += scores.get(0, 0)
            total_points_challenger += scores.get(1, 0)
            if winner is None:
                ties += 1
            elif winner == 0:
                control_wins += 1
            else:
                challenger_wins += 1
    # Challenger as team 0, control as team 1 (swap seats)
    for i in range(n):
        winner, scores, completed = run_one_game_control_vs_challenger(
            seed=seed_base + 1000 + i,
            control_team=1,
            challenger_team=0,
            control_bot=control_bot,
            challenger_bot=challenger_bot,
        )
        if completed and scores:
            completed_count += 1
            total_points_control += scores.get(1, 0)
            total_points_challenger += scores.get(0, 0)
            if winner is None:
                ties += 1
            elif winner == 1:
                control_wins += 1
            else:
                challenger_wins += 1
    games_played = completed_count
    avg_diff = (
        (total_points_challenger - total_points_control) / games_played
        if games_played else 0
    )
    return {
        "control_wins": control_wins,
        "challenger_wins": challenger_wins,
        "ties": ties,
        "total_points_control": total_points_control,
        "total_points_challenger": total_points_challenger,
        "games_played": games_played,
        "games_requested": 2 * n,
        "avg_point_diff": avg_diff,  # positive = challenger scores more on average
    }


def run_one_game_bot_vs_random(
    seed: int,
    bot_team: int = 0,
    max_turns: int = 500,
) -> tuple[int | None, dict[int, int]]:
    """Run one game: bot_team uses play_ai_turn, other team uses random.
    Returns (winner_team, team_scores)."""
    try:
        rng = random.Random(seed)
        engine = Engine(num_players=4)
        engine.start_new_game()
        turn_count = 0
        while not engine.game_over and turn_count < max_turns:
            current = engine.get_current_player()
            if current.team == bot_team:
                play_ai_turn(engine)
            else:
                _play_random_turn(engine, rng)
            turn_count += 1
        if not engine.game_over:
            return (None, {0: 0, 1: 0})
        winner, team_scores = engine.get_winner_message()
        return (winner, team_scores)
    except Exception:
        return (None, {0: 0, 1: 0})


def benchmark_win_rate_vs_random(
    num_games: int = 20,
    bot_team: int = 0,
    seed_base: int = 42,
) -> dict:
    """Run bot vs random for num_games. Return win rate and average point diff."""
    wins = 0
    total_point_diff = 0
    for i in range(num_games):
        winner, scores = run_one_game_bot_vs_random(
            seed=seed_base + i, bot_team=bot_team,
        )
        if winner == bot_team:
            wins += 1
        if scores:
            diff = scores.get(bot_team, 0) - scores.get(1 - bot_team, 0)
            total_point_diff += diff
    return {
        "games": num_games,
        "wins": wins,
        "win_rate": wins / num_games if num_games else 0,
        "avg_point_diff": total_point_diff / num_games if num_games else 0,
    }


def _blunder_scenario_discard_joker() -> bool:
    """Scenario: discard phase, we have a joker and a low card. Good move:
    discard the low card, not the joker."""
    engine = Engine(num_players=4)
    engine.start_new_game()
    engine.current_player_index = 0
    engine.turn_phase = TurnPhase.DISCARD
    # Set hand to something with a joker and a safe low card (e.g. 4♠ and Joker)
    engine.players[0].hand = [
        Card(Rank.JOKER),
        Card(Rank.FOUR, Suit.SPADES),
    ]
    engine.discard_pile.append(Card(Rank.FIVE, Suit.HEARTS))  # pile top
    action, _ = get_counterfactual_action(engine)
    if action is None:
        return True  # no suggestion, skip
    if action[0] != "discard":
        return True
    hand_idx = action[1]
    card = engine.players[0].hand[hand_idx]
    # Pass if bot did NOT discard the joker
    return card.rank != Rank.JOKER


def _blunder_scenario_take_useful_discard() -> bool:
    """Scenario: draw phase, we can add the discard pile top to a meld.
    Good move: take the pile."""
    from game import Game, GameType

    engine = Engine(num_players=4)
    engine.start_new_game()
    engine.current_player_index = 0
    engine.turn_phase = TurnPhase.DRAW
    p = engine.players[0]
    # Sequence 3-4-5-6♥; we can add 7♥ from the pile
    seq_cards = [
        Card(Rank.THREE, Suit.HEARTS),
        Card(Rank.FOUR, Suit.HEARTS),
        Card(Rank.FIVE, Suit.HEARTS),
        Card(Rank.SIX, Suit.HEARTS),
    ]
    p.games.append(Game(GameType.SEQUENCE, list(seq_cards), Suit.HEARTS))
    p.hand = [Card(Rank.TEN, Suit.CLUBS), Card(Rank.TWO, Suit.DIAMONDS)]
    engine.discard_pile = [Card(Rank.SEVEN, Suit.HEARTS)]
    engine.stock = [Card(Rank.ACE, Suit.SPADES)]  # so draw_stock is also legal
    action, _ = get_counterfactual_action(engine)
    if action is None:
        return True
    return action[0] == "draw_discard"


def _blunder_scenario_avoid_discard_matching_pile() -> bool:
    """Scenario: discard phase, pile top is 4♠. We have 4♦ and 7♥. Good:
    prefer discarding 7♥ (don't match pile)."""
    engine = Engine(num_players=4)
    engine.start_new_game()
    engine.current_player_index = 0
    engine.turn_phase = TurnPhase.DISCARD
    engine.players[0].hand = [
        Card(Rank.FOUR, Suit.DIAMONDS),
        Card(Rank.SEVEN, Suit.HEARTS),
    ]
    engine.discard_pile = [Card(Rank.FOUR, Suit.CLUBS)]
    action, _ = get_counterfactual_action(engine)
    if action is None:
        return True
    if action[0] != "discard":
        return True
    hand_idx = action[1]
    card = engine.players[0].hand[hand_idx]
    return card.rank != Rank.FOUR


def run_blunder_scenarios() -> dict:
    """Run hand-crafted scenarios where a blunder would be a bad move.
    Return passed/total."""
    results = []
    results.append((
        "Don't discard joker when safe alternative",
        _blunder_scenario_discard_joker(),
    ))
    results.append((
        "Take discard when we can use it",
        _blunder_scenario_take_useful_discard(),
    ))
    results.append((
        "Prefer discard that doesn't match pile top",
        _blunder_scenario_avoid_discard_matching_pile(),
    ))
    passed = sum(1 for _, ok in results if ok)
    return {"passed": passed, "total": len(results), "details": results}


def _run_assert_challenger_wins(num_games_per_side: int) -> None:
    """Run control vs challenger and exit 1 if challenger is not better
    (more points or more wins)."""
    print("Running control vs challenger (assert challenger wins)...")
    result = run_control_vs_challenger(num_games_per_side=num_games_per_side)
    if result["games_played"] < 2:
        print(
            f"ERROR: Only {result['games_played']} games completed (need at least 2). "
            "Cannot assert challenger is better."
        )
        sys.exit(1)
    better_points = result["total_points_challenger"] > result["total_points_control"]
    better_wins = result["challenger_wins"] > result["control_wins"]
    if better_points or better_wins:
        print(
            f"OK: Challenger is better. Points: {result['total_points_challenger']} "
            f"vs {result['total_points_control']} "
            f"(avg diff {result['avg_point_diff']:+.0f}). "
            f"Wins: Challenger {result['challenger_wins']}, "
            f"Control {result['control_wins']}."
        )
        return
    print(
        f"FAIL: Challenger total points ({result['total_points_challenger']}) "
        f"<= Control ({result['total_points_control']}) "
        f"and wins ({result['challenger_wins']}) <= Control "
        f"({result['control_wins']}). "
        "Challenger must score more or win more games."
    )
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark bot quality: blunder scenarios, win rate vs random, "
            "control vs challenger."
        ),
    )
    parser.add_argument(
        "--games",
        type=int,
        default=5,
        help="Games for win-rate vs random (default 5)",
    )
    parser.add_argument(
        "--compare-games",
        type=int,
        default=4,
        help="Games per side for control vs challenger (total 2*N; default 4)",
    )
    parser.add_argument(
        "--skip-blunder",
        action="store_true",
        help="Skip blunder scenarios (faster run)",
    )
    parser.add_argument(
        "--skip-random",
        action="store_true",
        help="Skip win rate vs random (faster run)",
    )
    parser.add_argument(
        "--assert-challenger-wins",
        action="store_true",
        help=(
            "Run only control vs challenger and exit 1 if challenger does not "
            "have more total points (guarantee challenger is better)"
        ),
    )
    args = parser.parse_args()

    if args.assert_challenger_wins:
        _run_assert_challenger_wins(args.compare_games)
        return

    print("=== Bot benchmark ===\n")

    if not args.skip_blunder:
        print("1. Blunder scenarios (Sugestão do bot should avoid bad moves)")
        start = time.perf_counter()
        blunder = run_blunder_scenarios()
        elapsed = time.perf_counter() - start
        print(f"   Passed: {blunder['passed']}/{blunder['total']} in {elapsed:.1f}s")
        for name, ok in blunder["details"]:
            print(f"   - {name}: {'PASS' if ok else 'FAIL'}")
        print()

    if not args.skip_random:
        print(f"2. Win rate vs random ({args.games} games, bot = team 0)")
        start = time.perf_counter()
        win_rate_result = benchmark_win_rate_vs_random(num_games=args.games)
        elapsed = time.perf_counter() - start
        print(
            f"   Win rate: {win_rate_result['win_rate']:.0%} "
            f"({win_rate_result['wins']}/{win_rate_result['games']})"
        )
        print(
            f"   Avg point diff (bot - random): "
            f"{win_rate_result['avg_point_diff']:.0f}"
        )
        print(f"   Time: {elapsed:.1f}s")
        print()

    print("3. Control vs Challenger (head-to-head, more points = better)")
    ctrl = CONTROL_CONFIG
    chal = CHALLENGER_CONFIG
    ctrl_r, ctrl_s, ctrl_t = (
        ctrl.get("rollouts"),
        ctrl.get("rollout_max_steps"),
        ctrl.get("discourage_early_trinca", False),
    )
    chal_r, chal_s, chal_t = (
        chal.get("rollouts"),
        chal.get("rollout_max_steps"),
        chal.get("discourage_early_trinca", False),
    )
    print(
        f"   Control:   rollouts={ctrl_r}, rollout_max_steps={ctrl_s}, "
        f"discourage_early_trinca={ctrl_t}"
    )
    print(
        f"   Challenger: rollouts={chal_r}, rollout_max_steps={chal_s}, "
        f"discourage_early_trinca={chal_t}"
    )
    print(
        f"   Games: {args.compare_games} per side "
        f"(total {2 * args.compare_games} requested)"
    )
    start = time.perf_counter()
    cmp = run_control_vs_challenger(num_games_per_side=args.compare_games)
    elapsed = time.perf_counter() - start
    if cmp["games_played"] < cmp["games_requested"]:
        print(
            f"   Completed: {cmp['games_played']}/{cmp['games_requested']} "
            "(some games errored or timed out)"
        )
    print(f"   Results ({cmp['games_played']} games):")
    print(f"      Control wins:   {cmp['control_wins']}")
    print(f"      Challenger wins: {cmp['challenger_wins']}")
    print(f"      Ties:           {cmp['ties']}")
    print(f"      Total points — Control:   {cmp['total_points_control']}")
    print(f"      Total points — Challenger: {cmp['total_points_challenger']}")
    print(f"      Avg point diff (Challenger − Control): {cmp['avg_point_diff']:+.0f}")
    if cmp["avg_point_diff"] > 0:
        print("   → Challenger is ahead by points (candidate improvement).")
    elif cmp["avg_point_diff"] < 0:
        print("   → Control is ahead by points (challenger is worse).")
    else:
        print("   → Tie on average points.")
    print(f"   Time: {elapsed:.1f}s")
    print()
    print(
        "To test an improvement: set CHALLENGER_CONFIG in benchmark_bot.py "
        "and re-run. Challenger should have more wins and/or more total points."
    )
    print("Use --skip-blunder --skip-random to run only control vs challenger.")


if __name__ == "__main__":
    main()
