"""
Web interface dla aplikacji Metin2 Price Chart
"""
import os
import hmac
import hashlib
import subprocess
from flask import Flask, render_template, jsonify, request
from chart_manager import ChartManager
import logging
from datetime import datetime
import json
import config

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


@app.route('/api/servers')
def get_servers():
    """Zwraca listę dostępnych serwerów"""
    return jsonify({'servers': config.AVAILABLE_SERVERS, 'default': config.DEFAULT_SERVER_ID})

@app.route('/api/items')
def get_items():
    """Zwraca listę wszystkich unikalnych przedmiotów dla danego serwera"""
    server_id = request.args.get('server_id', type=int, default=config.DEFAULT_SERVER_ID)
    cm = get_chart_manager()
    items_list = cm.db.get_unique_items(server_id)
    return jsonify({'items': items_list, 'server_id': server_id})


@app.route('/api/item/<item_name>')
def get_item_history(item_name):
    """Zwraca historię cen dla konkretnego przedmiotu z znormalizowanymi cenami w won oraz statystykami"""
    from urllib.parse import unquote
    cm = get_chart_manager()
    
    # Dekodujemy nazwę przedmiotu z URL
    item_name = unquote(item_name)
    
    # Pobieramy parametry z query string
    server_id = request.args.get('server_id', type=int, default=config.DEFAULT_SERVER_ID)
    limit = request.args.get('limit', type=int)
    days = request.args.get('days', type=int)
    
    # Domyślnie ograniczamy do ostatnich 30 dni lub 5000 wpisów dla wydajności
    if not limit and not days:
        days = 30  # Domyślnie ostatnie 30 dni
    
    # Dla wydajności - maksymalny limit 10000 wpisów
    if limit and limit > 10000:
        limit = 10000
    
    history = cm.db.get_item_history(item_name, server_id, limit=limit, days=days)
    
    if not history:
        return jsonify({'history': [], 'message': 'Brak danych', 'server_id': server_id})
    
    # Pobieramy statystyki z bazy danych (używamy ostatnich 90 dni dla statystyk - szybciej)
    stats = cm.db.get_item_statistics(item_name, server_id, use_full_history=True)
    total_quantity = stats['total_quantity'] if stats else 0
    
    return jsonify({
        'item_name': item_name,
        'server_id': server_id,
        'history': history,
        'count': len(history),
        'statistics': stats,
        'total_quantity': total_quantity,
        'limit_applied': limit is not None or days is not None
    })


@app.route('/api/search')
def search_items():
    """Wyszukuje przedmioty po nazwie (zwraca tylko nazwy – szybko). Limit wyników 100."""
    query = request.args.get('q', '').strip()
    server_id = request.args.get('server_id', type=int, default=config.DEFAULT_SERVER_ID)
    limit = request.args.get('limit', type=int, default=100)
    
    if not query:
        return jsonify({'items': [], 'server_id': server_id})
    
    cm = get_chart_manager()
    items_list = cm.db.search_items(query, server_id, limit=min(limit, 200))
    return jsonify({'items': items_list, 'server_id': server_id})


@app.route('/api/stats')
def get_statistics():
    """Zwraca statystyki dla wszystkich przedmiotów dla danego serwera"""
    server_id = request.args.get('server_id', type=int, default=config.DEFAULT_SERVER_ID)
    cm = get_chart_manager()
    stats = cm.get_statistics(server_id)
    return jsonify({'statistics': stats, 'server_id': server_id})


@app.route('/api/latest')
def get_latest_data():
    """
    Zwraca najnowsze ceny (strona lub dla podanych przedmiotów).
    - limit, offset: paginacja (domyślnie limit=10, offset=0).
    - items: lista nazw oddzielonych przecinkiem – tylko te przedmioty (np. wyniki wyszukiwania).
    """
    server_id = request.args.get('server_id', type=int, default=config.DEFAULT_SERVER_ID)
    limit = request.args.get('limit', type=int, default=10)
    offset = request.args.get('offset', type=int, default=0)
    items_param = request.args.get('items', '').strip()
    
    cm = get_chart_manager()
    
    if items_param:
        item_names = [n.strip() for n in items_param.split(',') if n.strip()]
        latest_data, total_quantity = cm.db.get_latest_data_for_items(server_id, item_names)
        total_count = len(latest_data)
    else:
        limit = min(max(1, limit), 100)
        latest_data, total_count, total_quantity = cm.db.get_latest_data_paginated(server_id, limit=limit, offset=offset)
    
    if not latest_data:
        return jsonify({
            'data': [],
            'message': 'Brak danych w historii',
            'total_quantity': 0,
            'total_count': total_count,
            'server_id': server_id,
        })
    
    latest_timestamp = latest_data[0].get('timestamp') if latest_data else None
    return jsonify({
        'data': latest_data,
        'count': len(latest_data),
        'total_count': total_count,
        'total_quantity': total_quantity,
        'last_update': latest_timestamp,
        'server_id': server_id,
        'limit': limit if not items_param else None,
        'offset': offset if not items_param else None,
    })


