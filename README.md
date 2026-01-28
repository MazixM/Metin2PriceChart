# Metin2 Price Chart - Wykres Cen Ulepszaczy

Aplikacja do monitorowania i wizualizacji cen ulepszaczy z serwera Metin2 Alerts.

## Funkcje

- ✅ Automatyczne pobieranie danych o cenach ulepszaczy ze strony metin2alerts.com/store/
- ✅ **Web interface** do przeglądania danych w czasie rzeczywistym
- ✅ Wykresy interaktywne z historią cen (używając Plotly)
- ✅ Automatyczne odświeżanie danych co 5 minut
- ✅ Zapis historii cen do pliku JSON
- ✅ Statystyki cen (min, max, średnia, aktualna)
- ✅ Wyszukiwanie konkretnych przedmiotów
- ✅ Wyświetlanie historii cen dla każdego przedmiotu
- ✅ Tłumaczenie nazw przedmiotów na język polski

## Instalacja

1. Zainstaluj wymagane biblioteki:
```bash
pip install -r requirements.txt
```

2. Upewnij się, że masz zainstalowany Chrome/Chromium (wymagany dla Selenium)

## Użycie

### Uruchomienie głównej aplikacji:
```bash
python main.py
```

Aplikacja uruchomi:
- **Background service** - automatycznie pobiera dane co 5 minut (zgodnie z `REFRESH_INTERVAL` w `config.py`)
- **Web interface** - dostępny pod adresem http://localhost:5000

### Web Interface

Po uruchomieniu aplikacji, otwórz przeglądarkę i przejdź do:
```
http://localhost:5000
```

Funkcje web interface:
- **Przeglądanie wszystkich przedmiotów** - widok kart z najnowszymi cenami
- **Wyszukiwanie** - wpisz nazwę przedmiotu, aby znaleźć konkretne przedmioty
- **Historia cen** - kliknij na kartę przedmiotu, aby zobaczyć wykres historii cen
- **Automatyczne odświeżanie** - dane są automatycznie odświeżane co 30 sekund
- **Statystyki** - wyświetlanie liczby przedmiotów i punktów danych

### Pliki wyjściowe

- `price_history.json` - historia wszystkich pobranych cen

## Konfiguracja

Edytuj plik `config.py`, aby dostosować:

- `REFRESH_INTERVAL` - interwał odświeżania danych w sekundach (domyślnie 300 = 5 minut)
- `UPGRADE_ITEMS` - lista nazw ulepszaczy do śledzenia (można używać tureckich/angielskich nazw)
- `DEFAULT_SERVER_ID` - ID serwera dla API (domyślnie 426)
- `STORE_URL` - URL strony z danymi
- `TRANSLATION_URL` - URL pliku z tłumaczeniami nazw przedmiotów na polski

## Wymagania

- Python 3.7+
- Chrome/Chromium (dla Selenium - opcjonalne, jeśli API działa)
- Połączenie z internetem
- Flask (dla web interface)

## API Endpoints

Web interface udostępnia następujące endpointy API:

- `GET /` - Strona główna z interfejsem użytkownika
- `GET /api/latest` - Najnowsze dane dla wszystkich przedmiotów
- `GET /api/item/<item_name>` - Historia cen dla konkretnego przedmiotu
- `GET /api/search?q=<query>` - Wyszukiwanie przedmiotów po nazwie
- `GET /api/stats` - Statystyki dla wszystkich przedmiotów
- `GET /api/items` - Lista wszystkich unikalnych przedmiotów
