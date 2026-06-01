# media_tracker.py
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
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageTk

USER_DATA_DIR = Path("media_data")
USER_DATA_DIR.mkdir(exist_ok=True)
USER_GAMES_FILE = USER_DATA_DIR / "user_games.json"
USER_SERIES_FILE = USER_DATA_DIR / "user_series.json"
USER_ANIME_FILE = USER_DATA_DIR / "user_anime.json"
USER_MANGA_FILE = USER_DATA_DIR / "user_manga.json"
DB_FILE = USER_DATA_DIR / "release_dates_db.json"

class GameReleaseAPI:
    @staticmethod
    def search_game(title):
        try:
            encoded = urllib.parse.quote(title)
            url = f"https://api.rawg.io/api/games?search={encoded}&page_size=1"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    return data["results"][0].get("released")
            return None
        except:
            return None

class SeriesReleaseAPI:
    @staticmethod
    def search_series(title):
        try:
            encoded = urllib.parse.quote(title)
            url = f"https://api.tvmaze.com/singlesearch/shows?q={encoded}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json().get("premiered")
            return None
        except:
            return None

class AnimeReleaseAPI:
    @staticmethod
    def search_anime(title):
        try:
            encoded = urllib.parse.quote(title)
            url = f"https://api.jikan.moe/v4/anime?q={encoded}&limit=1"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("data"):
                    aired = data["data"][0].get("aired", {})
                    from_date = aired.get("from")
                    return from_date[:10] if from_date else None
            return None
        except:
            return None

RSS_SOURCES = {
    "StopGame": "https://stopgame.ru/news/rss",
    "DTF": "https://dtf.ru/rss/news",
    "Игромания": "https://www.igromania.ru/rss/news/",
    "Kanobu": "https://kanobu.ru/rss/feed",
    "VGTimes": "https://vgtimes.ru/rss/news.xml",
    "Кинопоиск": "https://www.kinopoisk.ru/media/rss/",
    "IGN": "https://feeds.feedburner.com/ign/news",
    "GameSpot": "https://www.gamespot.com/feeds/news/",
    "Anime News Network": "https://www.animenewsnetwork.com/news/rss.xml",
}

class MediaTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("MediaTracker")
        self.root.geometry("1300x750")
        self.root.minsize(1100, 650)
        
        self.bg_color = "#0f0f1a"
        self.fg_color = "#e0e0e0"
        self.accent_color = "#1a1a2e"
        self.highlight = "#e94560"
        self.game_color = "#4ecdc4"
        self.series_color = "#ff6b6b"
        self.anime_color = "#c44ec5"
        self.root.configure(bg=self.bg_color)

        self.user_games = []
        self.user_series = []
        self.user_anime = []
        self.user_manga = []
        self.current_news = []

        self.setup_ui()
        self.refresh_all_news()
        self._load_calendar()

    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Вкладка новостей
        self.news_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.news_frame, text="НОВОСТИ")
        
        title = tk.Label(self.news_frame, text="АКТУАЛЬНЫЕ НОВОСТИ",
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
        self.search_entry = tk.Entry(filter_frame, width=35)
        self.search_entry.pack(side="left", padx=10)
        self.search_entry.bind("<Return>", lambda e: self._search_news())

        self.search_btn = tk.Button(filter_frame, text="НАЙТИ", command=self._search_news,
                                     bg=self.highlight, fg="white", padx=15)
        self.search_btn.pack(side="left", padx=10)

        self.refresh_btn = tk.Button(filter_frame, text="ОБНОВИТЬ", command=self.refresh_all_news,
                                      bg=self.accent_color, fg="white", padx=15)
        self.refresh_btn.pack(side="left", padx=10)

        self.status_label = tk.Label(self.news_frame, text="Загрузка...",
                                      fg="orange", bg=self.bg_color)
        self.status_label.pack(pady=5)

        columns = ("date", "category", "source", "title")
        self.news_tree = ttk.Treeview(self.news_frame, columns=columns, show="headings", height=18)
        self.news_tree.heading("date", text="Дата")
        self.news_tree.heading("category", text="Категория")
        self.news_tree.heading("source", text="Источник")
        self.news_tree.heading("title", text="Заголовок")
        self.news_tree.column("date", width=120)
        self.news_tree.column("category", width=80)
        self.news_tree.column("source", width=150)
        self.news_tree.column("title", width=600)

        scroll = ttk.Scrollbar(self.news_frame, orient="vertical", command=self.news_tree.yview)
        self.news_tree.configure(yscrollcommand=scroll.set)
        self.news_tree.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scroll.pack(side="right", fill="y", pady=10)

        self.news_tree.bind("<Double-1>", lambda e: self._open_news())
        self.news_tree.bind("<<TreeviewSelect>>", self._show_news_preview)

        preview_frame = tk.Frame(self.news_frame, bg=self.accent_color, relief="ridge", bd=2)
        preview_frame.pack(fill="x", padx=20, pady=10)
        tk.Label(preview_frame, text="Предпросмотр:", fg=self.fg_color, bg=self.accent_color).pack(anchor="w", padx=10, pady=5)
        self.news_preview = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, height=6,
                                                       font=("Arial", 9), bg="#2a2a3e", fg=self.fg_color)
        self.news_preview.pack(fill="both", expand=True, padx=10, pady=10)

        # Вкладка игр (упрощённо)
        self.games_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.games_frame, text="ИГРЫ")
        
        tk.Label(self.games_frame, text="МОИ ИГРЫ", font=("Arial", 16, "bold"),
                fg=self.game_color, bg=self.bg_color).pack(pady=10)
        
        add_frame = tk.Frame(self.games_frame, bg=self.accent_color, relief="ridge", bd=2)
        add_frame.pack(fill="x", padx=20, pady=10)
        
        tk.Label(add_frame, text="Название:", fg=self.fg_color, bg=self.accent_color).pack(side="left", padx=10, pady=10)
        self.new_game_entry = tk.Entry(add_frame, width=35)
        self.new_game_entry.pack(side="left", padx=10, pady=10)
        
        tk.Button(add_frame, text="ДОБАВИТЬ", command=self._add_game,
                  bg=self.highlight, fg="white", padx=15).pack(side="left", padx=20, pady=10)
        
        columns = ("title", "platform", "status", "release_date", "rating")
        self.games_tree = ttk.Treeview(self.games_frame, columns=columns, show="headings", height=12)
        self.games_tree.heading("title", text="Игра")
        self.games_tree.heading("platform", text="Платформа")
        self.games_tree.heading("status", text="Статус")
        self.games_tree.heading("release_date", text="Дата")
        self.games_tree.heading("rating", text="Оценка")
        self.games_tree.column("title", width=280)
        self.games_tree.column("platform", width=100)
        self.games_tree.column("status", width=100)
        self.games_tree.column("release_date", width=110)
        self.games_tree.column("rating", width=60)
        
        scroll = ttk.Scrollbar(self.games_frame, orient="vertical", command=self.games_tree.yview)
        self.games_tree.configure(yscrollcommand=scroll.set)
        self.games_tree.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scroll.pack(side="right", fill="y", pady=10)

        # Вкладка календаря
        self.calendar_frame = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.calendar_frame, text="КАЛЕНДАРЬ")
        
        tk.Label(self.calendar_frame, text="ПРЕДСТОЯЩИЕ РЕЛИЗЫ", font=("Arial", 18, "bold"),
                fg=self.highlight, bg=self.bg_color).pack(pady=10)
        
        columns = ("type", "title", "date", "status")
        self.calendar_tree = ttk.Treeview(self.calendar_frame, columns=columns, show="headings", height=18)
        self.calendar_tree.heading("type", text="Тип")
        self.calendar_tree.heading("title", text="Название")
        self.calendar_tree.heading("date", text="Дата")
        self.calendar_tree.heading("status", text="Статус")
        self.calendar_tree.column("type", width=80)
        self.calendar_tree.column("title", width=380)
        self.calendar_tree.column("date", width=120)
        self.calendar_tree.column("status", width=100)
        
        scroll = ttk.Scrollbar(self.calendar_frame, orient="vertical", command=self.calendar_tree.yview)
        self.calendar_tree.configure(yscrollcommand=scroll.set)
        self.calendar_tree.pack(side="left", fill="both", expand=True, padx=20, pady=10)
        scroll.pack(side="right", fill="y", pady=10)

    def refresh_all_news(self):
        self.status_label.config(text="Загрузка новостей...", fg="orange")
        self.refresh_btn.config(state="disabled")
        
        def load():
            all_news = []
            for name, url in RSS_SOURCES.items():
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries[:8]:
                        if name in ["StopGame", "DTF", "Игромания", "Kanobu", "VGTimes", "IGN", "GameSpot"]:
                            cat = "Игры"
                        elif name in ["Кинопоиск"]:
                            cat = "Сериалы"
                        else:
                            cat = "Аниме"
                        all_news.append({
                            "source": name, "category": cat,
                            "title": entry.get('title', ''),
                            "link": entry.get('link', ''),
                            "summary": re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:500],
                            "date": entry.get('published', '')
                        })
                except:
                    continue
            all_news.sort(key=lambda x: x['date'], reverse=True)
            self.current_news = all_news[:100]
            self.root.after(0, self._display_news)
        
        threading.Thread(target=load, daemon=True).start()

    def _display_news(self):
        self.refresh_btn.config(state="normal")
        for item in self.news_tree.get_children():
            self.news_tree.delete(item)
        if not self.current_news:
            self.status_label.config(text="Новостей нет", fg="red")
            return
        for news in self.current_news:
            self.news_tree.insert("", "end", values=(
                news["date"][:16] if news["date"] else "Дата неизв.",
                news["category"], news["source"], news["title"][:100]
            ))
        self.status_label.config(text=f"Загружено {len(self.current_news)} новостей", fg="green")

    def _filter_news(self):
        cat = self.category_filter.get()
        if not self.current_news:
            return
        for item in self.news_tree.get_children():
            self.news_tree.delete(item)
        filtered = [n for n in self.current_news if cat == "Все" or n["category"] == cat]
        for news in filtered:
            self.news_tree.insert("", "end", values=(
                news["date"][:16] if news["date"] else "Дата неизв.",
                news["category"], news["source"], news["title"][:100]
            ))
        self.status_label.config(text=f"Показано {len(filtered)} новостей", fg="green")

    def _search_news(self):
        query = self.search_entry.get().strip()
        if not query or len(query) < 3:
            self.status_label.config(text="Введите минимум 3 символа", fg="red")
            return
        self.status_label.config(text=f"Поиск '{query}'...", fg="orange")
        self.search_btn.config(state="disabled", text="ПОИСК...")
        
        def search():
            found = []
            try:
                encoded = urllib.parse.quote(f"{query} news")
                url = f"https://news.google.com/rss/search?q={encoded}&hl=ru"
                feed = feedparser.parse(url)
                for entry in feed.entries[:20]:
                    found.append({
                        "source": "Google News", "category": "Новости",
                        "title": entry.get('title', ''), "link": entry.get('link', ''),
                        "summary": re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:500],
                        "date": entry.get('published', '')
                    })
            except:
                pass
            for name, url in RSS_SOURCES.items():
                try:
                    feed = feedparser.parse(url)
                    for entry in feed.entries[:10]:
                        if query.lower() in entry.get('title', '').lower():
                            if name in ["StopGame", "DTF", "Игромания", "Kanobu", "VGTimes", "IGN", "GameSpot"]:
                                cat = "Игры"
                            elif name in ["Кинопоиск"]:
                                cat = "Сериалы"
                            else:
                                cat = "Аниме"
                            found.append({
                                "source": name, "category": cat,
                                "title": entry.get('title', ''), "link": entry.get('link', ''),
                                "summary": re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:500],
                                "date": entry.get('published', '')
                            })
                except:
                    continue
            unique = []
            seen = set()
            for item in found:
                if item["link"] not in seen:
                    seen.add(item["link"])
                    unique.append(item)
            self.root.after(0, lambda: self._display_search_results(unique, query))
        
        threading.Thread(target=search, daemon=True).start()

    def _display_search_results(self, results, query):
        self.search_btn.config(state="normal", text="НАЙТИ")
        for item in self.news_tree.get_children():
            self.news_tree.delete(item)
        if not results:
            self.status_label.config(text=f"Новостей про '{query}' не найдено", fg="red")
            return
        for news in results:
            self.news_tree.insert("", "end", values=(
                news["date"][:16] if news["date"] else "Дата неизв.",
                news["category"], news["source"], news["title"][:100]
            ))
        self.status_label.config(text=f"Найдено {len(results)} новостей", fg="green")

    def _show_news_preview(self, event):
        sel = self.news_tree.selection()
        if not sel:
            return
        idx = self.news_tree.index(sel[0])
        cat = self.category_filter.get()
        current = [n for n in self.current_news if cat == "Все" or n["category"] == cat]
        if idx < len(current):
            n = current[idx]
            self.news_preview.delete(1.0, tk.END)
            self.news_preview.insert(1.0, f"{n['title']}\n\n{n['date']}\n{n['source']}\n\n{n['summary']}")

    def _open_news(self):
        sel = self.news_tree.selection()
        if not sel:
            return
        idx = self.news_tree.index(sel[0])
        cat = self.category_filter.get()
        current = [n for n in self.current_news if cat == "Все" or n["category"] == cat]
        if idx < len(current):
            webbrowser.open(current[idx]["link"])

    def _add_game(self):
        title = self.new_game_entry.get().strip()
        if not title:
            messagebox.showwarning("Ошибка", "Введите название")
            return
        
        def process():
            date = GameReleaseAPI.search_game(title)
            game = {"title": title, "platform": "PC", "status": "В планах", "release_date": date, "rating": 0}
            self.user_games.append(game)
            self.root.after(0, self._load_games)
            self.root.after(0, self._load_calendar)
            messagebox.showinfo("Успех", f"Игра '{title}' добавлена!")
        
        threading.Thread(target=process, daemon=True).start()
        self.new_game_entry.delete(0, tk.END)

    def _load_games(self):
        for item in self.games_tree.get_children():
            self.games_tree.delete(item)
        for i, g in enumerate(self.user_games):
            self.games_tree.insert("", "end", iid=str(i), values=(
                g["title"], g["platform"], g["status"], g.get("release_date", "-"), f"⭐ {g.get('rating', 0)}"
            ))

    def _load_calendar(self):
        for item in self.calendar_tree.get_children():
            self.calendar_tree.delete(item)
        today = datetime.now().date()
        items = []
        for g in self.user_games:
            if g.get("release_date") and g["status"] in ["Играю", "В планах"]:
                items.append(("Игра", g["title"], g["release_date"], g["status"]))
        items.sort(key=lambda x: x[2])
        for type_, title, date, status in items:
            self.calendar_tree.insert("", "end", values=(type_, title, date, status))

if __name__ == "__main__":
    root = tk.Tk()
    app = MediaTracker(root)
    root.mainloop()
