# Canastra refactoring plan

This document captures refactoring opportunities: shared abstractions, module split, and **reducing deeply nested ifs/loops**.

---

## 1. Centralize deck and rank order

- **Deck**: `Engine.create_deck()` and `game_helpers._create_full_deck()` duplicate the same Canastra deck. Add a single `create_canastra_deck()` (e.g. in `card.py`) and use it in both.
- **Rank order**: The same A→K order is reimplemented in `game.py` (3 places), `ui_components.py`, and `game_helpers.py` (display order differs). Introduce one canonical order in `card.py` (e.g. `RANK_ORDER_SEQUENCE`) and reuse; keep display-specific order in one place.

---

## 2. Split `game_helpers.py`

- **simulation/actions**: determinization, `_get_legal_actions` / `_get_abstract_actions`, `_apply_action`.
- **mcts**: IS-MCTS, UCB, rollout policy, constants.
- **game.py**: move `detect_game_type` and `find_valid_game`.
- **Hand display**: move `organize_hand` to `card.py` or `hand_display.py` using shared rank order.

---

## 3. Single source for wildcard/sequence rules

- `game.py`: `_is_natural_in_sequence`, `_counts_as_wildcard_in_sequence`.
- `ui_components.py`: `_counts_as_wildcard_in_sequence_ui` duplicates the same rule. Import one helper from `game.py`.

---

## 4. Formalize actions

- Replace ad-hoc tuples with a small action model (dataclass or union type) and a registry of handlers for `_apply_action` and legal-action generation.

---

## 5. Single place for card/suit display

- Consolidate `SUIT_NAMES_PT`, `card_display_pt`, `get_suit_symbol`, `_SUIT_SYMBOLS`, etc. in one module.

---

## 6. Reducing deeply nested ifs and loops

Concrete spots and patterns to apply:

### 6.1 `game.py` — `_validate_sequence`

**Current**: Deep nesting with `if has_wildcard` → gap loop → `if not can_form` → `if other_ranks` → `if highest_idx >= 9`; and in the `else` branch more `if len(twos_of_suit)` → `if len(ranks_without_2)` → `if _sequence_total_gaps(...)`.

**Approach**:

- Extract **gap computation** into `_sequence_total_gaps(ranks_sorted)` (already exists) and a small helper that returns “can wildcard fill these ranks?” so the main method just asks one question.
- Extract **wrapped-order (A at end) check** into something like `_wildcard_can_fill_wrapped_sequence(ranks_sorted)` returning bool; keep the “other_ranks / highest_idx >= 9” logic there with early returns.
- In the no-wildcard branch, extract **“valid sequence with optional 2 of suit”** into `_is_valid_natural_sequence_with_optional_two(ranks, cards, suit)` and use a single call + early return.
- Use **guard clauses**: validate preconditions (e.g. “at least 2 natural”, “only one wildcard”) at the top and `return` or `raise`; then one clear block per case (with wildcard vs without).

### 6.2 `game.py` — `can_add`

**Current**: Nested `if game_type == SEQUENCE` with multiple levels (wildcard check, natural check, duplicate rank, `_is_sequence`, then wildcards/twos_of_suit/gaps); then `elif TRIPLE` with more ifs.

**Approach**:

- Split into **`_can_add_to_sequence(self, card)`** and **`_can_add_to_triple(self, card)`**; `can_add` becomes a short dispatcher by `game_type`.
- Inside `_can_add_to_sequence`, use **early returns**: e.g. “if counts as wildcard → return len(wildcards)==0”; “if not natural → return False”; “if duplicate rank → return False”; “if already sequence → return True”; then one block for “one wildcard + gap check” with a small helper for the 2-of-suit case.
- Reduces mental stack and makes each branch one level deep.

### 6.3 `game_helpers.py` — `_get_legal_actions` / `_get_abstract_actions`

