#!/usr/bin/env bash
# =============================================================================
#  Claro TV+ Stream Proxy — Instalador
#  Compatível com Ubuntu x86_64 e ARM (Oracle VPS)
#  Uso: sudo bash install.sh
# =============================================================================
set -euo pipefail

# ─── Cores ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

step()  { echo -e "\n${BLUE}${BOLD}▶  $*${NC}"; }
ok()    { echo -e "${GREEN}✓  $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠  $*${NC}"; }
die()   { echo -e "${RED}✗  $*${NC}" >&2; exit 1; }
info()  { echo -e "${CYAN}   $*${NC}"; }

# ─── Configurações ────────────────────────────────────────────────────────────
REPO_RAW="https://raw.githubusercontent.com/jeanfraga95/claro/main"
INSTALL_DIR="/opt/claro"
SERVICE_NAME="claro-proxy"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PORT="${CLARO_PORT:-8080}"
VENV="${INSTALL_DIR}/venv"
PYTHON="${VENV}/bin/python3"
PIP="${VENV}/bin/pip"
LOG_FILE="/var/log/${SERVICE_NAME}.log"
SESSION_CACHE="/tmp/claro_session.json"

# ─── Verificações iniciais ────────────────────────────────────────────────────
echo -e "\n${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║       Claro TV+  Stream Proxy  —  Instalador        ║"
echo "╚══════════════════════════════════════════════════════╝${NC}"

[[ $EUID -ne 0 ]] && die "Execute como root:  sudo bash install.sh"

# Detecta arquitetura
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)          ARCH_LABEL="x86_64 (amd64)"  ;;
  aarch64|arm64)   ARCH_LABEL="ARM64 (aarch64)" ;;
  armv7l)          ARCH_LABEL="ARM32 (armv7l)"  ;;
  *)               ARCH_LABEL="$ARCH"            ;;
esac
info "Arquitetura detectada: ${ARCH_LABEL}"
info "Porta configurada:     ${PORT}"

# ─── Remove instalação anterior ──────────────────────────────────────────────
REINSTALL=false
if systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null || \
   systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null || \
   [[ -d "${INSTALL_DIR}" ]]; then
    REINSTALL=true
fi

if $REINSTALL; then
    step "Removendo instalação anterior..."
    systemctl stop    "${SERVICE_NAME}" 2>/dev/null || true
    systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
    [[ -f "${SERVICE_FILE}" ]] && rm -f "${SERVICE_FILE}"
    [[ -d "${INSTALL_DIR}" ]]  && rm -rf "${INSTALL_DIR}"
    [[ -f "${SESSION_CACHE}" ]] && rm -f "${SESSION_CACHE}"
    systemctl daemon-reload 2>/dev/null || true
    ok "Instalação anterior removida"
fi

# ─── Atualiza sistema ─────────────────────────────────────────────────────────
step "Atualizando lista de pacotes..."
apt-get update -qq 2>/dev/null
ok "Pacotes atualizados"

# ─── Dependências de sistema ──────────────────────────────────────────────────
step "Instalando dependências de sistema..."

PKGS=(
    python3 python3-pip python3-venv python3-dev
    wget curl ca-certificates
    # Dependências Chromium / Playwright
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2
    libasound2 libxshmfence1 libx11-6 libxext6
    libxcb1 libxcb-shm0 libxcb-render0
    fonts-liberation libappindicator3-1 xdg-utils
    # Build tools (necessários em algumas distros)
    gcc make
)

# Em ARM, algumas libs têm nomes diferentes — tenta instalar com --ignore-missing
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    --no-install-recommends "${PKGS[@]}" 2>/dev/null || \
DEBIAN_FRONTEND=noninteractive apt-get install -y \
    --no-install-recommends "${PKGS[@]}" 2>&1 | grep -v "^E:" || true

ok "Dependências de sistema instaladas"

# ─── Estrutura de diretórios ──────────────────────────────────────────────────
step "Criando estrutura de diretórios..."
mkdir -p "${INSTALL_DIR}"
touch "${LOG_FILE}"
chmod 644 "${LOG_FILE}"
ok "Diretórios criados: ${INSTALL_DIR}"

