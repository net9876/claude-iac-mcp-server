# IaC MCP server — container image for a shared/hosted (org) instance.
# Serves the Model Context Protocol over HTTP at /mcp.
FROM python:3.12-slim

WORKDIR /app

# Dependencies first (better layer caching).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The platform: server + the registry/standards/skill it serves.
COPY server/    ./server/
COPY registry/  ./registry/
COPY standards/ ./standards/
COPY skills/    ./skills/

# HTTP transport for a hosted instance (local dev uses stdio instead).
ENV MCP_TRANSPORT=http \
    PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Run as non-root.
RUN useradd -m appuser
USER appuser

CMD ["python", "server/iac_mcp_server.py"]
