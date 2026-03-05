"""Engine for Canastra game."""

import random

from .card import Card, Suit, create_canastra_deck
from .constants import (
    DisplayNameTemplates,
    EngineErrors,
    EngineLog,
    GameRules,
    GameType,
    KnockType,
    TurnPhase,
    UIText,
)
from .game import Game


class Player:
    """Represents a player in the game."""

    def __init__(self, name: str, team: int, is_human: bool = True):
        self.name = name
        self.team = team
        self.is_human = is_human
        self.hand: list[Card] = []
        self.games: list[Game] = []
        self.points = 0
        self.has_dead_hand = False

    def add_card(self, card: Card):
        """Add a card to hand."""
        self.hand.append(card)

    def remove_card(self, card: Card) -> bool:
        """Remove a card from hand. Returns True if removed."""
        if card in self.hand:
            self.hand.remove(card)
            return True
        return False

    def get_hand_value(self) -> int:
        """Calculate total value of cards in hand."""
        return sum(card.point_value for card in self.hand)

    def get_games_value(self) -> int:
        """Calculate total value of laid down games."""
        return sum(game.point_value for game in self.games)

    def has_dirty_canastra(self) -> bool:
        """Check if has at least one dirty canastra."""
        return any(game.is_dirty_canastra for game in self.games)

    def has_clean_canastra(self) -> bool:
        """Check if has at least one clean canastra (7+ cards, no wildcards)."""
        return any(game.is_clean_canastra for game in self.games)