# ─── Ambiente virtual Python ──────────────────────────────────────────────────
step "Criando ambiente virtual Python..."
python3 -m venv "${VENV}"
"${PIP}" install -q --upgrade pip setuptools wheel
ok "Venv criado em ${VENV}"

# ─── Pacotes Python ───────────────────────────────────────────────────────────
step "Instalando pacotes Python (flask, requests, playwright)..."
"${PIP}" install -q flask requests playwright
ok "Pacotes Python instalados"

# ─── Playwright + Chromium ────────────────────────────────────────────────────
step "Instalando Chromium via Playwright..."
info "Isso pode levar alguns minutos..."

# Instala dependências do sistema para playwright
"${PYTHON}" -m playwright install-deps chromium 2>&1 | \
    grep -v "^$" | head -30 || true

# Instala o próprio Chromium
"${PYTHON}" -m playwright install chromium

ok "Chromium instalado pelo Playwright"

# ─── Baixa o script principal ─────────────────────────────────────────────────
step "Baixando claro.py do GitHub..."
MAIN_SCRIPT="${INSTALL_DIR}/claro.py"

if command -v wget &>/dev/null; then
    wget -q -O "${MAIN_SCRIPT}" "${REPO_RAW}/claro.py" || \
        { warn "wget falhou, tentando curl..."; \
          curl -fsSL -o "${MAIN_SCRIPT}" "${REPO_RAW}/claro.py"; }
else
    curl -fsSL -o "${MAIN_SCRIPT}" "${REPO_RAW}/claro.py"
fi

chmod +x "${MAIN_SCRIPT}"
ok "claro.py baixado em ${MAIN_SCRIPT}"

# ─── Arquivo de ambiente (variáveis) ─────────────────────────────────────────
step "Criando arquivo de configuração..."
ENV_FILE="${INSTALL_DIR}/.env"
cat > "${ENV_FILE}" << EOF
# Configuração Claro TV+ Proxy
CLARO_PORT=${PORT}
# Para alterar credenciais, edite as variáveis abaixo e reinicie o serviço:
# CLARO_USER=seu_cpf_ou_email
# CLARO_PASS=sua_senha
EOF
chmod 600 "${ENV_FILE}"
ok "Configuração em ${ENV_FILE}"

# ─── Script de início rápido ──────────────────────────────────────────────────
WRAPPER="${INSTALL_DIR}/start.sh"
cat > "${WRAPPER}" << WRAPPER_EOF
#!/usr/bin/env bash
# Iniciador do Claro TV+ Proxy
set -euo pipefail
source "${INSTALL_DIR}/.env" 2>/dev/null || true
export CLARO_PORT=\${CLARO_PORT:-${PORT}}
export PYTHONUNBUFFERED=1
# Playwright precisa de DISPLAY ou modo headless verdadeiro
export DISPLAY=:99
exec "${PYTHON}" "${MAIN_SCRIPT}"
WRAPPER_EOF
chmod +x "${WRAPPER}"

# ─── Serviço systemd ──────────────────────────────────────────────────────────
step "Configurando serviço systemd..."
cat > "${SERVICE_FILE}" << SERVICE_EOF
[Unit]
Description=Claro TV+ Stream Proxy
Documentation=https://github.com/jeanfraga95/claro
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=-${ENV_FILE}
Environment=CLARO_PORT=${PORT}
Environment=PYTHONUNBUFFERED=1
Environment=DISPLAY=:99
ExecStart=${WRAPPER}
Restart=always
RestartSec=15
StartLimitIntervalSec=300
StartLimitBurst=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable  "${SERVICE_NAME}"
systemctl start   "${SERVICE_NAME}"

ok "Serviço systemd configurado e iniciado"

# ─── Aguarda inicialização ────────────────────────────────────────────────────
step "Aguardando inicialização do servidor..."
WAIT=0
while [[ $WAIT -lt 30 ]]; do
    sleep 2; ((WAIT+=2))
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        # Testa se a porta está respondendo
        if curl -sf "http://127.0.0.1:${PORT}/status" &>/dev/null; then
            ok "Servidor respondendo na porta ${PORT}"
            break
        fi
    fi
    info "Aguardando... (${WAIT}s)"
