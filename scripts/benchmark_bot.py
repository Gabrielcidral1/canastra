"""Benchmark and measure bot quality: blunder scenarios and control vs challenger.

Run with: python -m benchmark_bot [--compare-games N]
Or: python benchmark_bot.py

Control vs Challenger:
- Control: baseline bot (current default parameters).
- Challenger: candidate improvement (edit CHALLENGER_CONFIG in this file).
- We run head-to-head games and compare total points and wins. The challenger
  should only be considered better if it wins more and/or scores more points.
"""

import argparse
import logging
import math
import random
import sys
import time
from collections.abc import Callable

from tqdm import tqdm

from canastra.core import (
    AIConfig,
    Engine,
    GameRules,
    TurnPhase,
    get_counterfactual_action,
    play_ai_turn,
)
from canastra.core.card import Card, Rank, Suit

logger = logging.getLogger(__name__)

# --- Control vs Challenger configs ---
# Control = production default: early-game heuristic + avoid early trincas/bad discards.
CONTROL_CONFIG = {
    "rollouts": AIConfig.AI_TURN_ROLLOUTS,
    "rollout_max_steps": AIConfig.AI_TURN_ROLLOUT_MAX_STEPS,
    "discourage_early_triple": True,
    "use_early_heuristic": True,
}

# Challenger: same as control until you try a new candidate (edit here for A/B tests).
CHALLENGER_CONFIG = {
    "rollouts": AIConfig.AI_TURN_ROLLOUTS,
    "rollout_max_steps": AIConfig.AI_TURN_ROLLOUT_MAX_STEPS,
    "discourage_early_triple": True,
    "use_early_heuristic": True,
}


def make_bot(config: dict) -> Callable[[Engine], None]:
    """Return a bot function that plays one turn using the given config."""

    def play(engine: Engine) -> None:
        play_ai_turn(
            engine,
            rollouts=config.get("rollouts"),
            rollout_max_steps=config.get("rollout_max_steps"),
            discourage_early_triple=config.get("discourage_early_triple", False),
            use_early_heuristic=config.get("use_early_heuristic", False),
        )

    return play


def run_one_game_control_vs_challenger(
    seed: int,
    control_team: int,
    challenger_team: int,
    control_bot: Callable[[Engine], None],
    challenger_bot: Callable[[Engine], None],
    max_turns: int = 200,
) -> tuple[int | None, dict[int, int], bool, str | None]:
    """Run one game: control_team uses control_bot, challenger_team uses challenger_bot.
    max_turns = max number of player-turns (one full turn per player). With ~42 cards
    in stock and 4 players, a game finishes in ~40–45 full rounds
    (~160–180 player-turns).
    Returns (winner_team, team_scores, completed, incomplete_reason).
    incomplete_reason is None if completed; else 'timeout' or 'error'."""
    try:
        random.seed(seed)
        engine = Engine(num_players=GameRules.NUM_PLAYERS)
        engine.start_new_game()
        turn_count = 0
        while not engine.game_over and turn_count < max_turns:
            current_player_before = engine.current_player_index
            while (
                not engine.game_over
                and engine.current_player_index == current_player_before
            ):
                current = engine.get_current_player()
                if current.team == control_team:
                    control_bot(engine)
                else:
                    challenger_bot(engine)
            turn_count += 1
        if not engine.game_over:
            return (None, {}, False, "timeout")
        winner, team_scores = engine.get_winner_message()
        return (winner, team_scores, True, None)
    except Exception:
        return (None, {}, False, "error")


def _ci95_mean(samples: list[float]) -> tuple[float, float] | None:
    """Return (lower, upper) 95% confidence interval for the mean, or None if n < 2."""
    n = len(samples)
    if n < 2:
        return None
    mean = sum(samples) / n
    variance = sum((x - mean) ** 2 for x in samples) / (n - 1)
    se = math.sqrt(variance / n)
    half = 1.96 * se
    return (mean - half, mean + half)


