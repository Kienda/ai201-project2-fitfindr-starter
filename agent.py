"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


def _parse_price(query: str) -> float | None:
    price_patterns = [
        r"(?:under|below|less than|up to|no more than|max|maximum)\s*\$?\s*(\d+(?:\.\d+)?)",
        r"\$\s*(\d+(?:\.\d+)?)",
    ]
    for pattern in price_patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _parse_size(query: str) -> str | None:
    patterns = [
        r"(?:in\s+)?size\s+([a-z0-9./-]+)",
        r"\b(W\d{2}(?:\s*L\d{2})?)\b",
        r"\b(US\s*\d{1,2}(?:\.\d)?)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(1).strip()).upper()
    return None


def _description_from_query(query: str) -> str:
    description = query
    description = re.sub(
        r"(?:under|below|less than|up to|no more than|max|maximum)\s*\$?\s*\d+(?:\.\d+)?",
        " ",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(r"\$\s*\d+(?:\.\d+)?", " ", description)
    description = re.sub(r"(?:in\s+)?size\s+[a-z0-9./-]+", " ", description, flags=re.IGNORECASE)
    description = re.sub(r"\bUS\s*\d{1,2}(?:\.\d)?\b", " ", description, flags=re.IGNORECASE)
    description = re.sub(r"\bfind\s+me\b|\bi'?m\s+looking\s+for\b|\blooking\s+for\b", " ", description, flags=re.IGNORECASE)
    description = re.sub(r"[^a-zA-Z0-9\s/-]+", " ", description)
    description = re.sub(r"\s+", " ", description).strip()
    return description or query.strip()


def _parse_query(query: str) -> dict:
    return {
        "description": _description_from_query(query),
        "size": _parse_size(query),
        "max_price": _parse_price(query),
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    """
    session = _new_session(query, wardrobe)

    if not query or not query.strip():
        session["error"] = "Please describe the clothing item you want to find."
        return session

    session["parsed"] = _parse_query(query)

    results = search_listings(
        description=session["parsed"]["description"],
        size=session["parsed"]["size"],
        max_price=session["parsed"]["max_price"],
    )
    session["search_results"] = results

    if not results:
        session["error"] = (
            "No listings found matching your request. Try broader keywords such as "
            "'jacket', 'outerwear', or a different color."
        )
        return session

    session["selected_item"] = results[0]

    outfit = suggest_outfit(session["selected_item"], wardrobe)
    if not outfit or not outfit.strip():
        session["error"] = "Unable to generate an outfit recommendation for this item."
        return session
    session["outfit_suggestion"] = outfit

    fit_card = create_fit_card(outfit, session["selected_item"])
    if not fit_card or not fit_card.strip() or fit_card.startswith("Unable to create"):
        session["error"] = "Unable to create the final style card. Please try again."
        return session
    session["fit_card"] = fit_card

    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
