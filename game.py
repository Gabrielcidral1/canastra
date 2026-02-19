"""Canastra game rules."""

from typing import List, Optional, Tuple
from enum import Enum
from card import Card, Rank, Suit


class GameType(Enum):
    SEQUENCE = "sequencia"
    TRIPLE = "trinca"


class Game:
    """Represents a game laid down on the table (sequence or triple)."""
    
    def __init__(self, game_type: GameType, cards: List[Card], suit: Optional[Suit] = None):
        self.game_type = game_type
        self.cards = cards.copy()
        self.suit = suit
        self._validate()
    
    def _validate(self):
        """Validate that the game is legal."""
        if len(self.cards) < 3:
            raise ValueError("Game must have at least 3 cards")
        
        if self.game_type == GameType.SEQUENCE:
            if not self.suit:
                raise ValueError("Sequence needs a suit")
            self._validate_sequence()
        elif self.game_type == GameType.TRIPLE:
            self._validate_triple()
    
    def _validate_sequence(self):
        """Validate sequence of the same suit."""
        wildcards = [c for c in self.cards if c.rank == Rank.TWO]
        if len(wildcards) > 1:
            raise ValueError("Only one wildcard per game")
        
        has_wildcard = len(wildcards) == 1
        
        natural_cards = [c for c in self.cards if c.rank != Rank.TWO and c.suit == self.suit]
        if len(natural_cards) < 2:
            raise ValueError("Sequence needs at least 2 natural cards of the same suit")
        
        for card in self.cards:
            if card.rank != Rank.TWO and card.suit != self.suit:
                raise ValueError("All cards in sequence must be of the same suit")
        
        ranks = [c.rank for c in natural_cards]
        
        if has_wildcard:
            if len(ranks) < 2:
                raise ValueError("Sequence with wildcard needs at least 2 natural cards")
            ranks_sorted = self._sort_ranks_for_sequence(ranks)
            gaps = 0
            for i in range(len(ranks_sorted) - 1):
                current_idx = self._get_rank_index(ranks_sorted[i])
                next_idx = self._get_rank_index(ranks_sorted[i + 1])
                if Rank.ACE in ranks_sorted and Rank.KING in ranks_sorted:
                    if ranks_sorted[i] == Rank.KING and ranks_sorted[i + 1] == Rank.ACE:
                        continue
                gap = next_idx - current_idx - 1
                gaps += gap
            if gaps > 1:
                raise ValueError("Wildcard cannot fill more than one gap")
        else:
            ranks_sorted = self._sort_ranks_for_sequence(ranks)
            if not self._is_sequence(ranks_sorted):
                raise ValueError("Cards do not form a valid sequence")
    
    def _get_rank_index(self, rank: Rank) -> int:
        """Return the index of the rank in order."""
        rank_order = [Rank.ACE, Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE,
                     Rank.SIX, Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN,
                     Rank.JACK, Rank.QUEEN, Rank.KING]
        return rank_order.index(rank)
    
    def _validate_triple(self):
        """Validate triple of the same number."""
        wildcards = [c for c in self.cards if c.rank == Rank.TWO]
        if len(wildcards) > 1:
            raise ValueError("Only one wildcard per game")
        
        ranks = [c.rank for c in self.cards if c.rank != Rank.TWO]
        if len(set(ranks)) > 1:
            raise ValueError("Triple must have cards of the same number")
        
        if len(ranks) < 2:
            raise ValueError("Triple needs at least 2 natural cards of the same number")
        
        allowed_ranks = {Rank.ACE, Rank.THREE, Rank.KING}
        if ranks and ranks[0] not in allowed_ranks:
            raise ValueError("Trincas só podem ser feitas com Ás, 3 ou Rei")
    
    def _sort_ranks_for_sequence(self, ranks: List[Rank]) -> List[Rank]:
        """Sort ranks considering Ace before 2 or after K."""
        rank_order = [Rank.ACE, Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE, 
                     Rank.SIX, Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN,
                     Rank.JACK, Rank.QUEEN, Rank.KING]
        
        sorted_ranks = sorted(ranks, key=lambda r: rank_order.index(r))
        
        if Rank.ACE in ranks and Rank.KING in ranks:
            ace_pos = sorted_ranks.index(Rank.ACE)
            king_pos = sorted_ranks.index(Rank.KING)
            if ace_pos < king_pos:
                sorted_ranks = [r for r in sorted_ranks if r != Rank.ACE and r != Rank.KING]
                sorted_ranks.append(Rank.KING)
                sorted_ranks.append(Rank.ACE)
        
        return sorted_ranks
    
    def _is_sequence(self, ranks: List[Rank]) -> bool:
        """Check if ranks form a sequence."""
        if len(ranks) < 2:
            return False
        
        rank_order = [Rank.ACE, Rank.TWO, Rank.THREE, Rank.FOUR, Rank.FIVE,
                     Rank.SIX, Rank.SEVEN, Rank.EIGHT, Rank.NINE, Rank.TEN,
                     Rank.JACK, Rank.QUEEN, Rank.KING]
        
        for i in range(len(ranks) - 1):
            current_idx = rank_order.index(ranks[i])
            next_idx = rank_order.index(ranks[i + 1])
            
            if Rank.ACE in ranks and Rank.KING in ranks:
                if ranks[i] == Rank.KING and ranks[i + 1] == Rank.ACE:
                    continue
            
            if next_idx != current_idx + 1:
                return False
        
        return True
    
    @property
    def is_canastra(self) -> bool:
        """Check if it's a canastra (7+ cards)."""
        return len(self.cards) >= 7
    
    @property
    def is_clean_canastra(self) -> bool:
        """Check if it's a clean canastra (without wildcard)."""
        return self.is_canastra and not any(c.rank == Rank.TWO for c in self.cards)
    
    @property
    def is_dirty_canastra(self) -> bool:
        """Check if it's a dirty canastra (with wildcard)."""
        return self.is_canastra and any(c.rank == Rank.TWO for c in self.cards)
    
    @property
    def point_value(self) -> int:
        """Calculate point value of the game."""
        base = len(self.cards) * 10
        
        if self.is_clean_canastra:
            base += 200
        elif self.is_dirty_canastra:
            base += 100
        
        return base
    
    def can_add(self, card: Card) -> bool:
        """Check if a card can be added to the game."""
        if self.game_type == GameType.SEQUENCE:
            if card.rank == Rank.TWO:
                wildcards = [c for c in self.cards if c.rank == Rank.TWO]
                return len(wildcards) == 0
            
            if card.suit != self.suit:
                return False
            
            ranks = [c.rank for c in self.cards if c.rank != Rank.TWO]
            ranks.append(card.rank)
            ranks_sorted = self._sort_ranks_for_sequence(ranks)
            return self._is_sequence(ranks_sorted)
        
        elif self.game_type == GameType.TRIPLE:
            if card.rank == Rank.TWO:
                wildcards = [c for c in self.cards if c.rank == Rank.TWO]
                return len(wildcards) == 0
            
            allowed_ranks = {Rank.ACE, Rank.THREE, Rank.KING}
            if card.rank not in allowed_ranks:
                return False
            
            ranks = [c.rank for c in self.cards if c.rank != Rank.TWO]
            if not ranks:
                return True
            return card.rank == ranks[0]
        
        return False
    
    def add_card(self, card: Card):
        """Add a card to the game."""
        if not self.can_add(card):
            raise ValueError(f"Cannot add {card} to this game")
        self.cards.append(card)
        self._validate()


