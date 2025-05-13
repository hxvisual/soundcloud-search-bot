#!/bin/bash

# HX Music Bot - Скрипт первого развертывания
# Автор: @crypthx (https://t.me/crypthx)
# Версия: 1.0

# Цветовые коды
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
print_message() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Баннер
echo -e "${MAGENTA}"
echo -e "╔════════════════════════════════════════════════╗"
echo -e "║                                                ║"
echo -e "║             🎵 HX MUSIC BOT SETUP 🎵           ║"
echo -e "║                                                ║"
echo -e "║  Telegram бот для скачивания музыки с         ║"
echo -e "║  SoundCloud и Spotify                          ║"
echo -e "║                                                ║"
echo -e "╚════════════════════════════════════════════════╝"
echo -e "${NC}"

# Проверка прав суперпользователя
if [[ $EUID -ne 0 ]]; then
    print_warning "Этот скрипт рекомендуется запускать с правами суперпользователя"
    read -p "Продолжить без прав суперпользователя? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_error "Выполнение прервано. Запустите скрипт с правами суперпользователя"
        exit 1
    fi
fi

# Определение системы
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$NAME
elif [ -f /etc/lsb-release ]; then
    . /etc/lsb-release
    OS=$DISTRIB_ID
else
    OS=$(uname -s)
fi

print_message "Определена операционная система: $OS"

# Проверка требований
print_message "Проверка системных требований..."

# Проверка и установка Python
if ! command -v python3 &> /dev/null; then
    print_warning "Python 3 не установлен. Установка..."
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        apt-get update && apt-get install -y python3 python3-pip python3-venv
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"RedHat"* ]]; then
        yum install -y python3 python3-pip
    elif [[ "$OS" == *"Arch"* ]]; then
        pacman -S --noconfirm python python-pip
    else
        print_error "Невозможно определить метод установки Python для вашей ОС"
        exit 1
    fi
fi

# Проверка и установка Git
if ! command -v git &> /dev/null; then
    print_warning "Git не установлен. Установка..."
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        apt-get update && apt-get install -y git
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"RedHat"* ]]; then
        yum install -y git
    elif [[ "$OS" == *"Arch"* ]]; then
        pacman -S --noconfirm git
    else
        print_error "Невозможно определить метод установки Git для вашей ОС"
        exit 1
    fi
fi

# Проверка и установка FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    print_warning "FFmpeg не установлен. Установка..."
    if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
        apt-get update && apt-get install -y ffmpeg
    elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"RedHat"* ]]; then
        yum install -y epel-release
        yum install -y ffmpeg
    elif [[ "$OS" == *"Arch"* ]]; then
        pacman -S --noconfirm ffmpeg
    else
        print_error "Невозможно определить метод установки FFmpeg для вашей ОС"
        exit 1
    fi
fi

# Создание и настройка директории для бота
print_message "Настройка директории для бота..."
BOT_DIR="/opt/soundcloud-search-bot"
BOT_REPO="https://github.com/hxvisual/soundcloud-search-bot.git"

if [ -d "$BOT_DIR" ]; then
    print_warning "Директория $BOT_DIR уже существует"
    read -p "Удалить и создать заново? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$BOT_DIR"
    else
        print_error "Установка прервана. Директория уже существует"
        exit 1
    fi
fi

# Запрос данных для конфигурации
echo -e "${CYAN}"
echo -e "╔════════════════════════════════════════════════╗"
echo -e "║        НАСТРОЙКА ПАРАМЕТРОВ TELEGRAM БОТА      ║"
echo -e "╚════════════════════════════════════════════════╝"
echo -e "${NC}"

read -p "Введите Telegram Bot Token (от @BotFather): " BOT_TOKEN
read -p "Введите Spotify Client ID (из Spotify Developer Dashboard): " SPOTIFY_CLIENT_ID
read -p "Введите Spotify Client Secret (из Spotify Developer Dashboard): " SPOTIFY_CLIENT_SECRET

USERNAME=$(logname 2>/dev/null || echo $SUDO_USER || echo $USER)
USERGROUP=$(id -gn $USERNAME)

print_message "Клонирование основного репозитория..."
mkdir -p "$BOT_DIR"
git clone "$BOT_REPO" "$BOT_DIR"

