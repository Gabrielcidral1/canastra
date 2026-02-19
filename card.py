"""Card representation and utilities for Canastra game."""

from enum import Enum
from typing import List, Dict, Tuple


class Suit(Enum):
    """Card suits."""
    CLUBS = "C"
    DIAMONDS = "D"
    HEARTS = "H"
    SPADES = "S"
    JOKER = "J"


class Rank(Enum):
    """Card ranks."""
    ACE = "A"
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    JOKER = "J"


class Card:
    """Represents a playing card."""
    
    def __init__(self, rank: Rank, suit: Suit = None):
        """Initialize a card.
        
        Args:
            rank: The rank of the card
            suit: The suit (None for jokers)
        """
        self.rank = rank
        self.suit = suit if suit is not None else Suit.JOKER
        
    @property
    def is_wild(self) -> bool:
        """Check if card can be used as wild (joker or 2).
        
        Note: 2 can also be used as natural, so this checks if it CAN be wild.
        """
        return self.rank == Rank.JOKER or self.rank == Rank.TWO
    
    @property
    def is_natural(self) -> bool:
        """Check if card is natural (not a joker).
        
        Note: 2 can be used as natural, so it's considered natural here.
        """
        return self.rank != Rank.JOKER
    
    @property
    def can_be_natural_two(self) -> bool:
        """Check if this is a 2 that can be used as natural."""
        return self.rank == Rank.TWO
    
    @property
    def point_value(self) -> int:
        """Get the point value of this card (all cards have same value)."""
        return 10
    
    def __eq__(self, other):
        """Check equality."""
        if not isinstance(other, Card):
            return False
        return self.rank == other.rank and self.suit == other.suit
    
    def __hash__(self):
        """Hash for use in sets/dicts."""
        return hash((self.rank, self.suit))
    
    def __repr__(self):
        """String representation."""
        if self.rank == Rank.JOKER:
            return "Joker"
        if self.rank == Rank.TWO:
            return f"2{self.suit.value}"
        return f"{self.rank.value}{self.suit.value}"
    
    @classmethod
    def from_string(cls, card_str: str) -> 'Card':
        """Parse a card from string format (e.g., 'AS', '2C', 'Joker').
        
        Args:
            card_str: String representation of card
            
        Returns:
            Card object
        """
        card_str = card_str.strip().upper()
        
        if card_str == "JOKER" or card_str == "J":
            return cls(Rank.JOKER)
        
        if len(card_str) < 2:
            raise ValueError(f"Invalid card format: {card_str}")
        
        rank_str = card_str[:-1]
        suit_str = card_str[-1]
        
        # Map rank strings
        rank_map = {
            "A": Rank.ACE, "2": Rank.TWO, "3": Rank.THREE, "4": Rank.FOUR,
            "5": Rank.FIVE, "6": Rank.SIX, "7": Rank.SEVEN, "8": Rank.EIGHT,
            "9": Rank.NINE, "10": Rank.TEN, "J": Rank.JACK,
            "Q": Rank.QUEEN, "K": Rank.KING
        }
        
        suit_map = {
            "C": Suit.CLUBS, "D": Suit.DIAMONDS,
            "H": Suit.HEARTS, "S": Suit.SPADES
        }
        
        if rank_str not in rank_map:
            raise ValueError(f"Invalid rank: {rank_str}")
        if suit_str not in suit_map:
            raise ValueError(f"Invalid suit: {suit_str}")
        
        return cls(rank_map[rank_str], suit_map[suit_str])


def parse_hand(hand_str: str) -> List[Card]:
    """Parse a hand from string format.
    
    Args:
        hand_str: Comma-separated card strings (e.g., "AS,2C,KD,Joker")
        
    Returns:
        List of Card objects
    """
    if not hand_str.strip():
        return []
    
    cards = []
    for card_str in hand_str.split(","):
        cards.append(Card.from_string(card_str.strip()))
    return cards

