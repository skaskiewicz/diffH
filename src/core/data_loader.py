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
    logging.debug(
        f"Rozpoczęto wczytywanie pliku zakresu: {file_path}, swap_xy={swap_xy}"
    )
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
                        print(
                            f"{Fore.GREEN}Plik wczytany poprawnie (separator: '{sep_display}')."
                        )
                        logging.debug(
                            f"Plik zakresu wczytany z separatorem '{sep_display}'."
                        )
                        break
                except pd.errors.ParserError:
                    logging.debug(
                        f"Nie udało się sparsować pliku zakresu z separatorem '{sep}'. Próbuję dalej."
                    )
                    continue

        if df is None:
            print(
                f"{Fore.RED}Błąd: Nie udało się wczytać pliku zakresu lub ma on niepoprawną liczbę kolumn (oczekiwano 2 lub 3)."
            )
            logging.error(
                "Nie udało się wczytać pliku zakresu - nie znaleziono separatora lub niepoprawna liczba kolumn."
            )
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
                logging.debug(
                    f"Wykryto i pominięto nagłówek w pliku zakresu: {df.iloc[0].to_list()}"
                )
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
            logging.error(
                "Plik zakresu zawiera nienumeryczne wartości w kolumnach X/Y."
            )
            return None

        df.dropna(subset=["x", "y"], inplace=True)
        print(f"Wczytano {len(df)} wierzchołków zakresu.")
        logging.debug(
            f"Pomyślnie wczytano i przetworzono {len(df)} wierzchołków zakresu."
        )
        return df

    except Exception as e:
        print(f"{Fore.RED}Błąd podczas wczytywania pliku zakresu: {e}")
        logging.error(
            f"Nieoczekiwany błąd podczas wczytywania pliku zakresu: {e}", exc_info=True
        )
        return None


def load_data(
    file_path: str, swap_xy: bool = False, expect_height_column: bool = True
) -> Optional[pd.DataFrame]:
    """
    Wczytuje dane z pliku CSV, XLS lub XLSX, sprawdza strukturę i zwraca DataFrame.
    Steruje oczekiwaniami co do kolumn za pomocą flagi 'expect_height_column'.

    Args:
        file_path (str): Ścieżka do pliku z danymi.
        swap_xy (bool): Czy zamienić kolumny X i Y.
        expect_height_column (bool): Jeśli True, oczekuje kolumny H (tryby 1-3).
                                    Jeśli False, oczekuje tylko kolumn XY (tryb 4).
    """
    print(f"Wczytuję plik danych: {file_path}")
    logging.debug(
        f"Rozpoczęto wczytywanie pliku: {file_path}, swap_xy={swap_xy}, expect_height={expect_height_column}"
    )
    df = None
    try:
        # 1. Wczytanie surowych danych (logika wspólna)
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
                # Sprawdzamy, czy w ogóle mamy jakieś kolumny do pracy
                if len(temp_df.columns) >= 2:
                    df = temp_df
                    sep_display = "spacja/tab" if sep == r"\s+" else sep
                    print(
                        f"{Fore.GREEN}Plik wczytany poprawnie (separator: '{sep_display}')."
                    )
                    logging.debug(f"Plik wczytany z separatorem '{sep_display}'.")
                    break

        if df is None:
            print(
                f"{Fore.RED}Nie udało się rozpoznać separatora lub plik ma mniej niż 2 kolumny."
            )
            return None

        # 2. Pomijanie nagłówka (logika wspólna)
        if len(df) > 0:
            try:
                # Sprawdź, czy w ostatniej kolumnie jest liczba (najbezpieczniejsza metoda)
                pd.to_numeric(str(df.iloc[0, -1]).replace(",", "."))
            except (ValueError, TypeError):
                print(
                    f"{Fore.YELLOW}Wykryto nagłówek. Pierwszy wiersz zostanie pominięty.{Style.RESET_ALL}"
                )
                logging.debug(f"Wykryto i pominięto nagłówek: {df.iloc[0].to_list()}")
                df = df.iloc[1:].reset_index(drop=True)

        # 3. Logika walidacji i przypisywania kolumn (zależna od flagi)
        num_cols = len(df.columns)
        logging.debug(f"Wykryto {num_cols} kolumn.")

        cols_to_process = []
        if expect_height_column:
            # --- LOGIKA DLA TRYBÓW 1-3 (z wysokością) ---
            if num_cols >= 4:
                if num_cols > 4:
                    print(
                        f"{Fore.YELLOW}Wykryto więcej niż 4 kolumny. Użyte zostaną pierwsze 4."
                    )
                df = df.iloc[:, :4]
                df.columns = ["id", "x", "y", "h"]
            elif num_cols == 3:
                print(f"{Fore.YELLOW}Wykryto 3 kolumny (brak ID).")
                prefix = (
                    input(
                        f"{Fore.YELLOW}Podaj prefiks dla autonumeracji (np. P): {Style.RESET_ALL}"
                    ).strip()
                    or "P"
                )
                df.columns = ["x", "y", "h"]
                df.insert(0, "id", [f"{prefix}_{i + 1}" for i in range(len(df))])
            else:
                print(
                    f"{Fore.RED}Błąd: Plik musi mieć 3 lub 4 kolumny (wykryto: {num_cols})."
                )
                return None
            cols_to_process = ["x", "y", "h"]
        else:
            # --- LOGIKA DLA TRYBU 4 (bez wysokości) ---
            if num_cols >= 3:
                if num_cols > 3:
                    print(
                        f"{Fore.YELLOW}Wykryto więcej niż 3 kolumny. Użyte zostaną pierwsze 3."
                    )
                df = df.iloc[:, :3]
                df.columns = ["id", "x", "y"]
            elif num_cols == 2:
                print(f"{Fore.YELLOW}Wykryto 2 kolumny (brak ID).")
                prefix = (
                    input(
                        f"{Fore.YELLOW}Podaj prefiks dla autonumeracji (np. P): {Style.RESET_ALL}"
                    ).strip()
                    or "P"
                )
                df.columns = ["x", "y"]
                df.insert(0, "id", [f"{prefix}_{i + 1}" for i in range(len(df))])
            else:
                print(
                    f"{Fore.RED}Błąd: Plik musi mieć 2 lub 3 kolumny (wykryto: {num_cols})."
                )
                return None
            cols_to_process = ["x", "y"]

        # 4. Zamiana X/Y i konwersja na typy numeryczne (logika wspólna)
        if swap_xy:
            df[["x", "y"]] = df[["y", "x"]]
            logging.debug("Zamieniono kolumny X i Y.")

        for col in cols_to_process:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "."), errors="coerce"
            )

        # Sprawdzenie, czy po konwersji nie ma pustych wartości w kluczowych kolumnach
        if df[cols_to_process].isnull().values.any():
            print(
                f"{Fore.RED}Błąd: Plik zawiera nienumeryczne wartości w kolumnach współrzędnych."
            )
            logging.error("Plik zawiera nienumeryczne wartości po konwersji.")
            return None

        df.dropna(subset=cols_to_process, inplace=True)
        print(f"Wczytano {len(df)} wierszy.")
        logging.debug(f"Pomyślnie wczytano i przetworzono {len(df)} wierszy.")
        return df

    except Exception as e:
        print(f"{Fore.RED}Błąd podczas wczytywania pliku danych: {e}")
        logging.error(
            f"Nieoczekiwany błąd podczas wczytywania pliku: {e}", exc_info=True
        )
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
