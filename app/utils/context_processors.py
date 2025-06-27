"""
コンテキストプロセッサー
"""
from flask import request
import re

def inject_client_info():
    """全てのテンプレートでクライアント情報を利用可能にする"""
    return dict(client_info=get_client_info())

def get_client_info():
    """リクエストのUser-Agentを解析してクライアント情報を返す"""
    user_agent = request.headers.get('User-Agent', '')
    
    client_info = {
        'user_agent': user_agent,
        'is_mobile': False,
        'is_ios': False,
        'is_android': False,
        'is_app': False,
        'is_browser': True,
        'device_type': 'desktop',
        'browser': 'unknown',
        'os': 'unknown',
        'app_version': None
    }
    
    # モバイルデバイスの検出
    mobile_patterns = [
        r'Mobile', r'Android', r'iPhone', r'iPad', r'iPod',
        r'BlackBerry', r'Windows Phone', r'Opera Mini'
    ]
    
    for pattern in mobile_patterns:
        if re.search(pattern, user_agent, re.IGNORECASE):
            client_info['is_mobile'] = True
            break
    
    # OS の検出
    if re.search(r'iPhone|iPad|iPod', user_agent, re.IGNORECASE):
        client_info['is_ios'] = True
        client_info['os'] = 'iOS'
        client_info['device_type'] = 'mobile' if 'iPhone' in user_agent or 'iPod' in user_agent else 'tablet'
    elif re.search(r'Android', user_agent, re.IGNORECASE):
        client_info['is_android'] = True
        client_info['os'] = 'Android'
        client_info['device_type'] = 'mobile'
    elif re.search(r'Windows', user_agent, re.IGNORECASE):
        client_info['os'] = 'Windows'
    elif re.search(r'Mac', user_agent, re.IGNORECASE):
        client_info['os'] = 'macOS'
    elif re.search(r'Linux', user_agent, re.IGNORECASE):
        client_info['os'] = 'Linux'
    
    # ブラウザの検出
    if re.search(r'Chrome', user_agent, re.IGNORECASE):
        client_info['browser'] = 'Chrome'
    elif re.search(r'Safari', user_agent, re.IGNORECASE) and not re.search(r'Chrome', user_agent, re.IGNORECASE):
        client_info['browser'] = 'Safari'
    elif re.search(r'Firefox', user_agent, re.IGNORECASE):
        client_info['browser'] = 'Firefox'
    elif re.search(r'Edge', user_agent, re.IGNORECASE):
        client_info['browser'] = 'Edge'
    
    # アプリからのアクセスの検出
    if re.search(r'LifePlanApp', user_agent, re.IGNORECASE):
        client_info['is_app'] = True
        client_info['is_browser'] = False
        # バージョン情報を抽出
        version_match = re.search(r'LifePlanApp/(\d+\.\d+(?:\.\d+)?)', user_agent)
        if version_match:
            client_info['app_version'] = version_match.group(1)
        
        # 画面サイズ情報を抽出
        screen_match = re.search(r'Screen/(\d+)x(\d+)', user_agent)
        if screen_match:
            client_info['screen_width'] = int(screen_match.group(1))
            client_info['screen_height'] = int(screen_match.group(2))
        
        # スケール情報を抽出
        scale_match = re.search(r'Scale/(\d+(?:\.\d+)?)', user_agent)
        if scale_match:
            client_info['screen_scale'] = float(scale_match.group(1))
    
    # WebViewの検出
    if re.search(r'wv\)|WebView', user_agent, re.IGNORECASE):
        client_info['is_app'] = True
        client_info['is_browser'] = False
    
    return client_info 