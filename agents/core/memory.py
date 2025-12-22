"""
Memory Management System

Handles memory split between:
1. USB drive - Physical identity and finalized outputs
2. Nextcloud SSD - Shared working memory for intermediate results
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def read(self, path: str) -> str:
        """Read data from storage."""
        pass
    
    @abstractmethod
    def write(self, path: str, data: str, append: bool = False) -> None:
        """Write data to storage."""
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if path exists."""
        pass
    
    @abstractmethod
    def list_files(self, path: str) -> List[str]:
        """List files in directory."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def read(self, path: str) -> str:
        """Read file from local storage."""
        full_path = self.base_path / path
        try:
            return full_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {path}")
    
    def write(self, path: str, data: str, append: bool = False) -> None:
        """Write file to local storage."""
        full_path = self.base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = "a" if append else "w"
        with open(full_path, mode, encoding="utf-8") as f:
            f.write(data)
    
    def exists(self, path: str) -> bool:
        """Check if file exists."""
        return (self.base_path / path).exists()
    
    def list_files(self, path: str) -> List[str]:
        """List files in directory."""
        full_path = self.base_path / path
        if not full_path.exists():
            return []
        return [str(p.relative_to(self.base_path)) for p in full_path.iterdir()]


class NextcloudStorageBackend(StorageBackend):
    """
    Nextcloud WebDAV storage backend.
    
    This is used for shared working memory - intermediate analysis,
    summaries, embeddings, logs, and state during execution.
    """
    
    def __init__(self, url: str, username: str, password: str, base_path: str = ""):
        """
        Initialize Nextcloud storage.
        
        Args:
            url: Nextcloud WebDAV URL
            username: Nextcloud username
            password: Nextcloud password
            base_path: Base path within Nextcloud
        """
        self.url = url
        self.username = username
        self.password = password
        self.base_path = base_path
    
    def read(self, path: str) -> str:
        """
        Read file from Nextcloud.
        
        Note: This is a placeholder. In production, you would:
        1. Use webdavclient3 or similar library
        2. Make WebDAV requests
        3. Handle authentication and errors
        """
        raise NotImplementedError(
            "Nextcloud backend requires WebDAV client library. "
            "Install with: pip install webdavclient3"
        )
    
    def write(self, path: str, data: str, append: bool = False) -> None:
        """Write file to Nextcloud."""
        raise NotImplementedError("Nextcloud backend not yet implemented")
    
    def exists(self, path: str) -> bool:
        """Check if file exists in Nextcloud."""
        raise NotImplementedError("Nextcloud backend not yet implemented")
    
    def list_files(self, path: str) -> List[str]:
        """List files in Nextcloud directory."""
        raise NotImplementedError("Nextcloud backend not yet implemented")


class USBIdentity:
    """
    USB-based agent identity.
    
    The USB stores:
    - Agent configuration and role
    - System prompts
    - Lightweight finalized knowledge
    - Summaries
    - Timestamped memory logs
    
    It does NOT store the model or do inference.
    Writes are infrequent and mostly final outputs.
    """
    
    def __init__(self, storage: StorageBackend):
        self.storage = storage
        self.config = {}
        self.role = ""
        self.prompts = {}
        self.knowledge = {}
    
    def load(self, config_file: str = "agent_config.json") -> None:
        """Load agent identity from USB storage."""
        try:
            if self.storage.exists(config_file):
                config_data = self.storage.read(config_file)
                self.config = json.loads(config_data)
                
                self.role = self.config.get("role", "")
                self.prompts = self.config.get("prompts", {})
                self.knowledge = self.config.get("knowledge", {})
                
                logger.info(f"Loaded agent identity: {self.role}")
            else:
                logger.warning(f"Config file not found: {config_file}")
                self._create_default_config(config_file)
        except Exception as e:
            logger.error(f"Failed to load identity: {str(e)}")
            raise
    
    def _create_default_config(self, config_file: str) -> None:
        """Create default configuration."""
        self.config = {
            "role": "General Assistant",
            "prompts": {
                "system": "You are a helpful AI assistant.",
                "user_prefix": "User: ",
                "assistant_prefix": "Assistant: "
            },
            "knowledge": {},
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "version": "1.0"
            }
        }
        self.save(config_file)
    
    def save(self, config_file: str = "agent_config.json") -> None:
        """Save agent identity to USB storage."""
        try:
            config_data = json.dumps(self.config, indent=2)
            self.storage.write(config_file, config_data)
            logger.info("Saved agent identity to USB")
        except Exception as e:
            logger.error(f"Failed to save identity: {str(e)}")
            raise
    
    def append_memory_log(self, entry: Dict[str, Any]) -> None:
        """
        Append to timestamped memory log.
        
        Args:
            entry: Memory log entry
        """
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            **entry
        }
        
        # Append to daily log file
        log_file = f"memory_logs/{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        self.storage.write(
            log_file,
            json.dumps(log_entry) + "\n",
            append=True
        )
    
    def save_summary(self, summary: str, summary_type: str = "general") -> None:
        """
        Save a finalized summary to USB.
        
        Args:
            summary: Summary text
            summary_type: Type of summary
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = f"summaries/{summary_type}_{timestamp}.txt"
        self.storage.write(summary_file, summary)
        logger.info(f"Saved summary: {summary_file}")


