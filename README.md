# Project Intelligence Dashboard

A web-based dashboard for monitoring dev project status across multiple sources.

![Status](https://img.shields.io/badge/status-in%20development-yellow)

## Features

- **Git repos**: Commits, branch status, uncommitted changes
- **Todoist**: Tasks filtered by project
- **Linear.app**: Issues by status and assignment
- **Kanban board**: Integration with Jeeves task board

## Quick Start

```bash
# Clone and setup
cd ~/clawd/projects/project-dashboard
cp config.example.yaml config.yaml
# Edit config.yaml with your API keys

# Install dependencies
pip install -r requirements.txt

# Run
./start-server.sh
# Or: python server.py

# Open http://localhost:8889
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and configure:

- **Todoist**: API token from [Todoist Settings](https://todoist.com/app/settings/integrations)
- **Linear**: API key from [Linear Settings](https://linear.app/settings/api)
- **Git**: Paths to scan for repositories
- **Kanban**: URL of Jeeves Kanban API

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run in debug mode
FLASK_DEBUG=1 python server.py
```

## Architecture

- **Backend**: Flask API serving aggregated data
- **Frontend**: Single self-contained HTML file
- **Port**: 8889 (configurable)

See [design document](docs/plans/2026-01-29-project-dashboard-design.md) for full details.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Serves the dashboard UI |
| `GET /api/dashboard` | Returns aggregated data from all sources |
| `GET /api/health` | Health check endpoint |

## License

MIT
