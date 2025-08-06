import pytest
from unittest.mock import patch

from src.app import app


class TestVisualValidation:
    """Tests de validation visuelle pour l'interface utilisateur"""

    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app"""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @patch("app.check_urls_async")
    def test_annotations_button_style_visual(self, mock_check_urls, client):
        """Test visuel du style des boutons d'annotations"""
        mock_check_urls.return_value = [
            {
                "url": "service-with-many-annotations.com",
                "name": "complex-service",
                "namespace": "production",
                "type": "HTTPRoute",
                "status": 200,
                "details": "",
                "response_time": 95,
                "annotations": {
                    "cert-manager.io/cluster-issuer": "letsencrypt-prod",
                    "ingress.kubernetes.io/ssl-redirect": "true",
                    "nginx.ingress.kubernetes.io/proxy-body-size": "10m",
                    "nginx.ingress.kubernetes.io/cors-allow-origin": "*",
                    "kubernetes.io/ingress.class": "nginx",
                    "meta.helm.sh/release-name": "my-release",
                    "meta.helm.sh/release-namespace": "production",
                },
            },
            {
                "url": "service-with-one-annotation.com",
                "name": "simple-service",
                "namespace": "staging",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 150,
                "annotations": {
                    "cert-manager.io/cluster-issuer": "letsencrypt-staging",
                },
            },
            {
                "url": "service-without-annotations.com",
                "name": "basic-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 75,
                "annotations": {},
            },
            {
                "url": "service-null-annotations.com",
                "name": "null-service",
                "namespace": "test",
                "type": "HTTPRoute",
                "status": 404,
                "details": "❓ Not Found",
                "response_time": 2000,
                "annotations": None,
            },
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier la présence du style bouton pour annotations-preview
        assert "background: #4b5563;" in html_content
        assert "color: white;" in html_content
        assert "padding: 4px 8px;" in html_content
        assert "border-radius: 4px;" in html_content
        assert "display: inline-block;" in html_content

        # Vérifier l'effet hover
        assert "background: #374151;" in html_content

        # Vérifier que les données sont correctement formatées pour JavaScript
        annotations_data_points = [
            '"cert-manager.io/cluster-issuer": "letsencrypt-prod"',
            '"nginx.ingress.kubernetes.io/proxy-body-size": "10m"',
            '"cert-manager.io/cluster-issuer": "letsencrypt-staging"',
        ]

        for data_point in annotations_data_points:
            assert data_point in html_content

        # Vérifier que les services sans annotations ont des objets vides
        assert '"annotations": {}' in html_content
        assert '"annotations": null' in html_content

    @patch("app.check_urls_async")
    def test_ui_layout_consistency(self, mock_check_urls, client):
        """Test de la cohérence de la mise en page"""
        mock_check_urls.return_value = [
            {
                "url": "layout-test.com",
                "name": "layout-service",
                "namespace": "ui-test",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 125,
                "annotations": {
                    "ui-test": "value",
                    "layout": "test",
                },
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier la structure de la table
        assert "<table>" in html_content
        assert "<thead>" in html_content
        assert 'id="resultsTable"' in html_content  # tbody est généré par JavaScript

        # Vérifier les en-têtes de colonnes
        expected_headers = [
            "Namespace",
            "Name",
            "Type",
            "Annotations",
            "URL",
            "Status",
            "Time (ms)",
            "Details",
        ]

        for header in expected_headers:
            assert f"<th" in html_content and header in html_content

        # Vérifier que les colonnes sont triables
        sortable_columns = ["url", "status", "response_time"]
        for column in sortable_columns:
            assert f'onclick="sortTable(\'{column}\')"' in html_content

        # Vérifier la présence des icônes de tri
        assert "urlSort" in html_content
        assert "statusSort" in html_content
        assert "response_timeSort" in html_content

    @patch("app.check_urls_async")
    def test_color_scheme_consistency(self, mock_check_urls, client):
        """Test de la cohérence du schéma de couleurs"""
        mock_check_urls.return_value = [
            {
                "url": "color-test-200.com",
                "name": "success-service",
                "namespace": "test",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 100,
                "annotations": {"status": "success"},
            },
            {
                "url": "color-test-401.com",
                "name": "auth-service",
                "namespace": "test",
                "type": "HTTPRoute",
                "status": 401,
                "details": "",
                "response_time": 50,
                "annotations": {"status": "auth"},
            },
            {
                "url": "color-test-500.com",
                "name": "error-service",
                "namespace": "test",
                "type": "Ingress",
                "status": 500,
                "details": "❌ Internal Server Error",
                "response_time": 5000,
                "annotations": {"status": "error"},
            },
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier les classes de status
        assert "status-200" in html_content  # Vert pour succès
        assert "status-401" in html_content  # Jaune pour auth
        assert "status-error" in html_content  # Rouge pour erreur

        # Vérifier les couleurs du schéma
        color_definitions = [
            "#dcfce7",  # Vert clair pour 200
            "#166534",  # Vert foncé pour 200
            "#fef9c3",  # Jaune clair pour 401
            "#854d0e",  # Jaune foncé pour 401
            "#fee2e2",  # Rouge clair pour erreur
            "#991b1b",  # Rouge foncé pour erreur
        ]

        for color in color_definitions:
            assert color in html_content

        # Vérifier le style des boutons annotations (gris)
        assert "#4b5563" in html_content  # Gris pour bouton
        assert "#374151" in html_content  # Gris foncé pour hover

    @patch("app.check_urls_async")
    def test_responsive_design_elements(self, mock_check_urls, client):
        """Test des éléments de design responsive"""
        mock_check_urls.return_value = [
            {
                "url": "responsive.test.com",
                "name": "responsive-service",
                "namespace": "responsive",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 120,
                "annotations": {"responsive": "design"},
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier les meta tags responsive
        assert 'name="viewport"' in html_content
        assert "width=device-width" in html_content
        assert "initial-scale=1.0" in html_content

        # Vérifier les largeurs des colonnes
        assert 'style="width: 400px;"' in html_content  # URL column
        assert 'style="width: 100px;"' in html_content  # Status et Time columns

        # Vérifier les styles de conteneur
        assert "max-width: 1200px;" in html_content
        assert "margin: 0 auto;" in html_content

        # Vérifier les styles de recherche
        assert 'type="search"' in html_content
        assert "flex: 1;" in html_content  # Search input flexible

    @patch("app.check_urls_async")
    def test_accessibility_compliance(self, mock_check_urls, client):
        """Test de conformité d'accessibilité"""
        mock_check_urls.return_value = [
            {
                "url": "accessible.test.com",
                "name": "accessible-service",
                "namespace": "accessibility",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 90,
                "annotations": {"accessibility": "compliant"},
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier la langue
        assert 'lang="fr"' in html_content

        # Vérifier les contrastes suffisants
        # Les annotations en blanc sur gris foncé (#4b5563) ont un bon contraste
        assert "color: white;" in html_content
        assert "background: #4b5563;" in html_content

        # Vérifier que les éléments interactifs ont des indications visuelles
        assert "cursor: pointer;" in html_content
        assert ":hover" in html_content

        # Vérifier que les liens externes sont identifiés
        assert 'target="_blank"' in html_content

        # Vérifier la structure sémantique
        # tbody et td sont générés par JavaScript, donc on vérifie les éléments statiques
        static_semantic_elements = ["<table>", "<thead>", "<th>"]
        for element in static_semantic_elements:
            assert element in html_content
        
        # Vérifier que JavaScript génère les éléments dynamiques
        assert 'tr.innerHTML' in html_content
        assert 'appendChild(tr)' in html_content