"""Canastra game rules."""

from .card import (
    JOKER_DISPLAY_NAME_PT,
    RANK_ORDER_SEQUENCE,
    SUIT_NAMES_PT,
    Card,
    Rank,
    Suit,
)
from .constants import GameRules, GameType, GameValidation


def is_wildcard(card: Card) -> bool:
    """Check if a card is a wildcard (2 or Joker)."""
    return card.rank == Rank.TWO or card.rank == Rank.JOKER


def _is_natural_in_sequence(card: Card, suit: Suit) -> bool:
    """True if card counts as natural in this sequence (same suit, and 2 of suit
    counts as natural)."""
    return card.suit == suit and (not is_wildcard(card) or card.rank == Rank.TWO)


def counts_as_wildcard_in_sequence(card: Card, suit: Suit) -> bool:
    """True if card counts toward the one-wildcard limit (Joker or 2 of
    another suit)."""
    return is_wildcard(card) and not (card.rank == Rank.TWO and card.suit == suit)


def card_display_pt(card: Card) -> str:
    """Return card description in Portuguese with full suit name (e.g. '2 de Paus')."""
    if card.rank == Rank.JOKER:
        return JOKER_DISPLAY_NAME_PT
    suit_name = SUIT_NAMES_PT.get(card.suit, card.suit.value)
    rank_str = card.rank.value if card.rank != Rank.TWO else "2"
    return f"{rank_str} de {suit_name}"


