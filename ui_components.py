"""UI components for Canastra game."""

import streamlit as st

from card import RANK_ORDER_SEQUENCE, Card, Rank, Suit
from engine import Engine, TurnPhase
from game import GameType, counts_as_wildcard_in_sequence, is_wildcard


def get_card_color(card: Card) -> str:
    """Get card color based on suit."""
    if card.rank == Rank.JOKER:
        return "#FFD700"
    if card.suit == Suit.HEARTS or card.suit == Suit.DIAMONDS:
        return "#DC143C"
    return "#000000"


def get_suit_symbol(card: Card) -> str:
    """Get suit symbol."""
    if card.rank == Rank.JOKER:
        return "🃏"
    suit_map = {Suit.HEARTS: "♥", Suit.DIAMONDS: "♦", Suit.CLUBS: "♣", Suit.SPADES: "♠"}
    return suit_map.get(card.suit, "")


def get_rank_display(card: Card) -> str:
    """Get rank display."""
    if card.rank == Rank.JOKER:
        return "J"
    return card.rank.value


def get_card_display_short(card: Card) -> str:
    """Short display for buttons etc: rank + suit symbol (e.g. A♦, 2♣, J)."""
    if card.rank == Rank.JOKER:
        return "🃏"
    return f"{get_rank_display(card)}{get_suit_symbol(card)}"


def _update_selection(phase: TurnPhase, card: Card, selected: bool) -> None:
    """Update session selected_cards by phase and checkbox state (by identity)."""
    sel = st.session_state.selected_cards
    if selected:
        if phase == TurnPhase.DISCARD:
            if card not in sel:
                st.session_state.selected_cards = [card]
        elif phase == TurnPhase.LAY_DOWN and card not in sel:
            st.session_state.selected_cards = list(sel) + [card]
    else:
        for i, c in enumerate(sel):
            if c is card:
                st.session_state.selected_cards = sel[:i] + sel[i + 1 :]
                break


def display_card(
    card: Card,
    key: str,
    engine: Engine,
    selectable: bool = True,
    highlight: bool = False,
):
    """Display a card with visual styling.
    highlight=True for just-drawn card in hand."""
    card_str = str(card)
    color = get_card_color(card)
    symbol = get_suit_symbol(card)
    rank = get_rank_display(card)
    is_selected = card in st.session_state.selected_cards

    if is_selected:
        border_color = "#0066FF"
        bg_color = "#E6F3FF"
        border_width = "3px"
    elif highlight:
        border_color = "#2d7d32"
        bg_color = "#e8f5e9"
        border_width = "3px"
    else:
        border_color = "#333"
        bg_color = "white"
        border_width = "2px"

    if highlight and not is_selected:
        box_shadow = "0 0 10px rgba(45,125,50,0.5)"
    else:
        box_shadow = "0 2px 3px rgba(0,0,0,0.2)"

    card_html = f"""
    <div style="
        display: inline-block;
        width: 55px;
        height: 82px;
        border: {border_width} solid {border_color};
        border-radius: 7px;
        background: {bg_color};
        box-shadow: {box_shadow};
        margin: 3px;
        padding: 4px;
        text-align: center;
        font-weight: bold;
    ">
        <div style="color: {color}; font-size: 16px; line-height: 1.2;">
            {rank}
        </div>
        <div style="color: {color}; font-size: 24px; line-height: 1.2;">
            {symbol}
        </div>
    </div>
    """

    if selectable:
        checkbox_key = f"chk_{key}"
        col1, col2 = st.columns([1, 20])
        with col1:
            selected = st.checkbox(
                f"Selecionar {card_str}",
                value=is_selected,
                key=checkbox_key,
                label_visibility="collapsed",
            )
            _update_selection(engine.turn_phase, card, selected)
        with col2:
            st.markdown(card_html, unsafe_allow_html=True)
    else:
        st.markdown(card_html, unsafe_allow_html=True)


