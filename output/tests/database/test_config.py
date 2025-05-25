from pathlib import Path
import pytest
from pydantic import ValidationError
from typing import Callable

from database.config import DatabaseSettings


@pytest.fixture
def temp_env_file(tmp_path: Path):
    def _create_env(content):
        env_file = tmp_path / ".env"
        env_file.write_text(content)
        return str(env_file.parent) # pydantic_settings needs dir
    return _create_env


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch: pytest.MonkeyPatch):
    # Clear relevant env vars before each test to ensure isolation
    env_vars_to_clear = [
        "DB_TYPE", "DB_HOST", "DB_PORT", "DB_USER",
        "DB_PASSWORD", "DB_NAME", "SQLITE_PATH"
    ]
    for var in env_vars_to_clear:
        monkeypatch.delenv(var, raising=False)

def test_デフォルト設定のPostgreSQL接続情報が正しく生成される(monkeypatch: pytest.MonkeyPatch):
    # Test with default DB_TYPE and required PostgreSQL vars from environment
    monkeypatch.setenv("DB_HOST", "localhost_pg")
    monkeypatch.setenv("DB_PORT", "5433")
    monkeypatch.setenv("DB_USER", "user_pg")
    monkeypatch.setenv("DB_PASSWORD", "pass_pg")
    monkeypatch.setenv("DB_NAME", "db_pg")

    settings = DatabaseSettings()
    assert settings.DB_TYPE == "postgresql"
    assert settings.DB_HOST == "localhost_pg"
    assert settings.get_dsn() == "postgresql+asyncpg://user_pg:pass_pg@localhost_pg:5433/db_pg"

def test_環境変数からSQLiteファイルパス指定時の接続情報が正しく生成される(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", "test.db")

    settings = DatabaseSettings()
    assert settings.DB_TYPE == "sqlite"
    assert settings.SQLITE_PATH == "test.db"
    assert settings.get_dsn() == "sqlite+aiosqlite:///test.db"

def test_環境変数からSQLiteインメモリ指定時の接続情報が正しく生成される(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", ":memory:")

    settings = DatabaseSettings()
    assert settings.DB_TYPE == "sqlite"
    assert settings.SQLITE_PATH == ":memory:"
    assert settings.get_dsn() == "sqlite+aiosqlite:///:memory:"

def test_envファイルからSQLite設定を読み込み接続情報が正しく生成される(temp_env_file: Callable[..., str], monkeypatch: pytest.MonkeyPatch):
    # Create a .env file with some settings
    env_dir = temp_env_file(
        "DB_TYPE=sqlite\n"
        "SQLITE_PATH=file.db"
    )
    # pydantic-settings uses current working directory if env_file is just ".env"
    # or we can point it to the specific .env file path
    # For simplicity, let's assume it picks it up from cwd or a specified path
    # Here, we'll rely on it picking up from cwd, so we change cwd for the test duration
    monkeypatch.chdir(env_dir)
    settings = DatabaseSettings()
    assert settings.DB_TYPE == "sqlite"
    assert settings.SQLITE_PATH == "file.db"
    assert settings.get_dsn() == "sqlite+aiosqlite:///file.db"

def test_PostgreSQLの必須環境変数が不足している場合にエラーが発生する(monkeypatch: pytest.MonkeyPatch):
    # Only DB_TYPE is set, others are missing for postgresql
    monkeypatch.setenv("DB_TYPE", "postgresql")
    with pytest.raises(ValueError, match="DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME are required"):
        settings = DatabaseSettings()
        settings.get_dsn() # Trigger DSN generation which should fail

def test_SQLiteのファイルパスが未指定の場合にエラーが発生する(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    # SQLITE_PATH is None by default in class if not set via env or file
    # but we want to test the case where it's explicitly set to empty or missing for a file DB
    monkeypatch.delenv("SQLITE_PATH", raising=False) # Ensure it uses the default

    settings = DatabaseSettings() # SQLITE_PATH will be its default "sqlite.db"
    assert settings.SQLITE_PATH == "sqlite.db" # Default value check

    # To specifically test the empty path error, we need to override the default
    monkeypatch.setattr(settings, 'SQLITE_PATH', None)
    with pytest.raises(ValueError, match="SQLITE_PATH is required for SQLite if not in-memory"):
        settings.get_sqlite_dsn()

def test_サポート外のDBタイプが指定された場合にエラーが発生する(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DB_TYPE", "mongodb")
    with pytest.raises(ValueError, match="Unsupported DB_TYPE: mongodb"):
        settings = DatabaseSettings()
        settings.get_dsn()

def test_環境変数がデフォルト値を上書きできる(monkeypatch: pytest.MonkeyPatch):
    # Default DB_TYPE is postgresql
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", "overridden.db")
    settings = DatabaseSettings()
    assert settings.DB_TYPE == "sqlite"
    assert settings.SQLITE_PATH == "overridden.db"

def test_余分な環境変数が無視される(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DB_TYPE", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", "extra.db")
    monkeypatch.setenv("EXTRA_VAR", "this_should_be_ignored")
    try:
        settings = DatabaseSettings()
        assert settings.DB_TYPE == "sqlite"
        assert not hasattr(settings, "EXTRA_VAR")
    except ValidationError:
        pytest.fail("ValidationError raised unexpectedly for extra env var with extra='ignore'")
