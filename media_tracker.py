# media_tracker.py - ФИНАЛЬНАЯ ВЕРСИЯ С ВИДЕО
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import requests
import feedparser
import json
import os
import re
import webbrowser
import threading
import urllib.parse
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from pathlib import Path
from PIL import Image, ImageTk

# Импорты для видео
import vlc
from youtube_search import YoutubeSearch

# ========== КОНФИГУРАЦИЯ ==========
USER_DATA_DIR = Path("media_data")
USER_DATA_DIR.mkdir(exist_ok=True)
USER_GAMES_FILE = USER_DATA_DIR / "user_games.json"
USER_SERIES_FILE = USER_DATA_DIR / "user_series.json"
USER_ANIME_FILE = USER_DATA_DIR / "user_anime.json"
USER_MANGA_FILE = USER_DATA_DIR / "user_manga.json"
DB_FILE = USER_DATA_DIR / "release_dates_db.json"

# Пути к фоновым изображениям
BG_GAMES = Path("bg_games.jpeg")
BG_SERIES = Path("bg_series.jpeg")
BG_ANIME = Path("bg_anime.png")
BG_MANGA = Path("bg_manga.jpeg")

# ========== КЛАСС ДЛЯ ВОСПРОИЗВЕДЕНИЯ ВИДЕО ==========
class VideoPlayer:
    """
    Класс для поиска и воспроизведения видео-трейлеров.
    Использует YouTube Search и плеер VLC.
    """
    def __init__(self, parent_frame):
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.is_playing = False
        
        # Создаем виджет Tkinter, в котором будет отображаться видео
        self.video_panel = tk.Frame(parent_frame, bg="black", bd=2, relief="solid")
        self.video_panel.pack(fill="both", expand=True)
        self.video_panel.pack_forget()  # Скрываем по умолчанию
        
        # Привязываем окно плеера к панели Tkinter по ID окна
        self._bind_window()
        
        # Кнопка закрытия видео
        self.close_btn = tk.Button(self.video_panel, text="✖ ЗАКРЫТЬ ВИДЕО", 
                                   command=self.stop, bg="#e94560", fg="white")
        self.close_btn.place(relx=0.98, rely=0.02, anchor="ne")
    
    def _bind_window(self):
        """Привязывает VLC плеер к окну Tkinter"""
        if self.video_panel.winfo_exists():
            if os.name == 'nt':  # Windows
                self.player.set_hwnd(self.video_panel.winfo_id())
            elif os.name == 'posix':  # Linux/MacOS
                self.player.set_xwindow(self.video_panel.winfo_id())
    
    def play_trailer(self, title: str, media_type: str) -> bool:
        """Ищет и запускает трейлер по названию игры/аниме/сериала."""
        query = f"{title} {media_type} официальный трейлер"
        print(f"🎬 Поиск трейлера: '{query}'...")
        
        try:
            results = YoutubeSearch(query, max_results=5).to_dict()
            if not results:
                messagebox.showwarning("Видео", f"Трейлер для '{title}' не найден.")
                return False
            
            # Берем первый результат из поиска
            video_url = f"https://www.youtube.com{results[0]['url_suffix']}"
            print(f"🎬 Найдено видео: {video_url}")
            
            media = self.instance.media_new(video_url)
            self.player.set_media(media)
            
            # Показываем панель и запускаем видео
            self.video_panel.pack(fill="both", expand=True, pady=5)
            self._bind_window()  # Перепривязываем окно после отображения
            self.player.play()
            self.is_playing = True
            
            return True
            
        except Exception as e:
            print(f"Ошибка при поиске видео: {e}")
            messagebox.showerror("Ошибка", f"Не удалось найти или запустить видео: {e}")
            return False
    
    def stop(self):
        """Останавливает воспроизведение и скрывает панель."""
        if self.player and self.player.is_playing():
            self.player.stop()
        self.is_playing = False
        self.video_panel.pack_forget()
    
    def pause(self):
        """Пауза/возобновление"""
        if self.is_playing:
            self.player.pause()
            self.is_playing = False
        else:
            self.player.play()
            self.is_playing = True

