"""
Główny moduł procesora aplikacji diffH
"""

import os
import logging
import traceback
import pandas as pd
from typing import Optional
from tqdm import tqdm
from scipy.spatial import KDTree
from colorama import Fore, Style

from ..utils.logging_config import setup_logging
from ..utils.ui_helpers import (
    clear_screen, display_welcome_screen, get_user_choice,
    get_file_path, get_max_distance, ask_swap_xy,
    get_geoportal_tolerance, get_round_decimals
)
from ..config.settings import DEBUG_MODE, DEFAULT_SPARSE_GRID_DISTANCE
from .data_loader import load_data, load_scope_data, assign_geodetic_roles, get_source_epsg
from .coordinate_transform import transform_coordinates_parallel
from .geoportal_client import get_geoportal_heights_concurrent
from .grid_generator import znajdz_punkty_dla_siatki
from .export import export_to_csv, export_to_geopackage


def process_data(
    input_df: pd.DataFrame,
    comparison_df: Optional[pd.DataFrame],
    use_geoportal: bool,
    max_distance: float,
    geoportal_tolerance: Optional[float] = None,
    round_decimals: int = 1,
) -> pd.DataFrame:
    """
    Główna funkcja przetwarzająca dane wejściowe, wykonująca transformację współrzędnych,
    porównanie z danymi referencyjnymi oraz eksport wyników do pliku GeoPackage.
    """
    results = []
    input_df = assign_geodetic_roles(input_df)
    logging.debug("Rozpoczęto główną funkcję przetwarzania danych 'process_data'.")
    
    geoportal_heights, transformed_points = {}, []
    if use_geoportal:
        transformed_points = transform_coordinates_parallel(input_df)
        if transformed_points:
            geoportal_heights = get_geoportal_heights_concurrent(transformed_points)

    if DEBUG_MODE and use_geoportal:
        # 1. Eksport wyników transformacji
        if transformed_points:
            transform_results_for_debug = []
            for i, point in enumerate(transformed_points):
                original_id = input_df.iloc[i]['id']
                if point:
                    transform_results_for_debug.append({'id_punktu': original_id, 'x_2180': point[0], 'y_2180': point[1]})
                else:
                    transform_results_for_debug.append({'id_punktu': original_id, 'x_2180': 'Błąd', 'y_2180': 'Błąd'})
            
            if transform_results_for_debug:
                debug_transform_df = pd.DataFrame(transform_results_for_debug)
                debug_transform_df.to_csv("debug_transformacja_wyniki.csv", sep=';', index=False, float_format='%.2f')
                logging.debug("Zapisano wyniki transformacji do pliku debug_transformacja_wyniki.csv")

        # 2. Eksport punktów, dla których nie udało się pobrać wysokości
        missing_height_points = []
        for i, transformed_point in enumerate(transformed_points):
            if transformed_point:
                lookup_key = f"{transformed_point[1]:.2f} {transformed_point[0]:.2f}"
                if lookup_key not in geoportal_heights:
                    original_point = input_df.iloc[i]
                    missing_height_points.append({
                        'id_odniesienia': original_point['id'],
                        'x_odniesienia': original_point['x'],
                        'y_odniesienia': original_point['y']
                    })
        
        if missing_height_points:
            debug_missing_df = pd.DataFrame(missing_height_points)
            debug_missing_df.to_csv("debug_geoportal_brak_wysokosci.csv", sep=';', index=False, float_format=f'%.{round_decimals}f')
            logging.debug(f"Zapisano {len(missing_height_points)} punktów bez wysokości z Geoportalu do pliku debug_geoportal_brak_wysokosci.csv")
            
    tree_comparison = None
    if comparison_df is not None and not comparison_df.empty:
        comparison_points = comparison_df[["x", "y"]].values
        tree_comparison = KDTree(comparison_points)
        logging.debug("Utworzono KDTree dla pliku porównawczego.")
        
    paired_count = 0
    for i, (_, point) in enumerate(
        tqdm(input_df.iterrows(), total=len(input_df), desc="Przetwarzanie punktów")
    ):
        row_data = {
            "id_odniesienia": point["id"],
            "x_odniesienia": point["x"],
            "y_odniesienia": point["y"],
            "h_odniesienia": point["h"],
        }
        if tree_comparison is not None and comparison_df is not None:
            distance, nearest_idx = tree_comparison.query([point["x"], point["y"]])
            if (max_distance == 0) or (distance <= max_distance):
                nearest_in_comp_point = comparison_df.iloc[nearest_idx]
                row_data.update(
                    {
                        "id_porownania": nearest_in_comp_point["id"],
                        "x_porownania": nearest_in_comp_point["x"],
                        "y_porownania": nearest_in_comp_point["y"],
                        "h_porownania": nearest_in_comp_point["h"],
                        "odleglosc_pary": distance,
                    }
                )
                try:
                    diff = float(point["h"]) - float(nearest_in_comp_point["h"])
                    diff_rounded = round(diff, round_decimals)
                    if diff_rounded == -0.0:
                        diff_rounded = 0.0
                    row_data["diff_h"] = diff_rounded
                except (ValueError, TypeError):
                    row_data["diff_h"] = "brak_danych"
                paired_count += 1
                
        if use_geoportal and i < len(transformed_points):
            transformed_point = transformed_points[i]
            if transformed_point is not None:
                easting_2180, northing_2180 = transformed_point
                # lookup_key w formacie 'Y X' z dwoma miejscami po przecinku
                lookup_key = f"{northing_2180:.2f} {easting_2180:.2f}"
                height = geoportal_heights.get(lookup_key, "brak_danych")
                row_data["geoportal_h"] = str(height)
                if height == "brak_danych":
                    logging.debug(f"Brak wysokości z Geoportalu dla punktu {point['id']} ({lookup_key})")
                if height != "brak_danych" and pd.notnull(point["h"]):
                    try:
                        diff_h_geoportal = round(
                            float(point["h"]) - float(height), round_decimals
                        )
                        if diff_h_geoportal == -0.0:
                            diff_h_geoportal = 0.0
                        row_data["diff_h_geoportal"] = diff_h_geoportal
                        if geoportal_tolerance is not None:
                            row_data["osiaga_dokladnosc"] = (
                                "Tak"
                                if abs(diff_h_geoportal) <= geoportal_tolerance
                                else "Nie"
                            )
                    except (ValueError, TypeError):
                        row_data["diff_h_geoportal"] = "brak_danych"
                else:
                    row_data["diff_h_geoportal"] = "brak_danych"
            else:
                row_data["geoportal_h"] = "brak_danych"
                row_data["diff_h_geoportal"] = "brak_danych"
                logging.debug(f"Punkt {point['id']}: Brak przetransformowanych współrzędnych lub brak danych z geoportalu.")
        results.append(row_data)

    if comparison_df is not None:
        print(
            f"{Fore.GREEN}Znaleziono i połączono {paired_count} par punktów.{Style.RESET_ALL}"
        )
        logging.debug(f"Znaleziono i połączono {paired_count} par punktów.")
        
    results_df = pd.DataFrame(results)
    if use_geoportal and "diff_h_geoportal" in results_df.columns:
        results_df["__abs_diff_h_geoportal"] = pd.to_numeric(
            results_df["diff_h_geoportal"], errors="coerce"
        ).abs()
        results_df = results_df.sort_values(
            by="__abs_diff_h_geoportal", ascending=False
        ).drop(columns=["__abs_diff_h_geoportal"])
        
    final_cols = [
        "id_odniesienia",
        "x_odniesienia",
        "y_odniesienia",
        "h_odniesienia",
        "diff_h_geoportal",
        "geoportal_h",
        "osiaga_dokladnosc",
        "id_porownania",
        "x_porownania",
        "y_porownania",
        "h_porownania",
        "diff_h",
        "odleglosc_pary",
    ]
    existing_cols = [col for col in final_cols if col in results_df.columns]
    logging.debug("Zakończono główną funkcję przetwarzania danych.")
    return results_df[existing_cols]


