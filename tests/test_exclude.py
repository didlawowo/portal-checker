import os
import sys

import pytest

# Ajoutez le chemin du projet au PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import de la fonction à tester
from app import _is_url_excluded, excluded_urls


@pytest.fixture
def setup_excluded_urls():
    # Réinitialiser les URLs exclues pour chaque test
    global excluded_urls
    excluded_urls.clear()
    
    # Ajouter des URLs de test
    excluded_urls.update([
        "example.com/admin",
        "api.example.com/private/*",
        "test.com"
    ])

def test_exact_match(setup_excluded_urls):
    assert _is_url_excluded("example.com/admin") is True
    assert _is_url_excluded("example.com/public") is False

def test_wildcard_match(setup_excluded_urls):
    assert _is_url_excluded("api.example.com/private/users") is True
    assert _is_url_excluded("api.example.com/private/settings") is True
    assert _is_url_excluded("api.example.com/public/users") is False

def test_domain_match(setup_excluded_urls):
    assert _is_url_excluded("test.com") is True
    assert _is_url_excluded("test.com/") is True  # Test avec slash à la fin
    assert _is_url_excluded("test.com/any") is False  # Ne devrait pas matcher les sous-chemins

def test_trailing_slash(setup_excluded_urls):
    # Ajouter une URL avec slash final pour tester
    excluded_urls.add("service.example.com/")
    
    assert _is_url_excluded("service.example.com") is True
    assert _is_url_excluded("service.example.com/") is True