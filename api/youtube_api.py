import re
import os
import subprocess
import logging
import tempfile
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TCON, TRCK, TYER, COMM
from config import USER_AGENT
from utils.logger import setup_logger

logger = setup_logger(__name__, log_to_file=False)

class YouTubeClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
    
    def search_on_youtube(self, query, artist=None, title=None):
        """Search for a track on YouTube Music and return the video URL"""
        try:
            # Если переданы отдельно исполнитель и название, формируем более точный запрос
            if artist and title:
                # Формируем несколько вариантов поисковых запросов для лучшего результата
                search_queries = [
                    f"{artist} - {title} audio",
                    f"{artist} - {title} official audio",
                    f"{artist} {title} lyrics",
                    f"{artist} {title} official"
                ]
            else:
                search_queries = [
                    f"{query} audio",
                    f"{query} official audio",
                    f"{query} lyrics"
                ]
            
            # Пробуем каждый запрос по очереди, пока не найдем подходящий результат
            all_video_ids = []
            
            for search_query in search_queries:
                logger.info(f"Поиск на YouTube Music: {search_query}")
                
                # Используем YouTube Music вместо обычного YouTube
                encoded_query = quote(search_query)
                search_url = f"https://music.youtube.com/search?q={encoded_query}"
                
                try:
                    response = self.session.get(search_url)
                    response.raise_for_status()
                    
                    # Извлекаем ID видео из результатов поиска
                    html_content = response.text
                    
                    # Пробуем найти видео ID в YouTube Music
                    video_ids = re.findall(r"videoId\":\"(\w{11})\"", html_content)
                    if video_ids:
                        all_video_ids.extend(video_ids)
                except Exception as e:
                    logger.warning(f"Ошибка при поиске на YouTube Music: {e}")
                
                # Пробуем также на обычном YouTube
                try:
                    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
                    response = self.session.get(search_url)
                    response.raise_for_status()
                    
                    # Извлекаем все видео ID
                    youtube_ids = re.findall(r"watch\?v=(\S{11})", response.text)
                    if youtube_ids:
                        all_video_ids.extend(youtube_ids)
                except Exception as e:
                    logger.warning(f"Ошибка при поиске на обычном YouTube: {e}")
            
            # Убираем дубликаты
            all_video_ids = list(dict.fromkeys(all_video_ids))
            
            if not all_video_ids:
                logger.error(f"Не найдено результатов для запросов")
                return None
            
            # Проверяем каждое видео на доступность и возрастные ограничения
            for video_id in all_video_ids[:5]:  # Проверяем только первые 5 результатов
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                
                # Пробуем получить информацию о видео, чтобы проверить наличие ограничений
                try:
                    info_cmd = ["yt-dlp", "--skip-download", "--print", "title", youtube_url]
                    process = subprocess.Popen(
                        info_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate()
                    
                    # Если удалось получить информацию без ошибок, значит видео доступно
                    if process.returncode == 0 and not "age" in stderr.lower():
                        logger.info(f"Найдено доступное видео: {youtube_url}")
                        return youtube_url
                except Exception as e:
                    logger.warning(f"Ошибка при проверке видео {video_id}: {e}")
            
            # Если не нашли подходящего видео без возрастных ограничений, 
            # возвращаем первое найденное (будем пробовать скачать его другими методами)
            youtube_url = f"https://www.youtube.com/watch?v={all_video_ids[0]}"
            logger.info(f"Возвращаем лучший доступный результат: {youtube_url}")
            return youtube_url
            
        except Exception as e:
            logger.error(f"Ошибка при поиске на YouTube: {e}")
            return None
    
    def download_from_youtube(self, youtube_url, output_file, metadata=None):
        """Download audio from YouTube using youtube-dl or yt-dlp"""
        try:
            # Create temporary directory for the download
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file = os.path.join(temp_dir, "audio.mp3")
                
                # First check if yt-dlp is available (preferred)
                ytdlp_available = self._check_command_available("yt-dlp")
                youtube_dl_available = self._check_command_available("youtube-dl")
                
                if not (ytdlp_available or youtube_dl_available):
                    logger.error("Neither yt-dlp nor youtube-dl is available on the system!")
                    return False
                
                # Пробуем разные подходы для скачивания
                download_approaches = [
                    # Подход 1: Стандартный подход с аргументами для обхода ограничений
                    {
                        "name": "Стандартный подход",
                        "cmd_extra": [
                            "--age-limit", "21",
                            "--no-check-certificate", 
                            "--ignore-errors",
                        ]
                    },
                    # Подход 2: Использование альтернативного URL через прокси-сервис
                    {
                        "name": "Альтернативный URL через yewtu.be",
                        "url_transform": lambda url: re.sub(
                            r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})",
                            r"https://yewtu.be/watch?v=\1",
                            url
                        )
                    },
                    # Подход 3: Использование Piped - альтернативный клиент YouTube
                    {
                        "name": "Piped клиент",
                        "url_transform": lambda url: re.sub(
                            r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})",
                            r"https://piped.video/watch?v=\1",
                            url
                        )
                    },
                    # Подход 4: Использование инвидио
                    {
                        "name": "Invidious клиент",
                        "url_transform": lambda url: re.sub(
                            r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})",
                            r"https://invidious.snopyta.org/watch?v=\1",
                            url
                        )
                    },
                    # Подход 5: Последняя попытка - использование --force-ipv4
                    {
                        "name": "Принудительный IPv4",
                        "cmd_extra": [
                            "--force-ipv4",
                            "--age-limit", "21",
                            "--ignore-errors",
                        ]
                    }
                ]
                
                # Перебираем все подходы
                for approach_idx, approach in enumerate(download_approaches):
                    try:
                        # Command for downloading (prefer yt-dlp, fallback to youtube-dl)
                        cmd = ["yt-dlp"] if ytdlp_available else ["youtube-dl"]
                        cmd.extend([
                            "-x", "--audio-format", "mp3",
                            "--audio-quality", "0",      # Best quality
                            "--embed-thumbnail",         # Embed thumbnail if available
                            "--add-metadata",            # Add metadata from YouTube
                            "--no-playlist",             # Не скачивать плейлист, только видео
                        ])
                        
                        # Добавляем дополнительные аргументы, если они есть
                        if "cmd_extra" in approach:
                            cmd.extend(approach["cmd_extra"])
                        
                        # Преобразуем URL если нужно
                        current_url = youtube_url
                        if "url_transform" in approach:
                            current_url = approach["url_transform"](youtube_url)
                        
                        # Добавляем выходной файл и URL
                        current_temp_file = os.path.join(temp_dir, f"audio_{approach_idx}.mp3")
                        cmd.extend(["-o", current_temp_file, current_url])
                        
                        logger.info(f"Попытка {approach_idx + 1}: {approach['name']}")
                        logger.info(f"Команда: {' '.join(cmd)}")
                        
                        # Execute the command
                        process = subprocess.Popen(
                            cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            text=True
                        )
                        stdout, stderr = process.communicate()
                        
                        if process.returncode == 0:
                            logger.info(f"✅ Успешно скачано с помощью подхода: {approach['name']}")
                            
                            # Проверяем наличие файла
                            downloaded_file = self._find_downloaded_file(temp_dir, current_temp_file)
                            if downloaded_file:
                                # Добавляем метаданные
                                if metadata:
                                    self._add_metadata_to_file(downloaded_file, metadata)
                                
                                # Копируем файл в указанное место
                                shutil.copy(downloaded_file, output_file)
                                return True
                        else:
                            logger.warning(f"❌ Не удалось скачать с помощью подхода {approach['name']}: {stderr}")
                    
                    except Exception as e:
                        logger.warning(f"Ошибка при использовании подхода {approach['name']}: {e}")
                
                # Если все подходы не сработали
                logger.error("Все попытки скачивания не удались")
                return False
                
        except Exception as e:
            logger.error(f"Error in YouTube download process: {e}")
            return False
    
    def _check_command_available(self, command):
        """Check if a command is available on the system"""
        try:
            subprocess.run(
                [command, "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=False
            )
            return True
        except FileNotFoundError:
            return False
    
    def _convert_to_mp3(self, input_file, output_file):
        """Convert audio file to MP3 using ffmpeg"""
        try:
            cmd = [
                "ffmpeg",
                "-i", input_file,
                "-codec:a", "libmp3lame",
                "-q:a", "0",  # Best quality
                output_file
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Error converting to MP3: {stderr}")
                raise Exception(f"FFmpeg error: {stderr}")
            
            return True
        except Exception as e:
            logger.error(f"Error in conversion process: {e}")
            raise
    
    def _add_metadata_to_file(self, filename, metadata):
        """Add metadata to the downloaded MP3 file"""
        try:
            # Extract metadata from the dictionary and ensure all values are strings
            title = self._extract_simple_value(metadata.get('title', ''))
            artist = self._extract_simple_value(metadata.get('artist', ''))
            album = self._extract_simple_value(metadata.get('album', ''))
            release_year = self._extract_simple_value(metadata.get('release_year', ''))
            track_number = self._extract_simple_value(metadata.get('track_number', ''))
            genre = self._extract_simple_value(metadata.get('genre', ''))
            artwork_url = self._extract_simple_value(metadata.get('artwork_url', ''))
            
            logger.info(f"Processing metadata: Title={title}, Artist={artist}, Album={album}")
            
            # Download artwork if available
            artwork_data = None
            if artwork_url:
                try:
                    artwork_response = self.session.get(artwork_url)
                    artwork_response.raise_for_status()
                    artwork_data = artwork_response.content
                except Exception as e:
                    logger.error(f"Error downloading artwork: {e}")
            
            # Add ID3 tags
            try:
                # First try to load existing tags
                try:
                    audio = MP3(filename, ID3=ID3)
                except Exception:
                    # If there are no tags or error loading them, create new
                    audio = MP3(filename)
                    audio.add_tags()
                
                # Add the artwork
                if artwork_data:
                    audio.tags.add(
                        APIC(
                            encoding=3,  # UTF-8
                            mime='image/jpeg',
                            type=3,  # Cover image
                            desc='Cover',
                            data=artwork_data
                        )
                    )
                
                # Add track information, ensuring all values are strings
                if title:
                    audio.tags.add(TIT2(encoding=3, text=title))
                if artist:
                    audio.tags.add(TPE1(encoding=3, text=artist))
                if album:
                    audio.tags.add(TALB(encoding=3, text=album))
                
                # Add additional metadata if available
                if genre:
                    audio.tags.add(TCON(encoding=3, text=genre))
                if track_number:
                    audio.tags.add(TRCK(encoding=3, text=str(track_number)))
                if release_year:
                    audio.tags.add(TYER(encoding=3, text=str(release_year)))
                
                # Add comment 
                audio.tags.add(COMM(encoding=3, lang='eng', desc='desc', text='Downloaded with Music Search Bot'))
                
                # Save the changes
                audio.save()
                logger.info(f"Added metadata to file: {filename}")
                
            except Exception as e:
                logger.error(f"Error adding ID3 tags: {e}")
                
        except Exception as e:
            logger.error(f"Error adding metadata to file: {e}")

    def _extract_simple_value(self, value):
        """Extract a simple string value from potentially complex objects"""
        if value is None:
            return ""
        
        if isinstance(value, str):
            return value
        
        if isinstance(value, (int, float)):
            return str(value)
        
        if isinstance(value, dict):
            # Try common fields that might contain the value we want
            for key in ['name', 'title', 'value', 'text']:
                if key in value and isinstance(value[key], (str, int, float)):
                    return str(value[key])
            
            # Return empty string if we can't find a suitable value
            return ""
        
        if isinstance(value, list):
            # If it's a list, try to extract from the first item
            if len(value) > 0:
                if isinstance(value[0], dict):
                    return self._extract_simple_value(value[0])
                else:
                    return str(value[0])
            return ""
        
        # Default case, convert to string and hope for the best
        try:
            return str(value)
        except:
            return ""

    def _find_downloaded_file(self, directory, expected_file):
        """Находит скачанный файл в директории, даже если его расширение изменилось"""
        # Проверяем, существует ли ожидаемый файл
        if os.path.exists(expected_file):
            return expected_file
        
        # Проверяем другие возможные расширения
        base_name = os.path.splitext(expected_file)[0]
        for ext in ['.mp3', '.m4a', '.webm', '.opus', '.mp4']:
            potential_file = f"{base_name}{ext}"
            if os.path.exists(potential_file):
                return potential_file
        
        # Ищем любой аудио файл в директории
        for file in os.listdir(directory):
            if file.endswith(('.mp3', '.m4a', '.webm', '.opus', '.mp4')):
                return os.path.join(directory, file)
        
        return None

# Add missing imports if needed
import shutil 