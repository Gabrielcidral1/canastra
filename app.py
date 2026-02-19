"""Streamlit interface for Canastra."""

import streamlit as st
from itertools import combinations
from card import Card, Rank, Suit
from engine import Engine, TurnPhase, Player
from game import Game, GameType, can_form_sequence, can_form_triple


def initialize_session():
    """Initialize session state."""
    if 'engine' not in st.session_state:
        st.session_state.engine = Engine(num_players=4)
        st.session_state.engine.start_new_game()
    
    if 'selected_cards' not in st.session_state:
        st.session_state.selected_cards = []
    
    if 'selected_game' not in st.session_state:
        st.session_state.selected_game = None


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
    suit_map = {
        Suit.HEARTS: "♥",
        Suit.DIAMONDS: "♦",
        Suit.CLUBS: "♣",
        Suit.SPADES: "♠"
    }
    return suit_map.get(card.suit, "")


def get_rank_display(card: Card) -> str:
    """Get rank display."""
    if card.rank == Rank.JOKER:
        return "J"
    return card.rank.value


def display_card(card: Card, key: str, engine: Engine, selectable: bool = True):
    """Display a card with visual styling."""
    card_str = str(card)
    color = get_card_color(card)
    symbol = get_suit_symbol(card)
    rank = get_rank_display(card)
    is_selected = card in st.session_state.selected_cards
    
    border_color = '#0066FF' if is_selected else '#333'
    bg_color = '#E6F3FF' if is_selected else 'white'
    border_width = '3px' if is_selected else '2px'
    
    card_html = f"""
    <div style="
        display: inline-block;
        width: 60px;
        height: 90px;
        border: {border_width} solid {border_color};
        border-radius: 8px;
        background: {bg_color};
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        margin: 5px;
        padding: 5px;
        text-align: center;
        font-weight: bold;
    ">
        <div style="color: {color}; font-size: 18px; line-height: 1.2;">
            {rank}
        </div>
        <div style="color: {color}; font-size: 28px; line-height: 1.2;">
            {symbol}
        </div>
    </div>
    """
    
    if selectable:
        checkbox_key = f"chk_{key}"
        col1, col2 = st.columns([1, 20])
        with col1:
            selected = st.checkbox(f"Selecionar {card_str}", value=is_selected, key=checkbox_key, 
                                 label_visibility="collapsed")
            if selected:
                if engine.turn_phase == TurnPhase.DISCARD:
                    if card not in st.session_state.selected_cards:
                        st.session_state.selected_cards = [card]
                elif engine.turn_phase == TurnPhase.LAY_DOWN:
                    if card not in st.session_state.selected_cards:
                        st.session_state.selected_cards.append(card)
            else:
                if card in st.session_state.selected_cards:
                    st.session_state.selected_cards.remove(card)
        with col2:
            st.markdown(card_html, unsafe_allow_html=True)
    else:
        st.markdown(card_html, unsafe_allow_html=True)


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
            from itertools import combinations
            for combo in combinations(hand, combo_size):
                cards = list(combo)
                if can_form_sequence(cards, suit):
                    return ("sequence", suit, cards)
                if can_form_triple(cards):
                    return ("triple", None, cards)
    return None


def play_ai_turn(engine: Engine):
    """Play turn for AI players."""
    player = engine.get_current_player()
    
    if engine.turn_phase == TurnPhase.DRAW:
        if engine.stock:
            engine.draw_from_stock()
        elif engine.discard_pile:
            engine.draw_from_discard()
        else:
            engine.game_over = True
            engine._calculate_final_points()
    
    elif engine.turn_phase == TurnPhase.LAY_DOWN:
        team_players = [p for p in engine.players if p.team == player.team]
        team_games = []
        for p in team_players:
            team_games.extend(p.games)
        
        added_to_game = False
        max_additions = 5
        additions = 0
        
        if team_games and player.hand:
            for card in list(player.hand):
                if additions >= max_additions:
                    break
                for game in team_games:
                    game_owner = None
                    for p in team_players:
                        if game in p.games:
                            game_owner = p
                            break
                    if game_owner:
                        game_index = game_owner.games.index(game)
                        try:
                            test_game = Game(game.game_type, game.cards + [card], game.suit)
                            if engine.add_to_game(game_index, card, target_player=game_owner) is None:
                                added_to_game = True
                                additions += 1
                                break
                        except:
                            pass
                if added_to_game and additions >= max_additions:
                    break
        
        if not added_to_game and len(player.hand) >= 3:
            game_result = find_valid_game(player, player.hand)
            if game_result:
                game_type, suit, cards = game_result
                if game_type == "sequence":
                    error = engine.lay_down_sequence(suit, cards)
                else:
                    error = engine.lay_down_triple(cards)
                if error is None:
                    added_to_game = True
        
        if not added_to_game:
            engine.end_lay_down_phase()
    
    elif engine.turn_phase == TurnPhase.DISCARD:
        if player.hand:
            engine.discard(player.hand[0])
        else:
            engine.end_lay_down_phase()