**Current**: Top-level `if phase == DRAW` / `LAY_DOWN` / `DISCARD` with nested loops: for card → for player → for game → if can_add → append.

**Approach**:

- **Phase dispatcher**: one function per phase, e.g. `_actions_draw(engine)`, `_actions_lay_down(engine, player)`, `_actions_discard(player)`; main function only switches on phase and calls the right one.
- **“Add to game” actions**: extract to something like `_collect_add_to_game_actions(engine, player)` that returns a list of `("add_to_game", owner_idx, gi, rank, suit)`; then both `_get_legal_actions` and `_get_abstract_actions` can call it and optionally sample. This removes the duplicated triple loop in both functions.
- Keeps the same behavior while flattening structure.

### 6.4 `game_helpers.py` — `_apply_action`

**Current**: Long chain of `if kind == "draw_stock"` … `elif kind == "draw_discard"` … with repeated “resolve card_tuples from hand” logic for lay_sequence and lay_triple.

**Approach**:

- **Handler registry**: map action kind to a small function, e.g. `_HANDLERS = {"draw_stock": _handle_draw_stock, "draw_discard": _handle_draw_discard, ...}`; `_apply_action` does `kind = action[0]; return _HANDLERS.get(kind, _handle_unknown)(engine, action)`.
- **Shared helper for card_tuples**: extract `_resolve_cards_from_hand(player, card_tuples)` that returns `(list[Card] or None)`; use it in both lay_sequence and lay_triple handlers so the “find card in remaining, remove, append” loop lives once.
- Cuts nesting and duplication.

### 6.5 `game_helpers.py` — `find_valid_game`

**Current**: Four nested loops (suit × i × j × k) then another three (suit × combo_size × combo) with two conditionals inside.

**Approach**:

- **Single “try hand subset” helper**: e.g. `_first_valid_game_from_cards(cards)` that, given a list of cards, returns `("sequence", suit, cards)` or `("triple", None, cards)` or `None` by iterating suits (and for sequence, trying the given cards with that suit). No nested index loops.
- **Combination driver**: use `combinations(hand, size)` for sizes 3, 4, …, min(8, len(hand)); for each combo call `_first_valid_game_from_cards(list(combo))`; return first non-None. This replaces the two big nested blocks with one clear loop over sizes and one over combos.
- Optionally break early when a valid game is found for a given size to avoid redundant checks.

### 6.6 `game_helpers.py` — `_discard_danger`

**Current**: Several sequential ifs with nested loop (team_players × games) and more conditions.

**Approach**:

- Compute **components** with early returns or small helpers: e.g. `_danger_team_can_use(engine, card)`, `_danger_joker(card)`, `_danger_pile_match(engine, card)` each returning a float; then `return max(0.0, team_danger, joker_danger, pile_danger)`. The “team can add to meld” logic becomes one function with a single loop (or `any(game.can_add(card) for p in team for game in p.games)`).
- Keeps behavior, flattens and makes each danger type testable.

### 6.7 `ui_components.py` — `display_card` selection update

**Current**: `if selectable` → `if selected` → `if phase == DISCARD` / `elif phase == LAY_DOWN` with inner `if card not in ...`; `else` → `for i, c in enumerate` → `if c is card` → pop.

**Approach**:

- Extract **`_update_selection(phase, card, selected)`**: given phase and whether the card is now selected, update `st.session_state.selected_cards` (single-card replace for DISCARD, append/remove by identity for LAY_DOWN). Then `display_card` just calls `_update_selection(engine.turn_phase, card, selected)` when selectable and selected changed. All branching lives in one small function with clear branches (no nested if/for).
- Removes nesting from the display function and makes selection logic reusable/testable.

### 6.8 `app.py` — `render_lay_down_phase_actions`

**Current**: Deep nesting: `if len(selected_cards) >= 3` → `if game_type is None` / `else` → `if game_type == "both"` / `elif` / `else` → `if option == "Sequência"` → suit choice → `if st.button` → `if can_form_sequence` → `if error` / `else`; similar for Trinca and for “add to game” block.

