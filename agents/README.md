# AI Agent System

A portable, auditable AI agent architecture with cloud-based cognition and split memory storage.

## Architecture Overview

This system implements an AI agent with the following key principles:

### Cloud-Based Cognition
- **Neural network (LLM) runs in the cloud** on a GPU and is accessed via API
- The agent is a **wrapper/orchestrator**, not the model itself
- Contains prompts, tool logic, control loop, and memory handling
- All "thinking" happens by sending context to the cloud LLM
- The agent decides next actions based on LLM outputs

### Physical Identity (USB Drive)
- Each agent has a **physical identity** using a USB drive
- USB stores:
  - Agent configuration and role
  - System prompts
  - Lightweight finalized knowledge
  - Summaries
  - Timestamped memory logs
- Does **NOT** store the model or do inference
- Writes are **infrequent** and mostly final outputs

### Shared Working Memory (Nextcloud SSD)
- **Nextcloud-attached SSD** used as shared working memory
- Agent can read and write during execution for:
  - Intermediate analysis
  - Summaries during processing
  - Embeddings
  - Logs (append-only where possible)
  - State during execution
- This storage is for "thinking space," not source of truth

### Read-Only Database Access
- Agent can access a **central database in read-only mode**
- May query and analyze data
- **Must never modify** source data
- Permissions enforced at database level

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Agent loads identity and state from USB                  │
│ 2. Reads working context from Nextcloud                     │
│ 3. Sends context to cloud LLM                               │
│ 4. Receives output                                          │
│ 5. Writes intermediate results to Nextcloud                │
│ 6. Writes finalized outputs and summaries back to USB      │
└─────────────────────────────────────────────────────────────┘
```

### GitHub (Development Only)
- **GitHub Pro** used only for code management and versioning
- Private repos for agent code, prompts, tools, and tests
- GitHub does **NOT** run the agent or host the model
- Execution happens on local machine or small VM

## Installation

### Prerequisites
- Python 3.8+
- Access to cloud LLM API (OpenAI, Anthropic, etc.)
- USB drive for agent identity (or local directory for testing)
- Nextcloud instance (or local directory for testing)
- Optional: Database for read-only queries

### Install Dependencies

```bash
pip install -r agents/requirements.txt
```

### Configuration

1. Copy the example environment file:
```bash
cp agents/config/.env.example agents/config/.env
```

2. Edit `.env` with your settings:
```bash
# LLM Configuration
LLM_PROVIDER=openai
LLM_API_KEY=your_api_key_here
LLM_MODEL=gpt-4

# Storage paths
USB_STORAGE_PATH=/mnt/usb_agent
NEXTCLOUD_URL=https://your-nextcloud.com/remote.php/dav/files/username
NEXTCLOUD_USERNAME=your_username
NEXTCLOUD_PASSWORD=your_password

# Database (optional)
DATABASE_TYPE=sqlite
DATABASE_PATH=/path/to/database.db
```

3. Create agent configuration on USB:
```bash
# Copy example config to USB
cp agents/config/example_agent_config.json /mnt/usb_agent/agent_config.json
```

## Usage

### Basic Example

```python
from agents.core.agent import Agent
from agents.core.llm_client import create_llm_client
from agents.core.memory import MemoryManager, LocalStorageBackend
from agents.tools.base import ToolRegistry
from agents.tools.file_tools import FileReadTool, FileWriteTool

# Set up storage backends
usb_storage = LocalStorageBackend("/mnt/usb_agent")
working_storage = LocalStorageBackend("/mnt/nextcloud/agent_working")

# Create memory manager
memory = MemoryManager(usb_storage, working_storage)

# Create LLM client
llm = create_llm_client(provider="openai", api_key="your_key")

# Create tool registry
tools = ToolRegistry()
tools.register(FileReadTool())
tools.register(FileWriteTool())

# Create agent
agent = Agent(llm, memory, tools)

# Initialize and run
agent.initialize()
results = agent.run("Analyze the current directory")
agent.shutdown()
```

### Run Example Scripts

```bash
# Run basic task example
python agents/examples/example_usage.py

# Run chat interface example
python agents/examples/example_usage.py chat

