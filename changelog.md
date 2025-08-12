# Dziennik Zmian (Changelog)

Wszystkie istotne zmiany w tym projekcie będą dokumentowane w tym pliku.

Format bazuje na [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), a projekt stosuje [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2025-08-04

### Dodano

*   **Tryb 4 - Wzbogacanie danych o wysokość:**
    *   Dodano nowy tryb działania (opcja 4 w menu), który umożliwia wczytanie pliku z samymi współrzędnymi (w formacie `ID,X,Y` lub `X,Y`).
    *   Program automatycznie pobiera wysokość z API Geoportal.gov.pl i zapisuje kompletne dane (`ID,X,Y,H`) do plików `wynik_geoportal.csv` i `wynik_geoportal.gpkg`.

*   **Tryb 5 - Generowanie siatki i pobieranie wysokości:**
    *   Dodano nowy, niezależny tryb działania (opcja 5 w menu).
    *   Na podstawie pliku z zakresem (wielobokiem) i zadanego odstępu, program generuje regularną siatkę heksagonalną punktów.
    *   Dla każdego punktu siatki pobierana jest wysokość z API Geoportal.gov.pl.
    *   Użytkownik może zdefiniować własny prefiks dla automatycznie generowanych numerów punktów.
    *   Wyniki są zapisywane do plików `wynik_siatka_geoportal.csv` i `wynik_siatka_geoportal.gpkg`.

### Zmieniono

*   **Refaktoryzacja wczytywania danych:** Ujednolicono funkcję `load_data`, aby obsługiwała pliki wejściowe z kolumną wysokości i bez niej, co uprościło logikę dla nowych trybów.
*   **Ulepszenia eksportu:** Funkcje `export_to_csv` i `export_to_geopackage` zostały dostosowane, aby poprawnie obsługiwać wyniki z trybów 4 i 5, które nie wymagają podziału na pliki `_dokladne` i `_niedokladne`.
*   **Interfejs użytkownika:** Zaktualizowano menu główne i komunikaty, aby uwzględnić nowe tryby 4 i 5.

## [1.3.1] - 2025-08-02

### Dodano

*   **Tolerancja dokładności dla porównania plik-plik (tryby 1 i 3):**
    *   Program pyta teraz użytkownika o dopuszczalną różnicę wysokości (`diff_h`) przy porównywaniu z drugim plikiem.
    *   Generowana jest kolumna `osiaga_dokladnosc` (Tak/Nie) również dla trybu 1, co umożliwia podział plików wynikowych na `_dokladne` i `_niedokladne`.
    *   Dodano nową opcję `comparison_tolerance` do pliku konfiguracyjnego `config.json`.

### Zmieniono

*   Wartość `odleglosc_pary` w plikach wynikowych jest teraz zaokrąglana do 3 miejsc po przecinku przy użyciu standardowego zaokrąglenia.

### Naprawiono

*   **Krytyczny błąd w trybie 3:** Naprawiono błąd, przez który dane z pliku porównawczego (np. `id_porownania`, `diff_h`) nie były wyświetlane (pokazywały `brak_danych`), gdy jednocześnie aktywne było porównanie z Geoportalem.
*   Usprawniono logikę przetwarzania, aby zapewnić spójność danych we wszystkich trybach porównawczych.

## [1.3.0] - 2025-08-01

### Dodano

*   **Przyspieszenie GPU (CUDA):** Automatyczne wykrywanie kart NVIDIA i wykorzystanie przyspieszenia CUDA do transformacji współrzędnych.
    *   Program automatycznie przełącza się między przetwarzaniem GPU a CPU w zależności od dostępności sprzętu.
    *   Brak ingerencji użytkownika - wybór metody odbywa się automatycznie.
    *   Zoptymalizowane przetwarzanie partiami dla lepszego wykorzystania pamięci GPU.
    *   Fallback do przetwarzania CPU w przypadku braku CUDA lub błędów GPU.
    *   Dodano zależności CuPy dla obsługi CUDA (opcjonalne instalowanie).
*   **Test wykrywania CUDA:** Dodano skrypt `test_cuda_detection.py` do sprawdzenia dostępności CUDA.

### Zmieniono

*   Zaktualizowano `requirements.txt` z zależnościami CUDA (CuPy).
*   Zmodyfikowano moduł `coordinate_transform.py` do automatycznego wykrywania i używania CUDA.
*   Dodano informację o metodzie transformacji w interfejsie użytkownika.
*   Zaktualizowano dokumentację README.md z informacjami o przyspieszeniu GPU.

## [1.2.2] - 2025-07-03

### Dodano

*   **Eksport rozrzedzonej siatki (thinned grid):**
    *   Możliwość wygenerowania i eksportu reprezentatywnej, rozrzedzonej siatki punktów, które spełniają kryterium dokładności.
    *   Algorytm bazuje na heksagonalnym pokryciu zadanego obszaru i wybiera najlepszy punkt z każdej komórki.
    *   Wymaga podania pliku z zakresem (wielobokiem) oraz oczekiwanej odległości między punktami siatki.
    *   Wyniki zapisywane są do plików `wynik_siatka.csv` i `wynik_siatka.gpkg`.
*   **Walidacja zgodności stref układu współrzędnych:** Program sprawdza, czy plik wejściowy i plik z zakresem są w tej samej strefie PL-2000. W przypadku niezgodności, program przerywa działanie, aby uniknąć błędów.
*   **Obsługa plików Excel:** Dodano możliwość wczytywania plików wejściowych w formatach `.xls` i `.xlsx`.
*   **Personalizowana autonumeracja:** Przy wczytywaniu plików 3-kolumnowych (bez ID), użytkownik może podać własny prefiks dla automatycznie generowanych numerów punktów.

### Zmieniono

*   Zaktualizowano interfejs użytkownika i komunikaty, aby uwzględnić nową funkcjonalność generowania siatki.
*   Ulepszono logikę wczytywania danych, aby obsługiwać nowe formaty i opcje.

## [1.2.1] - 2025-07-02

### Dodano

* Parametryzacja zaokrąglenia danych wejściowych – możliwość ustawienia liczby miejsc po przecinku dla współrzędnych i wysokości.
* Logowanie do plików – zapisywanie logów z działania programu do osobnych plików.
* Domyślne wartości dla komunikatów użytkownika w funkcjach wejściowych (odległość, tolerancja) oraz informowanie o ich użyciu.

### Zmieniono

* Poprawa logowania: lepsza czytelność, dodanie ponawiania wysyłki punktów w przypadku braku danych.
* Pomijanie pierwszego wiersza, gdy druga kolumna nie jest liczbą.

### Naprawiono

* Ponawianie pobierania punktów, gdy występuje brak danych z geoportalu.

## [1.2.0] - 2025-07-01

### Dodano

* Eksport wyników do trzech plików GeoPackage (GPKG):
    * `wynik.gpkg` – wszystkie punkty,
    * `wynik_dokladne.gpkg` – tylko punkty spełniające warunek dokładnościowy,
    * `wynik_niedokladne.gpkg` – tylko punkty niespełniające warunku dokładnościowego.
* Kolumna `eksport` w plikach GPKG – logiczna flaga (True/False) informująca, czy punkt spełnia warunek dokładnościowy.
* Automatyczne usuwanie cudzysłowów lub apostrofów otaczających ścieżkę pliku przy wczytywaniu (przeciąganie pliku z Eksploratora Windows).

### Zmieniono

* Szczegółowy opis działania programu i eksportu w pliku README.md.
* Poprawa logiki zaokrąglania i prezentacji różnic wysokości (brak długich ogonków po przecinku).

---

## [1.1.2] - 2025-06-30

### Dodano

* Selektywne debugowanie – możliwość logowania tylko wybranego punktu (np. `tg1`).
* Ograniczenie liczby logów debugowania w operacjach masowych (np. transformacje, pobieranie z API) do pierwszego punktu lub wybranego punktu.
* Poprawa formatowania i dopasowania kluczy przy pobieraniu wysokości z Geoportalu (format "Y X", zaokrąglenie do 2 miejsc po przecinku).
* Możliwość logowania wartości odejmowanych przy obliczaniu różnicy wysokości względem geoportalu.

### Naprawiono

* Błąd precyzji float – wyniki różnic wysokości są zaokrąglane do 2 lub 3 miejsc po przecinku.
* Poprawa dopasowania odpowiedzi z Geoportalu do punktów wejściowych (lepsze klucze lookup).
* Poprawa czytelności i selektywności logów debugowania.

## [1.1.1] - 2025-06-29

### Zmieniono

* Kolumna `osiaga_dokladnosc` eksportowana do CSV i GeoPackage przyjmuje teraz wartości "Tak"/"Nie" zamiast "T"/"F".
* Dodano eksport wyników do pliku GeoPackage (GPKG) – umożliwia bezpośrednie wykorzystanie wyników w aplikacjach GIS, poprawiając interoperacyjność danych przestrzennych.
* Zaktualizowano komunikaty interfejsu oraz zależności, aby odzwierciedlić nową opcję eksportu do GeoPackage.

## [1.1.0] - 2025-06-28

### Dodano

* Automatyczne obliczanie różnicy wysokości pomiędzy plikiem wejściowym a plikiem porównawczym (`diff_h`) oraz pomiędzy plikiem wejściowym a geoportalem (`diff_h_geoportal`).
* Kolumna `diff_h_geoportal` jest wstawiana po kolumnie `h_odniesienia`.
* Kolumna `osiaga_dokladnosc` (T/F) informująca, czy różnica wysokości względem geoportalu mieści się w zadanej tolerancji.
* Możliwość podania tolerancji różnicy wysokości względem geoportalu przez użytkownika.
* Wyniki sortowane malejąco według wartości bezwzględnej różnicy wysokości względem geoportalu.
* Obsługa porównania plik + plik + geoportal: dodatkowa kolumna `diff_h_geoportal_pair` (różnica h_porownania - geoportal_h).
* Licznik sparowanych punktów (`paired_count`) przywrócony i poprawnie zliczany.

## [1.0.1] - 2025-06-27

### Naprawiono

* Fix wysyłki punktów do geoportalu – ograniczenie paczki do 300 punktów wysyłanych na raz.
* Dodano zaokrąglanie wczytywanych i zapisywanych współrzędnych do 2 miejsc po przecinku.
* Zaokrąglenie zgodnie z regułą Bradissa-Kryłowa.

## [1.0.0] - 2025-06-24

### Dodano

*   Wersja początkowa 