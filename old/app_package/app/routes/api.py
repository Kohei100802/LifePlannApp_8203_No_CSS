"""
API関連のルート
"""
from flask import Blueprint, jsonify, request, make_response
from flask_login import login_required, current_user
from datetime import datetime
import yfinance as yf
from datetime import timedelta

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/nikkei')
def get_nikkei():
    """日経平均株価取得API"""
    try:
        # 日経平均株価のティッカーシンボル
        nikkei = yf.Ticker("^N225")
        
        # 直近のデータを取得
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        hist = nikkei.history(start=start_date, end=end_date)
        
        # 最新のデータを取得
        latest = hist.iloc[-1]
        
        # 前日比を計算
        prev_day = hist.iloc[-2]
        change = latest['Close'] - prev_day['Close']
        change_percent = (change / prev_day['Close']) * 100
        
        return jsonify({
            'price': round(latest['Close'], 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': int(latest['Volume']),
            'date': latest.name.strftime('%Y-%m-%d')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/log', methods=['POST'])
def log_client_error():
    """クライアントエラーログAPI"""
    try:
        data = request.get_json()
        level = data.get('level', 'error')
        message = data.get('message', 'Unknown error')
        source = data.get('source', 'unknown')
        context = data.get('context', {})
        
        # 詳細なログ出力
        detailed_log = f"""
=== クライアントログ ({level.upper()}) ===
時刻: {datetime.now()}
ソース: {source}
メッセージ: {message}
URL: {context.get('url', 'N/A')}
User Agent: {context.get('userAgent', 'N/A')}
Chart.js Status: {context.get('chartJsStatus', 'N/A')}
"""
        
        # デバッグ情報がある場合は追加
        debug_info = context.get('debugInfo')
        if debug_info:
            detailed_log += f"""
デバッグ情報:
  Chart.js読み込み履歴: {len(debug_info.get('chartJsLoading', []))}件
  エラー履歴: {len(debug_info.get('errors', []))}件
  Canvas確認履歴: {len(debug_info.get('canvasChecks', []))}件
  最新エラー: {debug_info.get('lastError', 'なし')}
"""
            
            # 最新のエラーがある場合は詳細を表示
            if debug_info.get('errors'):
                latest_errors = debug_info['errors'][-3:]  # 最新3件
                detailed_log += "\n最新エラー履歴:\n"
                for err in latest_errors:
                    detailed_log += f"  - {err.get('timestamp', 'N/A')}: {err.get('message', 'N/A')}\n"
                    
        # 追加データがある場合
        additional_data = context.get('data')
        if additional_data:
            detailed_log += f"\n追加データ: {str(additional_data)[:500]}\n"  # 500文字まで
            
        detailed_log += "=== ログ終了 ===\n"
        
        # ログレベルに応じてログを記録
        from flask import current_app
        log_func = getattr(current_app.logger, level, current_app.logger.error)
        log_func(detailed_log)
        
        return jsonify({'status': 'success'})
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'ログ記録中にエラーが発生: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/client-info', methods=['GET'])
def api_client_info():
    """クライアント情報を返すAPIエンドポイント"""
    try:
        from app.utils.context_processors import get_client_info
        client_info = get_client_info()
        
        # 追加情報
        additional_info = {
            'ip_address': request.remote_addr,
            'timestamp': datetime.now().isoformat(),
            'headers': {
                'Accept': request.headers.get('Accept'),
                'Accept-Language': request.headers.get('Accept-Language'),
                'Accept-Encoding': request.headers.get('Accept-Encoding'),
                'Connection': request.headers.get('Connection'),
                'Host': request.headers.get('Host'),
                'Referer': request.headers.get('Referer'),
                'X-Forwarded-For': request.headers.get('X-Forwarded-For'),
                'X-Real-IP': request.headers.get('X-Real-IP')
            }
        }
        
        # 認証情報
        auth_info = {
            'is_authenticated': current_user.is_authenticated,
            'user_id': current_user.id if current_user.is_authenticated else None,
            'username': current_user.username if current_user.is_authenticated else None
        }
        
        return jsonify({
            'success': True,
            'client_info': client_info,
            'additional_info': additional_info,
            'auth_info': auth_info
        }), 200
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error getting client info: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get client info'
        }), 500 