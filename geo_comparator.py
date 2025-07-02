# === Importowanie niezbędnych bibliotek ===
import os
from typing import Dict, List, Tuple, Optional
import pandas as pd
from pyproj import Transformer
from pyproj.exceptions import CRSError
import requests
from scipy.spatial import KDTree
from colorama import init, Fore, Style
import geopandas as gpd
from tqdm import tqdm
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
import traceback
import math

# ==============================================================================
# === KONFIGURACJA SKRYPTU ===
DEBUG_MODE = True
CONCURRENT_API_REQUESTS = 10
# ======================================================================

init(autoreset=True)

# === Funkcje pomocnicze interfejsu użytkownika ===
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def display_welcome_screen():
    print(f"{Fore.GREEN}======================================")
    print(f"{Fore.GREEN}===           diffH               ===")
    print(f"{Fore.GREEN}======================================")
    if DEBUG_MODE:
        print(f"{Fore.MAGENTA}*** TRYB DEBUGOWANIA AKTYWNY ***")
    print(f"\n{Fore.WHITE}Instrukcja:\n1. Przygotuj plik wejściowy (CSV, TXT, XLS, XLSX) z danymi w układzie PL-2000.\n   Format: [id, x, y, h] lub [x, y, h]. Skrypt automatycznie wykryje strefę.\n2. Postępuj zgodnie z instrukcjami na ekranie.\n3. Wynik zostanie zapisany w plikach '{'wynik.csv'}' oraz '{'wynik.gpkg'}'.\n")

def get_user_choice() -> int:
    while True:
        print(f"\n{Fore.YELLOW}Wybierz rodzaj porównania:\n[1] Porównaj plik wejściowy z drugim plikiem\n[2] Porównaj plik wejściowy z danymi z Geoportal.gov.pl\n[3] Porównaj plik wejściowy z drugim plikiem ORAZ z Geoportal.gov.pl")
        try:
            choice = int(input("\nTwój wybór (1-3): "))
            if 1 <= choice <= 3:
                return choice
            print(f"{Fore.RED}Błąd: Wybierz liczbę od 1 do 3.")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.")

def get_file_path(prompt: str) -> str:
    while True:
        file_path = input(prompt).strip()
        # Usuń tylko parę cudzysłowów lub apostrofów na początku i końcu
        if (file_path.startswith('"') and file_path.endswith('"')) or (file_path.startswith("'") and file_path.endswith("'")):
            file_path = file_path[1:-1]
        if os.path.exists(file_path):
            return file_path
        print(f"{Fore.RED}Błąd: Plik nie istnieje. Spróbuj ponownie.")

def get_max_distance() -> float:
    default_distance = 15.0
    while True:
        try:
            prompt = (f"\n{Fore.YELLOW}Podaj maksymalną odległość wyszukiwania pary w metrach (np. 0.5)\n"
                f"(Wpisz 0, aby pominąć ten warunek, domyślnie {default_distance} m): {Style.RESET_ALL}")
            distance_str = input(prompt)
            if not distance_str.strip():
                print(f"{Fore.CYAN}Przyjęto domyślną wartość: {default_distance} m{Style.RESET_ALL}")
                return default_distance
            distance = float(distance_str.replace(',', '.'))
            if distance >= 0:
                return distance
            print(f"{Fore.RED}Błąd: Odległość nie może być ujemna.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.{Style.RESET_ALL}")

def ask_swap_xy(file_label: str) -> bool:
    default = 'n'
    while True:
        resp = input(f"Czy plik {file_label} ma zamienioną kolejność kolumn (Y,X zamiast X,Y)? [t/n] (domyślnie: n): ").strip().lower()
        if not resp:
            print(f"{Fore.CYAN}Przyjęto domyślną odpowiedź: {default}{Style.RESET_ALL}")
            return False
        if resp in ['t', 'tak', 'y', 'yes']:
            return True
        if resp in ['n', 'nie', 'no']:
            return False
        print("Wpisz 't' (tak) lub 'n' (nie).")

