# === Importowanie niezbędnych bibliotek ===
import os
from typing import Dict, List, Tuple, Optional
import pandas as pd
from pyproj import Transformer
import requests
from scipy.spatial import KDTree
from colorama import init, Fore, Style
import geopandas as gpd
from tqdm import tqdm

# ==============================================================================
# === KONFIGURACJA SKRYPTU ===
DEBUG_MODE = False
# ==============================================================================

init(autoreset=True)

# === Funkcje pomocnicze interfejsu użytkownika ===

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def display_welcome_screen():
    print(f"{Fore.GREEN}======================================")
    print(f"{Fore.GREEN}===           diffH v1.1          ===")
    print(f"{Fore.GREEN}======================================")
    if DEBUG_MODE:
        print(f"{Fore.MAGENTA}*** TRYB DEBUGOWANIA AKTYWNY ***")
    print(f"\n{Fore.WHITE}Instrukcja:")
    print("1. Przygotuj plik wejściowy z danymi w układzie PL-2000.")
    print("   Format: [id, x, y, h] lub [id, y, x, h] (separator: spacja, przecinek, średnik) lub plik Excel (xls/xlsx).")
    print("   Obsługiwane formaty: CSV, TXT, XLS, XLSX.")
    print("   UWAGA: Skrypt automatycznie wykryje strefę 2000 w pliku.")
    print("   Jeśli plik nie zawiera kolumny z numerami punktów (tylko 3 kolumny), program zapyta o prefiks i nada automatyczną numerację.")
    print("   Plik musi mieć dokładnie 3 lub 4 kolumny. W innym przypadku import zostanie przerwany.")
    print("2. Skrypt zapyta o ścieżkę do pliku i rodzaj porównania.")
    print("3. Wynik zostanie zapisany w pliku 'wynik.csv' oraz w bazie przestrzennej 'wynik.gpkg'.\n")

def get_user_choice() -> int:
    while True:
        print(f"\n{Fore.YELLOW}Wybierz rodzaj porównania:")
        print("[1] Porównaj plik wejściowy z drugim plikiem (w tym samym układzie)")
        print("[2] Porównaj plik wejściowy z danymi wysokościowymi z Geoportal.gov.pl")
        print("[3] Porównaj plik wejściowy z drugim plikiem ORAZ z Geoportal.gov.pl")
        try:
            choice = int(input("\nTwój wybór (1-3): "))
            if 1 <= choice <= 3:
                return choice
            print(f"{Fore.RED}Błąd: Wybierz liczbę od 1 do 3.")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.")

def get_file_path(prompt: str) -> str:
    while True:
        file_path = input(prompt)
        if os.path.exists(file_path):
            return file_path
        print(f"{Fore.RED}Błąd: Plik nie istnieje. Spróbuj ponownie.")

def get_max_distance() -> float:
    while True:
        try:
            distance_str = input(f"\n{Fore.YELLOW}Podaj maksymalną odległość wyszukiwania pary w metrach (np. 0.5)\n(Wpisz 0, aby pominąć ten warunek): {Style.RESET_ALL}")
            distance = float(distance_str.replace(',', '.'))
            if distance >= 0:
                return distance
            print(f"{Fore.RED}Błąd: Odległość nie może być ujemna.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.{Style.RESET_ALL}")

def ask_swap_xy(file_label: str) -> bool:
    while True:
        resp = input(f"Czy plik {file_label} ma zamienioną kolejność kolumn (Y,X zamiast X,Y)? [t/n]: ").strip().lower()
        if resp in ['t', 'tak', 'y', 'yes']:
            return True
        if resp in ['n', 'nie', 'no']:
            return False
        print("Wpisz 't' (tak) lub 'n' (nie).")

def get_geoportal_tolerance() -> float:
    while True:
        try:
            val = input(f"\n{Fore.YELLOW}Podaj dopuszczalną różnicę wysokości względem Geoportalu (w metrach, np. 0.2): {Style.RESET_ALL}")
            val = float(val.replace(',', '.'))
            if val >= 0:
                return val
            print(f"{Fore.RED}Błąd: Wartość nie może być ujemna.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.{Style.RESET_ALL}")

