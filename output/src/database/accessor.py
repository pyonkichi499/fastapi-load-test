from typing import Any, Dict, List, Optional, Union, Tuple
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select, table, column, and_, literal_column
from sqlalchemy.sql.expression import ColumnElement
from sqlalchemy.exc import SQLAlchemyError

from .config import DatabaseSettings

# Custom Exceptions
class DatabaseError(Exception):
    """Base exception for database operations in this module."""
    pass

class DatabaseConnectionError(DatabaseError):
    """Raised when a connection to the database cannot be established or is lost."""
    pass

class DatabaseQueryError(DatabaseError):
    """Raised when a query execution fails for reasons other than connection issues."""
    pass

class DatabaseAccessor:
    def __init__(self, settings: DatabaseSettings):
        self.settings = settings
        try:
            self.engine = create_async_engine(
                settings.get_dsn(),
                echo=False  # Set to True for SQL query logging
            )
        except ValueError as e: # Catch DSN generation errors from config
            raise DatabaseConnectionError(f"Invalid DSN or database configuration: {e}")
        except SQLAlchemyError as e: # Catch other SQLAlchemy errors during engine creation
            raise DatabaseConnectionError(f"Failed to create database engine: {e}")

        self.async_session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def get_session(self) -> AsyncSession:
        """Provides an asynchronous database session."""
        # This is a simplified session provider.
        # In a real app, session scope might be tied to request scope.
        async with self.async_session_factory() as session:
            yield session
            # Commit/rollback logic is typically handled by the caller
            # or within specific data manipulation methods.

    async def fetch_records(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        filters: Optional[Dict[str, Union[Any, List[Any]]]] = None,
        order_by: Optional[List[Tuple[str, str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches records from the specified table based on the given criteria.
        Uses SQLAlchemy Core Expression Language for dynamic query building.
        """
        tbl = table(table_name) # Represents the database table

        if columns:
            select_columns = [column(c) for c in columns]
            query = select(*select_columns).select_from(tbl)
        else:
            # Selecting all columns. For simplicity, we assume '*' behavior.
            # A more robust approach for typed results would be to define
            # table metadata explicitly or query column names first.
            query = select(literal_column("*")).select_from(tbl)

        if filters:
            filter_conditions: List[ColumnElement] = []
            for col_name, value in filters.items():
                current_col = column(col_name)
                if isinstance(value, list):
                    filter_conditions.append(current_col.in_(value))
                else:
                    filter_conditions.append(current_col == value)
            if filter_conditions: # Ensure there's something to apply
                query = query.where(and_(*filter_conditions))

        if order_by:
            order_by_expressions = []
            for col_name, direction in order_by:
                current_col = column(col_name)
                if direction.upper() == "DESC":
                    order_by_expressions.append(current_col.desc())
                else: # Default to ASC if not DESC
                    order_by_expressions.append(current_col.asc())
            if order_by_expressions: # Ensure there's something to apply
                query = query.order_by(*order_by_expressions)

        if limit is not None:
            if limit < 0:
                raise ValueError("Limit cannot be negative.")
            query = query.limit(limit)

        if offset is not None:
            if offset < 0:
                raise ValueError("Offset cannot be negative.")
            query = query.offset(offset)

        try:
            async with self.engine.connect() as connection:
                result_proxy = await connection.execute(query)
                return [dict(row) for row in result_proxy.mappings()]
        except SQLAlchemyError as e:
            # Catch specific exceptions like NoSuchTableError, ProgrammingError if needed
            # For now, a general catch for query-related issues.
            # Log the error here with more details (e.g., generated query)
            # logger.error(f"Database query error for table {table_name}: {e}")
            # logger.debug(f"Failed query: {query}")
            raise DatabaseQueryError(
                f"Failed to fetch records from table '{table_name}': {e}"
            )

    async def close(self):
        """Closes the database engine connection pool."""
        if self.engine:
            try:
                await self.engine.dispose()
            except SQLAlchemyError as e:
                # Log this error, but don't necessarily re-raise,
                # as it's part of shutdown.
                # logger.error(f"Error disposing database engine: {e}")
                pass # Or raise a specific shutdown error if critical

# Example (for illustration, actual usage would be in an async context)
async def example_usage():
    # This assumes .env or environment variables are set for DatabaseSettings.
    # Example for SQLite in-memory:
    settings = DatabaseSettings(
        DB_TYPE="sqlite",
        SQLITE_PATH=":memory:"
    )
    accessor = None  # Initialize accessor to None for finally block
    try:
        accessor = DatabaseAccessor(settings)

        async def setup_dummy_data(engine):
            async with engine.connect() as conn:
                await conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS items ("
                    "id INTEGER PRIMARY KEY, name TEXT, value INTEGER"
                    ")"
                ))
                await conn.execute(text("DELETE FROM items"))
                await conn.execute(
                    text("INSERT INTO items (name, value) VALUES (:name, :value)"),
                    [
                        {"name": "apple", "value": 10},
                        {"name": "banana", "value": 20},
                        {"name": "cherry", "value": 10},
                        {"name": "date", "value": 30},
                    ]
                )
                await conn.commit()

        await setup_dummy_data(accessor.engine)

        print("Fetching all items (expect 4):")
        all_items = await accessor.fetch_records(
            table_name="items", columns=["id", "name", "value"]
        )
        print(all_items)

        print("\nFetching items with value=10 (expect 2: apple, cherry):")
        value_10_items = await accessor.fetch_records(
            table_name="items", columns=["name"], filters={"value": 10}
        )
        print(value_10_items)

        print("\nFetching items with name in [\"apple\", \"date\"] (expect 2):")
        name_in_items = await accessor.fetch_records(
            table_name="items",
            columns=["name", "value"],
            filters={"name": ["apple", "date"]}
        )
        print(name_in_items)

        print(
            "\nFetching items ordered by value DESC, then name ASC "
            "(expect date, banana, apple, cherry):"
        )
        ordered_items = await accessor.fetch_records(
            table_name="items",
            columns=["name", "value"],
            order_by=[("value", "DESC"), ("name", "ASC")]
        )
        print(ordered_items)

        print("\nFetching first 2 items ordered by name:")
        limited_items = await accessor.fetch_records(
            table_name="items",
            columns=["name"],
            order_by=[("name", "ASC")],
            limit=2
        )
        print(limited_items)

        print("\nFetching items skipping first one, ordered by id:")
        offset_items = await accessor.fetch_records(
            table_name="items",
            columns=["id", "name"],
            order_by=[("id", "ASC")],
            limit=2,
            offset=1
        )
        print(offset_items)

    except DatabaseError as e:
        print(f"A database error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during example usage: {e}")
    finally:
        if accessor:
            await accessor.close()

if __name__ == '__main__':
    import asyncio
    # Note: This main execution block is for testing/demonstration.
    # In a FastAPI app, the event loop is managed by uvicorn.
    try:
        asyncio.run(example_usage())
    except Exception as e:
        print(f"An error occurred during example_usage execution: {e}")
