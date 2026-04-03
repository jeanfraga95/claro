#!/usr/bin/env bash
# =============================================================================
#  Claro TV+ Stream Proxy — Instalador v2.0
#  Ubuntu x86_64 e ARM (Oracle VPS)
#  Uso: sudo bash install.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

step() { echo -e "\n${BLUE}${BOLD}▶  $*${NC}"; }
ok()   { echo -e "${GREEN}✓  $*${NC}"; }
warn() { echo -e "${YELLOW}⚠  $*${NC}"; }
die()  { echo -e "${RED}✗  $*${NC}" >&2; exit 1; }
info() { echo -e "${CYAN}   $*${NC}"; }

REPO_RAW="https://raw.githubusercontent.com/jeanfraga95/claro/main"
INSTALL_DIR="/opt/claro"
SVC="claro-proxy"
SERVICE_FILE="/etc/systemd/system/${SVC}.service"
PORT="${CLARO_PORT:-8080}"
VENV="${INSTALL_DIR}/venv"
PYTHON="${VENV}/bin/python3"
PIP="${VENV}/bin/pip"

# ─── Banner ────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║      Claro TV+  Stream Proxy  —  Instalador v2.0    ║"
echo "╚══════════════════════════════════════════════════════╝${NC}"

[[ $EUID -ne 0 ]] && die "Execute como root:  sudo bash install.sh"

ARCH=$(uname -m)
info "Arquitetura: ${ARCH}"
info "Porta: ${PORT}"

# ─── Remove instalação anterior ──────────────────────────────────────────────
if systemctl is-active --quiet "${SVC}" 2>/dev/null || \
   [[ -d "${INSTALL_DIR}" ]]; then
    step "Removendo instalação anterior..."
    systemctl stop    "${SVC}" 2>/dev/null || true
    systemctl disable "${SVC}" 2>/dev/null || true
    rm -f "${SERVICE_FILE}"
    rm -rf "${INSTALL_DIR}"
    rm -f /tmp/claro_session.json
    systemctl daemon-reload 2>/dev/null || true
    ok "Instalação anterior removida"
fi

# ─── Atualiza pacotes ─────────────────────────────────────────────────────────
step "Atualizando pacotes..."
apt-get update -qq
ok "Pacotes atualizados"

# ─── Dependências de sistema ──────────────────────────────────────────────────
step "Instalando dependências de sistema..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    python3 python3-pip python3-venv python3-dev \
    wget curl ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libxshmfence1 libx11-6 libxext6 \
    libxcb1 fonts-liberation xdg-utils gcc make 2>/dev/null || \
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-pip python3-venv python3-dev \
    wget curl ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libxkbcommon0 libgbm1 libpango-1.0-0 \
    libasound2 libx11-6 libxext6 gcc make 2>&1 | grep -v "^E:" || true
ok "Dependências instaladas"

# ─── Diretório ────────────────────────────────────────────────────────────────
step "Criando diretório ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
ok "Diretório criado"

# ─── Venv Python ──────────────────────────────────────────────────────────────
step "Criando virtualenv Python..."
python3 -m venv "${VENV}"
"${PIP}" install -q --upgrade pip setuptools wheel
ok "Virtualenv criado em ${VENV}"

# ─── Pacotes Python ───────────────────────────────────────────────────────────
step "Instalando Flask e Requests..."
"${PIP}" install -q flask requests
ok "Flask e Requests instalados"

# ─── Playwright (opcional — fallback do login) ────────────────────────────────
step "Instalando Playwright + Chromium (fallback de login)..."
"${PIP}" install -q playwright && \
    "${PYTHON}" -m playwright install-deps chromium 2>/dev/null || true && \
    "${PYTHON}" -m playwright install chromium 2>/dev/null || \
    warn "Playwright não pôde ser instalado — login direto via API será usado (OK)"
ok "Playwright configurado"

# ─── Baixa claro.py ───────────────────────────────────────────────────────────
step "Baixando claro.py do GitHub..."
SCRIPT="${INSTALL_DIR}/claro.py"
if command -v wget &>/dev/null; then
    wget -q -O "${SCRIPT}" "${REPO_RAW}/claro.py" || \
        curl -fsSL -o "${SCRIPT}" "${REPO_RAW}/claro.py"
else
    curl -fsSL -o "${SCRIPT}" "${REPO_RAW}/claro.py"
fi
chmod +x "${SCRIPT}"
ok "claro.py baixado"

# ─── Arquivo .env ─────────────────────────────────────────────────────────────
ENV_FILE="${INSTALL_DIR}/.env"
cat > "${ENV_FILE}" << EOF
# Claro TV+ Proxy — Configuração
CLARO_PORT=${PORT}
# Para alterar credenciais descomente e edite:
# CLARO_USER=seu_cpf_ou_email
# CLARO_PASS=sua_senha
EOF
chmod 600 "${ENV_FILE}"

# ─── Script wrapper ───────────────────────────────────────────────────────────
WRAPPER="${INSTALL_DIR}/start.sh"
cat > "${WRAPPER}" << WEOF
#!/usr/bin/env bash
set -euo pipefail
# Carrega .env
set -a; source "${INSTALL_DIR}/.env" 2>/dev/null || true; set +a
export CLARO_PORT=\${CLARO_PORT:-${PORT}}
export PYTHONUNBUFFERED=1
exec "${PYTHON}" "${SCRIPT}"
WEOF
chmod +x "${WRAPPER}"

