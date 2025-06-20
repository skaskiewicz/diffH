import os
import sys
import time
from typing import Dict, List, Tuple, Optional
import pandas as pd
from pyproj import Transformer
import requests
from scipy.spatial import KDTree
from colorama import init, Fore, Style

# ==============================================================================
# === TRYB DEBUGOWANIA ===
DEBUG_MODE = False
# ==============================================================================

init(autoreset=True)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def display_welcome_screen():
    print(f"{Fore.CYAN}======================================")
    print("===      Geo-Komparator 2000       ===")
    print("======================================")
    if DEBUG_MODE:
        print(f"{Fore.MAGENTA}*** TRYB DEBUGOWANIA AKTYWNY ***")
    print(f"\n{Fore.WHITE}Instrukcja:")
    print("1. Przygotuj plik wejściowy z danymi w układzie PL-2000.")
    print("   Format: [id, x, y, h] (separator: spacja, przecinek lub średnik).")
    print("   UWAGA: Skrypt automatycznie wykryje konwencję (geodezyjną lub GIS) w pliku.")
    print("2. Skrypt zapyta o ścieżkę do pliku i rodzaj porównania.")
    print("3. Wynik zostanie zapisany w pliku 'wynik.csv'.\n")

def get_user_choice() -> int:
    while True:
        print(f"\n{Fore.YELLOW}Wybierz rodzaj porównania:")
        print("[1] Porównaj plik wejściowy z drugim plikiem (w tym samym układzie)")
        print("[2] Porównaj plik wejściowy z danymi wysokościowymi z Geoportal.gov.pl")
        print("[3] Porównaj plik wejściowy z drugim plikiem ORAZ z Geoportal.gov.pl")
        try:
            choice = int(input("\nTwój wybór (1-3): "))
            if 1 <= choice <= 3: return choice
            print(f"{Fore.RED}Błąd: Wybierz liczbę od 1 do 3.")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.")

def get_file_path(prompt: str) -> str:
    while True:
        file_path = input(prompt)
        if os.path.exists(file_path): return file_path
        print(f"{Fore.RED}Błąd: Plik nie istnieje. Spróbuj ponownie.")

def load_data(file_path: str) -> Optional[pd.DataFrame]:
    print(f"Wczytuję plik: {file_path}")
    try:
        for sep in [';', ',', r'\s+']:
            try:
                df = pd.read_csv(file_path, sep=sep, header=None, on_bad_lines='skip', engine='python', dtype=str)
                if len(df.columns) >= 4:
                    df = df.iloc[:, :4]
                    df.columns = ['id', 'x', 'y', 'h']
                    for col in ['x', 'y', 'h']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    df.dropna(subset=['x', 'y', 'h'], inplace=True)
                    sep_display = 'spacja/tab' if sep == r'\s+' else sep
                    print(f"{Fore.GREEN}Plik wczytany poprawnie (separator: '{sep_display}', {len(df)} wierszy).")
                    return df
            except Exception:
                continue
        raise ValueError("Nie udało się zinterpretować pliku.")
    except Exception as e:
        print(f"{Fore.RED}Błąd podczas wczytywania pliku: {e}")
        return None

def has_easting_structure(coord: float) -> bool:
    """Checks if a coordinate has the structure of an Easting in PL-2000."""
    try:
        coord_str = str(int(coord))
        return len(coord_str) == 7 and coord_str[0] in ['5', '6', '7', '8']
    except (ValueError, TypeError, IndexError):
        return False

