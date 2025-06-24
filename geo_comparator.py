# -*- coding: utf-8 -*-

# === Importowanie niezbędnych bibliotek ===
import os
import sys
from typing import Dict, List, Tuple, Optional
import pandas as pd
from pyproj import Transformer
import requests
from scipy.spatial import KDTree
from colorama import init, Fore, Style

# ==============================================================================
# === KONFIGURACJA SKRYPTU ===
# Ustaw na True, aby wyświetlić szczegółowe komunikaty diagnostyczne podczas działania.
# W trybie produkcyjnym ustaw na False dla czystszego widoku i większej wydajności.
DEBUG_MODE = False
# ==============================================================================

# Inicjalizacja biblioteki colorama, która umożliwia wyświetlanie kolorów w konsoli
# na różnych systemach operacyjnych. `autoreset=True` powoduje, że każdy `print`
# wraca do domyślnego koloru, nie trzeba ręcznie resetować stylu.
init(autoreset=True)

# === Funkcje pomocnicze interfejsu użytkownika ===

def clear_screen():
    """Czyści ekran konsoli w zależności od systemu operacyjnego."""
    os.system('cls' if os.name == 'nt' else 'clear')

def display_welcome_screen():
    """Wyświetla estetyczny ekran powitalny z tytułem i instrukcją obsługi."""
    print(f"{Fore.CYAN}======================================")
    print("===           diffH               ===")
    print("======================================")
    if DEBUG_MODE:
        print(f"{Fore.MAGENTA}*** TRYB DEBUGOWANIA AKTYWNY ***")
    print(f"\n{Fore.WHITE}Instrukcja:")
    print("1. Przygotuj plik wejściowy z danymi w układzie PL-2000.")
    print("   Format: [id, x, y, h] (separator: spacja, przecinek lub średnik).")
    print("   UWAGA: Skrypt automatycznie wykryje strefę 2000 w pliku.")
    print("2. Skrypt zapyta o ścieżkę do pliku i rodzaj porównania.")
    print("3. Wynik zostanie zapisany w pliku 'wynik.csv'.\n")

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

def get_file_path(prompt: str) -> str:
    """Pobiera od użytkownika ścieżkę do pliku i sprawdza, czy plik istnieje."""
    while True:
        file_path = input(prompt)
        if os.path.exists(file_path):
            return file_path
        print(f"{Fore.RED}Błąd: Plik nie istnieje. Spróbuj ponownie.")

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

# === Funkcje przetwarzania danych geoprzestrzennych ===

def load_data(file_path: str) -> Optional[pd.DataFrame]:
    """
    Wczytuje dane z pliku tekstowego, automatycznie wykrywając separator.
    - Próbuje wczytać plik z separatorem ';', ',', a na końcu spacją/tabulatorem.
    - Nazywa pierwsze 4 kolumny jako 'id', 'x', 'y', 'h'.
    - Konwertuje współrzędne i wysokość na typ liczbowy.
    - Usuwa wiersze, w których konwersja się nie powiodła.
    Zwraca obiekt DataFrame z biblioteki pandas lub None w przypadku błędu.
    """
    print(f"Wczytuję plik: {file_path}")
    try:
        # Pętla próbująca wczytać plik z różnymi popularnymi separatorami
        for sep in [';', ',', r'\s+']:
            try:
                # Wczytanie danych jako tekst, aby uniknąć problemów z typami
                df = pd.read_csv(file_path, sep=sep, header=None, on_bad_lines='skip', engine='python', dtype=str)
                # Sprawdzenie, czy plik ma co najmniej 4 kolumny
                if len(df.columns) >= 4:
                    df = df.iloc[:, :4]
                    df.columns = ['id', 'x', 'y', 'h']
                    for col in ['x', 'y', 'h']:
                        # Konwersja na liczby; błędy zamieniane są na 'NaN' (Not a Number)
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    # Usunięcie wierszy z błędami (NaN)
                    df.dropna(subset=['x', 'y', 'h'], inplace=True)
                    sep_display = 'spacja/tab' if sep == r'\s+' else sep
                    print(f"{Fore.GREEN}Plik wczytany poprawnie (separator: '{sep_display}', {len(df)} wierszy).")
                    return df
            except Exception:
                continue
        raise ValueError("Nie udało się zinterpretować pliku. Sprawdź format i separator.")
    except Exception as e:
        print(f"{Fore.RED}Błąd podczas wczytywania pliku: {e}")
        return None

def has_easting_structure(coord: float) -> bool:
    """Sprawdza, czy podana współrzędna ma strukturę Eastingu w układzie PL-2000."""
    try:
        coord_str = str(int(coord))
        # Easting w PL-2000 ma 7 cyfr i zaczyna się od 5, 6, 7 lub 8
        return len(coord_str) == 7 and coord_str[0] in ['5', '6', '7', '8']
    except (ValueError, TypeError, IndexError):
        return False

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

