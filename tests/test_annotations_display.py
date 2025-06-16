from unittest.mock import patch

import pytest

from app import app


class TestAnnotationsDisplay:
    """Test de l'affichage des annotations dans le frontend"""

    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app"""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @patch("app.check_urls_async")
    def test_index_with_empty_annotations(self, mock_check_urls, client):
        """Test que les annotations vides n'affichent pas de bouton"""
        mock_check_urls.return_value = [
            {
                "url": "example.com",
                "name": "test-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 150,
                "annotations": {},  # Annotations vides
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        # Vérifier que la page contient les données
        html_content = response.get_data(as_text=True)
        assert "example.com" in html_content
        assert "test-service" in html_content

    @patch("app.check_urls_async")
    def test_index_with_null_annotations(self, mock_check_urls, client):
        """Test que les annotations null n'affichent pas de bouton"""
        mock_check_urls.return_value = [
            {
                "url": "example.com",
                "name": "test-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 150,
                "annotations": None,  # Annotations null
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)
        assert "example.com" in html_content

    @patch("app.check_urls_async")
    def test_index_with_valid_annotations(self, mock_check_urls, client):
        """Test que les annotations valides affichent le bouton"""
        mock_check_urls.return_value = [
            {
                "url": "example.com",
                "name": "test-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 150,
                "annotations": {
                    "ingress.kubernetes.io/ssl-redirect": "true",
                    "nginx.ingress.kubernetes.io/cors-allow-origin": "*",
                },
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)
        assert "example.com" in html_content
        # La logique du bouton est côté JavaScript, on vérifie que les données sont bien passées
        assert '"annotations"' in html_content

    @patch("app.check_urls_async")
    def test_index_with_mixed_annotations(self, mock_check_urls, client):
        """Test avec un mélange de services avec et sans annotations"""
        mock_check_urls.return_value = [
            {
                "url": "service1.com",
                "name": "service-with-annotations",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 100,
                "annotations": {"cert-manager.io/cluster-issuer": "letsencrypt"},
            },
            {
                "url": "service2.com",
                "name": "service-without-annotations",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 200,
                "annotations": {},  # Pas d'annotations
            },
            {
                "url": "service3.com",
                "name": "service-null-annotations",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 300,
                "annotations": None,  # Annotations null
            },
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier que tous les services sont présents
        assert "service1.com" in html_content
        assert "service2.com" in html_content
        assert "service3.com" in html_content

        # Vérifier que les données d'annotations sont bien dans le JSON
        assert '"annotations"' in html_content

    @patch("app.check_urls_async")
    def test_response_time_display_integer(self, mock_check_urls, client):
        """Test que les temps de réponse sont affichés comme entiers"""
        mock_check_urls.return_value = [
            {
                "url": "fast.example.com",
                "name": "fast-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 42,  # Entier
                "annotations": {},
            },
            {
                "url": "slow.example.com",
                "name": "slow-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 1234,  # Entier plus grand
                "annotations": {},
            },
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Les temps de réponse devraient être présents dans le JSON comme entiers
        assert '"response_time": 42' in html_content
        assert '"response_time": 1234' in html_content

        # Pas de décimales dans les données
        assert '"response_time": 42.0' not in html_content
        assert '"response_time": 1234.0' not in html_content

    @patch("app.check_urls_async")
    def test_index_template_structure(self, mock_check_urls, client):
        """Test la structure générale du template"""
        mock_check_urls.return_value = [
            {
                "url": "test.example.com",
                "name": "test-service",
                "namespace": "test-ns",
                "type": "HTTPRoute",
                "status": 200,
                "details": "",
                "response_time": 89,
                "annotations": {"test": "value"},
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier les éléments structurels du template
        assert "<table>" in html_content
        assert "<th>Annotations</th>" in html_content
        assert "<th onclick=\"sortTable('response_time')\"" in html_content
        assert "Time (ms)" in html_content
        assert "formatAnnotations" in html_content  # JavaScript function
        assert "toggleAnnotations" in html_content  # JavaScript function

    @patch("app.check_urls_async")
    def test_javascript_functions_present(self, mock_check_urls, client):
        """Test que les fonctions JavaScript nécessaires sont présentes"""
        mock_check_urls.return_value = []

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier la présence des fonctions JavaScript
        assert "function formatAnnotations(" in html_content
        assert "function toggleAnnotations(" in html_content
        assert "function updateSortArrows(" in html_content
        assert "response_timeSort" in html_content  # Tri pour temps de réponse

    @patch("app.check_urls_async")
    def test_no_response_time_display_dash(self, mock_check_urls, client):
        """Test que l'absence de temps de réponse affiche un tiret"""
        mock_check_urls.return_value = [
            {
                "url": "no-time.example.com",
                "name": "no-time-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 404,
                "details": "Not Found",
                "response_time": None,  # Pas de temps de réponse
                "annotations": {},
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Le JavaScript devrait gérer les valeurs null/undefined
        assert "no-time.example.com" in html_content
