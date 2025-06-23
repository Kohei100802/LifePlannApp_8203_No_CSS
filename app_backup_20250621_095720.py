from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import os
import json
import logging
import traceback
from logging.handlers import RotatingFileHandler
from enum import Enum
from sqlalchemy import inspect
import yfinance as yf

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lifeplan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# エラーログ設定
if not os.path.exists('logs'):
    os.makedirs('logs')

# ローテーティングファイルハンドラーでログを設定
file_handler = RotatingFileHandler('logs/error.log', maxBytes=10240000, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.ERROR)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

# 404エラーハンドラー（Not Found専用）
@app.errorhandler(404)
def handle_not_found(e):
    # 特定のパスは無視
    ignored_paths = [
        '/favicon.ico',
        '/.well-known/',
        '/apple-touch-icon',
        '/robots.txt',
        '/sitemap.xml',
        '/.env'
    ]
    
    should_ignore = any(ignored_path in request.path for ignored_path in ignored_paths)
    
    if should_ignore:
        return '', 404
    
    # APIエンドポイントの場合
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not Found', 'path': request.path}), 404
    
    # 通常のページの場合
    return render_template('error.html', error='ページが見つかりません'), 404

# エラーハンドラー追加
@app.errorhandler(Exception)
def handle_exception(e):
    # 特定のエラーは無視（ログに記録しない）
    ignored_paths = [
        '/favicon.ico',
        '/.well-known/',
        '/apple-touch-icon',
        '/robots.txt',
        '/sitemap.xml',
        '/.env'
    ]
    
    # 無視するパスかチェック
    should_ignore = any(ignored_path in request.path for ignored_path in ignored_paths)
    
    # 404エラーかつ無視すべきパスの場合はログに記録しない
    if should_ignore and hasattr(e, 'code') and e.code == 404:
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not Found'}), 404
        return '', 404
    
    # 通常のエラーのみログに記録
    error_message = f"""
=== エラー発生 ===
時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
URL: {request.url}
メソッド: {request.method}
ユーザーエージェント: {request.headers.get('User-Agent', 'Unknown')}
リモートアドレス: {request.remote_addr}
エラータイプ: {type(e).__name__}
エラーメッセージ: {str(e)}
スタックトレース:
{traceback.format_exc()}
=== エラー終了 ===
    """
    app.logger.error(error_message)
    
    # JSONレスポンスを期待するAPIエンドポイントの場合
    if request.path.startswith('/api/'):
        return jsonify({
            'error': True,
            'message': 'サーバーエラーが発生しました。',
            'details': str(e) if app.debug else 'Internal Server Error',
            'timestamp': datetime.now().isoformat()
        }), 500
    
    # 通常のWebページの場合
    return render_template('error.html', error=str(e) if app.debug else 'Internal Server Error'), 500

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Enums for choices
class ResidenceType(Enum):
    RENTAL = '賃貸'
    OWNED_WITH_LOAN = '持家（ローンあり）'
    OWNED_WITHOUT_LOAN = '持家（ローンなし）'

class KindergartenType(Enum):
    NONE = '未就園'
    PUBLIC = '公立幼稚園'
    PRIVATE = '私立幼稚園'

class ElementaryType(Enum):
    PUBLIC = '公立小学校'
    PRIVATE = '私立小学校'

class JuniorType(Enum):
    PUBLIC = '公立中学校'
    PRIVATE = '私立中学校'

class HighType(Enum):
    PUBLIC = '公立高校'
    PRIVATE = '私立高校'

class CollegeType(Enum):
    NONE = '進学しない'
    NATIONAL = '国公立大学'
    PRIVATE_LIBERAL = '私立文系'
    PRIVATE_SCIENCE = '私立理系'
    JUNIOR_COLLEGE = '短期大学'
    VOCATIONAL = '専門学校'

class EventCategory(Enum):
    MARRIAGE = '結婚'
    BIRTH = '出産'
    CAR = '車'
    MOVING = '引越'
    CARE = '介護'
    FUNERAL = '葬儀'
    TRAVEL = '旅行'
    OTHER = 'その他'

class RepaymentMethod(Enum):
    EQUAL_PAYMENT = '元利均等'
    EQUAL_PRINCIPAL = '元金均等'

# Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)  # メールアドレス追加
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LivingExpenses(db.Model):
    __tablename__ = 'living_expenses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    # 物価上昇率（年率%）
    inflation_rate = db.Column(db.Float, default=2.0)  # デフォルト2%
    
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
    child_food = db.Column(db.Float, default=0)      # 子供の食費
    child_clothing = db.Column(db.Float, default=0)  # 子供の衣服費
    child_medical = db.Column(db.Float, default=0)   # 子供の医療費
    child_other = db.Column(db.Float, default=0)     # 子供のその他費用
    
    # その他
    transport = db.Column(db.Float, default=0)
    entertainment = db.Column(db.Float, default=0)
    pet_costs = db.Column(db.Float, default=0)
    other_expenses = db.Column(db.Float, default=0)
    
    monthly_total_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 教育費統合管理用の新しいモデル
class EducationPlans(db.Model):
    __tablename__ = 'education_plans'
    id = db.Column(db.Integer, primary_key=True)  # 統合ID
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
    __tablename__ = 'education_expenses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    education_plan_id = db.Column(db.Integer, db.ForeignKey('education_plans.id'), nullable=False)  # 統合IDへの参照
    
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    child_name = db.Column(db.String(100), nullable=False)
    child_birth_date = db.Column(db.Date, nullable=False)
    
    # 教育段階の種類（どの段階か）
    stage = db.Column(db.String(20), nullable=False)  # 'kindergarten', 'elementary', 'junior', 'high', 'college'
    stage_type = db.Column(db.String(50), nullable=False)  # 具体的なタイプ
    
    monthly_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 統合計画への関係
    education_plan = db.relationship('EducationPlans', backref='expenses')

class HousingExpenses(db.Model):
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
    is_recurring = db.Column(db.Boolean, default=False)  # 繰り返しかどうか
    recurrence_interval = db.Column(db.Integer, default=1)  # 繰り返し間隔（年）
    recurrence_count = db.Column(db.Integer, default=1)  # 繰り返し回数（0=無制限）
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Income Models
class SalaryIncomes(db.Model):
    __tablename__ = 'salary_incomes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    monthly_amount = db.Column(db.Float, nullable=False)
    annual_bonus = db.Column(db.Float, default=0)  # 年間ボーナス額
    annual_amount = db.Column(db.Float, nullable=False)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    
    # 昇給率（年率%）
    salary_increase_rate = db.Column(db.Float, default=3.0)  # デフォルト3%
    
    # 年間収入上限設定
    has_cap = db.Column(db.Boolean, default=False)  # 上限設定の有無
    annual_income_cap = db.Column(db.Float, default=0)  # 年間収入上限金額
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SidejobIncomes(db.Model):
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
    income_increase_rate = db.Column(db.Float, default=0.0)  # デフォルト0%（副業は昇給なしが一般的）
    
    # 年間収入上限設定
    has_cap = db.Column(db.Boolean, default=False)  # 上限設定の有無
    annual_income_cap = db.Column(db.Float, default=0)  # 年間収入上限金額
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class InvestmentIncomes(db.Model):
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
    annual_return_rate = db.Column(db.Float, default=5.0)  # デフォルト5%
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PensionIncomes(db.Model):
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

# Simulation Models
class LifeplanSimulations(db.Model):
    __tablename__ = 'lifeplan_simulations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    base_age = db.Column(db.Integer, nullable=False)
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LifeplanExpenseLinks(db.Model):
    __tablename__ = 'lifeplan_expense_links'
    id = db.Column(db.Integer, primary_key=True)
    lifeplan_id = db.Column(db.Integer, db.ForeignKey('lifeplan_simulations.id'), nullable=False)
    expense_type = db.Column(db.String(20), nullable=False)  # 'living', 'education', 'housing', 'insurance', 'event'
    expense_id = db.Column(db.Integer, nullable=False)

class LifeplanIncomeLinks(db.Model):
    __tablename__ = 'lifeplan_income_links'
    id = db.Column(db.Integer, primary_key=True)
    lifeplan_id = db.Column(db.Integer, db.ForeignKey('lifeplan_simulations.id'), nullable=False)
    income_type = db.Column(db.String(20), nullable=False)  # 'salary', 'sidejob', 'investment', 'pension', 'other'
    income_id = db.Column(db.Integer, nullable=False)

class HouseholdBook(db.Model):
    __tablename__ = 'household_books'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # 家計簿名
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    entries = db.relationship('HouseholdEntry', backref='household_book', lazy=True, cascade='all, delete-orphan')

class ExpenseCategory(db.Model):
    __tablename__ = 'expense_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    icon = db.Column(db.String(30), default='category')  # Material Icons名
    color = db.Column(db.String(7), default='#666666')  # HEXカラー
    is_default = db.Column(db.Boolean, default=True)  # デフォルトカテゴリかどうか
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class IncomeCategory(db.Model):
    __tablename__ = 'income_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    icon = db.Column(db.String(30), default='attach_money')  # Material Icons名
    color = db.Column(db.String(7), default='#4CAF50')  # HEXカラー
    is_default = db.Column(db.Boolean, default=True)  # デフォルトカテゴリかどうか
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class HouseholdEntry(db.Model):
    __tablename__ = 'household_entries'
    id = db.Column(db.Integer, primary_key=True)
    household_book_id = db.Column(db.Integer, db.ForeignKey('household_books.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    entry_type = db.Column(db.String(10), nullable=False)  # 'income' or 'expense'
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    
    # カテゴリ
    expense_category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'), nullable=True)
    income_category_id = db.Column(db.Integer, db.ForeignKey('income_categories.id'), nullable=True)
    
    # 日付
    entry_date = db.Column(db.Date, nullable=False, default=date.today)
    
    # メタデータ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    expense_category = db.relationship('ExpenseCategory', backref='entries')
    income_category = db.relationship('IncomeCategory', backref='entries')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Education Cost Calculator
def calculate_education_costs(child_birth_date, kindergarten_type, elementary_type, junior_type, high_type, college_type):
    """
    教育費を自動計算する関数
    日本の平均的な教育費に基づいて計算
    """
    costs = {
        'kindergarten_monthly': 0,
        'elementary_monthly': 0,
        'junior_monthly': 0,
        'high_monthly': 0,
        'college_monthly': 0,
        'kindergarten_start_year': 0,
        'kindergarten_end_year': 0,
        'elementary_start_year': 0,
        'elementary_end_year': 0,
        'junior_start_year': 0,
        'junior_end_year': 0,
        'high_start_year': 0,
        'high_end_year': 0,
        'college_start_year': 0,
        'college_end_year': 0
    }
    
    birth_year = child_birth_date.year
    
    # 幼稚園・保育園（3-5歳）
    if kindergarten_type == KindergartenType.PUBLIC:
        costs['kindergarten_monthly'] = 22000  # 公立幼稚園
    elif kindergarten_type == KindergartenType.PRIVATE:
        costs['kindergarten_monthly'] = 48000  # 私立幼稚園
    
    if kindergarten_type != KindergartenType.NONE:
        costs['kindergarten_start_year'] = birth_year + 3
        costs['kindergarten_end_year'] = birth_year + 5
    
    # 小学校（6-11歳）
    if elementary_type == ElementaryType.PUBLIC:
        costs['elementary_monthly'] = 27000  # 公立小学校
    elif elementary_type == ElementaryType.PRIVATE:
        costs['elementary_monthly'] = 130000  # 私立小学校
    
    costs['elementary_start_year'] = birth_year + 6
    costs['elementary_end_year'] = birth_year + 11
    
    # 中学校（12-14歳）
    if junior_type == JuniorType.PUBLIC:
        costs['junior_monthly'] = 40000  # 公立中学校
    elif junior_type == JuniorType.PRIVATE:
        costs['junior_monthly'] = 110000  # 私立中学校
    
    costs['junior_start_year'] = birth_year + 12
    costs['junior_end_year'] = birth_year + 14
    
    # 高校（15-17歳）
    if high_type == HighType.PUBLIC:
        costs['high_monthly'] = 35000  # 公立高校
    elif high_type == HighType.PRIVATE:
        costs['high_monthly'] = 70000  # 私立高校
    
    costs['high_start_year'] = birth_year + 15
    costs['high_end_year'] = birth_year + 17
    
    # 大学・専門学校（18-21歳）
    if college_type == CollegeType.NATIONAL:
        costs['college_monthly'] = 45000  # 国公立大学
        costs['college_start_year'] = birth_year + 18
        costs['college_end_year'] = birth_year + 21
    elif college_type == CollegeType.PRIVATE_LIBERAL:
        costs['college_monthly'] = 75000  # 私立文系
        costs['college_start_year'] = birth_year + 18
        costs['college_end_year'] = birth_year + 21
    elif college_type == CollegeType.PRIVATE_SCIENCE:
        costs['college_monthly'] = 95000  # 私立理系
        costs['college_start_year'] = birth_year + 18
        costs['college_end_year'] = birth_year + 21
    elif college_type == CollegeType.JUNIOR_COLLEGE:
        costs['college_monthly'] = 60000  # 短期大学
        costs['college_start_year'] = birth_year + 18
        costs['college_end_year'] = birth_year + 19
    elif college_type == CollegeType.VOCATIONAL:
        costs['college_monthly'] = 80000  # 専門学校
        costs['college_start_year'] = birth_year + 18
        costs['college_end_year'] = birth_year + 19
    
    return costs

# Mortgage Calculator
def calculate_mortgage_payment(loan_amount, interest_rate, term_years, repayment_method):
    """
    住宅ローンの月額返済額を計算する関数
    """
    if loan_amount <= 0 or interest_rate <= 0 or term_years <= 0:
        return 0
    
    monthly_rate = interest_rate / 100 / 12
    num_payments = term_years * 12
    
    if repayment_method == RepaymentMethod.EQUAL_PAYMENT:
        # 元利均等返済
        if monthly_rate == 0:
            return loan_amount / num_payments
        else:
            monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** num_payments) / ((1 + monthly_rate) ** num_payments - 1)
            return monthly_payment
    else:
        # 元金均等返済（初回の月額返済額を返す）
        principal_payment = loan_amount / num_payments
        interest_payment = loan_amount * monthly_rate
        return principal_payment + interest_payment

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = str(data.get('password'))  # 文字列に変換
        
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'message': 'ユーザー名が既に存在します'})
        
        user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '登録が完了しました'})
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = str(data.get('password'))  # 文字列に変換
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return jsonify({'success': True, 'message': 'ログインしました'})
        else:
            return jsonify({'success': False, 'message': 'ユーザー名またはパスワードが間違っています'})
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/expenses')
@login_required
def expenses():
    return render_template('expenses.html')

