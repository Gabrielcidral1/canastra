"""Integration tests for Canastra game engine.

These tests verify the complete game flow and behavior to ensure
that refactoring preserves the same functionality.
"""

import time
import unittest.mock as mock

import pytest

from card import Card, Rank, Suit
from engine import Engine, KnockType, TurnPhase
from game import Game, GameType, can_form_sequence, can_form_triple
from game_helpers import (
    _apply_action,
    _determinize,
    _discard_danger,
    _early_trinca_penalty,
    _get_legal_actions,
    _is_early_game,
    get_counterfactual_action,
    play_ai_turn,
)


class TestGameInitialization:
    """Test game initialization and setup."""

    def test_engine_initialization(self):
        """Test that engine initializes correctly."""
        engine = Engine(num_players=4)
        assert engine.num_players == 4
        assert len(engine.players) == 4
        assert engine.current_player_index == 0
        assert engine.turn_phase == TurnPhase.DRAW
        assert not engine.game_over
        assert len(engine.stock) == 0
        assert len(engine.discard_pile) == 0

    def test_start_new_game(self):
        """Test starting a new game."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        # Check deck creation (2 decks of 52 + 4 jokers = 108)
        deck = engine.create_deck()
        assert len(deck) == 108
        assert sum(1 for c in deck if c.rank == Rank.JOKER) == 4
        assert sum(1 for c in deck if c.rank != Rank.JOKER) == 104  # 2 * 52
        assert len(engine.stock) > 0

        # Check players have cards
        for player in engine.players:
            assert len(player.hand) == 11

        # Check dead hands
        for team in engine.dead_hands:
            assert len(engine.dead_hands[team]) == 11

        # Check turn phase
        assert engine.turn_phase == TurnPhase.DRAW
        assert not engine.game_over

    def test_player_teams(self):
        """Test that players are assigned to correct teams."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        # Players 0 and 1 should be team 0, players 2 and 3 should be team 1
        assert engine.players[0].team == 0
        assert engine.players[1].team == 0
        assert engine.players[2].team == 1
        assert engine.players[3].team == 1

    def test_human_player(self):
        """Test that first player is human."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        assert engine.players[0].is_human
        assert not engine.players[1].is_human
        assert not engine.players[2].is_human
        assert not engine.players[3].is_human


class TestCardDrawing:
    """Test card drawing mechanics."""

    def test_draw_from_stock(self):
        """Test drawing a card from stock."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        initial_stock_size = len(engine.stock)
        initial_hand_size = len(engine.get_current_player().hand)

        error = engine.draw_from_stock()

        assert error is None
        assert len(engine.stock) == initial_stock_size - 1
        assert len(engine.get_current_player().hand) == initial_hand_size + 1
        assert engine.turn_phase == TurnPhase.LAY_DOWN

    def test_draw_from_stock_wrong_phase(self):
        """Test drawing from stock in wrong phase."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.draw_from_stock()  # Move to LAY_DOWN phase

        error = engine.draw_from_stock()
        assert error == "Só é possível comprar na fase de compra"

    def test_draw_from_empty_stock(self):
        """Drawing from empty stock ends the game and calculates final points."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        # Empty the stock
        while engine.stock:
            engine.stock.pop()

        error = engine.draw_from_stock()
        assert error is None
        assert engine.game_over
        winner_team, team_scores = engine.get_winner_message()
        assert len(team_scores) == 2

    def test_draw_from_discard(self):
        """Test drawing all cards from discard pile."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        # Add cards to discard pile
        player = engine.get_current_player()
        card1 = Card(Rank.ACE, Suit.HEARTS)
        card2 = Card(Rank.TWO, Suit.CLUBS)
        engine.discard_pile = [card1, card2]

        initial_hand_size = len(player.hand)

        error = engine.draw_from_discard()

        assert error is None
        assert len(engine.discard_pile) == 0
        assert len(player.hand) == initial_hand_size + 2
        assert engine.turn_phase == TurnPhase.LAY_DOWN

    def test_draw_from_empty_discard(self):
        """Test drawing from empty discard pile."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        error = engine.draw_from_discard()
        assert error == "Lixo está vazio"


