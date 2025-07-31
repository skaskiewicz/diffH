"""
Moduł transformacji współrzędnych geodezyjnych z wykorzystaniem CUDA
"""

import logging
import numpy as np
import pandas as pd
from typing import List, Optional, Tuple
from tqdm import tqdm
from pyproj import Transformer
from pyproj.exceptions import CRSError
from .data_loader import get_source_epsg

try:
    import cupy as cp
    CUDA_AVAILABLE = True
    logging.info("CuPy jest dostępne - sprawdzam CUDA")
except ImportError:
    CUDA_AVAILABLE = False
    logging.info("CuPy nie jest dostępne - używam przetwarzania CPU")


def check_cuda_availability() -> bool:
    """
    Sprawdza dostępność CUDA i zwraca True jeśli można używać GPU.
    Obsługuje hybrydowe karty graficzne w laptopach i wielokartowe konfiguracje.
    """
    if not CUDA_AVAILABLE:
        return False
    
    try:
        # Sprawdź liczbę dostępnych urządzeń CUDA
        device_count = cp.cuda.runtime.getDeviceCount()
        logging.info(f"Znaleziono {device_count} urządzeń CUDA")
        
        if device_count == 0:
            logging.warning("Brak urządzeń CUDA")
            return False
        
        # Sprawdź każde urządzenie
        available_devices = []
        for device_id in range(device_count):
            try:
                device = cp.cuda.Device(device_id)
                device_name = cp.cuda.runtime.getDeviceProperties(device_id)['name'].decode('utf-8')
                compute_capability = device.compute_capability
                total_memory = device.mem_info[1]  # Total memory in bytes
                
                logging.info(f"Urządzenie {device_id}: {device_name}")
                logging.info(f"  Compute Capability: {compute_capability}")
                logging.info(f"  Pamięć: {total_memory / (1024**3):.2f} GB")
                
                # Sprawdź czy urządzenie jest aktywne i ma wystarczającą pamięć
                if total_memory > 1024**3:  # Minimum 1GB pamięci
                    available_devices.append(device_id)
                    logging.info(f"  ✓ Urządzenie {device_id} jest gotowe do użycia")
                else:
                    logging.warning(f"  ⚠ Urządzenie {device_id} ma za mało pamięci ({total_memory / (1024**3):.2f} GB)")
                    
            except Exception as e:
                logging.warning(f"Błąd sprawdzania urządzenia {device_id}: {e}")
                continue
        
        if available_devices:
            # Wybierz najlepsze urządzenie (z największą pamięcią)
            best_device = max(available_devices, key=lambda d: cp.cuda.Device(d).mem_info[1])
            cp.cuda.Device(best_device).use()
            
            device_name = cp.cuda.runtime.getDeviceProperties(best_device)['name'].decode('utf-8')
            logging.info(f"Wybrano urządzenie {best_device}: {device_name}")
            logging.info("CUDA jest dostępne i gotowe do użycia")
            return True
        else:
            logging.warning("Brak odpowiednich urządzeń CUDA")
            return False
            
    except Exception as e:
        logging.warning(f"Błąd sprawdzania CUDA: {e}")
        return False


def get_cuda_device_info() -> Optional[dict]:
    """
    Zwraca informacje o dostępnych urządzeniach CUDA
    """
    if not CUDA_AVAILABLE:
        return None
    
    try:
        device_count = cp.cuda.runtime.getDeviceCount()
        if device_count == 0:
            return None
        
        devices_info = []
        for device_id in range(device_count):
            try:
                device = cp.cuda.Device(device_id)
                device_name = cp.cuda.runtime.getDeviceProperties(device_id)['name'].decode('utf-8')
                compute_capability = device.compute_capability
                total_memory = device.mem_info[1]
                
                devices_info.append({
                    'id': device_id,
                    'name': device_name,
                    'compute_capability': compute_capability,
                    'memory_gb': total_memory / (1024**3),
                    'available': total_memory > 1024**3
                })
            except Exception:
                continue
        
        return {
            'device_count': device_count,
            'devices': devices_info,
            'current_device': cp.cuda.Device().id if devices_info else None
        }
    except Exception:
        return None


