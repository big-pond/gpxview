import json
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex


class GPXTableModel(QAbstractTableModel):

    def __init__(self, data=None):
        super().__init__()
        self._data = data or []
        # Исходная копия данных для проверки изменений при закрытии
        self._initial_data_str = json.dumps(self._data, sort_keys=True)
        # Заголовки столбцов таблицы
        self.headers = ["ID", "Имя файла", "Дата старта", "Название", "Длительность", "Время движения", "Время стоянок", "Дистанция (км)"]
        # Ключи, соответствующие столбцам в JSON объекте
        self.fields = ["id", "file_name", "start_time", "name", "duration", "moving_time", "stopped_time", "distance_km"]

     
    def rowCount(self, parent=QModelIndex()):
        return len(self._data)


    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)


    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None
        
        row_data = self._data[index.row()]
        field_name = self.fields[index.column()]
        value = row_data.get(field_name, "")

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return str(value)
        return None


    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if index.isValid() and role == Qt.ItemDataRole.EditRole:
            row = index.row()
            field_name = self.fields[index.column()]
            
            # Разрешаем редактировать только поле "name" (индекс столбца 1)
            if field_name == "name":
                cleaned_value = value.strip()
                if self._data[row][field_name] != cleaned_value:
                    self._data[row][field_name] = cleaned_value
                    self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
                    return True
        return False


    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        # Получаем имя поля для текущего столбца
        field_name = self.fields[index.column()]
        
        # Делаем редактируемым только столбец "name"
        if field_name == "name":
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable


    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self.headers[section]
            else:
                return section + 1
        return None


    def has_changes(self):
        """Проверяет, изменились ли данные по сравнению с исходными."""
        current_data_str = json.dumps(self._data, sort_keys=True)
        return current_data_str != self._initial_data_str


    def get_data(self):
        return self._data

