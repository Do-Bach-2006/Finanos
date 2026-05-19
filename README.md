Overall structure of the project

```
finanos/
  README.md
  .env
  .env.example
  requirements.txt
  server.py

  app/
    __init__.py
    config.py
    bootstrap.py

    core/
      router.py
      intents.py
      commands.py
      responses.py
      exceptions.py

    interfaces/
      telegram/
        bot.py
        handlers.py
        formatters.py

      web/
        routes.py
        dashboard.py
        templates/
        static/

      cli/
        listener.py

    modules/
      assets/
        models.py
        parser.py
        service.py
        portfolio.py
        pricing.py
        storage.py

      transactions/
        models.py
        parser.py
        service.py
        history.py
        reports.py

      debt/
        models.py
        parser.py
        service.py
        reminders.py
        interest.py

      market/
        crypto.py
        stocks.py
        forex.py
        cs2.py
        service.py

    integrations/
      firefly/
        client.py
        mapper.py

      telegram/
        client.py

      crypto/
        coingecko.py
        coinmarketcap.py

      stocks/
        finnhub.py
        alphavantage.py

      forex/
        exchangerate_api.py
        currencyfreaks.py

      cs2/
        price_provider.py
        steam_market.py

    storage/
      database.py
      migrations/
      repositories/
        asset_repo.py
        transaction_repo.py
        debt_repo.py
        settings_repo.py

    settings/
      models.py
      service.py
      defaults.py

    scheduler/
      jobs.py
      alerts.py
      reports.py
      README.md

    utils/
      money.py
      text.py
      dates.py
      logging.py
```

## Assets tracking features

- User type in what they buy, amount.

- - If no amount, reprompt till they provide the amount

- - If no provide a ticker symbol

    Query for possible names and reask the user

### Docstrings for each files

```text
finanos/
  README.md
    """
    Project overview.

    Explains what FinanOS does, how to set it up, which APIs are required,
    and how the local server, Telegram bot, Firefly III, and market APIs work
    together.
    """

  .env
    """
    Local runtime secrets.

    Stores API keys, bot tokens, database URL, and user-specific configuration.
    This file must stay private and should not be committed.
    """

  .env.example
    """
    Environment template.

    Lists all required variables so the user knows what they need to configure
    before running the project.
    """

  requirements.txt
    """
    Python dependency list.

    Keeps all required packages in one place for quick installation.
    """

  server.py
    """
    Main application entry point.

    Starts the local server, loads configuration, initializes services,
    connects the Telegram bot, and prepares the app runtime.
    """
```

```text
app/
  __init__.py
    """
    Application package marker.

    Allows the app directory to be imported as a Python package.
    """

  config.py
    """
    Runtime configuration loader.

    Reads values from .env and exposes them through one central config object.
    This includes API keys, service URLs, database paths, and default settings.
    """

  bootstrap.py
    """
    Application bootstrap logic.

    Wires together repositories, services, integrations, and interfaces.
    Keeps startup setup out of server.py.
    """
```

```text
app/core/
  router.py
    """
    Central message router.

    Receives normalized user input and decides which module should handle it:
    assets, transactions, debt, or market information.
    """

  intents.py
    """
    Intent definitions and detection helpers.

    Converts user messages into high-level actions such as BUY_ASSET,
    SELL_ASSET, CREATE_TRANSACTION, CHECK_PRICE, or ADD_DEBT.
    """

  commands.py
    """
    Command mapping layer.

    Connects detected intents to the correct service function.
    Keeps command handling separate from business logic.
    """

  responses.py
    """
    Response builder.

    Standardizes messages returned to Telegram, CLI, or web interfaces.
    Keeps user-facing output consistent.
    """

  exceptions.py
    """
    Application-specific exceptions.

    Defines clean error types for missing input, invalid commands,
    failed API calls, and validation problems.
    """
```

```text
app/interfaces/telegram/
  bot.py
    """
    Telegram bot setup.

    Creates the Telegram application, registers handlers, and starts polling
    for incoming user messages.
    """

  handlers.py
    """
    Telegram update handlers.

    Receives raw Telegram messages, extracts user text, sends it to the core
    router, and returns the response back to the chat.
    """

  formatters.py
    """
    Telegram response formatting.

    Converts internal response objects into clean Telegram messages.
    Handles plain text, markdown, lists, and error messages.
    """
```