def display_face_down_card():
    """Display a face-down card (upside down)."""
    card_html = """
    <div style="
        display: inline-block;
        width: 40px;
        height: 60px;
        border: 2px solid #333;
        border-radius: 5px;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        box-shadow: 0 2px 3px rgba(0,0,0,0.3);
        margin: 1px;
        padding: 2px;
        text-align: center;
        background-image: repeating-linear-gradient(
            45deg,
            #1a1a2e,
            #1a1a2e 8px,
            #16213e 8px,
            #16213e 16px
        );
    ">
        <div style="color:#fff;font-size:10px;transform:rotate(180deg);opacity:0.3;">
            🂠</div>
    </div>
    """
    return card_html


def display_player_panel(player, engine, is_current=False):
    """Display a player panel with face-down cards instead of count."""
    status_icon = "▶" if is_current else "○"
    status_color = "#0066FF" if is_current else "#666"

    # Display face-down cards instead of "Cartas: X"
    num_cards = len(player.hand)
    cards_html = ""
    cards_per_row = 8
    for i in range(num_cards):
        if i > 0 and i % cards_per_row == 0:
            cards_html += "<br>"
        cards_html += display_face_down_card()

    st.markdown("<div style='padding: 2px;'>", unsafe_allow_html=True)
    st.markdown(
        f"<div style='color:{status_color};font-size:14px;margin-bottom:3px;'>"
        f"{status_icon}</div>",
        unsafe_allow_html=True,
    )
    if cards_html:
        st.markdown(cards_html, unsafe_allow_html=True)
    if is_current:
        phase_div = (
            f"<div style='color:{status_color};font-size:10px;margin-top:3px;'>"
            f"<strong>Fase: {engine.turn_phase.value.upper()}</strong></div>"
        )
        st.markdown(phase_div, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _sort_natural_cards_for_sequence(natural_cards: list, suit: Suit):
    """Sort natural cards by sequence order; handle Ace after King."""
    natural_cards = list(natural_cards)
    natural_cards.sort(
        key=lambda c: (
            RANK_ORDER_SEQUENCE.index(c.rank)
            if c.rank in RANK_ORDER_SEQUENCE else 99
        ),
    )
    ranks = [c.rank for c in natural_cards]
    if Rank.ACE not in ranks or Rank.KING not in ranks:
        return natural_cards
    ace_cards = [c for c in natural_cards if c.rank == Rank.ACE]
    king_cards = [c for c in natural_cards if c.rank == Rank.KING]
    other_cards = [
        c for c in natural_cards
        if c.rank != Rank.ACE and c.rank != Rank.KING
    ]
    other_cards.sort(key=lambda c: RANK_ORDER_SEQUENCE.index(c.rank))
    return other_cards + king_cards + ace_cards


def _place_wildcard_in_sequence_gap(natural_cards: list, wildcard: Card) -> list:
    """Insert wildcard in first gap; else append."""
    if len(natural_cards) < 2:
        return natural_cards + [wildcard]
    ranks = [RANK_ORDER_SEQUENCE.index(c.rank) for c in natural_cards]
    for i in range(len(ranks) - 1):
        if ranks[i + 1] - ranks[i] > 1:
            return natural_cards[: i + 1] + [wildcard] + natural_cards[i + 1 :]
    return natural_cards + [wildcard]


def sort_game_cards(game):
    """Sort cards in a game in ascending order.
    For sequences with 2 of suit: both 5♥,6♥,7♥,2♥ and 2♥,5♥,6♥,7♥ are valid;
    we show 2 at the start of the run when it was filling a gap (2,5,6,7)."""
    if game.game_type != GameType.SEQUENCE:
        wildcards = [c for c in game.cards if is_wildcard(c)]
        natural_cards = [c for c in game.cards if not is_wildcard(c)]
        suit_order = {Suit.CLUBS: 0, Suit.DIAMONDS: 1, Suit.HEARTS: 2, Suit.SPADES: 3}
        natural_cards.sort(key=lambda c: suit_order.get(c.suit, 4))
        return natural_cards + wildcards

    wildcards = [c for c in game.cards if counts_as_wildcard_in_sequence(c, game.suit)]
    natural_cards = [
        c for c in game.cards
        if not counts_as_wildcard_in_sequence(c, game.suit)
    ]
    natural_cards = _sort_natural_cards_for_sequence(natural_cards, game.suit)

    if wildcards:
        return _place_wildcard_in_sequence_gap(natural_cards, wildcards[0])

    twos_of_suit = [
        c for c in natural_cards
        if c.rank == Rank.TWO and game.suit and c.suit == game.suit
    ]
    rest = [c for c in natural_cards if c not in twos_of_suit]
    if len(twos_of_suit) == 1 and len(rest) >= 2:
        return twos_of_suit + rest
    return natural_cards


def display_games_area(games, engine, area_id, selectable=False):
    """Display a games area with all melds."""
    if games:
        # Sort games by point value (ascending), then by type
        sorted_games = sorted(
            games,
            key=lambda g: (g.point_value, 0 if g.game_type == GameType.SEQUENCE else 1),
        )

        for i, game in enumerate(sorted_games):
            # Wrap each meld (badge + cards) in a container
            # so the badge sits right on its game
            with st.container():
                pts = game.point_value
                # Badge/label: tight to the cards below (minimal margin)
                if game.is_canastra:
                    if game.is_clean_canastra:
                        label = "Canastra Limpa"
                        badge_color = "#2d7d46"
                    else:
                        label = "Canastra Suja"
                        badge_color = "#b8860b"
                    st.markdown(
                        f'<span style="'
                        f'display: inline-block; '
                        f'background: {badge_color}; '
                        f'color: white; '
                        f'padding: 2px 8px; '
                        f'border-radius: 6px; '
                        f'font-size: 0.75rem; '
                        f'font-weight: bold; '
                        f'margin-bottom: 2px;'
                        f'">{label} · {pts} pts</span>',
                        unsafe_allow_html=True,
                    )
                # Non-canastra melds: no point label (only canastra badge shown above)

                # Sort cards in ascending order
                sorted_cards = sort_game_cards(game)
                cards_per_row = 13
                num_rows = (len(sorted_cards) + cards_per_row - 1) // cards_per_row
                for row in range(num_rows):
                    cols = st.columns(cards_per_row)
                    for col_idx in range(cards_per_row):
                        card_idx = row * cards_per_row + col_idx
                        if card_idx < len(sorted_cards):
                            with cols[col_idx]:
                                display_card(
                                    sorted_cards[card_idx],
                                    f"{area_id}_game_{i}_card_{card_idx}",
                                    engine,
                                    selectable=selectable,
                                )
            # Space between melds (not inside the same meld)
            st.markdown(
                "<div style='margin-bottom: 10px;'></div>",
                unsafe_allow_html=True,
            )
    else:
        st.write("Nenhum jogo baixado")


def get_app_styles():
    """Get CSS styles for the application."""
    return """
    <style>
    .main .block-container {
        padding-top: 0.1rem !important;
        padding-bottom: 0.1rem !important;
        max-width: 100% !important;
    }
    footer {
        visibility: hidden;
    }
    header[data-testid="stHeader"] > div:first-child {
        display: none;
    }
    .stApp {
        margin-top: -80px;
    }
    h1, h2, h3 {
        margin-top: 0.1rem !important;
        margin-bottom: 0.1rem !important;
        font-size: 1.1rem !important;
    }
    h4 {
        margin-top: 0.05rem !important;
        margin-bottom: 0.05rem !important;
        font-size: 0.9rem !important;
    }
    [data-testid="stVerticalBlock"] {
        gap: 0.05rem !important;
    }
    .element-container {
        margin-bottom: 0.1rem !important;
    }
    .stMarkdown {
        margin-bottom: 0.1rem !important;
    }
    </style>
    """
