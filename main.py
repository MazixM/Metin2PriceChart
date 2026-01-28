"""
Główny plik aplikacji do monitorowania cen ulepszaczy Metin2
Uruchamia background service do aktualizacji danych oraz web interface
"""
import time
import logging
import threading
from datetime import datetime
from data_fetcher import Metin2DataFetcher
from chart_manager import ChartManager
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Wyłączamy logowanie błędów 405 przez Werkzeug (spam w logach)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Globalne instancje współdzielone między wątkami
fetcher = None
chart_manager = None


def data_update_worker():
    """Worker thread do aktualizacji danych w tle"""
    global fetcher, chart_manager
    
    logger.info("Uruchamianie background service do aktualizacji danych")
    
    fetcher = Metin2DataFetcher(config.STORE_URL)
    chart_manager = ChartManager()
    
    # Ustawiamy chart_manager w app.py, jeśli już został zaimportowany
    try:
        from app import set_chart_manager
        set_chart_manager(chart_manager)
        logger.info("Chart manager udostępniony dla web interface")
    except ImportError:
        pass  # app.py jeszcze nie został zaimportowany
    
    iteration = 0
    
    try:
        while True:
            iteration += 1
            logger.info(f"=== Iteracja {iteration} ===")
            logger.info(f"Czas: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            try:
                # Pobieramy wszystkie dane (bez wstępnego filtrowania)
                # Filtrowanie będzie dostępne później w interfejsie użytkownika (po nazwie, sklepie, itp.)
                logger.info("Pobieranie wszystkich danych...")
                items = fetcher.fetch_upgrade_items(
                    server_name=config.DEFAULT_SERVER,
                    item_names=None,  # None = pobierz wszystkie przedmioty
                    server_id=config.DEFAULT_SERVER_ID
                )
                
                if items:
                    logger.info(f"Pobrano {len(items)} przedmiotów")
                    
                    # Dodajemy dane do historii
                    chart_manager.add_price_data(items)
                    
                    # Wyświetlamy statystyki
                    stats = chart_manager.get_statistics()
                    logger.info("Statystyki cen:")
                    for item, stat in stats.items():
                        min_price = stat.get('min_price', 0) or 0
                        max_price = stat.get('max_price', 0) or 0
                        avg_price = stat.get('avg_price', 0) or 0
                        current_price = stat.get('current_price', 0) or 0
                        logger.info(f"  {item}: min={min_price:.0f}, "
                                  f"max={max_price:.0f}, "
                                  f"avg={avg_price:.0f}, "
                                  f"current={current_price:.0f}")
                else:
                    logger.warning("Nie pobrano żadnych danych")
                
            except Exception as e:
                logger.error(f"Błąd podczas pobierania danych: {e}", exc_info=True)
            
            # Czekamy na następną iterację
            logger.info(f"Oczekiwanie {config.REFRESH_INTERVAL} sekund do następnego odświeżenia...")
            time.sleep(config.REFRESH_INTERVAL)
            
    except Exception as e:
        logger.error(f"Krytyczny błąd w worker thread: {e}", exc_info=True)
    finally:
        # Zamykamy połączenia
        if fetcher:
            fetcher._close_selenium()
        logger.info("Background service zakończony")


def main():
    """Główna funkcja aplikacji - uruchamia web interface i background service"""
    logger.info("Uruchamianie aplikacji Metin2 Price Chart")
    
    # Uruchamiamy background service w osobnym wątku
    worker_thread = threading.Thread(target=data_update_worker, daemon=True)
    worker_thread.start()
    
    logger.info("Background service uruchomiony")
    logger.info("Uruchamianie web interface...")
    
    # Czekamy chwilę, aby chart_manager został zainicjalizowany
    time.sleep(2)
    
    # Importujemy i uruchamiamy Flask app
    try:
        from app import app, set_chart_manager
        
        # Ustawiamy globalny chart_manager w app.py
        set_chart_manager(chart_manager)
        
        web_port = getattr(config, 'WEB_PORT', 5001)
        logger.info(f"Web interface dostępny na http://localhost:{web_port}")
        # Uruchamiamy Flask
        app.run(debug=False, host='0.0.0.0', port=web_port, use_reloader=False)
        
    except KeyboardInterrupt:
        logger.info("Zatrzymywanie aplikacji...")
    except Exception as e:
        logger.error(f"Błąd uruchamiania web interface: {e}", exc_info=True)
    finally:
        if fetcher:
            fetcher._close_selenium()
        logger.info("Aplikacja zakończona")


if __name__ == "__main__":
    main()