def get_geoportal_tolerance() -> float:
    default_tolerance = 0.2
    while True:
        try:
            prompt = (f"\n{Fore.YELLOW}Podaj dopuszczalną różnicę wysokości względem Geoportalu (w metrach, np. 0.2) "
                f"(domyślnie: {default_tolerance}): {Style.RESET_ALL}")
            val = input(prompt)
            if not val.strip():
                print(f"{Fore.CYAN}Przyjęto domyślną wartość: {default_tolerance}{Style.RESET_ALL}")
                return default_tolerance
            val = float(val.replace(',', '.'))
            if val >= 0:
                return val
            print(f"{Fore.RED}Błąd: Wartość nie może być ujemna.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.{Style.RESET_ALL}")

# === Funkcje wczytywania danych ===
def load_data(file_path: str, swap_xy: bool = False) -> Optional[pd.DataFrame]:
    print(f"Wczytuję plik: {file_path}")
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        def handle_columns(df):
            if len(df.columns) >= 4:
                if len(df.columns) > 4:
                    print(f"{Fore.YELLOW}Wykryto więcej niż 4 kolumny. Importowane będą tylko pierwsze 4 kolumny.")
                    df = df.iloc[:, :4]
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
                print(f"{Fore.RED}Błąd: Plik musi mieć dokładnie 3, 4 lub więcej kolumn (wykryto: {len(df.columns)}). Import przerwany.")
                return None
        if file_ext in ['.xls', '.xlsx']:
            try:
                df = pd.read_excel(file_path, header=None, dtype=str, engine='openpyxl' if file_ext == '.xlsx' else None)
            except ImportError:
                print(f"{Fore.RED}Błąd: Do obsługi plików Excel wymagany jest pakiet openpyxl. Zainstaluj go poleceniem: pip install openpyxl")
                return None
            df = df.dropna(axis=1, how='all')
            df = handle_columns(df)
        else:
            tried_separators = [';', ',', r'\s+']
            df = None
            for sep in tried_separators:
                try:
                    temp_df = pd.read_csv(file_path, sep=sep, header=None, on_bad_lines='skip', engine='python', dtype=str)
                    temp_df = temp_df.dropna(axis=1, how='all')
                    if len(temp_df.columns) > 1:
                        df = temp_df
                        sep_display = 'spacja/tab' if sep == r'\s+' else sep
                        print(f"{Fore.GREEN}Plik wczytany poprawnie (separator: '{sep_display}').")
                        break
                except Exception:
                    continue
            if df is None:
                print(f"{Fore.RED}Nie udało się rozpoznać separatora lub plik nie ma poprawnej struktury.")
                return None
            df = handle_columns(df)
        if df is None:
            return None
        if swap_xy:
            df[['x', 'y']] = df[['y', 'x']]
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
    first_row = df.iloc[0]
    if has_easting_structure(first_row['y']):
        df['geodetic_northing'], df['geodetic_easting'] = df['x'], df['y']
    elif has_easting_structure(first_row['x']):
        df['geodetic_northing'], df['geodetic_easting'] = df['y'], df['x']
    else:
        df['geodetic_northing'], df['geodetic_easting'] = df['x'], df['y']
    return df

def get_source_epsg(easting_coordinate: float) -> Optional[int]:
    try:
        easting_str = str(int(easting_coordinate))
        if len(easting_str) == 7:
            return {'5': 2176, '6': 2177, '7': 2178, '8': 2179}.get(easting_str[0])
    except (ValueError, TypeError, IndexError):
        return None
    return None

