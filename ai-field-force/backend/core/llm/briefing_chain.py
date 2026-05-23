import os
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from core.llm.prompts.briefing import BRIEFING_PROMPT, get_language_instruction

load_dotenv()

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    api_key=os.getenv("OPENAI_API_KEY")
)


def run_briefing_chain(context: dict, nba_actions: list, lang: str = "en") -> str:
    """Generate a visit briefing in the requested language.

    Args:
        context:      Entity profile + signal dict.
        nba_actions:  Ordered list of recommended next-best actions.
        lang:         ISO language code ('en', 'hi', 'gu', 'bn'). Falls back to English.
    """
    prompt = PromptTemplate(
        input_variables=["entity_profile", "signal_summary", "nba_actions", "language_instruction"],
        template=BRIEFING_PROMPT
    )
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({
        "entity_profile":       format_profile(context),
        "signal_summary":       format_signals(context),
        "nba_actions":          format_actions(nba_actions),
        "language_instruction": get_language_instruction(lang),
    })


def format_profile(ctx: dict) -> str:
    return f"{ctx['name']} | {ctx['type']} | Region: {ctx.get('region', 'unknown')}"


def format_signals(ctx: dict) -> str:
    s = ctx
    return (
        f"Pest: {s.get('pest_alert_severity', 'none')} | "
        f"Stock shortage: {s.get('inventory_shortage_level', 0):.0%} | "
        f"Days since visit: {s.get('days_since_last_visit', '?')} | "
        f"Crop stage: {s.get('crop_stage', 'unknown')}"
    )


def format_actions(actions: list) -> str:
    if not actions:
        return "General relationship maintenance visit"
    return "\n".join(
        f"{i+1}. {a.get('action', '')}: {a.get('detail', '')}"
        for i, a in enumerate(actions)
    )