def organize_hand(hand):
    """Organize hand by suit with jokers in gaps."""
    suit_order = {Suit.CLUBS: 0, Suit.DIAMONDS: 1, Suit.HEARTS: 2, Suit.SPADES: 3}
    rank_order = {
        Rank.ACE: 1, Rank.TWO: 2, Rank.THREE: 3, Rank.FOUR: 4, Rank.FIVE: 5,
        Rank.SIX: 6, Rank.SEVEN: 7, Rank.EIGHT: 8, Rank.NINE: 9, Rank.TEN: 10,
        Rank.JACK: 11, Rank.QUEEN: 12, Rank.KING: 13
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
                    if ranks[i+1] - ranks[i] > 1:
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


def display_player_panel(player, engine, is_current=False):
    """Display a player panel with hand count and status."""
    status_icon = "▶" if is_current else "○"
    status_color = "#0066FF" if is_current else "#666"
    
    st.markdown(f"<div style='border: 2px solid {status_color}; border-radius: 8px; padding: 10px; margin: 5px;'>", unsafe_allow_html=True)
    st.markdown(f"**{status_icon} {player.name}**")
    st.write(f"Cartas: {len(player.hand)}")
    if is_current:
        st.write(f"**Fase: {engine.turn_phase.value.upper()}**")
    st.markdown("</div>", unsafe_allow_html=True)


def display_games_area(games, engine, area_id, selectable=False):
    """Display a games area with all melds."""
    if games:
        for i, game in enumerate(games):
            type_str = "Sequência" if game.game_type == GameType.SEQUENCE else "Trinca"
            suit_str = f" de {game.suit.value}" if game.suit else ""
            canastra_str = ""
            if game.is_clean_canastra:
                canastra_str = " (Canastra Limpa!)"
            elif game.is_dirty_canastra:
                canastra_str = " (Canastra Suja!)"
            
            st.write(f"**Jogo {i+1}**: {type_str}{suit_str} - {len(game.cards)} cartas, {game.point_value} pontos{canastra_str}")
            cards_per_row = 13
            num_rows = (len(game.cards) + cards_per_row - 1) // cards_per_row
            for row in range(num_rows):
                cols = st.columns(cards_per_row)
                for col_idx in range(cards_per_row):
                    card_idx = row * cards_per_row + col_idx
                    if card_idx < len(game.cards):
                        with cols[col_idx]:
                            display_card(game.cards[card_idx], f"{area_id}_game_{i}_card_{card_idx}", engine, selectable=selectable)
    else:
        st.write("Nenhum jogo baixado")


def main():
    """Main application function."""
    st.set_page_config(page_title="Canastra Brasileiro", layout="wide")
    
    initialize_session()
    
    engine = st.session_state.engine
    current_player = engine.get_current_player()
    
    if not current_player.is_human and not engine.game_over:
        play_ai_turn(engine)
        st.rerun()
    
    st.markdown("""
    <style>
    .main .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
    }
    footer {
        visibility: hidden;
    }
    header[data-testid="stHeader"] > div:first-child {
        display: none;
    }
    .stApp {
        margin-top: -60px;
    }
    h1, h2, h3 {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🎴 Canastra")
    
    with st.sidebar:
        st.header("📊 Placar")
        for team in sorted(set(p.team for p in engine.players)):
            team_players = [p for p in engine.players if p.team == team]
            points = team_players[0].points
            team_name = "Nós" if team == current_player.team else "Eles"
            st.subheader(f"Time {team_name}: {points} pontos")
            for player in team_players:
                st.write(f"  • {player.name}: {len(player.hand)} cartas, {len(player.games)} jogos")
        
        st.divider()
        st.header("ℹ️ Informações")
        st.write(f"**Jogador Atual**: {current_player.name}")
        st.write(f"**Fase**: {engine.turn_phase.value.upper()}")
        st.write(f"**Monte**: {len(engine.stock)} cartas")
        st.write(f"**Lixo**: {len(engine.discard_pile)} cartas")
        
        if engine.game_over:
            st.success("🎉 Jogo Terminado!")
        
        st.divider()
        st.header("📝 Log do Jogo")
        for msg in engine.messages[-10:]:
            st.write(msg)
    
    opponent_team = 1 if current_player.team == 0 else 0
    opponent_players = [p for p in engine.players if p.team == opponent_team]
    your_team_players = [p for p in engine.players if p.team == current_player.team]
    partner = [p for p in your_team_players if p != current_player]
    partner = partner[0] if partner else None
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Top row: Partner (across from you)
    partner_col = st.columns([1, 3, 1])
    with partner_col[1]:
        if partner:
            st.header("🤝 Parceiro")
            display_player_panel(partner, engine, is_current=(partner == current_player))
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Middle section: Opponents on sides, center table in middle
    main_area = st.columns([2, 3, 2])
    
    # Left side: Opponent 1
    with main_area[0]:
        st.header("👥 Oponente 1")
        opp1 = opponent_players[0] if len(opponent_players) > 0 else None
        if opp1:
            display_player_panel(opp1, engine, is_current=(opp1 == current_player))
    
    # Center: Table with draw pile, discard pile, and meld areas
    with main_area[1]:
        # Use CSS to directly style the column container and all its children
        # This approach targets the Streamlit column structure directly
        st.markdown("""
        <style>
        /* Target the middle column (index 1) in the main_area columns */
        section[data-testid="stApp"] > div:first-child > div > div > div > div[data-testid="column"]:nth-of-type(2),
        .main .block-container > div > div > div[data-testid="column"]:nth-of-type(2) {
            background: linear-gradient(135deg, #2d5016 0%, #3d6b1f 100%) !important;
            border: 3px solid #8B4513 !important;
            border-radius: 15px !important;
            padding: 20px !important;
            min-height: 300px !important;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3) !important;
            margin: 10px 0 !important;
        }
        
        /* Make sure child elements don't override the background */
        section[data-testid="stApp"] > div:first-child > div > div > div > div[data-testid="column"]:nth-of-type(2) > div,
        .main .block-container > div > div > div[data-testid="column"]:nth-of-type(2) > div {
            background: transparent !important;
        }
        
        /* Style all content inside the middle column */
        section[data-testid="stApp"] > div:first-child > div > div > div > div[data-testid="column"]:nth-of-type(2) *,
        .main .block-container > div > div > div[data-testid="column"]:nth-of-type(2) * {
            color: inherit;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.header("🎴 Centro da Mesa")
        
        table_cols = st.columns(2)
        
        with table_cols[0]:
            st.markdown("### 🃏 Monte")
            st.write(f"**{len(engine.stock)} cartas**")
            if engine.stock:
                st.markdown("""
                <div style="
                    width: 70px;
                    height: 100px;
                    border: 3px solid #333;
                    border-radius: 10px;
                    background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%);
                    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                    margin: 10px auto;
                    padding: 10px;
                    text-align: center;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                ">
                    <div style="font-size: 32px;">🂠</div>
                </div>
                """, unsafe_allow_html=True)
        
        with table_cols[1]:
            st.markdown("### 🗑️ Lixeira")
            if engine.discard_pile:
                st.write(f"**{len(engine.discard_pile)} cartas**")
                top_card = engine.discard_pile[-1]
                display_card(top_card, "discard_top", engine, selectable=False)
                if len(engine.discard_pile) > 1:
                    st.caption(f"(+ {len(engine.discard_pile) - 1} cartas abaixo)")
            else:
                st.write("Vazio")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Meld areas inside the green table
        meld_cols = st.columns(2)
        
        with meld_cols[0]:
            st.markdown("### 🃏 Área da Mesa (Eles)")
            opponent_games = []
            for player in opponent_players:
                opponent_games.extend(player.games)
            display_games_area(opponent_games, engine, "opponent", selectable=False)
        
        with meld_cols[1]:
            st.markdown("### 🃏 Área da Mesa (Nós)")
            your_team_games = []
            for player in your_team_players:
                your_team_games.extend(player.games)
            display_games_area(your_team_games, engine, "your_team", selectable=False)
    
    # Right side: Opponent 2
    with main_area[2]:
        st.header("👥 Oponente 2")
        opp2 = opponent_players[1] if len(opponent_players) > 1 else None
        if opp2:
            display_player_panel(opp2, engine, is_current=(opp2 == current_player))
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    
    # Bottom: Your hand
    st.header("👤 Sua Mão")
    if current_player.is_human:
        hand = organize_hand(current_player.hand.copy())
        if hand:
            cards_per_row = 7
            num_rows = (len(hand) + cards_per_row - 1) // cards_per_row
            for row in range(num_rows):
                cols = st.columns(cards_per_row)
                for col_idx in range(cards_per_row):
                    card_idx = row * cards_per_row + col_idx
                    if card_idx < len(hand):
                        with cols[col_idx]:
                            display_card(hand[card_idx], f"card_{card_idx}", engine, selectable=True)
        else:
            st.write("Mão vazia")
    else:
        display_player_panel(current_player, engine, is_current=True)
    
    st.markdown("---")
    
    # Actions section
    st.header("🎮 Ações")
    
    if not engine.game_over and current_player.is_human:
        if engine.turn_phase == TurnPhase.DRAW:
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
                    if st.button(f"🗑️ Comprar do Lixo ({len(engine.discard_pile)} cartas)", use_container_width=True):
                        error = engine.draw_from_discard()
                        if error:
                            st.error(error)
                        else:
                            st.session_state.selected_cards = []
                            st.rerun()
        
        elif engine.turn_phase == TurnPhase.LAY_DOWN:
            st.write("**Cartas Selecionadas**:")
            if st.session_state.selected_cards:
                st.write(f"{len(st.session_state.selected_cards)} cartas selecionadas:")
                selected_cols = st.columns(min(len(st.session_state.selected_cards), 10))
                for i, card in enumerate(st.session_state.selected_cards):
                    with selected_cols[i % 10]:
                        display_card(card, f"selected_{i}", engine, selectable=True)
            else:
                st.info("💡 Clique nas cartas da sua mão para selecioná-las e baixar um jogo")
            
            if len(st.session_state.selected_cards) >= 3:
                st.subheader("Baixar Novo Jogo")
                
                option = st.radio(
                    "Tipo de jogo:",
                    ["Sequência", "Trinca"],
                    key="game_type",
                    horizontal=True
                )
                
                if option == "Sequência":
                    suit = st.selectbox(
                        "Naipe:",
                        ["C", "D", "H", "S"],
                        format_func=lambda x: {"C": "Paus", "D": "Ouros", "H": "Copas", "S": "Espadas"}[x]
                    )
                    suit_map = {"C": Suit.CLUBS, "D": Suit.DIAMONDS, "H": Suit.HEARTS, "S": Suit.SPADES}
                    
                    if st.button("Baixar Sequência", type="primary"):
                        if can_form_sequence(st.session_state.selected_cards, suit_map[suit]):
                            error = engine.lay_down_sequence(suit_map[suit], st.session_state.selected_cards.copy())
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
                            error = engine.lay_down_triple(st.session_state.selected_cards.copy())
                            if error:
                                st.error(error)
                            else:
                                st.session_state.selected_cards = []
                                st.rerun()
                        else:
                            st.error("Cartas não formam uma trinca válida")
            
            your_team_players = [p for p in engine.players if p.team == current_player.team]
            team_games = []
            game_owners = []
            for p in your_team_players:
                for game in p.games:
                    team_games.append(game)
                    game_owners.append(p)
            
            if team_games:
                st.subheader("Adicionar a Jogo Existente do Time")
                game_options = []
                game_indices = []
                for i, game in enumerate(team_games):
                    owner = game_owners[i]
                    game_index_in_owner = owner.games.index(game)
                    game_indices.append((owner, game_index_in_owner))
                    type_str = "Sequência" if game.game_type == GameType.SEQUENCE else "Trinca"
                    suit_str = f" de {game.suit.value}" if game.suit else ""
                    owner_str = f" (de {owner.name})" if owner != current_player else ""
                    game_options.append(f"Jogo {i+1}: {type_str}{suit_str}{owner_str}")
                
                game_idx = st.selectbox(
                    "Selecione o jogo:",
                    range(len(team_games)),
                    format_func=lambda i: game_options[i]
                )
                
                if len(st.session_state.selected_cards) == 1:
                    card = st.session_state.selected_cards[0]
                    if st.button("Adicionar Carta ao Jogo", type="primary"):
                        target_player, game_index_in_owner = game_indices[game_idx]
                        error = engine.add_to_game(game_index_in_owner, card, target_player=target_player)
                        if error:
                            st.error(error)
                        else:
                            st.session_state.selected_cards = []
                            st.rerun()
            
            if st.button("✅ Terminar Fase de Baixar", use_container_width=True):
                engine.end_lay_down_phase()
                st.rerun()
        
        elif engine.turn_phase == TurnPhase.DISCARD:
            st.write("**Selecione uma carta para descartar:**")
            if st.session_state.selected_cards:
                card = st.session_state.selected_cards[0]
                if st.button(f"🗑️ Descartar {card}", type="primary", use_container_width=True):
                    error = engine.discard(card)
                    if error:
                        st.error(error)
                    else:
                        st.session_state.selected_cards = []
                        st.rerun()
            else:
                st.info("Selecione uma carta para descartar")
    
    if st.button("🔄 Novo Jogo", use_container_width=True):
        engine.start_new_game()
        st.session_state.selected_cards = []
        st.rerun()


if __name__ == "__main__":
    main()