# === NOWE FUNKCJE ROBOCZE DLA RÓWNOLEGŁOŚCI ===
def worker_transform(point_data_with_index: Tuple[int, float, float]) -> Optional[Tuple[float, float]]:
    """
    Worker function for parallel coordinate transformation.
    Logs detailed information in DEBUG_MODE.
    """
    log_file = "transform_log.txt"
    index, northing, easting = point_data_with_index
    
    source_epsg = get_source_epsg(easting)
    if source_epsg is None:
        if DEBUG_MODE:
            message = f"Punkt {index+1}: BŁĄD - Nie można określić strefy EPSG dla easting={easting}. Współrzędne (N, E): ({northing}, {easting})"
            log_to_file(log_file, message)
        return None
    try:
        transformer = Transformer.from_crs(f"EPSG:{source_epsg}", "EPSG:2180", always_xy=True)
        x_out, y_out = transformer.transform(easting, northing)
        if DEBUG_MODE:
            message = f"Punkt {index+1}: OK. Oryginalne (N, E)=({northing}, {easting}) -> Transformowane (X, Y)=({x_out:.2f}, {y_out:.2f})"
            log_to_file(log_file, message)
        return x_out, y_out
    except CRSError as e:
        if DEBUG_MODE:
            message = f"Punkt {index+1}: BŁĄD transformacji (CRSError) dla (N, E)=({northing}, {easting}). Błąd: {e}"
            log_to_file(log_file, message)
        return None

# === LOGOWANIE DO PLIKÓW ===
def log_to_file(filename: str, message: str):
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(message + '\n')

# Flagi do jednorazowego logowania adresu URL i odpowiedzi Geoportalu
_geoportal_url_logged = False
_geoportal_response_logged = False

def fetch_height_batch(batch: List[Tuple[float, float]]) -> Dict[str, float]:
    if not batch:
        return {}
    log_file = "geoportal_log.txt"
    # Usuwanie duplikatów z paczki (API zwraca wysokość dla każdej współrzędnej, ale klucz w słowniku bywa nadpisany)
    unique_batch = list(dict.fromkeys(batch))
    point_strings = [f"{northing:.2f} {easting:.2f}" for easting, northing in unique_batch]
    list_parameter = ",".join(point_strings)
    url = f"https://services.gugik.gov.pl/nmt/?request=GetHByPointList&list={list_parameter}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        if DEBUG_MODE:
            log_to_file(log_file, f"Wysyłka do Geoportalu (próba {attempt}): URL={url}")
        try:
            response = requests.get(url, timeout=30, headers=headers)
            if DEBUG_MODE:
                log_to_file(log_file, f"Odpowiedź: status={response.status_code}, body={response.text}")
            response.raise_for_status()
            batch_heights = {}
            if response.text.strip():
                results = response.text.strip().split(',')
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
                if all_zero and attempt < max_retries:
                    if DEBUG_MODE:
                        log_to_file(log_file, "Ostrzeżenie: Wszystkie wysokości 0.0, ponawiam próbę...")
                    continue
                return batch_heights
            else:
                if DEBUG_MODE:
                    log_to_file(log_file, "Pusta odpowiedź, ponawiam próbę...")
                continue
        except requests.exceptions.RequestException as e:
            if DEBUG_MODE:
                log_to_file(log_file, f"Błąd komunikacji z API (próba {attempt}): {e}")
            if attempt == max_retries:
                print(f"{Fore.RED}Błąd komunikacji z API: {e}")
    # Jeśli po wszystkich próbach nie udało się uzyskać poprawnych danych
    if DEBUG_MODE:
        log_to_file(log_file, f"Nie udało się uzyskać poprawnych danych z Geoportalu po {max_retries} próbach.")
    return {}

# --- Dodatkowa funkcja do ponownego pobierania brakujących wysokości ---
def fetch_missing_heights(missing_points: List[Tuple[float, float]]) -> Dict[str, float]:
    log_file = "geoportal_log.txt"
    if not missing_points:
        return {}
    if DEBUG_MODE:
        log_to_file(log_file, f"Ponowna próba pobrania wysokości dla {len(missing_points)} punktów z 'brak_danych'.")
    return fetch_height_batch(missing_points)

