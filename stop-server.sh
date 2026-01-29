#!/bin/bash
# Stop the Project Dashboard server

pkill -f "python.*server.py.*8889" 2>/dev/null && echo "✅ Server stopped" || echo "⚠️  Server not running"
