from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory, make_response
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
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lifeplan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# セッション設定（アプリ対応）
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)  # 30日間有効
app.config['SESSION_COOKIE_SECURE'] = False  # HTTPSでない場合はFalse
app.config['SESSION_COOKIE_HTTPONLY'] = True  # XSS攻撃対策
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF攻撃対策

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

class BusinessIncomes(db.Model):
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
    income_increase_rate = db.Column(db.Float, default=5.0)  # デフォルト5%（事業は成長が期待される）
    
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
    income_type = db.Column(db.String(20), nullable=False)  # 'salary', 'sidejob', 'business', 'investment', 'pension', 'other'
    income_id = db.Column(db.Integer, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# グローバルコンテキストプロセッサー
@app.context_processor
def inject_client_info():
    """全てのテンプレートでクライアント情報を利用可能にする"""
    return dict(client_info=get_client_info())

# User-Agent識別のヘルパー関数
def get_client_info():
    """
    リクエストのUser-Agentを解析してクライアント情報を返す
    """
    user_agent = request.headers.get('User-Agent', '')
    
    client_info = {
        'user_agent': user_agent,
        'is_mobile': False,
        'is_ios': False,
        'is_android': False,
        'is_app': False,
        'is_browser': True,
        'device_type': 'desktop',
        'browser': 'unknown',
        'os': 'unknown',
        'app_version': None
    }
    
    # モバイルデバイスの検出
    mobile_patterns = [
        r'Mobile', r'Android', r'iPhone', r'iPad', r'iPod',
        r'BlackBerry', r'Windows Phone', r'Opera Mini'
    ]
    
    for pattern in mobile_patterns:
        if re.search(pattern, user_agent, re.IGNORECASE):
            client_info['is_mobile'] = True
            break
    
    # OS の検出
    if re.search(r'iPhone|iPad|iPod', user_agent, re.IGNORECASE):
        client_info['is_ios'] = True
        client_info['os'] = 'iOS'
        client_info['device_type'] = 'mobile' if 'iPhone' in user_agent or 'iPod' in user_agent else 'tablet'
    elif re.search(r'Android', user_agent, re.IGNORECASE):
        client_info['is_android'] = True
        client_info['os'] = 'Android'
        client_info['device_type'] = 'mobile'
    elif re.search(r'Windows', user_agent, re.IGNORECASE):
        client_info['os'] = 'Windows'
    elif re.search(r'Mac', user_agent, re.IGNORECASE):
        client_info['os'] = 'macOS'
    elif re.search(r'Linux', user_agent, re.IGNORECASE):
        client_info['os'] = 'Linux'
    
    # ブラウザの検出
    if re.search(r'Chrome', user_agent, re.IGNORECASE):
        client_info['browser'] = 'Chrome'
    elif re.search(r'Safari', user_agent, re.IGNORECASE) and not re.search(r'Chrome', user_agent, re.IGNORECASE):
        client_info['browser'] = 'Safari'
    elif re.search(r'Firefox', user_agent, re.IGNORECASE):
        client_info['browser'] = 'Firefox'
    elif re.search(r'Edge', user_agent, re.IGNORECASE):
        client_info['browser'] = 'Edge'
    
    # アプリからのアクセスの検出
    # カスタムUser-Agentでアプリを識別
    if re.search(r'LifePlanApp', user_agent, re.IGNORECASE):
        client_info['is_app'] = True
        client_info['is_browser'] = False
        # バージョン情報を抽出
        version_match = re.search(r'LifePlanApp/(\d+\.\d+(?:\.\d+)?)', user_agent)
        if version_match:
            client_info['app_version'] = version_match.group(1)
        
        # 画面サイズ情報を抽出
        screen_match = re.search(r'Screen/(\d+)x(\d+)', user_agent)
        if screen_match:
            client_info['screen_width'] = int(screen_match.group(1))
            client_info['screen_height'] = int(screen_match.group(2))
        
        # スケール情報を抽出
        scale_match = re.search(r'Scale/(\d+(?:\.\d+)?)', user_agent)
        if scale_match:
            client_info['screen_scale'] = float(scale_match.group(1))
    
    # WebViewの検出（アプリ内ブラウザ）
    if re.search(r'wv\)|WebView', user_agent, re.IGNORECASE):
        client_info['is_app'] = True  # WebViewもアプリとして扱う
        client_info['is_browser'] = False
    
    return client_info

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
        remember_me = data.get('remember_me', False)
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            # クライアント情報を取得
            client_info = get_client_info()
            
            # アプリからのアクセスの場合は自動的にremember_meをTrueに
            if client_info['is_app']:
                remember_me = True
                session.permanent = True
            
            login_user(user, remember=remember_me)
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

@app.route('/incomes/business')
@login_required
def incomes_business():
    return render_template('incomes/business.html')

@app.route('/incomes/business/new')
@login_required
def incomes_business_new():
    return render_template('incomes/business_form.html', income_id=None)

@app.route('/incomes/business/edit/<int:income_id>')
@login_required
def incomes_business_edit(income_id):
    return render_template('incomes/business_form.html', income_id=income_id)

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



@app.route('/household-swipe')
@login_required
def household_swipe():
    """家計簿（スワイプ版）"""
    return render_template('household_swipe.html')

@app.route('/household-swipe-dev')
@login_required
def household_swipe_dev():
    """家計簿開発版（スワイプ版）"""
    return render_template('household_swipe_dev.html')

@app.route('/mypage')
@login_required
def mypage():
    return render_template('mypage.html')

@app.route('/test-menu')
@login_required
def test_menu():
    return render_template('test_menu.html')

# 家計簿機能のルーティング
@app.route('/account-management')
@login_required
def account_management():
    expense_categories = ExpenseCategory.query.order_by(ExpenseCategory.id).all()
    return render_template('account_management.html', expense_categories=expense_categories)

@app.route('/household-books')
@login_required
def household_books():
    """家計簿：今月の家計簿にリダイレクト"""
    # 現在の年月を取得して月次家計簿にリダイレクト
    current_date = datetime.now()
    return redirect(url_for('household_book_monthly', year=current_date.year, month=current_date.month))

@app.route('/household-calendar')
@app.route('/household-calendar/<int:year>/<int:month>')
@login_required
def household_calendar(year=None, month=None):
    """家計簿カレンダー表示ページ"""
    try:
        # 現在の日付をデフォルトに設定
        if year is None or month is None:
            current_date = datetime.now()
            year = current_date.year
            month = current_date.month
        
        # カテゴリを取得（なければデフォルトを作成）
        expense_categories = ExpenseCategory.query.all()
        income_categories = IncomeCategory.query.all()
        
        # デフォルトカテゴリが存在しない場合は作成
        if not expense_categories:
            default_expense_categories = [
                {'name': '食費', 'icon': 'restaurant', 'color': '#FF5722'},
                {'name': '交通費', 'icon': 'directions_car', 'color': '#2196F3'},
                {'name': '娯楽', 'icon': 'movie', 'color': '#9C27B0'},
                {'name': '光熱費', 'icon': 'bolt', 'color': '#FF9800'},
                {'name': 'その他', 'icon': 'category', 'color': '#666666'}
            ]
            for cat_data in default_expense_categories:
                category = ExpenseCategory(**cat_data)
                db.session.add(category)
            db.session.commit()
            expense_categories = ExpenseCategory.query.all()
        
        if not income_categories:
            default_income_categories = [
                {'name': '給与', 'icon': 'work', 'color': '#4CAF50'},
                {'name': '副業', 'icon': 'business_center', 'color': '#8BC34A'},
                {'name': 'その他', 'icon': 'attach_money', 'color': '#4CAF50'}
            ]
            for cat_data in default_income_categories:
                category = IncomeCategory(**cat_data)
                db.session.add(category)
            db.session.commit()
            income_categories = IncomeCategory.query.all()
        
        return render_template('household_calendar.html',
                             expense_categories=expense_categories,
                             income_categories=income_categories,
                             current_year=year,
                             current_month=month)
    except Exception as e:
        app.logger.error(f"家計簿カレンダー表示エラー: {str(e)}")
        return render_template('error.html', error="カレンダー表示に失敗しました。"), 500

@app.route('/api/calendar-entries/<int:year>/<int:month>')
@login_required
def api_calendar_entries(year, month):
    """カレンダー用の月次エントリー取得API"""
    try:
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
        
        # 指定年月の範囲を設定
        from calendar import monthrange
        month_start = date(year, month, 1)
        _, last_day = monthrange(year, month)
        month_end = date(year, month, last_day)
        
        # エントリーを取得（指定年月の範囲内のみ）
        entries = HouseholdEntry.query.filter_by(household_book_id=household_book.id)\
            .filter(HouseholdEntry.entry_date >= month_start)\
            .filter(HouseholdEntry.entry_date <= month_end)\
            .order_by(HouseholdEntry.entry_date.desc()).all()
        
        # 日付別にグループ化
        entries_by_date = {}
        total_income = 0
        total_expense = 0
        
        for entry in entries:
            date_str = entry.entry_date.strftime('%Y-%m-%d')
            if date_str not in entries_by_date:
                entries_by_date[date_str] = []
            
            entry_data = {
                'id': entry.id,
                'entry_type': entry.entry_type,
                'amount': entry.amount,
                'description': entry.description or '',
                'category': entry.expense_category.name if entry.expense_category else (entry.income_category.name if entry.income_category else ''),
                'category_icon': entry.expense_category.icon if entry.expense_category else (entry.income_category.icon if entry.income_category else 'category'),
                'category_color': entry.expense_category.color if entry.expense_category else (entry.income_category.color if entry.income_category else '#666666'),
                'income_category_id': entry.income_category_id,
                'expense_category_id': entry.expense_category_id
            }
            entries_by_date[date_str].append(entry_data)
            
            if entry.entry_type == 'income':
                total_income += entry.amount
            else:
                total_expense += entry.amount
        
        return jsonify({
            'success': True,
            'entries': entries_by_date,
            'summary': {
                'total_income': total_income,
                'total_expense': total_expense,
                'balance': total_income - total_expense
            },
            'household_book_id': household_book.id
        })
        
    except Exception as e:
        app.logger.error(f"カレンダーエントリー取得エラー: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/daily-entries/<int:year>/<int:month>/<int:day>')
@login_required
def api_daily_entries(year, month, day):
    """指定日のエントリー詳細取得API"""
    try:
        # 指定年月の家計簿を取得
        household_book = HouseholdBook.query.filter_by(
            user_id=current_user.id, year=year, month=month
        ).first()
        
        if not household_book:
            return jsonify({
                'success': True,
                'entries': [],
                'daily_total': {'income': 0, 'expense': 0, 'balance': 0}
            })
        
        # 指定日のエントリーを取得
        target_date = date(year, month, day)
        entries = HouseholdEntry.query.filter_by(
            household_book_id=household_book.id,
            entry_date=target_date
        ).order_by(HouseholdEntry.created_at.desc()).all()
        
        # エントリーデータを整形
        entries_data = []
        daily_income = 0
        daily_expense = 0
        
        for entry in entries:
            entry_data = {
                'id': entry.id,
                'entry_type': entry.entry_type,
                'amount': entry.amount,
                'description': entry.description or '',
                'category': entry.expense_category.name if entry.expense_category else (entry.income_category.name if entry.income_category else ''),
                'category_icon': entry.expense_category.icon if entry.expense_category else (entry.income_category.icon if entry.income_category else 'category'),
                'category_color': entry.expense_category.color if entry.expense_category else (entry.income_category.color if entry.income_category else '#666666'),
                'income_category_id': entry.income_category_id,
                'expense_category_id': entry.expense_category_id,
                'created_at': entry.created_at.strftime('%H:%M')
            }
            entries_data.append(entry_data)
            
            if entry.entry_type == 'income':
                daily_income += entry.amount
            else:
                daily_expense += entry.amount
        
        return jsonify({
            'success': True,
            'entries': entries_data,
            'daily_total': {
                'income': daily_income,
                'expense': daily_expense,
                'balance': daily_income - daily_expense
            },
            'date': target_date.strftime('%Y年%m月%d日')
        })
        
    except Exception as e:
        app.logger.error(f"日次エントリー取得エラー: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/household-menu')
@login_required
def household_menu():
    """
    家計簿メニューページ
    """
    try:
        # 現在の年月を取得
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month
        
        # 最新の家計簿エントリを10件取得
        recent_entries = HouseholdEntry.query.filter_by(user_id=current_user.id)\
            .order_by(HouseholdEntry.entry_date.desc(), HouseholdEntry.created_at.desc())\
            .limit(10).all()
        
        # 今月の統計を計算
        month_start = date(current_year, current_month, 1)
        if current_month == 12:
            month_end = date(current_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(current_year, current_month + 1, 1) - timedelta(days=1)
        
        # 今月の収入・支出を集計
        monthly_entries = HouseholdEntry.query.filter_by(user_id=current_user.id)\
            .filter(HouseholdEntry.entry_date >= month_start)\
            .filter(HouseholdEntry.entry_date <= month_end).all()
        
        monthly_income = sum(entry.amount for entry in monthly_entries if entry.entry_type == 'income')
        monthly_expense = sum(entry.amount for entry in monthly_entries if entry.entry_type == 'expense')
        monthly_balance = monthly_income - monthly_expense
        
        # カテゴリ別の支出統計
        expense_categories = {}
        income_categories = {}
        
        for entry in monthly_entries:
            if entry.entry_type == 'expense' and entry.expense_category:
                cat_name = entry.expense_category.name
                if cat_name not in expense_categories:
                    expense_categories[cat_name] = {
                        'total': 0,
                        'icon': entry.expense_category.icon,
                        'color': entry.expense_category.color
                    }
                expense_categories[cat_name]['total'] += entry.amount
            elif entry.entry_type == 'income' and entry.income_category:
                cat_name = entry.income_category.name
                if cat_name not in income_categories:
                    income_categories[cat_name] = {
                        'total': 0,
                        'icon': entry.income_category.icon,
                        'color': entry.income_category.color
                    }
                income_categories[cat_name]['total'] += entry.amount
        
        # テンプレートに渡すデータ
        template_data = {
            'current_year': current_year,
            'current_month': current_month,
            'monthly_income': monthly_income,
            'monthly_expense': monthly_expense,
            'monthly_balance': monthly_balance,
            'recent_entries': recent_entries,
            'expense_categories': expense_categories,
            'income_categories': income_categories
        }
        
        return render_template('household_menu.html', **template_data)
        
    except Exception as e:
        app.logger.error(f"家計簿メニューエラー: {str(e)}")
        flash('家計簿メニューの読み込み中にエラーが発生しました', 'error')
        return redirect(url_for('dashboard'))

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
                         balance=balance,
                         year=year,
                         month=month)

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
        
        # 教育費を自動計算
        costs = calculate_education_costs(
            education_plan.child_birth_date,
            education_plan.kindergarten_type,
            education_plan.elementary_type,
            education_plan.junior_type,
            education_plan.high_type,
            education_plan.college_type
        )
        
        # 各教育段階のレコードを作成
        stages = [
            ('kindergarten', education_plan.kindergarten_type.value, costs['kindergarten_monthly'], costs['kindergarten_start_year'], costs['kindergarten_end_year']),
            ('elementary', education_plan.elementary_type.value, costs['elementary_monthly'], costs['elementary_start_year'], costs['elementary_end_year']),
            ('junior', education_plan.junior_type.value, costs['junior_monthly'], costs['junior_start_year'], costs['junior_end_year']),
            ('high', education_plan.high_type.value, costs['high_monthly'], costs['high_start_year'], costs['high_end_year']),
            ('college', education_plan.college_type.value, costs['college_monthly'], costs['college_start_year'], costs['college_end_year'])
        ]
        
        created_expenses = []
        for stage, stage_type, monthly_amount, start_year, end_year in stages:
            # 費用が0または期間が無効な場合はスキップ
            if monthly_amount <= 0 or start_year <= 0 or end_year <= 0:
                continue
                
            # "進学しない"や"未就園"の場合もスキップ
            if stage_type in ['進学しない', '未就園']:
                continue
            
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
            'created_count': len(created_expenses)
        })
    
    elif request.method == 'PUT':
        # 統合プランの編集機能
        try:
            data = request.get_json()
            plan_id = data.get('id')
            
            if not plan_id:
                return jsonify({'success': False, 'message': 'プランIDが指定されていません'}), 400
            
            # 既存の教育プランを取得
            education_plan = EducationPlans.query.filter_by(id=plan_id, user_id=current_user.id).first()
            if not education_plan:
                return jsonify({'success': False, 'message': '指定された教育プランが見つかりません'}), 404
            
            # 教育プランの基本情報を更新
            education_plan.name = data.get('name', education_plan.name)
            education_plan.description = data.get('description', education_plan.description)
            
            # 子供情報の更新（生年月日が変わる場合は期間も再計算）
            old_birth_date = education_plan.child_birth_date
            new_child_name = data.get('child_name', education_plan.child_name)
            new_birth_date = datetime.strptime(data.get('child_birth_date'), '%Y-%m-%d').date() if data.get('child_birth_date') else old_birth_date
            
            education_plan.child_name = new_child_name
            education_plan.child_birth_date = new_birth_date
            
            # 教育段階の選択を更新
            education_plan.kindergarten_type = KindergartenType(data.get('kindergarten_type', education_plan.kindergarten_type.value))
            education_plan.elementary_type = ElementaryType(data.get('elementary_type', education_plan.elementary_type.value))
            education_plan.junior_type = JuniorType(data.get('junior_type', education_plan.junior_type.value))
            education_plan.high_type = HighType(data.get('high_type', education_plan.high_type.value))
            education_plan.college_type = CollegeType(data.get('college_type', education_plan.college_type.value))
            
            # 既存の教育費レコードを削除
            existing_expenses = EducationExpenses.query.filter_by(education_plan_id=education_plan.id).all()
            for expense in existing_expenses:
                db.session.delete(expense)
            
            # 新しい教育費を再計算・再作成
            costs = calculate_education_costs(
                education_plan.child_birth_date,
                education_plan.kindergarten_type,
                education_plan.elementary_type,
                education_plan.junior_type,
                education_plan.high_type,
                education_plan.college_type
            )
            
            # 各教育段階のレコードを再作成
            stages = [
                ('kindergarten', education_plan.kindergarten_type.value, costs['kindergarten_monthly'], costs['kindergarten_start_year'], costs['kindergarten_end_year']),
                ('elementary', education_plan.elementary_type.value, costs['elementary_monthly'], costs['elementary_start_year'], costs['elementary_end_year']),
                ('junior', education_plan.junior_type.value, costs['junior_monthly'], costs['junior_start_year'], costs['junior_end_year']),
                ('high', education_plan.high_type.value, costs['high_monthly'], costs['high_start_year'], costs['high_end_year']),
                ('college', education_plan.college_type.value, costs['college_monthly'], costs['college_start_year'], costs['college_end_year'])
            ]
            
            updated_expenses = []
            for stage, stage_type, monthly_amount, start_year, end_year in stages:
                # 費用が0または期間が無効な場合はスキップ
                if monthly_amount <= 0 or start_year <= 0 or end_year <= 0:
                    continue
                    
                # "進学しない"や"未就園"の場合もスキップ
                if stage_type in ['進学しない', '未就園']:
                    continue
                
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
                updated_expenses.append(expense)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': '教育費プランを更新しました',
                'updated_count': len(updated_expenses)
            })
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'教育費プラン更新エラー: {str(e)}')
            return jsonify({'success': False, 'message': f'更新中にエラーが発生しました: {str(e)}'}), 500
    
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

