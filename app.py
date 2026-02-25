"""Streamlit interface for Canastra - Orchestrator."""

import streamlit as st

from card import Suit
from engine import Engine, TurnPhase
from game import GameType, can_form_sequence, can_form_triple
from game_helpers import (
    detect_game_type,
    get_counterfactual_action,
    organize_hand,
    play_ai_turn,
)
from ui_components import (
    display_card,
    display_games_area,
    display_player_panel,
    get_app_styles,
    get_card_display_short,
)


def initialize_session():
    """Initialize session state."""
    if "engine" not in st.session_state:
        st.session_state.engine = Engine(num_players=4)
        st.session_state.engine.start_new_game()

    if "selected_cards" not in st.session_state:
        st.session_state.selected_cards = []

    if "selected_game" not in st.session_state:
        st.session_state.selected_game = None

    if "counterfactual_suggestion" not in st.session_state:
        st.session_state.counterfactual_suggestion = None  # (state_key, desc) when user asks

    if "confirm_new_game" not in st.session_state:
        st.session_state.confirm_new_game = False


def render_game_over_message(engine: Engine, current_player, in_sidebar: bool = False):
    """Render the same winner/tie message for any game over (empty stock or canastra)."""
    winner_team, team_scores = engine.get_winner_message()
    our_team = current_player.team
    if winner_team is None:
        our_pts = team_scores.get(our_team, 0)
        other_pts = team_scores.get(1 - our_team, 0)
        msg = f"Empate! Nós {our_pts} x Eles {other_pts} pontos."
    else:
        winner_name = "Nós" if winner_team == our_team else "Eles"
        msg = (
            f"🎉 Time {winner_name} venceu com "
            f"{team_scores[winner_team]} pontos!"
        )
    if in_sidebar:
        st.success(msg)
    else:
        st.success(f"**Jogo encerrado.** {msg}")


def render_sidebar(engine: Engine, current_player):
    """Render the sidebar with score and game information."""
    st.header("📊 Placar")
    for team in sorted(set(p.team for p in engine.players)):
        team_players = [p for p in engine.players if p.team == team]
        if engine.game_over:
            points = team_players[0].points
        else:
            points = engine.get_team_live_points(team)
            # -100 for team that hasn't picked up the morto yet
            if not any(p.has_dead_hand for p in team_players):
                points -= 100
        team_name = "Nós" if team == current_player.team else "Eles"
        st.write(f"**{team_name}:** {points} pontos")

    st.divider()
    st.header("ℹ️ Informações")
    st.write(f"**Jogador Atual**: {current_player.name}")
    st.write(f"**Fase**: {engine.turn_phase.value.upper()}")
    st.write(f"**Monte**: {len(engine.stock)} cartas")
    st.write(f"**Lixo**: {len(engine.discard_pile)} cartas")

    if engine.game_over:
        render_game_over_message(engine, current_player, in_sidebar=True)

    st.divider()
    st.header("📝 Log do Jogo")
    for msg in engine.messages[-10:]:
        st.write(msg)


def render_player_areas(engine: Engine, current_player):
    """Render the top area with opponent and partner panels."""
    opponent_team = 1 if current_player.team == 0 else 0
    opponent_players = [p for p in engine.players if p.team == opponent_team]
    your_team_players = [p for p in engine.players if p.team == current_player.team]
    partner = [p for p in your_team_players if p != current_player]
    partner = partner[0] if partner else None

    top_area = st.columns([2.5, 3, 2.5])

    with top_area[0]:
        st.markdown("### 👥 Oponente 1")
        opp1 = opponent_players[0] if len(opponent_players) > 0 else None
        if opp1:
            display_player_panel(opp1, engine, is_current=(opp1 == current_player))

    with top_area[1]:
        if partner:
            st.markdown("### 🤝 Parceiro")
            display_player_panel(
                partner, engine, is_current=(partner == current_player)
            )

    with top_area[2]:
        st.markdown("### 👥 Oponente 2")
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
            st.markdown("#### 🃏 Monte")
            st.write(f"**{len(engine.stock)} cartas**")
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
            st.markdown("#### 🗑️ Lixeira")
            if engine.discard_pile:
                st.write(f"**{len(engine.discard_pile)} cartas**")
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
                st.write("Vazio")

        meld_cols = st.columns(2)

        with meld_cols[0]:
            st.markdown("#### 🃏 Jogos Baixados (Nós)")
            your_team_games = []
            for player in your_team_players:
                your_team_games.extend(player.games)
            display_games_area(your_team_games, engine, "your_team", selectable=False)

        with meld_cols[1]:
            st.markdown("#### 🃏 Jogos Baixados (Eles)")
            opponent_games = []
            for player in opponent_players:
                opponent_games.extend(player.games)
            display_games_area(opponent_games, engine, "opponent", selectable=False)


