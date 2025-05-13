import re
import json
import requests
from bs4 import BeautifulSoup
import logging
import urllib.parse
import os
import io
import subprocess
import tempfile
import shutil
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TCON, TRCK, TYER, COMM
from config import USER_AGENT, SOUNDCLOUD_SEARCH_URL, SOUNDCLOUD_API_URL
from utils.logger import setup_logger

logger = setup_logger(__name__, log_to_file=False)

class SoundCloudClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.client_id = None

    def search_tracks(self, query, limit=5):
        try:
            if not self.client_id:
                self.client_id = self._fetch_client_id()
                if not self.client_id:
                    logger.error("Failed to fetch client ID")
                    return []

            encoded_query = urllib.parse.quote_plus(query)
            
            search_url = f"{SOUNDCLOUD_API_URL}/search/tracks?q={encoded_query}&client_id={self.client_id}&limit={limit}"
            
            response = self.session.get(search_url)
            response.raise_for_status()
            
            data = response.json()
            collection = data.get('collection', [])
            
            tracks = []
            for track in collection:
                if len(tracks) >= limit:
                    break
                
                user = track.get('user', {})
                
                tracks.append({
                    "id": track.get('id'),
                    "title": track.get('title', ''),
                    "permalink_url": track.get('permalink_url', ''),
                    "artwork_url": track.get('artwork_url', ''),
                    "user": user.get('username', ''),
                    "duration": track.get('duration', 0),
                    "genre": track.get('genre', ''),
                    "description": track.get('description', ''),
                    "release_year": track.get('release_year', ''),
                    "track_number": track.get('track_number', ''),
                    "publisher_metadata": track.get('publisher_metadata', {}),
                })
            
            return tracks
            
        except Exception as e:
            logger.error(f"Error searching tracks: {e}")
            return []

    def _fetch_client_id(self):
        try:
            known_client_ids = [
                "iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX",
                "a3e059563d7fd3372b49b37f00a00bcf",
                "j884AoRfUqCRXS8Cm1DzMxyY0xSn9Knd",
                "HW84SNgpVYl6cSsQrjFe3LiYQqd4pH4y",
                "2t9loNQH90kzJcsFCODdigxfp325aq4z"
            ]
            
            for client_id in known_client_ids:
                test_url = f"{SOUNDCLOUD_API_URL}/me?client_id={client_id}"
                response = self.session.get(test_url)
                if response.status_code != 401:
                    logger.info(f"Using known client ID: {client_id}")
                    return client_id
            
            response = self.session.get("https://soundcloud.com/")
            response.raise_for_status()
            
            client_id = self._extract_client_id_from_page(response.text)
            if client_id:
                return client_id
                
            return known_client_ids[0]
            
        except Exception as e:
            logger.error(f"Error fetching client ID: {e}")
            return "iZIs9mchVcX5lhVRyQGGAYlNPVldzAoX"
    
    def _extract_client_id_from_page(self, html_content):
        try:
            script_urls = re.findall(r'<script[^>]*src="([^"]*)"', html_content)
            
            app_script_urls = [url for url in script_urls if url.startswith('https://') and 'sndcdn.com' in url]
            
            for script_url in app_script_urls:
                script_content = self.session.get(script_url).text
                client_id_match = re.search(r'client_id:"([^"]*)"', script_content)
                if client_id_match:
                    return client_id_match.group(1)
                    
            return None
        except Exception as e:
            logger.error(f"Error extracting client ID from page: {e}")
            return None
    
    def get_track_download_url(self, track_url):
        try:
            if not self.client_id:
                self.client_id = self._fetch_client_id()
                if not self.client_id:
                    logger.error("Failed to fetch client ID for download")
                    return None
            
            logger.info(f"Getting download URL for: {track_url}")
            
            track_id = None
            try:
                parts = track_url.strip('/').split('/')
                if len(parts) >= 5:
                    username = parts[-2]
                    track_name = parts[-1]
                    
                    resolve_url = f"{SOUNDCLOUD_API_URL}/resolve?url={track_url}&client_id={self.client_id}"
                    resolve_response = self.session.get(resolve_url)
                    if resolve_response.status_code == 200:
                        track_data = resolve_response.json()
                        track_id = track_data.get('id')
                        
                        if track_id:
                            logger.info(f"Found track ID from resolve: {track_id}")
                            return self._get_stream_url_from_id(track_id), track_data
            except Exception as e:
                logger.error(f"Error resolving track URL: {e}")
            
            response = self.session.get(track_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            track_data = None
            
            for script in soup.find_all("script", {"type": "application/ld+json"}):
                if script.string:
                    try:
                        ld_data = json.loads(script.string)
                        if ld_data.get("@type") == "MusicRecording":
                            track_url = ld_data.get("url")
                            if track_url:
                                resolve_url = f"{SOUNDCLOUD_API_URL}/resolve?url={track_url}&client_id={self.client_id}"
                                resolve_response = self.session.get(resolve_url)
                                if resolve_response.status_code == 200:
                                    track_data = resolve_response.json()
                                    track_id = track_data.get('id')
                                    if track_id:
                                        logger.info(f"Found track ID from LD+JSON: {track_id}")
                                        return self._get_stream_url_from_id(track_id), track_data
                    except:
                        pass
            
            for script in soup.find_all("script"):
                if script.string and "window.__sc_hydration" in script.string:
                    match = re.search(r'window\.__sc_hydration = (.+?);<\/script>', script.string)
                    if match:
                        hydration_data = json.loads(match.group(1))
                        for item in hydration_data:
                            if item.get("hydratable") == "sound":
                                track_data = item.get("data", {})
                                track_id = track_data.get("id")
                                
                                if track_id:
                                    logger.info(f"Found track ID from hydration: {track_id}")
                                    
                                    media_url = track_data.get("media", {}).get("transcodings", [])
                                    for media in media_url:
                                        if media.get("format", {}).get("protocol") == "progressive":
                                            stream_url = media.get("url")
                                            if stream_url:
                                                stream_full_url = f"{stream_url}?client_id={self.client_id}"
                                                logger.info(f"Found progressive stream URL: {stream_full_url}")
                                                
                                                try:
                                                    stream_response = self.session.get(stream_full_url)
                                                    stream_response.raise_for_status()
                                                    stream_data = stream_response.json()
                                                    download_url = stream_data.get("url")
                                                    if download_url:
                                                        logger.info(f"Successfully got download URL from progressive stream")
                                                        return download_url, track_data
                                                except Exception as e:
                                                    logger.error(f"Error getting progressive stream: {e}")
                                    
                                    download_url = self._get_stream_url_from_id(track_id)
                                    if download_url:
                                        return download_url, track_data
            
            logger.error(f"Could not find track data in the page: {track_url}")
            return None, None
        except Exception as e:
            logger.error(f"Error getting download URL: {e}")
            return None, None
    
    def _get_stream_url_from_id(self, track_id):
        try:
            api_url = f"{SOUNDCLOUD_API_URL}/tracks/{track_id}/stream?client_id={self.client_id}"
            response = self.session.get(api_url, allow_redirects=False)
            
            if response.status_code == 302:
                redirect_url = response.headers.get('Location')
                logger.info(f"Got redirect URL for track {track_id}: {redirect_url}")
                return redirect_url
            
            api_url = f"{SOUNDCLOUD_API_URL}/tracks/{track_id}?client_id={self.client_id}"
            response = self.session.get(api_url)
            response.raise_for_status()
            
            track_data = response.json()
            media_url = track_data.get("media", {}).get("transcodings", [])
            
            for media in media_url:
                if media.get("format", {}).get("protocol") == "progressive":
                    stream_url = media.get("url")
                    if stream_url:
                        stream_full_url = f"{stream_url}?client_id={self.client_id}"
                        stream_response = self.session.get(stream_full_url)
                        stream_response.raise_for_status()
                        stream_data = stream_response.json()
                        return stream_data.get("url")
            
            for media in media_url:
                if media.get("format", {}).get("protocol") == "hls":
                    stream_url = media.get("url")
                    if stream_url:
                        stream_full_url = f"{stream_url}?client_id={self.client_id}"
                        stream_response = self.session.get(stream_full_url)
                        stream_response.raise_for_status()
                        stream_data = stream_response.json()
                        playlist_url = stream_data.get("url")
                        
                        if playlist_url:
                            logger.info(f"Found HLS playlist URL: {playlist_url}")
                            return playlist_url
            
            logger.error(f"No streaming URLs found for track {track_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting stream URL from ID: {e}")
            return None
    
    def download_track(self, download_url, track_data, filename=None):
        temp_output = None
        temp_artwork = None
        
        try:
            logger.info(f"⬇️ Начинаем загрузку трека...")
            logger.debug(f"URL для скачивания: {download_url}")
            
            if track_data:
                title = track_data.get('title', '<без названия>')
                artist = track_data.get('user', {}).get('username', '<неизвестный артист>') if isinstance(track_data.get('user'), dict) else '<неизвестный артист>'
                logger.info(f"🎵 Загружаем: {artist} - {title}")
            else:
                logger.warning("⚠️ Метаданные трека отсутствуют")
                
            if not filename:
                filename = "track.mp3"
                
            if not self._check_ffmpeg_available():
                logger.warning("FFmpeg not available, falling back to direct download")
                self._download_file(download_url, filename)
                try:
                    self._add_metadata_to_file(filename, track_data)
                except Exception as e:
                    logger.error(f"❌ Ошибка добавления метаданных в direct download: {e}")
                return filename
            
            is_hls = False
            if download_url:
                is_hls = download_url.endswith('.m3u8') or 'playlist.m3u8' in download_url
            
            if is_hls:
                logger.info("🔄 Конвертация HLS плейлиста с помощью FFmpeg...")
            else:
                logger.info("🔄 Конвертация трека с помощью FFmpeg...")
            
            temp_output = os.path.join(tempfile.gettempdir(), f"sc_temp_{os.urandom(4).hex()}.mp3")
            
            artwork_url = None
            try:
                if track_data:
                    artwork_url = self._get_best_artwork_url(track_data)
            except Exception as e:
                logger.error(f"❌ Ошибка получения URL обложки: {e}")
                
            if artwork_url:
                try:
                    temp_artwork = os.path.join(tempfile.gettempdir(), f"sc_art_{os.urandom(4).hex()}.jpg")
                    artwork_response = self.session.get(artwork_url)
                    artwork_response.raise_for_status()
                    
                    with open(temp_artwork, 'wb') as f:
                        f.write(artwork_response.content)
                        
                    logger.info(f"📁 Скачана обложка во временный файл: {os.path.basename(temp_artwork)}")
                except Exception as e:
                    logger.error(f"❌ Ошибка скачивания обложки: {e}")
                    temp_artwork = None
            
            title = ""
            artist = ""
            album = "SoundCloud"
            genre = ""
            comment = ""
            year = ""
            track_num = ""
            
            if track_data:
                if isinstance(track_data.get("title"), str):
                    title = track_data.get("title", "")
                
                user_data = track_data.get("user", {})
                if isinstance(user_data, dict) and isinstance(user_data.get("username"), str):
                    artist = user_data.get("username", "")
                    
                publisher = track_data.get("publisher_metadata", {})
                if isinstance(publisher, dict) and isinstance(publisher.get("album_title"), str):
                    album = publisher.get("album_title", "SoundCloud")
                    
                if isinstance(track_data.get("genre"), str):
                    genre = track_data.get("genre", "")
                    
                if isinstance(track_data.get("description"), str):
                    comment = track_data.get("description", "")
                    
                if track_data.get("release_year"):
                    year = str(track_data.get("release_year", ""))
                    
                if track_data.get("track_number"):
                    track_num = str(track_data.get("track_number", ""))
            
            title = f"{title} | @hxmusic_robot" if title else "@hxmusic_robot"
            
            metadata = {
                "title": title,
                "artist": artist,
                "album": album,
                "genre": genre,
                "comment": comment,
                "year": year,
                "track": track_num,
            }
            
            command = ['ffmpeg', '-i', download_url]
            
            if temp_artwork:
                command.extend(['-i', temp_artwork])
            
            for key, value in metadata.items():
                if value:
                    command.extend(['-metadata', f'{key}={value}'])
            
            command.extend([
                '-c:a', 'libmp3lame',
                '-q:a', '2',
                '-ar', '44100',
                '-map_metadata', '0',
            ])
            
            if temp_artwork:
                command.extend([
                    '-map', '0:a',
                    '-map', '1:v',
                    '-c:v', 'mjpeg',
                    '-disposition:v', 'attached_pic'
                ])
            
            command.extend([
                '-v', 'warning',
                '-stats',
                '-y',
                temp_output
            ])
            
            logger.info(f"🔄 Конвертация трека с помощью FFmpeg...")
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if process.returncode != 0:
                logger.error(f"❌ Ошибка FFmpeg: {process.stderr.decode()}")
                logger.info("🔄 Переключаемся на прямое скачивание...")
                self._download_file(download_url, filename)
                try:
                    self._add_metadata_to_file(filename, track_data)
                except Exception as e:
                    logger.error(f"❌ Ошибка добавления метаданных: {e}")
            else:
                shutil.copy2(temp_output, filename)
                logger.info(f"✅ Трек успешно обработан и сохранен: {os.path.basename(filename)}")
            
            return filename
            
        except Exception as e:
            logger.error(f"❌ Ошибка при скачивании трека: {e}")
            try:
                logger.info("🔄 Пробуем прямое скачивание как запасной вариант...")
                self._download_file(download_url, filename)
                try:
                    self._add_metadata_to_file(filename, track_data)
                except Exception as e2:
                    logger.error(f"❌ Ошибка добавления метаданных: {e2}")
                logger.info(f"✅ Трек скачан напрямую и сохранен: {os.path.basename(filename)}")
                return filename
            except Exception as e2:
                logger.error(f"❌ Ошибка при запасном скачивании: {e2}")
                return None
                
        finally:
            temp_files = [f for f in [temp_output, temp_artwork] if f and os.path.exists(f)]
            if temp_files:
                self._cleanup_temp_files(temp_files)
                logger.debug(f"🧹 Очищено {len(temp_files)} временных файлов")
    
    def _check_ffmpeg_available(self):
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            logger.info("FFmpeg is available")
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning("FFmpeg not found in system path")
            return False
    
    def _get_best_artwork_url(self, track_data):
        if not track_data:
            return None
            
        artwork_url = track_data.get("artwork_url", "")
        if artwork_url:
            artwork_url = re.sub(r'large|t500x500', 'original', artwork_url)
            return artwork_url
        
        if "user" in track_data:
            avatar_url = track_data.get("user", {}).get("avatar_url", "")
            if avatar_url:
                avatar_url = re.sub(r'large|t500x500', 'original', avatar_url)
                return avatar_url
        
        return None
    
    def _cleanup_temp_files(self, file_list):
        if not file_list:
            return
            
        for file_path in file_list:
            if file_path and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                    logger.debug(f"🧹 Удален временный файл: {os.path.basename(file_path)}")
                except (PermissionError, OSError) as e:
                    logger.debug(f"⚠️ Не удалось удалить файл {os.path.basename(file_path)}: {e}")
                    try:
                        os.chmod(file_path, 0o777)
                        tempfile._finalizer.register(os.unlink, file_path)
                    except Exception:
                        pass
    
    def _download_file(self, url, filename):
        try:
            logger.info(f"📥 Начинаем прямую загрузку файла...")
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            chunk_size = 8192
            
            logger.info(f"📦 Размер файла: {total_size / (1024 * 1024):.2f} МБ")
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0 and downloaded % (total_size // 10) < chunk_size:
                        percent = int(downloaded * 100 / total_size)
                        logger.info(f"⏳ Прогресс загрузки: {percent}% ({downloaded / (1024 * 1024):.2f} / {total_size / (1024 * 1024):.2f} МБ)")
                    
            logger.info(f"✅ Загрузка завершена: {os.path.basename(filename)}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки файла: {e}")
            return False

    def _add_metadata_to_file(self, filename, track_data):
        try:
            if not track_data:
                logger.warning("⚠️ Нет данных для добавления метаданных")
                return
                
            if not os.path.exists(filename):
                logger.error(f"❌ Файл не существует: {filename}")
                return
                
            logger.info(f"🔖 Добавляем метаданные к файлу...")
                
            title = ""
            if isinstance(track_data.get("title"), str):
                title = track_data.get("title", "")
                
            artist = ""
            user_data = track_data.get("user", {})
            if isinstance(user_data, dict) and isinstance(user_data.get("username"), str):
                artist = user_data.get("username", "")
                
            album = "SoundCloud"
            publisher = track_data.get("publisher_metadata", {})
            if isinstance(publisher, dict) and isinstance(publisher.get("album_title"), str):
                album = publisher.get("album_title", "SoundCloud")
                
            genre = ""
            if isinstance(track_data.get("genre"), str):
                genre = track_data.get("genre", "")
                
            year = ""
            if track_data.get("release_year"):
                year = str(track_data.get("release_year", ""))
                
            track_number = ""
            if track_data.get("track_number"):
                track_number = str(track_data.get("track_number", ""))
                
            description = ""
            if isinstance(track_data.get("description"), str):
                description = track_data.get("description", "")
            
            title = f"{title} | @hxmusic_robot" if title else "@hxmusic_robot"
            
            artwork_url = None
            try:
                artwork_url = self._get_best_artwork_url(track_data)
            except Exception as e:
                logger.error(f"Error getting artwork URL for metadata: {e}")
            
            try:
                audio = MP3(filename, ID3=ID3)
                
                try:
                    audio.add_tags()
                except:
                    pass
                
                if title:
                    audio.tags.add(TIT2(encoding=3, text=title))
                if artist:
                    audio.tags.add(TPE1(encoding=3, text=artist))
                if album:
                    audio.tags.add(TALB(encoding=3, text=album))
                if genre:
                    audio.tags.add(TCON(encoding=3, text=genre))
                if track_number:
                    audio.tags.add(TRCK(encoding=3, text=track_number))
                if year:
                    audio.tags.add(TYER(encoding=3, text=year))
                if description:
                    audio.tags.add(COMM(encoding=3, lang='eng', desc='Description', text=description))
                
                if artwork_url:
                    try:
                        logger.info(f"🖼️ Загружаем обложку для трека...")
                        artwork_response = self.session.get(artwork_url)
                        artwork_response.raise_for_status()
                        
                        content_type = artwork_response.headers.get('Content-Type', 'image/jpeg')
                        
                        audio.tags.add(APIC(
                            encoding=3,
                            mime=content_type,
                            type=3,
                            desc='Cover',
                            data=artwork_response.content
                        ))
                        
                        logger.info(f"✅ Обложка добавлена к файлу")
                    except Exception as e:
                        logger.error(f"❌ Ошибка добавления обложки: {e}")
                
                audio.save()
                logger.info(f"✅ Метаданные успешно добавлены к файлу")
                
            except Exception as e:
                logger.error(f"❌ Ошибка добавления метаданных через mutagen: {e}")
                try:
                    logger.info("🔄 Пробуем альтернативный метод добавления метаданных через ffmpeg...")
                    self._add_metadata_with_ffmpeg(filename, track_data, artwork_url)
                except Exception as e2:
                    logger.error(f"❌ Ошибка с альтернативным методом добавления метаданных: {e2}")
        except Exception as e:
            logger.error(f"❌ Ошибка добавления метаданных: {e}")
            
    def _add_metadata_with_ffmpeg(self, filename, track_data, artwork_url=None):
        try:
            if not track_data:
                logger.warning("No track data available for adding metadata with ffmpeg")
                return False
                
            if not os.path.exists(filename):
                logger.error(f"File does not exist for ffmpeg metadata: {filename}")
                return False
                
            if not self._check_ffmpeg_available():
                logger.warning("ffmpeg not available for metadata")
                return False
                
            temp_output = os.path.join(tempfile.gettempdir(), f"sc_meta_{os.urandom(4).hex()}.mp3")
            temp_artwork = None
            
            title = ""
            if isinstance(track_data.get("title"), str):
                title = track_data.get("title", "")
                
            artist = ""
            user_data = track_data.get("user", {})
            if isinstance(user_data, dict) and isinstance(user_data.get("username"), str):
                artist = user_data.get("username", "")
                
            album = "SoundCloud"
            publisher = track_data.get("publisher_metadata", {})
            if isinstance(publisher, dict) and isinstance(publisher.get("album_title"), str):
                album = publisher.get("album_title", "SoundCloud")
                
            genre = ""
            if isinstance(track_data.get("genre"), str):
                genre = track_data.get("genre", "")
                
            description = ""
            if isinstance(track_data.get("description"), str):
                description = track_data.get("description", "")
            
            title = f"{title} | @hxmusic_robot" if title else "@hxmusic_robot"
            
            metadata = {
                "title": title,
                "artist": artist,
                "album": album,
                "genre": genre,
                "comment": description
            }
            
            args = ['ffmpeg', '-i', filename]
            
            for key, value in metadata.items():
                if value:
                    args.extend(['-metadata', f'{key}={value}'])
            
            if artwork_url:
                try:
                    temp_artwork = os.path.join(tempfile.gettempdir(), f"sc_art_{os.urandom(4).hex()}.jpg")
                    artwork_response = self.session.get(artwork_url)
                    artwork_response.raise_for_status()
                    
                    with open(temp_artwork, 'wb') as f:
                        f.write(artwork_response.content)
                    
                    args.extend(['-i', temp_artwork, '-map', '0:a', '-map', '1:v', '-c:v', 'copy', '-disposition:v', 'attached_pic'])
                except Exception as e:
                    logger.error(f"Error downloading artwork for ffmpeg: {e}")
            
            args.extend(['-c:a', 'copy', '-y', temp_output])
            
            process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if process.returncode != 0:
                logger.error(f"FFmpeg metadata error: {process.stderr.decode()}")
                return False
            
            shutil.move(temp_output, filename)
            
            self._cleanup_temp_files([temp_artwork])
                
            logger.info(f"Added metadata using ffmpeg to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error in ffmpeg metadata: {e}")
            return False