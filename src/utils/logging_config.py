"""
Konfiguracja systemu logowania
"""

import os
import logging
from ..config.settings import DEBUG_MODE


def setup_logging():
    """Konfiguruje system logowania, jeśli DEBUG_MODE jest włączony."""
    if DEBUG_MODE:
        log_file = "debug.log"
        # Usuń stary plik logu, jeśli istnieje
        if os.path.exists(log_file):
            os.remove(log_file)

        # Skonfiguruj logger, aby zapisywał do pliku
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
            filename=log_file,
            filemode="w",
            encoding='utf-8'
        )
        logging.debug("Tryb debugowania aktywny. Logi zapisywane do debug.log")
    else:
        # Jeśli tryb debugowania jest wyłączony, wyłącz logowanie
        logging.disable(logging.CRITICAL) 