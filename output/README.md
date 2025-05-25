# FastAPI Load Test

API that returns current time in JST (Japan Standard Time)

## Installation & Usage (venv + pip)

**1. Create and activate a virtual environment:**

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
```

**2. Install dependencies:**

```bash
pip install -r requirements.txt
```

**3. Run the server:**

```bash
PYTHONPATH=src uvicorn openapi_server.main:app --host 0.0.0.0 --port 8080
```

Access the API docs at [http://localhost:8080/docs/](http://localhost:8080/docs/).

## Testing (venv + pip)

**1. Ensure your virtual environment is active and development dependencies are installed.**
   (Development dependencies like pytest are currently managed in `pyproject.toml` under `[tool.rye].dev-dependencies` or `[project.optional-dependencies].dev`. You might need to install them manually in your venv if not using rye for dev.)

   Example for pytest:
   ```bash
   pip install pytest pytest-asyncio httpx freezegun
   ```

**2. Run tests:**

```bash
PYTHONPATH=src pytest
```

## Docker

To build and run the application using Docker:

```bash
docker compose up -d --build
```

This will use the `Dockerfile` which sets up a venv environment and installs dependencies from `requirements.txt`.

## 単体テストによる保証範囲

単体テストは、データベースアクセス層 (`DatabaseAccessor`) およびその設定 (`DatabaseSettings`) の信頼性と正確性を保証することを目的としています。

**テストによってカバーされる主要な観点:**

**1. `DatabaseSettings` (設定 - `tests/database/test_config.py`):**
    *   **設定の読み込み:**
        *   環境変数からのPostgreSQLおよびSQLite接続パラメータの正しい読み込み。
        *   SQLiteのインメモリモードの適切な処理。
        *   `.env` ファイルからの設定の優先的な読み込み。
    *   **DSN (Data Source Name) 生成:**
        *   PostgreSQL用のDSN（`asyncpg` ドライバを含む）の正確な生成。
        *   SQLite用のDSN（`aiosqlite` ドライバを含む）の正確な生成（ファイルベースおよびインメモリデータベースの両方）。
    *   **バリデーションとエラーハンドリング:**
        *   必須パラメータ（例: PostgreSQLの認証情報）が欠落している場合にエラーが発生することの確認。
        *   SQLiteパスに対する正しいデフォルト値の適用とエラーハンドリング。
        *   サポートされていないデータベースタイプが拒否されること。
        *   環境変数がデフォルト設定を正しく上書きすることの確認。
        *   未定義の余分な環境変数が無視されることの検証。

**2. `DatabaseAccessor` (データアクセス - `tests/database/test_accessor.py`, `tests/database/test_accessor_postgres.py`):**
    *   **コアデータ取得 (`fetch_records`):**
        *   指定されたテーブルからの全カラムおよび全レコードの取得。
        *   特定カラムの選択。
    *   **フィルタリングロジック:**
        *   単一条件によるフィルタリング。
        *   複数AND条件によるフィルタリング。
        *   IN句によるフィルタリング (例: `column IN (value1, value2)`)。
        *   真偽値によるフィルタリング。
    *   **ソート (`order_by`):**
        *   単一カラムによるソート（昇順および降順）。
        *   複数カラムによるソート。
    *   **ページネーション (`limit`, `offset`):**
        *   返されるレコード数の制限。
        *   レコード取得開始位置のオフセット。
        *   limitとoffsetの組み合わせ利用。
    *   **エッジケースとエラーハンドリング:**
        *   フィルタ基準に一致するレコードがない場合に空リストを返すこと。
        *   存在しないテーブルやカラム（select、filter、order by句内）に対する操作で `DatabaseQueryError` が発生すること。
        *   無効な（負の）limitまたはoffset値に対して `ValueError` が発生すること。
    *   **接続管理:**
        *   データベース設定が無効または不完全な場合に、初期化中に `DatabaseConnectionError` が発生すること。
    *   **データベース間の互換性:**
        *   SQLiteとPostgreSQLの両方でコア機能が一貫して動作することの保証（PostgreSQLテストは環境の利用可否に依存）。

これらのテストは、データベース対話コンポーネントが堅牢であり、設定を正しく処理し、柔軟かつ安全なデータ取得を可能にすることへの信頼性を提供します。
