# ゾーン状態検出API実装手順

## 概要
ルービックキューブのソルブで、連続して好タイムが出ている「ゾーン状態」を検出し、現在の調子を数値化するAPIです。

## ブランチ作成
```bash
git checkout develop
git pull origin develop
git checkout -b feature/api-zone-detection
```

## 実装手順

### 1. レスポンスモデルの作成
`src/openapi_server/models/zone_detection.py`:
```python
from pydantic import BaseModel
from datetime import datetime
from typing import List

class RecentSolve(BaseModel):
    timestamp: datetime
    solve_time_ms: int
    solve_time_seconds: float
    deviation_from_average: float  # 平均からの偏差（秒）
    performance_rating: int  # パフォーマンス評価（0-100）

class ZoneMetrics(BaseModel):
    current_average: float  # 直近10回の平均
    personal_best_average: float  # 過去30日のベスト平均
    standard_deviation: float  # 標準偏差
    consistency_rating: float  # 一貫性評価（0-100）
    zone_score: float  # ゾーンスコア（0-100）

class ZoneDetectionResponse(BaseModel):
    player_name: str
    is_in_zone: bool
    zone_level: str  # "Not in Zone", "Entering Zone", "In the Zone", "Peak Performance"
    recent_solves: List[RecentSolve]
    metrics: ZoneMetrics
    message: str
    recommendations: List[str]
```

