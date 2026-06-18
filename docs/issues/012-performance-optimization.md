# Issue #12: パフォーマンス最適化

## 📋 概要
CO2モニタリングAPIのパフォーマンスを最適化し、大量データ処理とレスポンス時間の改善を実現する

## 🎯 目標
- レスポンス時間の短縮（目標: 500ms以下）
- BigQueryクエリの最適化
- メモリ使用量の削減
- 同時リクエスト処理能力の向上

## 📝 詳細要件

### パフォーマンス最適化項目

#### 1. BigQueryクエリ最適化
```python
class OptimizedBigQueryClient:
    """最適化されたBigQueryクライアント"""
    
    def __init__(self, project_id: str):
        self.client = bigquery.Client(project=project_id)
        self.query_cache = {}  # クエリ結果キャッシュ
        self.connection_pool = ConnectionPool(max_connections=10)
    
    async def execute_optimized_query(
        self, 
        query: str, 
        params: dict = None,
        cache_ttl: int = 300  # 5分間キャッシュ
    ) -> List[Dict]:
        """最適化されたクエリ実行"""
        
        # 1. キャッシュチェック
        cache_key = self._generate_cache_key(query, params)
        if cache_key in self.query_cache:
            cached_result, timestamp = self.query_cache[cache_key]
            if time.time() - timestamp < cache_ttl:
                return cached_result
        
        # 2. クエリ最適化
        optimized_query = self._optimize_query(query)
        
        # 3. 非同期実行
        result = await self._execute_async_query(optimized_query, params)
        
        # 4. 結果キャッシュ
        self.query_cache[cache_key] = (result, time.time())
        
        return result
    
    def _optimize_query(self, query: str) -> str:
        """クエリ最適化"""
        
        # パーティション最適化
        if "WHERE datetime" not in query and "room_temperature.bedroom_co2" in query:
            # 自動的に直近24時間に制限
            query = query.replace(
                "FROM `monitoring-bedroom.room_temperature.bedroom_co2`",
                "FROM `monitoring-bedroom.room_temperature.bedroom_co2` "
                "WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)"
            )
        
        # 不要なカラム除去
        if "SELECT *" in query:
            query = query.replace(
                "SELECT *",
                "SELECT datetime, temperature, co2"
            )
        
        return query
```

#### 2. 分析処理の最適化
```python
class OptimizedCO2AnalysisEngine:
    """最適化された分析エンジン"""
    
    def __init__(self):
        self.analysis_cache = LRUCache(maxsize=100)
        self.numpy_available = self._check_numpy()
    
    async def analyze_air_quality_optimized(
        self, 
        hours: int = 3,
        include_timeline: bool = True
    ) -> AirQualityResponse:
        """最適化された空気質分析"""
        
        # 1. 並列データ取得
        tasks = [
            self._get_latest_reading_task(),
            self._get_readings_task(hours),
            self._get_statistics_task(hours)
        ]
        
        latest, readings, stats = await asyncio.gather(*tasks)
        
        # 2. 高速分析処理
        if self.numpy_available and len(readings) > 100:
            trend_analysis = self._numpy_trend_analysis(readings)
        else:
            trend_analysis = self._basic_trend_analysis(readings)
        
        # 3. メモリ効率的なタイムライン生成
        timeline = None
        if include_timeline:
            timeline = self._generate_optimized_timeline(readings)
        
        return self._build_response(latest, readings, stats, trend_analysis, timeline)
    
    def _numpy_trend_analysis(self, readings: List[Dict]) -> Dict:
        """NumPyを使用した高速トレンド分析"""
        import numpy as np
        
        # データ変換
        co2_values = np.array([r['co2'] for r in readings])
        timestamps = np.array([r['datetime'].timestamp() for r in readings])
        
        # 線形回帰（NumPy使用）
        coeffs = np.polyfit(timestamps, co2_values, 1)
        slope = coeffs[0] * 3600  # 時間あたりの変化
        
        # 移動平均（NumPy使用）
        window_size = min(60, len(co2_values) // 4)
        if window_size > 1:
            moving_avg = np.convolve(
                co2_values, 
                np.ones(window_size) / window_size, 
                mode='valid'
            )
        else:
            moving_avg = co2_values
        
        return {
            'slope': slope,
            'trend': self._classify_trend(slope),
            'moving_average': moving_avg.tolist()[-10:],  # 最新10個
            'volatility': float(np.std(co2_values))
        }
    
    def _generate_optimized_timeline(
        self, 
        readings: List[Dict]
    ) -> List[TimelinePoint]:
        """メモリ効率的なタイムライン生成"""
        
        # データ量に応じて間引き
        if len(readings) > 500:
            step = len(readings) // 200  # 最大200ポイント
            readings = readings[::step]
        
        # バッチ処理でTimelinePoint作成
        timeline = []
        for i in range(0, len(readings), 50):  # 50個ずつバッチ処理
            batch = readings[i:i+50]
            timeline.extend([
                TimelinePoint(
                    timestamp=r['datetime'],
                    co2=r['co2'],
                    temperature=r['temperature']
                ) for r in batch
            ])
        
        return timeline
```

