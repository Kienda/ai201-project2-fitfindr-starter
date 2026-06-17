"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "any",
    "are",
    "around",
    "as",
    "at",
    "for",
    "find",
    "finding",
    "get",
    "give",
    "i",
    "im",
    "in",
    "is",
    "it",
    "looking",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "show",
    "some",
    "something",
    "than",
    "the",
    "to",
    "under",
    "up",
    "want",
    "with",
}

_CATEGORY_ALIASES = {
    "accessories": {"accessory", "accessories", "bag", "belt", "hat", "jewelry"},
    "bottoms": {"bottom", "bottoms", "jean", "jeans", "pant", "pants", "skirt", "shorts", "trouser", "trousers"},
    "outerwear": {"blazer", "coat", "hoodie", "jacket", "outerwear", "sweater", "sweatshirt"},
    "shoes": {"boot", "boots", "loafer", "loafers", "shoe", "shoes", "sneaker", "sneakers"},
    "tops": {"blouse", "buttondown", "shirt", "tank", "tee", "top", "tops", "tshirt"},
}

_TOKEN_ALIASES = {
    "babytee": {"baby", "tee", "top"},
    "buttondown": {"button", "down", "shirt"},
    "crewneck": {"crew", "neck", "sweatshirt"},
    "denim": {"jeans"},
    "graphic": {"print"},
    "jacket": {"outerwear"},
    "midi": {"skirt"},
    "sneakers": {"shoes"},
    "tee": {"shirt", "top"},
    "tshirt": {"tee", "shirt", "top"},
    "y2k": {"2000s"},
}

_CATEGORY_NEEDS = {
    "accessories": ["tops", "bottoms", "shoes", "outerwear"],
    "bottoms": ["tops", "shoes", "outerwear", "accessories"],
    "outerwear": ["tops", "bottoms", "shoes", "accessories"],
    "shoes": ["tops", "bottoms", "outerwear", "accessories"],
    "tops": ["bottoms", "shoes", "outerwear", "accessories"],
}


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _normalize_text(value: object) -> str:
    """Lowercase text and keep only simple searchable word characters."""
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _tokenize(value: object) -> list[str]:
    tokens = _normalize_text(value).split()
    return [token for token in tokens if token and token not in _STOP_WORDS]


def _listing_search_text(listing: dict) -> str:
    parts = [
        listing.get("title", ""),
        listing.get("description", ""),
        listing.get("category", ""),
        listing.get("size", ""),
        listing.get("condition", ""),
        listing.get("brand", "") or "",
        listing.get("platform", ""),
        " ".join(listing.get("colors", [])),
        " ".join(listing.get("style_tags", [])),
    ]
    return " ".join(parts)


def _expand_tokens(tokens: list[str]) -> set[str]:
    expanded = set(tokens)
    for token in tokens:
        expanded.update(_TOKEN_ALIASES.get(token, set()))
        for category, aliases in _CATEGORY_ALIASES.items():
            if token in aliases:
                expanded.add(category)
    return expanded


def _requested_categories(tokens: set[str]) -> set[str]:
    categories = set()
    for category, aliases in _CATEGORY_ALIASES.items():
        if category in tokens or tokens.intersection(aliases):
            categories.add(category)
    return categories


def _size_parts(size: object) -> set[str]:
    compact = re.sub(r"\s+", "", str(size).lower())
    parts = {compact}

    if compact.startswith("us") and len(compact) > 2:
        parts.add(compact[2:])

    for match in re.findall(r"[a-z]+\d+(?:\.\d+)?|[a-z]+|\d+(?:\.\d+)?", compact):
        parts.add(match)

    return {part for part in parts if part}


def _size_matches(listing_size: object, requested_size: str | None) -> bool:
    if not requested_size:
        return True
    requested_parts = _size_parts(requested_size)
    listing_parts = _size_parts(listing_size)
    return bool(requested_parts.intersection(listing_parts))


def _condition_rank(condition: str) -> int:
    return {"excellent": 3, "good": 2, "fair": 1}.get(str(condition).lower(), 0)


