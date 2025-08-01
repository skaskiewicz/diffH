"""
Moduł wczytywania danych z plików
"""

import os
import logging
import pandas as pd
from typing import Optional
from colorama import Fore, Style


def load_scope_data(file_path: str, swap_xy: bool = False) -> Optional[pd.DataFrame]:
    """
    Wczytuje i waliduje plik z zakresem (wielobokiem).
    Akceptuje 2 lub 3 kolumny (XY, YX, NrXY, NrYX).
    Sprawdza, czy kolumny współrzędnych są numeryczne.
    """
    print(f"Wczytuję plik z zakresem: {file_path}")
    logging.debug(f"Rozpoczęto wczytywanie pliku zakresu: {file_path}, swap_xy={swap_xy}")
    df = None
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in [".xls", ".xlsx"]:
            df = pd.read_excel(file_path, header=None, dtype=str)
        else:
            # Próba wczytania z różnymi separatorami
            for sep in [";", ",", r"\s+"]:
                # Używamy try-except, aby uniknąć błędów przy parsowaniu
                try:
                    temp_df = pd.read_csv(
                        file_path,
                        sep=sep,
                        header=None,
                        on_bad_lines="skip",
                        engine="python",
                        dtype=str,
                    ).dropna(how="all", axis=1)
                    if len(temp_df.columns) in [2, 3]:
                        df = temp_df
                        sep_display = "spacja/tab" if sep == r"\s+" else sep
                        print(f"{Fore.GREEN}Plik wczytany poprawnie (separator: '{sep_display}').")
                        logging.debug(f"Plik zakresu wczytany z separatorem '{sep_display}'.")
                        break
                except pd.errors.ParserError:
                    logging.debug(f"Nie udało się sparsować pliku zakresu z separatorem '{sep}'. Próbuję dalej.")
                    continue

        if df is None:
            print(
                f"{Fore.RED}Błąd: Nie udało się wczytać pliku zakresu lub ma on niepoprawną liczbę kolumn (oczekiwano 2 lub 3)."
            )
            logging.error("Nie udało się wczytać pliku zakresu - nie znaleziono separatora lub niepoprawna liczba kolumn.")
            return None

        # Pomijanie nagłówka - sprawdzamy każdy element osobno
        if not df.empty:
            first_row_vals = df.iloc[0].values
            is_header = False
            try:
                # Sprawdź czy wartości w potencjalnych kolumnach X, Y są liczbami
                for val in first_row_vals[
                    -2:
                ]:  # Iterujemy po dwóch ostatnich elementach
                    pd.to_numeric(str(val).replace(",", "."))
            except (ValueError, TypeError):
                # Jeśli konwersja się nie powiedzie dla któregokolwiek elementu, to jest to nagłówek
                is_header = True

            if is_header:
                print(
                    f"{Fore.YELLOW}Wykryto nagłówek w pliku zakresu. Pierwszy wiersz zostanie pominięty.{Style.RESET_ALL}"
                )
                logging.debug(f"Wykryto i pominięto nagłówek w pliku zakresu: {df.iloc[0].to_list()}")
                df = df.iloc[1:].reset_index(drop=True)

        # Jeśli po usunięciu nagłówka ramka jest pusta
        if df.empty:
            print(
                f"{Fore.RED}Błąd: Plik zakresu jest pusty lub zawierał tylko nagłówek."
            )
            logging.error("Plik zakresu jest pusty po usunięciu nagłówka.")
            return None

        # Przypisanie nazw kolumn
        if len(df.columns) == 2:
            df.columns = ["x", "y"]
        else:  # len == 3
            df.columns = ["id", "x", "y"]
        logging.debug(f"Przypisano kolumny: {df.columns.to_list()}")

        if swap_xy:
            df[["x", "y"]] = df[["y", "x"]]
            logging.debug("Zamieniono kolumny X i Y w pliku zakresu.")

        # Walidacja numeryczności kolumn X i Y
        for col in ["x", "y"]:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "."), errors="coerce"
            )

        if df[["x", "y"]].isnull().values.any():
            print(
                f"{Fore.RED}Błąd: Plik zakresu zawiera nienumeryczne wartości w kolumnach współrzędnych. Popraw plik i spróbuj ponownie."
            )
            logging.error("Plik zakresu zawiera nienumeryczne wartości w kolumnach X/Y.")
            return None

        df.dropna(subset=["x", "y"], inplace=True)
        print(f"Wczytano {len(df)} wierzchołków zakresu.")
        logging.debug(f"Pomyślnie wczytano i przetworzono {len(df)} wierzchołków zakresu.")
        return df

    except Exception as e:
        print(f"{Fore.RED}Błąd podczas wczytywania pliku zakresu: {e}")
        logging.error(f"Nieoczekiwany błąd podczas wczytywania pliku zakresu: {e}", exc_info=True)
        return None