@app.route('/api/education-expenses/<int:plan_id>/detail', methods=['GET'])
@login_required
def api_education_plan_detail(plan_id):
    """統合プランの詳細情報を取得（編集用）"""
    try:
        education_plan = EducationPlans.query.filter_by(id=plan_id, user_id=current_user.id).first()
        if not education_plan:
            return jsonify({'success': False, 'message': '指定された教育プランが見つかりません'}), 404
        
        # 関連する教育費を取得
        expenses = EducationExpenses.query.filter_by(education_plan_id=education_plan.id).all()
        
        # 各段階の詳細情報
        stages_detail = []
        for expense in expenses:
            stages_detail.append({
                'id': expense.id,
                'name': expense.name,
                'start_year': expense.start_year,
                'end_year': expense.end_year,
                'monthly_amount': expense.monthly_amount,
                'stage': expense.stage,
                'stage_type': expense.stage_type
            })
        
        # 統合プランの詳細情報を返す
        plan_detail = {
            'id': education_plan.id,
            'name': education_plan.name,
            'description': education_plan.description,
            'child_name': education_plan.child_name,
            'child_birth_date': education_plan.child_birth_date.isoformat(),
            'kindergarten_type': education_plan.kindergarten_type.value,
            'elementary_type': education_plan.elementary_type.value,
            'junior_type': education_plan.junior_type.value,
            'high_type': education_plan.high_type.value,
            'college_type': education_plan.college_type.value,
            'stages': stages_detail,
            'total_monthly_amount': sum(e.monthly_amount for e in expenses),
            'created_at': education_plan.created_at.isoformat()
        }
        
        return jsonify({
            'success': True,
            'plan': plan_detail
        })
        
    except Exception as e:
        app.logger.error(f'教育プラン詳細取得エラー: {str(e)}')
        return jsonify({'success': False, 'message': f'詳細取得中にエラーが発生しました: {str(e)}'}), 500

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

