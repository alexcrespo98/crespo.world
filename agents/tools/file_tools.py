"""File operation tools."""

import logging
from pathlib import Path
from typing import Dict, Any
from .base import Tool


logger = logging.getLogger(__name__)


class FileReadTool(Tool):
    """Tool for reading files."""
    
    def __init__(self):
        super().__init__(
            name="read_file",
            description="Read contents of a file"
        )
    
    def execute(self, file_path: str) -> str:
        """
        Read file contents.
        
        Args:
            file_path: Path to file
            
        Returns:
            File contents as string
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return f"Error: File not found: {file_path}"
            
            content = path.read_text(encoding="utf-8")
            logger.info(f"Read file: {file_path} ({len(content)} chars)")
            return content
        except Exception as e:
            error_msg = f"Error reading file {file_path}: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read"
                }
            },
            "required": ["file_path"]
        }


class FileWriteTool(Tool):
    """Tool for writing files."""
    
    def __init__(self):
        super().__init__(
            name="write_file",
            description="Write contents to a file"
        )
    
    def execute(self, file_path: str, content: str, append: bool = False) -> str:
        """
        Write to file.
        
        Args:
            file_path: Path to file
            content: Content to write
            append: Whether to append or overwrite
            
        Returns:
            Success message or error
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            mode = "a" if append else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(content)
            
            action = "Appended to" if append else "Wrote to"
            msg = f"{action} file: {file_path} ({len(content)} chars)"
            logger.info(msg)
            return msg
        except Exception as e:
            error_msg = f"Error writing file {file_path}: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                },
                "append": {
                    "type": "boolean",
                    "description": "Whether to append (true) or overwrite (false)",
                    "default": False
                }
            },
            "required": ["file_path", "content"]
        }


class FileListTool(Tool):
    """Tool for listing files in a directory."""
    
    def __init__(self):
        super().__init__(
            name="list_files",
            description="List files in a directory"
        )
    
    def execute(self, directory: str, pattern: str = "*") -> str:
        """
        List files in directory.
        
        Args:
            directory: Directory path
            pattern: Glob pattern (default: *)
            
        Returns:
            List of files as string
        """
        try:
            path = Path(directory)
            if not path.exists():
                return f"Error: Directory not found: {directory}"
            
            if not path.is_dir():
                return f"Error: Not a directory: {directory}"
            
            files = list(path.glob(pattern))
            file_list = "\n".join([str(f.relative_to(path)) for f in files])
            
            logger.info(f"Listed {len(files)} files in {directory}")
            return file_list if file_list else "No files found"
        except Exception as e:
            error_msg = f"Error listing directory {directory}: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """Get parameters schema."""
        return {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path to list"
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (default: *)",
                    "default": "*"
                }
            },
            "required": ["directory"]
        }
