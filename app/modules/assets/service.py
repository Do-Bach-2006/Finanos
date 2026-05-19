"""
Asset business logic.
Handles buying, selling, holding, updating, and validating asset records.
Saves, updates, and persists holdings in SQLite.
"""
from typing import List, Dict, Any
from app.modules.assets.models import Holding
from app.utils.logging import logger

class AssetService:
    def __init__(self):
        pass
        
    def execute_action(self, db, action_data: Dict[str, Any], user_id: str):
        """
        Executes a portfolio transaction (buy, sell, or hold) and updates SQLite holdings.
        """
        action = action_data.get("action", "buy") # buy, sell, hold
        symbol = action_data.get("symbol", "").strip().upper()
        asset_type = action_data.get("asset_type", "crypto").strip().lower()
        quantity = float(action_data.get("quantity", 0.0))
        price = float(action_data.get("price", 0.0)) # total cost/spent for buy, revenue for sell, avg_price for hold
        currency = action_data.get("currency", "VND").strip().upper()
        
        if not symbol:
            raise ValueError("Asset symbol/name is required")
            
        # Filter by both symbol and asset_type to prevent overlaps
        holding = db.query(Holding).filter(
            Holding.symbol == symbol,
            Holding.asset_type == asset_type
        ).first()
        
        if action == "buy":
            if holding:
                logger.info(f"[AssetService] Updating existing holding for {symbol} ({asset_type})")
                holding.quantity += quantity
                holding.total_spent += price
                if holding.quantity > 0:
                    holding.average_buy_price = holding.total_spent / holding.quantity
            else:
                logger.info(f"[AssetService] Creating new holding for {symbol} ({asset_type})")
                holding = Holding(
                    symbol=symbol,
                    asset_type=asset_type,
                    quantity=quantity,
                    total_spent=price,
                    average_buy_price=price / quantity if quantity > 0 else 0.0,
                    currency=currency
                )
                db.add(holding)
                
        elif action == "hold":
            # Direct tracking of existing holdings (override or add)
            if holding:
                logger.info(f"[AssetService] Replacing existing hold quantity for {symbol} ({asset_type})")
                holding.quantity = quantity
                holding.average_buy_price = price # here price represents avg buy price
                holding.total_spent = quantity * price
            else:
                logger.info(f"[AssetService] Adding new hold for {symbol} ({asset_type})")
                holding = Holding(
                    symbol=symbol,
                    asset_type=asset_type,
                    quantity=quantity,
                    average_buy_price=price,
                    total_spent=quantity * price,
                    currency=currency
                )
                db.add(holding)
                
        elif action == "sell":
            if holding and holding.quantity >= quantity:
                logger.info(f"[AssetService] Selling {quantity} units of {symbol}")
                holding.quantity -= quantity
                holding.total_spent = max(0.0, holding.total_spent - (quantity * holding.average_buy_price))
                if holding.quantity <= 0.000001:
                    db.delete(holding)
            else:
                raise ValueError(f"Insufficient quantity of {symbol} in portfolio to sell (Have: {holding.quantity if holding else 0}, selling: {quantity})")
        
        db.commit()
        return holding

asset_service = AssetService()