class TestLayingDownGames:
    """Test laying down games (sequences and triples)."""

    def test_lay_down_sequence(self):
        """Test laying down a valid sequence."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Create a valid sequence
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.THREE, Suit.HEARTS),
        ]

        # Add cards to player's hand
        for card in cards:
            player.add_card(card)

        error = engine.lay_down_sequence(Suit.HEARTS, cards)

        assert error is None
        assert len(player.games) == 1
        assert player.games[0].game_type == GameType.SEQUENCE
        assert len(player.hand) == 11  # Original 11 cards minus 3 laid down

    def test_lay_down_sequence_wrong_phase(self):
        """Test laying down sequence in wrong phase."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.THREE, Suit.HEARTS),
        ]
        for card in cards:
            player.add_card(card)

        error = engine.lay_down_sequence(Suit.HEARTS, cards)
        assert error == "Só é possível baixar jogos na fase de baixar"

    def test_lay_down_sequence_card_not_in_hand(self):
        """Test laying down sequence with card not in hand."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.THREE, Suit.HEARTS),
        ]
        # Don't add cards to hand

        error = engine.lay_down_sequence(Suit.HEARTS, cards)
        assert error is not None
        assert "não está na mão" in error

    def test_lay_down_sequence_with_wildcard(self):
        """Test laying down sequence with a wildcard (2 or Joker)."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Sequence with wildcard: A, 2 (wild as 3), 4
        # Actually, 2 can only fill one gap, so A, 2, 4 doesn't work (needs 3)
        # Use A, 2 (wild as 2), 3 instead
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.TWO, Suit.HEARTS),  # Wildcard
            Card(Rank.THREE, Suit.HEARTS),
        ]

        for card in cards:
            player.add_card(card)

        error = engine.lay_down_sequence(Suit.HEARTS, cards)
        assert error is None
        assert len(player.games) == 1

    def test_lay_down_triple(self):
        """Test laying down a valid triple."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Create a valid triple (A, A, A)
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.CLUBS),
        ]

        for card in cards:
            player.add_card(card)

        error = engine.lay_down_triple(cards)

        assert error is None
        assert len(player.games) == 1
        assert player.games[0].game_type == GameType.TRIPLE

    def test_lay_down_triple_with_wildcard(self):
        """Test laying down triple with wildcard."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Triple with wildcard: A, A, Joker
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.JOKER),
        ]

        for card in cards:
            player.add_card(card)

        error = engine.lay_down_triple(cards)
        assert error is None

    def test_lay_down_invalid_sequence(self):
        """Test laying down invalid sequence."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Invalid sequence: A, 3, 5 (missing 2 and 4)
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
        ]

        for card in cards:
            player.add_card(card)

        error = engine.lay_down_sequence(Suit.HEARTS, cards)
        assert error is not None

    def test_sequence_duplicate_ranks_not_allowed(self):
        """Sequence cannot have duplicate ranks (e.g. 6D, 2D, 8D, 8D)."""
        from game import Game, GameType

        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN
        cards = [
            Card(Rank.SIX, Suit.DIAMONDS),
            Card(Rank.TWO, Suit.DIAMONDS),
            Card(Rank.EIGHT, Suit.DIAMONDS),
            Card(Rank.EIGHT, Suit.DIAMONDS),
        ]
        with pytest.raises(ValueError) as exc_info:
            Game(GameType.SEQUENCE, cards, Suit.DIAMONDS)
        assert (
            "repetidas" in str(exc_info.value).lower()
            or "duplicate" in str(exc_info.value).lower()
        )


class TestAddingToGames:
    """Test adding cards to existing games."""

    def test_add_card_to_sequence(self):
        """Test adding a card to an existing sequence."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Create a valid sequence (consecutive ranks)
        sequence_cards = [
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
        ]
        for card in sequence_cards:
            player.add_card(card)

        error = engine.lay_down_sequence(Suit.HEARTS, sequence_cards)
        assert error is None
        assert len(player.games) == 1

        # Add a card to extend the sequence
        new_card = Card(Rank.SIX, Suit.HEARTS)
        player.add_card(new_card)

        error = engine.add_to_game(0, new_card)

        assert error is None
        assert len(player.games[0].cards) == 4

    def test_add_card_to_sequence_with_2_of_suit_filling_gap(self):
        """Adding the natural card that the 2 of suit stands for
        (e.g. 6 to 5,2,7) must be allowed."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN
        # Sequence 5H, 2H, 7H (2 stands for 6)
        seq = [
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
        ]
        for c in seq:
            player.add_card(c)
        err = engine.lay_down_sequence(Suit.HEARTS, seq)
        assert err is None
        six_hearts = Card(Rank.SIX, Suit.HEARTS)
        player.add_card(six_hearts)
        assert player.games[0].can_add(six_hearts), "6H should be addable to 5H,2H,7H"
        error = engine.add_to_game(0, six_hearts)
        assert error is None, f"add_to_game should succeed: {error}"
        assert len(player.games[0].cards) == 4

    def test_add_card_to_triple(self):
        """Test adding a card to an existing triple."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Create a triple
        triple_cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.CLUBS),
        ]
        for card in triple_cards:
            player.add_card(card)

        engine.lay_down_triple(triple_cards)

        # Add another ace
        new_card = Card(Rank.ACE, Suit.SPADES)
        player.add_card(new_card)

        error = engine.add_to_game(0, new_card)

        assert error is None
        assert len(player.games[0].cards) == 4

    def test_add_card_to_partner_game(self):
        """Test adding card to partner's game."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        # Get players from the same team
        team_0_players = [p for p in engine.players if p.team == 0]
        player = team_0_players[0]
        partner = team_0_players[1]

        # Set current player to the first player
        engine.current_player_index = engine.players.index(player)
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Partner lays down a valid sequence
        sequence_cards = [
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
        ]
        for card in sequence_cards:
            partner.add_card(card)

        # Temporarily set partner as current to lay down
        old_index = engine.current_player_index
        engine.current_player_index = engine.players.index(partner)
        error = engine.lay_down_sequence(Suit.HEARTS, sequence_cards)
        assert error is None
        engine.current_player_index = old_index

        # Current player adds to partner's game
        new_card = Card(Rank.SIX, Suit.HEARTS)
        player.add_card(new_card)

        error = engine.add_to_game(0, new_card, target_player=partner)

        assert error is None
        assert len(partner.games[0].cards) == 4

    def test_add_card_to_opponent_game_fails(self):
        """Test that adding card to opponent's game fails."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        player_team = player.team

        # Find an opponent (different team)
        opponent = None
        for p in engine.players:
            if p.team != player_team:
                opponent = p
                break

        assert opponent is not None
        assert opponent.team != player.team

        engine.turn_phase = TurnPhase.LAY_DOWN

        # Opponent lays down a valid game
        sequence_cards = [
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
        ]
        for card in sequence_cards:
            opponent.add_card(card)

        # Temporarily set opponent as current to lay down
        old_index = engine.current_player_index
        engine.current_player_index = engine.players.index(opponent)
        error = engine.lay_down_sequence(Suit.HEARTS, sequence_cards)
        assert error is None
        engine.current_player_index = old_index

        # Current player tries to add to opponent's game
        new_card = Card(Rank.SIX, Suit.HEARTS)
        player.add_card(new_card)

        error = engine.add_to_game(0, new_card, target_player=opponent)

        # Should fail because opponent is on different team
        assert error is not None
        assert "time" in error.lower()

    def test_add_card_to_sequence_with_wildcard(self):
        """Adding a card that fills the gap after a wildcard (e.g. 5H,2H,7H + 8H)
        must be accepted."""
        from game import Game, GameType

        engine = Engine(num_players=4)
        engine.start_new_game()
        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Sequence with one wildcard: 5H, 2H (wildcard as 6), 7H
        sequence_cards = [
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
        ]
        game = Game(GameType.SEQUENCE, sequence_cards, Suit.HEARTS)
        player.games.append(game)

        eight_hearts = Card(Rank.EIGHT, Suit.HEARTS)
        player.add_card(eight_hearts)

        error = engine.add_to_game(0, eight_hearts)
        assert error is None
        assert len(player.games[0].cards) == 4
        ranks = [c.rank for c in player.games[0].cards if c.rank != Rank.TWO]
        assert Rank.EIGHT in ranks

    def test_add_2_of_suit_to_sequence_with_existing_wildcard(self):
        """Adding 2 of the sequence suit (e.g. 2C to a Clubs sequence) is allowed
        as natural even if there is already a wildcard (e.g. 2D)."""
        from game import Game, GameType

        engine = Engine(num_players=4)
        engine.start_new_game()
        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Sequence: 3C, 2D (wildcard as 4), 5C, 6C
        sequence_cards = [
            Card(Rank.THREE, Suit.CLUBS),
            Card(Rank.TWO, Suit.DIAMONDS),
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.SIX, Suit.CLUBS),
        ]
        game = Game(GameType.SEQUENCE, sequence_cards, Suit.CLUBS)
        player.games.append(game)

        two_clubs = Card(Rank.TWO, Suit.CLUBS)
        player.add_card(two_clubs)

        error = engine.add_to_game(0, two_clubs)
        assert error is None
        assert len(player.games[0].cards) == 5
        natural_ranks = [c.rank for c in player.games[0].cards if c.suit == Suit.CLUBS]
        assert Rank.TWO in natural_ranks

    def test_add_duplicate_rank_to_sequence_rejected(self):
        """Adding a card that would duplicate a rank in the sequence (e.g. second
        8D) is rejected."""
        from game import Game, GameType

        engine = Engine(num_players=4)
        engine.start_new_game()
        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN
        sequence_cards = [
            Card(Rank.SIX, Suit.DIAMONDS),
            Card(Rank.TWO, Suit.DIAMONDS),
            Card(Rank.EIGHT, Suit.DIAMONDS),
        ]
        game = Game(GameType.SEQUENCE, sequence_cards, Suit.DIAMONDS)
        player.games.append(game)
        second_eight = Card(Rank.EIGHT, Suit.DIAMONDS)
        player.add_card(second_eight)
        error = engine.add_to_game(0, second_eight)
        assert error is not None
        assert len(player.games[0].cards) == 3


