import os
import logging
import tempfile
import time
import html
import re
import subprocess
import shutil
from aiogram import types, Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile, InputMediaAudio, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from api.soundcloud_api import SoundCloudClient
from api.spotify_api import SpotifyClient
from api.youtube_api import YouTubeClient
from utils.logger import setup_logger

logger = setup_logger(__name__, log_to_file=False)

router = Router()

sc_client = SoundCloudClient()
spotify_client = SpotifyClient()
youtube_client = YouTubeClient()

class SearchStates(StatesGroup):
    waiting_for_query = State()
    select_platform = State()
    select_track = State()

TRACKS_PER_PAGE = 5
MAX_CAPTION_LENGTH = 1024

def escape_html(text):
    if not text:
        return ""
    return html.escape(str(text))

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Эмодзи для оформления
    music_emoji = "🎵"
    sound_emoji = "🟠"
    spotify_emoji = "🟢"
    download_emoji = "⬇️"
    search_emoji = "🔍"
    star_emoji = "⭐"
    info_emoji = "ℹ️"
    support_emoji = "👨‍💻"
    
    # Создаем клавиатуру с кнопками для быстрого начала работы
    builder = InlineKeyboardBuilder()
    
    # Кнопка для связи с поддержкой (замените на актуальный юзернейм)
    builder.row(
        types.InlineKeyboardButton(
            text=f"{support_emoji} Связаться с поддержкой", 
            url="https://t.me/crypthx"
        )
    )
    
    # Формируем приветственное сообщение с HTML-форматированием
    welcome_text = f"""
<b>{music_emoji} HX MUSIC BOT {music_emoji}</b>

{star_emoji} <b>Поиск и скачивание музыки с разных платформ</b> {star_emoji}

Привет! Я помогу тебе найти и скачать твои любимые треки c {sound_emoji} <b>SoundCloud</b> и {spotify_emoji} <b>Spotify</b>.

<b>{info_emoji} КАК ПОЛЬЗОВАТЬСЯ:</b>

<b>1.</b> Просто напиши название трека или имя исполнителя
<b>2.</b> Выбери платформу для поиска (SoundCloud или Spotify)
<b>3.</b> Выбери нужный трек из результатов поиска
<b>4.</b> Получи трек прямо в Telegram!

<b>{star_emoji} ПРЕИМУЩЕСТВА:</b>

{download_emoji} Высокое качество аудио (320 kbps)
{download_emoji} Сохранение метаданных и обложек треков
{download_emoji} Удобная навигация и поиск

<b>{support_emoji} ПОДДЕРЖКА:</b>

Если у тебя возникли вопросы или нужна помощь - обращайся к @crypthx

<i>Начни поиск прямо сейчас - просто напиши название трека!</i>
"""
    
    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

async def show_help_message(message: types.Message):
    await message.answer(
        "🎵 <b>Как пользоваться ботом:</b>\n\n"
        "• /start - Перезапустить бота\n\n"
        "• Просто напишите название трека или имя исполнителя, и я найду его для вас.\n"
        "• Выберите платформу для поиска (SoundCloud или Spotify).\n"
        "• Выберите трек из списка, нажав на соответствующую кнопку с номером.\n"
        "• Ожидайте загрузки трека - это может занять некоторое время в зависимости от размера файла.\n\n"
        "⚠️ <b>Примечание:</b> Для треков со Spotify используется поиск и загрузка через YouTube.",
        parse_mode="HTML"
    )

@router.message(Command("search"))
async def cmd_search(message: types.Message, command: CommandObject, state: FSMContext):
    if command.args:
        # Show search message with platform options in the same message
        search_msg = await message.answer(f"🔍 Поиск: <b>{escape_html(command.args)}</b>\n\nВыберите платформу:", 
                                          parse_mode="HTML",
                                          reply_markup=get_platform_selection_keyboard())
        
        # Store data for future use
        await state.update_data(
            query=command.args,
            search_message_id=search_msg.message_id
        )
        await state.set_state(SearchStates.select_platform)
    else:
        await message.answer("Пожалуйста, введите название трека или имя исполнителя, которое вы хотите найти:")
        await state.set_state(SearchStates.waiting_for_query)

