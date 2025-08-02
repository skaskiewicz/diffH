#!/usr/bin/env python3
"""
diffH - Porównanie wysokości punktów
Główny plik uruchomieniowy aplikacji
"""

import sys
import os
import traceback
import warnings
from colorama import Fore, Style

# Ignoruj ostrzeżenie z CuPy o braku CUDA_PATH, jeśli i tak działa
warnings.filterwarnings("ignore", category=UserWarning, message="CUDA path could not be detected.*")
# Ignoruj ostrzeżenia o przestarzałych funkcjach (np. z setuptools)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Dodaj katalog src do ścieżki Pythona
# Upewnijmy się, że ścieżka do src jest dodawana poprawnie
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(project_root, 'src'))

if __name__ == "__main__":
    try:
        from src.core.processor import main

        # Zdefiniuj ścieżkę do pliku konfiguracyjnego w głównym katalogu
        config_file_path = os.path.join(project_root, "config.json")
        main(config_path=config_file_path)

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Przerwano działanie programu.{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Wystąpił nieoczekiwany błąd globalny: {e}")
        traceback.print_exc()
    finally:
        input(f"\n{Fore.YELLOW}Naciśnij Enter, aby zakończyć...{Style.RESET_ALL}")