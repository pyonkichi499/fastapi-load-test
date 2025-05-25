import pytest
import pytest_asyncio
import os
from sqlalchemy import text

from database.config import DatabaseSettings
from database.accessor import DatabaseAccessor

# Test table name used across database tests (SQLite)
TEST_TABLE_NAME = "test_items"

# Sample test data used for testing database operations (SQLite)
TEST_DATA = [
    {'id': 1, 'name': 'Apple', 'category': 'Fruit', 'value': 10, 'is_active': True},
    {'id': 2, 'name': 'Banana', 'category': 'Fruit', 'value': 20, 'is_active': True},
    {'id': 3, 'name': 'Carrot', 'category': 'Vegetable', 'value': 15, 'is_active': False},
    {'id': 4, 'name': 'Date', 'category': 'Fruit', 'value': 20, 'is_active': True},
    {'id': 5, 'name': 'Eggplant', 'category': 'Vegetable', 'value': 25, 'is_active': False},
]

# PostgreSQL test constants
TEST_TABLE_POSTGRES = "test_items_pg"

# Sample test data for PostgreSQL tests
TEST_DATA_POSTGRES = [
    {'id': 1, 'name': 'PG Apple', 'category': 'Fruit', 'value': 100, 'is_active': True},
    {'id': 2, 'name': 'PG Banana', 'category': 'Fruit', 'value': 200, 'is_active': False},
    {'id': 3, 'name': 'PG Carrot', 'category': 'Vegetable', 'value': 150, 'is_active': True},
]

# Marker to skip tests if POSTGRES_TEST_ENABLED is not set to true
requires_postgres = pytest.mark.skipif(
    os.environ.get("POSTGRES_TEST_ENABLED", "false").lower() != "true",
    reason="PostgreSQL integration tests are disabled. Set POSTGRES_TEST_ENABLED=true to run."
)


@pytest_asyncio.fixture(scope="function")
async def db_settings() -> DatabaseSettings:
    """Provides database settings for SQLite in-memory testing."""
    return DatabaseSettings(DB_TYPE="sqlite", SQLITE_PATH=":memory:")


@pytest_asyncio.fixture(scope="function")
async def db_accessor(db_settings: DatabaseSettings) -> DatabaseAccessor:
    """
    Provides a DatabaseAccessor instance with a pre-configured test table and data.

    This fixture:
    - Creates a SQLite in-memory database
    - Sets up a test table with sample data
    - Yields the accessor for testing
    - Cleans up the connection after tests
    """
    accessor = DatabaseAccessor(settings=db_settings)

    # Setup: Create table and insert initial data
    async with accessor.engine.connect() as conn:
        # Create test table
        await conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {TEST_TABLE_NAME} (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                value INTEGER,
                is_active BOOLEAN DEFAULT TRUE
            )
        """))

        # Clear any existing data (defensive programming)
        await conn.execute(text(f"DELETE FROM {TEST_TABLE_NAME}"))

        # Insert test data
        for row in TEST_DATA:
            await conn.execute(
                text(f"INSERT INTO {TEST_TABLE_NAME} (id, name, category, value, is_active) "
                     f"VALUES (:id, :name, :category, :value, :is_active)"),
                [row]  # SQLAlchemy expects list of dicts for parameterized queries
            )

        await conn.commit()

    yield accessor

    # Teardown: close the engine
    await accessor.close()


@pytest_asyncio.fixture(scope="function")
async def pg_db_settings() -> DatabaseSettings:
    """Provides database settings for PostgreSQL testing."""
    # These should match your docker-compose.test.yml and .env for testing PostgreSQL
    return DatabaseSettings(
        DB_TYPE="postgresql",
        DB_HOST=os.environ.get("CI_POSTGRES_HOST", "localhost"),
        DB_PORT=int(os.environ.get("CI_POSTGRES_PORT", 5433)),
        DB_USER=os.environ.get("CI_POSTGRES_USER", "testuser"),
        DB_PASSWORD=os.environ.get("CI_POSTGRES_PASSWORD", "testpassword"),
        DB_NAME=os.environ.get("CI_POSTGRES_DB", "testdb")
    )


@pytest_asyncio.fixture(scope="function")
@requires_postgres  # Apply marker to the fixture itself
async def pg_db_accessor(pg_db_settings: DatabaseSettings) -> DatabaseAccessor:
    """
    Provides a DatabaseAccessor instance for PostgreSQL with a pre-configured test table and data.

    This fixture:
    - Creates a PostgreSQL database connection
    - Sets up a test table with sample data
    - Yields the accessor for testing
    - Cleans up the table and connection after tests

    Note: This fixture requires PostgreSQL to be available and POSTGRES_TEST_ENABLED=true
    """
    try:
        accessor = DatabaseAccessor(settings=pg_db_settings)
    except Exception as e:
        pytest.fail(f"Failed to connect to PostgreSQL for testing: {e}")

    async with accessor.engine.connect() as conn:
        # Clean up and create test table
        await conn.execute(text(f"DROP TABLE IF EXISTS {TEST_TABLE_POSTGRES} CASCADE"))
        await conn.execute(text(f"""
            CREATE TABLE {TEST_TABLE_POSTGRES} (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                value INTEGER,
                is_active BOOLEAN DEFAULT TRUE
            )
        """))

        # Insert test data
        for row in TEST_DATA_POSTGRES:
            await conn.execute(
                text(f"INSERT INTO {TEST_TABLE_POSTGRES} (id, name, category, value, is_active) "
                     f"VALUES (:id, :name, :category, :value, :is_active)"),
                [row]
            )
        await conn.commit()

    yield accessor

    # Teardown: clean up table and close connection
    async with accessor.engine.connect() as conn:
        await conn.execute(text(f"DROP TABLE IF EXISTS {TEST_TABLE_POSTGRES} CASCADE"))
        await conn.commit()
    await accessor.close()


# Make test constants available for import in test files
__all__ = [
    "TEST_TABLE_NAME", "TEST_DATA",
    "TEST_TABLE_POSTGRES", "TEST_DATA_POSTGRES",
    "requires_postgres",
    "db_settings", "db_accessor",
    "pg_db_settings", "pg_db_accessor"
]
