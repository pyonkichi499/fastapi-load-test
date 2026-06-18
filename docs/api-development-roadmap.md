# API開発ロードマップ

## 🎯 プロジェクト概要
FastAPIとDatabaseAccessorを使用して、気温記録とルービックキューブタイムのデータを活用するAPIを段階的に実装します。

## 🌳 ブランチ戦略

### メインブランチ
- `main` - 本番環境相当
- `develop` - 開発統合ブランチ

### フィーチャーブランチ命名規則
- `feature/api-{api-name}` - 各API実装用
- `feature/db-enhancement` - DatabaseAccessor拡張用

### 実装順序とブランチ
1. `feature/api-comfort-score` - 快適度スコアAPI
2. `feature/api-cube-progress` - 成長曲線API
3. `feature/api-zone-detection` - ゾーン状態検出API
4. `feature/api-temperature-predict` - 温度変化予測API
5. `feature/db-enhancement` - DatabaseAccessor拡張
6. `feature/api-energy-ranking` - 省エネランキングAPI

## 📋 共通事前準備

### 1. 開発環境セットアップ
```bash
# developブランチから最新を取得
git checkout develop
git pull origin develop

# Python仮想環境の準備
cd output
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. データベース接続設定
`.env`ファイルを作成:
```env
# PostgreSQL使用の場合
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=your_database

# SQLite使用の場合
DB_TYPE=sqlite
SQLITE_PATH=./test.db
```

### 3. テーブル作成
```sql
-- 気温記録テーブル
CREATE TABLE room_temperature (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    room_name VARCHAR(50) NOT NULL,
    temperature DECIMAL(5,2) NOT NULL,
    humidity DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ルービックキューブタイムテーブル
CREATE TABLE cube_times (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    player_name VARCHAR(100) NOT NULL,
    solve_time_ms INTEGER NOT NULL,
    scramble TEXT,
    cube_type VARCHAR(10) DEFAULT '3x3',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス作成
CREATE INDEX idx_room_temp_room_time ON room_temperature(room_name, timestamp);
CREATE INDEX idx_cube_player_time ON cube_times(player_name, timestamp);
```

## 🚀 Phase 1: 基礎API実装（初級）

この段階では、DatabaseAccessorの基本機能のみを使用してAPIを実装します。

- [快適度スコアAPI実装手順](./api-implementations/01-comfort-score-api.md)
- [成長曲線API実装手順](./api-implementations/02-cube-progress-api.md)
- [ゾーン状態検出API実装手順](./api-implementations/03-zone-detection-api.md)

## 🚀 Phase 2: 中級API実装

より複雑なロジックやデータ処理を含むAPIを実装します。

- [温度変化予測API実装手順](./api-implementations/04-temperature-predict-api.md)

## 🚀 Phase 3: DatabaseAccessor拡張

GROUP BYやウィンドウ関数に対応するための拡張を行います。

- [DatabaseAccessor拡張実装手順](./api-implementations/05-db-enhancement.md)

## 🚀 Phase 4: 上級API実装

拡張されたDatabaseAccessorを活用して、より高度なAPIを実装します。

- [省エネランキングAPI実装手順](./api-implementations/06-energy-ranking-api.md)

## 📊 進捗管理

### チェックリスト
- [ ] 開発環境セットアップ完了
- [ ] データベース接続確認
- [ ] テーブル作成完了
- [ ] Phase 1 完了
- [ ] Phase 2 完了
- [ ] Phase 3 完了
- [ ] Phase 4 完了

### コードレビュー観点
1. DatabaseAccessorの適切な使用
2. エラーハンドリング
3. 非同期処理の正しい実装
4. レスポンスモデルの適切な定義
5. テストカバレッジ

## 📚 参考資料
- [FastAPI公式ドキュメント](https://fastapi.tiangolo.com/)
- [SQLAlchemy非同期サポート](https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html)
- [Pydanticバリデーション](https://docs.pydantic.dev/)