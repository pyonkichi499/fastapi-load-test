"""
Database access module for FastAPI Load Test application.

This module provides database configuration and accessor classes
for interacting with various databases (PostgreSQL, SQLite).
"""

from .config import DatabaseSettings
from .accessor import DatabaseAccessor, DatabaseConnectionError, DatabaseQueryError

__all__ = [
    "DatabaseSettings",
    "DatabaseAccessor",
    "DatabaseConnectionError",
    "DatabaseQueryError"
]
