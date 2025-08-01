"""
Moduł config - Konfiguracja aplikacji
"""

from .settings import (
    API_MAX_RETRIES,
    CONCURRENT_API_REQUESTS,
    DEBUG_MODE,
    DEFAULT_SPARSE_GRID_DISTANCE,
    ROUND_INPUT_DECIMALS,
)

__all__ = [
    'DEBUG_MODE',
    'CONCURRENT_API_REQUESTS', 
    'API_MAX_RETRIES',
    'ROUND_INPUT_DECIMALS',
    'DEFAULT_SPARSE_GRID_DISTANCE'
] 