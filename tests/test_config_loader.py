"""
Tests for centralized config loader module.
"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from config_loader import (
    load_config, validate_config, ConfigurationError,
    DatabaseConfig, TodoistConfig, EmailAccount, EmailConfig,
    AppConfig, ConfigProxy
)


class TestDatabaseConfig:
    """Tests for DatabaseConfig dataclass."""

    def test_default_values(self):
        """Should have correct defaults."""
        config = DatabaseConfig()
        assert config.name == "nick"
        assert config.host == "localhost"

    def test_to_psycopg2_params(self):
        """Should convert to psycopg2 format."""
        config = DatabaseConfig(name="testdb", host="dbserver")
        params = config.to_psycopg2_params()

        assert params == {"dbname": "testdb", "host": "dbserver"}


class TestTodoistConfig:
    """Tests for TodoistConfig dataclass."""

    def test_is_configured_with_token(self):
        """Should be configured when token is set."""
        config = TodoistConfig(token="test-token")
        assert config.is_configured

    def test_not_configured_without_token(self):
        """Should not be configured when token is empty."""
        config = TodoistConfig(token="")
        assert not config.is_configured


class TestEmailConfig:
    """Tests for EmailConfig dataclass."""

    def test_configured_accounts_filters(self):
        """Should only return accounts with passwords."""
        accounts = [
            EmailAccount(email="test@example.com", name="Test", app_password="secret"),
            EmailAccount(email="nopass@example.com", name="NoPass", app_password=""),
        ]
        config = EmailConfig(accounts=accounts)

        configured = config.configured_accounts
        assert len(configured) == 1
        assert configured[0].email == "test@example.com"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_missing_config_uses_defaults(self):
        """Should use defaults when config file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.yaml"
            config = load_config(config_path)

            assert isinstance(config, AppConfig)
            assert config.database.name == "nick"
            assert config.server.port == 8889

    def test_load_valid_config(self):
        """Should load valid YAML config."""
        yaml_content = """
database:
  name: testdb
  host: testhost
server:
  port: 9999
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                config = load_config(Path(f.name))
                assert config.database.name == "testdb"
                assert config.database.host == "testhost"
                assert config.server.port == 9999
            finally:
                os.unlink(f.name)

    def test_load_invalid_yaml_raises_error(self):
        """Should raise ConfigurationError for invalid YAML."""
        yaml_content = """
invalid: yaml: content:
  - missing
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with pytest.raises(ConfigurationError):
                    load_config(Path(f.name))
            finally:
                os.unlink(f.name)

    def test_environment_variable_override(self):
        """Should override config with environment variables."""
        yaml_content = """
database:
  name: yamldb
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with patch.dict(os.environ, {"DASHBOARD_DB_NAME": "envdb"}):
                    config = load_config(Path(f.name))
                    assert config.database.name == "envdb"
            finally:
                os.unlink(f.name)

    def test_todoist_token_from_env(self):
        """Should load Todoist token from environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config_path.write_text("todoist:\n  projects: []\n")

            with patch.dict(os.environ, {"DASHBOARD_TODOIST_TOKEN": "env-token"}):
                config = load_config(config_path)
                assert config.todoist.token == "env-token"
                assert config.todoist.is_configured

    def test_env_variable_syntax_in_yaml(self):
        """Should resolve ${VAR} syntax in YAML values."""
        yaml_content = """
notifications:
  telegram:
    enabled: true
    bot_token: "${TEST_BOT_TOKEN}"
    chat_id: "12345"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()

            try:
                with patch.dict(os.environ, {"TEST_BOT_TOKEN": "resolved-token"}):
                    config = load_config(Path(f.name))
                    assert config.notifications.telegram.bot_token == "resolved-token"
            finally:
                os.unlink(f.name)


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_validate_no_required_services(self):
        """Should pass with no required services."""
        config = AppConfig()
        errors = validate_config(config)
        assert errors == []

    def test_validate_missing_todoist(self):
        """Should error when Todoist required but not configured."""
        config = AppConfig()
        errors = validate_config(config, required_services=["todoist"])

        assert len(errors) == 1
        assert "Todoist" in errors[0]

    def test_validate_missing_email(self):
        """Should error when email required but no accounts configured."""
        config = AppConfig()
        errors = validate_config(config, required_services=["email"])

        assert len(errors) == 1
        assert "email" in errors[0].lower()

    def test_validate_invalid_port(self):
        """Should error on invalid port."""
        config = AppConfig()
        config.server.port = 99999

        errors = validate_config(config)
        assert any("port" in e.lower() for e in errors)


class TestConfigProxy:
    """Tests for ConfigProxy backward compatibility."""

    def test_dict_access(self):
        """Should allow dict-like access."""
        config = AppConfig()
        config.database.name = "testdb"

        proxy = ConfigProxy(config)

        assert proxy["database"]["name"] == "testdb"

    def test_get_method(self):
        """Should support .get() method."""
        config = AppConfig()
        proxy = ConfigProxy(config)

        assert proxy.get("database") is not None
        assert proxy.get("nonexistent", "default") == "default"

    def test_contains(self):
        """Should support 'in' operator."""
        config = AppConfig()
        proxy = ConfigProxy(config)

        assert "database" in proxy
        assert "nonexistent" not in proxy


class TestAppConfigToDict:
    """Tests for AppConfig.to_dict method."""

    def test_to_dict_structure(self):
        """Should convert to proper dict structure."""
        config = AppConfig()
        config.database.name = "testdb"
        config.todoist.token = "test-token"

        d = config.to_dict()

        assert d["database"]["name"] == "testdb"
        assert d["todoist"]["token"] == "test-token"
        assert "server" in d
        assert "integrations" in d