#### 3. 接続プールとリソース管理
```python
class ResourceManager:
    """リソース管理クラス"""
    
    def __init__(self):
        self.bigquery_pool = asyncio.Semaphore(5)  # 同時BigQuery接続数制限
        self.analysis_pool = asyncio.Semaphore(10)  # 同時分析処理数制限
        self.memory_monitor = MemoryMonitor()
    
    async def execute_with_resource_control(self, coro):
        """リソース制御付き実行"""
        
        # メモリ使用量チェック
        if self.memory_monitor.get_usage() > 0.8:  # 80%超過
            await self._cleanup_caches()
        
        # セマフォで同時実行数制御
        if 'bigquery' in str(coro):
            async with self.bigquery_pool:
                return await coro
        else:
            async with self.analysis_pool:
                return await coro
    
    async def _cleanup_caches(self):
        """キャッシュクリーンアップ"""
        # 古いキャッシュエントリを削除
        current_time = time.time()
        for cache in [bigquery_cache, analysis_cache]:
            expired_keys = [
                k for k, (_, timestamp) in cache.items()
                if current_time - timestamp > 300  # 5分以上古い
            ]
            for key in expired_keys:
                del cache[key]

class MemoryMonitor:
    """メモリ監視クラス"""
    
    def get_usage(self) -> float:
        """メモリ使用率取得"""
        import psutil
        return psutil.virtual_memory().percent / 100.0
    
    def get_process_memory(self) -> int:
        """プロセスメモリ使用量（MB）"""
        import psutil
        return psutil.Process().memory_info().rss // 1024 // 1024
```

#### 4. レスポンス圧縮とストリーミング
```python
from fastapi.responses import StreamingResponse
import gzip
import json

class OptimizedAPIResponse:
    """最適化されたAPIレスポンス"""
    
    @staticmethod
    def create_compressed_response(data: dict) -> StreamingResponse:
        """圧縮レスポンス生成"""
        
        def generate_compressed_json():
            json_str = json.dumps(data, ensure_ascii=False)
            compressed = gzip.compress(json_str.encode('utf-8'))
            yield compressed
        
        return StreamingResponse(
            generate_compressed_json(),
            media_type="application/json",
            headers={
                "Content-Encoding": "gzip",
                "Cache-Control": "public, max-age=300"  # 5分間キャッシュ
            }
        )
    
    @staticmethod
    def create_streaming_timeline(readings: List[Dict]) -> StreamingResponse:
        """ストリーミング形式のタイムラインレスポンス"""
        
        def generate_timeline_stream():
            yield '{"timeline":['
            
            for i, reading in enumerate(readings):
                if i > 0:
                    yield ','
                
                point = {
                    "timestamp": reading['datetime'].isoformat(),
                    "co2": reading['co2'],
                    "temperature": reading['temperature']
                }
                yield json.dumps(point)
            
            yield ']}'
        
        return StreamingResponse(
            generate_timeline_stream(),
            media_type="application/json"
        )
```

### パフォーマンス監視

#### 1. レスポンス時間監視
```python
import time
from functools import wraps

class PerformanceMonitor:
    """パフォーマンス監視"""
    
    def __init__(self):
        self.metrics = {
            'response_times': [],
            'bigquery_times': [],
            'analysis_times': [],
            'memory_usage': []
        }
    
    def monitor_endpoint(self, endpoint_name: str):
        """エンドポイント監視デコレータ"""
        
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                memory_before = self._get_memory_usage()
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # メトリクス記録
                    end_time = time.time()
                    response_time = end_time - start_time
                    memory_after = self._get_memory_usage()
                    
                    self.metrics['response_times'].append({
                        'endpoint': endpoint_name,
                        'time': response_time,
                        'timestamp': end_time
                    })
                    
                    # アラート判定
                    if response_time > 2.0:  # 2秒超過
                        self._alert_slow_response(endpoint_name, response_time)
                    
                    return result
                    
                except Exception as e:
                    self._record_error(endpoint_name, str(e))
                    raise
                    
            return wrapper
        return decorator
    
    def _alert_slow_response(self, endpoint: str, time: float):
        """遅いレスポンスのアラート"""
        logger.warning(
            f"Slow response detected",
            extra={
                "endpoint": endpoint,
                "response_time": time,
                "threshold": 2.0
            }
        )
    
    def get_performance_summary(self) -> dict:
        """パフォーマンスサマリー取得"""
        
        if not self.metrics['response_times']:
            return {"message": "No metrics available"}
        
        times = [m['time'] for m in self.metrics['response_times']]
        
        return {
            "avg_response_time": sum(times) / len(times),
            "max_response_time": max(times),
            "min_response_time": min(times),
            "total_requests": len(times),
            "slow_requests": len([t for t in times if t > 1.0])
        }
```

