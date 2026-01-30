"""
Moduł do zarządzania wykresami cen ulepszaczy.
Wykresy są generowane w przeglądarce (Plotly.js); ten moduł obsługuje dane i statystyki.
"""
from datetime import datetime
from typing import List, Dict, Optional
import logging
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChartManager:
    """Klasa do zarządzania wykresami cen"""
    
    # Stała konwersji: 1 won = 100000000 yang
    YANG_TO_WON = 100000000
    
    def __init__(self, db_path: str = "price_history.db"):
        self.db = Database(db_path)
        # Kompatybilność wsteczna - price_history jako property
        self._price_history_cache = None
    
    @staticmethod
    def yang_to_won(yang: float) -> float:
        """Konwertuje yang na won (1 won = 100000000 yang)"""
        return yang / ChartManager.YANG_TO_WON
    
    @staticmethod
    def won_to_yang(won: float) -> int:
        """Konwertuje won na yang"""
        return int(won * ChartManager.YANG_TO_WON)
    
    @property
    def price_history(self) -> List[Dict]:
        """Kompatybilność wsteczna - zwraca historię z bazy danych"""
        if self._price_history_cache is None:
            self._price_history_cache = self.db.get_all_history()
        return self._price_history_cache
    
    def add_price_data(self, items: List[Dict], server_id: int):
        """
        Dodaje nowe dane cenowe do bazy danych
        
        Args:
            items: Lista przedmiotów z danymi cenowymi
            server_id: ID serwera (np. 426, 702)
        """
        self.db.add_price_data(items, server_id)
        # Czyścimy cache aby następne odwołanie pobrało świeże dane
        self._price_history_cache = None
    
    def create_chart(self, item_name: Optional[str] = None,
                    output_file: str = "price_chart.html") -> Optional[str]:
        """
        Zachowana dla kompatybilności. Wykresy są w interfejsie WWW (Plotly.js).
        """
        logger.info("Wykresy dostępne w interfejsie WWW (http://localhost:5001)")
        return None
    
    def get_statistics(self, server_id: int) -> Dict:
        """
        Zwraca statystyki cen (wszystkie ceny znormalizowane do won) dla danego serwera
        
        Args:
            server_id: ID serwera (np. 426, 702)
        """
        return self.db.get_statistics(server_id)
