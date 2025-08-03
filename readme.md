# diffH - Geo-Komparator wysokości

**Porównywanie i transformacja współrzędnych geoprzestrzennych**

---

### O programie

`diffH` to narzędzie uruchamiane w linii poleceń (CLI), stworzone w języku Python. Jego głównym zadaniem jest przetwarzanie, transformacja i porównywanie danych geoprzestrzennych zawartych w plikach tekstowych. Skrypt został zaprojektowany z myślą o pracy z polskimi układami współrzędnych PL-2000 i PL-1992.

### Główne Funkcje

*   **Transformacja Współrzędnych:** Automatyczne przeliczanie współrzędnych z układu **PL-2000** (strefy 5, 6, 7, 8 - EPSG: 2176, 2177, 2178, 2179) do układu **PL-1992** (EPSG: 2180).
*   **Przyspieszenie GPU (CUDA):** Automatyczne wykrywanie kart NVIDIA i wykorzystanie przyspieszenia CUDA do transformacji współrzędnych. Program automatycznie przełącza się między przetwarzaniem GPU a CPU w zależności od dostępności sprzętu.
*   **Eksport rozrzedzonej siatki:** Możliwość wygenerowania reprezentatywnej, rozrzedzonej siatki punktów, które spełniają kryterium dokładności. Algorytm bazuje na heksagonalnym pokryciu zadanego obszaru.
*   **Walidacja stref układu współrzędnych:** Program sprawdza, czy plik wejściowy i plik z zakresem są w tej samej strefie PL-2000, aby uniknąć błędów.
*   **Obsługa plików Excel:** Dodano możliwość wczytywania plików wejściowych w formatach `.xls` i `.xlsx`.
*   **Personalizowana autonumeracja:** Przy wczytywaniu plików 3-kolumnowych (bez ID), użytkownik może podać własny prefiks dla automatycznie generowanych numerów punktów.
*   **Porównanie z Geoportal.gov.pl:** Pobieranie wysokości z serwisu Geoportal.gov.pl dla punktów z pliku wejściowego i dołączenie ich do wyników. Wysyłka punktów do API odbywa się w paczkach po maksymalnie 300 punktów.
*   **Zaawansowane Porównanie Plików:** Porównywanie punktów z pliku wejściowego z punktami z drugiego pliku referencyjnego. Parowanie odbywa się na podstawie **dwóch warunków**:
    1.  **Progu odległości:** para jest tworzona tylko, jeśli odległość między punktami jest mniejsza niż zdefiniowana przez użytkownika.
    2.  **Wzajemności:** punkty muszą być dla siebie nawzajem najbliższymi sąsiadami.
*   **Obliczanie różnic wysokości:**
    *   Automatyczne obliczanie różnicy wysokości pomiędzy plikiem wejściowym a plikiem porównawczym (`diff_h`).
    *   Obliczanie różnicy wysokości pomiędzy plikiem wejściowym a geoportalem (`diff_h_geoportal`).
    *   W trybie porównania plik + plik + geoportal: dodatkowa kolumna `diff_h_geoportal_pair` (różnica h_porownania - geoportal_h).
*   **Tolerancja dokładności:**
    *   Możliwość podania przez użytkownika dopuszczalnej różnicy wysokości **zarówno względem Geoportalu, jak i względem drugiego pliku**.
    *   Kolumna `osiaga_dokladnosc` (Tak/Nie) informuje, czy różnica (`diff_h` lub `diff_h_geoportal`) mieści się w zadanej tolerancji.
*   **Inteligentna Analiza Danych:**
    *   **Automatyczne wykrywanie separatora** w plikach wejściowych (obsługuje średnik, przecinek, spację/tabulator).
    *   **Automatyczne wykrywanie konwencji osi współrzędnych** (czy plik używa układu geodezyjnego `X=Północ, Y=Wschód`, czy standardu GIS `X=Wschód, Y=Północ`). Użytkownik może też ręcznie wskazać zamianę osi (Y,X).
*   **Parametryzacja zaokrąglania:** Możliwość zdefiniowania przez użytkownika liczby miejsc po przecinku dla współrzędnych i wysokości w danych wejściowych i wynikowych.
*   **Przyjazny Interfejs:** Skrypt prowadzi użytkownika krok po kroku przez proces wyboru opcji i podawania plików.
*   **Czyste Pliki Wynikowe:** Generuje przejrzyste, tabelaryczne pliki `wynik.csv` (oraz `_dokladne.csv` i `_niedokladne.csv`), gotowe do importu w innych programach (np. Excel, QGIS). Wyniki są sortowane malejąco według wartości bezwzględnej różnicy wysokości.
*   **Eksport do GeoPackage (GPKG):** Możliwość zapisu wyników do pliku GeoPackage, który można otworzyć bezpośrednio w QGIS lub innych programach GIS. Ułatwia to dalszą analizę i wizualizację danych przestrzennych.

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

