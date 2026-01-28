"""
Moduł do zarządzania wykresami cen ulepszaczy
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    
    def _normalize_price_to_won(self, price: float, currency: str) -> float:
        """Normalizuje cenę do won"""
        if currency == 'yang':
            return self.yang_to_won(price)
        elif currency == 'won':
            return price
        else:
            return price  # Fallback
    
    @property
    def price_history(self) -> List[Dict]:
        """Kompatybilność wsteczna - zwraca historię z bazy danych"""
        if self._price_history_cache is None:
            self._price_history_cache = self.db.get_all_history()
        return self._price_history_cache
    
    def add_price_data(self, items: List[Dict]):
        """
        Dodaje nowe dane cenowe do bazy danych
        
        Args:
            items: Lista przedmiotów z danymi cenowymi
        """
        self.db.add_price_data(items)
        # Czyścimy cache aby następne odwołanie pobrało świeże dane
        self._price_history_cache = None
    
    def _parse_price(self, price_str: str) -> Optional[float]:
        """Parsuje cenę z stringa"""
        try:
            # Usuwamy przecinki i spacje
            cleaned = price_str.replace(',', '').replace('.', '').replace(' ', '').strip()
            if cleaned.isdigit():
                return float(cleaned)
        except:
            pass
        return None
    
    def create_chart(self, item_name: Optional[str] = None, 
                    output_file: str = "price_chart.html") -> str:
        """
        Tworzy wykres cen
        
        Args:
            item_name: Nazwa przedmiotu (None = wszystkie przedmioty)
            output_file: Nazwa pliku wyjściowego
        
        Returns:
            Ścieżka do wygenerowanego pliku
        """
        if not self.price_history:
            logger.warning("Brak danych do wyświetlenia")
            return None
        
        # Filtrujemy dane jeśli podano nazwę przedmiotu
        filtered_data = self.price_history
        if item_name:
            filtered_data = [
                entry for entry in self.price_history 
                if item_name.lower() in entry.get('item_name', '').lower()
            ]
        
        if not filtered_data:
            logger.warning(f"Brak danych dla przedmiotu: {item_name}")
            return None
        
        # Tworzymy DataFrame
        df = pd.DataFrame(filtered_data)
        df['datetime'] = pd.to_datetime(df['timestamp'])
        
        # Grupujemy po przedmiocie i walucie
        fig = make_subplots(
            rows=1, cols=1,
            subplot_titles=('Historia Cen Ulepszaczy',),
            specs=[[{"secondary_y": False}]]
        )
        
        # Rysujemy wykresy dla każdego przedmiotu
        items = df['item_name'].unique()
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
        
        for idx, item in enumerate(items):
            item_data = df[df['item_name'] == item].sort_values('datetime')
            
            # Dzielimy na yang i won
            for currency in ['yang', 'won']:
                currency_data = item_data[item_data['currency'] == currency]
                if not currency_data.empty:
                    color = colors[idx % len(colors)]
                    line_style = '-' if currency == 'yang' else '--'
                    
                    fig.add_trace(
                        go.Scatter(
                            x=currency_data['datetime'],
                            y=currency_data['price'],
                            mode='lines+markers',
                            name=f"{item} ({currency})",
                            line=dict(color=color, dash=line_style),
                            marker=dict(size=4)
                        ),
                        row=1, col=1
                    )
        
        # Aktualizujemy layout
        fig.update_layout(
            title={
                'text': 'Historia Cen Ulepszaczy Metin2',
                'x': 0.5,
                'xanchor': 'center'
            },
            xaxis_title='Data',
            yaxis_title='Cena',
            hovermode='x unified',
            height=600,
            template='plotly_white',
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.01
            )
        )
        
        # Zapisujemy wykres
        fig.write_html(output_file)
        logger.info(f"Wykres zapisany do: {output_file}")
        
        return output_file
    
    def get_statistics(self) -> Dict:
        """Zwraca statystyki cen (wszystkie ceny znormalizowane do won)"""
        return self.db.get_statistics()
    
    def get_item_price_stats(self, item_name: str, price_type: str = 'min') -> Optional[float]:
        """
        Zwraca statystykę ceny dla konkretnego przedmiotu
        
        Args:
            item_name: Nazwa przedmiotu
            price_type: 'min', 'max', lub 'avg'
        
        Returns:
            Cena w won lub None
        """
        stats = self.get_statistics()
        if item_name not in stats:
            return None
        
        item_stats = stats[item_name]
        if price_type == 'min':
            return item_stats['min_price']
        elif price_type == 'max':
            return item_stats['max_price']
        elif price_type == 'avg':
            return item_stats['avg_price']
        else:
            return item_stats['min_price']  # Domyślnie min
