#!/usr/bin/env python3
"""
Claro TV+ Stream Extractor - Funciona em x86_64 e ARM
Gera links fixos VLC para todos os canais
"""

import re
import json
import time
import uuid
import requests
from urllib.parse import urljoin, urlparse, parse_qs
import threading
import http.server
import socketserver
import webbrowser
import sys
import os
from datetime import datetime
import base64
import hashlib
from pathlib import Path

class ClaroTV:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.base_url = "https://www.clarotvmais.com.br"
        self.login_url = urljoin(self.base_url, "/home-landing")
        self.channels = {
            "rede-gospel": 59, "polishop": 468, "rede-gospel2": 59,
            "like": 183, "tv-brasil": 61, "cbi": 54, "futura": 95,
            "canal-off": 96, "getv": 466, "sportv3": 32, "sportv2": 31,
            "sportv": 30, "globonews": 78, "gnt": 97, "multishow": 98,
            "globoplay-novela": 99, "modo-viagem": 100, "travel-food": 353,
            "bm-c-news": 321, "lmc+": 353, "canal-uol": 352, "e": 87,
            "f": 76, "tlc": 12, "arte1": 34, "food-network": 52,
            "h&h-network": 8, "curta": 19, "travel-boxbrasil": 75,
            "fishbrasil": 40, "hgtv": 115, "sabor&arte": 288,
            "cnbc": 339, "cnn-money": 349, "tbc": 335, "woohoo": 48,
            "nsports": 329, "sportnet": 315, "xsports": 439,
            "espn6": 50, "espn": 29, "espn2": 28, "espn3": 39,
            "espn4": 26, "espn5": 27, "band-sports": 5,
            "jp-news": 187, "cnn-brasil": 77, "band-news": 182,
            "discovery": 7, "animal-planet": 15, "history": 84,
            "discovery-turbo": 18, "discovery-science": 116,
            "sbt-news": 469, "discovery-theater": 117, "discovery-world": 118,
            "history-h2": 85, "globinho": 94, "discovery-kids": 1,
            "gloob": 93, "cartoon-network": 2, "cartoonito": 11,
            "tv-ratimbum": 62, "dun-dun": 49, "bis": 101, "play": 56,
            "music-box-brasil": 55, "trace-brasil": 81, "universal-tv": 102,
            "warnerbros-tv": 83, "sony-channel": 82, "axn": 79,
            "tnt-novelas": 299, "e&a": 86, "discovery-id": 13,
            "usa": 103, "lifetime": 88, "adult-swim": 322,
            "tnt-series": 20, "amc": 33, "euro-channel": 119,
            "film&art": 51, "canal-brasil": 104, "tnt": 9,
            "megapix": 105, "space": 10, "cinemax": 178,
            "primebox-brasil": 57, "studio-universal": 106, "tcm": 47,
            "c3-tv": 314, "vale-agricola": 338, "gazeta": 53,
            "agro": 80, "canal-do-boi": 328, "cnn-internacional": 177,
            "bloomberg": 35, "bbc-news": 67, "rai-italia": 58,
            "tv5monde": 63, "tve": 176, "premier-clubes": 107,
            "premier-2": 108, "premier-3": 109, "premier-4": 110,
            "premier-5": 111, "premier-6": 112, "premier-7": 113
        }
        self.credentials = {
            'username': '309.420.858-41',
            'password': 'Mirian83'
        }
        self.authenticated = False

    def login(self):
        """Realiza login no Claro TV+"""
        try:
            print("🔐 Fazendo login...")
            r = self.session.get(self.login_url)
            
            # Extrai XSRF token da página
            xsrf_match = re.search(r'name="X-XSRF-TOKEN" content="([^"]+)"', r.text)
            if xsrf_match:
                self.session.headers['X-XSRF-TOKEN'] = xsrf_match.group(1)
            
            # POST login
            login_data = {
                'username': self.credentials['username'],
                'password': self.credentials['password']
            }
            
            login_r = self.session.post(
                urljoin(self.base_url, '/api/auth/login'),
                json=login_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if login_r.status_code == 200:
                self.authenticated = True
                print("✅ Login realizado com sucesso!")
                return True
            else:
                print(f"❌ Erro no login: {login_r.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Erro no login: {e}")
            return False

    def get_playback_token(self, channel_id):
        """Obtém token de playback para canal específico"""
        try:
            url = urljoin(self.base_url, f"/avsclient/playback/getcdn")
            params = {
                'id': channel_id,
                'type': 'LIVE',
                'player': 'bitmovin',
                'tvChannelId': channel_id,
                'location': 'SAO PAULO,SAO PAULO',
                'channel': 'PCTV'
            }
            
            r = self.session.get(url, params=params)
            if r.status_code == 200:
                data = r.json()
                playback_token = r.cookies.get('playback_token')
                if playback_token:
                    return {
                        'mpd': data.get('manifestUri', ''),
                        'token': playback_token,
                        'session_id': r.cookies.get('sessionId', ''),
                        'expires': int(time.time()) + 600  # 10 min
                    }
            return None
        except:
            return None

    def get_channel_stream(self, channel_name):
        """Gera link VLC fixo para canal"""
        channel_id = self.channels.get(channel_name)
        if not channel_id:
            return None
            
        token_data = self.get_playback_token(channel_id)
        if token_data and token_data['mpd']:
            # Link fixo para VLC - funciona mesmo se token/m3u8 mudar
            fixed_url = f"http://localhost:8080/stream/{channel_name}"
            return {
                'name': channel_name.replace('-', ' ').title(),
                'vlc_url': fixed_url,
                'channel_id': channel_id,
                'mpd': token_data['mpd'],
                'status': 'online'
            }
        return {
            'name': channel_name.replace('-', ' ').title(),
            'vlc_url': f"http://localhost:8080/stream/{channel_name}",
            'channel_id': channel_id,
            'status': 'offline'
        }

    def get_all_channels(self):
        """Retorna todos os canais com status"""
        channels = []
        for name in self.channels.keys():
            stream = self.get_channel_stream(name)
            channels.append(stream)
        return channels

class StreamHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, claro_instance=None, **kwargs):
        self.claro = claro_instance
        super().__init__(*args, **kwargs)

    def do_GET(self):
        parser = parse_qs(self.path[2:])
        channel_name = parser.get('channel', [None])[0]
        
        if self.path.startswith('/stream/'):
            channel_name = self.path.split('/stream/')[1].rstrip('/')
            
            if channel_name in self.claro.channels:
                stream_info = self.claro.get_channel_stream(channel_name)
                if stream_info['status'] == 'online':
                    self.send_m3u_response(stream_info)
                else:
                    self.send_error(404, "Canal offline")
            else:
                self.send_error(404, "Canal não encontrado")
        elif self.path == '/':
            self.send_main_page()
        elif self.path == '/channels.json':
            self.send_json_response(self.claro.get_all_channels())
        else:
            self.send_error(404)

    def send_m3u_response(self, stream_info):
        """Gera M3U8 proxy para VLC"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
        self.send_header('Content-Disposition', 'attachment', f'filename="{stream_info["name"]}.m3u8"')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        m3u_content = f"""#EXTM3U
