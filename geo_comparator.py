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
import numpy as np
from matplotlib.path import Path

# ==============================================================================
# === KONFIGURACJA SKRYPTU ===
DEBUG_MODE = False
CONCURRENT_API_REQUESTS = 10
API_MAX_RETRIES = 5
ROUND_INPUT_DECIMALS = 1  # domyślna liczba miejsc po przecinku do zaokrąglania
DEFAULT_SPARSE_GRID_DISTANCE = 25.0  # domyślna odległość siatki rozrzedzonej (m)
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
            choice = int(input(f"\n{Fore.YELLOW}Twój wybór (1-3): {Style.RESET_ALL}"))
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
        resp = input(f"{Fore.YELLOW}Czy plik {file_label} ma zamienioną kolejność kolumn (Y,X zamiast X,Y)? [t/n] (domyślnie: n): {Style.RESET_ALL}").strip().lower()
        if not resp:
            print(f"{Fore.CYAN}Przyjęto domyślną odpowiedź: {default}{Style.RESET_ALL}")
            return False
        if resp in ['t', 'tak', 'y', 'yes']:
            return True
        if resp in ['n', 'nie', 'no']:
            return False
        print(f"{Fore.YELLOW}Wpisz 't' (tak) lub 'n' (nie).{Style.RESET_ALL}")

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

def get_round_decimals() -> int:
    default_decimals = 1
    while True:
        try:
            prompt = (f"\n{Fore.YELLOW}Podaj liczbę miejsc po przecinku do zaokrąglenia danych wejściowych (domyślnie: {default_decimals}): {Style.RESET_ALL}")
            val = input(prompt)
            if not val.strip():
                print(f"{Fore.CYAN}Przyjęto domyślną wartość: {default_decimals}{Style.RESET_ALL}")
                return default_decimals
            val_int = int(val)
            if 0 <= val_int <= 6:
                return val_int
            print(f"{Fore.RED}Błąd: Podaj liczbę z zakresu 0-6.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę całkowitą.{Style.RESET_ALL}")

# === Funkcje wczytywania danych ===
def load_data(file_path: str, swap_xy: bool = False) -> Optional[pd.DataFrame]:
    print(f"Wczytuję plik: {file_path}")
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        def handle_columns(df):
            # --- WALIDACJA NAGŁÓWKA ---
            if len(df) > 0:
                val = str(df.iloc[0, 1]).replace(',', '.').strip()
                try:
                    float(val)
                except ValueError:
                    print(f"{Fore.YELLOW}Wykryto nagłówek w pliku. Pierwszy wiersz zostanie pominięty.{Style.RESET_ALL}")
                    df = df.iloc[1:].reset_index(drop=True)
            if len(df.columns) >= 4:
                if len(df.columns) > 4:
                    print(f"{Fore.YELLOW}Wykryto więcej niż 4 kolumny. Importowane będą tylko pierwsze 4 kolumny.")
                    df = df.iloc[:, :4]
                df.columns = ['id', 'x', 'y', 'h']
                return df
            elif len(df.columns) == 3:
                print(f"{Fore.YELLOW}Wykryto 3 kolumny (brak numeru punktu).")
                prefix = input(f"{Fore.YELLOW}Podaj prefiks dla numeracji punktów (np. P): {Style.RESET_ALL}").strip() or "P"
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

# === FUNKCJE ROBOCZE DLA RÓWNOLEGŁOŚCI ===
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
    for attempt in range(1, API_MAX_RETRIES + 1):
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
                if all_zero and attempt < API_MAX_RETRIES:
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
            if attempt == API_MAX_RETRIES:
                print(f"{Fore.RED}Błąd komunikacji z API: {e}")
    # Jeśli po wszystkich próbach nie udało się uzyskać poprawnych danych
    if DEBUG_MODE:
        log_to_file(log_file, f"Nie udało się uzyskać poprawnych danych z Geoportalu po {API_MAX_RETRIES} próbach.")
    return {}

# --- Dodatkowa funkcja do ponownego pobierania brakujących wysokości ---
def fetch_missing_heights(missing_points: List[Tuple[float, float]]) -> Dict[str, float]:
    log_file = "geoportal_log.txt"
    if not missing_points:
        return {}
    if DEBUG_MODE:
        log_to_file(log_file, f"Ponowna próba pobrania wysokości dla {len(missing_points)} punktów z 'brak_danych'.")
    return fetch_height_batch(missing_points)

# === FUNKCJE GEOPRZETWARZANIA ===
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