done

# ─── Descobre IP público ──────────────────────────────────────────────────────
PUBLIC_IP=""
for svc in "https://api.ipify.org" "https://ifconfig.me/ip" "https://icanhazip.com"; do
    PUBLIC_IP=$(curl -s --max-time 5 "$svc" 2>/dev/null | tr -d '[:space:]') && break
done
[[ -z "$PUBLIC_IP" ]] && PUBLIC_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[[ -z "$PUBLIC_IP" ]] && PUBLIC_IP="SEU_IP"

# ─── Resumo final ─────────────────────────────────────────────────────────────
echo ""
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    STATUS_ICON="✅"; STATUS_MSG="SERVIÇO ATIVO"
else
    STATUS_ICON="⚠️ "; STATUS_MSG="INICIANDO (aguarde ~60s)"
fi

echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          CLARO TV+ PROXY — INSTALADO COM SUCESSO        ║"
echo "╠══════════════════════════════════════════════════════════╣"
printf "║  ${STATUS_ICON} Status: %-47s║\n" "${STATUS_MSG}"
echo "║                                                          ║"
printf "║  🌐 Interface Web:                                       ║\n"
printf "║     http://%-50s║\n" "${PUBLIC_IP}:${PORT}"
echo "║                                                          ║"
printf "║  📋 Playlist M3U:                                        ║\n"
printf "║     http://%-50s║\n" "${PUBLIC_IP}:${PORT}/lista.m3u"
echo "║                                                          ║"
printf "║  📺 Exemplo de canal:                                    ║\n"
printf "║     http://%-50s║\n" "${PUBLIC_IP}:${PORT}/canal/sportv"
echo "║                                                          ║"
printf "║  ⚙️  Status JSON:                                        ║\n"
printf "║     http://%-50s║\n" "${PUBLIC_IP}:${PORT}/status"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}${BOLD}Comandos úteis:${NC}"
echo -e "  Ver logs em tempo real : ${CYAN}journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e "  Status do serviço      : ${CYAN}systemctl status ${SERVICE_NAME}${NC}"
echo -e "  Reiniciar              : ${CYAN}systemctl restart ${SERVICE_NAME}${NC}"
echo -e "  Parar                  : ${CYAN}systemctl stop ${SERVICE_NAME}${NC}"
echo -e "  Forçar novo login      : ${CYAN}curl http://localhost:${PORT}/relogin${NC}"
echo ""
echo -e "${YELLOW}Para alterar porta ou credenciais edite:${NC}"
echo -e "  ${CYAN}${ENV_FILE}${NC}"
echo -e "  e reinicie: ${CYAN}systemctl restart ${SERVICE_NAME}${NC}"
echo ""
echo -e "${YELLOW}Para atualizar o script:${NC}"
echo -e "  ${CYAN}sudo bash <(curl -fsSL ${REPO_RAW}/install.sh)${NC}"
echo ""

# ─── Abre porta no firewall (Oracle VPS tem iptables por padrão) ──────────────
if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
    step "Abrindo porta ${PORT} no ufw..."
    ufw allow "${PORT}/tcp" comment "Claro TV+ Proxy" >/dev/null 2>&1 || true
    ok "Porta ${PORT} liberada no ufw"
fi

# Oracle Linux / Ubuntu no Oracle Cloud usa iptables
if command -v iptables &>/dev/null; then
    if ! iptables -C INPUT -p tcp --dport "${PORT}" -j ACCEPT 2>/dev/null; then
        iptables -I INPUT -p tcp --dport "${PORT}" -j ACCEPT 2>/dev/null || true
        # Persiste se disponível
        if command -v iptables-save &>/dev/null; then
            iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
        fi
        info "Regra iptables adicionada para porta ${PORT}"
    fi
fi

echo -e "${GREEN}Instalação concluída! Acesse: http://${PUBLIC_IP}:${PORT}${NC}"
echo ""
