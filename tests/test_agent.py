from agent import run_agent
from app import handle_query


SELECTED_ITEM = {
    "id": "lst_001",
    "title": "Test Black Jacket",
    "description": "A black jacket for testing.",
    "category": "outerwear",
    "style_tags": ["classic"],
    "size": "M",
    "condition": "good",
    "price": 42.0,
    "colors": ["black"],
    "brand": None,
    "platform": "depop",
}


def test_run_agent_passes_state_between_tools(monkeypatch):
    calls = []

    def fake_search_listings(description, size=None, max_price=None):
        calls.append(("search", description, size, max_price))
        return [SELECTED_ITEM]

    def fake_suggest_outfit(new_item, wardrobe):
        calls.append(("suggest", new_item, wardrobe))
        assert new_item is SELECTED_ITEM
        return "Wear it with straight-leg jeans and low-top sneakers."

    def fake_create_fit_card(outfit, new_item):
        calls.append(("card", outfit, new_item))
        assert outfit == "Wear it with straight-leg jeans and low-top sneakers."
        assert new_item is SELECTED_ITEM
        return "STYLE RECOMMENDATION\nTest Black Jacket"

    monkeypatch.setattr("agent.search_listings", fake_search_listings)
    monkeypatch.setattr("agent.suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr("agent.create_fit_card", fake_create_fit_card)

    wardrobe = {"items": [{"id": "w_001", "name": "Straight-leg jeans"}]}
    session = run_agent("Find me a black jacket under $60 in size M", wardrobe)

    assert session["error"] is None
    assert session["parsed"] == {
        "description": "black jacket",
        "size": "M",
        "max_price": 60.0,
    }
    assert session["search_results"] == [SELECTED_ITEM]
    assert session["selected_item"] is SELECTED_ITEM
    assert session["outfit_suggestion"] == "Wear it with straight-leg jeans and low-top sneakers."
    assert session["fit_card"] == "STYLE RECOMMENDATION\nTest Black Jacket"
    assert calls == [
        ("search", "black jacket", "M", 60.0),
        ("suggest", SELECTED_ITEM, wardrobe),
        ("card", "Wear it with straight-leg jeans and low-top sneakers.", SELECTED_ITEM),
    ]


def test_run_agent_stops_when_search_returns_no_results(monkeypatch):
    calls = []

    def fake_search_listings(description, size=None, max_price=None):
        calls.append(("search", description, size, max_price))
        return []

    def fail_if_called(*args, **kwargs):
        raise AssertionError("This tool should not run when search has no results.")

    monkeypatch.setattr("agent.search_listings", fake_search_listings)
    monkeypatch.setattr("agent.suggest_outfit", fail_if_called)
    monkeypatch.setattr("agent.create_fit_card", fail_if_called)

    session = run_agent("designer ballgown size XXS under $5", {"items": []})

    assert calls == [("search", "designer ballgown", "XXS", 5.0)]
    assert session["error"] == (
        "No listings found matching your request. Try broader keywords such as "
        "'jacket', 'outerwear', or a different color."
    )
    assert session["search_results"] == []
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None


def test_handle_query_maps_success_session_to_three_panels(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {
            "error": None,
            "selected_item": SELECTED_ITEM,
            "outfit_suggestion": "Wear it with straight-leg jeans.",
            "fit_card": "STYLE RECOMMENDATION\nTest Black Jacket",
        }

    monkeypatch.setattr("app.run_agent", fake_run_agent)

    listing_text, outfit_text, fit_card = handle_query("black jacket", "Example wardrobe")

    assert "Test Black Jacket" in listing_text
    assert "Category: Outerwear" in listing_text
    assert outfit_text == "Wear it with straight-leg jeans."
    assert fit_card == "STYLE RECOMMENDATION\nTest Black Jacket"


def test_handle_query_maps_error_to_first_panel(monkeypatch):
    monkeypatch.setattr(
        "app.run_agent",
        lambda query, wardrobe: {
            "error": "No listings found matching your request.",
            "selected_item": None,
            "outfit_suggestion": None,
            "fit_card": None,
        },
    )

    listing_text, outfit_text, fit_card = handle_query("no match", "Example wardrobe")

    assert listing_text == "No listings found matching your request."
    assert outfit_text == ""
    assert fit_card == ""
