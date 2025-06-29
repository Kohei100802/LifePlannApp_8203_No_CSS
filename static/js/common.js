// 共通JavaScript関数

// ネイティブアプリ情報処理
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM読み込み完了');
    
    // ネイティブアプリからの情報を受信
    if (window.nativeAppInfo) {
        handleNativeAppInfo(window.nativeAppInfo);
    }
    
    // ネイティブアプリ準備完了イベントのリスナー
    document.addEventListener('nativeAppReady', function(event) {
        console.log('ネイティブアプリ準備完了:', event.detail);
        handleNativeAppInfo(event.detail);
    });
    
    // 年度セレクトボックス初期化
    initializeYearSelects();
});

// ネイティブアプリ情報を処理する関数
function handleNativeAppInfo(appInfo) {
    console.log('ネイティブアプリ情報:', appInfo);
    
    // Safe Area情報を使用してスタイルを動的調整
    if (appInfo.safeAreaInsets) {
        const safeArea = appInfo.safeAreaInsets;
        const root = document.documentElement;
        
        // CSS変数として設定
        root.style.setProperty('--safe-area-inset-top', `${safeArea.top}px`);
        root.style.setProperty('--safe-area-inset-bottom', `${safeArea.bottom}px`);
        root.style.setProperty('--safe-area-inset-left', `${safeArea.left}px`);
        root.style.setProperty('--safe-area-inset-right', `${safeArea.right}px`);
        
        console.log('Safe Area設定:', safeArea);
    }
    
    // 画面サイズ情報を使用
    if (appInfo.screenSize) {
        const screen = appInfo.screenSize;
        console.log(`画面サイズ: ${screen.width}x${screen.height}, スケール: ${appInfo.screenScale}`);
        
        // 画面サイズに応じた調整
        if (screen.width < 375) {
            document.body.classList.add('small-screen');
        }
    }
    
    // アプリ固有の設定
    if (appInfo.isNativeApp) {
        document.body.classList.add('native-app-detected');
        
        // アプリ版でのスクロール最適化
        enableAppScrollOptimization();
        
        // アプリ版でのタッチ最適化
        enableAppTouchOptimization();
    }
}

// アプリ版スクロール最適化
function enableAppScrollOptimization() {
    // スクロール時のパフォーマンス最適化
    let ticking = false;
    
    function updateScrollPosition() {
        // フッター位置の微調整
        const footer = document.querySelector('.client-app .footer-nav');
        if (footer) {
            footer.style.transform = 'translate3d(0, 0, 0)';
        }
        ticking = false;
    }
    
    window.addEventListener('scroll', function() {
        if (!ticking) {
            requestAnimationFrame(updateScrollPosition);
            ticking = true;
        }
    }, { passive: true });
}

// アプリ版タッチ最適化
function enableAppTouchOptimization() {
    // タッチイベントの最適化
    document.addEventListener('touchstart', function(e) {
        // タッチ開始時の処理
    }, { passive: true });
    
    document.addEventListener('touchend', function(e) {
        // タッチ終了時の処理
    }, { passive: true });
    
    // ダブルタップズーム無効化（改善版）
    let lastTouchEnd = 0;
    document.addEventListener('touchend', function(event) {
        // 口座管理ページでは完全に無効化
        if (window.location.pathname.includes('account-management')) {
            const now = (new Date()).getTime();
            if (now - lastTouchEnd <= 300) {
                event.preventDefault();
            }
            lastTouchEnd = now;
            return;
        }
        
        // 他のページでは通常通り
        const now = (new Date()).getTime();
        if (now - lastTouchEnd <= 300) {
            event.preventDefault();
        }
        lastTouchEnd = now;
    }, false);
}

// ネイティブアプリ準備完了コールバック（Swift側から呼び出し可能）
window.onNativeAppReady = function(appInfo) {
    console.log('Swift側からのコールバック:', appInfo);
    handleNativeAppInfo(appInfo);
};

// 年度プルダウン生成関数
function generateYearOptions(startYear = 2020, endYear = 2100, defaultYear = null) {
    let options = '';
    for (let year = startYear; year <= endYear; year++) {
        const selected = (defaultYear && year == defaultYear) ? 'selected' : '';
        options += `<option value="${year}" ${selected}>${year}年</option>`;
    }
    return options;
}

