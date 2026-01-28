# Deployment Guide - Metin2 Price Chart

## Opcje deploymentu

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

4. **Background Worker:**
   - W ustawieniach projektu dodaj nowy service
   - Start Command: `python -c "from main import data_update_worker; data_update_worker()"`

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

### Selenium w chmurze
Aplikacja używa Selenium, które może wymagać dodatkowej konfiguracji w chmurze:

**Opcja 1: Użyj headless Chrome**
- Render/Railway automatycznie instalują Chrome
- Może wymagać dodatkowych zależności

**Opcja 2: Zastąp Selenium requests**
- Jeśli API nie wymaga JavaScript, użyj `requests` zamiast Selenium
- To znacznie uprości deployment

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

**Problem: Selenium nie działa**
- Sprawdź logi w Render/Railway
- Może wymagać dodatkowych pakietów systemowych
- Rozważ zastąpienie Selenium przez `requests`

**Problem: Baza danych nie działa**
- SQLite może mieć problemy z zapisem w chmurze
- Rozważ migrację na PostgreSQL

**Problem: Worker nie działa**
- Sprawdź czy worker service jest uruchomiony
- Sprawdź logi w Render/Railway
