# 🎵 HX Music Bot

<div align="center">
  
  ![HX Music Bot Logo](https://raw.githubusercontent.com/hxvisual/soundcloud-search-bot/main/.github/assets/logo.png)

  <h3>🎧 Многофункциональный Telegram бот для поиска и скачивания музыки с SoundCloud и Spotify</h3>

  [![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue?style=for-the-badge&logo=python)](https://www.python.org/downloads/)
  [![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
  [![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI/CD-2088FF?style=for-the-badge&logo=github-actions)](https://github.com/features/actions)

</div>

## 📋 Содержание

- [✨ Возможности](#-возможности)
- [🖼️ Скриншоты](#️-скриншоты)
- [🔧 Технологии](#-технологии)
- [🚀 Установка и запуск](#-установка-и-запуск)
  - [Предварительные требования](#предварительные-требования)
  - [Установка](#установка)
  - [Настройка переменных окружения](#настройка-переменных-окружения)
  - [Запуск бота](#запуск-бота)
- [🔄 Автоматические обновления](#-автоматические-обновления)
- [⚙️ Конфигурация](#️-конфигурация)
- [📚 API-интеграции](#-api-интеграции)
- [📦 Структура проекта](#-структура-проекта)
- [🛠️ Разработка](#️-разработка)
- [🔨 Команды бота](#-команды-бота)
- [📄 Лицензия](#-лицензия)
- [👨‍💻 Контакты](#-контакты)

## ✨ Возможности

- **🔍 Мультиплатформенный поиск**: Поиск музыки на SoundCloud и Spotify в одном интерфейсе
- **🟠🟢 Цветовая кодировка**: Интуитивное разделение платформ (SoundCloud - 🟠, Spotify - 🟢)
- **📱 Удобный интерфейс**: Встроенные кнопки и пагинация для простой навигации
- **📊 Расширенные результаты**: Показывает исполнителя, название, длительность трека
- **🔄 Переключение платформ**: Мгновенное переключение между SoundCloud и Spotify
- **⬇️ Высокое качество**: Загрузка треков в высоком качестве (320 kbps)
- **🏷️ Метаданные**: Сохранение всех метаданных и обложек в ID3-тегах
- **🧩 Интеграция с YouTube**: Автоматический поиск треков на YouTube для скачивания со Spotify
- **🔀 Удобная пагинация**: Легкая навигация по большому количеству результатов поиска

## 🖼️ Скриншоты

<div align="center">
  <img src="https://raw.githubusercontent.com/hxvisual/soundcloud-search-bot/main/.github/assets/screenshot1.jpg" alt="Скриншот 1" width="30%">
  <img src="https://raw.githubusercontent.com/hxvisual/soundcloud-search-bot/main/.github/assets/screenshot2.jpg" alt="Скриншот 2" width="30%">
  <img src="https://raw.githubusercontent.com/hxvisual/soundcloud-search-bot/main/.github/assets/screenshot3.jpg" alt="Скриншот 3" width="30%">
</div>

## 🔧 Технологии

- **🐍 Python 3.9+**: Основной язык программирования
- **🤖 Aiogram 3.x**: Фреймворк для разработки Telegram-ботов
- **🎵 FFmpeg**: Обработка аудио и сохранение метаданных
- **🔍 API SoundCloud**: Поиск и загрузка треков с SoundCloud
- **🟢 API Spotify**: Поиск и получение метаданных треков в Spotify
- **📺 YouTube**: Загрузка аудио для треков Spotify через YouTube
- **🐳 Docker**: Контейнеризация для простого развертывания
- **🔄 GitHub Actions**: Автоматическое развертывание

## 🚀 Установка и запуск

### Предварительные требования

- **Python 3.9+**
- **FFmpeg** (установлено и доступно в системе)
- **Telegram Bot Token** (получен от @BotFather)
- **Spotify API ключи** (для поиска в Spotify)

### Установка

#### Метод 1: Использование скрипта автоматической установки

```bash
curl -sSL https://raw.githubusercontent.com/hxvisual/soundcloud-search-bot/main/deploy.sh | bash
# или
wget -qO- https://raw.githubusercontent.com/hxvisual/soundcloud-search-bot/main/deploy.sh | bash
```

#### Метод 2: Ручная установка

1. Клонируйте репозиторий:
```bash
git clone https://github.com/hxvisual/soundcloud-search-bot.git
cd soundcloud-search-bot
```

2. Создайте и активируйте виртуальное окружение:
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Установите FFmpeg (если еще не установлено):
```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y ffmpeg

# Arch Linux
sudo pacman -S ffmpeg

# macOS с использованием Homebrew
brew install ffmpeg

# Windows с использованием Chocolatey
choco install ffmpeg
```

### Настройка переменных окружения

Создайте файл `.env` в корневой директории проекта со следующим содержимым:

```
BOT_TOKEN=ваш_токен_бота_telegram
SPOTIFY_CLIENT_ID=ваш_client_id_spotify
SPOTIFY_CLIENT_SECRET=ваш_client_secret_spotify
```

### Запуск бота

```bash
python main.py
```

## 🔄 Автоматические обновления

Бот поддерживает автоматические обновления с использованием GitHub Actions.

### Настройка на сервере:

1. Клонируйте репозиторий с флагом `--bare`:
```bash
git clone --bare https://github.com/hxvisual/soundcloud-search-bot.git /opt/soundcloud-search-bot-bare
```

2. Настройте хук для автоматического обновления:
```bash
cd /opt/soundcloud-search-bot-bare
cat > hooks/post-receive << 'EOF'
#!/bin/bash
git --work-tree=/opt/soundcloud-search-bot --git-dir=/opt/soundcloud-search-bot-bare checkout -f main
cd /opt/soundcloud-search-bot
# Перезапуск бота
systemctl restart soundcloud-bot
EOF
chmod +x hooks/post-receive
```

3. Настройте GitHub Actions в вашем репозитории (см. файл `.github/workflows/deploy.yml`)

## ⚙️ Конфигурация

### Системная служба (systemd)

Для автоматического запуска бота при перезагрузке сервера, создайте systemd-сервис:

```bash
sudo nano /etc/systemd/system/soundcloud-bot.service
```

Содержимое:

```
[Unit]
Description=HX Music Telegram Bot
After=network.target

[Service]
User=your_username
Group=your_group
WorkingDirectory=/opt/soundcloud-search-bot
ExecStart=/opt/soundcloud-search-bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=soundcloud-bot
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Активация сервиса:

```bash
sudo systemctl enable soundcloud-bot
sudo systemctl start soundcloud-bot
```

## 📚 API-интеграции

### SoundCloud API

Бот использует неофициальный API SoundCloud для поиска и загрузки треков. API-интеграция реализована в файле `api/soundcloud_api.py`.

### Spotify API

Для интеграции со Spotify используется официальный Web API. Для использования требуются Client ID и Client Secret, которые можно получить в [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).

### YouTube API

Для загрузки аудио треков со Spotify используется интеграция с YouTube, которая ищет соответствующие треки и загружает их аудио. Реализация находится в файле `api/youtube_api.py`.

## 📦 Структура проекта

```
soundcloud-search-bot/
├── .github/
│   ├── workflows/
│   │   └── deploy.yml
│   └── assets/
│       ├── logo.png
│       └── screenshots/
├── api/
│   ├── soundcloud_api.py
│   ├── spotify_api.py
│   └── youtube_api.py
├── utils/
│   └── logger.py
├── .env
├── config.py
├── handlers.py
├── main.py
├── requirements.txt
├── deploy.sh
└── README.md
```

## 🛠️ Разработка

### Добавление новых платформ

Для добавления новой платформы:

1. Создайте новый класс API-клиента в директории `api/`
2. Добавьте инициализацию клиента в файле `handlers.py`
3. Добавьте новую платформу в функцию `get_platform_selection_keyboard()`
4. Добавьте обработчик поиска и загрузки по аналогии с существующими платформами

### Стиль кода

Проект следует стандарту PEP 8. Вы можете использовать `flake8` для проверки кода:

```bash
pip install flake8
flake8 .
```

## 🔨 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начать работу с ботом и получить приветственное сообщение |
| `/search <запрос>` | Выполнить поиск по указанному запросу |
| [Любой текст] | Поиск музыки по введенному тексту |

## 📄 Лицензия

Проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

## 👨‍💻 Контакты

- **Автор:** [@crypthx](https://t.me/crypthx)
- **Поддержка бота:** [@hxmusic_robot](https://t.me/hxmusic_robot) 