#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  Claro TV Mais – Instalador / Atualizador
#  Uso: sudo bash install.sh
#        CLARO_USER="seu_cpf" CLARO_PASS="sua_senha" sudo -E bash install.sh
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Cores ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}✔${NC}  $*"; }
info() { echo -e "${CYAN}→${NC}  $*"; }
warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "${RED}✘${NC}  $*"; }
sep()  { echo -e "${CYAN}────────────────────────────────────────────${NC}"; }

# ── Configurações ─────────────────────────────────────────────────────────────
SERVICE_NAME="claro-proxy"
INSTALL_DIR="/opt/claro"
VENV_DIR="$INSTALL_DIR/venv"
SCRIPT_SRC="$(dirname "$(realpath "$0")")/claro.py"   # claro.py ao lado do install.sh
SCRIPT_DST="$INSTALL_DIR/claro.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
PORT="${PROXY_PORT:-3535}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# ── Credenciais (interativo se não passadas via env) ──────────────────────────
CLARO_USER="${CLARO_USER:-}"
CLARO_PASS="${CLARO_PASS:-}"
CLARO_LOCATION="${CLARO_LOCATION:-SAO PAULO,SAO PAULO}"

# ═══════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${CYAN}📡  Claro TV Mais – Instalador${NC}"
sep
echo ""

# ── Root check ────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    err "Execute como root:  sudo bash install.sh"
    exit 1
fi

# ── Verifica se claro.py existe ───────────────────────────────────────────────
if [[ ! -f "$SCRIPT_SRC" ]]; then
    err "Arquivo claro.py não encontrado em: $SCRIPT_SRC"
    err "Coloque install.sh e claro.py na mesma pasta e execute novamente."
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 1 – Credenciais
# ═══════════════════════════════════════════════════════════════════════════════
sep
info "ETAPA 1 – Credenciais Claro"

if [[ -z "$CLARO_USER" || -z "$CLARO_PASS" ]]; then
    # Tenta ler do arquivo de credenciais existente
    CREDS_FILE="$INSTALL_DIR/claro.env"
    if [[ -f "$CREDS_FILE" ]]; then
        warn "Credenciais não fornecidas. Usando arquivo existente: $CREDS_FILE"
        source "$CREDS_FILE"
    else
        echo ""
        read -rp "  CPF, e-mail ou username Claro: " CLARO_USER
        read -rsp "  Senha: " CLARO_PASS
        echo ""
    fi
fi

if [[ -z "$CLARO_USER" || -z "$CLARO_PASS" ]]; then
    err "Credenciais obrigatórias. Defina CLARO_USER e CLARO_PASS."
    exit 1
fi

ok "Usuário: $CLARO_USER"

# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 2 – Remover instalação anterior
# ═══════════════════════════════════════════════════════════════════════════════
sep
info "ETAPA 2 – Limpando instalação anterior"

# Para e desabilita serviço se existir
if systemctl list-units --full -all 2>/dev/null | grep -q "${SERVICE_NAME}.service"; then
    info "Parando serviço ${SERVICE_NAME}…"
    systemctl stop  "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    ok "Serviço parado e desabilitado"
else
    info "Serviço ${SERVICE_NAME} não encontrado (instalação nova)"
fi

# Remove arquivo de serviço antigo
if [[ -f "$SERVICE_FILE" ]]; then
    rm -f "$SERVICE_FILE"
    systemctl daemon-reload 2>/dev/null || true
    ok "Arquivo de serviço removido"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 3 – Liberar a porta
# ═══════════════════════════════════════════════════════════════════════════════
sep
info "ETAPA 3 – Liberando porta $PORT"

kill_port() {
    local port="$1"
    local pids

    # Método 1: lsof
    if command -v lsof &>/dev/null; then
        pids=$(lsof -ti TCP:"$port" 2>/dev/null || true)
        if [[ -n "$pids" ]]; then
            warn "Processos usando porta $port (lsof): $pids"
            echo "$pids" | xargs -r kill -9 2>/dev/null || true
            sleep 1
        fi
    fi

    # Método 2: ss + awk
    if command -v ss &>/dev/null; then
        pids=$(ss -tlnp "sport = :$port" 2>/dev/null \
               | grep -oP '(?<=pid=)\d+' || true)
        if [[ -n "$pids" ]]; then
            warn "Processos usando porta $port (ss): $pids"
            echo "$pids" | xargs -r kill -9 2>/dev/null || true
            sleep 1
        fi
    fi

    # Método 3: fuser
    if command -v fuser &>/dev/null; then
        fuser -k "${port}/tcp" 2>/dev/null || true
        sleep 1
    fi

    # Verifica se a porta ficou livre
    if command -v ss &>/dev/null; then
        if ss -tlnp 2>/dev/null | grep -q ":$port "; then
            err "Porta $port ainda em uso após tentativas de liberação!"
            ss -tlnp | grep ":$port" || true
            return 1
        fi
    fi
    ok "Porta $port liberada"
}

kill_port "$PORT"

# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 4 – Dependências do sistema
# ═══════════════════════════════════════════════════════════════════════════════
sep
info "ETAPA 4 – Dependências do sistema"

apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv curl lsof net-tools
ok "Pacotes instalados"

# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 5 – Diretório e venv
# ═══════════════════════════════════════════════════════════════════════════════
sep
info "ETAPA 5 – Preparando ambiente Python"

# Recria diretório limpo (mantém apenas claro.env se já existir)
if [[ -d "$INSTALL_DIR" ]]; then
    # Salva credenciais se existirem
    [[ -f "$INSTALL_DIR/claro.env" ]] && cp "$INSTALL_DIR/claro.env" /tmp/claro.env.bak || true
    rm -rf "$INSTALL_DIR"
