import sys
import os
# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from unittest.mock import patch

from src.app import app


class TestAnnotationsUIImprovements:
    """Test des améliorations de l'interface utilisateur pour les annotations"""

    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app"""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    @patch("app.check_urls_async")
    def test_no_toggle_button_in_html(self, mock_check_urls, client):
        """Test qu'il n'y a plus de bouton Afficher/Masquer dans le HTML"""
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

        # Vérifier qu'il n'y a plus de bouton "Afficher/Masquer"
        assert "Afficher/Masquer" not in html_content
        assert "toggle-btn" not in html_content

        # Vérifier que les fonctions JavaScript sont toujours présentes
        assert "toggleAnnotations" in html_content
        assert "formatAnnotations" in html_content

    @patch("app.check_urls_async")
    def test_annotations_preview_clickable(self, mock_check_urls, client):
        """Test que le texte du nombre d'annotations est cliquable"""
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
                    "cert-manager.io/cluster-issuer": "letsencrypt",
                    "ingress.kubernetes.io/ssl-redirect": "true",
                    "nginx.ingress.kubernetes.io/proxy-body-size": "10m",
                },
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier que la classe annotations-preview est présente
        assert "annotations-preview" in html_content
        # Vérifier que le onclick est sur la preview et non sur un bouton
        assert 'onclick="toggleAnnotations(' in html_content

    @patch("app.check_urls_async")
    def test_css_styles_for_clickable_annotations(self, mock_check_urls, client):
        """Test que les styles CSS pour les annotations cliquables sont présents"""
        mock_check_urls.return_value = []

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier la présence des styles CSS pour annotations-preview (style bouton)
        assert ".annotations-preview {" in html_content
        assert "background: #4b5563;" in html_content
        assert "color: white;" in html_content
        assert "padding: 4px 8px;" in html_content
        assert "border-radius: 4px;" in html_content
        assert "cursor: pointer;" in html_content

        # Vérifier la présence du style hover
        assert ".annotations-preview:hover {" in html_content
        assert "background: #374151;" in html_content

        # Vérifier que les anciens styles du bouton ne sont plus présents
        assert ".toggle-btn {" not in html_content

    @patch("app.check_urls_async")
    def test_singular_plural_annotations_text(self, mock_check_urls, client):
        """Test l'affichage singulier/pluriel du nombre d'annotations"""
        mock_check_urls.return_value = [
            {
                "url": "single.example.com",
                "name": "single-annotation-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 100,
                "annotations": {"single": "annotation"},  # 1 annotation
            },
            {
                "url": "multiple.example.com",
                "name": "multiple-annotations-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 200,
                "annotations": {  # 3 annotations
                    "first": "value1",
                    "second": "value2",
                    "third": "value3",
                },
            },
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Les textes singulier/pluriel sont générés côté JavaScript
        # On vérifie que la logique est présente dans le JS
        assert "annotation${annotationKeys.length > 1 ? 's' : ''}" in html_content

    @patch("app.check_urls_async")
    def test_no_annotations_shows_dash(self, mock_check_urls, client):
        """Test que l'absence d'annotations affiche un tiret"""
        mock_check_urls.return_value = [
            {
                "url": "no-annotations.example.com",
                "name": "no-annotations-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 150,
                "annotations": {},  # Pas d'annotations
            },
            {
                "url": "null-annotations.example.com",
                "name": "null-annotations-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 150,
                "annotations": None,  # Annotations null
            },
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier que la logique pour afficher "-" est présente
        assert 'if (!annotations) return \'-\';' in html_content
        assert 'if (annotationKeys.length === 0) {' in html_content
        assert 'return \'-\';' in html_content

    @patch("app.check_urls_async")
    def test_javascript_functions_structure(self, mock_check_urls, client):
        """Test la structure des fonctions JavaScript"""
        mock_check_urls.return_value = [
            {
                "url": "test.example.com",
                "name": "test-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 150,
                "annotations": {"test": "annotation"},
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier que les fonctions JavaScript essentielles sont présentes
        assert "function formatAnnotations(annotations)" in html_content
        assert "function toggleAnnotations(id)" in html_content

        # Vérifier que la logique de toggle est correcte
        assert "if (content.style.display === 'none')" in html_content
        assert "content.style.display = 'block';" in html_content
        assert "content.style.display = 'none';" in html_content

    @patch("app.check_urls_async")
    def test_ui_consistency(self, mock_check_urls, client):
        """Test la cohérence de l'interface utilisateur"""
        mock_check_urls.return_value = [
            {
                "url": "test.example.com",
                "name": "test-service",
                "namespace": "default",
                "type": "Ingress",
                "status": 200,
                "details": "",
                "response_time": 150,
                "annotations": {"example": "annotation"},
            }
        ]

        response = client.get("/")
        assert response.status_code == 200

        html_content = response.get_data(as_text=True)

        # Vérifier que l'en-tête de colonne Annotations est toujours présent
        assert "<th>Annotations</th>" in html_content

        # Vérifier que les autres éléments de l'interface sont cohérents
        assert "Time (ms)" in html_content
        assert "response_timeSort" in html_content

        # Vérifier qu'il n'y a pas de références aux anciens boutons
        assert "toggle-btn" not in html_content
        # Le style background: #4b5563 est maintenant utilisé pour annotations-preview, donc on ne peut plus le tester ainsi