# ─── Serviço systemd ──────────────────────────────────────────────────────────
step "Configurando serviço systemd..."
cat > "${SERVICE_FILE}" << SEOF
[Unit]
Description=Claro TV+ Stream Proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=-${ENV_FILE}
Environment=CLARO_PORT=${PORT}
Environment=PYTHONUNBUFFERED=1
ExecStart=${WRAPPER}
Restart=always
RestartSec=20
StartLimitIntervalSec=300
StartLimitBurst=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SVC}

[Install]
WantedBy=multi-user.target
SEOF

systemctl daemon-reload
systemctl enable  "${SVC}"
systemctl start   "${SVC}"
ok "Serviço systemd iniciado"

# ─── Aguarda servidor ─────────────────────────────────────────────────────────
step "Aguardando o servidor subir (máx 30s)..."
WAIT=0
while [[ $WAIT -lt 30 ]]; do
    sleep 3; ((WAIT+=3))
    if curl -sf "http://127.0.0.1:${PORT}/status" &>/dev/null; then
        ok "Servidor respondendo na porta ${PORT}!"
        break
    fi
    info "Aguardando... (${WAIT}s)"
done

# ─── IP público ───────────────────────────────────────────────────────────────
PIP_ADDR=""
for svc in "https://api.ipify.org" "https://ifconfig.me/ip" "https://icanhazip.com"; do
    PIP_ADDR=$(curl -s --max-time 5 "$svc" 2>/dev/null | tr -d '[:space:]') && \
        [[ -n "$PIP_ADDR" ]] && break
done
[[ -z "$PIP_ADDR" ]] && PIP_ADDR=$(hostname -I | awk '{print $1}')
[[ -z "$PIP_ADDR" ]] && PIP_ADDR="SEU_IP"

# ─── Firewall ─────────────────────────────────────────────────────────────────
# ufw
if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
    ufw allow "${PORT}/tcp" comment "Claro Proxy" >/dev/null 2>&1 || true
    info "Porta ${PORT} liberada no ufw"
fi
# iptables (Oracle Cloud usa iptables por padrão)
if command -v iptables &>/dev/null; then
    if ! iptables -C INPUT -p tcp --dport "${PORT}" -j ACCEPT 2>/dev/null; then
        iptables -I INPUT -p tcp --dport "${PORT}" -j ACCEPT 2>/dev/null || true
        # Persiste se possível
        iptables-save > /etc/iptables/rules.v4 2>/dev/null || \
        iptables-save > /etc/iptables.rules 2>/dev/null || true
        info "Regra iptables adicionada para porta ${PORT}"
    fi
fi

# ─── Resumo ───────────────────────────────────────────────────────────────────
if systemctl is-active --quiet "${SVC}"; then
    SSTATUS="✅ ATIVO"
else
    SSTATUS="⚠️  INICIANDO (aguarde ~30s)"
fi

echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        CLARO TV+ PROXY — INSTALADO COM SUCESSO          ║"
echo "╠══════════════════════════════════════════════════════════╣"
printf "║  %s%-52s║\n" "" "Status: ${SSTATUS}"
echo "║                                                          ║"
printf "║  🌐 Interface Web:                                       ║\n"
printf "║     http://%-50s║\n" "${PIP_ADDR}:${PORT}"
echo "║                                                          ║"
printf "║  📋 Playlist M3U:                                        ║\n"
printf "║     http://%-50s║\n" "${PIP_ADDR}:${PORT}/lista.m3u"
echo "║                                                          ║"
printf "║  📺 Exemplo de canal:                                    ║\n"
printf "║     http://%-50s║\n" "${PIP_ADDR}:${PORT}/canal/sportv"
echo "║                                                          ║"
printf "║  🔬 Debug (diagnóstico):                                 ║\n"
printf "║     http://%-50s║\n" "${PIP_ADDR}:${PORT}/debug"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}${BOLD}Comandos úteis:${NC}"
echo -e "  Logs em tempo real  : ${CYAN}journalctl -u ${SVC} -f${NC}"
echo -e "  Status do serviço   : ${CYAN}systemctl status ${SVC}${NC}"
echo -e "  Reiniciar           : ${CYAN}systemctl restart ${SVC}${NC}"
echo -e "  Forçar relogin      : ${CYAN}curl http://localhost:${PORT}/relogin${NC}"
echo -e "  Debug de sessão     : ${CYAN}curl http://localhost:${PORT}/debug | python3 -m json.tool${NC}"
echo ""
echo -e "${YELLOW}Configuração em:${NC} ${CYAN}${ENV_FILE}${NC}"
echo -e "${YELLOW}Para atualizar:${NC}   ${CYAN}sudo bash <(curl -fsSL ${REPO_RAW}/install.sh)${NC}"
echo ""
echo -e "${YELLOW}⚠  No Oracle Cloud, abra também a porta ${PORT} no Security List da VPC!${NC}"
echo ""