@app.route('/expenses/incomes')
@login_required
def expenses_incomes():
    return render_template('expenses_incomes.html')

@app.route('/expenses/living')
@login_required
def expenses_living():
    return render_template('expenses/living.html')

@app.route('/expenses/living/new')
@login_required
def expenses_living_new():
    return render_template('expenses/living_form.html', expense_id=None)

@app.route('/expenses/living/edit/<int:expense_id>')
@login_required
def expenses_living_edit(expense_id):
    return render_template('expenses/living_form.html', expense_id=expense_id)

@app.route('/expenses/education')
@login_required
def expenses_education():
    return render_template('expenses/education.html')

@app.route('/expenses/education/new')
@login_required
def expenses_education_new():
    return render_template('expenses/education_form.html', expense_id=None)

@app.route('/expenses/education/edit/<int:expense_id>')
@login_required
def expenses_education_edit(expense_id):
    return render_template('expenses/education_form.html', expense_id=expense_id)

@app.route('/expenses/housing')
@login_required
def expenses_housing():
    return render_template('expenses/housing.html')

@app.route('/expenses/housing/new')
@login_required
def expenses_housing_new():
    return render_template('expenses/housing_form.html', expense_id=None)

@app.route('/expenses/housing/edit/<int:expense_id>')
@login_required
def expenses_housing_edit(expense_id):
    return render_template('expenses/housing_form.html', expense_id=expense_id)

@app.route('/expenses/insurance')
@login_required
def expenses_insurance():
    return render_template('expenses/insurance.html')

@app.route('/expenses/insurance/new')
@login_required
def expenses_insurance_new():
    return render_template('expenses/insurance_form.html', expense_id=None)

@app.route('/expenses/insurance/edit/<int:expense_id>')
@login_required
def expenses_insurance_edit(expense_id):
    return render_template('expenses/insurance_form.html', expense_id=expense_id)

@app.route('/expenses/events')
@login_required
def expenses_events():
    return render_template('expenses/events.html')

@app.route('/expenses/events/new')
@login_required
def expenses_events_new():
    return render_template('expenses/events_form.html', expense_id=None)

@app.route('/expenses/events/edit/<int:expense_id>')
@login_required
def expenses_events_edit(expense_id):
    return render_template('expenses/events_form.html', expense_id=expense_id)

@app.route('/incomes')
@login_required
def incomes():
    return render_template('incomes.html')

@app.route('/incomes/salary')
@login_required
def incomes_salary():
    return render_template('incomes/salary.html')

@app.route('/incomes/salary/new')
@login_required
def incomes_salary_new():
    return render_template('incomes/salary_form.html', income_id=None)

@app.route('/incomes/salary/edit/<int:income_id>')
@login_required
def incomes_salary_edit(income_id):
    return render_template('incomes/salary_form.html', income_id=income_id)

@app.route('/incomes/sidejob')
@login_required
def incomes_sidejob():
    return render_template('incomes/sidejob.html')

@app.route('/incomes/sidejob/new')
@login_required
def incomes_sidejob_new():
    return render_template('incomes/sidejob_form.html', income_id=None)

@app.route('/incomes/sidejob/edit/<int:income_id>')
@login_required
def incomes_sidejob_edit(income_id):
    return render_template('incomes/sidejob_form.html', income_id=income_id)

@app.route('/incomes/investment')
@login_required
def incomes_investment():
    return render_template('incomes/investment.html')

@app.route('/incomes/investment/new')
@login_required
def incomes_investment_new():
    return render_template('incomes/investment_form.html', income_id=None)

@app.route('/incomes/investment/edit/<int:income_id>')
@login_required
def incomes_investment_edit(income_id):
    return render_template('incomes/investment_form.html', income_id=income_id)

@app.route('/incomes/pension')
@login_required
def incomes_pension():
    return render_template('incomes/pension.html')

@app.route('/incomes/pension/new')
@login_required
def incomes_pension_new():
    return render_template('incomes/pension_form.html', income_id=None)

@app.route('/incomes/pension/edit/<int:income_id>')
@login_required
def incomes_pension_edit(income_id):
    return render_template('incomes/pension_form.html', income_id=income_id)

@app.route('/incomes/other')
@login_required
def incomes_other():
    return render_template('incomes/other.html')

@app.route('/incomes/other/new')
@login_required
def incomes_other_new():
    return render_template('incomes/other_form.html', income_id=None)

@app.route('/incomes/other/edit/<int:income_id>')
@login_required
def incomes_other_edit(income_id):
    return render_template('incomes/other_form.html', income_id=income_id)

@app.route('/simulation')
@login_required
def simulation():
    return render_template('simulation.html')

@app.route('/simulation/create')
@login_required
def simulation_create():
    return render_template('simulation_create.html')

@app.route('/simulation/edit/<int:plan_id>')
@login_required
def simulation_edit(plan_id):
    return render_template('simulation_edit.html')

@app.route('/simulation/run/<int:plan_id>')
@login_required
def simulation_run(plan_id):
    return render_template('simulation_run.html')

@app.route('/household-menu')
@login_required
def household_menu():
    """家計簿メニュー画面"""
    # 直近の家計簿エントリを10件取得
    recent_entries = db.session.query(HouseholdEntry)\
        .join(HouseholdBook)\
        .filter(HouseholdBook.user_id == current_user.id)\
        .order_by(HouseholdEntry.entry_date.desc(), HouseholdEntry.created_at.desc())\
        .limit(10).all()
    
    # 今月の統計を計算
    today = date.today()
    current_month_entries = db.session.query(HouseholdEntry)\
        .join(HouseholdBook)\
        .filter(
            HouseholdBook.user_id == current_user.id,
            HouseholdBook.year == today.year,
            HouseholdBook.month == today.month
        ).all()
    
    # カテゴリ別集計
    category_summary = {}
    total_income = 0
    total_expense = 0
    
    for entry in current_month_entries:
        if entry.entry_type == 'income':
            total_income += entry.amount
            if entry.income_category:
                category_name = entry.income_category.name
                if category_name not in category_summary:
                    category_summary[category_name] = {
                        'type': 'income',
                        'amount': 0,
                        'icon': entry.income_category.icon,
                        'color': entry.income_category.color
                    }
                category_summary[category_name]['amount'] += entry.amount
        else:
            total_expense += entry.amount
            if entry.expense_category:
                category_name = entry.expense_category.name
                if category_name not in category_summary:
                    category_summary[category_name] = {
                        'type': 'expense',
                        'amount': 0,
                        'icon': entry.expense_category.icon,
                        'color': entry.expense_category.color
                    }
                category_summary[category_name]['amount'] += entry.amount
    
    balance = total_income - total_expense
    
    return render_template('household_menu.html', 
                         recent_entries=recent_entries,
                         category_summary=category_summary,
                         total_income=total_income,
                         total_expense=total_expense,
                         balance=balance,
                         current_month=today.month,
                         current_year=today.year)

@app.route('/household-book')
@login_required
def household_book():
    return render_template('household_book.html')

@app.route('/household-book-dev')
@login_required
def household_book_dev():
    return render_template('household_book_dev.html')

@app.route('/mypage')
@login_required
def mypage():
    return render_template('mypage.html')

# 新しい家計簿機能のルーティング
@app.route('/household-books')
@login_required
def household_books():
    """家計簿一覧・新規作成ページ"""
    # 直近の家計簿を取得
    recent_books = HouseholdBook.query.filter_by(user_id=current_user.id)\
        .order_by(HouseholdBook.year.desc(), HouseholdBook.month.desc())\
        .limit(5).all()
    
    return render_template('household_books.html', recent_books=recent_books)

@app.route('/household-books/<int:year>/<int:month>')
@login_required
def household_book_monthly(year, month):
    """月次家計簿ページ"""
    # 指定年月の家計簿を取得または作成
    household_book = HouseholdBook.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()
    
    if not household_book:
        # 家計簿が存在しない場合は作成
        household_book = HouseholdBook(
            user_id=current_user.id,
            name=f"{year}年{month}月の家計簿",
            year=year,
            month=month
        )
        db.session.add(household_book)
        db.session.commit()
    
    # エントリーを取得
    entries = HouseholdEntry.query.filter_by(household_book_id=household_book.id)\
        .order_by(HouseholdEntry.entry_date.desc()).all()
    
    # カテゴリを取得
    expense_categories = ExpenseCategory.query.all()
    income_categories = IncomeCategory.query.all()
    
    # 月次統計を計算
    total_income = sum(entry.amount for entry in entries if entry.entry_type == 'income')
    total_expense = sum(entry.amount for entry in entries if entry.entry_type == 'expense')
    balance = total_income - total_expense
    
    return render_template('household_book_monthly.html', 
                         household_book=household_book,
                         entries=entries,
                         expense_categories=expense_categories,
                         income_categories=income_categories,
                         total_income=total_income,
                         total_expense=total_expense,
                         balance=balance)

# API Routes for Expenses
@app.route('/api/living-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_living_expenses():
    if request.method == 'POST':
        data = request.get_json()
        
        # Calculate monthly total with proper type conversion
        monthly_total = sum([
            float(data.get('food_home', 0) or 0),
            float(data.get('food_outside', 0) or 0),
            float(data.get('utility_electricity', 0) or 0),
            float(data.get('utility_gas', 0) or 0),
            float(data.get('utility_water', 0) or 0),
            float(data.get('subscription_services', 0) or 0),
            float(data.get('internet', 0) or 0),
            float(data.get('phone', 0) or 0),
            float(data.get('household_goods', 0) or 0),
            float(data.get('hygiene', 0) or 0),
            float(data.get('clothing', 0) or 0),
            float(data.get('beauty', 0) or 0),
            float(data.get('child_food', 0) or 0),
            float(data.get('child_clothing', 0) or 0),
            float(data.get('child_medical', 0) or 0),
            float(data.get('child_other', 0) or 0),
            float(data.get('transport', 0) or 0),
            float(data.get('entertainment', 0) or 0),
            float(data.get('pet_costs', 0) or 0),
            float(data.get('other_expenses', 0) or 0)
        ])
        
        expense = LivingExpenses(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            inflation_rate=float(data.get('inflation_rate', 2.0)),
            food_home=float(data.get('food_home', 0) or 0),
            food_outside=float(data.get('food_outside', 0) or 0),
            utility_electricity=float(data.get('utility_electricity', 0) or 0),
            utility_gas=float(data.get('utility_gas', 0) or 0),
            utility_water=float(data.get('utility_water', 0) or 0),
            subscription_services=float(data.get('subscription_services', 0) or 0),
            internet=float(data.get('internet', 0) or 0),
            phone=float(data.get('phone', 0) or 0),
            household_goods=float(data.get('household_goods', 0) or 0),
            hygiene=float(data.get('hygiene', 0) or 0),
            clothing=float(data.get('clothing', 0) or 0),
            beauty=float(data.get('beauty', 0) or 0),
            child_food=float(data.get('child_food', 0) or 0),
            child_clothing=float(data.get('child_clothing', 0) or 0),
            child_medical=float(data.get('child_medical', 0) or 0),
            child_other=float(data.get('child_other', 0) or 0),
            transport=float(data.get('transport', 0) or 0),
            entertainment=float(data.get('entertainment', 0) or 0),
            pet_costs=float(data.get('pet_costs', 0) or 0),
            other_expenses=float(data.get('other_expenses', 0) or 0),
            monthly_total_amount=monthly_total
        )
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '生活費を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        expense_id = data.get('id')
        
        if not expense_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        expense = LivingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
        if not expense:
            return jsonify({'success': False, 'message': '指定された生活費が見つかりません'}), 404
        
        # Calculate monthly total with proper type conversion
        monthly_total = sum([
            float(data.get('food_home', 0) or 0),
            float(data.get('food_outside', 0) or 0),
            float(data.get('utility_electricity', 0) or 0),
            float(data.get('utility_gas', 0) or 0),
            float(data.get('utility_water', 0) or 0),
            float(data.get('subscription_services', 0) or 0),
            float(data.get('internet', 0) or 0),
            float(data.get('phone', 0) or 0),
            float(data.get('household_goods', 0) or 0),
            float(data.get('hygiene', 0) or 0),
            float(data.get('clothing', 0) or 0),
            float(data.get('beauty', 0) or 0),
            float(data.get('child_food', 0) or 0),
            float(data.get('child_clothing', 0) or 0),
            float(data.get('child_medical', 0) or 0),
            float(data.get('child_other', 0) or 0),
            float(data.get('transport', 0) or 0),
            float(data.get('entertainment', 0) or 0),
            float(data.get('pet_costs', 0) or 0),
            float(data.get('other_expenses', 0) or 0)
        ])
        
        # Update expense data
        expense.name = data.get('name')
        expense.description = data.get('description')
        expense.start_year = int(data.get('start_year', 0))
        expense.end_year = int(data.get('end_year', 0))
        expense.inflation_rate = float(data.get('inflation_rate', 2.0))
        expense.food_home = float(data.get('food_home', 0) or 0)
        expense.food_outside = float(data.get('food_outside', 0) or 0)
        expense.utility_electricity = float(data.get('utility_electricity', 0) or 0)
        expense.utility_gas = float(data.get('utility_gas', 0) or 0)
        expense.utility_water = float(data.get('utility_water', 0) or 0)
        expense.subscription_services = float(data.get('subscription_services', 0) or 0)
        expense.internet = float(data.get('internet', 0) or 0)
        expense.phone = float(data.get('phone', 0) or 0)
        expense.household_goods = float(data.get('household_goods', 0) or 0)
        expense.hygiene = float(data.get('hygiene', 0) or 0)
        expense.clothing = float(data.get('clothing', 0) or 0)
        expense.beauty = float(data.get('beauty', 0) or 0)
        expense.child_food = float(data.get('child_food', 0) or 0)
        expense.child_clothing = float(data.get('child_clothing', 0) or 0)
        expense.child_medical = float(data.get('child_medical', 0) or 0)
        expense.child_other = float(data.get('child_other', 0) or 0)
        expense.transport = float(data.get('transport', 0) or 0)
        expense.entertainment = float(data.get('entertainment', 0) or 0)
        expense.pet_costs = float(data.get('pet_costs', 0) or 0)
        expense.other_expenses = float(data.get('other_expenses', 0) or 0)
        expense.monthly_total_amount = monthly_total
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '生活費を更新しました'})
    
    else:
        expenses = LivingExpenses.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': e.id,
            'name': e.name,
            'description': e.description,
            'start_year': e.start_year,
            'end_year': e.end_year,
            'inflation_rate': e.inflation_rate,
            'monthly_total_amount': e.monthly_total_amount,
            'food_home': e.food_home,
            'food_outside': e.food_outside,
            'utility_electricity': e.utility_electricity,
            'utility_gas': e.utility_gas,
            'utility_water': e.utility_water,
            'subscription_services': e.subscription_services,
            'internet': e.internet,
            'phone': e.phone,
            'household_goods': e.household_goods,
            'hygiene': e.hygiene,
            'clothing': e.clothing,
            'beauty': e.beauty,
            'child_food': e.child_food,
            'child_clothing': e.child_clothing,
            'child_medical': e.child_medical,
            'child_other': e.child_other,
            'transport': e.transport,
            'entertainment': e.entertainment,
            'pet_costs': e.pet_costs,
            'other_expenses': e.other_expenses
        } for e in expenses])