def transform_coordinates(df: pd.DataFrame) -> List[Tuple[float, float]]:
    """Transformuje współrzędne z układu PL-2000 do PL-1992 (EPSG:2180)."""
    transformed_points = []
    print(f"\n{Fore.CYAN}Transformuję współrzędne z PL-2000 do PL-1992 (EPSG:2180)...{Style.RESET_ALL}")

    for _, row in df.iterrows():
        northing = row['geodetic_northing']
        easting = row['geodetic_easting']
        source_epsg = get_source_epsg(easting)
        
        if source_epsg is None:
            if DEBUG_MODE:
                print(f"{Fore.YELLOW}[DEBUG-OSTRZEŻENIE] Nie można określić strefy dla ptk {row.id} (Easting={easting}). Pomijam.{Style.RESET_ALL}")
            transformed_points.append((0.0, 0.0)) 
            continue

        # Tworzenie obiektu transformującego z biblioteki pyproj
        transformer = Transformer.from_crs(f"EPSG:{source_epsg}", "EPSG:2180")
        
        # WAŻNE: pyproj dla tych układów oczekuje kolejności (Northing, Easting),
        # a zwraca w standardzie GIS, czyli (Easting, Northing).
        x_gis_easting, y_gis_northing = transformer.transform(northing, easting)
        transformed_points.append((x_gis_easting, y_gis_northing))
    
    print(f"{Fore.GREEN}Transformacja zakończona.{Style.RESET_ALL}")
    return transformed_points

def get_geoportal_heights(transformed_points: List[Tuple[float, float]]) -> Dict[str, float]:
    """Pobiera wysokości dla listy punktów z API Geoportalu w jednym zapytaniu."""
    print(f"\n{Fore.CYAN}Pobieranie danych wysokościowych z Geoportalu...{Style.RESET_ALL}")
    
    # Filtrowanie punktów, które mogły nie zostać poprawnie przetransformowane
    valid_points = [p for p in transformed_points if p != (0.0, 0.0)]
    if not valid_points:
        print(f"{Fore.YELLOW}Brak poprawnych punktów do wysłania do API Geoportalu.")
        return {}
    
    # Formatowanie listy punktów do postaci tekstowej wymaganej przez API
    point_strings = [f"{easting:.2f} {northing:.2f}" for easting, northing in valid_points]
    list_parameter = ",".join(point_strings)
    url = f"https://services.gugik.gov.pl/nmt/?request=GetHByPointList&list={list_parameter}"
    
    try:
        # Wysłanie zapytania HTTP GET
        response = requests.get(url, timeout=30)
        # Sprawdzenie, czy zapytanie zakończyło się sukcesem (kod 2xx)
        response.raise_for_status()
        geoportal_heights = {}
        # Parsowanie odpowiedzi tekstowej
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

