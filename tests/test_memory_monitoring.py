import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from app import app, _deduplicate_urls, _extract_essential_annotations, _is_cache_valid, _update_cache, _get_cached_urls, _kubernetes_cache, _reset_cache


class TestMemoryMonitoring:
    """Tests pour le monitoring mémoire et l'optimisation"""

    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app"""
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_memory_endpoint_success(self, client):
        """Test que l'endpoint /memory retourne les informations mémoire"""
        with patch("psutil.Process") as mock_process:
            # Mock du processus psutil
            mock_memory_info = MagicMock()
            mock_memory_info.rss = 104857600  # 100MB in bytes
            mock_memory_info.vms = 209715200  # 200MB in bytes
            
            mock_process_instance = MagicMock()
            mock_process_instance.memory_info.return_value = mock_memory_info
            mock_process_instance.memory_percent.return_value = 15.5
            mock_process.return_value = mock_process_instance

            response = client.get("/memory")
            assert response.status_code == 200
            
            data = response.get_json()
            assert "memory_rss_mb" in data
            assert "memory_vms_mb" in data
            assert "memory_percent" in data
            assert "status" in data
            
            # Vérifier les valeurs calculées
            assert data["memory_rss_mb"] == 100.0  # 104857600 / 1024 / 1024
            assert data["memory_vms_mb"] == 200.0  # 209715200 / 1024 / 1024
            assert data["memory_percent"] == 15.5
            assert data["status"] == "ok"

    def test_memory_endpoint_psutil_not_available(self, client):
        """Test l'endpoint /memory quand psutil n'est pas disponible"""
        with patch("builtins.__import__", side_effect=ImportError("psutil not found")):
            response = client.get("/memory")
            assert response.status_code == 500
            
            data = response.get_json()
            assert "error" in data
            assert "psutil not available" in data["error"]

    def test_deduplicate_urls_removes_duplicates(self):
        """Test que la déduplication supprime les URLs dupliquées"""
        url_details = [
            {
                "url": "example.com/api",
                "namespace": "production",
                "name": "api-service",
                "type": "HTTPRoute",
                "status": "active"
            },
            {
                "url": "example.com/api",  # Duplicate
                "namespace": "production",
                "name": "api-service",
                "type": "Ingress",
                "status": "active"
            },
            {
                "url": "another.com/web",
                "namespace": "staging",
                "name": "web-service",
                "type": "HTTPRoute",
                "status": "active"
            },
            {
                "url": "example.com/api",  # Another duplicate
                "namespace": "production", 
                "name": "api-service",
                "type": "HTTPRoute",
                "status": "pending"
            }
        ]

        unique_urls = _deduplicate_urls(url_details)
        
        # Devrait garder seulement 2 URLs uniques
        assert len(unique_urls) == 2
        
        # Vérifier que les URLs restantes sont les bonnes
        urls_set = {(url["url"], url["namespace"], url["name"]) for url in unique_urls}
        expected_set = {
            ("example.com/api", "production", "api-service"),
            ("another.com/web", "staging", "web-service")
        }
        assert urls_set == expected_set

    def test_deduplicate_urls_empty_list(self):
        """Test la déduplication avec une liste vide"""
        result = _deduplicate_urls([])
        assert result == []

    def test_deduplicate_urls_no_duplicates(self):
        """Test la déduplication quand il n'y a pas de doublons"""
        url_details = [
            {
                "url": "api.example.com",
                "namespace": "prod",
                "name": "api",
                "type": "HTTPRoute"
            },
            {
                "url": "web.example.com", 
                "namespace": "prod",
                "name": "web",
                "type": "Ingress"
            }
        ]

        unique_urls = _deduplicate_urls(url_details)
        assert len(unique_urls) == 2
        assert unique_urls == url_details  # Pas de changement

    def test_deduplicate_urls_different_namespaces(self):
        """Test que les URLs identiques dans différents namespaces sont gardées"""
        url_details = [
            {
                "url": "app.example.com",
                "namespace": "production",
                "name": "app-service",
                "type": "HTTPRoute"
            },
            {
                "url": "app.example.com",  # Same URL but different namespace
                "namespace": "staging",
                "name": "app-service",
                "type": "HTTPRoute"
            }
        ]

        unique_urls = _deduplicate_urls(url_details)
        assert len(unique_urls) == 2  # Both should be kept
        
        namespaces = {url["namespace"] for url in unique_urls}
        assert namespaces == {"production", "staging"}

    def test_deduplicate_urls_missing_fields(self):
        """Test la déduplication avec des champs manquants"""
        url_details = [
            {
                "url": "test.com",
                "namespace": "default",
                # Missing "name"
                "type": "HTTPRoute"
            },
            {
                "url": "test.com",
                "namespace": "default",
                "name": "",  # Empty name
                "type": "Ingress"
            }
        ]

        unique_urls = _deduplicate_urls(url_details)
        # Ces deux URLs sont considérées comme identiques car 
        # get() retourne "" pour les clés manquantes et les valeurs vides
        assert len(unique_urls) == 1

    @patch("app.logger")
    def test_deduplicate_urls_logs_duplicates(self, mock_logger):
        """Test que la déduplication log les doublons trouvés"""
        url_details = [
            {"url": "dup.com", "namespace": "ns", "name": "svc"},
            {"url": "dup.com", "namespace": "ns", "name": "svc"},  # Duplicate
            {"url": "unique.com", "namespace": "ns", "name": "svc2"}
        ]

        _deduplicate_urls(url_details)
        
        # Vérifier que le log info a été appelé pour signaler la suppression
        mock_logger.info.assert_called_with("🔄 1 URLs dupliquées supprimées")
        
        # Vérifier que le log debug a été appelé pour chaque duplicate
        mock_logger.debug.assert_called_with("🔄 URL dupliquée ignorée: dup.com")

    def test_extract_essential_annotations_empty(self):
        """Test l'extraction d'annotations avec un dictionnaire vide"""
        result = _extract_essential_annotations({})
        assert result == {}
        
        result = _extract_essential_annotations(None)
        assert result == {}

    def test_extract_essential_annotations_essential_keys(self):
        """Test que les annotations essentielles sont gardées"""
        annotations = {
            'portal-checker.io/exclude': 'true',
            'cert-manager.io/cluster-issuer': 'letsencrypt-prod',
            'ingress.kubernetes.io/ssl-redirect': 'true',
            'some.other.annotation': 'value',
            'nginx.ingress.kubernetes.io/cors-allow-origin': '*'
        }
        
        result = _extract_essential_annotations(annotations)
        
        # Les annotations essentielles doivent être gardées
        assert 'portal-checker.io/exclude' in result
        assert 'cert-manager.io/cluster-issuer' in result
        assert 'ingress.kubernetes.io/ssl-redirect' in result
        assert 'nginx.ingress.kubernetes.io/cors-allow-origin' in result
        
        # Les autres annotations courtes sont aussi gardées
        assert 'some.other.annotation' in result

    def test_extract_essential_annotations_filters_long_values(self):
        """Test que les annotations avec des valeurs longues sont filtrées"""
        annotations = {
            'short.annotation': 'short value',
            'long.annotation': 'x' * 100,  # 100 caractères, > 50
            'cert-manager.io/cluster-issuer': 'x' * 100,  # Essentielle mais longue
        }
        
        result = _extract_essential_annotations(annotations)
        
        # L'annotation courte doit être gardée
        assert 'short.annotation' in result
        
        # L'annotation longue normale doit être filtrée
        assert 'long.annotation' not in result
        
        # L'annotation essentielle doit être gardée même si longue
        assert 'cert-manager.io/cluster-issuer' in result

    def test_extract_essential_annotations_limits_count(self):
        """Test que le nombre d'annotations est limité à 10"""
        annotations = {f'annotation{i}': f'value{i}' for i in range(20)}
        
        result = _extract_essential_annotations(annotations)
        
        # Doit être limité à 10 annotations maximum
        assert len(result) == 10

    def test_extract_essential_annotations_preserves_essential_over_limit(self):
        """Test que les annotations essentielles sont gardées même avec la limite"""
        annotations = {f'annotation{i}': f'value{i}' for i in range(20)}
        annotations['cert-manager.io/cluster-issuer'] = 'letsencrypt-prod'
        annotations['portal-checker.io/exclude'] = 'true'
        
        result = _extract_essential_annotations(annotations)
        
        # Les annotations essentielles doivent être présentes
        assert 'cert-manager.io/cluster-issuer' in result
        assert 'portal-checker.io/exclude' in result
        
        # Le total doit être limité à 10
        assert len(result) <= 10

    def test_cache_endpoint_success(self, client):
        """Test que l'endpoint /cache retourne les informations du cache"""
        response = client.get("/cache")
        assert response.status_code == 200
        
        data = response.get_json()
        assert "cache_valid" in data
        assert "last_updated" in data
        assert "expiry" in data
        assert "ttl_seconds" in data
        assert "cached_urls_count" in data
        assert "seconds_until_expiry" in data
        assert "status" in data
        assert data["status"] == "ok"

    def test_cache_validity_functions(self):
        """Test des fonctions de validité du cache"""
        import app
        
        # Réinitialiser le cache avant le test
        _reset_cache()
        
        # Test cache non initialisé
        assert not _is_cache_valid()
        
        # Test cache expiré
        app._kubernetes_cache['expiry'] = datetime.now() - timedelta(seconds=10)
        assert not _is_cache_valid()
        
        # Test cache valide
        app._kubernetes_cache['expiry'] = datetime.now() + timedelta(seconds=300)
        app._kubernetes_cache['data'] = []  # Add some data
        assert _is_cache_valid()

    def test_cache_update_function(self):
        """Test de la fonction de mise à jour du cache"""
        import app
        
        # Réinitialiser le cache avant le test
        _reset_cache()
        
        test_data = [{"url": "test.com", "name": "test"}]
        
        _update_cache(test_data)
        
        assert app._kubernetes_cache['data'] == test_data
        assert app._kubernetes_cache['last_updated'] is not None
        assert app._kubernetes_cache['expiry'] is not None
        assert _is_cache_valid()

    def test_get_cached_urls_valid(self):
        """Test de récupération des URLs depuis un cache valide"""
        # Réinitialiser le cache avant le test
        _reset_cache()
        
        test_data = [{"url": "cached.com", "name": "cached"}]
        _update_cache(test_data)
        
        result = _get_cached_urls()
        assert result == test_data

    def test_get_cached_urls_invalid(self):
        """Test de récupération des URLs depuis un cache invalide"""
        import app
        
        # Réinitialiser le cache avant le test
        _reset_cache()
        
        app._kubernetes_cache['expiry'] = datetime.now() - timedelta(seconds=10)
        
        result = _get_cached_urls()
        assert result is None

    def test_cache_integration_with_get_all_urls(self):
        """Test d'intégration du cache avec la fonction principale"""
        # Réinitialiser le cache avant le test
        _reset_cache()
        
        # Cette fonction nécessiterait de mocker les appels Kubernetes
        # Pour l'instant, on teste juste que les fonctions de cache fonctionnent
        test_data = [{"url": "integration.com", "name": "integration"}]
        
        # Simuler une mise à jour du cache
        _update_cache(test_data)
        
        # Vérifier que le cache est valide
        assert _is_cache_valid()
        
        # Vérifier que on peut récupérer les données
        cached = _get_cached_urls()
        assert cached == test_data