### 2. API実装クラスの作成
`src/openapi_server/impl/zone_detection_api_impl.py`:
```python
from datetime import datetime, timedelta
import statistics
from typing import List, Tuple
from fastapi import HTTPException

from openapi_server.apis.zone_detection_api_base import BaseZoneDetectionApi
from database.accessor import DatabaseAccessor
from database.config import get_db_settings
from openapi_server.models.zone_detection import (
    ZoneDetectionResponse, RecentSolve, ZoneMetrics
)

class ZoneDetectionApiImpl(BaseZoneDetectionApi):
    def __init__(self):
        self.settings = get_db_settings()
        self.db_accessor = DatabaseAccessor(self.settings)
    
    def calculate_performance_rating(self, time: float, avg: float, std_dev: float) -> int:
        """個別のソルブのパフォーマンス評価"""
        if std_dev == 0:
            return 50
        
        # 標準スコア（Zスコア）を計算
        z_score = (avg - time) / std_dev
        
        # Zスコアを0-100の評価に変換
        # z_score = 2 (2σ速い) → 100点
        # z_score = 0 (平均) → 50点
        # z_score = -2 (2σ遅い) → 0点
        rating = 50 + (z_score * 25)
        return max(0, min(100, int(rating)))
    
    def calculate_zone_score(
        self, 
        recent_times: List[float], 
        historical_avg: float,
        historical_std: float
    ) -> Tuple[float, bool, str]:
        """ゾーンスコアとゾーン状態を計算"""
        if len(recent_times) < 3:
            return 0.0, False, "Not enough data"
        
        recent_avg = statistics.mean(recent_times)
        recent_std = statistics.stdev(recent_times) if len(recent_times) > 1 else 0
        
        # 1. 速さスコア（過去の平均と比較）
        speed_improvement = (historical_avg - recent_avg) / historical_avg * 100
        speed_score = min(100, max(0, speed_improvement * 10))  # 10%改善で100点
        
        # 2. 安定性スコア（標準偏差の比較）
        if historical_std > 0:
            consistency_improvement = (historical_std - recent_std) / historical_std * 100
            consistency_score = min(100, max(0, consistency_improvement * 5))  # 20%改善で100点
        else:
            consistency_score = 50
        
        # 3. 連続性スコア（連続して良いタイムが出ているか）
        good_times = sum(1 for t in recent_times if t < historical_avg)
        streak_score = (good_times / len(recent_times)) * 100
        
        # 総合ゾーンスコア
        zone_score = (speed_score * 0.5 + consistency_score * 0.3 + streak_score * 0.2)
        
        # ゾーン判定
        if zone_score >= 80:
            is_in_zone = True
            zone_level = "Peak Performance"
        elif zone_score >= 65:
            is_in_zone = True
            zone_level = "In the Zone"
        elif zone_score >= 50:
            is_in_zone = False
            zone_level = "Entering Zone"
        else:
            is_in_zone = False
            zone_level = "Not in Zone"
        
        return zone_score, is_in_zone, zone_level
    
    def generate_recommendations(self, zone_level: str, metrics: ZoneMetrics) -> List[str]:
        """状態に応じたアドバイスを生成"""
        recommendations = []
        
        if zone_level == "Peak Performance":
            recommendations.extend([
                "素晴らしい調子です！このリズムを維持しましょう",
                "記録更新のチャンスです。集中を切らさないように",
                "水分補給を忘れずに、体調管理も大切です"
            ])
        elif zone_level == "In the Zone":
            recommendations.extend([
                "良い調子が続いています。深呼吸でリラックスを",
                "今の感覚を覚えておきましょう",
                "無理せず自然体で続けることが大切です"
            ])
        elif zone_level == "Entering Zone":
            recommendations.extend([
                "調子が上向いてきています",
                "ウォームアップを十分に行いましょう",
                "リズムを意識して、焦らずに"
            ])
        else:
            recommendations.extend([
                "一度休憩を取ってリフレッシュしましょう",
                "基本に立ち返って、正確性を重視してみては",
                "調子の波は誰にでもあります。焦らずに"
            ])
        
        # 一貫性に関するアドバイス
        if metrics.consistency_rating < 50:
            recommendations.append("タイムのばらつきが大きいようです。一定のペースを心がけましょう")
        
        return recommendations
    
    async def detect_zone_state(
        self,
        player_name: str,
        recent_count: int = 10
    ) -> ZoneDetectionResponse:
        """プレイヤーの現在のゾーン状態を検出"""
        
        # 直近のデータを取得
        try:
            recent_records = await self.db_accessor.fetch_records(
                table_name="cube_times",
                columns=["timestamp", "solve_time_ms"],
                filters={"player_name": player_name},
                order_by=[("timestamp", "DESC")],
                limit=recent_count
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        if not recent_records:
            raise HTTPException(status_code=404, detail=f"No data found for player: {player_name}")
        
        # 時系列順に並び替え（取得時はDESCなので逆順に）
        recent_records.reverse()
        
        # 過去30日の履歴データを取得（比較用）
        try:
            historical_records = await self.db_accessor.fetch_records(
                table_name="cube_times",
                columns=["solve_time_ms"],
                filters={"player_name": player_name},
                order_by=[("timestamp", "DESC")],
                limit=500  # 十分なデータを取得
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        # 時間でフィルタリング（30日以内）
        cutoff_date = datetime.now() - timedelta(days=30)
        historical_times = []
        for record in historical_records:
            # 注意: このフィルタリングは本来SQLで行うべき
            historical_times.append(record["solve_time_ms"] / 1000.0)
        
        if len(historical_times) < 20:
            # 履歴データが少ない場合は全データを使用
            historical_times = [r["solve_time_ms"] / 1000.0 for r in historical_records]
        
        # 統計計算
        recent_times = [r["solve_time_ms"] / 1000.0 for r in recent_records]
        historical_avg = statistics.mean(historical_times)
        historical_std = statistics.stdev(historical_times) if len(historical_times) > 1 else 0
        
        # 最近のソルブデータを作成
        recent_solves = []
        for record in recent_records:
            time_sec = record["solve_time_ms"] / 1000.0
            deviation = time_sec - historical_avg
            rating = self.calculate_performance_rating(time_sec, historical_avg, historical_std)
            
            recent_solves.append(RecentSolve(
                timestamp=record["timestamp"],
                solve_time_ms=record["solve_time_ms"],
                solve_time_seconds=time_sec,
                deviation_from_average=deviation,
                performance_rating=rating
            ))
        
        # メトリクス計算
        current_avg = statistics.mean(recent_times)
        current_std = statistics.stdev(recent_times) if len(recent_times) > 1 else 0
        
        # 過去30日のベスト平均（連続10回の最良平均）
        best_avg = historical_avg
        if len(historical_times) >= 10:
            for i in range(len(historical_times) - 9):
                window_avg = statistics.mean(historical_times[i:i+10])
                best_avg = min(best_avg, window_avg)
        
        # 一貫性評価
        consistency_rating = 100 - min(100, (current_std / current_avg * 100) * 2)
        
        # ゾーンスコア計算
        zone_score, is_in_zone, zone_level = self.calculate_zone_score(
            recent_times, historical_avg, historical_std
        )
        
        metrics = ZoneMetrics(
            current_average=current_avg,
            personal_best_average=best_avg,
            standard_deviation=current_std,
            consistency_rating=consistency_rating,
            zone_score=zone_score
        )
        
        # メッセージ生成
        if is_in_zone:
            message = f"🔥 {zone_level}! あなたは今絶好調です！"
        else:
            message = f"現在の状態: {zone_level}。もう少しで調子が上がりそうです。"
        
        # レコメンデーション生成
        recommendations = self.generate_recommendations(zone_level, metrics)
        
        return ZoneDetectionResponse(
            player_name=player_name,
            is_in_zone=is_in_zone,
            zone_level=zone_level,
            recent_solves=recent_solves,
            metrics=metrics,
            message=message,
            recommendations=recommendations
        )
```

