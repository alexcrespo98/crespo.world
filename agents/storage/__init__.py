"""
Read-Only Database Interface

The agent can access a central database in read-only mode.
It may query and analyze data but must never modify the source data.
Permissions enforce this at the database level.
"""

import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


class DatabaseInterface(ABC):
    """
    Abstract base class for database interfaces.
    
    All implementations must enforce read-only access.
    """
    
    def __init__(self, connection_string: str, read_only: bool = True):
        """
        Initialize database interface.
        
        Args:
            connection_string: Database connection string
            read_only: Enforce read-only mode (should always be True)
        """
        if not read_only:
            logger.warning("Database initialized in write mode - this violates architecture!")
        
        self.connection_string = connection_string
        self.read_only = read_only
        self._connection = None
    
    @abstractmethod
    def connect(self) -> None:
        """Establish database connection."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close database connection."""
        pass
    
    @abstractmethod
    def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a read-only query.
        
        Args:
            sql: SQL query string
            params: Query parameters
            
        Returns:
            List of result rows as dictionaries
        """
        pass
    
    def _validate_read_only(self, sql: str) -> None:
        """
        Validate that SQL query is read-only.
        
        Raises ValueError if query appears to modify data.
        """
        sql_upper = sql.strip().upper()
        
        # List of forbidden SQL keywords that modify data
        forbidden_keywords = [
            "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
            "ALTER", "TRUNCATE", "REPLACE", "MERGE"
        ]
        
        for keyword in forbidden_keywords:
            if sql_upper.startswith(keyword):
                raise ValueError(
                    f"Write operation not allowed: {keyword}. "
                    "Database interface is read-only."
                )
    
    def analyze_table(self, table_name: str, limit: int = 100) -> Dict[str, Any]:
        """
        Analyze a table structure and sample data.
        
        Args:
            table_name: Name of the table to analyze
            limit: Maximum number of sample rows
            
        Returns:
            Dictionary with table analysis
        """
        # This is a template method - subclasses can override
        return {
            "table": table_name,
            "note": "Override this method in subclass for specific database"
        }


class SQLiteDatabase(DatabaseInterface):
    """SQLite database interface with read-only enforcement."""
    
    def connect(self) -> None:
        """Connect to SQLite database in read-only mode."""
        try:
            import sqlite3
            
            # Open in read-only mode
            # URI format: file:path?mode=ro
            uri = f"file:{self.connection_string}?mode=ro"
            self._connection = sqlite3.connect(uri, uri=True)
            self._connection.row_factory = sqlite3.Row
            
            logger.info(f"Connected to SQLite database (read-only): {self.connection_string}")
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise
    
    def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Disconnected from database")
    
    def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a read-only query.
        
        Args:
            sql: SQL query string
            params: Query parameters
            
        Returns:
            List of result rows as dictionaries
        """
        # Validate query is read-only
        self._validate_read_only(sql)
        
        if not self._connection:
            raise RuntimeError("Not connected to database")
        
        try:
            cursor = self._connection.cursor()
            
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            # Convert rows to dictionaries
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            logger.debug(f"Query returned {len(results)} rows")
            return results
            
        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            raise
    
    def analyze_table(self, table_name: str, limit: int = 100) -> Dict[str, Any]:
        """
        Analyze SQLite table structure and sample data.
        
        Args:
            table_name: Name of the table
            limit: Maximum rows to sample
            
        Returns:
            Table analysis dictionary
        """
        # Get table schema
        schema_query = f"PRAGMA table_info({table_name})"
        schema = self.query(schema_query)
        
        # Get row count
        count_query = f"SELECT COUNT(*) as count FROM {table_name}"
        count_result = self.query(count_query)
        row_count = count_result[0]["count"] if count_result else 0
        
        # Get sample data
        sample_query = f"SELECT * FROM {table_name} LIMIT {limit}"
        sample_data = self.query(sample_query)
        
        return {
            "table": table_name,
            "row_count": row_count,
            "columns": schema,
            "sample_data": sample_data[:10]  # Only return first 10 for preview
        }


class PostgreSQLDatabase(DatabaseInterface):
    """PostgreSQL database interface with read-only enforcement."""
    
    def connect(self) -> None:
        """Connect to PostgreSQL database."""
        try:
            # Placeholder for psycopg2 implementation
            raise NotImplementedError(
                "PostgreSQL backend requires psycopg2 library. "
                "Install with: pip install psycopg2-binary"
            )
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            raise
    
    def disconnect(self) -> None:
        """Close database connection."""
        pass
    
    def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute read-only query."""
        self._validate_read_only(sql)
        raise NotImplementedError("PostgreSQL backend not yet implemented")


class MySQLDatabase(DatabaseInterface):
    """MySQL database interface with read-only enforcement."""
    
    def connect(self) -> None:
        """Connect to MySQL database."""
        try:
            # Placeholder for mysql-connector implementation
            raise NotImplementedError(
                "MySQL backend requires mysql-connector library. "
                "Install with: pip install mysql-connector-python"
            )
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            raise
    
    def disconnect(self) -> None:
        """Close database connection."""
        pass
    
    def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute read-only query."""
        self._validate_read_only(sql)
        raise NotImplementedError("MySQL backend not yet implemented")


def create_database(db_type: str, connection_string: str) -> DatabaseInterface:
    """
    Factory function to create database interfaces.
    
    Args:
        db_type: Database type ('sqlite', 'postgresql', 'mysql')
        connection_string: Connection string or path
        
    Returns:
        DatabaseInterface instance
    """
    databases = {
        "sqlite": SQLiteDatabase,
        "postgresql": PostgreSQLDatabase,
        "mysql": MySQLDatabase
    }
    
    if db_type not in databases:
        raise ValueError(f"Unknown database type: {db_type}")
    
    return databases[db_type](connection_string, read_only=True)
