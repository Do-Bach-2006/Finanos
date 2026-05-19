"""
Debt domain models.
Defines structures for borrowed money, lent money, repayments,
due dates, and interest terms.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, func
from app.storage.database import Base

class Debt(Base):
    __tablename__ = "debts"

    id = Column(Integer, primary_key=True, index=True)
    person_name = Column(String, index=True, nullable=False)
    direction = Column(String, nullable=False) # "borrowed" or "lent"
    amount = Column(Float, nullable=False)
    currency = Column(String, nullable=False, default="VND")
    interest_rate = Column(Float, nullable=True) # annual percentage
    due_date = Column(DateTime, nullable=True)
    is_settled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
