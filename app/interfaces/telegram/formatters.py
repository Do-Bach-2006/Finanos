"""
Telegram message formatters.
Converts raw data dictionaries into clean Markdown strings for chat.
"""

def format_accounts_report(accounts_data: list) -> str:
    from app.modules.market.forex import get_exchange_rate
    from app.config import config
    
    if not accounts_data:
        return "You have no active cash/bank accounts."
        
    msg = "🏦 *My Accounts*\n\n"
    total_cash = 0.0
    target_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
    
    negative_accounts = []
    
    for acc in accounts_data:
        name = acc["attributes"]["name"]
        balance = float(acc["attributes"].get("current_balance", 0.0))
        currency = acc["attributes"].get("currency_code", target_currency)
        
        msg += f"• *{name}*: {balance:,.2f} {currency}\n"
        
        if balance < 0:
            negative_accounts.append((name, balance, currency))
            
        if currency != target_currency:
            rate = get_exchange_rate(currency, target_currency)
            total_cash += balance * rate
        else:
            total_cash += balance
            
    msg += f"\n*Total Cash*: {total_cash:,.2f} {target_currency}"
    
    # ⚠️ Situational Alerts
    warnings = []
    if negative_accounts:
        for name, bal, curr in negative_accounts:
            warnings.append(f"❌ *{name}* has a negative balance: `{bal:,.2f} {curr}`!")
            
    # Convert low cash limit to VND
    if total_cash < 5000000.0:
        warnings.append(f"⚠️ *Low Cash Reserve*: Your total liquid cash ({total_cash:,.2f} {target_currency}) is below the standard backup threshold of 5,000,000 VND!")
        
    if warnings:
        msg += "\n\n🚨 *FINANCIAL WARNINGS*:\n" + "\n".join(warnings)
        
    return msg

def format_portfolio_report(holdings: list) -> str:
    """
    Formulates a comprehensive portfolio report comparing purchase cost
    with real-time live asset valuations and individual yield tracking.
    """
    from app.modules.market.service import market_service
    from app.modules.market.forex import get_exchange_rate
    from app.config import config
    
    if not holdings:
        return "📈 *My Portfolio*\n\nYou have no recorded assets."
        
    target_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
    
    msg = "📈 *My Portfolio (Live Valuations)*\n\n"
    total_live_val = 0.0
    total_cost_val = 0.0
    underperforming_assets = []
    
    for h in holdings:
        symbol = h.symbol.upper()
        asset_type = h.asset_type
        qty = h.quantity
        spent = h.total_spent
        h_curr = h.currency if hasattr(h, 'currency') else "VND"
        
        # Convert cost to default system currency
        cost_converted = spent * get_exchange_rate(h_curr, target_currency)
        total_cost_val += cost_converted
        
        # Fetch Live Price in USD
        live_price_usd = market_service.get_price(symbol, asset_type)
        if live_price_usd > 0.0:
            live_price_converted = live_price_usd * get_exchange_rate("USD", target_currency)
            live_value_converted = qty * live_price_converted
        else:
            live_value_converted = cost_converted
            live_price_converted = cost_converted / qty if qty > 0 else 0.0
            
        total_live_val += live_value_converted
        
        # Compute Profit & Loss (P&L) metrics
        pnl_converted = live_value_converted - cost_converted
        pnl_pct = (pnl_converted / cost_converted * 100) if cost_converted > 0 else 0.0
        pnl_sign = "+" if pnl_converted >= 0 else ""
        pnl_emoji = "🟢" if pnl_converted >= 0 else "🔴"
        
        if pnl_pct <= -15.0:
            underperforming_assets.append((symbol, pnl_pct))
            
        msg += (
            f"• *{symbol}* ({asset_type.upper()})\n"
            f"  Qty: {qty:,.4f} | Live: {live_value_converted:,.2f} {target_currency}\n"
            f"  Cost: {cost_converted:,.2f} {target_currency} ({spent:,.2f} {h_curr})\n"
            f"  P&L: {pnl_emoji} {pnl_sign}{pnl_converted:,.2f} {target_currency} ({pnl_sign}{pnl_pct:.1f}%)\n\n"
        )
        
    total_pnl = total_live_val - total_cost_val
    total_pnl_pct = (total_pnl / total_cost_val * 100) if total_cost_val > 0 else 0.0
    pnl_sign_total = "+" if total_pnl >= 0 else ""
    pnl_emoji_total = "🟢" if total_pnl >= 0 else "🔴"
    
    msg += "──────────────────\n"
    msg += f"💰 *Total Cost*: {total_cost_val:,.2f} {target_currency}\n"
    msg += f"🚀 *Total Live Value*: {total_live_val:,.2f} {target_currency}\n"
    msg += f"📊 *Total Return*: {pnl_emoji_total} {pnl_sign_total}{total_pnl:,.2f} {target_currency} ({pnl_sign_total}{total_pnl_pct:.1f}%)\n"
    
    # Underperforming warnings
    if underperforming_assets:
        msg += "\n⚠️ *ASSET DEPRECIATION WARNINGS*:\n"
        for sym, drop in underperforming_assets:
            msg += f"  • *{sym}* is down `{drop:.1f}%` from cost! Consider reviewing your strategy.\n"
            
    return msg