def render_player_hand(engine: Engine, current_player):
    """Render the player's hand."""
    st.markdown("### 👤 Sua Mão")
    if current_player.is_human:
        hand = organize_hand(current_player.hand.copy())
        if hand:
            cards_per_row = 8
            num_rows = (len(hand) + cards_per_row - 1) // cards_per_row
            for row in range(num_rows):
                cols = st.columns(cards_per_row)
                for col_idx in range(cards_per_row):
                    card_idx = row * cards_per_row + col_idx
                    if card_idx < len(hand):
                        card = hand[card_idx]
                        # Use id(card) so each card instance has a stable key;
                        # avoids losing selection when hand is reordered or
                        # when duplicate cards (same rank/suit) exist
                        unique_key = (
                            f"hand_card_{card_idx}_{card.rank.value}_"
                            f"{card.suit.value}_{id(card)}"
                        )
                        with cols[col_idx]:
                            display_card(card, unique_key, engine, selectable=True)
        else:
            st.write("Mão vazia")
    else:
        display_player_panel(current_player, engine, is_current=True)


def render_draw_phase_actions(engine: Engine):
    """Render actions for the draw phase."""
    action_cols = st.columns(2)
    with action_cols[0]:
        if st.button("🃏 Comprar do Monte", type="primary", use_container_width=True):
            error = engine.draw_from_stock()
            if error:
                st.error(error)
            else:
                st.session_state.selected_cards = []
                st.rerun()

    with action_cols[1]:
        if engine.discard_pile:
            if st.button(
                f"🗑️ Comprar do Lixo ({len(engine.discard_pile)} cartas)",
                use_container_width=True,
            ):
                error = engine.draw_from_discard()
                if error:
                    st.error(error)
                else:
                    st.session_state.selected_cards = []
                    st.rerun()