# Run database query example (requires database)
python agents/examples/example_usage.py database
```

## Components

### Core Components

- **`agents/core/agent.py`**: Main agent orchestrator with control loop
- **`agents/core/llm_client.py`**: Cloud LLM API interface
- **`agents/core/memory.py`**: Memory management (USB + Nextcloud)

### Storage

- **`agents/storage/__init__.py`**: Read-only database interfaces
  - SQLite support (built-in)
  - PostgreSQL support (requires `psycopg2-binary`)
  - MySQL support (requires `mysql-connector-python`)

### Tools

- **`agents/tools/base.py`**: Tool framework and registry
- **`agents/tools/file_tools.py`**: File operation tools
- **`agents/tools/data_tools.py`**: Data analysis and query tools

### Configuration

- **`agents/config/`**: Configuration files and examples
  - `example_agent_config.json`: Agent identity template
  - `.env.example`: Environment variables template

## Project Structure

```
agents/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── agent.py          # Main agent orchestrator
│   ├── llm_client.py     # Cloud LLM interface
│   └── memory.py         # Memory management
├── storage/
│   └── __init__.py       # Read-only database interfaces
├── tools/
│   ├── __init__.py
│   ├── base.py           # Tool framework
│   ├── file_tools.py     # File operations
│   └── data_tools.py     # Data analysis
├── config/
│   ├── example_agent_config.json
│   └── .env.example
├── examples/
│   └── example_usage.py  # Usage examples
└── requirements.txt
```

## Security Considerations

1. **Read-Only Database**: All database interfaces enforce read-only access
2. **API Keys**: Store API keys in environment variables, never in code
3. **USB Security**: USB drive contains agent identity - keep it secure
4. **Audit Trail**: All actions logged to USB memory logs (timestamped, append-only)
5. **Isolation**: Agent cannot modify source data, only read and analyze

## Development with GitHub

This project uses GitHub Pro for version control:

1. **Private Repository**: Keep agent code, prompts, and configurations private
2. **Version Control**: Track changes to agent logic and prompts
3. **Testing**: Use GitHub for test code and CI/CD
4. **Collaboration**: Share code securely with team members

GitHub does NOT:
- Run the agent
- Host the LLM model
- Store runtime data or memory

## Extending the System

### Adding Custom Tools

```python
from agents.tools.base import Tool

class MyCustomTool(Tool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="My custom tool description"
        )
    
    def execute(self, **kwargs):
        # Tool implementation
        return "Result"
    
    def _get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "param": {"type": "string"}
            },
            "required": ["param"]
        }

# Register the tool
tools.register(MyCustomTool())
```

### Adding Custom LLM Providers

```python
from agents.core.llm_client import LLMClient

class MyLLMClient(LLMClient):
    def send_message(self, messages, temperature=0.7, max_tokens=None):
        # Implement API call to your LLM provider
        return "Response from LLM"
    
    def stream_message(self, messages, temperature=0.7, max_tokens=None):
        # Implement streaming
        yield "Chunk"
```

### Adding Custom Storage Backends

```python
from agents.core.memory import StorageBackend

class MyStorageBackend(StorageBackend):
    def read(self, path):
        # Implement read
        pass
    
    def write(self, path, data, append=False):
        # Implement write
        pass
    
    def exists(self, path):
        # Implement exists check
        pass
    
    def list_files(self, path):
        # Implement list
        pass
```

## Testing

The system supports testing without cloud LLM calls:

```python
# Use mock LLM client for testing
llm = create_llm_client(provider="mock")
```

## Troubleshooting

### "Module not found" errors
Install dependencies: `pip install -r agents/requirements.txt`

### "API key not found" errors
Set `LLM_API_KEY` in `.env` or environment variables

### USB mount issues
Ensure USB is mounted and path is correct in configuration

### Nextcloud connection errors
Verify Nextcloud URL, credentials, and WebDAV access

### Database write errors
Verify database is opened in read-only mode and permissions are set correctly

## License

This project is part of the crespo.world repository.

## Architecture Benefits

1. **Portability**: Agent identity on USB can be moved between machines
2. **Auditability**: All decisions and outputs logged with timestamps
3. **Security**: Read-only data access, append-only logs
4. **Scalability**: Cloud-based LLM provides unlimited compute
5. **Separation of Concerns**: Identity (USB), Working Memory (Nextcloud), Code (GitHub), Cognition (Cloud)
6. **Cost-Effective**: No need for local GPU, runs on small VM or laptop
