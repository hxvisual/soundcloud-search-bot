import re
import json
import requests
import base64
import time
import urllib.parse
import os
import io
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, TCON, TRCK, TYER, COMM
from config import USER_AGENT
from utils.logger import setup_logger

logger = setup_logger(__name__, log_to_file=False)

class SpotifyClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.access_token = None
        self.token_expiry = 0

    def _get_access_token(self):
        try:
            # Check if token is still valid
            if self.access_token and time.time() < self.token_expiry:
                return self.access_token

            if not self.client_id or not self.client_secret:
                logger.error("Spotify credentials not configured")
                return None

            # Request a new token
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_bytes = auth_string.encode("utf-8")
            auth_base64 = base64.b64encode(auth_bytes).decode("utf-8")

            url = "https://accounts.spotify.com/api/token"
            headers = {
                "Authorization": f"Basic {auth_base64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            data = {"grant_type": "client_credentials"}

            response = self.session.post(url, headers=headers, data=data)
            response.raise_for_status()
            
            json_result = response.json()
            self.access_token = json_result["access_token"]
            self.token_expiry = time.time() + json_result["expires_in"] - 60  # Subtract 60 seconds to be safe
            
            logger.info("Successfully obtained Spotify access token")
            return self.access_token
            
        except Exception as e:
            logger.error(f"Error getting Spotify access token: {e}")
            return None

    def search_tracks(self, query, limit=20):
        try:
            access_token = self._get_access_token()
            if not access_token:
                logger.error("Failed to get Spotify access token")
                return []

            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://api.spotify.com/v1/search?q={encoded_query}&type=track&limit={limit}"
            
            headers = {"Authorization": f"Bearer {access_token}"}
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            tracks_data = data.get('tracks', {}).get('items', [])
            
            tracks = []
            for track in tracks_data:
                artists = track.get('artists', [])
                artist_names = [artist.get('name', '') for artist in artists]
                artist_name = ', '.join(artist_names)
                
                album = track.get('album', {})
                album_name = album.get('name', '')
                
                # Get the largest image from album
                images = album.get('images', [])
                artwork_url = images[0].get('url') if images else ''
                
                # Preview URL might be None for some tracks
                preview_url = track.get('preview_url', '')
                
                track_info = {
                    "id": track.get('id'),
                    "title": track.get('name', ''),
                    "permalink_url": track.get('external_urls', {}).get('spotify', ''),
                    "artwork_url": artwork_url,
                    "user": artist_name,
                    "duration": track.get('duration_ms', 0),
                    "genre": "",  # Spotify API doesn't directly provide genre in track object
                    "description": "",
                    "release_year": album.get('release_date', '')[:4] if album.get('release_date') else '',
                    "track_number": track.get('track_number', ''),
                    "album": album_name,
                    "preview_url": preview_url,
                    "platform": "spotify"  # Mark this as a Spotify track
                }
                
                tracks.append(track_info)
            
            return tracks
            
        except Exception as e:
            logger.error(f"Error searching Spotify tracks: {e}")
            return []

    def get_track_download_url(self, track_url):
        """
        Note: Spotify doesn't allow direct download of full tracks.
        This function will return preview_url if available.
        """
        try:
            access_token = self._get_access_token()
            if not access_token:
                return None, None
            
            # Extract track ID from URL
            track_id = track_url.split('/')[-1]
            if '?' in track_id:
                track_id = track_id.split('?')[0]
            
            url = f"https://api.spotify.com/v1/tracks/{track_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
            
            track_data = response.json()
            preview_url = track_data.get('preview_url')
            
            # Also get more info about album for metadata
            album_id = track_data.get('album', {}).get('id')
            if album_id:
                album_url = f"https://api.spotify.com/v1/albums/{album_id}"
                album_response = self.session.get(album_url, headers=headers)
                
                if album_response.status_code == 200:
                    album_data = album_response.json()
                    track_data['album_details'] = album_data
            
            return preview_url, track_data
        
        except Exception as e:
            logger.error(f"Error getting Spotify track details: {e}")
            return None, None
    
    def download_track(self, download_url, track_data, filename=None):
        """
        Download a track preview from Spotify
        Note: This will only download the preview clip, not the full track
        """
        if not download_url:
            logger.error("No download URL provided for Spotify track")
            return False
        
        if not filename:
            # Generate a filename based on track data
            artist = track_data.get('artists', [{}])[0].get('name', 'Unknown Artist')
            title = track_data.get('name', 'Unknown Track')
            filename = f"{artist} - {title}.mp3"
            
            # Clean filename
            filename = re.sub(r'[\\/*?:"<>|]', '', filename)
        
        try:
            # Download the file
            response = self.session.get(download_url, stream=True)
            response.raise_for_status()
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Add metadata to the file
            self._add_metadata_to_file(filename, track_data)
            
            return True
        
        except Exception as e:
            logger.error(f"Error downloading Spotify preview: {e}")
            return False
    
    def _add_metadata_to_file(self, filename, track_data):
        try:
            # Download album artwork
            artwork_url = None
            images = track_data.get('album', {}).get('images', [])
            if images and len(images) > 0:
                artwork_url = images[0].get('url')
            
            if not artwork_url:
                logger.warning("No artwork URL found for Spotify track")
                return
            
            # Get artist and title information
            artists = track_data.get('artists', [])
            artist_name = artists[0].get('name', '') if artists else 'Unknown Artist'
            title = track_data.get('name', 'Unknown Track')
            album = track_data.get('album', {}).get('name', '')
            
            # Get album artwork
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
                audio = MP3(filename, ID3=ID3)
                
                # Create ID3 tag if it doesn't exist
                try:
                    audio.add_tags()
                except:
                    pass
                
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
                
                # Add track information
                if title:
                    audio.tags.add(TIT2(encoding=3, text=title))
                if artist_name:
                    audio.tags.add(TPE1(encoding=3, text=artist_name))
                if album:
                    audio.tags.add(TALB(encoding=3, text=album))
                
                # Add comment indicating this is only a preview from Spotify
                audio.tags.add(COMM(encoding=3, lang='eng', desc='desc', text='Spotify preview'))
                
                # Save the changes
                audio.save()
                logger.info(f"Added metadata to file: {filename}")
                
            except Exception as e:
                logger.error(f"Error adding ID3 tags: {e}")
                
        except Exception as e:
            logger.error(f"Error adding metadata to file: {e}") 