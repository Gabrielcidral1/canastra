"""Landing page: mode selection (1v1 / doubles), rules, and card examples.

This module is used only before a game is started. Rendered when there is no
engine in session.
"""

import re

import streamlit as st

from canastra.core.card import Card, Rank, Suit
from canastra.core.constants import GameMode, UIText
from canastra.core.rules_loader import RULES_BODY
from canastra.ui.ui_components import card_html_static


def _bold_to_html(text: str) -> str:
    """Replace **x** with <strong>x</strong>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def _rules_markdown_to_html(md: str) -> str:
    """Convert rules markdown to HTML for the landing page rules block."""
    lines = md.strip().split("\n")
    out: list[str] = []
    in_list = False
    list_tag = "ul"
    for line in lines:
        if line.startswith("### "):
            if in_list:
                out.append("</ul>" if list_tag == "ul" else "</ol>")
                in_list = False
            out.append(f"<h3>{_bold_to_html(line[4:])}</h3>")
        elif line.strip().startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
                list_tag = "ul"
            out.append(f"<li>{_bold_to_html(line.strip()[2:])}</li>")
        elif re.match(r"^\d+\.\s", line.strip()):
            if not in_list:
                out.append("<ol>")
                in_list = True
                list_tag = "ol"
            elif list_tag != "ol":
                out.append("</ul>")
                out.append("<ol>")
                list_tag = "ol"
            rest = re.sub(r"^\d+\.\s", "", line.strip())
            out.append(f"<li>{_bold_to_html(rest)}</li>")
        else:
            if in_list:
                out.append("</ul>" if list_tag == "ul" else "</ol>")
                in_list = False
            if line.strip():
                out.append(f"<p>{_bold_to_html(line)}</p>")
    if in_list:
        out.append("</ul>" if list_tag == "ul" else "</ol>")
    return "\n".join(out)


def _landing_page_styles() -> str:
    """CSS for the mode selection landing page."""
    return """
    <style>
    [data-testid="stAppViewContainer"] main .block-container {
        max-width: 100rem; padding-left: 2rem; padding-right: 2rem;
    }
    div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="column"]) {
        gap: 2rem;
    }
    .landing-title {
        font-size: 3.25rem !important; font-weight: 700 !important;
        margin-bottom: 1.5rem; line-height: 1.2;
    }
    [data-testid="column"]:first-child [data-testid="stMarkdown"] p {
        font-size: 1.15rem !important;
    }
    [data-testid="column"]:first-child [data-testid="stMarkdown"] h4 {
        font-size: 1.35rem !important;
    }
    .landing-rules-block {
        background: var(--background-secondary, rgba(255,255,255,0.04));
        border-radius: 12px;
        padding: 1.5rem 2.25rem;
        border: 1px solid var(--border-color, rgba(255,255,255,0.08));
        max-height: 80vh;
        overflow-y: auto;
        font-size: 1.12rem;
        line-height: 1.6;
        width: 100%;
    }
    .landing-rules-block h3 {
        margin-top: 1.25em; margin-bottom: 0.5em;
        font-size: 1.35rem !important;
    }
    .landing-rules-block h3:first-child { margin-top: 0; }
    .landing-rules-block ul, .landing-rules-block ol {
        margin: 0.5em 0; padding-left: 1.5em; font-size: 1.1rem;
    }
    .landing-rules-block p { font-size: 1.1rem; }
    .landing-examples { margin-top: 1.5rem; }
    .landing-examples-row { margin-bottom: 1rem; }
    .landing-examples-label {
        font-size: 1.08rem; font-weight: 600; margin-bottom: 0.35rem;
        color: var(--text-color, inherit);
    }
    [data-testid="column"]:last-child [data-testid="stMarkdown"] h4 {
        font-size: 1.4rem !important;
    }
    </style>
    """


def _render_card_examples():
    """Render example melds (sequência, trinca, canastra) below the Iniciar jogo
    button."""
    seq_cards = [
        Card(Rank.FIVE, Suit.CLUBS),
        Card(Rank.SIX, Suit.CLUBS),
        Card(Rank.SEVEN, Suit.CLUBS),
    ]
    tri_cards = [
        Card(Rank.KING, Suit.DIAMONDS),
        Card(Rank.KING, Suit.SPADES),
        Card(Rank.KING, Suit.CLUBS),
    ]
    canastra_cards = [
        Card(Rank.FOUR, Suit.DIAMONDS),
        Card(Rank.FIVE, Suit.DIAMONDS),
        Card(Rank.SIX, Suit.DIAMONDS),
        Card(Rank.SEVEN, Suit.DIAMONDS),
        Card(Rank.EIGHT, Suit.DIAMONDS),
        Card(Rank.NINE, Suit.DIAMONDS),
        Card(Rank.TEN, Suit.DIAMONDS),
    ]
    w, h = 52, 78

    st.markdown("#### Exemplos de jogos")
    # One HTML block per row so Streamlit renders the card divs correctly
    row1 = (
        '<div class="landing-examples">'
        '<div class="landing-examples-row">'
        '<div class="landing-examples-label">Sequência (mesmo naipe)</div>'
        + "".join(card_html_static(c, w, h) for c in seq_cards)
        + "</div></div>"
    )
    st.markdown(row1, unsafe_allow_html=True)

    row2 = (
        '<div class="landing-examples-row">'
        '<div class="landing-examples-label">Trinca (mesmo número)</div>'
        + "".join(card_html_static(c, w, h) for c in tri_cards)
        + "</div>"
    )
    st.markdown(row2, unsafe_allow_html=True)

    row3 = (
        '<div class="landing-examples-row">'
        '<div class="landing-examples-label">Canastra (7+ cartas do mesmo naipe)</div>'
        + "".join(
            card_html_static(
                c,
                w,
                h,
                rotate_deg=270 if i == len(canastra_cards) - 1 else None,
            )
            for i, c in enumerate(canastra_cards)
        )
        + "</div>"
    )
    st.markdown(row3, unsafe_allow_html=True)


def render_mode_selection():
    """Show 1v1 vs doubles choice, card examples below the button (left), and
    rules (right)."""
    st.markdown(_landing_page_styles(), unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 2.9], gap="large")

    with col_left:
        st.markdown(
            '<p class="landing-title" style="font-size: 3.25rem !important; '
            'font-weight: 700 !important;">🎴 Canastra</p>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{UIText.ModeSelection.TITLE}**")
        mode = st.radio(
            "Modo",
            options=[GameMode.ONE_VS_ONE, GameMode.DOUBLES],
            format_func=lambda x: (
                UIText.ModeSelection.ONE_VS_ONE
                if x == GameMode.ONE_VS_ONE
                else UIText.ModeSelection.DOUBLES
            ),
            key="mode_radio",
            horizontal=True,
            label_visibility="collapsed",
        )
        st.markdown("")
        if st.button(
            UIText.ModeSelection.BUTTON_START,
            type="primary",
            use_container_width=True,
        ):
            st.session_state.game_mode = mode
            st.rerun()

        # Card examples below "Iniciar jogo" button (bottom left)
        st.markdown("")
        _render_card_examples()

    with col_right:
        st.markdown("#### 📖 Regras do jogo")
        rules_html = _rules_markdown_to_html(RULES_BODY)
        st.markdown(
            f'<div class="landing-rules-block">{rules_html}</div>',
            unsafe_allow_html=True,
        )
