# diffH - Geo-Komparator wysokości

**Porównywanie i transformacja współrzędnych geoprzestrzennych**

---

### O programie

`diffH` to narzędzie uruchamiane w linii poleceń (CLI), stworzone w języku Python. Jego głównym zadaniem jest przetwarzanie, transformacja i porównywanie danych geoprzestrzennych zawartych w plikach tekstowych. Skrypt został zaprojektowany z myślą o pracy z polskimi układami współrzędnych PL-2000 i PL-1992.

### Główne Funkcje

*   **Transformacja Współrzędnych:** Automatyczne przeliczanie współrzędnych z układu **PL-2000** (strefy 5, 6, 7, 8 - EPSG: 2176, 2177, 2178, 2179) do układu **PL-1992** (EPSG: 2180).
*   **Porównanie z Geoportal.gov.pl:** Pobieranie wysokości z serwisu Geoportal.gov.pl dla punktów z pliku wejściowego i dołączenie ich do wyników.
*   **Zaawansowane Porównanie Plików:** Porównywanie punktów z pliku wejściowego z punktami z drugiego pliku referencyjnego. Parowanie odbywa się na podstawie **dwóch warunków**:
    1.  **Progu odległości:** para jest tworzona tylko, jeśli odległość między punktami jest mniejsza niż zdefiniowana przez użytkownika.
    2.  **Wzajemności:** punkty muszą być dla siebie nawzajem najbliższymi sąsiadami.
*   **Inteligentna Analiza Danych:**
    *   **Automatyczne wykrywanie separatora** w plikach wejściowych (obsługuje średnik, przecinek, spację/tabulator).
    *   **Automatyczne wykrywanie konwencji osi współrzędnych** (czy plik używa układu geodezyjnego `X=Północ, Y=Wschód`, czy standardu GIS `X=Wschód, Y=Północ`).
*   **Przyjazny Interfejs:** Skrypt prowadzi użytkownika krok po kroku przez proces wyboru opcji i podawania plików.
*   **Czysty Plik Wynikowy:** Generuje przejrzysty, tabelaryczny plik `wynik.csv`, gotowy do importu w innych programach (np. Excel, QGIS).

### Wymagania i Instalacja

Aby uruchomić skrypt, potrzebujesz:

1.  **Python 3** (rekomendowana wersja 3.8 lub nowsza).
2.  Kilka bibliotek, które należy zainstalować.

**Kroki instalacji:**

1.  **Pobierz skrypt** i umieść go w wybranym folderze.

2.  **Utwórz plik `requirements.txt`** w tym samym folderze i wklej do niego poniższą zawartość:
    ```
    pandas
    pyproj
    requests
    scipy
    colorama
    ```

3.  **Otwórz terminal** (wiersz poleceń) w tym folderze.

4.  (Zalecane) **Stwórz i aktywuj środowisko wirtualne**, aby nie instalować bibliotek globalnie:
    ```bash
    # Utworzenie środowiska o nazwie .venv
    python -m venv .venv

    # Aktywacja środowiska (Windows)
    .\.venv\Scripts\activate

    # Aktywacja środowiska (Linux/macOS)
    source .venv/bin/activate
    ```

5.  **Zainstaluj wymagane biblioteki** za pomocą menedżera pakietów `pip`:
    ```bash
    pip install -r requirements.txt
    ```

Po wykonaniu tych kroków środowisko jest gotowe do pracy.

### Użycie

1.  Upewnij się, że Twoje środowisko wirtualne jest aktywne (jeśli je utworzyłeś).
2.  Uruchom skrypt za pomocą polecenia:
    ```bash
    python geo_komparator.py
    ```
3.  Postępuj zgodnie z instrukcjami na ekranie:
    *   Wybierz tryb porównania (1, 2 lub 3).
    *   Jeśli wybrałeś porównanie plików, podaj maksymalną odległość wyszukiwania pary.
    *   Podaj ścieżki do pliku wejściowego i (opcjonalnie) porównawczego.
4.  Po zakończeniu pracy, w folderze ze skryptem zostanie utworzony plik `wynik.csv`.

### Format Pliku Wejściowego

*   Plik musi być w formacie `.txt` lub `.csv`.
*   Musi zawierać co najmniej 4 kolumny w kolejności: `numer_punktu`, `współrzędna_X`, `współrzędna_Y`, `wysokość_H`.
*   Skrypt automatycznie wykrywa, czy plik jest zapisany w konwencji:
    *   **Geodezyjnej:** `X` to współrzędna północna (Northing), `Y` to wschodnia (Easting).
    *   **GIS:** `X` to współrzędna wschodnia (Easting), `Y` to północna (Northing).

**Przykład:**
```csv
1001;5958143.50;7466893.08;137.90
1002;5955909.72;7466350.05;138.82
```

### Format Pliku Wyjściowego

*   Nazwa pliku: `wynik.csv`
*   Separator: średnik (`;`)
*   Brakujące dane są oznaczane jako `brak_danych`.
*   Możliwe kolumny:
    *   `id_odniesienia`, `x_odniesienia`, `y_odniesienia`, `h_odniesienia`: Dane z pliku wejściowego.
    *   `id_porownania`, `x_porownania`, `y_porownania`, `h_porownania`: Dane dopasowanego punktu z pliku porównawczego.
    *   `odleglosc_pary`: Odległość w metrach między sparowanymi punktami.
    *   `geoportal_h`: Wysokość pobrana z serwisu Geoportal.gov.pl.

### Tryb Deweloperski

Na samej górze skryptu znajduje się flaga `DEBUG_MODE`. Ustawienie jej na `True` włączy wyświetlanie szczegółowych komunikatów diagnostycznych, które mogą być pomocne przy rozwiązywaniu problemów.