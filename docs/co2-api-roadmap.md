# CO2モニタリングAPI開発ロードマップ

## 🎯 プロジェクト概要
CO2濃度と温度データを元に、室内空気質を評価し換気タイミングを提案するAPIを開発

### 技術スタック
- **Backend**: FastAPI + Python
- **Database**: BigQuery (本番) / SQLite (開発)
- **Deploy**: Cloud Run
- **認証**: サービスアカウント

### データソース
- **テーブル**: `room_temperature.bedroom_co2`
- **頻度**: 1レコード/分
- **項目**: datetime, temperature, co2, data

## 📋 Issue駆動開発フロー

### Phase 1: 基盤構築
1. **Issue #1**: BigQuery接続ライブラリの実装
2. **Issue #2**: 環境設定とテーブルアクセス確認
3. **Issue #3**: ローカル開発用SQLiteセットアップ

### Phase 2: データアクセス層
4. **Issue #4**: AirQualityDatabaseAccessor実装
5. **Issue #5**: BigQuery専用クエリ実装
6. **Issue #6**: CO2分析ロジック実装

### Phase 3: API層
7. **Issue #7**: Pydanticモデル定義
8. **Issue #8**: CO2ステータスAPI実装
9. **Issue #9**: エラーハンドリングと入力検証

### Phase 4: テスト・デプロイ
10. **Issue #10**: 単体テスト実装
11. **Issue #11**: Cloud Run対応とデプロイ設定
12. **Issue #12**: パフォーマンス最適化

## 🚀 開発フロー

### ブランチ戦略
```
main
  ├── develop
  │   ├── feature/issue-001-bigquery-connection
  │   ├── feature/issue-002-env-setup
  │   └── ...
```

### Issue → PR → マージの流れ
1. Issue作成・アサイン
2. ブランチ作成 (`feature/issue-XXX-description`)
3. 実装・テスト
4. PR作成・レビュー
5. develop へマージ
6. Issue クローズ

## 📅 想定スケジュール

- **Week 1**: Phase 1-2 (基盤・データアクセス)
- **Week 2**: Phase 3 (API実装)
- **Week 3**: Phase 4 (テスト・デプロイ)

## 🎯 成果物

### API エンドポイント
```
GET /api/air-quality/co2-status
  ?hours=3&include_timeline=true
```

### レスポンス例
```json
{
  "status": "注意",
  "current": {"co2": 950, "temperature": 23.5},
  "analysis": {"trend": "上昇傾向", "high_co2_duration_minutes": 45},
  "message": "CO2濃度が上昇傾向です。換気を検討してください",
  "action": "換気推奨"
}
```

## 📖 参考ドキュメント
- [BigQuery Python クライアント](https://cloud.google.com/bigquery/docs/quickstarts/quickstart-client-libraries)
- [FastAPI 公式ドキュメント](https://fastapi.tiangolo.com/)
- [Cloud Run デプロイガイド](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-service)