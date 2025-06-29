"""
シミュレーション関連モデル
"""
from datetime import datetime
from app import db

class LifeplanSimulations(db.Model):
    """ライフプランシミュレーションモデル"""
    __tablename__ = 'lifeplan_simulations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    # シミュレーション設定
    birth_year = db.Column(db.Integer, nullable=False)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    # 初期資産
    initial_assets = db.Column(db.Float, default=0)
    
    # 物価上昇率（年率%）
    inflation_rate = db.Column(db.Float, default=2.0)
    
    # 運用利回り（年率%）
    investment_return_rate = db.Column(db.Float, default=3.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    expense_links = db.relationship('LifeplanExpenseLinks', backref='simulation', lazy='dynamic', cascade='all, delete-orphan')
    income_links = db.relationship('LifeplanIncomeLinks', backref='simulation', lazy='dynamic', cascade='all, delete-orphan')

class LifeplanExpenseLinks(db.Model):
    """シミュレーションと支出の関連モデル"""
    __tablename__ = 'lifeplan_expense_links'
    
    id = db.Column(db.Integer, primary_key=True)
    simulation_id = db.Column(db.Integer, db.ForeignKey('lifeplan_simulations.id'), nullable=False)
    expense_type = db.Column(db.String(50), nullable=False)
    expense_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LifeplanIncomeLinks(db.Model):
    """シミュレーションと収入の関連モデル"""
    __tablename__ = 'lifeplan_income_links'
    
    id = db.Column(db.Integer, primary_key=True)
    simulation_id = db.Column(db.Integer, db.ForeignKey('lifeplan_simulations.id'), nullable=False)
    income_type = db.Column(db.String(50), nullable=False)
    income_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow) 