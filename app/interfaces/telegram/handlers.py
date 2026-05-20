"""
Telegram state machine handlers.
Implements the simplified, user-friendly 5-flow menu system for FinanOS.
Includes AI-powered natural text inputs, fuzzy search item suggestions, and automated cost confirmation.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from app.integrations.firefly.client import firefly_client
from app.utils.parsers import extract_amount, extract_amount_and_currency, extract_tags, parse_natural_purchase, suggest_alternative_symbols
from app.interfaces.telegram.formatters import format_accounts_report, format_portfolio_report, format_debt_report, format_net_worth
from app.storage.database import SessionLocal
from app.modules.assets.models import Holding
from app.storage.models import ActivityLog
from app.utils.logging import logger

def record_activity(activity_type: str, description: str, amount: float = None):
    """Saves a record of the transaction/action to the activity log."""
    db = SessionLocal()
    try:
        log_entry = ActivityLog(
            activity_type=activity_type,
            description=description,
            amount=amount
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to record activity log: {e}")
    else:
        db.refresh(log_entry)
        from app.storage.activity_buffer import push_to_activity_queue
        push_to_activity_queue(log_entry)
    finally:
        db.close()


# States
MAIN_MENU = 0
(BUY_ASSET_TYPE, BUY_ASSET_NAME, BUY_SELECT_MODE, BUY_ASSET_QTY, BUY_ASSET_COST, BUY_ASSET_COST_MANUAL, BUY_ASSET_ACCOUNT, BUY_ASSET_SPENT_AMOUNT, BUY_ASSET_CALCULATED_CONFIRM) = range(10, 19)
(SELL_ASSET_SELECT, SELL_ASSET_QTY, SELL_ASSET_REV, SELL_ASSET_REV_MANUAL, SELL_ASSET_ACCOUNT) = range(20, 25)
(DEPOSIT_AMOUNT, DEPOSIT_SOURCE, DEPOSIT_ACCOUNT) = range(40, 43)
(DEBT_LENDER, DEBT_AMOUNT, DEBT_ACCOUNT, DEBT_DUE) = range(50, 54)
(BORROWER_NAME, BORROWER_AMOUNT, BORROWER_ACCOUNT, BORROWER_DUE) = range(60, 64)
(TRANSFER_AMOUNT, TRANSFER_SOURCE, TRANSFER_DEST) = range(70, 73)

# --- ENTRY ---
async def send_receipt_and_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: str):
    """Sends the receipt/log message as a standalone message, then immediately triggers the main menu."""
    chat_id = update.effective_chat.id
    if update.callback_query:
        await update.callback_query.edit_message_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    keyboard = [
        [InlineKeyboardButton("Buy 📈", callback_data="flow_buy")],
        [InlineKeyboardButton("Sell Asset 📉", callback_data="flow_sell")],
        [InlineKeyboardButton("Deposit 💵", callback_data="flow_deposit")],
        [InlineKeyboardButton("Transfer 🔄", callback_data="flow_transfer")],
        [InlineKeyboardButton("Add Debt 🤝", callback_data="flow_debt_sub")],
        [InlineKeyboardButton("View Vault 🏦", callback_data="trigger_view")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    main_menu_msg = '🏠 *Welcome to FinanOS Personal Wealth Manager!*\n\nSelect an action from the options below:'
    await context.bot.send_message(chat_id=chat_id, text=main_menu_msg, reply_markup=reply_markup, parse_mode="Markdown")
    return MAIN_MENU

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point of the bot."""
    keyboard = [
        [InlineKeyboardButton("Buy 📈", callback_data="flow_buy")],
        [InlineKeyboardButton("Sell Asset 📉", callback_data="flow_sell")],
        [InlineKeyboardButton("Deposit 💵", callback_data="flow_deposit")],
        [InlineKeyboardButton("Transfer 🔄", callback_data="flow_transfer")],
        [InlineKeyboardButton("Add Debt 🤝", callback_data="flow_debt_sub")],
        [InlineKeyboardButton("View Vault 🏦", callback_data="trigger_view")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = '🏠 *Welcome to FinanOS Personal Wealth Manager!*\n\nSelect an action from the options below:'
    if update.message:
        await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(msg, reply_markup=reply_markup, parse_mode="Markdown")
    return MAIN_MENU

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Initialize fresh state data
    context.user_data['flow_data'] = {}
    
    flow = query.data
    if flow == "flow_buy":
        keyboard = [
            [InlineKeyboardButton("Crypto", callback_data="type_crypto"), 
             InlineKeyboardButton("Stock", callback_data="type_stock"),
             InlineKeyboardButton("CS2 Item", callback_data="type_cs2")],
            [InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")]
        ]
        await query.edit_message_text(
            "What type of asset are you buying?\n\n"
            "💡 _Or simply type what you bought directly in the chat below (e.g. bought a pizza for 120k) to record a normal withdrawal purchase with AI auto-categorization!_",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return BUY_ASSET_TYPE
        
    elif flow == "flow_sell":
        # 1. Query database for active holdings with quantities > 0
        db = SessionLocal()
        holdings = db.query(Holding).filter(Holding.quantity > 0).all()
        db.close()
        
        if not holdings:
            await query.edit_message_text(
                "❌ You don't have any registered assets in your portfolio to sell.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")]])
            )
            return MAIN_MENU
            
        # 2. Build keyboard dynamically
        keyboard = []
        for h in holdings:
            keyboard.append([InlineKeyboardButton(f"{h.symbol} ({h.quantity:,.4f} units)", callback_data=f"sell_{h.id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
            
        await query.edit_message_text("Select an active asset to sell from your portfolio:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELL_ASSET_SELECT
        
    elif flow == "flow_deposit":
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await query.edit_message_text("How much is the deposit?", reply_markup=InlineKeyboardMarkup(keyboard))
        return DEPOSIT_AMOUNT
        
    elif flow == "flow_transfer":
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await query.edit_message_text("How much do you want to transfer?", reply_markup=InlineKeyboardMarkup(keyboard))
        return TRANSFER_AMOUNT
        
    elif flow == "flow_debt_sub":
        # User-friendly Sub-menu for Debt (Borrowing vs Lending)
        keyboard = [
            [InlineKeyboardButton("Add Debt (You Owe) 🔻", callback_data="sub_owe")],
            [InlineKeyboardButton("Add Borrower (Owes You) 🔺", callback_data="sub_owed")],
            [InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")]
        ]
        await query.edit_message_text(
            "🤝 *Debt & Loans Configuration*\n\n"
            "Are you borrowing money (You Owe) or lending money to someone (Owes You)?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return MAIN_MENU
        
    # Handlers for submenu clicks inside MAIN_MENU CallbackQuery routing
    elif flow == "sub_owe":
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await query.edit_message_text("Who did you borrow money from? (Lender Name)", reply_markup=InlineKeyboardMarkup(keyboard))
        return DEBT_LENDER
        
    elif flow == "sub_owed":
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await query.edit_message_text("Who are you lending money to? (Borrower Name)", reply_markup=InlineKeyboardMarkup(keyboard))
        return BORROWER_NAME

async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback query to instantly return to main menu at any step."""
    query = update.callback_query
    await query.answer()
    await start(update, context)
    return MAIN_MENU


# --- FLOW 1: BUY ASSET / AI NATURAL PURCHASE ---
async def buy_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['flow_data']['type'] = query.data.split("_")[1]
    
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
    await query.edit_message_text(
        "Enter the symbol or name (e.g., BTC, AAPL, AK-47 Redline):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BUY_ASSET_NAME

async def buy_natural_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Intercepts natural text typed in response to Buy prompt and parses it with Gemini AI."""
    text = update.message.text.strip()
    status_msg = await update.message.reply_text("🧠 Analyzing purchase with Google Gemini AI...")
    
    parsed = parse_natural_purchase(text)
    context.user_data['flow_data'] = {
        "mode": "natural_purchase",
        "amount": parsed["amount"],
        "description": parsed["description"],
        "tags": parsed["tags"]
    }
    
    msg = (
        f"🎯 **AI Purchase Parsed!**\n"
        f"• **Description**: `{parsed['description']}`\n"
        f"• **Amount**: `{parsed['amount']:,.2f} VND`\n"
        f"• **Category/Tags**: `{', '.join(parsed['tags'])}`\n\n"
        f"Which account funded this purchase?"
    )
    
    accounts = firefly_client.get_accounts("asset")
    keyboard = []
    for acc in accounts:
        keyboard.append([InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"natbuy_{acc['id']}")])
        
    keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
    
    await status_msg.delete()
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return BUY_ASSET_ACCOUNT

async def buy_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = update.message.text.strip().upper()
    asset_type = context.user_data['flow_data']['type']
    
    status_msg = await update.message.reply_text(f"🔍 Searching online market for '{symbol}' ({asset_type})...")
    
    from app.modules.market.service import market_service
    live_price_usd = market_service.get_price(symbol, asset_type)
    
    await status_msg.delete()
    
    if live_price_usd > 0.0:
        context.user_data['flow_data']['name'] = symbol
        context.user_data['flow_data']['live_price_usd'] = live_price_usd
        context.user_data['flow_data']['mode'] = "invest"
        
        keyboard = [
            [InlineKeyboardButton("✏️ I Spent a Specific Amount Instead", callback_data="buy_spent_instead")],
            [InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")]
        ]
        msg = (
            f"✅ *Asset Found!*\n"
            f"• *Symbol/Name*: `{symbol}`\n"
            f"• *Current Live Price*: `${live_price_usd:,.2f} USD`\n\n"
            f"How many units (or fractions) did you acquire?\n"
            f"_(CS2 items accept whole numbers only; Stock & Crypto can accept fractions)_"
        )
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return BUY_ASSET_QTY
    else:
        # Exact item not found online. Prompt Gemini to suggest similar standard match symbols!
        suggest_msg = await update.message.reply_text("⚠️ Symbol not found online. Checking for alternatives using Gemini...")
        suggestions = suggest_alternative_symbols(symbol, asset_type)
        await suggest_msg.delete()
        
        context.user_data['flow_data']['original_symbol_failed'] = symbol
        
        keyboard = []
        if suggestions:
            for s in suggestions:
                keyboard.append([InlineKeyboardButton(s, callback_data=f"buysugg_{s}")])
        keyboard.append([InlineKeyboardButton(f"Use manual input: '{symbol}'", callback_data="buysugg_manual")])
        keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
        
        await update.message.reply_text(
            f"⚠️ *Symbol/Name '{symbol}' was not found online.*\n"
            f"Did you mean one of these standard trackable listings?",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return BUY_SELECT_MODE

async def buy_suggestion_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback triggered when the user chooses an alternative symbol suggested by Gemini."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    asset_type = context.user_data['flow_data']['type']
    
    if data == "buysugg_manual":
        # Keep original typed name and set price to $0.00
        symbol = context.user_data['flow_data']['original_symbol_failed']
        context.user_data['flow_data']['name'] = symbol
        context.user_data['flow_data']['live_price_usd'] = 0.0
    else:
        # Use alternative suggestion
        symbol = data[len("buysugg_"):]
        context.user_data['flow_data']['name'] = symbol
        
        status_msg = await query.message.reply_text(f"🔍 Selected alternative. Fetching price for '{symbol}'...")
        from app.modules.market.service import market_service
        live_price_usd = market_service.get_price(symbol, asset_type)
        await status_msg.delete()
        
        context.user_data['flow_data']['live_price_usd'] = live_price_usd

    # Automatically set investment mode and proceed straight to Quantity
    context.user_data['flow_data']['mode'] = "invest"
    symbol_actual = context.user_data['flow_data']['name']
    live_price = context.user_data['flow_data']['live_price_usd']
    
    keyboard = [
        [InlineKeyboardButton("✏️ I Spent a Specific Amount Instead", callback_data="buy_spent_instead")],
        [InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")]
    ]
    
    if live_price > 0.0:
        msg = (
            f"✅ *Asset Configured!*\n"
            f"• *Symbol/Name*: `{symbol_actual}`\n"
            f"• *Live Price*: `${live_price:,.2f} USD`\n\n"
            f"How many units (or fractions) did you acquire?\n"
            f"_(CS2 items accept whole numbers only; Stock & Crypto can accept fractions)_"
        )
    else:
        msg = (
            f"⚠️ *Asset Configured (Manual Entry)*\n"
            f"• *Symbol/Name*: `{symbol_actual}`\n"
            f"• *Price*: `$0.00 USD` (Manual overrides will be prompted)\n\n"
            f"How many units (or fractions) did you acquire?\n"
            f"_(CS2 items accept whole numbers only; Stock & Crypto can accept fractions)_"
        )
        
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return BUY_ASSET_QTY

async def buy_select_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    mode = query.data.split("_")[1] # invest or hold
    context.user_data['flow_data']['mode'] = mode
    
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
    await query.edit_message_text(
        "How many units (or fractions) did you acquire?\n"
        "_(CS2 items accept whole numbers only; Stock & Crypto can accept fractions)_",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BUY_ASSET_QTY

async def buy_spent_instead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback triggered when the user chooses to input spent money instead of quantity."""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Quantity Input", callback_data="back_to_qty")],
        [InlineKeyboardButton("❌ Cancel & Main Menu", callback_data="back_main")]
    ]
    
    await query.edit_message_text(
        "How much money (in VND) did you spend for this purchase?\n"
        "_(We will use this to automatically calculate your asset quantity based on live market price)_",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BUY_ASSET_SPENT_AMOUNT

async def back_to_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback to return to quantity input screen."""
    query = update.callback_query
    await query.answer()
    
    symbol_actual = context.user_data['flow_data']['name']
    live_price = context.user_data['flow_data']['live_price_usd']
    
    keyboard = [
        [InlineKeyboardButton("✏️ I Spent a Specific Amount Instead", callback_data="buy_spent_instead")],
        [InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")]
    ]
    
    msg = (
        f"✅ *Asset Configured!*\n"
        f"• *Symbol/Name*: `{symbol_actual}`\n"
        f"• *Live Price*: `${live_price:,.2f} USD`\n\n"
        f"How many units (or fractions) did you acquire?\n"
        f"_(CS2 items accept whole numbers only; Stock & Crypto can accept fractions)_"
    )
    await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return BUY_ASSET_QTY

async def buy_spent_amount_entered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles parsing the user-inputted spent VND amount and calculates the equivalent quantity."""
    text = update.message.text.strip()
    spent_amount = extract_amount(text)
    
    if spent_amount <= 0:
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Quantity Input", callback_data="back_to_qty")],
            [InlineKeyboardButton("❌ Cancel & Main Menu", callback_data="back_main")]
        ]
        await update.message.reply_text(
            "❌ Amount spent must be greater than 0. Please enter a valid amount in VND:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return BUY_ASSET_SPENT_AMOUNT
        
    symbol = context.user_data['flow_data']['name']
    live_price_usd = context.user_data['flow_data'].get('live_price_usd', 0.0)
    asset_type = context.user_data['flow_data']['type']
    
    if live_price_usd <= 0.0:
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await update.message.reply_text(
            "⚠️ Live market price is not available for this symbol. Please enter quantity instead:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return BUY_ASSET_QTY
        
    from app.modules.market.forex import get_exchange_rate
    from app.config import config
    target_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
    
    vnd_unit_price = live_price_usd * get_exchange_rate("USD", target_currency)
    
    if vnd_unit_price <= 0.0:
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await update.message.reply_text(
            "⚠️ Unable to fetch currency exchange rate. Please try again or input quantity:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return BUY_ASSET_QTY
        
    raw_qty = spent_amount / vnd_unit_price
    
    # In the case of CS2 items! Always round up!
    if asset_type == "cs2":
        import math
        qty = math.ceil(raw_qty)
        cost = qty * vnd_unit_price
    else:
        qty = round(raw_qty, 6)
        cost = spent_amount
        
    context.user_data['flow_data']['qty'] = qty
    context.user_data['flow_data']['cost'] = cost
    context.user_data['flow_data']['spent_vnd_input'] = spent_amount
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Correct", callback_data="calc_confirm_yes")],
        [InlineKeyboardButton("✏️ No, Change Qty / Spend", callback_data="calc_confirm_no")],
        [InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")]
    ]
    
    msg = (
        f"📊 *Asset Quantity Calculation Result*\n"
        f"• *Asset*: `{symbol}`\n"
        f"• *Calculated Quantity*: `{qty}` units" + (" (rounded up)" if asset_type == "cs2" else "") + "\n"
        f"• *Target Cost*: `{cost:,.2f} VND`\n"
        f"• *Your Input Spent*: `{spent_amount:,.2f} VND`\n\n"
        f"Is this the correct number you bought?"
    )
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return BUY_ASSET_CALCULATED_CONFIRM

async def buy_calculated_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback triggered on confirming the calculated quantity results."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == "calc_confirm_yes":
        # Proceed straight to funding account step!
        accounts = firefly_client.get_accounts("asset")
        keyboard = []
        for acc in accounts:
            keyboard.append([InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"acc_{acc['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
        await query.edit_message_text("Which bank/cash account funded this purchase?", reply_markup=InlineKeyboardMarkup(keyboard))
        return BUY_ASSET_ACCOUNT
        
    elif choice == "calc_confirm_no":
        # Go back to the quantity input step
        symbol_actual = context.user_data['flow_data']['name']
        live_price = context.user_data['flow_data']['live_price_usd']
        
        keyboard = [
            [InlineKeyboardButton("✏️ I Spent a Specific Amount Instead", callback_data="buy_spent_instead")],
            [InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")]
        ]
        
        msg = (
            f"✅ *Asset Configured!*\n"
            f"• *Symbol/Name*: `{symbol_actual}`\n"
            f"• *Live Price*: `${live_price:,.2f} USD`\n\n"
            f"How many units (or fractions) did you acquire?\n"
            f"_(CS2 items accept whole numbers only; Stock & Crypto can accept fractions)_"
        )
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return BUY_ASSET_QTY

async def buy_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asset_type = context.user_data['flow_data']['type']
    text = update.message.text.strip()
    qty = extract_amount(text)
    
    if qty <= 0:
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await update.message.reply_text("❌ Quantity must be greater than 0. Please enter a valid quantity:", reply_markup=InlineKeyboardMarkup(keyboard))
        return BUY_ASSET_QTY
        
    if asset_type == "cs2":
        if qty != int(qty):
            keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
            await update.message.reply_text("❌ CS2 items can only be bought in whole integer units (no fractions). Please enter a valid whole number (e.g., 1, 2, 5):", reply_markup=InlineKeyboardMarkup(keyboard))
            return BUY_ASSET_QTY
        qty = int(qty)
        
    context.user_data['flow_data']['qty'] = qty
    
    # ⚡ AUTOMATED COST CALCULATION
    symbol = context.user_data['flow_data']['name']
    live_price_usd = context.user_data['flow_data'].get('live_price_usd', 0.0)
    
    if live_price_usd > 0.0:
        from app.modules.market.forex import get_exchange_rate
        from app.config import config
        target_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
        
        vnd_unit_price = live_price_usd * get_exchange_rate("USD", target_currency)
        calculated_cost = qty * vnd_unit_price
        
        context.user_data['flow_data']['calculated_cost'] = calculated_cost
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Correct", callback_data="cost_confirm_yes")],
            [InlineKeyboardButton("✏️ No, Enter Manually", callback_data="cost_confirm_no")],
            [InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")]
        ]
        
        msg = (
            f"📊 *Estimated Valuation Calculation*\n"
            f"• *Asset*: `{symbol}`\n"
            f"• *Quantity*: `{qty}` units\n"
            f"• *Live Unit Price*: `${live_price_usd:,.2f} USD` (~ `{vnd_unit_price:,.2f} VND`)\n\n"
            f"👉 **Calculated Valuation**: *{calculated_cost:,.2f} VND*\n\n"
            f"Is this valuation/cost correct?"
        )
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return BUY_ASSET_COST
    else:
        # No live price available, fallback directly to manual cost entry
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await update.message.reply_text("How much did you spend in VND for this transaction?", reply_markup=InlineKeyboardMarkup(keyboard))
        return BUY_ASSET_COST_MANUAL

async def buy_cost_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback handling confirmation of calculated cost."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    data = context.user_data['flow_data']
    
    if choice == "cost_confirm_yes":
        cost = data['calculated_cost']
        context.user_data['flow_data']['cost'] = cost
        
        mode = data['mode']
        if mode == "invest":
            accounts = firefly_client.get_accounts("asset")
            keyboard = []
            for acc in accounts:
                keyboard.append([InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"acc_{acc['id']}")])
            keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
            await query.edit_message_text("Which bank/cash account funded this purchase?", reply_markup=InlineKeyboardMarkup(keyboard))
            return BUY_ASSET_ACCOUNT
        else:
            # Pure Holding direct save
            from app.modules.assets.service import asset_service
            db = SessionLocal()
            try:
                asset_service.execute_action(db, {
                    "action": "hold",
                    "symbol": data['name'],
                    "asset_type": data['type'],
                    "quantity": data['qty'],
                    "price": cost, # average price
                    "currency": "VND"
                }, str(query.from_user.id))
                record_activity("hold", f"Recorded holding of {data['qty']} {data['name']}", cost * data['qty'])
            except Exception as e:
                logger.error(f"Failed to save pure holding: {e}")
            finally:
                db.close()
                
            msg = f"✅ Successfully recorded holding of {data['qty']} {data['name']} in your vault!"
            return await send_receipt_and_main_menu(update, context, msg)
            
    elif choice == "cost_confirm_no":
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await query.edit_message_text("How much did you spend in VND for this transaction?", reply_markup=InlineKeyboardMarkup(keyboard))
        return BUY_ASSET_COST_MANUAL

async def buy_cost_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cost = extract_amount(update.message.text)
    context.user_data['flow_data']['cost'] = cost
    
    data = context.user_data['flow_data']
    mode = data['mode']
    
    if mode == "invest":
        accounts = firefly_client.get_accounts("asset")
        keyboard = []
        for acc in accounts:
            keyboard.append([InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"acc_{acc['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
        await update.message.reply_text("Which bank/cash account funded this purchase?", reply_markup=InlineKeyboardMarkup(keyboard))
        return BUY_ASSET_ACCOUNT
    else:
        # Pure Holding direct save with manual cost
        from app.modules.assets.service import asset_service
        db = SessionLocal()
        try:
            asset_service.execute_action(db, {
                "action": "hold",
                "symbol": data['name'],
                "asset_type": data['type'],
                "quantity": data['qty'],
                "price": cost, # manual average price
                "currency": "VND"
            }, str(update.message.from_user.id))
            record_activity("hold", f"Recorded holding of {data['qty']} {data['name']}", cost * data['qty'])
        except Exception as e:
            logger.error(f"Failed to save manual holding: {e}")
        finally:
            db.close()
            
        msg = f"✅ Successfully recorded holding of {data['qty']} {data['name']} in your vault!"
        return await send_receipt_and_main_menu(update, context, msg)

async def buy_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    source_id = callback_data.split("_")[1]
    data = context.user_data['flow_data']
    
    if data.get("mode") == "natural_purchase":
        dest_category = data["tags"][0].capitalize() if data["tags"] else "Shopping"
        dest_id = firefly_client.get_or_create_account(dest_category, "expense")
        
        tx_payload = {
            "transactions": [{
                "type": "withdrawal",
                "date": "2026-05-06",
                "amount": str(data["amount"]),
                "description": data["description"],
                "source_id": source_id,
                "destination_id": dest_id,
                "tags": data["tags"]
            }]
        }
        firefly_client.create_transaction(tx_payload)
        record_activity("natural_purchase", f"Bought {data['description']} via AI", data["amount"])
        
        msg = f"✅ AI Purchase recorded: {data['description']} for {data['amount']:,.2f} VND."
        return await send_receipt_and_main_menu(update, context, msg)
        
    else:
        # Investment purchase save
        from app.modules.assets.service import asset_service
        db = SessionLocal()
        try:
            asset_service.execute_action(db, {
                "action": "buy",
                "symbol": data['name'],
                "asset_type": data['type'],
                "quantity": data['qty'],
                "price": data['cost'], # total cost
                "currency": "VND"
            }, str(query.from_user.id))
        except Exception as e:
            logger.error(f"Failed to save purchase to database: {e}")
        finally:
            db.close()
        
        inv_id = firefly_client.get_or_create_account("Investments", "expense")
        
        tx_payload = {
            "transactions": [{
                "type": "withdrawal",
                "date": "2026-05-06",
                "amount": str(data["cost"]),
                "description": f"Bought {data['qty']} {data['name']}",
                "source_id": source_id,
                "destination_id": inv_id,
                "tags": ["Investment", data['name']]
            }]
        }
        firefly_client.create_transaction(tx_payload)
        record_activity("buy", f"Bought {data['qty']} {data['name']}", data["cost"])
        
        msg = f"✅ Successfully recorded investment purchase of {data['name']}!"
        return await send_receipt_and_main_menu(update, context, msg)


# --- FLOW 2: REAL DB-DRIVEN SELL ASSET ---
async def sell_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    holding_id = int(query.data.split("_")[1])
    
    db = SessionLocal()
    holding = db.query(Holding).filter(Holding.id == holding_id).first()
    db.close()
    
    if not holding:
        msg = "❌ Error: Selected holding was not found."
        return await send_receipt_and_main_menu(update, context, msg)
        
    context.user_data['flow_data']['holding_id'] = holding_id
    context.user_data['flow_data']['symbol'] = holding.symbol
    context.user_data['flow_data']['type'] = holding.asset_type
    context.user_data['flow_data']['max_qty'] = holding.quantity
    
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
    await query.edit_message_text(
        f"📉 Selling *{holding.symbol.upper()}* ({holding.asset_type.upper()})\n"
        f"You currently own `{holding.quantity:,.4f}` units.\n\n"
        f"How many units are you selling?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELL_ASSET_QTY

async def sell_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    asset_type = context.user_data['flow_data']['type']
    max_qty = context.user_data['flow_data']['max_qty']
    text = update.message.text.strip()
    qty = extract_amount(text)
    
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
    if qty <= 0:
        await update.message.reply_text("❌ Quantity must be greater than 0. Please enter a valid quantity:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELL_ASSET_QTY
        
    if qty > max_qty:
        await update.message.reply_text(f"❌ Insufficient balance. You only own `{max_qty:,.4f}` units of {context.user_data['flow_data']['symbol']}. Please enter a valid quantity to sell:", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELL_ASSET_QTY
        
    if asset_type == "cs2":
        if qty != int(qty):
            await update.message.reply_text("❌ CS2 items must be in whole units. Please enter a valid whole number:", reply_markup=InlineKeyboardMarkup(keyboard))
            return SELL_ASSET_QTY
        qty = int(qty)
        
    context.user_data['flow_data']['qty'] = qty
    
    # ⚡ AUTOMATED REVENUE CALCULATION
    symbol = context.user_data['flow_data']['symbol']
    
    from app.modules.market.service import market_service
    live_price_usd = market_service.get_price(symbol, asset_type)
    
    if live_price_usd > 0.0:
        from app.modules.market.forex import get_exchange_rate
        from app.config import config
        target_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
        
        vnd_unit_price = live_price_usd * get_exchange_rate("USD", target_currency)
        calculated_revenue = qty * vnd_unit_price
        
        context.user_data['flow_data']['calculated_revenue'] = calculated_revenue
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Correct", callback_data="sell_revenue_confirm_yes")],
            [InlineKeyboardButton("✏️ No, Enter Manually", callback_data="sell_revenue_confirm_no")],
            [InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")]
        ]
        
        msg = (
            f"📊 *Estimated Sale Revenue Calculation*\n"
            f"• *Asset*: `{symbol.upper()}` ({asset_type.upper()})\n"
            f"• *Quantity*: `{qty}` units\n"
            f"• *Live Unit Price*: `${live_price_usd:,.2f} USD` (~ `{vnd_unit_price:,.2f} VND`)\n\n"
            f"👉 **Calculated Revenue**: *{calculated_revenue:,.2f} VND*\n\n"
            f"Is this revenue correct?"
        )
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return SELL_ASSET_REV
    else:
        # No live price available, fallback directly to manual revenue entry
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await update.message.reply_text("What is the total revenue received in VND?", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELL_ASSET_REV_MANUAL

async def sell_revenue_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    data = context.user_data['flow_data']
    
    if choice == "sell_revenue_confirm_yes":
        revenue = data['calculated_revenue']
        context.user_data['flow_data']['revenue'] = revenue
        
        accounts = firefly_client.get_accounts("asset")
        keyboard = []
        for acc in accounts:
            keyboard.append([InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"acc_{acc['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
        await query.edit_message_text("Which bank/cash account should receive these funds?", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELL_ASSET_ACCOUNT
        
    elif choice == "sell_revenue_confirm_no":
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await query.edit_message_text("What is the total revenue received in VND?", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELL_ASSET_REV_MANUAL

async def sell_rev_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['flow_data']['revenue'] = extract_amount(update.message.text)
    accounts = firefly_client.get_accounts("asset")
    keyboard = []
    for acc in accounts:
        keyboard.append([InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"acc_{acc['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
    await update.message.reply_text("Which bank/cash account should receive these funds?", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELL_ASSET_ACCOUNT

async def sell_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dest_id = query.data.split("_")[1]
    data = context.user_data['flow_data']
    
    # 1. DB Save as SELL
    from app.modules.assets.service import asset_service
    db = SessionLocal()
    try:
        asset_service.execute_action(db, {
            "action": "sell",
            "symbol": data['symbol'],
            "asset_type": data['type'],
            "quantity": data['qty'],
            "price": data['revenue'], # total revenue
            "currency": "VND"
        }, str(query.from_user.id))
    except Exception as e:
        logger.error(f"Failed to save sale to DB: {e}")
    finally:
        db.close()
        
    inv_id = firefly_client.get_or_create_account("Investments", "revenue")
    
    tx_payload = {
        "transactions": [{
            "type": "deposit",
            "date": "2026-05-06",
            "amount": str(data["revenue"]),
            "description": f"Sold {data['qty']} {data['symbol']}",
            "source_id": inv_id,
            "destination_id": dest_id,
            "tags": ["Investment", "Sale", data['symbol']]
        }]
    }
    firefly_client.create_transaction(tx_payload)
    record_activity("sell", f"Sold {data['qty']} {data['symbol']}", data["revenue"])
    
    msg = f"✅ Successfully recorded sale of {data['qty']} {data['symbol']}!"
    return await send_receipt_and_main_menu(update, context, msg)


# --- FLOW 3: DEPOSIT ---
async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount, currency = extract_amount_and_currency(update.message.text)
    context.user_data['flow_data']['amount'] = amount
    context.user_data['flow_data']['input_currency'] = currency
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
    await update.message.reply_text("What is this for? (e.g., Salary, Freelance, Gift)", reply_markup=InlineKeyboardMarkup(keyboard))
    return DEPOSIT_SOURCE

async def deposit_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    context.user_data['flow_data']['description'] = desc
    context.user_data['flow_data']['tags'] = extract_tags(desc)
    
    accounts = firefly_client.get_accounts("asset")
    keyboard = []
    for acc in accounts:
        name = acc["attributes"]["name"]
        acc_id = acc["id"]
        keyboard.append([InlineKeyboardButton(name, callback_data=f"acc_{acc_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
    
    await update.message.reply_text("Where is it going?", reply_markup=InlineKeyboardMarkup(keyboard))
    return DEPOSIT_ACCOUNT

async def deposit_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    acc_id = query.data.split("_")[1]
    data = context.user_data['flow_data']
    
    # Check currency conversion requirement
    from app.modules.market.forex import get_exchange_rate
    from app.config import config
    
    accounts = firefly_client.get_accounts("asset")
    dest_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
    dest_name = "Account"
    for acc in accounts:
        if str(acc["id"]) == str(acc_id):
            dest_currency = acc["attributes"].get("currency_code", dest_currency)
            dest_name = acc["attributes"]["name"]
            break
            
    input_amount = data["amount"]
    input_currency = data.get("input_currency")
    
    converted_amount = input_amount
    log_msg = f"Deposit of {input_amount} logged successfully!"
    description = data["description"]
    
    if input_currency and input_currency != dest_currency:
        rate = get_exchange_rate(input_currency, dest_currency)
        converted_amount = input_amount * rate
        log_msg = (
            f"✅ *Deposit Converted Successfully!*\n"
            f"• *Original*: `{input_amount:,.2f} {input_currency}`\n"
            f"• *Forex Rate*: `1 {input_currency} = {rate:,.4f} {dest_currency}`\n"
            f"👉 *Deposited*: `{converted_amount:,.2f} {dest_currency}` into *{dest_name}*"
        )
        description = f"Deposit: {data['description']} (Converted {input_amount:,.2f} {input_currency} to {converted_amount:,.2f} {dest_currency})"
        
    tx_payload = {
        "transactions": [{
            "type": "deposit",
            "date": "2026-05-06",
            "amount": f"{converted_amount:.2f}",
            "description": description,
            "destination_id": acc_id,
            "tags": data["tags"]
        }]
    }
    firefly_client.create_transaction(tx_payload)
    
    # Ensure activity log is saved in standard system currency (VND)
    from app.modules.market.forex import get_exchange_rate
    system_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
    activity_amount = converted_amount
    if dest_currency != system_currency:
        activity_amount = converted_amount * get_exchange_rate(dest_currency, system_currency)
        
    record_activity("deposit", f"Deposited: {data['description']}", activity_amount)
    
    return await send_receipt_and_main_menu(update, context, log_msg)


# --- FLOW 4: ADD DEBT (You owe) ---
async def create_debt_transaction_and_log(data, message):
    lender_id = firefly_client.get_or_create_account(data["lender"], "revenue")
    
    import datetime
    today_iso = datetime.date.today().strftime("%Y-%m-%d")
    
    tx_payload = {
        "transactions": [{
            "type": "deposit",
            "date": today_iso,
            "amount": str(data["amount"]),
            "description": f"Borrowed from {data['lender']}",
            "source_id": lender_id,
            "destination_id": data["account_id"],
            "tags": ["Borrowed"]
        }]
    }
    firefly_client.create_transaction(tx_payload)
    
    # Ensure activity log is saved in standard system currency (VND)
    from app.modules.market.forex import get_exchange_rate
    accounts = firefly_client.get_accounts("asset")
    acc_currency = "VND"
    for acc in accounts:
        if str(acc["id"]) == str(data["account_id"]):
            acc_currency = acc["attributes"].get("currency_code", "VND")
            break
            
    system_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
    activity_amount = data["amount"]
    if acc_currency != system_currency:
        activity_amount = data["amount"] * get_exchange_rate(acc_currency, system_currency)
        
    record_activity("debt", f"Borrowed from {data['lender']}", activity_amount)
    
    # Save/update due date in local SQLite database
    due_str = str(data.get('due', '')).strip().lower()
    if due_str and due_str != 'skip' and due_str != 'none':
        from app.storage.models import Debt
        try:
            parsed_date = datetime.datetime.strptime(due_str.split()[0], "%Y-%m-%d")
            db = SessionLocal()
            local_debt = db.query(Debt).filter(Debt.person_name == data["lender"]).first()
            if not local_debt:
                local_debt = Debt(
                    person_name=data["lender"],
                    direction="borrowed",
                    amount=data["amount"],
                    currency=acc_currency,
                    interest_rate=0.0,
                    due_date=parsed_date,
                    is_settled=False
                )
                db.add(local_debt)
            else:
                local_debt.due_date = parsed_date
                local_debt.amount = data["amount"]
                local_debt.currency = acc_currency
                local_debt.is_settled = False
            db.commit()
            db.close()
        except Exception as ex:
            logger.error(f"Failed to save due date to local DB: {ex}")
            
    msg_text = (
        f"✅ **Debt Recorded Successfully!**\n\n"
        f"• **Lender**: `{data['lender']}`\n"
        f"• **Amount**: `{data['amount']:,.2f} {acc_currency}`\n"
        f"• **Due Date**: `{data.get('due') or 'None'}`"
    )
    return msg_text

async def debt_lender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.utils.parsers import parse_natural_debt_or_loan
    text = update.message.text.strip()
    
    # Run the sentence parsing through Gemini AI
    status_msg = await update.message.reply_text("🧠 Analyzing debt information with Google Gemini AI...")
    parsed = parse_natural_debt_or_loan(text)
    await status_msg.delete()
    
    name = parsed.get("name")
    if not name:
        name = text
        
    context.user_data['flow_data']['lender'] = name
    context.user_data['flow_data']['amount'] = parsed.get("amount")
    context.user_data['flow_data']['due'] = parsed.get("due_date")
    
    # If amount was missing, we must ask the user
    if context.user_data['flow_data']['amount'] is None:
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await update.message.reply_text(
            f"Lender: *{name}*\n\nHow much did you borrow from them?", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return DEBT_AMOUNT
        
    # If amount is present, go straight to selecting the receiving account
    accounts = firefly_client.get_accounts("asset")
    keyboard = [[InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"acc_{acc['id']}")] for acc in accounts]
    keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
    await update.message.reply_text(
        f"Lender: *{name}*\n"
        f"Amount: *{context.user_data['flow_data']['amount']:,.2f} VND*\n\n"
        f"Which account received this money?", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return DEBT_ACCOUNT

async def debt_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['flow_data']['amount'] = extract_amount(update.message.text)
    accounts = firefly_client.get_accounts("asset")
    keyboard = [[InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"acc_{acc['id']}")] for acc in accounts]
    keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
    await update.message.reply_text("Which account received this money?", reply_markup=InlineKeyboardMarkup(keyboard))
    return DEBT_ACCOUNT

async def debt_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = context.user_data['flow_data']
    data['account_id'] = query.data.split("_")[1]
    
    # If we already have the due date from AI parsing, skip asking and create immediately!
    if data.get('due'):
        await query.edit_message_text("💾 Creating transaction & saving payment terms...")
        msg_text = await create_debt_transaction_and_log(data, query.message)
        return await send_receipt_and_main_menu(update, context, msg_text)
        
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
    await query.edit_message_text("When is this due? (Format: YYYY-MM-DD or 'Skip')", reply_markup=InlineKeyboardMarkup(keyboard))
    return DEBT_DUE

async def debt_due(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['flow_data']
    data['due'] = update.message.text
    
    msg_text = await create_debt_transaction_and_log(data, update.message)
    return await send_receipt_and_main_menu(update, context, msg_text)


# --- FLOW 5: ADD BORROWER (Owes you) ---
async def create_borrow_transaction_and_log(data, message):
    borrower_id = firefly_client.get_or_create_account(data["borrower"], "expense")
    
    import datetime
    today_iso = datetime.date.today().strftime("%Y-%m-%d")
    
    tx_payload = {
        "transactions": [{
            "type": "withdrawal",
            "date": today_iso,
            "amount": str(data["amount"]),
            "description": f"Lent to {data['borrower']}",
            "source_id": data["account_id"],
            "destination_id": borrower_id,
            "tags": ["Lent"]
        }]
    }
    firefly_client.create_transaction(tx_payload)
    
    # Ensure activity log is saved in standard system currency (VND)
    from app.modules.market.forex import get_exchange_rate
    accounts = firefly_client.get_accounts("asset")
    acc_currency = "VND"
    for acc in accounts:
        if str(acc["id"]) == str(data["account_id"]):
            acc_currency = acc["attributes"].get("currency_code", "VND")
            break
            
    system_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
    activity_amount = data["amount"]
    if acc_currency != system_currency:
        activity_amount = data["amount"] * get_exchange_rate(acc_currency, system_currency)
        
    record_activity("borrower", f"Lent to {data['borrower']}", activity_amount)
    
    # Save/update due date in local SQLite database
    due_str = str(data.get('due', '')).strip().lower()
    if due_str and due_str != 'skip' and due_str != 'none':
        from app.storage.models import Debt
        try:
            parsed_date = datetime.datetime.strptime(due_str.split()[0], "%Y-%m-%d")
            db = SessionLocal()
            local_debt = db.query(Debt).filter(Debt.person_name == data["borrower"]).first()
            if not local_debt:
                local_debt = Debt(
                    person_name=data["borrower"],
                    direction="lent",
                    amount=data["amount"],
                    currency=acc_currency,
                    interest_rate=0.0,
                    due_date=parsed_date,
                    is_settled=False
                )
                db.add(local_debt)
            else:
                local_debt.due_date = parsed_date
                local_debt.amount = data["amount"]
                local_debt.currency = acc_currency
                local_debt.is_settled = False
            db.commit()
            db.close()
        except Exception as ex:
            logger.error(f"Failed to save due date to local DB: {ex}")
            
    msg_text = (
        f"✅ **Lending Recorded Successfully!**\n\n"
        f"• **Borrower**: `{data['borrower']}`\n"
        f"• **Amount**: `{data['amount']:,.2f} {acc_currency}`\n"
        f"• **Due Date**: `{data.get('due') or 'None'}`"
    )
    return msg_text

async def borrow_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from app.utils.parsers import parse_natural_debt_or_loan
    text = update.message.text.strip()
    
    status_msg = await update.message.reply_text("🧠 Analyzing loan information with Google Gemini AI...")
    parsed = parse_natural_debt_or_loan(text)
    await status_msg.delete()
    
    name = parsed.get("name")
    if not name:
        name = text
        
    context.user_data['flow_data']['borrower'] = name
    context.user_data['flow_data']['amount'] = parsed.get("amount")
    context.user_data['flow_data']['due'] = parsed.get("due_date")
    
    # If amount was missing, ask the user
    if context.user_data['flow_data']['amount'] is None:
        keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
        await update.message.reply_text(
            f"Borrower: *{name}*\n\nHow much are you lending them?", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return BORROWER_AMOUNT
        
    # If amount is present, go straight to selecting funding account
    accounts = firefly_client.get_accounts("asset")
    keyboard = [[InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"acc_{acc['id']}")] for acc in accounts]
    keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
    await update.message.reply_text(
        f"Borrower: *{name}*\n"
        f"Amount: *{context.user_data['flow_data']['amount']:,.2f} VND*\n\n"
        f"Which account funded this loan?", 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return BORROWER_ACCOUNT

async def borrow_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['flow_data']['amount'] = extract_amount(update.message.text)
    accounts = firefly_client.get_accounts("asset")
    keyboard = [[InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"acc_{acc['id']}")] for acc in accounts]
    keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
    await update.message.reply_text("Which account funded this loan?", reply_markup=InlineKeyboardMarkup(keyboard))
    return BORROWER_ACCOUNT

async def borrow_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = context.user_data['flow_data']
    data['account_id'] = query.data.split("_")[1]
    
    # If we already have the due date from AI parsing, skip asking and create immediately!
    if data.get('due'):
        await query.edit_message_text("💾 Creating transaction & saving payment terms...")
        msg_text = await create_borrow_transaction_and_log(data, query.message)
        return await send_receipt_and_main_menu(update, context, msg_text)
        
    keyboard = [[InlineKeyboardButton("🔙 Cancel", callback_data="back_main")]]
    await query.edit_message_text("When is this due? (Format: YYYY-MM-DD or 'Skip')", reply_markup=InlineKeyboardMarkup(keyboard))
    return BORROWER_DUE

async def borrow_due(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data['flow_data']
    data['due'] = update.message.text
    
    msg_text = await create_borrow_transaction_and_log(data, update.message)
    return await send_receipt_and_main_menu(update, context, msg_text)


# --- FLOW 6: TRANSFER ---
async def transfer_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['flow_data'] = {}
    amount, currency = extract_amount_and_currency(update.message.text)
    context.user_data['flow_data']['amount'] = amount
    context.user_data['flow_data']['input_currency'] = currency
    accounts = firefly_client.get_accounts("asset")
    keyboard = [[InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"src_{acc['id']}")] for acc in accounts]
    keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
    await update.message.reply_text("Which account are you transferring FROM?", reply_markup=InlineKeyboardMarkup(keyboard))
    return TRANSFER_SOURCE

async def transfer_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    source_id = query.data.split("_")[1]
    context.user_data['flow_data']['source_id'] = source_id
    
    accounts = firefly_client.get_accounts("asset")
    keyboard = []
    for acc in accounts:
        if str(acc["id"]) != str(source_id):
            keyboard.append([InlineKeyboardButton(acc["attributes"]["name"], callback_data=f"dst_{acc['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Cancel & Main Menu", callback_data="back_main")])
    
    await query.edit_message_text("Which account are you transferring TO?", reply_markup=InlineKeyboardMarkup(keyboard))
    return TRANSFER_DEST

async def transfer_dest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    dest_id = query.data.split("_")[1]
    data = context.user_data['flow_data']
    
    amount = data["amount"]
    source_id = data["source_id"]
    input_currency = data.get("input_currency")
    
    # Get currency codes
    accounts = firefly_client.get_accounts("asset")
    source_curr = "VND"
    dest_curr = "VND"
    source_name = "Source"
    dest_name = "Destination"
    
    for acc in accounts:
        if str(acc["id"]) == str(source_id):
            source_curr = acc["attributes"].get("currency_code", "VND")
            source_name = acc["attributes"]["name"]
        elif str(acc["id"]) == str(dest_id):
            dest_curr = acc["attributes"].get("currency_code", "VND")
            dest_name = acc["attributes"]["name"]
            
    source_deduct_amount = amount
    if input_currency and input_currency != source_curr:
        from app.modules.market.forex import get_exchange_rate
        rate = get_exchange_rate(input_currency, source_curr)
        source_deduct_amount = amount * rate
        
    dest_add_amount = source_deduct_amount
    exchange_note = ""
    
    if source_curr != dest_curr:
        from app.modules.market.forex import get_exchange_rate
        rate = get_exchange_rate(source_curr, dest_curr)
        dest_add_amount = source_deduct_amount * rate
        exchange_note = f" (Converted to {dest_add_amount:,.2f} {dest_curr} at rate {rate:,.4f})"
        
    import datetime
    today_iso = datetime.date.today().strftime("%Y-%m-%d")
    
    tx_payload = {
        "transactions": [{
            "type": "transfer",
            "date": today_iso,
            "amount": str(source_deduct_amount),
            "description": f"Transfer from {source_name} to {dest_name}{exchange_note}",
            "source_id": source_id,
            "destination_id": dest_id,
            "foreign_amount": str(dest_add_amount) if source_curr != dest_curr else None,
            "foreign_currency_code": dest_curr if source_curr != dest_curr else None
        }]
    }
    
    # Clean payload
    if not tx_payload["transactions"][0]["foreign_amount"]:
        del tx_payload["transactions"][0]["foreign_amount"]
        del tx_payload["transactions"][0]["foreign_currency_code"]
        
    firefly_client.create_transaction(tx_payload)
    
    # Activity logging
    from app.modules.market.forex import get_exchange_rate
    from app.config import config
    system_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
    activity_amount = source_deduct_amount
    if source_curr != system_currency:
        activity_amount = source_deduct_amount * get_exchange_rate(source_curr, system_currency)
        
    record_activity("transfer", f"Transferred from {source_name} to {dest_name}", activity_amount)
    
    msg = (
        f"✅ **Transfer Successful!**\n\n"
        f"• **From**: `{source_name}`\n"
        f"• **To**: `{dest_name}`\n"
        f"• **Amount Sent**: `{source_deduct_amount:,.2f} {source_curr}`\n"
        + (f"• **Amount Received**: `{dest_add_amount:,.2f} {dest_curr}`\n" if source_curr != dest_curr else "")
    )
    return await send_receipt_and_main_menu(update, context, msg)

# Fallbacks
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Flow cancelled.")
    await start(update, context)
    return MAIN_MENU

def get_conversation_handler():
    return ConversationHandler(
        entry_points=[CommandHandler('start', start), CallbackQueryHandler(main_menu_callback, pattern="^(flow_|sub_)")],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(main_menu_callback, pattern="^(flow_|sub_)"),
                CallbackQueryHandler(view_cmd, pattern="^trigger_view$"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            
            BUY_ASSET_TYPE: [
                CallbackQueryHandler(buy_type, pattern="^type_"),
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, buy_natural_purchase)
            ],
            BUY_ASSET_NAME: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, buy_name)
            ],
            BUY_SELECT_MODE: [
                CallbackQueryHandler(buy_select_mode, pattern="^buy_"),
                CallbackQueryHandler(buy_suggestion_callback, pattern="^buysugg_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            BUY_ASSET_QTY: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                CallbackQueryHandler(buy_spent_instead, pattern="^buy_spent_instead$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, buy_qty)
            ],
            BUY_ASSET_SPENT_AMOUNT: [
                CallbackQueryHandler(back_to_qty, pattern="^back_to_qty$"),
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, buy_spent_amount_entered)
            ],
            BUY_ASSET_CALCULATED_CONFIRM: [
                CallbackQueryHandler(buy_calculated_confirm, pattern="^calc_confirm_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            BUY_ASSET_COST: [
                CallbackQueryHandler(buy_cost_confirm, pattern="^cost_confirm_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            BUY_ASSET_COST_MANUAL: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, buy_cost_manual)
            ],
            BUY_ASSET_ACCOUNT: [
                CallbackQueryHandler(buy_account, pattern="^(acc_|natbuy_)"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            
            SELL_ASSET_SELECT: [
                CallbackQueryHandler(sell_select, pattern="^sell_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            SELL_ASSET_QTY: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sell_qty)
            ],
            SELL_ASSET_REV: [
                CallbackQueryHandler(sell_revenue_confirm, pattern="^sell_revenue_confirm_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            SELL_ASSET_REV_MANUAL: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sell_rev_manual)
            ],
            SELL_ASSET_ACCOUNT: [
                CallbackQueryHandler(sell_account, pattern="^acc_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            
            DEPOSIT_AMOUNT: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount)
            ],
            DEPOSIT_SOURCE: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_source)
            ],
            DEPOSIT_ACCOUNT: [
                CallbackQueryHandler(deposit_account, pattern="^acc_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            
            DEBT_LENDER: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_lender)
            ],
            DEBT_AMOUNT: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_amount)
            ],
            DEBT_ACCOUNT: [
                CallbackQueryHandler(debt_account, pattern="^acc_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            DEBT_DUE: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, debt_due)
            ],
            
            BORROWER_NAME: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, borrow_name)
            ],
            BORROWER_AMOUNT: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, borrow_amount)
            ],
            BORROWER_ACCOUNT: [
                CallbackQueryHandler(borrow_account, pattern="^acc_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            BORROWER_DUE: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, borrow_due)
            ],
            TRANSFER_AMOUNT: [
                CallbackQueryHandler(back_main, pattern="^back_main$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_amount)
            ],
            TRANSFER_SOURCE: [
                CallbackQueryHandler(transfer_source, pattern="^src_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
            TRANSFER_DEST: [
                CallbackQueryHandler(transfer_dest, pattern="^dst_"),
                CallbackQueryHandler(back_main, pattern="^back_main$")
            ],
        },
        fallbacks=[
            CommandHandler('start', start),
            CommandHandler('cancel', cancel)
        ],
        per_message=False
    )

# --- VIEW FLOWS (Stateless) ---
async def view_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for /view. Combines all vault data into a single large report."""
    if update.callback_query:
        await update.callback_query.answer("Fetching vault data...")
        await update.callback_query.edit_message_text("🔄 Compiling your comprehensive vault report. Please wait...")
    else:
        status_msg = await update.message.reply_text("🔄 Compiling your comprehensive vault report. Please wait...")
        
    # 1. Accounts
    accounts = firefly_client.get_accounts("asset")
    acc_msg = format_accounts_report(accounts)
    
    # 2. Portfolio
    db = SessionLocal()
    holdings = db.query(Holding).all()
    port_msg = format_portfolio_report(holdings)
    
    # 3. Debt
    receivables_accs = firefly_client.get_accounts("expense") # Borrowers who owe us
    liabilities_accs = firefly_client.get_accounts("revenue") # Lenders we owe
    debt_msg = format_debt_report(receivables_accs, liabilities_accs)
    
    # 4. Net Worth
    from app.modules.market.forex import get_exchange_rate
    from app.config import config
    from app.modules.market.service import market_service
    target_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
    
    def sum_converted_accounts(accs):
        total = 0.0
        for a in accs:
            bal = abs(float(a["attributes"].get("current_balance", 0.0)))
            curr = a["attributes"].get("currency_code", target_currency)
            if curr != target_currency:
                bal *= get_exchange_rate(curr, target_currency)
            total += bal
        return total
        
    cash = sum_converted_accounts(accounts)
    assets = 0.0
    for h in holdings:
        live_price_usd = market_service.get_price(h.symbol, h.asset_type)
        if live_price_usd > 0.0:
            live_price_converted = live_price_usd * get_exchange_rate("USD", target_currency)
            assets += h.quantity * live_price_converted
        else:
            currency = h.currency if hasattr(h, "currency") else "VND"
            assets += h.total_spent * get_exchange_rate(currency, target_currency)
            
    filtered_receivables = [r for r in receivables_accs if r["attributes"]["name"].lower() != "investments"]
    receivables = sum_converted_accounts(filtered_receivables)
    liabilities = sum_converted_accounts(liabilities_accs)
    
    db.close()
    
    nw_msg = format_net_worth(cash, assets, receivables, liabilities)
    combined_msg = f"{acc_msg}\n\n---\n\n{port_msg}\n\n---\n\n{debt_msg}\n\n---\n\n{nw_msg}"
    
    if not update.callback_query:
        await status_msg.delete()
        
    return await send_receipt_and_main_menu(update, context, combined_msg)

def get_view_handlers():
    """Returns a list of handlers for the view operations, to be registered alongside the ConversationHandler."""
    return [
        CommandHandler('view', view_cmd),
        CallbackQueryHandler(view_cmd, pattern="^trigger_view$")
    ]