# API Routes for Incomes
@app.route('/api/salary-incomes', methods=['GET', 'POST', 'PUT'])
@login_required
def api_salary_incomes():
    if request.method == 'POST':
        data = request.get_json()
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        annual_bonus = float(data.get('annual_bonus', 0) or 0)
        annual_amount = monthly_amount * 12 + annual_bonus
        
        income = SalaryIncomes(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            monthly_amount=monthly_amount,
            annual_bonus=annual_bonus,
            annual_amount=annual_amount,
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            salary_increase_rate=float(data.get('salary_increase_rate', 3.0)),
            has_cap=bool(data.get('has_cap', False)),
            annual_income_cap=float(data.get('annual_income_cap', 0) or 0)
        )
        
        db.session.add(income)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '給与収入を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        income_id = data.get('id')
        
        if not income_id:
            return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
        
        income = SalaryIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
        if not income:
            return jsonify({'success': False, 'message': '指定された給与収入が見つかりません'}), 404
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        annual_bonus = float(data.get('annual_bonus', 0) or 0)
        annual_amount = monthly_amount * 12 + annual_bonus
        
        # Update income data
        income.name = data.get('name')
        income.description = data.get('description')
        income.monthly_amount = monthly_amount
        income.annual_bonus = annual_bonus
        income.annual_amount = annual_amount
        income.start_year = int(data.get('start_year', 0))
        income.end_year = int(data.get('end_year', 0))
        income.salary_increase_rate = float(data.get('salary_increase_rate', 3.0))
        income.has_cap = bool(data.get('has_cap', False))
        income.annual_income_cap = float(data.get('annual_income_cap', 0) or 0)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '給与収入を更新しました'})
    
    else:
        incomes = SalaryIncomes.query.filter_by(user_id=current_user.id).all()
        return jsonify([{
            'id': i.id,
            'name': i.name,
            'description': i.description,
            'monthly_amount': i.monthly_amount,
            'annual_bonus': i.annual_bonus,
            'annual_amount': i.annual_amount,
            'start_year': i.start_year,
            'end_year': i.end_year,
            'salary_increase_rate': i.salary_increase_rate,
            'has_cap': i.has_cap if hasattr(i, 'has_cap') else False,
            'annual_income_cap': i.annual_income_cap if hasattr(i, 'annual_income_cap') else 0
        } for i in incomes])

# Delete APIs
@app.route('/api/living-expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def api_delete_living_expense(expense_id):
    expense = LivingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not expense:
        return jsonify({'success': False, 'message': '支出データが見つかりません'}), 404
    
    db.session.delete(expense)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '生活費を削除しました'})

@app.route('/api/salary-incomes/<int:income_id>', methods=['DELETE'])
@login_required
def api_delete_salary_income(income_id):
    income = SalaryIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if not income:
        return jsonify({'success': False, 'message': '収入データが見つかりません'}), 404
    
    db.session.delete(income)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '給与収入を削除しました'})

# Copy APIs - IDのみを変更して中身をそのまま複製
@app.route('/api/living-expenses/<int:expense_id>/copy', methods=['POST'])
@login_required
def api_copy_living_expense(expense_id):
    # 元のデータを取得
    original = LivingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': '支出データが見つかりません'}), 404
    
    # 新しいデータを作成（IDを除いて全てコピー）
    new_expense = LivingExpenses(
        user_id=current_user.id,
        name=original.name + ' (コピー)',
        description=original.description,
        start_year=original.start_year,
        end_year=original.end_year,
        inflation_rate=original.inflation_rate if hasattr(original, 'inflation_rate') else 2.0,
        food_home=original.food_home if hasattr(original, 'food_home') else 0,
        food_outside=original.food_outside if hasattr(original, 'food_outside') else 0,
        utility_electricity=original.utility_electricity if hasattr(original, 'utility_electricity') else 0,
        utility_gas=original.utility_gas if hasattr(original, 'utility_gas') else 0,
        utility_water=original.utility_water if hasattr(original, 'utility_water') else 0,
        subscription_services=original.subscription_services if hasattr(original, 'subscription_services') else 0,
        internet=original.internet if hasattr(original, 'internet') else 0,
        phone=original.phone if hasattr(original, 'phone') else 0,
        household_goods=original.household_goods if hasattr(original, 'household_goods') else 0,
        hygiene=original.hygiene if hasattr(original, 'hygiene') else 0,
        clothing=original.clothing if hasattr(original, 'clothing') else 0,
        beauty=original.beauty if hasattr(original, 'beauty') else 0,
        child_food=original.child_food if hasattr(original, 'child_food') else 0,
        child_clothing=original.child_clothing if hasattr(original, 'child_clothing') else 0,
        child_medical=original.child_medical if hasattr(original, 'child_medical') else 0,
        child_other=original.child_other if hasattr(original, 'child_other') else 0,
        transport=original.transport if hasattr(original, 'transport') else 0,
        entertainment=original.entertainment if hasattr(original, 'entertainment') else 0,
        pet_costs=original.pet_costs if hasattr(original, 'pet_costs') else 0,
        other_expenses=original.other_expenses if hasattr(original, 'other_expenses') else 0,
        monthly_total_amount=original.monthly_total_amount if hasattr(original, 'monthly_total_amount') else 0
    )
    
    db.session.add(new_expense)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '生活費をコピーしました',
        'new_id': new_expense.id
    })

@app.route('/api/housing-expenses/<int:expense_id>/copy', methods=['POST'])
@login_required
def api_copy_housing_expense(expense_id):
    # 元のデータを取得
    original = HousingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': '住宅費データが見つかりません'}), 404
    
    # 新しいデータを作成（IDを除いて全てコピー）
    new_expense = HousingExpenses(
        user_id=current_user.id,
        name=original.name + ' (コピー)',
        description=original.description,
        start_year=original.start_year,
        end_year=original.end_year,
        residence_type=original.residence_type,
        rent_monthly=original.rent_monthly if hasattr(original, 'rent_monthly') else 0,
        mortgage_monthly=original.mortgage_monthly if hasattr(original, 'mortgage_monthly') else 0,
        property_tax_monthly=original.property_tax_monthly if hasattr(original, 'property_tax_monthly') else 0,
        management_fee_monthly=original.management_fee_monthly if hasattr(original, 'management_fee_monthly') else 0,
        repair_reserve_monthly=original.repair_reserve_monthly if hasattr(original, 'repair_reserve_monthly') else 0,
        fire_insurance_monthly=original.fire_insurance_monthly if hasattr(original, 'fire_insurance_monthly') else 0,
        purchase_price=original.purchase_price if hasattr(original, 'purchase_price') else 0,
        down_payment=original.down_payment if hasattr(original, 'down_payment') else 0,
        loan_interest_rate=original.loan_interest_rate if hasattr(original, 'loan_interest_rate') else 0,
        loan_term_years=original.loan_term_years if hasattr(original, 'loan_term_years') else 0,
        repayment_method=original.repayment_method if hasattr(original, 'repayment_method') else None,
        monthly_total_amount=original.monthly_total_amount if hasattr(original, 'monthly_total_amount') else 0
    )
    
    db.session.add(new_expense)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '住宅費をコピーしました',
        'new_id': new_expense.id
    })

@app.route('/api/salary-incomes/<int:income_id>/copy', methods=['POST'])
@login_required
def api_copy_salary_income(income_id):
    # 元のデータを取得
    original = SalaryIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': '給与収入データが見つかりません'}), 404
    
    # 新しいデータを作成（IDを除いて全てコピー）
    new_income = SalaryIncomes(
        user_id=current_user.id,
        name=original.name + ' (コピー)',
        description=original.description,
        monthly_amount=original.monthly_amount,
        annual_bonus=original.annual_bonus,
        annual_amount=original.annual_amount,
        start_year=original.start_year,
        end_year=original.end_year,
        salary_increase_rate=original.salary_increase_rate if hasattr(original, 'salary_increase_rate') else 3.0,
        has_cap=original.has_cap if hasattr(original, 'has_cap') else False,
        annual_income_cap=original.annual_income_cap if hasattr(original, 'annual_income_cap') else 0
    )
    
    db.session.add(new_income)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '給与収入をコピーしました',
        'new_id': new_income.id
    })

@app.route('/api/sidejob-incomes/<int:income_id>/copy', methods=['POST'])
@login_required
def api_copy_sidejob_income(income_id):
    # 元のデータを取得
    original = SidejobIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': '副業収入データが見つかりません'}), 404
    
    # 新しいデータを作成（IDを除いて全てコピー）
    new_income = SidejobIncomes(
        user_id=current_user.id,
        name=original.name + ' (コピー)',
        description=original.description,
        monthly_amount=original.monthly_amount,
        annual_amount=original.annual_amount,
        start_year=original.start_year,
        end_year=original.end_year,
        income_increase_rate=original.income_increase_rate if hasattr(original, 'income_increase_rate') else 0.0,
        has_cap=original.has_cap if hasattr(original, 'has_cap') else False,
        annual_income_cap=original.annual_income_cap if hasattr(original, 'annual_income_cap') else 0
    )
    
    db.session.add(new_income)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '副業収入をコピーしました',
        'new_id': new_income.id
    })

@app.route('/api/investment-incomes/<int:income_id>/copy', methods=['POST'])
@login_required
def api_copy_investment_income(income_id):
    # 元のデータを取得
    original = InvestmentIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': '投資収入データが見つかりません'}), 404
    
    # 新しいデータを作成（IDを除いて全てコピー）
    new_income = InvestmentIncomes(
        user_id=current_user.id,
        name=original.name + ' (コピー)',
        description=original.description,
        monthly_amount=original.monthly_amount,
        annual_amount=original.annual_amount,
        start_year=original.start_year,
        end_year=original.end_year,
        annual_return_rate=original.annual_return_rate if hasattr(original, 'annual_return_rate') else 5.0
    )
    
    db.session.add(new_income)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '投資収入をコピーしました',
        'new_id': new_income.id
    })

@app.route('/api/pension-incomes/<int:income_id>/copy', methods=['POST'])
@login_required
def api_copy_pension_income(income_id):
    # 元のデータを取得
    original = PensionIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': '年金収入データが見つかりません'}), 404
    
    # 新しいデータを作成（IDを除いて全てコピー）
    new_income = PensionIncomes(
        user_id=current_user.id,
        name=original.name + ' (コピー)',
        description=original.description,
        monthly_amount=original.monthly_amount,
        annual_amount=original.annual_amount,
        start_year=original.start_year,
        end_year=original.end_year
    )
    
    db.session.add(new_income)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '年金収入をコピーしました',
        'new_id': new_income.id
    })

