"""
支出管理のルート
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models import (
    LivingExpenses, EducationPlans, EducationExpenses,
    HousingExpenses, InsuranceExpenses, EventExpenses
)
from app.models.enums import ResidenceType, EventCategory
from datetime import datetime

bp = Blueprint('expenses', __name__, url_prefix='/expenses')

@bp.route('/')
@login_required
def index():
    """支出管理トップページ"""
    return render_template('expenses.html')

@bp.route('/living')
@login_required
def living():
    """生活費管理"""
    expenses = LivingExpenses.query.filter_by(user_id=current_user.id).all()
    return render_template('expenses/living.html', expenses=expenses)

@bp.route('/living/create', methods=['GET', 'POST'])
@login_required
def living_create():
    """生活費作成"""
    if request.method == 'POST':
        data = request.get_json()
        
        expense = LivingExpenses(
            user_id=current_user.id,
            name=data['name'],
            description=data.get('description', ''),
            start_year=data['start_year'],
            end_year=data['end_year'],
            inflation_rate=data.get('inflation_rate', 2.0),
            food_home=data.get('food_home', 0),
            food_outside=data.get('food_outside', 0),
            utility_electricity=data.get('utility_electricity', 0),
            utility_gas=data.get('utility_gas', 0),
            utility_water=data.get('utility_water', 0),
            subscription_services=data.get('subscription_services', 0),
            internet=data.get('internet', 0),
            phone=data.get('phone', 0),
            household_goods=data.get('household_goods', 0),
            hygiene=data.get('hygiene', 0),
            clothing=data.get('clothing', 0),
            beauty=data.get('beauty', 0),
            child_food=data.get('child_food', 0),
            child_clothing=data.get('child_clothing', 0),
            child_medical=data.get('child_medical', 0),
            child_other=data.get('child_other', 0),
            transport=data.get('transport', 0),
            entertainment=data.get('entertainment', 0),
            pet_costs=data.get('pet_costs', 0),
            other_expenses=data.get('other_expenses', 0)
        )
        
        # 月額合計を計算
        expense.monthly_total_amount = sum([
            expense.food_home, expense.food_outside,
            expense.utility_electricity, expense.utility_gas, expense.utility_water,
            expense.subscription_services, expense.internet, expense.phone,
            expense.household_goods, expense.hygiene,
            expense.clothing, expense.beauty,
            expense.child_food, expense.child_clothing, expense.child_medical, expense.child_other,
            expense.transport, expense.entertainment, expense.pet_costs, expense.other_expenses
        ])
        
        db.session.add(expense)
        db.session.commit()
        
        return jsonify({'success': True, 'id': expense.id})
    
    return render_template('expenses/living_form.html')

@bp.route('/education')
@login_required
def education():
    """教育費管理"""
    plans = EducationPlans.query.filter_by(user_id=current_user.id).all()
    expenses = EducationExpenses.query.filter_by(user_id=current_user.id).all()
    return render_template('expenses/education.html', plans=plans, expenses=expenses)

@bp.route('/housing')
@login_required
def housing():
    """住居費管理"""
    expenses = HousingExpenses.query.filter_by(user_id=current_user.id).all()
    return render_template('expenses/housing.html', expenses=expenses)

@bp.route('/insurance')
@login_required
def insurance():
    """保険費管理"""
    expenses = InsuranceExpenses.query.filter_by(user_id=current_user.id).all()
    return render_template('expenses/insurance.html', expenses=expenses)

@bp.route('/events')
@login_required
def events():
    """イベント費用管理"""
    expenses = EventExpenses.query.filter_by(user_id=current_user.id).all()
    return render_template('expenses/events.html', expenses=expenses) 