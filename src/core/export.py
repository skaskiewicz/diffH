"""
Moduł eksportu wyników do różnych formatów
"""

import os
import logging
import pandas as pd
import geopandas as gpd
from colorama import Fore, Style
from .data_loader import assign_geodetic_roles, get_source_epsg


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
    results_df.to_csv(
        csv_path,
        sep=";",
        index=False,
        float_format=f"%.{round_decimals}f",
        na_rep="brak_danych",
    )
    print(
        f"{Fore.GREEN}Wyniki tabelaryczne (wszystkie) zapisano w: {os.path.abspath(csv_path)}{Style.RESET_ALL}"
    )

    # Sprawdzenie, czy istnieje kolumna do podziału
    if "osiaga_dokladnosc" not in results_df.columns:
        print(
            f"{Fore.YELLOW}Brak kolumny 'osiaga_dokladnosc', nie można podzielić plików CSV."
        )
        return

    # Przygotowanie do podziału
    df_copy = results_df.copy()
    df_copy["eksport"] = df_copy["osiaga_dokladnosc"].apply(
        lambda x: str(x).strip().lower() == "tak"
    )

    # 2. Eksport tylko spełniających warunek dokładności
    df_ok = df_copy[df_copy["eksport"]].drop(columns=["eksport"])
    if not df_ok.empty:
        path_ok = csv_path.replace(".csv", "_dokladne.csv")
        df_ok.to_csv(
            path_ok,
            sep=";",
            index=False,
            float_format=f"%.{round_decimals}f",
            na_rep="brak_danych",
        )
        print(
            f"{Fore.GREEN}Wyniki spełniające warunek dokładności zapisano w: {os.path.abspath(path_ok)}{Style.RESET_ALL}"
        )
    else:
        print(
            f"{Fore.YELLOW}Brak punktów spełniających warunek dokładności do eksportu CSV."
        )

    # 3. Eksport niespełniających warunku dokładności
    df_nok = df_copy[~df_copy["eksport"]].drop(columns=["eksport"])
    if not df_nok.empty:
        path_nok = csv_path.replace(".csv", "_niedokladne.csv")
        df_nok.to_csv(
            path_nok,
            sep=";",
            index=False,
            float_format=f"%.{round_decimals}f",
            na_rep="brak_danych",
        )
        print(
            f"{Fore.GREEN}Wyniki niespełniające warunku dokładności zapisano w: {os.path.abspath(path_nok)}{Style.RESET_ALL}"
        )
    else:
        print(
            f"{Fore.YELLOW}Brak punktów niespełniających warunku dokładności do eksportu CSV."
        )


def export_to_geopackage(results_df: pd.DataFrame, input_df: pd.DataFrame, gpkg_path: str, layer_name: str = "wyniki", round_decimals: int = 1, split_by_accuracy: bool = True):
    """
    Eksportuje wyniki do pliku GeoPackage.
    Jeśli split_by_accuracy jest True, tworzy dodatkowe pliki _dokladne i _niedokladne.
    """
    if results_df.empty:
        print(f"{Fore.YELLOW}Brak danych do zapisu w GeoPackage.")
        return
    source_epsg = None
    if not input_df.empty:
        # Używamy .copy(), aby uniknąć ostrzeżenia SettingWithCopyWarning
        temp_input_df = assign_geodetic_roles(input_df.copy())
        first_point_easting = temp_input_df.iloc[0]['geodetic_easting']
        source_epsg = get_source_epsg(first_point_easting)
        
    if source_epsg is None:
        print(f"{Fore.RED}Błąd: Nie można było ustalić źródłowego układu współrzędnych (EPSG). Plik GeoPackage nie zostanie utworzony.")
        logging.error("Nie można ustalić źródłowego EPSG, eksport do GPKG przerwany.")
        return
    
    # Komunikat o układzie jest teraz w jednym miejscu, aby uniknąć powtórzeń
    print(f"\n{Fore.CYAN}Wykryto układ współrzędnych dla plików GeoPackage: EPSG:{source_epsg}{Style.RESET_ALL}")
    logging.debug(f"Wykryto EPSG:{source_epsg} dla eksportu GeoPackage.")
    
    try:
        df_geo = results_df.copy()
        # Zaokrąglenie wysokości
        for col in ['h_odniesienia', 'diff_h_geoportal', 'diff_h']:
            if col in df_geo.columns:
                df_geo[col] = pd.to_numeric(df_geo[col], errors='coerce').round(round_decimals)

        # Stworzenie geometrii
        geometry = gpd.points_from_xy(df_geo['y_odniesienia'], df_geo['x_odniesienia'])
        gdf = gpd.GeoDataFrame(df_geo, geometry=geometry, crs=f"EPSG:{source_epsg}")
        
        # 1. Eksport całościowy
        gdf.to_file(gpkg_path, layer=layer_name, driver="GPKG")
        print(f"{Fore.GREEN}Wyniki (wszystkie) zostały poprawnie zapisane w bazie przestrzennej: {os.path.abspath(gpkg_path)}{Style.RESET_ALL}")
        
        # 2. Logika dzielenia plików (uruchamiana warunkowo)
        if split_by_accuracy:
            if 'osiaga_dokladnosc' not in gdf.columns:
                print(f"{Fore.YELLOW}Brak kolumny 'osiaga_dokladnosc', nie można podzielić plików GeoPackage.")
                return

            gdf['eksport'] = gdf['osiaga_dokladnosc'].apply(lambda x: str(x).strip().lower() == 'tak')
            
            # Eksport tylko spełniających warunek dokładności
            gdf_ok = gdf[gdf['eksport']]
            if not gdf_ok.empty:
                path_ok = gpkg_path.replace('.gpkg', '_dokladne.gpkg')
                gdf_ok.to_file(path_ok, layer=layer_name, driver="GPKG")
                print(f"{Fore.GREEN}Wyniki spełniające warunek dokładności zapisano w: {os.path.abspath(path_ok)}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}Brak punktów spełniających warunek dokładności do eksportu GeoPackage.")
                
            # Eksport niespełniających warunku dokładności
            gdf_nok = gdf[~gdf['eksport']]
            if not gdf_nok.empty:
                path_nok = gpkg_path.replace('.gpkg', '_niedokladne.gpkg')
                gdf_nok.to_file(path_nok, layer=layer_name, driver="GPKG")
                print(f"{Fore.GREEN}Wyniki niespełniające warunku dokładności zapisano w: {os.path.abspath(path_nok)}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}Brak punktów niespełniających warunku dokładności do eksportu GeoPackage.")
            
    except Exception as e:
        print(f"{Fore.RED}Wystąpił błąd podczas tworzenia pliku GeoPackage: {e}")
        logging.error(f"Błąd podczas eksportu do GeoPackage: {e}", exc_info=True) 