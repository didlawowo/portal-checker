import os
import sys
import tempfile

import pytest
import yaml

# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import functions to test
from src.app import _is_url_excluded, excluded_urls


class TestExcludedUrls:
    """Test suite for excluded URL functionality"""
    
    @pytest.fixture
    def setup_excluded_urls(self):
        """Setup fixture to reset excluded_urls for each test"""
        global excluded_urls
        excluded_urls.clear()
        
        # Add test exclusion patterns based on current config
        excluded_urls.update([
            "monitoring.*",  # Wildcard at end - matches from config
            "*.internal/*",  # Wildcard pattern from config  
            "infisical.dc-tech.work/ss-webhook",  # Exact match from config
            "admin.example.com",  # Domain exact match
            "api.test.com/private/*",  # Path with wildcard
            "service.local/",  # With trailing slash
        ])
        
        yield
        
        # Cleanup after test
        excluded_urls.clear()

    def test_exact_url_match(self, setup_excluded_urls):
        """Test exact URL matching"""
        assert _is_url_excluded("infisical.dc-tech.work/ss-webhook") is True
        assert _is_url_excluded("admin.example.com") is True
        assert _is_url_excluded("other.example.com") is False

    def test_domain_wildcard_patterns(self, setup_excluded_urls):
        """Test wildcard patterns for domains"""
        # monitoring.* pattern (wildcard at end)
        assert _is_url_excluded("monitoring.example.com") is True
        assert _is_url_excluded("monitoring.test.local") is True
        assert _is_url_excluded("monitoring.") is True
        assert _is_url_excluded("notmonitoring.example.com") is False
        
        # *.internal/* pattern - now supported with fnmatch
        assert _is_url_excluded("test.internal/api") is True
        assert _is_url_excluded("service.internal/admin") is True
        assert _is_url_excluded("app.internal/dashboard") is True
        assert _is_url_excluded("external.example.com/api") is False

    def test_path_wildcard_patterns(self, setup_excluded_urls):
        """Test wildcard patterns in paths"""
        # api.test.com/private/* pattern (wildcard at end)
        assert _is_url_excluded("api.test.com/private/users") is True
        assert _is_url_excluded("api.test.com/private/settings") is True
        assert _is_url_excluded("api.test.com/private/admin") is True
        assert _is_url_excluded("api.test.com/public/users") is False
        # Note: exact match "api.test.com/private" won't match "api.test.com/private/*"

    def test_trailing_slash_normalization(self, setup_excluded_urls):
        """Test URL normalization with trailing slashes"""
        # service.local/ pattern
        assert _is_url_excluded("service.local") is True
        assert _is_url_excluded("service.local/") is True
        assert _is_url_excluded("service.local/admin") is False

    def test_url_normalization_edge_cases(self, setup_excluded_urls):
        """Test edge cases in URL normalization"""
        # Add pattern for testing
        excluded_urls.add("test.com/path")
        
        assert _is_url_excluded("test.com/path") is True
        assert _is_url_excluded("test.com/path/") is True
        assert _is_url_excluded("test.com/path/subpath") is False

    def test_empty_excluded_urls(self):
        """Test behavior when no URLs are excluded"""
        excluded_urls.clear()
        
        assert _is_url_excluded("any.domain.com") is False
        assert _is_url_excluded("any.domain.com/path") is False

    def test_wildcard_only_at_end(self, setup_excluded_urls):
        """Test that wildcards only work at the end of patterns"""
        # Add a pattern with wildcard at end
        excluded_urls.add("test.example.com/api/*")
        
        # Should match paths starting with the prefix
        assert _is_url_excluded("test.example.com/api/users") is True
        assert _is_url_excluded("test.example.com/api/admin") is True
        assert _is_url_excluded("test.example.com/other/users") is False

    def test_fnmatch_complex_patterns(self, setup_excluded_urls):
        """Test complex patterns using fnmatch functionality"""
        # Add complex patterns that work with fnmatch
        excluded_urls.add("*.test.com/admin")  # wildcard at start
        excluded_urls.add("api-*.example.com")  # wildcard in middle
        
        # Test wildcard at start
        assert _is_url_excluded("app.test.com/admin") is True
        assert _is_url_excluded("web.test.com/admin") is True
        assert _is_url_excluded("app.test.com/public") is False
        
        # Test wildcard in middle
        assert _is_url_excluded("api-v1.example.com") is True
        assert _is_url_excluded("api-v2.example.com") is True
        assert _is_url_excluded("web-v1.example.com") is False

    def test_load_excluded_urls_from_yaml(self):
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
            # Save original state
            original_excluded_urls = excluded_urls.copy()
            original_file = os.environ.get('EXCLUDED_URLS_FILE')
            
            # Set temp file and reload
            os.environ['EXCLUDED_URLS_FILE'] = temp_file
            excluded_urls.clear()
            
            # Import again to get a fresh load_excluded_urls function
            import importlib

            import src.app as app
            importlib.reload(app)
            loaded_exclusions = app.load_excluded_urls()
            
            assert len(loaded_exclusions) == 3
            assert "test.example.com" in loaded_exclusions
            assert "*.internal/*" in loaded_exclusions
            assert "monitoring.*" in loaded_exclusions
            
        finally:
            # Restore original state
            excluded_urls.clear()
            excluded_urls.update(original_excluded_urls)
            
            # Cleanup
            os.unlink(temp_file)
            if original_file:
                os.environ['EXCLUDED_URLS_FILE'] = original_file
            elif 'EXCLUDED_URLS_FILE' in os.environ:
                del os.environ['EXCLUDED_URLS_FILE']


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
        assert _is_url_excluded(url) is expected

if __name__ == "__main__":
    pytest.main([__file__, "-v"])