6.  **Opcjonalnie - dla przyspieszenia GPU:** Jeśli masz kartę NVIDIA, biblioteki CUDA zostaną automatycznie zainstalowane. Program automatycznie wykryje dostępność CUDA i użyje przyspieszenia GPU.

Po wykonaniu tych kroków środowisko jest gotowe do pracy.

### Użycie

1.  Upewnij się, że Twoje środowisko wirtualne jest aktywne (jeśli je utworzyłeś).
2.  Uruchom skrypt za pomocą polecenia:
    ```bash
    python geo_comparator.py
    ```
3.  Postępuj zgodnie z instrukcjami na ekranie:
    *   Wybierz tryb porównania (1 - plik z plikiem, 2 - plik z geoportalem, 3 - plik z plikiem i geoportalem).
    *   Podaj ścieżki do pliku wejściowego i (opcjonalnie) porównawczego oraz inne parametry zgodnie z monitami.
4.  Po zakończeniu pracy, w folderze ze skryptem zostaną utworzone pliki wynikowe.

### Format Pliku Wejściowego

*   Obsługiwane formaty: `.txt`, `.csv`, `.xls`, `.xlsx`.
*   Struktura pliku:
    *   4 kolumny: `numer_punktu`, `współrzędna_X`, `współrzędna_Y`, `wysokość_H`.
    *   3 kolumny: `współrzędna_X`, `współrzędna_Y`, `wysokość_H`. W tym przypadku program poprosi o podanie prefiksu do automatycznej numeracji punktów.
*   Skrypt automatycznie wykrywa, czy plik jest zapisany w konwencji:
    *   **Geodezyjnej:** `X` to współrzędna północna (Northing), `Y` to wschodnia (Easting).
    *   **GIS:** `X` to współrzędna wschodnia (Easting), `Y` to północna (Northing).
*   Użytkownik może ręcznie wskazać zamianę osi (Y,X zamiast X,Y).
**Przykład:**
```csv
1001;5958143.50;7466893.08;137.90
1002;5955909.72;7466350.05;138.82
```

### Format Pliku Wyjściowego

*   Nazwy plików: `wynik.csv`, `wynik_dokladne.csv`, `wynik_niedokladne.csv`.
*   Separator: średnik (`;`)
*   Brakujące dane są oznaczane jako `brak_danych`.
*   Dodatkowo generowane są pliki GeoPackage (GPKG) z wynikami przestrzennymi gotowymi do użycia w QGIS lub innym oprogramowaniu GIS:
    *   `wynik.gpkg` – zawiera wszystkie punkty.
    *   `wynik_dokladne.gpkg` – zawiera tylko punkty spełniające warunek dokładnościowy (kolumna `osiaga_dokladnosc` = Tak).
    *   `wynik_niedokladne.gpkg` – zawiera tylko punkty niespełniające warunku dokładnościowego (kolumna `osiaga_dokladnosc` ≠ Tak).
    *   `wynik_siatka.gpkg` i `wynik_siatka.csv` – (opcjonalnie) zawierają reprezentatywną, rozrzedzoną siatkę punktów.
*   Kolumna `eksport` w plikach GPKG przyjmuje wartość `True` tylko dla punktów spełniających warunek dokładnościowy, w pozostałych przypadkach `False`.
*   Możliwe kolumny:
    *   `id_odniesienia`, `x_odniesienia`, `y_odniesienia`, `h_odniesienia`: Dane z pliku wejściowego.
    *   `diff_h_geoportal`: Różnica wysokości pomiędzy plikiem wejściowym a geoportalem (wstawiana po h_odniesienia).
    *   `osiaga_dokladnosc`: Informacja (Tak/Nie), czy różnica wysokości (`diff_h` lub `diff_h_geoportal`) mieści się w zadanej tolerancji (ostatnia kolumna).
    *   `eksport`: Flaga logiczna (True/False) – czy punkt spełnia warunek dokładnościowy.
    *   `id_porownania`, `x_porownania`, `y_porownania`, `h_porownania`: Dane dopasowanego punktu z pliku porównawczego.
    *   `diff_h`: Różnica wysokości pomiędzy plikiem wejściowym a porównawczym.
    *   `odleglosc_pary`: Odległość w metrach między sparowanymi punktami, zaokrąglona do 3 miejsc po przecinku.
    *   `diff_h_geoportal_pair`: Różnica wysokości pomiędzy punktem porównawczym a geoportalem (w trybie plik+plik+geoportal).
    *   `geoportal_h`: Wysokość pobrana z serwisu Geoportal.gov.pl.

### Szczegółowy Przebieg Pracy Programu

