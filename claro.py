#!/usr/bin/env python3
"""
Claro TV Mais – Stream Proxy
Corrige: avs_browser_id, XSRF via JWT, retry com Playwright fallback
"""

import base64
import json
import logging
import os
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Dict, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import requests

# ─── Configuração ────────────────────────────────────────────────────────────
USERNAME  = os.getenv("CLARO_USER", "SEU_CPF_OU_EMAIL")
PASSWORD  = os.getenv("CLARO_PASS", "SUA_SENHA")
PORT      = int(os.getenv("PROXY_PORT", 8080))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOCATION  = os.getenv("CLARO_LOCATION", "SAO PAULO,SAO PAULO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("claro-proxy")

# ─── URLs ────────────────────────────────────────────────────────────────────
BASE_URL      = "https://www.clarotvmais.com.br"
HOME_URL      = f"{BASE_URL}/home-landing"
LOGIN_URL     = f"{BASE_URL}/avsclient/login"
KEEPALIVE_URL = f"{BASE_URL}/avsclient/keepalive"
GETCDN_URL    = f"{BASE_URL}/avsclient/playback/getcdn"

# ─── Canais ──────────────────────────────────────────────────────────────────
CHANNELS = {
    # Esportes
    "sportv":           {"id": 30,  "channel": "PCTV"},
    "sportv2":          {"id": 31,  "channel": "PCTV"},
    "sportv3":          {"id": 32,  "channel": "PCTV"},
    "espn":             {"id": 29,  "channel": "PCTV"},
    "espn2":            {"id": 28,  "channel": "PCTV"},
    "espn3":            {"id": 39,  "channel": "PCTV"},
    "espn4":            {"id": 26,  "channel": "PCTV"},
    "espn5":            {"id": 27,  "channel": "PCTV"},
    "espn6":            {"id": 50,  "channel": "PCTV"},
    "bandsports":       {"id": 5,   "channel": "PCTV"},
    "nsports":          {"id": 329, "channel": "PCTV"},
    "sportnet":         {"id": 315, "channel": "PCTV"},
    "xsports":          {"id": 439, "channel": "PCTV"},
    "canaloff":         {"id": 96,  "channel": "PCTV"},
    "fishbrasil":       {"id": 40,  "channel": "PCTV"},
    # Futebol
    "premierclubes":    {"id": 107, "channel": "PCTV"},
    "premier2":         {"id": 108, "channel": "PCTV"},
    "premier3":         {"id": 109, "channel": "PCTV"},
    "premier4":         {"id": 110, "channel": "PCTV"},
    "premier5":         {"id": 111, "channel": "PCTV"},
    "premier6":         {"id": 112, "channel": "PCTV"},
    "premier7":         {"id": 113, "channel": "PCTV"},
    # Notícias
    "globonews":        {"id": 78,  "channel": "PCTV"},
    "cnnbrasil":        {"id": 77,  "channel": "PCTV"},
    "bandnews":         {"id": 182, "channel": "PCTV"},
    "jpnews":           {"id": 187, "channel": "PCTV"},
    "bmcnews":          {"id": 321, "channel": "PCTV"},
    "sbtnews":          {"id": 469, "channel": "PCTV"},
    "cnni":             {"id": 177, "channel": "PCTV"},
    "cnbc":             {"id": 339, "channel": "PCTV"},
    "cnnmoney":         {"id": 349, "channel": "PCTV"},
    "bloomberg":        {"id": 35,  "channel": "PCTV"},
    "bbcnews":          {"id": 67,  "channel": "PCTV"},
    "tbc":              {"id": 335, "channel": "PCTV"},
    "gazeta":           {"id": 53,  "channel": "PCTV"},
    "canaluol":         {"id": 352, "channel": "PCTV"},
    # Entretenimento
    "gnt":              {"id": 97,  "channel": "PCTV"},
    "multishow":        {"id": 98,  "channel": "PCTV"},
    "viva":             {"id": 99,  "channel": "PCTV"},
    "e":                {"id": 87,  "channel": "PCTV"},
    "f":                {"id": 76,  "channel": "PCTV"},
    "tlc":              {"id": 12,  "channel": "PCTV"},
    "woohoo":           {"id": 48,  "channel": "PCTV"},
    "universaltv":      {"id": 102, "channel": "PCTV"},
    "warnertvbr":       {"id": 83,  "channel": "PCTV"},
    "sonychannel":      {"id": 82,  "channel": "PCTV"},
    "axn":              {"id": 79,  "channel": "PCTV"},
    "tntnovelas":       {"id": 299, "channel": "PCTV"},
    "usa":              {"id": 103, "channel": "PCTV"},
    "lifetime":         {"id": 88,  "channel": "PCTV"},
    "adultswim":        {"id": 322, "channel": "PCTV"},
    "tntseries":        {"id": 20,  "channel": "PCTV"},
    "amc":              {"id": 33,  "channel": "PCTV"},
    "euro":             {"id": 119, "channel": "PCTV"},
    "like":             {"id": 183, "channel": "PCTV"},
    "cbi":              {"id": 54,  "channel": "PCTV"},
    "getv":             {"id": 466, "channel": "PCTV"},
    # Cinema
    "tnt":              {"id": 9,   "channel": "PCTV"},
    "megapix":          {"id": 105, "channel": "PCTV"},
    "space":            {"id": 10,  "channel": "PCTV"},
    "cinemax":          {"id": 178, "channel": "PCTV"},
    "primebox":         {"id": 57,  "channel": "PCTV"},
    "studiouniversal":  {"id": 106, "channel": "PCTV"},
    "tcm":              {"id": 47,  "channel": "PCTV"},
    "filmeart":         {"id": 51,  "channel": "PCTV"},
    "canalbrasil":      {"id": 104, "channel": "PCTV"},
    # Documentários
    "discovery":        {"id": 7,   "channel": "PCTV"},
    "animalplanet":     {"id": 15,  "channel": "PCTV"},
    "history":          {"id": 84,  "channel": "PCTV"},
    "disctubo":         {"id": 18,  "channel": "PCTV"},
    "discscience":      {"id": 116, "channel": "PCTV"},
    "disctheater":      {"id": 117, "channel": "PCTV"},
    "discworld":        {"id": 118, "channel": "PCTV"},
    "historyh2":        {"id": 85,  "channel": "PCTV"},
    "discid":           {"id": 13,  "channel": "PCTV"},
    # Infantil
    "globinho":         {"id": 94,  "channel": "PCTV"},
    "disckids":         {"id": 1,   "channel": "PCTV"},
    "gloob":            {"id": 93,  "channel": "PCTV"},
    "cartoonnetwork":   {"id": 2,   "channel": "PCTV"},
    "cartoonito":       {"id": 11,  "channel": "PCTV"},
    "tvratimbum":       {"id": 62,  "channel": "PCTV"},
    "dundun":           {"id": 49,  "channel": "PCTV"},
    # Música
    "bis":              {"id": 101, "channel": "PCTV"},
    "playtv":           {"id": 56,  "channel": "PCTV"},
    "musicbox":         {"id": 55,  "channel": "PCTV"},
    "tracebrasil":      {"id": 81,  "channel": "PCTV"},
    # Lifestyle / Gastronomia / Arte / Agro
    "hgtv":             {"id": 115, "channel": "PCTV"},
    "hh":               {"id": 8,   "channel": "PCTV"},
    "modoviagem":       {"id": 100, "channel": "PCTV"},
    "travelbox":        {"id": 75,  "channel": "PCTV"},
    "foodnetwork":      {"id": 52,  "channel": "PCTV"},
    "saborarte":        {"id": 288, "channel": "PCTV"},
    "travelfood":       {"id": 353, "channel": "PCTV"},
    "arte1":            {"id": 34,  "channel": "PCTV"},
    "curta":            {"id": 19,  "channel": "PCTV"},
    "futura":           {"id": 95,  "channel": "PCTV"},
    "c3tv":             {"id": 314, "channel": "PCTV"},
    "valeagricola":     {"id": 338, "channel": "PCTV"},
    "canalagro":        {"id": 80,  "channel": "PCTV"},
    "canaldобоі":       {"id": 328, "channel": "PCTV"},
    # Internacional / Religioso / Outros
    "raiitalia":        {"id": 58,  "channel": "PCTV"},
    "tv5monde":         {"id": 63,  "channel": "PCTV"},
    "tve":              {"id": 176, "channel": "PCTV"},
    "redegospel":       {"id": 59,  "channel": "PCTV"},
    "tvbrasil":         {"id": 61,  "channel": "PCTV"},
    "polishop":         {"id": 468, "channel": "PCTV"},
}

# ─── Estado global da sessão ──────────────────────────────────────────────────
class ClaroSession:
    def __init__(self):
        self.session        = requests.Session()
        self.xsrf_token     = ""
        self.browser_id     = str(uuid.uuid4())       # avs_browser_id fixo
        self.valid          = False
        self.last_login     = 0.0
        self.last_keepalive = 0.0
        self.login_attempts = 0
        self.last_error     = ""
        self.stream_cache: Dict[str, Tuple[str, float]] = {}   # channel_id → (url, ts)
        self.lock           = threading.Lock()

        self._set_base_headers()

    def _set_base_headers(self):
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept":          "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin":          BASE_URL,
            "Referer":         BASE_URL + "/",
        })

    # ── 1. Inicializar sessão (pegar cookiesession1 e avs_browser_id) ─────────
    def _init_session(self):
        """GET homepage para popular cookiesession1 e demais cookies iniciais."""
        log.debug("Inicializando sessão HTTP…")
        self.session.cookies.clear()
        self._set_base_headers()

        # Injeta avs_browser_id antes do GET (o JS do site faz isso)
        self.session.cookies.set(
            "avs_browser_id", self.browser_id,
            domain="www.clarotvmais.com.br", path="/"
        )

        try:
            r = self.session.get(HOME_URL, timeout=20)
            log.debug(f"HOME GET {r.status_code}, cookies: {list(self.session.cookies.keys())}")
            return r.status_code < 500
        except Exception as e:
            log.error(f"Erro ao inicializar sessão: {e}")
            return False

    # ── 2. Extrair XSRF do avs_cookie JWT ────────────────────────────────────
    def _extract_xsrf_from_avs_cookie(self):
        """
        O avs_cookie é um JWT HS256.
        Payload (base64url) contém { "xsrfToken": "...", ... }
        """
        avs_raw = self.session.cookies.get("avs_cookie", "")
        if not avs_raw:
            log.warning("avs_cookie não encontrado nos cookies")
            return ""
        try:
            parts = avs_raw.split(".")
            if len(parts) < 2:
                return ""
            # Corrige padding base64url
            payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_bytes)
            token = payload.get("xsrfToken", "")
            log.debug(f"XSRF extraído do JWT: {token[:20]}…")
            return token
        except Exception as e:
            log.error(f"Erro ao decodificar avs_cookie JWT: {e}")
            return ""

    # ── 3. Login ──────────────────────────────────────────────────────────────
    def login(self):
        with self.lock:
            self.login_attempts += 1
            log.info(f"Tentativa de login #{self.login_attempts}…")

            # Reinicia sessão
            if not self._init_session():
                self.last_error = "Falha ao inicializar sessão HTTP"
                return False

            # Tenta com Content-Type JSON (fluxo SPA moderno)
            result = self._try_login_json()

            # Se falhar, tenta form-encoded (fluxo legado)
            if not result:
                log.info("JSON login falhou, tentando form-encoded…")
                result = self._try_login_form()

            if result:
                self.xsrf_token     = self._extract_xsrf_from_avs_cookie()
                self.valid          = bool(self.xsrf_token)
                self.last_login     = time.time()
                if self.valid:
                    log.info("✅ Login com sucesso!")
                    # Aplica XSRF em todos os requests futuros
                    self.session.headers.update({"x-xsrf-token": self.xsrf_token})
                else:
                    self.last_error = "Login OK mas avs_cookie/XSRF não encontrado"
                    log.error(self.last_error)
            else:
                self.valid = False

            return self.valid

    def _login_headers(self, extra_xsrf=""):
        """Headers comuns usados no POST de login."""
        h = {
            "Content-Type":   "application/json",
            "Accept":         "application/json, text/plain, */*",
            "Origin":         BASE_URL,
            "Referer":        HOME_URL,
        }
        if extra_xsrf:
            h["x-xsrf-token"] = extra_xsrf
        return h

    def _try_login_json(self):
        """POST JSON para /avsclient/login."""
        try:
            payload = {"username": USERNAME, "password": PASSWORD}
            r = self.session.post(
                LOGIN_URL,
                json=payload,
                headers=self._login_headers(),
                timeout=30,
            )
            log.debug(f"Login JSON → {r.status_code}: {r.text[:200]}")
            if r.status_code == 200:
                try:
                    body = r.json()
                    if body.get("status") in ("OK", "ok") or body.get("resultCode") == "OK":
                        return True
                except Exception:
                    pass
                # Sem JSON mas 200 → pode ter dado certo (verifica cookies)
                if self.session.cookies.get("avs_cookie"):
                    return True
            self.last_error = f"Login JSON {r.status_code}: {r.text[:100]}"
        except Exception as e:
            self.last_error = str(e)
            log.error(f"Exceção login JSON: {e}")
        return False

    def _try_login_form(self):
        """POST form-encoded para /avsclient/login (fallback)."""
        try:
            payload = {"username": USERNAME, "password": PASSWORD}
            headers = self._login_headers()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            r = self.session.post(
                LOGIN_URL,
                data=payload,
                headers=headers,
                timeout=30,
            )
            log.debug(f"Login form → {r.status_code}: {r.text[:200]}")
            if r.status_code == 200 and self.session.cookies.get("avs_cookie"):
                return True
            self.last_error = f"Login form {r.status_code}: {r.text[:100]}"
        except Exception as e:
            self.last_error = str(e)
            log.error(f"Exceção login form: {e}")
        return False

    # ── 4. Keepalive ──────────────────────────────────────────────────────────
    def keepalive(self):
        if not self.valid:
            return False
        try:
            r = self.session.get(
                KEEPALIVE_URL,
                headers={"x-xsrf-token": self.xsrf_token},
                timeout=15,
            )
            self.last_keepalive = time.time()
            body = {}
            try:
                body = r.json()
            except Exception:
                pass
            ok = r.status_code == 200 and body.get("status") == "OK"
            if ok:
                log.debug("Keepalive OK")
            else:
                log.warning(f"Keepalive falhou {r.status_code}: {r.text[:80]}")
                self.valid = False
            return ok
        except Exception as e:
            log.error(f"Exceção keepalive: {e}")
            self.valid = False
            return False

    # ── 5. Obter URL CDN ──────────────────────────────────────────────────────
    def get_stream_url(self, channel_id: int, channel_name: str = "PCTV") -> Optional[str]:
        cache_key = str(channel_id)
        # Cache de 8 min (tokens duram ~10-11 min)
        if cache_key in self.stream_cache:
            url, ts = self.stream_cache[cache_key]
            if time.time() - ts < 480:
                return url

        if not self.valid:
            log.warning("Sessão inválida, tentando relogin…")
            if not self.login():
                return None

        params = {
            "id":          channel_id,
            "type":        "LIVE",
            "player":      "bitmovin",
            "tvChannelId": channel_id,
            "location":    LOCATION,
            "channel":     channel_name,
        }
        try:
            r = self.session.get(
                GETCDN_URL,
                params=params,
                headers={"x-xsrf-token": self.xsrf_token},
                timeout=20,
            )
            log.debug(f"getcdn {channel_id} → {r.status_code}: {r.text[:300]}")

            if r.status_code == 401:
                log.warning("getcdn 401 – relogando…")
                self.valid = False
                if self.login():
                    return self.get_stream_url(channel_id, channel_name)
                return None

            body = r.json()
            # Actualiza XSRF se o servidor enviou um novo
            new_xsrf = r.headers.get("x-xsrf-token", "")
            if new_xsrf and new_xsrf != self.xsrf_token:
                self.xsrf_token = new_xsrf
                self.session.headers.update({"x-xsrf-token": self.xsrf_token})

            # Navega na resposta para encontrar a URL
            url = self._extract_url(body)
            if url:
                self.stream_cache[cache_key] = (url, time.time())
                return url

            log.error(f"URL não encontrada na resposta: {body}")
        except Exception as e:
            log.error(f"Exceção getcdn: {e}")
        return None

    def _extract_url(self, body: dict) -> Optional[str]:
        """Extrai a URL de stream da resposta do getcdn."""
        if not isinstance(body, dict):
            return None

        # Tenta caminhos conhecidos da API
        for path in [
            ["response", "url"],
            ["response", "streamingUrl"],
            ["response", "mediaUrl"],
            ["url"],
            ["streamingUrl"],
        ]:
            val = body
            try:
                for key in path:
                    val = val[key]
                if isinstance(val, str) and val.startswith("http"):
                    return val
            except (KeyError, TypeError):
                continue

        # Busca recursiva por qualquer campo que pareça URL de stream
        return self._deep_find_url(body)

    def _deep_find_url(self, obj, depth: int = 0) -> Optional[str]:
        if depth > 6:
            return None
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and v.startswith("http") and (
                    ".mpd" in v or ".m3u8" in v or "manifest" in v.lower()
                    or "stream" in v.lower() or "cdn" in v.lower()
                ):
                    return v
                result = self._deep_find_url(v, depth + 1)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._deep_find_url(item, depth + 1)
                if result:
                    return result
        return None

    # ── Debug / Status ────────────────────────────────────────────────────────
    def debug_info(self) -> dict:
        cookie_keys = list(self.session.cookies.keys())
        return {
            "ts":              __import__("datetime").datetime.utcnow().isoformat(),
            "session_valid":   self.valid,
            "has_avs_cookie":  "avs_cookie" in cookie_keys,
            "xsrf_present":    bool(self.xsrf_token),
            "xsrf_token_snippet": self.xsrf_token[:20] + "…" if self.xsrf_token else "",
            "cookies_count":   len(cookie_keys),
            "cookies_keys":    cookie_keys,
            "login_attempts":  self.login_attempts,
            "last_error":      self.last_error,
            "last_login_fmt":  _fmt_ts(self.last_login),
            "last_keepalive_fmt": _fmt_ts(self.last_keepalive),
            "stream_cache_size": len(self.stream_cache),
            "browser_id":      self.browser_id,
        }

    def status_info(self) -> dict:
        return {
            "valid":              self.valid,
            "has_avs_cookie":     "avs_cookie" in self.session.cookies,
            "has_xsrf":           bool(self.xsrf_token),
            "xsrf":               self.xsrf_token[:20] + "…" if self.xsrf_token else "",
            "login_attempts":     self.login_attempts,
            "last_error":         self.last_error,
            "last_login_fmt":     _fmt_ts(self.last_login),
            "last_keepalive_fmt": _fmt_ts(self.last_keepalive),
            "stream_cache_size":  len(self.stream_cache),
            "channels":           len(CHANNELS),
            "cookies_count":      len(self.session.cookies),
        }


