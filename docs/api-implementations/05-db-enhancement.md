# DatabaseAccessor拡張実装手順

## 概要
GROUP BY、集計関数、ウィンドウ関数などの高度なSQL機能をサポートするためのDatabaseAccessor拡張です。

## ブランチ作成
```bash
git checkout develop
git pull origin develop
git checkout -b feature/db-enhancement
```

## 実装手順

### 1. 拡張DatabaseAccessorクラスの作成
`src/database/enhanced_accessor.py`:
```python
from typing import Any, Dict, List, Optional, Union, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, table, column, and_, literal_column, func
from sqlalchemy.sql import Select
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.exc import SQLAlchemyError

from .accessor import DatabaseAccessor, DatabaseQueryError

class EnhancedDatabaseAccessor(DatabaseAccessor):
    """拡張版DatabaseAccessor - GROUP BY、集計関数、ウィンドウ関数をサポート"""
    
    async def fetch_aggregated_records(
        self,
        table_name: str,
        group_by: List[str],
        aggregations: Dict[str, Dict[str, str]],  # {"alias": {"function": "SUM", "column": "amount"}}
        filters: Optional[Dict[str, Union[Any, List[Any]]]] = None,
        having: Optional[Dict[str, Dict[str, Any]]] = None,  # {"alias": {"operator": ">", "value": 100}}
        order_by: Optional[List[Tuple[str, str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        GROUP BYと集計関数を使用してレコードを取得
        
        Example:
            await fetch_aggregated_records(
                table_name="sales",
                group_by=["product_id", "date"],
                aggregations={
                    "total_amount": {"function": "SUM", "column": "amount"},
                    "avg_price": {"function": "AVG", "column": "price"},
                    "count": {"function": "COUNT", "column": "*"}
                },
                having={"total_amount": {"operator": ">", "value": 1000}}
            )
        """
        tbl = table(table_name)
        
        # SELECT句の構築
        select_columns = []
        
        # GROUP BY列を追加
        for col_name in group_by:
            select_columns.append(column(col_name).label(col_name))
        
        # 集計関数を追加
        for alias, agg_info in aggregations.items():
            func_name = agg_info["function"].upper()
            col_name = agg_info["column"]
            
            if func_name == "COUNT":
                if col_name == "*":
                    agg_column = func.count().label(alias)
                else:
                    agg_column = func.count(column(col_name)).label(alias)
            elif func_name == "SUM":
                agg_column = func.sum(column(col_name)).label(alias)
            elif func_name == "AVG":
                agg_column = func.avg(column(col_name)).label(alias)
            elif func_name == "MAX":
                agg_column = func.max(column(col_name)).label(alias)
            elif func_name == "MIN":
                agg_column = func.min(column(col_name)).label(alias)
            else:
                raise ValueError(f"Unsupported aggregation function: {func_name}")
            
            select_columns.append(agg_column)
        
        query = select(*select_columns).select_from(tbl)
        
        # WHERE句の追加
        if filters:
            filter_conditions: List[ColumnElement] = []
            for col_name, value in filters.items():
                current_col = column(col_name)
                if isinstance(value, list):
                    filter_conditions.append(current_col.in_(value))
                else:
                    filter_conditions.append(current_col == value)
            if filter_conditions:
                query = query.where(and_(*filter_conditions))
        
        # GROUP BY句の追加
        group_by_columns = [column(col_name) for col_name in group_by]
        query = query.group_by(*group_by_columns)
        
        # HAVING句の追加
        if having:
            having_conditions: List[ColumnElement] = []
            for alias, condition in having.items():
                operator = condition["operator"]
                value = condition["value"]
                
                # 集計結果のカラムを参照
                if operator == ">":
                    having_conditions.append(literal_column(alias) > value)
                elif operator == ">=":
                    having_conditions.append(literal_column(alias) >= value)
                elif operator == "<":
                    having_conditions.append(literal_column(alias) < value)
                elif operator == "<=":
                    having_conditions.append(literal_column(alias) <= value)
                elif operator == "=":
                    having_conditions.append(literal_column(alias) == value)
                elif operator == "!=":
                    having_conditions.append(literal_column(alias) != value)
                else:
                    raise ValueError(f"Unsupported operator: {operator}")
            
            if having_conditions:
                query = query.having(and_(*having_conditions))
        
        # ORDER BY句の追加
        if order_by:
            order_by_expressions = []
            for col_name, direction in order_by:
                # 集計結果のエイリアスも使用可能
                if col_name in aggregations:
                    current_col = literal_column(col_name)
                else:
                    current_col = column(col_name)
                
                if direction.upper() == "DESC":
                    order_by_expressions.append(current_col.desc())
                else:
                    order_by_expressions.append(current_col.asc())
            
            if order_by_expressions:
                query = query.order_by(*order_by_expressions)
        
        # LIMIT/OFFSET
        if limit is not None:
            if limit < 0:
                raise ValueError("Limit cannot be negative.")
            query = query.limit(limit)
        
        if offset is not None:
            if offset < 0:
                raise ValueError("Offset cannot be negative.")
            query = query.offset(offset)
        
        # クエリ実行
        try:
            async with self.engine.connect() as connection:
                result_proxy = await connection.execute(query)
                return [dict(row) for row in result_proxy.mappings()]
        except SQLAlchemyError as e:
            raise DatabaseQueryError(
                f"Failed to fetch aggregated records from table '{table_name}': {e}"
            )
    
    async def execute_raw_query(
        self,
        query_string: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        生のSQLクエリを実行（ウィンドウ関数など複雑なクエリ用）
        
        Example:
            await execute_raw_query(
                query_string='''
                    WITH ranked_data AS (
                        SELECT 
                            *,
                            ROW_NUMBER() OVER (PARTITION BY category ORDER BY score DESC) as rank
                        FROM scores
                        WHERE created_at >= :start_date
                    )
                    SELECT * FROM ranked_data WHERE rank <= 3
                ''',
                params={"start_date": datetime.now() - timedelta(days=7)}
            )
        """
        try:
            async with self.engine.connect() as connection:
                result_proxy = await connection.execute(
                    text(query_string),
                    params or {}
                )
                return [dict(row) for row in result_proxy.mappings()]
        except SQLAlchemyError as e:
            raise DatabaseQueryError(f"Failed to execute raw query: {e}")
    
    async def fetch_with_window_function(
        self,
        table_name: str,
        columns: List[str],
        window_functions: Dict[str, Dict[str, Any]],  # {"alias": {"function": "ROW_NUMBER", "partition_by": [...], "order_by": [...]}}
        filters: Optional[Dict[str, Union[Any, List[Any]]]] = None,
        final_filters: Optional[Dict[str, Dict[str, Any]]] = None,  # ウィンドウ関数結果に対するフィルタ
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        ウィンドウ関数を使用してレコードを取得（簡易版）
        
        Example:
            await fetch_with_window_function(
                table_name="cube_times",
                columns=["player_name", "solve_time_ms", "timestamp"],
                window_functions={
                    "rank": {
                        "function": "RANK",
                        "partition_by": ["player_name"],
                        "order_by": [("solve_time_ms", "ASC")]
                    },
                    "avg_time": {
                        "function": "AVG",
                        "partition_by": ["player_name"],
                        "order_by": [("timestamp", "DESC")],
                        "frame": "ROWS BETWEEN 4 PRECEDING AND CURRENT ROW"
                    }
                },
                final_filters={"rank": {"operator": "<=", "value": 10}}
            )
        """
        # ウィンドウ関数を含むCTEクエリを構築
        select_list = ", ".join([f"{col}" for col in columns])
        
        window_specs = []
        for alias, spec in window_functions.items():
            func_name = spec["function"]
            partition_by = spec.get("partition_by", [])
            order_by = spec.get("order_by", [])
            frame = spec.get("frame", "")
            
            window_def = f"{func_name}("
            if func_name in ["AVG", "SUM", "COUNT"]:
                window_def += spec.get("column", "*")
            window_def += ") OVER ("
            
            if partition_by:
                window_def += f"PARTITION BY {', '.join(partition_by)} "
            
            if order_by:
                order_parts = []
                for col, direction in order_by:
                    order_parts.append(f"{col} {direction}")
                window_def += f"ORDER BY {', '.join(order_parts)} "
            
            if frame:
                window_def += frame
            
            window_def += f") AS {alias}"
            window_specs.append(window_def)
        
        # WHERE句の構築
        where_conditions = []
        if filters:
            for col_name, value in filters.items():
                if isinstance(value, list):
                    values_str = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in value])
                    where_conditions.append(f"{col_name} IN ({values_str})")
                else:
                    if isinstance(value, str):
                        where_conditions.append(f"{col_name} = '{value}'")
                    else:
                        where_conditions.append(f"{col_name} = {value}")
        
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        
        # CTEクエリの構築
        cte_query = f"""
        WITH windowed_data AS (
            SELECT 
                {select_list},
                {', '.join(window_specs)}
            FROM {table_name}
            {where_clause}
        )
        SELECT * FROM windowed_data
        """
        
        # 最終フィルタの追加
        if final_filters:
            final_conditions = []
            for col_name, condition in final_filters.items():
                operator = condition["operator"]
                value = condition["value"]
                final_conditions.append(f"{col_name} {operator} {value}")
            
            if final_conditions:
                cte_query += f" WHERE {' AND '.join(final_conditions)}"
        
        # LIMIT/OFFSET
        if limit is not None:
            cte_query += f" LIMIT {limit}"
        if offset is not None:
            cte_query += f" OFFSET {offset}"
        
        return await self.execute_raw_query(cte_query)

# 使用例
async def example_enhanced_usage():
    from database.config import DatabaseSettings
    
    settings = DatabaseSettings()
    accessor = EnhancedDatabaseAccessor(settings)
    
    # GROUP BY例: 部屋ごとの温度統計
    room_stats = await accessor.fetch_aggregated_records(
        table_name="room_temperature",
        group_by=["room_name"],
        aggregations={
            "avg_temp": {"function": "AVG", "column": "temperature"},
            "max_temp": {"function": "MAX", "column": "temperature"},
            "min_temp": {"function": "MIN", "column": "temperature"},
            "reading_count": {"function": "COUNT", "column": "*"}
        },
        having={"avg_temp": {"operator": ">", "value": 25}},
        order_by=[("avg_temp", "DESC")]
    )
    
    # ウィンドウ関数例: プレイヤーごとのランキング
    player_rankings = await accessor.fetch_with_window_function(
        table_name="cube_times",
        columns=["player_name", "solve_time_ms", "timestamp"],
        window_functions={
            "rank": {
                "function": "RANK",
                "partition_by": ["player_name"],
                "order_by": [("solve_time_ms", "ASC")]
            }
        },
        final_filters={"rank": {"operator": "<=", "value": 5}}
    )
    
    # 生クエリ例: 移動平均を含む複雑なクエリ
    complex_result = await accessor.execute_raw_query(
        query_string='''
            WITH temp_with_ma AS (
                SELECT 
                    timestamp,
                    room_name,
                    temperature,
                    AVG(temperature) OVER (
                        PARTITION BY room_name 
                        ORDER BY timestamp 
                        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
                    ) as moving_avg_7
                FROM room_temperature
                WHERE timestamp >= :start_date
            )
            SELECT * FROM temp_with_ma
            WHERE ABS(temperature - moving_avg_7) > 3
            ORDER BY timestamp DESC
        ''',
        params={"start_date": datetime.now() - timedelta(days=7)}
    )
    
    await accessor.close()
```

