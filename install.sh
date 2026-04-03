#!/bin/bash

# Claro TV+ Auto Installer - x86_64 & ARM (NGINX FIX)
set -e

echo "🚀 Instalador Claro TV+ Stream Server"
echo "====================================="

# Detecta arquitetura
ARCH=$(uname -m)
echo "📱 Arquitetura: $ARCH"

# Remove instalação anterior
echo "🗑️  Limpando instalação anterior..."
rm -rf /opt/claro-tv
rm -f /etc/systemd/system/claro-tv.service
rm -f /etc/nginx/sites-available/claro-tv /etc/nginx/sites-enabled/claro-tv
systemctl daemon-reload 2>/dev/null || true
systemctl stop nginx claro-tv 2>/dev/null || true

# Atualiza sistema
echo "📦 Atualizando sistema..."
apt update -y && apt upgrade -y

# Instala dependências (nginx SEM full pra evitar conflitos)
echo "📦 Instalando dependências..."
apt install -y python3 python3-pip python3-venv curl wget nginx ufw

# Para nginx se estiver rodando
systemctl stop nginx

# Cria diretório
mkdir -p /opt/claro-tv
cd /opt/claro-tv

# Python virtualenv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install requests

# Baixa scripts
echo "📥 Baixando scripts..."
curl -s -o claro.py https://raw.githubusercontent.com/jeanfraga95/claro/main/claro.py
curl -s -o claro.service https://raw.githubusercontent.com/jeanfraga95/claro/main/claro.service
chmod +x claro.py

# ✅ NGINX CONFIG CORRIGIDA (sem conflito com default)
cat > /etc/nginx/sites-available/claro-tv << 'EOF'
server {
    listen 80 default_server;
    server_name _;
    root /var/www/html;
    index index.html;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_buffering off;
    }

    location /stream {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
    }
}
EOF

# Remove default e ativa novo site
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/claro-tv /etc/nginx/sites-enabled/

# Testa e reinicia nginx
nginx -t && systemctl restart nginx || {
    echo "❌ Erro Nginx, limpando config..."
    rm -f /etc/nginx/sites-enabled/claro-tv
    systemctl restart nginx
}

# Firewall
ufw --force enable
ufw allow 80
ufw allow 8080
ufw allow 22
ufw reload

# Instala service
curl -s -o /etc/systemd/system/claro-tv.service https://raw.githubusercontent.com/jeanfraga95/claro/main/claro.service
systemctl daemon-reload
systemctl enable claro-tv
systemctl start claro-tv

# IP público
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ipinfo.io/ip 2>/dev/null || echo "localhost")
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "✅ INSTALAÇÃO CONCLUÍDA!"
echo "====================================="
echo "🌐 WEB:        http://$PUBLIC_IP"
echo "🟢 LOCAL:      http://$LOCAL_IP:8080"
echo "📱 VLC:        http://$PUBLIC_IP:8080/stream/rede-gospel"
echo ""
echo "📋 Status:"
systemctl status claro-tv --no-pager -l
echo ""
echo "🔍 Logs: journalctl -u claro-tv -f"
echo ""
echo "✅ Teste agora: curl http://localhost:8080"