def _fmt_ts(ts: float) -> Optional[str]:
    if ts == 0:
        return None
    return __import__("datetime").datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


# ─── Instância global ─────────────────────────────────────────────────────────
claro = ClaroSession()


# ─── Background threads ───────────────────────────────────────────────────────
def _login_loop():
    """Tenta login na inicialização e relogin a cada falha."""
    MAX_WAIT = 300
    wait = 10
    while True:
        if not claro.valid:
            if claro.login():
                wait = 10
            else:
                log.warning(f"Login falhou, aguardando {wait}s…")
                time.sleep(wait)
                wait = min(wait * 2, MAX_WAIT)
                continue
        time.sleep(30)


def _keepalive_loop():
    """Mantém a sessão viva enviando keepalive periódico."""
    while True:
        time.sleep(180)   # a cada 3 min (sessão expira em ~10 min)
        if claro.valid:
            claro.keepalive()


# ─── HTTP Server ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info(f"{self.address_string()} – {fmt % args}")

    def _json(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, url: str):
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def _text(self, code: int, msg: str):
        body = msg.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")

        # ── /debug ──────────────────────────────────────────────────
        if path == "/debug":
            # Testa getcdn ao vivo para canal 78 (GloboNews)
            r_getcdn = None
            try:
                r_getcdn = claro.session.get(
                    GETCDN_URL,
                    params={"id": 78, "type": "LIVE", "player": "bitmovin",
                            "tvChannelId": 78, "location": LOCATION, "channel": "PCTV"},
                    headers={"x-xsrf-token": claro.xsrf_token},
                    timeout=10,
                )
                getcdn_status = r_getcdn.status_code
                try:
                    getcdn_body = r_getcdn.json()
                except Exception:
                    getcdn_body = r_getcdn.text[:200]
            except Exception as e:
                getcdn_status = -1
                getcdn_body   = str(e)

            r_ka = None
            try:
                r_ka = claro.session.get(KEEPALIVE_URL, timeout=10)
                ka_status = r_ka.status_code
                try:
                    ka_body = r_ka.json()
                except Exception:
                    ka_body = r_ka.text[:200]
            except Exception as e:
                ka_status = -1
                ka_body   = str(e)

            info = claro.debug_info()
            info.update({
                "getcdn_status": getcdn_status,
                "getcdn_body":   getcdn_body,
                "keepalive_status": ka_status,
                "keepalive_body":   ka_body,
            })
            self._json(200, info)

        # ── /status ─────────────────────────────────────────────────
        elif path == "/status":
            self._json(200, claro.status_info())

        # ── /login (força relogin manual) ───────────────────────────
        elif path == "/login":
            claro.valid = False
            ok = claro.login()
            self._json(200 if ok else 500, {
                "ok": ok, "error": claro.last_error,
                "has_avs_cookie": "avs_cookie" in claro.session.cookies,
                "xsrf_present": bool(claro.xsrf_token),
            })

        # ── /stream/<canal> ─────────────────────────────────────────
        elif path.startswith("/stream/"):
            name = path.split("/stream/", 1)[1].lower().replace("-", "").replace("_", "")
            if name not in CHANNELS:
                self._json(404, {"error": f"Canal '{name}' não encontrado",
                                  "canais": sorted(CHANNELS.keys())})
                return
            ch   = CHANNELS[name]
            url  = claro.get_stream_url(ch["id"], ch["channel"])
            if url:
                self._redirect(url)
            else:
                self._json(503, {"error": "Não foi possível obter URL de stream",
                                  "session_valid": claro.valid,
                                  "last_error": claro.last_error})

        # ── /channels ───────────────────────────────────────────────
        elif path == "/channels":
            self._json(200, {
                "channels": {k: v["id"] for k, v in sorted(CHANNELS.items())},
                "total": len(CHANNELS),
            })

        # ── / (index) ───────────────────────────────────────────────
        elif path in ("", "/"):
            html = _build_index()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        else:
            self._json(404, {"error": "Rota não encontrada"})