print_message "Клонирование bare репозитория для автоматических обновлений..."
BARE_DIR="/opt/soundcloud-search-bot-bare"
git clone --bare "$BOT_REPO" "$BARE_DIR"

print_message "Настройка хука для автоматических обновлений..."
cat > "$BARE_DIR/hooks/post-receive" << 'EOF'
#!/bin/bash
git --work-tree=/opt/soundcloud-search-bot --git-dir=/opt/soundcloud-search-bot-bare checkout -f main
cd /opt/soundcloud-search-bot
# Активация виртуального окружения
source venv/bin/activate
# Обновление зависимостей
pip install -r requirements.txt
# Перезапуск бота
systemctl restart soundcloud-bot
EOF

chmod +x "$BARE_DIR/hooks/post-receive"

# Настройка прав доступа
print_message "Настройка прав доступа..."
chown -R "$USERNAME":"$USERGROUP" "$BOT_DIR" "$BARE_DIR"

# Создание виртуального окружения и установка зависимостей
print_message "Создание виртуального окружения и установка зависимостей..."
cd "$BOT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Создание файла окружения
print_message "Создание файла окружения (.env)..."
cat > "$BOT_DIR/.env" << EOF
BOT_TOKEN=$BOT_TOKEN
SPOTIFY_CLIENT_ID=$SPOTIFY_CLIENT_ID
SPOTIFY_CLIENT_SECRET=$SPOTIFY_CLIENT_SECRET
EOF

# Создание systemd сервиса
print_message "Создание systemd сервиса..."
cat > /etc/systemd/system/soundcloud-bot.service << EOF
[Unit]
Description=HX Music Telegram Bot
After=network.target

[Service]
User=$USERNAME
Group=$USERGROUP
WorkingDirectory=$BOT_DIR
ExecStart=$BOT_DIR/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=soundcloud-bot
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Настройка логов
print_message "Настройка логирования..."
mkdir -p /var/log/soundcloud-bot
chown "$USERNAME":"$USERGROUP" /var/log/soundcloud-bot

# Активация и запуск сервиса
print_message "Активация и запуск сервиса..."
systemctl daemon-reload
systemctl enable soundcloud-bot
systemctl start soundcloud-bot

print_success "Установка и настройка HX Music Bot успешно завершена!"
echo -e "Статус сервиса можно проверить командой: ${CYAN}systemctl status soundcloud-bot${NC}"
echo -e "Логи можно просмотреть командой: ${CYAN}journalctl -u soundcloud-bot -f${NC}"

# Инструкции для настройки GitHub Actions
echo -e "${YELLOW}"
echo -e "╔════════════════════════════════════════════════╗"
echo -e "║        НАСТРОЙКА АВТОМАТИЧЕСКИХ ОБНОВЛЕНИЙ     ║"
echo -e "╚════════════════════════════════════════════════╝"
echo -e "${NC}"

print_message "Для настройки автоматических обновлений через GitHub Actions:"
echo -e "1. Создайте SSH ключ на этом сервере командой: ${CYAN}ssh-keygen -t ed25519 -C 'github-actions'${NC}"
echo -e "2. Добавьте публичный ключ в authorized_keys: ${CYAN}cat ~/.ssh/id_ed25519.pub >> ~/.ssh/authorized_keys${NC}"
echo -e "3. Добавьте приватный ключ в GitHub репозиторий как секрет с именем SSH_PRIVATE_KEY"
echo -e "4. Добавьте следующие секреты в ваш GitHub репозиторий:"
echo -e "   - VPS_HOST: IP-адрес вашего сервера"
echo -e "   - VPS_USER: Имя пользователя на сервере (${CYAN}$USERNAME${NC})"

echo -e "${GREEN}"
echo -e "╔════════════════════════════════════════════════╗"
echo -e "║                                                ║"
echo -e "║              УСТАНОВКА ЗАВЕРШЕНА!              ║"
echo -e "║                                                ║"
echo -e "║  Бот запущен и готов к использованию!          ║"
echo -e "║  Проверьте Telegram бота: @hxmusic_robot       ║"
echo -e "║                                                ║"
echo -e "╚════════════════════════════════════════════════╝"
echo -e "${NC}" 