#!/bin/bash

# Claro TV+ Auto Installer - x86_64 & ARM
set -e

echo "🚀 Instalador Claro TV+ Stream Server"
echo "====================================="

# Detecta arquitetura
ARCH=$(uname -m)
echo "📱 Arquitetura detectada: $ARCH"

# Remove instalação anterior
echo "🗑️  Removendo instalação anterior..."
rm -rf /opt/claro-tv
rm -f /etc/systemd/system/claro-tv.service
systemctl daemon-reload 2>/dev/null || true

# Cria diretório
mkdir -p /opt/claro-tv
cd /opt/claro-tv

# Atualiza sistema e instala dependências
echo "📦 Instalando dependências..."
apt update -y
apt install -y python3 python3-pip python3-venv curl wget nginx-full ufw

# Cria ambiente virtual Python
python3 -m venv venv
source venv/bin/activate

# Instala Python packages
pip install --upgrade pip
pip install requests

# Baixa scripts
echo "📥 Baixando scripts..."
curl -s -o claro.py https://raw.githubusercontent.com/jeanfraga95/claro/main/claro.py
curl -s -o claro.service https://raw.githubusercontent.com/jeanfraga95/claro/main/claro.service
chmod +x claro.py

# Configura Nginx reverse proxy
cat > /etc/nginx/sites-available/claro-tv << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

# Ativa site Nginx
ln -sf /etc/nginx/sites-available/claro-tv /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# Configura firewall
ufw --force enable
ufw allow 80
ufw allow 8080
ufw allow ssh

# Cria service systemd
cat > claro.service << 'EOF'
[Unit]
Description=Claro TV+ Stream Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/claro-tv
Environment=PATH=/opt/claro-tv/venv/bin
ExecStart=/opt/claro-tv/venv/bin/python claro.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

mv claro.service /etc/systemd/system/claro-tv.service
systemctl daemon-reload
systemctl enable claro-tv
systemctl start claro-tv

# Obtém IP público
PUBLIC_IP=$(curl -s ifconfig.me || curl -s ipinfo.io/ip || echo "localhost")
LOCAL_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "✅ INSTALAÇÃO CONCLUÍDA!"
echo "====================================="
echo "🌐 Acesse pelos links:"
echo "   🔴 WEB:        http://$PUBLIC_IP"
echo "   🟢 LOCAL:      http://$LOCAL_IP"
echo "   📱 VLC:        http://$PUBLIC_IP:8080/stream/[canal]"
echo ""
echo "📋 Exemplos VLC