def load_data(file_path: str, swap_xy: bool = False) -> Optional[pd.DataFrame]:
    """
    Wczytuje dane z pliku CSV, XLS lub XLSX, sprawdza strukturę i zwraca DataFrame.
    Args:
        file_path (str): Ścieżka do pliku z danymi.
    swap_xy (bool): Czy zamienić kolumny X i Y (domyślnie False).
    """
    print(f"Wczytuję plik danych: {file_path}")
    logging.debug(f"Rozpoczęto wczytywanie pliku danych: {file_path}, swap_xy={swap_xy}")
    df = None
    try:
        # 1. Wczytanie surowych danych do DataFrame
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in [".xls", ".xlsx"]:
            df = pd.read_excel(file_path, header=None, dtype=str).dropna(
                how="all", axis=1
            )
        else:
            for sep in [";", ",", r"\s+"]:
                temp_df = pd.read_csv(
                    file_path,
                    sep=sep,
                    header=None,
                    on_bad_lines="skip",
                    engine="python",
                    dtype=str,
                ).dropna(how="all", axis=1)
                if len(temp_df.columns) > 1:
                    df = temp_df
                    sep_display = "spacja/tab" if sep == r"\s+" else sep
                    print(
                        f"{Fore.GREEN}Plik wczytany poprawnie (separator: '{sep_display}')."
                    )
                    logging.debug(f"Plik danych wczytany z separatorem '{sep_display}'.")
                    break

        if df is None:
            print(
                f"{Fore.RED}Nie udało się rozpoznać separatora lub plik nie ma poprawnej struktury."
            )
            logging.error("Nie udało się wczytać pliku danych - nie znaleziono separatora lub niepoprawna struktura.")
            return None

        # 2. Pomijanie nagłówka
        if len(df) > 0:
            try:
                # Sprawdź, czy w drugim wierszu jest liczba
                pd.to_numeric(str(df.iloc[0, 1]).replace(",", "."))
            except (ValueError, TypeError):
                print(
                    f"{Fore.YELLOW}Wykryto nagłówek w pliku. Pierwszy wiersz zostanie pominięty.{Style.RESET_ALL}"
                )
                logging.debug(f"Wykryto i pominięto nagłówek w pliku danych: {df.iloc[0].to_list()}")
                df = df.iloc[1:].reset_index(drop=True)

        # 3. Logika walidacji i przypisywania kolumn
        num_cols = len(df.columns)
        logging.debug(f"Wykryto {num_cols} kolumn w pliku danych.")
        if num_cols >= 4:
            if num_cols > 4:
                print(
                    f"{Fore.YELLOW}Wykryto więcej niż 4 kolumny. Importowane będą tylko pierwsze 4."
                )
                logging.warning(f"Wykryto {num_cols} kolumn, użyte zostaną tylko pierwsze 4.")
            df = df.iloc[:, :4]
            df.columns = ["id", "x", "y", "h"]

        elif num_cols == 3:
            # Rygorystyczna walidacja numeryczności dla 3 kolumn
            is_numeric_cols = df.apply(
                lambda s: pd.to_numeric(
                    s.astype(str).str.replace(",", "."), errors="coerce"
                )
                .notna()
                .all()
            ).values
            if not all(is_numeric_cols):
                print(
                    f"{Fore.RED}Błąd: Plik ma 3 kolumny, ale nie wszystkie są numeryczne. Oczekiwano formatu X,Y,H."
                )
                print(f"{Fore.RED}Popraw plik.")
                logging.error("Plik ma 3 kolumny, ale nie wszystkie są numeryczne.")
                return None

            # Jeśli walidacja się powiodła
            print(f"{Fore.YELLOW}Wykryto 3 kolumny numeryczne (brak ID).")
            prefix = (
                input(
                    f"{Fore.YELLOW}Podaj prefiks dla autonumeracji punktów (np. P): {Style.RESET_ALL}"
                ).strip()
                or "P"
            )
            df.columns = ["x", "y", "h"]
            df.insert(0, "id", [f"{prefix}_{i + 1}" for i in range(len(df))])
            print(
                f"{Fore.GREEN}Dodano automatyczną numerację punktów z prefiksem '{prefix}'."
            )
            logging.debug(f"Dodano autonumerację z prefiksem '{prefix}'.")

        else:
            print(
                f"{Fore.RED}Błąd: Plik musi mieć 3 lub 4 kolumny (wykryto: {num_cols}). Import przerwany."
            )
            logging.error(f"Niepoprawna liczba kolumn: {num_cols}. Oczekiwano 3 lub 4.")
            return None

        # 4. Zamiana X/Y i konwersja na typy numeryczne
        if swap_xy:
            df[["x", "y"]] = df[["y", "x"]]
            logging.debug("Zamieniono kolumny X i Y w pliku danych.")

        for col in ["x", "y", "h"]:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "."), errors="coerce"
            )

        df.dropna(subset=["x", "y", "h"], inplace=True)
        print(f"Wczytano {len(df)} wierszy.")
        logging.debug(f"Pomyślnie wczytano i przetworzono {len(df)} wierszy danych.")
        return df

    except Exception as e:
        print(f"{Fore.RED}Błąd podczas wczytywania pliku danych: {e}")
        logging.error(f"Nieoczekiwany błąd podczas wczytywania pliku danych: {e}", exc_info=True)
        return None


