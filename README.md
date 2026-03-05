# Brazilian Canastra

A Brazilian Canastra card game implemented in Python with a Streamlit interface. Play in 1v1 or doubles (4 players), with an AI opponent and optional bot suggestion.

## How to run

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv run streamlit run app.py
```

Install uv if needed (`curl -LsSf https://astral.sh/uv/install.sh | sh`), then from the project root run the command above.

---

## Goal of the game

Two teams compete to **score more points than the other**. You do that by:

- **Forming melds** on the table: sequences (same suit, in order) or triples (same rank). Each card in a meld is worth points.
- **Building canastras**: melds of 7+ cards earn big bonuses (clean +200, dirty +100).
- **Going out** (“bater”): emptying your hand gives your team the “dead hand” (morto) and, with a clean canastra, lets you end the game and trigger final scoring.

Points from your melds and bonuses are added; cards left in your hand at the end count **negative**. The team with the higher total wins.

---

## Game rules

### Definitions

- **MELDS (sequências)**: Three or more cards of the same suit in sequence (Ace can be before 2 or after King).
- **TRIPLE (trinca)**: Three or more cards of the same rank (Ace, 3, or King; wildcards allowed).
- **WILDCARD (curinga)**: The 2 substitutes any card. Each meld may contain at most one wildcard. A 2 of the sequence suit counts as natural in a sequence.
- **STOCK (monte)**: Remaining cards after the deal.
- **DEAD HAND (morto)**: Two piles of 11 cards, one per team; the first player to empty their hand takes their team’s pile.
- **DISCARD PILE (lixo)**: Discarded cards, all visible. You may draw the whole pile instead of one card from the stock.
- **CANASTRA**: A meld of 7+ cards:
  - **Clean**: No wildcards (+200).
  - **Dirty**: With wildcard(s) (+100).

### Actions

- **DRAW**: One card from the stock or the entire discard pile.
- **LAY DOWN**: Place new sequences or triples and/or add cards to your team’s existing melds.
- **KNOCK (bater)** when your hand is empty:
  - **Direct**: Last card was laid; you take the dead hand immediately.
  - **Indirect**: Last card was discarded; you take the dead hand at the start of your next turn.
  - **Final**: Ends the game (requires a clean canastra).

### Scoring

- Final knock: +100
- Each card in melds: 10 points
- Dirty canastra: +100
- Clean canastra: +200
- Team never took the dead hand: -100
- Cards left in hand at the end: count as negative points

---

## Code organization

The project is split into: **data and rules** (card, game), **game state and flow** (engine), **AI and simulation** (game_helpers), **UI** (ui_components, landing), and the **app** that wires everything together.

### Module roles

| Module | Role |
|--------|------|
| **card.py** | Card representation (`Card`, `Rank`, `Suit`), deck creation (`create_canastra_deck()`), rank order for sequences. |
| **game.py** | Meld model and rules: `Game` (sequence or triple), validation, `can_form_sequence` / `can_form_triple`, wildcard rules. |
| **engine.py** | Game state and flow: `Engine`, `Player`, turn phases (draw → lay down → discard), knock handling, scoring. |
| **game_helpers.py** | AI and simulation: legal/abstract actions, determinization, MCTS/rollouts, bot suggestion, `detect_game_type`, `find_valid_game`, `organize_hand`. |
| **ui_components.py** | Streamlit UI: card display, player panels, meld areas, app CSS. |
| **landing.py** | Landing page: mode selection (1v1 / doubles), rules block, card examples. |
| **app.py** | Main Streamlit app: session state, layout, phase-specific rendering, wiring to engine and game_helpers. |
| **constants.py** | Centralized constants: enums, game rules, AI config, UI/engine text. |
| **rules_loader.py** | Loads rules text from `rules.md`. |
| **benchmark_bot.py** | Bot benchmarks and comparison (e.g. control vs challenger). |

### Data flow (simplified)

1. **User action** (e.g. “Draw from stock”) → **app.py** handles the widget and calls **engine** (e.g. `engine.draw_from_stock()`).
2. **Engine** updates state (hands, stock, phase) and logs messages.
3. **App** re-renders from **engine** and **ui_components** (cards, panels, melds).
4. On the AI’s turn, **app** calls **game_helpers.play_ai_turn(engine)**; the helper uses legal actions, MCTS/rollouts, and the engine to perform the turn.

---

## Interface

The Streamlit UI lets you:

- Choose **1v1** or **doubles** (4 players) on the landing page.
- View and select cards in your hand.
- Draw from the stock or the discard pile.
- Lay down sequences or triples and add cards to existing melds.
- Discard a card.
- Use **“Sugestão do bot”** to see what the bot would play.
- See the game log, scores, and other players’ status (e.g. card counts).

---

## Project structure

```
canastra/
├── app.py               # Main Streamlit app
├── landing.py           # Landing page (mode selection, rules)
├── engine.py            # Game state and flow
├── game.py              # Melds and rules
├── game_helpers.py       # AI, legal actions, simulation
├── card.py              # Cards, deck, rank order
├── ui_components.py     # Streamlit UI building blocks
├── constants.py         # Enums, game rules, AI config, UI text
├── rules_loader.py      # Load rules from rules.md
├── rules.md             # Game rules (Portuguese)
├── main.py              # Optional entry (runs streamlit run app.py)
├── benchmark_bot.py     # Bot benchmarks
├── pyproject.toml       # Project and test config
├── README.md
└── tests/
    ├── __init__.py
    ├── test_integration.py
    └── test_play_and_validate.py
```