def _score_listing(listing: dict, description: str) -> int:
    original_token_list = _tokenize(description)
    original_tokens = set(original_token_list)
    query_tokens = _expand_tokens(original_token_list)
    if not original_tokens:
        return 0

    query_text = _normalize_text(description)
    listing_text = _normalize_text(_listing_search_text(listing))
    listing_tokens = set(_tokenize(listing_text))
    score = 0
    category_terms = set(_CATEGORY_ALIASES.keys())
    for aliases in _CATEGORY_ALIASES.values():
        category_terms.update(aliases)
    content_tokens = original_tokens - category_terms
    has_content_match = any(
        token in listing_tokens or (len(token) > 3 and token in listing_text)
        for token in content_tokens
    )
    if content_tokens and not has_content_match:
        return 0

    for token in query_tokens:
        if token in listing_tokens:
            score += 3
        elif len(token) > 3 and token in listing_text:
            score += 1

    requested_categories = _requested_categories(query_tokens)
    if requested_categories and listing.get("category") not in requested_categories:
        return 0

    if listing.get("category") in requested_categories:
        score += 5

    title_text = _normalize_text(listing.get("title", ""))
    for token in query_tokens:
        if token in title_text.split():
            score += 2

    query_phrases = [
        " ".join(original_token_list[index : index + 2])
        for index in range(len(original_token_list) - 1)
    ]
    for phrase in query_phrases:
        if phrase in title_text:
            score += 8
        elif phrase in listing_text:
            score += 3

    for color in listing.get("colors", []):
        color_text = _normalize_text(color)
        if color_text and color_text in query_text:
            score += 4

    for tag in listing.get("style_tags", []):
        tag_text = _normalize_text(tag)
        if tag_text and tag_text in query_text:
            score += 5
        elif set(tag_text.split()).intersection(query_tokens):
            score += 2

    return score


def _format_price(price: object) -> str:
    try:
        amount = float(price)
    except (TypeError, ValueError):
        return "price unavailable"
    return f"${amount:.0f}" if amount.is_integer() else f"${amount:.2f}"


def _format_item_for_prompt(item: dict) -> str:
    colors = ", ".join(item.get("colors", [])) or "unspecified colors"
    tags = ", ".join(item.get("style_tags", [])) or "no style tags"
    return (
        f"{item.get('title', 'Unknown item')} | "
        f"category: {item.get('category', 'unknown')} | "
        f"price: {_format_price(item.get('price'))} | "
        f"size: {item.get('size', 'unknown')} | "
        f"colors: {colors} | style: {tags}"
    )


def _try_groq_completion(prompt: str, temperature: float = 0.6) -> str | None:
    """
    Try an LLM completion when a key is configured. Return None on any failure
    so the app remains usable offline and during local tests.
    """
    if os.environ.get("FITFINDR_DISABLE_LLM", "").lower() in {"1", "true", "yes"}:
        return None
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key or api_key.lower().startswith("your_"):
        return None

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a concise secondhand fashion stylist. "
                        "Give practical, specific advice and do not invent item details."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=220,
            temperature=temperature,
        )
    except Exception:
        return None

    text = response.choices[0].message.content if response.choices else ""
    text = text.strip()
    return text or None


def _wardrobe_items(wardrobe: dict) -> list[dict]:
    if not isinstance(wardrobe, dict):
        return []
    items = wardrobe.get("items", [])
    return items if isinstance(items, list) else []


def _item_match_score(new_item: dict, wardrobe_item: dict) -> int:
    new_tags = set(_tokenize(" ".join(new_item.get("style_tags", []))))
    old_tags = set(_tokenize(" ".join(wardrobe_item.get("style_tags", []))))
    new_colors = set(_tokenize(" ".join(new_item.get("colors", []))))
    old_colors = set(_tokenize(" ".join(wardrobe_item.get("colors", []))))

    score = len(new_tags.intersection(old_tags)) * 3
    score += len(new_colors.intersection(old_colors)) * 2
    if wardrobe_item.get("category") != new_item.get("category"):
        score += 1
    return score


def _choose_wardrobe_piece(items: list[dict], category: str, new_item: dict, used_ids: set[str]) -> dict | None:
    candidates = [
        item
        for item in items
        if item.get("category") == category and item.get("id") not in used_ids
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: (_item_match_score(new_item, item), item.get("name", "")))


def _general_style_advice(new_item: dict) -> str:
    title = new_item.get("title", "This item")
    category = new_item.get("category", "")
    tags = ", ".join(new_item.get("style_tags", [])[:3]) or "everyday"

    templates = {
        "accessories": "Use it to finish a simple base outfit: a fitted tee or tank, relaxed jeans, and clean sneakers.",
        "bottoms": "Pair it with a fitted tank or soft tee, a light jacket, and sneakers or boots depending on the vibe.",
        "outerwear": "Layer it over a plain tee or ribbed tank with straight-leg jeans and low-profile sneakers.",
        "shoes": "Build around them with straight-leg denim, a simple top, and one accessory that repeats the shoe color.",
        "tops": "Style it with relaxed denim or wide-leg trousers, then add sneakers and a simple jacket.",
    }
    advice = templates.get(category, "Keep the rest of the outfit simple so the piece stays intentional.")
    return f"{title} has a {tags} feel. {advice}"


