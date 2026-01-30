# Deployment Guide - Metin2 Price Chart

## Wymagania RAM

Dane są pobierane **wyłącznie przez HTTP** (API metin2alerts.com), bez przeglądarki.

| Scenariusz | Zalecane RAM |
|------------|---------------|
| **Minimum** | **512 MB** – Python, Flask, SQLite (cache 64 MB), worker przy pobieraniu jednego serwera (~40–80k ofert) |
| **Bezpiecznie** | **1 GB** – zapas na szczyty przy 2 serwerach i wielu requestach |

**Skąd te wartości:**
- Python + Flask: ~50–100 MB  
- SQLite: 64 MB cache na połączenie (`PRAGMA cache_size=-64000`)  
- Worker: przy zapisie snapshotu (~80k ofert) krótkotrwały szczyt ~100–200 MB  

**Mało RAM (np. 256–512 MB):** zmniejsz cache SQLite: `export SQLITE_CACHE_KB=-16000` (16 MB zamiast 64 MB). Wartość ujemna = rozmiar w KB (`-16000` = 16 MB).

### Serwer z małym RAM (np. 384 MB)

**Najprościej – tryb LOW_MEMORY (jedna zmienna):**

```bash
export LOW_MEMORY=1
python main.py
```

`LOW_MEMORY=1` ustawia automatycznie:
- **SQLITE_CACHE_KB=-4096** (4 MB zamiast 64 MB)
- **BATCH_INSERT_SIZE=2000** (mniejsze porcje zapisu)
- **SKIP_PRICE_HISTORY_TABLE=1** (zapis tylko do tabeli `offers`, bez duplikatu w `price_history`)
- Worker po każdym serwerze zwalnia pamięć (`gc.collect()`)
- Pomijane jest logowanie statystyk w workerze (mniej zapytań do bazy)

**Ręcznie (gdy chcesz dopasować wartości):**

```bash
export SQLITE_CACHE_KB=-8192    # 8 MB cache
export BATCH_INSERT_SIZE=3000
export SKIP_PRICE_HISTORY_TABLE=1   # opcjonalnie – oszczędza RAM i dysk
python main.py
```

Opcjonalnie: uruchom **tylko jeden serwer** – w `config.py` ustaw `AVAILABLE_SERVERS = {426: "[RUBY] Charon"}` (bez 702).

---

## Opcje deploymentu

### 0. VPS (np. Ubuntu, Debian)

**Tak, aplikacja będzie działać na VPS.** Wymagania:

- **Python 3.10+** i `pip install -r requirements.txt`
- **Dostęp do internetu** (pobieranie danych z metin2alerts.com)
- **Port** – aplikacja nasłuchuje na `0.0.0.0` (dostęp z zewnątrz). Port z zmiennej `PORT` lub domyślnie `5001`.

**Uruchomienie:**

```bash
# Opcjonalnie: ścieżka do bazy (domyślnie price_history.db w katalogu roboczym)
export DATABASE_PATH=/var/lib/metin2pricechart/price_history.db
export PORT=5001
python main.py
```

**Produkcja (gunicorn):**

```bash
pip install gunicorn
export PORT=5001
gunicorn -w 1 -b 0.0.0.0:${PORT} --timeout 120 "app:app"
```

Uwaga: worker (aktualizacja danych) działa w `main.py`. Przy gunicorn worker **nie** jest uruchamiany – do pełnej funkcjonalności uruchamiaj `python main.py` albo dodaj osobny proces/cron do okresowego pobierania danych.

**Pobieranie danych:** wyłącznie przez HTTP (request do API metin2alerts.com, np. `curl`-style). Bez przeglądarki i bez dodatkowych zależności.

**Firewall:** Otwórz port (np. 5001) lub postaw reverse proxy (nginx) z SSL.

**Automatyczne aktualizowanie po commicie (webhook z GitHub):**

