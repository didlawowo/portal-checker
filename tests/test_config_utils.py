import sys
import os
# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from unittest.mock import patch, mock_open, MagicMock
import tempfile
import os
import ssl
import certifi

from src.app import serialize_record, get_app_version, setup_logger, sslMode, load_excluded_urls


class TestConfigurationAndUtils:
    """Test configuration functions and utilities"""

    def test_serialize_record_basic(self):
        """Test basic log record serialization"""
        # Mock a loguru record
        mock_record = {
            "time": MagicMock(),
            "level": MagicMock(),
            "message": "Test message",
            "module": "test_module",
            "function": "test_function", 
            "line": 42,
            "process": MagicMock(),
            "thread": MagicMock(),
            "extra": {},
            "exception": None
        }
        
        # Configure mocks
        mock_record["time"].strftime.return_value = "2024-01-01 12:00:00.000000"
        mock_record["level"].name = "INFO"
        mock_record["process"].id = 1234
        mock_record["process"].name = "test-process"
        mock_record["thread"].id = 5678
        mock_record["thread"].name = "test-thread"
        
        result = serialize_record(mock_record)
        
        assert result["timestamp"] == "2024-01-01 12:00:00.000000"
        assert result["level"] == "INFO"
        assert result["message"] == "Test message"
        assert result["module"] == "test_module"
        assert result["function"] == "test_function"
        assert result["line"] == 42
        assert result["process"]["id"] == 1234
        assert result["process"]["name"] == "test-process"
        assert result["thread"]["id"] == 5678
        assert result["thread"]["name"] == "test-thread"

    def test_serialize_record_with_extra(self):
        """Test log record serialization with extra data"""
        mock_record = {
            "time": MagicMock(),
            "level": MagicMock(),
            "message": "Test with extra",
            "module": "test",
            "function": "test",
            "line": 1,
            "process": MagicMock(),
            "thread": MagicMock(),
            "extra": {"user_id": 123, "request_id": "abc-123"},
            "exception": None
        }
        
        mock_record["time"].strftime.return_value = "2024-01-01 12:00:00.000000"
        mock_record["level"].name = "DEBUG"
        mock_record["process"].id = 1
        mock_record["process"].name = "test"
        mock_record["thread"].id = 1
        mock_record["thread"].name = "test"
        
        result = serialize_record(mock_record)
        
        assert "extra" in result
        assert result["extra"]["user_id"] == 123
        assert result["extra"]["request_id"] == "abc-123"

    def test_serialize_record_with_exception(self):
        """Test log record serialization with exception"""
        mock_record = {
            "time": MagicMock(),
            "level": MagicMock(),
            "message": "Error occurred",
            "module": "test",
            "function": "test",
            "line": 1,
            "process": MagicMock(),
            "thread": MagicMock(),
            "extra": {},
            "exception": "ValueError: Something went wrong"
        }
        
        mock_record["time"].strftime.return_value = "2024-01-01 12:00:00.000000"
        mock_record["level"].name = "ERROR"
        mock_record["process"].id = 1
        mock_record["process"].name = "test"
        mock_record["thread"].id = 1
        mock_record["thread"].name = "test"
        
        result = serialize_record(mock_record)
        
        assert "exception" in result
        assert result["exception"] == "ValueError: Something went wrong"

    @patch('builtins.open', new_callable=mock_open, read_data='[tool.project]\nversion = "2.6.6"')
    @patch('app.tomllib.load')
    def test_get_app_version_success(self, mock_toml_load, mock_file):
        """Test successful version extraction from pyproject.toml"""
        mock_toml_load.return_value = {
            "project": {
                "version": "2.6.6"
            }
        }
        
        version = get_app_version()
        
        assert version == "2.6.6"
        mock_file.assert_called_once()

    @patch('builtins.open')
    @patch('app.tomllib.load')
    def test_get_app_version_file_not_found(self, mock_toml_load, mock_file):
        """Test version extraction when pyproject.toml not found"""
        mock_file.side_effect = FileNotFoundError()
        
        version = get_app_version()
        
        assert version == "unknown"


    @patch('builtins.open', new_callable=mock_open)
    @patch('app.tomllib.load')
    def test_get_app_version_missing_version(self, mock_toml_load, mock_file):
        """Test version extraction when version field is missing"""
        mock_toml_load.return_value = {
            "project": {
                "name": "portal-checker"
                # Missing version field
            }
        }
        
        version = get_app_version()
        
        assert version == "unknown"

    @patch('app.logger.remove')
    @patch('app.logger.add')
    def test_setup_logger_text_format(self, mock_logger_add, mock_logger_remove):
        """Test logger setup with text format"""
        setup_logger(log_format="text", log_level="DEBUG")
        
        mock_logger_remove.assert_called()
        mock_logger_add.assert_called()
        
        # Verify the logger.add call parameters
        call_args = mock_logger_add.call_args
        assert "level=DEBUG" in str(call_args) or call_args[1]["level"] == "DEBUG"

    @patch('app.logger.remove')
    @patch('app.logger.add')
    def test_setup_logger_json_format(self, mock_logger_add, mock_logger_remove):
        """Test logger setup with JSON format"""
        setup_logger(log_format="json", log_level="INFO")
        
        mock_logger_remove.assert_called()
        mock_logger_add.assert_called()
        
        # Verify JSON serializer is used
        call_args = mock_logger_add.call_args
        assert call_args is not None

    @patch('app.logger.remove')
    @patch('app.logger.add')
    def test_setup_logger_default_params(self, mock_logger_add, mock_logger_remove):
        """Test logger setup with default parameters"""
        setup_logger()  # No parameters, should use defaults
        
        mock_logger_remove.assert_called()
        mock_logger_add.assert_called()

    @patch('app.os.getenv')
    @patch('app.os.path.exists')
    @patch('app.ssl.create_default_context')
    def test_ssl_mode_with_custom_cert(self, mock_ssl_context, mock_exists, mock_getenv):
        """Test SSL mode with custom certificate"""
        def mock_env(key, default=None):
            if key == "CUSTOM_CERT":
                return "/path/to/custom/cert.pem"
            return default
            
        mock_getenv.side_effect = mock_env
        mock_exists.return_value = True
        
        mock_context = MagicMock()
        mock_context.get_ca_certs.return_value = ["cert1", "cert2"]
        mock_ssl_context.return_value = mock_context
        
        result = sslMode()
        
        # Verify SSL context creation and cert loading
        mock_ssl_context.assert_called_once_with(cafile=certifi.where())
        mock_context.load_verify_locations.assert_called_once_with(capath="/path/to/custom/cert.pem")
        assert result == mock_context

    @patch('app.os.getenv')
    @patch('app.os.path.exists')
    @patch('app.ssl.create_default_context')
    def test_ssl_mode_custom_cert_not_found(self, mock_ssl_context, mock_exists, mock_getenv):
        """Test SSL mode when custom cert file doesn't exist"""
        def mock_env(key, default=None):
            if key == "CUSTOM_CERT":
                return "/path/to/missing/cert.pem"
            return default
            
        mock_getenv.side_effect = mock_env
        mock_exists.return_value = False
        
        mock_context = MagicMock()
        mock_ssl_context.return_value = mock_context
        
        result = sslMode()
        
        # Should still return context but not load custom cert
        mock_ssl_context.assert_called_once()
        mock_context.load_verify_locations.assert_not_called()
        assert result == mock_context

    @patch('app.os.getenv')
    @patch('app.os.path.exists')
    @patch('app.ssl.create_default_context')
    def test_ssl_mode_cert_loading_error(self, mock_ssl_context, mock_exists, mock_getenv):
        """Test SSL mode handles cert loading errors"""
        def mock_env(key, default=None):
            if key == "CUSTOM_CERT":
                return "/path/to/invalid/cert.pem"
            return default
            
        mock_getenv.side_effect = mock_env
        mock_exists.return_value = True
        
        mock_context = MagicMock()
        mock_context.load_verify_locations.side_effect = Exception("Invalid cert")
        mock_ssl_context.return_value = mock_context
        
        result = sslMode()
        
        # Should handle error and still return context
        assert result == mock_context

    @patch('app.os.getenv')
    def test_ssl_mode_no_custom_cert(self, mock_getenv):
        """Test SSL mode without custom certificate"""
        mock_getenv.return_value = None  # No CUSTOM_CERT env var
        
        result = sslMode()
        
        # Should return False (SSL verification disabled)
        assert result is False

    @patch('app.EXCLUDED_URLS_FILE', '/tmp/test-excluded.yaml')
    @patch('builtins.open', new_callable=mock_open, read_data='- monitoring.*\n- "*.internal/*"\n- admin.example.com')
    @patch('app.os.path.exists')
    def test_load_excluded_urls_success(self, mock_exists, mock_file):
        """Test successful loading of excluded URLs"""
        mock_exists.return_value = True
        
        result = load_excluded_urls()
        
        assert isinstance(result, set)
        assert "monitoring.*" in result
        assert "*.internal/*" in result
        assert "admin.example.com" in result

    @patch('app.EXCLUDED_URLS_FILE', '/tmp/missing-file.yaml')
    @patch('app.os.path.exists')
    def test_load_excluded_urls_file_not_found(self, mock_exists):
        """Test loading excluded URLs when file doesn't exist"""
        mock_exists.return_value = False
        
        result = load_excluded_urls()
        
        assert result == set()

    @patch('app.EXCLUDED_URLS_FILE', '/tmp/invalid.yaml')
    @patch('builtins.open', new_callable=mock_open, read_data='invalid: yaml: content')
    @patch('app.os.path.exists')
    def test_load_excluded_urls_yaml_error(self, mock_exists, mock_file):
        """Test loading excluded URLs with YAML parsing error"""
        mock_exists.return_value = True
        
        result = load_excluded_urls()
        
        assert result == set()

    @patch('app.EXCLUDED_URLS_FILE', '/tmp/excluded-urls.yaml')
    @patch('builtins.open', new_callable=mock_open, read_data='invalid: format')
    @patch('app.os.path.exists')
    def test_load_excluded_urls_invalid_format(self, mock_exists, mock_file):
        """Test loading excluded URLs with invalid data format"""
        mock_exists.return_value = True
        
        result = load_excluded_urls()
        
        assert result == set()

    def test_load_excluded_urls_no_env_var(self):
        """Test loading excluded URLs uses default file"""
        # This test just verifies the function doesn't crash with default file
        result = load_excluded_urls()
        
        assert isinstance(result, set)