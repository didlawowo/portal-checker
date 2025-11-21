import sys
import os
# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch


class TestConfig:
    """Test configuration module"""

    def test_default_flask_env(self):
        """Test default Flask environment is production"""
        with patch.dict(os.environ, {}, clear=True):
            # Reimport to get fresh config
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.FLASK_ENV == "production"

    def test_default_port(self):
        """Test default port is 5000"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.PORT == 5000

    def test_custom_port_from_env(self):
        """Test port can be set from environment"""
        with patch.dict(os.environ, {"PORT": "8080"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.PORT == 8080

    def test_default_log_format(self):
        """Test default log format is text"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.LOG_FORMAT == "text"

    def test_default_request_timeout(self):
        """Test default request timeout is 10 seconds"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.REQUEST_TIMEOUT == 10

    def test_custom_request_timeout(self):
        """Test request timeout can be customized"""
        with patch.dict(os.environ, {"REQUEST_TIMEOUT": "30"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.REQUEST_TIMEOUT == 30

    def test_default_max_concurrent_requests(self):
        """Test default max concurrent requests is 10"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.MAX_CONCURRENT_REQUESTS == 10

    def test_default_cache_ttl(self):
        """Test default cache TTL is 300 seconds (5 minutes)"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.CACHE_TTL_SECONDS == 300

    def test_default_kubernetes_poll_interval(self):
        """Test default Kubernetes poll interval is 600 seconds"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.KUBERNETES_POLL_INTERVAL == 600

    def test_default_check_interval(self):
        """Test default check interval is 30 seconds"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.CHECK_INTERVAL == 30

    def test_default_swagger_discovery_interval(self):
        """Test default Swagger discovery interval is 3600 seconds (1 hour)"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.SWAGGER_DISCOVERY_INTERVAL == 3600

    def test_urls_file_development_mode(self):
        """Test URLs file path in development mode"""
        with patch.dict(os.environ, {"FLASK_ENV": "development"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.URLS_FILE == "config/urls.yaml"

    def test_urls_file_production_mode(self):
        """Test URLs file path in production mode"""
        with patch.dict(os.environ, {"FLASK_ENV": "production"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.URLS_FILE == "/app/data/urls.yaml"

    def test_excluded_urls_file_development_mode(self):
        """Test excluded URLs file path in development mode"""
        with patch.dict(os.environ, {"FLASK_ENV": "development"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.EXCLUDED_URLS_FILE == "config/excluded-urls.yaml"

    def test_excluded_urls_file_production_mode(self):
        """Test excluded URLs file path in production mode"""
        with patch.dict(os.environ, {"FLASK_ENV": "production"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.EXCLUDED_URLS_FILE == "/app/config/excluded-urls.yaml"

    def test_custom_cert_default_none(self):
        """Test custom cert is None by default"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.CUSTOM_CERT is None

    def test_custom_cert_from_env(self):
        """Test custom cert can be set from environment"""
        with patch.dict(os.environ, {"CUSTOM_CERT": "/path/to/cert.pem"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.CUSTOM_CERT == "/path/to/cert.pem"

    def test_auto_refresh_enabled_by_default(self):
        """Test auto refresh is enabled by default"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.AUTO_REFRESH_ON_START is True

    def test_auto_refresh_can_be_disabled(self):
        """Test auto refresh can be disabled"""
        with patch.dict(os.environ, {"AUTO_REFRESH_ON_START": "false"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.AUTO_REFRESH_ON_START is False

    def test_slack_notifications_disabled_by_default(self):
        """Test Slack notifications are disabled by default"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.ENABLE_SLACK_NOTIFICATIONS is False

    def test_slack_notifications_can_be_enabled(self):
        """Test Slack notifications can be enabled"""
        with patch.dict(os.environ, {"ENABLE_SLACK_NOTIFICATIONS": "true"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.ENABLE_SLACK_NOTIFICATIONS is True

    def test_autoswagger_enabled_by_default(self):
        """Test autoswagger is enabled by default"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.ENABLE_AUTOSWAGGER is True

    def test_autoswagger_can_be_disabled(self):
        """Test autoswagger can be disabled"""
        with patch.dict(os.environ, {"ENABLE_AUTOSWAGGER": "false"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.ENABLE_AUTOSWAGGER is False

    def test_debug_mode_development(self):
        """Test DEBUG is True in development mode"""
        with patch.dict(os.environ, {"FLASK_ENV": "development"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.DEBUG is True

    def test_debug_mode_production(self):
        """Test DEBUG is False in production mode"""
        with patch.dict(os.environ, {"FLASK_ENV": "production"}):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.DEBUG is False

    def test_default_kube_env(self):
        """Test default Kubernetes environment is production"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.KUBE_ENV == "production"

    def test_slack_webhook_url_empty_by_default(self):
        """Test Slack webhook URL is empty by default"""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import src.config as config
            importlib.reload(config)
            assert config.SLACK_WEBHOOK_URL == ""
