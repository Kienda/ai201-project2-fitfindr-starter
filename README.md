# FitFindr

FitFindr helps a user find a secondhand clothing listing from a natural language request, then recommends an outfit and produces a final fit card.

## Setup

```bash
pip install -r requirements.txt
```

Optional LLM-powered wording uses Groq. Add a `.env` file if you want live model responses:

```text
GROQ_API_KEY=your_key_here
```

The app still works without an API key because the tools include local fallback styling and fit-card generation.

## Run

```bash
python app.py
```

Then open the local Gradio URL printed in the terminal.

## Tool Inventory

### `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

Searches `data/listings.json` for listings matching the user's description. It filters by optional size and maximum price, scores the remaining listings by keyword/category/color/style relevance, and returns matching listing dictionaries sorted best-first.

### `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

Creates one outfit recommendation for the selected listing. If the wardrobe has saved items, it prefers named wardrobe pieces; if the wardrobe is empty, it returns general styling advice for the selected item.

### `create_fit_card(outfit: str, new_item: dict) -> str`

Creates the final user-facing recommendation card. The card includes the selected item, category, price, platform, suggested outfit, and a short explanation of why the outfit works.

## Interaction Walkthrough

**User query:**
`vintage graphic tee under $30`

**Step 1 - Tool called:**
- Tool: `search_listings`
- Input: `description="vintage graphic tee"`, `size=None`, `max_price=30.0`
- Why this tool: The agent needs to find matching listings before it can style anything.
- Output: A ranked list of matches, with `Graphic Tee - 2003 Tour Bootleg Style` selected as the top result.

**Step 2 - Tool called:**
- Tool: `suggest_outfit`
- Input: the selected listing and the chosen wardrobe.
- Why this tool: The selected item needs to be turned into a wearable outfit recommendation.
- Output: A styling suggestion using the selected tee with compatible wardrobe pieces such as denim, sneakers, and an outer layer.

**Step 3 - Tool called:**
- Tool: `create_fit_card`
- Input: the outfit suggestion and selected listing.
- Why this tool: The final response should be a shareable recommendation card, not just raw tool output.
- Output: A formatted fit card with item details, outfit, and why the pairing works.

**Final output to user:**
The Gradio app shows three panels: the top listing found, the outfit idea, and the final fit card.

## Error Handling and Fail Points

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No results match the parsed description, size, and price filters | Stop execution and show "No listings found matching your request. Try broader keywords such as 'jacket', 'outerwear', or a different color." |
| `suggest_outfit` | The selected item is missing or no recommendation can be generated | Stop execution and show "Unable to generate an outfit recommendation for this item." |
| `create_fit_card` | The outfit text or selected item is missing | Stop execution and show "Unable to create the final style card. Please try again." |

## Spec Reflection

**One way planning.md helped during implementation:**
The planning document made the data flow explicit: query parsing feeds search, search stores a selected item, the selected item feeds outfit generation, and the outfit feeds card creation. That made the early-return error branches straightforward because each tool has a clear prerequisite.

**One divergence from your spec, and why:**
The attached plan listed `search_listings(description: str)`, but the starter code already defined optional `size` and `max_price` parameters and the README warned that signatures should match the implementation. I kept the starter signature and treated size and price as optional filters, which preserves compatibility while still following the planned search-first workflow.