// 年度セレクトボックスを初期化
function initializeYearSelects() {
    // 開始年のセレクトボックスを初期化
    const startYearSelects = document.querySelectorAll('select[name="start_year"]');
    startYearSelects.forEach(select => {
        if (select.children.length === 0) { // まだオプションが設定されていない場合のみ
            // ページによって開始年のデフォルト値を調整
            let defaultStartYear = 2024;
            if (window.location.pathname.includes('pension')) {
                defaultStartYear = 2060; // 年金は受給開始年が遅い
            }
            select.innerHTML = generateYearOptions(2020, 2100, defaultStartYear);
        }
    });
    
    // 終了年のセレクトボックスを初期化
    const endYearSelects = document.querySelectorAll('select[name="end_year"]');
    endYearSelects.forEach(select => {
        if (select.children.length === 0) { // まだオプションが設定されていない場合のみ
            // ページによってデフォルト値を調整
            let defaultEndYear = 2050;
            if (window.location.pathname.includes('pension')) {
                defaultEndYear = 2080; // 年金は受給期間が長い
            } else if (window.location.pathname.includes('salary') || window.location.pathname.includes('sidejob') || window.location.pathname.includes('investment') || window.location.pathname.includes('other')) {
                defaultEndYear = 2060; // 一般的な退職年齢まで
            } else if (window.location.pathname.includes('simulation')) {
                defaultEndYear = 2070; // シミュレーションは長期間
            }
            select.innerHTML = generateYearOptions(2020, 2100, defaultEndYear);
        }
    });
}

// ページトランジション
function createPageTransition() {
    const overlay = document.createElement('div');
    overlay.id = 'page-transition';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(45deg, var(--color-primary), var(--color-accent));
        z-index: 9999;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.3s ease;
    `;
    document.body.appendChild(overlay);
    return overlay;
}

// ローディング表示（アニメーション付き）
function showLoading(message = '読み込み中...') {
    let overlay = document.getElementById('loading-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9998;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;
        
        overlay.innerHTML = `
            <div style="
                background: white;
                padding: 2rem;
                border-radius: 12px;
                text-align: center;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                transform: scale(0.8);
                transition: transform 0.3s ease;
            " id="loading-content">
                <div style="
                    width: 40px;
                    height: 40px;
                    border: 4px solid #f0f0f0;
                    border-top: 4px solid var(--color-primary);
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 1rem auto;
                "></div>
                <p style="margin: 0; color: var(--color-text-primary); font-weight: 500;">${message}</p>
            </div>
        `;
        
        document.body.appendChild(overlay);
        
        // CSSアニメーションを追加
        if (!document.getElementById('loading-styles')) {
            const style = document.createElement('style');
            style.id = 'loading-styles';
            style.textContent = `
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                @keyframes pulse {
                    0%, 100% { transform: scale(1); }
                    50% { transform: scale(1.05); }
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    // メッセージを安全に更新
    const loadingContentP = overlay.querySelector('#loading-content p');
    if (loadingContentP) {
        loadingContentP.textContent = message;
    }
    
    overlay.classList.remove('hidden');
    overlay.style.display = 'flex';
    
    // アニメーション
    setTimeout(() => {
        overlay.style.opacity = '1';
        const loadingContent = document.getElementById('loading-content');
        if (loadingContent) {
            loadingContent.style.transform = 'scale(1)';
        }
    }, 10);
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.opacity = '0';
        const loadingContent = document.getElementById('loading-content');
        if (loadingContent) {
            loadingContent.style.transform = 'scale(0.8)';
        }
        
        setTimeout(() => {
            overlay.style.display = 'none';
            overlay.classList.add('hidden');
        }, 300);
    }
}

// MoneyForward風 UI用の共通関数

/**
 * トースト通知を表示（改善版）
 */
function showToast(message, type = 'info', duration = 5000) {
    // トーストコンテナを取得または作成
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container';
        document.body.appendChild(toastContainer);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    toastContainer.appendChild(toast);

    // 表示アニメーション
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    // 自動削除
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease forwards';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 300);
    }, duration);
}

/**
 * トーストを手動で削除
 */
function removeToast(toast) {
    if (toast && toast.parentNode) {
        toast.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 300);
    }
}

/**
 * 数値をフォーマットして表示
 */
function formatCurrency(amount, showSign = false) {
    // 小数点を切り捨てて整数にする
    const roundedAmount = Math.floor(amount);
    const absAmount = Math.abs(roundedAmount);
    const formatted = absAmount.toLocaleString();
    
    if (showSign && roundedAmount !== 0) {
        return roundedAmount > 0 ? `+¥${formatted}` : `-¥${formatted}`;
    }
    
    // 負の数の場合はマイナス記号を付ける
    if (roundedAmount < 0) {
        return `-¥${formatted}`;
    }
    
    return `¥${formatted}`;
}