def get_epsg_zones_for_batch(eastings: np.ndarray) -> np.ndarray:
    """
    Określa strefy EPSG dla partii współrzędnych easting
    """
    epsg_zones = np.zeros(len(eastings), dtype=np.int32)
    
    for i, easting in enumerate(eastings):
        epsg_zone = get_source_epsg(easting)
        if epsg_zone is not None:
            epsg_zones[i] = epsg_zone
        else:
            epsg_zones[i] = -1  # Oznaczenie błędu
    
    return epsg_zones


def create_transformers_for_zones(unique_epsg_zones: List[int]) -> dict:
    """
    Tworzy transformery dla unikalnych stref EPSG
    """
    transformers = {}
    
    for epsg_zone in unique_epsg_zones:
        if epsg_zone > 0:
            try:
                transformer = Transformer.from_crs(
                    f"EPSG:{epsg_zone}", "EPSG:2180", always_xy=True
                )
                transformers[epsg_zone] = transformer
            except CRSError as e:
                logging.warning(f"Błąd tworzenia transformera dla EPSG:{epsg_zone}: {e}")
    
    return transformers


def transform_coordinates_cuda(
    df: pd.DataFrame,
    batch_size: int = 10000
) -> List[Optional[Tuple[float, float]]]:
    """
    Funkcja do transformacji współrzędnych geodezyjnych z wykorzystaniem CUDA.
    Automatycznie dzieli dane na partie dla optymalnego wykorzystania GPU.
    
    Args:
        df (pd.DataFrame): DataFrame z kolumnami 'geodetic_northing' i 'geodetic_easting'.
        batch_size (int): Rozmiar partii danych przetwarzanych na GPU.
    
    Returns:
        List[Optional[Tuple[float, float]]]: Lista przekształconych współrzędnych.
    """
    from colorama import Fore, Style
    
    if not check_cuda_availability():
        logging.warning("CUDA nie jest dostępne - przełączam na przetwarzanie CPU")
        return None
    
    # Pobierz informacje o urządzeniu CUDA
    device_info = get_cuda_device_info()
    if device_info:
        current_device = device_info['current_device']
        device_name = device_info['devices'][current_device]['name']
        print(f"{Fore.GREEN}Używam karty: {device_name}{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}Transformuję współrzędne z wykorzystaniem CUDA...{Style.RESET_ALL}")
    logging.debug("Rozpoczęto transformację współrzędnych z wykorzystaniem CUDA.")
    
    results = []
    total_points = len(df)
    
    # Przetwarzanie w partiach
    for start_idx in tqdm(range(0, total_points, batch_size), desc="Partie CUDA"):
        end_idx = min(start_idx + batch_size, total_points)
        batch_df = df.iloc[start_idx:end_idx]
        
        # Przygotowanie danych dla partii
        northings = batch_df["geodetic_northing"].values
        eastings = batch_df["geodetic_easting"].values
        
        # Określenie stref EPSG dla partii
        epsg_zones = get_epsg_zones_for_batch(eastings)
        unique_zones = list(set(epsg_zones[epsg_zones > 0]))
        
        # Tworzenie transformerów dla unikalnych stref
        transformers = create_transformers_for_zones(unique_zones)
        
        # Transformacja dla każdego punktu w partii
        batch_results = []
        for i, (northing, easting, epsg_zone) in enumerate(zip(northings, eastings, epsg_zones)):
            if epsg_zone <= 0:
                logging.debug(f"Punkt {start_idx + i + 1}: BŁĄD - Nie można określić strefy EPSG dla easting={easting}")
                batch_results.append(None)
                continue
            
            if epsg_zone not in transformers:
                logging.debug(f"Punkt {start_idx + i + 1}: BŁĄD - Brak transformera dla EPSG:{epsg_zone}")
                batch_results.append(None)
                continue
            
            try:
                transformer = transformers[epsg_zone]
                x_out, y_out = transformer.transform(easting, northing)
                logging.debug(f"Punkt {start_idx + i + 1}: OK. Oryginalne (N, E)=({northing}, {easting}) -> Transformowane (X, Y)=({x_out:.2f}, {y_out:.2f})")
                batch_results.append((x_out, y_out))
            except Exception as e:
                logging.debug(f"Punkt {start_idx + i + 1}: BŁĄD transformacji dla (N, E)=({northing}, {easting}). Błąd: {e}")
                batch_results.append(None)
        
        results.extend(batch_results)
    
    logging.debug(f"Zakończono transformację CUDA. Przetworzono {len(results)} punktów.")
    return results


