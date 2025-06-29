# === Importowanie niezbędnych bibliotek ===
import os  # Operacje na plikach i systemie operacyjnym
import sys  # Dostęp do funkcji systemowych (np. obsługa postępu)
from typing import Dict, List, Tuple, Optional  # Typowanie dla lepszej czytelności kodu
import pandas as pd  # Przetwarzanie i analiza danych tabelarycznych
from pyproj import Transformer  # Transformacje współrzędnych geodezyjnych
import requests  # Wysyłanie zapytań HTTP (np. do Geoportalu)
from scipy.spatial import KDTree  # Efektywne wyszukiwanie najbliższych punktów
from colorama import init, Fore, Style  # Kolorowanie tekstu w konsoli
import geopandas as gpd # Dodano geopandas do obsługi danych przestrzennych

# ==============================================================================
# === KONFIGURACJA SKRYPTU ===
# Flaga DEBUG_MODE steruje wyświetlaniem szczegółowych komunikatów diagnostycznych.
# Ustaw na True, aby zobaczyć szczegóły działania (przydatne podczas nauki i debugowania).
# Ustaw na False, aby program działał "ciszej" i szybciej (zalecane w produkcji).
DEBUG_MODE = False  # <--- WYŁĄCZONY TRYB DEBUGOWANIA
# ==============================================================================

# Inicjalizacja biblioteki colorama, która umożliwia wyświetlanie kolorów w konsoli
# na różnych systemach operacyjnych. `autoreset=True` powoduje, że każdy `print`
# wraca do domyślnego koloru, nie trzeba ręcznie resetować stylu.
init(autoreset=True)

# === Funkcje pomocnicze interfejsu użytkownika ===

# Funkcja czyszcząca ekran konsoli, aby poprawić czytelność wyświetlanych komunikatów.
def clear_screen():
    """Czyści ekran konsoli w zależności od systemu operacyjnego."""
    os.system('cls' if os.name == 'nt' else 'clear')

# Funkcja wyświetlająca ekran powitalny z nazwą programu i instrukcją obsługi.
def display_welcome_screen():
    """Wyświetla estetyczny ekran powitalny z tytułem i instrukcją obsługi."""
    print(f"{Fore.GREEN}======================================")
    print(f"{Fore.GREEN}===           diffH               ===")
    print(f"{Fore.GREEN}======================================")
    if DEBUG_MODE:
        print(f"{Fore.MAGENTA}*** TRYB DEBUGOWANIA AKTYWNY ***")
    print(f"\n{Fore.WHITE}Instrukcja:")
    print("1. Przygotuj plik wejściowy z danymi w układzie PL-2000.")
    print("   Format: [id, x, y, h] lub [id, y, x, h] (separator: spacja, przecinek lub średnik).")
    print("   UWAGA: Skrypt automatycznie wykryje strefę 2000 w pliku.")
    print("2. Skrypt zapyta o ścieżkę do pliku i rodzaj porównania.")
    print("3. Wynik zostanie zapisany w pliku 'wynik.csv' oraz w bazie przestrzennej 'wynik.gpkg'.\n")

# Funkcja pobierająca od użytkownika wybór trybu działania programu.
def get_user_choice() -> int:
    """Pobiera od użytkownika wybór trybu działania (1, 2 lub 3) i waliduje go."""
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

# Funkcja pobierająca od użytkownika ścieżkę do pliku i sprawdzająca, czy plik istnieje.
def get_file_path(prompt: str) -> str:
    """Pobiera od użytkownika ścieżkę do pliku i sprawdza, czy plik istnieje."""
    while True:
        file_path = input(prompt)
        if os.path.exists(file_path):
            return file_path
        print(f"{Fore.RED}Błąd: Plik nie istnieje. Spróbuj ponownie.")

# Funkcja pobierająca od użytkownika maksymalną odległość do parowania punktów.
def get_max_distance() -> float:
    """Pobiera od użytkownika maksymalną odległość do parowania punktów."""
    while True:
        try:
            distance_str = input(f"\n{Fore.YELLOW}Podaj maksymalną odległość wyszukiwania pary w metrach (np. 0.5)\n(Wpisz 0, aby pominąć ten warunek): {Style.RESET_ALL}")
            # Zamienia przecinek na kropkę, aby obsłużyć oba formaty wprowadzania liczb
            distance = float(distance_str.replace(',', '.'))
            if distance >= 0:
                return distance
            print(f"{Fore.RED}Błąd: Odległość nie może być ujemna.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.{Style.RESET_ALL}")

