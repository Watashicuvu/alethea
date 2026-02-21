#!/bin/bash
set -e

echo "🔍 Проверка модели: $MODEL_PATH"
mkdir -p $(dirname "$MODEL_PATH")

if [ ! -f "$MODEL_PATH" ]; then
    if [ -z "$MODEL_URL" ]; then
        echo "❌ Ошибка: Модель не найдена и MODEL_URL не указан!"
        exit 1
    fi
    echo "⬇️ Скачивание модели..."
    curl -L -o "$MODEL_PATH" "$MODEL_URL"
else
    echo "✅ Модель найдена."
fi

# Если количество слоев GPU не указано, ставим 99 (загружать всё, что влезет)
if [ -z "$GPU_LAYERS" ]; then
    GPU_LAYERS=99
fi

echo "🚀 Запуск llama-server (GPU слоев: $GPU_LAYERS)..."

# Собираем аргументы
ARGS=("-m" "$MODEL_PATH" "--host" "0.0.0.0" "-ngl" "$GPU_LAYERS")

# Добавляем остальные аргументы из CMD
ARGS+=("$@")

exec llama-server "${ARGS[@]}"
