"""
メインルート
"""
from flask import Blueprint, render_template, redirect, url_for, send_from_directory
from flask_login import login_required, current_user
import os

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    """トップページ"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    """ダッシュボード"""
    return render_template('dashboard.html')

@bp.route('/mypage')
@login_required
def mypage():
    """マイページ"""
    return render_template('mypage.html')

@bp.route('/test-menu')
@login_required
def test_menu():
    """テストメニュー"""
    return render_template('test_menu.html')

@bp.route('/favicon.ico')
def favicon():
    """ファビコン"""
    return send_from_directory(
        os.path.join(bp.root_path, '..', '..', 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    ) 