"""
Tests for AI Agent System core components.

These tests validate the basic functionality without requiring
external services (LLM APIs, Nextcloud, etc.)
"""

import unittest
import tempfile
import shutil
import json
from pathlib import Path

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.core.llm_client import create_llm_client, MockLLMClient
from agents.core.memory import (
    LocalStorageBackend,
    USBIdentity,
    WorkingMemory,
    MemoryManager
)
from agents.tools.base import Tool, ToolRegistry
from agents.tools.file_tools import FileReadTool, FileWriteTool
from agents.storage import create_database, SQLiteDatabase


class TestLLMClient(unittest.TestCase):
    """Test LLM client functionality."""
    
    def test_create_mock_client(self):
        """Test creating mock LLM client."""
        client = create_llm_client(provider="mock")
        self.assertIsInstance(client, MockLLMClient)
    
    def test_mock_client_response(self):
        """Test mock client returns responses."""
        client = create_llm_client(provider="mock")
        messages = [{"role": "user", "content": "Hello"}]
        response = client.send_message(messages)
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)


class TestStorageBackend(unittest.TestCase):
    """Test storage backend functionality."""
    
    def setUp(self):
        """Create temporary directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_local_storage_write_read(self):
        """Test writing and reading files."""
        storage = LocalStorageBackend(self.temp_dir)
        
        # Write file
        storage.write("test.txt", "Hello, world!")
        
        # Read file
        content = storage.read("test.txt")
        self.assertEqual(content, "Hello, world!")
    
    def test_local_storage_exists(self):
        """Test file existence check."""
        storage = LocalStorageBackend(self.temp_dir)
        
        # File doesn't exist
        self.assertFalse(storage.exists("nonexistent.txt"))
        
        # Create file
        storage.write("test.txt", "content")
        
        # File exists
        self.assertTrue(storage.exists("test.txt"))
    
    def test_local_storage_append(self):
        """Test appending to files."""
        storage = LocalStorageBackend(self.temp_dir)
        
        # Write initial content
        storage.write("log.txt", "Line 1\n")
        
        # Append more content
        storage.write("log.txt", "Line 2\n", append=True)
        
        # Read and verify
        content = storage.read("log.txt")
        self.assertEqual(content, "Line 1\nLine 2\n")


class TestUSBIdentity(unittest.TestCase):
    """Test USB identity management."""
    
    def setUp(self):
        """Create temporary storage."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = LocalStorageBackend(self.temp_dir)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_create_default_config(self):
        """Test creating default configuration."""
        identity = USBIdentity(self.storage)
        identity.load()
        
        # Should create default config
        self.assertIsNotNone(identity.role)
        self.assertIsNotNone(identity.prompts)
    
    def test_save_and_load_identity(self):
        """Test saving and loading identity."""
        # Create and save identity
        identity1 = USBIdentity(self.storage)
        identity1.config = {
            "role": "Test Agent",
            "prompts": {"system": "Test prompt"},
            "knowledge": {}
        }
        identity1.save()
        
        # Load in new instance
        identity2 = USBIdentity(self.storage)
        identity2.load()
        
        self.assertEqual(identity2.config["role"], "Test Agent")
        self.assertEqual(identity2.config["prompts"]["system"], "Test prompt")
    
    def test_append_memory_log(self):
        """Test appending memory logs."""
        identity = USBIdentity(self.storage)
        identity.append_memory_log({"action": "test", "result": "success"})
        
        # Verify log file was created
        import datetime
        log_file = f"memory_logs/{datetime.datetime.now().strftime('%Y-%m-%d')}.jsonl"
        self.assertTrue(self.storage.exists(log_file))


class TestWorkingMemory(unittest.TestCase):
    """Test working memory functionality."""
    
    def setUp(self):
        """Create temporary storage."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = LocalStorageBackend(self.temp_dir)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_write_analysis(self):
        """Test writing analysis."""
        memory = WorkingMemory(self.storage)
        memory.write_analysis("Test analysis", "test")
        
        # Check that file was created
        files = self.storage.list_files("analysis")
        self.assertGreater(len(files), 0)
    
    def test_write_and_read_state(self):
        """Test writing and reading state."""
        memory = WorkingMemory(self.storage)
        
        state = {"step": 1, "data": "test"}
        memory.write_state(state, "session123")
        
        loaded_state = memory.read_state("session123")
        self.assertEqual(loaded_state["step"], 1)
        self.assertEqual(loaded_state["data"], "test")
    
    def test_append_log(self):
        """Test appending to logs."""
        memory = WorkingMemory(self.storage)
        
        memory.append_log("Log message 1", "test")
        memory.append_log("Log message 2", "test")
        
        # Verify log file exists
        self.assertTrue(self.storage.exists("logs/test.log"))
        
        # Verify both messages are in log
        log_content = self.storage.read("logs/test.log")
        self.assertIn("Log message 1", log_content)
        self.assertIn("Log message 2", log_content)


class TestToolRegistry(unittest.TestCase):
    """Test tool registry functionality."""
    
    def test_register_tool(self):
        """Test registering a tool."""
        registry = ToolRegistry()
        tool = FileReadTool()
        
        registry.register(tool)
        
        self.assertIn("read_file", registry.list_tools())
    
    def test_get_tool(self):
        """Test getting a tool by name."""
        registry = ToolRegistry()
        tool = FileReadTool()
        registry.register(tool)
        
        retrieved = registry.get_tool("read_file")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "read_file")
    
    def test_execute_tool(self):
        """Test executing a tool."""
        registry = ToolRegistry()
        
        # Create a temp file
        temp_dir = tempfile.mkdtemp()
        temp_file = Path(temp_dir) / "test.txt"
        temp_file.write_text("Test content")
        
        try:
            # Register and execute file read tool
            registry.register(FileReadTool())
            result = registry.execute_tool("read_file", file_path=str(temp_file))
            
            self.assertEqual(result, "Test content")
        finally:
            shutil.rmtree(temp_dir)


class TestDatabase(unittest.TestCase):
    """Test read-only database functionality."""
    
    def setUp(self):
        """Create temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        
        # Create a test database
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT,
                value INTEGER
            )
        """)
        cursor.execute("INSERT INTO test_table VALUES (1, 'item1', 100)")
        cursor.execute("INSERT INTO test_table VALUES (2, 'item2', 200)")
        conn.commit()
        conn.close()
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_create_sqlite_database(self):
        """Test creating SQLite database interface."""
        db = create_database("sqlite", str(self.db_path))
        self.assertIsInstance(db, SQLiteDatabase)
    
    def test_connect_and_query(self):
        """Test connecting and querying database."""
        db = create_database("sqlite", str(self.db_path))
        db.connect()
        
        results = db.query("SELECT * FROM test_table")
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "item1")
        self.assertEqual(results[1]["value"], 200)
        
        db.disconnect()
    
    def test_read_only_enforcement(self):
        """Test that write operations are rejected."""
        db = create_database("sqlite", str(self.db_path))
        db.connect()
        
        # Try to insert (should fail)
        with self.assertRaises(ValueError):
            db.query("INSERT INTO test_table VALUES (3, 'item3', 300)")
        
        # Try to update (should fail)
        with self.assertRaises(ValueError):
            db.query("UPDATE test_table SET value = 999")
        
        # Try to delete (should fail)
        with self.assertRaises(ValueError):
            db.query("DELETE FROM test_table")
        
        db.disconnect()


if __name__ == "__main__":
    unittest.main()