@app.route('/api/other-incomes/<int:income_id>/copy', methods=['POST'])
@login_required
def api_copy_other_income(income_id):
    # 元のデータを取得
    original = OtherIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': 'その他収入データが見つかりません'}), 404
    
    # 新しいデータを作成（IDを除いて全てコピー）
    new_income = OtherIncomes(
        user_id=current_user.id,
        name=original.name + ' (コピー)',
        description=original.description,
        monthly_amount=original.monthly_amount,
        annual_amount=original.annual_amount,
        start_year=original.start_year,
        end_year=original.end_year
    )
    
    db.session.add(new_income)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': 'その他収入をコピーしました',
        'new_id': new_income.id
    })

@app.route('/api/business-incomes/<int:income_id>/copy', methods=['POST'])
@login_required
def api_copy_business_income(income_id):
    # 元のデータを取得
    original = BusinessIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': '事業収入データが見つかりません'}), 404
    
    # 新しいデータを作成（IDを除いて全てコピー）
    new_income = BusinessIncomes(
        user_id=current_user.id,
        name=original.name + ' (コピー)',
        description=original.description,
        monthly_amount=original.monthly_amount,
        annual_amount=original.annual_amount,
        start_year=original.start_year,
        end_year=original.end_year,
        income_increase_rate=original.income_increase_rate,
        has_cap=original.has_cap,
        annual_income_cap=original.annual_income_cap
    )
    
    db.session.add(new_income)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': '事業収入をコピーしました',
        'new_id': new_income.id
    })

# Simulation API
# 保険費用API
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

# イベント費用API
@app.route('/api/event-expenses', methods=['GET', 'POST', 'PUT'])
@login_required
def api_event_expenses():
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'success': False, 'message': 'データが送信されていません'}), 400
            
            # 必須フィールドの検証
            required_fields = ['name', 'category', 'start_year', 'end_year', 'amount']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'message': f'{field}は必須項目です'}), 400
            
            # カテゴリの検証
            try:
                category = EventCategory(data.get('category'))
            except ValueError:
                return jsonify({'success': False, 'message': '無効なカテゴリが指定されました'}), 400
            
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
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'イベント費登録エラー: {str(e)}')
            return jsonify({'success': False, 'message': f'登録に失敗しました: {str(e)}'}), 500
    
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'success': False, 'message': 'データが送信されていません'}), 400
                
            expense_id = data.get('id')
            
            if not expense_id:
                return jsonify({'success': False, 'message': 'IDが指定されていません'}), 400
            
            expense = EventExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
            if not expense:
                return jsonify({'success': False, 'message': '指定されたイベントが見つかりません'}), 404
            
            # 必須フィールドの検証
            required_fields = ['name', 'category', 'start_year', 'end_year', 'amount']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'message': f'{field}は必須項目です'}), 400
            
            # カテゴリの検証
            try:
                category = EventCategory(data.get('category'))
            except ValueError:
                return jsonify({'success': False, 'message': '無効なカテゴリが指定されました'}), 400
            
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
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'イベント費更新エラー: {str(e)}')
            return jsonify({'success': False, 'message': f'更新に失敗しました: {str(e)}'}), 500
    
    else:
        try:
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
                'recurrence_count': e.recurrence_count,
                'total_amount': e.amount  # 表示用
            } for e in expenses])
        except Exception as e:
            app.logger.error(f'イベント費取得エラー: {str(e)}')
            return jsonify({'success': False, 'message': f'データの取得に失敗しました: {str(e)}'}), 500

@app.route('/api/event-expenses/<int:expense_id>/copy', methods=['POST'])
@login_required
def api_copy_events_expense(expense_id):
    # 元のデータを取得
    original = EventExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': '元データが見つかりません'}), 404
    
    # コピーを作成
    copy = EventExpenses(
        user_id=current_user.id,
        name=original.name + ' (コピー)',
        description=original.description,
        start_year=original.start_year,
        end_year=original.end_year,
        category=original.category,
        amount=original.amount,
        is_recurring=original.is_recurring if hasattr(original, 'is_recurring') else False,
        recurrence_interval=original.recurrence_interval if hasattr(original, 'recurrence_interval') else 1,
        recurrence_count=original.recurrence_count if hasattr(original, 'recurrence_count') else 1
    )
    
    db.session.add(copy)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '特別費をコピーしました',
        'new_id': copy.id
    })

@app.route('/api/insurance-expenses/<int:expense_id>/copy', methods=['POST'])
@login_required
def api_copy_insurance_expense(expense_id):
    # 元のデータを取得
    original = InsuranceExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': '元データが見つかりません'}), 404
    
    # コピーを作成
    copy = InsuranceExpenses(
        user_id=current_user.id,
        name=original.name + ' (コピー)',
        description=original.description,
        start_year=original.start_year,
        end_year=original.end_year,
        medical_insurance=original.medical_insurance if hasattr(original, 'medical_insurance') else 0,
        cancer_insurance=original.cancer_insurance if hasattr(original, 'cancer_insurance') else 0,
        life_insurance=original.life_insurance if hasattr(original, 'life_insurance') else 0,
        income_protection=original.income_protection if hasattr(original, 'income_protection') else 0,
        accident_insurance=original.accident_insurance if hasattr(original, 'accident_insurance') else 0,
        liability_insurance=original.liability_insurance if hasattr(original, 'liability_insurance') else 0,
        fire_insurance=original.fire_insurance if hasattr(original, 'fire_insurance') else 0,
        long_term_care_insurance=original.long_term_care_insurance if hasattr(original, 'long_term_care_insurance') else 0,
        other_insurance=original.other_insurance if hasattr(original, 'other_insurance') else 0,
        insured_person=original.insured_person if hasattr(original, 'insured_person') else None,
        insurance_company=original.insurance_company if hasattr(original, 'insurance_company') else None,
        insurance_term_years=original.insurance_term_years if hasattr(original, 'insurance_term_years') else 0,
        renew_type=original.renew_type if hasattr(original, 'renew_type') else None,
        monthly_total_amount=original.monthly_total_amount if hasattr(original, 'monthly_total_amount') else 0
    )
    
    db.session.add(copy)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '保険費をコピーしました',
        'new_id': copy.id
    })

@app.route('/api/education-expenses/<int:expense_id>/copy', methods=['POST'])
@login_required
def api_copy_education_expense(expense_id):
    # 元のデータを取得
    original = EducationExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not original:
        return jsonify({'success': False, 'message': '教育費データが見つかりません'}), 404
    
    # 教育プランも一緒にコピー
    original_plan = original.education_plan
    if not original_plan:
        return jsonify({'success': False, 'message': '教育プランが見つかりません'}), 404
    
    # 新しい教育プランを作成
    new_plan = EducationPlans(
        user_id=current_user.id,
        name=original_plan.name + ' (コピー)',
        description=original_plan.description,
        child_name=original_plan.child_name,
        child_birth_date=original_plan.child_birth_date,
        kindergarten_type=original_plan.kindergarten_type if hasattr(original_plan, 'kindergarten_type') else None,
        elementary_type=original_plan.elementary_type if hasattr(original_plan, 'elementary_type') else None,
        junior_type=original_plan.junior_type if hasattr(original_plan, 'junior_type') else None,
        high_type=original_plan.high_type if hasattr(original_plan, 'high_type') else None,
        college_type=original_plan.college_type if hasattr(original_plan, 'college_type') else None
    )
    
    db.session.add(new_plan)
    db.session.flush()  # プランのIDを取得するためにflush
    
    # 新しい教育費を作成
    new_expense = EducationExpenses(
        user_id=current_user.id,
        education_plan_id=new_plan.id,
        name=original.name + ' (コピー)',
        description=original.description,
        start_year=original.start_year,
        end_year=original.end_year,
        child_name=original.child_name,
        child_birth_date=original.child_birth_date,
        stage=original.stage if hasattr(original, 'stage') else '',
        stage_type=original.stage_type if hasattr(original, 'stage_type') else '',
        monthly_amount=original.monthly_amount if hasattr(original, 'monthly_amount') else 0
    )
    
    db.session.add(new_expense)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': '教育費をコピーしました',
        'new_id': new_expense.id
    })

# 副業収入API
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
            'income_increase_rate': i.income_increase_rate if hasattr(i, 'income_increase_rate') else 0.0,
            'has_cap': i.has_cap if hasattr(i, 'has_cap') else False,
            'annual_income_cap': i.annual_income_cap if hasattr(i, 'annual_income_cap') else 0
        } for i in incomes])

# 投資収入API
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

# 年金収入API
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

# その他収入API
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

# 事業収入API
@app.route('/api/business-incomes', methods=['GET', 'POST', 'PUT'])
@login_required
def api_business_incomes():
    if request.method == 'POST':
        data = request.get_json()
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        income = BusinessIncomes(
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            monthly_amount=monthly_amount,
            annual_amount=monthly_amount * 12,
            start_year=int(data.get('start_year', 0)),
            end_year=int(data.get('end_year', 0)),
            income_increase_rate=float(data.get('income_increase_rate', 0) or 0),
            has_cap=bool(data.get('has_cap', False)),
            annual_income_cap=float(data.get('annual_income_cap', 0) or 0)
        )
        
        db.session.add(income)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '事業収入を登録しました'})
    
    elif request.method == 'PUT':
        data = request.get_json()
        income_id = data.get('id')
        
        income = BusinessIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
        if not income:
            return jsonify({'success': False, 'message': '事業収入が見つかりません'})
        
        monthly_amount = float(data.get('monthly_amount', 0) or 0)
        income.name = data.get('name')
        income.description = data.get('description')
        income.monthly_amount = monthly_amount
        income.annual_amount = monthly_amount * 12
        income.start_year = int(data.get('start_year', 0))
        income.end_year = int(data.get('end_year', 0))
        income.income_increase_rate = float(data.get('income_increase_rate', 0) or 0)
        income.has_cap = bool(data.get('has_cap', False))
        income.annual_income_cap = float(data.get('annual_income_cap', 0) or 0)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': '事業収入を更新しました'})
    
    else:
        incomes = BusinessIncomes.query.filter_by(user_id=current_user.id).all()
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

@app.route('/api/business-incomes/<int:income_id>', methods=['GET', 'DELETE'])
@login_required
def api_business_income_detail(income_id):
    income = BusinessIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
    if not income:
        return jsonify({'success': False, 'message': '事業収入が見つかりません'})
    
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'data': {
                'id': income.id,
                'name': income.name,
                'description': income.description,
                'monthly_amount': income.monthly_amount,
                'annual_amount': income.annual_amount,
                'start_year': income.start_year,
                'end_year': income.end_year,
                'income_increase_rate': income.income_increase_rate,
                'has_cap': income.has_cap,
                'annual_income_cap': income.annual_income_cap
            }
        })
    
    elif request.method == 'DELETE':
        db.session.delete(income)
        db.session.commit()
        return jsonify({'success': True, 'message': '事業収入を削除しました'})

