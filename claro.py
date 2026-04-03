#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Claro TV+ Stream Proxy v2.0
Login direto via API (sem Playwright) — mais rápido e confiável em VPS
"""

import os, sys, json, time, re, threading, logging, base64, uuid
from datetime import datetime
from urllib.parse import quote, urljoin, urlencode
import requests
from flask import Flask, Response, redirect, request, jsonify, render_template_string, stream_with_context

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger('claro-proxy')

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BASE_URL      = 'https://www.clarotvmais.com.br'
GETCDN_URL    = f'{BASE_URL}/avsclient/playback/getcdn'
KEEPALIVE_URL = f'{BASE_URL}/avsclient/playback/keepalive'
PORT          = int(os.environ.get('CLARO_PORT', '8080'))
HOST          = '0.0.0.0'
SESSION_CACHE = '/tmp/claro_session.json'
STREAM_CACHE_TTL   = 280
KEEPALIVE_INTERVAL = 180
SESSION_MAX_AGE    = 21600

CREDS = {
    'username': os.environ.get('CLARO_USER', '309.420.858-41'),
    'password': os.environ.get('CLARO_PASS', 'Mirian83'),
}

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124.0.0.0 Safari/537.36')

DEVICE_ID = os.environ.get('CLARO_DEVICE_ID', str(uuid.uuid4()))

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
ID_TO_SLUG = {v['id']: k for k, v in CHANNELS.items()}

# ─── ESTADO ───────────────────────────────────────────────────────────────────
_state = {
    'cookies': {},
    'xsrf':    '',
    'valid':   False,
    'last_login':     0.0,
    'last_keepalive': 0.0,
    'last_error':     '',
    'login_attempts': 0,
}
_state_lock   = threading.Lock()
_stream_cache: dict = {}
_sc_lock      = threading.Lock()
_login_lock   = threading.Lock()

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _decode_jwt(token: str) -> dict:
    try:
        p = token.split('.')[1]
        p += '=' * (-len(p) % 4)
        return json.loads(base64.b64decode(p))
    except Exception:
        return {}


def _xsrf_from_cookies(cookies: dict) -> str:
    avs = cookies.get('avs_cookie', '')
    if avs:
        x = _decode_jwt(avs).get('xsrfToken', '')
        if x:
            return x
    return ''


def _headers(referer: str = '') -> dict:
    with _state_lock:
        xsrf = _state['xsrf']
    h = {
        'User-Agent':      UA,
        'Accept':          'application/json, text/plain, */*',
        'Accept-Language': 'pt-BR,pt;q=0.9',
        'Origin':          BASE_URL,
        'Referer':         referer or f'{BASE_URL}/',
    }
    if xsrf:
        h['x-xsrf-token'] = xsrf
    return h


def _cookies() -> dict:
    with _state_lock:
        return dict(_state['cookies'])


def _merge(r: requests.Response, extra: dict = None):
    with _state_lock:
        for k, v in r.cookies.items():
            _state['cookies'][k] = v
        if extra:
            _state['cookies'].update(extra)
        xsrf = r.headers.get('x-xsrf-token', '')
        if xsrf:
            _state['xsrf'] = xsrf
        avs = _state['cookies'].get('avs_cookie', '')
        if avs:
            x = _decode_jwt(avs).get('xsrfToken', '')
            if x:
                _state['xsrf'] = x


def _save():
    with _state_lock:
        d = {'cookies': _state['cookies'], 'xsrf': _state['xsrf'], 'ts': time.time()}
    try:
        with open(SESSION_CACHE, 'w') as f:
            json.dump(d, f)
    except Exception:
        pass


# ─── LOGIN ────────────────────────────────────────────────────────────────────

def do_login() -> bool:
    with _login_lock:
        with _state_lock:
            _state['login_attempts'] += 1
            att = _state['login_attempts']
        log.info(f"=== LOGIN tentativa #{att} ===")

        # 1) Sessão inicial — coleta cookies de primeiro acesso
        sess = requests.Session()
        sess.headers['User-Agent'] = UA
        try:
            log.info("Visitando home para cookies iniciais...")
            r0 = sess.get(BASE_URL, timeout=20)
            log.debug(f"Home: {r0.status_code}, cookies: {list(r0.cookies.keys())}")
        except Exception as e:
            log.warning(f"Erro visitando home: {e}")

        # xsrf inicial (pode vir do cookie da home)
        init_xsrf = _xsrf_from_cookies(dict(sess.cookies))

        username = CREDS['username']
        password = CREDS['password']

        attempts = [
            # Tentativa A: JSON padrão
            {
                'url': f'{BASE_URL}/avsclient/auth/login',
                'ct':  'application/json',
                'body': json.dumps({
                    'username': username, 'password': password,
                    'deviceId': DEVICE_ID, 'channel': 'PCTV',
                    'type': 'LAPTOP',
                }),
            },
            # Tentativa B: JSON com cpId
            {
                'url': f'{BASE_URL}/avsclient/auth/login',
                'ct':  'application/json',
                'body': json.dumps({
                    'username': username, 'password': password,
                    'deviceId': DEVICE_ID, 'channel': 'PCTV',
                    'deviceType': 'WEB', 'cpId': 10,
                }),
            },
            # Tentativa C: form-urlencoded
            {
                'url': f'{BASE_URL}/avsclient/auth/login',
                'ct':  'application/x-www-form-urlencoded',
                'body': urlencode({'username': username, 'password': password,
                                   'deviceId': DEVICE_ID, 'channel': 'PCTV'}),
            },
            # Tentativa D: endpoint alternativo
            {
                'url': f'{BASE_URL}/avsclient/userauth/login',
                'ct':  'application/json',
                'body': json.dumps({
                    'username': username, 'password': password,
                    'deviceId': DEVICE_ID, 'channel': 'PCTV', 'type': 'LAPTOP',
                }),
            },
        ]

        for i, ep in enumerate(attempts, 1):
            log.info(f"  Tentativa {i}: POST {ep['url']}")
            try:
                h = {
                    'Content-Type':   ep['ct'],
                    'Accept':         'application/json, text/plain, */*',
                    'Accept-Language':'pt-BR,pt;q=0.9',
                    'Origin':         BASE_URL,
                    'Referer':        f'{BASE_URL}/home-landing',
                }
                if init_xsrf:
                    h['x-xsrf-token'] = init_xsrf

                r = sess.post(ep['url'], data=ep['body'], headers=h, timeout=20)
                log.info(f"    status={r.status_code}  body={r.text[:200]}")
                log.debug(f"    resp cookies: {list(r.cookies.keys())}")

                ok = False
                if r.status_code in (200, 201):
                    try:
                        d = r.json()
                        rc = str(d.get('resultCode') or d.get('status') or '').upper()
                        ok = rc in ('OK', 'SUCCESS', 'TRUE') or bool(r.cookies.get('avs_cookie'))
                    except Exception:
                        ok = bool(r.cookies.get('avs_cookie'))

                if ok or sess.cookies.get('avs_cookie'):
                    log.info(f"  ✓ Login OK na tentativa {i}")
                    _merge(r, dict(sess.cookies))
                    with _state_lock:
                        _state['valid']      = True
                        _state['last_login'] = time.time()
                        _state['last_error'] = ''
                    _do_keepalive_internal()
                    _save()
                    log.info("=== LOGIN BEM-SUCEDIDO ===")
                    return True
                else:
                    log.warning(f"    Tentativa {i} falhou.")

            except Exception as e:
                log.error(f"    Exceção tentativa {i}: {e}")

        # 2) Fallback: Playwright
        log.warning("API login falhou em todas as tentativas. Tentando Playwright...")
        if _try_playwright():
            return True

        err = "Todas as tentativas de login falharam"
        with _state_lock:
            _state['valid']      = False
            _state['last_error'] = err
        log.error(f"=== {err} ===")
        return False


def _try_playwright() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("Playwright não disponível.")
        return False
    try:
        with sync_playwright() as pw:
            log.info("Lançando Chromium headless...")
            browser = pw.chromium.launch(headless=True, args=[
                '--no-sandbox', '--disable-setuid-sandbox',
                '--disable-dev-shm-usage', '--disable-gpu', '--single-process',
            ])
            ctx = browser.new_context(user_agent=UA, locale='pt-BR')
            page = ctx.new_page()
            page.goto(f'{BASE_URL}/home-landing', wait_until='domcontentloaded', timeout=40000)
            page.wait_for_timeout(2500)
            for sel in ['.footer-link', 'text=Acesse', 'span:has-text("Acesse")']:
                try:
                    page.click(sel, timeout=3500)
                    break
                except Exception:
                    pass
            page.wait_for_timeout(1500)
            page.fill('#username', CREDS['username'])
            page.fill('#password', CREDS['password'])
            page.click('#submit')
            try:
                page.wait_for_url(f'{BASE_URL}/**', timeout=20000)
            except Exception:
                pass
            cookies_list = ctx.cookies()
            browser.close()

        ck = {c['name']: c['value'] for c in cookies_list}
        log.debug(f"Playwright cookies: {list(ck.keys())}")
        if ck.get('avs_cookie'):
            xsrf = _xsrf_from_cookies(ck)
            with _state_lock:
                _state['cookies']    = ck
                _state['xsrf']       = xsrf
                _state['valid']      = True
                _state['last_login'] = time.time()
                _state['last_error'] = ''
            _save()
            log.info("Playwright login OK.")
            return True
        log.error("Playwright: avs_cookie ausente.")
        return False
    except Exception as e:
        log.error(f"Playwright erro: {e}", exc_info=True)
        return False


def _load_session() -> bool:
    try:
        if not os.path.exists(SESSION_CACHE):
            return False
        with open(SESSION_CACHE) as f:
            d = json.load(f)
        age = time.time() - d.get('ts', 0)
        if age > SESSION_MAX_AGE:
            log.info(f"Cache expirado ({int(age/3600)}h).")
            return False
        ck = d.get('cookies', {})
        if not ck.get('avs_cookie'):
            return False
        with _state_lock:
            _state['cookies']    = ck
            _state['xsrf']       = d.get('xsrf') or _xsrf_from_cookies(ck)
            _state['last_login'] = d.get('ts', 0)
        log.info(f"Sessão carregada do cache ({int(age/60)}min).")
        return True
    except Exception as e:
        log.warning(f"Erro cache: {e}")
        return False


def _do_keepalive_internal() -> bool:
    try:
        r = requests.get(
            f'{KEEPALIVE_URL}?noRefresh=N&channel=PCTV',
            headers=_headers(f'{BASE_URL}/ao-vivo'),
            cookies=_cookies(), timeout=12,
        )
        _merge(r)
        log.debug(f"Keepalive: {r.status_code} {r.text[:80]}")
        if r.status_code == 200:
            try:
                if r.json().get('status') == 'OK':
                    with _state_lock:
                        _state['last_keepalive'] = time.time()
                    return True
            except Exception:
                pass
    except Exception as e:
        log.warning(f"Keepalive erro: {e}")
    return False


def ensure_session() -> bool:
    with _state_lock:
        valid = _state['valid']
        last  = _state['last_login']
    if valid and (time.time() - last < SESSION_MAX_AGE):
        return True
    if _load_session() and _do_keepalive_internal():
        with _state_lock:
            _state['valid'] = True
        return True
    return do_login()


def _keepalive_worker():
    log.info("Thread keepalive iniciada.")
    while True:
        time.sleep(KEEPALIVE_INTERVAL)
        with _state_lock:
            valid = _state['valid']
        if valid:
            if not _do_keepalive_internal():
                with _state_lock:
                    _state['valid'] = False
                do_login()


# ─── CDN URL ──────────────────────────────────────────────────────────────────

def _extract_cdn_url(data: dict) -> str:
    if not isinstance(data, dict):
        return ''
    resp = data.get('response', data)
    for k in ('url', 'streamUrl', 'cdnUrl', 'cdn_url', 'manifestUrl',
               'manifest', 'hls', 'dash', 'mpd', 'stream'):
        v = resp.get(k, '')
        if isinstance(v, str) and v.startswith('http'):
            return v
    cdn = resp.get('cdn')
    if isinstance(cdn, dict):
        for k in ('url', 'manifest', 'streamUrl', 'cdnUrl', 'hls', 'dash'):
            v = cdn.get(k, '')
            if isinstance(v, str) and v.startswith('http'):
                return v
    elif isinstance(cdn, str) and cdn.startswith('http'):
        return cdn
    raw = json.dumps(data)
    for pat in [
        r'https?://[^\s"\'\\]+\.mpd[^\s"\'\\]*',
        r'https?://[^\s"\'\\]+\.m3u8[^\s"\'\\]*',
        r'https?://[^\s"\'\\]+(manifest|stream|live|cdn)[^\s"\'\\]*',
    ]:
        m = re.search(pat, raw)
        if m:
            return m.group(0).rstrip('\\')
    return ''


def get_stream_url(channel_id: str, force: bool = False):
    now = time.time()
    if not force:
        with _sc_lock:
            c = _stream_cache.get(channel_id)
        if c:
            url, ts, raw = c
            if now - ts < STREAM_CACHE_TTL:
                return url, raw

    ensure_session()

    params = {
        'id': channel_id, 'type': 'LIVE', 'player': 'bitmovin',
        'tvChannelId': channel_id, 'location': 'SAO PAULO,SAO PAULO',
        'channel': 'PCTV',
    }
    raw = {}
    try:
        r = requests.get(
            GETCDN_URL, params=params,
            headers=_headers(f'{BASE_URL}/player/{channel_id}/no-ar'),
            cookies=_cookies(), timeout=18,
        )
        _merge(r)
        log.info(f"getcdn canal={channel_id} status={r.status_code}")

        if r.status_code in (401, 403):
            with _state_lock:
                _state['valid'] = False
            do_login()
            r = requests.get(GETCDN_URL, params=params,
                             headers=_headers(f'{BASE_URL}/player/{channel_id}/no-ar'),
                             cookies=_cookies(), timeout=18)
            _merge(r)

        if r.status_code != 200:
            err = f"getcdn {channel_id}: HTTP {r.status_code} — {r.text[:200]}"
            with _state_lock:
                _state['last_error'] = err
            log.error(err)
            return '', {}

        raw = r.json()
        log.debug(f"getcdn resposta: {json.dumps(raw)[:400]}")
        url = _extract_cdn_url(raw)
        if url:
            with _sc_lock:
                _stream_cache[channel_id] = (url, now, raw)
            log.info(f"  CDN URL: {url[:90]}")
            return url, raw
        else:
            err = f"URL não encontrada no JSON do canal {channel_id}: {json.dumps(raw)[:250]}"
            with _state_lock:
                _state['last_error'] = err
            log.error(err)
            return '', raw
    except Exception as e:
        log.error(f"get_stream_url erro: {e}", exc_info=True)
        with _state_lock:
            _state['last_error'] = str(e)
        return '', raw


# ─── FLASK ────────────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.route('/')
def index():
    base = request.host_url.rstrip('/')
    chs = sorted(
        [{'slug': s, 'name': i['name'], 'id': i['id'],
          'url': f'{base}/canal/{s}', 'mpd': f'{base}/proxy/{i["id"]}/stream.mpd'}
         for s, i in CHANNELS.items()],
        key=lambda x: x['name'],
    )
    with _state_lock:
        valid = _state['valid']
        last  = _state['last_login']
        err   = _state['last_error']
    last_fmt = datetime.fromtimestamp(last).strftime('%d/%m/%Y %H:%M') if last else 'nunca'
    return render_template_string(HTML_TEMPLATE,
        channels=chs, total=len(chs),
        sess_valid=valid, last_login=last_fmt, last_error=err)


@app.route('/lista.m3u')
@app.route('/playlist.m3u')
def playlist():
    base = request.host_url.rstrip('/')
    lines = ['#EXTM3U x-tvg-url=""']
    for s, i in sorted(CHANNELS.items(), key=lambda x: x[1]['name']):
        lines.append(f'#EXTINF:-1 tvg-id="{s}" tvg-name="{i["name"]}" group-title="Claro TV+",{i["name"]}')
        lines.append(f'{base}/canal/{s}')
    return Response('\n'.join(lines), mimetype='audio/x-mpegurl',
                    headers={'Content-Disposition': 'attachment; filename=claro.m3u',
                             'Cache-Control': 'no-cache'})


@app.route('/canal/<slug>')
def canal(slug):
    ch = CHANNELS.get(slug)
    if not ch:
        return jsonify({'erro': 'Canal não encontrado'}), 404
    url, _ = get_stream_url(ch['id'])
    if not url:
        url, _ = get_stream_url(ch['id'], force=True)
    if not url:
        return jsonify({'erro': 'Stream indisponível', 'dica': 'Veja /debug'}), 503
    return redirect(url, code=302)


@app.route('/proxy/<channel_id>/stream.mpd')
def proxy_mpd(channel_id):
    if channel_id not in ID_TO_SLUG:
        return 'Canal não encontrado', 404
    url, _ = get_stream_url(channel_id)
    if not url:
        return 'Stream não disponível', 503
    try:
        r = requests.get(url, headers={'User-Agent': UA}, timeout=18)
        if r.status_code != 200:
            return f'CDN erro {r.status_code}', 502
        mpd = _rewrite_mpd(r.text, url.rsplit('/', 1)[0] + '/')
        return Response(mpd, mimetype='application/dash+xml',
                        headers={'Cache-Control': 'no-cache',
                                 'Access-Control-Allow-Origin': '*'})
    except Exception as e:
        return f'Erro: {e}', 502


@app.route('/proxy/seg')
def proxy_seg():
    seg_url = request.args.get('url', '')
    if not seg_url or not seg_url.startswith('http'):
        return 'url inválida', 400
    try:
        hdrs = {'User-Agent': UA}
        rng = request.headers.get('Range')
        if rng:
            hdrs['Range'] = rng
        r = requests.get(seg_url, headers=hdrs, stream=True, timeout=30)
        oh = {'Content-Type': r.headers.get('Content-Type', 'video/mp4'),
              'Cache-Control': 'no-cache', 'Access-Control-Allow-Origin': '*'}
        for h in ('Content-Length', 'Content-Range'):
            if h in r.headers:
                oh[h] = r.headers[h]
        return Response(stream_with_context(r.iter_content(65536)),
                        status=r.status_code, headers=oh)
    except Exception as e:
        return f'Erro: {e}', 502


@app.route('/status')
def status():
    with _state_lock:
        s = {k: v for k, v in _state.items() if k != 'cookies'}
        s['cookies_count']  = len(_state['cookies'])
        s['cookies_keys']   = list(_state['cookies'].keys())
        s['has_avs_cookie'] = bool(_state['cookies'].get('avs_cookie'))
        s['has_xsrf']       = bool(_state['xsrf'])
    s['channels'] = len(CHANNELS)
    for fld, val in [('last_login', s['last_login']),
                     ('last_keepalive', s['last_keepalive'])]:
        s[f'{fld}_fmt'] = datetime.fromtimestamp(val).isoformat() if val else None
    with _sc_lock:
        s['stream_cache_size'] = len(_stream_cache)
    return jsonify(s)


@app.route('/debug')
def debug():
    out = {'ts': datetime.now().isoformat()}
    with _state_lock:
        out['session_valid']  = _state['valid']
        out['cookies_count']  = len(_state['cookies'])
        out['cookies_keys']   = list(_state['cookies'].keys())
        out['has_avs_cookie'] = bool(_state['cookies'].get('avs_cookie'))
        out['xsrf_present']   = bool(_state['xsrf'])
        out['last_error']     = _state['last_error']

    try:
        r = requests.get(f'{KEEPALIVE_URL}?noRefresh=N&channel=PCTV',
                         headers=_headers(), cookies=_cookies(), timeout=12)
        out['keepalive_status'] = r.status_code
        try:
            out['keepalive_body'] = r.json()
        except Exception:
            out['keepalive_body'] = r.text[:200]
    except Exception as e:
        out['keepalive_error'] = str(e)

    params = {'id': '78', 'type': 'LIVE', 'player': 'bitmovin',
              'tvChannelId': '78', 'location': 'SAO PAULO,SAO PAULO', 'channel': 'PCTV'}
    try:
        r = requests.get(GETCDN_URL, params=params,
                         headers=_headers(f'{BASE_URL}/player/78/no-ar'),
                         cookies=_cookies(), timeout=15)
        out['getcdn_status'] = r.status_code
        try:
            out['getcdn_body'] = r.json()
        except Exception:
            out['getcdn_body'] = r.text[:300]
    except Exception as e:
        out['getcdn_error'] = str(e)

    return jsonify(out)


@app.route('/relogin')
def relogin():
    with _state_lock:
        _state['valid'] = False
    with _sc_lock:
        _stream_cache.clear()
    threading.Thread(target=do_login, daemon=True).start()
    return jsonify({'status': 'relogin iniciado — aguarde ~20s e veja /status e /debug'})


@app.route('/cache/clear')
def cache_clear():
    with _sc_lock:
        _stream_cache.clear()
    return jsonify({'status': 'cache limpo'})


@app.route('/canal-debug/<slug>')
def canal_debug(slug):
    ch = CHANNELS.get(slug)
    if not ch:
        return jsonify({'erro': 'Canal não encontrado'}), 404
    url, raw = get_stream_url(ch['id'], force=True)
    return jsonify({'canal': slug, 'id': ch['id'], 'url_extraida': url, 'resposta_cdn': raw})


def _rewrite_mpd(mpd: str, base_cdn: str) -> str:
    server = request.host_url.rstrip('/')
    def to_proxy(u):
        if not u.startswith('http'):
            u = urljoin(base_cdn, u)
        return f'{server}/proxy/seg?url={quote(u, safe="")}'
    mpd = re.sub(r'<BaseURL>\s*(https?://[^<]+?)\s*</BaseURL>',
                 lambda m: f'<BaseURL>{to_proxy(m.group(1).strip())}</BaseURL>', mpd)
    mpd = re.sub(r'(media|initialization)="(https?://[^"]+)"',
                 lambda m: f'{m.group(1)}="{to_proxy(m.group(2))}"', mpd)
    return mpd


# ─── HTML ─────────────────────────────────────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claro TV+ Proxy</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0c0c0c;color:#e8e8e8;min-height:100vh}
header{background:linear-gradient(135deg,#d4272f,#7a0000);padding:16px 24px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
header h1{font-size:1.4rem;font-weight:800}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}
.badge{padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:600}
.b-ok{background:rgba(0,200,80,.2);color:#00e060;border:1px solid rgba(0,200,80,.4)}
.b-err{background:rgba(200,0,0,.2);color:#ff5050;border:1px solid rgba(200,0,0,.4)}
.b-info{background:rgba(255,255,255,.08);color:#aaa;border:1px solid rgba(255,255,255,.12)}
.error-bar{background:#1a0000;border:1px solid #5a0000;color:#ff7070;padding:10px 24px;font-size:.8rem;word-break:break-all}
.toolbar{background:#111;border-bottom:1px solid #1e1e1e;padding:10px 24px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.toolbar input{flex:1;min-width:180px;padding:7px 12px;border-radius:6px;border:1px solid #282828;background:#181818;color:#e8e8e8;font-size:.85rem;outline:none}
.toolbar input:focus{border-color:#d4272f}
.btn{padding:6px 13px;border-radius:6px;font-size:.8rem;text-decoration:none;border:none;cursor:pointer;font-weight:600;white-space:nowrap;transition:.15s}
.btn-red{background:#d4272f;color:#fff}.btn-red:hover{background:#b01e26}
.btn-dark{background:#222;color:#bbb;border:1px solid #2e2e2e}.btn-dark:hover{background:#2e2e2e}
.count{color:#555;font-size:.8rem;margin-left:auto}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px;padding:16px 24px}
.card{background:#141414;border:1px solid #1e1e1e;border-radius:9px;padding:13px;transition:border-color .2s}
.card:hover{border-color:#d4272f}
.card h3{font-size:.88rem;font-weight:700;margin-bottom:9px;display:flex;align-items:center;gap:6px}
.ch-id{font-size:.68rem;background:#1c1c1c;color:#555;padding:1px 5px;border-radius:3px;margin-left:auto;font-family:monospace;font-weight:400}
.row-lbl{font-size:.68rem;color:#4a4a4a;margin:7px 0 3px}
.url-row{display:flex;gap:4px}
.url-row input{flex:1;padding:5px 7px;background:#0c0c0c;border:1px solid #222;border-radius:4px;color:#666;font-size:.7rem;font-family:monospace;cursor:pointer}
.url-row input:focus{outline:none;color:#bbb}
.cp{padding:4px 8px;background:#1e1e1e;border:1px solid #282828;border-radius:4px;color:#999;cursor:pointer;font-size:.7rem;white-space:nowrap;transition:.15s}
.cp:hover{background:#d4272f;color:#fff;border-color:#d4272f}
.debug-lnk{font-size:.64rem;color:#333;text-decoration:none;margin-top:5px;display:block}
.debug-lnk:hover{color:#888}
.hidden{display:none!important}
footer{text-align:center;padding:20px;color:#2a2a2a;font-size:.76rem;border-top:1px solid #181818;margin-top:8px}
</style>
</head>
<body>
<header>
  <div>
    <h1>📺 Claro TV+ Proxy</h1>
    <div style="font-size:.74rem;color:rgba(255,255,255,.5);margin-top:2px">Último login: {{ last_login }}</div>
  </div>
  <div class="badges">
    {% if sess_valid %}<span class="badge b-ok">● Sessão ativa</span>
    {% else %}<span class="badge b-err">● Sessão inativa</span>{% endif %}
    <span class="badge b-info">{{ total }} canais</span>
  </div>
</header>
{% if last_error %}<div class="error-bar">⚠ {{ last_error }}</div>{% endif %}
<div class="toolbar">
  <input type="text" id="search" placeholder="🔍 Pesquisar canal...">
  <a class="btn btn-red" href="/lista.m3u">⬇ M3U</a>
  <a class="btn btn-dark" href="/status" target="_blank">⚙ Status</a>
  <a class="btn btn-dark" href="/debug" target="_blank">🔬 Debug</a>
  <a class="btn btn-dark" href="/relogin" onclick="return confirm('Forçar relogin?')">🔄 Relogin</a>
  <a class="btn btn-dark" href="/cache/clear" onclick="return confirm('Limpar cache?')">🗑 Cache</a>
  <span class="count" id="count">{{ total }} canais</span>
</div>
<div class="grid" id="grid">
{% for ch in channels %}
<div class="card" data-name="{{ ch.name.lower() }}">
  <h3>{{ ch.name }}<span class="ch-id">id={{ ch.id }}</span></h3>
  <div class="row-lbl">🔗 Link fixo (auto-token):</div>
  <div class="url-row">
    <input type="text" value="{{ ch.url }}" readonly onclick="this.select()">
    <button class="cp" onclick="cp('{{ ch.url }}',this)">Copiar</button>
  </div>
  <div class="row-lbl">📡 Proxy MPD:</div>
  <div class="url-row">
    <input type="text" value="{{ ch.mpd }}" readonly onclick="this.select()">
    <button class="cp" onclick="cp('{{ ch.mpd }}',this)">Copiar</button>
  </div>
  <a class="debug-lnk" href="/canal-debug/{{ ch.slug }}" target="_blank">🔬 testar canal</a>
</div>
{% endfor %}
</div>
<footer>Claro TV+ Proxy v2.0 · Links fixos · Auto-refresh de tokens CDN</footer>
<script>
function cp(t,b){navigator.clipboard.writeText(t).then(()=>{const o=b.textContent;b.textContent='✓';b.style.background='#1a5c2a';setTimeout(()=>{b.textContent=o;b.style.background=''},1800);})}
const cards=[...document.querySelectorAll('.card')];
document.getElementById('search').addEventListener('input',function(){
  const q=this.value.toLowerCase();let n=0;
  cards.forEach(c=>{const show=c.dataset.name.includes(q);c.classList.toggle('hidden',!show);if(show)n++;});
  document.getElementById('count').textContent=n+' canais';
});
</script>
</body>
</html>
"""


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("  Claro TV+ Stream Proxy v2.0")
    log.info(f"  Porta   : {PORT}")
    log.info(f"  Canais  : {len(CHANNELS)}")
    log.info(f"  DeviceID: {DEVICE_ID}")
    log.info("=" * 60)
    threading.Thread(target=_keepalive_worker, daemon=True, name='keepalive').start()
    if _load_session() and _do_keepalive_internal():
        with _state_lock:
            _state['valid'] = True
        log.info("Sessão restaurada do cache.")
    else:
        threading.Thread(target=do_login, daemon=True).start()
    log.info(f"Servidor iniciado em http://0.0.0.0:{PORT}")
    app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)


if __name__ == '__main__':
    main()