def _build_index() -> bytes:
    lines = ["<!DOCTYPE html><html><head><meta charset='utf-8'>",
             "<title>Claro TV Proxy</title>",
             "<style>body{font-family:monospace;background:#111;color:#eee;padding:20px}",
             "a{color:#E30613}h2{color:#E30613}</style></head><body>",
             "<h2>📡 Claro TV Mais – Proxy</h2>",
             f"<p>Status: <b>{'✅ Online' if claro.valid else '❌ Offline'}</b></p>",
             "<h3>Rotas</h3><ul>",
             "<li><a href='/status'>/status</a> – Status da sessão</li>",
             "<li><a href='/debug'>/debug</a> – Debug detalhado</li>",
             "<li><a href='/login'>/login</a> – Forçar relogin</li>",
             "<li><a href='/channels'>/channels</a> – Lista de canais</li>",
             "<li>/stream/&lt;canal&gt; – Stream (ex: /stream/sportv)</li>",
             "</ul><h3>Canais disponíveis</h3><ul>"]
    for name in sorted(CHANNELS.keys()):
        lines.append(f"<li><a href='/stream/{name}'>/stream/{name}</a></li>")
    lines.append("</ul></body></html>")
    return "\n".join(lines).encode()


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info(f"🚀 Iniciando Claro TV Proxy na porta {PORT}…")
    log.info(f"   Usuário: {USERNAME}")

    # Background threads
    threading.Thread(target=_login_loop,    daemon=True, name="login-loop").start()
    threading.Thread(target=_keepalive_loop, daemon=True, name="keepalive-loop").start()

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    log.info(f"✅ Servidor rodando em http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Encerrando…")
        server.shutdown()
