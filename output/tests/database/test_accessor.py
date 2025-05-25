import pytest
import pytest_asyncio

from database.config import DatabaseSettings
from database.accessor import (
    DatabaseAccessor,
    DatabaseConnectionError,
    DatabaseQueryError
)

# Import test constants from conftest.py
from .conftest import TEST_TABLE_NAME


@pytest.mark.asyncio
async def test_フィルタなしで全カラムのレコードを全て取得できる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(table_name=TEST_TABLE_NAME)
    assert len(records) == 5
    # Assuming default SELECT * returns columns in order of definition or as dicts
    # and that all columns are present
    for record in records:
        assert all(
            key in record for key in [
                'id', 'name', 'category', 'value', 'is_active'
            ]
        )


@pytest.mark.asyncio
async def test_指定したカラムのレコードを全て取得できる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME, columns=["name", "value"]
    )
    assert len(records) == 5
    for record in records:
        assert list(record.keys()) == ["name", "value"]
        assert record['name'] in [
            'Apple', 'Banana', 'Carrot', 'Date', 'Eggplant'
        ]


@pytest.mark.asyncio
async def test_単一条件フィルタでレコードを取得できる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME,
        columns=["name"],
        filters={"category": "Fruit"}
    )
    assert len(records) == 3
    names = {r['name'] for r in records}
    assert names == {'Apple', 'Banana', 'Date'}


@pytest.mark.asyncio
async def test_複数AND条件フィルタでレコードを取得できる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME,
        columns=["name"],
        filters={"category": "Fruit", "value": 20}
    )
    assert len(records) == 2
    names = {r['name'] for r in records}
    assert names == {'Banana', 'Date'}


@pytest.mark.asyncio
async def test_IN条件フィルタでレコードを取得できる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME,
        columns=["name"],
        filters={"name": ["Apple", "Carrot", "Eggplant"]}
    )
    assert len(records) == 3
    names = {r['name'] for r in records}
    assert names == {'Apple', 'Carrot', 'Eggplant'}


@pytest.mark.asyncio
async def test_ブール値フィルタでレコードを取得できる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME,
        columns=["name"],
        filters={"is_active": False}
    )
    assert len(records) == 2
    names = {r['name'] for r in records}
    assert names == {'Carrot', 'Eggplant'}


@pytest.mark.asyncio
async def test_単一カラム昇順ソートでレコードを取得できる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME,
        columns=["name"],
        order_by=[("name", "ASC")]
    )
    assert [r['name'] for r in records] == ['Apple', 'Banana', 'Carrot', 'Date', 'Eggplant']


@pytest.mark.asyncio
async def test_単一カラム降順ソートでレコードを取得できる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME,
        columns=["value"],
        order_by=[("value", "DESC")]
    )
    assert [r['value'] for r in records] == [25, 20, 20, 15, 10]


@pytest.mark.asyncio
async def test_複数カラムソートでレコードを取得できる(db_accessor: DatabaseAccessor):
    # Order by category (ASC), then value (DESC)
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME,
        columns=["name", "category", "value"],
        order_by=[("category", "ASC"), ("value", "DESC")]
    )
    # Expected: Fruits (Banana 20, Date 20, Apple 10),
    # Vegetables (Eggplant 25, Carrot 15)
    # Adjusted based on SQLite behavior for items with same primary
    # and secondary sort key
    expected_names_order = ['Banana', 'Date', 'Apple', 'Eggplant', 'Carrot']
    assert [r['name'] for r in records] == expected_names_order


@pytest.mark.asyncio
async def test_LIMIT指定でレコード数を制限できる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME,
        columns=["id"],
        order_by=[("id", "ASC")],
        limit=2
    )
    assert len(records) == 2
    assert [r['id'] for r in records] == [1, 2]


@pytest.mark.asyncio
async def test_OFFSET指定でレコード開始位置をずらせる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME,
        columns=["id"],
        order_by=[("id", "ASC")],
        offset=3
    )
    assert len(records) == 2  # 5 total, offset 3 means skip 3, get last 2
    assert [r['id'] for r in records] == [4, 5]


@pytest.mark.asyncio
async def test_LIMITとOFFSET指定でレコードを取得できる(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME,
        columns=["id"],
        order_by=[("id", "ASC")],
        limit=2,
        offset=1
    )
    assert len(records) == 2
    assert [r['id'] for r in records] == [2, 3]


@pytest.mark.asyncio
async def test_フィルタ条件に一致するレコードがない場合に空の結果が返る(db_accessor: DatabaseAccessor):
    records = await db_accessor.fetch_records(
        table_name=TEST_TABLE_NAME, filters={"name": "NonExistent"}
    )
    assert len(records) == 0


@pytest.mark.asyncio
async def test_存在しないテーブルからの取得時にエラーが発生する(db_accessor: DatabaseAccessor):
    with pytest.raises(DatabaseQueryError, match="Failed to fetch records from table 'non_existent_table'"):
        await db_accessor.fetch_records(table_name="non_existent_table")


@pytest.mark.asyncio
async def test_SELECT句に不正なカラム名がある場合にエラーが発生する(db_accessor: DatabaseAccessor):
    # This behavior depends on the DB; SQLite might not error immediately on select
    # but rather return None or error upon access if the column truly doesn't exist.
    # SQLAlchemy's dynamic table/column might behave differently than a fully declared model.
    # Let's assume a query error if the column doesn't exist at query execution time.
    with pytest.raises(DatabaseQueryError):  # Generic error, could be more specific depending on DB
        await db_accessor.fetch_records(table_name=TEST_TABLE_NAME, columns=["name", "invalid_column"])


@pytest.mark.asyncio
async def test_フィルタ条件に不正なカラム名がある場合にエラーが発生する(db_accessor: DatabaseAccessor):
    with pytest.raises(DatabaseQueryError):
        await db_accessor.fetch_records(table_name=TEST_TABLE_NAME, filters={"invalid_column": "value"})


@pytest.mark.asyncio
async def test_ORDERBY句に不正なカラム名がある場合にエラーが発生する(db_accessor: DatabaseAccessor):
    with pytest.raises(DatabaseQueryError):
        await db_accessor.fetch_records(table_name=TEST_TABLE_NAME, order_by=[("invalid_column", "ASC")])


@pytest.mark.asyncio
async def test_LIMITまたはOFFSETに負数が指定された場合にエラーが発生する(db_accessor: DatabaseAccessor):
    with pytest.raises(ValueError, match="Limit cannot be negative"):
        await db_accessor.fetch_records(table_name=TEST_TABLE_NAME, limit=-1)
    with pytest.raises(ValueError, match="Offset cannot be negative"):
        await db_accessor.fetch_records(table_name=TEST_TABLE_NAME, offset=-1)


@pytest.mark.asyncio
async def test_不正なDSNまたはDB設定での初期化時に接続エラーが発生する():
    invalid_settings = DatabaseSettings(DB_TYPE="postgresql")  # Missing other PG params
    with pytest.raises(DatabaseConnectionError, match="Invalid DSN or database configuration"):
        DatabaseAccessor(settings=invalid_settings)

    # Test case for engine creation failure (harder to mock reliably without deeper SQLAlchemy mocking)
    # For now, the DSN value error above covers a part of init failures.
