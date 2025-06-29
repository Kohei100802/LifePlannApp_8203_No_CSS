#!/usr/bin/env python
"""
アプリケーションのエントリーポイント
"""
import os
from app import create_app, db
from app.models import *  # 全てのモデルをインポート

# 環境変数から設定を取得
config_name = os.environ.get('FLASK_ENV', 'development')

# アプリケーションを作成
app = create_app(config_name)

# データベースの初期化
with app.app_context():
    db.create_all()
    
    # デフォルトカテゴリの作成
    from app.models import ExpenseCategory, IncomeCategory
    
    # 支出カテゴリ
    default_expense_categories = [
        {'name': '食費', 'icon': 'restaurant', 'color': '#FF5722'},
        {'name': '交通費', 'icon': 'directions_car', 'color': '#2196F3'},
        {'name': '娯楽', 'icon': 'movie', 'color': '#9C27B0'},
        {'name': '光熱費', 'icon': 'bolt', 'color': '#FF9800'},
        {'name': 'その他', 'icon': 'category', 'color': '#666666'}
    ]
    
    for cat_data in default_expense_categories:
        if not ExpenseCategory.query.filter_by(name=cat_data['name']).first():
            category = ExpenseCategory(**cat_data)
            db.session.add(category)
    
    # 収入カテゴリ
    default_income_categories = [
        {'name': '給与', 'icon': 'work', 'color': '#4CAF50'},
        {'name': '副業', 'icon': 'business_center', 'color': '#8BC34A'},
        {'name': 'その他', 'icon': 'attach_money', 'color': '#4CAF50'}
    ]
    
    for cat_data in default_income_categories:
        if not IncomeCategory.query.filter_by(name=cat_data['name']).first():
            category = IncomeCategory(**cat_data)
            db.session.add(category)
    
    db.session.commit()

if __name__ == '__main__':
    # 開発サーバーの起動
    from app.config import Config
    app.run(
        host=Config.APP_HOST,
        port=Config.APP_PORT,
        debug=Config.DEBUG
    ) 