def assign_geodetic_roles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assigns geodetic roles (Northing, Easting) to columns based on their values.
    Polska konwencja geodezyjna: X=Northing, Y=Easting.
    Konwencja GIS: X=Easting, Y=Northing.
    """
    if df.empty: return df
    if DEBUG_MODE: print(f"{Fore.MAGENTA}[DEBUG] Sprawdzam konwencję współrzędnych w pliku...{Style.RESET_ALL}")

    first_row = df.iloc[0]
    x_from_file, y_from_file = first_row['x'], first_row['y']

    if has_easting_structure(y_from_file):
        if DEBUG_MODE: print(f"{Fore.MAGENTA}[DEBUG] WYKRYTO: Kolumna 'y' z pliku ma strukturę Easting. Przyjmuję, że plik ma układ geodezyjny (X=Northing, Y=Easting).{Style.RESET_ALL}")
        df['geodetic_northing'] = df['x']
        df['geodetic_easting'] = df['y']
    elif has_easting_structure(x_from_file):
        if DEBUG_MODE: print(f"{Fore.MAGENTA}[DEBUG] WYKRYTO: Kolumna 'x' z pliku ma strukturę Easting. Przyjmuję, że plik ma układ GIS (X=Easting, Y=Northing).{Style.RESET_ALL}")
        df['geodetic_northing'] = df['y']
        df['geodetic_easting'] = df['x']
    else:
        if DEBUG_MODE: print(f"{Fore.YELLOW}[DEBUG-OSTRZEŻENIE] Nie można jednoznacznie zidentyfikować struktury Easting. Zakładam domyślny układ geodezyjny (X=Northing, Y=Easting).{Style.RESET_ALL}")
        df['geodetic_northing'] = df['x']
        df['geodetic_easting'] = df['y']
    return df

def get_source_epsg(easting_coordinate: float) -> Optional[int]:
    """Determine EPSG code based on Easting coordinate."""
    try:
        easting_str = str(int(easting_coordinate))
        if len(easting_str) == 7:
            first_digit = easting_str[0]
            epsg_mapping = {'5': 2176, '6': 2177, '7': 2178, '8': 2179}
            return epsg_mapping.get(first_digit)
    except (ValueError, TypeError, IndexError): return None
    return None

def transform_coordinates(df: pd.DataFrame) -> List[Tuple[float, float]]:
    """Transform coordinates from PL-2000 to EPSG:2180."""
    transformed_points = []
    print(f"\n{Fore.CYAN}Transformuję współrzędne z PL-2000 do PL-1992 (EPSG:2180)...{Style.RESET_ALL}")

    for _, row in df.iterrows():
        northing = row['geodetic_northing']
        easting = row['geodetic_easting']
        source_epsg = get_source_epsg(easting)
        
        if source_epsg is None:
            if DEBUG_MODE: print(f"{Fore.YELLOW}[DEBUG-OSTRZEŻENIE] Nie można określić strefy dla ptk {row.id} (Easting={easting}). Pomijam.{Style.RESET_ALL}")
            transformed_points.append((0.0, 0.0)) 
            continue

        if DEBUG_MODE:
            print(f"{Fore.MAGENTA}--- Debug Transformacji dla punktu: {row.id} ---")
            print(f"  Wejście (PL-2000): Northing={northing:.2f}, Easting={easting:.2f} -> Strefa EPSG:{source_epsg}")

        transformer = Transformer.from_crs(f"EPSG:{source_epsg}", "EPSG:2180")
        
        # pyproj dla PL-2000 (EPSG:217x) oczekuje (Northing, Easting)
        # pyproj dla PL-1992 (EPSG:2180) zwraca w standardzie GIS (Easting, Northing)
        x_gis_easting, y_gis_northing = transformer.transform(northing, easting)
        
        if DEBUG_MODE:
            print(f"  Wynik (PL-1992, standard GIS): X (Easting)={x_gis_easting:.2f}, Y (Northing)={y_gis_northing:.2f}{Style.RESET_ALL}")
            
        transformed_points.append((x_gis_easting, y_gis_northing))
    
    print(f"{Fore.GREEN}Transformacja zakończona.{Style.RESET_ALL}")
    return transformed_points

def get_geoportal_heights(transformed_points: List[Tuple[float, float]]) -> Dict[str, float]:
    print(f"\n{Fore.CYAN}Pobieranie danych wysokościowych z Geoportalu...{Style.RESET_ALL}")
    valid_points = [p for p in transformed_points if p != (0.0, 0.0)]
    if not valid_points:
        print(f"{Fore.YELLOW}Brak poprawnych punktów do wysłania do API Geoportalu.")
        return {}
    
    # API Geoportalu dla PL-1992 oczekuje współrzędnych w kolejności (Easting, Northing)
    point_strings = [f"{easting:.2f} {northing:.2f}" for easting, northing in valid_points]
    list_parameter = ",".join(point_strings)
    url = f"https://services.gugik.gov.pl/nmt/?request=GetHByPointList&list={list_parameter}"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        geoportal_heights = {}
        if response.text.strip():
            results = response.text.strip().split(',')
            for point_result in results:
                parts = point_result.split()
                if len(parts) == 3:
                    easting_api, northing_api, h_api = parts
                    key = f"{float(easting_api):.2f} {float(northing_api):.2f}"
                    geoportal_heights[key] = float(h_api)
        print(f"{Fore.GREEN}Pobrano dane wysokościowe dla {len(geoportal_heights)} punktów.{Style.RESET_ALL}")
        return geoportal_heights
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Błąd podczas komunikacji z Geoportalem: {e}")
        return {}

def find_nearest_point(source_point: pd.Series, tree: KDTree, comparison_df: pd.DataFrame) -> pd.Series:
    # Porównanie plików odbywa się na oryginalnych współrzędnych z pliku wejściowego
    _, index = tree.query([source_point['x_oryginal'], source_point['y_oryginal']])
    return comparison_df.iloc[index]

def process_data(input_df: pd.DataFrame, 
                comparison_df: Optional[pd.DataFrame], 
                use_geoportal: bool) -> pd.DataFrame:
    results = []
    total_points = len(input_df)
    
    input_df['x_oryginal'] = input_df['x']
    input_df['y_oryginal'] = input_df['y']
    
    input_df = assign_geodetic_roles(input_df)
    if comparison_df is not None:
        comparison_df['x_oryginal'] = comparison_df['x']
        comparison_df['y_oryginal'] = comparison_df['y']
        comparison_df = assign_geodetic_roles(comparison_df.copy())

    geoportal_heights, transformed_points = {}, []
    if use_geoportal:
        transformed_points = transform_coordinates(input_df)
        if transformed_points:
            geoportal_heights = get_geoportal_heights(transformed_points)
        
    comparison_tree = None
    if comparison_df is not None:
        print(f"\n{Fore.CYAN}Buduję indeks punktów do porównania (KDTree)...{Style.RESET_ALL}")
        comparison_points = comparison_df[['x_oryginal', 'y_oryginal']].values
        comparison_tree = KDTree(comparison_points)
        print(f"{Fore.GREEN}Indeks zbudowany.{Style.RESET_ALL}")

    print(f"\n{Fore.CYAN}Przetwarzam punkty...{Style.RESET_ALL}")
    for i, (_, point) in enumerate(input_df.iterrows()):
        # ZMIANA 1: Używamy 'h' zamiast nieistniejącego 'h_oryginal'
        row_data = {
            'id_odniesienia': point['id'],
            'x_odniesienia': point['x_oryginal'],
            'y_odniesienia': point['y_oryginal'],
            'h_odniesienia': point['h'], 
        }
        
        if comparison_df is not None and comparison_tree is not None:
            nearest = find_nearest_point(point, comparison_tree, comparison_df)
            row_data['id_porownania'] = nearest['id']
            row_data['x_porownania'] = nearest['x_oryginal']
            row_data['y_porownania'] = nearest['y_oryginal']
            # ZMIANA 2: Używamy 'h' również tutaj
            row_data['h_porownania'] = nearest['h']
        
        if use_geoportal and transformed_points:
            easting_2180, northing_2180 = transformed_points[i]
            lookup_key = f"{easting_2180:.2f} {northing_2180:.2f}"
            height = geoportal_heights.get(lookup_key, "brak_danych")
            row_data['geoportal_h'] = str(height)
        
        results.append(row_data)
        progress = (i + 1) / total_points
        bar_length = 40
        block = int(round(bar_length * progress))
        text = f"\rPrzetworzono {i+1}/{total_points} punktów: [{'#' * block}{'-' * (bar_length - block)}] {int(progress * 100)}%"
        sys.stdout.write(text)
        sys.stdout.flush()
    print("\n")
    return pd.DataFrame(results)

def main():
    clear_screen()
    display_welcome_screen()
    choice = get_user_choice()
    input_file = get_file_path("\nPodaj ścieżkę do pliku wejściowego: ")
    comparison_file = get_file_path("Podaj ścieżkę do pliku porównawczego: ") if choice in [1, 3] else None
    
    print(f"\n{Fore.CYAN}--- Wczytywanie danych ---{Style.RESET_ALL}")
    input_df = load_data(input_file)
    if input_df is None or input_df.empty:
        print(f"{Fore.RED}Nie udało się wczytać danych wejściowych. Zamykanie programu.")
        return
    comparison_df = load_data(comparison_file) if comparison_file else None
    
    use_geoportal = choice in [2, 3]
    results_df = process_data(input_df, comparison_df, use_geoportal)
    
    if not results_df.empty:
        output_file = 'wynik.csv'
        print(f"\n{Fore.CYAN}--- Zapisywanie wyników ---{Style.RESET_ALL}")
        
        output_columns = ['id_odniesienia', 'x_odniesienia', 'y_odniesienia', 'h_odniesienia']
        if 'id_porownania' in results_df.columns:
            output_columns.extend(['id_porownania', 'x_porownania', 'y_porownania', 'h_porownania'])
        if 'geoportal_h' in results_df.columns:
            output_columns.append('geoportal_h')
        
        results_df.to_csv(
            output_file, 
            sep=';', 
            index=False, 
            columns=output_columns,
            float_format='%.2f',
            na_rep='brak_danych'
        )
        
        print(f"\n{Fore.GREEN}Zakończono przetwarzanie pomyślnie!")
        print(f"Wyniki zostały zapisane w pliku: {os.path.abspath(output_file)}{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}Nie wygenerowano żadnych wyników.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Przerwano działanie programu.{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Wystąpił nieoczekiwany błąd globalny: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\nNaciśnij Enter, aby zakończyć...")
        input()