@app.route('/api/education-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_education_expenses():
    if request.method == 'POST':
        data = request.get_json()
        
        # 教育費統合管理用の教育プランを作成
        education_plan = EducationPlans(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            child_name=data.get('child_name'),
            child_birth_date=datetime.strptime(data.get('child_birth_date'), '%Y-%m-%d').date(),
            kindergarten_type=KindergartenType(data.get('kindergarten_type', 'NONE')),
            elementary_type=ElementaryType(data.get('elementary_type', 'PUBLIC')),
            junior_type=JuniorType(data.get('junior_type', 'PUBLIC')),
            high_type=HighType(data.get('high_type', 'PUBLIC')),
            college_type=CollegeType(data.get('college_type', 'NONE'))
        )
        
        db.session.add(education_plan)
        db.session.flush()  # IDを取得するため
        
        # カスタム費用を取得（万円→円に変換）
        custom_costs = {
            'kindergarten': float(data.get('kindergarten_cost', 0)) * 10000,
            'elementary': float(data.get('elementary_cost', 0)) * 10000,
            'junior': float(data.get('junior_cost', 0)) * 10000,
            'high': float(data.get('high_cost', 0)) * 10000,
            'college': float(data.get('college_cost', 0)) * 10000
        }
        
        # 教育費を計算（期間情報取得用）
        costs = calculate_education_costs(
            education_plan.child_birth_date,
            education_plan.kindergarten_type,
            education_plan.elementary_type,
            education_plan.junior_type,
            education_plan.high_type,
            education_plan.college_type
        )
        
        # 各教育段階のレコードを作成（カスタム費用使用）
        stages = [
            ('kindergarten', education_plan.kindergarten_type.value, custom_costs['kindergarten'], costs['kindergarten_start_year'], costs['kindergarten_end_year'], 3),
            ('elementary', education_plan.elementary_type.value, custom_costs['elementary'], costs['elementary_start_year'], costs['elementary_end_year'], 6),
            ('junior', education_plan.junior_type.value, custom_costs['junior'], costs['junior_start_year'], costs['junior_end_year'], 3),
            ('high', education_plan.high_type.value, custom_costs['high'], costs['high_start_year'], costs['high_end_year'], 3),
            ('college', education_plan.college_type.value, custom_costs['college'], costs['college_start_year'], costs['college_end_year'], 4 if education_plan.college_type.value in ['国公立大学', '私立文系', '私立理系'] else 2)
        ]
        
        created_expenses = []
        for stage, stage_type, total_cost, start_year, end_year, years in stages:
            # 費用が0または期間が無効な場合はスキップ
            if total_cost <= 0 or start_year <= 0 or end_year <= 0:
                continue
                
            # "進学しない"や"未就園"の場合もスキップ
            if stage_type in ['進学しない', '未就園']:
                continue
            
            # 月額を計算
            monthly_amount = total_cost / (years * 12)
            
            expense = EducationExpenses(
                user_id=current_user.id,
                education_plan_id=education_plan.id,
                name=f"{education_plan.child_name}の{stage_type}",
                description=f"{education_plan.child_name}の{stage_type}にかかる費用",
                start_year=start_year,
                end_year=end_year,
                child_name=education_plan.child_name,
                child_birth_date=education_plan.child_birth_date,
                stage=stage,
                stage_type=stage_type,
                monthly_amount=monthly_amount
            )
            db.session.add(expense)
            created_expenses.append(expense)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '教育費を登録しました',
            'updated_count': len(created_expenses)
        })
    
    elif request.method == 'PUT':
        # 統合管理では編集は無効化
        return jsonify({'success': False, 'message': '教育費の編集は削除後、再登録してください'}), 400
    
    else:
        # 新しい統合表示：教育プラン毎にグループ化して表示
        education_plans = EducationPlans.query.filter_by(user_id=current_user.id).all()
        
        result = []
        for plan in education_plans:
            # 関連する教育費を取得
            expenses = EducationExpenses.query.filter_by(education_plan_id=plan.id).all()
            
            total_monthly = sum(e.monthly_amount for e in expenses)
            start_year = min(e.start_year for e in expenses) if expenses else None
            end_year = max(e.end_year for e in expenses) if expenses else None
            
            # 統合された結果を返す
            unified_result = {
                'id': plan.id,  # 統合削除時に使用
                'unified_id': f"{plan.child_name}_{plan.child_birth_date.isoformat()}",
                'name': f"{plan.child_name}の教育費",
                'description': f"{plan.child_name}の全教育段階費用",
                'start_year': start_year,
                'end_year': end_year,
                'child_name': plan.child_name,
                'child_birth_date': plan.child_birth_date.isoformat(),
                'monthly_total_amount': total_monthly,
                'expense_ids': [e.id for e in expenses],
                'stages': []
            }
            
            # 各段階の詳細情報
            for expense in expenses:
                stage_info = {
                    'id': expense.id,
                    'name': expense.name,
                    'start_year': expense.start_year,
                    'end_year': expense.end_year,
                    'monthly_amount': expense.monthly_amount,
                    'stage': expense.stage,
                    'stage_type': expense.stage_type
                }
                unified_result['stages'].append(stage_info)
            
            result.append(unified_result)
        
        return jsonify(result)

# 家計簿API
@app.route('/api/household-books', methods=['GET', 'POST'])
@login_required
def api_household_books():
    if request.method == 'GET':
        # 家計簿一覧を取得
        books = HouseholdBook.query.filter_by(user_id=current_user.id)\
            .order_by(HouseholdBook.year.desc(), HouseholdBook.month.desc()).all()
        
        return jsonify([{
            'id': book.id,
            'name': book.name,
            'year': book.year,
            'month': book.month,
            'description': book.description,
            'created_at': book.created_at.isoformat(),
            'updated_at': book.updated_at.isoformat()
        } for book in books])
    
    elif request.method == 'POST':
        # 新しい家計簿を作成
        try:
            data = request.get_json()
            year = data.get('year')
            month = data.get('month')
            name = data.get('name', f"{year}年{month}月の家計簿")
            description = data.get('description', '')
            
            # 既存チェック
            existing_book = HouseholdBook.query.filter_by(
                user_id=current_user.id, year=year, month=month
            ).first()
            
            if existing_book:
                return jsonify({'error': 'この年月の家計簿は既に存在します'}), 400
            
            # 新規作成
            new_book = HouseholdBook(
                user_id=current_user.id,
                name=name,
                year=year,
                month=month,
                description=description
            )
            
            db.session.add(new_book)
            db.session.commit()
            
            return jsonify({
                'id': new_book.id,
                'name': new_book.name,
                'year': new_book.year,
                'month': new_book.month,
                'description': new_book.description,
                'message': '家計簿を作成しました'
            }), 201
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'家計簿作成エラー: {str(e)}')
            return jsonify({'error': '家計簿作成中にエラーが発生しました'}), 500

@app.route('/api/household-entries', methods=['GET', 'POST'])
@login_required
def api_household_entries():
    if request.method == 'GET':
        # エントリー一覧を取得
        household_book_id = request.args.get('household_book_id')
        if not household_book_id:
            return jsonify({'error': '家計簿IDが必要です'}), 400
        
        entries = HouseholdEntry.query.filter_by(
            household_book_id=household_book_id,
            user_id=current_user.id
        ).order_by(HouseholdEntry.entry_date.desc()).all()
        
        return jsonify([{
            'id': entry.id,
            'entry_type': entry.entry_type,
            'amount': entry.amount,
            'description': entry.description,
            'entry_date': entry.entry_date.isoformat(),
            'expense_category': {
                'id': entry.expense_category.id,
                'name': entry.expense_category.name,
                'icon': entry.expense_category.icon,
                'color': entry.expense_category.color
            } if entry.expense_category else None,
            'income_category': {
                'id': entry.income_category.id,
                'name': entry.income_category.name,
                'icon': entry.income_category.icon,
                'color': entry.income_category.color
            } if entry.income_category else None,
            'created_at': entry.created_at.isoformat()
        } for entry in entries])
    
    elif request.method == 'POST':
        # 新しいエントリーを作成
        try:
            data = request.get_json()
            
            entry = HouseholdEntry(
                household_book_id=data['household_book_id'],
                user_id=current_user.id,
                entry_type=data['entry_type'],
                amount=float(data['amount']),
                description=data.get('description', ''),
                entry_date=datetime.strptime(data['entry_date'], '%Y-%m-%d').date(),
                expense_category_id=data.get('expense_category_id'),
                income_category_id=data.get('income_category_id')
            )
            
            db.session.add(entry)
            db.session.commit()
            
            return jsonify({
                'id': entry.id,
                'message': 'エントリーを追加しました'
            }), 201
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'エントリー作成エラー: {str(e)}')
            return jsonify({'error': 'エントリー作成中にエラーが発生しました'}), 500

@app.route('/api/household-entries/<int:entry_id>', methods=['PUT', 'DELETE'])
@login_required
def api_household_entry_detail(entry_id):
    entry = HouseholdEntry.query.filter_by(id=entry_id, user_id=current_user.id).first()
    if not entry:
        return jsonify({'error': 'エントリーが見つかりません'}), 404
    
    if request.method == 'PUT':
        # エントリーを更新
        try:
            data = request.get_json()
            
            entry.entry_type = data.get('entry_type', entry.entry_type)
            entry.amount = float(data.get('amount', entry.amount))
            entry.description = data.get('description', entry.description)
            entry.entry_date = datetime.strptime(data['entry_date'], '%Y-%m-%d').date() if 'entry_date' in data else entry.entry_date
            entry.expense_category_id = data.get('expense_category_id')
            entry.income_category_id = data.get('income_category_id')
            entry.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({'message': 'エントリーを更新しました'})
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'エントリー更新エラー: {str(e)}')
            return jsonify({'error': 'エントリー更新中にエラーが発生しました'}), 500
    
    elif request.method == 'DELETE':
        # エントリーを削除
        try:
            db.session.delete(entry)
            db.session.commit()
            
            return jsonify({'message': 'エントリーを削除しました'})
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'エントリー削除エラー: {str(e)}')
            return jsonify({'error': 'エントリー削除中にエラーが発生しました'}), 500

@app.route('/api/expense-categories', methods=['GET'])
@login_required
def api_expense_categories():
    categories = ExpenseCategory.query.all()
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'icon': cat.icon,
        'color': cat.color,
        'is_default': cat.is_default
    } for cat in categories])

@app.route('/api/income-categories', methods=['GET'])
@login_required
def api_income_categories():
    categories = IncomeCategory.query.all()
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'icon': cat.icon,
        'color': cat.color,
        'is_default': cat.is_default
    } for cat in categories])