# ========== ПУБЛИЧНЫЕ API ==========
class GameReleaseAPI:
    @staticmethod
    def search_game(title: str, timeout: int = 10) -> Optional[str]:
        try:
            encoded = urllib.parse.quote(title)
            url = f"https://api.rawg.io/api/games?search={encoded}&page_size=1"
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    release_date = data["results"][0].get("released")
                    return release_date if release_date else None
            return None
        except requests.exceptions.Timeout:
            print(f"⏱️ Таймаут RAWG API: {title}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"🌐 Ошибка RAWG API: {e}")
            return None

class SeriesReleaseAPI:
    @staticmethod
    def search_series(title: str, timeout: int = 10) -> Optional[str]:
        try:
            encoded = urllib.parse.quote(title)
            url = f"https://api.tvmaze.com/singlesearch/shows?q={encoded}"
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                premiered = data.get("premiered")
                return premiered if premiered else None
            return None
        except Exception as e:
            print(f"Ошибка TVMaze API: {e}")
            return None

class AnimeReleaseAPI:
    @staticmethod
    def search_anime(title: str, timeout: int = 10) -> Optional[str]:
        try:
            encoded = urllib.parse.quote(title)
            url = f"https://api.jikan.moe/v4/anime?q={encoded}&limit=1"
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    aired = data["data"][0].get("aired", {})
                    from_date = aired.get("from")
                    return from_date[:10] if from_date else None
            return None
        except Exception as e:
            print(f"Ошибка Jikan API: {e}")
            return None

# ========== RSS ИСТОЧНИКИ ==========
EN_RSS_SOURCES = {
    "IGN": "https://feeds.feedburner.com/ign/news",
    "GameSpot": "https://www.gamespot.com/feeds/news/",
}

RU_RSS_SOURCES = {
    "StopGame": "https://stopgame.ru/news/rss",
    "DTF": "https://dtf.ru/rss/news",
    "Игромания": "https://www.igromania.ru/rss/news/",
    "Kanobu": "https://kanobu.ru/rss/feed",
    "VGTimes": "https://vgtimes.ru/rss/news.xml",
    "Кинопоиск": "https://www.kinopoisk.ru/media/rss/",
}

SERIES_RSS_SOURCES = {
    "TVLine": "https://tvline.com/feed/",
    "Deadline TV": "https://deadline.com/category/tv/feed/",
}

ANIME_RSS_SOURCES = {
    "Anime News Network": "https://www.animenewsnetwork.com/news/rss.xml",
    "Crunchyroll": "https://www.crunchyroll.com/news/rss",
}

RSS_SOURCES = {**EN_RSS_SOURCES, **RU_RSS_SOURCES, **SERIES_RSS_SOURCES, **ANIME_RSS_SOURCES}

SOURCE_CATEGORIES = {
    "Игры": list(EN_RSS_SOURCES.keys()) + ["StopGame", "DTF", "Игромания", "Kanobu", "VGTimes"],
    "Сериалы": list(SERIES_RSS_SOURCES.keys()) + ["Кинопоиск"],
    "Аниме": list(ANIME_RSS_SOURCES.keys()),
}

RUSSIAN_SEARCH_QUERIES = {
    "Игры": ["игровые новости", "новости игр"],
    "Сериалы": ["новости сериалов", "сериалы новости"],
    "Аниме": ["новости аниме", "аниме новости"],
}

class MediaTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("🎮 MediaTracker - Самообучающийся календарь с видео")
        self.root.geometry("1450x850")
        self.root.minsize(1200, 700)
        
        self._running = True
        self._search_cancelled = False
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Цветовая схема
        self.bg_color = "#0f0f1a"
        self.fg_color = "#e0e0e0"
        self.accent_color = "#1a1a2e"
        self.highlight = "#e94560"
        self.game_color = "#4ecdc4"
        self.series_color = "#ff6b6b"
        self.anime_color = "#c44ec5"
        self.db_color = "#4CAF50"
        self.api_color = "#2196F3"
        self.root.configure(bg=self.bg_color)

        # Инициализация БД
        self._init_db()
        
        # Данные
        self.user_games = self._safe_load_json(USER_GAMES_FILE, [])
        self.user_series = self._safe_load_json(USER_SERIES_FILE, [])
        self.user_anime = self._safe_load_json(USER_ANIME_FILE, [])
        self.user_manga = self._safe_load_json(USER_MANGA_FILE, [])
        self.current_news = []
        self.video_player = None

        self.setup_ui()
        self._load_all_lists()
        self.refresh_all_news()
        self._load_calendar()
        
        # Автоматический поиск дат для существующих записей
        self._auto_find_missing_dates()
        
        self._schedule_auto_update()

    # ========== ВИДЕОПЛЕЕР ==========
    def _init_video_player(self, parent_frame):
        """Инициализирует видеоплеер в указанном фрейме"""
        if self.video_player:
            self.video_player.stop()
        self.video_player = VideoPlayer(parent_frame)
        return self.video_player

    def _play_trailer(self, media_type: str):
        """Воспроизводит трейлер выбранного элемента"""
        selected = None
        title = None
        
        if media_type == 'games':
            sel = self.games_tree.selection()
            if sel:
                idx = int(sel[0])
                selected = self.user_games[idx]
        elif media_type == 'series':
            sel = self.series_tree.selection()
            if sel:
                idx = int(sel[0])
                selected = self.user_series[idx]
        elif media_type == 'anime':
            sel = self.anime_tree.selection()
            if sel:
                idx = int(sel[0])
                selected = self.user_anime[idx]
        
        if not selected:
            messagebox.showwarning("Выбор", "Сначала выберите элемент из списка!")
            return
        
        title = selected.get("title", "Unknown")
        
        # Определяем родительский фрейм для видео
        if media_type == 'games':
            parent_frame = self.games_frame
        elif media_type == 'series':
            parent_frame = self.series_frame
        else:
            parent_frame = self.anime_frame
        
        # Инициализируем плеер
        if not self.video_player:
            self._init_video_player(parent_frame)
        else:
            # Останавливаем текущее видео и перепривязываем к новому родителю
            self.video_player.stop()
            self.video_player.video_panel.pack_forget()
            self.video_player.video_panel = tk.Frame(parent_frame, bg="black", bd=2, relief="solid")
            self.video_player._bind_window()
        
        # Запускаем поиск и воспроизведение
        self.video_player.play_trailer(title, media_type.capitalize())

    # ========== РАБОТА С САМООБУЧАЮЩЕЙСЯ БАЗОЙ ДАННЫХ ==========
    def _init_db(self):
        if not DB_FILE.exists():
            default_db = {
                "games": {},
                "series": {},
                "anime": {},
                "stats": {
                    "total_requests": 0,
                    "cache_hits": 0,
                    "api_calls": 0,
                    "user_confirmations": 0,
                    "api_errors": 0
                }
            }
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_db, f, ensure_ascii=False, indent=2)
            print("📁 Создана новая база данных релизов")

    def _load_db(self):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Ошибка чтения БД: {e}")
            return {"games": {}, "series": {}, "anime": {}, "stats": {}}

    def _save_db(self, db_data):
        try:
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(db_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"⚠️ Ошибка записи БД: {e}")
            return False

    def _get_date_from_db(self, media_type: str, title: str) -> Optional[str]:
        db = self._load_db()
        if media_type in db:
            result = db[media_type].get(title)
            if result:
                db["stats"]["cache_hits"] = db["stats"].get("cache_hits", 0) + 1
                db["stats"]["total_requests"] = db["stats"].get("total_requests", 0) + 1
                self._save_db(db)
                return result
        return None

    def _add_to_db(self, media_type: str, title: str, date: str):
        db = self._load_db()
        if media_type in db:
            db[media_type][title] = date
            db["stats"]["user_confirmations"] = db["stats"].get("user_confirmations", 0) + 1
            self._save_db(db)
            print(f"💾 Дата для '{title}' сохранена в локальную базу")
            return True
        return False

    def _search_date_with_api_and_confirm(self, title: str, media_type: str, api_func, parent=None) -> Optional[str]:
        cached_date = self._get_date_from_db(media_type, title)
        if cached_date:
            self.status_label.config(text=f"📂 Дата для '{title}' найдена в базе данных", fg="green")
            return cached_date
        
        self.status_label.config(text=f"🌐 Поиск даты для '{title}' через API...", fg="orange")
        self.root.update()
        
        try:
            release_date = api_func(title)
            db = self._load_db()
            db["stats"]["api_calls"] = db["stats"].get("api_calls", 0) + 1
            self._save_db(db)
        except Exception as e:
            db = self._load_db()
            db["stats"]["api_errors"] = db["stats"].get("api_errors", 0) + 1
            self._save_db(db)
            self.status_label.config(text=f"❌ Ошибка API: {e}", fg="red")
            return None
        
        if release_date:
            user_confirm = messagebox.askyesno(
                "Подтверждение даты",
                f"Найдена дата: {release_date}\n\nЭто верная дата для '{title}'?\n\n"
                f"✅ Да — сохранить в базу\n❌ Нет — пропустить"
            )
            if user_confirm:
                self._add_to_db(media_type, title, release_date)
                self.status_label.config(text=f"✅ Дата '{release_date}' сохранена в базу", fg="green")
                return release_date
            else:
                self.status_label.config(text=f"⚠️ Дата не подтверждена пользователем", fg="orange")
                return None
        else:
            self.status_label.config(text=f"❌ Дата не найдена в API", fg="red")
            return None

    def _safe_load_json(self, filepath: Path, default):
        try:
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except json.JSONDecodeError:
            backup = filepath.with_suffix('.json.bak')
            if filepath.exists():
                filepath.rename(backup)
            print(f"⚠️ Файл {filepath} повреждён, создан бэкап")
        except Exception as e:
            print(f"⚠️ Ошибка {filepath}: {e}")
        return default

    def _safe_save_json(self, filepath: Path, data):
        temp_file = filepath.with_suffix('.tmp')
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            temp_file.replace(filepath)
            return True
        except Exception as e:
            print(f"⚠️ Ошибка сохранения: {e}")
            return False

    def _on_closing(self):
        if self.video_player:
            self.video_player.stop()
        self._running = False
        self.root.destroy()

    def _schedule_auto_update(self):
        self.root.after(21600000, self._auto_update)

    def _auto_update(self):
        if self._running:
            self.refresh_all_news()
            self._schedule_auto_update()

    def _auto_find_missing_dates(self):
        updates = []
        
        for i, g in enumerate(self.user_games):
            if not g.get("release_date"):
                print(f"🔍 Поиск даты для игры: {g['title']}")
                date = self._search_date_with_api_and_confirm(g["title"], "games", GameReleaseAPI.search_game)
                if date:
                    updates.append((USER_GAMES_FILE, i, "release_date", date, "База данных"))
        
        for i, s in enumerate(self.user_series):
            if not s.get("release_date"):
                print(f"🔍 Поиск даты для сериала: {s['title']}")
                date = self._search_date_with_api_and_confirm(s["title"], "series", SeriesReleaseAPI.search_series)
                if date:
                    updates.append((USER_SERIES_FILE, i, "release_date", date, "База данных"))
        
        for i, a in enumerate(self.user_anime):
            if not a.get("release_date"):
                print(f"🔍 Поиск даты для аниме: {a['title']}")
                date = self._search_date_with_api_and_confirm(a["title"], "anime", AnimeReleaseAPI.search_anime)
                if date:
                    updates.append((USER_ANIME_FILE, i, "release_date", date, "База данных"))
        
        if updates:
            for filepath, idx, key, value, source in updates:
                data = self._safe_load_json(Path(filepath), [])
                if data and idx < len(data):
                    data[idx][key] = value
                    data[idx]["source"] = source
                    self._safe_save_json(Path(filepath), data)
            
            self._load_games()
            self._load_series()
            self._load_anime()
            self._load_calendar()
            print(f"✅ Автоматически найдено {len(updates)} дат")

    # ========== НАСТРОЙКА ВКЛАДОК С ФОНАМИ ==========
    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.news_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.news_frame, text="📰 НОВОСТИ")
        self._setup_news_tab()

        self.games_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.games_frame, text="🎮 ИГРЫ")
        self._setup_games_tab_with_bg()

        self.series_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.series_frame, text="🎬 СЕРИАЛЫ")
        self._setup_series_tab_with_bg()

        self.anime_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.anime_frame, text="🎌 АНИМЕ")
        self._setup_anime_tab_with_bg()

        self.manga_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.manga_frame, text="📚 МАНГА")
        self._setup_manga_tab_with_bg()

        self.calendar_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.calendar_frame, text="📅 УМНЫЙ КАЛЕНДАРЬ")
        self._setup_calendar_tab()

        self.stats_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.stats_frame, text="📊 СТАТИСТИКА")
        self._setup_stats_tab()

    def _setup_games_tab_with_bg(self):
        self.games_canvas = tk.Canvas(self.games_frame, bg=self.bg_color, highlightthickness=0)
        self.games_canvas.pack(fill="both", expand=True)
        
        self.games_bg_image = None
        self.games_bg_photo = None
        if BG_GAMES.exists():
            try:
                image = Image.open(BG_GAMES)
                self.games_bg_image = image
                self._resize_games_bg()
                self.games_canvas.bind("<Configure>", self._resize_games_bg)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки фона для игр: {e}")
        
        content_frame = tk.Frame(self.games_frame, bg=self.bg_color)
        self.games_canvas.create_window((0, 0), window=content_frame, anchor="nw")
        
        title = tk.Label(content_frame, text="🎮 МОИ ИГРЫ (самообучающийся календарь)", 
                        font=("Arial", 16, "bold"), fg=self.game_color, bg=self.bg_color)
        title.pack(pady=10)

        add_frame = tk.Frame(content_frame, bg=self.accent_color, relief="ridge", bd=2)
        add_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(add_frame, text="Название игры:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.new_game_entry = tk.Entry(add_frame, width=45)
        self.new_game_entry.pack(side="left", padx=10, pady=10)
        self.new_game_entry.bind("<Return>", lambda e: self._add_game_manual())

        tk.Label(add_frame, text="Платформа:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.game_platform = ttk.Combobox(add_frame, values=["PC", "PS5", "Xbox", "Switch", "Mobile"], width=8)
        self.game_platform.set("PC")
        self.game_platform.pack(side="left", padx=10, pady=10)

        tk.Label(add_frame, text="Статус:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.game_status = ttk.Combobox(add_frame, values=["Играю", "В планах", "Заброшено", "Пройдено"], width=10)
        self.game_status.set("В планах")
        self.game_status.pack(side="left", padx=10, pady=10)

        tk.Button(add_frame, text="➕ ДОБАВИТЬ", command=self._add_game_manual,
                  bg=self.highlight, fg="white", padx=15).pack(side="left", padx=20, pady=10)

        columns = ("title", "platform", "hours", "status", "release_date", "source", "rating")
        self.games_tree = ttk.Treeview(content_frame, columns=columns, show="headings", height=12)
        self.games_tree.heading("title", text="Игра")
        self.games_tree.heading("platform", text="Платформа")
        self.games_tree.heading("hours", text="Часов")
        self.games_tree.heading("status", text="Статус")
        self.games_tree.heading("release_date", text="Дата выхода")
        self.games_tree.heading("source", text="Источник")
        self.games_tree.heading("rating", text="Оценка")
        self.games_tree.column("title", width=250)
        self.games_tree.column("platform", width=80)
        self.games_tree.column("hours", width=60)
        self.games_tree.column("status", width=100)
        self.games_tree.column("release_date", width=110)
        self.games_tree.column("source", width=100)
        self.games_tree.column("rating", width=60)

        scroll = ttk.Scrollbar(content_frame, orient="vertical", command=self.games_tree.yview)
        self.games_tree.configure(yscrollcommand=scroll.set)
        self.games_tree.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scroll.pack(side="right", fill="y", pady=10)

        btn_frame = tk.Frame(content_frame, bg=self.bg_color)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="✓ +1 Час", command=self._add_game_hour,
                  bg=self.accent_color, fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="🔄 Обновить дату из API", command=self._refresh_game_date,
                  bg=self.accent_color, fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="🗑 Удалить", command=self._delete_game,
                  bg="#8b0000", fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="▶ СМОТРЕТЬ ТРЕЙЛЕР", command=lambda: self._play_trailer('games'),
                  bg=self.api_color, fg="white", padx=15).pack(side="left", padx=10)

        self._load_games()
        content_frame.update_idletasks()
        self.games_canvas.configure(scrollregion=self.games_canvas.bbox("all"))

    def _resize_games_bg(self, event=None):
        if self.games_bg_image:
            width = self.games_canvas.winfo_width()
            height = self.games_canvas.winfo_height()
            if width > 1 and height > 1:
                resized = self.games_bg_image.resize((width, height), Image.Resampling.LANCZOS)
                self.games_bg_photo = ImageTk.PhotoImage(resized)
                self.games_canvas.delete("bg")
                self.games_canvas.create_image(0, 0, image=self.games_bg_photo, anchor="nw", tags="bg")

    def _setup_series_tab_with_bg(self):
        self.series_canvas = tk.Canvas(self.series_frame, bg=self.bg_color, highlightthickness=0)
        self.series_canvas.pack(fill="both", expand=True)
        
        self.series_bg_image = None
        self.series_bg_photo = None
        if BG_SERIES.exists():
            try:
                image = Image.open(BG_SERIES)
                self.series_bg_image = image
                self._resize_series_bg()
                self.series_canvas.bind("<Configure>", self._resize_series_bg)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки фона для сериалов: {e}")
        
        content_frame = tk.Frame(self.series_frame, bg=self.bg_color)
        self.series_canvas.create_window((0, 0), window=content_frame, anchor="nw")
        
        title = tk.Label(content_frame, text="🎬 МОИ СЕРИАЛЫ (самообучающийся календарь)", 
                        font=("Arial", 16, "bold"), fg=self.series_color, bg=self.bg_color)
        title.pack(pady=10)

        add_frame = tk.Frame(content_frame, bg=self.accent_color, relief="ridge", bd=2)
        add_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(add_frame, text="Название сериала:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.new_series_entry = tk.Entry(add_frame, width=45)
        self.new_series_entry.pack(side="left", padx=10, pady=10)
        self.new_series_entry.bind("<Return>", lambda e: self._add_series_manual())

        tk.Label(add_frame, text="Текущий сезон:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.series_season = tk.Spinbox(add_frame, from_=1, to=20, width=5)
        self.series_season.pack(side="left", padx=10, pady=10)

        tk.Label(add_frame, text="Статус:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.series_status = ttk.Combobox(add_frame, values=["Смотрю", "В планах", "Заброшено", "Просмотрено"], width=10)
        self.series_status.set("В планах")
        self.series_status.pack(side="left", padx=10, pady=10)

        tk.Button(add_frame, text="➕ ДОБАВИТЬ", command=self._add_series_manual,
                  bg=self.highlight, fg="white", padx=15).pack(side="left", padx=20, pady=10)

        columns = ("title", "season", "episode", "release_date", "source", "status", "rating")
        self.series_tree = ttk.Treeview(content_frame, columns=columns, show="headings", height=12)
        self.series_tree.heading("title", text="Сериал")
        self.series_tree.heading("season", text="Сезон")
        self.series_tree.heading("episode", text="Серия")
        self.series_tree.heading("release_date", text="Дата премьеры")
        self.series_tree.heading("source", text="Источник")
        self.series_tree.heading("status", text="Статус")
        self.series_tree.heading("rating", text="Оценка")
        self.series_tree.column("title", width=280)
        self.series_tree.column("season", width=60)
        self.series_tree.column("episode", width=60)
        self.series_tree.column("release_date", width=110)
        self.series_tree.column("source", width=100)
        self.series_tree.column("status", width=100)
        self.series_tree.column("rating", width=60)

        scroll = ttk.Scrollbar(content_frame, orient="vertical", command=self.series_tree.yview)
        self.series_tree.configure(yscrollcommand=scroll.set)
        self.series_tree.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scroll.pack(side="right", fill="y", pady=10)

        btn_frame = tk.Frame(content_frame, bg=self.bg_color)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="✓ +1 Серия", command=self._add_series_episode,
                  bg=self.accent_color, fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="🔄 Обновить дату из API", command=self._refresh_series_date,
                  bg=self.accent_color, fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="🗑 Удалить", command=self._delete_series,
                  bg="#8b0000", fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="▶ СМОТРЕТЬ ТРЕЙЛЕР", command=lambda: self._play_trailer('series'),
                  bg=self.api_color, fg="white", padx=15).pack(side="left", padx=10)

        self._load_series()
        content_frame.update_idletasks()
        self.series_canvas.configure(scrollregion=self.series_canvas.bbox("all"))

    def _resize_series_bg(self, event=None):
        if self.series_bg_image:
            width = self.series_canvas.winfo_width()
            height = self.series_canvas.winfo_height()
            if width > 1 and height > 1:
                resized = self.series_bg_image.resize((width, height), Image.Resampling.LANCZOS)
                self.series_bg_photo = ImageTk.PhotoImage(resized)
                self.series_canvas.delete("bg")
                self.series_canvas.create_image(0, 0, image=self.series_bg_photo, anchor="nw", tags="bg")

    def _setup_anime_tab_with_bg(self):
        self.anime_canvas = tk.Canvas(self.anime_frame, bg=self.bg_color, highlightthickness=0)
        self.anime_canvas.pack(fill="both", expand=True)
        
        self.anime_bg_image = None
        self.anime_bg_photo = None
        if BG_ANIME.exists():
            try:
                image = Image.open(BG_ANIME)
                self.anime_bg_image = image
                self._resize_anime_bg()
                self.anime_canvas.bind("<Configure>", self._resize_anime_bg)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки фона для аниме: {e}")
        
        content_frame = tk.Frame(self.anime_frame, bg=self.bg_color)
        self.anime_canvas.create_window((0, 0), window=content_frame, anchor="nw")
        
        title = tk.Label(content_frame, text="🎌 МОИ АНИМЕ (самообучающийся календарь)", 
                        font=("Arial", 16, "bold"), fg=self.anime_color, bg=self.bg_color)
        title.pack(pady=10)

        add_frame = tk.Frame(content_frame, bg=self.accent_color, relief="ridge", bd=2)
        add_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(add_frame, text="Название аниме:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.new_anime_entry = tk.Entry(add_frame, width=45)
        self.new_anime_entry.pack(side="left", padx=10, pady=10)
        self.new_anime_entry.bind("<Return>", lambda e: self._add_anime_manual())

        tk.Label(add_frame, text="Тип:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.anime_type = ttk.Combobox(add_frame, values=["TV", "Movie", "OVA", "Special"], width=8)
        self.anime_type.set("TV")
        self.anime_type.pack(side="left", padx=10, pady=10)

        tk.Label(add_frame, text="Статус:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.anime_status = ttk.Combobox(add_frame, values=["Смотрю", "В планах", "Заброшено", "Просмотрено"], width=10)
        self.anime_status.set("В планах")
        self.anime_status.pack(side="left", padx=10, pady=10)

        tk.Button(add_frame, text="➕ ДОБАВИТЬ", command=self._add_anime_manual,
                  bg=self.highlight, fg="white", padx=15).pack(side="left", padx=20, pady=10)

        columns = ("title", "type", "episodes", "watched", "release_date", "source", "status", "rating")
        self.anime_tree = ttk.Treeview(content_frame, columns=columns, show="headings", height=12)
        self.anime_tree.heading("title", text="Аниме")
        self.anime_tree.heading("type", text="Тип")
        self.anime_tree.heading("episodes", text="Всего серий")
        self.anime_tree.heading("watched", text="Просмотрено")
        self.anime_tree.heading("release_date", text="Дата выхода")
        self.anime_tree.heading("source", text="Источник")
        self.anime_tree.heading("status", text="Статус")
        self.anime_tree.heading("rating", text="Оценка")
        self.anime_tree.column("title", width=230)
        self.anime_tree.column("type", width=60)
        self.anime_tree.column("episodes", width=80)
        self.anime_tree.column("watched", width=80)
        self.anime_tree.column("release_date", width=110)
        self.anime_tree.column("source", width=100)
        self.anime_tree.column("status", width=100)
        self.anime_tree.column("rating", width=60)

        scroll = ttk.Scrollbar(content_frame, orient="vertical", command=self.anime_tree.yview)
        self.anime_tree.configure(yscrollcommand=scroll.set)
        self.anime_tree.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scroll.pack(side="right", fill="y", pady=10)

        btn_frame = tk.Frame(content_frame, bg=self.bg_color)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="✓ +1 Серия", command=self._add_anime_episode,
                  bg=self.accent_color, fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="🔄 Обновить дату из API", command=self._refresh_anime_date,
                  bg=self.accent_color, fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="🗑 Удалить", command=self._delete_anime,
                  bg="#8b0000", fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="▶ СМОТРЕТЬ ТРЕЙЛЕР", command=lambda: self._play_trailer('anime'),
                  bg=self.api_color, fg="white", padx=15).pack(side="left", padx=10)

        self._load_anime()
        content_frame.update_idletasks()
        self.anime_canvas.configure(scrollregion=self.anime_canvas.bbox("all"))

    def _resize_anime_bg(self, event=None):
        if self.anime_bg_image:
            width = self.anime_canvas.winfo_width()
            height = self.anime_canvas.winfo_height()
            if width > 1 and height > 1:
                resized = self.anime_bg_image.resize((width, height), Image.Resampling.LANCZOS)
                self.anime_bg_photo = ImageTk.PhotoImage(resized)
                self.anime_canvas.delete("bg")
                self.anime_canvas.create_image(0, 0, image=self.anime_bg_photo, anchor="nw", tags="bg")

    def _setup_manga_tab_with_bg(self):
        self.manga_canvas = tk.Canvas(self.manga_frame, bg=self.bg_color, highlightthickness=0)
        self.manga_canvas.pack(fill="both", expand=True)
        
        self.manga_bg_image = None
        self.manga_bg_photo = None
        if BG_MANGA.exists():
            try:
                image = Image.open(BG_MANGA)
                self.manga_bg_image = image
                self._resize_manga_bg()
                self.manga_canvas.bind("<Configure>", self._resize_manga_bg)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки фона для манги: {e}")
        
        content_frame = tk.Frame(self.manga_frame, bg=self.bg_color)
        self.manga_canvas.create_window((0, 0), window=content_frame, anchor="nw")
        
        title = tk.Label(content_frame, text="📚 МОЯ МАНГА", font=("Arial", 16, "bold"),
                        fg=self.fg_color, bg=self.bg_color)
        title.pack(pady=10)

        add_frame = tk.Frame(content_frame, bg=self.accent_color, relief="ridge", bd=2)
        add_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(add_frame, text="Название:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.new_manga_entry = tk.Entry(add_frame, width=45)
        self.new_manga_entry.pack(side="left", padx=10, pady=10)
        self.new_manga_entry.bind("<Return>", lambda e: self._add_manga())

        tk.Label(add_frame, text="Всего томов:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.manga_total = tk.Spinbox(add_frame, from_=1, to=100, width=5)
        self.manga_total.pack(side="left", padx=10, pady=10)

        tk.Label(add_frame, text="Статус:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.manga_status = ttk.Combobox(add_frame, values=["Читаю", "В планах", "Заброшено", "Прочитано"], width=10)
        self.manga_status.set("Читаю")
        self.manga_status.pack(side="left", padx=10, pady=10)

        tk.Button(add_frame, text="➕ ДОБАВИТЬ", command=self._add_manga,
                  bg=self.highlight, fg="white", padx=15).pack(side="left", padx=20, pady=10)

        columns = ("title", "volumes", "read", "status", "rating")
        self.manga_tree = ttk.Treeview(content_frame, columns=columns, show="headings", height=12)
        self.manga_tree.heading("title", text="Манга")
        self.manga_tree.heading("volumes", text="Всего томов")
        self.manga_tree.heading("read", text="Прочитано")
        self.manga_tree.heading("status", text="Статус")
        self.manga_tree.heading("rating", text="Оценка")
        self.manga_tree.column("title", width=380)
        self.manga_tree.column("volumes", width=80)
        self.manga_tree.column("read", width=80)
        self.manga_tree.column("status", width=100)
        self.manga_tree.column("rating", width=60)

        scroll = ttk.Scrollbar(content_frame, orient="vertical", command=self.manga_tree.yview)
        self.manga_tree.configure(yscrollcommand=scroll.set)
        self.manga_tree.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scroll.pack(side="right", fill="y", pady=10)

        self.manga_tree.bind("<Double-1>", self._open_manga_search)
        self.manga_tree.bind("<Button-3>", self._show_manga_context_menu)

        btn_frame = tk.Frame(content_frame, bg=self.bg_color)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="✓ +1 Том", command=self._add_manga_volume,
                  bg=self.accent_color, fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="🗑 Удалить", command=self._delete_manga,
                  bg="#8b0000", fg="white", padx=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="🔍 ПОИСК МАНГИ", command=self._search_selected_manga,
                  bg=self.accent_color, fg="white", padx=15).pack(side="left", padx=10)

        self._load_manga()
        content_frame.update_idletasks()
        self.manga_canvas.configure(scrollregion=self.manga_canvas.bbox("all"))

    def _resize_manga_bg(self, event=None):
        if self.manga_bg_image:
            width = self.manga_canvas.winfo_width()
            height = self.manga_canvas.winfo_height()
            if width > 1 and height > 1:
                resized = self.manga_bg_image.resize((width, height), Image.Resampling.LANCZOS)
                self.manga_bg_photo = ImageTk.PhotoImage(resized)
                self.manga_canvas.delete("bg")
                self.manga_canvas.create_image(0, 0, image=self.manga_bg_photo, anchor="nw", tags="bg")

    # ========== НОВОСТИ ==========
    def _setup_news_tab(self):
        title = tk.Label(self.news_frame, text="📰 АКТУАЛЬНЫЕ НОВОСТИ",
                        font=("Arial", 18, "bold"), fg=self.highlight, bg=self.bg_color)
        title.pack(pady=10)

        filter_frame = tk.Frame(self.news_frame, bg=self.accent_color)
        filter_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(filter_frame, text="Категория:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10)
        self.category_filter = ttk.Combobox(filter_frame, values=["Все", "Игры", "Сериалы", "Аниме"], width=15)
        self.category_filter.set("Все")
        self.category_filter.pack(side="left", padx=10)
        self.category_filter.bind("<<ComboboxSelected>>", lambda e: self._filter_news())

        tk.Label(filter_frame, text="Поиск:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10)
        self.search_entry = tk.Entry(filter_frame, width=45)
        self.search_entry.pack(side="left", padx=10)
        self.search_entry.bind("<Return>", lambda e: self._search_news())

        self.search_btn = tk.Button(filter_frame, text="🔍 НАЙТИ", command=self._search_news,
                                     bg=self.highlight, fg="white", padx=15)
        self.search_btn.pack(side="left", padx=10)

        self.refresh_btn = tk.Button(filter_frame, text="🔄 ОБНОВИТЬ", command=self.refresh_all_news,
                                      bg=self.accent_color, fg="white", padx=15)
        self.refresh_btn.pack(side="left", padx=10)

        self.progress_bar = ttk.Progressbar(self.news_frame, mode='indeterminate')
        self.status_label = tk.Label(self.news_frame, text="🔄 Загрузка новостей...",
                                      fg="orange", bg=self.bg_color, font=("Arial", 10))
        self.status_label.pack(pady=5)

        columns = ("date", "lang", "category", "source", "title")
        self.news_tree = ttk.Treeview(self.news_frame, columns=columns, show="headings", height=18)
        self.news_tree.heading("date", text="Дата")
        self.news_tree.heading("lang", text="Язык")
        self.news_tree.heading("category", text="Категория")
        self.news_tree.heading("source", text="Источник")
        self.news_tree.heading("title", text="Заголовок")
        self.news_tree.column("date", width=120)
        self.news_tree.column("lang", width=50)
        self.news_tree.column("category", width=80)
        self.news_tree.column("source", width=150)
        self.news_tree.column("title", width=550)

        scroll_y = ttk.Scrollbar(self.news_frame, orient="vertical", command=self.news_tree.yview)
        self.news_tree.configure(yscrollcommand=scroll_y.set)
        self.news_tree.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scroll_y.pack(side="right", fill="y", pady=10)

        self.news_tree.bind("<Double-1>", lambda e: self._open_news())
        self.news_tree.bind("<<TreeviewSelect>>", self._show_news_preview)

        preview_frame = tk.Frame(self.news_frame, bg=self.accent_color, relief="ridge", bd=2)
        preview_frame.pack(fill="x", padx=20, pady=10)

        btn_frame = tk.Frame(preview_frame, bg=self.accent_color)
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(btn_frame, text="Предпросмотр:", fg=self.fg_color, bg=self.accent_color,
                 font=("Arial", 10, "bold")).pack(side="left")

        self.news_preview = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, height=6,
                                                       font=("Arial", 9), bg="#2a2a3e", fg=self.fg_color)
        self.news_preview.pack(fill="both", expand=True, padx=10, pady=10)

    def refresh_all_news(self):
        self.status_label.config(text="🔄 Загрузка свежих новостей...", fg="orange")
        self.refresh_btn.config(state="disabled")
        self.progress_bar.pack(fill="x", padx=20, pady=5)
        self.progress_bar.start(10)
        
        def load():
            all_news = []
            
            for source_name, feed_url in RSS_SOURCES.items():
                try:
                    feed = feedparser.parse(feed_url)
                    lang = "🇷🇺 RU" if source_name in RU_RSS_SOURCES else "🇬🇧 EN"
                    
                    for entry in feed.entries[:8]:
                        if source_name in SOURCE_CATEGORIES["Игры"]:
                            cat = "Игры"
                        elif source_name in SOURCE_CATEGORIES["Сериалы"]:
                            cat = "Сериалы"
                        else:
                            cat = "Аниме"
                        
                        all_news.append({
                            "source": source_name,
                            "lang": lang,
                            "category": cat,
                            "title": entry.get('title', ''),
                            "link": entry.get('link', ''),
                            "summary": re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:500],
                            "date": entry.get('published', '')
                        })
                except Exception as e:
                    print(f"Ошибка {source_name}: {e}")
            
            for category, queries in RUSSIAN_SEARCH_QUERIES.items():
                for query in queries:
                    try:
                        encoded = urllib.parse.quote(query)
                        url = f"https://news.google.com/rss/search?q={encoded}&hl=ru"
                        feed = feedparser.parse(url)
                        for entry in feed.entries[:5]:
                            all_news.append({
                                "source": "Google News",
                                "lang": "🇷🇺 RU",
                                "category": category,
                                "title": entry.get('title', ''),
                                "link": entry.get('link', ''),
                                "summary": re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:500],
                                "date": entry.get('published', '')
                            })
                    except Exception as e:
                        print(f"Ошибка поиска {query}: {e}")
            
            all_news.sort(key=lambda x: x['date'], reverse=True)
            self.current_news = all_news[:200]
            self.root.after(0, self._display_news)
        
        threading.Thread(target=load, daemon=True).start()

    def _display_news(self):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.refresh_btn.config(state="normal")
        
        for item in self.news_tree.get_children():
            self.news_tree.delete(item)
        
        if not self.current_news:
            self.status_label.config(text="❌ Не удалось загрузить новости", fg="red")
            return
        
        for news in self.current_news:
            self.news_tree.insert("", "end", values=(
                news["date"][:16] if news["date"] else "Дата неизв.",
                news["lang"],
                news["category"],
                news["source"],
                news["title"][:100]
            ))
        
        ru_count = sum(1 for n in self.current_news if n["lang"] == "🇷🇺 RU")
        en_count = sum(1 for n in self.current_news if n["lang"] == "🇬🇧 EN")
        self.status_label.config(text=f"✅ Загружено {len(self.current_news)} новостей (🇷🇺 {ru_count} | 🇬🇧 {en_count})", fg="green")

    def _filter_news(self):
        category = self.category_filter.get()
        if not self.current_news:
            return
        
        for item in self.news_tree.get_children():
            self.news_tree.delete(item)
        
        filtered = [n for n in self.current_news if category == "Все" or n["category"] == category]
        for news in filtered:
            self.news_tree.insert("", "end", values=(
                news["date"][:16] if news["date"] else "Дата неизв.",
                news["lang"],
                news["category"],
                news["source"],
                news["title"][:100]
            ))
        
        ru_count = sum(1 for n in filtered if n["lang"] == "🇷🇺 RU")
        en_count = sum(1 for n in filtered if n["lang"] == "🇬🇧 EN")
        self.status_label.config(text=f"✅ Показано {len(filtered)} новостей (🇷🇺 {ru_count} | 🇬🇧 {en_count})", fg="green")

    def _search_news(self):
        query = self.search_entry.get().strip()
        if not query or len(query) < 3:
            self.status_label.config(text="❌ Введите минимум 3 символа", fg="red")
            return

        self._search_cancelled = True
        self.status_label.config(text=f"🔍 Поиск '{query}'...", fg="orange")
        self.search_btn.config(state="disabled", text="⏳ ПОИСК...")
        self.progress_bar.pack(fill="x", padx=20, pady=5)
        self.progress_bar.start(10)

        for item in self.news_tree.get_children():
            self.news_tree.delete(item)

        found_news = []
        seen_links = set()

        # --- БЛОК 1: Поиск через Google News ---
        try:
            encoded = urllib.parse.quote(f"{query}")
            url = f"https://news.google.com/rss/search?q={encoded}&hl=ru"
            feed = feedparser.parse(url)
            
            category_map = {
                "игровые новости": "Игры", "новости игр": "Игры",
                "новости сериалов": "Сериалы", "сериалы новости": "Сериалы",
                "новости аниме": "Аниме", "аниме новости": "Аниме"
            }
            search_category = "Новости"
            for key in category_map:
                if key.lower() in query.lower():
                    search_category = category_map[key]
                    break

            for entry in feed.entries[:20]:
                if self._search_cancelled:
                    return
                link = entry.get('link', '')
                if link and link not in seen_links:
                    seen_links.add(link)
                    found_news.append({
                        "source": "Google News",
                        "lang": "🇷🇺 RU",
                        "category": search_category,
                        "title": entry.get('title', ''),
                        "link": link,
                        "summary": re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:500],
                        "date": entry.get('published', '')
                    })
        except Exception as e:
            print(f"Ошибка поиска в Google News: {e}")

        # --- БЛОК 2: Поиск по RSS-источникам ---
        for source_name, feed_url in RSS_SOURCES.items():
            if self._search_cancelled:
                return
            try:
                feed = feedparser.parse(feed_url)
                lang = "🇷🇺 RU" if source_name in RU_RSS_SOURCES else "🇬🇧 EN"
                
                if source_name in SOURCE_CATEGORIES["Игры"]:
                    cat = "Игры"
                elif source_name in SOURCE_CATEGORIES["Сериалы"]:
                    cat = "Сериалы"
                else:
                    cat = "Аниме"

                for entry in feed.entries[:10]:
                    title = entry.get('title', '').lower()
                    if query.lower() in title:
                        link = entry.get('link', '')
                        if link and link not in seen_links:
                            seen_links.add(link)
                            found_news.append({
                                "source": source_name,
                                "lang": lang,
                                "category": cat,
                                "title": entry.get('title', ''),
                                "link": link,
                                "summary": re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:500],
                                "date": entry.get('published', '')
                            })
            except Exception as e:
                print(f"Ошибка доступа к {source_name}: {e}")
                continue

        if not self._search_cancelled:
            self.root.after(0, lambda: self._display_search_results(found_news, query))

    def _display_search_results(self, results, query):
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.search_btn.config(state="normal", text="🔍 НАЙТИ")
        
        for item in self.news_tree.get_children():
            self.news_tree.delete(item)
        
        if not results:
            self.status_label.config(text=f"❌ Новостей про '{query}' не найдено", fg="red")
            return
        
        for news in results:
            self.news_tree.insert("", "end", values=(
                news["date"][:16] if news["date"] else "Дата неизв.",
                news["lang"],
                news["category"],
                news["source"],
                news["title"][:100]
            ))
        
        ru_count = sum(1 for n in results if n["lang"] == "🇷🇺 RU")
        en_count = sum(1 for n in results if n["lang"] == "🇬🇧 EN")
        self.status_label.config(text=f"✅ Найдено {len(results)} новостей (🇷🇺 {ru_count} | 🇬🇧 {en_count})", fg="green")

    def _get_current_selected_news(self):
        selection = self.news_tree.selection()
        if not selection:
            return None
        
        idx = self.news_tree.index(selection[0])
        category = self.category_filter.get()
        
        current = [n for n in self.current_news if category == "Все" or n["category"] == category]
        
        if idx >= len(current):
            return None
        
        return current[idx]

    def _show_news_preview(self, event):
        news = self._get_current_selected_news()
        if news:
            self.news_preview.delete(1.0, tk.END)
            preview = f"📰 {news['title']}\n\n📅 {news['date']}\n🌐 {news['lang']}\n📡 {news['source']}\n🔗 {news['link']}\n\n📄 {news['summary']}"
            self.news_preview.insert(1.0, preview)

    def _open_news(self):
        news = self._get_current_selected_news()
        if news:
            webbrowser.open(news["link"])

    # ========== ИГРЫ ==========
    def _add_game_manual(self):
        title = self.new_game_entry.get().strip()
        if not title:
            messagebox.showwarning("Ошибка", "Введите название игры")
            return
        
        self.status_label.config(text=f"🔍 Поиск даты для '{title}'...", fg="orange")
        self.root.update()
        
        def process():
            release_date = self._search_date_with_api_and_confirm(title, "games", GameReleaseAPI.search_game)
            
            game = {
                "title": title,
                "platform": self.game_platform.get(),
                "hours": 0,
                "status": self.game_status.get(),
                "release_date": release_date,
                "source": "База данных" if release_date and self._get_date_from_db("games", title) else ("API" if release_date else "—"),
                "rating": 0,
                "added": datetime.now().isoformat()
            }
            
            self.user_games.append(game)
            self._safe_save_json(USER_GAMES_FILE, self.user_games)
            self.root.after(0, lambda: self._on_game_added(title, release_date))
        
        threading.Thread(target=process, daemon=True).start()

    def _on_game_added(self, title, release_date):
        self._load_games()
        self._load_calendar()
        self.new_game_entry.delete(0, tk.END)
        self.status_label.config(text="✅ Готово", fg="green")
        
        if release_date:
            messagebox.showinfo("Успех", f"Игра '{title}' добавлена!\nДата выхода: {release_date}\n(сохранено в базу)")
        else:
            messagebox.showinfo("Успех", f"Игра '{title}' добавлена!\n(дата не найдена)")

    def _refresh_game_date(self):
        sel = self.games_tree.selection()
        if not sel:
            messagebox.showwarning("Ошибка", "Выберите игру")
            return
        idx = int(sel[0])
        game = self.user_games[idx]
        
        self.status_label.config(text=f"🔍 Поиск даты для '{game['title']}'...", fg="orange")
        
        def process():
            release_date = self._search_date_with_api_and_confirm(game["title"], "games", GameReleaseAPI.search_game)
            if release_date:
                game["release_date"] = release_date
                game["source"] = "База данных" if self._get_date_from_db("games", game["title"]) else "API"
                self._safe_save_json(USER_GAMES_FILE, self.user_games)
                self.root.after(0, lambda: self._load_games())
                self.root.after(0, lambda: self._load_calendar())
                self.root.after(0, lambda: messagebox.showinfo("Успех", f"Дата обновлена: {release_date}"))
            else:
                self.root.after(0, lambda: messagebox.showinfo("Не найдено", "Дата не найдена"))
        
        threading.Thread(target=process, daemon=True).start()

    def _load_games(self):
        for item in self.games_tree.get_children():
            self.games_tree.delete(item)
        for i, g in enumerate(self.user_games):
            release = g.get("release_date", "-")
            source = g.get("source", "—")
            if source == "База данных":
                release_display = f"✅ {release}"
            elif source == "API":
                release_display = f"🌐 {release}"
            else:
                release_display = release
            self.games_tree.insert("", "end", iid=str(i), values=(
                g["title"], g["platform"], g.get("hours", 0),
                g["status"], release_display, source, f"⭐ {g.get('rating', 0)}"
            ))

    def _add_game_hour(self):
        sel = self.games_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.user_games[idx]["hours"] = self.user_games[idx].get("hours", 0) + 1
        self._safe_save_json(USER_GAMES_FILE, self.user_games)
        self._load_games()

    def _delete_game(self):
        sel = self.games_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if messagebox.askyesno("Подтверждение", f"Удалить '{self.user_games[idx]['title']}'?"):
            self.user_games.pop(idx)
            self._safe_save_json(USER_GAMES_FILE, self.user_games)
            self._load_games()
            self._load_calendar()

    # ========== СЕРИАЛЫ ==========
    def _add_series_manual(self):
        title = self.new_series_entry.get().strip()
        if not title:
            messagebox.showwarning("Ошибка", "Введите название сериала")
            return
        
        self.status_label.config(text=f"🔍 Поиск даты для '{title}'...", fg="orange")
        self.root.update()
        
        def process():
            release_date = self._search_date_with_api_and_confirm(title, "series", SeriesReleaseAPI.search_series)
            
            series = {
                "title": title,
                "season": int(self.series_season.get()),
                "episode": 1,
                "release_date": release_date,
                "source": "База данных" if release_date and self._get_date_from_db("series", title) else ("API" if release_date else "—"),
                "status": self.series_status.get(),
                "rating": 0,
                "added": datetime.now().isoformat()
            }
            
            self.user_series.append(series)
            self._safe_save_json(USER_SERIES_FILE, self.user_series)
            self.root.after(0, lambda: self._on_series_added(title, release_date))
        
        threading.Thread(target=process, daemon=True).start()

    def _on_series_added(self, title, release_date):
        self._load_series()
        self._load_calendar()
        self.new_series_entry.delete(0, tk.END)
        self.status_label.config(text="✅ Готово", fg="green")
        
        if release_date:
            messagebox.showinfo("Успех", f"Сериал '{title}' добавлен!\nДата премьеры: {release_date}\n(сохранено в базу)")
        else:
            messagebox.showinfo("Успех", f"Сериал '{title}' добавлен!\n(дата не найдена)")

    def _refresh_series_date(self):
        sel = self.series_tree.selection()
        if not sel:
            messagebox.showwarning("Ошибка", "Выберите сериал")
            return
        idx = int(sel[0])
        series = self.user_series[idx]
        
        self.status_label.config(text=f"🔍 Поиск даты для '{series['title']}'...", fg="orange")
        
        def process():
            release_date = self._search_date_with_api_and_confirm(series["title"], "series", SeriesReleaseAPI.search_series)
            if release_date:
                series["release_date"] = release_date
                series["source"] = "База данных" if self._get_date_from_db("series", series["title"]) else "API"
                self._safe_save_json(USER_SERIES_FILE, self.user_series)
                self.root.after(0, lambda: self._load_series())
                self.root.after(0, lambda: self._load_calendar())
                self.root.after(0, lambda: messagebox.showinfo("Успех", f"Дата обновлена: {release_date}"))
            else:
                self.root.after(0, lambda: messagebox.showinfo("Не найдено", "Дата не найдена"))
        
        threading.Thread(target=process, daemon=True).start()

    def _load_series(self):
        for item in self.series_tree.get_children():
            self.series_tree.delete(item)
        for i, s in enumerate(self.user_series):
            release = s.get("release_date", "-")
            source = s.get("source", "—")
            if source == "База данных":
                release_display = f"✅ {release}"
            elif source == "API":
                release_display = f"🌐 {release}"
            else:
                release_display = release
            self.series_tree.insert("", "end", iid=str(i), values=(
                s["title"], s["season"], s["episode"], release_display, source,
                s["status"], f"⭐ {s.get('rating', 0)}"
            ))

    def _add_series_episode(self):
        sel = self.series_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        s = self.user_series[idx]
        s["episode"] += 1
        self._safe_save_json(USER_SERIES_FILE, self.user_series)
        self._load_series()

    def _delete_series(self):
        sel = self.series_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if messagebox.askyesno("Подтверждение", f"Удалить '{self.user_series[idx]['title']}'?"):
            self.user_series.pop(idx)
            self._safe_save_json(USER_SERIES_FILE, self.user_series)
            self._load_series()
            self._load_calendar()

    # ========== АНИМЕ ==========
    def _add_anime_manual(self):
        title = self.new_anime_entry.get().strip()
        if not title:
            messagebox.showwarning("Ошибка", "Введите название аниме")
            return
        
        self.status_label.config(text=f"🔍 Поиск даты для '{title}'...", fg="orange")
        self.root.update()
        
        def process():
            release_date = self._search_date_with_api_and_confirm(title, "anime", AnimeReleaseAPI.search_anime)
            
            anime = {
                "title": title,
                "type": self.anime_type.get(),
                "episodes": 0,
                "watched": 0,
                "release_date": release_date,
                "source": "База данных" if release_date and self._get_date_from_db("anime", title) else ("API" if release_date else "—"),
                "status": self.anime_status.get(),
                "rating": 0,
                "added": datetime.now().isoformat()
            }
            
            self.user_anime.append(anime)
            self._safe_save_json(USER_ANIME_FILE, self.user_anime)
            self.root.after(0, lambda: self._on_anime_added(title, release_date))
        
        threading.Thread(target=process, daemon=True).start()

    def _on_anime_added(self, title, release_date):
        self._load_anime()
        self._load_calendar()
        self.new_anime_entry.delete(0, tk.END)
        self.status_label.config(text="✅ Готово", fg="green")
        
        if release_date:
            messagebox.showinfo("Успех", f"Аниме '{title}' добавлено!\nДата выхода: {release_date}\n(сохранено в базу)")
        else:
            messagebox.showinfo("Успех", f"Аниме '{title}' добавлено!\n(дата не найдена)")

    def _refresh_anime_date(self):
        sel = self.anime_tree.selection()
        if not sel:
            messagebox.showwarning("Ошибка", "Выберите аниме")
            return
        idx = int(sel[0])
        anime = self.user_anime[idx]
        
        self.status_label.config(text=f"🔍 Поиск даты для '{anime['title']}'...", fg="orange")
        
        def process():
            release_date = self._search_date_with_api_and_confirm(anime["title"], "anime", AnimeReleaseAPI.search_anime)
            if release_date:
                anime["release_date"] = release_date
                anime["source"] = "База данных" if self._get_date_from_db("anime", anime["title"]) else "API"
                self._safe_save_json(USER_ANIME_FILE, self.user_anime)
                self.root.after(0, lambda: self._load_anime())
                self.root.after(0, lambda: self._load_calendar())
                self.root.after(0, lambda: messagebox.showinfo("Успех", f"Дата обновлена: {release_date}"))
            else:
                self.root.after(0, lambda: messagebox.showinfo("Не найдено", "Дата не найдена"))
        
        threading.Thread(target=process, daemon=True).start()

    def _load_anime(self):
        for item in self.anime_tree.get_children():
            self.anime_tree.delete(item)
        for i, a in enumerate(self.user_anime):
            release = a.get("release_date", "-")
            source = a.get("source", "—")
            if source == "База данных":
                release_display = f"✅ {release}"
            elif source == "API":
                release_display = f"🌐 {release}"
            else:
                release_display = release
            self.anime_tree.insert("", "end", iid=str(i), values=(
                a["title"], a.get("type", "TV"), a.get("episodes", "?"), 
                f"{a.get('watched', 0)}/{a.get('episodes', '?')}",
                release_display, source, a["status"], f"⭐ {a.get('rating', 0)}"
            ))

    def _add_anime_episode(self):
        sel = self.anime_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        a = self.user_anime[idx]
        a["watched"] = a.get("watched", 0) + 1
        if a.get("episodes") and a["watched"] >= a["episodes"]:
            a["status"] = "Просмотрено"
        self._safe_save_json(USER_ANIME_FILE, self.user_anime)
        self._load_anime()

    def _delete_anime(self):
        sel = self.anime_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if messagebox.askyesno("Подтверждение", f"Удалить '{self.user_anime[idx]['title']}'?"):
            self.user_anime.pop(idx)
            self._safe_save_json(USER_ANIME_FILE, self.user_anime)
            self._load_anime()
            self._load_calendar()

    # ========== МАНГА ==========
    def _add_manga(self):
        title = self.new_manga_entry.get().strip()
        if not title:
            messagebox.showwarning("Ошибка", "Введите название манги")
            return
        manga = {
            "title": title,
            "total_volumes": int(self.manga_total.get()),
            "read_volumes": 0,
            "status": self.manga_status.get(),
            "rating": 0,
            "added": datetime.now().isoformat()
        }
        self.user_manga.append(manga)
        self._safe_save_json(USER_MANGA_FILE, self.user_manga)
        self._load_manga()
        self.new_manga_entry.delete(0, tk.END)

    def _load_manga(self):
        for item in self.manga_tree.get_children():
            self.manga_tree.delete(item)
        for i, m in enumerate(self.user_manga):
            self.manga_tree.insert("", "end", iid=str(i), values=(
                m["title"], m.get("total_volumes", "?"), f"{m.get('read_volumes', 0)}/{m.get('total_volumes', '?')}",
                m["status"], f"⭐ {m.get('rating', 0)}"
            ))

    def _add_manga_volume(self):
        sel = self.manga_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        m = self.user_manga[idx]
        m["read_volumes"] = m.get("read_volumes", 0) + 1
        if m.get("total_volumes") and m["read_volumes"] >= m["total_volumes"]:
            m["status"] = "Прочитано"
        self._safe_save_json(USER_MANGA_FILE, self.user_manga)
        self._load_manga()

    def _delete_manga(self):
        sel = self.manga_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        if messagebox.askyesno("Подтверждение", f"Удалить '{self.user_manga[idx]['title']}'?"):
            self.user_manga.pop(idx)
            self._safe_save_json(USER_MANGA_FILE, self.user_manga)
            self._load_manga()

    def _show_manga_context_menu(self, event):
        row_id = self.manga_tree.identify_row(event.y)
        if not row_id:
            return
        self.manga_tree.selection_set(row_id)
        idx = int(row_id)
        manga_title = self.user_manga[idx]["title"]
        
        menu = tk.Menu(self.root, tearoff=0, bg=self.accent_color, fg=self.fg_color)
        menu.add_command(label=f"🔍 Поиск '{manga_title}'", command=lambda: self._search_manga(manga_title))
        menu.add_command(label=f"📖 Поиск '{manga_title}' читать онлайн", 
                        command=lambda: self._search_manga(manga_title + " читать онлайн"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_manga_search(self, event):
        sel = self.manga_tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        manga_title = self.user_manga[idx]["title"]
        self._search_manga(manga_title)

    def _search_selected_manga(self):
        sel = self.manga_tree.selection()
        if not sel:
            messagebox.showwarning("Ошибка", "Выберите мангу для поиска")
            return
        idx = int(sel[0])
        manga_title = self.user_manga[idx]["title"]
        self._search_manga(manga_title)

    def _search_manga(self, query: str):
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://yandex.ru/search/?text={encoded_query}"
        webbrowser.open(search_url)

    # ========== КАЛЕНДАРЬ ==========
    def _setup_calendar_tab(self):
        title = tk.Label(self.calendar_frame, text="📅 УМНЫЙ КАЛЕНДАРЬ РЕЛИЗОВ", font=("Arial", 18, "bold"),
                        fg=self.highlight, bg=self.bg_color)
        title.pack(pady=10)

        filter_frame = tk.Frame(self.calendar_frame, bg=self.accent_color)
        filter_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(filter_frame, text="Тип медиа:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10)
        self.calendar_filter = ttk.Combobox(filter_frame, values=["Все", "Игры", "Сериалы", "Аниме"], width=15)
        self.calendar_filter.set("Все")
        self.calendar_filter.pack(side="left", padx=10)
        self.calendar_filter.bind("<<ComboboxSelected>>", lambda e: self._load_calendar())

        self.calendar_status = tk.Label(self.calendar_frame, text="", fg=self.fg_color, bg=self.bg_color)
        self.calendar_status.pack(pady=5)

        columns = ("type", "title", "date", "status", "source")
        self.calendar_tree = ttk.Treeview(self.calendar_frame, columns=columns, show="headings", height=18)
        self.calendar_tree.heading("type", text="Тип")
        self.calendar_tree.heading("title", text="Название")
        self.calendar_tree.heading("date", text="Дата выхода")
        self.calendar_tree.heading("status", text="Статус")
        self.calendar_tree.heading("source", text="Источник")
        self.calendar_tree.column("type", width=80)
        self.calendar_tree.column("title", width=380)
        self.calendar_tree.column("date", width=120)
        self.calendar_tree.column("status", width=100)
        self.calendar_tree.column("source", width=100)

        scroll_y = ttk.Scrollbar(self.calendar_frame, orient="vertical", command=self.calendar_tree.yview)
        self.calendar_tree.configure(yscrollcommand=scroll_y.set)
        self.calendar_tree.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scroll_y.pack(side="right", fill="y", pady=10)

        self.calendar_tree.bind("<Double-1>", self._on_calendar_click)

    def _load_calendar(self):
        for item in self.calendar_tree.get_children():
            self.calendar_tree.delete(item)

        media_type = self.calendar_filter.get()
        items = []

        def is_active(status):
            return status in ["Играю", "Смотрю", "В планах"]

        if media_type in ["Все", "Игры"]:
            for g in self.user_games:
                date = g.get("release_date")
                status = g.get("status", "")
                if date and is_active(status):
                    source = g.get("source", "—")
                    items.append(("🎮 Игра", g["title"], date, status, source))

        if media_type in ["Все", "Сериалы"]:
            for s in self.user_series:
                date = s.get("release_date")
                status = s.get("status", "")
                if date and is_active(status):
                    source = s.get("source", "—")
                    items.append(("🎬 Сериал", s["title"], date, status, source))

        if media_type in ["Все", "Аниме"]:
            for a in self.user_anime:
                date = a.get("release_date")
                status = a.get("status", "")
                if date and is_active(status):
                    source = a.get("source", "—")
                    items.append(("🎌 Аниме", a["title"], date, status, source))

        def parse_date(date_str):
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except:
                return datetime.max.date()
        
        items.sort(key=lambda x: parse_date(x[2]))
        
        for type_, title, date, status, source in items:
            self.calendar_tree.insert("", "end", values=(type_, title, date, status, source))
        
        self.calendar_status.config(text=f"✅ Показано {len(items)} предстоящих релизов", fg="green")
        
        if len(items) == 0:
            self.calendar_status.config(
                text="📭 Нет предстоящих релизов.\n\n👉 Добавьте игры/сериалы/аниме — программа сама найдёт даты и запомнит их!", 
                fg="orange")

    def _on_calendar_click(self, event):
        sel = self.calendar_tree.selection()
        if not sel:
            return
        
        values = self.calendar_tree.item(sel[0])["values"]
        media_type = values[0]
        title = values[1]
        
        if "Игра" in media_type:
            self.notebook.select(1)
            for item in self.games_tree.get_children():
                if self.games_tree.item(item)["values"][0] == title:
                    self.games_tree.selection_set(item)
                    self.games_tree.see(item)
                    break
        elif "Сериал" in media_type:
            self.notebook.select(2)
            for item in self.series_tree.get_children():
                if self.series_tree.item(item)["values"][0] == title:
                    self.series_tree.selection_set(item)
                    self.series_tree.see(item)
                    break
        elif "Аниме" in media_type:
            self.notebook.select(3)
            for item in self.anime_tree.get_children():
                if self.anime_tree.item(item)["values"][0] == title:
                    self.anime_tree.selection_set(item)
                    self.anime_tree.see(item)
                    break

    # ========== СТАТИСТИКА ==========
    def _setup_stats_tab(self):
        title = tk.Label(self.stats_frame, text="📊 СТАТИСТИКА", font=("Arial", 18, "bold"),
                        fg=self.highlight, bg=self.bg_color)
        title.pack(pady=10)

        self.stats_text = scrolledtext.ScrolledText(self.stats_frame, wrap=tk.WORD,
                                                     font=("Arial", 11), bg="#2a2a3e", fg=self.fg_color)
        self.stats_text.pack(fill="both", expand=True, padx=20, pady=10)

        tk.Button(self.stats_frame, text="🔄 ОБНОВИТЬ", command=self._update_stats,
                  bg=self.accent_color, fg="white", padx=20).pack(pady=10)
        self._update_stats()

    def _update_stats(self):
        self.stats_text.delete(1.0, tk.END)
        
        upcoming = 0
        db_found = 0
        api_found = 0
        
        for g in self.user_games:
            if g.get("release_date") and g.get("status") in ["Играю", "В планах"]:
                upcoming += 1
                if g.get("source") == "База данных":
                    db_found += 1
                elif g.get("source") == "API":
                    api_found += 1
        for s in self.user_series:
            if s.get("release_date") and s.get("status") in ["Смотрю", "В планах"]:
                upcoming += 1
                if s.get("source") == "База данных":
                    db_found += 1
                elif s.get("source") == "API":
                    api_found += 1
        for a in self.user_anime:
            if a.get("release_date") and a.get("status") in ["Смотрю", "В планах"]:
                upcoming += 1
                if a.get("source") == "База данных":
                    db_found += 1
                elif a.get("source") == "API":
                    api_found += 1
        
        db = self._load_db()
        stats = db.get("stats", {})
        
        stats_text = f"""
📊 ОБЩАЯ СТАТИСТИКА
{"="*50}

🎮 ИГРЫ: {len(self.user_games)} тайтлов
   Часов всего: {sum(g.get('hours', 0) for g in self.user_games)}

🎬 СЕРИАЛЫ: {len(self.user_series)} тайтлов
   Всего серий: {sum(s['episode'] for s in self.user_series)}

🎌 АНИМЕ: {len(self.user_anime)} тайтлов
   Просмотрено серий: {sum(a.get('watched', 0) for a in self.user_anime)}

📚 МАНГА: {len(self.user_manga)} тайтлов
   Прочитано томов: {sum(m.get('read_volumes', 0) for m in self.user_manga)}

{"="*50}
📅 ПРЕДСТОЯЩИХ РЕЛИЗОВ: {upcoming}
   ├─ из базы данных: {db_found}
   └─ из API: {api_found}

{"="*50}
💾 СТАТИСТИКА САМООБУЧАЮЩЕЙСЯ БД
   Запросов к БД: {stats.get('total_requests', 0)}
   Попаданий в кэш: {stats.get('cache_hits', 0)}
   Вызовов API: {stats.get('api_calls', 0)}
   Ошибок API: {stats.get('api_errors', 0)}
   Подтверждений пользователя: {stats.get('user_confirmations', 0)}

📅 {datetime.now().strftime("%d.%m.%Y %H:%M")}
        """
        self.stats_text.insert(tk.END, stats_text)

    def _load_all_lists(self):
        self._load_games()
        self._load_series()
        self._load_anime()
        self._load_manga()


if __name__ == "__main__":
    root = tk.Tk()
    app = MediaTracker(root)
    root.mainloop()