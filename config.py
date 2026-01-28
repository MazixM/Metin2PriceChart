# Konfiguracja aplikacji

# URL strony z danymi
STORE_URL = "https://metin2alerts.com/store/"

# Interwał odświeżania danych (w sekundach)
REFRESH_INTERVAL = 300  # 5 minut

# Serwer do monitorowania (domyślnie pierwszy dostępny)
DEFAULT_SERVER = None  # None = pierwszy dostępny

# ID serwera dla API (np. 426)
# Jeśli None, używa domyślnego serwera (426)
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
