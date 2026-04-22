Overall structure and what do they use:

```
assets/
  parser.py
  validator.py
  resolver.py
  service.py
  storage.py
  models.py
```

## Assets tracking features !

- User type in what they buy, amount.

- - If no amount, reprompt till they provide the amount

- - If no provide a ticker symbol

    Query for possible names and reask the user

- - Calculate the money spent. Save the assets and symbol !

### doctrings:

```python
class AssetInput:
    """
    Represents a partially parsed user input.

    This object flows through the pipeline (parse → validate → resolve → process).
    It does not guarantee completeness.

    Attributes:
        raw_text   : Original user message
        name       : Asset name as typed by the user
        ticker     : Normalized ticker symbol (if resolved)
        amount     : Total money spent (user input)
        quantity   : Number of units purchased
    """

def parse_message(text: str) -> AssetInput:
    """
    Extract basic fields from user input.

    This step is intentionally loose — it only pulls out obvious values:
        - numbers (amount / quantity)
        - potential asset name

    No validation or correction happens here.


    Example:
        "buy 2 btc 1000"
        → quantity=2, name="btc", amount=1000

    Returns:
        AssetInput (possibly incomplete)
    """

  def require_amount(asset: AssetInput) -> str | None:
    """
    Ensure the user provided a total amount.

    Returns:
        None if valid
        A prompt message if missing
    """


def require_asset_name(asset: AssetInput) -> str | None:
    """
    Ensure the user specified what asset they are buying.

    Returns:
        None if valid
        A prompt message if missing
    """


def require_ticker(asset: AssetInput) -> str | None:
    """
    Ensure a ticker has been resolved.

    This function does NOT resolve it — only checks presence.

    Returns:
        None if valid
        A prompt message if missing
    """

  def search_ticker_candidates(query: str) -> list[str]:
    """
    Look up possible ticker symbols for a given name.

    This should query external APIs such as:
        - crypto (CoinGecko)
        - stocks (Alpha Vantage, Finnhub)

    Returns:
        A list of matching tickers (can be empty)
    """


def resolve_ticker(asset: AssetInput) -> list[str] | None:
    """
    Attempt to resolve a ticker from the asset name.

    Behavior:
        - If ticker already exists → return None
        - If no match → return []
        - If multiple matches → return list of candidates

    Used to decide whether to prompt the user again.
    """

    def calculate_spent(asset: AssetInput) -> float:
    """
    Compute how much money the user spent.

    Rules:
        - If amount is provided → use it directly
        - If only quantity is provided → requires price lookup (handled elsewhere)

    This function is pure logic — no API calls here.
    """


def enrich_with_price(asset: AssetInput) -> AssetInput:
    """
    Attach current price data to the asset.

    This is where external APIs are used.

    Used when:
        - user provides quantity but no total amount

    Returns:
        Updated AssetInput
    """


def process_asset_flow(text: str) -> dict:
    """
    Main entry point for handling user input.

    Flow:
        1. Parse input
        2. Validate required fields
     3. Resolve ticker
        4. If missing data → return prompt
        5. If complete → calculate and save

    Returns:
        {
            "status": "need_input" | "ok",
            "message": str,
            "data": optional
        }
    """

  def save_asset(asset: AssetInput) -> None:
    """
    Persist the asset record.

    Can be implemented using:
        - SQLite (local storage)
        - Firefly III (as a transaction or metadata)

    No return value.
    """


def get_user_assets(user_id: int) -> list:
    """
    Retrieve stored assets for a given user.

    Useful for:
        - portfolio tracking
        - reporting
    """
  def normalize_text(text: str) -> str:
    """
    Clean up user input.

    Typical steps:
        - lowercase
        - trim spaces
        - normalize formats (e.g. '50k' → '50000')
    """


def parse_amount_token(token: str) -> float | None:
    """
    Convert shorthand numbers into floats.

    Examples:
        50k → 50000
        2m  → 2000000

    Returns:
        float or None if parsing fails
    """


def is_number(token: str) -> bool:
    """
    Check whether a token represents a numeric value.
    """

  def merge_with_session(previous: AssetInput, new_text: str) -> AssetInput:
    """
    Merge new user input into an existing incomplete asset.

    Used for multi-step conversations:
        User: "buy btc"
        Bot: "how much?"
        User: "1000"

    This function combines both into a complete AssetInput.
    """

  `
```