#EXTINF:-1 tvg-id="{stream_info['name']}" tvg-logo="" group-title="Claro TV+",{stream_info['name']}
{stream_info['mpd']}
"""
        self.wfile.write(m3u_content.encode())

    def send_main_page(self):
        channels = self.claro.get_all_channels()
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Claro TV+ - Canais ao Vivo</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: white; }}
        .channel {{ background: #333; margin: 10px 0; padding: 15px; border-radius: 8px; cursor: pointer; }}
        .channel:hover {{ background: #444; }}
        .online {{ border-left: 5px solid #4CAF50; }}
        .offline {{ border-left: 5px solid #f44336; opacity: 0.6; }}
        .name {{ font-size: 18px; font-weight: bold; margin-bottom: 5px; }}
        .url {{ font-family: monospace; background: #000; padding: 5px; border-radius: 4px; word-break: break-all; }}
        .status {{ float: right; font-size: 12px; }}
        h1 {{ text-align: center; color: #4CAF50; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }}
        @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <h1>📺 Claro TV+ - {len([c for c in channels if c['status']=='online'])} Canais Online</h1>
    <div class="grid">
"""
        for channel in sorted(channels, key=lambda x: x['status'] == 'online', reverse=True):
            status_class = "online" if channel['status'] == 'online' else "offline"
            status_text = "🟢 ONLINE" if channel['status'] == 'online' else "🔴 OFFLINE"
            html += f"""
        <div class="channel {status_class}" onclick="navigator.clipboard.writeText('{channel['vlc_url']}'); alert('Link copiado! Cole no VLC')">
            <div class="name">{channel['name']}</div>
            <div class="status">{status_text}</div>
            <div class="url">{channel['vlc_url']}</div>
        </div>
"""
        html += """
    </div>
    <script>
        // Auto refresh a cada 30s
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def send_json_response(self, channels):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(channels, ensure_ascii=False).encode())

    def log_message(self, format, *args):
        pass  # Silent logging

def main():
    print("🚀 Claro TV+ Stream Server")
    print("=" * 50)
    
    claro = ClaroTV()
    
    if not claro.login():
        print("❌ Falha no login. Verifique as credenciais.")
        sys.exit(1)
    
    PORT = 8080
    HOST = '0.0.0.0'
    
    print(f"🌐 Servidor rodando em http://{socket.gethostbyname(socket.gethostname())}:{PORT}")
    print("📱 Acesse pelo navegador ou use os links no VLC")
    print("⏹️  Ctrl+C para parar")
    print("\n📋 Links fixos (funcionam mesmo se tokens mudarem):")
    
    handler = lambda *args, **kwargs: StreamHandler(*args, claro_instance=claro, **kwargs)
    
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        webbrowser.open(f'http://localhost:{PORT}')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Servidor parado.")

if __name__ == "__main__":
    main()
