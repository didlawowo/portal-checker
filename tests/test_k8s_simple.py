import sys
import os
# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from unittest.mock import patch, MagicMock
import asyncio

from src.app import _get_http_routes, _get_all_urls_with_details, _reset_cache


class TestKubernetesSimple:
    """Simple Kubernetes tests with minimal mocking"""

    @patch('app._get_http_routes')
    def test_get_all_urls_with_details_with_mock_http_routes(self, mock_get_http_routes):
        """Test _get_all_urls_with_details with mocked HTTPRoutes"""
        # Reset cache before test
        _reset_cache()
        
        # Mock the HTTPRoute data in the expected format
        mock_get_http_routes.return_value = [
            {
                'hostname': 'api.example.com',
                'paths': [{'type': 'PathPrefix', 'value': '/v1'}],
                'name': 'api-route',
                'namespace': 'default',
                'annotations': {}
            }
        ]
        
        # Mock the Ingress discovery to avoid K8s API calls
        with patch('app.client.NetworkingV1Api') as mock_networking_api:
            mock_api_instance = MagicMock()
            mock_networking_api.return_value = mock_api_instance
            
            # Mock empty Ingress list
            mock_ingress_list = MagicMock()
            mock_ingress_list.items = []
            mock_api_instance.list_ingress_for_all_namespaces.return_value = mock_ingress_list
            
            # Test the function
            result = _get_all_urls_with_details()
            
            # Verify results
            assert len(result) == 1
            assert result[0]['url'] == 'api.example.com/v1'
            assert result[0]['name'] == 'api-route'
            assert result[0]['namespace'] == 'default'
            assert result[0]['type'] == 'HTTPRoute'
            
            # Verify mocked function was called
            mock_get_http_routes.assert_called_once()

    @patch('app._get_http_routes')
    def test_get_all_urls_with_details_excludes_annotated(self, mock_get_http_routes):
        """Test that URLs with exclusion annotations are filtered out"""
        # Reset cache before test
        _reset_cache()
        
        # Mock HTTPRoute with exclusion annotation
        mock_get_http_routes.return_value = [
            {
                'hostname': 'excluded.example.com',
                'paths': [{'type': 'PathPrefix', 'value': '/'}],
                'name': 'excluded-route',
                'namespace': 'default',
                'annotations': {'portal-checker.io/exclude': 'true'}
            }
        ]
        
        # Mock Ingress discovery
        with patch('app.client.NetworkingV1Api') as mock_networking_api:
            mock_api_instance = MagicMock()
            mock_networking_api.return_value = mock_api_instance
            mock_ingress_list = MagicMock()
            mock_ingress_list.items = []
            mock_api_instance.list_ingress_for_all_namespaces.return_value = mock_ingress_list
            
            # Test the function
            result = _get_all_urls_with_details()
            
            # Should return empty list due to exclusion
            assert result == []

    @patch('app._get_http_routes')
    def test_get_all_urls_with_details_multiple_paths(self, mock_get_http_routes):
        """Test HTTPRoute with multiple paths"""
        # Reset cache before test
        _reset_cache()
        
        # Mock HTTPRoute with multiple paths
        mock_get_http_routes.return_value = [
            {
                'hostname': 'multi.example.com',
                'paths': [
                    {'type': 'PathPrefix', 'value': '/api'},
                    {'type': 'PathPrefix', 'value': '/web'}
                ],
                'name': 'multi-route',
                'namespace': 'default',
                'annotations': {}
            }
        ]
        
        # Mock Ingress discovery
        with patch('app.client.NetworkingV1Api') as mock_networking_api:
            mock_api_instance = MagicMock()
            mock_networking_api.return_value = mock_api_instance
            mock_ingress_list = MagicMock()
            mock_ingress_list.items = []
            mock_api_instance.list_ingress_for_all_namespaces.return_value = mock_ingress_list
            
            # Test the function
            result = _get_all_urls_with_details()
            
            # Should create 2 URLs for the 2 paths
            assert len(result) == 2
            urls = [item['url'] for item in result]
            assert 'multi.example.com/api' in urls
            assert 'multi.example.com/web' in urls

    @patch('app._get_http_routes')
    def test_get_all_urls_with_details_ingress_and_httproute(self, mock_get_http_routes):
        """Test combining HTTPRoute and Ingress results"""
        # Reset cache before test
        _reset_cache()
        
        # Mock HTTPRoute
        mock_get_http_routes.return_value = [
            {
                'hostname': 'api.example.com',
                'paths': [{'type': 'PathPrefix', 'value': '/api'}],
                'name': 'api-route',
                'namespace': 'default',
                'annotations': {}
            }
        ]
        
        # Mock Ingress discovery
        with patch('app.client.NetworkingV1Api') as mock_networking_api:
            mock_api_instance = MagicMock()
            mock_networking_api.return_value = mock_api_instance
            
            # Mock Ingress list with one item
            mock_ingress = MagicMock()
            mock_ingress.metadata.name = 'web-ingress'
            mock_ingress.metadata.namespace = 'production'
            mock_ingress.metadata.annotations = {}
            
            # Mock Ingress spec
            mock_rule = MagicMock()
            mock_rule.host = 'web.example.com'
            mock_path = MagicMock()
            mock_path.path = '/app'
            mock_rule.http.paths = [mock_path]
            mock_ingress.spec.rules = [mock_rule]
            
            mock_ingress_list = MagicMock()
            mock_ingress_list.items = [mock_ingress]
            mock_api_instance.list_ingress_for_all_namespaces.return_value = mock_ingress_list
            
            # Test the function
            result = _get_all_urls_with_details()
            
            # Should have both HTTPRoute and Ingress results
            assert len(result) == 2
            
            # Check HTTPRoute result
            httproute_result = next(item for item in result if item['type'] == 'HTTPRoute')
            assert httproute_result['url'] == 'api.example.com/api'
            assert httproute_result['name'] == 'api-route'
            
            # Check Ingress result
            ingress_result = next(item for item in result if item['type'] == 'Ingress')
            assert ingress_result['url'] == 'web.example.com/app'
            assert ingress_result['name'] == 'web-ingress'
            assert ingress_result['namespace'] == 'production'

    @patch('app._get_http_routes')
    def test_get_all_urls_with_details_http_routes_exception(self, mock_get_http_routes):
        """Test handling HTTPRoute exceptions"""
        # Reset cache before test
        _reset_cache()
        
        # Mock HTTPRoute to raise exception
        mock_get_http_routes.side_effect = Exception("HTTPRoute API error")
        
        # Mock Ingress discovery
        with patch('app.client.NetworkingV1Api') as mock_networking_api:
            mock_api_instance = MagicMock()
            mock_networking_api.return_value = mock_api_instance
            mock_ingress_list = MagicMock()
            mock_ingress_list.items = []
            mock_api_instance.list_ingress_for_all_namespaces.return_value = mock_ingress_list
            
            # Test the function handles exception gracefully
            result = _get_all_urls_with_details()
            
            # Should return empty list from Ingress only (HTTPRoute failed)
            assert result == []

    @patch('app._is_url_excluded')
    @patch('app._get_http_routes')
    def test_get_all_urls_with_details_url_exclusion(self, mock_get_http_routes, mock_is_url_excluded):
        """Test URL exclusion logic"""
        # Reset cache before test
        _reset_cache()
        
        # Mock HTTPRoute
        mock_get_http_routes.return_value = [
            {
                'hostname': 'test.example.com',
                'paths': [{'type': 'PathPrefix', 'value': '/'}],
                'name': 'test-route',
                'namespace': 'default',
                'annotations': {}
            }
        ]
        
        # Mock URL exclusion to return True (exclude this URL)
        mock_is_url_excluded.return_value = True
        
        # Mock Ingress discovery
        with patch('app.client.NetworkingV1Api') as mock_networking_api:
            mock_api_instance = MagicMock()
            mock_networking_api.return_value = mock_api_instance
            mock_ingress_list = MagicMock()
            mock_ingress_list.items = []
            mock_api_instance.list_ingress_for_all_namespaces.return_value = mock_ingress_list
            
            # Test the function
            result = _get_all_urls_with_details()
            
            # Should return empty list due to URL exclusion
            assert result == []
            
            # Verify exclusion check was called
            mock_is_url_excluded.assert_called()