def _fallback_outfit(new_item: dict, wardrobe: dict) -> str:
    items = _wardrobe_items(wardrobe)
    if not items:
        return _general_style_advice(new_item)

    used_ids: set[str] = set()
    selected = []
    for category in _CATEGORY_NEEDS.get(new_item.get("category"), ["tops", "bottoms", "shoes", "accessories"]):
        piece = _choose_wardrobe_piece(items, category, new_item, used_ids)
        if piece:
            selected.append(piece)
            used_ids.add(piece.get("id", ""))

    if not selected:
        return _general_style_advice(new_item)

    piece_names = [piece.get("name", "an existing wardrobe piece") for piece in selected[:3]]
    if len(piece_names) == 1:
        pairing = piece_names[0]
    elif len(piece_names) == 2:
        pairing = f"{piece_names[0]} and {piece_names[1]}"
    else:
        pairing = f"{', '.join(piece_names[:-1])}, and {piece_names[-1]}"

    title = new_item.get("title", "this item")
    tags = new_item.get("style_tags", [])
    vibe = tags[0] if tags else "balanced"
    return (
        f"Style {title} with {pairing}. "
        f"The combination keeps the {vibe} feel of the thrifted piece while using items already in your wardrobe."
    )


def _why_it_works(new_item: dict) -> str:
    category = new_item.get("category", "")
    tags = new_item.get("style_tags", [])
    colors = new_item.get("colors", [])
    style = tags[0] if tags else "personal"
    color = colors[0] if colors else "neutral"

    if category == "outerwear":
        return f"The {color} outer layer adds structure while the {style} styling keeps the outfit intentional."
    if category == "tops":
        return f"The top anchors the outfit with a {style} focal point while the other pieces balance the silhouette."
    if category == "bottoms":
        return f"The bottoms set the silhouette, and the supporting pieces keep the {style} mood wearable."
    if category == "shoes":
        return f"The shoes ground the look and repeat the {style} energy without making the outfit feel overdone."
    if category == "accessories":
        return f"The accessory adds a finishing detail that ties the outfit together through color and texture."
    return "The outfit balances color, silhouette, and style tags from the selected piece."


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    """
    if not description or not description.strip():
        return []

    matches: list[tuple[int, dict]] = []
    for listing in load_listings():
        if max_price is not None and float(listing.get("price", 0)) > max_price:
            continue
        if not _size_matches(listing.get("size", ""), size):
            continue

        score = _score_listing(listing, description)
        if score > 0:
            matches.append((score, listing))

    matches.sort(
        key=lambda scored: (
            scored[0],
            _condition_rank(scored[1].get("condition", "")),
            -float(scored[1].get("price", 0)),
        ),
        reverse=True,
    )
    return [listing for _, listing in matches]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    """
    if not isinstance(new_item, dict) or not new_item:
        return ""

    items = _wardrobe_items(wardrobe)
    if items:
        wardrobe_lines = "\n".join(
            f"- {item.get('name', 'Unnamed item')} ({item.get('category', 'unknown')}; "
            f"colors: {', '.join(item.get('colors', []))}; "
            f"style: {', '.join(item.get('style_tags', []))})"
            for item in items
        )
        prompt = (
            "Suggest one complete outfit using the new thrifted item and named pieces "
            "from this wardrobe. Keep it to 2-3 sentences.\n\n"
            f"New item: {_format_item_for_prompt(new_item)}\n\n"
            f"Wardrobe:\n{wardrobe_lines}"
        )
    else:
        prompt = (
            "Suggest one complete outfit for this thrifted item for a user with no saved wardrobe yet. "
            "Keep it to 2-3 sentences and mention the types of pieces to pair with it.\n\n"
            f"New item: {_format_item_for_prompt(new_item)}"
        )

    return _try_groq_completion(prompt, temperature=0.5) or _fallback_outfit(new_item, wardrobe)


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    """
    if not outfit or not outfit.strip() or not isinstance(new_item, dict) or not new_item:
        return "Unable to create the final style card. Please try again."

    prompt = (
        "Create a short fit card for a secondhand find. Include the item name, "
        "price, platform, the outfit suggestion, and one sentence explaining why it works. "
        "Use a casual but clear tone.\n\n"
        f"Item: {_format_item_for_prompt(new_item)}\n\n"
        f"Outfit suggestion: {outfit}"
    )
    llm_card = _try_groq_completion(prompt, temperature=0.9)
    if llm_card:
        return llm_card

    title = new_item.get("title", "Selected item")
    category = str(new_item.get("category", "unknown")).title()
    platform = str(new_item.get("platform", "unknown")).title()
    price = _format_price(new_item.get("price"))

    return (
        "STYLE RECOMMENDATION\n\n"
        "Selected Item:\n"
        f"{title}\n\n"
        "Category:\n"
        f"{category}\n\n"
        "Price:\n"
        f"{price}\n\n"
        "Platform:\n"
        f"{platform}\n\n"
        "Suggested Outfit:\n"
        f"{outfit.strip()}\n\n"
        "Why It Works:\n"
        f"{_why_it_works(new_item)}"
    )