#### 2. BigQuery最適化ガイドライン
```python
class BigQueryOptimizationGuide:
    """BigQuery最適化ガイドライン"""
    
    OPTIMIZATION_RULES = [
        {
            "rule": "Use partitioned tables",
            "description": "日付でパーティション分割されたテーブルを使用",
            "example": "WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)"
        },
        {
            "rule": "Limit data scanning",
            "description": "必要な期間のみスキャン",
            "example": "LIMIT 1000"
        },
        {
            "rule": "Select specific columns",
            "description": "SELECT * を避け、必要なカラムのみ選択",
            "example": "SELECT datetime, co2, temperature"
        },
        {
            "rule": "Use approximate functions",
            "description": "可能な場合は近似関数を使用",
            "example": "APPROX_COUNT_DISTINCT() instead of COUNT(DISTINCT)"
        }
    ]
    
    @staticmethod
    def analyze_query_performance(query: str) -> dict:
        """クエリパフォーマンス分析"""
        
        issues = []
        suggestions = []
        
        # SELECT * チェック
        if "SELECT *" in query.upper():
            issues.append("Using SELECT * - consider selecting specific columns")
            suggestions.append("Replace SELECT * with specific column names")
        
        # WHERE句チェック
        if "WHERE" not in query.upper():
            issues.append("No WHERE clause - may scan entire table")
            suggestions.append("Add WHERE clause to limit data scanning")
        
        # LIMIT句チェック
        if "LIMIT" not in query.upper():
            issues.append("No LIMIT clause - may return large result set")
            suggestions.append("Add LIMIT clause to control result size")
        
        return {
            "issues": issues,
            "suggestions": suggestions,
            "estimated_performance": "medium" if len(issues) < 2 else "low"
        }
```

## ✅ 完了条件
- [ ] BigQueryクエリ最適化の実装
- [ ] 分析処理の高速化
- [ ] メモリ使用量の最適化
- [ ] レスポンス圧縮の実装
- [ ] パフォーマンス監視システム
- [ ] 負荷テストの実行
- [ ] 最適化効果の測定

## 🧪 パフォーマンステスト
```python
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

async def load_test_co2_api():
    """CO2 API負荷テスト"""
    
    async def single_request():
        # APIリクエスト実行
        start_time = time.time()
        # await api_client.get_co2_status(hours=3)
        return time.time() - start_time
    
    # 100並行リクエスト
    tasks = [single_request() for _ in range(100)]
    response_times = await asyncio.gather(*tasks)
    
    # 結果分析
    avg_time = sum(response_times) / len(response_times)
    max_time = max(response_times)
    p95_time = sorted(response_times)[int(len(response_times) * 0.95)]
    
    assert avg_time < 1.0, f"Average response time too high: {avg_time}s"
    assert max_time < 5.0, f"Max response time too high: {max_time}s"
    assert p95_time < 2.0, f"95th percentile too high: {p95_time}s"
    
    return {
        "avg_response_time": avg_time,
        "max_response_time": max_time,
        "p95_response_time": p95_time,
        "throughput": len(response_times) / max(response_times)
    }

def benchmark_analysis_engine():
    """分析エンジンベンチマーク"""
    
    # 大量データ生成
    large_dataset = generate_test_data(hours=24)
    
    # ベンチマーク実行
    start_time = time.time()
    
    engine = OptimizedCO2AnalysisEngine()
    result = engine.calculate_basic_trend(large_dataset)
    
    processing_time = time.time() - start_time
    
    assert processing_time < 0.5, f"Analysis too slow: {processing_time}s"
    
    return {
        "data_points": len(large_dataset),
        "processing_time": processing_time,
        "throughput": len(large_dataset) / processing_time
    }
```

## 📁 ファイル構成
```
src/
├── optimization/
│   ├── __init__.py
│   ├── bigquery_optimizer.py     # 新規作成
│   ├── analysis_optimizer.py     # 新規作成
│   ├── resource_manager.py       # 新規作成
│   └── performance_monitor.py    # 新規作成
├── cache/
│   ├── __init__.py
│   └── memory_cache.py           # 新規作成
tests/
├── performance/
│   ├── test_load_testing.py      # 新規作成
│   ├── test_optimization.py      # 新規作成
│   └── benchmark_analysis.py     # 新規作成
```

## 🔗 関連Issue
- 前のIssue: #11 Cloud Run対応とデプロイ設定
- 関連: #5 BigQuery専用クエリ実装
- 関連: #6 CO2分析ロジック実装

## 📊 パフォーマンス目標
- **レスポンス時間**: 平均500ms以下、95%tile 1秒以下
- **スループット**: 100 requests/sec以上
- **メモリ使用量**: 512MB以下
- **BigQueryコスト**: 月額$10以下
- **同時接続**: 50接続以上対応

## 🎯 最適化効果測定
- **Before/After比較**: 最適化前後のメトリクス比較
- **リアルタイム監視**: Prometheus + Grafanaダッシュボード
- **定期レポート**: 週次パフォーマンスレポート
- **コスト追跡**: BigQuery使用量とコストの追跡