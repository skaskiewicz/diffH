"""
Moduł do zarządzania plikiem konfiguracyjnym użytkownika.
"""
import json
import os
import logging
from colorama import Fore, Style

def load_config(config_path: str) -> dict:
    """
    Wczytuje konfigurację z podanej ścieżki.
    Zwraca pusty słownik, jeśli plik nie istnieje lub jest uszkodzony.
    """
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.warning(f"Nie udało się wczytać pliku konfiguracyjnego: {e}")
        print(f"{Fore.YELLOW}Ostrzeżenie: Nie udało się wczytać pliku konfiguracyjnego '{os.path.basename(config_path)}'. Zostaną użyte wartości domyślne.{Style.RESET_ALL}")
        return {}

def save_config_for_mode(mode: int, settings: dict, config_path: str):
    """
    Zapisuje ustawienia dla danego trybu w pliku konfiguracyjnym.
    """
    try:
        # Wczytaj istniejącą konfigurację, aby jej nie nadpisać całkowicie
        all_configs = load_config(config_path)
        # Zaktualizuj ustawienia dla wybranego trybu
        all_configs[str(mode)] = settings
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(all_configs, f, indent=4)
        logging.info(f"Zapisano konfigurację dla trybu {mode} w pliku {os.path.basename(config_path)}.")
    except Exception as e:
        logging.error(f"Nie udało się zapisać konfiguracji: {e}")
        print(f"{Fore.RED}Błąd: Nie udało się zapisać pliku konfiguracyjnego.{Style.RESET_ALL}")