def has_easting_structure(coord: float) -> bool:
    """
    Sprawdza, czy współrzędna ma strukturę wschodniej (easting) w układzie PL-2000.
    Args:
        coord (float): Współrzędna do sprawdzenia.
    Returns:
        bool: True jeśli współrzędna ma strukturę wschodniej, False w przeciwnym razie.
    """
    try:
        coord_str = str(int(coord))
        return len(coord_str) == 7 and coord_str[0] in ["5", "6", "7", "8"]
    except (ValueError, TypeError, IndexError):
        return False


def assign_geodetic_roles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Funkcja przypisuje kolumnom 'geodetic_northing' i 'geodetic_easting' odpowiednie wartości
    na podstawie struktury współrzędnych w DataFrame.
    Args:
        df (pd.DataFrame): DataFrame z kolumnami 'x' i 'y'.
    Returns:
        pd.DataFrame: DataFrame z dodanymi kolumnami 'geodetic_northing' i 'geodetic_easting'.
    """
    if df.empty:
        return df
    first_row = df.iloc[0]
    if has_easting_structure(first_row["y"]):
        df["geodetic_northing"], df["geodetic_easting"] = df["x"], df["y"]
    elif has_easting_structure(first_row["x"]):
        df["geodetic_northing"], df["geodetic_easting"] = df["y"], df["x"]
    else:
        df["geodetic_northing"], df["geodetic_easting"] = df["x"], df["y"]
    return df


def get_source_epsg(easting_coordinate: float) -> Optional[int]:
    """
    Funkcja do określenia strefy EPSG na podstawie współrzędnej wschodniej (easting).
    Args:
        easting_coordinate (float): Współrzędna wschodnia do sprawdzenia.
    Returns:
        Optional[int]: Kod EPSG strefy, lub None jeśli nie można określić.
    """
    try:
        easting_str = str(int(easting_coordinate))
        if len(easting_str) == 7:
            return {"5": 2176, "6": 2177, "7": 2178, "8": 2179}.get(easting_str[0])
    except (ValueError, TypeError, IndexError):
        return None
    return None 