def run_control_vs_challenger(
    num_games_per_side: int = 5,
    seed_base: int = 100,
    max_turns: int = 200,
) -> dict:
    """Run control vs challenger head-to-head. Each side plays as team 0 in half
    the games and team 1 in the other half (for fairness). Results are in terms
    of control vs challenger, not team 0 vs team 1.

    Returns dict with: control_wins, challenger_wins, ties, total_points_control,
    total_points_challenger, games_played, games_requested, avg_point_diff,
    point_diff_ci95 (tuple or None), incomplete_reasons (dict: timeout/error counts).
    """
    control_bot = make_bot(CONTROL_CONFIG)
    challenger_bot = make_bot(CHALLENGER_CONFIG)
    control_wins = 0
    challenger_wins = 0
    ties = 0
    total_points_control = 0
    total_points_challenger = 0
    point_diffs: list[float] = []
    incomplete_reasons: dict[str, int] = {"timeout": 0, "error": 0}
    n = num_games_per_side

    def process_result(
        winner: int | None,
        scores: dict,
        completed: bool,
        reason: str | None,
        control_team: int,
        challenger_team: int,
    ) -> None:
        nonlocal control_wins, challenger_wins, ties
        nonlocal total_points_control, total_points_challenger, point_diffs
        if not completed:
            if reason:
                incomplete_reasons[reason] = incomplete_reasons.get(reason, 0) + 1
            return
        if not scores:
            return
        total_points_control += scores.get(control_team, 0)
        total_points_challenger += scores.get(challenger_team, 0)
        point_diffs.append(scores.get(challenger_team, 0) - scores.get(control_team, 0))
        if winner is None:
            ties += 1
        elif winner == control_team:
            control_wins += 1
        else:
            challenger_wins += 1

    # Control as team 0, challenger as team 1; then swap seats (2*n games total)
    game_configs = [(seed_base + i, 0, 1) for i in range(n)] + [
        (seed_base + 1000 + i, 1, 0) for i in range(n)
    ]
    for seed, ctrl_team, chal_team in tqdm(
        game_configs,
        desc="Control vs Challenger",
        unit="game",
    ):
        winner, scores, completed, reason = run_one_game_control_vs_challenger(
            seed=seed,
            control_team=ctrl_team,
            challenger_team=chal_team,
            control_bot=control_bot,
            challenger_bot=challenger_bot,
            max_turns=max_turns,
        )
        process_result(winner, scores, completed, reason, ctrl_team, chal_team)

    games_played = len(point_diffs)
    avg_diff = (
        (total_points_challenger - total_points_control) / games_played
        if games_played
        else 0
    )
    point_diff_ci95 = _ci95_mean(point_diffs) if point_diffs else None

    return {
        "control_wins": control_wins,
        "challenger_wins": challenger_wins,
        "ties": ties,
        "total_points_control": total_points_control,
        "total_points_challenger": total_points_challenger,
        "games_played": games_played,
        "games_requested": 2 * n,
        "avg_point_diff": avg_diff,
        "point_diff_ci95": point_diff_ci95,
        "incomplete_reasons": incomplete_reasons,
    }


def _blunder_scenario_discard_joker() -> bool:
    """Scenario: discard phase, we have a joker and a low card. Good move:
    discard the low card, not the joker."""
    engine = Engine(num_players=GameRules.NUM_PLAYERS)
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

    engine = Engine(num_players=GameRules.NUM_PLAYERS)
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
    engine = Engine(num_players=GameRules.NUM_PLAYERS)
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
    scenarios = [
        ("Don't discard joker when safe alternative", _blunder_scenario_discard_joker),
        ("Take discard when we can use it", _blunder_scenario_take_useful_discard),
        (
            "Prefer discard that doesn't match pile top",
            _blunder_scenario_avoid_discard_matching_pile,
        ),
    ]
    results = []
    for name, fn in tqdm(scenarios, desc="Blunder scenarios", unit="scenario"):
        results.append((name, fn()))
    passed = sum(1 for _, ok in results if ok)
    return {"passed": passed, "total": len(results), "details": results}


