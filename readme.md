# diffH - Geo-Komparator wysokości

**Porównywanie i transformacja współrzędnych geoprzestrzennych**

---

### O programie

`diffH` to narzędzie uruchamiane w linii poleceń (CLI), stworzone w języku Python. Jego głównym zadaniem jest przetwarzanie, transformacja i porównywanie danych geoprzestrzennych zawartych w plikach tekstowych. Skrypt został zaprojektowany z myślą o pracy z polskimi układami współrzędnych PL-2000 i PL-1992.

### Główne Funkcje

*   **Transformacja Współrzędnych:** Automatyczne przeliczanie współrzędnych z układu **PL-2000** (strefy 5, 6, 7, 8 - EPSG: 2176, 2177, 2178, 2179) do układu **PL-1992** (EPSG: 2180).
*   **Porównanie z Geoportal.gov.pl:** Pobieranie wysokości z serwisu Geoportal.gov.pl dla punktów z pliku wejściowego i dołączenie ich do wyników. Wysyłka punktów do API odbywa się w paczkach po maksymalnie 300 punktów.
*   **Zaawansowane Porównanie Plików:** Porównywanie punktów z pliku wejściowego z punktami z drugiego pliku referencyjnego. Parowanie odbywa się na podstawie **dwóch warunków**:
    1.  **Progu odległości:** para jest tworzona tylko, jeśli odległość między punktami jest mniejsza niż zdefiniowana przez użytkownika.
    2.  **Wzajemności:** punkty muszą być dla siebie nawzajem najbliższymi sąsiadami.
*   **Obliczanie różnic wysokości:**
    *   Automatyczne obliczanie różnicy wysokości pomiędzy plikiem wejściowym a plikiem porównawczym (`diff_h`).
    *   Obliczanie różnicy wysokości pomiędzy plikiem wejściowym a geoportalem (`diff_h_geoportal`).
    *   W trybie porównania plik + plik + geoportal: dodatkowa kolumna `diff_h_geoportal_pair` (różnica h_porownania - geoportal_h).
*   **Tolerancja dokładności:**
    *   Możliwość podania przez użytkownika dopuszczalnej różnicy wysokości względem geoportalu.
    *   Kolumna `osiaga_dokladnosc` (Tak/Nie) informuje, czy różnica mieści się w zadanej tolerancji.
*   **Inteligentna Analiza Danych:**
    *   **Automatyczne wykrywanie separatora** w plikach wejściowych (obsługuje średnik, przecinek, spację/tabulator).
    *   **Automatyczne wykrywanie konwencji osi współrzędnych** (czy plik używa układu geodezyjnego `X=Północ, Y=Wschód`, czy standardu GIS `X=Wschód, Y=Północ`).