# === Funkcje przetwarzania danych geoprzestrzennych ===

def load_data(file_path: str, swap_xy: bool = False) -> Optional[pd.DataFrame]:
    print(f"Wczytuję plik: {file_path}")
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        def handle_columns(df):
            if len(df.columns) == 4:
                df.columns = ['id', 'x', 'y', 'h']
                return df
            elif len(df.columns) == 3:
                print(f"{Fore.YELLOW}Wykryto 3 kolumny (brak numeru punktu).")
                prefix = input("Podaj prefiks dla numeracji punktów (np. P): ").strip() or "P"
                df.columns = ['x', 'y', 'h']
                df.insert(0, 'id', [f"{prefix}_{i+1}" for i in range(len(df))])
                print(f"{Fore.GREEN}Dodano automatyczną numerację punktów z prefiksem '{prefix}'.")
                return df
            else:
                print(f"{Fore.RED}Błąd: Plik musi mieć dokładnie 3 lub 4 kolumny (wykryto: {len(df.columns)}). Import przerwany.")
                return None
        
        if file_ext in ['.xls', '.xlsx']:
            try:
                df = pd.read_excel(file_path, header=None, dtype=str, engine='openpyxl' if file_ext == '.xlsx' else None)
            except ImportError:
                print(f"{Fore.RED}Błąd: Do obsługi plików Excel wymagany jest pakiet openpyxl. Zainstaluj go poleceniem: pip install openpyxl")
                return None
            df = df.dropna(axis=1, how='all')
            df = handle_columns(df)
        else: # Obsługa plików CSV/TXT
            tried_separators = [';', ',', r'\s+']
            df = None
            for sep in tried_separators:
                try:
                    if DEBUG_MODE: 
                        print(f"[DEBUG] Próbuję separator: '{sep}' dla pliku {file_path}")
                    temp_df = pd.read_csv(file_path, sep=sep, header=None, on_bad_lines='skip', engine='python', dtype=str)
                    temp_df = temp_df.dropna(axis=1, how='all')
                    if len(temp_df.columns) > 1:
                        df = temp_df
                        sep_display = 'spacja/tab' if sep == r'\s+' else sep
                        print(f"{Fore.GREEN}Plik wczytany poprawnie (separator: '{sep_display}').")
                        break
                except Exception as ex:
                    if DEBUG_MODE:
                        print(f"[DEBUG] Błąd przy próbie separatora '{sep}': {ex}")
                    continue
            if df is None:
                print(f"{Fore.RED}Nie udało się rozpoznać separatora lub plik nie ma poprawnej struktury.")
                return None
            df = handle_columns(df)

        if df is None:
            return None

        if swap_xy:
            if DEBUG_MODE:
                print(f"[DEBUG] Zamieniam kolumny X i Y dla pliku {file_path}")
            df[['x', 'y']] = df[['y', 'x']]
        
        # Konwersja na typ numeryczny, bez zaokrąglania
        for col in ['x', 'y', 'h']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df.dropna(subset=['x', 'y', 'h'], inplace=True)
        print(f"Wczytano {len(df)} wierszy.")
        return df
    except Exception as e:
        print(f"{Fore.RED}Błąd podczas wczytywania pliku: {e}")
        return None

def has_easting_structure(coord: float) -> bool:
    try:
        coord_str = str(int(coord))
        return len(coord_str) == 7 and coord_str[0] in ['5', '6', '7', '8']
    except (ValueError, TypeError, IndexError):
        return False