@app.route('/api/housing-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_housing_expenses():
    if request.method == 'POST':
        data = request.get_json()
        
        residence_type = ResidenceType(data.get('residence_type'))
        
        # Calculate mortgage if applicable
        mortgage_monthly = 0
        if residence_type == ResidenceType.OWNED_WITH_LOAN:
            loan_amount = float(data.get('purchase_price', 0) or 0) - float(data.get('down_payment', 0) or 0)
            mortgage_monthly = calculate_mortgage_payment(
                loan_amount,
                float(data.get('loan_interest_rate', 0) or 0),
                int(data.get('loan_term_years', 0) or 0),
                RepaymentMethod(data.get('repayment_method', 'EQUAL_PAYMENT'))
            )
        
        # Calculate monthly total
        if residence_type == ResidenceType.RENTAL:
            monthly_total = float(data.get('rent_monthly', 0) or 0)
        else:
            monthly_total = sum([
                mortgage_monthly,
                float(data.get('property_tax_monthly', 0) or 0),
                float(data.get('management_fee_monthly', 0) or 0),
                float(data.get('repair_reserve_monthly', 0) or 0),
                float(data.get('fire_insurance_monthly', 0) or 0)
            ])
        
        expense = HousingExpenses(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            residence_type=residence_type,
            rent_monthly=float(data.get('rent_monthly', 0) or 0),
            mortgage_monthly=mortgage_monthly,
            property_tax_monthly=float(data.get('property_tax_monthly', 0) or 0),
            management_fee_monthly=float(data.get('management_fee_monthly', 0) or 0),
            repair_reserve_monthly=float(data.get('repair_reserve_monthly', 0) or 0),
            fire_insurance_monthly=float(data.get('fire_insurance_monthly', 0) or 0),
            purchase_price=float(data.get('purchase_price', 0) or 0),
            down_payment=float(data.get('down_payment', 0) or 0),
            loan_interest_rate=float(data.get('loan_interest_rate', 0) or 0),
            loan_term_years=int(data.get('loan_term_years', 0) or 0),
            repayment_method=RepaymentMethod(data.get('repayment_method', 'EQUAL_PAYMENT')),
            monthly_total_amount=monthly_total
        )
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': '住居費を登録しました',
            'calculated_mortgage': mortgage_monthly
        })
    
    elif request.method == 'PUT':
        data = request.get_json()
        expense_id = data.get('id')
        
        if not expense_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        expense = HousingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
        if not expense:
            return jsonify({'success': False, 'message': '指定された住居費が見つかりません'}), 404
        
        residence_type = ResidenceType(data.get('residence_type'))
        
        # Calculate mortgage if applicable
        mortgage_monthly = 0
        if residence_type == ResidenceType.OWNED_WITH_LOAN:
            loan_amount = float(data.get('purchase_price', 0) or 0) - float(data.get('down_payment', 0) or 0)
            mortgage_monthly = calculate_mortgage_payment(
                loan_amount,
                float(data.get('loan_interest_rate', 0) or 0),
                int(data.get('loan_term_years', 0) or 0),
                RepaymentMethod(data.get('repayment_method', 'EQUAL_PAYMENT'))
            )
        
        # Calculate monthly total
        if residence_type == ResidenceType.RENTAL:
            monthly_total = float(data.get('rent_monthly', 0) or 0)
        else:
            monthly_total = sum([
                mortgage_monthly,
                float(data.get('property_tax_monthly', 0) or 0),
                float(data.get('management_fee_monthly', 0) or 0),
                float(data.get('repair_reserve_monthly', 0) or 0),
                float(data.get('fire_insurance_monthly', 0) or 0)
            ])
        
        # Update expense data
        expense.name = data.get('name')
        expense.description = data.get('description')
        expense.start_year = int(data.get('start_year', 0))
        expense.end_year = int(data.get('end_year', 0))
        expense.residence_type = residence_type
        expense.rent_monthly = float(data.get('rent_monthly', 0) or 0)
        expense.mortgage_monthly = mortgage_monthly
        expense.property_tax_monthly = float(data.get('property_tax_monthly', 0) or 0)
        expense.management_fee_monthly = float(data.get('management_fee_monthly', 0) or 0)
        expense.repair_reserve_monthly = float(data.get('repair_reserve_monthly', 0) or 0)
        expense.fire_insurance_monthly = float(data.get('fire_insurance_monthly', 0) or 0)
        expense.purchase_price = float(data.get('purchase_price', 0) or 0)
        expense.down_payment = float(data.get('down_payment', 0) or 0)
        expense.loan_interest_rate = float(data.get('loan_interest_rate', 0) or 0)
        expense.loan_term_years = int(data.get('loan_term_years', 0) or 0)
        expense.repayment_method = RepaymentMethod(data.get('repayment_method', 'EQUAL_PAYMENT'))
        expense.monthly_total_amount = monthly_total
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': '住居費を更新しました',
            'calculated_mortgage': mortgage_monthly
        })
    
    else:
        expenses = HousingExpenses.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': e.id,
            'name': e.name,
            'description': e.description,
            'start_year': e.start_year,
            'end_year': e.end_year,
            'residence_type': e.residence_type.value,
            'rent_monthly': e.rent_monthly,
            'mortgage_monthly': e.mortgage_monthly,
            'property_tax_monthly': e.property_tax_monthly,
            'management_fee_monthly': e.management_fee_monthly,
            'repair_reserve_monthly': e.repair_reserve_monthly,
            'fire_insurance_monthly': e.fire_insurance_monthly,
            'purchase_price': e.purchase_price,
            'down_payment': e.down_payment,
            'loan_interest_rate': e.loan_interest_rate,
            'loan_term_years': e.loan_term_years,
            'repayment_method': e.repayment_method.value,
            'monthly_total_amount': e.monthly_total_amount
        } for e in expenses])

@app.route('/api/housing-expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def api_delete_housing_expense(expense_id):
    expense = HousingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not expense:
        return jsonify({'success': False, 'message': '指定された住居費が見つかりません'}), 404
    
    db.session.delete(expense)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '住居費を削除しました'})

@app.route('/api/housing-expenses/<int:expense_id>/copy', methods=['POST'])
@login_required
def api_copy_housing_expense(expense_id):
    # 元のデータを取得
    original_expense = HousingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not original_expense:
        return jsonify({'success': False, 'message': '指定された住居費が見つかりません'}), 404
    
    # 新しいデータを作成（IDを除く）
    new_expense = HousingExpenses(
        user_id=current_user.id,
        name=f"{original_expense.name} - コピー",
        description=original_expense.description,
        start_year=original_expense.start_year,
        end_year=original_expense.end_year,
        residence_type=original_expense.residence_type,
        rent_monthly=original_expense.rent_monthly,
        mortgage_monthly=original_expense.mortgage_monthly,
        property_tax_monthly=original_expense.property_tax_monthly,
        management_fee_monthly=original_expense.management_fee_monthly,
        repair_reserve_monthly=original_expense.repair_reserve_monthly,
        fire_insurance_monthly=original_expense.fire_insurance_monthly,
        purchase_price=original_expense.purchase_price,
        down_payment=original_expense.down_payment,
        loan_interest_rate=original_expense.loan_interest_rate,
        loan_term_years=original_expense.loan_term_years,
        repayment_method=original_expense.repayment_method,
        monthly_total_amount=original_expense.monthly_total_amount
    )
    
    db.session.add(new_expense)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '住居費をコピーしました',
        'new_id': new_expense.id
    })

@app.route('/api/insurance-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_insurance_expenses():
    if request.method == 'POST':
        data = request.get_json()
        
        # Calculate monthly total with proper type conversion
        monthly_total = sum([
            float(data.get('medical_insurance', 0) or 0),
            float(data.get('cancer_insurance', 0) or 0),
            float(data.get('life_insurance', 0) or 0),
            float(data.get('income_protection', 0) or 0),
            float(data.get('accident_insurance', 0) or 0),
            float(data.get('liability_insurance', 0) or 0),
            float(data.get('fire_insurance', 0) or 0),
            float(data.get('long_term_care_insurance', 0) or 0),
            float(data.get('other_insurance', 0) or 0)
        ])
        
        expense = InsuranceExpenses(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            medical_insurance=float(data.get('medical_insurance', 0) or 0),
            cancer_insurance=float(data.get('cancer_insurance', 0) or 0),
            life_insurance=float(data.get('life_insurance', 0) or 0),
            income_protection=float(data.get('income_protection', 0) or 0),
            accident_insurance=float(data.get('accident_insurance', 0) or 0),
            liability_insurance=float(data.get('liability_insurance', 0) or 0),
            fire_insurance=float(data.get('fire_insurance', 0) or 0),
            long_term_care_insurance=float(data.get('long_term_care_insurance', 0) or 0),
            other_insurance=float(data.get('other_insurance', 0) or 0),
            insured_person=data.get('insured_person'),
            insurance_company=data.get('insurance_company'),
            insurance_term_years=int(data.get('insurance_term_years', 0) or 0),
            renew_type=data.get('renew_type'),
            monthly_total_amount=monthly_total
        )
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '保険費を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        expense_id = data.get('id')
        
        if not expense_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        expense = InsuranceExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
        if not expense:
            return jsonify({'success': False, 'message': '指定された保険が見つかりません'}), 404
        
        # Calculate monthly total with proper type conversion
        monthly_total = sum([
            float(data.get('medical_insurance', 0) or 0),
            float(data.get('cancer_insurance', 0) or 0),
            float(data.get('life_insurance', 0) or 0),
            float(data.get('income_protection', 0) or 0),
            float(data.get('accident_insurance', 0) or 0),
            float(data.get('liability_insurance', 0) or 0),
            float(data.get('fire_insurance', 0) or 0),
            float(data.get('long_term_care_insurance', 0) or 0),
            float(data.get('other_insurance', 0) or 0)
        ])
        
        # Update expense data
        expense.name = data.get('name')
        expense.description = data.get('description')
        expense.start_year = int(data.get('start_year', 0))
        expense.end_year = int(data.get('end_year', 0))
        expense.medical_insurance = float(data.get('medical_insurance', 0) or 0)
        expense.cancer_insurance = float(data.get('cancer_insurance', 0) or 0)
        expense.life_insurance = float(data.get('life_insurance', 0) or 0)
        expense.income_protection = float(data.get('income_protection', 0) or 0)
        expense.accident_insurance = float(data.get('accident_insurance', 0) or 0)
        expense.liability_insurance = float(data.get('liability_insurance', 0) or 0)
        expense.fire_insurance = float(data.get('fire_insurance', 0) or 0)
        expense.long_term_care_insurance = float(data.get('long_term_care_insurance', 0) or 0)
        expense.other_insurance = float(data.get('other_insurance', 0) or 0)
        expense.insured_person = data.get('insured_person')
        expense.insurance_company = data.get('insurance_company')
        expense.insurance_term_years = int(data.get('insurance_term_years', 0) or 0)
        expense.renew_type = data.get('renew_type')
        expense.monthly_total_amount = monthly_total
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '保険費を更新しました'})
    
    else:
        expenses = InsuranceExpenses.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': e.id,
            'name': e.name,
            'description': e.description,
            'start_year': e.start_year,
            'end_year': e.end_year,
            'monthly_total_amount': e.monthly_total_amount,
            'medical_insurance': e.medical_insurance,
            'cancer_insurance': e.cancer_insurance,
            'life_insurance': e.life_insurance,
            'income_protection': e.income_protection,
            'accident_insurance': e.accident_insurance,
            'liability_insurance': e.liability_insurance,
            'fire_insurance': e.fire_insurance,
            'long_term_care_insurance': e.long_term_care_insurance,
            'other_insurance': e.other_insurance,
            'insured_person': e.insured_person,
            'insurance_company': e.insurance_company,
            'insurance_term_years': e.insurance_term_years,
            'renew_type': e.renew_type
        } for e in expenses])

@app.route('/api/event-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_event_expenses():
    if request.method == 'POST':
        data = request.get_json()
        
        category = EventCategory(data.get('category'))
        
        expense = EventExpenses(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            category=category,
            amount=float(data.get('amount', 0) or 0),
            is_recurring=bool(data.get('is_recurring', False)),
            recurrence_interval=int(data.get('recurrence_interval', 1)),
            recurrence_count=int(data.get('recurrence_count', 1))
        )
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'イベント費用を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        expense_id = data.get('id')
        
        if not expense_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        expense = EventExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
        if not expense:
            return jsonify({'success': False, 'message': '指定されたイベントが見つかりません'}), 404
        
        category = EventCategory(data.get('category'))
        
        # Update expense data
        expense.name = data.get('name')
        expense.description = data.get('description')
        expense.start_year = int(data.get('start_year', 0))
        expense.end_year = int(data.get('end_year', 0))
        expense.category = category
        expense.amount = float(data.get('amount', 0) or 0)
        expense.is_recurring = bool(data.get('is_recurring', False))
        expense.recurrence_interval = int(data.get('recurrence_interval', 1))
        expense.recurrence_count = int(data.get('recurrence_count', 1))
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'イベント費用を更新しました'})
    
    else:
        expenses = EventExpenses.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': e.id,
            'name': e.name,
            'description': e.description,
            'start_year': e.start_year,
            'end_year': e.end_year,
            'category': e.category.value,
            'amount': e.amount,
            'is_recurring': e.is_recurring,
            'recurrence_interval': e.recurrence_interval,
            'recurrence_count': e.recurrence_count
        } for e in expenses])

@app.route('/api/sidejob-incomes', methods=['GET', 'POST', 'PUT'])
@login_required
def api_sidejob_incomes():
    if request.method == 'POST':
        data = request.get_json()
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        income = SidejobIncomes(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            monthly_amount=monthly_amount,
            annual_amount=monthly_amount * 12,
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            income_increase_rate=float(data.get('income_increase_rate', 0.0)),
            has_cap=bool(data.get('has_cap', False)),
            annual_income_cap=float(data.get('annual_income_cap', 0) or 0)
        )
        
        db.session.add(income)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '副業収入を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        income_id = data.get('id')
        
        if not income_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        income = SidejobIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
        if not income:
            return jsonify({'success': False, 'message': '指定された副業収入が見つかりません'}), 404
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        
        # Update income data
        income.name = data.get('name')
        income.description = data.get('description')
        income.monthly_amount = monthly_amount
        income.annual_amount = monthly_amount * 12
        income.start_year = int(data.get('start_year', 0))
        income.end_year = int(data.get('end_year', 0))
        income.income_increase_rate = float(data.get('income_increase_rate', 0.0))
        income.has_cap = bool(data.get('has_cap', False))
        income.annual_income_cap = float(data.get('annual_income_cap', 0) or 0)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '副業収入を更新しました'})
    
    else:
        incomes = SidejobIncomes.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': i.id,
            'name': i.name,
            'description': i.description,
            'monthly_amount': i.monthly_amount,
            'annual_amount': i.annual_amount,
            'start_year': i.start_year,
            'end_year': i.end_year,
            'income_increase_rate': i.income_increase_rate,
            'has_cap': i.has_cap,
            'annual_income_cap': i.annual_income_cap
        } for i in incomes])