### 2. テストの作成
`tests/test_enhanced_accessor.py`:
```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from database.enhanced_accessor import EnhancedDatabaseAccessor
from database.config import DatabaseSettings

@pytest.fixture
def mock_settings():
    settings = MagicMock(spec=DatabaseSettings)
    settings.get_dsn.return_value = "sqlite+aiosqlite:///:memory:"
    return settings

@pytest.fixture
def enhanced_accessor(mock_settings):
    return EnhancedDatabaseAccessor(mock_settings)

@pytest.mark.asyncio
async def test_fetch_aggregated_records(enhanced_accessor):
    """GROUP BYと集計関数のテスト"""
    
    # モックデータ
    mock_result = [
        {"room_name": "living_room", "avg_temp": 25.5, "max_temp": 28.0, "min_temp": 23.0, "reading_count": 100},
        {"room_name": "bedroom", "avg_temp": 24.0, "max_temp": 26.0, "min_temp": 22.0, "reading_count": 95}
    ]
    
    with patch.object(enhanced_accessor.engine, 'connect') as mock_connect:
        mock_connection = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_connection
        
        mock_result_proxy = MagicMock()
        mock_result_proxy.mappings.return_value = [dict(row) for row in mock_result]
        mock_connection.execute.return_value = mock_result_proxy
        
        result = await enhanced_accessor.fetch_aggregated_records(
            table_name="room_temperature",
            group_by=["room_name"],
            aggregations={
                "avg_temp": {"function": "AVG", "column": "temperature"},
                "max_temp": {"function": "MAX", "column": "temperature"},
                "min_temp": {"function": "MIN", "column": "temperature"},
                "reading_count": {"function": "COUNT", "column": "*"}
            },
            order_by=[("avg_temp", "DESC")]
        )
        
        assert len(result) == 2
        assert result[0]["room_name"] == "living_room"
        assert result[0]["avg_temp"] == 25.5

@pytest.mark.asyncio
async def test_having_clause(enhanced_accessor):
    """HAVING句のテスト"""
    
    mock_result = [
        {"category": "A", "total_sales": 1500}
    ]
    
    with patch.object(enhanced_accessor.engine, 'connect') as mock_connect:
        mock_connection = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_connection
        
        mock_result_proxy = MagicMock()
        mock_result_proxy.mappings.return_value = [dict(row) for row in mock_result]
        mock_connection.execute.return_value = mock_result_proxy
        
        result = await enhanced_accessor.fetch_aggregated_records(
            table_name="sales",
            group_by=["category"],
            aggregations={
                "total_sales": {"function": "SUM", "column": "amount"}
            },
            having={"total_sales": {"operator": ">", "value": 1000}}
        )
        
        assert len(result) == 1
        assert result[0]["total_sales"] == 1500

@pytest.mark.asyncio
async def test_execute_raw_query(enhanced_accessor):
    """生クエリ実行のテスト"""
    
    mock_result = [
        {"id": 1, "name": "test", "value": 100}
    ]
    
    with patch.object(enhanced_accessor.engine, 'connect') as mock_connect:
        mock_connection = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_connection
        
        mock_result_proxy = MagicMock()
        mock_result_proxy.mappings.return_value = [dict(row) for row in mock_result]
        mock_connection.execute.return_value = mock_result_proxy
        
        result = await enhanced_accessor.execute_raw_query(
            query_string="SELECT * FROM test_table WHERE value > :min_value",
            params={"min_value": 50}
        )
        
        assert len(result) == 1
        assert result[0]["value"] == 100

@pytest.mark.asyncio
async def test_unsupported_aggregation_function(enhanced_accessor):
    """サポートされていない集計関数のテスト"""
    
    with pytest.raises(ValueError, match="Unsupported aggregation function"):
        await enhanced_accessor.fetch_aggregated_records(
            table_name="test_table",
            group_by=["category"],
            aggregations={
                "invalid": {"function": "INVALID_FUNC", "column": "value"}
            }
        )
```