def main():
    """Główna funkcja programu"""
    setup_logging()
    clear_screen()
    display_welcome_screen()
    choice = get_user_choice()
    max_distance = get_max_distance() if choice in [1, 3] else 0.0
    round_decimals = get_round_decimals()
    input_file = get_file_path(
        f"\n{Fore.YELLOW}Podaj ścieżkę do pliku wejściowego: {Style.RESET_ALL}"
    )
    swap_input = ask_swap_xy("wejściowego")
    comparison_file = None
    swap_comparison = False
    if choice in [1, 3]:
        comparison_file = get_file_path(
            f"{Fore.YELLOW}Podaj ścieżkę do pliku porównawczego: {Style.RESET_ALL}"
        )
        swap_comparison = ask_swap_xy("porównawczego")
    geoportal_tolerance = get_geoportal_tolerance() if choice in [2, 3] else None

    # --- Parametry eksportu rozrzedzonej siatki ---
    sparse_grid_requested = False
    sparse_grid_distance = DEFAULT_SPARSE_GRID_DISTANCE
    zakres_df = None
    if choice in [2, 3]:
        resp = (
            input(
                f"\n{Fore.YELLOW}Czy wykonać eksport rozrzedzonej siatki dla punktów spełniających dokładność? [t/n] (domyślnie: n): "
            )
            .strip()
            .lower()
        )
        if resp in ["t", "tak", "y", "yes"]:
            sparse_grid_requested = True
            dist_prompt = f"{Fore.YELLOW}Podaj oczekiwaną odległość pomiędzy punktami siatki (w metrach, domyślnie: {DEFAULT_SPARSE_GRID_DISTANCE}): {Style.RESET_ALL}"
            dist_val = input(dist_prompt).strip()
            if dist_val:
                try:
                    parsed_dist = float(dist_val.replace(",", "."))
                    if parsed_dist > 0:
                        sparse_grid_distance = parsed_dist
                    else:
                        print(
                            f"{Fore.RED}Błąd: Odległość musi być większa od zera. Przyjęto domyślną wartość {DEFAULT_SPARSE_GRID_DISTANCE} m."
                        )
                except ValueError:
                    print(
                        f"{Fore.RED}Błąd: Wprowadzono niepoprawną liczbę. Przyjęto domyślną wartość {DEFAULT_SPARSE_GRID_DISTANCE} m."
                    )
            print(
                f"{Fore.CYAN}Wybrano eksport rozrzedzonej siatki z parametrem odległości: {sparse_grid_distance} m{Style.RESET_ALL}"
            )
            zakres_file = get_file_path(
                f"{Fore.YELLOW}Podaj ścieżkę do pliku z zakresem opracowania (wierzchołki wieloboku): {Style.RESET_ALL}"
            )
            swap_scope = ask_swap_xy("z zakresem")
            zakres_df = load_scope_data(zakres_file, swap_scope)

    print(f"\n{Fore.CYAN}--- Wczytywanie danych ---{Style.RESET_ALL}")
    input_df = load_data(input_file, swap_input)
    if input_df is None or input_df.empty:
        print(
            f"{Fore.RED}Nie udało się wczytać danych wejściowych. Zamykanie programu."
        )
        return
    # Zaokrąglanie danych wejściowych
    for col in ["x", "y", "h"]:
        input_df[col] = input_df[col].round(round_decimals)
    comparison_df = (
        load_data(comparison_file, swap_comparison) if comparison_file else None
    )
    if comparison_df is not None:
        if "h" in comparison_df.columns:
            comparison_df["h"] = comparison_df["h"].round(round_decimals)

    # Sprawdzenie zgodności stref PL-2000 dla siatki
    if sparse_grid_requested and zakres_df is not None:
        input_df_with_roles = assign_geodetic_roles(input_df.copy())
        zakres_df_with_roles = assign_geodetic_roles(zakres_df.copy())

        input_epsg = get_source_epsg(input_df_with_roles.iloc[0]["geodetic_easting"])
        zakres_epsg = get_source_epsg(zakres_df_with_roles.iloc[0]["geodetic_easting"])

        if input_epsg and zakres_epsg and input_epsg != zakres_epsg:
            print(
                f"\n{Fore.RED}BŁĄD KRYTYCZNY: Niezgodność stref układu współrzędnych!"
            )
            print(
                f"{Fore.RED}Plik wejściowy jest w strefie EPSG: {input_epsg}, a plik z zakresem w strefie EPSG: {zakres_epsg}."
            )
            print(
                f"{Fore.RED}Oba pliki muszą być w tej samej strefie. Popraw dane i spróbuj ponownie."
            )
            logging.critical(f"Niezgodność stref EPSG: wejściowy={input_epsg}, zakres={zakres_epsg}. Przerwano program.")
            return  # Zakończ program

    results_df = process_data(
        input_df,
        comparison_df,
        choice in [2, 3],
        max_distance,
        geoportal_tolerance,
        round_decimals,
    )

    # --- Eksport rozrzedzonej siatki po przetworzeniu danych ---
    if sparse_grid_requested:
        if (
            zakres_df is not None
            and not zakres_df.empty
            and "osiaga_dokladnosc" in results_df.columns
        ):
            print(
                f"{Fore.CYAN}\n--- Przetwarzanie rozrzedzonej siatki ---{Style.RESET_ALL}"
            )
            punkty_dokladne_df = results_df[
                results_df["osiaga_dokladnosc"] == "Tak"
            ].copy()
            if punkty_dokladne_df.empty:
                print(
                    f"{Fore.YELLOW}Brak punktów spełniających kryterium dokładności. Nie można wygenerować siatki."
                )
            else:
                obszar_wielokat = zakres_df[["x", "y"]].values
                wyniki_siatki_df = znajdz_punkty_dla_siatki(
                    punkty_dokladne_df, obszar_wielokat, sparse_grid_distance
                )
                if not wyniki_siatki_df.empty:
                    output_siatka_csv = "wynik_siatka.csv"
                    output_siatka_gpkg = "wynik_siatka.gpkg"
                    wyniki_siatki_df.to_csv(
                        output_siatka_csv,
                        sep=";",
                        index=False,
                        float_format=f"%.{round_decimals}f",
                        na_rep="brak_danych",
                    )
                    print(
                        f"{Fore.GREEN}Wyniki rozrzedzonej siatki zapisano w pliku CSV: {os.path.abspath(output_siatka_csv)}{Style.RESET_ALL}"
                    )
                    export_to_geopackage(
                        wyniki_siatki_df,
                        input_df,
                        output_siatka_gpkg,
                        layer_name="wynik_siatki",
                        round_decimals=round_decimals,
                        split_by_accuracy=False
                    )
                else:
                    print(
                        f"{Fore.YELLOW}Nie udało się wygenerować żadnych punktów dla rozrzedzonej siatki."
                    )
        else:
            if zakres_df is None or zakres_df.empty:
                print(
                    f"{Fore.RED}Nie udało się wczytać danych zakresu. Przetwarzanie siatki przerwane."
                )
            if "osiaga_dokladnosc" not in results_df.columns:
                print(
                    f"{Fore.RED}Brak kolumny 'osiaga_dokladnosc' w wynikach. Przetwarzanie siatki przerwane."
                )

    # --- Standardowy eksport wyników ---
    if not results_df.empty:
        print(f"\n{Fore.CYAN}--- Zapisywanie wyników ---{Style.RESET_ALL}")

        # Eksport do plików CSV
        output_csv_file = "wynik.csv"
        export_to_csv(results_df, output_csv_file, round_decimals=round_decimals)

        # Eksport do plików GeoPackage
        output_gpkg_file = "wynik.gpkg"
        export_to_geopackage(
            results_df, input_df, output_gpkg_file, round_decimals=round_decimals
        )

        print(f"\n{Fore.GREEN}Zakończono przetwarzanie pomyślnie!")
    else:
        print(f"{Fore.YELLOW}Nie wygenerowano żadnych wyników.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Przerwano działanie programu.{Style.RESET_ALL}")
        logging.warning("Program przerwany przez użytkownika (KeyboardInterrupt).")
    except Exception as e:
        print(f"\n{Fore.RED}Wystąpił nieoczekiwany błąd globalny: {e}")
        logging.critical(f"Wystąpił nieoczekiwany błąd globalny: {e}", exc_info=True)
        traceback.print_exc()
    finally:
        input(f"\n{Fore.YELLOW}Naciśnij Enter, aby zakończyć...{Style.RESET_ALL}") 