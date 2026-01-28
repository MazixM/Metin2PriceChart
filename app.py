"""
Web interface dla aplikacji Metin2 Price Chart
"""
from flask import Flask, render_template, jsonify, request
from chart_manager import ChartManager
import logging
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Zmieniamy poziom logowania Werkzeug na WARNING aby zmniejszyć spam
# Ale nasze własne logowanie POST będzie na poziomie WARNING
logging.getLogger('werkzeug').setLevel(logging.WARNING)

app = Flask(__name__)

# Globalna instancja chart_manager - będzie ustawiona przez main.py
_chart_manager_instance = None

# Cache dla logowania Steam GSI (aby nie logować każdego żądania)
_steam_gsi_logged = False

def get_chart_manager():
    """Zwraca globalną instancję chart_manager"""
    global _chart_manager_instance
    if _chart_manager_instance is None:
        _chart_manager_instance = ChartManager()
    return _chart_manager_instance

def set_chart_manager(manager):
    """Ustawia globalną instancję chart_manager"""
    global _chart_manager_instance
    _chart_manager_instance = manager


@app.route('/', methods=['GET'])
def index():
    """Strona główna z listą przedmiotów"""
    return render_template('index.html')

@app.route('/', methods=['POST', 'PUT', 'DELETE', 'PATCH'])
def index_method_not_allowed():
    """Obsługa nieobsługiwanych metod HTTP - loguje szczegóły żądania aby zobaczyć skąd pochodzi"""
    # Zbieramy szczegóły żądania
    user_agent = request.headers.get('User-Agent', 'Unknown')
    referer = request.headers.get('Referer', 'None')
    origin = request.headers.get('Origin', 'None')
    content_type = request.headers.get('Content-Type', 'None')
    content_length = request.headers.get('Content-Length', '0')
    
    # Próbujemy odczytać body jeśli jest
    try:
        if request.is_json:
            body_preview = str(request.get_json())[:200]
        elif request.data:
            body_preview = request.data[:200].decode('utf-8', errors='ignore')
        else:
            body_preview = 'Empty'
    except Exception as e:
        body_preview = f'Could not read: {str(e)[:100]}'
    
    # Sprawdzamy czy to Steam Game State Integration
    is_steam_gsi = 'Steam' in user_agent or 'Valve' in user_agent
    
    if is_steam_gsi:
        # To Steam GSI z CS:GO - logujemy tylko raz
        global _steam_gsi_logged
        if not _steam_gsi_logged:
            logger.info(
                f"📢 Steam Game State Integration (CS:GO) wykryty!\n"
                f"   CS:GO próbuje wysłać dane o grze na port {request.environ.get('SERVER_PORT', '?')}.\n"
                f"   Aplikacja używa portu z config.WEB_PORT (domyślnie 5001).\n"
                f"   Jeśli chcesz używać Steam GSI, zmień port aplikacji w config.py (WEB_PORT) lub skonfiguruj CS:GO na inny port.\n"
                f"   Te żądania będą ignorowane (405 Method Not Allowed)."
            )
            _steam_gsi_logged = True
    else:
        # Inne żądania POST - logujemy szczegóły
        logger.warning(
            f"⚠️  {request.method} request to '/' from {request.remote_addr}:\n"
            f"   User-Agent: {user_agent}\n"
            f"   Referer: {referer}\n"
            f"   Origin: {origin}\n"
            f"   Content-Type: {content_type}\n"
            f"   Content-Length: {content_length}\n"
            f"   Body preview: {body_preview}"
        )
    
    return jsonify({'error': 'Method not allowed'}), 405


@app.route('/api/items')
def get_items():
    """Zwraca listę wszystkich unikalnych przedmiotów"""
    cm = get_chart_manager()
    items_list = cm.db.get_unique_items()
    return jsonify({'items': items_list})


@app.route('/api/item/<item_name>')
def get_item_history(item_name):
    """Zwraca historię cen dla konkretnego przedmiotu z znormalizowanymi cenami w won oraz statystykami"""
    from urllib.parse import unquote
    cm = get_chart_manager()
    
    # Dekodujemy nazwę przedmiotu z URL
    item_name = unquote(item_name)
    
    # Pobieramy parametry z query string
    limit = request.args.get('limit', type=int)
    days = request.args.get('days', type=int)
    
    # Domyślnie ograniczamy do ostatnich 30 dni lub 5000 wpisów dla wydajności
    if not limit and not days:
        days = 30  # Domyślnie ostatnie 30 dni
    
    # Dla wydajności - maksymalny limit 10000 wpisów
    if limit and limit > 10000:
        limit = 10000
    
    history = cm.db.get_item_history(item_name, limit=limit, days=days)
    
    if not history:
        return jsonify({'history': [], 'message': 'Brak danych'})
    
    # Pobieramy statystyki z bazy danych (używamy ostatnich 90 dni dla statystyk - szybciej)
    stats = cm.db.get_item_statistics(item_name, use_full_history=True)
    total_quantity = stats['total_quantity'] if stats else 0
    
    return jsonify({
        'item_name': item_name,
        'history': history,
        'count': len(history),
        'statistics': stats,
        'total_quantity': total_quantity,
        'limit_applied': limit is not None or days is not None
    })


@app.route('/api/search')
def search_items():
    """Wyszukuje przedmioty po nazwie"""
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'items': []})
    
    cm = get_chart_manager()
    items_list = cm.db.search_items(query)
    return jsonify({'items': items_list})


@app.route('/api/stats')
def get_statistics():
    """Zwraca statystyki dla wszystkich przedmiotów"""
    cm = get_chart_manager()
    stats = cm.get_statistics()
    return jsonify({'statistics': stats})


@app.route('/api/latest')
def get_latest_data():
    """Zwraca najnowsze dane dla wszystkich przedmiotów (bez obliczania statystyk - tylko najnowsze ceny)"""
    cm = get_chart_manager()
    latest_data, total_quantity = cm.db.get_latest_data()
    
    if not latest_data:
        return jsonify({'data': [], 'message': 'Brak danych w historii', 'total_quantity': 0})
    
    # Znajdujemy najnowszy timestamp
    latest_timestamp = latest_data[0].get('timestamp') if latest_data else None
    
    return jsonify({
        'data': latest_data,
        'count': len(latest_data),
        'total_quantity': total_quantity,
        'last_update': latest_timestamp
    })


if __name__ == '__main__':
    import config
    web_port = getattr(config, 'WEB_PORT', 5001)
    logger.info(f"Uruchamianie web interface na http://localhost:{web_port}")
    app.run(debug=True, host='0.0.0.0', port=web_port)