# 削除API群
@app.route('/api/education-expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def api_delete_education_expense(expense_id):
    # 統合削除：教育プランIDで削除
    education_plan = EducationPlans.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if not education_plan:
        return jsonify({'success': False, 'message': '教育費が見つかりません'})
    
    # 関連する全ての教育費を削除
    related_expenses = EducationExpenses.query.filter_by(education_plan_id=education_plan.id).all()
    
    for expense in related_expenses:
        db.session.delete(expense)
    
    # 教育プランも削除
    db.session.delete(education_plan)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': f'{education_plan.child_name}の教育費（{len(related_expenses)}件）を削除しました'
    })

@app.route('/api/housing-expenses/<int:expense_id>', methods=['DELETE'])
@login_required
def api_delete_housing_expense(expense_id):
    expense = HousingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
    if expense:
        db.session.delete(expense)
        db.session.commit()
        return jsonify({'success': True, 'message': '住居費を削除しました'})
    return jsonify({'success': False, 'message': '住居費が見つかりません'})

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
    business_incomes = BusinessIncomes.query.filter_by(user_id=current_user.id).all()
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
        'business': [{
            'id': i.id, 'name': i.name, 'description': i.description,
            'start_year': i.start_year, 'end_year': i.end_year,
            'monthly_amount': i.monthly_amount, 'annual_amount': i.annual_amount
        } for i in business_incomes],
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
        
        # 選択された項目をタイプ別に整理
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
        # 関連するリンクを削除
        LifeplanExpenseLinks.query.filter_by(lifeplan_id=plan.id).delete()
        LifeplanIncomeLinks.query.filter_by(lifeplan_id=plan.id).delete()
        
        # プランを削除
        db.session.delete(plan)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'シミュレーションプランが削除されました'})

@app.route('/api/simulation-plans/<int:plan_id>/copy', methods=['POST'])
@login_required
def api_copy_simulation_plan(plan_id):
    # 元のプランを取得
    original_plan = LifeplanSimulations.query.filter_by(id=plan_id, user_id=current_user.id).first()
    if not original_plan:
        return jsonify({'success': False, 'message': 'プランが見つかりません'}), 404
    
    try:
        # 新しいプランを作成
        new_plan = LifeplanSimulations(
            user_id=current_user.id,
            name=original_plan.name + ' (コピー)',
            description=original_plan.description,
            base_age=original_plan.base_age,
            start_year=original_plan.start_year,
            end_year=original_plan.end_year
        )
        db.session.add(new_plan)
        db.session.flush()  # IDを取得するためにflush
        
        # 元のプランの支出リンクをコピー
        original_expense_links = LifeplanExpenseLinks.query.filter_by(lifeplan_id=plan_id).all()
        for link in original_expense_links:
            new_link = LifeplanExpenseLinks(
                lifeplan_id=new_plan.id,
                expense_type=link.expense_type,
                expense_id=link.expense_id
            )
            db.session.add(new_link)
        
        # 元のプランの収入リンクをコピー
        original_income_links = LifeplanIncomeLinks.query.filter_by(lifeplan_id=plan_id).all()
        for link in original_income_links:
            new_link = LifeplanIncomeLinks(
                lifeplan_id=new_plan.id,
                income_type=link.income_type,
                income_id=link.income_id
            )
            db.session.add(new_link)
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'シミュレーションプランをコピーしました'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'コピーに失敗しました: {str(e)}'}), 500

@app.route('/api/simulate', methods=['POST'])
@login_required
def api_simulate():
    try:
        data = request.get_json()
        
        # ログに実行開始を記録
        app.logger.info(f"シミュレーション開始 - ユーザー: {current_user.id}, データ: {data}")
        
        base_age = data.get('base_age')
        start_year = data.get('start_year')
        end_year = data.get('end_year')
        selected_expenses = data.get('selected_expenses', {})
        selected_incomes = data.get('selected_incomes', {})
        
        # バリデーション
        if not all([base_age, start_year, end_year]):
            error_msg = "必須パラメータが不足しています"
            app.logger.error(f"シミュレーションバリデーションエラー - ユーザー: {current_user.id}, エラー: {error_msg}")
            return jsonify({'error': True, 'message': error_msg}), 400
        
        if start_year >= end_year:
            error_msg = "開始年は終了年より前である必要があります"
            app.logger.error(f"シミュレーションバリデーションエラー - ユーザー: {current_user.id}, エラー: {error_msg}")
            return jsonify({'error': True, 'message': error_msg}), 400
        
        simulation_data = []
        cumulative_balance = 0
        total_income = 0
        total_expenses = 0
        
        for year in range(start_year, end_year + 1):
            age = base_age + (year - start_year)
            year_income = 0
            year_expenses = 0
            income_details = []
            expense_details = []
            
            # 収入計算
            try:
                if 'salary' in selected_incomes:
                    for income_id in selected_incomes['salary']:
                        income = SalaryIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
                        if income and income.start_year <= year <= income.end_year:
                            # 昇給率を適用した複利計算
                            years_passed = year - income.start_year
                            
                            # 月額給与の計算
                            monthly_with_increase = income.monthly_amount * ((1 + income.salary_increase_rate / 100) ** years_passed)
                            
                            # ボーナスの計算
                            bonus_with_increase = income.annual_bonus * ((1 + income.salary_increase_rate / 100) ** years_passed)
                            
                            # 年間収入の計算
                            annual_amount = monthly_with_increase * 12 + bonus_with_increase
                            
                            # 年間収入上限の適用
                            if hasattr(income, 'has_cap') and income.has_cap and hasattr(income, 'annual_income_cap') and income.annual_income_cap > 0:
                                annual_amount = min(annual_amount, income.annual_income_cap)
                            year_income += annual_amount
                            income_details.append({'type': 'salary', 'name': income.name, 'amount': annual_amount})
                
                if 'sidejob' in selected_incomes:
                    for income_id in selected_incomes['sidejob']:
                        income = SidejobIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
                        if income and income.start_year <= year <= income.end_year:
                            # 昇給率を適用した複利計算（副業にも昇給率がある場合）
                            years_passed = year - income.start_year
                            increase_rate = income.income_increase_rate if hasattr(income, 'income_increase_rate') else 0.0
                            
                            # 月額収入の計算
                            monthly_with_increase = income.monthly_amount * ((1 + increase_rate / 100) ** years_passed)
                            
                            # 年間収入の計算
                            annual_amount = monthly_with_increase * 12
                            
                            # 年間収入上限の適用
                            if hasattr(income, 'has_cap') and income.has_cap and hasattr(income, 'annual_income_cap') and income.annual_income_cap > 0:
                                annual_amount = min(annual_amount, income.annual_income_cap)
                            year_income += annual_amount
                            income_details.append({'type': 'sidejob', 'name': income.name, 'amount': annual_amount})
                
                if 'investment' in selected_incomes:
                    for income_id in selected_incomes['investment']:
                        income = InvestmentIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
                        if income and income.start_year <= year <= income.end_year:
                            # 運用利回りを適用した複利計算
                            years_passed = year - income.start_year
                            annual_amount = income.annual_amount * ((1 + income.annual_return_rate / 100) ** years_passed)
                            year_income += annual_amount
                            income_details.append({'type': 'investment', 'name': income.name, 'amount': annual_amount})
                
                if 'pension' in selected_incomes:
                    for income_id in selected_incomes['pension']:
                        income = PensionIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
                        if income and income.start_year <= year <= income.end_year:
                            annual_amount = income.annual_amount
                            year_income += annual_amount
                            income_details.append({'type': 'pension', 'name': income.name, 'amount': annual_amount})
                
                if 'other' in selected_incomes:
                    for income_id in selected_incomes['other']:
                        income = OtherIncomes.query.filter_by(id=income_id, user_id=current_user.id).first()
                        if income and income.start_year <= year <= income.end_year:
                            annual_amount = income.annual_amount
                            year_income += annual_amount
                            income_details.append({'type': 'other', 'name': income.name, 'amount': annual_amount})
            
            except Exception as e:
                error_msg = f"収入計算エラー（{year}年）: {str(e)}"
                app.logger.error(f"シミュレーション収入エラー - ユーザー: {current_user.id}, {error_msg}")
                return jsonify({
                    'error': True, 
                    'message': '収入データの処理中にエラーが発生しました', 
                    'details': error_msg
                }), 500
            
            # 支出計算
            try:
                if 'living' in selected_expenses:
                    for expense_id in selected_expenses['living']:
                        expense = LivingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
                        if expense and expense.start_year <= year <= expense.end_year:
                            # 物価上昇率を適用した複利計算
                            years_passed = year - expense.start_year
                            annual_amount = expense.monthly_total_amount * 12 * ((1 + expense.inflation_rate / 100) ** years_passed)
                            year_expenses += annual_amount
                            expense_details.append({'type': 'living', 'name': expense.name, 'amount': annual_amount})
                
                # その他の支出項目も同様に処理...
                if 'housing' in selected_expenses:
                    for expense_id in selected_expenses['housing']:
                        expense = HousingExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
                        if expense and expense.start_year <= year <= expense.end_year:
                            annual_amount = expense.monthly_total_amount * 12
                            year_expenses += annual_amount
                            expense_details.append({'type': 'housing', 'name': expense.name, 'amount': annual_amount})
                
                if 'education' in selected_expenses:
                    for expense_id in selected_expenses['education']:
                        expense = EducationExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
                        if expense and expense.start_year <= year <= expense.end_year:
                            annual_amount = expense.monthly_amount * 12
                            year_expenses += annual_amount
                            expense_details.append({'type': 'education', 'name': expense.name, 'amount': annual_amount})
                
                if 'insurance' in selected_expenses:
                    for expense_id in selected_expenses['insurance']:
                        expense = InsuranceExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
                        if expense and expense.start_year <= year <= expense.end_year:
                            annual_amount = expense.monthly_total_amount * 12
                            year_expenses += annual_amount
                            expense_details.append({'type': 'insurance', 'name': expense.name, 'amount': annual_amount})
                
                if 'event' in selected_expenses:
                    for expense_id in selected_expenses['event']:
                        expense = EventExpenses.query.filter_by(id=expense_id, user_id=current_user.id).first()
                        if expense and expense.start_year <= year <= expense.end_year:
                            annual_amount = expense.amount
                            year_expenses += annual_amount
                            expense_details.append({'type': 'event', 'name': expense.name, 'amount': annual_amount})
            
            except Exception as e:
                error_msg = f"支出計算エラー（{year}年）: {str(e)}"
                app.logger.error(f"シミュレーション支出エラー - ユーザー: {current_user.id}, {error_msg}")
                return jsonify({
                    'error': True, 
                    'message': '支出データの処理中にエラーが発生しました', 
                    'details': error_msg
                }), 500
            
            # 年間収支計算
            annual_balance = year_income - year_expenses
            cumulative_balance += annual_balance
            
            total_income += year_income
            total_expenses += year_expenses
            
            # デバッグログ: 収支がマイナスの場合のみログ出力
            if annual_balance < 0:
                app.logger.info(f"年間収支マイナス - 年: {year}, 収入: {year_income:,.0f}, 支出: {year_expenses:,.0f}, 収支: {annual_balance:,.0f}")
            
            simulation_data.append({
                'year': year,
                'age': age,
                'total_income': year_income,
                'total_expenses': year_expenses,
                'balance': annual_balance,
                'cumulative_balance': cumulative_balance,
                'income_details': income_details,
                'expense_details': expense_details
            })
        
        # サマリー計算
        summary = {
            'total_years': len(simulation_data),
            'total_income': total_income,
            'total_expenses': total_expenses,
            'final_cumulative_balance': cumulative_balance,
            'avg_annual_balance': (total_income - total_expenses) / len(simulation_data) if simulation_data else 0
        }
        
        app.logger.info(f"シミュレーション完了 - ユーザー: {current_user.id}, 期間: {start_year}-{end_year}, 最終収支: {cumulative_balance}")
        
        return jsonify({
            'simulation_data': simulation_data,
            'summary': summary
        })
    
    except Exception as e:
        error_msg = f"シミュレーション実行エラー: {str(e)}"
        app.logger.error(f"シミュレーション全般エラー - ユーザー: {current_user.id}, エラー: {error_msg}, スタックトレース: {traceback.format_exc()}")
        return jsonify({
            'error': True, 
            'message': 'シミュレーションの実行中にエラーが発生しました', 
            'details': error_msg if app.debug else 'Internal Server Error'
        }), 500

