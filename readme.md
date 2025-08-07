# diffH - Geo-Komparator wysokości

**Porównywanie, transformacja i wzbogacanie danych geoprzestrzennych**

---

### O programie

`diffH` to narzędzie uruchamiane w linii poleceń (CLI), stworzone w języku Python. Jego głównym zadaniem jest przetwarzanie, transformacja, porównywanie i wzbogacanie danych geoprzestrzennych zawartych w plikach tekstowych. Skrypt został zaprojektowany z myślą o pracy z polskimi układami współrzędnych PL-2000 i PL-1992.

### Główne Funkcje

*   **Pobieranie Wysokości (Tryb 4):** Nowa, dedykowana funkcja umożliwiająca wczytanie pliku z samymi współrzędnymi (`X,Y` lub `ID,X,Y`) i automatyczne pobranie dla nich wysokości z serwisu Geoportal.gov.pl. Wyniki (`ID,X,Y,H`) są eksportowane do plików CSV i GPKG.
*   **Zaawansowane Porównanie Plików (Tryby 1-3):** Porównywanie punktów z pliku wejściowego z punktami z drugiego pliku referencyjnego na podstawie progu odległości i wzajemności (najbliżsi sąsiedzi).
*   **Porównanie z Geoportal.gov.pl (Tryby 2-3):** Pobieranie wysokości z serwisu Geoportal.gov.pl dla punktów z pliku wejściowego i dołączenie ich do wyników. Wysyłka punktów do API odbywa się w paczkach po maksymalnie 300 punktów.
*   **Transformacja Współrzędnych:** Automatyczne przeliczanie współrzędnych z układu **PL-2000** (strefy 5, 6, 7, 8 - EPSG: 2176, 2177, 2178, 2179) do układu **PL-1992** (EPSG: 2180).
*   **Przyspieszenie GPU (CUDA):** Automatyczne wykrywanie kart NVIDIA i wykorzystanie przyspieszenia CUDA do transformacji współrzędnych. Program automatycznie przełącza się między przetwarzaniem GPU a CPU w zależności od dostępności sprzętu.
*   **Inteligentna Analiza Danych:**
    *   **Automatyczne wykrywanie separatora** w plikach wejściowych (obsługuje średnik, przecinek, spację/tabulator).
    *   **Automatyczne wykrywanie konwencji osi współrzędnych** (`X,Y` vs `Y,X`). Użytkownik może też ręcznie wskazać zamianę osi.
*   **Eksport rozrzedzonej siatki:** Możliwość wygenerowania reprezentatywnej, rozrzedzonej siatki punktów, które spełniają kryterium dokładności. Algorytm bazuje na heksagonalnym pokryciu zadanego obszaru.
*   **Obsługa plików Excel:** Możliwość wczytywania plików wejściowych w formatach `.xls` i `.xlsx`.
*   **Personalizowana autonumeracja:** Przy wczytywaniu plików bez kolumny ID, użytkownik może podać własny prefiks dla automatycznie generowanych numerów punktów.
*   **Obliczanie różnic i tolerancji:** Program oblicza różnice wysokości (`diff_h`, `diff_h_geoportal`) i pozwala użytkownikowi zdefiniować progi tolerancji, oznaczając punkty jako `Tak`/`Nie` w kolumnie `osiaga_dokladnosc`.
*   **Czyste Pliki Wynikowe:** Generuje przejrzyste, tabelaryczne pliki CSV oraz gotowe do analizy przestrzennej pliki GeoPackage (GPKG), które można otworzyć bezpośrednio w QGIS.

### Wymagania i Instalacja

Aby uruchomić skrypt, potrzebujesz:

1.  **Python 3** (rekomendowana wersja 3.8 lub nowsza).
2.  Kilka bibliotek, które należy zainstalować.
3.  **Opcjonalnie:** Karta graficzna NVIDIA z obsługą CUDA dla przyspieszenia GPU (automatycznie wykrywane).