def _webhook_secret_ok(secret: str) -> bool:
    """Weryfikacja secretu: GitHub X-Hub-Signature-256 albo ?secret= / X-Webhook-Secret."""
    if not secret:
        return False
    # GitHub: Secret w ustawieniach webhooka, podpis w nagłówku (nie w URL)
    sig_header = request.headers.get('X-Hub-Signature-256', '').strip()
    if sig_header and sig_header.startswith('sha256='):
        expected = 'sha256=' + hmac.new(
            secret.encode('utf-8'),
            request.get_data(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(sig_header, expected)
    # Fallback: secret w query lub nagłówku (np. ręczne wywołanie)
    provided = (request.args.get('secret') or request.headers.get('X-Webhook-Secret') or '').strip()
    return hmac.compare_digest(provided, secret)


@app.route('/webhook', methods=['POST', 'GET'])
def webhook_deploy():
    """
    Webhook do automatycznego deployu po pushu (np. z GitHub).
    Secret: w GitHub → Settings → Webhooks → Secret (podpis X-Hub-Signature-256)
    albo w URL: ?secret=... / nagłówek X-Webhook-Secret (fallback).
    """
    secret = os.environ.get('DEPLOY_WEBHOOK_SECRET', '').strip()
    if not secret:
        return jsonify({'error': 'Webhook nie skonfigurowany (brak DEPLOY_WEBHOOK_SECRET)'}), 503
    if not _webhook_secret_ok(secret):
        return jsonify({'error': 'Nieprawidłowy secret'}), 403
    if request.method != 'POST':
        return jsonify({'error': 'Użyj POST'}), 405
    deploy_script = os.environ.get('DEPLOY_SCRIPT', '')
    if not deploy_script or not os.path.isfile(deploy_script):
        # Domyślnie: szukaj deploy.sh w katalogu aplikacji
        app_dir = os.path.dirname(os.path.abspath(__file__))
        deploy_script = os.path.join(app_dir, 'deploy.sh')
    if not os.path.isfile(deploy_script):
        return jsonify({'error': 'Brak skryptu deploy (ustaw DEPLOY_SCRIPT lub dodaj deploy.sh)'}), 503
    try:
        subprocess.Popen(
            ['/bin/bash', deploy_script],
            cwd=os.path.dirname(deploy_script),
            env=os.environ.copy(),
            start_new_session=True,
        )
        logger.info("Webhook: uruchomiono skrypt deploy w tle")
        return jsonify({'ok': True, 'message': 'Deploy uruchomiony'}), 200
    except Exception as e:
        logger.exception("Webhook: błąd uruchomienia deploy")
        return jsonify({'error': str(e)}), 500


@app.route('/api/logs')
def get_logs():
    """
    Podgląd ostatnich linii z pliku logów (gdy ustawiono LOG_FILE).
    Wymaga secret: ?secret=... lub nagłówek X-Log-Secret (ten sam co DEPLOY_WEBHOOK_SECRET lub LOG_SECRET).
    """
    secret = os.environ.get('LOG_SECRET', '').strip() or os.environ.get('DEPLOY_WEBHOOK_SECRET', '').strip()
    if not secret:
        return jsonify({'error': 'Brak konfiguracji (LOG_SECRET lub DEPLOY_WEBHOOK_SECRET)'}), 503
    provided = (request.args.get('secret') or request.headers.get('X-Log-Secret') or '').strip()
    if provided != secret:
        return jsonify({'error': 'Nieprawidłowy secret', 'hint': 'Wartość w URL musi być identyczna jak w systemd (bez spacji). Oczekiwana długość: %d' % len(secret)}), 403
    log_file = os.environ.get('LOG_FILE', '').strip()
    if not log_file or not os.path.isfile(log_file):
        return jsonify({
            'message': 'Brak pliku logów. Ustaw LOG_FILE w systemd albo zobacz: journalctl -u metin2pricechart -n 200',
            'lines': []
        }), 200
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        last = int(request.args.get('lines', 100))
        last = min(max(1, last), 500)
        tail = lines[-last:]
        return jsonify({'lines': tail, 'path': log_file})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    import config
    web_port = getattr(config, 'WEB_PORT', 5001)
    logger.info(f"Uruchamianie web interface na http://localhost:{web_port}")
    app.run(debug=True, host='0.0.0.0', port=web_port)
