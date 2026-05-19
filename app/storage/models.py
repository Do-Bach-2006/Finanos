"""
Core storage models for cross-module features like message history.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, Float, func
from app.storage.database import Base

class MessageHistory(Base):
    __tablename__ = "message_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)
    chat_id = Column(String, index=True, nullable=False)
    message_text = Column(Text, nullable=False)
    intent = Column(String, nullable=True)
    response_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    activity_type = Column(String, index=True, nullable=False) # buy, sell, hold, deposit, debt, borrower, natural_purchase
    description = Column(Text, nullable=False)
    amount = Column(Float, nullable=True) # in system target currency (VND)
    created_at = Column(DateTime, default=func.now())

