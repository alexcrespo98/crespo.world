"""
Example usage of the AI Agent System.

This demonstrates the data flow:
1. Agent loads identity and state from USB
2. Reads working context from Nextcloud  
3. Sends context to cloud LLM
4. Receives output
5. Writes intermediate results to Nextcloud
6. Writes finalized outputs and summaries back to USB
"""

import os
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.core.agent import Agent
from agents.core.llm_client import create_llm_client
from agents.core.memory import MemoryManager, LocalStorageBackend
from agents.tools.base import ToolRegistry
from agents.tools.file_tools import FileReadTool, FileWriteTool, FileListTool
from agents.tools.data_tools import DataAnalysisTool, QueryTool, SummarizeTool
from agents.storage import create_database


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_agent():
    """
    Set up agent with all components.
    
    In production:
    - USB_STORAGE_PATH would point to a physical USB drive
    - NEXTCLOUD storage would use WebDAV
    - DATABASE would be a real database with read-only permissions
    """
    
    # For demonstration, use local directories
    # In production, these would be actual USB and Nextcloud paths
    usb_path = os.getenv("USB_STORAGE_PATH", "/tmp/agent_usb")
    working_path = os.getenv("WORKING_STORAGE_PATH", "/tmp/agent_working")
    
    # Create storage backends
    usb_storage = LocalStorageBackend(usb_path)
    working_storage = LocalStorageBackend(working_path)
    
    # Create memory manager
    memory_manager = MemoryManager(usb_storage, working_storage)
    
    # Create LLM client
    # Using mock client for demonstration
    # In production, use 'openai' or 'anthropic' with actual API key
    llm_client = create_llm_client(
        provider=os.getenv("LLM_PROVIDER", "mock"),
        api_key=os.getenv("LLM_API_KEY")
    )
    
    # Create tool registry and register tools
    tool_registry = ToolRegistry()
    tool_registry.register(FileReadTool())
    tool_registry.register(FileWriteTool())
    tool_registry.register(FileListTool())
    tool_registry.register(DataAnalysisTool())
    tool_registry.register(SummarizeTool())
    
    # Optional: Set up read-only database
    database = None
    if os.getenv("DATABASE_PATH"):
        try:
            database = create_database(
                db_type=os.getenv("DATABASE_TYPE", "sqlite"),
                connection_string=os.getenv("DATABASE_PATH")
            )
            database.connect()
            
            # Register query tool with database
            query_tool = QueryTool(database)
            tool_registry.register(query_tool)
            
            logger.info("Database connected (read-only mode)")
        except Exception as e:
            logger.warning(f"Could not connect to database: {str(e)}")
    
    # Create agent
    agent = Agent(
        llm_client=llm_client,
        memory_manager=memory_manager,
        tool_registry=tool_registry,
        database=database
    )
    
    return agent


def example_task():
    """Run an example task with the agent."""
    
    logger.info("=== AI Agent System Example ===")
    
    # Set up agent
    agent = setup_agent()
    
    # Initialize agent (loads from USB, prepares working memory)
    agent.initialize()
    
    logger.info(f"Agent role: {agent.memory.get_role()}")
    
    # Example task
    task = """
    Please analyze the current directory structure and provide a summary
    of the key files and their purposes.
    """
    
    logger.info(f"Running task: {task}")
    
    # Run task
    results = agent.run(task, max_iterations=5)
    
    # Print results
    logger.info("=== Task Results ===")
    logger.info(f"Completed: {results['completed']}")
    logger.info(f"Iterations: {len(results['iterations'])}")
    
    if results.get('final_output'):
        logger.info(f"Final output: {results['final_output']}")
    
    # Shutdown
    agent.shutdown()
    
    logger.info("=== Agent session complete ===")
    
    return results


def example_chat():
    """Example of chat interface."""
    
    logger.info("=== AI Agent Chat Example ===")
    
    agent = setup_agent()
    agent.initialize()
    
    # Chat messages
    messages = [
        "Hello! What can you help me with?",
        "Can you list the available tools?",
        "Thank you!"
    ]
    
    for msg in messages:
        logger.info(f"User: {msg}")
        response = agent.chat(msg)
        logger.info(f"Agent: {response}")
    
    agent.shutdown()


def example_with_database():
    """Example using database queries."""
    
    logger.info("=== Database Query Example ===")
    
    # This example requires a database to be configured
    if not os.getenv("DATABASE_PATH"):
        logger.warning("No database configured. Set DATABASE_PATH to run this example.")
        return
    
    agent = setup_agent()
    agent.initialize()
    
    task = """
    Query the database to understand its structure, then analyze 
    the most recent data entries.
    """
    
    results = agent.run(task)
    
    logger.info(f"Results: {results}")
    
    agent.shutdown()


if __name__ == "__main__":
    import sys
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == "chat":
            example_chat()
        elif mode == "database":
            example_with_database()
        else:
            logger.error(f"Unknown mode: {mode}")
            logger.info("Usage: python example_usage.py [task|chat|database]")
    else:
        # Default: run task example
        example_task()
