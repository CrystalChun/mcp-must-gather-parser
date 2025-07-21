# Must-gather Parser MCP Server

Exposes tools for an LLM to parse a must-gather directory and find clusters that failed installation along with any relevant logs.

## Getting Started

### Prerequisites

1. Python 3.12
2. `uv` tool
3. fast-agent
    ```sh
    uv pip install fast-agent-mcp
    ```
4. Path to a must-gather directory

### Run the server

Clone the repo

```sh
git clone https://github.com/CrystalChun/mcp-must-gather-parser
cd mcp-must-gather-parser
```

Install dependencies
```sh
uv pip install -r requirements.txt
```

Run the server (listens on http://0.0.0.0:8080/sse, already configured for the client in this repo)
```sh
uv run main.py
```

### Run the client

Configure an LLM using the file `fastagent.config.yaml`

```yaml
generic:
  api_key: "<your api key>"
  base_url: "<url of LLM>"
```

Run the client
```sh
uv run client.py --model=generic.<model>
```
