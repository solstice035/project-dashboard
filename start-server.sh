#!/bin/bash
# Start the Project Dashboard server

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check for config
if [ ! -f "config.yaml" ]; then
    echo "⚠️  No config.yaml found. Copying from example..."
    cp config.example.yaml config.yaml
    echo "   Edit config.yaml with your API keys."
fi

# Check for venv
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Start server
echo "🚀 Starting Project Dashboard on http://localhost:8889"
python server.py
