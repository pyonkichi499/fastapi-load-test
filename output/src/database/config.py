from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    DB_TYPE: str = "postgresql"  # "postgresql" or "sqlite"
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[int] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_NAME: Optional[str] = None
    SQLITE_PATH: Optional[str] = "sqlite.db"  # For sqlite if not in-memory

    # For PostgreSQL DSN construction
    def get_postgresql_dsn(self) -> str:
        if not all([
            self.DB_HOST, self.DB_USER, self.DB_PASSWORD,
            self.DB_NAME, self.DB_PORT
        ]):
            raise ValueError(
                "DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME are required "
                "for PostgreSQL"
            )
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    # For SQLite DSN construction
    def get_sqlite_dsn(self) -> str:
        if not self.SQLITE_PATH:
            raise ValueError(
                "SQLITE_PATH is required for SQLite if not in-memory"
            )
        if self.SQLITE_PATH == ":memory:":
            return "sqlite+aiosqlite:///:memory:"
        return f"sqlite+aiosqlite:///{self.SQLITE_PATH}"

    def get_dsn(self) -> str:
        if self.DB_TYPE == "postgresql":
            return self.get_postgresql_dsn()
        elif self.DB_TYPE == "sqlite":
            return self.get_sqlite_dsn()
        else:
            raise ValueError(f"Unsupported DB_TYPE: {self.DB_TYPE}")


def get_db_settings() -> DatabaseSettings:
    return DatabaseSettings()


if __name__ == '__main__':
    # Example usage:
    # Create a .env file in the same directory as this script or project root
    # with content like:
    # DB_TYPE="postgresql"
    # DB_HOST="localhost"
    # DB_PORT=5432
    # DB_USER="youruser"
    # DB_PASSWORD="yourpassword"
    # DB_NAME="yourdbname"
    #
    # or for SQLite:
    # DB_TYPE="sqlite"
    # SQLITE_PATH="mydatabase.db" # or ":memory:" for in-memory

    settings = get_db_settings()
    print(f"Current DB Type: {settings.DB_TYPE}")
    try:
        print(f"Generated DSN: {settings.get_dsn()}")
        if settings.DB_TYPE == "postgresql":
            print(f"PostgreSQL DSN: {settings.get_postgresql_dsn()}")
        elif settings.DB_TYPE == "sqlite":
            print(f"SQLite DSN: {settings.get_sqlite_dsn()}")
    except ValueError as e:
        print(f"Error generating DSN: {e}")

    # To test with specific env vars if .env is not present or for override:
    # import os
    # os.environ['DB_TYPE'] = 'sqlite'
    # os.environ['SQLITE_PATH'] = ':memory:'
    # # Must re-instantiate to pick up new env vars if model_config.env_prefix is not used
    # settings_sqlite_mem = DatabaseSettings() # Re-read settings
    # print(f"SQLite In-Memory DSN from re-instantiated: {settings_sqlite_mem.get_dsn()}")
