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

# Wersja w rogu UI: z env VERSION, RENDER_GIT_COMMIT, GITHUB_SHA lub z git. Opcjonalnie GITHUB_REPO (URL repo) – wersja będzie linkiem.
def _get_version():
    v = os.environ.get('VERSION') or os.environ.get('RENDER_GIT_COMMIT') or os.environ.get('GITHUB_SHA')
    if v:
        return (v.strip())[:12]
    try:
        import subprocess
        r = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True, timeout=2, cwd=os.path.dirname(os.path.abspath(__file__)))
        if r.returncode == 0 and r.stdout:
            return r.stdout.strip()
    except Exception:
        pass
    return 'dev'
APP_VERSION = _get_version()
GITHUB_REPO = os.environ.get('GITHUB_REPO', '').rstrip('/')