class TestDiscarding:
    """Test discarding cards."""

    def test_discard_card(self):
        """Test discarding a card."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.DISCARD

        card = player.hand[0]
        initial_hand_size = len(player.hand)

        error = engine.discard(card)

        assert error is None
        assert len(player.hand) == initial_hand_size - 1
        assert len(engine.discard_pile) == 1
        assert engine.discard_pile[0] == card

    def test_discard_wrong_phase(self):
        """Test discarding in wrong phase."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        card = player.hand[0]

        error = engine.discard(card)
        assert error == "Só é possível descartar na fase de descartar"

    def test_discard_card_not_in_hand(self):
        """Test discarding card not in hand."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.DISCARD

        # Create a card that's definitely not in the hand
        # Remove all cards from hand first to ensure the card is not there
        original_hand = player.hand.copy()
        player.hand.clear()

        # Try to discard a card that's not in the (now empty) hand
        card = Card(Rank.ACE, Suit.HEARTS)
        error = engine.discard(card)

        # Restore hand for cleanup
        player.hand = original_hand

        assert error is not None
        assert "não está na mão" in error

    def test_discard_duplicate_cards_selection_by_identity(self):
        """With two identical cards (e.g. two 6H), selecting one must keep
        selection until that card is unchecked. Simulates UI fix: removing from
        selection must be by identity so the other duplicate doesn't clear it."""
        six_h_a = Card(Rank.SIX, Suit.HEARTS)
        six_h_b = Card(Rank.SIX, Suit.HEARTS)
        assert six_h_a == six_h_b and six_h_a is not six_h_b

        selected_cards = [six_h_a]

        # Simulate "uncheck" of the other 6H (six_h_b): must NOT remove six_h_a
        # (remove by identity only)
        for i, c in enumerate(selected_cards):
            if c is six_h_b:
                selected_cards.pop(i)
                break

        assert len(selected_cards) == 1 and selected_cards[0] is six_h_a

    def test_discard_with_two_identical_cards_in_hand(self):
        """Discarding when hand has two 6H: the selected card reference must
        succeed (engine removes by equality)."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.DISCARD

        six_h_1 = Card(Rank.SIX, Suit.HEARTS)
        six_h_2 = Card(Rank.SIX, Suit.HEARTS)
        other = Card(Rank.ACE, Suit.SPADES)
        player.hand.clear()
        player.hand.extend([six_h_1, six_h_2, other])

        # Discard one 6H (e.g. the one "selected" in the UI); engine removes by
        # equality so either ref works
        error = engine.discard(six_h_1)
        assert error is None
        assert len(player.hand) == 2
        assert six_h_2 in player.hand and other in player.hand
        assert len(engine.discard_pile) == 1
        assert (
            engine.discard_pile[0].rank == Rank.SIX
            and engine.discard_pile[0].suit == Suit.HEARTS
        )


class TestTurnProgression:
    """Test turn progression and phase transitions."""

    def test_turn_progression(self):
        """Test that turns progress correctly."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        initial_player_index = engine.current_player_index

        # Complete a full turn
        engine.draw_from_stock()
        engine.end_lay_down_phase()
        engine.discard(engine.get_current_player().hand[0])

        # Should move to next player
        assert engine.current_player_index == (initial_player_index + 1) % 4
        assert engine.turn_phase == TurnPhase.DRAW

    def test_end_lay_down_phase(self):
        """Test ending lay down phase."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        engine.draw_from_stock()
        assert engine.turn_phase == TurnPhase.LAY_DOWN

        engine.end_lay_down_phase()
        assert engine.turn_phase == TurnPhase.DISCARD


class TestKnockTypes:
    """Test different knock types (direct, indirect, final)."""

    def test_direct_knock(self):
        """Test direct knock (empty hand during lay down phase)."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Lay down all cards except one
        while len(player.hand) > 1:
            card = player.hand[0]
            player.remove_card(card)

        # Move to discard phase first
        engine.end_lay_down_phase()
        assert engine.turn_phase == TurnPhase.DISCARD

        # Discard last card (should trigger indirect knock, not direct)
        # For direct knock, we need to discard during LAY_DOWN phase
        # Let's simulate by manually checking the knock logic
        last_card = player.hand[0]
        player.remove_card(last_card)
        engine.discard_pile.append(last_card)

        # Manually trigger knock logic
        if len(player.hand) == 0:
            engine._determine_knock_type(player)
            # Set phase back to LAY_DOWN to simulate direct knock
            engine.turn_phase = TurnPhase.LAY_DOWN
            engine._process_knock(player, KnockType.DIRECT)

        assert player.has_dead_hand
        assert len(player.hand) == 11  # Should get dead hand cards
        assert engine.turn_phase == TurnPhase.LAY_DOWN

    def test_indirect_knock(self):
        """Test indirect knock (empty hand during discard phase)."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.DISCARD

        # Remove all cards except one
        while len(player.hand) > 1:
            card = player.hand[0]
            player.remove_card(card)

        # Discard last card (should trigger indirect knock)
        last_card = player.hand[0]
        error = engine.discard(last_card)

        assert error is None
        assert not player.has_dead_hand
        # Should move to next player
        assert engine.current_player_index != 0 or engine.turn_phase == TurnPhase.DRAW

    def test_indirect_knock_receives_morto_on_next_turn(self):
        """After indirect knock (discard last card), player receives morto (11
        cards) when their turn comes again."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        knocker_index = engine.current_player_index
        player = engine.players[knocker_index]
        engine.turn_phase = TurnPhase.DISCARD
        while len(player.hand) > 1:
            player.remove_card(player.hand[0])
        last_card = player.hand[0]
        error = engine.discard(last_card)
        assert error is None
        assert len(player.hand) == 0
        # Advance turn until it's the knocker's turn again (3 full turns for 4 players)
        for _ in range(3):
            engine._next_turn()
        assert engine.current_player_index == knocker_index
        assert player.has_dead_hand
        assert len(player.hand) == 11

    def test_final_knock(self):
        """Test final knock (empty hand when already has dead hand)."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        player.has_dead_hand = True
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Remove all cards
        while player.hand:
            card = player.hand[0]
            player.remove_card(card)

        # Try to discard (should trigger final knock)
        # Since hand is empty, we need to simulate the discard
        engine.turn_phase = TurnPhase.DISCARD
        # Manually trigger the knock logic
        if len(player.hand) == 0:
            knock_type = engine._determine_knock_type(player)
            engine._process_knock(player, knock_type)

        assert engine.game_over

    def test_cannot_finish_without_clean_canastra(self):
        """Final knock (or direct with morto) is rejected without a clean canastra."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        player = engine.get_current_player()
        player.has_dead_hand = True
        engine.turn_phase = TurnPhase.DISCARD
        # Only a dirty canastra (7 cards with wildcard), no clean canastra
        dirty_cards = [
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.JOKER),
            Card(Rank.SIX, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.HEARTS),
            Card(Rank.NINE, Suit.HEARTS),
        ]
        game = Game(GameType.SEQUENCE, dirty_cards, Suit.HEARTS)
        player.games.append(game)
        player.hand = [Card(Rank.ACE, Suit.SPADES)]

        error = engine.discard(player.hand[0])
        assert error is not None
        assert "canastra limpa" in error
        assert not engine.game_over
        assert len(player.hand) == 1

    def test_can_finish_with_clean_canastra(self):
        """Final knock is allowed when team has a clean canastra."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        player = engine.get_current_player()
        player.has_dead_hand = True
        engine.turn_phase = TurnPhase.DISCARD
        clean_cards = [
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SIX, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.HEARTS),
            Card(Rank.NINE, Suit.HEARTS),
        ]
        game = Game(GameType.SEQUENCE, clean_cards, Suit.HEARTS)
        player.games.append(game)
        player.hand = [Card(Rank.ACE, Suit.SPADES)]

        error = engine.discard(player.hand[0])
        assert error is None
        assert engine.game_over


class TestPointCalculation:
    """Test point calculation."""

    def test_game_point_value(self):
        """Test point value of games."""
        # Regular game (3 cards) - valid consecutive sequence
        game = Game(
            GameType.SEQUENCE,
            [
                Card(Rank.THREE, Suit.HEARTS),
                Card(Rank.FOUR, Suit.HEARTS),
                Card(Rank.FIVE, Suit.HEARTS),
            ],
            Suit.HEARTS,
        )
        assert game.point_value == 30  # 3 * 10

        # Canastra (7 cards) - all natural cards (no 2s or jokers)
        canastra_cards = [
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
            Card(Rank.SIX, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.HEARTS),
            Card(Rank.NINE, Suit.HEARTS),
        ]
        clean_canastra = Game(GameType.SEQUENCE, canastra_cards, Suit.HEARTS)
        assert clean_canastra.is_clean_canastra
        assert clean_canastra.point_value == 270  # 7 * 10 + 200

        # Dirty canastra (with wildcard)
        dirty_cards = canastra_cards.copy()
        dirty_cards[2] = Card(Rank.JOKER)  # Replace one with joker
        dirty_canastra = Game(GameType.SEQUENCE, dirty_cards, Suit.HEARTS)
        assert dirty_canastra.is_dirty_canastra
        assert dirty_canastra.point_value == 170  # 7 * 10 + 100

    def test_final_points_calculation(self):
        """Test final points calculation."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        # Get players from the same team
        team_0_players = [p for p in engine.players if p.team == 0]
        player = team_0_players[0]
        partner = team_0_players[1]

        # Set current player and lay down some games
        engine.current_player_index = engine.players.index(player)
        engine.turn_phase = TurnPhase.LAY_DOWN
        sequence_cards = [
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
        ]
        for card in sequence_cards:
            player.add_card(card)
        error = engine.lay_down_sequence(Suit.HEARTS, sequence_cards)
        assert error is None

        # End game
        engine.game_over = True
        engine._calculate_final_points()

        # Both players on same team should have same points (team points)
        # The calculation should assign the same team_points to all players on the team
        assert player.points == partner.points, (
            f"Players on same team should have same points, but got "
            f"{player.points} and {partner.points}"
        )
        # Points should be calculated as team total
        assert isinstance(player.points, int)

    def test_get_team_live_points(self):
        """Team live points = sum(jogos) - sum(mão) for all players on that team."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        team_0_players = [p for p in engine.players if p.team == 0]
        team_1_players = [p for p in engine.players if p.team == 1]
        player0 = team_0_players[0]
        player1 = team_0_players[1]

        engine.current_player_index = engine.players.index(player0)
        engine.turn_phase = TurnPhase.LAY_DOWN
        seq_cards = [
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
        ]
        for c in seq_cards:
            player0.add_card(c)
        engine.lay_down_sequence(Suit.HEARTS, seq_cards)
        # Team 0 has one game worth 30 (3 cards * 10).
        # Hands: partner has 11 cards (unknown), player0 has rest
        live_0 = engine.get_team_live_points(0)
        live_1 = engine.get_team_live_points(1)
        assert isinstance(live_0, int)
        assert isinstance(live_1, int)
        # Team 0 has 30 from the sequence; minus hand values (positive card values)
        assert live_0 == 30 - player0.get_hand_value() - player1.get_hand_value()
        assert live_1 == 0 - sum(p.get_hand_value() for p in team_1_players)


class TestGameValidation:
    """Test game validation logic."""

    def test_can_form_sequence(self):
        """Test can_form_sequence function."""
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.THREE, Suit.HEARTS),
        ]
        assert can_form_sequence(cards, Suit.HEARTS)

        # Invalid sequence
        invalid_cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
        ]
        assert not can_form_sequence(invalid_cards, Suit.HEARTS)

    def test_can_form_triple(self):
        """Test can_form_triple function."""
        cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.CLUBS),
        ]
        assert can_form_triple(cards)

        # Invalid triple (wrong rank)
        invalid_cards = [
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FOUR, Suit.DIAMONDS),
            Card(Rank.FOUR, Suit.CLUBS),
        ]
        assert not can_form_triple(invalid_cards)


class TestCompleteGameFlow:
    """Test complete game flow scenarios."""

    def test_complete_turn_flow(self):
        """Test a complete turn from draw to discard."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        initial_hand_size = len(player.hand)

        # Draw phase
        assert engine.turn_phase == TurnPhase.DRAW
        engine.draw_from_stock()
        assert len(player.hand) == initial_hand_size + 1
        assert engine.turn_phase == TurnPhase.LAY_DOWN

        # Lay down phase (skip for now)
        engine.end_lay_down_phase()
        assert engine.turn_phase == TurnPhase.DISCARD

        # Discard phase
        card_to_discard = player.hand[0]
        index_before = engine.current_player_index
        engine.discard(card_to_discard)
        assert len(player.hand) == initial_hand_size
        assert engine.turn_phase == TurnPhase.DRAW
        assert (
            engine.current_player_index == (index_before + 1) % 4
        )  # Next player's turn

    def test_lay_down_and_add_to_game(self):
        """Test laying down a game and adding cards to it."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Lay down valid sequence
        sequence_cards = [
            Card(Rank.THREE, Suit.HEARTS),
            Card(Rank.FOUR, Suit.HEARTS),
            Card(Rank.FIVE, Suit.HEARTS),
        ]
        for card in sequence_cards:
            player.add_card(card)

        error = engine.lay_down_sequence(Suit.HEARTS, sequence_cards)
        assert error is None
        assert len(player.games) == 1
        assert len(player.games[0].cards) == 3

        # Add more cards
        for rank in [Rank.SIX, Rank.SEVEN]:
            card = Card(rank, Suit.HEARTS)
            player.add_card(card)
            error = engine.add_to_game(0, card)
            assert error is None

        assert len(player.games[0].cards) == 5

    def test_multiple_games_per_player(self):
        """Test that a player can lay down multiple games."""
        engine = Engine(num_players=4)
        engine.start_new_game()

        player = engine.get_current_player()
        engine.turn_phase = TurnPhase.LAY_DOWN

        # Lay down first game (sequence)
        seq_cards = [
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.TWO, Suit.HEARTS),
            Card(Rank.THREE, Suit.HEARTS),
        ]
        for card in seq_cards:
            player.add_card(card)
        engine.lay_down_sequence(Suit.HEARTS, seq_cards)

        # Lay down second game (triple)
        triple_cards = [
            Card(Rank.ACE, Suit.CLUBS),
            Card(Rank.ACE, Suit.DIAMONDS),
            Card(Rank.ACE, Suit.SPADES),
        ]
        for card in triple_cards:
            player.add_card(card)
        engine.lay_down_triple(triple_cards)

        assert len(player.games) == 2


class TestAIISMCTS:
    """Tests for IS-MCTS AI: legal actions, apply action,
    determinization, play_ai_turn."""

    def test_discard_danger_joker_rates_higher(self):
        """Discarding a joker has higher danger than discarding a non-joker."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 0
        engine.turn_phase = TurnPhase.DISCARD
        engine.players[0].hand = [Card(Rank.JOKER), Card(Rank.FOUR, Suit.SPADES)]
        danger_joker = _discard_danger(engine, ("discard", 0))
        danger_low = _discard_danger(engine, ("discard", 1))
        assert danger_joker == 1.0
        assert danger_low == 0.0

    def test_discard_danger_matching_pile_top(self):
        """Discarding a card that matches the pile top is rated
        more dangerous than a non-match."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 0
        engine.turn_phase = TurnPhase.DISCARD
        engine.players[0].hand = [
            Card(Rank.FOUR, Suit.DIAMONDS),
            Card(Rank.SEVEN, Suit.HEARTS),
        ]
        engine.discard_pile.append(Card(Rank.FOUR, Suit.CLUBS))
        # discard 4♦, pile top 4♣
        danger_match = _discard_danger(engine, ("discard", 0))
        danger_safe = _discard_danger(engine, ("discard", 1))   # discard 7♥
        assert danger_match >= 0.5 and danger_safe == 0.0

    def test_discard_danger_addable_card_high_danger(self):
        """Discarding a card we can add to our team's meld is rated dangerous
        (avoid 5♣ blunder)."""
        from game import Game, GameType

        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 0
        engine.turn_phase = TurnPhase.DISCARD
        # We have 5♣ in hand; our team has sequence 6♣-7♣-8♣ (can take 5♣)
        seq = [
            Card(Rank.SIX, Suit.CLUBS),
            Card(Rank.SEVEN, Suit.CLUBS),
            Card(Rank.EIGHT, Suit.CLUBS),
        ]
        engine.players[0].games.append(
            Game(GameType.SEQUENCE, list(seq), Suit.CLUBS),
        )
        engine.players[0].hand = [
            Card(Rank.FIVE, Suit.CLUBS),
            Card(Rank.KING, Suit.SPADES),
        ]
        danger_discard_addable = _discard_danger(engine, ("discard", 0))
        danger_discard_other = _discard_danger(engine, ("discard", 1))
        assert danger_discard_addable >= 0.9
        assert danger_discard_other == 0.0

    def test_early_trinca_penalty(self):
        """Laying a triple in early game gets a penalty; with wildcards
        the penalty is higher."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 0
        engine.turn_phase = TurnPhase.LAY_DOWN
        while len(engine.stock) <= 50:
            engine.stock.append(Card(Rank.ACE, Suit.CLUBS))
        assert _is_early_game(engine)
        # Early triple with joker
        action_wild = (
            "lay_triple",
            [
                (Rank.ACE, Suit.CLUBS),
                (Rank.ACE, Suit.DIAMONDS),
                (Rank.JOKER, Suit.JOKER),
            ],
        )
        assert _early_trinca_penalty(engine, action_wild) == 50.0
        # Early triple without wildcards
        action_natural = (
            "lay_triple",
            [
                (Rank.ACE, Suit.CLUBS),
                (Rank.ACE, Suit.DIAMONDS),
                (Rank.ACE, Suit.HEARTS),
            ],
        )
        assert _early_trinca_penalty(engine, action_natural) == 25.0
        # Non-triple action
        assert _early_trinca_penalty(engine, ("discard", 0)) == 0.0

    def test_get_legal_actions_draw_with_stock(self):
        """In DRAW phase with stock, legal actions include draw_stock."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 1
        assert engine.turn_phase == TurnPhase.DRAW
        actions = _get_legal_actions(engine)
        assert ("draw_stock",) in actions
        assert len(actions) >= 1

    def test_get_legal_actions_draw_with_stock_and_discard(self):
        """In DRAW with stock and discard pile, both draw actions are legal."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 1
        engine.discard_pile = [Card(Rank.ACE, Suit.HEARTS)]
        actions = _get_legal_actions(engine)
        assert ("draw_stock",) in actions
        assert ("draw_discard",) in actions

    def test_get_legal_actions_discard_phase(self):
        """In DISCARD phase, each card in hand is a legal discard action."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        player = engine.get_current_player()
        engine.draw_from_stock()
        engine.end_lay_down_phase()
        assert engine.turn_phase == TurnPhase.DISCARD
        actions = _get_legal_actions(engine)
        assert len(actions) == len(player.hand)
        assert all(a[0] == "discard" and isinstance(a[1], int) for a in actions)

    def test_get_legal_actions_empty_draw_returns_empty(self):
        """In DRAW with no stock and no discard, legal actions are empty."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 1
        while engine.stock:
            engine.stock.pop()
        engine.discard_pile = []
        actions = _get_legal_actions(engine)
        assert actions == []

    def test_apply_action_draw_stock(self):
        """Applying draw_stock adds a card to hand and moves to LAY_DOWN."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 1
        player = engine.get_current_player()
        hand_size_before = len(player.hand)
        ok = _apply_action(engine, ("draw_stock",))
        assert ok
        assert engine.turn_phase == TurnPhase.LAY_DOWN
        assert len(player.hand) == hand_size_before + 1

    def test_apply_action_end_lay_down(self):
        """Applying end_lay_down moves to DISCARD phase."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.draw_from_stock()
        assert engine.turn_phase == TurnPhase.LAY_DOWN
        ok = _apply_action(engine, ("end_lay_down",))
        assert ok
        assert engine.turn_phase == TurnPhase.DISCARD

    def test_apply_action_discard(self):
        """Applying discard removes one card and advances turn."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.draw_from_stock()
        _apply_action(engine, ("end_lay_down",))
        player = engine.get_current_player()
        hand_size = len(player.hand)
        ok = _apply_action(engine, ("discard", 0))
        assert ok
        assert len(engine.get_current_player().hand) == hand_size - 1
        assert len(engine.discard_pile) == 1

    def test_determinize_preserves_observer_hand_and_refills_stock(self):
        """Determinization keeps observer hand unchanged and refills stock size."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 1
        observer = engine.get_current_player()
        hand_cards = [(c.rank, c.suit) for c in observer.hand]
        n_stock = len(engine.stock)
        rng = __import__("random").Random(42)
        clone = _determinize(engine, 1, rng)
        assert len(clone.players[1].hand) == len(observer.hand)
        assert [(c.rank, c.suit) for c in clone.players[1].hand] == hand_cards
        assert len(clone.stock) == n_stock

    @mock.patch("game_helpers.AI_TURN_ROLLOUTS", 2)
    def test_play_ai_turn_draw_phase(self):
        """play_ai_turn in DRAW phase performs a draw and advances phase."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 1
        player = engine.get_current_player()
        hand_size_before = len(player.hand)
        play_ai_turn(engine)
        assert len(player.hand) == hand_size_before + 1
        assert engine.turn_phase == TurnPhase.LAY_DOWN

    @mock.patch("game_helpers.AI_TURN_ROLLOUTS", 2)
    def test_play_ai_turn_discard_phase(self):
        """play_ai_turn in DISCARD phase discards a card."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.draw_from_stock()
        engine.end_lay_down_phase()
        player = engine.get_current_player()
        hand_size = len(player.hand)
        discard_size_before = len(engine.discard_pile)
        play_ai_turn(engine)
        assert len(player.hand) == hand_size - 1
        assert len(engine.discard_pile) == discard_size_before + 1

    def test_play_ai_turn_no_legal_actions_ends_game(self):
        """When no legal actions (empty stock and discard),
        play_ai_turn ends the game."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 1
        while engine.stock:
            engine.stock.pop()
        engine.discard_pile = []
        assert not engine.game_over
        play_ai_turn(engine)
        assert engine.game_over
        winner_team, team_scores = engine.get_winner_message()
        assert len(team_scores) == 2

    @mock.patch("game_helpers.ISMCTS_COUNTERFACTUAL_ROLLOUTS", 2)
    def test_get_counterfactual_action_on_human_turn_returns_suggestion(self):
        """When it's the human's turn, get_counterfactual_action
        returns an action and description."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 0
        assert engine.get_current_player().is_human
        action, desc = get_counterfactual_action(engine)
        assert action is not None
        assert desc != ""
        assert "Comprar" in desc or "Monte" in desc or "Lixo" in desc

    def test_get_counterfactual_action_on_ai_turn_returns_empty(self):
        """When it's not the human's turn, counterfactual returns (None, '')."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 1
        assert not engine.get_current_player().is_human
        action, desc = get_counterfactual_action(engine)
        assert action is None
        assert desc == ""

    def test_play_ai_turn_completes_quickly(self):
        """IS-MCTS AI turn (abstraction + progressive widening + fast rollout)
        finishes in under 2s."""
        engine = Engine(num_players=4)
        engine.start_new_game()
        engine.current_player_index = 1
        assert engine.turn_phase == TurnPhase.DRAW
        start = time.perf_counter()
        play_ai_turn(engine)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"play_ai_turn took {elapsed:.2f}s (expected < 2s)"
        assert engine.turn_phase == TurnPhase.LAY_DOWN
        assert len(engine.get_current_player().hand) == 12

    @mock.patch("game_helpers.AI_TURN_ROLLOUTS", 2)
    @mock.patch("game_helpers.AI_TURN_ROLLOUT_MAX_STEPS", 3)
    @mock.patch("game_helpers.ISMCTS_COUNTERFACTUAL_ROLLOUTS", 8)
    @mock.patch("game_helpers.COUNTERFACTUAL_ROLLOUT_MAX_STEPS", 6)
    def test_counterfactual_suggestion_takes_longer_but_still_reasonable(self):
        """Sugestão do bot (stronger MCTS) with more rollouts completes
        within a reasonable time. With patched rollouts, suggestion does
        more work than in-game AI and stays under 2s."""
        engine_cf = Engine(num_players=4)
        engine_cf.start_new_game()
        engine_cf.current_player_index = 0
        engine_cf.discard_pile.append(Card(Rank.ACE, Suit.HEARTS))
        assert engine_cf.get_current_player().is_human
        assert len(_get_legal_actions(engine_cf)) >= 2

        start_cf = time.perf_counter()
        action, desc = get_counterfactual_action(engine_cf)
        cf_elapsed = time.perf_counter() - start_cf

        assert action is not None and desc != ""
        assert cf_elapsed < 2.0, (
            f"Sugestão do bot took {cf_elapsed:.2f}s "
            "(expected < 2s with patched rollouts)"
        )
