"""
ライフプランアプリケーション
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
import logging
from logging.handlers import RotatingFileHandler

# グローバル拡張機能
db = SQLAlchemy()
login_manager = LoginManager()

def create_app(config_name=None):
    """アプリケーションファクトリー"""
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    
    # 設定を読み込み
    from app.config import Config
    app.config.from_object(Config)
    
    # 拡張機能の初期化
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # ログ設定
    setup_logging(app)
    
    # コンテキストプロセッサーの登録
    from app.utils.context_processors import inject_client_info
    app.context_processor(inject_client_info)
    
    # ブループリントの登録
    from app.routes import auth, main, api, expenses, incomes, simulation, household
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(expenses.bp)
    app.register_blueprint(incomes.bp)
    app.register_blueprint(simulation.bp)
    app.register_blueprint(household.bp)
    
    # エラーハンドラーの登録
    from app.utils.error_handlers import register_error_handlers
    register_error_handlers(app)
    
    return app

def setup_logging(app):
    """ログ設定"""
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/lifeplan.log',
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('ライフプランアプリ起動') 