"""
Moduł config - Konfiguracja aplikacji
"""

from .settings import *

__all__ = [
    'DEBUG_MODE',
    'CONCURRENT_API_REQUESTS', 
    'API_MAX_RETRIES',
    'ROUND_INPUT_DECIMALS',
    'DEFAULT_SPARSE_GRID_DISTANCE'
] 