@app.route('/api/investment-incomes', methods=['GET', 'POST', 'PUT'])
@login_required
def api_investment_incomes():
    if request.method == 'POST':
        data = request.get_json()
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        income = InvestmentIncomes(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            monthly_amount=monthly_amount,
            annual_amount=monthly_amount * 12,
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            annual_return_rate=float(data.get('annual_return_rate', 5.0))
        )
        
        db.session.add(income)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '投資収入を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        income_id = data.get('id')
        
        income = InvestmentIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
        if not income:
            return jsonify({'success': False, 'message': '投資収入が見つかりません'})
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        
        # Update income data
        income.name = data.get('name')
        income.description = data.get('description')
        income.monthly_amount = monthly_amount
        income.annual_amount = monthly_amount * 12
        income.start_year = int(data.get('start_year', 0))
        income.end_year = int(data.get('end_year', 0))
        income.annual_return_rate = float(data.get('annual_return_rate', 5.0))
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '投資収入を更新しました'})
    
    else:
        incomes = InvestmentIncomes.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': i.id,
            'name': i.name,
            'description': i.description,
            'monthly_amount': i.monthly_amount,
            'annual_amount': i.annual_amount,
            'start_year': i.start_year,
            'end_year': i.end_year,
            'annual_return_rate': i.annual_return_rate
        } for i in incomes])

@app.route('/api/pension-incomes', methods=['GET', 'POST'])
@login_required
def api_pension_incomes():
    if request.method == 'POST':
        data = request.get_json()
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        income = PensionIncomes(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            monthly_amount=monthly_amount,
            annual_amount=monthly_amount * 12,
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0))
        )
        
        db.session.add(income)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '年金収入を登録しました'})
    
    else:
        incomes = PensionIncomes.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': i.id,
            'name': i.name,
            'description': i.description,
            'monthly_amount': i.monthly_amount,
            'annual_amount': i.annual_amount,
            'start_year': i.start_year,
            'end_year': i.end_year
        } for i in incomes])

@app.route('/api/other-incomes', methods=['GET', 'POST'])
@login_required
def api_other_incomes():
    if request.method == 'POST':
        data = request.get_json()
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        income = OtherIncomes(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            monthly_amount=monthly_amount,
            annual_amount=monthly_amount * 12,
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0))
        )
        
        db.session.add(income)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'その他収入を登録しました'})
    
    else:
        incomes = OtherIncomes.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': i.id,
            'name': i.name,
            'description': i.description,
            'monthly_amount': i.monthly_amount,
            'annual_amount': i.annual_amount,
            'start_year': i.start_year,
            'end_year': i.end_year
        } for i in incomes])

# 削除API群
@app.route('/api/insurance-expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def api_delete_insurance_expense(expense_id):
    expense = InsuranceExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if expense:
        db.session.delete(expense)
        db.session.commit()
        return jsonify({'success': True, 'message': '保険費を削除しました'})
    return jsonify({'success': False, 'message': '保険費が見つかりません'})

@app.route('/api/event-expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def api_delete_event_expense(expense_id):
    expense = EventExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if expense:
        db.session.delete(expense)
        db.session.commit()
        return jsonify({'success': True, 'message': 'イベント費用を削除しました'})
    return jsonify({'success': False, 'message': 'イベント費用が見つかりません'})

@app.route('/api/sidejob-incomes/<int:income_id>', methods=['DELETE'])
@login_required
def api_delete_sidejob_income(income_id):
    income = SidejobIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if income:
        db.session.delete(income)
        db.session.commit()
        return jsonify({'success': True, 'message': '副業収入を削除しました'})
    return jsonify({'success': False, 'message': '副業収入が見つかりません'})

@app.route('/api/investment-incomes/<int:income_id>', methods=['DELETE'])
@login_required
def api_delete_investment_income(income_id):
    income = InvestmentIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if income:
        db.session.delete(income)
        db.session.commit()
        return jsonify({'success': True, 'message': '投資収入を削除しました'})
    return jsonify({'success': False, 'message': '投資収入が見つかりません'})

@app.route('/api/pension-incomes/<int:income_id>', methods=['DELETE'])
@login_required
def api_delete_pension_income(income_id):
    income = PensionIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if income:
        db.session.delete(income)
        db.session.commit()
        return jsonify({'success': True, 'message': '年金収入を削除しました'})
    return jsonify({'success': False, 'message': '年金収入が見つかりません'})

@app.route('/api/other-incomes/<int:income_id>', methods=['DELETE'])
@login_required
def api_delete_other_income(income_id):
    income = OtherIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if income:
        db.session.delete(income)
        db.session.commit()
        return jsonify({'success': True, 'message': 'その他収入を削除しました'})
    return jsonify({'success': False, 'message': 'その他収入が見つかりません'})

@app.route('/household-menu')
@login_required
def household_menu():
    """家計簿メニュー画面"""
    # 直近の家計簿エントリを10件取得
    recent_entries = db.session.query(HouseholdEntry)\
        .join(HouseholdBook)\
        .filter(HouseholdBook.user_id == current_user.id)\
        .order_by(HouseholdEntry.entry_date.desc(), HouseholdEntry.created_at.desc())\
        .limit(10).all()
    
    # 今月の統計を計算
    today = date.today()
    current_month_entries = db.session.query(HouseholdEntry)\
        .join(HouseholdBook)\
        .filter(
            HouseholdBook.user_id == current_user.id,
            HouseholdBook.year == today.year,
            HouseholdBook.month == today.month
        ).all()
    
    # カテゴリ別集計
    category_summary = {}
    total_income = 0
    total_expense = 0
    
    for entry in current_month_entries:
        if entry.entry_type == 'income':
            total_income += entry.amount
            if entry.income_category:
                category_name = entry.income_category.name
                if category_name not in category_summary:
                    category_summary[category_name] = {
                        'type': 'income',
                        'amount': 0,
                        'icon': entry.income_category.icon,
                        'color': entry.income_category.color
                    }
                category_summary[category_name]['amount'] += entry.amount
        else:
            total_expense += entry.amount
            if entry.expense_category:
                category_name = entry.expense_category.name
                if category_name not in category_summary:
                    category_summary[category_name] = {
                        'type': 'expense',
                        'amount': 0,
                        'icon': entry.expense_category.icon,
                        'color': entry.expense_category.color
                    }
                category_summary[category_name]['amount'] += entry.amount
    
    balance = total_income - total_expense
    
    return render_template('household_menu.html', 
                         recent_entries=recent_entries,
                         category_summary=category_summary,
                         total_income=total_income,
                         total_expense=total_expense,
                         balance=balance,
                         current_month=today.month,
                         current_year=today.year)

@app.route('/household-book')
@login_required
def household_book():
    return render_template('household_book.html')

@app.route('/household-book-dev')
@login_required
def household_book_dev():
    return render_template('household_book_dev.html')

@app.route('/mypage')
@login_required
def mypage():
    return render_template('mypage.html')

# 新しい家計簿機能のルーティング
@app.route('/household-books')
@login_required
def household_books():
    """家計簿一覧・新規作成ページ"""
    # 直近の家計簿を取得
    recent_books = HouseholdBook.query.filter_by(user_id=current_user.id)\
        .order_by(HouseholdBook.year.desc(), HouseholdBook.month.desc())\
        .limit(5).all()
    
    return render_template('household_books.html', recent_books=recent_books)

@app.route('/household-books/<int:year>/<int:month>')
@login_required
def household_book_monthly(year, month):
    """月次家計簿ページ"""
    # 指定年月の家計簿を取得または作成
    household_book = HouseholdBook.query.filter_by(
        user_id=current_user.id, year=year, month=month
    ).first()
    
    if not household_book:
        # 家計簿が存在しない場合は作成
        household_book = HouseholdBook(
            user_id=current_user.id,
            name=f"{year}年{month}月の家計簿",
            year=year,
            month=month
        )
        db.session.add(household_book)
        db.session.commit()
    
    # エントリーを取得
    entries = HouseholdEntry.query.filter_by(household_book_id=household_book.id)\
        .order_by(HouseholdEntry.entry_date.desc()).all()
    
    # カテゴリを取得
    expense_categories = ExpenseCategory.query.all()
    income_categories = IncomeCategory.query.all()
    
    # 月次統計を計算
    total_income = sum(entry.amount for entry in entries if entry.entry_type == 'income')
    total_expense = sum(entry.amount for entry in entries if entry.entry_type == 'expense')
    balance = total_income - total_expense
    
    return render_template('household_book_monthly.html', 
                         household_book=household_book,
                         entries=entries,
                         expense_categories=expense_categories,
                         income_categories=income_categories,
                         total_income=total_income,
                         total_expense=total_expense,
                         balance=balance)

# API Routes for Expenses
@app.route('/api/living-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_living_expenses():
    if request.method == 'POST':
        data = request.get_json()
        
        # Calculate monthly total with proper type conversion
        monthly_total = sum([
            float(data.get('food_home', 0) or 0),
            float(data.get('food_outside', 0) or 0),
            float(data.get('utility_electricity', 0) or 0),
            float(data.get('utility_gas', 0) or 0),
            float(data.get('utility_water', 0) or 0),
            float(data.get('subscription_services', 0) or 0),
            float(data.get('internet', 0) or 0),
            float(data.get('phone', 0) or 0),
            float(data.get('household_goods', 0) or 0),
            float(data.get('hygiene', 0) or 0),
            float(data.get('clothing', 0) or 0),
            float(data.get('beauty', 0) or 0),
            float(data.get('child_food', 0) or 0),
            float(data.get('child_clothing', 0) or 0),
            float(data.get('child_medical', 0) or 0),
            float(data.get('child_other', 0) or 0),
            float(data.get('transport', 0) or 0),
            float(data.get('entertainment', 0) or 0),
            float(data.get('pet_costs', 0) or 0),
            float(data.get('other_expenses', 0) or 0)
        ])
        
        expense = LivingExpenses(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            inflation_rate=float(data.get('inflation_rate', 2.0)),
            food_home=float(data.get('food_home', 0) or 0),
            food_outside=float(data.get('food_outside', 0) or 0),
            utility_electricity=float(data.get('utility_electricity', 0) or 0),
            utility_gas=float(data.get('utility_gas', 0) or 0),
            utility_water=float(data.get('utility_water', 0) or 0),
            subscription_services=float(data.get('subscription_services', 0) or 0),
            internet=float(data.get('internet', 0) or 0),
            phone=float(data.get('phone', 0) or 0),
            household_goods=float(data.get('household_goods', 0) or 0),
            hygiene=float(data.get('hygiene', 0) or 0),
            clothing=float(data.get('clothing', 0) or 0),
            beauty=float(data.get('beauty', 0) or 0),
            child_food=float(data.get('child_food', 0) or 0),
            child_clothing=float(data.get('child_clothing', 0) or 0),
            child_medical=float(data.get('child_medical', 0) or 0),
            child_other=float(data.get('child_other', 0) or 0),
            transport=float(data.get('transport', 0) or 0),
            entertainment=float(data.get('entertainment', 0) or 0),
            pet_costs=float(data.get('pet_costs', 0) or 0),
            other_expenses=float(data.get('other_expenses', 0) or 0),
            monthly_total_amount=monthly_total
        )
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '生活費を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        expense_id = data.get('id')
        
        if not expense_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        expense = LivingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
        if not expense:
            return jsonify({'success': False, 'message': '指定された生活費が見つかりません'}), 404
        
        # Calculate monthly total with proper type conversion
        monthly_total = sum([
            float(data.get('food_home', 0) or 0),
            float(data.get('food_outside', 0) or 0),
            float(data.get('utility_electricity', 0) or 0),
            float(data.get('utility_gas', 0) or 0),
            float(data.get('utility_water', 0) or 0),
            float(data.get('subscription_services', 0) or 0),
            float(data.get('internet', 0) or 0),
            float(data.get('phone', 0) or 0),
            float(data.get('household_goods', 0) or 0),
            float(data.get('hygiene', 0) or 0),
            float(data.get('clothing', 0) or 0),
            float(data.get('beauty', 0) or 0),
            float(data.get('child_food', 0) or 0),
            float(data.get('child_clothing', 0) or 0),
            float(data.get('child_medical', 0) or 0),
            float(data.get('child_other', 0) or 0),
            float(data.get('transport', 0) or 0),
            float(data.get('entertainment', 0) or 0),
            float(data.get('pet_costs', 0) or 0),
            float(data.get('other_expenses', 0) or 0)
        ])
        
        # Update expense data
        expense.name = data.get('name')
        expense.description = data.get('description')
        expense.start_year = int(data.get('start_year', 0))
        expense.end_year = int(data.get('end_year', 0))
        expense.inflation_rate = float(data.get('inflation_rate', 2.0))
        expense.food_home = float(data.get('food_home', 0) or 0)
        expense.food_outside = float(data.get('food_outside', 0) or 0)
        expense.utility_electricity = float(data.get('utility_electricity', 0) or 0)
        expense.utility_gas = float(data.get('utility_gas', 0) or 0)
        expense.utility_water = float(data.get('utility_water', 0) or 0)
        expense.subscription_services = float(data.get('subscription_services', 0) or 0)
        expense.internet = float(data.get('internet', 0) or 0)
        expense.phone = float(data.get('phone', 0) or 0)
        expense.household_goods = float(data.get('household_goods', 0) or 0)
        expense.hygiene = float(data.get('hygiene', 0) or 0)
        expense.clothing = float(data.get('clothing', 0) or 0)
        expense.beauty = float(data.get('beauty', 0) or 0)
        expense.child_food = float(data.get('child_food', 0) or 0)
        expense.child_clothing = float(data.get('child_clothing', 0) or 0)
        expense.child_medical = float(data.get('child_medical', 0) or 0)
        expense.child_other = float(data.get('child_other', 0) or 0)
        expense.transport = float(data.get('transport', 0) or 0)
        expense.entertainment = float(data.get('entertainment', 0) or 0)
        expense.pet_costs = float(data.get('pet_costs', 0) or 0)
        expense.other_expenses = float(data.get('other_expenses', 0) or 0)
        expense.monthly_total_amount = monthly_total
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '生活費を更新しました'})
    
    else:
        expenses = LivingExpenses.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': e.id,
            'name': e.name,
            'description': e.description,
            'start_year': e.start_year,
            'end_year': e.end_year,
            'inflation_rate': e.inflation_rate,
            'monthly_total_amount': e.monthly_total_amount,
            'food_home': e.food_home,
            'food_outside': e.food_outside,
            'utility_electricity': e.utility_electricity,
            'utility_gas': e.utility_gas,
            'utility_water': e.utility_water,
            'subscription_services': e.subscription_services,
            'internet': e.internet,
            'phone': e.phone,
            'household_goods': e.household_goods,
            'hygiene': e.hygiene,
            'clothing': e.clothing,
            'beauty': e.beauty,
            'child_food': e.child_food,
            'child_clothing': e.child_clothing,
            'child_medical': e.child_medical,
            'child_other': e.child_other,
            'transport': e.transport,
            'entertainment': e.entertainment,
            'pet_costs': e.pet_costs,
            'other_expenses': e.other_expenses
        } for e in expenses])