1. **Uruchom aplikację przez systemd** (żeby webhook mógł zrestartować usługę):
   - W katalogu projektu utwórz venv i zainstaluj zależności:  
     `python3 -m venv venv && ./venv/bin/pip install -r requirements.txt`
   - Skopiuj `metin2pricechart.service.example` do `/etc/systemd/system/metin2pricechart.service`
   - W pliku ustaw: `User`, `WorkingDirectory`, **ExecStart** – **musi używać Pythona z venv** (np. `/root/Metin2PriceChart/venv/bin/python main.py`), inaczej systemowy `python3` nie widzi Flask i będzie: `No module named 'flask'`.
   - Ustaw zmienne środowiskowe w sekcji `[Service]` (na początku startu usługi). Secret to **zwykła zmienna środowiskowa**:
     ```ini
     Environment=PORT=5001
     Environment=DATABASE_PATH=/root/Metin2PriceChart/price_history.db
     Environment=DEPLOY_WEBHOOK_SECRET=twoj_tajny_losowy_string
     Environment=DEPLOY_SERVICE=metin2pricechart
     ```
     **Secret:** dowolny długi losowy string (np. wygeneruj: `openssl rand -hex 32`). Bez spacji – albo całość w cudzysłowach: `Environment="DEPLOY_WEBHOOK_SECRET=string ze spacjami"`. Ten sam secret wpisujesz potem w GitHubie w URL webhooka: `?secret=twoj_tajny_losowy_string`.
   - Włącz i uruchom: `sudo systemctl daemon-reload && sudo systemctl enable --now metin2pricechart`

2. **Skrypt deploy** – w katalogu projektu jest `deploy.sh`. Nadaj uprawnienia: `chmod +x deploy.sh`. Opcjonalnie ustaw na VPS:
   - `DEPLOY_APP_DIR` – katalog z repo (domyślnie katalog, w którym leży `deploy.sh`)
   - `DEPLOY_PIP=1` – jeśli chcesz po `git pull` uruchamiać `pip install -r requirements.txt`
   - `DEPLOY_SERVICE=metin2pricechart` – nazwa usługi systemd do restartu (domyślnie `metin2pricechart`)

3. **Webhook w GitHubie:**
   - Repozytorium → **Settings** → **Webhooks** → **Add webhook**
   - **Payload URL:** `https://m2pricechart.bieda.it/webhook` (bez secretu w URL)
   - **Content type:** `application/json`
   - **Secret:** wpisz ten sam string co w systemd (`DEPLOY_WEBHOOK_SECRET`) – GitHub będzie podpisywał payload nagłówkiem `X-Hub-Signature-256`; aplikacja weryfikuje ten podpis. Secret nie trafia do URL.
   - **Events:** np. "Just the push event"
   - Opcjonalnie: ręczne wywołanie nadal działa z `?secret=...` lub nagłówkiem `X-Webhook-Secret`.

4. Po **pushu** na branch (np. `main`) GitHub wyśle POST na ten URL; aplikacja uruchomi `deploy.sh` w tle, skrypt zrobi `git pull` i `systemctl restart metin2pricechart`.

**Config:** `config.py` jest w `.gitignore` – nie jest w repo i nie jest nadpisywany przy `git pull`. Przy pierwszym klonowaniu na VPS: `cp config.example.py config.py` i edytuj. Jeśli w swoim repo nadal śledzisz `config.py`, usuń go z gita (plik zostaje): `git rm --cached config.py`.

**Logi:**

- **Systemd:** gdy aplikacja działa jako usługa, logi trafiają do journald:
  ```bash
  journalctl -u metin2pricechart -f      # na żywo
  journalctl -u metin2pricechart -n 200  # ostatnie 200 linii
  ```
- **Plik logów:** w jednostce systemd ustaw `Environment=LOG_FILE=/var/log/metin2pricechart/app.log` (katalog zostanie utworzony przy starcie). Wtedy logi są też w pliku.
- **Podgląd w przeglądarce:** jeśli ustawisz `LOG_FILE` i ten sam secret co webhook (lub `LOG_SECRET`), możesz podejrzeć ostatnie linie przez API:
  ```
  GET /api/logs?secret=TAJNY_STRING
  GET /api/logs?secret=...&lines=50
  ```
  Odpowiedź JSON: `{ "lines": ["...", ...], "path": "..." }`. Secret: ten sam co `DEPLOY_WEBHOOK_SECRET` albo osobno `LOG_SECRET`.