1.  **Uruchomienie programu**
    *   Upewnij się, że środowisko wirtualne jest aktywne (jeśli je utworzyłeś).
    *   Uruchom skrypt poleceniem:
        ```bash
        python geo_comparator.py
        ```
2.  **Wybór trybu działania**
    *   Program wyświetli menu z trzema trybami:
        1.  Porównanie pliku wejściowego z drugim plikiem.
        2.  Porównanie pliku wejściowego z danymi z Geoportal.gov.pl.
        3.  Porównanie pliku wejściowego z drugim plikiem ORAZ z Geoportal.gov.pl.
    *   Wybierz odpowiednią opcję wpisując 1, 2 lub 3.
3.  **Podanie parametrów**
    *   Jeśli wybrano tryb 1 lub 3, podaj maksymalną odległość wyszukiwania pary punktów (w metrach). Wpisz 0, aby pominąć ten warunek.
    *   Jeśli wybrano tryb 1 lub 3, podaj dopuszczalną różnicę wysokości względem pliku porównawczego (tolerancję).
    *   Podaj liczbę miejsc po przecinku do zaokrąglenia danych wejściowych.
    *   Podaj ścieżkę do pliku wejściowego (możesz przeciągnąć plik z Eksploratora Windows – program automatycznie usunie cudzysłowy lub apostrofy otaczające ścieżkę).
    *   Odpowiedz, czy plik wejściowy ma zamienioną kolejność kolumn (Y,X zamiast X,Y).
    *   Jeśli wybrano tryb 1 lub 3, podaj ścieżkę do pliku porównawczego i odpowiedz na pytanie o zamianę kolumn.
    *   Jeśli wybrano tryb 2 lub 3, podaj dopuszczalną różnicę wysokości względem geoportalu (tolerancję).
    *   Jeśli wybrano tryb 2 lub 3, program zapyta, czy wygenerować **rozrzedzoną siatkę punktów**. Jeśli odpowiesz twierdząco:
        *   Podaj oczekiwaną odległość między punktami siatki (w metrach).
        *   Podaj ścieżkę do pliku z zakresem (wielobokiem), w którym ma być wygenerowana siatka.
        *   Odpowiedz, czy plik z zakresem ma zamienioną kolejność kolumn.
4.  **Wczytywanie i analiza danych**
    *   Program automatycznie wykryje separator, strukturę pliku wejściowego oraz sprawdzi zgodność stref układu współrzędnych (jeśli podano plik z zakresem).
    *   W razie potrzeby doda automatyczną numerację punktów.
    *   Przekształci współrzędne do odpowiedniego układu.
5.  **Pobieranie danych z Geoportalu** (jeśli wybrano tryb 2 lub 3)
    *   Współrzędne są transformowane do układu 2180 i wysyłane do API Geoportalu w paczkach po 300 punktów.
    *   Wyniki są dopasowywane do punktów wejściowych z zachowaniem precyzji (zaokrąglenie do 2 miejsc po przecinku).
6.  **Porównanie z plikiem referencyjnym** (jeśli wybrano tryb 1 lub 3)
    *   Program buduje indeks przestrzenny i paruje punkty na podstawie odległości oraz wzajemności.
7.  **Obliczanie różnic i flag dokładności**
    *   Dla każdego punktu obliczana jest różnica wysokości względem geoportalu i/lub pliku porównawczego.
    *   Jeśli podano tolerancję, program ustala, czy punkt spełnia warunek dokładnościowy (`osiaga_dokladnosc` = Tak/Nie). W trybie 3 priorytet ma tolerancja względem Geoportalu.
8.  **Generowanie rozrzedzonej siatki** (jeśli zażądano)
    *   Program wybiera reprezentatywne punkty spełniające kryterium dokładności, które pokrywają zadany obszar w formie siatki heksagonalnej.
    *   Wyniki zapisywane są do plików `wynik_siatka.csv` i `wynik_siatka.gpkg`.
9.  **Eksport wyników**
    *   Tworzone są pliki `wynik.csv`, `wynik_dokladne.csv` i `wynik_niedokladne.csv`.
    *   Tworzone są trzy pliki GeoPackage:
        *   `wynik.gpkg` – wszystkie punkty.
        *   `wynik_dokladne.gpkg` – tylko punkty spełniające warunek dokładnościowy.
        *   `wynik_niedokladne.gpkg` – tylko punkty niespełniające warunku dokładnościowego.
    *   Pliki GPKG można otworzyć w QGIS lub innym programie GIS.

### Tryb Deweloperski

Na samej górze skryptu znajduje się flaga `DEBUG_MODE`. Ustawienie jej na `True` włączy wyświetlanie szczegółowych komunikatów diagnostycznych, które mogą być pomocne przy rozwiązywaniu problemów.

---

**Masz pytania lub napotkałeś problem?**

Napisz na issues lub sprawdź changelog, aby zobaczyć historię zmian.