# Funkcja pytająca użytkownika, czy zamienić kolumny X i Y dla danego pliku.
def ask_swap_xy(file_label: str) -> bool:
    """Pyta użytkownika czy zamienić kolumny X i Y dla danego pliku."""
    while True:
        resp = input(f"Czy plik {file_label} ma zamienioną kolejność kolumn (Y,X zamiast X,Y)? [t/n]: ").strip().lower()
        if resp in ['t', 'tak', 'y', 'yes']:
            return True
        if resp in ['n', 'nie', 'no']:
            return False
        print("Wpisz 't' (tak) lub 'n' (nie).")

# Funkcja pobierająca dopuszczalną różnicę wysokości względem geoportalu.
def get_geoportal_tolerance() -> float:
    """Pobiera od użytkownika dopuszczalną różnicę wysokości względem geoportalu."""
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

# Funkcja wczytująca dane z pliku tekstowego, automatycznie wykrywająca separator i zamieniająca kolumny X/Y jeśli trzeba.
def load_data(file_path: str, swap_xy: bool = False) -> Optional[pd.DataFrame]:
    """
    Wczytuje dane z pliku tekstowego, automatycznie wykrywając separator.
    swap_xy: jeśli True, zamienia kolumny X i Y po wczytaniu.
    Dodatkowo zaokrągla współrzędne i wysokości do 2 miejsc zgodnie z regułą Bradissa-Kryłowa.
    """
    print(f"Wczytuję plik: {file_path}")
    try:
        for sep in [';', ',', r'\s+']:
            try:
                if DEBUG_MODE:
                    print(f"[DEBUG] Próbuję separator: '{sep}' dla pliku {file_path}")
                df = pd.read_csv(file_path, sep=sep, header=None, on_bad_lines='skip', engine='python', dtype=str)
                if len(df.columns) >= 4:
                    df = df.iloc[:, :4]
                    df.columns = ['id', 'x', 'y', 'h']
                    if swap_xy:
                        if DEBUG_MODE:
                            print(f"[DEBUG] Zamieniam kolumny X i Y dla pliku {file_path}")
                        df[['x', 'y']] = df[['y', 'x']]
                    for col in ['x', 'y', 'h']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                        df[col] = df[col].apply(lambda v: round_bradis_krylov(v, 2) if pd.notnull(v) else v)
                        if DEBUG_MODE:
                            print(f"[DEBUG] Kolumna {col} po zaokrągleniu: {df[col].tolist()}")
                    df.dropna(subset=['x', 'y', 'h'], inplace=True)
                    sep_display = 'spacja/tab' if sep == r'\s+' else sep
                    print(f"{Fore.GREEN}Plik wczytany poprawnie (separator: '{sep_display}', {len(df)} wierszy).")
                    return df
            except Exception as ex:
                if DEBUG_MODE:
                    print(f"[DEBUG] Błąd przy próbie separatora '{sep}': {ex}")
                continue
        raise ValueError("Nie udało się zinterpretować pliku. Sprawdź format i separator.")
    except Exception as e:
        print(f"{Fore.RED}Błąd podczas wczytywania pliku: {e}")
        return None

# Funkcja sprawdzająca, czy podana współrzędna ma strukturę Eastingu w układzie PL-2000.
def has_easting_structure(coord: float) -> bool:
    """Sprawdza, czy podana współrzędna ma strukturę Easting w układzie PL-2000."""
    try:
        coord_str = str(int(coord))
        # Easting w PL-2000 ma 7 cyfr i zaczyna się od 5, 6, 7 lub 8
        return len(coord_str) == 7 and coord_str[0] in ['5', '6', '7', '8']
    except (ValueError, TypeError, IndexError):
        return False

