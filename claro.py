#!/usr/bin/env python3
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
from pathlib import Path

class ClaroTV:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.clarotvmais.com.br/home-landing',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        self.base_url = "https://www.clarotvmais.com.br"
        self.channels = {
            "rede-gospel": 59, "polishop": 468, "tv-brasil": 61, "cbi": 54, 
            "futura": 95, "canal-off": 96, "sportv": 30, "globonews": 78,
            # ... todos os outros canais da lista original
        }
        self.authenticated = False
        self.playback_tokens = {}

    def login(self):
        """Login REAL da Claro TV+ via form HTML"""
        try:
            print("🔐 Acessando página inicial...")
            r = self.session.get(self.base_url + "/home-landing")
            
            # Extrai CSRF token da página
            csrf_match = re.search(r'name="_token" value="([^"]+)"', r.text)
            if not csrf_match:
                print("❌ CSRF token não encontrado")
                return False
            
            csrf_token = csrf_match.group(1)
            print("✅ CSRF token obtido")
            
            # Dados do form de login
            login_data = {
                'username': '30942085841',
                'password': 'Mirian83',
                '_token': csrf_token,
            }
            
            print("🔐 Enviando credenciais...")
            login_url = self.base_url + "/login"
            login_r = self.session.post(login_url, data=login_data, allow_redirects=True)
            
            if "ao-vivo" in login_r.url or "player" in login_r.url or login_r.status_code == 200:
                print("✅ Login OK! Cookies salvos")
                self.authenticated = True
                return True
            else:
                print(f"❌ Login falhou: {login_r.status_code} - {login_r.url}")
                print(f"Response: {login_r.text[:200]}...")
                return False
                
        except Exception as e:
            print(f"❌ Erro login: {e}")
            return False

    def get_playback_token(self, channel_id):
        """Obtém MPD via getcdn"""
        try:
            if channel_id in self.playback_tokens and time.time() < self.playback_tokens[channel_id]['expires']:
                return self.playback_tokens[channel_id]
                
            url = f"{self.base_url}/avsclient/playback/getcdn"
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
                cookies = r.cookies.get_dict()
                playback_token = cookies.get('playback_token')
                
                if playback_token:
                    data = {
                        'mpd': r.json().get('manifestUri', f"https://fallback.mpd"),
                        'token': playback_token,
                        'expires': time.time() + 600
                    }
                    self.playback_tokens[channel_id] = data
                    return data
            return None
        except Exception as e:
            print(f"❌ Erro token {channel_id}: {e}")
            return None

    def get_channel_stream(self, channel_name):
        channel_id = self.channels.get(channel_name, 59)
        token_data = self.get_playback_token(channel_id)
        
        return {
            'name': channel_name.replace('-', ' ').title(),
            'vlc_url': f"http://localhost:8080/stream/{channel_name}",
            'channel_id': channel_id,
            'mpd': token_data['mpd'] if token_data else 'offline',
            'status': 'online' if token_data else 'offline'
        }

    def get_all_channels(self):
        return [self.get_channel_stream(name) for name in self.channels.keys()]

# RESTO DO CÓDIGO HTTP SERVER IGUAL...
class StreamHandler(http.server.BaseHTTPRequestHandler):
    def __init__(self, *args, claro_instance=None, **kwargs):
        self.claro = claro_instance
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/':
            self.send_main_page()
        elif self.path.startswith('/stream/'):
            self.handle_stream()
        elif self.path == '/channels.json':
            self.send_json(self.claro.get_all_channels())
        else:
            self.send_error(404)

    def handle_stream(self):
        channel_name = self.path.split('/stream/')[1].rstrip('/')
        stream = self.claro.get_channel_stream(channel_name)
        
        if stream['mpd'] != 'offline':
            self.send_m3u(stream)
        else:
            self.send_error(503, "Canal offline")

    def send_m3u(self, stream):
        self.send_response(200)
        self.send_header('Content-Type', 'application/vnd.apple.mpegurl')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        m3u = f"""#EXTM3U
#EXTINF:-1,{stream['name']}
{stream['mpd']}
"""
        self.wfile.write(m3u.encode())

    def send_main_page(self):
        channels = self.claro.get_all_channels()
        online = len([c for c in channels if c['status'] == 'online'])
        
        html = f"""
<!DOCTYPE html>
<html><head><title>Claro TV+ ({online} Online)</title>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width">
<style>body{{background:#000;color:#fff;padding:20px;font-family:Arial}}
.channel{{background:#222;margin:10px;padding:15px;border-radius:5px;cursor:pointer}}
.online{{border-left:4px #0f0 solid}}.offline{{opacity:.5}}</style></head>
<body>
<h1>📺 Claro TV+ - {online} Canais</h1>
"""
        for c in channels:
            cls = "online" if c['status']=='online' else "offline"
            html += f'<div class="channel {cls}" onclick="navigator.clipboard.writeText(`{c["vlc_url"]}`);alert(`Copiado: {c["name"]}`)">{c["name"]} <small>{c["status"].upper()}</small><br><code>{c["vlc_url"]}</code></div>'
        
        html += '<script>setTimeout(()=>location.reload(),3e4)</script></body></html>'
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, *args): pass

def main():
    print("🚀 Claro TV+ ARM Server")
    claro = ClaroTV()
    
    if not claro.login():
        print("❌ Login falhou")
        return
    
    PORT = 8088
    handler = lambda *args, **kwargs: StreamHandler(*args, claro_instance=claro, **kwargs)
    
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        ip = socket.gethostbyname(socket.gethostname())
        print(f"✅ OK! http://{ip}:{PORT}")
        print("VLC: http://localhost:8080/stream/rede-gospel")
        httpd.serve_forever()

if __name__ == "__main__":
    import socket
    main()
