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
                # Pobieramy dane dla wszystkich dostępnych serwerów
                servers = getattr(config, 'AVAILABLE_SERVERS', {config.DEFAULT_SERVER_ID: 'Default'})
                
                for server_id, server_name in servers.items():
                    logger.info(f"Pobieranie danych dla serwera {server_id} ({server_name})...")
                    
                    items = fetcher.fetch_upgrade_items(
                        server_name=None,  # Nie używamy server_name, tylko server_id
                        item_names=None,  # None = pobierz wszystkie przedmioty
                        server_id=server_id
                    )
                    
                    if items:
                        logger.info(f"Pobrano {len(items)} przedmiotów dla serwera {server_id}")
                        
                        # Dodajemy dane do historii z odpowiednim server_id
                        chart_manager.add_price_data(items, server_id)
                    else:
                        logger.warning(f"Nie pobrano żadnych danych dla serwera {server_id}")
                
                # Wyświetlamy statystyki (dla każdego serwera)
                for server_id, server_name in servers.items():
                    stats = chart_manager.get_statistics(server_id)
                    if stats:
                        logger.info(f"Statystyki cen (serwer {server_id} - {server_name}): {len(stats)} przedmiotów")
                        # Pokazujemy tylko pierwsze 3 dla czytelności
                        for item, stat in list(stats.items())[:3]:
                            min_price = stat.get('min_price', 0) or 0
                            max_price = stat.get('max_price', 0) or 0
                            avg_price = stat.get('avg_price', 0) or 0
                            current_price = stat.get('current_price', 0) or 0
                            logger.info(f"  {item}: min={min_price:.0f}, "
                                      f"max={max_price:.0f}, "
                                      f"avg={avg_price:.0f}, "
                                      f"current={current_price:.0f}")
                
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