# Funkcja przypisująca kolumnom odpowiednie role geodezyjne (Northing/Easting) na podstawie analizy danych.
def assign_geodetic_roles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analizuje dane i przypisuje im role geodezyjne (Northing, Easting).
    Inteligentnie wykrywa, czy plik źródłowy używa konwencji:
    - Geodezyjnej (X = Northing, Y = Easting)
    - GIS (X = Easting, Y = Northing)
    i tworzy nowe kolumny `geodetic_northing` i `geodetic_easting` do dalszego użytku.
    """
    if df.empty:
        return df
    if DEBUG_MODE:
        print(f"{Fore.MAGENTA}[DEBUG] Sprawdzam konwencję współrzędnych w pliku...{Style.RESET_ALL}")

    first_row = df.iloc[0]
    x_from_file, y_from_file = first_row['x'], first_row['y']

    if has_easting_structure(y_from_file):
        if DEBUG_MODE:
            print(f"{Fore.MAGENTA}[DEBUG] WYKRYTO: Kolumna 'y' z pliku ma strukturę Easting. Przyjmuję, że plik ma układ geodezyjny (X=Northing, Y=Easting).{Style.RESET_ALL}")
        df['geodetic_northing'] = df['x']
        df['geodetic_easting'] = df['y']
    elif has_easting_structure(x_from_file):
        if DEBUG_MODE:
            print(f"{Fore.MAGENTA}[DEBUG] WYKRYTO: Kolumna 'x' z pliku ma strukturę Easting. Przyjmuję, że plik ma układ GIS (X=Easting, Y=Northing).{Style.RESET_ALL}")
        df['geodetic_northing'] = df['y']
        df['geodetic_easting'] = df['x']
    else:
        if DEBUG_MODE:
            print(f"{Fore.YELLOW}[DEBUG-OSTRZEŻENIE] Nie można jednoznacznie zidentyfikować struktury Easting. Zakładam domyślny układ geodezyjny (X=Northing, Y=Easting).{Style.RESET_ALL}")
        df['geodetic_northing'] = df['x']
        df['geodetic_easting'] = df['y']
    return df

# Funkcja określająca kod EPSG strefy układu PL-2000 na podstawie współrzędnej Easting.
def get_source_epsg(easting_coordinate: float) -> Optional[int]:
    """Określa kod EPSG strefy układu PL-2000 na podstawie współrzędnej Easting."""
    try:
        easting_str = str(int(easting_coordinate))
        if len(easting_str) == 7:
            first_digit = easting_str[0]
            epsg_mapping = {'5': 2176, '6': 2177, '7': 2178, '8': 2179}
            return epsg_mapping.get(first_digit)
    except (ValueError, TypeError, IndexError):
        return None
    return None

# Funkcja zaokrąglająca liczbę zgodnie z regułą Bradissa-Kryłowa (bankers' rounding).
def round_bradis_krylov(value: float, ndigits: int = 2) -> float:
    """
    Zaokrągla liczbę zgodnie z regułą Bradissa-Kryłowa (bankers' rounding):
    - Jeśli cyfra po ostatniej zachowywanej jest 5 i dalej same zera, zaokrągla do parzystej.
    - W pozostałych przypadkach klasycznie.
    """
    return round(value, ndigits)

# Funkcja transformująca współrzędne z układu PL-2000 do PL-1992 (EPSG:2180).
def transform_coordinates(df: pd.DataFrame) -> List[Tuple[float, float]]:
    """Transformuje współrzędne z układu PL-2000 do PL-1992 (EPSG:2180) i zaokrągla do 2 miejsc zgodnie z regułą Bradissa-Kryłowa. Dodano pasek postępu."""
    transformed_points = []  # Lista na przetransformowane punkty
    print(f"\n{Fore.CYAN}Transformuję współrzędne z PL-2000 do PL-1992 (EPSG:2180)...{Style.RESET_ALL}")
    total_points = len(df)
    bar_length = 40  # Długość paska postępu
    for idx, (row_idx, row) in enumerate(df.iterrows()):
        northing = row['geodetic_northing']
        easting = row['geodetic_easting']
        source_epsg = get_source_epsg(easting)
        if source_epsg is None:
            if DEBUG_MODE:
                print(f"[DEBUG] Nie można określić strefy EPSG dla ptk {row.id} (Easting={easting})")
            transformed_points.append((0.0, 0.0)) 
            # Pasek postępu
            progress = (idx + 1) / total_points
            block = int(round(bar_length * progress))
            text = f"\rTransformacja: [{'#' * block}{'-' * (bar_length - block)}] {int(progress * 100)}%"
            sys.stdout.write(text)
            sys.stdout.flush()
            continue
        transformer = Transformer.from_crs(f"EPSG:{source_epsg}", "EPSG:2180")
        x_gis_easting, y_gis_northing = transformer.transform(northing, easting)
        x_gis_easting = round_bradis_krylov(x_gis_easting, 2)
        y_gis_northing = round_bradis_krylov(y_gis_northing, 2)
        if DEBUG_MODE:
            print(f"[DEBUG] {row.id}: ({northing}, {easting}) EPSG:{source_epsg} -> ({x_gis_easting}, {y_gis_northing}) EPSG:2180")
        transformed_points.append((x_gis_easting, y_gis_northing))
        # Pasek postępu
        progress = (idx + 1) / total_points
        block = int(round(bar_length * progress))
        text = f"\rTransformacja: [{'#' * block}{'-' * (bar_length - block)}] {int(progress * 100)}%"
        sys.stdout.write(text)
        sys.stdout.flush()
    print("\n" + f"{Fore.GREEN}Transformacja zakończona.{Style.RESET_ALL}")
    return transformed_points

# Funkcja pobierająca wysokości dla listy punktów z API Geoportalu w paczkach po 300 punktów.
def get_geoportal_heights(transformed_points: List[Tuple[float, float]]) -> Dict[str, float]:
    """
    Pobiera wysokości dla listy punktów z API Geoportalu w paczkach po 300 punktów.
    Zwraca słownik: klucz = 'easting northing' (zaokrąglone do 2 miejsc), wartość = wysokość.
    """
    print(f"\n{Fore.CYAN}Pobieranie danych wysokościowych z Geoportalu...{Style.RESET_ALL}")
    valid_points = [p for p in transformed_points if p != (0.0, 0.0)]
    if not valid_points:
        print(f"{Fore.YELLOW}Brak poprawnych punktów do wysłania do API Geoportalu.")
        return {}
    geoportal_heights = {}
    batch_size = 300  # Limit API Geoportalu na jedno zapytanie
    total = len(valid_points)
    for start in range(0, total, batch_size):
        batch = valid_points[start:start+batch_size]
        point_strings = [f"{easting:.2f} {northing:.2f}" for easting, northing in batch]
        list_parameter = ",".join(point_strings)
        url = f"https://services.gugik.gov.pl/nmt/?request=GetHByPointList&list={list_parameter}"
        if DEBUG_MODE:
            print(f"[DEBUG] Wysyłam zapytanie do Geoportalu: {url}")
        try:
            response = requests.get(url, timeout=30)
            if DEBUG_MODE:
                print(f"[DEBUG] Odpowiedź status: {response.status_code}")
                print(f"[DEBUG] Odpowiedź tekst: {response.text[:200]}{'...' if len(response.text) > 200 else ''}")
            response.raise_for_status()
            if response.text.strip():
                results = response.text.strip().split(',')
                for point_result in results:
                    parts = point_result.split()
                    if len(parts) == 3:
                        easting_api, northing_api, h_api = parts
                        key = f"{float(easting_api):.2f} {float(northing_api):.2f}"
                        geoportal_heights[key] = float(h_api)
                        if DEBUG_MODE:
                            print(f"[DEBUG] Odpowiedź API: {key} -> {h_api}")
            print(f"{Fore.GREEN}Pobrano dane wysokościowe dla paczki {start+1}-{min(start+batch_size, total)} z {total} punktów.{Style.RESET_ALL}")
        except requests.exceptions.RequestException as e:
            print(f"{Fore.RED}Błąd podczas komunikacji z Geoportalem (paczka {start+1}-{min(start+batch_size, total)}): {e}")
    return geoportal_heights

def export_to_geopackage(results_df: pd.DataFrame, input_df: pd.DataFrame, gpkg_path: str, layer_name: str = "wyniki"):
    """
    Eksportuje DataFrame do pliku GeoPackage (.gpkg), który jest czytelny dla QGIS.
    - Automatycznie tworzy geometrię punktową z kolumn x_odniesienia, y_odniesienia.
    - Wykrywa układ współrzędnych (CRS) na podstawie danych wejściowych.
    - Dodaje kolumnę 'eksport' typu bool (domyślnie True).
    """
    if results_df.empty:
        print(f"{Fore.YELLOW}Brak danych do zapisu w GeoPackage.")
        return

    # Krok 1: Wykryj CRS na podstawie pierwszego punktu w pliku wejściowym
    source_epsg = None
    if not input_df.empty:
        first_point_easting = input_df.iloc[0]['geodetic_easting']
        source_epsg = get_source_epsg(first_point_easting)

    if source_epsg is None:
        print(f"{Fore.RED}Błąd: Nie można było ustalić źródłowego układu współrzędnych (EPSG) dla pliku wejściowego.")
        print(f"{Fore.YELLOW}Plik GeoPackage nie zostanie utworzony.")
        return

    print(f"Wykryto układ współrzędnych dla pliku GeoPackage: EPSG:{source_epsg}")

    # Krok 2: Przygotuj dane do konwersji
    df_geo = results_df.copy()
    df_geo['eksport'] = True
    df_geo = df_geo.where(pd.notnull(df_geo), None)

    # Krok 3: Utwórz GeoDataFrame
    try:
        # Zamieniono kolejność kolumn, aby dopasować się do konwencji GIS (x=Easting, y=Northing).
        # W danych wejściowych 'y_odniesienia' to Easting, a 'x_odniesienia' to Northing.
        geometry = gpd.points_from_xy(df_geo['y_odniesienia'], df_geo['x_odniesienia'])
        gdf = gpd.GeoDataFrame(df_geo, geometry=geometry, crs=f"EPSG:{source_epsg}")

        # Krok 4: Zapisz do pliku GeoPackage
        gdf.to_file(gpkg_path, layer=layer_name, driver="GPKG")
        print(f"{Fore.GREEN}Wyniki zostały poprawnie zapisane w bazie przestrzennej: {os.path.abspath(gpkg_path)}{Style.RESET_ALL}")

    except Exception as e:
        print(f"{Fore.RED}Wystąpił błąd podczas tworzenia pliku GeoPackage: {e}")


# Główna funkcja przetwarzająca dane, wykonująca transformacje i porównania.
def process_data(input_df: pd.DataFrame, 
                comparison_df: Optional[pd.DataFrame], 
                use_geoportal: bool,
                max_distance: float,
                geoportal_tolerance: Optional[float] = None) -> pd.DataFrame:
    """Główna funkcja przetwarzająca dane, wykonująca transformacje i porównania."""
    results = []  # Lista na wyniki końcowe
    total_points = len(input_df)
    if DEBUG_MODE:
        print(f"[DEBUG] Rozpoczynam przetwarzanie {total_points} punktów.")
    # Zachowujemy oryginalne współrzędne do dalszego porównania
    input_df['x_oryginal'] = input_df['x']
    input_df['y_oryginal'] = input_df['y']
    input_df = assign_geodetic_roles(input_df)
    geoportal_heights, transformed_points = {}, []
    # Jeśli wybrano porównanie z Geoportalem, wykonujemy transformację i pobieramy wysokości
    if use_geoportal:
        transformed_points = transform_coordinates(input_df)
        if transformed_points:
            geoportal_heights = get_geoportal_heights(transformed_points)
    tree_input, tree_comparison = None, None
    # Jeśli wybrano porównanie z drugim plikiem, przygotowujemy KDTree do szybkiego wyszukiwania najbliższych punktów
    if comparison_df is not None:
        print(f"\n{Fore.CYAN}Przygotowuję zaawansowane parowanie punktów...{Style.RESET_ALL}")
        comparison_df['x_oryginal'] = comparison_df['x']
        comparison_df['y_oryginal'] = comparison_df['y']
        input_points = input_df[['x_oryginal', 'y_oryginal']].values
        comparison_points = comparison_df[['x_oryginal', 'y_oryginal']].values
        tree_input = KDTree(input_points)
        tree_comparison = KDTree(comparison_points)
        print(f"{Fore.GREEN}Indeksy do porównania gotowe.{Style.RESET_ALL}")
    paired_count = 0  # Licznik sparowanych punktów
    print(f"\n{Fore.CYAN}Przetwarzam punkty...{Style.RESET_ALL}")
    for i, (_, point) in enumerate(input_df.iterrows()):
        # Tworzymy słownik na dane wyjściowe dla każdego punktu
        row_data = {
            'id_odniesienia': point['id'],
            'x_odniesienia': point['x_oryginal'],
            'y_odniesienia': point['y_oryginal'],
            'h_odniesienia': point['h'],
        }
        # Parowanie punktów z plikiem porównawczym (jeśli wybrano)
        diff_h = None
        if comparison_df is not None and tree_comparison is not None and tree_input is not None:
            distance, nearest_idx_in_comp = tree_comparison.query([point['x_oryginal'], point['y_oryginal']])
            is_within_distance = (max_distance == 0) or (distance <= max_distance)
            if DEBUG_MODE:
                print(f"[DEBUG] Punkt {i}: szukam najbliższego w porównawczym, dystans={distance}, idx={nearest_idx_in_comp}, warunek dystansu={is_within_distance}")
            if is_within_distance:
                nearest_in_comp_point = comparison_df.iloc[nearest_idx_in_comp]
                _, nearest_idx_in_input = tree_input.query([nearest_in_comp_point['x_oryginal'], nearest_in_comp_point['y_oryginal']])
                is_reciprocal = (i == nearest_idx_in_input)
                if DEBUG_MODE:
                    print(f"[DEBUG] Punkt {i}: wzajemność={is_reciprocal}, idx_back={nearest_idx_in_input}")
                if is_reciprocal:
                    row_data['id_porownania'] = nearest_in_comp_point['id']
                    row_data['x_porownania'] = nearest_in_comp_point['x_oryginal']
                    row_data['y_porownania'] = nearest_in_comp_point['y_oryginal']
                    row_data['h_porownania'] = nearest_in_comp_point['h']
                    # Różnica wysokości odniesienia - porównania
                    try:
                        diff_h = float(point['h']) - float(nearest_in_comp_point['h'])
                    except Exception:
                        diff_h = 'brak_danych'
                    row_data['diff_h'] = diff_h
                    row_data['odleglosc_pary'] = distance
                    paired_count += 1
        # Pobieranie wysokości z Geoportalu (jeśli wybrano)
        if use_geoportal and transformed_points:
            easting_2180, northing_2180 = transformed_points[i]
            lookup_key = f"{easting_2180:.2f} {northing_2180:.2f}"
            height = geoportal_heights.get(lookup_key, "brak_danych")
            row_data['geoportal_h'] = str(height)
            # Dodaj różnicę h_odniesienia - geoportal_h
            if height != 'brak_danych' and point['h'] is not None:
                try:
                    diff_h_geoportal = float(point['h']) - float(height)
                except Exception:
                    diff_h_geoportal = 'brak_danych'
            else:
                diff_h_geoportal = 'brak_danych'
            row_data['diff_h_geoportal'] = diff_h_geoportal
            # Sprawdzenie tolerancji
            if geoportal_tolerance is not None and diff_h_geoportal != 'brak_danych':
                try:
                    is_within = abs(float(diff_h_geoportal)) <= geoportal_tolerance
                except Exception:
                    is_within = False
                row_data['osiaga_dokladnosc'] = 'Tak' if is_within else 'Nie'
        results.append(row_data)
        # Pasek postępu w konsoli
        progress = (i + 1) / total_points
        bar_length = 40
        block = int(round(bar_length * progress))
        text = f"\rPrzetworzono {i+1}/{total_points} punktów: [{'#' * block}{'-' * (bar_length - block)}] {int(progress * 100)}%"
        sys.stdout.write(text)
        sys.stdout.flush()
    print("\n")
    if comparison_df is not None:
        print(f"{Fore.GREEN}Znaleziono i połączono {paired_count} par punktów.{Style.RESET_ALL}")
    # Przestawianie kolumn w odpowiedniej kolejności
    results_df = pd.DataFrame(results)
    if comparison_df is not None:
        # Wstawiamy diff_h przed odleglosc_pary
        cols = list(results_df.columns)
        if 'diff_h' in cols and 'odleglosc_pary' in cols:
            cols.remove('diff_h')
            idx = cols.index('odleglosc_pary')
            cols.insert(idx, 'diff_h')
        if use_geoportal and 'diff_h_geoportal_pair' in cols and 'odleglosc_pary' in cols:
            cols.remove('diff_h_geoportal_pair')
            idx = cols.index('odleglosc_pary') + 1
            cols.insert(idx, 'diff_h_geoportal_pair')
        if 'diff_h_geoportal' in cols and 'h_odniesienia' in cols:
            cols.remove('diff_h_geoportal')
            idx = cols.index('h_odniesienia') + 1
            cols.insert(idx, 'diff_h_geoportal')
        if 'osiaga_dokladnosc' in cols:
            cols.remove('osiaga_dokladnosc')
            cols.append('osiaga_dokladnosc')
        results_df = results_df[cols]
    else:
        # Wstawiamy diff_h_geoportal po h_odniesienia
        cols = list(results_df.columns)
        if 'diff_h_geoportal' in cols and 'h_odniesienia' in cols:
            cols.remove('diff_h_geoportal')
            idx = cols.index('h_odniesienia') + 1
            cols.insert(idx, 'diff_h_geoportal')
        if 'osiaga_dokladnosc' in cols:
            cols.remove('osiaga_dokladnosc')
            cols.append('osiaga_dokladnosc')
        results_df = results_df[cols]
    # Sortowanie po bezwzględnej wartości diff_h_geoportal malejąco
    if 'diff_h_geoportal' in results_df.columns:
        def abs_or_nan(val):
            try:
                return abs(float(val))
            except Exception:
                return float('-inf')  # brak_danych na końcu
        results_df = results_df.copy()
        results_df['__abs_diff_h_geoportal'] = results_df['diff_h_geoportal'].apply(abs_or_nan)
        results_df = results_df.sort_values(by='__abs_diff_h_geoportal', ascending=False)
        results_df = results_df.drop(columns=['__abs_diff_h_geoportal'])
    return results_df

# === Główna funkcja programu ===
def main():
    """
    Główna funkcja programu, która steruje całym procesem:
    1. Wyświetla ekran powitalny i pobiera dane od użytkownika.
    2. Wczytuje pliki z danymi.
    3. Przetwarza dane zgodnie z wybranym trybem.
    4. Zapisuje wyniki do pliku CSV i GeoPackage.
    """
    clear_screen()
    display_welcome_screen()
    # Krok 1: Pobranie danych od użytkownika
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
    # Krok 2: Wczytanie danych z plików
    print(f"\n{Fore.CYAN}--- Wczytywanie danych ---{Style.RESET_ALL}")
    input_df = load_data(input_file, swap_input)
    if input_df is None or input_df.empty:
        print(f"{Fore.RED}Nie udało się wczytać danych wejściowych. Zamykanie programu.")
        return
    comparison_df = None
    if comparison_file:
        comparison_df = load_data(comparison_file, swap_comparison)
    # Krok 3: Główna logika przetwarzania
    use_geoportal = choice in [2, 3]
    results_df = process_data(input_df, comparison_df, use_geoportal, max_distance, geoportal_tolerance)
    
    # Krok 4: Zapis wyników
    if not results_df.empty:
        print(f"\n{Fore.CYAN}--- Zapisywanie wyników ---{Style.RESET_ALL}")
        
        # --- Zapis do pliku CSV (bez zmian) ---
        output_csv_file = 'wynik.csv'
        output_columns = ['id_odniesienia', 'x_odniesienia', 'y_odniesienia', 'h_odniesienia']
        if 'diff_h_geoportal' in results_df.columns:
            output_columns.append('diff_h_geoportal')
        if 'id_porownania' in results_df.columns:
            output_columns.extend(['id_porownania', 'x_porownania', 'y_porownania', 'h_porownania'])
            if 'diff_h' in results_df.columns:
                output_columns.append('diff_h')
            if 'odleglosc_pary' in results_df.columns:
                output_columns.append('odleglosc_pary')
            if 'diff_h_geoportal_pair' in results_df.columns:
                output_columns.append('diff_h_geoportal_pair')
        if 'geoportal_h' in results_df.columns:
            output_columns.append('geoportal_h')
        if 'osiaga_dokladnosc' in results_df.columns:
            output_columns.append('osiaga_dokladnosc')
        
        results_df.to_csv(
            output_csv_file, 
            sep=';', 
            index=False, 
            columns=output_columns,
            float_format='%.2f',
            na_rep='brak_danych'
        )
        print(f"{Fore.GREEN}Wyniki tabelaryczne zostały zapisane w pliku: {os.path.abspath(output_csv_file)}{Style.RESET_ALL}")

        # Zapis do bazy GeoPackage
        output_gpkg_file = 'wynik.gpkg'
        export_to_geopackage(results_df, input_df, output_gpkg_file)
        
        print(f"\n{Fore.GREEN}Zakończono przetwarzanie pomyślnie!")
    else:
        print(f"{Fore.YELLOW}Nie wygenerowano żadnych wyników.")

# === Punkt startowy programu ===
if __name__ == "__main__":
    try:
        main()
    # Obsługa przerwania programu przez użytkownika (Ctrl+C)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Przerwano działanie programu.{Style.RESET_ALL}")
    # Obsługa wszystkich innych, nieprzewidzianych błędów
    except Exception as e:
        print(f"\n{Fore.RED}Wystąpił nieoczekiwany błąd globalny: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Zapewnienie, że okno konsoli nie zamknie się natychmiast po zakończeniu
        print("\nNaciśnij Enter, aby zakończyć...")
        input()