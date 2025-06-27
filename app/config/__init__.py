"""
アプリケーション設定
"""
import os
from datetime import timedelta

class Config:
    """基本設定"""
    # 基本設定
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # データベース設定
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///lifeplan.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # セッション設定
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # アプリケーション設定
    APP_PORT = int(os.environ.get('APP_PORT', 8203))
    APP_HOST = os.environ.get('APP_HOST', '0.0.0.0')
    
    # 外部API設定
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
    
    # 開発/本番環境
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

class DevelopmentConfig(Config):
    """開発環境設定"""
    DEBUG = True

class ProductionConfig(Config):
    """本番環境設定"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True

# 設定マッピング
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 