@app.route('/api/education-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_education_expenses():
    if request.method == 'POST':
        data = request.get_json()
        
        # 教育費統合管理用の教育プランを作成
        education_plan = EducationPlans(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            child_name=data.get('child_name'),
            child_birth_date=datetime.strptime(data.get('child_birth_date'), '%Y-%m-%d').date(),
            kindergarten_type=KindergartenType(data.get('kindergarten_type', 'NONE')),
            elementary_type=ElementaryType(data.get('elementary_type', 'PUBLIC')),
            junior_type=JuniorType(data.get('junior_type', 'PUBLIC')),
            high_type=HighType(data.get('high_type', 'PUBLIC')),
            college_type=CollegeType(data.get('college_type', 'NONE'))
        )
        
        db.session.add(education_plan)
        db.session.flush()  # IDを取得するため
        
        # カスタム費用を取得（万円→円に変換）
        custom_costs = {
            'kindergarten': float(data.get('kindergarten_cost', 0)) * 10000,
            'elementary': float(data.get('elementary_cost', 0)) * 10000,
            'junior': float(data.get('junior_cost', 0)) * 10000,
            'high': float(data.get('high_cost', 0)) * 10000,
            'college': float(data.get('college_cost', 0)) * 10000
        }
        
        # 教育費を計算（期間情報取得用）
        costs = calculate_education_costs(
            education_plan.child_birth_date,
            education_plan.kindergarten_type,
            education_plan.elementary_type,
            education_plan.junior_type,
            education_plan.high_type,
            education_plan.college_type
        )
        
        # 各教育段階のレコードを作成（カスタム費用使用）
        stages = [
            ('kindergarten', education_plan.kindergarten_type.value, custom_costs['kindergarten'], costs['kindergarten_start_year'], costs['kindergarten_end_year'], 3),
            ('elementary', education_plan.elementary_type.value, custom_costs['elementary'], costs['elementary_start_year'], costs['elementary_end_year'], 6),
            ('junior', education_plan.junior_type.value, custom_costs['junior'], costs['junior_start_year'], costs['junior_end_year'], 3),
            ('high', education_plan.high_type.value, custom_costs['high'], costs['high_start_year'], costs['high_end_year'], 3),
            ('college', education_plan.college_type.value, custom_costs['college'], costs['college_start_year'], costs['college_end_year'], 4 if education_plan.college_type.value in ['国公立大学', '私立文系', '私立理系'] else 2)
        ]
        
        created_expenses = []
        for stage, stage_type, total_cost, start_year, end_year, years in stages:
            # 費用が0または期間が無効な場合はスキップ
            if total_cost <= 0 or start_year <= 0 or end_year <= 0:
                continue
                
            # "進学しない"や"未就園"の場合もスキップ
            if stage_type in ['進学しない', '未就園']:
                continue
            
            # 月額を計算
            monthly_amount = total_cost / (years * 12)
            
            expense = EducationExpenses(
                user_id=current_user.id,
                education_plan_id=education_plan.id,
                name=f"{education_plan.child_name}の{stage_type}",
                description=f"{education_plan.child_name}の{stage_type}にかかる費用",
                start_year=start_year,
                end_year=end_year,
                child_name=education_plan.child_name,
                child_birth_date=education_plan.child_birth_date,
                stage=stage,
                stage_type=stage_type,
                monthly_amount=monthly_amount
            )
            db.session.add(expense)
            created_expenses.append(expense)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '教育費を登録しました',
            'updated_count': len(created_expenses)
        })
    
    elif request.method == 'PUT':
        # 統合管理では編集は無効化
        return jsonify({'success': False, 'message': '教育費の編集は削除後、再登録してください'}), 400
    
    else:
        # 新しい統合表示：教育プラン毎にグループ化して表示
        education_plans = EducationPlans.query.filter_by(user_id=current_user.id).all()
        
        result = []
        for plan in education_plans:
            # 関連する教育費を取得
            expenses = EducationExpenses.query.filter_by(education_plan_id=plan.id).all()
            
            total_monthly = sum(e.monthly_amount for e in expenses)
            start_year = min(e.start_year for e in expenses) if expenses else None
            end_year = max(e.end_year for e in expenses) if expenses else None
            
            # 統合された結果を返す
            unified_result = {
                'id': plan.id,  # 統合削除時に使用
                'unified_id': f"{plan.child_name}_{plan.child_birth_date.isoformat()}",
                'name': f"{plan.child_name}の教育費",
                'description': f"{plan.child_name}の全教育段階費用",
                'start_year': start_year,
                'end_year': end_year,
                'child_name': plan.child_name,
                'child_birth_date': plan.child_birth_date.isoformat(),
                'monthly_total_amount': total_monthly,
                'expense_ids': [e.id for e in expenses],
                'stages': []
            }
            
            # 各段階の詳細情報
            for expense in expenses:
                stage_info = {
                    'id': expense.id,
                    'name': expense.name,
                    'start_year': expense.start_year,
                    'end_year': expense.end_year,
                    'monthly_amount': expense.monthly_amount,
                    'stage': expense.stage,
                    'stage_type': expense.stage_type
                }
                unified_result['stages'].append(stage_info)
            
            result.append(unified_result)
        
        return jsonify(result)

# 家計簿API
@app.route('/api/household-books', methods=['GET', 'POST'])
@login_required
def api_household_books():
    if request.method == 'GET':
        # 家計簿一覧を取得
        books = HouseholdBook.query.filter_by(user_id=current_user.id)\
            .order_by(HouseholdBook.year.desc(), HouseholdBook.month.desc()).all()
        
        return jsonify([{
            'id': book.id,
            'name': book.name,
            'year': book.year,
            'month': book.month,
            'description': book.description,
            'created_at': book.created_at.isoformat(),
            'updated_at': book.updated_at.isoformat()
        } for book in books])
    
    elif request.method == 'POST':
        # 新しい家計簿を作成
        try:
            data = request.get_json()
            year = data.get('year')
            month = data.get('month')
            name = data.get('name', f"{year}年{month}月の家計簿")
            description = data.get('description', '')
            
            # 既存チェック
            existing_book = HouseholdBook.query.filter_by(
                user_id=current_user.id, year=year, month=month
            ).first()
            
            if existing_book:
                return jsonify({'error': 'この年月の家計簿は既に存在します'}), 400
            
            # 新規作成
            new_book = HouseholdBook(
                user_id=current_user.id,
                name=name,
                year=year,
                month=month,
                description=description
            )
            
            db.session.add(new_book)
            db.session.commit()
            
            return jsonify({
                'id': new_book.id,
                'name': new_book.name,
                'year': new_book.year,
                'month': new_book.month,
                'description': new_book.description,
                'message': '家計簿を作成しました'
            }), 201
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'家計簿作成エラー: {str(e)}')
            return jsonify({'error': '家計簿作成中にエラーが発生しました'}), 500

@app.route('/api/household-entries', methods=['GET', 'POST'])
@login_required
def api_household_entries():
    if request.method == 'GET':
        # エントリー一覧を取得
        household_book_id = request.args.get('household_book_id')
        if not household_book_id:
            return jsonify({'error': '家計簿IDが必要です'}), 400
        
        entries = HouseholdEntry.query.filter_by(
            household_book_id=household_book_id,
            user_id=current_user.id
        ).order_by(HouseholdEntry.entry_date.desc()).all()
        
        return jsonify([{
            'id': entry.id,
            'entry_type': entry.entry_type,
            'amount': entry.amount,
            'description': entry.description,
            'entry_date': entry.entry_date.isoformat(),
            'expense_category': {
                'id': entry.expense_category.id,
                'name': entry.expense_category.name,
                'icon': entry.expense_category.icon,
                'color': entry.expense_category.color
            } if entry.expense_category else None,
            'income_category': {
                'id': entry.income_category.id,
                'name': entry.income_category.name,
                'icon': entry.income_category.icon,
                'color': entry.income_category.color
            } if entry.income_category else None,
            'created_at': entry.created_at.isoformat()
        } for entry in entries])
    
    elif request.method == 'POST':
        # 新しいエントリーを作成
        try:
            data = request.get_json()
            
            entry = HouseholdEntry(
                household_book_id=data['household_book_id'],
                user_id=current_user.id,
                entry_type=data['entry_type'],
                amount=float(data['amount']),
                description=data.get('description', ''),
                entry_date=datetime.strptime(data['entry_date'], '%Y-%m-%d').date(),
                expense_category_id=data.get('expense_category_id'),
                income_category_id=data.get('income_category_id')
            )
            
            db.session.add(entry)
            db.session.commit()
            
            return jsonify({
                'id': entry.id,
                'message': 'エントリーを追加しました'
            }), 201
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'エントリー作成エラー: {str(e)}')
            return jsonify({'error': 'エントリー作成中にエラーが発生しました'}), 500

@app.route('/api/household-entries/<int:entry_id>', methods=['PUT', 'DELETE'])
@login_required
def api_household_entry_detail(entry_id):
    entry = HouseholdEntry.query.filter_by(id=entry_id, user_id=current_user.id).first()
    if not entry:
        return jsonify({'error': 'エントリーが見つかりません'}), 404
    
    if request.method == 'PUT':
        # エントリーを更新
        try:
            data = request.get_json()
            
            entry.entry_type = data.get('entry_type', entry.entry_type)
            entry.amount = float(data.get('amount', entry.amount))
            entry.description = data.get('description', entry.description)
            entry.entry_date = datetime.strptime(data['entry_date'], '%Y-%m-%d').date() if 'entry_date' in data else entry.entry_date
            entry.expense_category_id = data.get('expense_category_id')
            entry.income_category_id = data.get('income_category_id')
            entry.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({'message': 'エントリーを更新しました'})
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'エントリー更新エラー: {str(e)}')
            return jsonify({'error': 'エントリー更新中にエラーが発生しました'}), 500
    
    elif request.method == 'DELETE':
        # エントリーを削除
        try:
            db.session.delete(entry)
            db.session.commit()
            
            return jsonify({'message': 'エントリーを削除しました'})
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'エントリー削除エラー: {str(e)}')
            return jsonify({'error': 'エントリー削除中にエラーが発生しました'}), 500

@app.route('/api/expense-categories', methods=['GET'])
@login_required
def api_expense_categories():
    categories = ExpenseCategory.query.all()
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'icon': cat.icon,
        'color': cat.color,
        'is_default': cat.is_default
    } for cat in categories])

@app.route('/api/income-categories', methods=['GET'])
@login_required
def api_income_categories():
    categories = IncomeCategory.query.all()
    return jsonify([{
        'id': cat.id,
        'name': cat.name,
        'icon': cat.icon,
        'color': cat.color,
        'is_default': cat.is_default
    } for cat in categories])