/**
 * 日付をフォーマット
 */
function formatDate(dateString, format = 'short') {
    const date = new Date(dateString);
    const now = new Date();
    
    if (format === 'relative') {
        const diffTime = now - date;
        const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) return '今日';
        if (diffDays === 1) return '昨日';
        if (diffDays < 7) return `${diffDays}日前`;
        if (diffDays < 30) return `${Math.floor(diffDays / 7)}週間前`;
        if (diffDays < 365) return `${Math.floor(diffDays / 30)}ヶ月前`;
        return `${Math.floor(diffDays / 365)}年前`;
    }
    
    if (format === 'short') {
        return `${date.getMonth() + 1}/${date.getDate()}`;
    }
    
    if (format === 'long') {
        return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
    }
    
    return date.toLocaleDateString('ja-JP');
}

/**
 * アニメーション付きで要素を表示
 */
function animateIn(element, animationType = 'fadeIn') {
    element.classList.add(`mf-animate-${animationType}`);
    
    // アニメーション終了後にクラスを削除
    element.addEventListener('animationend', function() {
        element.classList.remove(`mf-animate-${animationType}`);
    }, { once: true });
}

/**
 * 要素を段階的に表示（stagger animation）
 */
function staggerAnimation(elements, delay = 100) {
    elements.forEach((element, index) => {
        setTimeout(() => {
            animateIn(element, 'slide');
        }, index * delay);
    });
}

/**
 * 読み込み状態を管理
 */
class LoadingManager {
    static show(element, text = '読み込み中...') {
        const spinner = document.createElement('div');
        spinner.className = 'mf-loading-overlay';
        spinner.innerHTML = `
            <div class="mf-loading-content">
                <div class="mf-loading"></div>
                <span>${text}</span>
            </div>
        `;
        
        element.style.position = 'relative';
        element.appendChild(spinner);
        
        return spinner;
    }
    
    static hide(element) {
        const overlay = element.querySelector('.mf-loading-overlay');
        if (overlay) {
            overlay.remove();
        }
    }
}

/**
 * 金額入力のフォーマット
 */
function formatAmountInput(input) {
    input.addEventListener('input', function() {
        let value = this.value.replace(/[^\d]/g, '');
        if (value) {
            value = parseInt(value).toLocaleString();
        }
        this.value = value;
    });
    
    input.addEventListener('focus', function() {
        this.value = this.value.replace(/,/g, '');
    });
    
    input.addEventListener('blur', function() {
        if (this.value) {
            this.value = parseInt(this.value).toLocaleString();
        }
    });
}

/**
 * カテゴリカラーを取得
 */
function getCategoryColor(category, type = 'expense') {
    if (!category) {
        return type === 'income' ? '#4CAF50' : '#f44336';
    }
    return category.color || (type === 'income' ? '#4CAF50' : '#f44336');
}

/**
 * フォーム検証
 */
function validateForm(formElement) {
    const errors = [];
    const requiredFields = formElement.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            errors.push(`${field.previousElementSibling?.textContent || field.name} は必須です`);
            field.classList.add('error');
        } else {
            field.classList.remove('error');
        }
    });
    
    // 数値フィールドの検証
    const numberFields = formElement.querySelectorAll('input[type="number"]');
    numberFields.forEach(field => {
        if (field.value && (isNaN(field.value) || parseFloat(field.value) < 0)) {
            errors.push(`${field.previousElementSibling?.textContent || field.name} は正の数値を入力してください`);
            field.classList.add('error');
        }
    });
    
    return errors;
}

/**
 * デバウンス関数
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * ローカルストレージ管理
 */
class StorageManager {
    static set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (e) {
            console.warn('ローカルストレージの保存に失敗しました:', e);
        }
    }
    
    static get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (e) {
            console.warn('ローカルストレージの読み込みに失敗しました:', e);
            return defaultValue;
        }
    }
    
    static remove(key) {
        try {
            localStorage.removeItem(key);
        } catch (e) {
            console.warn('ローカルストレージの削除に失敗しました:', e);
        }
    }
}

// ストレージヘルパー関数（後方互換性のため）
function saveToStorage(key, value) {
    return StorageManager.set(key, value);
}

