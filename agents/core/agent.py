"""
Main Agent class - orchestrator and control loop.

The agent itself is a wrapper/orchestrator, not the model.
It contains prompts, tool logic, a control loop, and memory handling.
All "thinking" happens by sending context to the cloud LLM.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from .llm_client import LLMClient
from .memory import MemoryManager
from ..tools.base import ToolRegistry
from ..storage import DatabaseInterface


logger = logging.getLogger(__name__)


class Agent:
    """
    AI Agent orchestrator.
    
    Data flow:
    1. Agent loads identity and state from USB
    2. Reads working context from Nextcloud
    3. Sends context to cloud LLM
    4. Receives output
    5. Writes intermediate results to Nextcloud
    6. Writes finalized outputs and summaries back to USB
    """
    
    def __init__(
        self,
        llm_client: LLMClient,
        memory_manager: MemoryManager,
        tool_registry: ToolRegistry,
        database: Optional[DatabaseInterface] = None
    ):
        """
        Initialize agent.
        
        Args:
            llm_client: Cloud LLM client for inference
            memory_manager: Memory management system
            tool_registry: Registry of available tools
            database: Optional read-only database connection
        """
        self.llm_client = llm_client
        self.memory = memory_manager
        self.tools = tool_registry
        self.database = database
        
        self.session_id = str(uuid.uuid4())
        self.conversation_history: List[Dict[str, str]] = []
        
        logger.info(f"Agent initialized with session: {self.session_id}")
    
    def initialize(self) -> None:
        """
        Initialize agent systems.
        
        Loads identity from USB and prepares working memory.
        """
        # Load identity and state from USB
        self.memory.initialize()
        
        # Log to working memory
        self.memory.working_memory.append_log(
            f"Agent session started: {self.session_id}",
            "agent"
        )
        
        # Set up system prompt from USB identity
        system_prompt = self.memory.get_system_prompt()
        if system_prompt:
            self.conversation_history.append({
                "role": "system",
                "content": system_prompt
            })
        
        logger.info("Agent initialization complete")
    
    def run(self, task: str, max_iterations: int = 10) -> Dict[str, Any]:
        """
        Run agent on a task using control loop.
        
        Args:
            task: Task description
            max_iterations: Maximum iterations of control loop
            
        Returns:
            Task results
        """
        logger.info(f"Starting task: {task}")
        
        # Add task to conversation
        self.conversation_history.append({
            "role": "user",
            "content": task
        })
        
        results = {
            "task": task,
            "session_id": self.session_id,
            "iterations": [],
            "final_output": None,
            "completed": False
        }
        
        # Control loop
        for iteration in range(max_iterations):
            logger.debug(f"Iteration {iteration + 1}/{max_iterations}")
            
            try:
                # Send context to cloud LLM and receive output
                response = self._think()
                
                # Process response and determine next action
                action = self._decide_action(response)
                
                # Store iteration in working memory
                iteration_data = {
                    "iteration": iteration + 1,
                    "response": response,
                    "action": action
                }
                results["iterations"].append(iteration_data)
                
                # Write intermediate results to Nextcloud
                self.memory.working_memory.write_analysis(
                    f"Iteration {iteration + 1}:\n{response}",
                    f"task_{self.session_id}"
                )
                
                # Execute action
                if action["type"] == "complete":
                    results["final_output"] = action.get("output", response)
                    results["completed"] = True
                    break
                elif action["type"] == "use_tool":
                    tool_result = self._execute_tool(action)
                    # Add tool result to conversation
                    self.conversation_history.append({
                        "role": "user",
                        "content": f"Tool result: {tool_result}"
                    })
                elif action["type"] == "query_database":
                    query_result = self._query_database(action)
                    self.conversation_history.append({
                        "role": "user",
                        "content": f"Query result: {query_result}"
                    })
                else:
                    # Continue thinking
                    pass
                    
            except Exception as e:
                logger.error(f"Error in iteration {iteration + 1}: {str(e)}")
                results["error"] = str(e)
                break
        
        # Finalize results to USB
        self._finalize_results(results)
        
        return results
    
    def _think(self) -> str:
        """
        Send context to cloud LLM and receive response.
        
        All "thinking" happens by sending context to the cloud LLM.
        The agent decides next actions based on the output.
        
        Returns:
            LLM response
        """
        try:
            # Send conversation to cloud LLM
            response = self.llm_client.send_message(
                messages=self.conversation_history,
                temperature=0.7
            )
            
            # Add response to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            logger.debug(f"LLM response: {response[:100]}...")
            return response
            
        except Exception as e:
            logger.error(f"LLM request failed: {str(e)}")
            raise
    
    def _decide_action(self, response: str) -> Dict[str, Any]:
        """
        Decide next action based on LLM response.
        
        Args:
            response: LLM response text
            
        Returns:
            Action dictionary
        """
        # Simple action parsing
        # In production, this would use function calling or structured output
        
        response_lower = response.lower()
        
        if "task complete" in response_lower or "finished" in response_lower:
            return {"type": "complete", "output": response}
        elif "use tool:" in response_lower or "call tool:" in response_lower:
            # Parse tool call (simplified)
            return {"type": "use_tool", "tool_name": "example_tool"}
        elif "query" in response_lower and "database" in response_lower:
            return {"type": "query_database", "query": "SELECT * FROM example"}
        else:
            return {"type": "continue"}
    
    def _execute_tool(self, action: Dict[str, Any]) -> str:
        """
        Execute a tool.
        
        Args:
            action: Action dictionary with tool information
            
        Returns:
            Tool execution result
        """
        tool_name = action.get("tool_name")
        tool_params = action.get("params", {})
        
        try:
            result = self.tools.execute_tool(tool_name, **tool_params)
            logger.info(f"Tool {tool_name} executed successfully")
            return str(result)
        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _query_database(self, action: Dict[str, Any]) -> str:
        """
        Query the read-only database.
        
        Args:
            action: Action dictionary with query
            
        Returns:
            Query results
        """
        if not self.database:
            return "Error: No database connected"
        
        query = action.get("query", "")
        
        try:
            results = self.database.query(query)
            logger.info(f"Database query returned {len(results)} rows")
            return str(results)
        except Exception as e:
            error_msg = f"Database query failed: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _finalize_results(self, results: Dict[str, Any]) -> None:
        """
        Finalize results and write to USB.
        
        This is called infrequently for final outputs only.
        
        Args:
            results: Task results to finalize
        """
        try:
            # Create summary
            summary = f"""
Task: {results['task']}
Completed: {results['completed']}
Iterations: {len(results['iterations'])}
Session: {results['session_id']}
Timestamp: {datetime.now().isoformat()}
"""
            
            if results.get('final_output'):
                summary += f"\nFinal Output:\n{results['final_output']}"
            
            # Write to USB
            finalization_data = {
                "summary": summary,
                "summary_type": "task_completion",
                "session_id": self.session_id,
                "results": results
            }
            
            self.memory.finalize_to_usb(finalization_data)
            
            logger.info("Results finalized to USB")
            
        except Exception as e:
            logger.error(f"Failed to finalize results: {str(e)}")
    
    def chat(self, message: str) -> str:
        """
        Simple chat interface.
        
        Args:
            message: User message
            
        Returns:
            Agent response
        """
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        response = self._think()
        return response
    
    def shutdown(self) -> None:
        """Shutdown agent and cleanup."""
        logger.info(f"Shutting down agent session: {self.session_id}")
        
        # Disconnect database if connected
        if self.database:
            self.database.disconnect()
        
        # Log shutdown
        self.memory.working_memory.append_log(
            f"Agent session ended: {self.session_id}",
            "agent"
        )
