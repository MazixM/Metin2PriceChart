# Konfiguracja aplikacji

# URL strony z danymi
STORE_URL = "https://metin2alerts.com/store/"

# Interwał odświeżania danych (w sekundach)
REFRESH_INTERVAL = 300  # 5 minut

# Dostępne serwery
AVAILABLE_SERVERS = {
    426: "[RUBY] Charon",
    702: "Polska"
}

# ID serwera dla API (domyślnie 426)
# Można zmienić przez interfejs użytkownika
DEFAULT_SERVER_ID = 426

# URL pliku z tłumaczeniami nazw przedmiotów na język polski
# Plik zawiera mapowanie vnum (ID przedmiotu) -> polska nazwa
TRANSLATION_URL = "https://metin2alerts.com/m2_data/pl/item_names.json"

# Port dla web interface
# Uwaga: Port 5000 jest często używany przez Steam Game State Integration (CS:GO)
# Jeśli masz konflikt, zmień na inny port (np. 5001, 8080)
# W środowisku chmurowym (Render, Heroku) port jest ustawiany przez zmienną środowiskową PORT
import os
WEB_PORT = int(os.environ.get('PORT', 5001))

# Adres nasłuchu: '0.0.0.0' = IPv4, '::' = IPv6 (gdy VPS ma tylko IPv6)
WEB_HOST = os.environ.get('HOST', '0.0.0.0')

# Tryb oszczędzania RAM (mniejszy cache SQLite, mniejsze batchy, bez tabeli price_history, gc po serwerze)
# Ustaw True tutaj dla małego RAM lub: export LOW_MEMORY=1
LOW_MEMORY_DEFAULT = False
LOW_MEMORY = os.environ.get('LOW_MEMORY', str(LOW_MEMORY_DEFAULT)).lower() in ('1', 'true', 'yes')
