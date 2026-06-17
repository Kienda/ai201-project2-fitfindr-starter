from tools import create_fit_card, search_listings, suggest_outfit


SAMPLE_ITEM = {
    "id": "lst_test",
    "title": "Graphic Tee - 2003 Tour Bootleg Style",
    "description": "Vintage-style bootleg tee with faded graphic.",
    "category": "tops",
    "style_tags": ["graphic tee", "vintage", "streetwear"],
    "size": "L",
    "condition": "good",
    "price": 24.00,
    "colors": ["black"],
    "brand": None,
    "platform": "depop",
}


EXAMPLE_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "Baggy straight-leg jeans, dark wash",
            "category": "bottoms",
            "colors": ["dark blue", "indigo"],
            "style_tags": ["denim", "streetwear", "baggy"],
            "notes": "High-waisted",
        },
        {
            "id": "w_002",
            "name": "Chunky white sneakers",
            "category": "shoes",
            "colors": ["white"],
            "style_tags": ["sneakers", "chunky", "streetwear"],
            "notes": None,
        },
    ]
}


def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)

    assert isinstance(results, list)
    assert len(results) > 0
    assert all("title" in item for item in results)


def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)

    assert results == []


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)

    assert all(item["price"] <= 10 for item in results)


def test_suggest_outfit_uses_llm_for_wardrobe(monkeypatch):
    calls = []

    def fake_completion(prompt, temperature=0.6):
        calls.append({"prompt": prompt, "temperature": temperature})
        return "Wear it with baggy straight-leg jeans and chunky white sneakers."

    monkeypatch.setattr("tools._try_groq_completion", fake_completion)

    outfit = suggest_outfit(SAMPLE_ITEM, EXAMPLE_WARDROBE)

    assert outfit == "Wear it with baggy straight-leg jeans and chunky white sneakers."
    assert calls
    assert "Baggy straight-leg jeans" in calls[0]["prompt"]
    assert calls[0]["temperature"] == 0.5


def test_suggest_outfit_empty_wardrobe_does_not_crash(monkeypatch):
    monkeypatch.setattr("tools._try_groq_completion", lambda *args, **kwargs: None)

    outfit = suggest_outfit(SAMPLE_ITEM, {"items": []})

    assert isinstance(outfit, str)
    assert SAMPLE_ITEM["title"] in outfit
    assert outfit.strip() != ""


def test_suggest_outfit_missing_item_returns_empty_string():
    assert suggest_outfit({}, EXAMPLE_WARDROBE) == ""


def test_create_fit_card_uses_llm_with_high_temperature(monkeypatch):
    calls = []

    def fake_completion(prompt, temperature=0.6):
        calls.append({"prompt": prompt, "temperature": temperature})
        return "Fit card variation from the LLM."

    monkeypatch.setattr("tools._try_groq_completion", fake_completion)

    card = create_fit_card("Pair it with jeans and sneakers.", SAMPLE_ITEM)

    assert card == "Fit card variation from the LLM."
    assert calls
    assert SAMPLE_ITEM["title"] in calls[0]["prompt"]
    assert calls[0]["temperature"] >= 0.8


def test_create_fit_card_empty_outfit_returns_error():
    card = create_fit_card("", SAMPLE_ITEM)

    assert card == "Unable to create the final style card. Please try again."


def test_create_fit_card_missing_item_returns_error():
    card = create_fit_card("Pair it with jeans and sneakers.", {})

    assert card == "Unable to create the final style card. Please try again."
