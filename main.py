import sys
import os
import json
import math
from datetime import datetime
import argparse
from PyQt6.QtWidgets import (QApplication, QMainWindow, QSplitter, 
                             QTableWidget, QTableWidgetItem, QAbstractItemView, QVBoxLayout, QWidget)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView

import gpxpy
import pyqtgraph as pg

class GpxMapApp(QMainWindow):
    def __init__(self, tracks_dir):
        super().__init__()
        self.tracks_dir = os.path.abspath(tracks_dir) # Сохраняем переданный путь к папке
        self.setWindowTitle("GPX Tracks Viewer")
        self.resize(1200, 700)

        # self.init_ui()

        # Главный контейнер со сплиттером (разделение таблица/карта)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # Инициализация таблицы
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        splitter.addWidget(self.table)

        # Инициализация браузера для карты
        self.browser = QWebEngineView()
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        # Загружаем карту относительно папки скрипта main.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(current_dir, "map_assets", "map.html")
    
        # Читаем файл из Python и передаем как HTML с указанием базового URL папки
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            base_url = QUrl.fromLocalFile(os.path.dirname(html_path) + "/")
            self.browser.setHtml(html_content, base_url)
            print(f"Успешно загружен шаблон карты: {html_path}")
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось прочитать карту: {html_path}\n{e}")
            
        splitter.addWidget(self.browser)

        # Пропорции сторон сплиттера (40% таблица, 60% карта)
        splitter.setSizes([480, 720])

        # Флаг, гарантирующий, что карта загрузилась перед передачей первого трека
        self.map_loaded = False
        self.browser.loadFinished.connect(self.on_map_loaded)

        # Загрузка данных
        self.tracks_data = []
        self.load_json_data()

    def load_json_data(self):
        json_path = os.path.join(self.tracks_dir, "gpx_list.json")
        if not os.path.exists(json_path):
            print(f"Ошибка: Файл gpx_list.json не найден ни в переданной папке треков, ни в папку tracks проекта.")
            return

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                self.tracks_data = json.load(f)
        except Exception as e:
            print(f"Ошибка чтения JSON: {e}")
            return

        if not self.tracks_data:
            return

        # Настройка колонок таблицы
        headers = ["ID", "Название", "Дистанция (км)", "Длительность", "Время в движении", "Дата старта", "Имя файла"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(self.tracks_data))

        # Заполнение таблицы данными
        for row, track in enumerate(self.tracks_data):
            self.table.setItem(row, 0, QTableWidgetItem(str(track.get("id", 0))))
            self.table.setItem(row, 1, QTableWidgetItem(str(track.get("name", "Без названия"))))
            self.table.setItem(row, 2, QTableWidgetItem(str(track.get("distance_km", 0))))
            self.table.setItem(row, 3, QTableWidgetItem(str(track.get("duration", ""))))
            self.table.setItem(row, 4, QTableWidgetItem(str(track.get("moving_time", ""))))
            self.table.setItem(row, 5, QTableWidgetItem(str(track.get("start_time", ""))))
            self.table.setItem(row, 6, QTableWidgetItem(str(track.get("file_name", ""))))

        self.table.resizeColumnsToContents()

        # Делаем активной первую строку, если карта уже готова
        if self.map_loaded:
            self.select_first_row()

    def on_map_loaded(self, success):
        if success:
            self.map_loaded = True
            # Если данные уже в таблице, активируем первый трек
            if self.table.rowCount() > 0:
                self.select_first_row()

    def select_first_row(self):
        self.table.setCurrentCell(0, 0)

    def on_selection_changed(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        current_row = selected_rows[0].row()
        track_info = self.tracks_data[current_row]
        file_name = track_info.get("file_name")
        
        # Путь к файлу трека
        gpx_path = os.path.normpath(os.path.join(self.tracks_dir, file_name))
        print(f"\n--- Выбрана строка {current_row} ---")
        print(f"Ищем файл трека по пути: {gpx_path}")
        
        if os.path.exists(gpx_path):
            try:
                with open(gpx_path, "r", encoding="utf-8") as f:
                    gpx_content = f.read()
                
                # Передаем содержимое GPX файла напрямую в JavaScript-функцию на карте
                # Используем json.dumps для безопасного экранирования спецсимволов в строке XML/GPX
                js_code = f"loadGpx({json.dumps(gpx_content)});"
                self.browser.page().runJavaScript(js_code)
                
            except Exception as e:
                print(f"Ошибка чтения GPX файла {file_name}: {e}")
        else:
            print(f"Файл трека НЕ найден: {gpx_path}")

if __name__ == "__main__":
    # Настройка argparse для обработки параметров командной строки
    parser = argparse.ArgumentParser(description="Просмотрщик GPX-треков на карте OpenLayers.")
    
    # Добавляем аргумент --dir или -d. По умолчанию берется папка 'trecks' рядом с main.py
    default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracks")
    parser.add_argument(
        "-d", "--dir", 
        default=default_dir,
        help=f"Путь к папке с GPX-файлами (по умолчанию: {default_dir})"
    )
    
    args = parser.parse_args()

    # Проверяем, существует ли указанная папка
    if not os.path.isdir(args.dir):
        print(f"Ошибка: Указанный путь не является существующей папкой: {args.dir}")
        sys.exit(1)

    print(f"Запуск приложения. Рабочая папка с треками: {os.path.abspath(args.dir)}")

    os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "9222"
    app = QApplication(sys.argv)
    window = GpxMapApp(tracks_dir=args.dir)
    window.show()
    sys.exit(app.exec())