```text
app/interfaces/web/
  routes.py
    """
    Web route definitions.

    Defines local dashboard endpoints for settings, API status, portfolio view,
    transaction history, and debt overview.
    """

  dashboard.py
    """
    Dashboard view logic.

    Prepares data for the local web dashboard and calls services needed by
    the settings and overview pages.
    """

  templates/
    """
    HTML templates.

    Stores dashboard pages rendered by the local web interface.
    """

  static/
    """
    Static web assets.

    Stores CSS, JavaScript, images, and other frontend files used by the
    local dashboard.
    """
```

```text
app/interfaces/cli/
  listener.py
    """
    CLI testing interface.

    Allows user messages to be typed directly in the terminal.
    Useful for testing parser, router, and services without Telegram.
    """
```

```text
app/modules/assets/
  models.py
    """
    Asset domain models.

    Defines structures for assets, holdings, buy orders, sell orders,
    and portfolio entries.
    """

  parser.py
    """
    Asset message parser.

    Extracts asset-related information from user messages, such as ticker,
    name, quantity, amount spent, and action type.
    """

  service.py
    """
    Asset business logic.

    Handles buying, selling, holding, updating, and validating asset records.
    This is the main service layer for portfolio actions.
    """

  portfolio.py
    """
    Portfolio calculation logic.

    Calculates total holdings, average buy price, profit/loss, allocation,
    and current portfolio value.
    """

  pricing.py
    """
    Asset price lookup layer.

    Requests current market prices through the market module or external
    integrations. Does not store assets directly.
    """

  storage.py
    """
    Asset persistence helpers.

    Saves and retrieves asset records using the storage/repository layer.
    """
```

```text
app/modules/transactions/
  models.py
    """
    Transaction domain models.

    Defines structures for income, expense, transfers, categories,
    and transaction records.
    """

  parser.py
    """
    Transaction message parser.

    Extracts amount, category, note, account, and transaction type from
    user messages.
    """

  service.py
    """
    Transaction business logic.

    Creates, validates, updates, and syncs transactions with Firefly III.
    """

  history.py
    """
    Transaction history queries.

    Retrieves and filters past transactions by date, category, account,
    amount, or keyword.
    """

  reports.py
    """
    Transaction reporting logic.

    Builds daily, weekly, monthly, and category-based summaries from
    transaction data.
    """
```

```text
app/modules/debt/
  models.py
    """
    Debt domain models.

    Defines structures for borrowed money, lent money, repayments,
    due dates, and interest terms.
    """

  parser.py
    """
    Debt message parser.

    Extracts debt-related information from user messages, such as person,
    amount, due date, direction, and interest.
    """

  service.py
    """
    Debt business logic.

    Handles creating debt records, updating repayments, marking debts as paid,
    and checking outstanding balances.
    """

  reminders.py
    """
    Debt reminder logic.

    Prepares reminder data for future due dates.
    Actual scheduling belongs to the scheduler module.
    """

  interest.py
    """
    Interest calculation helpers.

    Calculates simple interest, repayment amount, remaining balance,
    and overdue cost.
    """
```

```text
app/modules/market/
  crypto.py
    """
    Crypto market service.

    Provides crypto price lookup and symbol search using configured crypto
    providers such as CoinGecko or CoinMarketCap.
    """

  stocks.py
    """
    Stock, ETF, and commodity market service.

    Provides quote lookup and symbol search using providers such as Finnhub
    or Alpha Vantage.
    """

  forex.py
    """
    Forex market service.

    Provides exchange rate lookup and currency conversion using configured
    forex providers.
    """

  cs2.py
    """
    CS2 market service.

    Provides CS2 item price lookup and item search using configured CS2
    market providers.
    """

  service.py
    """
    Unified market service.

    Routes price lookup requests to the correct market type:
    crypto, stocks, forex, or CS2.
    """
```

