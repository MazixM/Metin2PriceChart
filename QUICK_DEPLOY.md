# Szybki Deployment - Metin2 Price Chart

## Render (Zalecane - Najłatwiejsze) ⭐

### Krok 1: GitHub
```bash
git init
git add .
git commit -m "Ready for deployment"
git remote add origin https://github.com/TWOJE_USERNAME/Metin2PriceChart.git
git push -u origin main
```

### Krok 2: Render
1. Przejdź na https://render.com
2. Zaloguj się przez GitHub
3. Kliknij "New +" → "Blueprint"
4. Wybierz repozytorium
5. Render automatycznie wykryje `render.yaml` i utworzy:
   - Web Service (główna aplikacja + background worker w tle)

**Gotowe!** 🎉

Aplikacja będzie dostępna pod adresem: `https://metin2-price-chart.onrender.com`

**Uwaga:** Background worker działa w tym samym procesie co web service (w osobnym wątku), więc nie potrzebujesz osobnego worker service.

---

## Railway (Alternatywa)

1. Przejdź na https://railway.app
2. "New Project" → "Deploy from GitHub repo"
3. Wybierz repozytorium
4. Railway automatycznie wykryje Python i uruchomi aplikację

**Uwaga:** Background worker działa automatycznie w tle w tym samym procesie co web service (nie potrzebujesz osobnego worker service).

---

## Ważne!

### Pobieranie danych
Dane są pobierane wyłącznie przez HTTP (API). Nie jest potrzebna przeglądarka.

### Baza danych
- SQLite działa, ale w chmurze lepiej PostgreSQL
- Render oferuje darmowy PostgreSQL (można dodać później)

### Port
- Render/Railway automatycznie ustawiają `PORT`
- Kod już to obsługuje ✅

---

## Testowanie przed deploymentem

```bash
# Symulacja chmury (Windows)
set PORT=8080
python main.py

# Sprawdź czy działa na http://localhost:8080
```

---

## Troubleshooting

**"Worker nie działa"**
- Sprawdź czy worker service jest uruchomiony w Render
- Sprawdź logi worker service

**"Baza danych nie zapisuje"**
- SQLite może mieć problemy z zapisem w chmurze
- Rozważ PostgreSQL (Render oferuje darmowy)
