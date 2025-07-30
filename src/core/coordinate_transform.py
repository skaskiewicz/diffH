"""
Moduł transformacji współrzędnych geodezyjnych
"""

import logging
import multiprocessing
import pandas as pd
from typing import List, Optional, Tuple
from tqdm import tqdm
from pyproj import Transformer
from pyproj.exceptions import CRSError
from .data_loader import get_source_epsg


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
    Args:
        df (pd.DataFrame): DataFrame z kolumnami 'geodetic_northing' i 'geodetic_easting'.
    Returns:
        List[Optional[Tuple[float, float]]]: Lista przekształconych współrzędnych w formacie [(x, y), ...] lub None dla błędów.
    """
    from colorama import Fore, Style
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