class WorkingMemory:
    """
    Nextcloud-based working memory.
    
    This is shared storage for:
    - Intermediate analysis
    - Summaries during processing
    - Embeddings
    - Logs
    - State during execution
    
    Used for "thinking space," not as the source of truth.
    Logs are append-only where possible.
    """
    
    def __init__(self, storage: StorageBackend):
        self.storage = storage
    
    def write_analysis(self, analysis: str, name: str) -> None:
        """Write intermediate analysis."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"analysis/{name}_{timestamp}.txt"
        self.storage.write(file_path, analysis)
        logger.debug(f"Wrote analysis: {file_path}")
    
    def write_state(self, state: Dict[str, Any], session_id: str) -> None:
        """Write execution state."""
        file_path = f"state/{session_id}.json"
        self.storage.write(file_path, json.dumps(state, indent=2))
        logger.debug(f"Wrote state: {file_path}")
    
    def read_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Read execution state."""
        file_path = f"state/{session_id}.json"
        try:
            if self.storage.exists(file_path):
                return json.loads(self.storage.read(file_path))
            return None
        except Exception as e:
            logger.error(f"Failed to read state: {str(e)}")
            return None
    
    def append_log(self, message: str, log_name: str = "agent") -> None:
        """
        Append to log file (append-only).
        
        Args:
            message: Log message
            log_name: Log file name
        """
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {message}\n"
        log_file = f"logs/{log_name}.log"
        self.storage.write(log_file, log_entry, append=True)
    
    def write_embeddings(self, embeddings: Dict[str, Any], name: str) -> None:
        """Write embeddings data."""
        file_path = f"embeddings/{name}.json"
        self.storage.write(file_path, json.dumps(embeddings, indent=2))
        logger.debug(f"Wrote embeddings: {file_path}")


class MemoryManager:
    """
    Unified memory management system.
    
    Coordinates between:
    - USB identity (permanent, finalized)
    - Working memory (temporary, intermediate)
    """
    
    def __init__(
        self,
        usb_storage: StorageBackend,
        working_storage: StorageBackend
    ):
        self.usb_identity = USBIdentity(usb_storage)
        self.working_memory = WorkingMemory(working_storage)
    
    def initialize(self) -> None:
        """Initialize memory systems."""
        # Load identity from USB
        self.usb_identity.load()
        
        # Log initialization to working memory
        self.working_memory.append_log("Memory manager initialized")
    
    def get_system_prompt(self) -> str:
        """Get system prompt from USB identity."""
        return self.usb_identity.prompts.get("system", "")
    
    def get_role(self) -> str:
        """Get agent role from USB identity."""
        return self.usb_identity.role
    
    def finalize_to_usb(self, data: Dict[str, Any]) -> None:
        """
        Finalize outputs and write to USB.
        
        This is called infrequently for final outputs only.
        """
        # Save summary if present
        if "summary" in data:
            self.usb_identity.save_summary(
                data["summary"],
                data.get("summary_type", "general")
            )
        
        # Append to memory log
        self.usb_identity.append_memory_log(data)
        
        logger.info("Finalized outputs to USB")
