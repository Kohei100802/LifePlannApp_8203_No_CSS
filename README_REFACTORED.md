# ライフプランアプリ（リファクタリング版）

## 概要
個人の収支管理とライフプランシミュレーションを行うWebアプリケーション。
Flask + SQLAlchemyを使用し、モジュール化されたクリーンなアーキテクチャで実装。

## プロジェクト構造

```
203_lifeplannApp_8203_no_CSS/
├── app/                      # アプリケーションパッケージ
│   ├── __init__.py          # アプリケーションファクトリー
│   ├── config/              # 設定管理
│   │   └── __init__.py      # 環境別設定
│   ├── models/              # データベースモデル
│   │   ├── __init__.py
│   │   ├── enums.py         # 列挙型定義
│   │   ├── user.py          # ユーザーモデル
│   │   ├── expenses.py      # 支出モデル
│   │   ├── incomes.py       # 収入モデル
│   │   ├── simulation.py    # シミュレーションモデル
│   │   └── household.py     # 家計簿モデル
│   ├── routes/              # ルート定義
│   │   ├── __init__.py
│   │   ├── auth.py          # 認証関連
│   │   ├── main.py          # メインページ
│   │   ├── api.py           # 共通API
│   │   ├── expenses.py      # 支出管理
│   │   ├── incomes.py       # 収入管理
│   │   ├── simulation.py    # シミュレーション
│   │   └── household.py     # 家計簿
│   ├── services/            # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── calculation.py   # 計算処理
│   │   └── export.py        # エクスポート処理
│   └── utils/               # ユーティリティ
│       ├── __init__.py
│       ├── error_handlers.py # エラーハンドリング
│       └── context_processors.py # コンテキスト処理
├── static/                  # 静的ファイル
├── templates/               # HTMLテンプレート
├── logs/                    # ログファイル
├── instance/                # インスタンス固有ファイル
├── .env                     # 環境変数
├── run.py                   # エントリーポイント
├── requirements.txt         # 依存関係
└── README.md               # このファイル
```

## 主な改善点

### 1. モジュール化
- 5000行以上の単一ファイルを機能別に分割
- 責任の分離と保守性の向上
- 循環参照の回避

### 2. 設定管理
- 環境変数による設定管理
- 開発/本番環境の分離
- セキュリティの向上

### 3. エラーハンドリング
- 統一的なエラー処理
- 詳細なログ記録
- ユーザーフレンドリーなエラー表示

### 4. コードの再利用性
- 共通処理の抽出
- DRY原則の適用
- テスタビリティの向上

## セットアップ

### 1. 環境変数の設定
```bash
cp .env.example .env
# .envファイルを編集して適切な値を設定
```

### 2. 依存関係のインストール
```bash
pip install -r requirements.txt
```

### 3. アプリケーションの起動
```bash
python run.py
```

または

```bash
python3.10 run.py
```

## 環境変数

| 変数名 | 説明 | デフォルト値 |
|--------|------|--------------|
| FLASK_ENV | 実行環境 | development |
| FLASK_DEBUG | デバッグモード | True |
| SECRET_KEY | セッションキー | (要変更) |
| DATABASE_URL | データベースURL | sqlite:///lifeplan.db |
| APP_PORT | ポート番号 | 8203 |
| APP_HOST | ホスト | 0.0.0.0 |

## 機能一覧

### 認証機能
- ユーザー登録/ログイン/ログアウト
- セッション管理
- パスワードハッシュ化

### 収支管理
- 収入管理（給与、副業、投資、年金等）
- 支出管理（生活費、教育費、住居費、保険等）
- カテゴリ別管理

### シミュレーション
- ライフプランシミュレーション
- 年齢別収支予測
- グラフ表示

### 家計簿機能
- 月次家計簿
- カレンダー表示
- 収支サマリー

### その他
- 日経平均株価表示
- データエクスポート
- モバイル対応

## 開発者向け情報

### テスト実行
```bash
pytest tests/
```

### コード品質チェック
```bash
flake8 app/
black app/
```

### データベースマイグレーション
```bash
flask db init
flask db migrate -m "メッセージ"
flask db upgrade
```

## ライセンス
MIT License 