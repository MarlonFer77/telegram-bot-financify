import datetime
from sqlalchemy import Column, BigInteger, Integer, String, Float, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    first_name = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.now)

    transactions = relationship("Transaction", back_populates="owner")

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, index=True)
    amount = Column(Float, nullable=False)
    type = Column(String, default="despesa") # 'despesa' ou 'receita'
    category = Column(String, index=True)
    transaction_date = Column(Date, default=datetime.date.today)
    created_at = Column(DateTime, default=datetime.datetime.now)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="transactions")