# === funkcje do generowania rozrzedzonej siatki ===
def generuj_srodki_heksagonalne(obszar_wielokat: np.ndarray, odleglosc_miedzy_punktami: float) -> np.ndarray:
    """
    Generuje i filtruje środki okręgów w siatce heksagonalnej wewnątrz zadanego wieloboku.

    :param obszar_wielokat: Tablica NumPy z wierzchołkami wieloboku [[x1, y1], ...].
    :param odleglosc_miedzy_punktami: Oczekiwana odległość między środkami okręgów.
    :return: Posortowana tablica NumPy ze środkami [(x, y), ...].
    """
    d = odleglosc_miedzy_punktami
    dx, dy = d, d * np.sqrt(3) / 2
    sciezka_obszaru = Path(obszar_wielokat)
    min_x, min_y = np.min(obszar_wielokat, axis=0)
    max_x, max_y = np.max(obszar_wielokat, axis=0)
    lista_srodkow = []
    y_coord, wiersz = min_y, 0
    while y_coord < max_y + dy:
        x_coord = min_x
        if wiersz % 2 != 0:
            x_coord -= dx / 2
        while x_coord < max_x + dx:
            if sciezka_obszaru.contains_point((x_coord, y_coord)):
                lista_srodkow.append((x_coord, y_coord))
            x_coord += dx
        y_coord += dy
        wiersz += 1
    if not lista_srodkow:
        return np.array([])
    lista_srodkow.sort(key=lambda p: (p[1], p[0]))
    return np.array(lista_srodkow)

def znajdz_punkty_dla_siatki(punkty_kandydaci: pd.DataFrame, obszar_wielokat: np.ndarray, odleglosc_siatki: float) -> pd.DataFrame:
    """
    Główna funkcja implementująca algorytm pokrycia siatką heksagonalną.

    :param punkty_kandydaci: DataFrame z punktami, które spełniły warunek dokładności.
                            Musi zawierać kolumny ['x_odniesienia', 'y_odniesienia', 'h_odniesienia', 'geoportal_h'].
    :param obszar_wielokat: Tablica NumPy z wierzchołkami wieloboku.
    :param odleglosc_siatki: Oczekiwana odległość między punktami siatki (promień okręgu to połowa tej wartości).
    :return: DataFrame z wynikami dla siatki.
    """
    promien_szukania = odleglosc_siatki / 2.0
    dane_punktow = punkty_kandydaci[['x_odniesienia', 'y_odniesienia', 'h_odniesienia', 'geoportal_h']].apply(pd.to_numeric, errors='coerce').dropna()
    punkty_np = dane_punktow.values
    drzewo_kd = KDTree(punkty_np[:, :2])
    print("\nGenerowanie siatki pokrycia heksagonalnego...")
    lista_srodkow = generuj_srodki_heksagonalne(obszar_wielokat, odleglosc_siatki)
    if lista_srodkow.shape[0] == 0:
        print(f"{Fore.YELLOW}Nie wygenerowano żadnych punktów siatki wewnątrz zadanego obszaru.")
        return pd.DataFrame()
    print(f"Wygenerowano {len(lista_srodkow)} środków okręgów w zadanym obszarze.")
    odwiedzone_indeksy_w_np = set()
    wyniki_siatki = []
    for srodek in tqdm(lista_srodkow, desc="Przetwarzanie siatki heksagonalnej"):
        kandydaci_idx_w_np = drzewo_kd.query_ball_point(srodek, r=promien_szukania)
        aktualni_kandydaci_idx = [idx for idx in kandydaci_idx_w_np if idx not in odwiedzone_indeksy_w_np]
        if not aktualni_kandydaci_idx:
            continue
        najlepszy_idx_w_np = min(
            aktualni_kandydaci_idx,
            key=lambda idx: (
                abs(punkty_np[idx, 2] - punkty_np[idx, 3]),
                np.linalg.norm(punkty_np[idx, :2] - srodek)
            )
        )
        odwiedzone_indeksy_w_np.add(najlepszy_idx_w_np)
        oryginalny_indeks_df = dane_punktow.index[najlepszy_idx_w_np]
        znaleziony_punkt_dane = punkty_kandydaci.loc[oryginalny_indeks_df]
        wyniki_siatki.append(znaleziony_punkt_dane)
    if not wyniki_siatki:
        return pd.DataFrame()
    return pd.DataFrame(wyniki_siatki).reset_index(drop=True)

