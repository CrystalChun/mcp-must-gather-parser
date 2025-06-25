# OpenShift Must-Gather MCP Server

A **Model Context Protocol (MCP)** server for analyzing OpenShift must-gather data. This server provides tools and resources that AI models can use to parse, analyze, and extract insights from OpenShift cluster diagnostics.

## What is MCP?

The Model Context Protocol (MCP) is an open standard that enables AI assistants to securely connect to external tools and data sources. This server implements MCP to provide OpenShift expertise to AI models.

## Features

### 🔧 **MCP Tools**
- **parse_must_gather**: Parse and extract data from must-gather archives
- **analyze_cluster_health**: Analyze overall cluster health and operator status
- **analyze_node_issues**: Identify node-specific problems and resource pressure
- **analyze_pod_failures**: Detect failed pods and container issues
- **extract_resource**: Extract specific Kubernetes resources
- **get_cluster_info**: Retrieve cluster version and infrastructure details

### 📊 **MCP Resources**
- **Cluster Info**: Basic cluster information and version details
- **Nodes**: Node status, conditions, and hardware information
- **Pods by Namespace**: Pod information organized by namespace
- **Events**: Cluster and namespace events
- **Cluster Operators**: OpenShift operator status and health
- **Machine Config Pools**: Node configuration and update status
- **Analysis Results**: Intelligent analysis results and recommendations

### 🎯 **Analysis Capabilities**
- **Cluster Health Assessment**: Overall cluster status with degraded component detection
- **Node Issue Detection**: Memory/disk pressure, network issues, readiness problems
- **Pod Failure Analysis**: Container crashes, scheduling failures, resource issues
- **Event Correlation**: Warning events linked to affected resources
- **Operator Status Monitoring**: Degraded or progressing operators

## Installation

```bash
# Clone the repository
cd openshift/mcp-must-gather-parser

# Install dependencies
pip install -r requirements.txt

# Set up configuration (optional)
cp .env.example .env
# Edit .env with your preferred settings
```

## Quick Start

### 1. Start the MCP Server

```bash
# Start the server
python -m mcp-must-gather-parser server

# Or use the CLI
python -m mcp-must-gather-parser.cli server
```

### 2. Use with AI Assistant

Once running, the MCP server can be connected to compatible AI assistants. The server exposes:

- **Server Name**: `openshift-must-gather`
- **Protocol**: Model Context Protocol v1.0
- **Transport**: Standard input/output

### 3. CLI Usage

```bash
# Parse a must-gather archive
python -m mcp-must-gather-parser.cli parse /path/to/must-gather.tar.gz

# Analyze cluster health
python -m mcp-must-gather-parser.cli analyze-cluster <must-gather-id>

# Analyze node issues
python -m mcp-must-gather-parser.cli analyze-nodes <must-gather-id>

# Analyze pod failures
python -m mcp-must-gather-parser.cli analyze-pods <must-gather-id> --namespace kube-system

# List available tools
python -m mcp-must-gather-parser.cli list-tools

# List available resources
python -m mcp-must-gather-parser.cli list-resources
```

## Configuration

The server can be configured via environment variables or a `.env` file:

```bash
# Server Configuration
MCP_SERVER_NAME=openshift-must-gather
MCP_SERVER_VERSION=1.0.0
MCP_STORAGE_DIR=/tmp/mcp-must-gather
MCP_MAX_FILE_SIZE_MB=500

# Analysis Configuration
MCP_ENABLE_CLUSTER_ANALYSIS=true
MCP_ENABLE_NODE_ANALYSIS=true
MCP_ENABLE_POD_ANALYSIS=true
MCP_ENABLE_LOG_ANALYSIS=false

# Performance Configuration
MCP_MAX_CONCURRENT_OPS=5
MCP_OPERATION_TIMEOUT=300

# Logging Configuration
MCP_LOG_LEVEL=INFO
MCP_STRUCTURED_LOGGING=true
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    Tools    │  │  Resources  │  │   Config    │         │
│  │   Handler   │  │   Manager   │  │   Manager   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                 │                 │               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Parsers   │  │  Analyzers  │  │   Storage   │         │
│  │  (Extract)  │  │ (Insights)  │  │  (Persist)  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## MCP Tools Reference

### parse_must_gather
Parse and extract data from an OpenShift must-gather archive.

**Parameters:**
- `file_path` (string, required): Path to the must-gather tar.gz file
- `extract_logs` (boolean, optional): Whether to extract pod logs

**Returns:** Must-gather ID and parsing summary

### analyze_cluster_health
Analyze overall cluster health from must-gather data.

**Parameters:**
- `must_gather_id` (string, required): ID of the parsed must-gather data
- `include_degraded_only` (boolean, optional): Only include degraded components

**Returns:** Comprehensive cluster health analysis

### analyze_node_issues
Analyze node-specific issues and status.

**Parameters:**
- `must_gather_id` (string, required): ID of the parsed must-gather data
- `node_name` (string, optional): Specific node to analyze

**Returns:** Node health analysis and issue detection

### analyze_pod_failures
Analyze failed or problematic pods.

**Parameters:**
- `must_gather_id` (string, required): ID of the parsed must-gather data
- `namespace` (string, optional): Specific namespace to analyze
- `include_logs` (boolean, optional): Include pod logs in analysis

**Returns:** Pod failure analysis and recommendations

## MCP Resources Reference

Resources are accessible via URIs in the format: `must-gather://<id>/<resource-type>[/<namespace>]`

Examples:
- `must-gather://abc123/cluster-info` - Cluster information
- `must-gather://abc123/nodes` - All nodes
- `must-gather://abc123/pods/kube-system` - Pods in kube-system namespace
- `must-gather://abc123/events` - All cluster events
- `must-gather://abc123/cluster-operators` - Cluster operator status

## Integration Examples

### Claude Desktop

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "openshift-must-gather": {
      "command": "python",
      "args": ["-m", "mcp-must-gather-parser"],
      "cwd": "/path/to/mcp-must-gather-parser"
    }
  }
}
```

### API Usage

```python
import asyncio
from mcp import ClientSession, StdioServerParameters

async def analyze_cluster():
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "mcp-must-gather-parser"],
    )
    
    async with ClientSession(server_params) as session:
        # List available tools
        tools = await session.list_tools()
        
        # Parse must-gather
        result = await session.call_tool(
            "parse_must_gather",
            {"file_path": "/path/to/must-gather.tar.gz"}
        )
        
        # Analyze cluster health
        analysis = await session.call_tool(
            "analyze_cluster_health",
            {"must_gather_id": "parsed-id"}
        )

asyncio.run(analyze_cluster())
```

## Supported Must-Gather Types

- Standard OpenShift must-gather
- OCP cluster diagnostics
- Operator-specific must-gather (network, storage, etc.)
- Custom must-gather with standard directory structure

## Analysis Features

### Cluster Health
- Operator availability and degradation status
- Machine config pool health and update progress
- Node readiness and resource pressure
- Critical vs warning issue categorization

### Node Analysis
- Resource pressure detection (memory, disk, PID)
- Network connectivity issues
- Container runtime problems
- Kubelet health status

### Pod Analysis
- Failed pod detection and root cause analysis
- High restart count identification
- Container state analysis
- Scheduling and resource issues
- Event correlation for troubleshooting

## Development

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Start development server with hot reload
python -m mcp-must-gather-parser.cli server --log-level DEBUG

# Format code
black mcp-must-gather-parser/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Support

For issues and questions:
- Open an issue on GitHub
- Check the troubleshooting guide in the docs/
- Review the OpenShift must-gather documentation

