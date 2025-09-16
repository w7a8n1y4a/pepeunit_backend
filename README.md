# Pepeunit Backend

## [Репозиторий документации](https://git.pepemoss.com/pepe/pepeunit/pepeunit.git) Pepeunit

## Внешние зависимости
1. `Telegram Bot` и его `Api Key`
2. Чистая база данных в `Postgresql`
3. Чистая база данных в `Clickhouse`
3. Развёрнутый `EMQX MQTT Broker`
4. `Redis`

## Набор команд для установки в BotFather
```text
registry - Repo Registry
repo - Repo Actions
unit - Unit Actions
dashboard - Dashboard List url
info - Instance Metrics
help - About Instance
```

## Основные этапы развёртывания
0. Установите пакеты при помощи команды:
   ```bash
   poetry install
   ```
1. Войдите в окружение при помощи команды:
   ```bash
   poetry shell
   ```
1. Настройте `.env` файл по образцу `.env_example`
1. Выполните миграцию в БД, требуется только при первом запуске и добавлении новых миграций:
   ```bash
   alembic upgrade head
   ```
1. Запустите `Backend` приложение командой:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 5000
   ```

## Что произойдёт в момент запуска приложения ?
0. Будут выполнены миграции `Clickhouse` в автоматическом режиме. Миграции `Postgres` запускаются вне кода приложения
1. Проверка cоединения с `EMQX MQTT Broker` и его настройка
1. Будет настроен `webhook` или `pooling` для `Telegram Bot`
1. `Fastapi-mqtt` установит соединение с `EMQX MQTT Broker`
1. Бэкенд подпишется на топик `example.com/+/+/+/pepeunit`, авторизация при этом произойдёт через `redis`
1. Бэкенд скачает все отсутствующие локальные репозитории
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
3. В случае, если нужно запустить вручную
   ```bash
   pre-commit run --all-files
   ```

## Миграции базы данных
1. Создание новой миграции:
   ```bash
   alembic revision -m 'best_revision_name'
   ```
1. Применение новой миграции:
      ```bash
   alembic upgrade head
   ```   

## Модульное тестирование
Запустить модульное тестирование можно командой:
```bash
pytest app -v
```

## Интеграционное тестирование
Запустить интеграционное тестирование можно командой ниже. [Подробнее о настройке теста на странице документации](https://pepeunit.com/tests/integration-test.html#запуск)
```bash
pytest tests -v
```

## Нагрузочное тестирование

0. Установка дополнительных пакетов:
   ```bash
   poetry install --with load
   ```
1. [Подробнее о настройке тестов на странице документации](https://pepeunit.com/tests/load-test.html)
1. Запуск `MQTT` теста:
    ```bash
    python -m tests.load.load_test_mqtt
    ```
1. Запуск `GQL` и `REST` теста
    ```bash
    locust -f tests/load/locustfile.py
    ```