# === Funkcje zapisu i przetwarzania ===
def export_to_csv(results_df: pd.DataFrame, csv_path: str, round_decimals: int = 1):
    """
    Eksportuje wyniki do plików CSV:
    1. Plik główny ze wszystkimi wynikami.
    2. Plik z wynikami spełniającymi kryterium dokładności.
    3. Plik z wynikami niespełniającymi kryterium.
    """
    if results_df.empty:
        print(f"{Fore.YELLOW}Brak danych do zapisu w CSV.")
        return

    # 1. Eksport całościowy
    results_df.to_csv(csv_path, sep=';', index=False, float_format=f'%.{round_decimals}f', na_rep='brak_danych')
    print(f"{Fore.GREEN}Wyniki tabelaryczne (wszystkie) zapisano w: {os.path.abspath(csv_path)}{Style.RESET_ALL}")

    # Sprawdzenie, czy istnieje kolumna do podziału
    if 'osiaga_dokladnosc' not in results_df.columns:
        print(f"{Fore.YELLOW}Brak kolumny 'osiaga_dokladnosc', nie można podzielić plików CSV.")
        return

    # Przygotowanie do podziału
    df_copy = results_df.copy()
    df_copy['eksport'] = df_copy['osiaga_dokladnosc'].apply(lambda x: str(x).strip().lower() == 'tak')

    # 2. Eksport tylko spełniających warunek dokładności
    df_ok = df_copy[df_copy['eksport']].drop(columns=['eksport'])
    if not df_ok.empty:
        path_ok = csv_path.replace('.csv', '_dokladne.csv')
        df_ok.to_csv(path_ok, sep=';', index=False, float_format=f'%.{round_decimals}f', na_rep='brak_danych')
        print(f"{Fore.GREEN}Wyniki spełniające warunek dokładności zapisano w: {os.path.abspath(path_ok)}{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}Brak punktów spełniających warunek dokładności do eksportu CSV.")

    # 3. Eksport niespełniających warunku dokładności
    df_nok = df_copy[~df_copy['eksport']].drop(columns=['eksport'])
    if not df_nok.empty:
        path_nok = csv_path.replace('.csv', '_niedokladne.csv')
        df_nok.to_csv(path_nok, sep=';', index=False, float_format=f'%.{round_decimals}f', na_rep='brak_danych')
        print(f"{Fore.GREEN}Wyniki niespełniające warunku dokładności zapisano w: {os.path.abspath(path_nok)}{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}Brak punktów niespełniających warunku dokładności do eksportu CSV.")