*   **Zaokrąglanie współrzędnych:** Wszystkie współrzędne i wysokości są zaokrąglane do 2 miejsc po przecinku zgodnie z regułą Bradissa-Kryłowa (bankers' rounding).
*   **Przyjazny Interfejs:** Skrypt prowadzi użytkownika krok po kroku przez proces wyboru opcji i podawania plików.
*   **Czysty Plik Wynikowy:** Generuje przejrzysty, tabelaryczny plik `wynik.csv`, gotowy do importu w innych programach (np. Excel, QGIS). Wyniki są sortowane malejąco według wartości bezwzględnej różnicy wysokości względem geoportalu.
*   **Eksport do GeoPackage (GPKG):** Możliwość zapisu wyników do pliku GeoPackage, który można otworzyć bezpośrednio w QGIS lub innych programach GIS. Ułatwia to dalszą analizę i wizualizację danych przestrzennych.

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
    geopandas
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
    python geo_comparator.py
    ```
3.  Postępuj zgodnie z instrukcjami na ekranie:
    *   Wybierz tryb porównania (1 - plik z plikiem, 2 - plik z geoportalem, 3 - plik z plikiem i geoportalem).
    *   Jeśli wybrałeś porównanie plików, podaj maksymalną odległość wyszukiwania pary.
    *   Podaj ścieżki do pliku wejściowego i (opcjonalnie) porównawczego.
    *   Jeśli wybrałeś porównanie z geoportalem, podaj dopuszczalną różnicę wysokości.
4.  Po zakończeniu pracy, w folderze ze skryptem zostanie utworzony plik `wynik.csv` oraz plik `wynik.gpkg` (GeoPackage do GIS).

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
*   Dodatkowo generowane są pliki GeoPackage (GPKG) z wynikami przestrzennymi gotowymi do użycia w QGIS lub innym oprogramowaniu GIS:
    *   `wynik.gpkg` – zawiera wszystkie punkty.
    *   `wynik_dokladne.gpkg` – zawiera tylko punkty spełniające warunek dokładnościowy (kolumna `osiaga_dokladnosc` = Tak).
    *   `wynik_niedokladne.gpkg` – zawiera tylko punkty niespełniające warunku dokładnościowego (kolumna `osiaga_dokladnosc` ≠ Tak).
*   Kolumna `eksport` w plikach GPKG przyjmuje wartość `True` tylko dla punktów spełniających warunek dokładnościowy, w pozostałych przypadkach `False`.
*   Możliwe kolumny:
    *   `id_odniesienia`, `x_odniesienia`, `y_odniesienia`, `h_odniesienia`: Dane z pliku wejściowego.
    *   `diff_h_geoportal`: Różnica wysokości pomiędzy plikiem wejściowym a geoportalem (wstawiana po h_odniesienia).
    *   `osiaga_dokladnosc`: Informacja (Tak/Nie), czy różnica wysokości mieści się w zadanej tolerancji (ostatnia kolumna).
    *   `eksport`: Flaga logiczna (True/False) – czy punkt spełnia warunek dokładnościowy.
    *   `id_porownania`, `x_porownania`, `y_porownania`, `h_porownania`: Dane dopasowanego punktu z pliku porównawczego.
    *   `diff_h`: Różnica wysokości pomiędzy plikiem wejściowym a porównawczym.
    *   `odleglosc_pary`: Odległość w metrach między sparowanymi punktami.
    *   `diff_h_geoportal_pair`: Różnica wysokości pomiędzy punktem porównawczym a geoportalem (w trybie plik+plik+geoportal).
    *   `geoportal_h`: Wysokość pobrana z serwisu Geoportal.gov.pl.

### Szczegółowy Przebieg Pracy Programu

1. **Uruchomienie programu**
    * Upewnij się, że środowisko wirtualne jest aktywne (jeśli je utworzyłeś).
    * Uruchom skrypt poleceniem:
      ```bash
      python geo_comparator.py
      ```
2. **Wybór trybu działania**
    * Program wyświetli menu z trzema trybami:
        1. Porównanie pliku wejściowego z drugim plikiem.
        2. Porównanie pliku wejściowego z danymi z Geoportal.gov.pl.
        3. Porównanie pliku wejściowego z drugim plikiem ORAZ z Geoportal.gov.pl.
    * Wybierz odpowiednią opcję wpisując 1, 2 lub 3.
3. **Podanie parametrów**
    * Jeśli wybrano tryb 1 lub 3, podaj maksymalną odległość wyszukiwania pary punktów (w metrach). Wpisz 0, aby pominąć ten warunek.
    * Podaj ścieżkę do pliku wejściowego (możesz przeciągnąć plik z Eksploratora Windows – program automatycznie usunie cudzysłowy lub apostrofy otaczające ścieżkę).
    * Odpowiedz, czy plik wejściowy ma zamienioną kolejność kolumn (Y,X zamiast X,Y).
    * Jeśli wybrano tryb 1 lub 3, podaj ścieżkę do pliku porównawczego i odpowiedz na pytanie o zamianę kolumn.
    * Jeśli wybrano tryb 2 lub 3, podaj dopuszczalną różnicę wysokości względem geoportalu (tolerancję).
4. **Wczytywanie i analiza danych**
    * Program automatycznie wykryje separator i strukturę pliku wejściowego.
    * W razie potrzeby doda automatyczną numerację punktów.
    * Przekształci współrzędne do odpowiedniego układu.
5. **Pobieranie danych z Geoportalu** (jeśli wybrano tryb 2 lub 3)
    * Współrzędne są transformowane do układu 2180 i wysyłane do API Geoportalu w paczkach po 300 punktów.
    * Wyniki są dopasowywane do punktów wejściowych z zachowaniem precyzji (zaokrąglenie do 2 miejsc po przecinku).
6. **Porównanie z plikiem referencyjnym** (jeśli wybrano tryb 1 lub 3)
    * Program buduje indeks przestrzenny i paruje punkty na podstawie odległości oraz wzajemności.
7. **Obliczanie różnic i flag dokładności**
    * Dla każdego punktu obliczana jest różnica wysokości względem geoportalu i/lub pliku porównawczego.
    * Jeśli podano tolerancję, program ustala, czy punkt spełnia warunek dokładnościowy (`osiaga_dokladnosc` = Tak/Nie).
    * Kolumna `eksport` w plikach GPKG przyjmuje wartość True tylko dla punktów spełniających warunek dokładnościowy.
8. **Eksport wyników**
    * Tworzony jest plik `wynik.csv` z kompletem wyników (wszystkie punkty, bez względu na warunek dokładnościowy).
    * Tworzone są trzy pliki GeoPackage:
        * `wynik.gpkg` – wszystkie punkty.
        * `wynik_dokladne.gpkg` – tylko punkty spełniające warunek dokładnościowy.
        * `wynik_niedokladne.gpkg` – tylko punkty niespełniające warunku dokładnościowego.
    * Pliki GPKG można otworzyć w QGIS lub innym programie GIS.

### Tryb Deweloperski

Na samej górze skryptu znajduje się flaga `DEBUG_MODE`. Ustawienie jej na `True` włączy wyświetlanie szczegółowych komunikatów diagnostycznych, które mogą być pomocne przy rozwiązywaniu problemów.

---

**Masz pytania lub napotkałeś problem?**

Napisz na issues lub sprawdź changelog, aby zobaczyć historię zmian.