### 3. 既存コードへの統合
`src/database/__init__.py`に追加:
```python
from .accessor import DatabaseAccessor, DatabaseError, DatabaseConnectionError, DatabaseQueryError
from .config import DatabaseSettings, get_db_settings
from .enhanced_accessor import EnhancedDatabaseAccessor

__all__ = [
    "DatabaseAccessor",
    "EnhancedDatabaseAccessor",
    "DatabaseSettings",
    "get_db_settings",
    "DatabaseError",
    "DatabaseConnectionError",
    "DatabaseQueryError"
]
```

### 4. マイグレーションガイドの作成
`docs/db-enhancement-migration.md`:
```markdown
# DatabaseAccessor拡張マイグレーションガイド

## 概要
EnhancedDatabaseAccessorは、既存のDatabaseAccessorを継承し、以下の機能を追加します：

1. GROUP BY と集計関数
2. HAVING句
3. ウィンドウ関数（簡易版）
4. 生SQLクエリ実行

## 使用方法

### 既存コードの変更
```python
# Before
from database.accessor import DatabaseAccessor

# After
from database.enhanced_accessor import EnhancedDatabaseAccessor as DatabaseAccessor
```

### 新機能の使用例

#### GROUP BY
```python
# 部屋ごとの平均温度を取得
stats = await accessor.fetch_aggregated_records(
    table_name="room_temperature",
    group_by=["room_name"],
    aggregations={
        "avg_temp": {"function": "AVG", "column": "temperature"}
    }
)
```

#### HAVING句
```python
# 平均温度が25度を超える部屋のみ
hot_rooms = await accessor.fetch_aggregated_records(
    table_name="room_temperature",
    group_by=["room_name"],
    aggregations={
        "avg_temp": {"function": "AVG", "column": "temperature"}
    },
    having={"avg_temp": {"operator": ">", "value": 25}}
)
```

## 互換性
- 既存のfetch_recordsメソッドは完全に互換性を維持
- 新しいメソッドは追加のみで、既存機能への影響なし
```

### 5. 動作確認
```bash
# テスト実行
cd output
pytest tests/test_enhanced_accessor.py -v

# 統合テスト
pytest tests/database/ -v
```

## コミットとプルリクエスト
```bash
# コミット
git add .
git commit -m "feat: DatabaseAccessorを拡張してGROUP BYとウィンドウ関数をサポート

- fetch_aggregated_recordsメソッドを追加（GROUP BY、集計関数、HAVING）
- execute_raw_queryメソッドを追加（複雑なクエリ用）
- fetch_with_window_functionメソッドを追加（ウィンドウ関数の簡易サポート）
- 既存機能との完全な互換性を維持"

# プッシュとPR作成
git push origin feature/db-enhancement
```

## 学習ポイント
1. **SQLAlchemy Core**
   - 動的なクエリ構築
   - 集計関数の使用方法
   - CTEの構築

2. **設計パターン**
   - 継承による機能拡張
   - 後方互換性の維持

3. **高度なSQL**
   - GROUP BY / HAVING
   - ウィンドウ関数
   - CTE（Common Table Expression）

## 今後の拡張案
- JOINのサポート
- サブクエリのサポート
- トランザクション管理
- バッチ処理の最適化