# === ZAKTUALIZOWANE FUNKCJE GEOPRZETWARZANIA ===
def transform_coordinates_parallel(df: pd.DataFrame) -> List[Optional[Tuple[float, float]]]:
    """
    Prepares data and runs parallel coordinate transformation, now with index passing for logging.
    """
    print(f"\n{Fore.CYAN}Transformuję współrzędne ...{Style.RESET_ALL}")
    
    # Przygotowanie do logowania - czyszczenie starego pliku logu przy każdym uruchomieniu
    log_file = "transform_log.txt"
    if DEBUG_MODE and os.path.exists(log_file):
        os.remove(log_file)

    # Przygotowujemy dane wejściowe jako (indeks, northing, easting)
    points_to_transform = list(zip(
        range(len(df)), 
        df['geodetic_northing'], 
        df['geodetic_easting']
    ))
    
    results = []
    # Używamy puli procesów do równoległego przetwarzania
    # Nie ma potrzeby sprawdzania DEBUG_MODE tutaj, worker sam zdecyduje czy logować
    with multiprocessing.Pool() as pool:
        # Używamy imap dla efektywnego przetwarzania z paskiem postępu
        results = list(tqdm(pool.imap(worker_transform, points_to_transform, chunksize=100), 
                            total=len(points_to_transform), desc="Transformacja współrzędnych"))
    return results

def get_geoportal_heights_concurrent(transformed_points: List[Optional[Tuple[float, float]]]) -> Dict[str, float]:
    print(f"\n{Fore.CYAN}Pobieranie danych z Geoportalu ...{Style.RESET_ALL}")
    valid_points = [p for p in transformed_points if p is not None]
    log_to_file("log.txt", f"Liczba poprawnych punktów do pobrania wysokości: {len(valid_points)}")
    if not valid_points:
        print(f"{Fore.YELLOW}Brak poprawnych punktów do wysłania do API Geoportalu.")
        return {}
    batch_size = 300
    batches = [valid_points[i:i + batch_size] for i in range(0, len(valid_points), batch_size)]
    log_to_file("log.txt", f"Liczba partii do pobrania: {len(batches)} (po {batch_size} punktów)")
    all_heights = {}
    with ThreadPoolExecutor(max_workers=CONCURRENT_API_REQUESTS) as executor:
        results = list(tqdm(executor.map(fetch_height_batch, batches), 
                            total=len(batches), desc="Pobieranie z Geoportalu"))
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
        if DEBUG_MODE:
            log_to_file("geoportal_log.txt", f"Po ponownej próbie uzyskano wysokości dla {len(retry_heights)} z {len(missing_points)} brakujących punktów.")
    log_to_file("log.txt", f"Łącznie pobrano wysokości dla {len(all_heights)} punktów z Geoportalu.")
    return all_heights

