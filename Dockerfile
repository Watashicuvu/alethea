# Используем официальный образ Python 3.11 как базовый
FROM python:3.11-slim

# Устанавливаем uv — современный инструмент управления зависимостями
RUN pip install --no-cache-dir uv

# Устанавливаем bash (на случай, если нужны скрипты) и ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы управления зависимостями
# Предполагается, что у вас есть uv.lock и pyproject.toml
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости в read-only слой (без виртуального окружения — не поддерживается в serverless)
# uv sync устанавливает пакеты в .venv по умолчанию, но в serverless-образах лучше использовать --system
RUN uv sync

# Копируем исходный код приложения
COPY . .

# Порт, который слушает контейнер (для serverless не обязателен, но хорошая практика)
EXPOSE 8080

# Запуск приложения
CMD ["uv", "run", "python3", "-m", "main"]