**Kroki instalacji:**

1.  **Pobierz skrypt** i umieść go w wybranym folderze.

2.  **Utwórz plik `requirements.txt`** w tym samym folderze i wklej do niego poniższą zawartość:
    ```
    colorama>=0.4.6
    geopandas>=0.13.0
    pandas>=2.0.0
    pyproj>=3.5.0
    requests>=2.31.0
    scipy>=1.11.0
    openpyxl>=3.0.0
    tqdm>=4.60.0
    numpy>=1.24.0
    matplotlib>=3.7.0
    # CUDA dependencies for GPU acceleration (opcjonalne)
    cupy-cuda12x>=12.0.0; sys_platform != "win32"
    cupy-cuda11x>=11.0.0; sys_platform == "win32"
    ```

3.  **Otwórz terminal** (wiersz poleceń) w tym folderze.

4.  (Zalecane) **Stwórz i aktywuj środowisko wirtualne**:
    ```bash
    # Utworzenie środowiska o nazwie .venv
    python -m venv .venv

    # Aktywacja środowiska (Windows)
    .\.venv\Scripts\activate

    # Aktywacja środowiska (Linux/macOS)
    source .venv/bin/activate
    ```

5.  **Zainstaluj wymagane biblioteki**:
    ```bash
    pip install -r requirements.txt
    ```

Po wykonaniu tych kroków środowisko jest gotowe do pracy.

### Użycie

1.  Upewnij się, że Twoje środowisko wirtualne jest aktywne (jeśli je utworzyłeś).
2.  Uruchom skrypt za pomocą polecenia:
    ```bash
    python main.py
    ```
3.  Postępuj zgodnie z instrukcjami na ekranie:
    *   Wybierz tryb działania (1 - porównanie z plikiem, 2 - porównanie z geoportalem, 3 - oba porównania, 4 - pobranie wysokości dla pliku XY).
    *   Podaj ścieżki do plików oraz inne parametry zgodnie z monitami.
4.  Po zakończeniu pracy, w folderze ze skryptem zostaną utworzone pliki wynikowe.

### Format Pliku Wejściowego

*   **Obsługiwane formaty:** `.txt`, `.csv`, `.xls`, `.xlsx`.
*   **Separator kolumn:** Wykrywany automatycznie (średnik, przecinek, spacja/tabulator).
*   **Układ współrzędnych:** Program oczekuje współrzędnych w układzie PL-2000. Konwencja osi (`X,Y` vs `Y,X`) jest wykrywana automatycznie, ale użytkownik może ją nadpisać.

#### Struktura pliku (tryby 1, 2, 3):
*   **4 kolumny:** `numer_punktu`, `współrzędna_X`, `współrzędna_Y`, `wysokość_H`.
*   **3 kolumny:** `współrzędna_X`, `współrzędna_Y`, `wysokość_H` (program poprosi o prefiks do autonumeracji).
**Przykład:**
```csv
1001;5958143.50;7466893.08;137.90
1002;5955909.72;7466350.05;138.82
```

#### Struktura pliku (tryb 4):
*   **3 kolumny:** `numer_punktu`, `współrzędna_X`, `współrzędna_Y`.
*   **2 kolumny:** `współrzędna_X`, `współrzędna_Y` (program poprosi o prefiks do autonumeracji).
**Przykład:**
```csv
P1;5958143.50;7466893.08
P2;5955909.72;7466350.05
```

### Format Pliku Wyjściowego

*   **Nazwy plików (tryby 1-3):**
    *   `wynik.csv`, `wynik.gpkg` (wszystkie wyniki)
    *   `wynik_dokladne.csv`, `wynik_dokladne.gpkg` (punkty spełniające tolerancję)
    *   `wynik_niedokladne.csv`, `wynik_niedokladne.gpkg` (punkty niespełniające tolerancji)
