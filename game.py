"""Canastra game rules."""

from enum import Enum
from typing import Optional

from card import Card, Rank, Suit


class GameType(Enum):
    SEQUENCE = "sequencia"
    TRIPLE = "trinca"


def is_wildcard(card: Card) -> bool:
    """Check if a card is a wildcard (2 or Joker)."""
    return card.rank == Rank.TWO or card.rank == Rank.JOKER


def _is_natural_in_sequence(card: Card, suit: Suit) -> bool:
    """True if card counts as natural in this sequence (same suit, and 2 of suit
    counts as natural)."""
    return card.suit == suit and (not is_wildcard(card) or card.rank == Rank.TWO)


def _counts_as_wildcard_in_sequence(card: Card, suit: Suit) -> bool:
    """True if card counts toward the one-wildcard limit (Joker or 2 of
    another suit)."""
    return is_wildcard(card) and not (card.rank == Rank.TWO and card.suit == suit)


SUIT_NAMES_PT = {
    Suit.CLUBS: "Paus",
    Suit.DIAMONDS: "Ouros",
    Suit.HEARTS: "Copas",
    Suit.SPADES: "Espadas",
}


def card_display_pt(card: Card) -> str:
    """Return card description in Portuguese with full suit name (e.g. '2 de Paus')."""
    if card.rank == Rank.JOKER:
        return "Curinga"
    suit_name = SUIT_NAMES_PT.get(card.suit, card.suit.value)
    rank_str = card.rank.value if card.rank != Rank.TWO else "2"
    return f"{rank_str} de {suit_name}"