def format_debt_report(receivables: list, liabilities: list) -> str:
    msg = "🤝 *Debt Overview*\n\n"
    
    total_receivable = 0.0
    msg += "🟢 *Money Owed To Me (Receivables)*\n"
    
    # Filter out Investments
    receivables_filtered = [r for r in receivables if r["attributes"]["name"].lower() != "investments"]
    
    if not receivables_filtered:
        msg += "  _None_\n"
    for r in receivables_filtered:
        name = r["attributes"]["name"]
        balance = float(r["attributes"].get("current_balance", 0.0))
        total_receivable += balance
        msg += f"  • {name}: {balance:,.2f} VND\n"
        
    msg += "\n🔴 *Money I Owe (Liabilities)*\n"
    total_liability = 0.0
    if not liabilities:
        msg += "  _None_\n"
    for l in liabilities:
        name = l["attributes"]["name"]
        balance = abs(float(l["attributes"].get("current_balance", 0.0)))
        total_liability += balance
        msg += f"  • {name}: {balance:,.2f} VND\n"
        
    net_debt = total_receivable - total_liability
    msg += f"\n*Net Debt*: {net_debt:,.2f} VND"
    
    # Debt situation warnings
    warnings = []
    if total_liability > 0:
        warnings.append(f"⚠️ *Outstanding Liabilities*: You currently owe a total of `{total_liability:,.2f} VND` across {len(liabilities)} creditors.")
    if net_debt < 0:
        warnings.append(f"🚨 *Net Debt Deficit*: Your total liabilities exceed your receivables by `{abs(net_debt):,.2f} VND`!")
        
    if warnings:
        msg += "\n\n⚠️ *DEBT RISK WARNINGS*:\n" + "\n".join(warnings)
        
    return msg

def format_net_worth(total_cash: float, total_assets: float, total_receivable: float, total_liability: float) -> str:
    net_worth = total_cash + total_assets + total_receivable - total_liability
    
    msg = "📊 *Total Net Worth*\n\n"
    msg += f"Cash: {total_cash:,.2f} VND\n"
    msg += f"Assets (Live): {total_assets:,.2f} VND\n"
    msg += f"Receivables: {total_receivable:,.2f} VND\n"
    msg += f"Liabilities: -{total_liability:,.2f} VND\n"
    msg += "──────────────────\n"
    msg += f"*NET WORTH: {net_worth:,.2f} VND*"
    
    # Situational Warnings
    warnings = []
    if total_cash < 0:
        warnings.append("❌ *Negative Cash Balance*: Your consolidated cash/bank balance is currently negative!")
    elif total_cash < 5000000.0:
        warnings.append("⚠️ *Low Liquidity Reserve*: Your total cash is below 5,000,000 VND. Risk of cash shortage!")
        
    if total_liability > 0:
        # High leverage warning: liabilities are more than 50% of (cash + assets)
        total_wealth = total_cash + total_assets
        if total_wealth > 0:
            ratio = total_liability / total_wealth
            if ratio > 0.5:
                warnings.append(f"⚠️ *High Leverage*: Your liabilities constitute {ratio*100:.1f}% of your total cash & holdings! Recommend paying down debt.")
            
            # Liquidity cover ratio: cash / liability
            if total_cash > 0:
                cover_ratio = total_cash / total_liability
                if cover_ratio < 0.20:
                    warnings.append(f"⚠️ *Low Debt Cover*: Your liquid cash covers only {cover_ratio*100:.1f}% of your outstanding liabilities! High emergency risk.")
            else:
                warnings.append("🚨 *Zero Debt Cover*: You have zero liquid cash to cover your outstanding liabilities!")
                
    if net_worth < 0:
        warnings.append("💀 *Insolvency Critical*: Your total liabilities exceed all of your assets and cash combined! Net worth is negative.")
        
    if warnings:
        msg += "\n\n⚠️ *FINANCIAL RISK AUDIT*:\n" + "\n".join(warnings)
        
    return msg