def export_to_geopackage(results_df: pd.DataFrame, input_df: pd.DataFrame, gpkg_path: str, layer_name: str = "wyniki", round_decimals: int = 1):
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
        # Zaokrąglenie wysokości do round_decimals miejsc po przecinku
        if 'h_odniesienia' in df_geo.columns:
            df_geo['h_odniesienia'] = pd.to_numeric(df_geo['h_odniesienia'], errors='coerce').round(round_decimals)
        if 'diff_h_geoportal' in df_geo.columns:
            df_geo['diff_h_geoportal'] = pd.to_numeric(df_geo['diff_h_geoportal'], errors='coerce').round(round_decimals)
        if 'diff_h' in df_geo.columns:
            df_geo['diff_h'] = pd.to_numeric(df_geo['diff_h'], errors='coerce').round(round_decimals)
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
                geoportal_tolerance: Optional[float] = None,
                round_decimals: int = 1) -> pd.DataFrame:
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
                    diff_rounded = round(diff, round_decimals)
                    if diff_rounded == -0.0:
                        diff_rounded = 0.0
                    row_data['diff_h'] = diff_rounded
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
                        diff_h_geoportal = round(float(point['h']) - float(height), round_decimals)
                        if diff_h_geoportal == -0.0:
                            diff_h_geoportal = 0.0
                        row_data['diff_h_geoportal'] = diff_h_geoportal
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
    round_decimals = get_round_decimals()
    input_file = get_file_path(f"\n{Fore.YELLOW}Podaj ścieżkę do pliku wejściowego: {Style.RESET_ALL}")
    swap_input = ask_swap_xy("wejściowego")
    comparison_file = None
    swap_comparison = False
    if choice in [1, 3]:
        comparison_file = get_file_path(f"{Fore.YELLOW}Podaj ścieżkę do pliku porównawczego: {Style.RESET_ALL}")
        swap_comparison = ask_swap_xy("porównawczego")
    geoportal_tolerance = get_geoportal_tolerance() if choice in [2, 3] else None

    # --- Parametry eksportu rozrzedzonej siatki ---
    sparse_grid_requested = False
    sparse_grid_distance = DEFAULT_SPARSE_GRID_DISTANCE
    zakres_df = None
    if choice in [2, 3]:
        resp = input(f"\n{Fore.YELLOW}Czy wykonać eksport rozrzedzonej siatki dla punktów spełniających dokładność? [t/n] (domyślnie: n): ").strip().lower()
        if resp in ['t', 'tak', 'y', 'yes']:
            sparse_grid_requested = True
            dist_prompt = f"{Fore.YELLOW}Podaj oczekiwaną odległość pomiędzy punktami siatki (w metrach, domyślnie: {DEFAULT_SPARSE_GRID_DISTANCE}): {Style.RESET_ALL}"
            dist_val = input(dist_prompt).strip()
            if dist_val:
                try:
                    parsed_dist = float(dist_val.replace(',', '.'))
                    if parsed_dist > 0:
                        sparse_grid_distance = parsed_dist
                    else:
                        print(f"{Fore.RED}Błąd: Odległość musi być większa od zera. Przyjęto domyślną wartość {DEFAULT_SPARSE_GRID_DISTANCE} m.")
                except ValueError:
                    print(f"{Fore.RED}Błąd: Wprowadzono niepoprawną liczbę. Przyjęto domyślną wartość {DEFAULT_SPARSE_GRID_DISTANCE} m.")
            print(f"{Fore.CYAN}Wybrano eksport rozrzedzonej siatki z parametrem odległości: {sparse_grid_distance} m{Style.RESET_ALL}")
            zakres_file = get_file_path(f"{Fore.YELLOW}Podaj ścieżkę do pliku z zakresem opracowania (wierzchołki wieloboku): {Style.RESET_ALL}")
            zakres_df = load_data(zakres_file, False)

    print(f"\n{Fore.CYAN}--- Wczytywanie danych ---{Style.RESET_ALL}")
    input_df = load_data(input_file, swap_input)
    if input_df is None or input_df.empty:
        print(f"{Fore.RED}Nie udało się wczytać danych wejściowych. Zamykanie programu.")
        return
    # Zaokrąglanie danych wejściowych
    for col in ['x', 'y', 'h']:
        input_df[col] = input_df[col].round(round_decimals)
    comparison_df = load_data(comparison_file, swap_comparison) if comparison_file else None
    if comparison_df is not None:
        if 'h' in comparison_df.columns:
            comparison_df['h'] = comparison_df['h'].round(round_decimals)
    results_df = process_data(input_df, comparison_df, choice in [2, 3], max_distance, geoportal_tolerance, round_decimals)

    # --- Eksport rozrzedzonej siatki po przetworzeniu danych ---
    if sparse_grid_requested:
        if zakres_df is not None and not zakres_df.empty and 'osiaga_dokladnosc' in results_df.columns:
            print(f"{Fore.CYAN}\n--- Przetwarzanie rozrzedzonej siatki ---{Style.RESET_ALL}")
            punkty_dokladne_df = results_df[results_df['osiaga_dokladnosc'] == 'Tak'].copy()
            if punkty_dokladne_df.empty:
                print(f"{Fore.YELLOW}Brak punktów spełniających kryterium dokładności. Nie można wygenerować siatki.")
            else:
                obszar_wielokat = zakres_df[['x', 'y']].values
                wyniki_siatki_df = znajdz_punkty_dla_siatki(punkty_dokladne_df, obszar_wielokat, sparse_grid_distance)
                if not wyniki_siatki_df.empty:
                    output_siatka_csv = 'wynik_siatka.csv'
                    output_siatka_gpkg = 'wynik_siatka.gpkg'
                    wyniki_siatki_df.to_csv(output_siatka_csv, sep=';', index=False, float_format=f'%.{round_decimals}f', na_rep='brak_danych')
                    print(f"{Fore.GREEN}Wyniki rozrzedzonej siatki zapisano w pliku CSV: {os.path.abspath(output_siatka_csv)}{Style.RESET_ALL}")
                    export_to_geopackage(wyniki_siatki_df, input_df, output_siatka_gpkg, layer_name="wynik_siatki", round_decimals=round_decimals)
                else:
                    print(f"{Fore.YELLOW}Nie udało się wygenerować żadnych punktów dla rozrzedzonej siatki.")
        else:
            if zakres_df is None or zakres_df.empty:
                print(f"{Fore.RED}Nie udało się wczytać danych zakresu. Przetwarzanie siatki przerwane.")
            if 'osiaga_dokladnosc' not in results_df.columns:
                print(f"{Fore.RED}Brak kolumny 'osiaga_dokladnosc' w wynikach. Przetwarzanie siatki przerwane.")

    # --- Standardowy eksport wyników ---
    if not results_df.empty:
        print(f"\n{Fore.CYAN}--- Zapisywanie wyników ---{Style.RESET_ALL}")
        
        # Eksport do plików CSV
        output_csv_file = 'wynik.csv'
        export_to_csv(results_df, output_csv_file, round_decimals=round_decimals)

        # Eksport do plików GeoPackage
        output_gpkg_file = 'wynik.gpkg'
        export_to_geopackage(results_df, input_df, output_gpkg_file, round_decimals=round_decimals)
        
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
        input(f"\n{Fore.YELLOW}Naciśnij Enter, aby zakończyć...{Style.RESET_ALL}")