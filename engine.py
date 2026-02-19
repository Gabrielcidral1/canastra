"""Engine for Canastra game."""

import random
from enum import Enum
from typing import List, Optional, Dict, Tuple
from card import Card, Rank, Suit
from game import Game, GameType, can_form_sequence, can_form_triple


class TurnPhase(Enum):
    DRAW = "comprar"
    LAY_DOWN = "baixar"
    DISCARD = "descartar"
    ENDED = "terminado"


class KnockType(Enum):
    DIRECT = "direta"
    INDIRECT = "indireta"
    FINAL = "final"


class Player:
    """Represents a player in the game."""
    
    def __init__(self, name: str, team: int, is_human: bool = True):
        self.name = name
        self.team = team
        self.is_human = is_human
        self.hand: List[Card] = []
        self.games: List[Game] = []
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


class Engine:
    """Main engine for Canastra game."""
    
    def __init__(self, num_players: int = 4):
        self.num_players = num_players
        self.players: List[Player] = []
        self.stock: List[Card] = []
        self.discard_pile: List[Card] = []
        self.dead_hands: Dict[int, List[Card]] = {}
        self.current_player_index = 0
        self.turn_phase = TurnPhase.DRAW
        self.game_over = False
        self.messages: List[str] = []
        
        num_teams = num_players // 2
        for i in range(num_players):
            team = i // 2
            self.players.append(Player(f"Jogador {i+1}", team, is_human=(i == 0)))
            self.dead_hands[team] = []
    
    def _log(self, message: str):
        """Add message to log."""
        self.messages.append(message)
    
    def create_deck(self) -> List[Card]:
        """Create standard Canastra deck."""
        deck = []
        for _ in range(4):
            deck.append(Card(Rank.JOKER))
        ranks = [r for r in Rank if r != Rank.JOKER]
        suits = [Suit.CLUBS, Suit.DIAMONDS, Suit.HEARTS, Suit.SPADES]
        for _ in range(2):
            for rank in ranks:
                for suit in suits:
                    deck.append(Card(rank, suit))
        return deck
    
    def start_new_game(self):
        """Start a new game - deal cards and determine starting player."""
        self.stock = self.create_deck()
        random.shuffle(self.stock)
        self.discard_pile = []
        self.game_over = False
        self.messages = []
        
        for player in self.players:
            player.hand = []
            player.games = []
            player.points = 0
            player.has_dead_hand = False
        
        for _ in range(11):
            for player in self.players:
                if self.stock:
                    player.add_card(self.stock.pop())
        
        for team in self.dead_hands:
            self.dead_hands[team] = []
            for _ in range(11):
                if self.stock:
                    self.dead_hands[team].append(self.stock.pop())
        
        if self.stock:
            self.discard_pile.append(self.stock.pop())
        
        self.current_player_index = random.randint(0, self.num_players - 1)
        self.turn_phase = TurnPhase.DRAW
        self._log(f"{self.players[self.current_player_index].name} começa o jogo")
    
    def get_current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]
    
    def draw_from_stock(self) -> Optional[str]:
        """Draw a card from stock. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.DRAW:
            return "Só é possível comprar na fase de compra"
        
        if not self.stock:
            return "Monte está vazio"
        
        card = self.stock.pop()
        self.get_current_player().add_card(card)
        self.turn_phase = TurnPhase.LAY_DOWN
        self._log(f"{self.get_current_player().name} comprou do monte")
        return None
    
    def draw_from_discard(self) -> Optional[str]:
        """Draw all cards from discard pile. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.DRAW:
            return "Só é possível comprar na fase de compra"
        
        if not self.discard_pile:
            return "Lixo está vazio"
        
        player = self.get_current_player()
        for card in self.discard_pile:
            player.add_card(card)
        
        self.discard_pile = []
        self.turn_phase = TurnPhase.LAY_DOWN
        self._log(f"{player.name} comprou do lixo")
        return None
    
    def lay_down_sequence(self, suit: Suit, cards: List[Card]) -> Optional[str]:
        """Lay down a sequence. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.LAY_DOWN:
            return "Só é possível baixar jogos na fase de baixar"
        
        player = self.get_current_player()
        
        for card in cards:
            if not player.remove_card(card):
                return f"Carta {card} não está na mão"
        
        try:
            game = Game(GameType.SEQUENCE, cards, suit)
            player.games.append(game)
            self._log(f"{player.name} baixou sequência de {suit.value} com {len(cards)} cartas")
            return None
        except ValueError as e:
            for card in cards:
                player.add_card(card)
            return str(e)
    
    def lay_down_triple(self, cards: List[Card]) -> Optional[str]:
        """Lay down a triple. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.LAY_DOWN:
            return "Só é possível baixar jogos na fase de baixar"
        
        player = self.get_current_player()
        
        for card in cards:
            if not player.remove_card(card):
                return f"Carta {card} não está na mão"
        
        try:
            game = Game(GameType.TRIPLE, cards)
            player.games.append(game)
            self._log(f"{player.name} baixou trinca com {len(cards)} cartas")
            return None
        except ValueError as e:
            for card in cards:
                player.add_card(card)
            return str(e)
    
    def add_to_game(self, game_index: int, card: Card, target_player: Optional[Player] = None) -> Optional[str]:
        """Add card to an existing game. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.LAY_DOWN:
            return "Só é possível adicionar cartas na fase de baixar"
        
        player = self.get_current_player()
        
        if target_player is None:
            target_player = player
        elif target_player.team != player.team:
            return "Só é possível adicionar cartas aos jogos do seu time"
        
        if game_index < 0 or game_index >= len(target_player.games):
            return "Índice de jogo inválido"
        
        if not player.remove_card(card):
            return f"Carta {card} não está na mão"
        
        try:
            game = target_player.games[game_index]
            game.add_card(card)
            if target_player == player:
                self._log(f"{player.name} adicionou {card} ao jogo {game_index + 1}")
            else:
                self._log(f"{player.name} adicionou {card} ao jogo {game_index + 1} de {target_player.name}")
            return None
        except ValueError as e:
            player.add_card(card)
            return str(e)
    
    def discard(self, card: Card) -> Optional[str]:
        """Discard a card. Returns error message if invalid."""
        if self.turn_phase != TurnPhase.DISCARD:
            return "Só é possível descartar na fase de descartar"
        
        player = self.get_current_player()
        
        if not player.remove_card(card):
            return f"Carta {card} não está na mão"
        
        self.discard_pile.append(card)
        self._log(f"{player.name} descartou {card}")
        
        if len(player.hand) == 0:
            knock_type = self._determine_knock_type(player)
            self._process_knock(player, knock_type)
        else:
            self._next_turn()
        
        return None
    
    def _determine_knock_type(self, player: Player) -> KnockType:
        """Determine the type of knock."""
        if player.has_dead_hand:
            return KnockType.FINAL
        
        if self.turn_phase == TurnPhase.LAY_DOWN:
            return KnockType.DIRECT
        
        return KnockType.INDIRECT
    
    def _process_knock(self, player: Player, knock_type: KnockType):
        """Process player's knock."""
        if knock_type == KnockType.DIRECT:
            if not player.has_dead_hand:
                player.has_dead_hand = True
                team = player.team
                for card in self.dead_hands[team]:
                    player.add_card(card)
                self.dead_hands[team] = []
                self._log(f"{player.name} bateu DIRETA e pegou o morto")
                self.turn_phase = TurnPhase.LAY_DOWN
            else:
                self.game_over = True
                self._calculate_final_points()
                return
        
        elif knock_type == KnockType.INDIRECT:
            self._log(f"{player.name} bateu INDIRETA")
            self._next_turn()
            return
        
        elif knock_type == KnockType.FINAL:
            self.game_over = True
            self._calculate_final_points()
            return
    
    def end_lay_down_phase(self):
        """End the lay down phase and go to discard."""
        if self.turn_phase == TurnPhase.LAY_DOWN:
            self.turn_phase = TurnPhase.DISCARD
    
    def _next_turn(self):
        """Move to next player."""
        self.current_player_index = (self.current_player_index + 1) % self.num_players
        self.turn_phase = TurnPhase.DRAW
        self._log(f"Vez de {self.get_current_player().name}")
    
    def _calculate_final_points(self):
        """Calculate final points for all teams."""
        self._log("=== CONTAGEM DE PONTOS ===")
        
        for team in set(j.team for j in self.players):
            team_players = [j for j in self.players if j.team == team]
            team_points = 0
            
            has_final_knock = any(len(j.hand) == 0 for j in team_players)
            if has_final_knock:
                team_points += 100
                self._log(f"Time {team + 1}: +100 pontos (Batida Final)")
            
            for player in team_players:
                games_points = player.get_games_value()
                hand_points = player.get_hand_value()
                team_points += games_points - hand_points
                self._log(f"{player.name}: Jogos {games_points}, Mão -{hand_points}")
            
            if not any(j.has_dead_hand for j in team_players):
                team_points -= 100
                self._log(f"Time {team + 1}: -100 pontos (Não pegou o morto)")
            
            for player in team_players:
                player.points = team_points
            
            self._log(f"Time {team + 1} total: {team_points} pontos")

