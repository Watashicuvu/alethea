# src/debug/telemetry.py
import json
import time
import threading
import queue
from datetime import datetime
from typing import Any, Dict
from enum import Enum

class EventType(str, Enum):
    LLM_REQ = "LLM_REQUEST"       # Запрос ушел
    LLM_RES = "LLM_RESPONSE"      # Ответ пришел
    LLM_REPAIR = "LLM_REPAIR"     # Попытка исправления JSON
    STATE_SNAP = "STATE_SNAPSHOT" # Снимок состояния (кол-во сущностей и т.д.)
    STEP_INFO = "PIPELINE_STEP"   # Просто лог этапа (начало сцены, конец сцены)
    ERROR = "ERROR"

class TelemetryBus:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelemetryBus, cls).__new__(cls)
            cls._instance.init()
        return cls._instance
    
    def _serialize_data(self, data: Any) -> Any:
        """Рекурсивно преобразует объекты в JSON-сериализуемые структуры."""
        if isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        elif hasattr(data, 'model_dump'):
            return self._serialize_data(data.model_dump())
        elif hasattr(data, '__dict__'):
            return self._serialize_data(data.__dict__)
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            return str(data)

    def init(self):
        self.log_file = "debug_stream.jsonl"
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        # Запускаем фоновый поток записи, чтобы не тормозить LLM
        self._worker = threading.Thread(target=self._writer, daemon=True)
        self._worker.start()

    def _writer(self):
        """Пишет события в файл в реальном времени."""
        while not self._stop_event.is_set():
            try:
                event = self._queue.get(timeout=1)
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
                self._queue.task_done()
            except queue.Empty:
                continue

    def emit(self, event_type: EventType, title: str, data: Dict[str, Any], context_id: str = None):
        """
        Основной метод логирования.
        :param event_type: Тип события
        :param title: Заголовок для UI (например "Extract Scene 1")
        :param data: Любой JSON-serializable словарь (промпт, ответ, состояние)
        :param context_id: ID запроса (чтобы связать Request и Response)
        """
        payload = {
            "timestamp": datetime.now().isoformat(),
            "unixtime": time.time(),
            "type": event_type.value,
            "title": title,
            "context_id": context_id,
            "data": self._serialize_data(data)
        }
        self._queue.put(payload)

# Глобальный доступ
telemetry = TelemetryBus()
