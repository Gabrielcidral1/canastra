"""Streamlit interface for Canastra - Orchestrator."""

import sys
from pathlib import Path

# When the project is not installed as a package (e.g. Streamlit Community Cloud
# with package-mode = false), ensure the canastra package can be imported.
_app_dir = Path(__file__).resolve().parent
_src = _app_dir / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import time

import streamlit as st

from canastra.core import (
    RULES_BODY,
    AppConfig,
    Engine,
    GameMode,
    GameRules,
    GameType,
    GameTypeStr,
    TurnPhase,
    UIText,
    can_form_sequence,
    can_form_triple,
    detect_game_type,
    get_counterfactual_action,
    organize_hand,
    play_ai_turn,
)
from canastra.core.card import SUIT_MAP, SUIT_NAME_MAP
from canastra.ui import (
    display_card,
    display_games_area,
    display_player_panel,
    get_app_styles,
    get_card_display_short,
)
from canastra.ui import (
    render_mode_selection as _render_landing,
)

# Bot difficulty: 1=Fácil, 2=Médio, 3=Difícil. Harder = more MCTS rollouts.
# delay_sec: pause after AI turn before showing next (0 when hard, turn already long).
# Kept light so the app stays responsive; Médio was freezing on slower PCs.
BOT_DIFFICULTY_PRESETS = {
    1: {"rollouts": 1, "steps": 2, "delay_sec": 1},  # Fácil: very fast
    2: {"rollouts": 2, "steps": 3, "delay_sec": 1},  # Médio: light
    3: {"rollouts": 4, "steps": 5, "delay_sec": 0},  # Difícil: stronger
}


# Map sidebar label (from UIText.Sidebar) to preset key 1,2,3
def _bot_difficulty_level():
    label = st.session_state.get("bot_difficulty", UIText.Sidebar.BOT_DIFFICULTY_MEDIUM)
    return {
        UIText.Sidebar.BOT_DIFFICULTY_EASY: 1,
        UIText.Sidebar.BOT_DIFFICULTY_MEDIUM: 2,
        UIText.Sidebar.BOT_DIFFICULTY_HARD: 3,
    }.get(label, 2)


