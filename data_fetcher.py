"""
Moduł do pobierania danych o cenach ulepszaczy z API metin2alerts.com (HTTP, bez przeglądarki).
"""
import requests
import json
import time
import random
import os
from typing import List, Dict, Optional
import logging
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Metin2DataFetcher:
    """Klasa do pobierania danych o cenach ulepszaczy"""
    
    def __init__(self, store_url: str = "https://metin2alerts.com/store/"):
        self.store_url = store_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        # Wyłączamy proxy, jeśli jest skonfigurowane
        self.session.proxies = {
            'http': None,
            'https': None,
        }
        # Cache dla tłumaczeń nazw przedmiotów (vnum -> polska nazwa)
        self._translation_cache: Optional[Dict[str, str]] = None
        
    def _load_translations(self) -> Dict[str, str]:
        """
        Ładuje tłumaczenia nazw przedmiotów z pliku item_names.json
        Cache'uje wyniki, aby uniknąć wielokrotnych pobrań
        
        Returns:
            Dict z mapowaniem vnum (string) -> polska nazwa przedmiotu
        """
        if self._translation_cache is not None:
            return self._translation_cache
        
        translation_url = getattr(config, 'TRANSLATION_URL', None)
        if not translation_url:
            logger.warning("Nie skonfigurowano URL tłumaczeń. Używanie oryginalnych nazw.")
            self._translation_cache = {}
            return {}
        
        try:
            logger.info(f"Ładowanie tłumaczeń z: {translation_url}")
            # Wyłączamy proxy dla tego requestu
            old_proxy = os.environ.get('HTTP_PROXY'), os.environ.get('HTTPS_PROXY')
            try:
                os.environ['HTTP_PROXY'] = ''
                os.environ['HTTPS_PROXY'] = ''
                headers = self.session.headers.copy()
                response = requests.get(translation_url, headers=headers, timeout=15)
            finally:
                if old_proxy[0] is not None:
                    os.environ['HTTP_PROXY'] = old_proxy[0]
                else:
                    os.environ.pop('HTTP_PROXY', None)
                if old_proxy[1] is not None:
                    os.environ['HTTPS_PROXY'] = old_proxy[1]
                else:
                    os.environ.pop('HTTPS_PROXY', None)
            
            if response.status_code == 200:
                translations = response.json()
                if isinstance(translations, dict):
                    self._translation_cache = translations
                    logger.info(f"Załadowano {len(translations)} tłumaczeń")
                    return translations
                else:
                    logger.warning(f"Nieoczekiwany format tłumaczeń: {type(translations)}")
                    self._translation_cache = {}
                    return {}
            else:
                logger.warning(f"Nie udało się pobrać tłumaczeń: status {response.status_code}")
                self._translation_cache = {}
                return {}
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Błąd podczas pobierania tłumaczeń: {e}")
            self._translation_cache = {}
            return {}
        except json.JSONDecodeError as e:
            logger.warning(f"Błąd parsowania JSON tłumaczeń: {e}")
            self._translation_cache = {}
            return {}
        except Exception as e:
            logger.warning(f"Nieoczekiwany błąd podczas ładowania tłumaczeń: {e}")
            self._translation_cache = {}
            return {}
    
    def fetch_data_direct_api(self, server_id: Optional[int] = None) -> Optional[Dict]:
        """
        Pobiera dane bezpośrednio z endpointu API: /public/data/{serverId}.json
        
        Args:
            server_id: ID serwera (np. 426). Jeśli None, próbuje znaleźć domyślny serwer.
        
        Returns:
            Dane JSON z API lub None w przypadku błędu
        """
        try:
            # Jeśli nie podano server_id, próbujemy domyślny (426 z przykładu)
            if server_id is None:
                server_id = 426  # Domyślny serwer z przykładu
            
            # Generujemy parametry cache-busting jak w oryginalnym kodzie JavaScript
            timestamp = int(time.time() * 1000)  # Date.now() w milisekundach
            random_param = random.randint(0, 1000000)  # Math.floor(Math.random() * 1000000)
            
            api_url = f"{self.store_url}public/data/{server_id}.json?v={timestamp}&r={random_param}"
            
            logger.info(f"Pobieranie danych z API: {api_url}")
            # Wyłączamy proxy poprzez zmienne środowiskowe
            old_proxy = os.environ.get('HTTP_PROXY'), os.environ.get('HTTPS_PROXY')
            try:
                os.environ['HTTP_PROXY'] = ''
                os.environ['HTTPS_PROXY'] = ''
                # Używamy requests.get bezpośrednio, aby uniknąć problemów z proxy
                # Kopiujemy headers z session
                headers = self.session.headers.copy()
                response = requests.get(api_url, headers=headers, timeout=15)
            finally:
                # Przywracamy oryginalne wartości proxy
                if old_proxy[0] is not None:
                    os.environ['HTTP_PROXY'] = old_proxy[0]
                else:
                    os.environ.pop('HTTP_PROXY', None)
                if old_proxy[1] is not None:
                    os.environ['HTTPS_PROXY'] = old_proxy[1]
                else:
                    os.environ.pop('HTTPS_PROXY', None)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Pomyślnie pobrano dane z API dla serwera {server_id}")
                # Debug: logujemy strukturę danych
                logger.debug(f"Struktura danych API: typ={type(data)}")
                if isinstance(data, dict):
                    logger.debug(f"Klucze w danych: {list(data.keys())[:10]}")  # Pierwsze 10 kluczy
                    # Sprawdzamy czy są jakieś listy
                    for key, value in data.items():
                        if isinstance(value, list):
                            logger.debug(f"Klucz '{key}' zawiera listę z {len(value)} elementami")
                            if len(value) > 0:
                                logger.debug(f"Przykładowy element z '{key}': {value[0]}")
                elif isinstance(data, list):
                    logger.debug(f"Dane to lista z {len(data)} elementami")
                    if len(data) > 0:
                        logger.debug(f"Przykładowy element: {data[0]}")
                return data
            else:
                logger.warning(f"API zwróciło status {response.status_code} dla serwera {server_id}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Błąd podczas pobierania danych z API: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Błąd parsowania JSON z API: {e}")
            return None
        except Exception as e:
            logger.warning(f"Nieoczekiwany błąd podczas pobierania danych z API: {e}")
            return None
    
    def fetch_data_api(self, server_id: Optional[int] = None) -> Optional[Dict]:
        """
        Próba pobrania danych przez API (jeśli dostępne)
        Najpierw próbuje bezpośredniego endpointu, potem inne możliwe endpointy
        """
        # Najpierw próbujemy bezpośredniego endpointu
        direct_data = self.fetch_data_direct_api(server_id)
        if direct_data:
            return direct_data
        
        # Jeśli bezpośredni endpoint nie działa, próbujemy inne
        try:
            api_endpoints = [
                "https://metin2alerts.com/api/store",
                "https://metin2alerts.com/api/store/items",
                "https://metin2alerts.com/store/api",
            ]
            
            for endpoint in api_endpoints:
                try:
                    response = self.session.get(endpoint, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        logger.info(f"Znaleziono API endpoint: {endpoint}")
                        return data
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"Błąd podczas próby pobrania danych przez API: {e}")
            
        return None
    
    def fetch_upgrade_items(self, server_name: Optional[str] = None, 
                           item_names: Optional[List[str]] = None,
                           server_id: Optional[int] = None) -> List[Dict]:
        """
        Pobiera dane o przedmiotach ze sklepu
        
        Args:
            server_name: Nazwa serwera (nieużywane, zachowane dla kompatybilności API)
            item_names: Lista nazw przedmiotów do filtrowania (opcjonalnie, None = wszystkie przedmioty)
            server_id: ID serwera dla API (np. 426). Jeśli None, używa domyślnego.
        
        Returns:
            Lista słowników z danymi o przedmiotach
        """
        # Najpierw próbujemy bezpośredniego API
        api_data = self.fetch_data_api(server_id)
        if api_data:
            # Debug: logujemy surowe dane przed parsowaniem
            logger.debug(f"Przed parsowaniem - typ danych: {type(api_data)}")
            if isinstance(api_data, dict):
                logger.debug(f"Klucze w api_data: {list(api_data.keys())}")
            items = self._parse_api_data(api_data, item_names)
            if items:
                logger.info(f"Pobrano {len(items)} przedmiotów z API")
                return items
            else:
                logger.warning(f"API zwróciło dane, ale parsowanie zwróciło 0 przedmiotów. Struktura: {type(api_data)}")
                if isinstance(api_data, dict):
                    logger.warning(f"Dostępne klucze: {list(api_data.keys())}")
        
        logger.warning("API nie zwróciło danych. Pobieranie tylko przez HTTP (bez przeglądarki).")
        return []
    
    def _parse_api_data(self, api_data, item_names: Optional[List[str]] = None) -> List[Dict]:
        """
        Parsuje dane z API
        
        Obsługuje różne struktury danych:
        - Lista przedmiotów bezpośrednio
        - Dict z kluczem 'items', 'data', 'products', 'list'
        - Dict z przedmiotami w różnych formatach
        
        Args:
            api_data: Dane z API (dict lub list)
            item_names: Opcjonalna lista nazw do filtrowania (None = wszystkie przedmioty)
        
        Returns:
            Lista słowników z danymi o przedmiotach
        """
        items = []
        
        # Struktura zależy od formatu API
        if isinstance(api_data, list):
            data_list = api_data
        elif isinstance(api_data, dict):
            # Próbujemy różne możliwe klucze
            for key in ['items', 'data', 'products', 'list', 'results']:
                if key in api_data:
                    data_list = api_data[key]
                    break
            else:
                # Jeśli nie ma standardowego klucza, sprawdzamy czy dict zawiera listy
                # lub czy sam dict reprezentuje pojedynczy przedmiot
                if all(isinstance(v, (dict, list)) for v in api_data.values() if v):
                    # Może być dict z wieloma listami - próbujemy pierwszą listę
                    for value in api_data.values():
                        if isinstance(value, list) and len(value) > 0:
                            data_list = value
                            break
                    else:
                        logger.debug(f"Nieznana struktura danych API: {list(api_data.keys())}")
                        return []
                else:
                    # Może być pojedynczy przedmiot jako dict
                    data_list = [api_data]
        else:
            logger.warning(f"Nieoczekiwany typ danych z API: {type(api_data)}")
            return []
        
        if not isinstance(data_list, list):
            logger.warning(f"Oczekiwano listy, otrzymano: {type(data_list)}")
            return []
        
        logger.debug(f"Parsowanie {len(data_list)} przedmiotów z API")
        
        # Debug: sprawdzamy pierwsze kilka przedmiotów
        if len(data_list) > 0:
            logger.debug(f"Przykładowy przedmiot przed parsowaniem: {list(data_list[0].keys())}")
            logger.debug(f"Przykładowa nazwa: '{data_list[0].get('name', 'BRAK')}'")
            if item_names:
                logger.debug(f"Szukane nazwy przedmiotów: {item_names}")
        
        items_before_filter = 0
        items_after_filter = 0
        
        # Ładujemy tłumaczenia raz na początku parsowania
        translations = self._load_translations()
        
        for item in data_list:
            if not isinstance(item, dict):
                logger.debug(f"Pominięto przedmiot niebędący dict: {type(item)}")
                continue
            
            # Pobieramy vnum (ID przedmiotu) do tłumaczenia
            vnum = None
            for key in ['vnum', 'VNum', 'VNUM', 'id', 'item_id', 'itemId']:
                if key in item and item[key] is not None:
                    vnum = item[key]
                    break
            
            # Pobieramy oryginalną nazwę przedmiotu (różne możliwe klucze)
            # Używamy oryginalnej nazwy do filtrowania, potem przetłumaczymy
            original_item_name = (
                item.get('name') or 
                item.get('item_name') or 
                item.get('title') or 
                item.get('item') or
                item.get('itemName') or
                ''
            )
            
            # Filtrujemy po oryginalnych nazwach jeśli podano
            # Używamy bardziej elastycznego dopasowania - sprawdzamy czy któreś słowo kluczowe
            # jest zawarte w nazwie przedmiotu (nie wymagamy dokładnego dopasowania)
            if item_names:
                items_before_filter += 1
                item_name_lower = str(original_item_name).lower()
                # Sprawdzamy czy któreś słowo kluczowe z listy jest w nazwie
                # lub czy nazwa zawiera któreś słowo kluczowe
                matches = False
                for search_name in item_names:
                    search_lower = search_name.lower()
                    # Sprawdzamy dokładne dopasowanie lub częściowe
                    if (search_lower == item_name_lower or 
                        search_lower in item_name_lower or 
                        item_name_lower in search_lower):
                        matches = True
                        break
                    # Sprawdzamy też pojedyncze słowa (np. "Black" w "Black Stone")
                    search_words = search_lower.split()
                    item_words = item_name_lower.split()
                    if any(sw in item_words or any(sw in iw for iw in item_words) for sw in search_words):
                        matches = True
                        break
                
                if not matches:
                    continue
                items_after_filter += 1
            else:
                items_before_filter += 1
                items_after_filter += 1
            
            # Tłumaczymy nazwę na polski używając vnum (po filtrowaniu)
            item_name = original_item_name
            if vnum is not None and translations:
                vnum_str = str(vnum)
                if vnum_str in translations:
                    translated_name = translations[vnum_str]
                    if translated_name:
                        item_name = translated_name
                        logger.debug(f"Przetłumaczono vnum {vnum_str}: '{original_item_name}' -> '{translated_name}'")
                else:
                    logger.debug(f"Brak tłumaczenia dla vnum {vnum_str}, używanie oryginalnej nazwy: '{item_name}'")
            
            # Pobieramy ilość (różne możliwe klucze)
            # Używamy sprawdzenia is not None, bo 0 może być prawidłową wartością
            quantity = None
            for key in ['quantity', 'count', 'qty', 'amount', 'stock']:
                if key in item and item[key] is not None:
                    quantity = item[key]
                    break
            quantity = str(quantity) if quantity is not None else ''
            
            # Pobieramy cenę w Yang (różne możliwe klucze)
            # Uwaga: API używa 'yangPrice' (camelCase)
            # Używamy sprawdzenia is not None, bo 0 jest prawidłową ceną
            yang = None
            for key in ['yangPrice', 'yang', 'price_yang', 'yang_price', 'price']:
                if key in item and item[key] is not None:
                    yang = item[key]
                    break
            yang = str(yang) if yang is not None else ''
            
            # Pobieramy cenę w Won (różne możliwe klucze)
            # Uwaga: API używa 'wonPrice' (camelCase)
            # Używamy sprawdzenia is not None, bo 0 jest prawidłową ceną
            won = None
            for key in ['wonPrice', 'won', 'price_won', 'won_price']:
                if key in item and item[key] is not None:
                    won = item[key]
                    break
            won = str(won) if won is not None else ''
            
            # Pobieramy sprzedawcę (różne możliwe klucze)
            seller = (
                item.get('seller') or 
                item.get('seller_name') or 
                item.get('sellerName') or
                item.get('owner') or
                item.get('player') or
                item.get('player_name') or
                ''
            )
            
            parsed_item = {
                'name': str(item_name) if item_name else '',
                'quantity': str(quantity) if quantity else '',
                'yang': str(yang) if yang else '',
                'won': str(won) if won else '',
                'seller': str(seller) if seller else '',
                'timestamp': time.time()
            }
            
            # Dodajemy tylko jeśli mamy przynajmniej nazwę
            # Uwaga: usuwamy wymaganie ceny, bo niektóre przedmioty mogą mieć 0 jako cenę
            if parsed_item['name']:
                items.append(parsed_item)
            else:
                logger.debug(f"Pominięto przedmiot bez nazwy: {item}")
        
        logger.info(f"Sparsowano {len(items)} przedmiotów z API")
        if item_names:
            logger.debug(f"Filtrowanie: {items_before_filter} przedmiotów przed filtrem, {items_after_filter} po filtrze, {len(items)} ostatecznie sparsowanych")
        return items
    
