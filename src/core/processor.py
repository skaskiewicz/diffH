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
    get_geoportal_tolerance, get_round_decimals, ask_load_config
)
from ..utils.config_manager import load_config, save_config_for_mode
from ..config.settings import DEBUG_MODE, DEFAULT_SPARSE_GRID_DISTANCE
from .data_loader import load_data, load_scope_data, assign_geodetic_roles, get_source_epsg
from .coordinate_transform import transform_coordinates_parallel, get_transformation_method_info
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
        # Wyświetl informację o metodzie transformacji
        transformation_method = get_transformation_method_info()
        print(f"{Fore.CYAN}Metoda transformacji: {transformation_method}{Style.RESET_ALL}")
        
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


def main(config_path: str):
    """Główna funkcja programu"""
    setup_logging()
    clear_screen()
    display_welcome_screen()

    choice = get_user_choice()

    all_configs = load_config(config_path)
    mode_settings = all_configs.get(str(choice))
    use_saved_settings = False
    
    if mode_settings:
        if ask_load_config(mode_settings):
            use_saved_settings = True

    settings_to_save = {}

    # --- Pytania o ustawienia (zgodnie z oryginalną kolejnością) ---

    max_distance = 0.0
    if choice in [1, 3]:
        # Poprawka dla Pylance: Sprawdzamy, czy mode_settings nie jest None
        if use_saved_settings and mode_settings is not None and 'max_distance' in mode_settings:
            max_distance = mode_settings['max_distance']
        else:
            max_distance = get_max_distance()
            settings_to_save['max_distance'] = max_distance

    if use_saved_settings and mode_settings is not None and 'round_decimals' in mode_settings:
        round_decimals = mode_settings['round_decimals']
    else:
        round_decimals = get_round_decimals()
        settings_to_save['round_decimals'] = round_decimals

    input_file = get_file_path(
        f"\n{Fore.YELLOW}Podaj ścieżkę do pliku wejściowego: {Style.RESET_ALL}"
    )

    if use_saved_settings and mode_settings is not None and 'swap_input' in mode_settings:
        swap_input = mode_settings['swap_input']
    else:
        swap_input = ask_swap_xy("wejściowego")
        settings_to_save['swap_input'] = swap_input
        
    comparison_file, swap_comparison = None, False
    if choice in [1, 3]:
        comparison_file = get_file_path(
            f"{Fore.YELLOW}Podaj ścieżkę do pliku porównawczego: {Style.RESET_ALL}"
        )
        if use_saved_settings and mode_settings is not None and 'swap_comparison' in mode_settings:
            swap_comparison = mode_settings['swap_comparison']
        else:
            swap_comparison = ask_swap_xy("porównawczego")
            settings_to_save['swap_comparison'] = swap_comparison
            
    geoportal_tolerance = None
    if choice in [2, 3]:
        if use_saved_settings and mode_settings is not None and 'geoportal_tolerance' in mode_settings:
            geoportal_tolerance = mode_settings['geoportal_tolerance']
        else:
            geoportal_tolerance = get_geoportal_tolerance()
            settings_to_save['geoportal_tolerance'] = geoportal_tolerance

    sparse_grid_requested, sparse_grid_distance, zakres_df, swap_scope = False, DEFAULT_SPARSE_GRID_DISTANCE, None, False
    if choice in [2, 3]:
        if use_saved_settings and mode_settings is not None and 'sparse_grid_requested' in mode_settings:
            sparse_grid_requested = mode_settings['sparse_grid_requested']
        else:
            resp = input(f"\n{Fore.YELLOW}Czy wykonać eksport rozrzedzonej siatki dla punktów spełniających dokładność? [t/n] (domyślnie: n): ").strip().lower()
            sparse_grid_requested = resp in ["t", "tak", "y", "yes"]
            settings_to_save['sparse_grid_requested'] = sparse_grid_requested

        if sparse_grid_requested:
            if use_saved_settings and mode_settings is not None and 'sparse_grid_distance' in mode_settings:
                sparse_grid_distance = mode_settings['sparse_grid_distance']
            else:
                dist_prompt = f"{Fore.YELLOW}Podaj oczekiwaną odległość pomiędzy punktami siatki (w metrach, domyślnie: {DEFAULT_SPARSE_GRID_DISTANCE}): {Style.RESET_ALL}"
                dist_val = input(dist_prompt).strip()
                if dist_val:
                    try:
                        parsed_dist = float(dist_val.replace(",", "."))
                        if parsed_dist > 0:
                            sparse_grid_distance = parsed_dist
                    except ValueError:
                        # Poprawka dla Ruff: pusta instrukcja pass jest czytelniejsza
                        pass
                settings_to_save['sparse_grid_distance'] = sparse_grid_distance

            zakres_file = get_file_path(f"{Fore.YELLOW}Podaj ścieżkę do pliku z zakresem opracowania (wierzchołki wieloboku): {Style.RESET_ALL}")
            
            if use_saved_settings and mode_settings is not None and 'swap_scope' in mode_settings:
                swap_scope = mode_settings['swap_scope']
            else:
                swap_scope = ask_swap_xy("z zakresem")
                settings_to_save['swap_scope'] = swap_scope
            
            zakres_df = load_scope_data(zakres_file, swap_scope)

    # Zapisz nowe ustawienia, jeśli były wprowadzane ręcznie
    if settings_to_save:
        save_config_for_mode(choice, settings_to_save, config_path)

    # --- Wczytywanie i przetwarzanie danych ---
    print(f"\n{Fore.CYAN}--- Wczytywanie danych ---{Style.RESET_ALL}")
    input_df = load_data(input_file, swap_input)
    if input_df is None or input_df.empty:
        print(f"{Fore.RED}Nie udało się wczytać danych wejściowych. Zamykanie programu.")
        return
        
    for col in ["x", "y", "h"]:
        input_df[col] = input_df[col].round(round_decimals)
        
    comparison_df = load_data(comparison_file, swap_comparison) if comparison_file else None
    if comparison_df is not None and "h" in comparison_df.columns:
        comparison_df["h"] = comparison_df["h"].round(round_decimals)

    if sparse_grid_requested and zakres_df is not None:
        input_epsg = get_source_epsg(assign_geodetic_roles(input_df.copy()).iloc[0]["geodetic_easting"])
        zakres_epsg = get_source_epsg(assign_geodetic_roles(zakres_df.copy()).iloc[0]["geodetic_easting"])
        if input_epsg and zakres_epsg and input_epsg != zakres_epsg:
            print(f"\n{Fore.RED}BŁĄD KRYTYCZNY: Niezgodność stref układu współrzędnych!")
            print(f"{Fore.RED}Plik wejściowy jest w strefie EPSG: {input_epsg}, a plik z zakresem w strefie EPSG: {zakres_epsg}.")
            return

    results_df = process_data(input_df, comparison_df, choice in [2, 3], max_distance, geoportal_tolerance, round_decimals)

    if sparse_grid_requested and zakres_df is not None and "osiaga_dokladnosc" in results_df.columns:
        print(f"{Fore.CYAN}\n--- Przetwarzanie rozrzedzonej siatki ---{Style.RESET_ALL}")
        punkty_dokladne_df = results_df[results_df["osiaga_dokladnosc"] == "Tak"].copy()
        if not punkty_dokladne_df.empty:
            wyniki_siatki_df = znajdz_punkty_dla_siatki(punkty_dokladne_df, zakres_df[["x", "y"]].values, sparse_grid_distance)
            if not wyniki_siatki_df.empty:
                output_siatka_csv, output_siatka_gpkg = "wynik_siatka.csv", "wynik_siatka.gpkg"
                wyniki_siatki_df.to_csv(output_siatka_csv, sep=";", index=False, float_format=f"%.{round_decimals}f", na_rep="brak_danych")
                print(f"{Fore.GREEN}Wyniki rozrzedzonej siatki zapisano w pliku CSV: {os.path.abspath(output_siatka_csv)}{Style.RESET_ALL}")
                export_to_geopackage(wyniki_siatki_df, input_df, output_siatka_gpkg, "wynik_siatki", round_decimals, False)
            else:
                print(f"{Fore.YELLOW}Nie udało się wygenerować żadnych punktów dla rozrzedzonej siatki.")
        else:
            print(f"{Fore.YELLOW}Brak punktów spełniających kryterium dokładności. Nie można wygenerować siatki.")

    if not results_df.empty:
        print(f"\n{Fore.CYAN}--- Zapisywanie wyników ---{Style.RESET_ALL}")
        export_to_csv(results_df, "wynik.csv", round_decimals=round_decimals)
        export_to_geopackage(results_df, input_df, "wynik.gpkg", round_decimals=round_decimals)
        print(f"\n{Fore.GREEN}Zakończono przetwarzanie pomyślnie!")
    else:
        print(f"{Fore.YELLOW}Nie wygenerowano żadnych wyników.")


if __name__ == "__main__":
    try:
        # Ten kod jest tu na wypadek, gdyby plik był uruchamiany bezpośrednio, ale główna logika jest w main.py
        main(config_path="config.json")
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Przerwano działanie programu.{Style.RESET_ALL}")
        logging.warning("Program przerwany przez użytkownika (KeyboardInterrupt).")
    except Exception as e:
        print(f"\n{Fore.RED}Wystąpił nieoczekiwany błąd globalny: {e}")
        logging.critical(f"Wystąpił nieoczekiwany błąd globalny: {e}", exc_info=True)
        traceback.print_exc()
    finally:
        input(f"\n{Fore.YELLOW}Naciśnij Enter, aby zakończyć...{Style.RESET_ALL}")