def assign_geodetic_roles(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    if DEBUG_MODE:
        print(f"{Fore.MAGENTA}[DEBUG] Sprawdzam konwencję współrzędnych w pliku...{Style.RESET_ALL}")
    first_row = df.iloc[0]
    x_from_file, y_from_file = first_row['x'], first_row['y']
    if has_easting_structure(y_from_file):
        if DEBUG_MODE:
            print(f"{Fore.MAGENTA}[DEBUG] WYKRYTO: Kolumna 'y' ma strukturę Easting (układ geodezyjny X=N, Y=E).{Style.RESET_ALL}")
        df['geodetic_northing'] = df['x']
        df['geodetic_easting'] = df['y']
    elif has_easting_structure(x_from_file):
        if DEBUG_MODE:
            print(f"{Fore.MAGENTA}[DEBUG] WYKRYTO: Kolumna 'x' ma strukturę Easting (układ GIS X=E, Y=N).{Style.RESET_ALL}")
        df['geodetic_northing'] = df['y']
        df['geodetic_easting'] = df['x']
    else:
        if DEBUG_MODE:
            print(f"{Fore.YELLOW}[DEBUG-OSTRZEŻENIE] Nie można zidentyfikować Easting. Zakładam układ geodezyjny (X=N, Y=E).{Style.RESET_ALL}")
        df['geodetic_northing'] = df['x']
        df['geodetic_easting'] = df['y']
    return df

def get_source_epsg(easting_coordinate: float) -> Optional[int]:
    try:
        easting_str = str(int(easting_coordinate))
        if len(easting_str) == 7:
            first_digit = easting_str[0]
            epsg_mapping = {'5': 2176, '6': 2177, '7': 2178, '8': 2179}
            return epsg_mapping.get(first_digit)
    except (ValueError, TypeError, IndexError):
        return None
    return None

# --- USUNIĘTO FUNKCJĘ round_bradis_krylov ---

def transform_coordinates(df: pd.DataFrame) -> List[Tuple[float, float]]:
    transformed_points = []
    print(f"\n{Fore.CYAN}Transformuję współrzędne z PL-2000 do PL-1992 (EPSG:2180)...{Style.RESET_ALL}")
    
    # Użycie TQDM do stworzenia paska postępu
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Transformacja współrzędnych"):
        northing = row['geodetic_northing']
        easting = row['geodetic_easting']
        source_epsg = get_source_epsg(easting)
        if source_epsg is None:
            if DEBUG_MODE:
                print(f"[DEBUG] Nie można określić strefy EPSG dla ptk {row.id} (Easting={easting})")
            transformed_points.append((0.0, 0.0))
            continue
        
        transformer = Transformer.from_crs(f"EPSG:{source_epsg}", "EPSG:2180")
        x_gis_easting, y_gis_northing = transformer.transform(northing, easting)
        
        if DEBUG_MODE:
            print(f"[DEBUG] {row.id}: ({northing}, {easting}) EPSG:{source_epsg} -> ({x_gis_easting}, {y_gis_northing}) EPSG:2180")
        transformed_points.append((x_gis_easting, y_gis_northing))
        
    return transformed_points

def get_geoportal_heights(transformed_points: List[Tuple[float, float]]) -> Dict[str, float]:
    print(f"\n{Fore.CYAN}Pobieranie danych wysokościowych z Geoportalu...{Style.RESET_ALL}")
    valid_points = [p for p in transformed_points if p != (0.0, 0.0)]
    if not valid_points:
        print(f"{Fore.YELLOW}Brak poprawnych punktów do wysłania do API Geoportalu.")
        return {}
    
    geoportal_heights = {}
    batch_size = 300
    
    # Użycie TQDM do stworzenia paska postępu dla paczek
    for start in tqdm(range(0, len(valid_points), batch_size), desc="Pobieranie z Geoportalu"):
        batch = valid_points[start:start+batch_size]
        # Formatowanie do 2 miejsc po przecinku jest tutaj KLUCZOWE dla API
        point_strings = [f"{easting:.2f} {northing:.2f}" for easting, northing in batch]
        list_parameter = ",".join(point_strings)
        url = f"https://services.gugik.gov.pl/nmt/?request=GetHByPointList&list={list_parameter}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            if response.text.strip():
                results = response.text.strip().split(',')
                for point_result in results:
                    parts = point_result.split()
                    if len(parts) == 3:
                        easting_api, northing_api, h_api = parts
                        # Klucz musi być w tym samym formacie co zapytanie
                        key = f"{float(easting_api):.2f} {float(northing_api):.2f}"
                        geoportal_heights[key] = float(h_api)
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Błąd podczas komunikacji z Geoportalem (paczka {start//batch_size + 1}): {e}")
            
    return geoportal_heights

def export_to_geopackage(results_df: pd.DataFrame, input_df: pd.DataFrame, gpkg_path: str, layer_name: str = "wyniki"):
    if results_df.empty:
        print(f"{Fore.YELLOW}Brak danych do zapisu w GeoPackage.")
        return

    source_epsg = None
    if not input_df.empty:
        first_point_easting = input_df.iloc[0]['geodetic_easting']
        source_epsg = get_source_epsg(first_point_easting)

    if source_epsg is None:
        print(f"{Fore.RED}Błąd: Nie można było ustalić źródłowego układu współrzędnych (EPSG). Plik GeoPackage nie zostanie utworzony.")
        return

    print(f"Wykryto układ współrzędnych dla pliku GeoPackage: EPSG:{source_epsg}")

    try:
        df_geo = results_df.copy()
        geometry = gpd.points_from_xy(df_geo['y_odniesienia'], df_geo['x_odniesienia'])
        gdf = gpd.GeoDataFrame(df_geo, geometry=geometry, crs=f"EPSG:{source_epsg}")
        gdf.to_file(gpkg_path, layer=layer_name, driver="GPKG")
        print(f"{Fore.GREEN}Wyniki zostały poprawnie zapisane w bazie przestrzennej: {os.path.abspath(gpkg_path)}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Wystąpił błąd podczas tworzenia pliku GeoPackage: {e}")

def process_data(input_df: pd.DataFrame, 
                comparison_df: Optional[pd.DataFrame], 
                use_geoportal: bool,
                max_distance: float,
                geoportal_tolerance: Optional[float] = None) -> pd.DataFrame:
    results = []
    input_df = assign_geodetic_roles(input_df)
    
    geoportal_heights, transformed_points = {}, []
    if use_geoportal:
        transformed_points = transform_coordinates(input_df)
        if transformed_points:
            geoportal_heights = get_geoportal_heights(transformed_points)
            
    tree_comparison = None
    if comparison_df is not None:
        print(f"\n{Fore.CYAN}Przygotowuję zaawansowane parowanie punktów...{Style.RESET_ALL}")
        comparison_points = comparison_df[['x', 'y']].values
        tree_comparison = KDTree(comparison_points)
        print(f"{Fore.GREEN}Indeksy do porównania gotowe.{Style.RESET_ALL}")
        
    paired_count = 0
    
    # Użycie TQDM do głównej pętli przetwarzania
    for i, (_, point) in enumerate(tqdm(input_df.iterrows(), total=len(input_df), desc="Przetwarzanie punktów")):
        row_data = {
            'id_odniesienia': point['id'],
            'x_odniesienia': point['x'],
            'y_odniesienia': point['y'],
            'h_odniesienia': point['h'],
        }
        
        if comparison_df is not None and tree_comparison is not None:
            distance, nearest_idx = tree_comparison.query([point['x'], point['y']])
            if (max_distance == 0) or (distance <= max_distance):
                # Pomijamy weryfikację wzajemności dla uproszczenia, jest to kosztowne obliczeniowo
                nearest_in_comp_point = comparison_df.iloc[nearest_idx]
                row_data['id_porownania'] = nearest_in_comp_point['id']
                row_data['x_porownania'] = nearest_in_comp_point['x']
                row_data['y_porownania'] = nearest_in_comp_point['y']
                row_data['h_porownania'] = nearest_in_comp_point['h']
                try:
                    row_data['diff_h'] = float(point['h']) - float(nearest_in_comp_point['h'])
                except (ValueError, TypeError):
                    row_data['diff_h'] = 'brak_danych'
                row_data['odleglosc_pary'] = distance
                paired_count += 1
                
        if use_geoportal and transformed_points:
            easting_2180, northing_2180 = transformed_points[i]
            # Klucz musi być w tym samym formacie co w zapytaniu
            lookup_key = f"{easting_2180:.2f} {northing_2180:.2f}"
            height = geoportal_heights.get(lookup_key, "brak_danych")
            row_data['geoportal_h'] = str(height)
            
            if height != 'brak_danych' and pd.notnull(point['h']):
                try:
                    diff_h_geoportal = float(point['h']) - float(height)
                    row_data['diff_h_geoportal'] = diff_h_geoportal
                    if geoportal_tolerance is not None:
                        row_data['osiaga_dokladnosc'] = 'Tak' if abs(diff_h_geoportal) <= geoportal_tolerance else 'Nie'
                except (ValueError, TypeError):
                    row_data['diff_h_geoportal'] = 'brak_danych'
            else:
                row_data['diff_h_geoportal'] = 'brak_danych'
                
        results.append(row_data)

    if comparison_df is not None:
        print(f"{Fore.GREEN}Znaleziono i połączono {paired_count} par punktów.{Style.RESET_ALL}")
        
    results_df = pd.DataFrame(results)
    
    # Sortowanie i porządkowanie kolumn
    if use_geoportal and 'diff_h_geoportal' in results_df.columns:
        results_df['__abs_diff_h_geoportal'] = pd.to_numeric(results_df['diff_h_geoportal'], errors='coerce').abs()
        results_df = results_df.sort_values(by='__abs_diff_h_geoportal', ascending=False).drop(columns=['__abs_diff_h_geoportal'])
    
    # Ustalenie finalnej kolejności kolumn
    final_cols = [
        'id_odniesienia', 'x_odniesienia', 'y_odniesienia', 'h_odniesienia',
        'diff_h_geoportal', 'geoportal_h', 'osiaga_dokladnosc',
        'id_porownania', 'x_porownania', 'y_porownania', 'h_porownania',
        'diff_h', 'odleglosc_pary'
    ]
    
    # Bierzemy tylko te kolumny, które istnieją w DataFrame
    existing_cols = [col for col in final_cols if col in results_df.columns]
    return results_df[existing_cols]

# === Główna funkcja programu ===
def main():
    clear_screen()
    display_welcome_screen()
    choice = get_user_choice()
    max_distance = 0.0
    if choice in [1, 3]:
        max_distance = get_max_distance()
    input_file = get_file_path("\nPodaj ścieżkę do pliku wejściowego: ")
    swap_input = ask_swap_xy("wejściowego")
    comparison_file = None
    swap_comparison = False
    geoportal_tolerance = None
    if choice in [1, 3]:
        comparison_file = get_file_path("Podaj ścieżkę do pliku porównawczego: ")
        swap_comparison = ask_swap_xy("porównawczego")
    if choice in [2, 3]:
        geoportal_tolerance = get_geoportal_tolerance()
        
    print(f"\n{Fore.CYAN}--- Wczytywanie danych ---{Style.RESET_ALL}")
    input_df = load_data(input_file, swap_input)
    if input_df is None or input_df.empty:
        print(f"{Fore.RED}Nie udało się wczytać danych wejściowych. Zamykanie programu.")
        return
        
    comparison_df = None
    if comparison_file:
        comparison_df = load_data(comparison_file, swap_comparison)
        
    use_geoportal = choice in [2, 3]
    results_df = process_data(input_df, comparison_df, use_geoportal, max_distance, geoportal_tolerance)
    
    if not results_df.empty:
        print(f"\n{Fore.CYAN}--- Zapisywanie wyników ---{Style.RESET_ALL}")
        output_csv_file = 'wynik.csv'
        results_df.to_csv(
            output_csv_file, 
            sep=';', 
            index=False, 
            float_format='%.2f', # To jest najlepsze miejsce na zaokrąglenie dla użytkownika
            na_rep='brak_danych'
        )
        print(f"{Fore.GREEN}Wyniki tabelaryczne zostały zapisane w pliku: {os.path.abspath(output_csv_file)}{Style.RESET_ALL}")

        output_gpkg_file = 'wynik.gpkg'
        export_to_geopackage(results_df, input_df, output_gpkg_file)
        
        print(f"\n{Fore.GREEN}Zakończono przetwarzanie pomyślnie!")
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
        print("\nNaciśnij Enter, aby zakończyć...")
        input()