### 3. APIルートの追加
`src/openapi_server/apis/zone_detection_api.py`:
```python
from fastapi import APIRouter, Query, Path

from openapi_server.impl.zone_detection_api_impl import ZoneDetectionApiImpl
from openapi_server.models.zone_detection import ZoneDetectionResponse

router = APIRouter(prefix="/api/cube", tags=["cube"])
api_impl = ZoneDetectionApiImpl()

@router.get("/in-the-zone/{player_name}", response_model=ZoneDetectionResponse)
async def detect_zone_state(
    player_name: str = Path(..., description="プレイヤー名"),
    recent_count: int = Query(10, description="直近の確認件数", ge=3, le=20)
):
    """プレイヤーが「ゾーン」に入っているかを検出します"""
    return await api_impl.detect_zone_state(
        player_name=player_name,
        recent_count=recent_count
    )
```

### 4. main.pyへのルート登録
`src/openapi_server/main.py`に追加:
```python
from openapi_server.apis import zone_detection_api

# 既存のルーター登録に追加
app.include_router(zone_detection_api.router)
```

### 5. テストの作成
`tests/test_zone_detection_api.py`:
```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from openapi_server.impl.zone_detection_api_impl import ZoneDetectionApiImpl

@pytest.mark.asyncio
async def test_calculate_performance_rating():
    api = ZoneDetectionApiImpl()
    
    # 平均15秒、標準偏差1秒の場合
    avg = 15.0
    std = 1.0
    
    # 平均より2σ速い（13秒）→ 100点
    assert api.calculate_performance_rating(13.0, avg, std) == 100
    
    # 平均と同じ（15秒）→ 50点
    assert api.calculate_performance_rating(15.0, avg, std) == 50
    
    # 平均より2σ遅い（17秒）→ 0点
    assert api.calculate_performance_rating(17.0, avg, std) == 0

@pytest.mark.asyncio
async def test_calculate_zone_score():
    api = ZoneDetectionApiImpl()
    
    # ゾーン状態：最近のタイムが過去より速く安定
    recent_times = [12.5, 12.3, 12.4, 12.6, 12.2]  # 平均12.4秒
    historical_avg = 15.0
    historical_std = 1.5
    
    zone_score, is_in_zone, zone_level = api.calculate_zone_score(
        recent_times, historical_avg, historical_std
    )
    
    assert zone_score > 70  # 高いスコア
    assert is_in_zone is True
    assert zone_level in ["In the Zone", "Peak Performance"]

@pytest.mark.asyncio
async def test_detect_zone_state():
    api = ZoneDetectionApiImpl()
    
    # モックデータ：最近調子が良い
    now = datetime.now()
    recent_mock = [
        {"timestamp": now - timedelta(minutes=i*5), "solve_time_ms": 12000 + i*100}
        for i in range(10)
    ]
    
    # 履歴データ：平均的に遅い
    historical_mock = [
        {"timestamp": now - timedelta(days=i), "solve_time_ms": 15000 + (i%5)*500}
        for i in range(100)
    ]
    
    with patch.object(api.db_accessor, 'fetch_records', new_callable=AsyncMock) as mock_fetch:
        # 最初の呼び出し：最近のデータ
        # 2回目の呼び出し：履歴データ
        mock_fetch.side_effect = [recent_mock, historical_mock]
        
        response = await api.detect_zone_state("test_player", recent_count=10)
        
        assert response.player_name == "test_player"
        assert len(response.recent_solves) == 10
        assert response.metrics.zone_score > 0
        assert response.zone_level in ["Not in Zone", "Entering Zone", "In the Zone", "Peak Performance"]
        assert len(response.recommendations) > 0
```