@app.route('/api/housing-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_housing_expenses():
    if request.method == 'POST':
        data = request.get_json()
        
        residence_type = ResidenceType(data.get('residence_type'))
        
        # Calculate mortgage if applicable
        mortgage_monthly = 0
        if residence_type == ResidenceType.OWNED_WITH_LOAN:
            loan_amount = float(data.get('purchase_price', 0) or 0) - float(data.get('down_payment', 0) or 0)
            mortgage_monthly = calculate_mortgage_payment(
                loan_amount,
                float(data.get('loan_interest_rate', 0) or 0),
                int(data.get('loan_term_years', 0) or 0),
                RepaymentMethod(data.get('repayment_method', 'EQUAL_PAYMENT'))
            )
        
        # Calculate monthly total
        if residence_type == ResidenceType.RENTAL:
            monthly_total = float(data.get('rent_monthly', 0) or 0)
        else:
            monthly_total = sum([
                mortgage_monthly,
                float(data.get('property_tax_monthly', 0) or 0),
                float(data.get('management_fee_monthly', 0) or 0),
                float(data.get('repair_reserve_monthly', 0) or 0),
                float(data.get('fire_insurance_monthly', 0) or 0)
            ])
        
        expense = HousingExpenses(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            residence_type=residence_type,
            rent_monthly=float(data.get('rent_monthly', 0) or 0),
            mortgage_monthly=mortgage_monthly,
            property_tax_monthly=float(data.get('property_tax_monthly', 0) or 0),
            management_fee_monthly=float(data.get('management_fee_monthly', 0) or 0),
            repair_reserve_monthly=float(data.get('repair_reserve_monthly', 0) or 0),
            fire_insurance_monthly=float(data.get('fire_insurance_monthly', 0) or 0),
            purchase_price=float(data.get('purchase_price', 0) or 0),
            down_payment=float(data.get('down_payment', 0) or 0),
            loan_interest_rate=float(data.get('loan_interest_rate', 0) or 0),
            loan_term_years=int(data.get('loan_term_years', 0) or 0),
            repayment_method=RepaymentMethod(data.get('repayment_method', 'EQUAL_PAYMENT')),
            monthly_total_amount=monthly_total
        )
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': '住居費を登録しました',
            'calculated_mortgage': mortgage_monthly
        })
    
    elif request.method == 'PUT':
        data = request.get_json()
        expense_id = data.get('id')
        
        if not expense_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        expense = HousingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
        if not expense:
            return jsonify({'success': False, 'message': '指定された住居費が見つかりません'}), 404
        
        residence_type = ResidenceType(data.get('residence_type'))
        
        # Calculate mortgage if applicable
        mortgage_monthly = 0
        if residence_type == ResidenceType.OWNED_WITH_LOAN:
            loan_amount = float(data.get('purchase_price', 0) or 0) - float(data.get('down_payment', 0) or 0)
            mortgage_monthly = calculate_mortgage_payment(
                loan_amount,
                float(data.get('loan_interest_rate', 0) or 0),
                int(data.get('loan_term_years', 0) or 0),
                RepaymentMethod(data.get('repayment_method', 'EQUAL_PAYMENT'))
            )
        
        # Calculate monthly total
        if residence_type == ResidenceType.RENTAL:
            monthly_total = float(data.get('rent_monthly', 0) or 0)
        else:
            monthly_total = sum([
                mortgage_monthly,
                float(data.get('property_tax_monthly', 0) or 0),
                float(data.get('management_fee_monthly', 0) or 0),
                float(data.get('repair_reserve_monthly', 0) or 0),
                float(data.get('fire_insurance_monthly', 0) or 0)
            ])
        
        # Update expense data
        expense.name = data.get('name')
        expense.description = data.get('description')
        expense.start_year = int(data.get('start_year', 0))
        expense.end_year = int(data.get('end_year', 0))
        expense.residence_type = residence_type
        expense.rent_monthly = float(data.get('rent_monthly', 0) or 0)
        expense.mortgage_monthly = mortgage_monthly
        expense.property_tax_monthly = float(data.get('property_tax_monthly', 0) or 0)
        expense.management_fee_monthly = float(data.get('management_fee_monthly', 0) or 0)
        expense.repair_reserve_monthly = float(data.get('repair_reserve_monthly', 0) or 0)
        expense.fire_insurance_monthly = float(data.get('fire_insurance_monthly', 0) or 0)
        expense.purchase_price = float(data.get('purchase_price', 0) or 0)
        expense.down_payment = float(data.get('down_payment', 0) or 0)
        expense.loan_interest_rate = float(data.get('loan_interest_rate', 0) or 0)
        expense.loan_term_years = int(data.get('loan_term_years', 0) or 0)
        expense.repayment_method = RepaymentMethod(data.get('repayment_method', 'EQUAL_PAYMENT'))
        expense.monthly_total_amount = monthly_total
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': '住居費を更新しました',
            'calculated_mortgage': mortgage_monthly
        })
    
    else:
        expenses = HousingExpenses.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': e.id,
            'name': e.name,
            'description': e.description,
            'start_year': e.start_year,
            'end_year': e.end_year,
            'residence_type': e.residence_type.value,
            'rent_monthly': e.rent_monthly,
            'mortgage_monthly': e.mortgage_monthly,
            'property_tax_monthly': e.property_tax_monthly,
            'management_fee_monthly': e.management_fee_monthly,
            'repair_reserve_monthly': e.repair_reserve_monthly,
            'fire_insurance_monthly': e.fire_insurance_monthly,
            'purchase_price': e.purchase_price,
            'down_payment': e.down_payment,
            'loan_interest_rate': e.loan_interest_rate,
            'loan_term_years': e.loan_term_years,
            'repayment_method': e.repayment_method.value,
            'monthly_total_amount': e.monthly_total_amount
        } for e in expenses])

@app.route('/api/housing-expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def api_delete_housing_expense(expense_id):
    expense = HousingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not expense:
        return jsonify({'success': False, 'message': '指定された住居費が見つかりません'}), 404
    
    db.session.delete(expense)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '住居費を削除しました'})

@app.route('/api/housing-expenses/<int:expense_id>/copy', methods=['POST'])
@login_required
def api_copy_housing_expense(expense_id):
    # 元のデータを取得
    original_expense = HousingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not original_expense:
        return jsonify({'success': False, 'message': '指定された住居費が見つかりません'}), 404
    
    # 新しいデータを作成（IDを除く）
    new_expense = HousingExpenses(
        user_id=current_user.id,
        name=f"{original_expense.name} - コピー",
        description=original_expense.description,
        start_year=original_expense.start_year,
        end_year=original_expense.end_year,
        residence_type=original_expense.residence_type,
        rent_monthly=original_expense.rent_monthly,
        mortgage_monthly=original_expense.mortgage_monthly,
        property_tax_monthly=original_expense.property_tax_monthly,
        management_fee_monthly=original_expense.management_fee_monthly,
        repair_reserve_monthly=original_expense.repair_reserve_monthly,
        fire_insurance_monthly=original_expense.fire_insurance_monthly,
        purchase_price=original_expense.purchase_price,
        down_payment=original_expense.down_payment,
        loan_interest_rate=original_expense.loan_interest_rate,
        loan_term_years=original_expense.loan_term_years,
        repayment_method=original_expense.repayment_method,
        monthly_total_amount=original_expense.monthly_total_amount
    )
    
    db.session.add(new_expense)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '住居費をコピーしました',
        'new_id': new_expense.id
    })

@app.route('/api/insurance-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_insurance_expenses():
    if request.method == 'POST':
        data = request.get_json()
        
        # Calculate monthly total with proper type conversion
        monthly_total = sum([
            float(data.get('medical_insurance', 0) or 0),
            float(data.get('cancer_insurance', 0) or 0),
            float(data.get('life_insurance', 0) or 0),
            float(data.get('income_protection', 0) or 0),
            float(data.get('accident_insurance', 0) or 0),
            float(data.get('liability_insurance', 0) or 0),
            float(data.get('fire_insurance', 0) or 0),
            float(data.get('long_term_care_insurance', 0) or 0),
            float(data.get('other_insurance', 0) or 0)
        ])
        
        expense = InsuranceExpenses(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            medical_insurance=float(data.get('medical_insurance', 0) or 0),
            cancer_insurance=float(data.get('cancer_insurance', 0) or 0),
            life_insurance=float(data.get('life_insurance', 0) or 0),
            income_protection=float(data.get('income_protection', 0) or 0),
            accident_insurance=float(data.get('accident_insurance', 0) or 0),
            liability_insurance=float(data.get('liability_insurance', 0) or 0),
            fire_insurance=float(data.get('fire_insurance', 0) or 0),
            long_term_care_insurance=float(data.get('long_term_care_insurance', 0) or 0),
            other_insurance=float(data.get('other_insurance', 0) or 0),
            insured_person=data.get('insured_person'),
            insurance_company=data.get('insurance_company'),
            insurance_term_years=int(data.get('insurance_term_years', 0) or 0),
            renew_type=data.get('renew_type'),
            monthly_total_amount=monthly_total
        )
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '保険費を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        expense_id = data.get('id')
        
        if not expense_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        expense = InsuranceExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
        if not expense:
            return jsonify({'success': False, 'message': '指定された保険が見つかりません'}), 404
        
        # Calculate monthly total with proper type conversion
        monthly_total = sum([
            float(data.get('medical_insurance', 0) or 0),
            float(data.get('cancer_insurance', 0) or 0),
            float(data.get('life_insurance', 0) or 0),
            float(data.get('income_protection', 0) or 0),
            float(data.get('accident_insurance', 0) or 0),
            float(data.get('liability_insurance', 0) or 0),
            float(data.get('fire_insurance', 0) or 0),
            float(data.get('long_term_care_insurance', 0) or 0),
            float(data.get('other_insurance', 0) or 0)
        ])
        
        # Update expense data
        expense.name = data.get('name')
        expense.description = data.get('description')
        expense.start_year = int(data.get('start_year', 0))
        expense.end_year = int(data.get('end_year', 0))
        expense.medical_insurance = float(data.get('medical_insurance', 0) or 0)
        expense.cancer_insurance = float(data.get('cancer_insurance', 0) or 0)
        expense.life_insurance = float(data.get('life_insurance', 0) or 0)
        expense.income_protection = float(data.get('income_protection', 0) or 0)
        expense.accident_insurance = float(data.get('accident_insurance', 0) or 0)
        expense.liability_insurance = float(data.get('liability_insurance', 0) or 0)
        expense.fire_insurance = float(data.get('fire_insurance', 0) or 0)
        expense.long_term_care_insurance = float(data.get('long_term_care_insurance', 0) or 0)
        expense.other_insurance = float(data.get('other_insurance', 0) or 0)
        expense.insured_person = data.get('insured_person')
        expense.insurance_company = data.get('insurance_company')
        expense.insurance_term_years = int(data.get('insurance_term_years', 0) or 0)
        expense.renew_type = data.get('renew_type')
        expense.monthly_total_amount = monthly_total
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '保険費を更新しました'})
    
    else:
        expenses = InsuranceExpenses.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': e.id,
            'name': e.name,
            'description': e.description,
            'start_year': e.start_year,
            'end_year': e.end_year,
            'monthly_total_amount': e.monthly_total_amount,
            'medical_insurance': e.medical_insurance,
            'cancer_insurance': e.cancer_insurance,
            'life_insurance': e.life_insurance,
            'income_protection': e.income_protection,
            'accident_insurance': e.accident_insurance,
            'liability_insurance': e.liability_insurance,
            'fire_insurance': e.fire_insurance,
            'long_term_care_insurance': e.long_term_care_insurance,
            'other_insurance': e.other_insurance,
            'insured_person': e.insured_person,
            'insurance_company': e.insurance_company,
            'insurance_term_years': e.insurance_term_years,
            'renew_type': e.renew_type
        } for e in expenses])

@app.route('/api/event-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_event_expenses():
    if request.method == 'POST':
        data = request.get_json()
        
        category = EventCategory(data.get('category'))
        
        expense = EventExpenses(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            category=category,
            amount=float(data.get('amount', 0) or 0),
            is_recurring=bool(data.get('is_recurring', False)),
            recurrence_interval=int(data.get('recurrence_interval', 1)),
            recurrence_count=int(data.get('recurrence_count', 1))
        )
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'イベント費用を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        expense_id = data.get('id')
        
        if not expense_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        expense = EventExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
        if not expense:
            return jsonify({'success': False, 'message': '指定されたイベントが見つかりません'}), 404
        
        category = EventCategory(data.get('category'))
        
        # Update expense data
        expense.name = data.get('name')
        expense.description = data.get('description')
        expense.start_year = int(data.get('start_year', 0))
        expense.end_year = int(data.get('end_year', 0))
        expense.category = category
        expense.amount = float(data.get('amount', 0) or 0)
        expense.is_recurring = bool(data.get('is_recurring', False))
        expense.recurrence_interval = int(data.get('recurrence_interval', 1))
        expense.recurrence_count = int(data.get('recurrence_count', 1))
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'イベント費用を更新しました'})
    
    else:
        expenses = EventExpenses.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': e.id,
            'name': e.name,
            'description': e.description,
            'start_year': e.start_year,
            'end_year': e.end_year,
            'category': e.category.value,
            'amount': e.amount,
            'is_recurring': e.is_recurring,
            'recurrence_interval': e.recurrence_interval,
            'recurrence_count': e.recurrence_count
        } for e in expenses])

@app.route('/api/sidejob-incomes', methods=['GET', 'POST', 'PUT'])
@login_required
def api_sidejob_incomes():
    if request.method == 'POST':
        data = request.get_json()
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        income = SidejobIncomes(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            monthly_amount=monthly_amount,
            annual_amount=monthly_amount * 12,
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            income_increase_rate=float(data.get('income_increase_rate', 0.0)),
            has_cap=bool(data.get('has_cap', False)),
            annual_income_cap=float(data.get('annual_income_cap', 0) or 0)
        )
        
        db.session.add(income)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '副業収入を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        income_id = data.get('id')
        
        if not income_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        income = SidejobIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
        if not income:
            return jsonify({'success': False, 'message': '指定された副業収入が見つかりません'}), 404
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        
        # Update income data
        income.name = data.get('name')
        income.description = data.get('description')
        income.monthly_amount = monthly_amount
        income.annual_amount = monthly_amount * 12
        income.start_year = int(data.get('start_year', 0))
        income.end_year = int(data.get('end_year', 0))
        income.income_increase_rate = float(data.get('income_increase_rate', 0.0))
        income.has_cap = bool(data.get('has_cap', False))
        income.annual_income_cap = float(data.get('annual_income_cap', 0) or 0)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '副業収入を更新しました'})
    
    else:
        incomes = SidejobIncomes.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': i.id,
            'name': i.name,
            'description': i.description,
            'monthly_amount': i.monthly_amount,
            'annual_amount': i.annual_amount,
            'start_year': i.start_year,
            'end_year': i.end_year,
            'income_increase_rate': i.income_increase_rate,
            'has_cap': i.has_cap,
            'annual_income_cap': i.annual_income_cap
        } for i in incomes])