def initialize_session():
    """Initialize session state. Engine is created after user chooses game mode."""
    defaults = {
        "game_mode": None,  # "1v1" or "doubles"; set when user clicks "Iniciar jogo"
        "bot_difficulty": UIText.Sidebar.BOT_DIFFICULTY_MEDIUM,  # Fácil/Médio/Difícil
        "selected_cards": [],
        "selected_game": None,
        "counterfactual_suggestion": None,  # (state_key, desc) when user asks
        "confirm_new_game": False,
        "show_rules": False,
        "last_drawn_cards": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Create engine only after game mode is chosen
    if st.session_state.game_mode is not None and "engine" not in st.session_state:
        num_players = GameMode.num_players(st.session_state.game_mode)
        st.session_state.engine = Engine(num_players=num_players)
        st.session_state.engine.start_new_game()


def render_mode_selection():
    """Delegate to landing page module (mode choice, card examples, rules)."""
    _render_landing()


def _human_team(engine: Engine) -> int:
    """Team of the human player, so 'Nós' is always the human's team."""
    return next((p.team for p in engine.players if p.is_human), 0)


def render_game_over_message(
    engine: Engine,
    current_player,
    in_sidebar: bool = False,
):
    """Render winner/tie message for game over (empty stock or canastra)."""
    winner_team, team_scores = engine.get_winner_message()
    our_team = _human_team(engine)
    if winner_team is None:
        our_pts = team_scores.get(our_team, 0)
        other_pts = team_scores.get(1 - our_team, 0)
        msg = UIText.game_over_tie(our_pts, other_pts)
    else:
        winner_name = UIText.Teams.US if winner_team == our_team else UIText.Teams.THEM
        msg = UIText.game_over_won(winner_name, team_scores[winner_team])
    if in_sidebar:
        st.success(msg)
    else:
        st.success(UIText.GameOver.GAME_OVER_PREFIX + msg)


def render_rules_expander():
    """Render the game rules in Brazilian Portuguese inside an expander."""
    expanded = st.session_state.get("show_rules", False)
    with st.expander(UIText.Sidebar.RULES_EXPANDER, expanded=expanded):
        st.markdown(RULES_BODY)


def render_sidebar(engine: Engine, current_player):
    """Render the sidebar: title, score and log first, rules expander at the bottom."""
    difficulty_options = [
        UIText.Sidebar.BOT_DIFFICULTY_EASY,
        UIText.Sidebar.BOT_DIFFICULTY_MEDIUM,
        UIText.Sidebar.BOT_DIFFICULTY_HARD,
    ]
    # Normalize: session may have old int; selectbox needs a string option
    current = st.session_state.get(
        "bot_difficulty", UIText.Sidebar.BOT_DIFFICULTY_MEDIUM
    )
    if current not in difficulty_options:
        st.session_state.bot_difficulty = UIText.Sidebar.BOT_DIFFICULTY_MEDIUM
        current = UIText.Sidebar.BOT_DIFFICULTY_MEDIUM
    index = difficulty_options.index(current)

    st.markdown(UIText.Sidebar.TITLE)
    st.selectbox(
        UIText.Sidebar.BOT_DIFFICULTY_LABEL,
        options=difficulty_options,
        index=index,
        key="bot_difficulty",
    )
    st.divider()
    st.header(UIText.Sidebar.SCORE_HEADER)
    for team in sorted(set(p.team for p in engine.players)):
        team_players = engine.get_team_players(team)
        if engine.game_over:
            points = team_players[0].points
        else:
            points = engine.get_team_live_points(team)
            if not any(p.has_dead_hand for p in team_players):
                points -= GameRules.DEAD_HAND_PENALTY
        team_name = (
            UIText.Teams.US if team == _human_team(engine) else UIText.Teams.THEM
        )
        st.write(f"**{team_name}:** {points}{UIText.Sidebar.POINTS_SUFFIX}")

    if engine.game_over:
        render_game_over_message(engine, current_player, in_sidebar=True)

    st.divider()
    st.header(UIText.Sidebar.LOG_HEADER)
    for msg in engine.messages[-AppConfig.LAST_LOG_MESSAGES :]:
        st.write(msg)

    st.divider()
    render_rules_expander()


def render_player_areas(engine: Engine, current_player):
    """Render the top area with opponent and partner panels.
    'Our' team is always the human's team so labels stay correct."""
    our_team = _human_team(engine)
    opponent_team = 1 - our_team
    opponent_players = [p for p in engine.players if p.team == opponent_team]
    your_team_players = [p for p in engine.players if p.team == our_team]
    human = next((p for p in engine.players if p.is_human), None)
    partner = [p for p in your_team_players if p != human]
    partner = partner[0] if partner else None

    if engine.num_players == 2:
        # 1v1: single opponent panel centered
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown(UIText.PlayerAreas.OPPONENT)
            opp = opponent_players[0] if opponent_players else None
            if opp:
                display_player_panel(opp, engine, is_current=(opp == current_player))
    else:
        # Doubles: Opponent 1 | Partner | Opponent 2
        top_area = st.columns([2.5, 3, 2.5])
        with top_area[0]:
            st.markdown(UIText.PlayerAreas.OPPONENT_1)
            opp1 = opponent_players[0] if len(opponent_players) > 0 else None
            if opp1:
                display_player_panel(opp1, engine, is_current=(opp1 == current_player))
        with top_area[1]:
            if partner:
                st.markdown(UIText.PlayerAreas.PARTNER)
                display_player_panel(
                    partner, engine, is_current=(partner == current_player)
                )
        with top_area[2]:
            st.markdown(UIText.PlayerAreas.OPPONENT_2)
            opp2 = opponent_players[1] if len(opponent_players) > 1 else None
            if opp2:
                display_player_panel(opp2, engine, is_current=(opp2 == current_player))

    return opponent_players, your_team_players


def render_table_area(engine: Engine, opponent_players, your_team_players):
    """Render the center table area with stock, discard pile, and meld areas."""
    center_area = st.columns([1, 4, 1])

    with center_area[1]:
        table_cols = st.columns(2)

        with table_cols[0]:
            st.markdown(UIText.Table.STOCK_HEADING)
            st.write(f"**{len(engine.stock)}{UIText.Sidebar.CARDS_SUFFIX}**")
            if engine.stock:
                st.markdown(
                    """
                <div style="
                    width: 60px;
                    height: 85px;
                    border: 2px solid #333;
                    border-radius: 8px;
                    background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%);
                    box-shadow: 0 3px 5px rgba(0,0,0,0.3);
                    margin: 5px auto;
                    padding: 8px;
                    text-align: center;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                ">
                    <div style="font-size: 28px;">🂠</div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

        with table_cols[1]:
            st.markdown(UIText.Table.DISCARD_HEADING)
            if engine.discard_pile:
                st.write(f"**{len(engine.discard_pile)}{UIText.Sidebar.CARDS_SUFFIX}**")
                cards_per_row = 7
                num_rows = (
                    len(engine.discard_pile) + cards_per_row - 1
                ) // cards_per_row
                for row in range(num_rows):
                    cols = st.columns(cards_per_row)
                    for col_idx in range(cards_per_row):
                        card_idx = row * cards_per_row + col_idx
                        if card_idx < len(engine.discard_pile):
                            actual_idx = len(engine.discard_pile) - 1 - card_idx
                            with cols[col_idx]:
                                display_card(
                                    engine.discard_pile[actual_idx],
                                    f"discard_{actual_idx}",
                                    engine,
                                    selectable=False,
                                )
            else:
                st.write(UIText.Table.EMPTY)

        meld_cols = st.columns(2)

        with meld_cols[0]:
            st.markdown(UIText.Table.OUR_MELDS)
            your_team_games = []
            for player in your_team_players:
                your_team_games.extend(player.games)
            display_games_area(your_team_games, engine, "your_team", selectable=False)

        with meld_cols[1]:
            st.markdown(UIText.Table.THEIR_MELDS)
            opponent_games = []
            for player in opponent_players:
                opponent_games.extend(player.games)
            display_games_area(opponent_games, engine, "opponent", selectable=False)


def render_player_hand(engine: Engine, current_player):
    """Render 'Sua Mão': always show the human player's hand (face-up) so they can
    see their cards and count (11) even when it's an AI's turn."""
    human_player = next((p for p in engine.players if p.is_human), None)
    if not human_player:
        return

    # Clear "just drawn" highlight once user selects something or phase changes
    if (
        st.session_state.get("selected_cards")
        or engine.turn_phase == TurnPhase.DRAW
        or engine.turn_phase == TurnPhase.DISCARD
    ):
        st.session_state.last_drawn_cards = []

    st.markdown(UIText.Hand.HEADING)
    hand = organize_hand(human_player.hand.copy())
    last_drawn = st.session_state.get("last_drawn_cards") or []
    is_my_turn = current_player is human_player

    if hand:
        cards_per_row = 8
        num_rows = (len(hand) + cards_per_row - 1) // cards_per_row
        for row in range(num_rows):
            cols = st.columns(cards_per_row)
            for col_idx in range(cards_per_row):
                card_idx = row * cards_per_row + col_idx
                if card_idx < len(hand):
                    card = hand[card_idx]
                    unique_key = (
                        f"hand_card_{card_idx}_{card.rank.value}_"
                        f"{card.suit.value}_{id(card)}"
                    )
                    with cols[col_idx]:
                        display_card(
                            card,
                            unique_key,
                            engine,
                            selectable=is_my_turn,
                            highlight=card in last_drawn and is_my_turn,
                        )
    else:
        st.write(UIText.Hand.EMPTY)


def render_draw_phase_actions(engine: Engine):
    """Render actions for the draw phase."""
    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button(
            UIText.Actions.DRAW_STOCK,
            type="primary",
            use_container_width=True,
        ):
            error = engine.draw_from_stock()
            if error:
                st.error(error)
            else:
                st.session_state.selected_cards = []
                current = engine.get_current_player()
                last = current.hand[-1] if current.hand else None
                st.session_state.last_drawn_cards = [last] if last else []
                st.rerun()

    with action_cols[1]:
        if engine.discard_pile:
            n_discard = len(engine.discard_pile)
            if st.button(
                UIText.Actions.DRAW_DISCARD.format(n=n_discard),
                use_container_width=True,
            ):
                error = engine.draw_from_discard()
                if error:
                    st.error(error)
                else:
                    st.session_state.selected_cards = []
                    current = engine.get_current_player()
                    st.session_state.last_drawn_cards = (
                        current.hand[-n_discard:] if n_discard else []
                    )
                    st.rerun()


def _do_lay_and_rerun(engine: Engine, lay_fn, valid_check, invalid_msg: str) -> None:
    """Run lay_fn(); on success clear selection and rerun; else show error."""
    if not valid_check():
        st.error(invalid_msg)
        return
    error = lay_fn()
    if error:
        st.error(error)
    else:
        st.session_state.selected_cards = []
        st.rerun()


def _render_lay_new_game(engine: Engine, selected_cards: list) -> None:
    """Render 'Baixar Novo Jogo' block (only when len(selected_cards) >= 3)."""
    if len(selected_cards) < GameRules.MIN_MELD_CARDS:
        return
    st.markdown(UIText.LayDown.TITLE)
    game_type, detected_suit = detect_game_type(selected_cards)
    if game_type is None:
        st.warning(UIText.LayDown.INVALID_CARDS)
        return

    if game_type == GameTypeStr.BOTH:
        option = st.radio(
            UIText.LayDown.GAME_TYPE_LABEL,
            [UIText.LayDown.OPTION_SEQUENCE, UIText.LayDown.OPTION_TRIPLE],
            key="game_type",
            horizontal=True,
            index=0,
        )
    elif game_type == GameTypeStr.TRIPLE:
        option = UIText.LayDown.OPTION_TRIPLE
    else:
        option = UIText.LayDown.OPTION_SEQUENCE

    if option == UIText.LayDown.OPTION_SEQUENCE:
        if detected_suit is not None:
            suit = detected_suit
        else:
            suit_key = st.selectbox(
                UIText.LayDown.SUIT_LABEL,
                list(SUIT_MAP.keys()),
                format_func=lambda x: SUIT_NAME_MAP[x],
            )
            suit = SUIT_MAP[suit_key]
        if st.button(UIText.LayDown.BUTTON_SEQUENCE, type="primary"):
            _do_lay_and_rerun(
                engine,
                lambda: engine.lay_down_sequence(suit, selected_cards.copy()),
                lambda: can_form_sequence(selected_cards, suit),
                UIText.LayDown.INVALID_SEQUENCE,
            )
    elif option == UIText.LayDown.OPTION_TRIPLE:
        if st.button(UIText.LayDown.BUTTON_TRIPLE, type="primary"):
            _do_lay_and_rerun(
                engine,
                lambda: engine.lay_down_triple(selected_cards.copy()),
                lambda: can_form_triple(selected_cards),
                UIText.LayDown.INVALID_TRIPLE,
            )


def _build_team_game_pairs(engine: Engine, current_player) -> list:
    """(game, owner) for team's games, sorted like display."""
    your_team_players = engine.get_team_players(current_player.team)
    pairs = [(g, p) for p in your_team_players for g in p.games]
    pairs.sort(
        key=lambda gp: (
            gp[0].point_value,
            0 if gp[0].game_type == GameType.SEQUENCE else 1,
        )
    )
    return pairs


def _render_add_to_game_buttons(engine: Engine, current_player, card) -> None:
    """Render add-to-game buttons when one card is selected."""
    team_game_pairs = _build_team_game_pairs(engine, current_player)
    if not team_game_pairs:
        return
    valid_targets = []
    for display_pos, (game, owner) in enumerate(team_game_pairs, start=1):
        if not game.can_add(card):
            continue
        game_index_in_owner = owner.games.index(game)
        type_str = (
            UIText.LayDown.OPTION_SEQUENCE
            if game.game_type == GameType.SEQUENCE
            else UIText.LayDown.OPTION_TRIPLE
        )
        if game.suit is not None:
            suit_val = SUIT_NAME_MAP.get(game.suit.value, game.suit.value)
            base_label = f"{type_str} de {suit_val}"
        else:
            base_label = type_str
        valid_targets.append(
            (
                owner,
                game_index_in_owner,
                f"{base_label} ({display_pos}º jogo)",
            )
        )

    st.markdown(UIText.LayDown.ADD_TO_GAME_HEADING)
    if not valid_targets:
        st.caption(UIText.LayDown.CARD_CANNOT_ADD)
        return
    st.caption(UIText.LayDown.CLICK_GAME_TO_ADD)
    for idx, (target_player, game_index_in_owner, label) in enumerate(valid_targets):
        if st.button(
            UIText.LayDown.ADD_BUTTON_PREFIX + label,
            key=f"add_to_game_{idx}_{game_index_in_owner}_{target_player.name}",
            use_container_width=True,
        ):
            error = engine.add_to_game(
                game_index_in_owner, card, target_player=target_player
            )
            if error:
                st.error(error)
            else:
                st.session_state.selected_cards = []
            st.rerun()


def render_lay_down_phase_actions(engine: Engine, current_player):
    """Render actions for the lay down phase."""
    st.write(UIText.LayDown.SELECTED_HEADING)
    selected_cards = st.session_state.selected_cards
    if selected_cards:
        num_selected = len(selected_cards)
        st.write(UIText.selected_count(num_selected))
        cards_per_row = 10
        num_rows = (num_selected + cards_per_row - 1) // cards_per_row
        for row in range(num_rows):
            row_cols = st.columns(cards_per_row)
            for col_idx in range(cards_per_row):
                card_idx = row * cards_per_row + col_idx
                if card_idx < num_selected:
                    card = selected_cards[card_idx]
                    with row_cols[col_idx]:
                        display_card(
                            card,
                            f"selected_display_{card_idx}_{card.rank.value}_{card.suit.value}",
                            engine,
                            selectable=False,
                        )
    else:
        st.info(UIText.LayDown.HINT_SELECT)

    _render_lay_new_game(engine, selected_cards)

    if len(selected_cards) == 1:
        _render_add_to_game_buttons(engine, current_player, selected_cards[0])

    st.info(UIText.LayDown.HINT_FINISH)
    if st.button(UIText.LayDown.BUTTON_END_PHASE, use_container_width=True):
        engine.end_lay_down_phase()
        st.rerun()


def render_discard_phase_actions(engine: Engine):
    """Render actions for the discard phase."""
    st.write(UIText.Discard.PROMPT)
    if st.session_state.selected_cards:
        card = st.session_state.selected_cards[0]
        if st.button(
            UIText.Discard.BUTTON_PREFIX + get_card_display_short(card),
            type="primary",
            use_container_width=True,
        ):
            error = engine.discard(card)
            if error:
                st.error(error)
            else:
                st.session_state.selected_cards = []
                st.rerun()
    else:
        st.info(UIText.Discard.HINT)


def render_game_actions(engine: Engine, current_player):
    """Render game action buttons based on current phase."""
    if not engine.game_over and current_player.is_human:
        if engine.turn_phase == TurnPhase.DRAW:
            render_draw_phase_actions(engine)
        elif engine.turn_phase == TurnPhase.LAY_DOWN:
            render_lay_down_phase_actions(engine, current_player)
        elif engine.turn_phase == TurnPhase.DISCARD:
            render_discard_phase_actions(engine)

    if st.session_state.confirm_new_game:
        st.warning(UIText.Actions.CONFIRM_NEW_GAME)
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                UIText.Actions.BUTTON_NEW_GAME_YES,
                type="primary",
                use_container_width=True,
                key="confirm_new_game_yes",
            ):
                st.session_state.engine.start_new_game()
                st.session_state.selected_cards = []
                st.session_state.counterfactual_suggestion = None
                st.session_state.confirm_new_game = False
                st.rerun()
        with col2:
            if st.button(
                UIText.Actions.BUTTON_CANCEL,
                use_container_width=True,
                key="confirm_new_game_no",
            ):
                st.session_state.confirm_new_game = False
                st.rerun()
    else:
        if st.button(
            UIText.Actions.BUTTON_NEW_GAME,
            use_container_width=True,
            help=UIText.Actions.NEW_GAME_HELP,
            key="btn_novo_jogo",
        ):
            st.session_state.confirm_new_game = True
            st.rerun()


def main():
    """Main application function - orchestrates the UI."""
    st.set_page_config(
        page_title="Canastra",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    initialize_session()

    if "engine" not in st.session_state:
        render_mode_selection()
        return

    engine = st.session_state.engine
    current_player = engine.get_current_player()

    # One AI turn per run so the user can see each opponent's move
    just_played_name = None
    if not current_player.is_human and not engine.game_over:
        diff = _bot_difficulty_level()
        preset = BOT_DIFFICULTY_PRESETS.get(diff, BOT_DIFFICULTY_PRESETS[2])
        play_ai_turn(
            engine,
            rollouts=preset["rollouts"],
            rollout_max_steps=preset["steps"],
        )
        n = len(engine.players)
        just_played_idx = (engine.current_player_index - 1) % n
        just_played_name = engine._get_player_display_name(
            engine.players[just_played_idx]
        )
        current_player = engine.get_current_player()

    # Render sidebar first so it always appears (Streamlit can hide it if rendered late)
    with st.sidebar:
        try:
            render_sidebar(engine, current_player)
        except Exception as e:
            st.error("Sidebar error: " + str(e))
            st.caption("Score, difficulty and log could not be loaded.")

    st.markdown(get_app_styles(), unsafe_allow_html=True)

    if engine.game_over:
        render_game_over_message(engine, current_player, in_sidebar=False)

    # Show last move so user can follow each opponent's turn
    if just_played_name is not None and engine.messages:
        st.info(UIText.Actions.LAST_MOVE.format(msg=engine.messages[-1]))

    opponent_players, your_team_players = render_player_areas(engine, current_player)

    render_table_area(engine, opponent_players, your_team_players)

    st.markdown("---")

    render_player_hand(engine, current_player)

    st.markdown(UIText.Actions.ACTIONS_HEADING)

    if not engine.game_over and current_player.is_human:
        state_key = (
            engine.turn_phase,
            engine.current_player_index,
            len(engine.stock),
            len(engine.discard_pile),
            len(current_player.hand),
            tuple(len(p.games) for p in engine.players),
        )
        cached = st.session_state.counterfactual_suggestion
        if cached is not None and cached[0] == state_key and cached[1]:
            st.caption(UIText.Actions.BOT_WOULD_PLAY.format(desc=cached[1]))
        if st.button(
            UIText.Actions.BOT_SUGGESTION,
            help=UIText.Actions.BOT_SUGGESTION_HELP,
        ):
            with st.spinner(UIText.Actions.SPINNER):
                _action, cf_desc = get_counterfactual_action(engine)
            st.session_state.counterfactual_suggestion = (state_key, cf_desc or "")
            st.rerun()

    render_game_actions(engine, current_player)

    # Auto-advance after a short pause so user sees each AI's move before next.
    # Harder difficulty uses 0s delay (turn already took longer).
    if not engine.game_over and not current_player.is_human:
        diff = _bot_difficulty_level()
        presets = BOT_DIFFICULTY_PRESETS
        delay_sec = presets.get(diff, presets[2])["delay_sec"]
        st.caption(
            UIText.Actions.NEXT_PLAYER_SOON_BRIEF
            if delay_sec == 0
            else UIText.Actions.NEXT_PLAYER_SOON
        )
        if delay_sec > 0:
            time.sleep(delay_sec)
        st.rerun()


if __name__ == "__main__":
    main()
