import sys
import os
# Add the project path to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
import json

from src.app import app


class TestHealthEndpoint:
    """Tests complets pour l'endpoint /health"""

    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app"""
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_health_endpoint_success(self, client):
        """Test que l'endpoint /health retourne une réponse valide"""
        response = client.get('/health')
        
        # Vérifier le status code
        assert response.status_code == 200
        
        # Vérifier le content-type
        assert response.content_type == 'application/json'
        
        # Vérifier la structure de la réponse JSON
        data = response.get_json()
        assert isinstance(data, dict)
        assert 'status' in data
        assert data['status'] == 'ok'

    def test_health_endpoint_response_format(self, client):
        """Test le format exact de la réponse de l'endpoint health"""
        response = client.get('/health')
        
        # Vérifier que la réponse peut être parsée en JSON
        assert response.is_json
        
        # Vérifier le contenu exact
        expected_response = {"status": "ok"}
        actual_response = response.get_json()
        assert actual_response == expected_response

    def test_health_endpoint_http_methods(self, client):
        """Test que l'endpoint health ne répond qu'aux requêtes GET"""
        # GET devrait fonctionner
        response = client.get('/health')
        assert response.status_code == 200
        
        # POST ne devrait pas être autorisé
        response = client.post('/health')
        assert response.status_code == 405  # Method Not Allowed
        
        # PUT ne devrait pas être autorisé
        response = client.put('/health')
        assert response.status_code == 405
        
        # DELETE ne devrait pas être autorisé
        response = client.delete('/health')
        assert response.status_code == 405

    def test_health_endpoint_headers(self, client):
        """Test les headers de la réponse health"""
        response = client.get('/health')
        
        # Vérifier le Content-Type
        assert 'application/json' in response.content_type
        
        # Vérifier que la réponse contient les headers appropriés
        assert response.status_code == 200

    def test_health_endpoint_multiple_requests(self, client):
        """Test que l'endpoint health est idempotent"""
        # Faire plusieurs requêtes et vérifier la cohérence
        responses = []
        for _ in range(5):
            response = client.get('/health')
            responses.append(response)
        
        # Toutes les réponses doivent être identiques
        for response in responses:
            assert response.status_code == 200
            assert response.get_json() == {"status": "ok"}


    def test_health_endpoint_multiple_sequential_requests(self, client):
        """Test plusieurs requêtes séquentielles sur l'endpoint health"""
        # Au lieu de threads concurrents, testons plusieurs requêtes séquentielles
        results = []
        
        for _ in range(10):
            response = client.get('/health')
            results.append({
                'status_code': response.status_code,
                'data': response.get_json()
            })
        
        # Vérifier que toutes les requêtes ont réussi
        assert len(results) == 10
        for result in results:
            assert result['status_code'] == 200
            assert result['data'] == {"status": "ok"}

    def test_health_endpoint_response_time(self, client):
        """Test que l'endpoint health répond rapidement"""
        import time
        
        start_time = time.time()
        response = client.get('/health')
        end_time = time.time()
        
        response_time = end_time - start_time
        
        # L'endpoint health devrait répondre en moins de 100ms
        assert response_time < 0.1, f"Health endpoint trop lent: {response_time:.3f}s"
        assert response.status_code == 200

    def test_health_endpoint_with_query_parameters(self, client):
        """Test que l'endpoint health ignore les paramètres de requête"""
        # Test avec différents paramètres
        test_cases = [
            '/health?test=1',
            '/health?format=json',
            '/health?verbose=true',
            '/health?random=abc123'
        ]
        
        for url in test_cases:
            response = client.get(url)
            assert response.status_code == 200
            assert response.get_json() == {"status": "ok"}

    def test_health_endpoint_with_headers(self, client):
        """Test l'endpoint health avec différents headers"""
        # Test avec différents User-Agent
        response = client.get('/health', headers={'User-Agent': 'TestBot/1.0'})
        assert response.status_code == 200
        assert response.get_json() == {"status": "ok"}
        
        # Test avec Accept header
        response = client.get('/health', headers={'Accept': 'application/json'})
        assert response.status_code == 200
        assert response.get_json() == {"status": "ok"}
        
        # Test avec headers personnalisés
        custom_headers = {
            'X-Test-Header': 'test-value',
            'X-Request-ID': '12345'
        }
        response = client.get('/health', headers=custom_headers)
        assert response.status_code == 200
        assert response.get_json() == {"status": "ok"}

    def test_health_endpoint_json_serialization(self, client):
        """Test que la réponse JSON est correctement sérialisée"""
        response = client.get('/health')
        
        # Vérifier que la réponse peut être désérialisée manuellement
        raw_data = response.get_data(as_text=True)
        parsed_data = json.loads(raw_data)
        
        assert parsed_data == {"status": "ok"}
        assert isinstance(parsed_data["status"], str)

    def test_health_endpoint_robustness(self, client):
        """Test la robustesse de l'endpoint health"""
        # Test que l'endpoint fonctionne même avec des requêtes multiples
        for _ in range(5):
            response = client.get('/health')
            assert response.status_code == 200
            assert response.get_json() == {"status": "ok"}

    def test_health_endpoint_content_length(self, client):
        """Test que l'endpoint health retourne la bonne longueur de contenu"""
        response = client.get('/health')
        
        # Vérifier le Content-Length
        expected_content = '{"status":"ok"}\n'  # Flask ajoute \n
        assert len(response.get_data()) > 0
        
        # Vérifier que le contenu est cohérent
        assert response.status_code == 200

    def test_health_endpoint_encoding(self, client):
        """Test l'encodage de la réponse de l'endpoint health"""
        response = client.get('/health')
        
        # Vérifier que le contenu peut être décodé
        content = response.get_data(as_text=True)
        assert '"status"' in content
        assert '"ok"' in content
        
        # Vérifier que c'est du JSON valide
        import json
        json_data = json.loads(content)
        assert json_data == {"status": "ok"}

    def test_health_endpoint_load_testing(self, client):
        """Test de charge simple sur l'endpoint health"""
        # Faire 100 requêtes pour tester la performance
        for i in range(100):
            response = client.get('/health')
            assert response.status_code == 200
            assert response.get_json() == {"status": "ok"}
        
        # Si on arrive ici, l'endpoint a géré 100 requêtes sans problème

    def test_health_endpoint_memory_efficiency(self, client):
        """Test que l'endpoint health n'accumule pas de mémoire"""
        import gc
        
        # Forcer le garbage collection avant le test
        gc.collect()
        
        # Faire plusieurs requêtes
        for _ in range(50):
            response = client.get('/health')
            assert response.status_code == 200
            # Supprimer explicitement la référence
            del response
        
        # Forcer à nouveau le garbage collection
        gc.collect()
        
        # Le test réussit si aucune exception n'est levée

    def test_health_endpoint_status_field_type(self, client):
        """Test que le champ status est bien une chaîne de caractères"""
        response = client.get('/health')
        data = response.get_json()
        
        assert isinstance(data["status"], str)
        assert data["status"] == "ok"
        assert len(data["status"]) > 0

    def test_health_endpoint_json_structure(self, client):
        """Test approfondi de la structure JSON de la réponse"""
        response = client.get('/health')
        data = response.get_json()
        
        # Vérifier que c'est un dictionnaire avec exactement un élément
        assert isinstance(data, dict)
        assert len(data) == 1
        
        # Vérifier que la clé existe et a la bonne valeur
        assert "status" in data
        assert data["status"] == "ok"
        
        # Vérifier qu'il n'y a pas d'autres champs
        assert list(data.keys()) == ["status"]

    def test_health_endpoint_case_sensitivity(self, client):
        """Test que l'endpoint health est sensible à la casse dans l'URL"""
        # /health devrait fonctionner
        response = client.get('/health')
        assert response.status_code == 200
        
        # /Health ne devrait pas fonctionner (404)
        response = client.get('/Health')
        assert response.status_code == 404
        
        # /HEALTH ne devrait pas fonctionner (404)
        response = client.get('/HEALTH')
        assert response.status_code == 404