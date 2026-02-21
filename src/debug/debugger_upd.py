import functools
import inspect
import traceback
from dataclasses import dataclass, field
from typing import Callable, List, Set, Type, Any, Dict, Union, Optional
from types import TracebackType
import re

@dataclass
class FrameContext:
    """Контекст одного фрейма стека вызовов"""
    filename: str
    lineno: int
    function: str
    code_line: str
    # Безопасный дамп локальных переменных (только простые типы + __repr__ ограниченной длины)
    locals_snapshot: Dict[str, str] = field(default_factory=dict)

@dataclass
class CodeContext:
    error_type: str          # Тип исключения (например, "ValueError")
    error_message: str       # Сообщение об ошибке
    traceback_summary: str   # Человекочитаемый трейсбек (как traceback.format_exc())
    frames: List[FrameContext]  # Полный стек вызовов с локальными переменными
    failing_function_source: str  # Код упавшей функции/метода
    # Словарь: Имя класса -> Исходный код (включая базовые классы до глубины 1)
    class_dependencies: Dict[str, str] = field(default_factory=dict)
    # MRO цепочка для класса, где произошла ошибка (если применимо)
    mro_chain: List[str] = field(default_factory=list)

class RecursiveContextCollector:
    """
    Класс для вывода контекста ошибки и самой ошибки с управляемой
    глубиной traceback.

    Пример юза:

    ```
    try:
        service.get_user()
    except Exception as e:
        collector = RecursiveContextCollector(max_depth=2)
        ctx = collector.get_context(e)
        
        # Формируем промпт для LLM
        prompt = f'''
    Ошибка: {ctx.error_type}: {ctx.error_message}

    Трейсбек:
    {ctx.traceback_summary}

    Контекст выполнения (локальные переменные):
    {chr(10).join(f'  [{i}] {frame.function}({frame.lineno}): {frame.locals_snapshot}' 
                for i, frame in enumerate(ctx.frames[-3:], start=1))}

    Код упавшей функции:
    {ctx.failing_function_source}

    Зависимости (классы из аннотаций):
    {chr(10).join(f'--- {name} ---{chr(10)}{src[:300]}...' for name, src in ctx.class_dependencies.items())}
    '''
    ```
    """
    def __init__(
        self,
        max_depth: int = 2,
        max_locals_size: int = 500,    # Макс. суммарный размер локальных переменных на фрейм
        max_var_repr_len: int = 200,   # Макс. длина repr() для одной переменной
        include_builtins: bool = False
    ):
        self.max_depth = max_depth
        self.max_locals_size = max_locals_size
        self.max_var_repr_len = max_var_repr_len
        self.include_builtins = include_builtins
        self._visited_ids: Set[str] = set()

    def get_context(self, exc_value: BaseException) -> CodeContext:
        tb = exc_value.__traceback__
        if tb is None:
            raise ValueError("Exception has no traceback")

        # 1. Полный трейсбек + локальные переменные для КАЖДОГО фрейма
        all_frames = self._collect_full_traceback(tb)
        
        # 2. Фильтруем внешние фреймы из frames (оставляем только локальные)
        frames = [f for f in all_frames if not self._is_external_frame(f.filename, '')]

        # 3. Код упавшей функции (последний ЛОКАЛЬНЫЙ фрейм, или последний если все внешние)
        last_frame = frames[-1] if frames else all_frames[-1]
        failing_source = self._get_safe_source(last_frame.filename, last_frame.lineno)

        # 4. Сбор зависимостей через анализ класса из последнего фрейма
        class_deps = {}
        mro_chain = []
        self._visited_ids.clear()

        # Если ошибка в методе класса — собираем зависимости от его класса
        if hasattr(exc_value, '__traceback__'):
            tb_iter = exc_value.__traceback__
            while tb_iter.tb_next:
                tb_iter = tb_iter.tb_next
            frame_obj = tb_iter.tb_frame

            if 'self' in frame_obj.f_locals:
                root_class = frame_obj.f_locals['self'].__class__
                mro_chain = [cls.__name__ for cls in root_class.__mro__ if cls is not object]
                # Собираем только прямые базовые классы (глубина=1) + сам класс
                for cls in [root_class] + list(root_class.__mro__[1:2]):
                    self._collect_class_with_mro(cls, class_deps, current_depth=0)

        return CodeContext(
            error_type=type(exc_value).__name__,
            error_message=str(exc_value),
            traceback_summary=self._format_traceback(exc_value),
            frames=frames,
            failing_function_source=failing_source,
            class_dependencies=class_deps,
            mro_chain=mro_chain
        )

    def _collect_full_traceback(self, tb: TracebackType) -> List[FrameContext]:
        """Собирает ВЕСЬ стек вызовов с локальными переменными (без прыжка к tb_last)"""
        frames = []
        current_tb = tb
        
        while current_tb is not None:
            frame = current_tb.tb_frame
            lineno = current_tb.tb_lineno
            
            # Безопасный дамп локальных переменных
            locals_snapshot = self._safe_locals_snapshot(frame.f_locals)
            
            # Текущая строка кода
            try:
                line = inspect.getsourcelines(frame)[0][lineno - frame.f_code.co_firstlineno].strip()
            except (OSError, IndexError):
                line = "<line unavailable>"
            
            frames.append(FrameContext(
                filename=frame.f_code.co_filename,
                lineno=lineno,
                function=frame.f_code.co_name,
                code_line=line,
                locals_snapshot=locals_snapshot
            ))
            current_tb = current_tb.tb_next
        
        return frames

    def _safe_locals_snapshot(self, locals_dict: Dict[str, Any]) -> Dict[str, str]:
        """Сериализует локальные переменные с ограничениями по размеру и безопасности"""
        snapshot = {}
        total_size = 0
        
        # Сортируем по важности: аргументы функции первыми
        for key in sorted(locals_dict.keys(), key=lambda k: (k not in {'self', 'cls'}, k)):
            if total_size > self.max_locals_size:
                snapshot["..."] = f"<truncated: max {self.max_locals_size} chars>"
                break
            
            value = locals_dict[key]
            # Пропускаем служебные переменные и большие объекты
            if key.startswith('__') or key == 'builtins':
                continue
            
            # Сериализация с ограничениями
            try:
                if isinstance(value, (str, int, float, bool, type(None))):
                    repr_val = repr(value)
                elif isinstance(value, (list, dict, tuple, set)):
                    # Для коллекций показываем тип + размер
                    repr_val = f"{type(value).__name__}(len={len(value)})"
                else:
                    repr_val = repr(value)
                    # Обрезаем слишком длинные repr
                    if len(repr_val) > self.max_var_repr_len:
                        repr_val = repr_val[:self.max_var_repr_len] + "..."
            except Exception:
                repr_val = "<repr error>"
            
            snapshot[key] = repr_val
            total_size += len(repr_val) + len(key) + 4  # +4 для форматирования
        
        return snapshot

    def _collect_class_with_mro(self, cls: Type, results: Dict[str, str], current_depth: int):
        """Собирает класс + его прямые базовые классы (глубина 1 для MRO)"""
        if current_depth >= self.max_depth:
            return
        
        cls_id = f"{cls.__module__}.{cls.__qualname__}"
        if cls_id in self._visited_ids:
            return
        self._visited_ids.add(cls_id)
        
        # Пропускаем встроенные типы
        if not self.include_builtins and (cls.__module__ == 'builtins' or cls.__module__.startswith('_')):
            return
        
        # Получаем исходный код класса
        try:
            source = inspect.getsource(cls)
            results[cls.__name__] = source
        except (OSError, TypeError):
            return
        
        # Анализируем __init__ и другие методы на предмет зависимостей
        self._analyze_class_methods(cls, results, current_depth)

    def _analyze_class_methods(self, cls: Type, results: Dict[str, str], current_depth: int):
        """Анализирует __init__ + другие публичные методы для поиска зависимостей"""
        # Анализируем __init__ и методы, начинающиеся с буквы (публичные)
        for name in dir(cls):
            if name.startswith('_') and name != '__init__':
                continue
            
            attr = getattr(cls, name, None)
            if not callable(attr):
                continue
            
            # Обрабатываем декораторы через __wrapped__
            while hasattr(attr, '__wrapped__'):
                attr = attr.__wrapped__
            
            try:
                sig = inspect.signature(attr)
                for param in sig.parameters.values():
                    ann = param.annotation
                    if ann is inspect.Parameter.empty:
                        continue
                    
                    # Распаковываем типы из typing (Optional, List[Type], Union и т.д.)
                    resolved_types = self._resolve_annotation_types(ann)
                    for typ in resolved_types:
                        if inspect.isclass(typ):
                            self._collect_class_with_mro(typ, results, current_depth + 1)
            except (ValueError, TypeError):
                continue

    def _resolve_annotation_types(self, annotation: Any) -> List[Type]:
        """Распаковывает типы из аннотаций: Optional[X] -> [X], List[Y] -> [Y]"""
        types = []
        
        # Обработка typing модулей
        if hasattr(annotation, '__origin__'):  # Generic тип (List, Optional, Union)
            origin = annotation.__origin__
            args = getattr(annotation, '__args__', [])
            
            # Для Union/Optional извлекаем все аргументы кроме NoneType
            if origin is Union or str(origin) == 'typing.Union':
                for arg in args:
                    if arg is not type(None):
                        types.extend(self._resolve_annotation_types(arg))
            elif args:
                for arg in args:
                    if inspect.isclass(arg):
                        types.append(arg)
        
        # Простой класс
        elif inspect.isclass(annotation):
            types.append(annotation)
        
        return types

    def _get_safe_source(self, filename: str, lineno: int) -> str:
        """Получает исходный код функции с обработкой ошибок"""
        try:
            # Ищем функцию по позиции ошибки
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Простая эвристика: ищем начало функции выше текущей строки
            start = max(0, lineno - 20)
            code_window = ''.join(lines[start:lineno+5])
            return f"# File: {filename}:{lineno}\n{code_window}"
        except Exception:
            return f"<source unavailable for {filename}:{lineno}>"

    def _format_traceback(self, exc: BaseException) -> str:
        """Форматирует трейсбек, скрывая детали внешних библиотек, но оставляя полные детали для локальных модулей"""
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        
        # Определяем корень проекта (предполагаем, что проект не в .venv)
        project_root = self._detect_project_root(tb_lines)
        
        cleaned = []
        i = 0
        while i < len(tb_lines):
            line = tb_lines[i]
            
            # Проверяем, является ли фрейм частью внешней библиотеки
            if line.strip().startswith('File "') and self._is_external_frame(line, project_root):
                # Собираем последовательные внешние фреймы
                external_frames = []
                external_modules = set()
                
                while i < len(tb_lines):
                    current_line = tb_lines[i]
                    if current_line.strip().startswith('File "') and self._is_external_frame(current_line, project_root):
                        external_frames.append(current_line)
                        # Извлекаем имя модуля/библиотеки
                        module_name = self._extract_module_name(current_line)
                        if module_name:
                            external_modules.add(module_name)
                        i += 1
                    else:
                        break
                
                # Добавляем сжатое описание внешних фреймов
                if external_frames:
                    modules_str = ', '.join(sorted(external_modules))
                    cleaned.append(f"  [External libraries: {modules_str}] ({len(external_frames)} frames skipped)\n")
            else:
                # Локальный фрейм - оставляем подробным, но сокращаем пути
                cleaned_line = re.sub(r'File ".*?/([^/]+)"', r'File "\1"', line)
                cleaned.append(cleaned_line)
                i += 1
        
        return ''.join(cleaned)
    
    def _detect_project_root(self, tb_lines: List[str]) -> str:
        """Определяет корень проекта, находя первый не-.venv путь"""
        for line in tb_lines:
            match = re.search(r'File "([^"]+)"', line)
            if match:
                path = match.group(1)
                # Ищем путь, который не содержит .venv
                if '.venv' not in path and 'site-packages' not in path:
                    # Возвращаем директорию проекта
                    return path.split('/')[0] if path.startswith('/') else ''
        return ''
    
    def _is_external_frame(self, line: str, project_root: str) -> bool:
        """Проверяет, является ли фрейм частью внешней библиотеки.
        
        Args:
            line: Строка трейсбека или имя файла
            project_root: Не используется, оставлен для совместимости
        """
        return '.venv' in line or 'site-packages' in line
    
    def _extract_module_name(self, line: str) -> Optional[str]:
        """Извлекает имя модуля/библиотеки из строки трейсбека"""
        # Сначала пытаемся найти site-packages/<module_name>
        match = re.search(r'site-packages/([^/]+)', line)
        if match:
            return match.group(1).split('/')[0]
        
        # Затем пробуем найти .venv/lib/pythonX.Y/site-packages/<module>
        match = re.search(r'\.venv/lib/python[\d.]+/site-packages/([^/]+)', line)
        if match:
            return match.group(1).split('/')[0]
        
        # Общая эвристика: последний компонент пути перед .venv или site-packages
        match = re.search(r'File "[^"]*[/.]([^/\.]+)(?:\.py)?"', line)
        if match:
            name = match.group(1)
            # Игнорируем технические имена путей
            if name not in ['lib', 'site-packages', 'python3.13', 'python3.12', 'python3.11']:
                return name
        
        return None
    
def with_debug_context(func: Callable[..., Any]):
    """
    Декоратор, чтоб по-быстрому нацепить внедрение норм дебаггера 
    для кормёжки его выводом LLM.
    
    :param func: Любая функция, которая взрывается ошибкой
    :type func: Callable[..., Any]

    Example:
    ```
    @with_debug_context
    def critical_operation():
        ...
    ```
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if not hasattr(e, '_debug_context_collected'):
                collector = RecursiveContextCollector(max_depth=2)
                e._debug_context = collector.get_context(e)
                e._debug_context_collected = True
            raise
    return wrapper