function loadFromStorage(key, defaultValue = null) {
    return StorageManager.get(key, defaultValue);
}

/**
 * API呼び出しのヘルパー
 */
class ApiClient {
    static async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };
        
        const config = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API呼び出しエラー:', error);
            throw error;
        }
    }
    
    static async get(url) {
        return this.request(url, { method: 'GET' });
    }
    
    static async post(url, data) {
        return this.request(url, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }
    
    static async put(url, data) {
        return this.request(url, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }
    
    static async delete(url) {
        return this.request(url, { method: 'DELETE' });
    }
}

/**
 * API呼び出しヘルパー関数（後方互換性のため）
 */
async function apiCall(url, options = {}) {
    return ApiClient.request(url, options);
}

/**
 * モーダル管理
 */
class ModalManager {
    static open(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
            
            // フォーカスをモーダル内の最初の入力フィールドに移動
            const firstInput = modal.querySelector('input, select, textarea, button');
            if (firstInput) {
                setTimeout(() => firstInput.focus(), 100);
            }
        }
    }
    
    static close(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }
    
    static closeAll() {
        document.querySelectorAll('.mf-modal.active').forEach(modal => {
            modal.classList.remove('active');
        });
        document.body.style.overflow = '';
    }
}

// ESCキーでモーダルを閉じる
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        ModalManager.closeAll();
    }
});

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    // 金額入力フィールドの自動フォーマット
    document.querySelectorAll('input[type="number"][data-currency]').forEach(formatAmountInput);
    
    // フォーカスリングの追加
    document.querySelectorAll('button, input, select, textarea').forEach(element => {
        element.classList.add('mf-focus-ring');
    });
    
    // アニメーションの遅延読み込み
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateIn(entry.target, 'fadein');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);
    
    // 監視対象の要素を追加
    document.querySelectorAll('.mf-card, .mf-entry-item, .mf-summary-card').forEach(el => {
        observer.observe(el);
    });
});

// フォーム送信ヘルパー
async function submitForm(formElement, url, method = 'POST') {
    const formData = new FormData(formElement);
    const jsonData = {};
    
    for (let [key, value] of formData.entries()) {
        // 数値変換
        if (value && !isNaN(value) && value.trim() !== '') {
            jsonData[key] = parseFloat(value);
        } else {
            jsonData[key] = value;
        }
    }
    
    try {
        const response = await apiCall(url, {
            method: method,
            body: JSON.stringify(jsonData)
        });
        
        if (response.success) {
            showToast(response.message, 'success');
            return response;
        } else {
            showToast(response.message, 'error');
            throw new Error(response.message);
        }
    } catch (error) {
        console.error('Form submission error:', error);
        throw error;
    }
}

// 数値フォーマット
function formatNumber(number) {
    return new Intl.NumberFormat('ja-JP').format(number);
}

// 年齢計算
function calculateAge(birthDate, targetDate = new Date()) {
    const birth = new Date(birthDate);
    const target = new Date(targetDate);
    let age = target.getFullYear() - birth.getFullYear();
    const monthDiff = target.getMonth() - birth.getMonth();
    
    if (monthDiff < 0 || (monthDiff === 0 && target.getDate() < birth.getDate())) {
        age--;
    }
    
    return age;
}

// モーダル制御
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
}

function hideModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

// バリデーション
function validateRequired(formElement) {
    const requiredFields = formElement.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.style.borderColor = 'var(--color-red)';
            isValid = false;
        } else {
            field.style.borderColor = '';
        }
    });
    
    if (!isValid) {
        showToast('必須項目を入力してください', 'error');
    }
    
    return isValid;
}

// 個別フィールドバリデーション
function validateField(field, rules = {}) {
    const value = field.value.trim();
    let isValid = true;
    let errorMessage = '';
    
    // 必須チェック
    if (rules.required && !value) {
        isValid = false;
        errorMessage = '必須項目です';
    }
    
    // 数値チェック
    if (value && rules.type === 'number') {
        if (isNaN(value) || parseFloat(value) < 0) {
            isValid = false;
            errorMessage = '正の数値を入力してください';
        }
    }
    
    // 最小値チェック
    if (value && rules.min !== undefined && parseFloat(value) < rules.min) {
        isValid = false;
        errorMessage = `${rules.min}以上の値を入力してください`;
    }
    
    // 最大値チェック
    if (value && rules.max !== undefined && parseFloat(value) > rules.max) {
        isValid = false;
        errorMessage = `${rules.max}以下の値を入力してください`;
    }
    
    // UI更新
    if (isValid) {
        field.style.borderColor = '';
        field.classList.remove('error');
    } else {
        field.style.borderColor = 'var(--color-red)';
        field.classList.add('error');
        if (errorMessage) {
            showToast(errorMessage, 'error');
        }
    }
    
    return isValid;
}