```text
app/integrations/firefly/
  client.py
    """
    Firefly III API client.

    Handles HTTP requests to Firefly III, including accounts, transactions,
    categories, budgets, and summaries.
    """

  mapper.py
    """
    Firefly III data mapper.

    Converts internal transaction and finance models into Firefly-compatible
    request payloads.
    """
```

```text
app/integrations/telegram/
  client.py
    """
    Telegram API client.

    Low-level wrapper for Telegram API calls when direct access is needed.
    Most bot logic should still stay inside interfaces/telegram.
    """
```

```text
app/integrations/crypto/
  coingecko.py
    """
    CoinGecko API client.

    Handles crypto price lookup, coin search, and market data requests
    through CoinGecko.
    """

  coinmarketcap.py
    """
    CoinMarketCap API client.

    Handles crypto quotes, symbol lookup, and market information through
    CoinMarketCap.
    """
```

```text
app/integrations/stocks/
  finnhub.py
    """
    Finnhub API client.

    Handles stock, ETF, and market quote requests through Finnhub.
    """

  alphavantage.py
    """
    Alpha Vantage API client.

    Handles stock, ETF, commodity, and possible forex-related requests
    through Alpha Vantage.
    """
```

```text
app/integrations/forex/
  exchangerate_api.py
    """
    ExchangeRate API client.

    Handles exchange rate lookup and currency conversion using ExchangeRate API.
    """

  currencyfreaks.py
    """
    CurrencyFreaks API client.

    Handles exchange rate lookup and currency conversion using CurrencyFreaks.
    """
```

```text
app/integrations/cs2/
  price_provider.py
    """
    CS2 price provider abstraction.

    Defines a common interface for CS2 market price sources so the app can
    switch providers without changing business logic.
    """

  steam_market.py
    """
    Steam Market API wrapper.

    Fetches CS2 item prices from Steam Community Market when available.
    """
```

```text
app/storage/
  database.py
    """
    Database setup.

    Creates the database connection and exposes helpers for sessions,
    initialization, and schema setup.
    """

  migrations/
    """
    Database migrations.

    Stores schema changes over time.
    """

  repositories/
    asset_repo.py
      """
      Asset repository.

      Handles database operations for asset records and portfolio holdings.
      """

    transaction_repo.py
      """
      Transaction repository.

      Handles database operations for income, expense, and transaction history.
      """

    debt_repo.py
      """
      Debt repository.

      Handles database operations for debt records, repayments, and balances.
      """

    settings_repo.py
      """
      Settings repository.

      Stores and retrieves user configuration, API keys, provider choices,
      and local preferences.
      """
```

```text
app/settings/
  models.py
    """
    Settings models.

    Defines structures for user preferences, API configuration,
    provider selection, and default currency.
    """

  service.py
    """
    Settings service.

    Reads, validates, updates, and applies user settings across the app.
    """

  defaults.py
    """
    Default settings.

    Stores fallback values used when the user has not configured something yet.
    """
```

```text
app/scheduler/
  jobs.py
    """
    Future feature: scheduled job registration.

    Will define periodic tasks such as daily reports, price checks,
    and reminder scans.
    """

  alerts.py
    """
    Future feature: alert checks.

    Will handle budget alerts, asset price alerts, debt due alerts,
    and market movement alerts.
    """

  reports.py
    """
    Future feature: scheduled reports.

    Will generate automatic daily, weekly, or monthly summaries.
    """

  README.md
    """
    Scheduler feature notes.

    Documents planned scheduling features and how they will work later.
    """
```

```text
app/utils/
  money.py
    """
    Money utilities.

    Handles amount parsing, currency formatting, rounding, and conversion
    helpers used across modules.
    """

  text.py
    """
    Text utilities.

    Handles text normalization, keyword matching, token cleanup,
    and simple parsing helpers.
    """

  dates.py
    """
    Date utilities.

    Handles date parsing, relative dates, month ranges, and formatting.
    """

  logging.py
    """
    Logging setup.

    Provides consistent logging configuration for the app while avoiding
    leaking sensitive values such as tokens or API keys.
    """
```

# HOW TO SETUP
