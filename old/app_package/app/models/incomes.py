"""
収入関連モデル
"""
from datetime import datetime
from app import db

class SalaryIncomes(db.Model):
    """給与収入モデル"""
    __tablename__ = 'salary_incomes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    monthly_amount = db.Column(db.Float, nullable=False)
    annual_bonus = db.Column(db.Float, default=0)
    annual_amount = db.Column(db.Float, nullable=False)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    # 昇給率（年率%）
    salary_increase_rate = db.Column(db.Float, default=3.0)
    
    # 年間収入上限設定
    has_cap = db.Column(db.Boolean, default=False)
    annual_income_cap = db.Column(db.Float, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SidejobIncomes(db.Model):
    """副業収入モデル"""
    __tablename__ = 'sidejob_incomes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    monthly_amount = db.Column(db.Float, nullable=False)
    annual_amount = db.Column(db.Float, nullable=False)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    # 昇給率（年率%）
    income_increase_rate = db.Column(db.Float, default=0.0)
    
    # 年間収入上限設定
    has_cap = db.Column(db.Boolean, default=False)
    annual_income_cap = db.Column(db.Float, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BusinessIncomes(db.Model):
    """事業収入モデル"""
    __tablename__ = 'business_incomes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    monthly_amount = db.Column(db.Float, nullable=False)
    annual_amount = db.Column(db.Float, nullable=False)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    # 収入増加率（年率%）
    income_increase_rate = db.Column(db.Float, default=5.0)
    
    # 年間収入上限設定
    has_cap = db.Column(db.Boolean, default=False)
    annual_income_cap = db.Column(db.Float, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class InvestmentIncomes(db.Model):
    """投資収入モデル"""
    __tablename__ = 'investment_incomes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    monthly_amount = db.Column(db.Float, nullable=False)
    annual_amount = db.Column(db.Float, nullable=False)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    # 運用利回り（年率%）
    annual_return_rate = db.Column(db.Float, default=5.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PensionIncomes(db.Model):
    """年金収入モデル"""
    __tablename__ = 'pension_incomes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    monthly_amount = db.Column(db.Float, nullable=False)
    annual_amount = db.Column(db.Float, nullable=False)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class OtherIncomes(db.Model):
    """その他収入モデル"""
    __tablename__ = 'other_incomes'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    monthly_amount = db.Column(db.Float, nullable=False)
    annual_amount = db.Column(db.Float, nullable=False)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow) 