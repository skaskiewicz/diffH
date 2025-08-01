#!/usr/bin/env python3
"""
Test script do sprawdzenia wykrywania CUDA i metod transformacji
"""

import sys
import os
from colorama import Fore, Style
import warnings

# Dodaj katalog src do ścieżki Pythona
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)



# Ignoruj ostrzeżenie z CuPy o braku CUDA_PATH, jeśli i tak działa
warnings.filterwarnings("ignore", category=UserWarning, message="CUDA path could not be detected.*")

def test_cuda_detection():
    """Test wykrywania CUDA"""
    from src.core.coordinate_transform import get_transformation_method_info

    print(f"{Fore.CYAN}=== Test wykrywania CUDA ==={Style.RESET_ALL}")
    
    # Sprawdź metodę transformacji
    method = get_transformation_method_info()
    print(f"Metoda transformacji: {method}")
    
    # Sprawdź dostępność CUDA
    try:
        from src.core.cuda_transform import check_cuda_availability, get_cuda_device_info
        cuda_available = check_cuda_availability()
        print(f"CUDA dostępne: {cuda_available}")
        
        if cuda_available:
            print(f"{Fore.GREEN}✓ CUDA jest dostępne i gotowe do użycia{Style.RESET_ALL}")
            
            # Pokaż szczegółowe informacje o urządzeniach
            device_info = get_cuda_device_info()
            if device_info:
                print(f"\n{Fore.CYAN}=== Informacje o urządzeniach CUDA ==={Style.RESET_ALL}")
                print(f"Liczba urządzeń: {device_info['device_count']}")
                print(f"Aktywne urządzenie: {device_info['current_device']}")
                
                for device in device_info['devices']:
                    status = "✓ Gotowe" if device['available'] else "⚠ Za mało pamięci"
                    color = Fore.GREEN if device['available'] else Fore.YELLOW
                    print(f"\n{color}Urządzenie {device['id']}: {device['name']}{Style.RESET_ALL}")
                    print(f"  Compute Capability: {device['compute_capability']}")
                    print(f"  Pamięć: {device['memory_gb']:.2f} GB")
                    print(f"  Status: {color}{status}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠ CUDA nie jest dostępne - używany będzie CPU{Style.RESET_ALL}")
            
    except ImportError as e:
        print(f"{Fore.RED}✗ Błąd importu modułu CUDA: {e}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Zainstaluj CuPy: pip install cupy-cuda11x (Windows) lub cupy-cuda12x (Linux){Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}✗ Błąd sprawdzania CUDA: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    test_cuda_detection() 