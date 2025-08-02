"""
Moduł generowania rozrzedzonej siatki heksagonalnej
"""

import logging
import numpy as np
import pandas as pd
from scipy.spatial import KDTree
from tqdm import tqdm
from matplotlib.path import Path
from ..config.settings import DEBUG_MODE


def generuj_srodki_heksagonalne_wektorowo(
    obszar_wielokat: np.ndarray, odleglosc_miedzy_punktami: float
) -> np.ndarray:
    """
    Generuje i filtruje środki okręgów w siatce heksagonalnej wewnątrz zadanego wieloboku.
    WERSJA ZOPTYMALIZOWANA Z UŻYCIEM WEKTORYZACJI NUMPY.

    :param obszar_wielokat: Tablica NumPy z wierzchołkami wieloboku [[x1, y1], ...].
    :param odleglosc_miedzy_punktami: Oczekiwana odległość między środkami okręgów.
    :return: Posortowana tablica NumPy ze środkami [(x, y), ...].
    """
    d = odleglosc_miedzy_punktami
    dx, dy = d, d * np.sqrt(3) / 2
    sciezka_obszaru = Path(obszar_wielokat)

    # 1. Określ prostokątny obszar otaczający wielobok
    min_x, min_y = np.min(obszar_wielokat, axis=0)
    max_x, max_y = np.max(obszar_wielokat, axis=0)

    # 2. Wygeneruj wszystkie punkty-kandydatów w siatce heksagonalnej
    #    pokrywającej ten prostokąt. Zamiast pętli, tworzymy dwie siatki i je łączymy.
    
    # Siatka dla rzędów parzystych (0, 2, 4, ...)
    y_parzyste = np.arange(min_y, max_y + dy, dy * 2)
    x_parzyste = np.arange(min_x, max_x + dx, dx)
    grid_parzyste_x, grid_parzyste_y = np.meshgrid(x_parzyste, y_parzyste)

    # Siatka dla rzędów nieparzystych (1, 3, 5, ...), przesunięta w osi X
    y_nieparzyste = np.arange(min_y + dy, max_y + dy, dy * 2)
    x_nieparzyste = np.arange(min_x - dx / 2, max_x + dx, dx)
    grid_nieparzyste_x, grid_nieparzyste_y = np.meshgrid(x_nieparzyste, y_nieparzyste)

    # Połącz obie siatki w jedną dużą tablicę punktów (N, 2)
    punkty_parzyste = np.vstack([grid_parzyste_x.ravel(), grid_parzyste_y.ravel()]).T
    punkty_nieparzyste = np.vstack([grid_nieparzyste_x.ravel(), grid_nieparzyste_y.ravel()]).T
    
    # Sprawdzenie, czy którykolwiek z gridów nie jest pusty
    if punkty_parzyste.size > 0 and punkty_nieparzyste.size > 0:
        wszystkie_punkty = np.vstack([punkty_parzyste, punkty_nieparzyste])
    elif punkty_parzyste.size > 0:
        wszystkie_punkty = punkty_parzyste
    elif punkty_nieparzyste.size > 0:
        wszystkie_punkty = punkty_nieparzyste
    else:
        return np.array([]) # Zwróć pustą tablicę, jeśli nie ma kandydatów

    # 3. Użyj ZWEKTORYZOWANEJ metody `contains_points` do sprawdzenia wszystkich punktów naraz.
    maska_wewnatrz = sciezka_obszaru.contains_points(wszystkie_punkty)
    
    # 4. Wybierz tylko te punkty, które znalazły się wewnątrz wieloboku
    srodki_wewnatrz = wszystkie_punkty[maska_wewnatrz]

    if srodki_wewnatrz.shape[0] == 0:
        return np.array([])

    # 5. Posortuj wyniki. np.lexsort jest wydajnym sposobem sortowania po wielu kolumnach.
    #    Sortuje najpierw po drugiej kolumnie (y), a potem po pierwszej (x).
    posortowane_indeksy = np.lexsort((srodki_wewnatrz[:, 0], srodki_wewnatrz[:, 1]))
    posortowane_srodki = srodki_wewnatrz[posortowane_indeksy]

    # Blok debugowania (przystosowany do pracy z tablicą NumPy)
    if DEBUG_MODE and posortowane_srodki.shape[0] > 0:
        try:
            srodki_df = pd.DataFrame(posortowane_srodki, columns=['x', 'y'])
            srodki_df.insert(0, 'id', [f"s_{i+1}" for i in range(len(srodki_df))])
            srodki_df.to_csv("debug_siatka_srodki.csv", sep=';', index=False, float_format='%.2f')
            logging.debug(f"Eksportowano {len(srodki_df)} środków siatki do pliku debug_siatka_srodki.csv")
        except Exception as e:
            logging.error(f"Nie udało się wyeksportować środków siatki do pliku CSV: {e}")

    return posortowane_srodki


