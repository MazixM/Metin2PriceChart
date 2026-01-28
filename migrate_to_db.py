"""
Skrypt migracji danych z JSON do bazy danych SQLite
"""
import json
import os
import logging
from database import Database
from chart_manager import ChartManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_json_to_db(json_file: str = "price_history.json", db_path: str = "price_history.db"):
    """
    Migruje dane z pliku JSON do bazy danych SQLite
    
    Args:
        json_file: Ścieżka do pliku JSON z historią cen
        db_path: Ścieżka do pliku bazy danych SQLite
    """
    if not os.path.exists(json_file):
        logger.warning(f"Plik {json_file} nie istnieje. Pomijanie migracji.")
        return
    
    logger.info(f"Rozpoczynanie migracji z {json_file} do {db_path}")
    
    # Wczytujemy dane z JSON
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            price_history = json.load(f)
    except Exception as e:
        logger.error(f"Błąd podczas wczytywania pliku JSON: {e}")
        return
    
    if not price_history:
        logger.info("Plik JSON jest pusty. Brak danych do migracji.")
        return
    
    logger.info(f"Wczytano {len(price_history)} wpisów z pliku JSON")
    
    # Tworzymy instancję bazy danych
    db = Database(db_path)
    
    # Konwertujemy dane z JSON do formatu akceptowanego przez Database.add_price_data
    # Musimy pogrupować dane po timestamp, bo add_price_data oczekuje listy items
    items_by_timestamp = {}
    
    for entry in price_history:
        timestamp = entry.get('timestamp', '')
        if timestamp not in items_by_timestamp:
            items_by_timestamp[timestamp] = []
        
        # Konwertujemy entry z bazy na format item
        item = {
            'name': entry.get('item_name', 'Unknown'),
            'quantity': entry.get('quantity', ''),
            'seller': entry.get('seller', ''),
        }
        
        # Dodajemy cenę w odpowiedniej walucie
        currency = entry.get('currency', 'won')
        price = entry.get('price', 0)
        
        if currency == 'won':
            item['won'] = str(price)
            item['yang'] = ''
        elif currency == 'yang':
            item['yang'] = str(price)
            item['won'] = ''
        else:
            # Fallback - próbujemy odgadnąć z price_in_won
            price_in_won = entry.get('price_in_won', 0)
            if price_in_won > 0:
                item['won'] = str(int(price_in_won))
                item['yang'] = ''
            else:
                continue  # Pomijamy wpisy bez ceny
        
        items_by_timestamp[timestamp].append(item)
    
    # Dodajemy dane do bazy danych
    total_added = 0
    for timestamp, items in items_by_timestamp.items():
        db.add_price_data(items)
        total_added += len(items)
        if total_added % 1000 == 0:
            logger.info(f"Zmigrowano {total_added} wpisów...")
    
    logger.info(f"Migracja zakończona. Dodano {total_added} wpisów do bazy danych.")
    
    # Sprawdzamy czy migracja się powiodła
    db_items_count = len(db.get_all_history())
    logger.info(f"Weryfikacja: baza danych zawiera {db_items_count} wpisów")
    
    if db_items_count == len(price_history):
        logger.info("✓ Migracja zakończona pomyślnie - wszystkie dane zostały zmigrowane")
    else:
        logger.warning(f"⚠ Uwaga: Liczba wpisów się nie zgadza. JSON: {len(price_history)}, DB: {db_items_count}")


if __name__ == "__main__":
    import sys
    
    json_file = sys.argv[1] if len(sys.argv) > 1 else "price_history.json"
    db_path = sys.argv[2] if len(sys.argv) > 2 else "price_history.db"
    
    migrate_json_to_db(json_file, db_path)
