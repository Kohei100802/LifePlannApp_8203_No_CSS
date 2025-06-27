"""
収入管理のルート
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (
    SalaryIncomes, SidejobIncomes, BusinessIncomes,
    InvestmentIncomes, PensionIncomes, OtherIncomes
)

bp = Blueprint('incomes', __name__, url_prefix='/incomes')

@bp.route('/')
@login_required
def index():
    """収入管理トップページ"""
    return render_template('incomes.html')

@bp.route('/salary')
@login_required
def salary():
    """給与収入管理"""
    incomes = SalaryIncomes.query.filter_by(user_id=current_user.id).all()
    return render_template('incomes/salary.html', incomes=incomes)

@bp.route('/salary/create', methods=['GET', 'POST'])
@login_required
def salary_create():
    """給与収入作成"""
    if request.method == 'POST':
        data = request.get_json()
        
        income = SalaryIncomes(
            user_id=current_user.id,
            name=data['name'],
            description=data.get('description', ''),
            monthly_amount=data['monthly_amount'],
            annual_bonus=data.get('annual_bonus', 0),
            start_year=data['start_year'],
            end_year=data['end_year'],
            salary_increase_rate=data.get('salary_increase_rate', 3.0),
            has_cap=data.get('has_cap', False),
            annual_income_cap=data.get('annual_income_cap', 0)
        )
        
        # 年収を計算
        income.annual_amount = (income.monthly_amount * 12) + income.annual_bonus
        
        db.session.add(income)
        db.session.commit()
        
        return jsonify({'success': True, 'id': income.id})
    
    return render_template('incomes/salary_form.html')

@bp.route('/sidejob')
@login_required
def sidejob():
    """副業収入管理"""
    incomes = SidejobIncomes.query.filter_by(user_id=current_user.id).all()
    return render_template('incomes/sidejob.html', incomes=incomes)

@bp.route('/business')
@login_required
def business():
    """事業収入管理"""
    incomes = BusinessIncomes.query.filter_by(user_id=current_user.id).all()
    return render_template('incomes/business.html', incomes=incomes)

@bp.route('/investment')
@login_required
def investment():
    """投資収入管理"""
    incomes = InvestmentIncomes.query.filter_by(user_id=current_user.id).all()
    return render_template('incomes/investment.html', incomes=incomes)

@bp.route('/pension')
@login_required
def pension():
    """年金収入管理"""
    incomes = PensionIncomes.query.filter_by(user_id=current_user.id).all()
    return render_template('incomes/pension.html', incomes=incomes)

@bp.route('/other')
@login_required
def other():
    """その他収入管理"""
    incomes = OtherIncomes.query.filter_by(user_id=current_user.id).all()
    return render_template('incomes/other.html', incomes=incomes) 