*   **Nazwy plików (tryb 4):**
    *   `wynik_geoportal.csv`
    *   `wynik_geoportal.gpkg`
*   **Opcjonalnie (tryby 2-3):** `wynik_siatka.csv`, `wynik_siatka.gpkg`
*   Separator w plikach CSV to średnik (`;`).
*   Brakujące dane są oznaczane jako `brak_danych`.
*   Możliwe kolumny w plikach wynikowych:
    *   `id_odniesienia`, `x_odniesienia`, `y_odniesienia`, `h_odniesienia`: Dane z pliku wejściowego.
    *   `h_geoportal` / `geoportal_h`: Wysokość pobrana z serwisu Geoportal.gov.pl.
    *   `diff_h_geoportal`: Różnica wysokości (plik wejściowy - geoportal).
    *   `id_porownania`, `x_porownania`, `y_porownania`, `h_porownania`: Dane dopasowanego punktu z pliku porównawczego.
    *   `diff_h`: Różnica wysokości (plik wejściowy - plik porównawczy).
    *   `odleglosc_pary`: Odległość w metrach między sparowanymi punktami.
    *   `osiaga_dokladnosc`: Informacja (Tak/Nie), czy punkt mieści się w zadanej tolerancji.

### Szczegółowy Przebieg Pracy Programu

1.  **Uruchomienie programu**
    *   Uruchom skrypt poleceniem:
        ```bash
        python main.py
        ```
2.  **Wybór trybu działania**
    *   Program wyświetli menu z czterema trybami:
        1.  Porównanie pliku wejściowego z drugim plikiem.
        2.  Porównanie pliku wejściowego z danymi z Geoportal.gov.pl.
        3.  Porównanie pliku wejściowego z drugim plikiem ORAZ z Geoportal.gov.pl.
        4.  **Nowość:** Pobranie wysokości z Geoportal.gov.pl dla pliku z punktami (XY).
    *   Wybierz odpowiednią opcję wpisując 1, 2, 3 lub 4.
3.  **Podanie parametrów**
    *   W zależności od wybranego trybu, program poprosi o:
        *   Ścieżkę do pliku wejściowego (i opcjonalnie porównawczego).
        *   Informację o ewentualnej zamianie kolumn (Y,X zamiast X,Y).
        *   Parametry porównania (maksymalna odległość, tolerancja wysokości).
        *   Parametry eksportu rozrzedzonej siatki (dla trybów 2 i 3).
        *   Liczbę miejsc po przecinku dla danych wynikowych.
4.  **Wczytywanie i analiza danych**
    *   Program automatycznie wykryje separator, strukturę pliku i sprawdzi, czy dane są numeryczne.
    *   W razie potrzeby doda automatyczną numerację punktów.
5.  **Transformacja i pobieranie danych**
    *   Współrzędne są transformowane do układu EPSG:2180.
    *   Jeśli wybrano tryb z Geoportalem, dane są wysyłane do API w paczkach po 300 punktów.
6.  **Porównanie i obliczenia (tryby 1-3)**
    *   Program buduje indeks przestrzenny, paruje punkty i oblicza różnice wysokości.
    *   Ustalane jest, czy punkty spełniają zdefiniowane przez użytkownika kryteria dokładności.
7.  **Eksport wyników**
    *   Tworzone są pliki CSV oraz GeoPackage (GPKG) z wynikami, gotowe do dalszej analizy w programach biurowych lub GIS.

### Tryb Deweloperski

Na samej górze skryptu (`src/config/settings.py`) znajduje się flaga `DEBUG_MODE`. Ustawienie jej na `True` włączy wyświetlanie szczegółowych komunikatów diagnostycznych, które mogą być pomocne przy rozwiązywaniu problemów.

---

**Masz pytania lub napotkałeś problem?**

Napisz na issues lub sprawdź changelog, aby zobaczyć historię zmian.