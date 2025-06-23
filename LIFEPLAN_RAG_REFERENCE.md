# ライフプランアプリケーション RAG参照ファイル

## 📋 プロジェクト概要

### アプリケーション名
**ライフプランシミュレーター** - FP1級相当の精度を持つスマホ専用ライフプランシミュレーションWebアプリケーション

### 技術スタック
- **バックエンド**: Flask 2.3.3 + SQLAlchemy + SQLite
- **フロントエンド**: HTML5 + CSS3 + JavaScript + Chart.js
- **認証**: Flask-Login
- **データベース**: SQLite (instance/lifeplan.db)
- **ポート**: 8203

### プロジェクト構造
```
203_lifeplannApp_8203/
├── app.py                 # メインアプリケーション (2231行)
├── requirements.txt       # 依存関係
├── README.md             # プロジェクト説明
├── templates/            # HTMLテンプレート
│   ├── base.html         # ベーステンプレート
│   ├── index.html        # トップページ
│   ├── login.html        # ログインページ
│   ├── register.html     # 登録ページ
│   ├── dashboard.html    # ダッシュボード
│   ├── simulation.html   # シミュレーション (851行)
│   ├── expenses.html     # 支出管理
│   ├── incomes.html      # 収入管理
│   ├── error.html        # エラーページ
│   ├── expenses/         # 支出詳細テンプレート
│   └── incomes/          # 収入詳細テンプレート
├── static/               # 静的ファイル
│   ├── css/
│   │   └── styles.css    # メインスタイルシート (1827行)
│   ├── js/
│   │   ├── common.js     # 共通JavaScript (968行)
│   │   └── chart.min.js  # Chart.js ライブラリ
│   └── favicon.ico
├── instance/
│   └── lifeplan.db       # SQLiteデータベース
├── logs/
│   └── error.log         # エラーログ
└── backup_*/             # バックアップディレクトリ
```

## 🗄️ データベース設計

### ユーザー管理
- **users**: ユーザー情報 (id, username, password_hash, created_at)

### 支出管理テーブル
- **living_expenses**: 生活費 (食費、光熱費、通信費、日用品、被服・美容費など詳細項目)
- **education_expenses**: 教育費 (子供の進学パターン別自動計算)
- **housing_expenses**: 住居費 (賃貸・持家・ローン計算対応)
- **insurance_expenses**: 保険料 (医療、がん、生命、収入保障等)
- **event_expenses**: イベント費用 (結婚、出産、車、引越、介護等)

### 収入管理テーブル
- **salary_incomes**: 給与収入 (昇給率設定可能)
- **sidejob_incomes**: 副業収入
- **investment_incomes**: 投資収入 (運用利回り設定可能)
- **pension_incomes**: 年金収入
- **other_incomes**: その他収入

### シミュレーション管理
- **lifeplan_simulations**: シミュレーション設定
- **lifeplan_expense_links**: 支出データリンク
- **lifeplan_income_links**: 収入データリンク

### 教育計画管理
- **education_plans**: 教育計画 (統合管理)

## 🎯 主要機能

### 1. 認証システム
- ユーザー登録・ログイン・ログアウト
- セッション管理
- パスワードハッシュ化

### 2. 支出管理
- **生活費**: 月額ベース、物価上昇率考慮
- **教育費**: 進学パターン自動計算
- **住居費**: 住宅ローン自動計算（元利均等返済）
- **保険**: 各種保険料管理
- **イベント**: 一時的支出、繰り返し設定可能

### 3. 収入管理
- **給与**: 昇給率設定、ボーナス対応
- **副業**: 月額収入
- **投資**: 運用利回り設定
- **年金**: 公的・企業年金
- **その他**: その他収入源

### 4. シミュレーション機能
- 年次収支計算
- 累積収支推移
- Chart.js によるグラフ表示
- 詳細な年次テーブル表示
- トースト通知によるフィードバック

### 5. 外部データ連携
- 日経平均株価取得（yfinance使用）
- リアルタイム株価表示

## 🔧 API エンドポイント

### 認証
- `GET /` - トップページ
- `GET|POST /login` - ログイン
- `GET|POST /register` - ユーザー登録
- `GET /logout` - ログアウト

### ページ表示
- `GET /dashboard` - ダッシュボード
- `GET /expenses` - 支出管理
- `GET /incomes` - 収入管理
- `GET /simulation` - シミュレーション

### 支出API
- `GET|POST|PUT /api/living-expenses` - 生活費CRUD
- `GET|POST|PUT /api/education-expenses` - 教育費CRUD
- `GET|POST|PUT /api/housing-expenses` - 住居費CRUD
- `GET|POST|PUT /api/insurance-expenses` - 保険CRUD
- `GET|POST|PUT /api/event-expenses` - イベントCRUD
- `DELETE /api/{expense-type}/<int:id>` - 各種支出削除

