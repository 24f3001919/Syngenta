BRIEFING_PROMPT = """
You are a field sales coach for Syngenta India.

Farmer/Retailer Profile:
{entity_profile}

Today's Signals:
{signal_summary}

Recommended Actions (in priority order):
{nba_actions}

Write a visit briefing in under 120 words:
- What to open with
- What to discuss (tied to the actions above)
- One specific product to mention if relevant
- One key question to ask before leaving

Tone: Direct. Practical. Like a smart colleague, not a bot.
Do not use bullet points. Write in flowing sentences.

{language_instruction}
"""

# Language-specific output instructions appended to the base prompt.
# Use plain English for "en"; explicit script directives for others so the LLM
# does not default back to Latin script.
LANGUAGE_INSTRUCTIONS = {
    "en": "Respond in English.",
    "hi": (
        "Respond entirely in Hindi using Devanagari script (देवनागरी लिपि). "
        "Use natural agricultural terminology. Product names like 'Syngenta' "
        "may stay in Latin script. Do not include any English sentences."
    ),
    "gu": (
        "Respond entirely in Gujarati using Gujarati script (ગુજરાતી લિપિ). "
        "Use natural agricultural terminology. Product names like 'Syngenta' "
        "may stay in Latin script. Do not include any English sentences."
    ),
    "bn": (
        "Respond entirely in Bengali using Bengali script (বাংলা লিপি). "
        "Use natural agricultural terminology. Product names like 'Syngenta' "
        "may stay in Latin script. Do not include any English sentences."
    ),
}


def get_language_instruction(lang: str) -> str:
    """Return the appropriate language instruction; fall back to English."""
    return LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["en"])