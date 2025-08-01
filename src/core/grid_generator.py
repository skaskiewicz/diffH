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


def generuj_srodki_heksagonalne(
    obszar_wielokat: np.ndarray, odleglosc_miedzy_punktami: float
) -> np.ndarray:
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

    if DEBUG_MODE and lista_srodkow:
        try:
            srodki_df = pd.DataFrame(lista_srodkow, columns=['x', 'y'])
            srodki_df.insert(0, 'id', [f"s_{i+1}" for i in range(len(srodki_df))])
            srodki_df.to_csv("debug_siatka_srodki.csv", sep=';', index=False, float_format='%.2f')
            logging.debug(f"Eksportowano {len(srodki_df)} środków siatki do pliku debug_siatka_srodki.csv")
        except Exception as e:
            logging.error(f"Nie udało się wyeksportować środków siatki do pliku CSV: {e}")

    return np.array(lista_srodkow)


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
    lista_srodkow = generuj_srodki_heksagonalne(obszar_wielokat, odleglosc_siatki)
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