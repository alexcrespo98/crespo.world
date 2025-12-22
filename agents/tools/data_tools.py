"""Data analysis and query tools."""

import logging
import json
from typing import Dict, Any, Optional
from .base import Tool


logger = logging.getLogger(__name__)


class DataAnalysisTool(Tool):
    """Tool for analyzing data."""
    
    def __init__(self):
        super().__init__(
            name="analyze_data",
            description="Analyze structured data and provide insights"
        )
    
    def execute(self, data: str, analysis_type: str = "summary") -> str:
        """
        Analyze data.
        
        Args:
            data: JSON string or CSV data
            analysis_type: Type of analysis to perform
            
        Returns:
            Analysis results
        """
        try:
            # Try to parse as JSON
            try:
                parsed_data = json.loads(data)
                return self._analyze_json(parsed_data, analysis_type)
            except json.JSONDecodeError:
                return self._analyze_text(data, analysis_type)
        except Exception as e:
            error_msg = f"Error analyzing data: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _analyze_json(self, data: Any, analysis_type: str) -> str:
        """Analyze JSON data."""
        if isinstance(data, list):
            return f"List with {len(data)} items"
        elif isinstance(data, dict):
            return f"Dictionary with keys: {', '.join(data.keys())}"
        else:
            return f"Value: {data}"
    
    def _analyze_text(self, data: str, analysis_type: str) -> str:
        """Analyze text data."""
        lines = data.split("\n")
        words = data.split()
        return f"Text analysis: {len(lines)} lines, {len(words)} words, {len(data)} characters"
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Data to analyze (JSON or text)"
                },
                "analysis_type": {
                    "type": "string",
                    "description": "Type of analysis to perform",
                    "enum": ["summary", "detailed", "statistical"],
                    "default": "summary"
                }
            },
            "required": ["data"]
        }


class QueryTool(Tool):
    """Tool for querying databases."""
    
    def __init__(self, database=None):
        super().__init__(
            name="query_database",
            description="Query the read-only database"
        )
        self.database = database
    
    def execute(self, query: str) -> str:
        """
        Execute database query.
        
        Args:
            query: SQL query to execute
            
        Returns:
            Query results as JSON string
        """
        if not self.database:
            return "Error: No database connected"
        
        try:
            results = self.database.query(query)
            logger.info(f"Query returned {len(results)} rows")
            return json.dumps(results, indent=2)
        except Exception as e:
            error_msg = f"Query error: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SQL SELECT query to execute (read-only)"
                }
            },
            "required": ["query"]
        }


class SummarizeTool(Tool):
    """Tool for summarizing text or data."""
    
    def __init__(self):
        super().__init__(
            name="summarize",
            description="Summarize text or data"
        )
    
    def execute(self, content: str, max_length: int = 200) -> str:
        """
        Summarize content.
        
        Args:
            content: Content to summarize
            max_length: Maximum summary length
            
        Returns:
            Summary
        """
        try:
            # Simple summarization: take first max_length characters
            # In production, this would use the LLM
            if len(content) <= max_length:
                return content
            
            summary = content[:max_length] + "..."
            logger.info(f"Summarized {len(content)} chars to {len(summary)} chars")
            return summary
        except Exception as e:
            error_msg = f"Error summarizing: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "Content to summarize"
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum summary length",
                    "default": 200
                }
            },
            "required": ["content"]
        }