@router.message(SearchStates.waiting_for_query)
async def process_search_query(message: types.Message, state: FSMContext):
    query = message.text.strip()
    if not query:
        await message.answer("Пожалуйста, введите запрос для поиска.")
        return
        
    # Show search message with platform options in the same message
    search_msg = await message.answer(f"🔍 Поиск: <b>{escape_html(query)}</b>\n\nВыберите платформу:", 
                                     parse_mode="HTML",
                                     reply_markup=get_platform_selection_keyboard())
    
    # Store data for future use
    await state.update_data(
        query=query,
        search_message_id=search_msg.message_id
    )
    await state.set_state(SearchStates.select_platform)

def get_platform_selection_keyboard():
    """Create platform selection keyboard with colored emoji"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🟠 SoundCloud", callback_data="platform_soundcloud"),
        types.InlineKeyboardButton(text="🟢 Spotify", callback_data="platform_spotify")
    )
    return builder.as_markup()

@router.callback_query(SearchStates.select_platform, F.data.startswith("platform_"))
async def process_platform_selection(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    platform = callback_query.data.split("_")[1]
    data = await state.get_data()
    query = data.get("query", "")
    
    # Show loading in the same message
    platform_name = "SoundCloud" if platform == "soundcloud" else "Spotify"
    platform_emoji = "🟠" if platform == "soundcloud" else "🟢"
    
    await callback_query.message.edit_text(
        f"🔍 Ищу на {platform_emoji} {platform_name}: <b>{escape_html(query)}</b>...",
        parse_mode="HTML"
    )
    
    # Search based on selected platform
    tracks = []
    if platform == "soundcloud":
        tracks = sc_client.search_tracks(query, limit=20)
    elif platform == "spotify":
        tracks = spotify_client.search_tracks(query, limit=20)
    
    if not tracks:
        # Show no results but keep platform selection buttons
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="🟠 SoundCloud", callback_data="platform_soundcloud"),
            types.InlineKeyboardButton(text="🟢 Spotify", callback_data="platform_spotify")
        )
        
        await callback_query.message.edit_text(
            f"❌ Ничего не найдено на {platform_emoji} {platform_name} по запросу: <b>{escape_html(query)}</b>\n\n"
            f"Попробуйте поискать на другой платформе или измените запрос.",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        return
    
    await state.update_data(tracks=tracks, current_page=0, platform=platform)
    
    # Show results in the same message
    await show_tracks_page(callback_query.message, state)

async def show_tracks_page(message: types.Message, state: FSMContext):
    data = await state.get_data()
    tracks = data.get("tracks", [])
    current_page = data.get("current_page", 0)
    platform = data.get("platform", "soundcloud")
    total_tracks = len(tracks)
    
    start_idx = current_page * TRACKS_PER_PAGE
    end_idx = min(start_idx + TRACKS_PER_PAGE, total_tracks)
    current_tracks = tracks[start_idx:end_idx]
    
    track_list = []
    
    for i, track in enumerate(current_tracks):
        # Handle duration formatting differently for each platform
        if platform == "spotify":
            # Spotify uses milliseconds
            duration_ms = int(track.get("duration", 0))
            duration_sec = duration_ms // 1000
        else:
            # SoundCloud uses milliseconds too
            duration_sec = int(track.get("duration", 0) / 1000)
            
        duration_min = duration_sec // 60
        duration_sec = duration_sec % 60
        
        user_info = track.get('user', '')
        username = ''
        
        if isinstance(user_info, dict):
            username = user_info.get('username', 'Unknown')
        else:
            username = str(user_info)
        
        title = track.get('title', 'Untitled')
        
        safe_username = escape_html(username)
        safe_title = escape_html(title)
        
        # Removed platform emoji from individual tracks
        track_list.append(
            f"{start_idx + i + 1}. <b>{safe_username}</b> - {safe_title} ({duration_min}:{duration_sec:02d})"
        )
    
    builder = InlineKeyboardBuilder()
    
    number_buttons = []
    for i in range(len(current_tracks)):
        number_buttons.append(types.InlineKeyboardButton(
            text=f"{start_idx + i + 1}",
            callback_data=f"track_{start_idx + i}"
        ))
    
    builder.row(*number_buttons)
    
    pagination_buttons = []
    
    if current_page > 0:
        pagination_buttons.append(types.InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="page_prev"
        ))
    
    total_pages = (total_tracks + TRACKS_PER_PAGE - 1) // TRACKS_PER_PAGE
    pagination_buttons.append(types.InlineKeyboardButton(
        text=f"Стр. {current_page + 1}/{total_pages}",
        callback_data="page_info"
    ))
    
    if end_idx < total_tracks:
        pagination_buttons.append(types.InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data="page_next"
        ))
    
    builder.row(*pagination_buttons)
    
    # Add button to switch directly to the alternative platform
    alt_platform = "spotify" if platform == "soundcloud" else "soundcloud"
    alt_platform_name = "Spotify" if alt_platform == "spotify" else "SoundCloud"
    builder.row(types.InlineKeyboardButton(
        text=f"Поменять на {alt_platform_name}",
        callback_data=f"direct_change_{alt_platform}"
    ))
    
    query = data.get("query", "")
    safe_query = escape_html(query)
    
    # Add platform emoji to the platform name in the header
    platform_emoji = "🟠" if platform == "soundcloud" else "🟢"
    platform_name = "SoundCloud" if platform == "soundcloud" else "Spotify"
    
    text = f"🎵 Результаты поиска на {platform_emoji} {platform_name}: <b>{safe_query}</b>\n" \
           f"Показаны треки {start_idx + 1}-{end_idx} из {total_tracks}\n\n" \
           f"{'\n'.join(track_list)}"
    
    try:
        await message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except TelegramBadRequest as e:
        logger.error(f"Error editing message: {e}")
        new_message = await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.update_data(search_message_id=new_message.message_id)
    
    await state.set_state(SearchStates.select_track)

@router.callback_query(F.data.startswith("direct_change_"))
async def direct_change_platform(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    new_platform = callback_query.data.split("_")[2]
    data = await state.get_data()
    query = data.get("query", "")
    
    # Show loading message
    platform_name = "SoundCloud" if new_platform == "soundcloud" else "Spotify"
    platform_emoji = "🟠" if new_platform == "soundcloud" else "🟢"
    
    await callback_query.message.edit_text(
        f"🔍 Ищу на {platform_emoji} {platform_name}: <b>{escape_html(query)}</b>...",
        parse_mode="HTML"
    )
    
    # Search on the new platform
    tracks = []
    if new_platform == "soundcloud":
        tracks = sc_client.search_tracks(query, limit=20)
    elif new_platform == "spotify":
        tracks = spotify_client.search_tracks(query, limit=20)
    
    if not tracks:
        # Show platform selection buttons again
        builder = InlineKeyboardBuilder()
        alt_platform = "spotify" if new_platform == "soundcloud" else "soundcloud"
        alt_platform_name = "Spotify" if alt_platform == "spotify" else "SoundCloud"
        
        builder.row(
            types.InlineKeyboardButton(
                text=f"Поменять на {alt_platform_name}", 
                callback_data=f"direct_change_{alt_platform}"
            )
        )
        
        await callback_query.message.edit_text(
            f"❌ Ничего не найдено на {platform_emoji} {platform_name} по запросу: <b>{escape_html(query)}</b>\n\n"
            f"Попробуйте поискать на другой платформе или измените запрос.",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        return
    
    # Update state with new platform and tracks
    await state.update_data(
        platform=new_platform,
        tracks=tracks,
        current_page=0
    )
    
    # Show results
    await show_tracks_page(callback_query.message, state)

@router.callback_query(F.data == "change_platform")
async def change_platform(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    data = await state.get_data()
    query = data.get("query", "")
    
    # Show platform selection in the same message
    await callback_query.message.edit_text(
        f"🔍 Поиск: <b>{escape_html(query)}</b>\n\nВыберите платформу:",
        parse_mode="HTML",
        reply_markup=get_platform_selection_keyboard()
    )
    
    await state.set_state(SearchStates.select_platform)

@router.callback_query(F.data == "page_prev")
async def process_previous_page(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    data = await state.get_data()
    current_page = data.get("current_page", 0)
    
    if current_page > 0:
        await state.update_data(current_page=current_page - 1)
        
        await show_tracks_page(callback_query.message, state)

@router.callback_query(F.data == "page_next")
async def process_next_page(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    data = await state.get_data()
    current_page = data.get("current_page", 0)
    tracks = data.get("tracks", [])
    total_tracks = len(tracks)
    total_pages = (total_tracks + TRACKS_PER_PAGE - 1) // TRACKS_PER_PAGE
    
    if current_page < total_pages - 1:
        await state.update_data(current_page=current_page + 1)
        
        await show_tracks_page(callback_query.message, state)

@router.callback_query(F.data == "page_info")
async def process_page_info(callback_query: types.CallbackQuery):
    await callback_query.answer("Информация о текущей странице")

@router.callback_query(SearchStates.select_track, F.data.startswith("track_"))
async def process_track_selection(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.answer()
    
    track_index = int(callback_query.data.split("_")[1])
    
    data = await state.get_data()
    tracks = data.get("tracks", [])
    platform = data.get("platform", "soundcloud")
    
    if track_index >= len(tracks):
        await callback_query.message.answer("❌ Ошибка: Трек не найден. Пожалуйста, попробуйте снова.")
        return
        
    selected_track = tracks[track_index]
    
    user_info = selected_track.get('user', '')
    username = ''
    
    if isinstance(user_info, dict):
        username = user_info.get('username', 'Unknown')
    else:
        username = str(user_info)
    
    track_title = selected_track.get('title', 'Untitled')
    
    safe_username = escape_html(username)
    safe_title = escape_html(track_title)
    
    platform_emoji = "🟠" if platform == "soundcloud" else "🟢"
    platform_name = "SoundCloud" if platform == "soundcloud" else "Spotify"
    
    logger.info(f"🎵 Выбран трек: {username} - {track_title} на платформе {platform}")
    
    await callback_query.message.edit_text(
        f"⏳ Обрабатываю трек:\n"
        f"<b>{safe_username}</b> - {safe_title}",
        parse_mode="HTML"
    )
    
    track_url = selected_track.get("permalink_url")
    logger.info(f"🔗 URL трека: {track_url}")
    
    # Get download URL based on platform
    download_url = None
    track_data = None
    youtube_used = False
    
    if platform == "soundcloud":
        download_url, track_data = sc_client.get_track_download_url(track_url)
    elif platform == "spotify":
        # Try to get Spotify download URL first (for metadata)
        download_url, track_data = spotify_client.get_track_download_url(track_url)
        
        # Always use YouTube for Spotify tracks
        # Формируем более точный поисковый запрос с отдельной передачей исполнителя и названия
        # Не обновляем сообщение, оставляем "Обрабатываю трек"
        
        # Передаем исполнителя и название отдельно для более точного поиска
        youtube_url = youtube_client.search_on_youtube(
            f"{username} - {track_title}",  # Для совместимости оставляем полный запрос
            artist=username,                # Передаем исполнителя отдельно
            title=track_title               # Передаем название отдельно
        )
        
        if youtube_url:
            download_url = youtube_url
            youtube_used = True
            logger.info(f"YouTube URL для Spotify трека: {youtube_url}")
        else:
            logger.error(f"Не удалось найти трек на YouTube: {f"{username} - {track_title}"}")
            await callback_query.message.edit_text(
                f"❌ Не удалось найти трек на YouTube.\n"
                f"Попробуйте другой трек или платформу.",
                parse_mode="HTML"
            )
            return
    
    if not download_url:
        await callback_query.message.edit_text(
            f"❌ Не удалось получить ссылку для скачивания этого трека.\n"
            f"Пожалуйста, попробуйте другой трек или платформу.",
            parse_mode="HTML"
        )
        return
    
    # создаем временный каталог для работы с файлами
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_filename = None
        
        try:
            temp_filename = os.path.join(temp_dir, "audio.mp3")
            
            logger.info(f"📁 Создан временный файл: {temp_filename}")
            
            merged_track_data = track_data or selected_track
            
            if track_data and selected_track:
                for key, value in selected_track.items():
                    if key not in track_data or not track_data.get(key):
                        merged_track_data[key] = value
                        
            logger.info(f"Merged track data available: {bool(merged_track_data)}")
            
            # Download track based on platform
            download_success = False
            processed_with_ffmpeg = False
            
            if platform == "soundcloud":
                download_success = sc_client.download_track(download_url, merged_track_data, temp_filename)
            elif platform == "spotify" and youtube_used:
                try:
                    # Подготовка расширенных метаданных из Spotify
                    # Получаем данные из Spotify API для альбома
                    album_name = ""
                    artwork_url = ""
                    release_year = ""
                    
                    # Обработка метаданных альбома
                    album_data = merged_track_data.get('album', {})
                    if isinstance(album_data, dict):
                        album_name = album_data.get('name', '')
                        
                        # Получаем обложку альбома
                        images = album_data.get('images', [])
                        if images and len(images) > 0 and isinstance(images[0], dict):
                            artwork_url = images[0].get('url', '')
                        
                        # Получаем год выпуска
                        release_date = album_data.get('release_date', '')
                        if release_date and isinstance(release_date, str):
                            # Берем только год из даты (первые 4 символа)
                            release_year = release_date[:4] if len(release_date) >= 4 else ''
                    
                    # Формируем упрощенные метаданные для передачи
                    metadata = {
                        'title': track_title,
                        'artist': username,
                        'album': album_name,
                        'artwork_url': artwork_url,
                        'release_year': release_year,
                        'track_number': merged_track_data.get('track_number', ''),
                        'genre': '' # Spotify API не предоставляет напрямую жанр
                    }
                    
                    logger.info(f"Подготовлены метаданные: Название={metadata['title']}, Исполнитель={metadata['artist']}, Альбом={metadata['album']}")
                    
                    # Скачиваем сначала во временный файл
                    temp_yt_file = os.path.join(temp_dir, "youtube_audio.mp3")
                    download_success = youtube_client.download_from_youtube(download_url, temp_yt_file, metadata)
                    
                    if download_success:
                        # Обрабатываем через ffmpeg для обеспечения совместимости и улучшения качества
                        processed_with_ffmpeg = process_with_ffmpeg(temp_yt_file, temp_filename, metadata)
                        if processed_with_ffmpeg:
                            logger.info(f"✅ Трек успешно обработан через FFmpeg")
                        else:
                            # Если ffmpeg обработка не удалась, используем исходный файл
                            shutil.copy(temp_yt_file, temp_filename)
                            logger.warning(f"⚠️ Обработка через FFmpeg не удалась, используем исходный файл")
                except Exception as e:
                    logger.error(f"Ошибка при подготовке метаданных: {e}")
                    # Попытка загрузки с минимальными метаданными если возникла ошибка
                    simple_metadata = {
                        'title': track_title,
                        'artist': username
                    }
                    download_success = youtube_client.download_from_youtube(download_url, temp_filename, simple_metadata)
            elif platform == "spotify":
                download_success = spotify_client.download_track(download_url, merged_track_data, temp_filename)
            
            if not download_success:
                await callback_query.message.edit_text(
                    f"❌ Не удалось скачать трек. Пожалуйста, попробуйте другой трек.",
                    parse_mode="HTML"
                )
                return
            
            user = merged_track_data.get("user", "") if merged_track_data else ""
            title = merged_track_data.get("title", "") if merged_track_data else ""
            
            if isinstance(user, dict):
                user = user.get("username", "")
            
            user = str(user).replace('<', '').replace('>', '').replace('&', '').replace('"', '').replace("'", "")
            title = str(title).replace('<', '').replace('>', '').replace('&', '').replace('"', '').replace("'", "")
            
            if user and title:
                clean_title = f"{user} - {title} @hxmusic_robot"
            else:
                clean_title = "music_track @hxmusic_robot"
            
            clean_title = "".join(c for c in clean_title if c.isalnum() or c in " -_.")
            logger.info(f"📋 Подготовлено имя файла: {clean_title}.mp3")
            
            # Create caption with link to the bot (removed platform information)
            caption = "👉 <a href='https://t.me/hxmusic_robot'>Ищи свои любимые треки в боте</a> 👈"
            
            file_size = os.path.getsize(temp_filename)
            max_telegram_size = 50 * 1024 * 1024
            
            if file_size > max_telegram_size:
                await callback_query.message.edit_text(
                    f"❌ Файл слишком большой для отправки в Telegram ({file_size / (1024 * 1024):.2f} МБ).\n"
                    f"Максимальный размер файла: {max_telegram_size / (1024 * 1024):.2f} МБ",
                    parse_mode="HTML"
                )
                return
            
            logger.info(f"📊 Размер файла: {file_size / (1024 * 1024):.2f} МБ")
            
            try:
                audio = FSInputFile(temp_filename, filename=f"{clean_title}.mp3")
                logger.info(f"📤 Отправляем аудиофайл пользователю...")
                
                # Добавляем заголовок и исполнителя для корректного отображения в Telegram
                media = InputMediaAudio(
                    media=audio,
                    caption=caption,
                    parse_mode="HTML",
                    title=title,
                    performer=user
                )
                
                try:
                    logger.debug(f"Пробуем обновить сообщение с аудио")
                    await callback_query.message.edit_media(media=media)
                    logger.info(f"✅ Сообщение успешно обновлено с аудио")
                except TelegramBadRequest as e:
                    error_msg = str(e).lower()
                    logger.warning(f"⚠️ Ошибка Telegram при обновлении: {error_msg}")
                    
                    logger.info(f"⚠️ Не удалось обновить сообщение, отправляем новое")
                    
                    try:
                        await callback_query.message.delete()
                    except Exception:
                        pass
                    
                    await callback_query.message.answer_audio(
                        audio=audio,
                        caption=caption,
                        parse_mode="HTML",
                        title=title,
                        performer=user
                    )
                    logger.info(f"✅ Отправлено новое сообщение с аудио")
                    
            except Exception as e:
                error_text = str(e).lower()
                logger.error(f"❌ Ошибка при обновлении сообщения: {e}")
                
                if "too large" in error_text or "entity too large" in error_text:
                    logger.error(f"❌ Файл слишком большой для отправки: {error_text}")
                    try:
                        await callback_query.message.delete()
                    except Exception:
                        pass
                    
                    await callback_query.message.answer(
                        f"❌ Файл слишком большой для отправки в Telegram.\n"
                        f"Ошибка: {error_text}",
                        parse_mode="HTML"
                    )
                else:
                    logger.info(f"⚠️ Используем запасной метод отправки")
                    
                    try:
                        await callback_query.message.answer_audio(
                            audio=audio,
                            caption=caption,
                            parse_mode="HTML",
                            title=title,
                            performer=user
                        )
                        logger.info(f"✅ Успешно отправлено с использованием запасного метода")
                    except Exception as e2:
                        logger.error(f"❌ Финальная ошибка при отправке аудио: {e2}")
                        await callback_query.message.answer(f"❌ Не удалось отправить файл: {e2}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при обработке трека: {e}")
            await callback_query.message.edit_text(f"❌ Произошла ошибка при обработке трека: {e}")
        
    # Temporary directory will be automatically cleaned up after this block

def process_with_ffmpeg(input_file, output_file, metadata):
    """Обработка аудиофайла через FFmpeg с добавлением метаданных"""
    try:
        if not os.path.exists(input_file):
            logger.error(f"Входной файл не найден: {input_file}")
            return False
            
        # Базовые параметры FFmpeg
        cmd = [
            "ffmpeg",
            "-i", input_file,
            "-codec:a", "libmp3lame",
            "-q:a", "0",       # Лучшее качество MP3
            "-map_metadata", "0",  # Сохранить исходные метаданные
        ]
        
        # Добавляем метаданные если они доступны
        if metadata:
            if metadata.get('title'):
                cmd.extend(["-metadata", f"title={metadata['title']}"])
            if metadata.get('artist'):
                cmd.extend(["-metadata", f"artist={metadata['artist']}"])
            if metadata.get('album'):
                cmd.extend(["-metadata", f"album={metadata['album']}"])
            if metadata.get('release_year'):
                cmd.extend(["-metadata", f"date={metadata['release_year']}"])
            if metadata.get('track_number'):
                cmd.extend(["-metadata", f"track={metadata['track_number']}"])
            if metadata.get('genre'):
                cmd.extend(["-metadata", f"genre={metadata['genre']}"])
        
        # Добавляем выходной файл
        cmd.append(output_file)
        
        logger.info(f"Запуск FFmpeg: {' '.join(cmd)}")
        
        # Запускаем FFmpeg
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Ошибка FFmpeg: {stderr}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при обработке FFmpeg: {e}")
        return False

@router.message()
async def handle_text_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state == SearchStates.waiting_for_query.state:
        await process_search_query(message, state)
    else:
        query = message.text.strip()
        if query:
            # Show search message with platform options in the same message
            search_msg = await message.answer(f"🔍 Поиск: <b>{escape_html(query)}</b>\n\nВыберите платформу:", 
                                            parse_mode="HTML",
                                            reply_markup=get_platform_selection_keyboard())
            
            # Store data for future use
            await state.update_data(
                query=query,
                search_message_id=search_msg.message_id
            )
            await state.set_state(SearchStates.select_platform)