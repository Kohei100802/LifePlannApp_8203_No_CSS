"""
支出関連モデル
"""
from datetime import datetime
from app import db
from app.models.enums import (
    ResidenceType, KindergartenType, ElementaryType,
    JuniorType, HighType, CollegeType, EventCategory,
    RepaymentMethod
)

class LivingExpenses(db.Model):
    """生活費モデル"""
    __tablename__ = 'living_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    # 物価上昇率（年率%）
    inflation_rate = db.Column(db.Float, default=2.0)
    
    # 食費
    food_home = db.Column(db.Float, default=0)
    food_outside = db.Column(db.Float, default=0)
    
    # 光熱費
    utility_electricity = db.Column(db.Float, default=0)
    utility_gas = db.Column(db.Float, default=0)
    utility_water = db.Column(db.Float, default=0)
    
    # 通信費
    subscription_services = db.Column(db.Float, default=0)
    internet = db.Column(db.Float, default=0)
    phone = db.Column(db.Float, default=0)
    
    # 日用品
    household_goods = db.Column(db.Float, default=0)
    hygiene = db.Column(db.Float, default=0)
    
    # 被服・美容
    clothing = db.Column(db.Float, default=0)
    beauty = db.Column(db.Float, default=0)
    
    # 子供費用
    child_food = db.Column(db.Float, default=0)
    child_clothing = db.Column(db.Float, default=0)
    child_medical = db.Column(db.Float, default=0)
    child_other = db.Column(db.Float, default=0)
    
    # その他
    transport = db.Column(db.Float, default=0)
    entertainment = db.Column(db.Float, default=0)
    pet_costs = db.Column(db.Float, default=0)
    other_expenses = db.Column(db.Float, default=0)
    
    monthly_total_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EducationPlans(db.Model):
    """教育計画モデル"""
    __tablename__ = 'education_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    
    child_name = db.Column(db.String(100), nullable=False)
    child_birth_date = db.Column(db.Date, nullable=False)
    
    # 選択された教育段階
    kindergarten_type = db.Column(db.Enum(KindergartenType), default=KindergartenType.NONE)
    elementary_type = db.Column(db.Enum(ElementaryType), default=ElementaryType.PUBLIC)
    junior_type = db.Column(db.Enum(JuniorType), default=JuniorType.PUBLIC)
    high_type = db.Column(db.Enum(HighType), default=HighType.PUBLIC)
    college_type = db.Column(db.Enum(CollegeType), default=CollegeType.NONE)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EducationExpenses(db.Model):
    """教育費モデル"""
    __tablename__ = 'education_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    education_plan_id = db.Column(db.Integer, db.ForeignKey('education_plans.id'), nullable=False)
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    child_name = db.Column(db.String(100), nullable=False)
    child_birth_date = db.Column(db.Date, nullable=False)
    
    stage = db.Column(db.String(20), nullable=False)
    stage_type = db.Column(db.String(50), nullable=False)
    
    monthly_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    education_plan = db.relationship('EducationPlans', backref='expenses')

class HousingExpenses(db.Model):
    """住居費モデル"""
    __tablename__ = 'housing_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    residence_type = db.Column(db.Enum(ResidenceType), nullable=False)
    
    # 賃貸用
    rent_monthly = db.Column(db.Float, default=0)
    
    # 持家用
    mortgage_monthly = db.Column(db.Float, default=0)
    property_tax_monthly = db.Column(db.Float, default=0)
    management_fee_monthly = db.Column(db.Float, default=0)
    repair_reserve_monthly = db.Column(db.Float, default=0)
    fire_insurance_monthly = db.Column(db.Float, default=0)
    
    # ローン計算用
    purchase_price = db.Column(db.Float, default=0)
    down_payment = db.Column(db.Float, default=0)
    loan_interest_rate = db.Column(db.Float, default=0)
    loan_term_years = db.Column(db.Integer, default=0)
    repayment_method = db.Column(db.Enum(RepaymentMethod), default=RepaymentMethod.EQUAL_PAYMENT)
    
    monthly_total_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class InsuranceExpenses(db.Model):
    """保険費モデル"""
    __tablename__ = 'insurance_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    medical_insurance = db.Column(db.Float, default=0)
    cancer_insurance = db.Column(db.Float, default=0)
    life_insurance = db.Column(db.Float, default=0)
    income_protection = db.Column(db.Float, default=0)
    accident_insurance = db.Column(db.Float, default=0)
    liability_insurance = db.Column(db.Float, default=0)
    fire_insurance = db.Column(db.Float, default=0)
    long_term_care_insurance = db.Column(db.Float, default=0)
    other_insurance = db.Column(db.Float, default=0)
    
    insured_person = db.Column(db.String(100))
    insurance_company = db.Column(db.String(100))
    insurance_term_years = db.Column(db.Integer, default=0)
    renew_type = db.Column(db.String(50))
    
    monthly_total_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class EventExpenses(db.Model):
    """イベント費用モデル"""
    __tablename__ = 'event_expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    category = db.Column(db.Enum(EventCategory), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    
    # 繰り返し設定
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_interval = db.Column(db.Integer, default=1)
    recurrence_count = db.Column(db.Integer, default=1)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow) 