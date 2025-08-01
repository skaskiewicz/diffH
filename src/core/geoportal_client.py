"""
Moduł komunikacji z API Geoportalu
"""

import logging
import requests
from typing import Dict, List, Tuple, Optional
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
from ..config.settings import CONCURRENT_API_REQUESTS, API_MAX_RETRIES


def fetch_height_batch(batch: List[Tuple[float, float]]) -> Dict[str, float]:
    """
    Funkcja do pobierania wysokości z Geoportalu dla paczki współrzędnych.
    Args:
        batch (List[Tuple[float, float]]): Lista współrzędnych w formacie [(easting, northing), ...].
    Returns:
        Dict[str, float]: Słownik z wysokościami w formacie {'northing easting': height}.
    """
    if not batch:
        return {}
    # Usuwanie duplikatów z paczki (API zwraca wysokość dla każdej współrzędnej, ale klucz w słowniku bywa nadpisany)
    unique_batch = list(dict.fromkeys(batch))
    point_strings = [
        f"{northing:.2f} {easting:.2f}" for easting, northing in unique_batch
    ]
    list_parameter = ",".join(point_strings)
    url = f"https://services.gugik.gov.pl/nmt/?request=GetHByPointList&list={list_parameter}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    for attempt in range(1, API_MAX_RETRIES + 1):
        logging.debug(f"Wysyłka do Geoportalu (próba {attempt}): URL={url}")
        try:
            response = requests.get(url, timeout=30, headers=headers)
            logging.debug(f"Odpowiedź: status={response.status_code}, body={response.text}")
            response.raise_for_status()
            batch_heights = {}
            if response.text.strip():
                results = response.text.strip().split(",")
                all_zero = True
                for line in results:
                    parts = line.strip().split()
                    if len(parts) == 3:
                        northing_api, easting_api, h_api = parts
                        key = f"{northing_api} {easting_api}"
                        try:
                            h_val = float(h_api)
                            batch_heights[key] = h_val
                            if h_val != 0.0:
                                all_zero = False
                        except ValueError:
                            batch_heights[key] = 0.0
                # Jeśli wszystkie wysokości to 0.0, powtórz zapytanie (chyba że to ostatnia próba)
                if all_zero and attempt < API_MAX_RETRIES:
                    logging.warning("Ostrzeżenie: Wszystkie wysokości 0.0, ponawiam próbę...")
                    continue
                return batch_heights
            else:
                logging.warning("Pusta odpowiedź, ponawiam próbę...")
                continue
        except requests.exceptions.RequestException as e:
            logging.error(f"Błąd komunikacji z API (próba {attempt}): {e}")
            if attempt == API_MAX_RETRIES:
                from colorama import Fore
                print(f"{Fore.RED}Błąd komunikacji z API: {e}")
    # Jeśli po wszystkich próbach nie udało się uzyskać poprawnych danych
    logging.error(f"Nie udało się uzyskać poprawnych danych z Geoportalu po {API_MAX_RETRIES} próbach.")
    return {}


def fetch_missing_heights(
    missing_points: List[Tuple[float, float]],
) -> Dict[str, float]:
    """
    Funkcja do ponownego pobierania wysokości dla punktów, które nie miały danych.
    Args:
        missing_points (List[Tuple[float, float]]): Lista współrzędnych punktów, dla których brakuje danych wysokości.
    Returns:
        Dict[str, float]: Słownik z wysokościami w formacie {'northing easting': height}.
    """
    if not missing_points:
        return {}
    logging.debug(f"Ponowna próba pobrania wysokości dla {len(missing_points)} punktów z 'brak_danych'.")
    return fetch_height_batch(missing_points)


def get_geoportal_heights_concurrent(
    transformed_points: List[Optional[Tuple[float, float]]],
) -> Dict[str, float]:
    """
    Funkcja do pobierania wysokości z Geoportalu dla przekształconych współrzędnych.
    Args:
        transformed_points (List[Optional[Tuple[float, float]]]): Lista przekształconych współrzędnych w formacie [(x, y), ...] lub None dla błędów.
    Returns:
        Dict[str, float]: Słownik z wysokościami w formacie {'northing easting': height}.
    """
    from colorama import Fore, Style
    print(f"\n{Fore.CYAN}Pobieranie danych z Geoportalu ...{Style.RESET_ALL}")
    logging.debug("Rozpoczęto pobieranie wysokości z Geoportalu.")

    valid_points = [p for p in transformed_points if p is not None]
    logging.debug(f"Liczba poprawnych punktów do pobrania wysokości: {len(valid_points)}")

    if not valid_points:
        from colorama import Fore, Style
        print(f"{Fore.YELLOW}Brak poprawnych punktów do wysłania do API Geoportalu.")
        return {}

    batch_size = 300
    batches = [
        valid_points[i : i + batch_size]
        for i in range(0, len(valid_points), batch_size)
    ]
    logging.debug(f"Liczba partii do pobrania: {len(batches)} (po {batch_size} punktów)")
    all_heights = {}
    with ThreadPoolExecutor(max_workers=CONCURRENT_API_REQUESTS) as executor:
        results = list(
            tqdm(
                executor.map(fetch_height_batch, batches),
                total=len(batches),
                desc="Pobieranie z Geoportalu",
            )
        )
    for batch_result in results:
        all_heights.update(batch_result)
    # --- Ponowna próba dla punktów, które nie mają wysokości ---
    missing_points = []
    for p in valid_points:
        lookup_key = f"{p[1]:.2f} {p[0]:.2f}"
        if lookup_key not in all_heights:
            missing_points.append(p)
    if missing_points:
        retry_heights = fetch_missing_heights(missing_points)
        all_heights.update(retry_heights)
        logging.debug(f"Po ponownej próbie uzyskano wysokości dla {len(retry_heights)} z {len(missing_points)} brakujących punktów.")

    logging.debug(f"Łącznie pobrano wysokości dla {len(all_heights)} punktów z Geoportalu.")
    return all_heights 