class Engine:
    """Main engine for Canastra game."""

    def __init__(self, num_players: int | None = None):
        self.num_players = (
            num_players if num_players is not None else GameRules.NUM_PLAYERS
        )
        self.players: list[Player] = []
        self.stock: list[Card] = []
        self.discard_pile: list[Card] = []
        self.dead_hands: dict[int, list[Card]] = {}
        self.current_player_index = 0
        self.turn_phase = TurnPhase.DRAW
        self.game_over = False
        self.messages: list[str] = []
        self.pending_morto_player_index: int | None = (
            None  # receives morto at start of next turn (after indirect knock)
        )

        for i in range(self.num_players):
            team = i if self.num_players == 2 else i // 2
            self.players.append(
                Player(
                    DisplayNameTemplates.PLAYER_N.format(n=i + 1),
                    team,
                    is_human=(i == 0),
                )
            )
            self.dead_hands[team] = []

    def _get_player_display_name(self, player: Player) -> str:
        """Get display name for a player (Você, Parceiro, Oponente 1, Oponente 2)."""
        human_player = next((p for p in self.players if p.is_human), None)
        if not human_player:
            return player.name

        if player == human_player:
            return UIText.DisplayNames.YOU

        if player.team == human_player.team:
            return UIText.DisplayNames.PARTNER

        # Find opponent number based on their position in players list
        # Opponents are players from the other team, numbered by their order
        opponent_team = 1 if human_player.team == 0 else 0
        opponents = [
            p for p in self.players if p.team == opponent_team and p != human_player
        ]
        opponents.sort(key=lambda p: self.players.index(p))  # Sort by original position

        if player in opponents:
            if self.num_players == 2:
                return UIText.DisplayNames.OPPONENT
            opp_index = opponents.index(player)
            return DisplayNameTemplates.OPPONENT_N.format(n=opp_index + 1)

        return player.name

    def _log(self, message: str):
        """Add message to log."""
        self.messages.append(message)

    def _log_player_action(self, player: Player, message_template: str, *args):
        """Log a player action with proper display name."""
        display_name = self._get_player_display_name(player)
        # Replace player.name in the message with display_name
        message = message_template.replace(player.name, display_name)
        if args:
            message = message.format(*args)
        self._log(message)

    def create_deck(self) -> list[Card]:
        """Create standard Canastra deck."""
        return create_canastra_deck()

    def start_new_game(self):
        """Start a new game - deal cards and determine starting player."""
        self.stock = self.create_deck()
        random.shuffle(self.stock)
        self.discard_pile = []
        self.game_over = False
        self.messages = []
        self.pending_morto_player_index = None

        for player in self.players:
            player.hand = []
            player.games = []
            player.points = 0
            player.has_dead_hand = False

        for _ in range(GameRules.INITIAL_HAND_SIZE):
            for player in self.players:
                if self.stock:
                    player.add_card(self.stock.pop())

        for team in self.dead_hands:
            self.dead_hands[team] = []
            for _ in range(GameRules.MORTO_SIZE):
                if self.stock:
                    self.dead_hands[team].append(self.stock.pop())

        # Discard pile starts empty - first card is discarded by the starting player
        self.discard_pile = []

        self.current_player_index = random.randint(0, self.num_players - 1)
        self.turn_phase = TurnPhase.DRAW
        starting_player = self.players[self.current_player_index]
        display_name = self._get_player_display_name(starting_player)
        self._log(EngineLog.GAME_STARTED.format(display_name=display_name))

    def get_current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]

    def draw_from_stock(self) -> str | None:
        """Draw a card from stock. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.DRAW:
            return EngineErrors.DRAW_ONLY_IN_DRAW_PHASE

        if not self.stock:
            self.game_over = True
            self._calculate_final_points()
            return None

        card = self.stock.pop()
        player = self.get_current_player()
        player.add_card(card)
        self.turn_phase = TurnPhase.LAY_DOWN
        display_name = self._get_player_display_name(player)
        self._log(EngineLog.DREW_FROM_STOCK.format(display_name=display_name))
        return None

    def draw_from_discard(self) -> str | None:
        """Draw all cards from discard pile. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.DRAW:
            return EngineErrors.DRAW_ONLY_IN_DRAW_PHASE

        if not self.discard_pile:
            return EngineErrors.DISCARD_PILE_EMPTY

        player = self.get_current_player()
        for card in self.discard_pile:
            player.add_card(card)

        self.discard_pile = []
        self.turn_phase = TurnPhase.LAY_DOWN
        display_name = self._get_player_display_name(player)
        self._log(EngineLog.DREW_FROM_DISCARD.format(display_name=display_name))
        return None

    def lay_down_sequence(self, suit: Suit, cards: list[Card]) -> str | None:
        """Lay down a sequence. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.LAY_DOWN:
            return EngineErrors.LAY_DOWN_ONLY_IN_LAY_PHASE

        player = self.get_current_player()

        for card in cards:
            if not player.remove_card(card):
                return EngineLog.CARD_NOT_IN_HAND.format(card=card)

        try:
            game = Game(GameType.SEQUENCE, cards, suit)
            player.games.append(game)
            display_name = self._get_player_display_name(player)
            self._log(
                EngineLog.LAID_DOWN_SEQUENCE.format(
                    display_name=display_name, suit=suit.value, n=len(cards)
                )
            )
            err = self._check_empty_hand_knock(player)
            if err:
                player.games.pop()
                for card in cards:
                    player.add_card(card)
                return err
            return None
        except ValueError as e:
            for card in cards:
                player.add_card(card)
            return str(e)

    def lay_down_triple(self, cards: list[Card]) -> str | None:
        """Lay down a triple. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.LAY_DOWN:
            return EngineErrors.LAY_DOWN_ONLY_IN_LAY_PHASE

        player = self.get_current_player()

        for card in cards:
            if not player.remove_card(card):
                return EngineLog.CARD_NOT_IN_HAND.format(card=card)

        try:
            game = Game(GameType.TRIPLE, cards)
            player.games.append(game)
            display_name = self._get_player_display_name(player)
            self._log(
                EngineLog.LAID_DOWN_TRIPLE.format(
                    display_name=display_name, n=len(cards)
                )
            )
            err = self._check_empty_hand_knock(player)
            if err:
                player.games.pop()
                for card in cards:
                    player.add_card(card)
                return err
            return None
        except ValueError as e:
            for card in cards:
                player.add_card(card)
            return str(e)

    def add_to_game(
        self, game_index: int, card: Card, target_player: Player | None = None
    ) -> str | None:
        """Add card to an existing game. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.LAY_DOWN:
            return EngineErrors.ADD_ONLY_IN_LAY_PHASE

        player = self.get_current_player()

        if target_player is None:
            target_player = player
        elif target_player.team != player.team:
            return EngineErrors.ADD_ONLY_OWN_TEAM

        if game_index < 0 or game_index >= len(target_player.games):
            return EngineErrors.INVALID_GAME_INDEX

        if not player.remove_card(card):
            return EngineLog.CARD_NOT_IN_HAND.format(card=card)

        try:
            game = target_player.games[game_index]
            game.add_card(card)
            player_display = self._get_player_display_name(player)
            game_idx = game_index + 1
            if target_player == player:
                self._log(
                    EngineLog.ADDED_TO_GAME.format(
                        player_display=player_display, card=card, game_idx=game_idx
                    )
                )
            else:
                target_display = self._get_player_display_name(target_player)
                self._log(
                    EngineLog.ADDED_TO_GAME_OF.format(
                        player_display=player_display,
                        card=card,
                        game_idx=game_idx,
                        target_display=target_display,
                    )
                )
            err = self._check_empty_hand_knock(player)
            if err:
                game.cards.pop()
                player.add_card(card)
                return err
            return None
        except ValueError as e:
            player.add_card(card)
            return str(e)

    def discard(self, card: Card) -> str | None:
        """Discard a card. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.DISCARD:
            return EngineErrors.DISCARD_ONLY_IN_DISCARD_PHASE

        player = self.get_current_player()

        if not player.remove_card(card):
            return EngineLog.CARD_NOT_IN_HAND.format(card=card)

        self.discard_pile.append(card)
        display_name = self._get_player_display_name(player)
        self._log(EngineLog.DISCARDED.format(display_name=display_name, card=card))

        if len(player.hand) == 0:
            knock_type = self._determine_knock_type(player)
            # Picking up the morto (first time emptying hand) requires no meld.
            # Only ending the game (final knock, or direct when already had morto)
            # requires the team to have a clean canastra.
            would_end_game = knock_type == KnockType.FINAL or (
                knock_type == KnockType.DIRECT and player.has_dead_hand
            )
            if would_end_game and not self._team_has_clean_canastra(player):
                player.add_card(card)
                self.discard_pile.pop()
                return EngineErrors.FINISH_NEEDS_CLEAN_CANASTRA
            self._process_knock(player, knock_type)
        else:
            self._next_turn()

        return None

    def get_team_players(self, team: int) -> list[Player]:
        """Return all players on the given team."""
        return [p for p in self.players if p.team == team]

    def get_team_live_points(self, team: int) -> int:
        """Current points for a team: sum(jogos) - sum(mão)
        for all players on that team."""
        total_games = 0
        total_hand = 0
        for p in self.get_team_players(team):
            total_games += p.get_games_value()
            total_hand += p.get_hand_value()
        return total_games - total_hand

    def _team_has_clean_canastra(self, player: Player) -> bool:
        """True if the player's team has at least one clean canastra on the table."""
        return any(
            g.is_clean_canastra
            for p in self.get_team_players(player.team)
            for g in p.games
        )

    def _determine_knock_type(self, player: Player) -> KnockType:
        """Determine the type of knock."""
        if player.has_dead_hand:
            return KnockType.FINAL

        if self.turn_phase == TurnPhase.LAY_DOWN:
            return KnockType.DIRECT

        return KnockType.INDIRECT

    def _check_empty_hand_knock(self, player: Player) -> str | None:
        """If player hand is empty, validate and process knock (direct/indirect/final).
        Returns error if knock would end game without clean canastra (caller must
        undo)."""
        if len(player.hand) != 0:
            return None
        knock_type = self._determine_knock_type(player)
        would_end_game = knock_type == KnockType.FINAL or (
            knock_type == KnockType.DIRECT and player.has_dead_hand
        )
        if would_end_game and not self._team_has_clean_canastra(player):
            return EngineErrors.FINISH_NEEDS_CLEAN_CANASTRA
        self._process_knock(player, knock_type)
        return None

    def _process_knock(self, player: Player, knock_type: KnockType):
        """Process player's knock."""
        if knock_type == KnockType.DIRECT:
            if not player.has_dead_hand:
                player.has_dead_hand = True
                team = player.team
                for card in self.dead_hands[team]:
                    player.add_card(card)
                self.dead_hands[team] = []
                display_name = self._get_player_display_name(player)
                self._log(EngineLog.DIRECT_KNOCK.format(display_name=display_name))
                self.turn_phase = TurnPhase.LAY_DOWN
            else:
                self.game_over = True
                self._calculate_final_points()
                return

        elif knock_type == KnockType.INDIRECT:
            display_name = self._get_player_display_name(player)
            self._log(EngineLog.INDIRECT_KNOCK.format(display_name=display_name))
            self.pending_morto_player_index = self.current_player_index
            self._next_turn()
            return

        elif knock_type == KnockType.FINAL:
            self.game_over = True
            self._calculate_final_points()
            return

    def end_lay_down_phase(self):
        """End the lay down phase and go to discard."""
        if self.turn_phase == TurnPhase.LAY_DOWN:
            player = self.get_current_player()
            if len(player.hand) == 0:
                self._check_empty_hand_knock(player)
            if self.turn_phase == TurnPhase.LAY_DOWN:
                self.turn_phase = TurnPhase.DISCARD

    # Clockwise turn order: Parceiro (1) → Oponente 2 (3) → Você (0) → Oponente 1 (2)
    _CLOCKWISE_ORDER = (1, 3, 0, 2)

    def _next_turn(self):
        """Move to next player (clockwise: Parceiro → Oponente 2 → Você → Oponente
        1)."""
        if self.num_players == 4:
            order = self._CLOCKWISE_ORDER
            pos = order.index(self.current_player_index)
            self.current_player_index = order[(pos + 1) % 4]
        else:
            self.current_player_index = (
                self.current_player_index + 1
            ) % self.num_players
        self.turn_phase = TurnPhase.DRAW
        current_player = self.get_current_player()
        # If this player did an indirect knock, give them the morto (11 cards) now
        if (
            self.pending_morto_player_index is not None
            and self.current_player_index == self.pending_morto_player_index
        ):
            team = current_player.team
            for card in self.dead_hands[team]:
                current_player.add_card(card)
            self.dead_hands[team] = []
            current_player.has_dead_hand = True
            self.pending_morto_player_index = None
            display_name = self._get_player_display_name(current_player)
            self._log(EngineLog.PICKED_UP_DEAD_HAND.format(display_name=display_name))
        display_name = self._get_player_display_name(current_player)
        self._log(EngineLog.TURN_OF.format(display_name=display_name))

        if self.turn_phase == TurnPhase.DRAW and not self.stock:
            self.game_over = True
            self._calculate_final_points()

    def _calculate_final_points(self):
        """Calculate final points for all teams."""
        self._log(EngineLog.POINTS_COUNT_HEADER)

        for team in set(j.team for j in self.players):
            team_players = self.get_team_players(team)
            team_points = 0

            has_final_knock = any(len(j.hand) == 0 for j in team_players)
            if has_final_knock:
                team_points += GameRules.FINAL_KNOCK_BONUS
                self._log(EngineLog.TEAM_FINAL_KNOCK_BONUS.format(team=team + 1))

            for player in team_players:
                games_points = player.get_games_value()
                hand_points = player.get_hand_value()
                team_points += games_points - hand_points
                self._log(
                    EngineLog.GAMES_AND_HAND.format(
                        player_name=player.name,
                        games_points=games_points,
                        hand_points=hand_points,
                    )
                )

            if not any(j.has_dead_hand for j in team_players):
                team_points -= GameRules.DEAD_HAND_PENALTY
                self._log(EngineLog.TEAM_NO_DEAD_HAND_PENALTY.format(team=team + 1))

            for player in team_players:
                player.points = team_points

            self._log(
                EngineLog.TEAM_TOTAL_POINTS.format(team=team + 1, points=team_points)
            )

    def copy(self) -> "Engine":
        """Return a deep copy of the engine for simulation (no message log)."""

        eng = Engine(num_players=self.num_players)
        eng.players = []
        for p in self.players:
            new_p = Player(p.name, p.team, p.is_human)
            new_p.hand = [Card(c.rank, c.suit) for c in p.hand]
            new_p.games = []
            for g in p.games:
                new_cards = [Card(c.rank, c.suit) for c in g.cards]
                new_g = Game(g.game_type, new_cards, g.suit, _skip_validate=True)
                new_p.games.append(new_g)
            new_p.points = p.points
            new_p.has_dead_hand = p.has_dead_hand
            eng.players.append(new_p)
        eng.stock = [Card(c.rank, c.suit) for c in self.stock]
        eng.discard_pile = [Card(c.rank, c.suit) for c in self.discard_pile]
        eng.dead_hands = {
            t: [Card(c.rank, c.suit) for c in cards]
            for t, cards in self.dead_hands.items()
        }
        eng.current_player_index = self.current_player_index
        eng.turn_phase = self.turn_phase
        eng.game_over = self.game_over
        eng.pending_morto_player_index = self.pending_morto_player_index
        eng.messages = []
        return eng

    def get_winner_message(self) -> tuple[int | None, dict[int, int]]:
        """Return (winning_team or None if tie, {team: points}). Only valid when
        game_over and _calculate_final_points has been called."""
        team_scores: dict[int, int] = {}
        for p in self.players:
            team_scores[p.team] = p.points
        if len(team_scores) < 2:
            sole = list(team_scores.keys())[0] if team_scores else None
            return (sole, team_scores)
        scores = list(team_scores.values())
        if scores[0] == scores[1]:
            return (None, team_scores)
        winner = max(team_scores, key=team_scores.get)
        return (winner, team_scores)
