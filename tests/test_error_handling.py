import sys
import os
# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
import yaml

from src.kubernetes_client import is_url_excluded, invalidate_excluded_patterns_cache


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_url_exclusion_basic_functionality(self):
        """Test basic URL exclusion functionality"""
        # Test with simple URL
        result = is_url_excluded("example.com", {})
        assert isinstance(result, bool)

        # Test with URL and path
        result = is_url_excluded("example.com/api", {})
        assert isinstance(result, bool)

    def test_is_url_excluded_with_annotations(self):
        """Test URL exclusion with annotations"""
        # Test with exclusion annotation
        annotations = {'portal-checker.io/exclude': 'true'}
        assert is_url_excluded("example.com", annotations) == True

        # Test with case variation
        annotations = {'portal-checker.io/exclude': 'True'}
        assert is_url_excluded("example.com", annotations) == True

        # Test with false annotation
        annotations = {'portal-checker.io/exclude': 'false'}
        assert is_url_excluded("example.com", annotations) == False

        # Test without exclusion annotation
        annotations = {'other.annotation': 'value'}
        # This will check against loaded excluded URLs patterns
        result = is_url_excluded("example.com", annotations)
        assert isinstance(result, bool)

        # Test with empty annotations
        assert isinstance(is_url_excluded("example.com", {}), bool)

        # Test with None annotations
        assert isinstance(is_url_excluded("example.com", None), bool)

    def test_is_url_excluded_with_patterns(self, monkeypatch):
        """Test URL exclusion with different patterns"""
        # Create test YAML with monitoring pattern
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(["monitoring.*"], f)
            temp_file = f.name

        try:
            monkeypatch.setattr('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file)
            invalidate_excluded_patterns_cache()

            # Test with URLs that might match existing patterns
            result1 = is_url_excluded("monitoring.example.com", {})
            result2 = is_url_excluded("normal.example.com", {})

            # monitoring.* should match
            assert result1 is True
            assert result2 is False
        finally:
            os.unlink(temp_file)
            invalidate_excluded_patterns_cache()

    def test_is_url_excluded_different_urls(self):
        """Test URL exclusion with different URL types"""
        test_urls = [
            "any.example.com",
            "test.internal/api",
            "service.external.com",
            "app.test.com/admin"
        ]

        for url in test_urls:
            result = is_url_excluded(url, {})
            assert isinstance(result, bool), f"Failed for URL: {url}"

    def test_is_url_excluded_pattern_matching_error(self, monkeypatch):
        """Test URL exclusion when pattern matching fails"""
        # Create YAML with potentially problematic pattern
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(['[invalid-regex'], f)
            temp_file = f.name

        try:
            monkeypatch.setattr('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file)
            invalidate_excluded_patterns_cache()

            # Should handle pattern matching errors gracefully
            result = is_url_excluded("test.example.com", {})
            assert isinstance(result, bool)
        except Exception as e:
            # Pattern errors should be handled gracefully
            pytest.fail(f"is_url_excluded should handle pattern errors gracefully: {e}")
        finally:
            os.unlink(temp_file)
            invalidate_excluded_patterns_cache()

    def test_url_exclusion_case_sensitivity(self):
        """Test URL exclusion case sensitivity"""
        # URL normalization should handle case consistently
        result1 = is_url_excluded("Example.Com", {})
        result2 = is_url_excluded("example.com", {})
        result3 = is_url_excluded("EXAMPLE.COM", {})

        # Results should be consistent (URLs normalized to lowercase)
        assert isinstance(result1, bool)
        assert isinstance(result2, bool)
        assert isinstance(result3, bool)
        # All should be the same after normalization
        assert result1 == result2 == result3

    def test_url_exclusion_with_special_characters(self):
        """Test URL exclusion with special characters"""
        # Test URLs with special characters
        urls_to_test = [
            "example-test.com",
            "test_service.example.com",
            "api.example.com:8080",
            "service.example.com/api-v1",
            "app.example.com/user_profile"
        ]

        for url in urls_to_test:
            result = is_url_excluded(url, {})
            assert isinstance(result, bool), f"Failed for URL: {url}"
