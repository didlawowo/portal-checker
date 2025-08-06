import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import aiohttp

from src.app import check_single_url


class TestResponseTimeRounding:
    """Test que le temps de réponse est arrondi à l'unité"""

    @pytest.mark.asyncio
    async def test_response_time_rounded_to_integer(self):
        """Test que le temps de réponse est arrondi à l'entier"""
        # Mock session
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = "OK"
        
        # Mock la méthode __aenter__ pour le context manager
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        # Mock time.time pour contrôler le temps de réponse
        with patch('app.time.time') as mock_time:
            # Simuler un temps de réponse de 123.456 ms
            mock_time.side_effect = [0.0, 0.123456]  # start_time=0, end_time=0.123456
            
            test_data = {"url": "example.com", "name": "test"}
            result = await check_single_url(mock_session, test_data)
            
            # Vérifier que le temps de réponse est arrondi à l'entier
            # 0.123456 * 1000 = 123.456 ms, arrondi = 123 ms
            assert result["response_time"] == 123
            assert isinstance(result["response_time"], int)

    @pytest.mark.asyncio
    async def test_response_time_rounding_various_values(self):
        """Test l'arrondissement avec différentes valeurs"""
        test_cases = [
            (0.0501, 50),    # 50.1 ms -> 50 ms
            (0.0505, 50),    # 50.5 ms -> 50 ms (Python round() arrondi au pair)
            (0.0515, 52),    # 51.5 ms -> 52 ms
            (0.0999, 100),   # 99.9 ms -> 100 ms  
            (0.1234, 123),   # 123.4 ms -> 123 ms
            (0.1236, 124),   # 123.6 ms -> 124 ms
            (1.5678, 1568),  # 1567.8 ms -> 1568 ms
        ]
        
        for duration, expected_rounded in test_cases:
            # Mock session
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.reason = "OK"
            
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

            with patch('app.time.time') as mock_time:
                mock_time.side_effect = [0.0, duration]
                
                test_data = {"url": "example.com", "name": "test"}
                result = await check_single_url(mock_session, test_data)
                
                assert result["response_time"] == expected_rounded, \
                    f"Pour {duration}s, attendu {expected_rounded}ms, obtenu {result['response_time']}ms"
                assert isinstance(result["response_time"], int)

    @pytest.mark.asyncio
    async def test_response_time_timeout_rounded(self):
        """Test que le temps de réponse est arrondi même en cas de timeout"""
        mock_session = MagicMock()
        
        # Mock pour lever une TimeoutError
        mock_session.get.side_effect = asyncio.TimeoutError()

        with patch('app.time.time') as mock_time:
            # Simuler un timeout après 2.789 secondes
            mock_time.side_effect = [0.0, 2.789]
            
            test_data = {"url": "timeout.example.com", "name": "timeout-test"}
            result = await check_single_url(mock_session, test_data)
            
            # Vérifier que le temps de réponse est arrondi même en cas de timeout
            # 2.789 * 1000 = 2789 ms
            assert result["response_time"] == 2789
            assert isinstance(result["response_time"], int)
            assert result["status"] == 504
            assert "Timeout Error" in result["details"]

    @pytest.mark.asyncio
    async def test_response_time_exception_rounded(self):
        """Test que le temps de réponse est arrondi même en cas d'exception"""
        mock_session = MagicMock()
        
        # Mock pour lever une exception
        mock_session.get.side_effect = Exception("Connection error")

        with patch('app.time.time') as mock_time:
            # Simuler une exception après 1.234 secondes
            mock_time.side_effect = [0.0, 1.234]
            
            test_data = {"url": "error.example.com", "name": "error-test"}
            result = await check_single_url(mock_session, test_data)
            
            # Vérifier que le temps de réponse est arrondi même en cas d'exception
            # 1.234 * 1000 = 1234 ms
            assert result["response_time"] == 1234
            assert isinstance(result["response_time"], int)
            assert result["status"] == 500
            assert "Connection error" in result["details"]

    @pytest.mark.asyncio
    async def test_response_time_very_fast(self):
        """Test l'arrondissement pour des temps de réponse très rapides"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = "OK"
        
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch('app.time.time') as mock_time:
            # Temps de réponse très rapide: 0.0001 secondes = 0.1 ms
            mock_time.side_effect = [0.0, 0.0001]
            
            test_data = {"url": "fast.example.com", "name": "fast-test"}
            result = await check_single_url(mock_session, test_data)
            
            # 0.0001 * 1000 = 0.1 ms, arrondi = 0 ms
            assert result["response_time"] == 0
            assert isinstance(result["response_time"], int)

    @pytest.mark.asyncio
    async def test_response_time_very_slow(self):
        """Test l'arrondissement pour des temps de réponse très lents"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = "OK"
        
        mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)

        with patch('app.time.time') as mock_time:
            # Temps de réponse très lent: 10.9876 secondes = 10987.6 ms
            mock_time.side_effect = [0.0, 10.9876]
            
            test_data = {"url": "slow.example.com", "name": "slow-test"}
            result = await check_single_url(mock_session, test_data)
            
            # 10.9876 * 1000 = 10987.6 ms, arrondi = 10988 ms
            assert result["response_time"] == 10988
            assert isinstance(result["response_time"], int)