"""
家計簿関連のルート
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import (
    HouseholdBook, HouseholdEntry, ExpenseCategory,
    IncomeCategory, Account, AccountTransaction
)
from datetime import datetime, date
from sqlalchemy import extract

bp = Blueprint('household', __name__, url_prefix='/household')

@bp.route('/')
@login_required
def index():
    """家計簿トップページ"""
    # デフォルトの家計簿を取得または作成
    book = HouseholdBook.query.filter_by(user_id=current_user.id).first()
    if not book:
        book = HouseholdBook(
            user_id=current_user.id,
            name='メイン家計簿',
            description='デフォルトの家計簿'
        )
        db.session.add(book)
        db.session.commit()
    
    return render_template('household_menu.html', book=book)

@bp.route('/monthly')
@login_required
def monthly():
    """月別家計簿"""
    book = HouseholdBook.query.filter_by(user_id=current_user.id).first()
    
    # 現在の年月を取得
    now = datetime.now()
    year = request.args.get('year', now.year, type=int)
    month = request.args.get('month', now.month, type=int)
    
    # 月のエントリーを取得
    entries = HouseholdEntry.query.filter(
        HouseholdEntry.book_id == book.id,
        extract('year', HouseholdEntry.date) == year,
        extract('month', HouseholdEntry.date) == month
    ).order_by(HouseholdEntry.date.desc()).all()
    
    # カテゴリを取得
    expense_categories = ExpenseCategory.query.filter(
        (ExpenseCategory.user_id == current_user.id) | (ExpenseCategory.is_default == True)
    ).all()
    income_categories = IncomeCategory.query.filter(
        (IncomeCategory.user_id == current_user.id) | (IncomeCategory.is_default == True)
    ).all()
    
    return render_template(
        'household_book_monthly.html',
        book=book,
        entries=entries,
        year=year,
        month=month,
        expense_categories=expense_categories,
        income_categories=income_categories
    )

@bp.route('/entry/create', methods=['POST'])
@login_required
def create_entry():
    """エントリー作成"""
    data = request.get_json()
    
    book = HouseholdBook.query.filter_by(user_id=current_user.id).first()
    
    entry = HouseholdEntry(
        book_id=book.id,
        user_id=current_user.id,
        date=datetime.strptime(data['date'], '%Y-%m-%d').date(),
        category_id=data['category_id'],
        category_type=data['category_type'],
        amount=data['amount'],
        description=data.get('description', ''),
        payment_method=data.get('payment_method', '現金'),
        account_id=data.get('account_id')
    )
    
    db.session.add(entry)
    
    # 口座残高の更新
    if entry.account_id:
        account = Account.query.get(entry.account_id)
        if account:
            if entry.category_type == 'expense':
                account.balance -= entry.amount
                transaction_type = 'debit'
            else:
                account.balance += entry.amount
                transaction_type = 'credit'
            
            # 取引記録を作成
            transaction = AccountTransaction(
                account_id=account.id,
                transaction_date=datetime.now(),
                transaction_type=transaction_type,
                amount=entry.amount,
                balance_after=account.balance,
                description=entry.description,
                household_entry_id=entry.id
            )
            db.session.add(transaction)
    
    db.session.commit()
    
    return jsonify({'success': True, 'id': entry.id})

@bp.route('/calendar')
@login_required
def calendar():
    """カレンダー表示"""
    book = HouseholdBook.query.filter_by(user_id=current_user.id).first()
    
    # 現在の年月を取得
    now = datetime.now()
    year = request.args.get('year', now.year, type=int)
    month = request.args.get('month', now.month, type=int)
    
    # 月のエントリーを取得
    entries = HouseholdEntry.query.filter(
        HouseholdEntry.book_id == book.id,
        extract('year', HouseholdEntry.date) == year,
        extract('month', HouseholdEntry.date) == month
    ).all()
    
    # 日付ごとにエントリーを整理
    entries_by_date = {}
    for entry in entries:
        date_str = entry.date.strftime('%Y-%m-%d')
        if date_str not in entries_by_date:
            entries_by_date[date_str] = {'income': 0, 'expense': 0, 'entries': []}
        
        if entry.category_type == 'income':
            entries_by_date[date_str]['income'] += entry.amount
        else:
            entries_by_date[date_str]['expense'] += entry.amount
        
        entries_by_date[date_str]['entries'].append(entry)
    
    return render_template(
        'household_calendar.html',
        book=book,
        year=year,
        month=month,
        entries_by_date=entries_by_date
    )

@bp.route('/accounts')
@login_required
def accounts():
    """口座管理"""
    accounts = Account.query.filter_by(user_id=current_user.id).all()
    return render_template('account_management.html', accounts=accounts) 