# Dziennik Zmian (Changelog)

Wszystkie istotne zmiany w tym projekcie będą dokumentowane w tym pliku.

Format bazuje na [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), a projekt stosuje [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

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