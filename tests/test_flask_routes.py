import sys
import os
# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock

from src.api import app


class TestFlaskRoutes:
    """Test Flask routes and endpoints"""

    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_health_endpoint(self, client):
        """Test the health endpoint"""
        response = client.get('/health')
        assert response.status_code == 200

        data = response.get_json()
        assert 'status' in data
        assert data['status'] == 'ok'

    def test_api_urls_endpoint(self, client):
        """Test /api/urls endpoint returns JSON with cache data"""
        response = client.get('/api/urls')
        assert response.status_code == 200

        data = response.get_json()
        assert 'results' in data
        assert 'total' in data
        assert 'last_updated' in data
        assert isinstance(data['results'], list)
        assert isinstance(data['total'], int)

    def test_api_swagger_endpoint(self, client):
        """Test /api/swagger endpoint returns JSON with swagger data"""
        response = client.get('/api/swagger')
        assert response.status_code == 200

        data = response.get_json()
        assert 'results' in data
        assert 'total' in data
        assert 'last_updated' in data
        assert isinstance(data['results'], list)

    def test_api_excluded_urls_endpoint(self, client):
        """Test /api/excluded-urls endpoint"""
        response = client.get('/api/excluded-urls')
        assert response.status_code == 200

        data = response.get_json()
        assert 'excluded_urls' in data
        assert 'count' in data
        assert 'status' in data
        assert isinstance(data['excluded_urls'], list)
        assert data['status'] == 'ok'

    def test_favicon_endpoint(self, client):
        """Test favicon endpoint"""
        response = client.get('/static/favicon.ico')
        # Should attempt to serve favicon (might be 404 if file doesn't exist)
        assert response.status_code in [200, 404]

    def test_static_file_security(self, client):
        """Test that static file access is restricted"""
        response = client.get('/static/../secret.txt')
        # Should not allow directory traversal
        assert response.status_code in [400, 404]

    @patch('src.api.get_app_version')
    @patch('src.api._test_results_cache')
    def test_index_route_basic(self, mock_cache, mock_version, client):
        """Test main index route renders"""
        mock_version.return_value = "3.0.7"
        mock_cache.__getitem__.side_effect = lambda x: {
            "results": [],
            "last_updated": None
        }[x]

        response = client.get('/')
        assert response.status_code == 200
        # Should return HTML
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data

    @patch('src.api.get_all_urls_with_details')
    @patch('src.api.save_urls_to_file')
    @patch('src.api.asyncio.run')
    def test_refresh_endpoint_redirect(self, mock_run, mock_save, mock_get_urls, client):
        """Test /refresh endpoint redirects to home"""
        mock_get_urls.return_value = []
        mock_run.return_value = None

        response = client.get('/refresh', follow_redirects=False)
        # Should redirect to home page
        assert response.status_code in [302, 200]  # 302 redirect or 200 if followed

    @patch('src.api.get_all_urls_with_details')
    @patch('src.api.save_urls_to_file')
    def test_refresh_endpoint_discovers_urls(self, mock_save, mock_get_urls, client):
        """Test /refresh endpoint discovers URLs from Kubernetes"""
        mock_get_urls.return_value = [
            {
                "url": "example.com",
                "namespace": "default",
                "name": "test-service",
                "type": "Ingress"
            }
        ]

        response = client.get('/refresh', follow_redirects=False)
        # Should call discovery functions
        mock_get_urls.assert_called_once()

    def test_exclude_url_endpoint(self, client):
        """Test /api/exclude endpoint adds URL to exclusion list"""
        import tempfile
        import yaml

        # Create temp excluded URLs file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(["existing.com"], f)
            temp_file = f.name

        try:
            # Patch EXCLUDED_URLS_FILE from kubernetes_client where it's imported
            with patch('src.kubernetes_client.EXCLUDED_URLS_FILE', temp_file):
                response = client.post('/api/exclude', json={"url": "https://new.example.com/path"})

                assert response.status_code == 200
                data = response.get_json()
                assert data['status'] == 'ok'

                # Verify URL was added
                with open(temp_file, 'r') as f:
                    excluded = yaml.safe_load(f)
                    assert "new.example.com/path" in excluded
                    assert "existing.com" in excluded
        finally:
            import os
            os.unlink(temp_file)

    def test_exclude_url_endpoint_no_url(self, client):
        """Test /api/exclude endpoint returns error when URL missing"""
        response = client.post('/api/exclude', json={})

        assert response.status_code == 400
        data = response.get_json()
        assert data['status'] == 'error'
        assert 'URL required' in data['error']

    def test_refresh_async_endpoint(self, client):
        """Test /api/refresh-async endpoint"""
        response = client.post('/api/refresh-async')

        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'
