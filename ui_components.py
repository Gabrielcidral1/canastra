"""UI components for Canastra game."""

import streamlit as st

from card import Card, Rank, Suit
from engine import Engine, TurnPhase
from game import GameType, is_wildcard


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


def display_card(card: Card, key: str, engine: Engine, selectable: bool = True):
    """Display a card with visual styling."""
    card_str = str(card)
    color = get_card_color(card)
    symbol = get_suit_symbol(card)
    rank = get_rank_display(card)
    is_selected = card in st.session_state.selected_cards

    border_color = "#0066FF" if is_selected else "#333"
    bg_color = "#E6F3FF" if is_selected else "white"
    border_width = "3px" if is_selected else "2px"

    card_html = f"""
    <div style="
        display: inline-block;
        width: 55px;
        height: 82px;
        border: {border_width} solid {border_color};
        border-radius: 7px;
        background: {bg_color};
        box-shadow: 0 2px 3px rgba(0,0,0,0.2);
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
        # Key must be unique per card instance (key already contains id(card)
        # from caller in hand); so duplicate cards and reordered hands don't
        # share checkbox state or clear selection
        checkbox_key = f"chk_{key}"
        col1, col2 = st.columns([1, 20])
        with col1:
            selected = st.checkbox(
                f"Selecionar {card_str}",
                value=is_selected,
                key=checkbox_key,
                label_visibility="collapsed",
            )
            # Update selection based on checkbox state
            if selected:
                if engine.turn_phase == TurnPhase.DISCARD:
                    # In discard phase, only one card can be selected
                    if card not in st.session_state.selected_cards:
                        st.session_state.selected_cards = [card]
                elif engine.turn_phase == TurnPhase.LAY_DOWN:
                    # In lay down phase, multiple cards can be selected
                    if card not in st.session_state.selected_cards:
                        st.session_state.selected_cards.append(card)
            else:
                # Remove card from selection only by identity (so duplicate
                # cards don't clear the selection)
                for i, c in enumerate(st.session_state.selected_cards):
                    if c is card:
                        st.session_state.selected_cards.pop(i)
                        break
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


def _counts_as_wildcard_in_sequence_ui(card: Card, suit: Suit) -> bool:
    """True if card counts as wildcard for display (Joker or 2 of another suit).
    2 of the sequence suit counts as natural and is placed at start or end of run."""
    return is_wildcard(card) and not (card.rank == Rank.TWO and card.suit == suit)


def sort_game_cards(game):
    """Sort cards in a game in ascending order.
    For sequences with 2 of suit: both 5♥,6♥,7♥,2♥ and 2♥,5♥,6♥,7♥ are valid;
    we show 2 at the start of the run when it was filling a gap (2,5,6,7)."""
    if game.game_type == GameType.SEQUENCE:
        rank_order = [
            Rank.ACE,
            Rank.TWO,
            Rank.THREE,
            Rank.FOUR,
            Rank.FIVE,
            Rank.SIX,
            Rank.SEVEN,
            Rank.EIGHT,
            Rank.NINE,
            Rank.TEN,
            Rank.JACK,
            Rank.QUEEN,
            Rank.KING,
        ]

        # Real wildcards (Joker or 2 of other suit) vs natural (including 2 of sequence suit)
        wildcards = [
            c for c in game.cards if _counts_as_wildcard_in_sequence_ui(c, game.suit)
        ]
        natural_cards = [
            c for c in game.cards if not _counts_as_wildcard_in_sequence_ui(c, game.suit)
        ]

        # Sort natural cards by rank
        natural_cards.sort(
            key=lambda c: rank_order.index(c.rank) if c.rank in rank_order else 99
        )

        # Handle Ace after King case
        if Rank.ACE in [c.rank for c in natural_cards] and Rank.KING in [
            c.rank for c in natural_cards
        ]:
            ace_cards = [c for c in natural_cards if c.rank == Rank.ACE]
            king_cards = [c for c in natural_cards if c.rank == Rank.KING]
            other_cards = [
                c for c in natural_cards if c.rank != Rank.ACE and c.rank != Rank.KING
            ]
            other_cards.sort(key=lambda c: rank_order.index(c.rank))

            if other_cards and rank_order.index(ace_cards[0].rank) < rank_order.index(
                king_cards[0].rank
            ):
                natural_cards = other_cards + king_cards + ace_cards
            else:
                natural_cards = other_cards + king_cards + ace_cards

        # Place real wildcards (Joker / 2 other suit) in gaps; 2 of suit stays with natural
        sorted_cards = []
        if wildcards:
            wildcard = wildcards[0]
            if len(natural_cards) >= 2:
                ranks = [rank_order.index(c.rank) for c in natural_cards]
                wildcard_inserted = False
                for i in range(len(ranks) - 1):
                    if ranks[i + 1] - ranks[i] > 1:
                        sorted_cards = (
                            natural_cards[: i + 1] + [wildcard] + natural_cards[i + 1 :]
                        )
                        wildcard_inserted = True
                        break
                if not wildcard_inserted:
                    sorted_cards = natural_cards + [wildcard]
            else:
                sorted_cards = natural_cards + [wildcard]
        else:
            # All natural (including 2 of suit). Both 5,6,7,2 and 2,5,6,7 are valid; use 2 at start.
            twos_of_suit = [
                c for c in natural_cards if c.rank == Rank.TWO and game.suit and c.suit == game.suit
            ]
            rest = [c for c in natural_cards if c not in twos_of_suit]
            if len(twos_of_suit) == 1 and len(rest) >= 2:
                # Run like 5,6,7 with one 2: display as 2,5,6,7 (both valid)
                sorted_cards = twos_of_suit + rest
            else:
                sorted_cards = natural_cards

        return sorted_cards
    else:
        # For triples, keep natural cards together, wildcard at end
        wildcards = [c for c in game.cards if is_wildcard(c)]
        natural_cards = [c for c in game.cards if not is_wildcard(c)]
        # Sort natural cards by suit for consistency
        suit_order = {Suit.CLUBS: 0, Suit.DIAMONDS: 1, Suit.HEARTS: 2, Suit.SPADES: 3}
        natural_cards.sort(key=lambda c: suit_order.get(c.suit, 4))
        return natural_cards + wildcards


def display_games_area(games, engine, area_id, selectable=False):
    """Display a games area with all melds."""
    if games:
        # Sort games by point value (ascending), then by type
        sorted_games = sorted(
            games,
            key=lambda g: (g.point_value, 0 if g.game_type == GameType.SEQUENCE else 1),
        )

        for i, game in enumerate(sorted_games):
            # Wrap each meld (badge + cards) in a container so the badge sits right on its game
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
                else:
                    st.markdown(
                        f'<span style="'
                        f'display: inline-block; '
                        f'color: #666; '
                        f'font-size: 0.75rem; '
                        f'margin-bottom: 2px;'
                        f'">{pts} pts ({len(game.cards)} × 10)</span>',
                        unsafe_allow_html=True,
                    )

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
            st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
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
