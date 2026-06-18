# Issue #1: BigQuery接続ライブラリの実装

## 📋 概要
BigQueryに接続してCO2データを取得するためのライブラリを実装する

## 🎯 目標
- BigQueryクライアントの初期化
- 認証設定（サービスアカウント）
- 基本的なクエリ実行機能
- エラーハンドリング

## 📝 詳細要件

### 実装するクラス
```python
class BigQueryClient:
    def __init__(self, project_id: str = "monitoring-bedroom")
    async def execute_query(self, query: str, params: dict = None) -> List[Dict]
    async def test_connection(self) -> bool
```

### 設定項目
- プロジェクトID: `monitoring-bedroom`
- 認証: サービスアカウント（Cloud Run環境）
- ローカル開発: Application Default Credentials

### 依存関係
```
google-cloud-bigquery>=3.0.0
google-auth>=2.0.0
```

## ✅ 完了条件
- [ ] BigQueryClientクラスの実装
- [ ] 認証の動作確認
- [ ] 基本的なクエリが実行できる
- [ ] エラー時の適切な例外処理
- [ ] ローカル環境でのテスト実行

## 🧪 テスト内容
```python
async def test_bigquery_connection():
    client = BigQueryClient()
    assert await client.test_connection() == True

async def test_simple_query():
    client = BigQueryClient()
    result = await client.execute_query("SELECT 1 as test")
    assert result[0]["test"] == 1
```

## 📁 ファイル構成
```
src/database/
├── bigquery_client.py  # 新規作成
└── __init__.py         # 更新
```

## 🔗 関連Issue
- 次のIssue: #2 環境設定とテーブルアクセス確認

## 📚 参考資料
- [BigQuery Python クライアント](https://cloud.google.com/bigquery/docs/quickstarts/quickstart-client-libraries)
- [認証設定](https://cloud.google.com/docs/authentication/getting-started)