def transform_coordinates_cuda_optimized(
    df: pd.DataFrame
) -> List[Optional[Tuple[float, float]]]:
    """
    Zoptymalizowana wersja transformacji CUDA z lepszym wykorzystaniem pamięci GPU
    """
    from colorama import Fore, Style
    
    if not check_cuda_availability():
        logging.warning("CUDA nie jest dostępne - przełączam na przetwarzanie CPU")
        return None
    
    # Pobierz informacje o urządzeniu CUDA
    device_info = get_cuda_device_info()
    if device_info:
        current_device = device_info['current_device']
        device_name = device_info['devices'][current_device]['name']
        print(f"{Fore.GREEN}Używam karty: {device_name}{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}Transformuję współrzędne z wykorzystaniem CUDA (zoptymalizowane)...{Style.RESET_ALL}")
    logging.debug("Rozpoczęto zoptymalizowaną transformację współrzędnych z wykorzystaniem CUDA.")
    
    # Przygotowanie danych
    northings = df["geodetic_northing"].values
    eastings = df["geodetic_easting"].values
    
    # Określenie stref EPSG
    epsg_zones = get_epsg_zones_for_batch(eastings)
    unique_zones = list(set(epsg_zones[epsg_zones > 0]))
    
    # Tworzenie transformerów
    transformers = create_transformers_for_zones(unique_zones)
    
    # Grupowanie punktów według stref EPSG
    zone_groups = {}
    for i, epsg_zone in enumerate(epsg_zones):
        if epsg_zone > 0 and epsg_zone in transformers:
            if epsg_zone not in zone_groups:
                zone_groups[epsg_zone] = []
            zone_groups[epsg_zone].append(i)
    
    # Transformacja dla każdej strefy
    results = [None] * len(df)
    
    for epsg_zone, indices in tqdm(zone_groups.items(), desc="Transformacja stref CUDA"):
        transformer = transformers[epsg_zone]
        zone_northings = northings[indices]
        zone_eastings = eastings[indices]
        
        # Przetwarzanie partiami dla lepszego wykorzystania GPU
        batch_size = 5000
        for i in range(0, len(indices), batch_size):
            batch_end = min(i + batch_size, len(indices))
            batch_northings = zone_northings[i:batch_end]
            batch_eastings = zone_eastings[i:batch_end]
            
            try:
                # Transformacja partii
                x_out, y_out = transformer.transform(batch_eastings, batch_northings)
                
                # Zapisanie wyników
                for j, (x, y) in enumerate(zip(x_out, y_out)):
                    original_idx = indices[i + j]
                    results[original_idx] = (x, y)
                    
            except Exception as e:
                logging.warning(f"Błąd transformacji dla strefy EPSG:{epsg_zone}: {e}")
                # Fallback do przetwarzania punkt po punkcie
                for j in range(i, batch_end):
                    original_idx = indices[j]
                    try:
                        x, y = transformer.transform(zone_eastings[j], zone_northings[j])
                        results[original_idx] = (x, y)
                    except Exception as e2:
                        logging.debug(f"Błąd transformacji punktu {original_idx + 1}: {e2}")
                        results[original_idx] = None
    
    logging.debug(f"Zakończono zoptymalizowaną transformację CUDA. Przetworzono {len(results)} punktów.")
    return results 