# === Funkcje zapisu i przetwarzania ===
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
        # Zaokrąglenie wysokości do 2 miejsc po przecinku
        if 'h_odniesienia' in df_geo.columns:
            df_geo['h_odniesienia'] = pd.to_numeric(df_geo['h_odniesienia'], errors='coerce').round(2)
        # Dodaj/aktualizuj kolumnę 'eksport' zgodnie z warunkiem dokładności
        if 'osiaga_dokladnosc' in df_geo.columns:
            df_geo['eksport'] = df_geo['osiaga_dokladnosc'].apply(lambda x: True if str(x).strip().lower() == 'tak' else False)
        else:
            df_geo['eksport'] = True
        geometry = gpd.points_from_xy(df_geo['y_odniesienia'], df_geo['x_odniesienia'])
        gdf = gpd.GeoDataFrame(df_geo, geometry=geometry, crs=f"EPSG:{source_epsg}")
        # 1. Eksport całościowy
        gdf.to_file(gpkg_path, layer=layer_name, driver="GPKG")
        print(f"{Fore.GREEN}Wyniki zostały poprawnie zapisane w bazie przestrzennej: {os.path.abspath(gpkg_path)}{Style.RESET_ALL}")
        # 2. Eksport tylko spełniających warunek dokładności
        gdf_ok = gdf[gdf['eksport']]
        if not gdf_ok.empty:
            gdf_ok.to_file(gpkg_path.replace('.gpkg', '_dokladne.gpkg'), layer=layer_name, driver="GPKG")
            print(f"{Fore.GREEN}Wyniki spełniające warunek dokładności zapisano w: {os.path.abspath(gpkg_path.replace('.gpkg', '_dokladne.gpkg'))}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Brak punktów spełniających warunek dokładności do eksportu.")
        # 3. Eksport niespełniających warunku dokładności
        gdf_nok = gdf[~gdf['eksport']]
        if not gdf_nok.empty:
            gdf_nok.to_file(gpkg_path.replace('.gpkg', '_niedokladne.gpkg'), layer=layer_name, driver="GPKG")
            print(f"{Fore.GREEN}Wyniki niespełniające warunku dokładności zapisano w: {os.path.abspath(gpkg_path.replace('.gpkg', '_niedokladne.gpkg'))}{Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}Brak punktów niespełniających warunku dokładności do eksportu.")
    except Exception as e:
        print(f"{Fore.RED}Wystąpił błąd podczas tworzenia pliku GeoPackage: {e}")

def process_data(input_df: pd.DataFrame, 
                comparison_df: Optional[pd.DataFrame], 
                use_geoportal: bool,
                max_distance: float,
                geoportal_tolerance: Optional[float] = None) -> pd.DataFrame:
    results = []
    input_df = assign_geodetic_roles(input_df)
    log_file = "przetwarzanie_log.txt"
    if DEBUG_MODE and os.path.exists(log_file):
        os.remove(log_file)
    geoportal_heights, transformed_points = {}, []
    if use_geoportal:
        transformed_points = transform_coordinates_parallel(input_df)
        if transformed_points:
            geoportal_heights = get_geoportal_heights_concurrent(transformed_points)
    tree_comparison = None
    if comparison_df is not None and not comparison_df.empty:
        comparison_points = comparison_df[['x', 'y']].values
        tree_comparison = KDTree(comparison_points)
    paired_count = 0
    for i, (_, point) in enumerate(tqdm(input_df.iterrows(), total=len(input_df), desc="Przetwarzanie punktów")):
        row_data = {
            'id_odniesienia': point['id'], 'x_odniesienia': point['x'],
            'y_odniesienia': point['y'], 'h_odniesienia': point['h'],
        }
        if tree_comparison is not None and comparison_df is not None:
            distance, nearest_idx = tree_comparison.query([point['x'], point['y']])
            if (max_distance == 0) or (distance <= max_distance):
                # Teraz Pylance wie, że `comparison_df.iloc` jest bezpieczne
                nearest_in_comp_point = comparison_df.iloc[nearest_idx]
                row_data.update({
                    'id_porownania': nearest_in_comp_point['id'],
                    'x_porownania': nearest_in_comp_point['x'],
                    'y_porownania': nearest_in_comp_point['y'],
                    'h_porownania': nearest_in_comp_point['h'],
                    'odleglosc_pary': distance
                })
                try:
                    diff = float(point['h']) - float(nearest_in_comp_point['h'])
                    diff_rounded = round(diff, 2)
                    row_data['diff_h'] = math.copysign(diff_rounded, 1.0)
                except (ValueError, TypeError):
                    row_data['diff_h'] = 'brak_danych'
                paired_count += 1
        if use_geoportal and i < len(transformed_points):
            transformed_point = transformed_points[i]
            if transformed_point is not None:
                easting_2180, northing_2180 = transformed_point
                # lookup_key w formacie 'Y X' z dwoma miejscami po przecinku
                lookup_key = f"{northing_2180:.2f} {easting_2180:.2f}"
                height = geoportal_heights.get(lookup_key, "brak_danych")
                row_data['geoportal_h'] = str(height)
                if height == 'brak_danych' and DEBUG_MODE:
                    log_to_file(log_file, f"Brak wysokości z Geoportalu dla punktu {i+1} ({lookup_key})")
                if height != 'brak_danych' and pd.notnull(point['h']):
                    try:
                        diff_h_geoportal = round(float(point['h']) - float(height), 2)
                        row_data['diff_h_geoportal'] = math.copysign(diff_h_geoportal, 1.0)
                        if geoportal_tolerance is not None:
                            row_data['osiaga_dokladnosc'] = 'Tak' if abs(diff_h_geoportal) <= geoportal_tolerance else 'Nie'
                    except (ValueError, TypeError):
                        row_data['diff_h_geoportal'] = 'brak_danych'
                else:
                    row_data['diff_h_geoportal'] = 'brak_danych'
            else:
                row_data['geoportal_h'] = 'brak_danych'
                row_data['diff_h_geoportal'] = 'brak_danych'
                if DEBUG_MODE:
                    log_to_file(log_file, f"Punkt {i+1}: Brak przetransformowanych współrzędnych lub brak danych z geoportalu.")
        results.append(row_data)

    if comparison_df is not None:
        print(f"{Fore.GREEN}Znaleziono i połączono {paired_count} par punktów.{Style.RESET_ALL}")
    results_df = pd.DataFrame(results)
    if use_geoportal and 'diff_h_geoportal' in results_df.columns:
        results_df['__abs_diff_h_geoportal'] = pd.to_numeric(results_df['diff_h_geoportal'], errors='coerce').abs()
        results_df = results_df.sort_values(by='__abs_diff_h_geoportal', ascending=False).drop(columns=['__abs_diff_h_geoportal'])
    final_cols = ['id_odniesienia', 'x_odniesienia', 'y_odniesienia', 'h_odniesienia', 'diff_h_geoportal', 'geoportal_h', 'osiaga_dokladnosc', 'id_porownania', 'x_porownania', 'y_porownania', 'h_porownania', 'diff_h', 'odleglosc_pary']
    existing_cols = [col for col in final_cols if col in results_df.columns]
    return results_df[existing_cols]