class Game:
    """Represents a game laid down on the table (sequence or triple)."""

    def __init__(
        self,
        game_type: GameType,
        cards: list[Card],
        suit: Suit | None = None,
        *,
        _skip_validate: bool = False,
    ):
        self.game_type = game_type
        self.cards = cards.copy()
        self.suit = suit
        if not _skip_validate:
            self._validate()

    def _validate(self):
        """Validate that the game is legal."""
        if len(self.cards) < GameRules.MIN_MELD_CARDS:
            raise ValueError(GameValidation.GAME_MIN_CARDS)

        if self.game_type == GameType.SEQUENCE:
            if not self.suit:
                raise ValueError(GameValidation.SEQUENCE_NEEDS_SUIT)
            self._validate_sequence()
        elif self.game_type == GameType.TRIPLE:
            self._validate_triple()

    def _wildcard_can_fill_sequence(self, ranks_sorted: list[Rank]) -> bool:
        """True if one wildcard can fill the gaps in these ranks
        (normal or A-at-end)."""
        if self._sequence_total_gaps(ranks_sorted) <= 1:
            return True
        if Rank.ACE not in ranks_sorted or Rank.KING in ranks_sorted:
            return False
        other_ranks = [r for r in ranks_sorted if r != Rank.ACE]
        if not other_ranks:
            return False
        # Ace-at-end wrap only valid when highest natural is 10 or above (index 9+)
        highest_rank = max(other_ranks, key=lambda r: self._get_rank_index(r))
        highest_idx = self._get_rank_index(highest_rank)
        min_idx_ace_at_end = RANK_ORDER_SEQUENCE.index(Rank.TEN)
        return highest_idx >= min_idx_ace_at_end

    def _validate_sequence(self):
        """Validate sequence of the same suit (2 of the sequence suit counts
        as natural)."""
        wildcards = [
            c for c in self.cards if counts_as_wildcard_in_sequence(c, self.suit)
        ]
        if len(wildcards) > 1:
            raise ValueError(GameValidation.ONLY_ONE_WILDCARD)

        natural_cards = [c for c in self.cards if _is_natural_in_sequence(c, self.suit)]
        if len(natural_cards) < GameRules.MIN_NATURAL_CARDS:
            raise ValueError(GameValidation.SEQUENCE_NEEDS_TWO_NATURAL)

        for card in self.cards:
            if not is_wildcard(card) and card.suit != self.suit:
                raise ValueError(GameValidation.SEQUENCE_SAME_SUIT)

        ranks = [c.rank for c in natural_cards]
        if len(ranks) != len(set(ranks)):
            raise ValueError(GameValidation.SEQUENCE_NO_DUPLICATES)

        if len(wildcards) == 1:
            if len(ranks) < GameRules.MIN_NATURAL_CARDS:
                raise ValueError(GameValidation.SEQUENCE_WILDCARD_NEEDS_TWO)
            ranks_sorted = self._sort_ranks_for_sequence(ranks)
            if not self._wildcard_can_fill_sequence(ranks_sorted):
                raise ValueError(GameValidation.WILDCARD_ONE_GAP)
            return

        ranks_sorted = self._sort_ranks_for_sequence(ranks)
        if self._is_sequence(ranks_sorted):
            return
        twos_of_suit = [
            c for c in self.cards if c.rank == Rank.TWO and c.suit == self.suit
        ]
        if len(twos_of_suit) == 1:
            ranks_without_2 = [r for r in ranks if r != Rank.TWO]
            if len(ranks_without_2) >= GameRules.MIN_NATURAL_CARDS:
                other_sorted = self._sort_ranks_for_sequence(ranks_without_2)
                if self._sequence_total_gaps(other_sorted) <= 1:
                    return
        raise ValueError(GameValidation.CARDS_NOT_VALID_SEQUENCE)

    def _get_rank_index(self, rank: Rank) -> int:
        """Return the index of the rank in sequence order."""
        return RANK_ORDER_SEQUENCE.index(rank)

    def _validate_triple(self):
        """Validate triple of the same number."""
        wildcards = [c for c in self.cards if is_wildcard(c)]
        if len(wildcards) > 1:
            raise ValueError(GameValidation.ONLY_ONE_WILDCARD)

        ranks = [c.rank for c in self.cards if not is_wildcard(c)]
        if len(set(ranks)) > 1:
            raise ValueError(GameValidation.TRIPLE_SAME_NUMBER)

        if len(ranks) < GameRules.MIN_NATURAL_CARDS:
            raise ValueError(GameValidation.TRIPLE_TWO_NATURAL)

        allowed_ranks = {Rank.ACE, Rank.THREE, Rank.KING}
        if ranks and ranks[0] not in allowed_ranks:
            raise ValueError(GameValidation.TRIPLE_ONLY_ACE_THREE_KING)

    def _sort_ranks_for_sequence(self, ranks: list[Rank]) -> list[Rank]:
        """Sort ranks in sequence order (Ace high: 2..K, A)."""
        return sorted(ranks, key=lambda r: RANK_ORDER_SEQUENCE.index(r))

    def _is_sequence(self, ranks: list[Rank]) -> bool:
        """Check if ranks form a sequence."""
        if len(ranks) < 2:
            return False

        for i in range(len(ranks) - 1):
            current_idx = RANK_ORDER_SEQUENCE.index(ranks[i])
            next_idx = RANK_ORDER_SEQUENCE.index(ranks[i + 1])
            # Wrap: K→A and A→2 are consecutive (Ace high: 2..K,A)
            if ranks[i] == Rank.KING and ranks[i + 1] == Rank.ACE:
                continue
            if ranks[i] == Rank.ACE and ranks[i + 1] == Rank.TWO:
                continue
            # Run A,2,3,...,k sorted as [2,...,k,A]: last step →A is wrap (Ace low)
            if ranks[i + 1] == Rank.ACE and ranks[0] == Rank.TWO:
                continue
            if next_idx != current_idx + 1:
                return False

        return True

    def _sequence_total_gaps(self, ranks_sorted: list[Rank]) -> int:
        """Total gap count between consecutive ranks (for wildcard fill check)."""
        if len(ranks_sorted) < 2:
            return 0
        total = 0
        for i in range(len(ranks_sorted) - 1):
            current_idx = self._get_rank_index(ranks_sorted[i])
            next_idx = self._get_rank_index(ranks_sorted[i + 1])
            if ranks_sorted[i] == Rank.KING and ranks_sorted[i + 1] == Rank.ACE:
                continue
            if ranks_sorted[i] == Rank.ACE and ranks_sorted[i + 1] == Rank.TWO:
                continue
            if ranks_sorted[i + 1] == Rank.ACE and ranks_sorted[0] == Rank.TWO:
                continue
            total += next_idx - current_idx - 1
        return total

    @property
    def is_canastra(self) -> bool:
        """Check if it's a canastra (7+ cards)."""
        return len(self.cards) >= GameRules.CANASTRA_MIN_CARDS

    @property
    def is_clean_canastra(self) -> bool:
        """Clean canastra: 7+ cards, no Joker and no 2 of another suit.
        A 2 of the sequence suit counts as natural (can assume the value 2)."""
        if not self.is_canastra:
            return False
        if self.game_type == GameType.SEQUENCE and self.suit:
            return not any(
                counts_as_wildcard_in_sequence(c, self.suit) for c in self.cards
            )
        return not any(is_wildcard(c) for c in self.cards)

    @property
    def is_dirty_canastra(self) -> bool:
        """Dirty canastra: 7+ cards with at least one wildcard (Joker or 2 of
        other suit). A 2 of the sequence suit filling a gap is dirty; it becomes
        clean when it assumes the value of 2."""
        if not self.is_canastra:
            return False
        if self.game_type == GameType.SEQUENCE and self.suit:
            return any(counts_as_wildcard_in_sequence(c, self.suit) for c in self.cards)
        return any(is_wildcard(c) for c in self.cards)

    @property
    def point_value(self) -> int:
        """Calculate point value of the game."""
        base = len(self.cards) * 10

        if self.is_clean_canastra:
            base += GameRules.CLEAN_CANASTRA_POINTS
        elif self.is_dirty_canastra:
            base += GameRules.DIRTY_CANASTRA_POINTS

        return base

    def _can_add_to_sequence(self, card: Card) -> bool:
        """Check if card can be added to this sequence game."""
        if counts_as_wildcard_in_sequence(card, self.suit):
            wildcards = [
                c for c in self.cards if counts_as_wildcard_in_sequence(c, self.suit)
            ]
            return len(wildcards) == 0
        if not _is_natural_in_sequence(card, self.suit):
            return False
        existing_natural_ranks = [
            c.rank for c in self.cards if _is_natural_in_sequence(c, self.suit)
        ]
        if card.rank in existing_natural_ranks:
            return False
        ranks = existing_natural_ranks + [card.rank]
        ranks_sorted = self._sort_ranks_for_sequence(ranks)
        if self._is_sequence(ranks_sorted):
            return True
        wildcards = [c for c in self.cards if is_wildcard(c)]
        if len(wildcards) != 1:
            return False
        twos_of_suit = [
            c for c in self.cards if c.rank == Rank.TWO and c.suit == self.suit
        ]
        if len(twos_of_suit) == 1:
            ranks_without_2 = [r for r in ranks if r != Rank.TWO]
            if len(ranks_without_2) >= 2:
                gaps = self._sequence_total_gaps(
                    self._sort_ranks_for_sequence(ranks_without_2)
                )
                if gaps <= 1:
                    return True
        return self._sequence_total_gaps(ranks_sorted) <= 1

    def _can_add_to_triple(self, card: Card) -> bool:
        """Check if card can be added to this triple game."""
        if is_wildcard(card):
            return len([c for c in self.cards if is_wildcard(c)]) == 0
        allowed_ranks = {Rank.ACE, Rank.THREE, Rank.KING}
        if card.rank not in allowed_ranks:
            return False
        ranks = [c.rank for c in self.cards if not is_wildcard(c)]
        if not ranks:
            return True
        return card.rank == ranks[0]

    def can_add(self, card: Card) -> bool:
        """Check if a card can be added to the game (2 of sequence suit counts
        as natural)."""
        if self.game_type == GameType.SEQUENCE:
            return self._can_add_to_sequence(card)
        if self.game_type == GameType.TRIPLE:
            return self._can_add_to_triple(card)
        return False

    def add_card(self, card: Card):
        """Add a card to the game."""
        if not self.can_add(card):
            raise ValueError(
                GameValidation.CANNOT_ADD_CARD_TO_GAME.format(
                    card=card_display_pt(card)
                )
            )
        self.cards.append(card)
        try:
            self._validate()
        except ValueError:
            self.cards.pop()
            raise