### 収入API
- `GET|POST|PUT /api/salary-incomes` - 給与収入CRUD
- `GET|POST /api/sidejob-incomes` - 副業収入CRUD
- `GET|POST|PUT /api/investment-incomes` - 投資収入CRUD
- `GET|POST /api/pension-incomes` - 年金収入CRUD
- `GET|POST /api/other-incomes` - その他収入CRUD
- `DELETE /api/{income-type}/<int:id>` - 各種収入削除

### シミュレーション API
- `GET|POST|PUT /api/simulation-plans` - シミュレーション計画CRUD
- `GET|DELETE /api/simulation-plans/<int:id>` - 計画詳細・削除
- `POST /api/simulate` - シミュレーション実行

### その他API
- `GET /api/all-expenses` - 全支出データ取得
- `GET /api/all-incomes` - 全収入データ取得
- `GET /api/nikkei` - 日経平均取得
- `GET /favicon.ico` - ファビコン
- `POST /api/log` - クライアントエラーログ

## 📊 計算ロジック

### 教育費自動計算
```python
def calculate_education_costs(child_birth_date, kindergarten_type, elementary_type, junior_type, high_type, college_type):
    # 年齢別教育段階判定
    # 月額費用設定（幼稚園: 公立22,000円/私立48,000円 等）
    # 期間計算と総額算出
```

### 住宅ローン計算
```python
def calculate_mortgage_payment(loan_amount, interest_rate, term_years, repayment_method):
    # 元利均等返済: 月額 = 借入額 × [月利 × (1+月利)^返済回数] / [(1+月利)^返済回数-1]
```

### シミュレーション計算
- 年次ベースでの収支計算
- 昇給率・物価上昇率・運用利回り考慮
- 累積収支推移計算

## 🎨 UI/UX設計

### デザインシステム
- **Apple Human Interface Guidelines準拠**
- **カラーパレット**: システムカラー使用
- **フォント**: -apple-system, 17px基準
- **最小タップ領域**: 44×44px
- **角丸**: 12px統一

### レスポンシブ対応
- **モバイルファースト**: 320px〜対応
- **セーフエリア**: iOS対応
- **ダークモード**: システム設定連動

### JavaScript機能
- **Chart.js**: グラフ描画（累積収支・年次収支）
- **Toast通知**: 成功・エラーメッセージ
- **Ajax通信**: 非同期データ更新
- **フォームバリデーション**: クライアントサイド検証

## 🚨 エラーハンドリング

### サーバーサイド
- 404エラー: favicon.ico等の無視パス設定
- 例外ハンドリング: 詳細ログ出力
- ログローテーション: 10MB上限、10ファイル保持

### クライアントサイド
- Ajax エラーハンドリング
- ユーザーフレンドリーなエラーメッセージ
- 入力値検証

## 🔄 最近の主要変更

### 2025-06-18 大幅簡素化
- **デバッグ機能削除**: 複雑なデバッグパネル・ログシステム除去
- **Chart.js簡素化**: 単一CDN読み込みに変更
- **Toast通知復活**: シンプルな成功・エラー通知
- **シミュレーション機能復旧**: CRUD操作、グラフ表示、結果テーブル

### バックアップ管理
- **最新バックアップ**: backup_20250618_072626/
- **アーカイブ**: backup_20250618_072626.tar.gz (148KB)
- **バックアップ内容**: 全ソースコード、データベース、設定ファイル

## 🏃‍♂️ 起動方法

```bash
# 依存関係インストール
pip3 install -r requirements.txt

# アプリケーション起動
python3 -m flask --app app run --host=0.0.0.0 --port=8203

# アクセス URL
# ローカル: http://127.0.0.1:8203
# ネットワーク: http://10.32.1.63:8203
```

## 🔍 トラブルシューティング

### よくある問題
1. **ポート8203使用中**: `pkill -f "flask.*8203"` で既存プロセス終了
2. **データベースエラー**: instance/lifeplan.db の権限確認
3. **Chart.js読み込み失敗**: CDN接続確認
4. **セッションエラー**: ブラウザキャッシュクリア

### ログ確認
```bash
# エラーログ確認
tail -f logs/error.log

# アプリケーションログ（コンソール出力）
# Flask起動時のコンソール出力を確認
```

## 📈 パフォーマンス

### 最適化ポイント
- SQLite インデックス設定
- 静的ファイルキャッシュ
- Chart.js 軽量化
- Ajax 非同期処理

### メモリ使用量
- アプリケーション: 約50MB
- データベース: 約5MB（標準データ）
- 静的ファイル: 約300KB

---

**このファイルは Cursor AI がライフプランアプリケーションの全体像を理解するためのRAG参照ファイルです。**
**最終更新: 2025-06-18** 