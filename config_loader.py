"""
Centralized configuration loader for Project Dashboard.

Features:
- Single source of truth for all configuration
- Environment variable support for secrets (DASHBOARD_* prefix)
- Schema validation with clear error messages
- Fail-fast at startup if config is invalid

Environment Variables:
    DASHBOARD_TODOIST_TOKEN: Todoist API token
    DASHBOARD_LINEAR_API_KEY: Linear API key
    DASHBOARD_TELEGRAM_BOT_TOKEN: Telegram bot token
    DASHBOARD_SLACK_WEBHOOK_URL: Slack webhook URL
    DASHBOARD_DB_HOST: Database host (default: localhost)
    DASHBOARD_DB_NAME: Database name (default: nick)

    For email accounts, use indexed variables:
    DASHBOARD_EMAIL_0_ADDRESS: First email address
    DASHBOARD_EMAIL_0_APP_PASSWORD: First email app password
    DASHBOARD_EMAIL_1_ADDRESS: Second email address
    DASHBOARD_EMAIL_1_APP_PASSWORD: Second email app password
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# Environment variable prefix
ENV_PREFIX = "DASHBOARD_"


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing required values."""
    pass


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    name: str = "nick"
    host: str = "localhost"

    def to_psycopg2_params(self) -> dict:
        """Return parameters for psycopg2.connect()."""
        return {"dbname": self.name, "host": self.host}


@dataclass
class TodoistConfig:
    """Todoist integration configuration."""
    token: str = ""
    projects: list[str] = field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        return bool(self.token)


@dataclass
class LinearConfig:
    """Linear integration configuration."""
    api_key: str = ""
    team_id: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.team_id)


@dataclass
class GitConfig:
    """Git repository scanning configuration."""
    scan_paths: list[str] = field(default_factory=lambda: ["~/clawd/projects"])
    history_days: int = 7


@dataclass
class EmailAccount:
    """Single email account configuration."""
    email: str
    name: str
    priority: str = "medium"
    app_password: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.email and self.app_password)


@dataclass
class EmailConfig:
    """Email integration configuration."""
    accounts: list[EmailAccount] = field(default_factory=list)
    extract_pdfs: bool = True

    @property
    def configured_accounts(self) -> list[EmailAccount]:
        """Return only accounts that have credentials configured."""
        return [a for a in self.accounts if a.is_configured]


@dataclass
class TelegramConfig:
    """Telegram notification configuration."""
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.bot_token and self.chat_id)


@dataclass
class SlackConfig:
    """Slack notification configuration."""
    enabled: bool = False
    webhook_url: str = ""
    channel: str = "#email-digests"

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.webhook_url)


@dataclass
class NotificationsConfig:
    """Notifications configuration."""
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    slack: SlackConfig = field(default_factory=SlackConfig)
    routing: dict[str, list[str]] = field(default_factory=lambda: {
        "urgent": ["telegram"],
        "digest": ["slack"],
        "info": ["slack"]
    })


@dataclass
class IntegrationsConfig:
    """External integrations paths."""
    school_db: str = "~/clawd/data/school-automation.db"
    health_data: str = "~/clawd/projects/health-analytics/dashboard/data"
    sprint_logs: str = "~/obsidian/claude/1-Projects/0-Dev/01-JeeveSprints"
    monzo_api: str = "http://localhost/api/v1"


@dataclass
class ServerConfig:
    """Server configuration."""
    port: int = 8889
    host: str = "0.0.0.0"
    refresh_interval: int = 300


