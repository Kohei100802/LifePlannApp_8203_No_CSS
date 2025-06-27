"""
エラーハンドラー
"""
from flask import jsonify, render_template, request
import traceback
from datetime import datetime

def register_error_handlers(app):
    """エラーハンドラーを登録"""
    
    @app.errorhandler(404)
    def handle_not_found(e):
        """404エラーハンドラー"""
        # 無視するパス
        ignored_paths = [
            '/favicon.ico', '/.well-known/', '/apple-touch-icon',
            '/robots.txt', '/sitemap.xml', '/.env'
        ]
        
        if any(path in request.path for path in ignored_paths):
            return '', 404
        
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Not Found', 'path': request.path}), 404
        
        return render_template('error.html', error='ページが見つかりません'), 404
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """一般的な例外ハンドラー"""
        # 無視するパス
        ignored_paths = [
            '/favicon.ico', '/.well-known/', '/apple-touch-icon',
            '/robots.txt', '/sitemap.xml', '/.env'
        ]
        
        should_ignore = any(path in request.path for path in ignored_paths)
        
        # 404エラーかつ無視すべきパスの場合
        if should_ignore and hasattr(e, 'code') and e.code == 404:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Not Found'}), 404
            return '', 404
        
        # エラーログ
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
        
        # レスポンス
        if request.path.startswith('/api/'):
            return jsonify({
                'error': True,
                'message': 'サーバーエラーが発生しました。',
                'details': str(e) if app.debug else 'Internal Server Error',
                'timestamp': datetime.now().isoformat()
            }), 500
        
        return render_template('error.html', 
                             error=str(e) if app.debug else 'Internal Server Error'), 500 