"""
シミュレーション関連のルート
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import LifeplanSimulations, LifeplanExpenseLinks, LifeplanIncomeLinks
from datetime import datetime

bp = Blueprint('simulation', __name__, url_prefix='/simulation')

@bp.route('/')
@login_required
def index():
    """シミュレーション一覧"""
    simulations = LifeplanSimulations.query.filter_by(user_id=current_user.id).all()
    return render_template('simulation.html', simulations=simulations)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """シミュレーション作成"""
    if request.method == 'POST':
        data = request.get_json()
        
        simulation = LifeplanSimulations(
            user_id=current_user.id,
            name=data['name'],
            description=data.get('description', ''),
            birth_year=data['birth_year'],
            start_year=data['start_year'],
            end_year=data['end_year'],
            initial_assets=data.get('initial_assets', 0),
            inflation_rate=data.get('inflation_rate', 2.0),
            investment_return_rate=data.get('investment_return_rate', 3.0)
        )
        
        db.session.add(simulation)
        db.session.commit()
        
        return jsonify({'success': True, 'id': simulation.id})
    
    return render_template('simulation_create.html')

@bp.route('/<int:simulation_id>')
@login_required
def detail(simulation_id):
    """シミュレーション詳細"""
    simulation = LifeplanSimulations.query.filter_by(
        id=simulation_id,
        user_id=current_user.id
    ).first_or_404()
    
    return render_template('simulation_detail.html', simulation=simulation)

@bp.route('/<int:simulation_id>/run')
@login_required
def run(simulation_id):
    """シミュレーション実行"""
    simulation = LifeplanSimulations.query.filter_by(
        id=simulation_id,
        user_id=current_user.id
    ).first_or_404()
    
    # シミュレーション実行ロジック
    results = calculate_simulation(simulation)
    
    return render_template('simulation_run.html', simulation=simulation, results=results)

def calculate_simulation(simulation):
    """シミュレーション計算"""
    results = []
    current_assets = simulation.initial_assets
    
    for year in range(simulation.start_year, simulation.end_year + 1):
        age = year - simulation.birth_year
        
        # 収入の計算
        annual_income = calculate_annual_income(simulation, year)
        
        # 支出の計算
        annual_expense = calculate_annual_expense(simulation, year)
        
        # 収支
        annual_balance = annual_income - annual_expense
        
        # 資産運用
        investment_return = current_assets * (simulation.investment_return_rate / 100)
        
        # 資産更新
        current_assets = current_assets + annual_balance + investment_return
        
        results.append({
            'year': year,
            'age': age,
            'income': annual_income,
            'expense': annual_expense,
            'balance': annual_balance,
            'assets': current_assets
        })
    
    return results

def calculate_annual_income(simulation, year):
    """年間収入の計算"""
    total_income = 0
    
    # 各収入タイプの集計
    for link in simulation.income_links:
        # 実際の実装では各収入モデルから計算
        pass
    
    return total_income

def calculate_annual_expense(simulation, year):
    """年間支出の計算"""
    total_expense = 0
    
    # 各支出タイプの集計
    for link in simulation.expense_links:
        # 実際の実装では各支出モデルから計算
        pass
    
    return total_expense 