// HTMLエスケープ
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// スムーズスクロール機能
function smoothScrollTo(element, options = {}) {
    const defaultOptions = {
        behavior: 'smooth',
        block: 'start',
        inline: 'nearest'
    };
    
    if (typeof element === 'string') {
        element = document.querySelector(element);
    }
    
    if (element) {
        element.scrollIntoView({ ...defaultOptions, ...options });
    }
}

// フォーカストラップ（アクセシビリティ向上）
function trapFocus(element) {
    const focusableElements = element.querySelectorAll(
        'a[href], button, textarea, input[type="text"], input[type="radio"], input[type="checkbox"], select'
    );
    const firstFocusableElement = focusableElements[0];
    const lastFocusableElement = focusableElements[focusableElements.length - 1];

    element.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            if (e.shiftKey) {
                if (document.activeElement === firstFocusableElement) {
                    lastFocusableElement.focus();
                    e.preventDefault();
                }
            } else {
                if (document.activeElement === lastFocusableElement) {
                    firstFocusableElement.focus();
                    e.preventDefault();
                }
            }
        }
    });
}

// インタラクティブボタン効果
function addButtonEffects() {
    const buttons = document.querySelectorAll('button, .btn');
    buttons.forEach(button => {
        if (!button.hasAttribute('data-effects-added')) {
            button.setAttribute('data-effects-added', 'true');
            
            // クリック時のリップル効果
            button.addEventListener('click', function(e) {
                const ripple = document.createElement('span');
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;
                
                ripple.style.cssText = `
                    position: absolute;
                    width: ${size}px;
                    height: ${size}px;
                    left: ${x}px;
                    top: ${y}px;
                    background: rgba(255, 255, 255, 0.3);
                    border-radius: 50%;
                    transform: scale(0);
                    animation: ripple 0.6s linear;
                    pointer-events: none;
                `;
                
                this.style.position = 'relative';
                this.style.overflow = 'hidden';
                this.appendChild(ripple);
                
                setTimeout(() => {
                    if (ripple.parentNode) {
                        ripple.parentNode.removeChild(ripple);
                    }
                }, 600);
            });
            
            // ホバー効果の強化
            button.addEventListener('mouseenter', function() {
                this.style.transform = 'translateY(-1px)';
                this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
            });
            
            button.addEventListener('mouseleave', function() {
                this.style.transform = 'translateY(0)';
                this.style.boxShadow = '';
            });
        }
    });
    
    // リップルアニメーション
    if (!document.getElementById('ripple-styles')) {
        const style = document.createElement('style');
        style.id = 'ripple-styles';
        style.textContent = `
            @keyframes ripple {
                to {
                    transform: scale(4);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);
    }
}

// オートセーブ機能
function setupAutoSave(formSelector, saveCallback, interval = 30000) {
    const form = document.querySelector(formSelector);
    if (!form) return;
    
    let autoSaveTimer;
    let hasChanges = false;
    
    const inputs = form.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        input.addEventListener('input', () => {
            hasChanges = true;
            clearTimeout(autoSaveTimer);
            autoSaveTimer = setTimeout(() => {
                if (hasChanges) {
                    saveCallback();
                    hasChanges = false;
                    showToast('自動保存しました', 'info', 2000);
                }
            }, interval);
        });
    });
}

// ページ読み込み進捗表示
function showPageProgress() {
    const progressBar = document.createElement('div');
    progressBar.id = 'page-progress';
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 0%;
        height: 3px;
        background: linear-gradient(90deg, var(--color-primary), var(--color-accent));
        z-index: 10002;
        transition: width 0.3s ease;
    `;
    document.body.appendChild(progressBar);
    
    let progress = 0;
    const timer = setInterval(() => {
        progress += Math.random() * 15;
        if (progress >= 90) {
            progress = 90;
            clearInterval(timer);
        }
        progressBar.style.width = progress + '%';
    }, 100);
    
    window.addEventListener('load', () => {
        clearInterval(timer);
        progressBar.style.width = '100%';
        setTimeout(() => {
            progressBar.style.opacity = '0';
            setTimeout(() => {
                if (progressBar.parentNode) {
                    progressBar.parentNode.removeChild(progressBar);
                }
            }, 300);
        }, 200);
    });
}

/**
 * 新しいアコーディオンシステム - より効率的で現代的なアプローチ
 */
function toggleDetailContent(toggleElement) {
    const content = toggleElement.nextElementSibling;
    const icon = toggleElement.querySelector('.detail-toggle-icon');
    const isExpanded = toggleElement.getAttribute('aria-expanded') === 'true';
    
    // ARIA属性を更新
    toggleElement.setAttribute('aria-expanded', !isExpanded);
    
    // コンテンツの表示/非表示を切り替え
    if (isExpanded) {
        content.classList.remove('open');
        content.style.maxHeight = '0';
        toggleElement.querySelector('span').textContent = '詳細を表示';
    } else {
        content.classList.add('open');
        // 実際の高さを計算して設定
        const scrollHeight = content.scrollHeight;
        content.style.maxHeight = scrollHeight + 'px';
        toggleElement.querySelector('span').textContent = '詳細を隠す';
    }
    
    // アニメーション完了後に高さをautoに設定（レスポンシブ対応）
    if (!isExpanded) {
        setTimeout(() => {
            if (content.classList.contains('open')) {
                content.style.maxHeight = 'none';
            }
        }, 300);
    }
}

/**
 * すべての詳細コンテンツを閉じる
 */
function closeAllDetails() {
    const allToggles = document.querySelectorAll('.detail-toggle[aria-expanded="true"]');
    allToggles.forEach(toggle => {
        toggleDetailContent(toggle);
    });
}

/**
 * 詳細コンテンツを初期化
 */
function initializeDetailToggles() {
    const toggles = document.querySelectorAll('.detail-toggle');
    
    toggles.forEach(toggle => {
        // 初期状態を設定
        if (!toggle.hasAttribute('aria-expanded')) {
            toggle.setAttribute('aria-expanded', 'false');
        }
        
        // クリックイベントを追加
        toggle.addEventListener('click', (e) => {
            e.preventDefault();
            toggleDetailContent(toggle);
        });
        
        // キーボードアクセシビリティ
        toggle.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleDetailContent(toggle);
            }
        });
    });
}