def can_form_sequence(cards: List[Card], suit: Suit) -> bool:
    """Check if cards can form a sequence of the specified suit."""
    if len(cards) < 3:
        return False
    
    wildcards = [c for c in cards if c.rank == Rank.TWO]
    if len(wildcards) > 1:
        return False
    
    natural_cards = [c for c in cards if c.rank != Rank.TWO and c.suit == suit]
    if len(natural_cards) < 2:
        return False
    
    try:
        game = Game(GameType.SEQUENCE, cards, suit)
        return True
    except ValueError:
        return False


def can_form_triple(cards: List[Card]) -> bool:
    """Check if cards can form a triple."""
    if len(cards) < 3:
        return False
    
    wildcards = [c for c in cards if c.rank == Rank.TWO]
    if len(wildcards) > 1:
        return False
    
    natural_cards = [c for c in cards if c.rank != Rank.TWO]
    if len(natural_cards) < 2:
        return False
    
    ranks = [c.rank for c in natural_cards]
    if len(set(ranks)) > 1:
        return False
    
    allowed_ranks = {Rank.ACE, Rank.THREE, Rank.KING}
    if ranks[0] not in allowed_ranks:
        return False
    
    try:
        game = Game(GameType.TRIPLE, cards)
        return True
    except ValueError:
        return False