def _run_assert_challenger_wins(
    num_games_per_side: int,
    max_turns: int = 200,
) -> None:
    """Run control vs challenger and exit 1 if challenger is not better
    (more points or more wins)."""
    logger.info("Running control vs challenger (assert challenger wins)...")
    result = run_control_vs_challenger(
        num_games_per_side=num_games_per_side,
        max_turns=max_turns,
    )
    if result["games_played"] < 2:
        logger.error(
            "Only %s games completed (need at least 2). "
            "Cannot assert challenger is better.",
            result["games_played"],
        )
        sys.exit(1)
    better_points = result["total_points_challenger"] > result["total_points_control"]
    better_wins = result["challenger_wins"] > result["control_wins"]
    if better_points or better_wins:
        wins_msg = (
            f"Game wins: Challenger {result['challenger_wins']}, "
            f"Control {result['control_wins']}"
        )
        if result.get("ties", 0):
            wins_msg += f", {result['ties']} tied game(s)"
        logger.info(
            "OK: Challenger is better. Total points: %s vs %s (avg diff %+.0f). %s.",
            result["total_points_challenger"],
            result["total_points_control"],
            result["avg_point_diff"],
            wins_msg,
        )
        return
    logger.error(
        "FAIL: Challenger total points (%s) <= Control (%s) "
        "and wins (%s) <= Control (%s). "
        "Challenger must score more or win more games.",
        result["total_points_challenger"],
        result["total_points_control"],
        result["challenger_wins"],
        result["control_wins"],
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
        "--assert-challenger-wins",
        action="store_true",
        help=(
            "Run only control vs challenger and exit 1 if challenger does not "
            "have more total points (guarantee challenger is better)"
        ),
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=200,
        help=(
            "Max player-turns per game before timeout (default 200). "
            "One player-turn = one full turn (draw/lay/discard). "
            "A normal game uses ~160–180 player-turns; timeouts may indicate a bug."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
    )

    if args.assert_challenger_wins:
        _run_assert_challenger_wins(
            args.compare_games,
            max_turns=getattr(args, "max_turns", 200),
        )
        return

    logger.info("=== Bot benchmark ===\n")

    if not args.skip_blunder:
        logger.info("1. Blunder scenarios (Sugestão do bot should avoid bad moves)")
        start = time.perf_counter()
        blunder = run_blunder_scenarios()
        elapsed = time.perf_counter() - start
        logger.info(
            "   Passed: %s/%s in %.1fs",
            blunder["passed"],
            blunder["total"],
            elapsed,
        )
        for name, ok in blunder["details"]:
            logger.info("   - %s: %s", name, "PASS" if ok else "FAIL")
        logger.info("")

    logger.info("2. Control vs Challenger (head-to-head, more points = better)")
    ctrl = CONTROL_CONFIG
    chal = CHALLENGER_CONFIG
    ctrl_r, ctrl_s, ctrl_t, ctrl_h = (
        ctrl.get("rollouts"),
        ctrl.get("rollout_max_steps"),
        ctrl.get("discourage_early_triple", False),
        ctrl.get("use_early_heuristic", False),
    )
    chal_r, chal_s, chal_t, chal_h = (
        chal.get("rollouts"),
        chal.get("rollout_max_steps"),
        chal.get("discourage_early_triple", False),
        chal.get("use_early_heuristic", False),
    )
    logger.info(
        "   Control:   rollouts=%s, rollout_max_steps=%s, "
        "discourage_early_triple=%s, use_early_heuristic=%s",
        ctrl_r,
        ctrl_s,
        ctrl_t,
        ctrl_h,
    )
    logger.info(
        "   Challenger: rollouts=%s, rollout_max_steps=%s, "
        "discourage_early_triple=%s, use_early_heuristic=%s",
        chal_r,
        chal_s,
        chal_t,
        chal_h,
    )
    max_turns = getattr(args, "max_turns", 200)
    logger.info(
        "   Games: %s per side (total %s requested), max_turns=%s",
        args.compare_games,
        2 * args.compare_games,
        max_turns,
    )
    start = time.perf_counter()
    cmp = run_control_vs_challenger(
        num_games_per_side=args.compare_games,
        max_turns=max_turns,
    )
    elapsed = time.perf_counter() - start
    if cmp["games_played"] < cmp["games_requested"]:
        reasons = cmp.get("incomplete_reasons") or {}
        timeout = reasons.get("timeout", 0)
        err = reasons.get("error", 0)
        parts = [f"Completed: {cmp['games_played']}/{cmp['games_requested']}"]
        if timeout:
            parts.append(
                f"{timeout} timeout (hit max_turns={max_turns} player-turns; "
                "games normally finish in ~160–180 player-turns)"
            )
        if err:
            parts.append(f"{err} error(s)")
        logger.info("   %s", "; ".join(parts))
    logger.info("   Results (%s games):", cmp["games_played"])
    logger.info("      Games won by Control:   %s", cmp["control_wins"])
    logger.info("      Games won by Challenger: %s", cmp["challenger_wins"])
    logger.info("      Games tied (equal score): %s", cmp["ties"])
    logger.info("      Total points — Control:   %s", cmp["total_points_control"])
    logger.info("      Total points — Challenger: %s", cmp["total_points_challenger"])
    logger.info(
        "      Avg point diff (Challenger − Control): %+.0f",
        cmp["avg_point_diff"],
    )
    ci = cmp.get("point_diff_ci95")
    if ci and cmp["games_played"] >= 2:
        logger.info("      95%% CI (mean point diff): [%+.0f, %+.0f]", ci[0], ci[1])
        if ci[0] > 0:
            logger.info(
                "   → Challenger ahead; 95%% CI entirely above 0 (significant)."
            )
        elif ci[1] < 0:
            logger.info("   → Control ahead; 95%% CI entirely below 0 (significant).")
        else:
            logger.info(
                "   → CI includes 0; difference may not be significant "
                "(run more games)."
            )
    else:
        if cmp["avg_point_diff"] > 0:
            logger.info("   → Challenger is ahead by points (candidate improvement).")
        elif cmp["avg_point_diff"] < 0:
            logger.info("   → Control is ahead by points (challenger is worse).")
        else:
            logger.info("   → Tie on average points.")
    logger.info("   Time: %.1fs", elapsed)
    logger.info("")
    logger.info(
        "To test an improvement: set CHALLENGER_CONFIG in benchmark_bot.py "
        "and re-run. Challenger should have more wins and/or more total points."
    )
    logger.info("Use --skip-blunder to run only control vs challenger.")


if __name__ == "__main__":
    main()