@dataclass
class AppConfig:
    """Complete application configuration."""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    todoist: TodoistConfig = field(default_factory=TodoistConfig)
    linear: LinearConfig = field(default_factory=LinearConfig)
    git: GitConfig = field(default_factory=GitConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    integrations: IntegrationsConfig = field(default_factory=IntegrationsConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    kanban: dict = field(default_factory=dict)  # Flexible kanban config
    scheduling: dict = field(default_factory=dict)  # Flexible scheduling config

    def to_dict(self) -> dict:
        """Convert to dictionary format (for backward compatibility)."""
        return {
            "database": {"name": self.database.name, "host": self.database.host},
            "todoist": {"token": self.todoist.token, "projects": self.todoist.projects},
            "linear": {"api_key": self.linear.api_key, "team_id": self.linear.team_id},
            "git": {"scan_paths": self.git.scan_paths, "history_days": self.git.history_days},
            "email": {
                "accounts": [
                    {"email": a.email, "name": a.name, "priority": a.priority, "app_password": a.app_password}
                    for a in self.email.accounts
                ],
                "extract_pdfs": self.email.extract_pdfs
            },
            "notifications": {
                "telegram": {
                    "enabled": self.notifications.telegram.enabled,
                    "bot_token": self.notifications.telegram.bot_token,
                    "chat_id": self.notifications.telegram.chat_id
                },
                "slack": {
                    "enabled": self.notifications.slack.enabled,
                    "webhook_url": self.notifications.slack.webhook_url,
                    "channel": self.notifications.slack.channel
                },
                "routing": self.notifications.routing
            },
            "integrations": {
                "school_db": self.integrations.school_db,
                "health_data": self.integrations.health_data,
                "sprint_logs": self.integrations.sprint_logs,
                "monzo_api": self.integrations.monzo_api
            },
            "server": {
                "port": self.server.port,
                "host": self.server.host,
                "refresh_interval": self.server.refresh_interval
            },
            "kanban": self.kanban,
            "scheduling": self.scheduling
        }


def _get_env(key: str, default: str = "") -> str:
    """Get environment variable with DASHBOARD_ prefix."""
    return os.environ.get(f"{ENV_PREFIX}{key}", default)


def _resolve_env_value(value: Any) -> Any:
    """
    Resolve environment variable references in config values.

    Supports ${VAR_NAME} syntax for environment variable substitution.
    """
    if not isinstance(value, str):
        return value

    if value.startswith("${") and value.endswith("}"):
        env_var = value[2:-1]
        return os.environ.get(env_var, "")

    return value


def _load_yaml_config(config_path: Path) -> dict:
    """Load and parse YAML config file."""
    if not config_path.exists():
        logger.info(f"Config file not found at {config_path}, using defaults")
        return {}

    try:
        with open(config_path) as f:
            raw_config = yaml.safe_load(f)
            if raw_config is None:
                logger.warning(f"Config file {config_path} is empty")
                return {}
            return raw_config
    except yaml.YAMLError as e:
        raise ConfigurationError(f"YAML syntax error in {config_path}: {e}")
    except PermissionError:
        raise ConfigurationError(f"Permission denied reading {config_path}")


def _build_database_config(raw: dict) -> DatabaseConfig:
    """Build database config from raw dict + environment."""
    db_raw = raw.get("database", {})
    return DatabaseConfig(
        name=_get_env("DB_NAME") or db_raw.get("name", "nick"),
        host=_get_env("DB_HOST") or db_raw.get("host", "localhost")
    )


def _build_todoist_config(raw: dict) -> TodoistConfig:
    """Build Todoist config from raw dict + environment."""
    todoist_raw = raw.get("todoist", {})
    token = _get_env("TODOIST_TOKEN") or _resolve_env_value(todoist_raw.get("token", ""))
    return TodoistConfig(
        token=token,
        projects=todoist_raw.get("projects", [])
    )


def _build_linear_config(raw: dict) -> LinearConfig:
    """Build Linear config from raw dict + environment."""
    linear_raw = raw.get("linear", {})
    api_key = _get_env("LINEAR_API_KEY") or _resolve_env_value(linear_raw.get("api_key", ""))
    return LinearConfig(
        api_key=api_key,
        team_id=linear_raw.get("team_id", "")
    )


def _build_git_config(raw: dict) -> GitConfig:
    """Build Git config from raw dict."""
    git_raw = raw.get("git", {})
    return GitConfig(
        scan_paths=git_raw.get("scan_paths", ["~/clawd/projects"]),
        history_days=git_raw.get("history_days", 7)
    )


def _build_email_config(raw: dict) -> EmailConfig:
    """Build email config from raw dict + environment."""
    email_raw = raw.get("email", {})
    accounts = []

    # First, load from YAML
    for acc in email_raw.get("accounts", []):
        accounts.append(EmailAccount(
            email=acc.get("email", ""),
            name=acc.get("name", ""),
            priority=acc.get("priority", "medium"),
            app_password=_resolve_env_value(acc.get("app_password", ""))
        ))

    # Then, check for environment variable overrides/additions
    # Format: DASHBOARD_EMAIL_0_ADDRESS, DASHBOARD_EMAIL_0_APP_PASSWORD
    idx = 0
    while True:
        email_addr = _get_env(f"EMAIL_{idx}_ADDRESS")
        if not email_addr:
            break

        app_password = _get_env(f"EMAIL_{idx}_APP_PASSWORD")
        name = _get_env(f"EMAIL_{idx}_NAME") or email_addr.split("@")[0]
        priority = _get_env(f"EMAIL_{idx}_PRIORITY") or "medium"

        # Check if this email already exists in accounts (override)
        found = False
        for acc in accounts:
            if acc.email == email_addr:
                if app_password:
                    acc.app_password = app_password
                found = True
                break

        if not found:
            accounts.append(EmailAccount(
                email=email_addr,
                name=name,
                priority=priority,
                app_password=app_password
            ))

        idx += 1

    return EmailConfig(
        accounts=accounts,
        extract_pdfs=email_raw.get("extract_pdfs", True)
    )


def _build_notifications_config(raw: dict) -> NotificationsConfig:
    """Build notifications config from raw dict + environment."""
    notif_raw = raw.get("notifications", {})

    # Telegram
    telegram_raw = notif_raw.get("telegram", {})
    telegram_token = _get_env("TELEGRAM_BOT_TOKEN") or _resolve_env_value(telegram_raw.get("bot_token", ""))
    telegram = TelegramConfig(
        enabled=telegram_raw.get("enabled", False),
        bot_token=telegram_token,
        chat_id=telegram_raw.get("chat_id", "")
    )

    # Slack
    slack_raw = notif_raw.get("slack", {})
    slack_webhook = _get_env("SLACK_WEBHOOK_URL") or _resolve_env_value(slack_raw.get("webhook_url", ""))
    slack = SlackConfig(
        enabled=slack_raw.get("enabled", False),
        webhook_url=slack_webhook,
        channel=slack_raw.get("channel", "#email-digests")
    )

    return NotificationsConfig(
        telegram=telegram,
        slack=slack,
        routing=notif_raw.get("routing", {
            "urgent": ["telegram"],
            "digest": ["slack"],
            "info": ["slack"]
        })
    )


def _build_integrations_config(raw: dict) -> IntegrationsConfig:
    """Build integrations config from raw dict."""
    int_raw = raw.get("integrations", {})
    return IntegrationsConfig(
        school_db=int_raw.get("school_db", "~/clawd/data/school-automation.db"),
        health_data=int_raw.get("health_data", "~/clawd/projects/health-analytics/dashboard/data"),
        sprint_logs=int_raw.get("sprint_logs", "~/obsidian/claude/1-Projects/0-Dev/01-JeeveSprints"),
        monzo_api=int_raw.get("monzo_api", "http://localhost/api/v1")
    )


def _build_server_config(raw: dict) -> ServerConfig:
    """Build server config from raw dict."""
    server_raw = raw.get("server", {})
    return ServerConfig(
        port=server_raw.get("port", 8889),
        host=server_raw.get("host", "0.0.0.0"),
        refresh_interval=server_raw.get("refresh_interval", 300)
    )


def load_config(config_path: Optional[Path] = None) -> AppConfig:
    """
    Load application configuration from YAML file and environment variables.

    Environment variables take precedence over YAML values for secrets.

    Args:
        config_path: Path to config.yaml. Defaults to ./config.yaml

    Returns:
        AppConfig with all settings loaded

    Raises:
        ConfigurationError: If config file has syntax errors or is unreadable
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"

    raw = _load_yaml_config(config_path)

    config = AppConfig(
        database=_build_database_config(raw),
        todoist=_build_todoist_config(raw),
        linear=_build_linear_config(raw),
        git=_build_git_config(raw),
        email=_build_email_config(raw),
        notifications=_build_notifications_config(raw),
        integrations=_build_integrations_config(raw),
        server=_build_server_config(raw),
        kanban=raw.get("kanban", {}),
        scheduling=raw.get("scheduling", {})
    )

    logger.info(
        f"Configuration loaded: "
        f"todoist={'configured' if config.todoist.is_configured else 'not configured'}, "
        f"linear={'configured' if config.linear.is_configured else 'not configured'}, "
        f"email={len(config.email.configured_accounts)} accounts, "
        f"telegram={'configured' if config.notifications.telegram.is_configured else 'not configured'}, "
        f"slack={'configured' if config.notifications.slack.is_configured else 'not configured'}"
    )

    return config


def validate_config(config: AppConfig, required_services: Optional[list[str]] = None) -> list[str]:
    """
    Validate configuration and return list of errors.

    Args:
        config: The configuration to validate
        required_services: List of services that must be configured
            Options: "todoist", "linear", "email", "telegram", "slack", "database"

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    required = required_services or []

    if "todoist" in required and not config.todoist.is_configured:
        errors.append("Todoist token is required but not configured. Set DASHBOARD_TODOIST_TOKEN or add to config.yaml")

    if "linear" in required and not config.linear.is_configured:
        errors.append("Linear API key and team_id are required but not configured")

    if "email" in required and not config.email.configured_accounts:
        errors.append("At least one email account with app_password is required")

    if "telegram" in required and not config.notifications.telegram.is_configured:
        errors.append("Telegram bot_token and chat_id are required. Set DASHBOARD_TELEGRAM_BOT_TOKEN")

    if "slack" in required and not config.notifications.slack.is_configured:
        errors.append("Slack webhook_url is required. Set DASHBOARD_SLACK_WEBHOOK_URL")

    # Validate port range
    if not (1 <= config.server.port <= 65535):
        errors.append(f"Server port {config.server.port} is out of valid range (1-65535)")

    # Validate git scan paths exist (warning only)
    for path in config.git.scan_paths:
        expanded = os.path.expanduser(path)
        if not os.path.isdir(expanded):
            logger.warning(f"Git scan path does not exist: {expanded}")

    return errors


# Module-level singleton for backward compatibility
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get the loaded configuration (singleton)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config(config_path: Optional[Path] = None) -> AppConfig:
    """Force reload of configuration."""
    global _config
    _config = load_config(config_path)
    return _config


# Backward compatibility: dict-like access
class ConfigProxy:
    """
    Proxy object that provides dict-like access to AppConfig.

    This allows existing code using config['todoist']['token'] to continue working.
    """
    def __init__(self, config: AppConfig):
        self._config = config
        self._dict = config.to_dict()

    def __getitem__(self, key: str) -> Any:
        return self._dict[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._dict.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self._dict


def get_config_dict() -> ConfigProxy:
    """Get configuration as dict-like object (backward compatibility)."""
    return ConfigProxy(get_config())