**Tylko IPv6 (VPS bez IPv4):**

- Ustaw nasłuch na IPv6: `export HOST=::` przed uruchomieniem.
- Aplikacja będzie dostępna pod adresem `http://[twoje-ipv6]:PORT`.
- **Pobieranie danych:** jeśli serwer ma **tylko IPv6**, zapytania do `metin2alerts.com` muszą iść przez IPv6 – host docelowy musi mieć rekord AAAA. Jeśli nie ma, worker nie pobierze danych (API zwróci błąd). W takim przypadku rozważ VPS z dual-stack (IPv4 + IPv6) albo tunel IPv4.

---

### 1. Render (Zalecane) ⭐

**Dlaczego Render:**
- Darmowy tier z 750 godzin/miesiąc
- Obsługuje background workers
- Automatyczny deployment z GitHub
- Łatwa konfiguracja

**Kroki:**

1. **Przygotuj repozytorium GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/TWOJE_USERNAME/Metin2PriceChart.git
   git push -u origin main
   ```

2. **Utwórz konto na Render:**
   - Przejdź na https://render.com
   - Zaloguj się przez GitHub

3. **Utwórz Web Service:**
   - Kliknij "New +" → "Web Service"
   - Połącz z repozytorium GitHub
   - Ustawienia:
     - **Name:** `metin2-price-chart`
     - **Environment:** `Python 3`
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `python main.py`
     - **Plan:** Free

4. **Konfiguracja zmiennych środowiskowych (opcjonalnie):**
   - W ustawieniach Web Service dodaj:
     - `PORT=5001` (Render automatycznie ustawia PORT, ale możemy to nadpisać)

**Uwaga:** Background worker działa automatycznie w tle w tym samym procesie co web service (w osobnym wątku). Nie potrzebujesz osobnego worker service - wszystko działa w jednym web service!

**Alternatywnie - użyj render.yaml:**
- Render automatycznie wykryje plik `render.yaml` i utworzy web service z workerem w tle

### 2. Railway

**Kroki:**

1. **Utwórz konto na Railway:**
   - https://railway.app
   - Zaloguj się przez GitHub

2. **Nowy projekt:**
   - "New Project" → "Deploy from GitHub repo"
   - Wybierz repozytorium

3. **Konfiguracja:**
   - Railway automatycznie wykryje Python
   - Doda zmienną środowiskową `PORT`
   - Uruchomi `main.py`
   - Background worker działa w tym samym procesie co web (w `main.py`), nie dodawaj osobnego worker service.

### 3. Heroku (Płatne)

**Kroki:**

1. **Zainstaluj Heroku CLI:**
   ```bash
   # Windows
   winget install Heroku.HerokuCLI
   ```

2. **Zaloguj się:**
   ```bash
   heroku login
   ```

3. **Utwórz aplikację:**
   ```bash
   heroku create metin2-price-chart
   ```

4. **Deploy:**
   ```bash
   git push heroku main
   ```

5. **Uruchom worker:**
   ```bash
   heroku ps:scale worker=1
   ```

## Ważne uwagi

### Pobieranie danych
Dane są pobierane **wyłącznie przez HTTP** (API metin2alerts.com). Nie jest potrzebna przeglądarka ani Chrome.

### Baza danych
- SQLite działa lokalnie, ale w chmurze lepiej użyć PostgreSQL
- Render oferuje darmowy PostgreSQL
- Railway oferuje darmowy PostgreSQL

### Port
- Render/Heroku automatycznie ustawiają zmienną `PORT`
- Kod już to obsługuje przez `os.environ.get('PORT', 5001)`

## Testowanie lokalnie

Przed deploymentem przetestuj:
```bash
# Ustaw zmienną PORT (symulacja chmury)
set PORT=8080  # Windows
export PORT=8080  # Linux/Mac

python main.py
```

## Troubleshooting

**Problem: Baza danych nie działa**
- SQLite może mieć problemy z zapisem w chmurze
- Rozważ migrację na PostgreSQL

**Problem: Worker nie działa**
- Sprawdź czy worker service jest uruchomiony
- Sprawdź logi w Render/Railway