# === Główna funkcja programu ===
def main():
    clear_screen()
    display_welcome_screen()
    choice = get_user_choice()
    max_distance = get_max_distance() if choice in [1, 3] else 0.0
    input_file = get_file_path("\nPodaj ścieżkę do pliku wejściowego: ")
    swap_input = ask_swap_xy("wejściowego")
    
    comparison_file = None
    swap_comparison = False  # Inicjalizacja zmiennej
    if choice in [1, 3]:
        comparison_file = get_file_path("Podaj ścieżkę do pliku porównawczego: ")
        swap_comparison = ask_swap_xy("porównawczego")
        
    geoportal_tolerance = get_geoportal_tolerance() if choice in [2, 3] else None
        
    print(f"\n{Fore.CYAN}--- Wczytywanie danych ---{Style.RESET_ALL}")
    input_df = load_data(input_file, swap_input)
    if input_df is None or input_df.empty:
        print(f"{Fore.RED}Nie udało się wczytać danych wejściowych. Zamykanie programu.")
        return
        
    comparison_df = load_data(comparison_file, swap_comparison) if comparison_file else None
        
    results_df = process_data(input_df, comparison_df, choice in [2, 3], max_distance, geoportal_tolerance)
    
    if not results_df.empty:
        print(f"\n{Fore.CYAN}--- Zapisywanie wyników ---{Style.RESET_ALL}")
        output_csv_file = 'wynik.csv'
        results_df.to_csv(output_csv_file, sep=';', index=False, float_format='%.2f', na_rep='brak_danych')
        print(f"{Fore.GREEN}Wyniki tabelaryczne zapisano w: {os.path.abspath(output_csv_file)}{Style.RESET_ALL}")
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
        traceback.print_exc()
    finally:
        input("\nNaciśnij Enter, aby zakończyć...")