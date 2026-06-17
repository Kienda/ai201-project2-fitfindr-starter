# FitFindr

FitFindr is a small planning-loop agent that helps a user discover a secondhand clothing item and turn it into a styled outfit recommendation. The user enters a natural language request like "vintage graphic tee under $30"; the agent searches mock listings, selects the best match, generates an outfit idea, and returns a final fit card through a Gradio interface.

## Setup

```bash
pip install -r requirements.txt
```

Optional LLM-powered wording uses Groq. Add a `.env` file in the project root:

```text
GROQ_API_KEY=your_key_here
```

The app also includes deterministic fallback output, so local tests can run without making API calls.

## Run

```bash
python app.py
```

Open the Gradio URL printed in the terminal. For the final checkpoint, the app was verified at:

```text
http://localhost:7860
```

## Tool Inventory

### `search_listings(description: str, size: str | None = None, max_price: float | None = None) -> list[dict]`

Purpose: searches `data/listings.json` for listings matching the user's clothing request.

Inputs:
- `description` (`str`): the clothing request after query parsing, such as `"vintage graphic tee"` or `"black jacket"`.
- `size` (`str | None`): optional size filter, such as `"M"`, `"W28"`, or `"US 8"`.
- `max_price` (`float | None`): optional maximum price filter.

