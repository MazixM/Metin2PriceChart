# Konfiguracja aplikacji
# Skopiuj: cp config.example.py config.py  (config.py jest w .gitignore – nie nadpisuje git pull)

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
DEFAULT_SERVER_ID = 426

# URL pliku z tłumaczeniami nazw przedmiotów
TRANSLATION_URL = "https://metin2alerts.com/m2_data/pl/item_names.json"

# Port i host – często nadpisywane zmiennymi środowiskowymi (PORT, HOST)
import os
WEB_PORT = int(os.environ.get('PORT', 5001))
WEB_HOST = os.environ.get('HOST', '0.0.0.0')

# Tryb oszczędzania RAM (LOW_MEMORY=1 lub ustaw True poniżej)
LOW_MEMORY_DEFAULT = False
LOW_MEMORY = os.environ.get('LOW_MEMORY', str(LOW_MEMORY_DEFAULT)).lower() in ('1', 'true', 'yes')