def render_lay_down_phase_actions(engine: Engine, current_player):
    """Render actions for the lay down phase."""
    st.write("**Cartas selecionadas**")
    if st.session_state.selected_cards:
        num_selected = len(st.session_state.selected_cards)
        st.write(
            f"**{num_selected} carta selecionada:**"
            if num_selected == 1
            else f"**{num_selected} cartas selecionadas:**"
        )
        cards_per_row = 10
        num_rows = (num_selected + cards_per_row - 1) // cards_per_row
        for row in range(num_rows):
            row_cols = st.columns(cards_per_row)
            for col_idx in range(cards_per_row):
                card_idx = row * cards_per_row + col_idx
                if card_idx < num_selected:
                    card = st.session_state.selected_cards[card_idx]
                    with row_cols[col_idx]:
                        display_card(
                            card,
                            f"selected_display_{card_idx}_{card.rank.value}_{card.suit.value}",
                            engine,
                            selectable=False,
                        )
    else:
        st.info("💡 Clique nas cartas da sua mão para selecioná-las e baixar um jogo")

    if len(st.session_state.selected_cards) >= 3:
        st.markdown("#### Baixar Novo Jogo")

        game_type, detected_suit = detect_game_type(st.session_state.selected_cards)

        if game_type is None:
            st.warning("⚠️ As cartas selecionadas não formam um jogo válido")
        else:
            suit_map = {
                "C": Suit.CLUBS,
                "D": Suit.DIAMONDS,
                "H": Suit.HEARTS,
                "S": Suit.SPADES,
            }

            if game_type == "both":
                option = st.radio(
                    "Tipo de jogo:",
                    ["Sequência", "Trinca"],
                    key="game_type",
                    horizontal=True,
                    index=0,
                )
            elif game_type == "triple":
                option = "Trinca"
            else:
                option = "Sequência"

            if option == "Sequência":
                if detected_suit:
                    suit = detected_suit
                else:
                    suit_name_map = {
                        "C": "Paus",
                        "D": "Ouros",
                        "H": "Copas",
                        "S": "Espadas",
                    }
                    suit_key = st.selectbox(
                        "Naipe:",
                        ["C", "D", "H", "S"],
                        format_func=lambda x: suit_name_map[x],
                    )
                    suit = suit_map[suit_key]

                if st.button("Baixar Sequência", type="primary"):
                    if can_form_sequence(st.session_state.selected_cards, suit):
                        error = engine.lay_down_sequence(
                            suit, st.session_state.selected_cards.copy()
                        )
                        if error:
                            st.error(error)
                        else:
                            st.session_state.selected_cards = []
                            st.rerun()
                    else:
                        st.error("Cartas não formam uma sequência válida")

            elif option == "Trinca":
                if st.button("Baixar Trinca", type="primary"):
                    if can_form_triple(st.session_state.selected_cards):
                        error = engine.lay_down_triple(
                            st.session_state.selected_cards.copy()
                        )
                        if error:
                            st.error(error)
                        else:
                            st.session_state.selected_cards = []
                            st.rerun()
                    else:
                        st.error("Cartas não formam uma trinca válida")

    your_team_players = [p for p in engine.players if p.team == current_player.team]
    team_game_pairs = []
    for p in your_team_players:
        for game in p.games:
            team_game_pairs.append((game, p))

    # Sort like the display (by point value, then type) so "first game" on screen = first option
    team_game_pairs.sort(
        key=lambda gp: (
            gp[0].point_value,
            0 if gp[0].game_type == GameType.SEQUENCE else 1,
        )
    )

    if team_game_pairs and len(st.session_state.selected_cards) == 1:
        card = st.session_state.selected_cards[0]
        suit_name_map = {
            "C": "Paus",
            "D": "Ouros",
            "H": "Copas",
            "S": "Espadas",
        }
        valid_targets = []
        for display_pos, (game, owner) in enumerate(team_game_pairs, start=1):
            if not game.can_add(card):
                continue
            game_index_in_owner = owner.games.index(game)
            type_str = "Sequência" if game.game_type == GameType.SEQUENCE else "Trinca"
            if game.suit:
                suit_name = suit_name_map.get(game.suit.value, game.suit.value)
                base_label = f"{type_str} de {suit_name}"
            else:
                base_label = type_str
            # Match display order: "1º jogo" = first meld on screen
            label = f"{base_label} ({display_pos}º jogo)"
            valid_targets.append((owner, game_index_in_owner, label))

        st.markdown("#### Adicionar a um jogo do time")
        if not valid_targets:
            st.caption("Esta carta não pode ser adicionada a nenhum jogo do time.")
        else:
            st.caption("Clique no jogo ao qual deseja adicionar a carta:")
            for idx, (target_player, game_index_in_owner, label) in enumerate(
                valid_targets
            ):
                if st.button(
                    f"➕ Adicionar à {label}",
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

    st.info("💡 Você pode baixar mais jogos ou terminar a fase quando terminar.")
    if st.button("✅ Terminar Fase de Baixar", use_container_width=True):
        engine.end_lay_down_phase()
        st.rerun()


def render_discard_phase_actions(engine: Engine):
    """Render actions for the discard phase."""
    st.write("**Selecione uma carta para descartar:**")
    if st.session_state.selected_cards:
        card = st.session_state.selected_cards[0]
        if st.button(
            f"🗑️ Descartar {get_card_display_short(card)}",
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
        st.info("Selecione uma carta para descartar")


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
        st.warning("Tem certeza? O jogo atual será perdido.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Sim, novo jogo", type="primary", use_container_width=True, key="confirm_new_game_yes"):
                st.session_state.engine.start_new_game()
                st.session_state.selected_cards = []
                st.session_state.counterfactual_suggestion = None
                st.session_state.confirm_new_game = False
                st.rerun()
        with col2:
            if st.button("Cancelar", use_container_width=True, key="confirm_new_game_no"):
                st.session_state.confirm_new_game = False
                st.rerun()
    else:
        if st.button("🔄 Novo Jogo", use_container_width=True, help="Iniciar um novo jogo (o atual será perdido).", key="btn_novo_jogo"):
            st.session_state.confirm_new_game = True
            st.rerun()


def main():
    """Main application function - orchestrates the UI."""
    st.set_page_config(page_title="Canastra", layout="wide")

    initialize_session()

    engine = st.session_state.engine
    current_player = engine.get_current_player()

    if not current_player.is_human and not engine.game_over:
        play_ai_turn(engine)
        st.rerun()

    st.markdown(get_app_styles(), unsafe_allow_html=True)

    st.markdown("### 🎴 Canastra")

    if engine.game_over:
        render_game_over_message(engine, current_player, in_sidebar=False)

    with st.sidebar:
        render_sidebar(engine, current_player)

    opponent_players, your_team_players = render_player_areas(engine, current_player)

    render_table_area(engine, opponent_players, your_team_players)

    st.markdown("---")

    render_player_hand(engine, current_player)

    st.markdown("### 🎮 Ações")

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
            st.caption(f"🤖 O bot jogaria: **{cached[1]}**")
        if st.button("🤖 Sugestão do bot", help="Calcula o que o bot jogaria (pode demorar alguns segundos)."):
            with st.spinner("Calculando..."):
                _action, cf_desc = get_counterfactual_action(engine)
            st.session_state.counterfactual_suggestion = (state_key, cf_desc or "")
            st.rerun()

    render_game_actions(engine, current_player)


if __name__ == "__main__":
    main()