Output: a `list[dict]` of matching listing dictionaries sorted by relevance. Each listing includes fields such as `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Failure behavior: returns `[]` when no listings match. It does not raise an exception.

### `suggest_outfit(new_item: dict, wardrobe: dict) -> str`

Purpose: creates an outfit recommendation for the selected listing.

Inputs:
- `new_item` (`dict`): the listing selected from `search_listings`.
- `wardrobe` (`dict`): a wardrobe dictionary with an `items` list.

Output: a non-empty `str` containing a styling recommendation.

Failure behavior: if `new_item` is missing or invalid, it returns `""` so the planning loop can stop with a clear error. If the wardrobe is empty, it returns general styling advice instead of crashing.

### `create_fit_card(outfit: str, new_item: dict) -> str`

Purpose: creates the final user-facing fit card.

Inputs:
- `outfit` (`str`): the outfit recommendation from `suggest_outfit`.
- `new_item` (`dict`): the selected listing.

Output: a formatted `str` containing the selected item, category, price, platform, suggested outfit, and why the outfit works.

Failure behavior: if `outfit` is empty or `new_item` is missing, it returns `"Unable to create the final style card. Please try again."`

## Planning Loop

The agent does not call every tool unconditionally. It follows a conditional sequence where each tool depends on state created by the previous step.

1. `run_agent(query, wardrobe)` creates a fresh session dictionary.
2. The query is parsed into `description`, `size`, and `max_price`.
3. The agent calls `search_listings(description, size, max_price)`.
4. If search returns `[]`, the agent stores an error in `session["error"]` and returns immediately. It does not call `suggest_outfit` or `create_fit_card`.
5. If search returns results, the agent selects `results[0]` and stores it in `session["selected_item"]`.
6. The agent calls `suggest_outfit(session["selected_item"], wardrobe)`.
7. If the outfit string is empty, the agent stores an error and returns immediately.
8. If an outfit is returned, the agent stores it in `session["outfit_suggestion"]`.
9. The agent calls `create_fit_card(session["outfit_suggestion"], session["selected_item"])`.
10. If the card cannot be created, the agent stores an error. Otherwise it stores the final card in `session["fit_card"]`.

This means the agent behaves differently depending on input. A successful query flows through all three tools. An impossible query stops after search and returns a helpful message.

## State Management

The session dictionary is the source of truth for one user interaction:

```python
session = {
    "query": query,
    "parsed": {},
    "search_results": [],
    "selected_item": None,
    "wardrobe": wardrobe,
    "outfit_suggestion": None,
    "fit_card": None,
    "error": None,
}
```

State flow:
- `session["parsed"]` stores the extracted search parameters.
- `session["search_results"]` stores the list returned by `search_listings`.
- `session["selected_item"]` stores the first listing from `search_results`.
- That same selected-item dictionary is passed into `suggest_outfit`.
- `session["outfit_suggestion"]` stores the exact string returned by `suggest_outfit`.
- That outfit string and selected item are passed into `create_fit_card`.
- `session["fit_card"]` stores the final output.
- `session["error"]` stores the reason for early termination.

Example state check from Milestone 4:

```text
QUERY: Find me a black jacket under $80 in size M
parsed: {'description': 'black jacket', 'size': 'M', 'max_price': 80.0}
search_results_count: 1
selected_item: 90s Leather Bomber — Black
first_result_same_object: True
fit_card_contains_selected_title: True
fit_card_contains_outfit: True
error: None
```

## Error Handling

| Tool | Failure mode | Agent response | Concrete test example |
|------|--------------|----------------|-----------------------|
| `search_listings` | No listing matches the query, size, and price filters | Stop execution, keep `selected_item`, `outfit_suggestion`, and `fit_card` as `None`, and return a helpful error | `search_listings("designer ballgown", size="XXS", max_price=5)` returned `[]` |
| `suggest_outfit` | Empty wardrobe | Return general styling advice instead of crashing | `suggest_outfit(result, get_empty_wardrobe())` returned advice about relaxed denim, wide-leg trousers, sneakers, and a simple jacket |
| `suggest_outfit` | Missing selected item | Return `""`, which causes the planning loop to stop | Covered by `tests/test_tools.py` |
| `create_fit_card` | Empty outfit string | Return a descriptive error string | `create_fit_card("", result)` returned `"Unable to create the final style card. Please try again."` |

Milestone 5 evidence is saved in:
- `docs/milestone5_failure_modes.md`
- `docs/milestone5_no_results_failure.png`

## Interaction Walkthrough

Example user query:

```text
Find me a black jacket under $80 in size M
```

Step 1: The agent parses the query:

```python
{
    "description": "black jacket",
    "size": "M",
    "max_price": 80.0,
}
```

Step 2: The agent calls:

```python
search_listings("black jacket", size="M", max_price=80.0)
```

Step 3: Search returns a matching listing, and the agent stores the first result:

```python
session["selected_item"] = results[0]
```

For this query, the selected item is:

```text
90s Leather Bomber — Black
```

Step 4: The agent calls:

```python
suggest_outfit(session["selected_item"], wardrobe)
```

Step 5: The returned outfit suggestion is stored in:

```python
session["outfit_suggestion"]
```

Step 6: The agent calls:

```python
create_fit_card(session["outfit_suggestion"], session["selected_item"])
```

Final output: Gradio shows the selected listing, the outfit idea, and the final fit card in three separate panels.

## Testing

Run all tests:

```bash
python -m pytest tests/
```

Current result:

```text
13 passed
```

The tests cover:
- Search success.
- Search no-results failure.
- Price filtering.
- Empty wardrobe handling.
- Empty fit-card input handling.
- Planning-loop state passing.
- Planning-loop early stop when search returns no results.
- Gradio handler success and error output mapping.

## AI Usage

### Instance 1: Tool implementation from the tool specs

Input given to AI: the Tool 1, Tool 2, and Tool 3 sections from `planning.md`, including function names, parameters, return values, and failure behavior.

AI output: initial implementations for `search_listings`, `suggest_outfit`, and `create_fit_card`.

What I revised or overrode:
- I kept the starter repo's actual function signatures instead of simplifying to `search_listings(description)` because the project instructions require README signatures to match the code.
- I added deterministic fallback behavior so tests can run without a live Groq call.
- I tightened search scoring so explicit category requests like `"jacket"` do not incorrectly match unrelated black tops.

### Instance 2: Planning loop and state management

Input given to AI: the Planning Loop, State Management, Error Handling, and Architecture sections from `planning.md`.

AI output: a `run_agent()` flow that parsed the user query, called search, selected the first result, generated an outfit, and created a fit card.

What I revised or overrode:
- I added early returns after every failure branch so later tools are not called after a failed search or empty outfit.
- I added pytest tests with monkeypatched tool calls to prove `selected_item` and `outfit_suggestion` are the same values passed between steps.
- I adjusted query parsing so `"Find me a black jacket under $80 in size M"` stores `description="black jacket"` instead of keeping the leading article.

### Instance 3: Failure-mode documentation

Input given to AI: the Milestone 5 checklist requiring deliberate failures for no search results, empty wardrobe, and empty outfit string.

AI output: command examples and evidence format for recording the triggered failures.

What I revised or overrode:
- I ran the commands directly in the local environment and copied the actual outputs into `docs/milestone5_failure_modes.md`.
- I generated a readable PNG artifact for the no-results failure path to use in the demo video.

## Spec Reflection

One way `planning.md` helped during implementation:
The planning document made the dependency chain explicit. Search has to produce a selected item before outfit generation can run, and outfit generation has to produce a string before the fit card can run. That made it straightforward to design early-return error branches instead of calling all tools every time.

One divergence from the original spec, and why:
The original pasted plan described `search_listings(description: str)`, but the starter repo already had `search_listings(description, size=None, max_price=None)`. I kept the starter signature because the grading instructions say the documented interfaces must match the actual function signatures. This also made the agent more useful because users can request a size and price ceiling in the natural language query.

## Demo Video Outline

Use this outline for the 3-5 minute recording:

1. Open `http://localhost:7860`.
2. Enter `Find me a black jacket under $80 in size M`.
3. Explain that `run_agent` parses the query into `description`, `size`, and `max_price`.
4. Point to the listing panel and explain that `search_listings` selected `90s Leather Bomber — Black`.
5. Point to the outfit panel and explain that the selected listing dictionary is passed into `suggest_outfit`.
6. Point to the fit-card panel and explain that the outfit string and selected item are passed into `create_fit_card`.
7. Run the failure query `designer ballgown size XXS under $5`.
8. Explain that search returns `[]`, so the planning loop stops early and does not call the outfit or fit-card tools.
9. Show `docs/milestone5_no_results_failure.png` as recorded evidence of the failure-mode test.
