# Dziennik Zmian (Changelog)

Wszystkie istotne zmiany w tym projekcie będą dokumentowane w tym pliku.

Format bazuje na [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), a projekt stosuje [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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

*   Wersja początkowa programu.