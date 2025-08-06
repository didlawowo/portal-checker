import pytest
from unittest.mock import patch

from src.app import app


class TestIntegrationUI:
    """Tests d'intégration pour l'interface utilisateur"""

    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app"""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @patch("app.check_urls_async")
    def test_complete_ui_flow(self, mock_check_urls, client):
        """Test du flux complet de l'interface utilisateur"""
        # Simuler des données réalistes
        mock_check_urls.return_value = [
            {
                "url": "api.production.com/v1",
                "name": "api-service",
                "namespace": "production",
                "type": "HTTPRoute",
                "status": 200,
                "details": "",
                "response_time": 85,
                "annotations": {
                    "cert-manager.io/cluster-issuer": "letsencrypt-prod",
                    "ingress.kubernetes.io/ssl-redirect": "true",
                    "nginx.ingress.kubernetes.io/proxy-body-size": "10m",
                },
            },
            {
                "url": "app.staging.com",
                "name": "frontend-app",
                "namespace": "staging",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 120,
                "annotations": {
                    "nginx.ingress.kubernetes.io/cors-allow-origin": "*",
                },
            },
            {
                "url": "monitoring.internal.com/metrics",
                "name": "monitoring-service",
                "namespace": "monitoring",
                "type": "Ingress",
                "status": 401,
                "details": "",
                "response_time": 45,
                "annotations": {},  # Pas d'annotations
            },
            {
                "url": "broken.service.com",
                "name": "broken-service",
                "namespace": "default",
                "type": "HTTPRoute",
                "status": 500,
                "details": "❌ Internal Server Error",
                "response_time": 5000,
                "annotations": None,  # Annotations null
            },
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier la structure générale
        assert "<title>Portal Urls Checker</title>" in html_content
        assert "Portals Discovery" in html_content

        # Vérifier que toutes les URLs sont présentes
        assert "api.production.com/v1" in html_content
        assert "app.staging.com" in html_content
        assert "monitoring.internal.com/metrics" in html_content
        assert "broken.service.com" in html_content

        # Vérifier les types de services
        assert '"type": "HTTPRoute"' in html_content
        assert '"type": "Ingress"' in html_content

        # Vérifier les status codes
        assert '"status": 200' in html_content
        assert '"status": 401' in html_content
        assert '"status": 500' in html_content

        # Vérifier les temps de réponse (entiers)
        assert '"response_time": 85' in html_content
        assert '"response_time": 120' in html_content
        assert '"response_time": 45' in html_content
        assert '"response_time": 5000' in html_content

        # Vérifier que les annotations sont présentes dans les données
        assert "cert-manager.io/cluster-issuer" in html_content
        assert "nginx.ingress.kubernetes.io/cors-allow-origin" in html_content

        # Vérifier les fonctions JavaScript
        assert "formatAnnotations" in html_content
        assert "toggleAnnotations" in html_content
        assert "updateSortArrows" in html_content

        # Vérifier les styles CSS pour les annotations cliquables
        assert "annotations-preview" in html_content
        assert "cursor: pointer" in html_content
        assert "text-decoration: underline" in html_content

        # Vérifier qu'il n'y a plus de boutons toggle
        assert "toggle-btn" not in html_content
        assert "Afficher/Masquer" not in html_content

    @patch("app.check_urls_async")
    def test_ui_responsive_elements(self, mock_check_urls, client):
        """Test des éléments responsifs de l'interface"""
        mock_check_urls.return_value = [
            {
                "url": "responsive.test.com",
                "name": "responsive-service",
                "namespace": "test",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 100,
                "annotations": {"test": "annotation"},
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier les éléments responsifs
        assert 'meta name="viewport"' in html_content
        assert "width=device-width" in html_content

        # Vérifier les contrôles interactifs
        assert 'type="search"' in html_content
        assert 'id="searchInput"' in html_content
        assert 'placeholder="Rechercher..."' in html_content

        # Vérifier les boutons d'action
        assert "Refresh 🔄" in html_content
        assert "/refresh" in html_content

        # Vérifier les en-têtes de colonnes cliquables
        assert 'onclick="sortTable(' in html_content
        assert 'onclick="sortTable(\'url\')"' in html_content
        assert 'onclick="sortTable(\'status\')"' in html_content
        assert 'onclick="sortTable(\'response_time\')"' in html_content

    @patch("app.check_urls_async")
    def test_accessibility_features(self, mock_check_urls, client):
        """Test des fonctionnalités d'accessibilité"""
        mock_check_urls.return_value = [
            {
                "url": "accessible.test.com",
                "name": "accessible-service",
                "namespace": "test",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 150,
                "annotations": {"accessibility": "test"},
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier la langue
        assert 'lang="fr"' in html_content

        # Vérifier la structure sémantique
        assert "<table>" in html_content
        assert "<thead>" in html_content
        assert 'id="resultsTable"' in html_content  # tbody généré par JavaScript
        assert "<th>" in html_content

        # Vérifier que les liens sont accessibles
        assert 'target="_blank"' in html_content  # Les liens externes s'ouvrent dans un nouvel onglet

        # Vérifier que les éléments interactifs ont des indications visuelles
        assert "cursor: pointer" in html_content
        assert "text-decoration: underline" in html_content
        assert ":hover" in html_content

    @patch("app.check_urls_async")
    def test_performance_elements(self, mock_check_urls, client):
        """Test des éléments liés à la performance"""
        # Simuler de nombreux services pour tester la performance
        mock_data = []
        for i in range(50):
            mock_data.append(
                {
                    "url": f"service{i}.test.com",
                    "name": f"service-{i}",
                    "namespace": "test",
                    "type": "Ingress" if i % 2 == 0 else "HTTPRoute",
                    "status": 200 if i % 3 == 0 else 404,
                    "details": "",
                    "response_time": 50 + i * 10,
                    "annotations": {"index": str(i)} if i % 5 == 0 else {},
                }
            )

        mock_check_urls.return_value = mock_data

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier que toutes les données sont présentes
        assert "service0.test.com" in html_content
        assert "service49.test.com" in html_content

        # Vérifier que le JavaScript gère les grandes listes
        assert "initialData" in html_content
        assert "currentData" in html_content
        assert "renderTable" in html_content

        # Vérifier la fonctionnalité de recherche
        assert "handleSearch" in html_content
        assert "filter(item =>" in html_content