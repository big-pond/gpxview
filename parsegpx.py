import os
import json
import gpxpy


def format_duration(seconds):
    """Переводит секунды в формат ЧЧ:ММ:СС"""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def parse_gpx_files(source_dir, output_json):
    tracks_list = []

    if not os.path.exists(source_dir):
        print(f"Ошибка: Папка '{source_dir}' не существует.")
        return

    for id, file_name in enumerate(os.listdir(source_dir), start=1):
        if file_name.lower().endswith('.gpx'):
            file_path = os.path.join(source_dir, file_name)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as gpx_file:
                    gpx = gpxpy.parse(gpx_file)
                    
                    start_time = None
                    total_duration = 0
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
                                if start_time:
                                    break
                            if start_time:
                                break
                        
                        # Расчет расстояния
                        distance_meters = gpx.length_2d()
                        
                        # Расчет времени (0.1 км/ч = 0.1 / 3.6 м/с)
                        speed_limit_ms = 0.1 / 3.6
                        moving_data = gpx.get_moving_data(stopped_speed_threshold=speed_limit_ms)
                        if moving_data:
                            moving_time = moving_data.moving_time
                            stopped_time = moving_data.stopped_time
                            total_duration = moving_time + stopped_time

                    # Строгое форматирование ISO 8601 с буквой Z
                    start_time_str = None
                    if start_time:
                        start_time_str = start_time.isoformat()
                        if start_time_str.endswith('+00:00'):
                            start_time_str = start_time_str[:-6] + 'Z'

                    track_data = {
                        "id": id,
                        "file_name": file_name,
                        "start_time": start_time_str,
                        "name": "",
                        "duration": format_duration(total_duration),
                        "moving_time": format_duration(moving_time),
                        "stopped_time": format_duration(stopped_time),
                        "distance_km": round(distance_meters / 1000, 2)
                    }
                    
                    tracks_list.append(track_data)
                    print(f"Успешно обработан: {file_name}")
                    
            except Exception as e:
                print(f"Ошибка при обработке файла {file_name}: {e}")

    # СОРТИРОВКА: Сортируем список словарей по ключу "file_name" по алфавиту
    sorted_tracks_list = sorted(tracks_list, key=lambda x: x["file_name"])

    # Сохраняем отсортированный список в JSON
    output_json_file_path = os.path.join(source_dir, output_json)
    try:
        with open(output_json_file_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_tracks_list, f, ensure_ascii=False, indent=4)
        print(f"\nГотово! Результат сохранен в файл: {output_json_file_path}")
    except Exception as e:
        print(f"Ошибка при сохранении JSON-файла: {e}")