def process_data(input_df: pd.DataFrame, 
                comparison_df: Optional[pd.DataFrame], 
                use_geoportal: bool,
                max_distance: float) -> pd.DataFrame:
    """Główna funkcja przetwarzająca dane, wykonująca transformacje i porównania."""
    results = []
    total_points = len(input_df)
    
    # Zachowanie oryginalnych współrzędnych do zapisu w pliku wynikowym
    input_df['x_oryginal'] = input_df['x']
    input_df['y_oryginal'] = input_df['y']
    
    # Przypisanie ról geodezyjnych na podstawie struktury danych
    input_df = assign_geodetic_roles(input_df)
    
    # Transformacja współrzędnych, jeśli wybrano opcję z Geoportalem
    geoportal_heights, transformed_points = {}, []
    if use_geoportal:
        transformed_points = transform_coordinates(input_df)
        if transformed_points:
            geoportal_heights = get_geoportal_heights(transformed_points)
        
    # Przygotowanie do zaawansowanego parowania punktów między plikami
    tree_input, tree_comparison = None, None
    if comparison_df is not None:
        print(f"\n{Fore.CYAN}Przygotowuję zaawansowane parowanie punktów...{Style.RESET_ALL}")
        comparison_df['x_oryginal'] = comparison_df['x']
        comparison_df['y_oryginal'] = comparison_df['y']
        
        # Stworzenie struktur danych (drzew KD) do ultraszybkiego wyszukiwania najbliższych sąsiadów
        input_points = input_df[['x_oryginal', 'y_oryginal']].values
        comparison_points = comparison_df[['x_oryginal', 'y_oryginal']].values
        
        tree_input = KDTree(input_points)
        tree_comparison = KDTree(comparison_points)
        print(f"{Fore.GREEN}Indeksy do porównania gotowe.{Style.RESET_ALL}")
    
    paired_count = 0
    print(f"\n{Fore.CYAN}Przetwarzam punkty...{Style.RESET_ALL}")
    # Główna pętla iterująca po każdym punkcie z pliku wejściowego
    for i, (_, point) in enumerate(input_df.iterrows()):
        # Słownik przechowujący dane dla jednego wiersza w pliku wynikowym
        row_data = {
            'id_odniesienia': point['id'],
            'x_odniesienia': point['x_oryginal'],
            'y_odniesienia': point['y_oryginal'],
            'h_odniesienia': point['h'],
        }
        
        # Logika parowania punktów, jeśli wybrano tę opcję
        if comparison_df is not None and tree_comparison is not None and tree_input is not None:
            # 1. Znajdź najbliższego sąsiada w pliku porównawczym
            distance, nearest_idx_in_comp = tree_comparison.query([point['x_oryginal'], point['y_oryginal']])
            
            # 2. Sprawdź warunek maksymalnej odległości
            is_within_distance = (max_distance == 0) or (distance <= max_distance)
            
            if is_within_distance:
                # 3. Sprawdź warunek wzajemności (czy sąsiad sąsiada to ten sam punkt)
                nearest_in_comp_point = comparison_df.iloc[nearest_idx_in_comp]
                _, nearest_idx_in_input = tree_input.query([nearest_in_comp_point['x_oryginal'], nearest_in_comp_point['y_oryginal']])
                
                is_reciprocal = (i == nearest_idx_in_input)
                
                # Para jest akceptowana tylko, jeśli OBA warunki są spełnione
                if is_reciprocal:
                    row_data['id_porownania'] = nearest_in_comp_point['id']
                    row_data['x_porownania'] = nearest_in_comp_point['x_oryginal']
                    row_data['y_porownania'] = nearest_in_comp_point['y_oryginal']
                    row_data['h_porownania'] = nearest_in_comp_point['h']
                    row_data['odleglosc_pary'] = distance
                    paired_count += 1
        
        # Dodanie wysokości z Geoportalu, jeśli wybrano tę opcję
        if use_geoportal and transformed_points:
            easting_2180, northing_2180 = transformed_points[i]
            lookup_key = f"{easting_2180:.2f} {northing_2180:.2f}"
            height = geoportal_heights.get(lookup_key, "brak_danych")
            row_data['geoportal_h'] = str(height)
        
        results.append(row_data)
        
        # Wyświetlanie paska postępu
        progress = (i + 1) / total_points
        bar_length = 40
        block = int(round(bar_length * progress))
        text = f"\rPrzetworzono {i+1}/{total_points} punktów: [{'#' * block}{'-' * (bar_length - block)}] {int(progress * 100)}%"
        sys.stdout.write(text)
        sys.stdout.flush()
    print("\n")
    if comparison_df is not None:
        print(f"{Fore.GREEN}Znaleziono i połączono {paired_count} par punktów.{Style.RESET_ALL}")
        
    return pd.DataFrame(results)

def main():
    """Główna funkcja programu, która steruje całym procesem."""
    clear_screen()
    display_welcome_screen()
    
    # Krok 1: Pobranie danych od użytkownika
    choice = get_user_choice()
    
    max_distance = 0.0
    if choice in [1, 3]:
        max_distance = get_max_distance()
        
    input_file = get_file_path("\nPodaj ścieżkę do pliku wejściowego: ")
    comparison_file = None
    if choice in [1, 3]:
        comparison_file = get_file_path("Podaj ścieżkę do pliku porównawczego: ")
    
    # Krok 2: Wczytanie danych z plików
    print(f"\n{Fore.CYAN}--- Wczytywanie danych ---{Style.RESET_ALL}")
    input_df = load_data(input_file)
    if input_df is None or input_df.empty:
        print(f"{Fore.RED}Nie udało się wczytać danych wejściowych. Zamykanie programu.")
        return
    
    comparison_df = None
    if comparison_file:
        comparison_df = load_data(comparison_file)
    
    # Krok 3: Główna logika przetwarzania
    use_geoportal = choice in [2, 3]
    results_df = process_data(input_df, comparison_df, use_geoportal, max_distance)
    
    # Krok 4: Zapis wyników do pliku CSV
    if not results_df.empty:
        output_file = 'wynik.csv'
        print(f"\n{Fore.CYAN}--- Zapisywanie wyników ---{Style.RESET_ALL}")
        
        # Definicja kolumn w pliku wynikowym
        output_columns = ['id_odniesienia', 'x_odniesienia', 'y_odniesienia', 'h_odniesienia']
        if 'id_porownania' in results_df.columns:
            output_columns.extend(['id_porownania', 'x_porownania', 'y_porownania', 'h_porownania', 'odleglosc_pary'])
        if 'geoportal_h' in results_df.columns:
            output_columns.append('geoportal_h')
        
        # Zapis do pliku CSV z odpowiednim formatowaniem
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