# 各種データ取得API（シミュレーション選択用）
@app.route('/api/all-expenses', methods=['GET'])
@login_required
def api_all_expenses():
    living_expenses = LivingExpenses.query.filter_by(user_id=current_user.id).all()
    education_plans = EducationPlans.query.filter_by(user_id=current_user.id).all()  # 統合ID使用
    housing_expenses = HousingExpenses.query.filter_by(user_id=current_user.id).all()
    insurance_expenses = InsuranceExpenses.query.filter_by(user_id=current_user.id).all()
    event_expenses = EventExpenses.query.filter_by(user_id=current_user.id).all()
    
    # 教育費の統合表示用データ作成
    education_list = []
    for plan in education_plans:
        # 関連する教育費の合計を計算
        related_expenses = EducationExpenses.query.filter_by(education_plan_id=plan.id).all()
        total_monthly = sum(exp.monthly_amount for exp in related_expenses)
        
        # 期間の最小開始年と最大終了年を取得
        start_years = [exp.start_year for exp in related_expenses]
        end_years = [exp.end_year for exp in related_expenses]
        
        education_list.append({
            'id': plan.id,  # 統合ID
            'name': plan.name,
            'description': plan.description,
            'start_year': min(start_years) if start_years else 0,
            'end_year': max(end_years) if end_years else 0,
            'monthly_total_amount': total_monthly,
            'annual_amount': total_monthly * 12,
            'child_name': plan.child_name
        })
    
    return jsonify({
        'living': [{
            'id': e.id, 'name': e.name, 'description': e.description,
            'start_year': e.start_year, 'end_year': e.end_year,
            'monthly_total_amount': e.monthly_total_amount,
            'annual_amount': e.monthly_total_amount * 12
        } for e in living_expenses],
        'education': education_list,
        'housing': [{
            'id': e.id, 'name': e.name, 'description': e.description,
            'start_year': e.start_year, 'end_year': e.end_year,
            'monthly_total_amount': e.monthly_total_amount,
            'annual_amount': e.monthly_total_amount * 12,
            'residence_type': e.residence_type.value
        } for e in housing_expenses],
        'insurance': [{
            'id': e.id, 'name': e.name, 'description': e.description,
            'start_year': e.start_year, 'end_year': e.end_year,
            'monthly_total_amount': e.monthly_total_amount,
            'annual_amount': e.monthly_total_amount * 12,
            'insured_person': e.insured_person
        } for e in insurance_expenses],
        'event': [{
            'id': e.id, 'name': e.name, 'description': e.description,
            'start_year': e.start_year, 'end_year': e.end_year,
            'amount': e.amount,
            'category': e.category.value
        } for e in event_expenses]
    })

@app.route('/api/all-incomes', methods=['GET'])
@login_required
def api_all_incomes():
    salary_incomes = SalaryIncomes.query.filter_by(user_id=current_user.id).all()
    sidejob_incomes = SidejobIncomes.query.filter_by(user_id=current_user.id).all()
    investment_incomes = InvestmentIncomes.query.filter_by(user_id=current_user.id).all()
    pension_incomes = PensionIncomes.query.filter_by(user_id=current_user.id).all()
    other_incomes = OtherIncomes.query.filter_by(user_id=current_user.id).all()
    
    return jsonify({
        'salary': [{
            'id': i.id, 'name': i.name, 'description': i.description,
            'start_year': i.start_year, 'end_year': i.end_year,
            'monthly_amount': i.monthly_amount, 'annual_bonus': i.annual_bonus, 'annual_amount': i.annual_amount
        } for i in salary_incomes],
        'sidejob': [{
            'id': i.id, 'name': i.name, 'description': i.description,
            'start_year': i.start_year, 'end_year': i.end_year,
            'monthly_amount': i.monthly_amount, 'annual_amount': i.annual_amount
        } for i in sidejob_incomes],
        'investment': [{
            'id': i.id, 'name': i.name, 'description': i.description,
            'start_year': i.start_year, 'end_year': i.end_year,
            'monthly_amount': i.monthly_amount, 'annual_amount': i.annual_amount
        } for i in investment_incomes],
        'pension': [{
            'id': i.id, 'name': i.name, 'description': i.description,
            'start_year': i.start_year, 'end_year': i.end_year,
            'monthly_amount': i.monthly_amount, 'annual_amount': i.annual_amount
        } for i in pension_incomes],
        'other': [{
            'id': i.id, 'name': i.name, 'description': i.description,
            'start_year': i.start_year, 'end_year': i.end_year,
            'monthly_amount': i.monthly_amount, 'annual_amount': i.annual_amount
        } for i in other_incomes]
    })

# Simulation Plans CRUD API
@app.route('/api/simulation-plans', methods=['GET', 'POST', 'PUT'])
@login_required
def api_simulation_plans():
    if request.method == 'GET':
        plans = LifeplanSimulations.query.filter_by(user_id=current_user.id).order_by(LifeplanSimulations.created_at.desc()).all()
        
        plan_list = []
        for plan in plans:
            # 関連する支出・収入項目を取得
            expense_links = LifeplanExpenseLinks.query.filter_by(lifeplan_id=plan.id).all()
            income_links = LifeplanIncomeLinks.query.filter_by(lifeplan_id=plan.id).all()
            
            plan_list.append({
                'id': plan.id,
                'name': plan.name,
                'description': plan.description,
                'base_age': plan.base_age,
                'start_year': plan.start_year,
                'end_year': plan.end_year,
                'expense_count': len(expense_links),
                'income_count': len(income_links),
                'created_at': plan.created_at.strftime('%Y-%m-%d %H:%M')
            })
        
        return jsonify(plan_list)
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'リクエストデータがありません'}), 400
            
            # 必須フィールドのチェック
            required_fields = ['name', 'base_age', 'start_year', 'end_year']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'error': f'{field}は必須です'}), 400
            
            # 新規シミュレーションプラン作成
            plan = LifeplanSimulations(
                user_id=current_user.id,
                name=data.get('name'),
                description=data.get('description', ''),
                base_age=data.get('base_age'),
                start_year=data.get('start_year'),
                end_year=data.get('end_year')
            )
            
            db.session.add(plan)
            db.session.flush()  # IDを取得するためflush
            
            # 選択された支出項目のリンクを保存
            selected_expenses = data.get('selected_expenses', {})
            for expense_type, expense_ids in selected_expenses.items():
                for expense_id in expense_ids:
                    link = LifeplanExpenseLinks(
                        lifeplan_id=plan.id,
                        expense_type=expense_type,
                        expense_id=expense_id
                    )
                    db.session.add(link)
            
            # 選択された収入項目のリンクを保存
            selected_incomes = data.get('selected_incomes', {})
            for income_type, income_ids in selected_incomes.items():
                for income_id in income_ids:
                    link = LifeplanIncomeLinks(
                        lifeplan_id=plan.id,
                        income_type=income_type,
                        income_id=income_id
                    )
                    db.session.add(link)
            
            db.session.commit()
            
            return jsonify({
                'message': 'シミュレーションプランが登録されました',
                'plan_id': plan.id
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'プランの作成中にエラーが発生しました: {str(e)}'}), 500
    
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'error': 'リクエストデータがありません'}), 400
                
            plan_id = data.get('id')
            if not plan_id:
                return jsonify({'error': 'プランIDが必要です'}), 400
            
            plan = LifeplanSimulations.query.filter_by(id=plan_id, user_id=current_user.id).first()
            if not plan:
                return jsonify({'error': 'プランが見つかりません'}), 404
            
            # プラン情報を更新
            plan.name = data.get('name')
            plan.description = data.get('description', '')
            plan.base_age = data.get('base_age')
            plan.start_year = data.get('start_year')
            plan.end_year = data.get('end_year')
            
            # 既存のリンクを削除
            LifeplanExpenseLinks.query.filter_by(lifeplan_id=plan.id).delete()
            LifeplanIncomeLinks.query.filter_by(lifeplan_id=plan.id).delete()
            
            # 新しいリンクを追加
            selected_expenses = data.get('selected_expenses', {})
            for expense_type, expense_ids in selected_expenses.items():
                for expense_id in expense_ids:
                    link = LifeplanExpenseLinks(
                        lifeplan_id=plan.id,
                        expense_type=expense_type,
                        expense_id=expense_id
                    )
                    db.session.add(link)
            
            selected_incomes = data.get('selected_incomes', {})
            for income_type, income_ids in selected_incomes.items():
                for income_id in income_ids:
                    link = LifeplanIncomeLinks(
                        lifeplan_id=plan.id,
                        income_type=income_type,
                        income_id=income_id
                    )
                    db.session.add(link)
            
            db.session.commit()
            
            return jsonify({'message': 'シミュレーションプランが更新されました'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'プランの更新中にエラーが発生しました: {str(e)}'}), 500

@app.route('/api/simulation-plans/<int:plan_id>', methods=['GET', 'DELETE'])
@login_required
def api_simulation_plan_detail(plan_id):
    plan = LifeplanSimulations.query.filter_by(id=plan_id, user_id=current_user.id).first()
    if not plan:
        return jsonify({'error': 'プランが見つかりません'}), 404
    
    if request.method == 'GET':
        # プラン詳細とリンクされた項目を取得
        expense_links = LifeplanExpenseLinks.query.filter_by(lifeplan_id=plan.id).all()
        income_links = LifeplanIncomeLinks.query.filter_by(lifeplan_id=plan.id).all()
        
        # 選択された項目をタイプ別に分類
        selected_expenses = {}
        for link in expense_links:
            if link.expense_type not in selected_expenses:
                selected_expenses[link.expense_type] = []
            selected_expenses[link.expense_type].append(link.expense_id)
        
        selected_incomes = {}
        for link in income_links:
            if link.income_type not in selected_incomes:
                selected_incomes[link.income_type] = []
            selected_incomes[link.income_type].append(link.income_id)
        
        return jsonify({
            'id': plan.id,
            'name': plan.name,
            'description': plan.description,
            'base_age': plan.base_age,
            'start_year': plan.start_year,
            'end_year': plan.end_year,
            'selected_expenses': selected_expenses,
            'selected_incomes': selected_incomes,
            'created_at': plan.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    elif request.method == 'DELETE':
        try:
            # 関連するリンクを削除
            LifeplanExpenseLinks.query.filter_by(lifeplan_id=plan.id).delete()
            LifeplanIncomeLinks.query.filter_by(lifeplan_id=plan.id).delete()
            
            # プランを削除
            db.session.delete(plan)
            db.session.commit()
            
            return jsonify({'message': 'シミュレーションプランが削除されました'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'プランの削除中にエラーが発生しました: {str(e)}'}), 500

if __name__ == '__main__':
    with app.app_context():
        try:
            # データベースセッションをクリア
            db.session.close()
            db.session.remove()
            
            # 既存のデータベース接続をクリア
            db.engine.dispose()
            
            # メタデータをクリア
            db.metadata.clear()
            
            # データベーステーブルを作成
            db.create_all()
            
            # スキーマを強制的に再読み込み
            db.reflect()
            
            # 各テーブルのスキーマを検証
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"利用可能なテーブル: {tables}")
            
            # salary_incomes テーブルの列を確認
            if 'salary_incomes' in tables:
                columns = inspector.get_columns('salary_incomes')
                column_names = [col['name'] for col in columns]
                print(f"salary_incomes の列: {column_names}")
                
                if 'salary_increase_rate' not in column_names:
                    print("警告: salary_increase_rate 列が見つかりません")
                else:
                    print("✓ salary_increase_rate 列が存在します")
            
            # 家計簿テーブルが存在するかチェック
            household_tables = ['household_books', 'expense_categories', 'income_categories', 'household_entries']
            missing_tables = [table for table in household_tables if table not in tables]
            
            if missing_tables:
                print(f"不足している家計簿テーブル: {missing_tables}")
                print("家計簿テーブルを強制作成中...")
                
                # 家計簿テーブルのみを個別に作成
                HouseholdBook.__table__.create(db.engine, checkfirst=True)
                ExpenseCategory.__table__.create(db.engine, checkfirst=True)
                IncomeCategory.__table__.create(db.engine, checkfirst=True)
                HouseholdEntry.__table__.create(db.engine, checkfirst=True)
                
                print("✅ 家計簿テーブルの作成完了")
            
            # デフォルトカテゴリの初期化
            try:
                expense_count = db.session.query(ExpenseCategory).count()
            except:
                expense_count = 0
                
            if expense_count == 0:
                default_expense_categories = [
                    ExpenseCategory(name='食費', icon='restaurant', color='#FF9800'),
                    ExpenseCategory(name='交通費', icon='train', color='#2196F3'),
                    ExpenseCategory(name='日用品', icon='local_grocery_store', color='#4CAF50'),
                    ExpenseCategory(name='衣服・美容', icon='checkroom', color='#E91E63'),
                    ExpenseCategory(name='医療・健康', icon='local_hospital', color='#F44336'),
                    ExpenseCategory(name='教育・学習', icon='school', color='#9C27B0'),
                    ExpenseCategory(name='娯楽・趣味', icon='sports_esports', color='#FF5722'),
                    ExpenseCategory(name='光熱費', icon='flash_on', color='#FFC107'),
                    ExpenseCategory(name='通信費', icon='wifi', color='#607D8B'),
                    ExpenseCategory(name='住居費', icon='home', color='#795548'),
                    ExpenseCategory(name='保険', icon='security', color='#3F51B5'),
                    ExpenseCategory(name='税金', icon='account_balance', color='#009688'),
                    ExpenseCategory(name='その他', icon='category', color='#666666')
                ]
                
                for category in default_expense_categories:
                    db.session.add(category)
            
            try:
                income_count = db.session.query(IncomeCategory).count()
            except:
                income_count = 0
                
            if income_count == 0:
                default_income_categories = [
                    IncomeCategory(name='給与', icon='work', color='#4CAF50'),
                    IncomeCategory(name='副業', icon='business_center', color='#2196F3'),
                    IncomeCategory(name='投資・配当', icon='trending_up', color='#FF9800'),
                    IncomeCategory(name='年金', icon='elderly', color='#9C27B0'),
                    IncomeCategory(name='賞与・ボーナス', icon='card_giftcard', color='#E91E63'),
                    IncomeCategory(name='臨時収入', icon='volunteer_activism', color='#FF5722'),
                    IncomeCategory(name='その他', icon='attach_money', color='#4CAF50')
                ]
                
                for category in default_income_categories:
                    db.session.add(category)
            
            db.session.commit()
            
            print("データベース初期化完了")
            
        except Exception as e:
            print(f"データベース初期化エラー: {e}")
            import traceback
            traceback.print_exc()
        
    app.run(host='0.0.0.0', port=8203, debug=True) 