"""
Funkcje pomocnicze interfejsu użytkownika
"""

import os
from colorama import Fore, Style
from ..config.settings import DEBUG_MODE


def clear_screen():
    """Czyści ekran konsoli"""
    os.system("cls" if os.name == "nt" else "clear")


def display_welcome_screen():
    """Wyświetla ekran powitalny aplikacji"""
    print(f"{Fore.GREEN}======================================")
    print(f"{Fore.GREEN}===           diffH               ===")
    print(f"{Fore.GREEN}======================================")
    if DEBUG_MODE:
        print(f"{Fore.MAGENTA}*** TRYB DEBUGOWANIA AKTYWNY (logi w pliku debug.log) ***")
    print(f"\n{Fore.WHITE}Instrukcja:")
    print("1. Przygotuj plik wejściowy:")
    print("   - Formaty: CSV, TXT, XLS, XLSX")
    print("   - Układ współrzędnych: PL-2000 (strefy 5,6,7,8)")
    print(
        "   - Struktura: [id, x, y, h] lub [id, y, x, h] albo [x, y, h] lub [y, x, h]"
    )
    print("   - Separatory: średnik, przecinek lub spacja/tab")
    print("\n2. Pliki wynikowe:")
    print("   - Pełne wyniki: wynik.csv, wynik.gpkg")
    print("   - Punkty spełniające dokładność: wynik_dokladne.csv, wynik_dokladne.gpkg")
    print("   - Punkty niespełniające: wynik_niedokladne.csv, wynik_niedokladne.gpkg")
    print("   - Opcjonalnie: wynik_siatka.csv, wynik_siatka.gpkg (siatka rozrzedzona)")
    print("\n3. Postępuj zgodnie z instrukcjami na ekranie.\n")


def get_user_choice() -> int:
    """Pobiera wybór użytkownika dotyczący rodzaju porównania"""
    while True:
        print(
            f"\n{Fore.YELLOW}Wybierz rodzaj porównania wysokości punktów:\n[1] Porównanie z innym plikiem pomiarowym\n[2] Porównanie z danymi z Geoportal.gov.pl (NMT)\n[3] Porównanie z obydwoma źródłami (plik + Geoportal.gov.pl)"
        )
        try:
            choice = int(input(f"\n{Fore.YELLOW}Twój wybór (1-3): {Style.RESET_ALL}"))
            if 1 <= choice <= 3:
                return choice
            print(f"{Fore.RED}Błąd: Wybierz liczbę od 1 do 3.")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.")


def get_file_path(prompt: str) -> str:
    """Pobiera ścieżkę do pliku od użytkownika"""
    while True:
        file_path = input(f"{Fore.YELLOW}{prompt}{Style.RESET_ALL}").strip()
        # Usuń tylko parę cudzysłowów lub apostrofów na początku i końcu
        if (file_path.startswith('"') and file_path.endswith('"')) or (
            file_path.startswith("'") and file_path.endswith("'")
        ):
            file_path = file_path[1:-1]
        if os.path.exists(file_path):
            return file_path
        print(f"{Fore.RED}Błąd: Plik nie istnieje. Spróbuj ponownie.")


def get_max_distance() -> float:
    """
    Funkcja do pobrania maksymalnej odległości wyszukiwania pary w metrach.
    Domyślnie ustawiona na 15 metrów. Użytkownik może wpisać 0, aby pominąć ten warunek.
    Jeśli użytkownik nie poda wartości, zostanie przyjęta domyślna wartość 15 metrów.
    Returns:
        float: Maksymalna odległość wyszukiwania pary w metrach.
    """
    default_distance = 15.0
    while True:
        try:
            prompt = (
                f"\n{Fore.YELLOW}Podaj maksymalną odległość wyszukiwania pary w metrach (np. 0.5)\n"
                f"(Wpisz 0, aby pominąć ten warunek, domyślnie {default_distance} m): {Style.RESET_ALL}"
            )
            distance_str = input(prompt)
            if not distance_str.strip():
                print(
                    f"{Fore.CYAN}Przyjęto domyślną wartość: {default_distance} m{Style.RESET_ALL}"
                )
                return default_distance
            distance = float(distance_str.replace(",", "."))
            if distance >= 0:
                return distance
            print(f"{Fore.RED}Błąd: Odległość nie może być ujemna.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.{Style.RESET_ALL}")


