FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create storage directory
RUN mkdir -p /tmp/mcp-must-gather

# Set environment variables
ENV PYTHONPATH=/app
ENV MCP_STORAGE_DIR=/tmp/mcp-must-gather
ENV MCP_LOG_LEVEL=INFO

# Expose port (though MCP typically uses stdio)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD echo '{"method": "ping"}' | python -m mcp-must-gather-parser || exit 1

# Default command - start MCP server
CMD ["python", "-m", "mcp-must-gather-parser"]

# Alternative commands:
# CMD ["python", "-m", "mcp-must-gather-parser.cli", "server"] 