def znajdz_punkty_dla_siatki(
    punkty_kandydaci: pd.DataFrame, obszar_wielokat: np.ndarray, odleglosc_siatki: float
) -> pd.DataFrame:
    """
    Główna funkcja implementująca algorytm pokrycia siatką heksagonalną.

    :param punkty_kandydaci: DataFrame z punktami, które spełniły warunek dokładności.
                            Musi zawierać kolumny ['x_odniesienia', 'y_odniesienia', 'h_odniesienia', 'geoportal_h'].
    :param obszar_wielokat: Tablica NumPy z wierzchołkami wieloboku.
    :param odleglosc_siatki: Oczekiwana odległość między punktami siatki (promień okręgu to połowa tej wartości).
    :return: DataFrame z wynikami dla siatki.
    """
    from colorama import Fore
    promien_szukania = odleglosc_siatki / 2.0
    logging.debug(f"Rozpoczęto znajdowanie punktów dla siatki. Odległość siatki: {odleglosc_siatki}m, promień szukania: {promien_szukania}m.")
    dane_punktow = (
        punkty_kandydaci[
            ["x_odniesienia", "y_odniesienia", "h_odniesienia", "geoportal_h"]
        ]
        .apply(pd.to_numeric, errors="coerce")
        .dropna()
    )
    punkty_np = dane_punktow.values
    drzewo_kd = KDTree(punkty_np[:, :2])
    print("\nGenerowanie siatki pokrycia heksagonalnego...")
    lista_srodkow = generuj_srodki_heksagonalne_wektorowo(obszar_wielokat, odleglosc_siatki) 
    if lista_srodkow.shape[0] == 0:
        print(
            f"{Fore.YELLOW}Nie wygenerowano żadnych punktów siatki wewnątrz zadanego obszaru."
        )
        logging.warning("Nie wygenerowano żadnych środków siatki wewnątrz zadanego wieloboku.")
        return pd.DataFrame()
    print(f"Wygenerowano {len(lista_srodkow)} środków okręgów w zadanym obszarze.")
    logging.debug(f"Wygenerowano {len(lista_srodkow)} środków siatki heksagonalnej.")
    odwiedzone_indeksy_w_np = set()
    wyniki_siatki = []
    for srodek in tqdm(lista_srodkow, desc="Przetwarzanie siatki heksagonalnej"):
        logging.debug(f"Przetwarzanie środka heksagonu: ({srodek[0]:.2f}, {srodek[1]:.2f})")
        kandydaci_idx_w_np = drzewo_kd.query_ball_point(srodek, r=promien_szukania)
        logging.debug(f"  Znaleziono {len(kandydaci_idx_w_np)} kandydatów w promieniu {promien_szukania:.2f}m.")
        
        aktualni_kandydaci_idx = [
            idx for idx in kandydaci_idx_w_np if idx not in odwiedzone_indeksy_w_np
        ]
        
        if not aktualni_kandydaci_idx:
            logging.debug("  Brak nowych kandydatów w tym okręgu. Pomijam.")
            continue
        logging.debug(f"  Po odfiltrowaniu odwiedzonych, pozostało {len(aktualni_kandydaci_idx)} kandydatów.")

        najlepszy_idx_w_np = min(
            aktualni_kandydaci_idx,
            key=lambda idx: (
                abs(punkty_np[idx, 2] - punkty_np[idx, 3]),
                np.linalg.norm(punkty_np[idx, :2] - srodek),
            ),
        )
        
        odwiedzone_indeksy_w_np.add(najlepszy_idx_w_np)
        oryginalny_indeks_df = dane_punktow.index[najlepszy_idx_w_np]
        znaleziony_punkt_dane = punkty_kandydaci.loc[oryginalny_indeks_df]
        
        logging.debug(f"  Wybrano najlepszego kandydata: ID={znaleziony_punkt_dane['id_odniesienia']}, odległość od środka: {np.linalg.norm(punkty_np[najlepszy_idx_w_np, :2] - srodek):.2f}m, diff_h_geoportal: {abs(punkty_np[najlepszy_idx_w_np, 2] - punkty_np[najlepszy_idx_w_np, 3]):.3f}m")
        
        wyniki_siatki.append(znaleziony_punkt_dane)
        
    if not wyniki_siatki:
        logging.warning("Nie znaleziono żadnych punktów do siatki po przetworzeniu wszystkich środków.")
        return pd.DataFrame()
        
    logging.debug(f"Zakończono przetwarzanie siatki. Wybrano {len(wyniki_siatki)} punktów.")
    return pd.DataFrame(wyniki_siatki).reset_index(drop=True) 