fi
mkdir -p "$INSTALL_DIR"
# Restaura credenciais
[[ -f /tmp/claro.env.bak ]] && mv /tmp/claro.env.bak "$INSTALL_DIR/claro.env" || true

# Cria venv
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install requests -q
ok "Virtualenv criado em $VENV_DIR"

# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 6 – Instala o script
# ═══════════════════════════════════════════════════════════════════════════════
sep
info "ETAPA 6 – Instalando claro.py"

cp "$SCRIPT_SRC" "$SCRIPT_DST"
chmod 600 "$SCRIPT_DST"   # só root lê (tem credenciais no env)
ok "Script instalado em $SCRIPT_DST"

# Salva arquivo de credenciais (para reuso em futuras reinstalações)
cat > "$INSTALL_DIR/claro.env" <<EOF
CLARO_USER="${CLARO_USER}"
CLARO_PASS="${CLARO_PASS}"
CLARO_LOCATION="${CLARO_LOCATION}"
PROXY_PORT="${PORT}"
LOG_LEVEL="${LOG_LEVEL}"
EOF
chmod 600 "$INSTALL_DIR/claro.env"
ok "Credenciais salvas em $INSTALL_DIR/claro.env"

# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 7 – Serviço systemd
# ═══════════════════════════════════════════════════════════════════════════════
sep
info "ETAPA 7 – Configurando serviço systemd"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Claro TV+ Stream Proxy
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${VENV_DIR}/bin/python3 ${SCRIPT_DST}
Restart=always
RestartSec=15
StartLimitIntervalSec=120
StartLimitBurst=5

# Credenciais e configuração
Environment="CLARO_USER=${CLARO_USER}"
Environment="CLARO_PASS=${CLARO_PASS}"
Environment="CLARO_LOCATION=${CLARO_LOCATION}"
Environment="PROXY_PORT=${PORT}"
Environment="LOG_LEVEL=${LOG_LEVEL}"

# Limites
LimitNOFILE=65536

# Logs
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

[Install]
WantedBy=multi-user.target
EOF

chmod 600 "$SERVICE_FILE"
ok "Arquivo de serviço criado: $SERVICE_FILE"

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
ok "Serviço habilitado para iniciar no boot"

# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 8 – Firewall (UFW se disponível)
# ═══════════════════════════════════════════════════════════════════════════════
sep
info "ETAPA 8 – Firewall"

if command -v ufw &>/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow "$PORT"/tcp comment "Claro TV Proxy" 2>/dev/null || true
    ok "UFW: porta $PORT liberada"
else
    warn "UFW não ativo – verifique seu firewall manualmente se necessário"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 9 – Inicia o serviço
# ═══════════════════════════════════════════════════════════════════════════════
sep
info "ETAPA 9 – Iniciando serviço"

systemctl start "$SERVICE_NAME"
sleep 4   # aguarda subir

# Verifica se subiu
if systemctl is-active --quiet "$SERVICE_NAME"; then
    ok "Serviço ${SERVICE_NAME} rodando!"
else
    err "Serviço não iniciou. Últimas linhas do log:"
    journalctl -u "$SERVICE_NAME" -n 20 --no-pager || true
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
# ETAPA 10 – Teste rápido
# ═══════════════════════════════════════════════════════════════════════════════
sep
info "ETAPA 10 – Teste de conectividade"

sleep 3
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://127.0.0.1:${PORT}/status" --max-time 10 || echo "000")

if [[ "$HTTP_CODE" == "200" ]]; then
    ok "Proxy respondendo em http://127.0.0.1:${PORT}/status"

    # Mostra status JSON formatado
    echo ""
    curl -s "http://127.0.0.1:${PORT}/status" \
        | python3 -m json.tool 2>/dev/null || true
else
    warn "Proxy retornou HTTP $HTTP_CODE (pode ainda estar logando)"
    warn "Aguarde alguns segundos e acesse: http://SEU_IP:${PORT}/status"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Resumo final
# ═══════════════════════════════════════════════════════════════════════════════
sep
echo ""
echo -e "${BOLD}${GREEN}✅  Instalação concluída!${NC}"
echo ""

# Detecta IP público
PUBLIC_IP=$(curl -s --max-time 5 https://api.ipify.org 2>/dev/null \
         || curl -s --max-time 5 https://ifconfig.me 2>/dev/null \
         || hostname -I | awk '{print $1}')

echo -e "  ${BOLD}Acesso:${NC}"
echo -e "    http://${PUBLIC_IP}:${PORT}/          → Página inicial"
echo -e "    http://${PUBLIC_IP}:${PORT}/status    → Status da sessão"
echo -e "    http://${PUBLIC_IP}:${PORT}/debug     → Debug detalhado"
echo -e "    http://${PUBLIC_IP}:${PORT}/login     → Forçar relogin"
echo -e "    http://${PUBLIC_IP}:${PORT}/channels  → Lista de canais"
echo -e "    http://${PUBLIC_IP}:${PORT}/stream/sportv  → Stream SportV"
echo ""
echo -e "  ${BOLD}Comandos úteis:${NC}"
echo -e "    sudo systemctl status ${SERVICE_NAME}"
echo -e "    sudo journalctl -u ${SERVICE_NAME} -f"
echo -e "    sudo systemctl restart ${SERVICE_NAME}"
echo -e "    sudo bash install.sh    (reinstalar/atualizar)"
echo ""
sep
