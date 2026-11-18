"""The look of the app: one palette (linen and olive), used by .streamlit/config.toml and by the
extra CSS below. No Streamlit import here.

Streamlit's own theme settings (config.toml) colour the standard widgets. The CSS adds the
parts the settings cannot reach: serif headings, button shapes, the chat box, the alert box.
Keep the two in step: tests/test_theme.py compares config.toml with PALETTE.
"""

PALETTE = {
    "background": "#F4F0E6",   # linen
    "surface": "#FAF7F0",      # cards, buttons
    "surface_alt": "#EDE7D8",  # inputs, code chips
    "text": "#26261F",
    "muted": "#6B6A5C",
    "accent": "#5B6B3A",       # olive: buttons, links, progress
    "accent_dark": "#4A5A2C",
    "border": "#DDD7C3",
}

HEADING_FONT = "'Fraunces', 'Source Serif 4', Georgia, 'Times New Roman', serif"
BODY_FONT = "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"


def theme_css() -> str:
    p = PALETTE
    return f"""
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap');

html, body, .stApp, [data-testid="stAppViewContainer"] {{
    background: {p['background']};
    color: {p['text']};
    font-family: {BODY_FONT};
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ max-width: 760px; padding-top: 3rem; padding-bottom: 5rem; }}

h1, h2, h3, [data-testid="stHeading"] h1, [data-testid="stHeading"] h2, [data-testid="stHeading"] h3 {{
    font-family: {HEADING_FONT};
    font-weight: 600;
    letter-spacing: -0.01em;
    color: {p['text']};
}}
h1 {{ font-size: 2.4rem; line-height: 1.15; }}
h2, h3 {{ font-size: 1.55rem; }}
h4 {{ font-family: {BODY_FONT}; font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase;
     color: {p['muted']}; font-weight: 600; }}

/* buttons */
.stButton > button, [data-testid="stBaseButton-secondary"] {{
    background: {p['surface']};
    color: {p['text']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    font-weight: 500;
    padding: 0.5rem 1.15rem;
    box-shadow: 0 1px 0 rgba(38, 38, 31, 0.04);
    transition: border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
}}
.stButton > button:hover, [data-testid="stBaseButton-secondary"]:hover {{
    border-color: {p['accent']};
    color: {p['accent']};
    box-shadow: 0 2px 6px rgba(38, 38, 31, 0.08);
}}
.stButton > button:disabled, [data-testid="stBaseButton-secondary"]:disabled {{ opacity: 0.45; }}
.stButton > button[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] {{
    background: {p['accent']};
    border: 1px solid {p['accent']};
    color: {p['surface']};
    border-radius: 10px;
    font-weight: 600;
}}
.stButton > button[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primary"]:hover {{
    background: {p['accent_dark']};
    border-color: {p['accent_dark']};
    color: {p['surface']};
}}
[data-testid="stDownloadButton"] button {{ border-radius: 10px; }}

/* cards, chat, alerts */
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 14px; }}
[data-testid="stChatInput"] {{ border-radius: 14px; border: 1px solid {p['border']}; background: {p['surface']}; }}
[data-testid="stChatMessage"] {{ background: transparent; }}
[data-testid="stAlert"], [data-testid="stAlertContainer"], [data-testid="stAlert"] > div {{
    background: {p['surface_alt']} !important;
    border-radius: 12px;
}}
[data-testid="stAlert"] {{ border: 1px solid {p['border']}; border-radius: 12px; }}
[data-testid="stAlert"] p, [data-testid="stAlert"] svg {{ color: {p['text']}; fill: {p['text']}; }}
[data-testid="stExpander"] details {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 12px;
}}

/* small things */
code {{ background: {p['surface_alt']}; color: {p['accent']}; border-radius: 6px; padding: 0.1rem 0.4rem;
        font-size: 0.8rem; }}
a {{ color: {p['accent']}; text-underline-offset: 3px; }}
a:hover {{ color: {p['accent_dark']}; }}
hr {{ border-color: {p['border']}; }}
"""
