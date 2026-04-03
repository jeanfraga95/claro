#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claro TV+ Stream Proxy v1.0
Servidor proxy com links fixos e auto-refresh de tokens CDN
Compatível com x86_64 e ARM (Oracle VPS Ubuntu)
"""

import os, sys, json, time, re, threading, logging, base64
from datetime import datetime
from urllib.parse import quote, urljoin, urlparse
import requests
from flask import Flask, Response, redirect, request, jsonify, render_template_string, stream_with_context

# ─── LOGGING ──────────────────────────────────────────────────────────────────
LOG_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(LOG_DIR, 'claro.log')

handlers = [logging.StreamHandler(sys.stdout)]
try:
    handlers.append(logging.FileHandler(LOG_FILE, encoding='utf-8'))
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=handlers
)
log = logging.getLogger('claro-proxy')

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BASE_URL   = 'https://www.clarotvmais.com.br'
GETCDN_URL = f'{BASE_URL}/avsclient/playback/getcdn'
KEEPALIVE_URL = f'{BASE_URL}/avsclient/playback/keepalive'
LOGIN_PAGE = f'{BASE_URL}/home-landing'
PORT       = int(os.environ.get('CLARO_PORT', '8080'))
HOST       = '0.0.0.0'
SESSION_CACHE = '/tmp/claro_session.json'
STREAM_CACHE_TTL = 300          # segundos para cache do CDN URL
KEEPALIVE_INTERVAL = 180        # 3 minutos
SESSION_MAX_AGE = 43200         # 12 horas

CREDS = {
    'username': os.environ.get('CLARO_USER', '309.420.858-41'),
    'password': os.environ.get('CLARO_PASS', 'Mirian83'),
}

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124.0.0.0 Safari/537.36')

# ─── CHANNELS ─────────────────────────────────────────────────────────────────
CHANNELS = {
    'rede-gospel':       {'id': '59',  'name': 'Rede Gospel'},
    'polishop':          {'id': '468', 'name': 'Polishop'},
    'like':              {'id': '183', 'name': 'Like TV'},
    'tv-brasil':         {'id': '61',  'name': 'TV Brasil'},
    'cbi':               {'id': '54',  'name': 'CBI'},
    'futura':            {'id': '95',  'name': 'Canal Futura'},
    'canal-off':         {'id': '96',  'name': 'Canal Off'},
    'getv':              {'id': '466', 'name': 'GETV'},
    'sportv3':           {'id': '32',  'name': 'SporTV 3'},
    'sportv2':           {'id': '31',  'name': 'SporTV 2'},
    'sportv':            {'id': '30',  'name': 'SporTV'},
    'globonews':         {'id': '78',  'name': 'GloboNews'},
    'gnt':               {'id': '97',  'name': 'GNT'},
    'multishow':         {'id': '98',  'name': 'Multishow'},
    'globoplay-novela':  {'id': '99',  'name': 'Globoplay Novela'},
    'modo-viagem':       {'id': '100', 'name': 'Modo Viagem'},
    'travel-food':       {'id': '353', 'name': 'Travel & Food'},
    'bmc-news':          {'id': '321', 'name': 'BMC News'},
    'canal-uol':         {'id': '352', 'name': 'Canal UOL'},
    'e-entertainment':   {'id': '87',  'name': 'E! Entertainment'},
    'f-channel':         {'id': '76',  'name': 'F Channel'},
    'tlc':               {'id': '12',  'name': 'TLC'},
    'arte1':             {'id': '34',  'name': 'Arte 1'},
    'food-network':      {'id': '52',  'name': 'Food Network'},
    'hh-network':        {'id': '8',   'name': 'H&H Network'},
    'curta':             {'id': '19',  'name': 'Curta!'},
    'travel-box-brasil': {'id': '75',  'name': 'Travel Box Brasil'},
    'fish-brasil':       {'id': '40',  'name': 'Fish Brasil'},
    'hgtv':              {'id': '115', 'name': 'HGTV'},
    'sabor-arte':        {'id': '288', 'name': 'Sabor & Arte'},
    'cnbc':              {'id': '339', 'name': 'CNBC'},
    'cnn-money':         {'id': '349', 'name': 'CNN Money'},
    'tbc':               {'id': '335', 'name': 'TBC'},
    'woohoo':            {'id': '48',  'name': 'Woohoo'},
    'nsports':           {'id': '329', 'name': 'NSports'},
    'sportnet':          {'id': '315', 'name': 'SportNet'},
    'xsports':           {'id': '439', 'name': 'XSports'},
    'espn6':             {'id': '50',  'name': 'ESPN 6'},
    'espn':              {'id': '29',  'name': 'ESPN'},
    'espn2':             {'id': '28',  'name': 'ESPN 2'},
    'espn3':             {'id': '39',  'name': 'ESPN 3'},
    'espn4':             {'id': '26',  'name': 'ESPN 4'},
    'espn5':             {'id': '27',  'name': 'ESPN 5'},
    'bandsports':        {'id': '5',   'name': 'BandSports'},
    'band':              {'id': '174', 'name': 'Band'},
    'jp-news':           {'id': '187', 'name': 'JP News'},
    'cnn-brasil':        {'id': '77',  'name': 'CNN Brasil'},
    'band-news':         {'id': '182', 'name': 'Band News'},
    'sbt-news':          {'id': '469', 'name': 'SBT News'},
    'discovery':         {'id': '7',   'name': 'Discovery Channel'},
    'animal-planet':     {'id': '15',  'name': 'Animal Planet'},
    'history':           {'id': '84',  'name': 'History'},
    'discovery-turbo':   {'id': '18',  'name': 'Discovery Turbo'},
    'discovery-science': {'id': '116', 'name': 'Discovery Science'},
    'discovery-theater': {'id': '117', 'name': 'Discovery Theater'},
    'discovery-world':   {'id': '118', 'name': 'Discovery World'},
    'history-h2':        {'id': '85',  'name': 'History H2'},
    'globinho':          {'id': '94',  'name': 'Globinho'},
    'discovery-kids':    {'id': '1',   'name': 'Discovery Kids'},
    'gloob':             {'id': '93',  'name': 'Gloob'},
    'cartoon-network':   {'id': '2',   'name': 'Cartoon Network'},
    'cartoonito':        {'id': '11',  'name': 'Cartoonito'},
    'tv-ratimbum':       {'id': '62',  'name': 'TV Rá Tim Bum'},
    'dun-dun':           {'id': '49',  'name': 'Dun Dun'},
    'bis':               {'id': '101', 'name': 'Bis'},
    'play':              {'id': '56',  'name': 'Play TV'},
    'music-box-brasil':  {'id': '55',  'name': 'Music Box Brasil'},
    'trace-brasil':      {'id': '81',  'name': 'Trace Brasil'},
    'universal-tv':      {'id': '102', 'name': 'Universal TV'},
    'warnerbros-tv':     {'id': '83',  'name': 'Warner Bros. TV'},
    'sony-channel':      {'id': '82',  'name': 'Sony Channel'},
    'axn':               {'id': '79',  'name': 'AXN'},
    'tnt-novelas':       {'id': '299', 'name': 'TNT Novelas'},
    'e-a':               {'id': '86',  'name': 'E&A'},
    'discovery-id':      {'id': '13',  'name': 'Discovery ID'},
    'usa-network':       {'id': '103', 'name': 'USA Network'},
    'lifetime':          {'id': '88',  'name': 'Lifetime'},
    'adult-swim':        {'id': '322', 'name': 'Adult Swim'},
    'tnt-series':        {'id': '20',  'name': 'TNT Series'},
    'amc':               {'id': '33',  'name': 'AMC'},
    'euro-channel':      {'id': '119', 'name': 'Euro Channel'},
    'film-art':          {'id': '51',  'name': 'Film & Art'},
    'canal-brasil':      {'id': '104', 'name': 'Canal Brasil'},
    'tnt':               {'id': '9',   'name': 'TNT'},
    'megapix':           {'id': '105', 'name': 'Megapix'},
    'space':             {'id': '10',  'name': 'Space'},
    'cinemax':           {'id': '178', 'name': 'Cinemax'},
    'primebox-brasil':   {'id': '57',  'name': 'Primebox Brasil'},
    'studio-universal':  {'id': '106', 'name': 'Studio Universal'},
    'tcm':               {'id': '47',  'name': 'TCM'},
    'c3-tv':             {'id': '314', 'name': 'C3 TV'},
    'vale-agricola':     {'id': '338', 'name': 'Vale Agrícola'},
    'gazeta':            {'id': '53',  'name': 'TV Gazeta'},
    'agro':              {'id': '80',  'name': 'Canal Agro'},
    'canal-do-boi':      {'id': '328', 'name': 'Canal do Boi'},
    'cnn-internacional': {'id': '177', 'name': 'CNN Internacional'},
    'bloomberg':         {'id': '35',  'name': 'Bloomberg'},
    'bbc-news':          {'id': '67',  'name': 'BBC News'},
    'rai-italia':        {'id': '58',  'name': 'RAI Italia'},
    'tv5monde':          {'id': '63',  'name': 'TV5 Monde'},
    'tve':               {'id': '176', 'name': 'TVE'},
    'premier-clubes':    {'id': '107', 'name': 'Premiere Clubes'},
    'premier-2':         {'id': '108', 'name': 'Premiere 2'},
    'premier-3':         {'id': '109', 'name': 'Premiere 3'},
    'premier-4':         {'id': '110', 'name': 'Premiere 4'},
    'premier-5':         {'id': '111', 'name': 'Premiere 5'},
    'premier-6':         {'id': '112', 'name': 'Premiere 6'},
    'premier-7':         {'id': '113', 'name': 'Premiere 7'},
}

# reverse map: id -> slug (for proxy route)
ID_TO_SLUG = {v['id']: k for k, v in CHANNELS.items()}

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
_state = {
    'cookies': {},
    'xsrf':    '',
    'valid':   False,
    'last_login': 0.0,
    'last_keepalive': 0.0,
}
_state_lock = threading.Lock()

# CDN URL cache: channel_id -> (url, timestamp)
_stream_cache: dict = {}
_stream_cache_lock = threading.Lock()

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _xsrf_from_avs_cookie(avs_cookie: str) -> str:
    """Extract xsrfToken from avs_cookie JWT payload."""
    try:
        payload_b64 = avs_cookie.split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        return payload.get('xsrfToken', '')
    except Exception:
        return ''


def _build_headers(channel_id: str = '') -> dict:
    with _state_lock:
        xsrf = _state['xsrf']
    headers = {
        'User-Agent': UA,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8',
        'Origin': BASE_URL,
        'Referer': f'{BASE_URL}/player/{channel_id}/no-ar' if channel_id else f'{BASE_URL}/ao-vivo',
    }
    if xsrf:
        headers['x-xsrf-token'] = xsrf
    return headers


def _get_cookies() -> dict:
    with _state_lock:
        return dict(_state['cookies'])


def _update_from_response(r: requests.Response):
    """Merge new cookies and XSRF from a response."""
    with _state_lock:
        for k, v in r.cookies.items():
            _state['cookies'][k] = v
        new_xsrf = r.headers.get('x-xsrf-token', '')
        if new_xsrf:
            _state['xsrf'] = new_xsrf


# ─── LOGIN ────────────────────────────────────────────────────────────────────

def do_login() -> bool:
    """Login using Playwright browser automation."""
    log.info("Iniciando login via Playwright (Chromium headless)...")
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        log.error("Playwright não instalado. Execute: pip install playwright && playwright install chromium")
        return False

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--single-process',
                ]
            )
            ctx = browser.new_context(
                user_agent=UA,
                viewport={'width': 1280, 'height': 720},
                locale='pt-BR',
            )
            page = ctx.new_page()

            log.info("Navegando para página de login...")
            page.goto(LOGIN_PAGE, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(2000)

            # Clica no botão "É cliente Claro? Acesse"
            log.info("Clicando em 'É cliente Claro? Acesse'...")
            try:
                page.click('.footer-link', timeout=8000)
            except PWTimeout:
                # fallback: tenta pelo texto
                page.click('text=Acesse', timeout=8000)
            page.wait_for_timeout(1500)

            # Preenche usuário e senha
            log.info("Preenchendo credenciais...")
            page.fill('#username', CREDS['username'])
            page.wait_for_timeout(300)
            page.fill('#password', CREDS['password'])
            page.wait_for_timeout(300)

            # Submete
            log.info("Submetendo formulário...")
            page.click('#submit')

            # Aguarda redirecionamento
            page.wait_for_url(f'{BASE_URL}/**', timeout=20000)
            page.wait_for_load_state('networkidle', timeout=15000)
            log.info(f"Login bem-sucedido. URL atual: {page.url}")

            cookies_list = ctx.cookies()
            browser.close()

        cookie_dict = {c['name']: c['value'] for c in cookies_list}
        if not cookie_dict.get('avs_cookie'):
            log.error("Login falhou: avs_cookie não encontrado nos cookies.")
            return False

        xsrf = _xsrf_from_avs_cookie(cookie_dict['avs_cookie'])
        with _state_lock:
            _state['cookies']    = cookie_dict
            _state['xsrf']       = xsrf
            _state['valid']      = True
            _state['last_login'] = time.time()

        log.info(f"Sessão obtida: {len(cookie_dict)} cookies, xsrf={'presente' if xsrf else 'ausente'}")
        _save_session(cookie_dict)

        # Força keepalive para renovar tokens
        _do_keepalive()
        return True

    except Exception as e:
        log.error(f"Erro durante login: {e}", exc_info=True)
        return False


def _save_session(cookies: dict):
    try:
        with open(SESSION_CACHE, 'w') as f:
            json.dump({'cookies': cookies, 'ts': time.time()}, f)
        log.debug("Sessão salva em cache.")
    except Exception as e:
        log.warning(f"Não foi possível salvar sessão: {e}")


def _load_session() -> bool:
    try:
        if not os.path.exists(SESSION_CACHE):
            return False
        with open(SESSION_CACHE) as f:
            data = json.load(f)
        age = time.time() - data.get('ts', 0)
        if age > SESSION_MAX_AGE:
            log.info("Sessão em cache expirada.")
            return False
        cookies = data.get('cookies', {})
        if not cookies.get('avs_cookie'):
            return False
        xsrf = _xsrf_from_avs_cookie(cookies['avs_cookie'])
        with _state_lock:
            _state['cookies']    = cookies
            _state['xsrf']       = xsrf
            _state['last_login'] = data.get('ts', 0)
        log.info(f"Sessão carregada do cache ({int(age/60)} min de idade).")
        return _validate_session()
    except Exception as e:
        log.warning(f"Erro ao carregar sessão: {e}")
        return False


def _validate_session() -> bool:
    try:
        r = requests.get(
            f'{KEEPALIVE_URL}?noRefresh=N&channel=PCTV',
            headers=_build_headers(),
            cookies=_get_cookies(),
            timeout=12,
        )
        _update_from_response(r)
        if r.status_code == 200:
            data = r.json()
            if data.get('status') == 'OK':
                with _state_lock:
                    _state['valid'] = True
                    _state['last_keepalive'] = time.time()
                log.info("Sessão validada com sucesso.")
                return True
        log.warning(f"Sessão inválida: {r.status_code} {r.text[:120]}")
    except Exception as e:
        log.warning(f"Erro ao validar sessão: {e}")
    with _state_lock:
        _state['valid'] = False
    return False


def _do_keepalive():
    try:
        r = requests.get(
            f'{KEEPALIVE_URL}?noRefresh=N&channel=PCTV',
            headers=_build_headers(),
            cookies=_get_cookies(),
            timeout=10,
        )
        _update_from_response(r)
        with _state_lock:
            _state['last_keepalive'] = time.time()
        log.debug(f"Keepalive: {r.status_code}")
    except Exception as e:
        log.warning(f"Keepalive falhou: {e}")


def ensure_session() -> bool:
    """Garante sessão válida, faz login se necessário."""
    with _state_lock:
        valid = _state['valid']
        last  = _state['last_login']

    if valid and (time.time() - last < SESSION_MAX_AGE):
        return True

    if _load_session():
        return True

    return do_login()


# ─── CDN STREAM URL ───────────────────────────────────────────────────────────

def _extract_url_from_response(data: dict) -> str:
    """Extrai URL do stream da resposta getcdn."""
    if not isinstance(data, dict):
        return ''

    # Navega em response -> cdn / url / streamUrl etc
    resp = data.get('response', data)

    # Tenta campos diretos
    for key in ('url', 'streamUrl', 'cdnUrl', 'cdn_url', 'manifestUrl', 'manifest'):
        val = resp.get(key, '')
        if val and isinstance(val, str) and val.startswith('http'):
            return val

    # Tenta sub-objeto "cdn"
    cdn = resp.get('cdn')
    if isinstance(cdn, dict):
        for key in ('url', 'manifest', 'streamUrl', 'cdnUrl'):
            val = cdn.get(key, '')
            if val and isinstance(val, str) and val.startswith('http'):
                return val
    elif isinstance(cdn, str) and cdn.startswith('http'):
        return cdn

    # Busca qualquer URL .mpd na string JSON
    raw = json.dumps(data)
    m = re.search(r'https?://[^\s"\'\\]+\.mpd[^\s"\'\\]*', raw)
    if m:
        return m.group(0)

    # Busca qualquer URL de stream
    m = re.search(r'https?://[^\s"\'\\]+(manifest|stream|live)[^\s"\'\\]*', raw)
    if m:
        return m.group(0)

    return ''


def get_stream_url(channel_id: str, force: bool = False) -> str:
    """Retorna URL CDN para o canal, com cache de 5 minutos."""
    now = time.time()

    # Verifica cache
    if not force:
        with _stream_cache_lock:
            cached = _stream_cache.get(channel_id)
        if cached:
            url, ts = cached
            if now - ts < STREAM_CACHE_TTL:
                log.debug(f"Cache hit para canal {channel_id}")
                return url

    ensure_session()

    params = {
        'id':         channel_id,
        'type':       'LIVE',
        'player':     'bitmovin',
        'tvChannelId': channel_id,
        'location':   'SAO PAULO,SAO PAULO',
        'channel':    'PCTV',
    }

    try:
        r = requests.get(
            GETCDN_URL,
            params=params,
            headers=_build_headers(channel_id),
            cookies=_get_cookies(),
            timeout=15,
        )
        _update_from_response(r)
        log.info(f"getcdn canal={channel_id} status={r.status_code}")

        if r.status_code == 401 or r.status_code == 403:
            log.warning("Sessão expirada, fazendo re-login...")
            with _state_lock:
                _state['valid'] = False
            do_login()
            # Tenta novamente
            r = requests.get(
                GETCDN_URL, params=params,
                headers=_build_headers(channel_id),
                cookies=_get_cookies(), timeout=15,
            )
            _update_from_response(r)

        if r.status_code != 200:
            log.error(f"getcdn falhou: {r.status_code} {r.text[:200]}")
            return ''

        data = r.json()
        log.debug(f"getcdn resposta: {json.dumps(data)[:300]}")

        url = _extract_url_from_response(data)
        if url:
            with _stream_cache_lock:
                _stream_cache[channel_id] = (url, now)
            return url
        else:
            log.error(f"URL não encontrada na resposta: {json.dumps(data)[:300]}")
            return ''

    except Exception as e:
        log.error(f"Erro em get_stream_url: {e}", exc_info=True)
        return ''


# ─── BACKGROUND KEEPALIVE ─────────────────────────────────────────────────────

def _keepalive_worker():
    log.info("Thread de keepalive iniciada.")
    while True:
        time.sleep(KEEPALIVE_INTERVAL)
        with _state_lock:
            valid = _state['valid']
        if valid:
            _do_keepalive()


# ─── FLASK APP ────────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.route('/')
def index():
    base = request.host_url.rstrip('/')
    channels_list = sorted(
        [
            {
                'slug': slug,
                'name': info['name'],
                'id':   info['id'],
                'url':  f'{base}/canal/{slug}',
                'mpd':  f'{base}/proxy/{info["id"]}/stream.mpd',
            }
            for slug, info in CHANNELS.items()
        ],
        key=lambda x: x['name']
    )
    with _state_lock:
        sess_valid = _state['valid']
        last_login = _state['last_login']
    return render_template_string(
        HTML_TEMPLATE,
        channels=channels_list,
        total=len(channels_list),
        sess_valid=sess_valid,
        last_login=datetime.fromtimestamp(last_login).strftime('%d/%m/%Y %H:%M') if last_login else 'nunca',
    )


@app.route('/lista.m3u')
@app.route('/playlist.m3u')
def playlist():
    base = request.host_url.rstrip('/')
    lines = ['#EXTM3U x-tvg-url=""']
    for slug, info in sorted(CHANNELS.items(), key=lambda x: x[1]['name']):
        lines.append(
            f'#EXTINF:-1 tvg-id="{slug}" tvg-name="{info["name"]}" '
            f'group-title="Claro TV+",{info["name"]}'
        )
        lines.append(f'{base}/canal/{slug}')
    content = '\n'.join(lines)
    return Response(
        content,
        mimetype='audio/x-mpegurl',
        headers={'Content-Disposition': 'attachment; filename=claro.m3u',
                 'Cache-Control': 'no-cache'}
    )


@app.route('/canal/<slug>')
def canal(slug):
    """Link fixo por nome — redireciona para URL CDN sempre atualizada."""
    ch = CHANNELS.get(slug)
    if not ch:
        return jsonify({
            'erro': 'Canal não encontrado',
            'canais_disponiveis': sorted(CHANNELS.keys())
        }), 404

    url = get_stream_url(ch['id'])
    if not url:
        # Segunda tentativa após re-login
        do_login()
        url = get_stream_url(ch['id'], force=True)

    if not url:
        return jsonify({'erro': 'Stream não disponível no momento', 'canal': slug}), 503

    log.info(f"Redirecionando /canal/{slug} -> {url[:80]}...")
    return redirect(url, code=302)


@app.route('/proxy/<channel_id>/stream.mpd')
def proxy_mpd(channel_id):
    """Proxy do manifesto DASH com URLs de segmento reescritas."""
    if channel_id not in ID_TO_SLUG:
        return 'Canal não encontrado', 404

    url = get_stream_url(channel_id)
    if not url:
        return 'Stream não disponível', 503

    try:
        r = requests.get(url, headers={'User-Agent': UA}, timeout=15)
        if r.status_code != 200:
            return f'CDN retornou {r.status_code}', 502

        mpd = r.text
        base_cdn = url.rsplit('/', 1)[0] + '/'
        mpd = _rewrite_mpd(mpd, base_cdn)

        return Response(
            mpd,
            mimetype='application/dash+xml',
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Access-Control-Allow-Origin': '*',
            }
        )
    except Exception as e:
        log.error(f"Erro proxy MPD: {e}")
        return f'Erro: {e}', 502


@app.route('/proxy/seg')
def proxy_seg():
    """Proxy de segmentos DASH."""
    seg_url = request.args.get('url', '')
    if not seg_url or not seg_url.startswith('http'):
        return 'Parâmetro url inválido', 400

    try:
        headers = {'User-Agent': UA}
        rng = request.headers.get('Range')
        if rng:
            headers['Range'] = rng

        r = requests.get(seg_url, headers=headers, stream=True, timeout=30)

        resp_headers = {
            'Content-Type':  r.headers.get('Content-Type', 'video/mp4'),
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': '*',
        }
        for h in ('Content-Length', 'Content-Range'):
            if h in r.headers:
                resp_headers[h] = r.headers[h]

        return Response(
            stream_with_context(r.iter_content(chunk_size=65536)),
            status=r.status_code,
            headers=resp_headers,
        )
    except Exception as e:
        log.error(f"Erro proxy segmento: {e}")
        return f'Erro: {e}', 502


@app.route('/status')
def status():
    with _state_lock:
        s = dict(_state)
        s.pop('cookies', None)   # não expõe cookies
    s['cookies_count'] = len(_state.get('cookies', {}))
    s['channels'] = len(CHANNELS)
    s['last_login_fmt'] = (
        datetime.fromtimestamp(s['last_login']).isoformat() if s['last_login'] else None
    )
    s['last_keepalive_fmt'] = (
        datetime.fromtimestamp(s['last_keepalive']).isoformat() if s['last_keepalive'] else None
    )
    with _stream_cache_lock:
        s['stream_cache_size'] = len(_stream_cache)
    return jsonify(s)


@app.route('/relogin')
def relogin():
    """Força novo login (útil se sessão expirar)."""
    with _state_lock:
        _state['valid'] = False
    with _stream_cache_lock:
        _stream_cache.clear()
    t = threading.Thread(target=do_login, daemon=True)
    t.start()
    return jsonify({'status': 'relogin iniciado em background'})


@app.route('/cache/clear')
def cache_clear():
    with _stream_cache_lock:
        _stream_cache.clear()
    return jsonify({'status': 'cache limpo'})


# ─── MPD REWRITE ──────────────────────────────────────────────────────────────

def _rewrite_mpd(mpd: str, base_cdn: str) -> str:
    """Reescreve URLs de segmentos no MPD para passar pelo nosso proxy."""
    server = request.host_url.rstrip('/')

    def to_proxy(u: str) -> str:
        if not u.startswith('http'):
            u = urljoin(base_cdn, u)
        return f'{server}/proxy/seg?url={quote(u, safe="")}'

    # Reescreve <BaseURL>
    def repl_base(m):
        u = m.group(1).strip()
        return f'<BaseURL>{to_proxy(u)}</BaseURL>'
    mpd = re.sub(r'<BaseURL>\s*(https?://[^<]+?)\s*</BaseURL>', repl_base, mpd)

    # Reescreve atributos media= e initialization= com URL absoluta
    def repl_attr(m):
        attr, u, rest = m.group(1), m.group(2), m.group(3)
        return f'{attr}="{to_proxy(u)}"{rest}'
    mpd = re.sub(
        r'(media|initialization)="(https?://[^"]+)"([^/>\s]*)',
        repl_attr, mpd
    )
    return mpd


# ─── HTML TEMPLATE ─────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claro TV+ Proxy</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:#0d0d0d;color:#e8e8e8;min-height:100vh}
header{background:linear-gradient(135deg,#d4272f 0%,#7a0000 100%);
       padding:18px 24px;display:flex;align-items:center;gap:16px}
header h1{font-size:1.5rem;font-weight:800;letter-spacing:-.5px}
.badges{display:flex;gap:8px;flex-wrap:wrap}
.badge{padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:600}
.b-ok{background:rgba(0,200,80,.25);color:#00e060;border:1px solid rgba(0,200,80,.4)}
.b-err{background:rgba(200,0,0,.25);color:#ff5050;border:1px solid rgba(200,0,0,.4)}
.b-info{background:rgba(255,255,255,.1);color:#ccc;border:1px solid rgba(255,255,255,.15)}
.toolbar{background:#111;border-bottom:1px solid #1f1f1f;padding:12px 24px;
         display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.toolbar input{flex:1;min-width:200px;padding:8px 14px;border-radius:7px;
               border:1px solid #2a2a2a;background:#1a1a1a;color:#e8e8e8;
               font-size:.88rem;outline:none}
.toolbar input:focus{border-color:#d4272f}
.btn{padding:7px 14px;border-radius:7px;font-size:.82rem;text-decoration:none;
     border:none;cursor:pointer;white-space:nowrap;font-weight:600;transition:.15s}
.btn-red{background:#d4272f;color:#fff}.btn-red:hover{background:#b01e26}
.btn-dark{background:#252525;color:#ccc;border:1px solid #333}
.btn-dark:hover{background:#333}
.count{color:#666;font-size:.82rem;margin-left:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));
      gap:10px;padding:18px 24px}
.card{background:#161616;border:1px solid #212121;border-radius:10px;padding:14px;
      transition:border-color .2s,box-shadow .2s}
.card:hover{border-color:#d4272f;box-shadow:0 0 0 1px #d4272f22}
.card h3{font-size:.9rem;font-weight:700;margin-bottom:10px;
         display:flex;align-items:center;gap:8px}
.ch-id{font-size:.7rem;background:#1e1e1e;color:#555;padding:2px 6px;
       border-radius:4px;margin-left:auto;font-weight:400;font-family:monospace}
.row-lbl{font-size:.7rem;color:#555;margin:8px 0 3px}
.url-row{display:flex;gap:5px}
.url-row input{flex:1;padding:5px 8px;background:#0e0e0e;border:1px solid #252525;
               border-radius:5px;color:#7a7a7a;font-size:.72rem;font-family:monospace;
               cursor:pointer}
.url-row input:focus{outline:none;color:#ccc}
.copy-btn{padding:4px 9px;background:#222;border:1px solid #2a2a2a;
          border-radius:5px;color:#aaa;cursor:pointer;font-size:.72rem;white-space:nowrap;
          transition:.15s}
.copy-btn:hover{background:#d4272f;color:#fff;border-color:#d4272f}
footer{text-align:center;padding:24px;color:#333;font-size:.78rem;
       border-top:1px solid #1a1a1a;margin-top:10px}
.hidden{display:none!important}
</style>
</head>
<body>
<header>
  <div>
    <h1>📺 Claro TV+ Proxy</h1>
    <div style="font-size:.78rem;color:rgba(255,255,255,.6);margin-top:3px">
      Último login: {{ last_login }}
    </div>
  </div>
  <div class="badges" style="margin-left:auto">
    {% if sess_valid %}
    <span class="badge b-ok">● Sessão ativa</span>
    {% else %}
    <span class="badge b-err">● Sessão inativa</span>
    {% endif %}
    <span class="badge b-info">{{ total }} canais</span>
  </div>
</header>

<div class="toolbar">
  <input type="text" id="search" placeholder="🔍 Pesquisar canal...">
  <a class="btn btn-red" href="/lista.m3u">⬇ M3U Playlist</a>
  <a class="btn btn-dark" href="/status" target="_blank">⚙ Status JSON</a>
  <a class="btn btn-dark" href="/relogin" onclick="return confirm('Forçar novo login?')">🔄 Relogin</a>
  <a class="btn btn-dark" href="/cache/clear" onclick="return confirm('Limpar cache?')">🗑 Limpar Cache</a>
  <span class="count" id="count">{{ total }} canais</span>
</div>

<div class="grid" id="grid">
  {% for ch in channels %}
  <div class="card" data-name="{{ ch.name.lower() }}">
    <h3>{{ ch.name }}<span class="ch-id">id={{ ch.id }}</span></h3>
    <div class="row-lbl">🔗 Link fixo (redirect auto-token):</div>
    <div class="url-row">
      <input type="text" value="{{ ch.url }}" readonly onclick="this.select()">
      <button class="copy-btn" onclick="cp('{{ ch.url }}',this)">Copiar</button>
    </div>
    <div class="row-lbl">📡 Proxy MPD (segmentos via proxy):</div>
    <div class="url-row">
      <input type="text" value="{{ ch.mpd }}" readonly onclick="this.select()">
      <button class="copy-btn" onclick="cp('{{ ch.mpd }}',this)">Copiar</button>
    </div>
  </div>
  {% endfor %}
</div>
<footer>Claro TV+ Proxy — Auto-refresh de tokens CDN &nbsp;|&nbsp; Links fixos por canal</footer>

<script>
function cp(t,b){
  navigator.clipboard.writeText(t).then(()=>{
    const o=b.textContent;b.textContent='✓';b.style.background='#1a5c2a';
    setTimeout(()=>{b.textContent=o;b.style.background=''},1800);
  });
}
const cards=[...document.querySelectorAll('.card')];
document.getElementById('search').addEventListener('input',function(){
  const q=this.value.toLowerCase();
  let n=0;
  cards.forEach(c=>{
    const show=c.dataset.name.includes(q);
    c.classList.toggle('hidden',!show);
    if(show)n++;
  });
  document.getElementById('count').textContent=n+' canais';
});
</script>
</body>
</html>
"""


# ─── ENTRYPOINT ───────────────────────────────────────────────────────────────

def main():
    log.info("=" * 62)
    log.info("  Claro TV+ Stream Proxy v1.0")
    log.info(f"  Porta  : {PORT}")
    log.info(f"  Canais : {len(CHANNELS)}")
    log.info("=" * 62)

    # Inicia thread de keepalive
    t = threading.Thread(target=_keepalive_worker, daemon=True, name='keepalive')
    t.start()

    # Inicializa sessão
    log.info("Inicializando sessão...")
    if not _load_session():
        log.info("Sessão em cache inválida ou ausente, fazendo login...")
        if not do_login():
            log.warning("Login inicial falhou — o servidor tentará novamente na primeira requisição.")

    # Sobe Flask
    log.info(f"Servidor iniciado em http://0.0.0.0:{PORT}")
    app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)


if __name__ == '__main__':
    main()