class Game:
    """Represents a game laid down on the table (sequence or triple)."""

    def __init__(
        self,
        game_type: GameType,
        cards: list[Card],
        suit: Optional[Suit] = None,
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
        if len(self.cards) < 3:
            raise ValueError("Game must have at least 3 cards")

        if self.game_type == GameType.SEQUENCE:
            if not self.suit:
                raise ValueError("Sequence needs a suit")
            self._validate_sequence()
        elif self.game_type == GameType.TRIPLE:
            self._validate_triple()

    def _validate_sequence(self):
        """Validate sequence of the same suit (2 of the sequence suit counts
        as natural)."""
        wildcards = [
            c for c in self.cards if _counts_as_wildcard_in_sequence(c, self.suit)
        ]
        if len(wildcards) > 1:
            raise ValueError("Only one wildcard per game")

        has_wildcard = len(wildcards) == 1

        natural_cards = [c for c in self.cards if _is_natural_in_sequence(c, self.suit)]
        if len(natural_cards) < 2:
            raise ValueError("Sequence needs at least 2 natural cards of the same suit")

        for card in self.cards:
            if not is_wildcard(card) and card.suit != self.suit:
                raise ValueError("All cards in sequence must be of the same suit")

        ranks = [c.rank for c in natural_cards]
        if len(ranks) != len(set(ranks)):
            raise ValueError("Sequência não pode ter cartas repetidas do mesmo naipe")

        if has_wildcard:
            if len(ranks) < 2:
                raise ValueError(
                    "Sequence with wildcard needs at least 2 natural cards"
                )
            ranks_sorted = self._sort_ranks_for_sequence(ranks)

            # Check if sequence can be formed with wildcard
            # Try both normal order and wrapped order (A at end)
            can_form = False

            # Normal order check
            gaps = 0
            for i in range(len(ranks_sorted) - 1):
                current_idx = self._get_rank_index(ranks_sorted[i])
                next_idx = self._get_rank_index(ranks_sorted[i + 1])
                if Rank.ACE in ranks_sorted and Rank.KING in ranks_sorted:
                    if ranks_sorted[i] == Rank.KING and ranks_sorted[i + 1] == Rank.ACE:
                        continue
                gap = next_idx - current_idx - 1
                gaps += gap
            if gaps <= 1:
                can_form = True

            # Wrapped order check (A at end) - for cases like A, wildcard, Q
            # or A, wildcard, J, etc. In Canastra, A can be at the end:
            # ...K, A, 2, 3...Q. Valid pattern: A (at end), wildcard (as 2),
            # and a high card (10, J, Q)
            if (
                not can_form
                and Rank.ACE in ranks_sorted
                and Rank.KING not in ranks_sorted
            ):
                # Get the highest rank that's not A
                other_ranks = [r for r in ranks_sorted if r != Rank.ACE]
                if other_ranks:
                    highest_rank = max(
                        other_ranks, key=lambda r: self._get_rank_index(r)
                    )
                    highest_idx = self._get_rank_index(highest_rank)

                    # If highest rank is 10, J, or Q, and we have A at end
                    # with wildcard, this forms a valid sequence in Canastra.
                    # Example: K, A, wildcard (as 2), 3, 4, 5, 6, 7, 8, 9, 10,
                    # J, Q. The wildcard fills the gap, allowing A (at end)
                    # to connect to the high card.
                    if highest_idx >= 9:  # 10 (9), J (10), Q (11)
                        can_form = True

            if not can_form:
                raise ValueError("Wildcard cannot fill more than one gap")
        else:
            ranks_sorted = self._sort_ranks_for_sequence(ranks)
            if self._is_sequence(ranks_sorted):
                return
            # 2 of the sequence suit can act as wildcard (e.g. 5H, 2H, 7H with 2H as 6)
            twos_of_suit = [
                c for c in self.cards if c.rank == Rank.TWO and c.suit == self.suit
            ]
            if len(twos_of_suit) == 1:
                ranks_without_2 = [r for r in ranks if r != Rank.TWO]
                if len(ranks_without_2) >= 2:
                    other_sorted = self._sort_ranks_for_sequence(ranks_without_2)
                    if self._sequence_total_gaps(other_sorted) <= 1:
                        return
            raise ValueError("Cards do not form a valid sequence")

    def _get_rank_index(self, rank: Rank) -> int:
        """Return the index of the rank in order."""
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
        return rank_order.index(rank)

    def _validate_triple(self):
        """Validate triple of the same number."""
        wildcards = [c for c in self.cards if is_wildcard(c)]
        if len(wildcards) > 1:
            raise ValueError("Only one wildcard per game")

        ranks = [c.rank for c in self.cards if not is_wildcard(c)]
        if len(set(ranks)) > 1:
            raise ValueError("Triple must have cards of the same number")

        if len(ranks) < 2:
            raise ValueError("Triple needs at least 2 natural cards of the same number")

        allowed_ranks = {Rank.ACE, Rank.THREE, Rank.KING}
        if ranks and ranks[0] not in allowed_ranks:
            raise ValueError("Trincas só podem ser feitas com Ás, 3 ou Rei")

    def _sort_ranks_for_sequence(self, ranks: list[Rank]) -> list[Rank]:
        """Sort ranks considering Ace before 2 or after K."""
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

        sorted_ranks = sorted(ranks, key=lambda r: rank_order.index(r))

        if Rank.ACE in ranks and Rank.KING in ranks:
            ace_pos = sorted_ranks.index(Rank.ACE)
            king_pos = sorted_ranks.index(Rank.KING)
            if ace_pos < king_pos:
                sorted_ranks = [
                    r for r in sorted_ranks if r != Rank.ACE and r != Rank.KING
                ]
                sorted_ranks.append(Rank.KING)
                sorted_ranks.append(Rank.ACE)

        return sorted_ranks

    def _is_sequence(self, ranks: list[Rank]) -> bool:
        """Check if ranks form a sequence."""
        if len(ranks) < 2:
            return False

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

        for i in range(len(ranks) - 1):
            current_idx = rank_order.index(ranks[i])
            next_idx = rank_order.index(ranks[i + 1])

            if Rank.ACE in ranks and Rank.KING in ranks:
                if ranks[i] == Rank.KING and ranks[i + 1] == Rank.ACE:
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
            if Rank.ACE in ranks_sorted and Rank.KING in ranks_sorted:
                if ranks_sorted[i] == Rank.KING and ranks_sorted[i + 1] == Rank.ACE:
                    continue
            total += next_idx - current_idx - 1
        return total

    @property
    def is_canastra(self) -> bool:
        """Check if it's a canastra (7+ cards)."""
        return len(self.cards) >= 7

    @property
    def is_clean_canastra(self) -> bool:
        """Check if it's a clean canastra (without wildcard)."""
        return self.is_canastra and not any(is_wildcard(c) for c in self.cards)

    @property
    def is_dirty_canastra(self) -> bool:
        """Check if it's a dirty canastra (with wildcard)."""
        return self.is_canastra and any(is_wildcard(c) for c in self.cards)

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
        """Check if a card can be added to the game (2 of sequence suit counts
        as natural)."""
        if self.game_type == GameType.SEQUENCE:
            if _counts_as_wildcard_in_sequence(card, self.suit):
                wildcards = [
                    c
                    for c in self.cards
                    if _counts_as_wildcard_in_sequence(c, self.suit)
                ]
                return len(wildcards) == 0

            if not _is_natural_in_sequence(card, self.suit):
                return False
            existing_natural_ranks = [
                c.rank for c in self.cards if _is_natural_in_sequence(c, self.suit)
            ]
            if card.rank in existing_natural_ranks:
                return False  # sequence cannot have duplicate ranks

            ranks = existing_natural_ranks + [card.rank]
            ranks_sorted = self._sort_ranks_for_sequence(ranks)
            if self._is_sequence(ranks_sorted):
                return True
            # With one wildcard in the game, one gap is allowed
            wildcards = [c for c in self.cards if is_wildcard(c)]
            if len(wildcards) == 1:
                # If the wildcard is 2 of the suit (e.g. 5H,2H,7H), exclude it
                # from ranks for gap check
                twos_of_suit = [
                    c for c in self.cards if c.rank == Rank.TWO and c.suit == self.suit
                ]
                if len(twos_of_suit) == 1:
                    ranks_without_2 = [r for r in ranks if r != Rank.TWO]
                    gaps = self._sequence_total_gaps(
                        self._sort_ranks_for_sequence(ranks_without_2)
                    )
                    if len(ranks_without_2) >= 2 and gaps <= 1:
                        return True
                elif self._sequence_total_gaps(ranks_sorted) <= 1:
                    return True
            return False

        elif self.game_type == GameType.TRIPLE:
            if is_wildcard(card):
                wildcards = [c for c in self.cards if is_wildcard(c)]
                return len(wildcards) == 0

            allowed_ranks = {Rank.ACE, Rank.THREE, Rank.KING}
            if card.rank not in allowed_ranks:
                return False

            ranks = [c.rank for c in self.cards if not is_wildcard(c)]
            if not ranks:
                return True
            return card.rank == ranks[0]

        return False

    def add_card(self, card: Card):
        """Add a card to the game."""
        if not self.can_add(card):
            raise ValueError(
                f"Não é possível adicionar {card_display_pt(card)} a este jogo"
            )
        self.cards.append(card)
        self._validate()


def can_form_sequence(cards: list[Card], suit: Suit) -> bool:
    """Check if cards can form a sequence of the specified suit."""
    if len(cards) < 3:
        return False

    wildcards = [c for c in cards if is_wildcard(c)]
    if len(wildcards) > 1:
        return False

    natural_cards = [c for c in cards if not is_wildcard(c) and c.suit == suit]
    if len(natural_cards) < 2:
        return False

    try:
        Game(GameType.SEQUENCE, cards, suit)
        return True
    except ValueError:
        return False


def can_form_triple(cards: list[Card]) -> bool:
    """Check if cards can form a triple."""
    if len(cards) < 3:
        return False

    wildcards = [c for c in cards if is_wildcard(c)]
    if len(wildcards) > 1:
        return False

    natural_cards = [c for c in cards if not is_wildcard(c)]
    if len(natural_cards) < 2:
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
