import os
import sys
import tempfile

import pytest
import yaml

# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import functions to test
from src.kubernetes_client import is_url_excluded


class TestExcludedUrls:
    """Test suite for excluded URL functionality"""

    @pytest.fixture
    def setup_excluded_urls(self, monkeypatch):
        """Setup fixture with temporary YAML file"""
        # Create temporary YAML file with test patterns
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump([
                "monitoring.*",  # Wildcard at end
                "*.internal/*",  # Wildcard pattern
                "infisical.dc-tech.work/ss-webhook",  # Exact match
                "admin.example.com",  # Domain exact match
                "api.test.com/private/*",  # Path with wildcard
                "service.local/",  # With trailing slash
            ], f)
            temp_file = f.name

        # Patch EXCLUDED_URLS_FILE to use temp file
        monkeypatch.setattr('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file)

        # Invalidate cache to force reload
        from src.kubernetes_client import invalidate_excluded_patterns_cache
        invalidate_excluded_patterns_cache()

        yield temp_file

        # Cleanup
        os.unlink(temp_file)
        invalidate_excluded_patterns_cache()

    def test_exact_url_match(self, setup_excluded_urls):
        """Test exact URL matching"""
        assert is_url_excluded("infisical.dc-tech.work/ss-webhook", {}) is True
        assert is_url_excluded("admin.example.com", {}) is True
        assert is_url_excluded("other.example.com", {}) is False

    def test_domain_wildcard_patterns(self, setup_excluded_urls):
        """Test wildcard patterns for domains"""
        # monitoring.* pattern (wildcard at end)
        assert is_url_excluded("monitoring.example.com", {}) is True
        assert is_url_excluded("monitoring.test.local", {}) is True
        assert is_url_excluded("monitoring.", {}) is True
        assert is_url_excluded("notmonitoring.example.com", {}) is False
        
        # *.internal/* pattern - now supported with fnmatch
        assert is_url_excluded("test.internal/api", {}) is True
        assert is_url_excluded("service.internal/admin", {}) is True
        assert is_url_excluded("app.internal/dashboard", {}) is True
        assert is_url_excluded("external.example.com/api", {}) is False

    def test_path_wildcard_patterns(self, setup_excluded_urls):
        """Test wildcard patterns in paths"""
        # api.test.com/private/* pattern (wildcard at end)
        assert is_url_excluded("api.test.com/private/users", {}) is True
        assert is_url_excluded("api.test.com/private/settings", {}) is True
        assert is_url_excluded("api.test.com/private/admin", {}) is True
        assert is_url_excluded("api.test.com/public/users", {}) is False
        # Note: exact match "api.test.com/private" won't match "api.test.com/private/*"

    def test_trailing_slash_normalization(self, setup_excluded_urls):
        """Test URL normalization with trailing slashes"""
        # service.local/ pattern
        assert is_url_excluded("service.local", {}) is True
        assert is_url_excluded("service.local/", {}) is True
        assert is_url_excluded("service.local/admin", {}) is False

    def test_url_normalization_edge_cases(self, monkeypatch):
        """Test edge cases in URL normalization"""
        # Create YAML with test pattern
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(["test.com/path"], f)
            temp_file = f.name

        try:
            monkeypatch.setattr('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file)
            from src.kubernetes_client import invalidate_excluded_patterns_cache
            invalidate_excluded_patterns_cache()

            assert is_url_excluded("test.com/path", {}) is True
            assert is_url_excluded("test.com/path/", {}) is True
            assert is_url_excluded("test.com/path/subpath", {}) is False
        finally:
            os.unlink(temp_file)

    def test_empty_excluded_urls(self, monkeypatch):
        """Test behavior when no URLs are excluded"""
        # Create empty YAML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump([], f)
            temp_file = f.name

        try:
            # Patch EXCLUDED_URLS_FILE
            monkeypatch.setattr('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file)

            # Invalidate cache
            from src.kubernetes_client import invalidate_excluded_patterns_cache
            invalidate_excluded_patterns_cache()

            assert is_url_excluded("any.domain.com", {}) is False
            assert is_url_excluded("any.domain.com/path", {}) is False
        finally:
            os.unlink(temp_file)

    def test_wildcard_only_at_end(self, monkeypatch):
        """Test that wildcards only work at the end of patterns"""
        # Create YAML with wildcard pattern
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(["test.example.com/api/*"], f)
            temp_file = f.name

        try:
            monkeypatch.setattr('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file)
            from src.kubernetes_client import invalidate_excluded_patterns_cache
            invalidate_excluded_patterns_cache()

            # Should match paths starting with the prefix
            assert is_url_excluded("test.example.com/api/users", {}) is True
            assert is_url_excluded("test.example.com/api/admin", {}) is True
            assert is_url_excluded("test.example.com/other/users", {}) is False
        finally:
            os.unlink(temp_file)

    def test_fnmatch_complex_patterns(self, monkeypatch):
        """Test complex patterns using fnmatch functionality"""
        # Create YAML with complex patterns
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump([
                "*.test.com/admin",  # wildcard at start
                "api-*.example.com",  # wildcard in middle
            ], f)
            temp_file = f.name

        try:
            monkeypatch.setattr('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file)
            from src.kubernetes_client import invalidate_excluded_patterns_cache
            invalidate_excluded_patterns_cache()

            # Test wildcard at start
            assert is_url_excluded("app.test.com/admin", {}) is True
            assert is_url_excluded("web.test.com/admin", {}) is True
            assert is_url_excluded("app.test.com/public", {}) is False

            # Test wildcard in middle
            assert is_url_excluded("api-v1.example.com", {}) is True
            assert is_url_excluded("api-v2.example.com", {}) is True
            assert is_url_excluded("web-v1.example.com", {}) is False
        finally:
            os.unlink(temp_file)

    def test_load_excluded_urls_from_yaml(self, monkeypatch):
        """Test loading excluded URLs from YAML file"""
        # Create temporary YAML file
        test_exclusions = [
            "test.example.com",
            "*.internal/*",
            "monitoring.*"
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump(test_exclusions, f)
            temp_file = f.name

        try:
            # Patch EXCLUDED_URLS_FILE
            monkeypatch.setattr('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file)

            # Invalidate cache and load
            from src.kubernetes_client import invalidate_excluded_patterns_cache, _load_excluded_patterns
            invalidate_excluded_patterns_cache()
            loaded_exclusions = _load_excluded_patterns()

            assert len(loaded_exclusions) == 3
            assert "test.example.com" in loaded_exclusions
            assert "*.internal/*" in loaded_exclusions
            assert "monitoring.*" in loaded_exclusions

        finally:
            # Cleanup
            os.unlink(temp_file)
            invalidate_excluded_patterns_cache()


    @pytest.mark.parametrize("url,expected", [
        ("monitoring.example.com", True),  # matches monitoring.*
        ("test.internal/api", True),  # matches *.internal/* pattern
        ("service.internal/admin", True),  # matches *.internal/* pattern
        ("normal.website.com", False),  # no match
        ("external.example.com", False),  # no match
        ("external.example.com/api", False),  # doesn't match internal pattern
    ])
    def test_parametrized_exclusions(self, setup_excluded_urls, url, expected):
        """Parametrized test for various URL exclusion scenarios"""
        assert is_url_excluded(url, {}) is expected

if __name__ == "__main__":
    pytest.main([__file__, "-v"])