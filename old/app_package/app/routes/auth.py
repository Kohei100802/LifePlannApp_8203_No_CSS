"""
認証関連のルート
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from app.models import User
from app.utils.context_processors import get_client_info

bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    """ユーザーローダー"""
    return User.query.get(int(user_id))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    """ユーザー登録"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = str(data.get('password'))
        
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

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """ログイン"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = str(data.get('password'))
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

@bp.route('/logout')
@login_required
def logout():
    """ログアウト"""
    logout_user()
    return redirect(url_for('main.index')) 