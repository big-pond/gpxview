import sys
import os
import json
import math
from datetime import datetime
import argparse
from PyQt6.QtWidgets import (QApplication, QMainWindow, QSplitter, 
                             QTableWidget, QTableWidgetItem, QAbstractItemView, QVBoxLayout, QWidget, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt, QUrl, QSettings
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView

import gpxpy
import pyqtgraph as pg
pg.setConfigOption('background', '#f0f0f0')  # Светло-серый фон
pg.setConfigOption('foreground', 'k')        # Черный текст и шкалы

class GpxMapApp(QMainWindow):
    def __init__(self, tracks_dir):
        super().__init__()
        self.tracks_dir = os.path.abspath(tracks_dir) # Сохраняем переданный путь к папке
        self.setWindowTitle("GPX Tracks Viewer")
        self.resize(1200, 700)

        self.init_ui()
        self.create_menu_bar()

        # Загрузка данных
        self.tracks_data = []
        self.load_json_data()

        self.load_settings()


    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # Главный горизонтальный сплиттер (Разделяет Таблицу и Правый блок)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)
        
        # Инициализация таблицы слева
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.main_splitter.addWidget(self.table)

        # Правый блок (Карта + Графики)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Вертикальный сплиттер для Карты и Графиков
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(self.right_splitter)

        # Инициализация браузера для карты
        self.browser = QWebEngineView()
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        
        # Загружаем карту (сверху справа)
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
            
        self.right_splitter.addWidget(self.browser)

        # Виджет графиков (снизу справа)
        self.graph_widget = pg.GraphicsLayoutWidget()
        self.right_splitter.addWidget(self.graph_widget)

        # Настройка самих графиков в контейнере pyqtgraph
        self.setup_plots()

        # Добавляем правый блок в главный сплиттер
        self.main_splitter.addWidget(right_container)
        
        # Задаем базовые пропорции
        self.main_splitter.setSizes([350, 850])  # Таблица против Карты/Графиков
        self.right_splitter.setSizes([500, 300]) # Карта против Графиков



        # Флаг, гарантирующий, что карта загрузилась перед передачей первого трека
        self.map_loaded = False
        self.browser.loadFinished.connect(self.on_map_loaded)


    def load_settings(self):
        ini_path = os.path.join(os.path.dirname(__file__), "config.ini")
        # Инициализируем QSettings в формате INI
        settings = QSettings(ini_path, QSettings.Format.IniFormat)
        
        # Восстанавливаем положение и размер главного окна
        geometry = settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
            
        # Восстанавливаем состояние окна (развернуто/свернуто)
        window_state = settings.value("windowState")
        if window_state:
            self.restoreState(window_state)
            
        # Восстанавливаем размеры (структуру) сплиттеров
        main_splitter_state = settings.value("mainSplitter")
        if main_splitter_state:
            self.main_splitter.restoreState(main_splitter_state)
            
        right_splitter_state = settings.value("rightSplitter")
        if right_splitter_state:
            self.right_splitter.restoreState(right_splitter_state)


    def closeEvent(self, event):
        ini_path = os.path.join(os.path.dirname(__file__), "config.ini")
        settings = QSettings(ini_path, QSettings.Format.IniFormat)
        
        # Сохраняем геометрию и положение главного окна
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        
        # Сохраняем структуру (состояние разделения) сплиттеров
        settings.setValue("mainSplitter", self.main_splitter.saveState())
        settings.setValue("rightSplitter", self.right_splitter.saveState())
        
        # Позволяем окну закрыться
        event.accept()


    def create_menu_bar(self):
        menu_bar = self.menuBar()
        
        # Меню File
        file_menu = menu_bar.addMenu("File")
        
        open_dir_action = QAction("Open directory...", self)
        open_dir_action.setShortcut("Ctrl+O")
        open_dir_action.triggered.connect(self.menu_open_directory)
        file_menu.addAction(open_dir_action)
        
        file_menu.addSeparator()  # Разделительная линия
        
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)  # Закрытие приложения
        file_menu.addAction(quit_action)
        
        # Меню Help
        help_menu = menu_bar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.menu_about_app)
        help_menu.addAction(about_action)
        
        about_qt_action = QAction("About Qt", self)
        about_qt_action.triggered.connect(QApplication.aboutQt)  # Стандартное окно "О Qt"
        help_menu.addAction(about_qt_action)

    # --- СЛОТЫ ДЛЯ МЕНЮ ---
    def menu_open_directory(self):
        # Открывает диалог выбора папки
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory with GPX files")
        if dir_path:
            # На данном этапе просто выведем путь в консоль. 
            # При необходимости здесь можно реализовать сканирование папки на наличие .gpx файлов.
            print(f"Выбрана папка: {dir_path}")
            
    def menu_about_app(self):
        QMessageBox.about(
            self, 
            "About GPX Viewer",
            "<h3>GPX Track Viewer v1.0</h3>"
            "<p>The application for visualizing GPX tracks using PyQt6, "
            "OpenLayers (JavaScript) and PyQtGraph.</p>"
            "<p>© 2026 Developer  <a href=\"https://github.com/big-pond\">https://github.com/big-pond</a></p>"
        )


    def setup_plots(self):
        # Настройка цвета линий сетки (светло-серый, но темнее фона)
        grid_pen = pg.mkPen(color='#d0d0d0', width=1)
        # Карандаш для самих шкал и текста (черный)
        axis_pen = pg.mkPen(color='k', width=1)
        
        # График высоты (верхний)
        self.alt_plot = self.graph_widget.addPlot(row=0, col=0)
        self.alt_plot.setLabel('left', 'Высота', units='м')
        self.alt_plot.showGrid(x=True, y=True)
        # Применяем цвета к осям и сетке верхнего графика
        for axis_name in ['left', 'bottom']:
            axis = self.alt_plot.getAxis(axis_name)
            axis.setPen(axis_pen)       # Делаем саму линию шкалы черной
            axis.setGrid(150)           # Включаем сетку (прозрачность от 0 до 255)
            # Внутренний механизм pyqtgraph использует цвет оси для сетки, 
            # но мы можем управлять её стилем через стили отображения, если это необходимо.

        # График скорости (нижний)
        self.speed_plot = self.graph_widget.addPlot(row=1, col=0)
        self.speed_plot.setLabel('left', 'Скорость', units='км/ч')
        self.speed_plot.setLabel('bottom', 'Дистанция', units='км')
        self.speed_plot.showGrid(x=True, y=True)
        # Применяем цвета к осям и сетке нижнего графика
        for axis_name in ['left', 'bottom']:
            axis = self.speed_plot.getAxis(axis_name)
            axis.setPen(axis_pen)       # Делаем шкалу черной
            axis.setGrid(150)           
        
        # Синхронизируем масштабирование и перемещение по оси X (дистанции) для обоих графиков
        self.speed_plot.setXLink(self.alt_plot)
        
        # Создаем кривые (линии), которые будем обновлять данными
        self.alt_curve = self.alt_plot.plot(pen=pg.mkPen(color='#004488', width=2)) 
        self.speed_curve = self.speed_plot.plot(pen=pg.mkPen(color='#006622', width=2))

        # Вертикальные линии-курсоры на обоих графиках ---
        line_pen = pg.mkPen(color='#ffaa00', width=1.5, style=Qt.PenStyle.DashLine)
        self.alt_v_line = pg.InfiniteLine(angle=90, movable=False, pen=line_pen)
        self.speed_v_line = pg.InfiniteLine(angle=90, movable=False, pen=line_pen)
        
        self.alt_plot.addItem(self.alt_v_line, ignoreBounds=True)
        self.speed_plot.addItem(self.speed_v_line, ignoreBounds=True)

        # ---  Плавающее текстовое окошко внутри графика  ---

        self.tooltip_text = pg.TextItem(html="", anchor=(0, 0), fill=(240, 240, 240, 230), border='k')
        self.alt_plot.addItem(self.tooltip_text, ignoreBounds=True)
        self.alt_plot.addItem(self.tooltip_text)
        self.tooltip_text.hide() # По умолчанию скрыто

        # Подключаем отслеживание мыши
        self.graph_widget.scene().sigMouseMoved.connect(self.on_mouse_moved)


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

    def parse_gpx_file(self, gpx_path):
        """Парсит GPX файл и возвращает массивы расстояний, высот и скоростей."""
        self.current_track_points = []
        distances = [0.0]
        elevations = []
        speeds = [0.0]
        
        try:
            with open(gpx_path, 'r', encoding='utf-8') as f:
                gpx = gpxpy.parse(f)
        except Exception as e:
            print(f"Не удалось распарсить GPX: {e}")
            return [], [], []

        points = []
        for track in gpx.tracks:
            for segment in track.segments:
                points.extend(segment.points)
                
        if not points:
            return [], [], []

        # Извлекаем начальную высоту
        elevations.append(points[0].elevation if points[0].elevation is not None else 0.0)
        
        total_distance = 0.0
        
        for i in range(1, len(points)):
            p1 = points[i-1]
            p2 = points[i]
            
            # Считаем расстояние между точками (в метрах) и переводим в км
            dist = p1.distance_3d(p2)
            if dist is None:
                dist = p1.distance_2d(p2)
            
            total_distance += (dist / 1000.0)
            distances.append(total_distance)
            
            
            # Сохраняем высоту (если ее нет, берем предыдущую)
            ele = p2.elevation if p2.elevation is not None else elevations[-1]
            elevations.append(ele)
            
            # Считаем скорость между точками
            if p1.time and p2.time:
                time_diff = (p2.time - p1.time).total_seconds()
                if time_diff > 0:
                    # Скорость = м/с * 3.6 -> км/ч
                    speed = (dist / time_diff) * 3.6
                    # Сглаживаем аномальные выбросы GPS (например, скорость выше 150 км/ч)
                    if speed > 150: 
                        speed = speeds[-1]
                    speeds.append(speed)
                else:
                    speeds.append(speeds[-1])
            else:
                speeds.append(0.0)
                
        # Применяем легкое скользящее среднее к скорости для сглаживания графиков (убирает "шум" GPS)
        smoothed_speeds = self.smooth_data(speeds, window=5)
        
        # Сохраняем полную карту точек для быстрого поиска по X-координате (дистанции)
        for i in range(len(points)):
            self.current_track_points.append({
                'dist': distances[i],
                'ele': elevations[i],
                'speed': speeds[i],
                'lon': points[i].longitude,
                'lat': points[i].latitude
            })
        return distances, elevations, smoothed_speeds


    def smooth_data(self, data, window=5):
        """Простое скользящее среднее для сглаживания шумов GPS."""
        if len(data) < window:
            return data
        smoothed = []
        for i in range(len(data)):
            start = max(0, i - window // 2)
            end = min(len(data), i + window // 2 + 1)
            smoothed.append(sum(data[start:end]) / (end - start))
        return smoothed

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

                # 2. Обновляем графики профиля высот и скорости
                distances, elevations, speeds = self.parse_gpx_file(gpx_path)
                
                if distances:
                    self.alt_curve.setData(distances, elevations)
                    self.speed_curve.setData(distances, speeds)
                    
                    # Автомасштабирование графиков под новые данные
                    self.alt_plot.enableAutoRange()
                    self.speed_plot.enableAutoRange()
                else:
                    # Если данных нет, очищаем графики
                    self.alt_curve.clear()
                    self.speed_curve.clear()

            except Exception as e:
                print(f"Ошибка чтения GPX файла {file_name}: {e}")
        else:
            print(f"Файл трека НЕ найден: {gpx_path}")

    # --- Обработчик движения мыши по графикам ---
    def on_mouse_moved(self, pos):
        if not self.current_track_points:
            return

        # Проверяем, находится ли мышь в зоне какого-либо из двух графиков
        for plot in [self.alt_plot, self.speed_plot]:
            plot_point = plot.vb.mapSceneToView(pos)
            x_distance = plot_point.x() # Получаем дистанцию (ось X) в месте курсора
            
            # Проверяем, попадает ли X в диапазон нашего трека
            if self.current_track_points[0]['dist'] <= x_distance <= self.current_track_points[-1]['dist']:
                # Синхронно двигаем вертикальные линии-курсоры на графиках
                self.alt_v_line.setValue(x_distance)
                self.speed_v_line.setValue(x_distance)
                
                # Находим ближайшую точку трека методом бинарного поиска (для скорости)
                closest_point = min(self.current_track_points, key=lambda p: abs(p['dist'] - x_distance))
                
                # Передаем координаты точки в JavaScript на карту
                js_code = f"showMarkerAt({closest_point['lon']}, {closest_point['lat']});"
                self.browser.page().runJavaScript(js_code)

                # Формируем HTML-текст для внутренней плавающей плашки
                html_content = (
                    f"<div style='color: black; font-size: 10pt; padding: 3px;'>"
                    f"<b>Дистанция:</b> {closest_point['dist']:.2f} км<br>"
                    f"<b>Высота:</b> {closest_point['ele']:.1f} м<br>"
                    f"<b>Скорость:</b> {closest_point['speed']:.1f} км/ч"
                    f"</div>"
                )
                
                # Устанавливаем текст и позиционируем плашку чуть выше курсора мыши
                self.tooltip_text.setHtml(html_content)
                
                # --- ИСПРАВЛЕНО: Привязка к верхней границе + умный разворот у края ---
                y_range = self.alt_plot.getViewBox().viewRange()[1]
                y_upper_boundary = y_range[1] 
                x_max = self.current_track_points[-1]['dist'] # Конечная дистанция трека
                
                # Если курсор в первой половине трека — показываем подсказку справа от линии
                if x_distance < x_max / 2:
                    self.tooltip_text.setAnchor((0, 0)) # Левый верхний угол
                    # self.tooltip_text.setPos(x_distance + 0.02, y_upper_boundary)
                    self.tooltip_text.setPos(x_distance + x_max/50, y_upper_boundary)
                # Если во второй половине — разворачиваем подсказку влево, чтобы она не пряталась за край
                else:
                    self.tooltip_text.setAnchor((1, 0)) # Правый верхний угол
                    self.tooltip_text.setPos(x_distance - x_max/50, y_upper_boundary)
                    
                self.tooltip_text.show()
                return
            
        # Если мышь ушла за пределы графиков — скрываем текстовую плашку
        self.tooltip_text.hide()

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
