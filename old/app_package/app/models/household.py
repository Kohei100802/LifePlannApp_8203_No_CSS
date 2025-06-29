"""
家計簿関連モデル
"""
from datetime import datetime
from app import db

class HouseholdBook(db.Model):
    """家計簿モデル"""
    __tablename__ = 'household_books'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    entries = db.relationship('HouseholdEntry', backref='book', lazy='dynamic', cascade='all, delete-orphan')

class HouseholdEntry(db.Model):
    """家計簿エントリーモデル"""
    __tablename__ = 'household_entries'
    
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('household_books.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    date = db.Column(db.Date, nullable=False)
    category_id = db.Column(db.Integer, nullable=False)
    category_type = db.Column(db.String(20), nullable=False)  # 'expense' or 'income'
    
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    
    # 決済情報
    payment_method = db.Column(db.String(50))  # 現金、クレジットカード、電子マネー等
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExpenseCategory(db.Model):
    """支出カテゴリモデル"""
    __tablename__ = 'expense_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(50))
    color = db.Column(db.String(7))  # HEXカラーコード
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class IncomeCategory(db.Model):
    """収入カテゴリモデル"""
    __tablename__ = 'income_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(50))
    color = db.Column(db.String(7))  # HEXカラーコード
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Account(db.Model):
    """口座モデル"""
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    account_type = db.Column(db.String(50), nullable=False)  # 普通預金、当座預金、クレジットカード等
    
    balance = db.Column(db.Float, default=0)
    
    # 銀行情報
    bank_name = db.Column(db.String(100))
    branch_name = db.Column(db.String(100))
    account_number = db.Column(db.String(20))
    
    # クレジットカード情報
    credit_limit = db.Column(db.Float)
    closing_day = db.Column(db.Integer)  # 締め日
    payment_day = db.Column(db.Integer)  # 支払日
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    transactions = db.relationship('AccountTransaction', backref='account', lazy='dynamic')

class AccountTransaction(db.Model):
    """口座取引モデル"""
    __tablename__ = 'account_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)
    
    transaction_date = db.Column(db.DateTime, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'debit' or 'credit'
    amount = db.Column(db.Float, nullable=False)
    balance_after = db.Column(db.Float, nullable=False)
    
    description = db.Column(db.String(200))
    category = db.Column(db.String(50))
    
    # 関連エントリー
    household_entry_id = db.Column(db.Integer, db.ForeignKey('household_entries.id'))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow) 