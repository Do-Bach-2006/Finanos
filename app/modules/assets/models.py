"""
Asset domain models.
Defines structures for assets, holdings, buy orders, sell orders,
and portfolio entries.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.storage.database import Base

class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    asset_type = Column(String, index=True, nullable=False) # crypto, stock, forex, cs2
    quantity = Column(Float, nullable=False, default=0.0)
    average_buy_price = Column(Float, nullable=False, default=0.0)
    total_spent = Column(Float, nullable=False, default=0.0)
    currency = Column(String, nullable=False, default="VND")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
