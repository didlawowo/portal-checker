import pytest
from unittest.mock import  MagicMock
from app import test_single_url
import aiohttp

@pytest.fixture
async def session():
    """Fixture qui fournit une session aiohttp pour les tests."""
    async with aiohttp.ClientSession() as session:
        yield session

@pytest.fixture
def url():
    """Fixture qui fournit une URL de test."""
    return "example.com"o

@pytest.mark.asyncio
async def test_test_single_url():
    # Créer un mock pour ClientSession
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    # Tester la fonction
    result = await test_single_url(mock_session, "example.com")
    
    # Vérifier les résultats
    assert result["url"] == "example.com"
    assert result["status"] == 200
    assert result["details"] == ""
    
@pytest.mark.asyncio
async def test_test_single_url_with_error():
    # Créer un mock pour ClientSession
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.text.return_value = "Internal Server Error"
    mock_session.get.return_value.__aenter__.return_value = mock_response