/**
 * 詳細コンテンツの動的生成
 */
function createDetailToggle(title, content, isOpen = false) {
    const wrapper = document.createElement('div');
    wrapper.className = 'detail-wrapper';
    
    const toggle = document.createElement('button');
    toggle.className = 'detail-toggle';
    toggle.setAttribute('aria-expanded', isOpen.toString());
    toggle.innerHTML = `
        <span>${isOpen ? '詳細を隠す' : '詳細を表示'}</span>
        <i class="material-icons detail-toggle-icon">expand_more</i>
    `;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = `detail-content ${isOpen ? 'open' : ''}`;
    contentDiv.innerHTML = `<div class="detail-content-inner">${content}</div>`;
    
    wrapper.appendChild(toggle);
    wrapper.appendChild(contentDiv);
    
    // イベントリスナーを追加
    toggle.addEventListener('click', (e) => {
        e.preventDefault();
        toggleDetailContent(toggle);
    });
    
    return wrapper;
}

// 後方互換性のための関数
function toggleAccordion(headerElement) {
    // 新しいシステムに対応
    if (headerElement.classList.contains('detail-toggle')) {
        toggleDetailContent(headerElement);
    } else {
        // 古いシステムのフォールバック
        console.warn('古いアコーディオンシステムが使用されています。新しいシステムに移行してください。');
    }
}

// グローバル関数をwindowオブジェクトに追加
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.showToast = showToast;
window.removeToast = removeToast;
window.apiCall = apiCall;
window.submitForm = submitForm;
window.formatCurrency = formatCurrency;
window.formatNumber = formatNumber;
window.calculateAge = calculateAge;
window.formatDate = formatDate;
window.showModal = showModal;
window.hideModal = hideModal;
window.validateRequired = validateRequired;
window.validateField = validateField;
window.saveToStorage = saveToStorage;
window.loadFromStorage = loadFromStorage;
window.debounce = debounce;
window.escapeHtml = escapeHtml;
window.smoothScrollTo = smoothScrollTo;
window.trapFocus = trapFocus;
window.addButtonEffects = addButtonEffects;
window.setupAutoSave = setupAutoSave;
window.showPageProgress = showPageProgress;
window.createPageTransition = createPageTransition;
window.toggleAccordion = toggleAccordion;
window.toggleDetailContent = toggleDetailContent;
window.closeAllDetails = closeAllDetails;
window.initializeDetailToggles = initializeDetailToggles;
window.createDetailToggle = createDetailToggle;
window.stabilizeFooter = stabilizeFooter;
window.optimizeAppScrolling = optimizeAppScrolling;
window.optimizeFooterTouch = optimizeFooterTouch;