**Approach**:

- **Extract render helpers**: e.g. `_render_lay_new_game(engine, selected_cards)` (handles game_type, option, suit, and the two buttons with a single “try lay + show error or rerun” helper), and `_render_add_to_game_buttons(engine, current_player, selected_cards)` (builds valid_targets and renders the button list). Each helper uses early returns (e.g. “if len(selected_cards) < 3: return”) and one level of control flow.
- **Shared “execute lay + handle error”**: one function that takes (engine, lay_fn, success_callback) and does: run lay_fn, if error show st.error else clear selection and rerun. Cuts duplicated “if error / else clear + rerun” blocks.
- **suit_map / suit_name_map**: define once at module or function top and pass into the helpers instead of redefining inside branches.

### 6.9 `ui_components.py` — `sort_game_cards`

**Current**: Big `if SEQUENCE` block with inner `if Rank.ACE and Rank.KING`, then `if wildcards` → `if len(natural_cards) >= 2` → loop to find gap → `if not wildcard_inserted`; `else` with twos_of_suit/rest.

**Approach**:

- Use **shared rank order** from `card.py` (see §1) instead of a local list.
- Extract **`_sort_natural_cards_for_sequence(natural_cards, rank_order)`**: handle Ace-after-King and return sorted list; then **`_place_wildcard_in_sequence_gap(natural_cards, wildcard, rank_order)`** that returns either `natural + [wildcard]` or list with wildcard inserted in first gap. Main function: get wildcards/natural; sort natural; if wildcards call _place_wildcard_… else handle 2-of-suit vs rest; return. Each helper has a single responsibility and one or two levels of nesting.
- Triple branch stays as-is (already flat).

### 6.10 `game_helpers.py` — `organize_hand` joker placement

**Current**: Loop over suits, then “if suit_cards and jokers” with inner loop `for i in range(len(ranks)-1)` and “if gap then insert and break”.

**Approach**:

- Extract **`_insert_joker_in_first_gap(ranks, joker, suit_cards)`** that returns `(new_suit_cards, remaining_joker)` or just the list and mutate jokers list in caller. The “place jokers in gaps” logic is then a small loop that calls this until no jokers or no gaps, reducing nesting in the main loop.

### 6.11 General patterns to apply

- **Guard clauses**: validate and return/raise early; then main logic assumes “happy path” with less indentation.
- **Extract small functions**: one level of “what” (e.g. “can wildcard fill this sequence?”) so the caller doesn’t need to read the “how” (gaps, wrapped order, etc.).
- **Replace long if/elif chains with dispatch**: dict of handlers or small methods keyed by enum/string (e.g. action kind, game type).
- **Single loop + helper**: replace “loop inside loop with condition” by “loop; inside call helper that does the inner logic” so the inner part can use early returns and be tested alone.
- **Build lists then iterate**: e.g. build `valid_targets` then one simple loop to render buttons, instead of mixing “compute target” and “if button” and “if error” in nested blocks.

---

## Suggested order of work

1. **Deck + rank order** (§1) — low risk, enables other cleanups.
2. **Wildcard/sequence single source** (§3) and **display/suit consolidation** (§5) — quick wins.
3. **Flatten `game.py`** (§6.1, §6.2): extract helpers and early returns in `_validate_sequence` and `can_add`.
4. **Flatten action layer** (§6.3, §6.4, §6.5): phase dispatchers, add-to-game helper, action handlers, `find_valid_game` via combo helper.
5. **Flatten UI** (§6.7, §6.8, §6.9): selection update, lay-down render helpers, `sort_game_cards` with shared rank order.
6. **Split `game_helpers`** (§2) and **formalize actions** (§4) once the above is stable.

Running tests after each step keeps regressions under control.
