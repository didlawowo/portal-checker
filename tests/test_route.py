from unittest.mock import MagicMock

import pytest

from src.app import check_single_url as app_check_single_url


@pytest.mark.asyncio
async def test_test_single_url():
    # Créer un mock pour ClientSession
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    # Tester la fonction avec un dictionnaire comme attendu
    test_data = {"url": "example.com", "name": "test"}
    result = await app_check_single_url(mock_session, test_data)
    
    # Vérifier les résultats
    assert result["url"] == "example.com"
    assert result["status"] == 200
    assert result["details"] == ""
    assert "response_time" in result
    assert isinstance(result["response_time"], (int, float))
    
@pytest.mark.asyncio
async def test_test_single_url_with_error():
    # Créer un mock pour ClientSession
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 500
    mock_response.reason = "Internal Server Error"
    mock_session.get.return_value.__aenter__.return_value = mock_response
    
    test_data = {"url": "error.example.com", "name": "error-test"}
    result = await app_check_single_url(mock_session, test_data)
    
    # Vérifier les résultats d'erreur
    assert result["url"] == "error.example.com"
    assert result["status"] == 500
    assert "❌" in result["details"]
    assert "response_time" in result