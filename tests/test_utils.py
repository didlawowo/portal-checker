import sys
import os
# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
import yaml
from unittest.mock import patch, MagicMock, AsyncMock
import aiohttp

from src.utils import get_app_version, load_urls_from_file, check_urls_async


class TestUtils:
    """Test utility functions"""

    def test_get_app_version_success(self):
        """Test reading version from pyproject.toml"""
        version = get_app_version()
        assert isinstance(version, str)
        assert version != "unknown"
        # Version should be in semver format (e.g., "3.0.7")
        assert len(version.split('.')) >= 2

    @patch('builtins.open', side_effect=FileNotFoundError())
    def test_get_app_version_file_not_found(self, mock_open):
        """Test version returns 'unknown' when pyproject.toml not found"""
        version = get_app_version()
        assert version == "unknown"

    def test_load_urls_from_file_success(self):
        """Test loading URLs from valid YAML file"""
        # Create temp YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({
                "urls": [
                    {
                        "url": "example.com",
                        "namespace": "default",
                        "name": "test-service",
                        "type": "Ingress"
                    },
                    {
                        "url": "api.example.com",
                        "namespace": "production",
                        "name": "api-service",
                        "type": "HTTPRoute"
                    }
                ]
            }, f)
            temp_file = f.name

        try:
            urls = load_urls_from_file(temp_file)
            assert len(urls) == 2
            assert urls[0]["url"] == "example.com"
            assert urls[0]["namespace"] == "default"
            assert urls[1]["url"] == "api.example.com"
        finally:
            os.unlink(temp_file)

    def test_load_urls_from_file_list_format(self):
        """Test loading URLs from YAML file with list format"""
        # Create temp YAML file with list format (old format)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump([
                {"url": "example.com", "name": "test"},
                {"url": "api.com", "name": "api"}
            ], f)
            temp_file = f.name

        try:
            urls = load_urls_from_file(temp_file)
            assert len(urls) == 2
            assert urls[0]["url"] == "example.com"
        finally:
            os.unlink(temp_file)

    def test_load_urls_from_file_not_found(self):
        """Test loading URLs from non-existent file returns empty list"""
        urls = load_urls_from_file("/nonexistent/file.yaml")
        assert urls == []

    def test_load_urls_from_file_invalid_yaml(self):
        """Test loading URLs from invalid YAML returns empty list"""
        # Create temp file with invalid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_file = f.name

        try:
            urls = load_urls_from_file(temp_file)
            assert urls == []
        finally:
            os.unlink(temp_file)

    def test_load_urls_from_file_empty(self):
        """Test loading URLs from empty file returns empty list"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_file = f.name

        try:
            urls = load_urls_from_file(temp_file)
            assert urls == []
        finally:
            os.unlink(temp_file)

    @pytest.mark.asyncio
    async def test_check_urls_async_success(self):
        """Test async URL checking with successful responses"""
        test_urls = [
            {
                "url": "https://example.com",
                "namespace": "default",
                "name": "test-service",
                "type": "Ingress",
                "annotations": {}
            }
        ]

        # Mock aiohttp ClientSession with proper async context manager
        with patch('src.utils.aiohttp.ClientSession') as mock_session_class:
            # Mock response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="OK")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            # Mock session
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session

            results = await check_urls_async(test_urls, update_cache=False)

            assert len(results) == 1
            assert results[0]["status"] == 200
            assert results[0]["url"] == "https://example.com"
            assert "response_time" in results[0]

    @pytest.mark.asyncio
    async def test_check_urls_async_with_exclusion(self):
        """Test async URL checking with excluded URLs"""
        test_urls = [
            {
                "url": "https://example.com",
                "namespace": "default",
                "name": "test-service",
                "type": "Ingress",
                "annotations": {}
            }
        ]

        # Mock exclusion function to exclude all
        def mock_is_excluded(url):
            return True

        results = await check_urls_async(test_urls, update_cache=False, is_url_excluded_func=mock_is_excluded)

        # Excluded URLs are filtered out, so results should be empty
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_check_urls_async_http_error(self):
        """Test async URL checking with HTTP errors"""
        test_urls = [
            {
                "url": "https://error.example.com",
                "namespace": "default",
                "name": "error-service",
                "type": "Ingress",
                "annotations": {}
            }
        ]

        # Mock aiohttp to raise error
        with patch('src.utils.aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            # Make session.get() raise an error
            mock_session.get = MagicMock(side_effect=aiohttp.ClientError("Connection error"))
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            results = await check_urls_async(test_urls, update_cache=False)

            assert len(results) == 1
            # The function returns 503 for ClientError
            assert results[0]["status"] == 503
            assert "Connection error" in results[0].get("details", "")

    @pytest.mark.asyncio
    async def test_check_urls_async_timeout(self):
        """Test async URL checking with timeout"""
        test_urls = [
            {
                "url": "https://timeout.example.com",
                "namespace": "default",
                "name": "timeout-service",
                "type": "Ingress",
                "annotations": {}
            }
        ]

        # Mock aiohttp to raise timeout
        with patch('src.utils.aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session.get = MagicMock(side_effect=aiohttp.ServerTimeoutError("Timeout"))
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session_class.return_value = mock_session

            results = await check_urls_async(test_urls, update_cache=False)

            assert len(results) == 1
            # The function returns 408 for timeout errors
            assert results[0]["status"] == 408
            assert "timeout" in results[0].get("details", "").lower()

    @pytest.mark.asyncio
    async def test_check_urls_async_empty_list(self):
        """Test async URL checking with empty list"""
        results = await check_urls_async([], update_cache=False)
        assert results == []

    @pytest.mark.asyncio
    async def test_check_urls_async_response_time(self):
        """Test async URL checking includes response time"""
        test_urls = [
            {
                "url": "https://fast.example.com",
                "namespace": "default",
                "name": "fast-service",
                "type": "Ingress",
                "annotations": {}
            }
        ]

        with patch('src.utils.aiohttp.ClientSession') as mock_session_class:
            # Mock response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="OK")
            mock_response.__aenter__ = AsyncMock(return_value=mock_response)
            mock_response.__aexit__ = AsyncMock(return_value=None)

            # Mock session
            mock_session = AsyncMock()
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)

            mock_session_class.return_value = mock_session

            results = await check_urls_async(test_urls, update_cache=False)

            assert len(results) == 1
            assert "response_time" in results[0]
            assert isinstance(results[0]["response_time"], (int, float))
            assert results[0]["response_time"] >= 0
