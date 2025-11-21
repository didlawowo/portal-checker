import sys
import os
# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
import yaml

from src.kubernetes_client import is_url_excluded, invalidate_excluded_patterns_cache


class TestExclude:
    """Test suite for URL exclusion functionality"""

    @pytest.fixture
    def setup_excluded_urls(self, monkeypatch):
        """Setup fixture with temporary YAML file"""
        # Create temporary YAML file with test patterns
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump([
                "example.com/admin",
                "api.example.com/private/*",
                "test.com"
            ], f)
            temp_file = f.name

        # Patch EXCLUDED_URLS_FILE to use temp file
        monkeypatch.setattr('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file)

        # Invalidate cache to force reload
        invalidate_excluded_patterns_cache()

        yield temp_file

        # Cleanup
        os.unlink(temp_file)
        invalidate_excluded_patterns_cache()

    def test_exact_match(self, setup_excluded_urls):
        """Test exact URL matching"""
        assert is_url_excluded("example.com/admin", {}) is True
        assert is_url_excluded("example.com/public", {}) is False

    def test_wildcard_match(self, setup_excluded_urls):
        """Test wildcard pattern matching"""
        assert is_url_excluded("api.example.com/private/users", {}) is True
        assert is_url_excluded("api.example.com/private/settings", {}) is True
        assert is_url_excluded("api.example.com/public/users", {}) is False

    def test_domain_match(self, setup_excluded_urls):
        """Test domain-only matching"""
        assert is_url_excluded("test.com", {}) is True
        assert is_url_excluded("test.com/", {}) is True  # Test avec slash à la fin
        # Sous-chemins ne devraient pas matcher sans wildcard
        assert is_url_excluded("test.com/any", {}) is False

    def test_trailing_slash(self, monkeypatch):
        """Test URL normalization with trailing slashes"""
        # Create YAML with trailing slash pattern
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(["service.example.com/"], f)
            temp_file = f.name

        try:
            monkeypatch.setattr('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file)
            invalidate_excluded_patterns_cache()

            assert is_url_excluded("service.example.com", {}) is True
            assert is_url_excluded("service.example.com/", {}) is True
        finally:
            os.unlink(temp_file)
            invalidate_excluded_patterns_cache()