def ask_swap_xy(file_label: str) -> bool:
    """
    Funkcja do zapytania użytkownika, czy plik ma zamienioną kolejność kolumn (Y,X zamiast X,Y).
    Args:
        file_label (str): Etykieta pliku, która zostanie wyświetlona w komunikacie.
    Returns:
        bool: True jeśli kolumny są zamienione, False jeśli nie.
    """
    default = "n"
    while True:
        resp = (
            input(
                f"{Fore.YELLOW}Czy plik {file_label} ma zamienioną kolejność kolumn (Y,X zamiast X,Y)? [t/n] (domyślnie: n): {Style.RESET_ALL}"
            )
            .strip()
            .lower()
        )
        if not resp:
            print(f"{Fore.CYAN}Przyjęto domyślną odpowiedź: {default}{Style.RESET_ALL}")
            return False
        if resp in ["t", "tak", "y", "yes"]:
            return True
        if resp in ["n", "nie", "no"]:
            return False
        print(f"{Fore.YELLOW}Wpisz 't' (tak) lub 'n' (nie).{Style.RESET_ALL}")


def get_geoportal_tolerance() -> float:
    """
    Funkcja do pobrania dopuszczalnej różnicy wysokości względem Geoportalu w metrach.
    Domyślnie ustawiona na 0.2 metra. Użytkownik może wpisać 0, aby pominąć ten warunek.
    Returns:
        float: Dopuszczalna różnica wysokości względem Geoportalu w metrach.
    """
    default_tolerance = 0.2
    while True:
        try:
            prompt = (
                f"\n{Fore.YELLOW}Podaj dopuszczalną różnicę wysokości względem Geoportalu (w metrach, np. 0.2) "
                f"(domyślnie: {default_tolerance}): {Style.RESET_ALL}"
            )
            val = input(prompt)
            if not val.strip():
                print(
                    f"{Fore.CYAN}Przyjęto domyślną wartość: {default_tolerance}{Style.RESET_ALL}"
                )
                return default_tolerance
            val = float(val.replace(",", "."))
            if val >= 0:
                return val
            print(f"{Fore.RED}Błąd: Wartość nie może być ujemna.{Style.RESET_ALL}")
        except ValueError:
            print(f"{Fore.RED}Błąd: Wprowadź poprawną liczbę.{Style.RESET_ALL}")


def get_round_decimals() -> int:
    """
    Funkcja do pobrania liczby miejsc po przecinku do zaokrąglenia danych wejściowych.
    Domyślnie ustawiona na 1 miejsce po przecinku.
    Returns:
        int: Liczba miejsc po przecinku do zaokrąglenia danych wejściowych.
    """
    default_decimals = 1
    while True:
        try:
            prompt = f"\n{Fore.YELLOW}Podaj liczbę miejsc po przecinku do zaokrąglenia danych wejściowych (domyślnie: {default_decimals}): {Style.RESET_ALL}"
            val = input(prompt)
            if not val.strip():
                print(
                    f"{Fore.CYAN}Przyjęto domyślną wartość: {default_decimals}{Style.RESET_ALL}"
                )
                return default_decimals
            val_int = int(val)
            if 0 <= val_int <= 6:
                return val_int
            print(f"{Fore.RED}Błąd: Podaj liczbę z zakresu 0-6.{Style.RESET_ALL}")
        except ValueError:
            print(
                f"{Fore.RED}Błąd: Wprowadź poprawną liczbę całkowitą.{Style.RESET_ALL}"
            ) 