def can_form_sequence(cards: list[Card], suit: Suit) -> bool:
    """Check if cards can form a sequence of the specified suit."""
    if len(cards) < GameRules.MIN_MELD_CARDS:
        return False

    wildcards = [c for c in cards if is_wildcard(c)]
    if len(wildcards) > 1:
        return False

    natural_cards = [c for c in cards if not is_wildcard(c) and c.suit == suit]
    if len(natural_cards) < GameRules.MIN_NATURAL_CARDS:
        return False

    try:
        Game(GameType.SEQUENCE, cards, suit)
        return True
    except ValueError:
        return False


def can_form_triple(cards: list[Card]) -> bool:
    """Check if cards can form a triple."""
    if len(cards) < GameRules.MIN_MELD_CARDS:
        return False

    wildcards = [c for c in cards if is_wildcard(c)]
    if len(wildcards) > 1:
        return False

    natural_cards = [c for c in cards if not is_wildcard(c)]
    if len(natural_cards) < GameRules.MIN_NATURAL_CARDS:
        return False

    ranks = [c.rank for c in natural_cards]
    if len(set(ranks)) > 1:
        return False

    allowed_ranks = {Rank.ACE, Rank.THREE, Rank.KING}
    if ranks[0] not in allowed_ranks:
        return False

    try:
        Game(GameType.TRIPLE, cards)
        return True
    except ValueError:
        return False
