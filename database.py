"""
Moduł do zarządzania bazą danych SQLite dla historii cen
"""
import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional
import os
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    """Klasa do zarządzania bazą danych SQLite"""
    
    def __init__(self, db_path: str = None):
        # Używamy zmiennej środowiskowej lub domyślnej ścieżki
        if db_path is None:
            db_path = os.environ.get('DATABASE_PATH', 'price_history.db')
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Inicjalizuje bazę danych i tworzy tabele jeśli nie istnieją"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Stara tabela (dla kompatybilności wstecznej)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    price REAL NOT NULL,
                    price_in_won REAL NOT NULL,
                    currency TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    seller TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # NOWA STRUKTURA: Tabela snapshotów (odczyty z API)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(server_id, timestamp)
                )
            """)
            
            # NOWA STRUKTURA: Tabela ofert powiązanych z snapshotami
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS offers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    server_id INTEGER NOT NULL,
                    item_name TEXT NOT NULL,
                    price REAL NOT NULL,
                    price_in_won REAL NOT NULL,
                    currency TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    seller TEXT NOT NULL,
                    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
                )
            """)
            
            # Indeksy dla starej tabeli (kompatybilność wsteczna)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_item_name ON price_history(item_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON price_history(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_item_timestamp ON price_history(item_name, timestamp)
            """)
            
            # Indeksy dla nowej struktury (optymalizacja wydajności)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_server_timestamp ON snapshots(server_id, timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_offers_snapshot_id ON offers(snapshot_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_offers_server_id ON offers(server_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_offers_item_name ON offers(item_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_offers_snapshot_item ON offers(snapshot_id, item_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_offers_server_item ON offers(server_id, item_name)
            """)
            # Indeks dla szybkiego wyszukiwania po item_name i price_in_won
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_offers_item_price ON offers(item_name, price_in_won)
            """)
            # Indeks dla timestamp + item_name (dla szybkiego filtrowania)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_offers_snapshot_item_price ON offers(snapshot_id, item_name, price_in_won)
            """)
            
            conn.commit()
            logger.info(f"Baza danych zainicjalizowana: {self.db_path}")
            
            # Migrujemy strukturę jeśli brakuje kolumny server_id
            self._migrate_schema_if_needed(conn)
            
            # Sprawdzamy czy trzeba zmigrować dane ze starej struktury
            self._migrate_old_data_if_needed(conn)
    
    def _migrate_schema_if_needed(self, conn):
        """Migruje schemat bazy danych jeśli brakuje kolumny server_id"""
        cursor = conn.cursor()
        
        # Sprawdzamy czy kolumna server_id istnieje w tabeli snapshots
        cursor.execute("PRAGMA table_info(snapshots)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'server_id' not in columns:
            logger.info("Migracja schematu: dodawanie kolumny server_id do snapshots...")
            try:
                # Dodajemy kolumnę server_id z domyślną wartością 426
                cursor.execute("ALTER TABLE snapshots ADD COLUMN server_id INTEGER NOT NULL DEFAULT 426")
                # Usuwamy stary UNIQUE constraint i dodajemy nowy z server_id
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_server_timestamp_new ON snapshots(server_id, timestamp)")
                conn.commit()
                logger.info("Migracja schematu zakończona")
            except Exception as e:
                logger.warning(f"Błąd migracji schematu snapshots: {e}")
        
        # Sprawdzamy czy kolumna server_id istnieje w tabeli offers
        cursor.execute("PRAGMA table_info(offers)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'server_id' not in columns:
            logger.info("Migracja schematu: dodawanie kolumny server_id do offers...")
            try:
                # Dodajemy kolumnę server_id z domyślną wartością 426
                cursor.execute("ALTER TABLE offers ADD COLUMN server_id INTEGER NOT NULL DEFAULT 426")
                conn.commit()
                logger.info("Migracja schematu offers zakończona")
            except Exception as e:
                logger.warning(f"Błąd migracji schematu offers: {e}")
    
    def _migrate_old_data_if_needed(self, conn):
        """Migruje dane ze starej tabeli price_history do nowej struktury snapshotów"""
        cursor = conn.cursor()
        
        # Sprawdzamy czy są dane w starej tabeli
        cursor.execute("SELECT COUNT(*) as count FROM price_history")
        old_count = cursor.fetchone()['count']
        
        if old_count == 0:
            return  # Brak danych do migracji
        
        # Sprawdzamy czy są już dane w nowej strukturze
        cursor.execute("SELECT COUNT(*) as count FROM snapshots")
        new_count = cursor.fetchone()['count']
        
        if new_count > 0:
            logger.info("Nowa struktura już zawiera dane, pomijanie migracji")
            return
        
        logger.info(f"Rozpoczynanie migracji {old_count} wpisów ze starej struktury do nowej...")
        
        # Grupujemy dane po timestamp (snapshot)
        cursor.execute("""
            SELECT DISTINCT timestamp FROM price_history ORDER BY timestamp
        """)
        timestamps = [row['timestamp'] for row in cursor.fetchall()]
        
        # Domyślny server_id dla starych danych (426 - [RUBY] Charon)
        default_server_id = 426
        
        migrated = 0
        for timestamp in timestamps:
            # Tworzymy snapshot z domyślnym server_id
            cursor.execute("""
                INSERT OR IGNORE INTO snapshots (server_id, timestamp) VALUES (?, ?)
            """, (default_server_id, timestamp))
            snapshot_id = cursor.lastrowid
            
            # Jeśli snapshot już istniał, pobieramy jego ID
            if snapshot_id == 0:
                cursor.execute("SELECT id FROM snapshots WHERE server_id = ? AND timestamp = ?", (default_server_id, timestamp))
                result = cursor.fetchone()
                if result:
                    snapshot_id = result['id']
                else:
                    continue
            
            # Migrujemy oferty dla tego snapshot z domyślnym server_id
            cursor.execute("""
                INSERT INTO offers (snapshot_id, server_id, item_name, price, price_in_won, currency, quantity, seller)
                SELECT ?, ?, item_name, price, price_in_won, currency, quantity, seller
                FROM price_history
                WHERE timestamp = ? AND price_in_won > 0
            """, (snapshot_id, default_server_id, timestamp))
            
            migrated += cursor.rowcount
        
        conn.commit()
        logger.info(f"Zmigrowano {migrated} ofert do nowej struktury ({len(timestamps)} snapshotów)")
    
    @contextmanager
    def _get_connection(self):
        """Context manager dla połączenia z bazą danych"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Umożliwia dostęp przez nazwy kolumn
        try:
            yield conn
        finally:
            conn.close()
    
    def add_price_data(self, items: List[Dict], server_id: int):
        """
        Dodaje nowe dane cenowe do bazy danych używając struktury snapshotów
        
        Args:
            items: Lista przedmiotów z danymi cenowymi
            server_id: ID serwera (np. 426, 702)
        """
        timestamp = datetime.now().isoformat()
        added_count = 0
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Tworzymy snapshot (lub pobieramy istniejący jeśli już jest dla tego serwera)
            cursor.execute("""
                INSERT OR IGNORE INTO snapshots (server_id, timestamp) VALUES (?, ?)
            """, (server_id, timestamp))
            snapshot_id = cursor.lastrowid
            
            # Jeśli snapshot już istniał, pobieramy jego ID
            if snapshot_id == 0:
                cursor.execute("SELECT id FROM snapshots WHERE server_id = ? AND timestamp = ?", (server_id, timestamp))
                result = cursor.fetchone()
                if result:
                    snapshot_id = result['id']
                else:
                    logger.error("Nie udało się utworzyć/pobrać snapshot")
                    return
            
            # Dodajemy oferty do tego snapshot
            for item in items:
                # Próbujemy wyciągnąć cenę (yang lub won)
                price = None
                currency = None
                
                yang = item.get('yang', '').replace(',', '').replace('.', '').strip()
                won = item.get('won', '').replace(',', '').replace('.', '').strip()
                
                # Priorytet: won, potem yang
                if won and won.isdigit() and int(won) > 0:
                    price = int(won)
                    currency = 'won'
                elif yang and yang.isdigit() and int(yang) > 0:
                    price = int(yang)
                    currency = 'yang'
                
                if price is not None and price > 0:
                    # Normalizujemy cenę do won (1 won = 100000000 yang)
                    YANG_TO_WON = 100000000
                    price_in_won = (price / YANG_TO_WON) if currency == 'yang' else price
                    
                    # Dodajemy do nowej struktury (offers)
                    cursor.execute("""
                        INSERT INTO offers 
                        (snapshot_id, server_id, item_name, price, price_in_won, currency, quantity, seller)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        snapshot_id,
                        server_id,
                        item.get('name', 'Unknown'),
                        price,
                        price_in_won,
                        currency,
                        item.get('quantity', ''),
                        item.get('seller', '')
                    ))
                    added_count += 1
                    
                    # Dla kompatybilności wstecznej - również do starej tabeli
                    cursor.execute("""
                        INSERT INTO price_history 
                        (timestamp, item_name, price, price_in_won, currency, quantity, seller)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        timestamp,
                        item.get('name', 'Unknown'),
                        price,
                        price_in_won,
                        currency,
                        item.get('quantity', ''),
                        item.get('seller', '')
                    ))
            
            conn.commit()
        
        logger.info(f"Dodano {added_count} ofert do snapshotu {timestamp}")
    
    def get_all_history(self) -> List[Dict]:
        """Zwraca całą historię cen"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, item_name, price, price_in_won, currency, quantity, seller
                FROM price_history
                ORDER BY timestamp ASC
            """)
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_item_history(self, item_name: str, server_id: int, limit: Optional[int] = None, days: Optional[int] = None) -> List[Dict]:
        """
        Zwraca historię cen dla konkretnego przedmiotu używając zoptymalizowanej struktury snapshotów
        
        Args:
            item_name: Nazwa przedmiotu (dokładne dopasowanie - szybsze niż LIKE)
            server_id: ID serwera (np. 426, 702)
            limit: Maksymalna liczba wpisów do zwrócenia (None = wszystkie)
            days: Liczba ostatnich dni do pobrania (None = wszystkie)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # OPTYMALIZACJA: Używamy dokładnego dopasowania zamiast LIKE dla lepszej wydajności
            # Najpierw próbujemy dokładnego dopasowania
            exact_match = item_name.strip()
            
            # OPTYMALIZACJA: Pobieramy tylko unikalne snapshots dla danego przedmiotu i serwera
            # Używamy dokładnego dopasowania (szybsze niż LIKE)
            snapshot_query = """
                SELECT DISTINCT s.timestamp, s.id
                FROM snapshots s
                INNER JOIN offers o ON s.id = o.snapshot_id
                WHERE o.item_name = ?
                AND o.server_id = ?
                AND o.price_in_won > 0
            """
            snapshot_params = [exact_match, server_id]
            
            # Dodajemy filtr daty jeśli podano
            if days:
                from datetime import datetime, timedelta
                cutoff_date = datetime.now() - timedelta(days=days)
                cutoff_timestamp = cutoff_date.isoformat()
                snapshot_query += " AND s.timestamp >= ?"
                snapshot_params.append(cutoff_timestamp)
            
            snapshot_query += " ORDER BY s.timestamp DESC"
            
            # Dodajemy limit jeśli podano (limitujemy liczbę snapshotów)
            if limit:
                # Limit snapshotów - mniej danych do przetworzenia
                max_snapshots = min(limit // 10, 500) if limit else 500  # ~10 ofert na snapshot
                snapshot_query += " LIMIT ?"
                snapshot_params.append(max_snapshots if max_snapshots > 0 else 500)
            else:
                # Domyślnie limit 500 snapshotów dla wydajności
                snapshot_query += " LIMIT ?"
                snapshot_params.append(500)
            
            cursor.execute(snapshot_query, snapshot_params)
            snapshots = cursor.fetchall()
            
            if not snapshots:
                return []
            
            # Pobieramy oferty tylko dla wybranych snapshotów
            snapshot_ids = [s['id'] for s in snapshots]
            placeholders = ','.join(['?'] * len(snapshot_ids))
            
            query = f"""
                SELECT s.timestamp, o.item_name, o.price, o.price_in_won, o.currency, o.quantity, o.seller
                FROM offers o
                INNER JOIN snapshots s ON o.snapshot_id = s.id
                WHERE o.snapshot_id IN ({placeholders})
                AND o.item_name = ?
                AND o.server_id = ?
                AND o.price_in_won > 0
                ORDER BY s.timestamp ASC, o.id ASC
            """
            params = snapshot_ids + [exact_match, server_id]
            
            # Dodajemy limit na oferty jeśli podano
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            result = [dict(row) for row in rows]
            
            return result
    
    def get_latest_data(self, server_id: int) -> tuple[List[Dict], int]:
        """
        Zwraca najnowsze dane dla wszystkich przedmiotów używając zoptymalizowanej struktury snapshotów
        
        Args:
            server_id: ID serwera (np. 426, 702)
        
        Returns:
            Tuple: (lista najnowszych wpisów po przedmiocie, łączna ilość dostępnych sztuk)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # OPTYMALIZACJA: Pobieramy najnowszy snapshot dla danego serwera
            cursor.execute("SELECT id, timestamp FROM snapshots WHERE server_id = ? ORDER BY timestamp DESC LIMIT 1", (server_id,))
            snapshot_result = cursor.fetchone()
            
            if not snapshot_result:
                return [], 0
            
            snapshot_id = snapshot_result['id']
            latest_timestamp = snapshot_result['timestamp']
            
            # Pobieramy wszystkie oferty z najnowszego snapshot dla danego serwera
            cursor.execute("""
                SELECT s.timestamp, o.item_name, o.price, o.price_in_won, o.currency, o.quantity, o.seller
                FROM offers o
                INNER JOIN snapshots s ON o.snapshot_id = s.id
                WHERE o.snapshot_id = ? AND o.server_id = ? AND o.price_in_won > 0
            """, (snapshot_id, server_id))
            
            latest_offers = [dict(row) for row in cursor.fetchall()]
            
            # Obliczamy łączną ilość dostępnych sztuk
            total_quantity = 0
            
            # Grupujemy oferty po nazwie przedmiotu i obliczamy statystyki (min/max/avg) per sztukę
            offers_by_item = {}
            for offer in latest_offers:
                item_name = offer.get('item_name', 'Unknown')
                if item_name not in offers_by_item:
                    offers_by_item[item_name] = []
                
                # Obliczamy cenę per sztukę
                price_in_won = float(offer.get('price_in_won', 0))
                quantity_str = str(offer.get('quantity', '1')).strip()
                quantity_clean = ''.join(c for c in quantity_str if c.isdigit())
                quantity = int(quantity_clean) if quantity_clean else 1
                if quantity <= 0:
                    quantity = 1
                
                if price_in_won > 0 and quantity > 0:
                    price_per_unit = price_in_won / quantity
                    offers_by_item[item_name].append({
                        'price_per_unit': price_per_unit,
                        'price_in_won': price_in_won,
                        'quantity': quantity,
                        'offer': offer  # Zachowujemy oryginalną ofertę dla innych danych
                    })
                    total_quantity += quantity
            
            # Tworzymy agregowane dane dla każdego przedmiotu (używamy minimalnej ceny per sztukę)
            latest_data = []
            for item_name, offers in offers_by_item.items():
                if not offers:
                    continue
                
                # Obliczamy min/max/avg cen per sztukę
                prices_per_unit = [o['price_per_unit'] for o in offers]
                min_price_per_unit = min(prices_per_unit)
                max_price_per_unit = max(prices_per_unit)
                avg_price_per_unit = sum(prices_per_unit) / len(prices_per_unit)
                
                # Używamy oferty z minimalną ceną per sztukę jako reprezentatywnej
                min_offer = min(offers, key=lambda x: x['price_per_unit'])
                representative_offer = min_offer['offer']
                
                # Tworzymy agregowany wpis używając oferty z minimalną ceną per sztukę
                # price_in_won pozostaje ceną za całą ofertę (dla spójności z resztą kodu)
                latest_data.append({
                    'item_name': item_name,
                    'timestamp': representative_offer.get('timestamp'),
                    'price': representative_offer.get('price'),
                    'price_in_won': representative_offer.get('price_in_won'),  # Cena za całą ofertę
                    'currency': representative_offer.get('currency'),
                    'quantity': representative_offer.get('quantity'),
                    'seller': representative_offer.get('seller'),
                    # Dodatkowe statystyki (opcjonalnie, dla przyszłego użycia)
                    'min_price_per_unit': min_price_per_unit,
                    'max_price_per_unit': max_price_per_unit,
                    'avg_price_per_unit': avg_price_per_unit
                })
            
            latest_data.sort(key=lambda x: x.get('item_name', ''))
            
            return latest_data, total_quantity
    
    def get_unique_items(self, server_id: int) -> List[str]:
        """
        Zwraca listę unikalnych nazw przedmiotów dla danego serwera
        
        Args:
            server_id: ID serwera (np. 426, 702)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT o.item_name
                FROM offers o
                WHERE o.server_id = ?
                AND o.price_in_won > 0
                ORDER BY o.item_name ASC
            """, (server_id,))
            
            return [row['item_name'] for row in cursor.fetchall()]
    
    def search_items(self, query: str, server_id: int) -> List[str]:
        """
        Wyszukuje przedmioty po nazwie dla danego serwera
        
        Args:
            query: Fraza do wyszukania (case-insensitive)
            server_id: ID serwera (np. 426, 702)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT o.item_name
                FROM offers o
                WHERE LOWER(o.item_name) LIKE LOWER(?)
                AND o.server_id = ?
                AND o.price_in_won > 0
                ORDER BY o.item_name ASC
            """, (f'%{query}%', server_id))
            
            return [row['item_name'] for row in cursor.fetchall()]
    
    def get_statistics(self, server_id: int) -> Dict:
        """
        Zwraca statystyki cen dla wszystkich przedmiotów dla danego serwera
        
        Args:
            server_id: ID serwera (np. 426, 702)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Używamy nowej struktury offers zamiast price_history
            cursor.execute("""
                SELECT 
                    o.item_name,
                    MIN(o.price_in_won) as min_price,
                    MAX(o.price_in_won) as max_price,
                    AVG(o.price_in_won) as avg_price,
                    COUNT(*) as data_points
                FROM offers o
                WHERE o.server_id = ?
                AND o.price_in_won > 0
                GROUP BY o.item_name
            """, (server_id,))
            
            stats = {}
            for row in cursor.fetchall():
                # Pobieramy najnowszą cenę dla każdego przedmiotu z najnowszego snapshot
                cursor.execute("""
                    SELECT o.price_in_won
                    FROM offers o
                    INNER JOIN snapshots s ON o.snapshot_id = s.id
                    WHERE o.item_name = ? 
                    AND o.server_id = ?
                    AND o.price_in_won > 0
                    ORDER BY s.timestamp DESC
                    LIMIT 1
                """, (row['item_name'], server_id))
                
                current_row = cursor.fetchone()
                current_price = float(current_row['price_in_won']) if current_row else None
                
                stats[row['item_name']] = {
                    'min_price': float(row['min_price']) if row['min_price'] is not None else 0.0,
                    'max_price': float(row['max_price']) if row['max_price'] is not None else 0.0,
                    'avg_price': float(row['avg_price']) if row['avg_price'] is not None else 0.0,
                    'data_points': row['data_points'],
                    'current_price': current_price
                }
            
            return stats
    
    def get_item_statistics(self, item_name: str, server_id: int, use_full_history: bool = True) -> Optional[Dict]:
        """
        Zwraca statystyki dla konkretnego przedmiotu używając agregacji po stronie bazy danych
        (znacznie szybsze niż pobieranie wszystkich danych)
        
        Args:
            item_name: Nazwa przedmiotu
            server_id: ID serwera (np. 426, 702)
            use_full_history: Jeśli True, używa ostatnich 90 dni dla statystyk
        
        Returns:
            Dict ze statystykami lub None jeśli brak danych
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # OPTYMALIZACJA: Używamy agregacji SQL zamiast pobierania wszystkich danych
            days_filter = 90 if use_full_history else 30
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days_filter)
            cutoff_timestamp = cutoff_date.isoformat()
            
            # WAŻNE: Obliczamy statystyki z CEN PER SZTUKĘ, nie z cen całkowitych
            # Pobieramy wszystkie oferty z ceną per sztukę dla danego serwera
            cursor.execute("""
                SELECT 
                    o.price_in_won,
                    CAST(REPLACE(REPLACE(o.quantity, ',', ''), ' ', '') AS INTEGER) as qty
                FROM offers o
                INNER JOIN snapshots s ON o.snapshot_id = s.id
                WHERE o.item_name = ?
                AND o.server_id = ?
                AND o.price_in_won > 0
                AND s.timestamp >= ?
            """, (item_name, server_id, cutoff_timestamp))
            
            rows = cursor.fetchall()
            
            if not rows:
                return None
            
            # Obliczamy cenę per sztukę dla każdej oferty
            prices_per_unit = []
            total_quantity = 0
            
            for row in rows:
                price_in_won = float(row['price_in_won'])
                quantity = int(row['qty']) if row['qty'] and row['qty'] > 0 else 1
                
                if quantity > 0:
                    price_per_unit = price_in_won / quantity
                    if price_per_unit > 0:
                        prices_per_unit.append(price_per_unit)
                        total_quantity += quantity
            
            if not prices_per_unit:
                return None
            
            # Obliczamy statystyki z cen per sztukę
            sorted_prices = sorted(prices_per_unit)
            n = len(sorted_prices)
            
            # Mediana
            if n % 2 == 0:
                median_price = (sorted_prices[n//2 - 1] + sorted_prices[n//2]) / 2
            else:
                median_price = sorted_prices[n//2]
            
            min_price = float(min(prices_per_unit))
            max_price = float(max(prices_per_unit))
            avg_price = float(sum(prices_per_unit) / len(prices_per_unit))
            
            # Obliczamy ceny za 200 sztuk
            min_price_200 = min_price * 200
            max_price_200 = max_price * 200
            avg_price_200 = avg_price * 200
            median_price_200 = median_price * 200
            
            return {
                'min_price': min_price,
                'max_price': max_price,
                'avg_price': avg_price,
                'median_price': median_price,
                'min_price_200': min_price_200,
                'max_price_200': max_price_200,
                'avg_price_200': avg_price_200,
                'median_price_200': median_price_200,
                'data_points': len(prices_per_unit),
                'total_offers': len(prices_per_unit),
                'total_quantity': total_quantity
            }
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """
        Usuwa stare dane starsze niż określona liczba dni
        
        Args:
            days_to_keep: Liczba dni do zachowania danych
        """
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta
        cutoff_date = cutoff_date - timedelta(days=days_to_keep)
        cutoff_timestamp = cutoff_date.isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM price_history
                WHERE timestamp < ?
            """, (cutoff_timestamp,))
            
            deleted_count = cursor.rowcount
            conn.commit()
        
        logger.info(f"Usunięto {deleted_count} starych wpisów (starszych niż {days_to_keep} dni)")
        return deleted_count