/**
 * フッターの固定位置を安定化
 */
function stabilizeFooter() {
    const footer = document.querySelector('.footer-nav');
    if (!footer) return;
    
    // アプリモードの検出
    const isApp = document.body.classList.contains('client-app');
    
    if (isApp) {
        // アプリ用のフッター固定強化
        footer.style.position = 'fixed';
        footer.style.bottom = '0';
        footer.style.left = '0';
        footer.style.right = '0';
        footer.style.transform = 'translate3d(0, 0, 0)';
        footer.style.webkitTransform = 'translate3d(0, 0, 0)';
        footer.style.willChange = 'transform';
        footer.style.webkitBackfaceVisibility = 'hidden';
        footer.style.backfaceVisibility = 'hidden';
        
        // スクロール時の位置監視
        let ticking = false;
        
        function updateFooterPosition() {
            if (!ticking) {
                requestAnimationFrame(() => {
                    // フッターの位置を強制的に底部に固定
                    footer.style.bottom = '0';
                    footer.style.transform = 'translate3d(0, 0, 0)';
                    ticking = false;
                });
                ticking = true;
            }
        }
        
        // スクロールイベントの監視
        window.addEventListener('scroll', updateFooterPosition, { passive: true });
        window.addEventListener('touchmove', updateFooterPosition, { passive: true });
        window.addEventListener('resize', updateFooterPosition, { passive: true });
        
        // 画面向き変更時の対応
        window.addEventListener('orientationchange', () => {
            setTimeout(() => {
                updateFooterPosition();
                // 高さを再計算
                const safeAreaBottom = getComputedStyle(document.documentElement)
                    .getPropertyValue('--safe-area-inset-bottom') || '0px';
                footer.style.paddingBottom = `calc(var(--spacing-sm) + ${safeAreaBottom})`;
            }, 100);
        });
        
        // 初期位置設定
        updateFooterPosition();
    }
}

/**
 * アプリモード用のスクロール最適化
 */
function optimizeAppScrolling() {
    if (!document.body.classList.contains('client-app')) return;
    
    // スクロール最適化
    document.documentElement.style.webkitOverflowScrolling = 'touch';
    document.body.style.webkitOverflowScrolling = 'touch';
    
    // フッターとメインコンテンツの高さ調整
    const mainContent = document.querySelector('.main-content');
    const footer = document.querySelector('.footer-nav');
    
    if (mainContent && footer) {
        function adjustContentHeight() {
            const footerHeight = footer.offsetHeight;
            const safeAreaBottom = parseInt(getComputedStyle(document.documentElement)
                .getPropertyValue('--safe-area-inset-bottom') || '0px');
            
            mainContent.style.paddingBottom = `${footerHeight + safeAreaBottom}px`;
        }
        
        // 初期調整
        adjustContentHeight();
        
        // リサイズ時の再調整
        window.addEventListener('resize', adjustContentHeight);
        window.addEventListener('orientationchange', () => {
            setTimeout(adjustContentHeight, 100);
        });
    }
}

/**
 * フッターアイテムのタッチ最適化
 */
function optimizeFooterTouch() {
    const footerItems = document.querySelectorAll('.footer-item');
    
    footerItems.forEach(item => {
        // タッチフィードバックの改善
        item.addEventListener('touchstart', function(e) {
            this.style.transform = 'scale(0.95)';
            this.style.backgroundColor = 'rgba(0, 0, 0, 0.05)';
        }, { passive: true });
        
        item.addEventListener('touchend', function(e) {
            setTimeout(() => {
                this.style.transform = '';
                this.style.backgroundColor = '';
            }, 150);
        }, { passive: true });
        
        item.addEventListener('touchcancel', function(e) {
            this.style.transform = '';
            this.style.backgroundColor = '';
        }, { passive: true });
    });
}

