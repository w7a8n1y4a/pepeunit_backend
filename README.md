# Pepeunit Backend

## [Документация](https://git.pepemoss.com/pepe/pepeunit/pepeunit.git) Pepeunit

## Внешние зависимости
1. `Telegram Bot` и его `Api Key`
2. Чистая база данных в `Postgresql`
3. Развёрнутый `EMQX MQTT Broker`
4. `Redis`

## Основные этапы развёртывания
0. Установите пакеты при помощи команды `poetry install`
1. Войдите в окружение при помощи команды `poetry shell`
1. Настройте `.env` файл по образцу `.env_example`
1. Выполните миграцию в БД `alembic upgrade head` - требуется только при первом запуске
1. Запустите Бэкенд приложение командой - `uvicorn app.main:app --host 0.0.0.0 --port 5000`

## Что произойдёт в момент запуска приложения ?
0. Проверка cоединения с `EMQX MQTT Broker` и его настройка
1. Будет настроен `webhook` или `pooling` для `Telegram Bot`
1. `Fastapi-mqtt` установит соединение с `EMQX MQTT Broker`
1. Бэкенд подпишется на топики: `example.com/+/pepeunit` и `example.com/+/+/+/pepeunit`, авторизация при этом произойдёт через `redis`
1. Запуск веб сервера

## Как работает интеграция с Telegram Bot
Есть два режима работы: через `webhook`, и через `pooling` - выбор осуществляется на основании `BACKEND_DOMAIN`.
- если введён `ip` адрес, будет использовать `pooling`
- если введён домен, будет использоваться `webhook`

## Как найти playground`s Swagger UI и GraphQL
1. Введите в связанном Телеграм боте команду `/info` - она доступна без верификации
2. `https://BACKEND_DOMAIN/BACKEND_APP_PREFIX/docs` - Swagger UI
3. `https://BACKEND_DOMAIN/BACKEND_APP_PREFIX/graphql` - GraphQL

## Поддержание формата кода
1. Установите `.pre-commit-config.yaml` на основе `.pre-commit-config.example.yaml`
2. Теперь при каждом коммите у вас будет происходить проверка через `black` и `isort`
3. В случае, если нужно запустить вручную - `pre-commit run --all-files`

## Миграции базы данных
1. Создание новой миграции `alembic revision -m 'best_revision_name'`
1. Применение новой миграции `alembic upgrade head`

## Интеграционное тестирование
Запустить интеграционное тестирование можно командой - `pytest tests -v`