@app.route('/api/nikkei')
def get_nikkei():
    try:
        # 日経平均株価のティッカーシンボル
        nikkei = yf.Ticker("^N225")
        
        # 直近のデータを取得
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        hist = nikkei.history(start=start_date, end=end_date)
        
        # 最新のデータを取得
        latest = hist.iloc[-1]
        
        # 前日比を計算
        prev_day = hist.iloc[-2]
        change = latest['Close'] - prev_day['Close']
        change_percent = (change / prev_day['Close']) * 100
        
        return jsonify({
            'price': round(latest['Close'], 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': int(latest['Volume']),
            'date': latest.name.strftime('%Y-%m-%d')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                             'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/api/log', methods=['POST'])
def log_client_error():
    try:
        data = request.get_json()
        level = data.get('level', 'error')
        message = data.get('message', 'Unknown error')
        source = data.get('source', 'unknown')
        context = data.get('context', {})
        
        # より詳細なログ出力
        detailed_log = f"""
=== クライアントログ ({level.upper()}) ===
時刻: {datetime.now()}
ソース: {source}
メッセージ: {message}
URL: {context.get('url', 'N/A')}
User Agent: {context.get('userAgent', 'N/A')}
Chart.js Status: {context.get('chartJsStatus', 'N/A')}
"""
        
        # デバッグ情報がある場合は追加
        debug_info = context.get('debugInfo')
        if debug_info:
            detailed_log += f"""
デバッグ情報:
  Chart.js読み込み履歴: {len(debug_info.get('chartJsLoading', []))}件
  エラー履歴: {len(debug_info.get('errors', []))}件
  Canvas確認履歴: {len(debug_info.get('canvasChecks', []))}件
  最新エラー: {debug_info.get('lastError', 'なし')}
"""
            
            # 最新のエラーがある場合は詳細を表示
            if debug_info.get('errors'):
                latest_errors = debug_info['errors'][-3:]  # 最新3件
                detailed_log += "\n最新エラー履歴:\n"
                for err in latest_errors:
                    detailed_log += f"  - {err.get('timestamp', 'N/A')}: {err.get('message', 'N/A')}\n"
                    
        # 追加データがある場合
        additional_data = context.get('data')
        if additional_data:
            detailed_log += f"\n追加データ: {str(additional_data)[:500]}\n"  # 500文字まで
            
        detailed_log += "=== ログ終了 ===\n"
        
        # ログレベルに応じてログを記録
        log_func = getattr(app.logger, level, app.logger.error)
        log_func(detailed_log)
        
        return jsonify({'status': 'success'})
    except Exception as e:
        app.logger.error(f'ログ記録中にエラーが発生: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/client-info', methods=['GET'])
def api_client_info():
    """
    クライアント情報を返すAPIエンドポイント
    """
    try:
        client_info = get_client_info()
        
        # 追加情報
        additional_info = {
            'ip_address': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
            'headers': {
                'Accept': request.headers.get('Accept'),
                'Accept-Language': request.headers.get('Accept-Language'),
                'Accept-Encoding': request.headers.get('Accept-Encoding'),
                'Connection': request.headers.get('Connection'),
                'Host': request.headers.get('Host'),
                'Referer': request.headers.get('Referer'),
                'X-Forwarded-For': request.headers.get('X-Forwarded-For'),
                'X-Real-IP': request.headers.get('X-Real-IP')
            }
        }
        
        # 認証情報
        auth_info = {
            'is_authenticated': current_user.is_authenticated,
            'user_id': current_user.id if current_user.is_authenticated else None,
            'username': current_user.username if current_user.is_authenticated else None
        }
        
        return jsonify({
            'success': True,
            'client_info': client_info,
            'additional_info': additional_info,
            'auth_info': auth_info
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error getting client info: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get client info'
        }), 500

@app.route('/api/delete-account', methods=['POST'])
@login_required
def api_delete_account():
    """アカウント削除API"""
    try:
        data = request.get_json()
        
        # パスワード確認
        if not data or 'password' not in data:
            return jsonify({'error': 'パスワードが必要です'}), 400
        
        # 現在のユーザーのパスワードを確認
        if not check_password_hash(current_user.password_hash, data['password']):
            return jsonify({'error': 'パスワードが正しくありません'}), 401
        
        user_id = current_user.id
        username = current_user.username
        
        # 関連データを削除（外部キー制約により自動削除されない場合のため）
        try:
            # 収入データの削除
            SalaryIncomes.query.filter_by(user_id=user_id).delete()
            SidejobIncomes.query.filter_by(user_id=user_id).delete()
            InvestmentIncomes.query.filter_by(user_id=user_id).delete()
            PensionIncomes.query.filter_by(user_id=user_id).delete()
            OtherIncomes.query.filter_by(user_id=user_id).delete()
            
            # 支出データの削除
            LivingExpenses.query.filter_by(user_id=user_id).delete()
            HousingExpenses.query.filter_by(user_id=user_id).delete()
            InsuranceExpenses.query.filter_by(user_id=user_id).delete()
            EventExpenses.query.filter_by(user_id=user_id).delete()
            EducationExpenses.query.filter_by(user_id=user_id).delete()
            EducationPlans.query.filter_by(user_id=user_id).delete()
            
            # シミュレーション関連データの削除
            simulation_plans = LifeplanSimulations.query.filter_by(user_id=user_id).all()
            for plan in simulation_plans:
                # 関連するリンクテーブルのデータを削除
                LifeplanExpenseLinks.query.filter_by(lifeplan_id=plan.id).delete()
                LifeplanIncomeLinks.query.filter_by(lifeplan_id=plan.id).delete()
            
            LifeplanSimulations.query.filter_by(user_id=user_id).delete()
            
            # ユーザーアカウントの削除
            User.query.filter_by(id=user_id).delete()
            
            # 変更をコミット
            db.session.commit()
            
            # ログアウト
            logout_user()
            
            # ログ記録
            app.logger.info(f"アカウント削除完了: ユーザー名={username}, ID={user_id}")
            
            return jsonify({
                'success': True,
                'message': 'アカウントが正常に削除されました'
            }), 200
            
        except Exception as delete_error:
            db.session.rollback()
            app.logger.error(f"データ削除エラー: {str(delete_error)}")
            return jsonify({'error': 'データの削除中にエラーが発生しました'}), 500
        
    except Exception as e:
        app.logger.error(f"アカウント削除エラー: {str(e)}")
        return jsonify({'error': 'アカウント削除中にエラーが発生しました'}), 500

@app.route('/api/update-profile', methods=['PUT'])
@login_required
def api_update_profile():
    """プロフィール更新API"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'データが必要です'}), 400
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        
        # バリデーション
        if not username:
            return jsonify({'error': 'ユーザー名は必須です'}), 400
        
        if len(username) < 3:
            return jsonify({'error': 'ユーザー名は3文字以上である必要があります'}), 400
        
        if email and '@' not in email:
            return jsonify({'error': '有効なメールアドレスを入力してください'}), 400
        
        # 重複チェック（自分以外のユーザー）
        existing_user = User.query.filter(
            User.username == username,
            User.id != current_user.id
        ).first()
        
        if existing_user:
            return jsonify({'error': 'このユーザー名は既に使用されています'}), 400
        
        if email:
            existing_email = User.query.filter(
                User.email == email,
                User.id != current_user.id
            ).first()
            
            if existing_email:
                return jsonify({'error': 'このメールアドレスは既に使用されています'}), 400
        
        # プロフィール更新
        current_user.username = username
        current_user.email = email if email else None
        
        db.session.commit()
        
        app.logger.info(f"プロフィール更新: ユーザーID={current_user.id}, 新ユーザー名={username}")
        
        return jsonify({
            'success': True,
            'message': 'プロフィールを更新しました',
            'user': {
                'username': current_user.username,
                'email': current_user.email
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"プロフィール更新エラー: {str(e)}")
        return jsonify({'error': 'プロフィール更新中にエラーが発生しました'}), 500

@app.route('/api/change-password', methods=['PUT'])
@login_required
def api_change_password():
    try:
        data = request.get_json()
        
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({'error': '現在のパスワードと新しいパスワードを入力してください'}), 400
        
        # 現在のパスワードを確認
        if not check_password_hash(current_user.password_hash, current_password):
            return jsonify({'error': '現在のパスワードが正しくありません'}), 400
        
        # 新しいパスワードの長さチェック
        if len(new_password) < 6:
            return jsonify({'error': 'パスワードは6文字以上で入力してください'}), 400
        
        # パスワードを更新
        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        
        return jsonify({'message': 'パスワードを変更しました'})
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'パスワード変更エラー: {str(e)}')
        return jsonify({'error': 'パスワード変更中にエラーが発生しました'}), 500

# データエクスポートAPI
@app.route('/api/export-data', methods=['GET'])
@login_required
def api_export_data():
    """ユーザーのすべてのデータをJSONでエクスポート"""
    try:
        print(f"エクスポート開始: ユーザーID {current_user.id}")
        
        # ユーザー情報
        user_info = {
            'username': current_user.username,
            'email': current_user.email,
            'export_date': datetime.utcnow().isoformat()
        }
        print("✓ ユーザー情報取得完了")
        
        # 収入データ
        print("収入データ取得中...")
        income_data = {}
        try:
            income_data['salary'] = [serialize_income(i) for i in SalaryIncomes.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ 給与収入: {len(income_data['salary'])}件")
        except Exception as e:
            print(f"✗ 給与収入エラー: {e}")
            income_data['salary'] = []
            
        try:
            income_data['sidejob'] = [serialize_income(i) for i in SidejobIncomes.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ 副業収入: {len(income_data['sidejob'])}件")
        except Exception as e:
            print(f"✗ 副業収入エラー: {e}")
            income_data['sidejob'] = []
            
        try:
            # テーブルが存在するかチェック
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            if 'business_incomes' in inspector.get_table_names():
                income_data['business'] = [serialize_income(i) for i in BusinessIncomes.query.filter_by(user_id=current_user.id).all()]
                print(f"✓ 事業収入: {len(income_data['business'])}件")
            else:
                print("⚠ business_incomes テーブルが存在しません")
                income_data['business'] = []
        except Exception as e:
            print(f"✗ 事業収入エラー: {e}")
            income_data['business'] = []
            
        try:
            income_data['investment'] = [serialize_income(i) for i in InvestmentIncomes.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ 投資収入: {len(income_data['investment'])}件")
        except Exception as e:
            print(f"✗ 投資収入エラー: {e}")
            income_data['investment'] = []
            
        try:
            income_data['pension'] = [serialize_income(i) for i in PensionIncomes.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ 年金収入: {len(income_data['pension'])}件")
        except Exception as e:
            print(f"✗ 年金収入エラー: {e}")
            income_data['pension'] = []
            
        try:
            income_data['other'] = [serialize_income(i) for i in OtherIncomes.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ その他収入: {len(income_data['other'])}件")
        except Exception as e:
            print(f"✗ その他収入エラー: {e}")
            income_data['other'] = []
        
        # 支出データ
        print("支出データ取得中...")
        expense_data = {}
        try:
            expense_data['housing'] = [serialize_expense(e) for e in HousingExpenses.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ 住居費: {len(expense_data['housing'])}件")
        except Exception as e:
            print(f"✗ 住居費エラー: {e}")
            expense_data['housing'] = []
            
        try:
            expense_data['insurance'] = [serialize_expense(e) for e in InsuranceExpenses.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ 保険料: {len(expense_data['insurance'])}件")
        except Exception as e:
            print(f"✗ 保険料エラー: {e}")
            expense_data['insurance'] = []
            
        try:
            expense_data['education'] = [serialize_education_expense(e) for e in EducationExpenses.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ 教育費: {len(expense_data['education'])}件")
        except Exception as e:
            print(f"✗ 教育費エラー: {e}")
            expense_data['education'] = []
            
        try:
            expense_data['living'] = [serialize_living_expense(e) for e in LivingExpenses.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ 生活費: {len(expense_data['living'])}件")
        except Exception as e:
            print(f"✗ 生活費エラー: {e}")
            expense_data['living'] = []
            
        try:
            expense_data['events'] = [serialize_event_expense(e) for e in EventExpenses.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ イベント支出: {len(expense_data['events'])}件")
        except Exception as e:
            print(f"✗ イベント支出エラー: {e}")
            expense_data['events'] = []
        
        # シミュレーションデータ
        print("シミュレーションデータ取得中...")
        try:
            simulation_data = [serialize_simulation(s) for s in LifeplanSimulations.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ シミュレーション: {len(simulation_data)}件")
        except Exception as e:
            print(f"✗ シミュレーションエラー: {e}")
            simulation_data = []
        
        # 家計簿データ
        print("家計簿データ取得中...")
        try:
            household_data = [serialize_household(h) for h in HouseholdBook.query.filter_by(user_id=current_user.id).all()]
            print(f"✓ 家計簿: {len(household_data)}件")
        except Exception as e:
            print(f"✗ 家計簿エラー: {e}")
            household_data = []
        
        # データをまとめる
        export_data = {
            'user_info': user_info,
            'income_data': income_data,
            'expense_data': expense_data,
            'simulation_data': simulation_data,
            'household_data': household_data
        }
        
        print("JSONレスポンス作成中...")
        # JSONレスポンスとして返す
        try:
            response = make_response(jsonify(export_data))
            filename = f'lifeplan_data_{current_user.username}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
            response.headers['Content-Disposition'] = f'attachment; filename={filename}'
            response.headers['Content-Type'] = 'application/json'
            print(f"✓ エクスポート完了: {filename}")
            return response
        except Exception as json_error:
            print(f"✗ JSONレスポンス作成エラー: {json_error}")
            raise json_error
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"✗ データエクスポートエラー: {str(e)}")
        print(f"スタックトレース:\n{error_details}")
        app.logger.error(f"データエクスポートエラー: {str(e)}\n{error_details}")
        return jsonify({'success': False, 'error': f'データエクスポートに失敗しました: {str(e)}'}), 500

def serialize_income(income):
    """収入データのシリアライズ"""
    data = {
        'id': income.id,
        'name': income.name,
        'description': income.description,
        'monthly_amount': income.monthly_amount,
        'annual_amount': income.annual_amount,
        'start_year': income.start_year,
        'end_year': income.end_year,
        'created_at': income.created_at.isoformat() if income.created_at else None
    }
    
    # 収入タイプ別の特別な属性を追加
    if hasattr(income, 'annual_bonus'):
        data['annual_bonus'] = income.annual_bonus
    if hasattr(income, 'salary_increase_rate'):
        data['salary_increase_rate'] = income.salary_increase_rate
    if hasattr(income, 'income_increase_rate'):
        data['income_increase_rate'] = income.income_increase_rate
    if hasattr(income, 'annual_return_rate'):
        data['annual_return_rate'] = income.annual_return_rate
    if hasattr(income, 'has_cap'):
        data['has_cap'] = income.has_cap
    if hasattr(income, 'annual_income_cap'):
        data['annual_income_cap'] = income.annual_income_cap
    
    return data

def serialize_expense(expense):
    """支出データのシリアライズ"""
    data = {
        'id': expense.id,
        'name': expense.name,
        'description': expense.description,
        'start_year': expense.start_year,
        'end_year': expense.end_year,
        'created_at': expense.created_at.isoformat() if expense.created_at else None
    }
    
    # 支出タイプ別の特別な属性を追加
    if hasattr(expense, 'monthly_total_amount'):
        data['monthly_total_amount'] = expense.monthly_total_amount
    if hasattr(expense, 'residence_type'):
        data['residence_type'] = expense.residence_type.value if expense.residence_type else None
    if hasattr(expense, 'rent_monthly'):
        data['rent_monthly'] = expense.rent_monthly
    if hasattr(expense, 'mortgage_monthly'):
        data['mortgage_monthly'] = expense.mortgage_monthly
    
    return data

def serialize_living_expense(expense):
    """生活費データのシリアライズ"""
    return {
        'id': expense.id,
        'name': expense.name,
        'description': expense.description,
        'start_year': expense.start_year,
        'end_year': expense.end_year,
        'inflation_rate': expense.inflation_rate,
        'food_home': expense.food_home,
        'food_outside': expense.food_outside,
        'utility_electricity': expense.utility_electricity,
        'utility_gas': expense.utility_gas,
        'utility_water': expense.utility_water,
        'monthly_total_amount': expense.monthly_total_amount,
        'created_at': expense.created_at.isoformat() if expense.created_at else None
    }

def serialize_education_expense(expense):
    """教育費データのシリアライズ"""
    return {
        'id': expense.id,
        'name': expense.name,
        'description': expense.description,
        'start_year': expense.start_year,
        'end_year': expense.end_year,
        'child_name': expense.child_name,
        'child_birth_date': expense.child_birth_date.isoformat() if expense.child_birth_date else None,
        'stage': expense.stage,
        'stage_type': expense.stage_type,
        'monthly_amount': expense.monthly_amount,
        'created_at': expense.created_at.isoformat() if expense.created_at else None
    }

def serialize_event_expense(expense):
    """イベント支出データのシリアライズ"""
    return {
        'id': expense.id,
        'name': expense.name,
        'description': expense.description,
        'start_year': expense.start_year,
        'end_year': expense.end_year,
        'category': expense.category.value if expense.category else None,
        'amount': expense.amount,
        'is_recurring': expense.is_recurring,
        'recurrence_interval': expense.recurrence_interval,
        'recurrence_count': expense.recurrence_count,
        'created_at': expense.created_at.isoformat() if expense.created_at else None
    }

def serialize_simulation(simulation):
    """シミュレーションデータのシリアライズ"""
    return {
        'id': simulation.id,
        'name': simulation.name,
        'description': simulation.description,
        'base_age': simulation.base_age,
        'start_year': simulation.start_year,
        'end_year': simulation.end_year,
        'created_at': simulation.created_at.isoformat() if simulation.created_at else None
    }

def serialize_household(household):
    """家計簿データのシリアライズ"""
    try:
        entries = HouseholdEntry.query.filter_by(household_book_id=household.id).all()
        entry_list = []
        for entry in entries:
            try:
                entry_data = {
                    'id': entry.id,
                    'amount': entry.amount,
                    'description': entry.description,
                    'entry_type': entry.entry_type
                }
                
                # 日付フィールドを安全に取得
                if hasattr(entry, 'entry_date') and entry.entry_date:
                    entry_data['date'] = entry.entry_date.isoformat()
                elif hasattr(entry, 'date') and entry.date:
                    entry_data['date'] = entry.date.isoformat()
                else:
                    entry_data['date'] = None
                
                # カテゴリフィールドを安全に取得
                if hasattr(entry, 'expense_category_id'):
                    entry_data['expense_category_id'] = entry.expense_category_id
                if hasattr(entry, 'income_category_id'):
                    entry_data['income_category_id'] = entry.income_category_id
                
                entry_list.append(entry_data)
            except Exception as entry_error:
                print(f"家計簿エントリ処理エラー (ID: {getattr(entry, 'id', 'unknown')}): {entry_error}")
                continue
        
        return {
            'id': household.id,
            'name': household.name,
            'year': household.year,
            'month': household.month,
            'created_at': household.created_at.isoformat() if household.created_at else None,
            'entries': entry_list
        }
    except Exception as e:
        print(f"家計簿データシリアライズエラー (ID: {getattr(household, 'id', 'unknown')}): {e}")
        return {
            'id': getattr(household, 'id', None),
            'name': getattr(household, 'name', 'エラー'),
            'year': getattr(household, 'year', 0),
            'month': getattr(household, 'month', 0),
            'created_at': None,
            'entries': [],
            'error': str(e)
        }

# 家計簿関連のモデル
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

# 口座管理のためのモデル
class Account(db.Model):
    __tablename__ = 'accounts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # 口座名
    account_type = db.Column(db.String(20), nullable=False)  # 'wallet', 'bank', 'savings', 'investment'
    balance = db.Column(db.Float, default=0.0)  # 残高
    currency = db.Column(db.String(3), default='JPY')  # 通貨
    icon = db.Column(db.String(30), default='account_balance_wallet')  # Material Icons名
    color = db.Column(db.String(7), default='#2196F3')  # HEXカラー
    is_active = db.Column(db.Boolean, default=True)  # アクティブかどうか
    sort_order = db.Column(db.Integer, default=0)  # 表示順序
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーション
    transactions_from = db.relationship('AccountTransaction', foreign_keys='AccountTransaction.from_account_id', backref='from_account')
    transactions_to = db.relationship('AccountTransaction', foreign_keys='AccountTransaction.to_account_id', backref='to_account')

class AccountTransaction(db.Model):
    __tablename__ = 'account_transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    from_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True)  # 送金元口座（収入の場合はNull）
    to_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=False)  # 送金先口座
    amount = db.Column(db.Float, nullable=False)  # 金額
    transaction_type = db.Column(db.String(20), nullable=False)  # 'transfer', 'income', 'expense'
    description = db.Column(db.String(200))  # 説明
    transaction_date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
                'success': True,
                'id': entry.id,
                'message': 'エントリーを追加しました'
            }), 201
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'エントリー作成エラー: {str(e)}')
            return jsonify({'success': False, 'error': 'エントリー作成中にエラーが発生しました'}), 500

@app.route('/api/household-entries/<int:entry_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_household_entry_detail(entry_id):
    entry = HouseholdEntry.query.filter_by(id=entry_id, user_id=current_user.id).first()
    if not entry:
        return jsonify({'success': False, 'error': 'エントリーが見つかりません'}), 404
    
    if request.method == 'GET':
        # エントリー詳細を取得
        return jsonify({
            'success': True,
            'entry': {
                'id': entry.id,
                'household_book_id': entry.household_book_id,
                'entry_type': entry.entry_type,
                'amount': entry.amount,
                'description': entry.description,
                'entry_date': entry.entry_date.isoformat(),
                'expense_category_id': entry.expense_category_id,
                'income_category_id': entry.income_category_id,
                'created_at': entry.created_at.isoformat()
            }
        })
    
    elif request.method == 'PUT':
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
            
            return jsonify({'success': True, 'message': 'エントリーを更新しました'})
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'エントリー更新エラー: {str(e)}')
            return jsonify({'success': False, 'error': 'エントリー更新中にエラーが発生しました'}), 500
    
    elif request.method == 'DELETE':
        # エントリーを削除
        try:
            db.session.delete(entry)
            db.session.commit()
            
            return jsonify({'success': True, 'message': 'エントリーを削除しました'})
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'エントリー削除エラー: {str(e)}')
            return jsonify({'success': False, 'error': 'エントリー削除中にエラーが発生しました'}), 500

@app.route('/api/expense-categories', methods=['GET'])
@login_required
def api_expense_categories():
    categories = ExpenseCategory.query.all()
    return jsonify({
        'success': True,
        'categories': [{
            'id': cat.id,
            'name': cat.name,
            'icon': cat.icon,
            'color': cat.color
        } for cat in categories]
    })

@app.route('/api/income-categories', methods=['GET'])
@login_required
def api_income_categories():
    categories = IncomeCategory.query.all()
    return jsonify({
        'success': True,
        'categories': [{
            'id': cat.id,
            'name': cat.name,
            'icon': cat.icon,
            'color': cat.color
        } for cat in categories]
    })

@app.route('/api/household-swipe-dev/entries', methods=['GET'])
@login_required
def api_household_swipe_dev_entries():
    """家計簿（スワイプ開発版）のエントリーを取得"""
    try:
        # 家計簿スワイプ版のデータを模擬的に返す
        mock_entries = [
            {
                'id': 999,
                'type': 'expense',
                'amount': 1500,
                'description': '家計簿スワイプ版からの移行データ',
                'expense_category_id': 1,  # 食費
                'income_category_id': None,
                'date': '2025-06-22'
            }
        ]
        return jsonify(mock_entries)
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# データエクスポートAPI（簡素化版）
@app.route('/api/export-data-simple', methods=['GET'])
@login_required
def api_export_data_simple():
    """ユーザーの基本データのみをJSONでエクスポート（テスト版）"""
    try:
        print(f"簡素化エクスポート開始: ユーザーID {current_user.id}")
        
        # 基本的なユーザー情報のみ
        export_data = {
            'user_info': {
                'username': current_user.username,
                'email': current_user.email,
                'export_date': datetime.utcnow().isoformat(),
                'export_type': 'simple'
            },
            'data_summary': {
                'note': 'これは簡素化されたエクスポートです。完全版は別途実装予定です。'
            }
        }
        
        print("✓ 簡素化エクスポート完了")
        
        # JSONレスポンスとして返す
        response = make_response(jsonify(export_data))
        filename = f'lifeplan_simple_{current_user.username}_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'application/json'
        
        return response
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"✗ 簡素化エクスポートエラー: {str(e)}")
        print(f"スタックトレース:\n{error_details}")
        return jsonify({'success': False, 'error': f'簡素化エクスポートに失敗しました: {str(e)}'}), 500

# 口座管理API
@app.route('/api/accounts', methods=['GET', 'POST'])
@login_required
def api_accounts():
    """口座一覧取得・作成API"""
    try:
        if request.method == 'GET':
            accounts = Account.query.filter_by(user_id=current_user.id, is_active=True)\
                .order_by(Account.sort_order.asc(), Account.created_at.asc()).all()
            
            # デフォルト口座がない場合は作成
            if not accounts:
                default_account = Account(
                    user_id=current_user.id,
                    name='お財布',
                    account_type='wallet',
                    balance=0.0,
                    icon='account_balance_wallet',
                    color='#4CAF50',
                    sort_order=0
                )
                db.session.add(default_account)
                db.session.commit()
                accounts = [default_account]
            
            accounts_data = []
            for account in accounts:
                accounts_data.append({
                    'id': account.id,
                    'name': account.name,
                    'account_type': account.account_type,
                    'balance': account.balance,
                    'currency': account.currency,
                    'icon': account.icon,
                    'color': account.color,
                    'sort_order': account.sort_order
                })
            
            return jsonify({'success': True, 'accounts': accounts_data})
        
        elif request.method == 'POST':
            data = request.get_json()
            
            # 最大表示順序を取得
            max_order = db.session.query(db.func.max(Account.sort_order))\
                .filter_by(user_id=current_user.id).scalar() or 0
            
            account = Account(
                user_id=current_user.id,
                name=data.get('name', '新しい口座'),
                account_type=data.get('account_type', 'bank'),
                balance=float(data.get('balance', 0.0)),
                icon=data.get('icon', 'account_balance'),
                color=data.get('color', '#2196F3'),
                sort_order=max_order + 1
            )
            
            db.session.add(account)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'account': {
                    'id': account.id,
                    'name': account.name,
                    'account_type': account.account_type,
                    'balance': account.balance,
                    'currency': account.currency,
                    'icon': account.icon,
                    'color': account.color,
                    'sort_order': account.sort_order
                }
            })
    
    except Exception as e:
        app.logger.error(f"口座API エラー: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/accounts/<int:account_id>', methods=['PUT', 'DELETE'])
@login_required
def api_account_detail(account_id):
    """口座詳細更新・削除API"""
    try:
        account = Account.query.filter_by(id=account_id, user_id=current_user.id).first()
        if not account:
            return jsonify({'success': False, 'error': '口座が見つかりません'}), 404
        
        if request.method == 'PUT':
            data = request.get_json()
            
            account.name = data.get('name', account.name)
            account.account_type = data.get('account_type', account.account_type)
            account.balance = float(data.get('balance', account.balance))
            account.icon = data.get('icon', account.icon)
            account.color = data.get('color', account.color)
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'account': {
                    'id': account.id,
                    'name': account.name,
                    'account_type': account.account_type,
                    'balance': account.balance,
                    'currency': account.currency,
                    'icon': account.icon,
                    'color': account.color,
                    'sort_order': account.sort_order
                }
            })
        
        elif request.method == 'DELETE':
            account.is_active = False
            db.session.commit()
            
            return jsonify({'success': True, 'message': '口座を削除しました'})
    
    except Exception as e:
        app.logger.error(f"口座詳細API エラー: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/account-transfer', methods=['POST'])
@login_required
def api_account_transfer():
    """口座間送金API"""
    try:
        data = request.get_json()
        from_account_id = data.get('from_account_id')
        to_account_id = data.get('to_account_id')
        amount = float(data.get('amount', 0))
        description = data.get('description', '')
        
        if amount <= 0:
            return jsonify({'success': False, 'error': '金額は0より大きい値を入力してください'}), 400
        
        # 送金元口座の確認（収入の場合はNone）
        from_account = None
        if from_account_id:
            from_account = Account.query.filter_by(id=from_account_id, user_id=current_user.id).first()
            if not from_account:
                return jsonify({'success': False, 'error': '送金元口座が見つかりません'}), 404
            
            if from_account.balance < amount:
                return jsonify({'success': False, 'error': '残高が不足しています'}), 400
        
        # 送金先口座の確認
        to_account = Account.query.filter_by(id=to_account_id, user_id=current_user.id).first()
        if not to_account:
            return jsonify({'success': False, 'error': '送金先口座が見つかりません'}), 404
        
        # トランザクション作成
        transaction_type = 'income' if not from_account_id else 'transfer'
        transaction = AccountTransaction(
            user_id=current_user.id,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            transaction_type=transaction_type,
            description=description
        )
        
        # 残高更新
        if from_account:
            from_account.balance -= amount
        to_account.balance += amount
        
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '送金が完了しました',
            'transaction': {
                'id': transaction.id,
                'from_account_name': from_account.name if from_account else '外部収入',
                'to_account_name': to_account.name,
                'amount': amount,
                'description': description,
                'transaction_type': transaction_type
            }
        })
    
    except Exception as e:
        app.logger.error(f"口座送金API エラー: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/account-transactions', methods=['GET'])
@login_required
def api_account_transactions():
    """口座取引履歴取得API"""
    try:
        account_id = request.args.get('account_id')
        limit = int(request.args.get('limit', 50))
        
        query = AccountTransaction.query.filter_by(user_id=current_user.id)
        
        if account_id:
            query = query.filter(
                (AccountTransaction.from_account_id == account_id) |
                (AccountTransaction.to_account_id == account_id)
            )
        
        transactions = query.order_by(AccountTransaction.created_at.desc()).limit(limit).all()
        
        transactions_data = []
        for transaction in transactions:
            transactions_data.append({
                'id': transaction.id,
                'from_account_name': transaction.from_account.name if transaction.from_account else '外部収入',
                'to_account_name': transaction.to_account.name,
                'amount': transaction.amount,
                'transaction_type': transaction.transaction_type,
                'description': transaction.description,
                'transaction_date': transaction.transaction_date.isoformat(),
                'created_at': transaction.created_at.isoformat()
            })
        
        return jsonify({'success': True, 'transactions': transactions_data})
    
    except Exception as e:
        app.logger.error(f"取引履歴API エラー: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8203, debug=True) 