// DOMContentLoadedイベントでの初期化
document.addEventListener('DOMContentLoaded', function() {
    // 基本的な初期化
    initializeYearSelects();
    addButtonEffects();
    initializeDetailToggles();
    
    // フッター関連の初期化（アプリ経由の場合）
    if (document.body.classList.contains('client-app')) {
        console.log('アプリモード: フッター最適化を実行中...');
        
        // フッターの固定位置安定化
        stabilizeFooter();
        
        // スクロール最適化
        optimizeAppScrolling();
        
        // タッチ最適化
        optimizeFooterTouch();
        
        console.log('アプリモード: フッター最適化完了');
    }
    
    // ページ読み込み進捗表示
    if (document.readyState === 'loading') {
        showPageProgress();
    }
    
    // モーダルの外側クリックで閉じる（アニメーション付き）
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal-overlay')) {
            const modal = e.target;
            modal.style.opacity = '0';
            setTimeout(() => {
                modal.classList.add('hidden');
                document.body.style.overflow = '';
                modal.style.opacity = '';
            }, 300);
        }
    });
    
    // ESCキーでモーダルを閉じる
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const visibleModals = document.querySelectorAll('.modal-overlay:not(.hidden)');
            visibleModals.forEach(modal => {
                modal.style.opacity = '0';
                setTimeout(() => {
                    modal.classList.add('hidden');
                    modal.style.opacity = '';
                }, 300);
            });
            document.body.style.overflow = '';
        }
    });
    
    // スムーズスクロールの設定
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                smoothScrollTo(target);
            }
        });
    });
    
    // カードのホバー効果
    document.querySelectorAll('.card').forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 4px 20px rgba(0, 0, 0, 0.1)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = '';
            this.style.boxShadow = '';
        });
    });
});

// フローティングボタンの設定（共通関数）
function setupFormFab() {
    const fabButton = document.getElementById('formFabButton');
    const cancelButton = document.getElementById('cancelFabButton');
    
    if (fabButton) {
        // タッチデバイスでの反応性向上
        fabButton.addEventListener('touchstart', function() {
            this.style.transform = 'scale(0.95)';
        }, { passive: true });
        
        fabButton.addEventListener('touchend', function() {
            this.style.transform = '';
        }, { passive: true });
        
        fabButton.addEventListener('touchcancel', function() {
            this.style.transform = '';
        }, { passive: true });
    }
    
    if (cancelButton) {
        // キャンセルボタンのタッチ最適化
        cancelButton.addEventListener('touchstart', function() {
            this.style.transform = 'scale(0.95)';
        }, { passive: true });
        
        cancelButton.addEventListener('touchend', function() {
            this.style.transform = '';
        }, { passive: true });
        
        cancelButton.addEventListener('touchcancel', function() {
            this.style.transform = '';
        }, { passive: true });
    }
}

// フローティングボタンからのフォーム送信（共通関数）
function submitFormViaFab() {
    // フォームIDを自動検出
    const forms = [
        'housingExpenseForm',
        'insuranceExpenseForm', 
        'educationExpenseForm',
        'livingExpensesForm',
        'eventExpenseForm',
        'salaryIncomeForm',
        'otherIncomeForm',
        'investmentIncomeForm',
        'pensionIncomeForm',
        'sidejobIncomeForm',
        'businessIncomeForm'
    ];
    
    let targetForm = null;
    for (const formId of forms) {
        const form = document.getElementById(formId);
        if (form) {
            targetForm = form;
            break;
        }
    }
    
    const fabButton = document.getElementById('formFabButton');
    
    if (!targetForm) {
        showToast('フォームが見つかりません', 'error');
        return;
    }
    
    // FABボタンをローディング状態にする
    if (fabButton) {
        fabButton.classList.add('loading');
        const icon = fabButton.querySelector('.material-icons');
        const originalIcon = icon.textContent;
        icon.textContent = 'sync';
        
        // ローディング状態を解除（送信処理完了後）
        setTimeout(() => {
            if (fabButton) {
                fabButton.classList.remove('loading');
                icon.textContent = originalIcon;
            }
        }, 2000);
    }
    
    // フォーム送信
    const submitEvent = new Event('submit', {
        bubbles: true,
        cancelable: true
    });
    
    targetForm.dispatchEvent(submitEvent);
}

// フッターの支出・収入ポップアップを表示
function showExpenseIncomePopup() {
    const popup = document.getElementById('expense-income-popup-overlay');
    if (popup) {
        popup.style.display = 'flex';
        setTimeout(() => {
            popup.classList.add('show');
            document.body.style.overflow = 'hidden';
        }, 10);
    }
}
window.showExpenseIncomePopup = showExpenseIncomePopup; 