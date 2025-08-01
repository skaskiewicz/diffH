"""
Moduł transformacji współrzędnych geodezyjnych
"""

import logging
import multiprocessing
import pandas as pd
from typing import List, Optional, Tuple, Dict, Any # Upewnij się, że masz te importy
from tqdm import tqdm
from pyproj import Transformer
from pyproj.exceptions import CRSError
from .data_loader import get_source_epsg

# Import CUDA transform functions
try:
    from .cuda_transform import (
        check_cuda_availability,
        transform_coordinates_cuda,
        transform_coordinates_cuda_optimized,
        get_cuda_device_info
    )
    CUDA_MODULE_AVAILABLE = True
    logging.info("Moduł transformacji CUDA załadowany pomyślnie.")

except ImportError:
    # Definiujemy puste funkcje z sygnaturami zgodnymi z oryginałami,
    # aby Pylance był zadowolony.
    
    # Sygnatura musi być identyczna jak w prawdziwej funkcji
    def check_cuda_availability() -> bool:
        return False

    def transform_coordinates_cuda(df: pd.DataFrame, batch_size: int = 10000) -> Optional[List[Optional[Tuple[float, float]]]]:
        return None

    def transform_coordinates_cuda_optimized(df: pd.DataFrame) -> Optional[List[Optional[Tuple[float, float]]]]:
        return None
        
    def get_cuda_device_info() -> Optional[Dict[str, Any]]:
        return None

    CUDA_MODULE_AVAILABLE = False
    logging.info("Moduł CUDA nie jest dostępny. Funkcje CUDA będą nieaktywne.")


def worker_transform(
    point_data_with_index: Tuple[int, float, float],
) -> Optional[Tuple[float, float]]:
    """Worker do równoległej transformacji współrzędnych"""
    index, northing, easting = point_data_with_index

    source_epsg = get_source_epsg(easting)
    if source_epsg is None:
        logging.debug(f"Punkt {index + 1}: BŁĄD - Nie można określić strefy EPSG dla easting={easting}. Współrzędne (N, E): ({northing}, {easting})")
        return None
    try:
        transformer = Transformer.from_crs(
            f"EPSG:{source_epsg}", "EPSG:2180", always_xy=True
        )
        x_out, y_out = transformer.transform(easting, northing)
        logging.debug(f"Punkt {index + 1}: OK. Oryginalne (N, E)=({northing}, {easting}) -> Transformowane (X, Y)=({x_out:.2f}, {y_out:.2f})")
        return x_out, y_out
    except CRSError as e:
        logging.debug(f"Punkt {index + 1}: BŁĄD transformacji (CRSError) dla (N, E)=({northing}, {easting}). Błąd: {e}")
        return None


def transform_coordinates_parallel(
    df: pd.DataFrame,
) -> List[Optional[Tuple[float, float]]]:
    """
    Funkcja do równoległej transformacji współrzędnych geodezyjnych z układu PL-2000 do układu PL-1992 (EPSG:2180).
    Automatycznie wykrywa dostępność CUDA i używa przyspieszenia GPU jeśli jest dostępne.
    
    Args:
        df (pd.DataFrame): DataFrame z kolumnami 'geodetic_northing' i 'geodetic_easting'.
    Returns:
        List[Optional[Tuple[float, float]]]: Lista przekształconych współrzędnych w formacie [(x, y), ...] lub None dla błędów.
    """
    from colorama import Fore, Style
    
    # Sprawdź dostępność CUDA
    if CUDA_MODULE_AVAILABLE and check_cuda_availability():
        print(f"{Fore.GREEN}Wykryto kartę NVIDIA - używam przyspieszenia CUDA{Style.RESET_ALL}")
        logging.info("Używam transformacji CUDA")
        
        # Próbuj zoptymalizowaną wersję CUDA
        try:
            result = transform_coordinates_cuda_optimized(df)
            if result is not None:
                return result
        except Exception as e:
            logging.warning(f"Błąd w zoptymalizowanej transformacji CUDA: {e}")
        
        # Fallback do standardowej transformacji CUDA
        try:
            result = transform_coordinates_cuda(df)
            if result is not None:
                return result
        except Exception as e:
            logging.warning(f"Błąd w transformacji CUDA: {e}")
    
    # Fallback do przetwarzania CPU
    print(f"{Fore.YELLOW}Używam przetwarzania CPU (CUDA niedostępne){Style.RESET_ALL}")
    logging.info("Używam transformacji CPU")
    
    print(f"\n{Fore.CYAN}Transformuję współrzędne ...{Style.RESET_ALL}")
    logging.debug("Rozpoczęto równoległą transformację współrzędnych.")

    # Przygotowujemy dane wejściowe jako (indeks, northing, easting)
    points_to_transform = list(
        zip(range(len(df)), df["geodetic_northing"], df["geodetic_easting"])
    )

    results = []
    # Używamy puli procesów do równoległego przetwarzania
    with multiprocessing.Pool() as pool:
        # Używamy imap dla efektywnego przetwarzania z paskiem postępu
        results = list(
            tqdm(
                pool.imap(worker_transform, points_to_transform, chunksize=100),
                total=len(points_to_transform),
                desc="Transformacja współrzędnych",
            )
        )
    logging.debug(f"Zakończono transformację. Przetworzono {len(results)} punktów.")
    return results


def get_transformation_method_info() -> str:
    """
    Zwraca informację o dostępnej metodzie transformacji
    """
    if CUDA_MODULE_AVAILABLE and check_cuda_availability():
        device_info = get_cuda_device_info()
        if device_info and device_info['current_device'] is not None:
            device_name = device_info['devices'][device_info['current_device']]['name']
            return f"CUDA (GPU: {device_name})"
        return "CUDA (GPU acceleration)"
    else:
        return "CPU (multiprocessing)" 