import pytest
import pytest_asyncio

from database.accessor import (
    DatabaseAccessor,
    DatabaseQueryError
)

# Import test constants and fixtures from conftest.py
from .conftest import (
    TEST_TABLE_POSTGRES,
    requires_postgres
)


@requires_postgres
@pytest.mark.asyncio
async def test_PostgreSQLから全レコードを正しく取得できる(pg_db_accessor: DatabaseAccessor):
    records = await pg_db_accessor.fetch_records(table_name=TEST_TABLE_POSTGRES, columns=['id', 'name'])
    assert len(records) == 3
    assert any(r['name'] == 'PG Apple' for r in records)


@requires_postgres
@pytest.mark.asyncio
async def test_PostgreSQLでフィルタ条件に一致するレコードを正しく取得できる(pg_db_accessor: DatabaseAccessor):
    records = await pg_db_accessor.fetch_records(
        table_name=TEST_TABLE_POSTGRES,
        columns=['name'],
        filters={"category": "Fruit", "is_active": False}
    )
    assert len(records) == 1
    assert records[0]['name'] == 'PG Banana'


@requires_postgres
@pytest.mark.asyncio
async def test_PostgreSQLでINフィルタとソート条件を組み合わせたレコード取得が正しく動作する(pg_db_accessor: DatabaseAccessor):
    records = await pg_db_accessor.fetch_records(
        table_name=TEST_TABLE_POSTGRES,
        columns=['name', 'value'],
        filters={"name": ["PG Apple", "PG Carrot"]},
        order_by=[("value", "ASC")]
    )
    assert len(records) == 2
    assert records[0]['name'] == 'PG Apple'
    assert records[0]['value'] == 100
    assert records[1]['name'] == 'PG Carrot'
    assert records[1]['value'] == 150


@requires_postgres
@pytest.mark.asyncio
async def test_PostgreSQLでLIMITとOFFSETを指定したレコード取得が正しく動作する(pg_db_accessor: DatabaseAccessor):
    records = await pg_db_accessor.fetch_records(
        table_name=TEST_TABLE_POSTGRES,
        columns=['id'],
        order_by=[("id", "ASC")],
        limit=1,
        offset=1
    )
    assert len(records) == 1
    assert records[0]['id'] == 2 # Second item is PG Banana with id 2 if inserted in order


@requires_postgres
@pytest.mark.asyncio
async def test_PostgreSQLで存在しないテーブルからの取得時にエラーが発生する(pg_db_accessor: DatabaseAccessor):
    with pytest.raises(DatabaseQueryError):
        await pg_db_accessor.fetch_records(table_name="this_table_does_not_exist_pg")
