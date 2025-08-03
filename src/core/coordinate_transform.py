# START OF FILE src/core/coordinate_transform.py

"""
Moduł transformacji współrzędnych geodezyjnych
"""

import logging
import multiprocessing
import numpy as np
import pandas as pd
# --- ZMIANA: Dodajemy import `cast` ---
from typing import List, Optional, Tuple, Dict, Any, cast
from tqdm import tqdm
from pyproj import Transformer
from pyproj.exceptions import CRSError
from .data_loader import get_source_epsg

# Import CUDA transform functions
try:
    from .cuda_transform import (
        check_cuda_availability,
        transform_coordinates_cuda_optimized,
        get_cuda_device_info
    )
    CUDA_MODULE_AVAILABLE = True
    logging.info("Moduł transformacji CUDA załadowany pomyślnie.")
except ImportError:
    def check_cuda_availability() -> bool: return False
    def transform_coordinates_cuda_optimized(df: pd.DataFrame) -> Optional[List[Optional[Tuple[float, float]]]]: return None
    def get_cuda_device_info() -> Optional[Dict[str, Any]]: return None
    CUDA_MODULE_AVAILABLE = False
    logging.info("Moduł CUDA nie jest dostępny. Funkcje CUDA będą nieaktywne.")


def transform_chunk_cpu(chunk_data: Tuple[int, pd.DataFrame]) -> Tuple[pd.Index, np.ndarray]:
    """
    Worker do równoległej transformacji partii (chunk) danych dla jednej strefy EPSG.
    
    Args:
        chunk_data (Tuple[int, pd.DataFrame]): Krotka zawierająca (source_epsg, DataFrame z punktami).
    
    Returns:
        Tuple[pd.Index, np.ndarray]: Krotka zawierająca (oryginalne indeksy, przetransformowane punkty).
    """
    source_epsg, chunk_df = chunk_data
    
    if chunk_df.empty:
        return chunk_df.index, np.array([])
        
    try:
        transformer = Transformer.from_crs(
            f"EPSG:{source_epsg}", "EPSG:2180", always_xy=True
        )
        x_out, y_out = transformer.transform(
            chunk_df["geodetic_easting"].values, chunk_df["geodetic_northing"].values
        )
        return chunk_df.index, np.vstack((x_out, y_out)).T
    except CRSError as e:
        logging.error(f"BŁĄD KRYTYCZNY: Nie można utworzyć transformera dla EPSG:{source_epsg}. Błąd: {e}")
        return chunk_df.index, np.full((len(chunk_df), 2), np.nan)


def transform_coordinates_parallel(
    df: pd.DataFrame,
) -> List[Optional[Tuple[float, float]]]:
    """
    Funkcja do równoległej transformacji współrzędnych geodezyjnych z układu PL-2000 do układu PL-1992 (EPSG:2180).
    """
    from colorama import Fore, Style
    
    if df.empty:
        return []

    # Sprawdź dostępność CUDA
    if CUDA_MODULE_AVAILABLE and check_cuda_availability():
        print(f"{Fore.GREEN}Wykryto kartę NVIDIA - używam przyspieszenia CUDA{Style.RESET_ALL}")
        logging.info("Używam transformacji CUDA")
        
        try:
            result = transform_coordinates_cuda_optimized(df)
            if result is not None:
                return result
        except Exception as e:
            logging.warning(f"Błąd w zoptymalizowanej transformacji CUDA: {e}. Przełączam na CPU.")
    
    # === ZOPTYMALIZOWANY TRYB CPU ===
    print(f"{Fore.YELLOW}Używam zoptymalizowanego przetwarzania CPU (CUDA niedostępne lub wystąpił błąd){Style.RESET_ALL}")
    logging.info("Używam zoptymalizowanej, wsadowej transformacji CPU")
    print(f"\n{Fore.CYAN}Transformuję współrzędne ...{Style.RESET_ALL}")
    
    df_copy = df.copy()
    df_copy['source_epsg'] = df_copy['geodetic_easting'].apply(get_source_epsg)
    
    grouped = df_copy.groupby('source_epsg')
    
    # --- ZMIANA: Używamy `cast` do poinformowania Pylance o poprawnym typie ---
    tasks = [
        (cast(int, epsg), group_df)
        for epsg, group_df in grouped
        if epsg is not None and pd.notna(epsg)
    ]

    results_list: List[Optional[Tuple[float, float]]] = [None] * len(df)
    original_indices = df.index
    index_to_pos = {idx: pos for pos, idx in enumerate(original_indices)}

    with multiprocessing.Pool() as pool:
        results_iterator = pool.imap_unordered(transform_chunk_cpu, tasks)
        
        for chunk_indices, transformed_points_chunk in tqdm(results_iterator, total=len(tasks), desc="Transformacja stref (CPU)"):
            for i, original_idx in enumerate(chunk_indices):
                list_pos = index_to_pos.get(original_idx)
                if list_pos is None:
                    continue
                    
                point = transformed_points_chunk[i]
                if not np.isnan(point).any():
                    results_list[list_pos] = (point[0], point[1])
                else:
                    results_list[list_pos] = None
                    
    logging.debug(f"Zakończono transformację CPU. Przetworzono {len(df)} punktów.")
    return results_list


def get_transformation_method_info() -> str:
    """
    Zwraca informację o dostępnej metodzie transformacji
    """
    if CUDA_MODULE_AVAILABLE and check_cuda_availability():
        device_info = get_cuda_device_info()
        if device_info and device_info.get('current_device') is not None:
            if device_info.get('devices') and device_info['current_device'] < len(device_info['devices']):
                device_name = device_info['devices'][device_info['current_device']]['name']
                return f"CUDA (GPU: {device_name})"
        return "CUDA (GPU acceleration)"
    else:
        return "CPU (zoptymalizowane, wsadowe)"