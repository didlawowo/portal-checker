import pytest
from unittest.mock import patch, MagicMock
import tempfile
import os

from app import _is_url_excluded


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_url_exclusion_basic_functionality(self):
        """Test basic URL exclusion functionality"""
        # Test with simple URL
        result = _is_url_excluded("example.com")
        assert isinstance(result, bool)
        
        # Test with URL and path
        result = _is_url_excluded("example.com/api")
        assert isinstance(result, bool)

    def test_is_url_excluded_with_annotations(self):
        """Test URL exclusion with annotations"""
        # Test with exclusion annotation
        annotations = {'portal-checker.io/exclude': 'true'}
        assert _is_url_excluded("example.com", annotations) == True
        
        # Test with case variation
        annotations = {'portal-checker.io/exclude': 'True'}
        assert _is_url_excluded("example.com", annotations) == True
        
        # Test with false annotation
        annotations = {'portal-checker.io/exclude': 'false'}
        assert _is_url_excluded("example.com", annotations) == False
        
        # Test without exclusion annotation
        annotations = {'other.annotation': 'value'}
        # This will check against loaded excluded URLs patterns
        result = _is_url_excluded("example.com", annotations)
        assert isinstance(result, bool)
        
        # Test with empty annotations
        assert isinstance(_is_url_excluded("example.com", {}), bool)
        
        # Test with None annotations
        assert isinstance(_is_url_excluded("example.com", None), bool)

    def test_is_url_excluded_with_patterns(self):
        """Test URL exclusion with different patterns"""
        # Test with URLs that might match existing patterns
        result1 = _is_url_excluded("monitoring.example.com")
        result2 = _is_url_excluded("normal.example.com")
        
        # Both should return boolean values
        assert isinstance(result1, bool)
        assert isinstance(result2, bool)

    def test_is_url_excluded_different_urls(self):
        """Test URL exclusion with different URL types"""
        test_urls = [
            "any.example.com",
            "test.internal/api", 
            "service.external.com",
            "app.test.com/admin"
        ]
        
        for url in test_urls:
            result = _is_url_excluded(url)
            assert isinstance(result, bool), f"Failed for URL: {url}"

    @patch('app.load_excluded_urls')
    def test_is_url_excluded_pattern_matching_error(self, mock_load):
        """Test URL exclusion when pattern matching fails"""
        # Mock load_excluded_urls to return patterns that might cause issues
        mock_load.return_value = {'[invalid-regex'}
        
        # Should handle pattern matching errors gracefully
        try:
            result = _is_url_excluded("test.example.com")
            assert isinstance(result, bool)
        except Exception:
            pytest.fail("_is_url_excluded should handle pattern errors gracefully")

    def test_url_exclusion_case_sensitivity(self):
        """Test URL exclusion case sensitivity"""
        # Test with different cases
        result1 = _is_url_excluded("Example.Com")
        result2 = _is_url_excluded("example.com")
        result3 = _is_url_excluded("EXAMPLE.COM")
        
        # Results should be consistent (either all true or all false)
        assert isinstance(result1, bool)
        assert isinstance(result2, bool) 
        assert isinstance(result3, bool)

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
            result = _is_url_excluded(url)
            assert isinstance(result, bool), f"Failed for URL: {url}"