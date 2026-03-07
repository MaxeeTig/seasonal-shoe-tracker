# Shoes Storage MVP

MVP для учета сезонной обуви с русским интерфейсом и AI-подсказками через OpenRouter.

## Что реализовано

- Mobile web интерфейс на русском языке.
- Поток `Сложить обувь`: обувь -> коробка -> место (2 уровня: зона + место).
- Для каждой пары создается отдельная новая коробка (без поиска/переиспользования старых коробок).
- Поток `Найти обувь`: поиск по сезону/типу/названию.
- События хранения: `store` / `retrieve`.
- Vision-анализ фото через OpenRouter (`openai/gpt-4o-mini` по умолчанию).
- Хранение данных в SQLite (`data/shoes.db`).

## Запуск

1. Скопируйте `.env.example` в `.env` и добавьте `OPENROUTER_API_KEY`.
2. Запустите сервер:

```bash
python3 server.py
```

3. Откройте `http://localhost:8000`.

## Основные API

- `POST /api/ai/analyze`
- `POST /api/locations`
- `POST /api/boxes`
- `POST /api/shoe-pairs`
- `GET /api/shoe-pairs?query=&season=&status=`
- `GET /api/shoe-pairs/:id`
- `POST /api/shoe-pairs/:id/retrieve`
- `POST /api/shoe-pairs/:id/store`

## Примечания

- В v1 интерфейс и теги только на русском.
- Английские запросы типа `winter sneakers` не нормализуются автоматически.