### 6. 動作確認
```bash
# サーバー起動
cd output
uvicorn src.openapi_server.main:app --reload

# 別ターミナルでテスト
curl http://localhost:8000/api/cube/in-the-zone/player1?recent_count=10

# Swagger UIで確認
open http://localhost:8000/docs
```

### 7. テーブルへのサンプルデータ投入
```sql
-- ゾーン状態を示すサンプルデータ
DO $$
DECLARE
    i INTEGER;
    base_time TIMESTAMP;
    solve_time INTEGER;
BEGIN
    base_time := NOW() - INTERVAL '2 hours';
    
    -- 通常のソルブ（履歴データ）
    FOR i IN 1..50 LOOP
        solve_time := 15000 + (RANDOM() * 2000 - 1000)::INTEGER;
        
        INSERT INTO cube_times (timestamp, player_name, solve_time_ms, cube_type)
        VALUES (
            base_time - (i * INTERVAL '1 hour'),
            'zone_player',
            solve_time,
            '3x3'
        );
    END LOOP;
    
    -- 最近の良いソルブ（ゾーン状態）
    FOR i IN 0..9 LOOP
        solve_time := 12500 + (RANDOM() * 500 - 250)::INTEGER;
        
        INSERT INTO cube_times (timestamp, player_name, solve_time_ms, cube_type)
        VALUES (
            NOW() - (i * INTERVAL '5 minutes'),
            'zone_player',
            solve_time,
            '3x3'
        );
    END LOOP;
END $$;
```

## コミットとプルリクエスト
```bash
# テスト実行
pytest tests/test_zone_detection_api.py

# コミット
git add .
git commit -m "feat: ゾーン状態検出APIを実装

- リアルタイムパフォーマンス評価
- 統計的手法によるゾーン判定
- パーソナライズされたアドバイス生成
- limit機能を活用した効率的なデータ取得"

# プッシュとPR作成
git push origin feature/api-zone-detection
```

## 学習ポイント
1. **統計処理**
   - 標準偏差とZスコアの活用
   - 移動窓での統計量計算

2. **DatabaseAccessor活用**
   - `limit`パラメータの効果的な使用
   - 複数回のクエリ実行パターン

3. **UX設計**
   - リアルタイムフィードバック
   - 状態に応じたメッセージング

## 注意事項
- 日時フィルタリングは現状Python側で実装
- パフォーマンス向上にはDatabaseAccessorの拡張が望ましい