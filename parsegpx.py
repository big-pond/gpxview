import os
import json
import gpxpy
from datetime import timedelta
from PyQt6.QtCore import QThread, pyqtSignal


def format_duration(seconds):
    """Переводит секунды в формат ЧЧ:ММ:СС"""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

class GPXParserWorker(QThread):
    # Сигналы для связи с главным окном
    progress_changed = pyqtSignal(int, str)  # Передает: (текущий_индекс, имя_файла)
    finished_success = pyqtSignal(str)       # Передает: путь к сохраненному JSON
    error_occurred = pyqtSignal(str)         # Передает: текст ошибки

    def __init__(self, source_dir, output_json):
        super().__init__()
        self.source_dir = source_dir
        self.output_json = output_json

    def run(self):
        tracks_list = []

        if not os.path.exists(self.source_dir):
            self.error_occurred.emit(f"Папка '{self.source_dir}' не существует.")
            return

        # Фильтруем только gpx файлы заранее, чтобы знать точное количество для прогресс-бара
        gpx_files = [f for f in os.listdir(self.source_dir) if f.lower().endswith('.gpx')]
        total_files = len(gpx_files)

        if total_files == 0:
            self.error_occurred.emit("В указанной папке нет GPX-файлов.")
            return

        for index, file_name in enumerate(gpx_files, start=1):
            # Отправляем сигнал в интерфейс: какой файл обрабатывается
            self.progress_changed.emit(index, file_name)
            
            file_path = os.path.join(self.source_dir, file_name)
                
            try:
                with open(file_path, 'r', encoding='utf-8') as gpx_file:
                    gpx = gpxpy.parse(gpx_file)
                        
                    start_time = None
                    total_duration =  0
                    moving_time = 0
                    stopped_time = 0
                    distance_meters = 0
                        
                    if gpx.tracks:
                            # Надежный поиск первой точки со временем во всем файле
                        for track in gpx.tracks:
                            for segment in track.segments:
                                for point in segment.points:
                                    if point.time:
                                        start_time = point.time
                                        break
                                if start_time: break
                            if start_time: break
                            
                        # Расчет расстояния
                        distance_meters = gpx.length_2d()
                        STOPPED_THRESHOLD_SPEED = 0.3 # 0.3 m/c ~ 1 km/h

                        for track in gpx.tracks:
                            for segment in track.segments:
                                for i in range(1, len(segment.points)):
                                    p1 = segment.points[i-1]
                                    p2 = segment.points[i]
                                        
                                    if p1.time and p2.time:
                                        # Находим реальный временной отрезок между точками
                                        duration = p2.time - p1.time
                                        # Считаем расстояние между ними (в метрах)
                                        distance = p2.distance_3d(p1) if p1.elevation and p2.elevation else p2.distance_2d(p1)
                                        # Вычисляем скорость на этом отрезке
                                        seconds = duration.total_seconds()
                                        if seconds > 0:
                                            speed = distance / seconds
                                            # Если скорость ниже порога — это стоянка (включая ваши 11 часов)
                                            if speed < STOPPED_THRESHOLD_SPEED:
                                                stopped_time += seconds
                                            else:
                                                moving_time += seconds
                            
                        total_duration = moving_time + stopped_time


                    # Строгое форматирование ISO 8601 с буквой Z
                    start_time_str = None
                    if start_time:
                        start_time_str = start_time.isoformat()
                        if start_time_str.endswith('+00:00'):
                            start_time_str = start_time_str[:-6] + 'Z'

                    track_data = {
                        "id": index,
                        "file_name": file_name,
                        "start_time": start_time_str,
                        "name": "",
                        "duration": format_duration(total_duration),
                        "moving_time": format_duration(moving_time),
                        "stopped_time": format_duration(stopped_time),
                        "distance_km": round(distance_meters / 1000, 2)
                    }
                    
                    tracks_list.append(track_data)
                        
            except Exception as e:
                print(f"Ошибка при обработке файла {file_name}: {e}")
                # Пропускаем проблемный файл, но продолжаем работу

        # Сортировка и сохранение
        sorted_tracks_list = sorted(tracks_list, key=lambda x: x["file_name"])
        output_json_file_path = os.path.join(self.source_dir, self.output_json)
        
        try:
            with open(output_json_file_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_tracks_list, f, ensure_ascii=False, indent=4)
            self.finished_success.emit(output_json_file_path)
        except Exception as e:
            self.error_occurred.emit(f"Ошибка при сохранении JSON: {e}")
