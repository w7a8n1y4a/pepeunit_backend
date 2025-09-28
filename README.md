# Pepeunit Backend

## [Репозиторий документации](https://git.pepemoss.com/pepe/pepeunit/pepeunit.git) Pepeunit

## Управление проектом
```bash
make help
```

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
1. Настройте `.env` файл по образцу `.env_example` - [Подробнее о переменных окружения](https://pepeunit.com/deployment/env-variables.html#backend)
1. Выполните миграцию в БД, требуется только при первом запуске и добавлении новых миграций:
   ```bash
   make migrate
   ```
1. Запустить `Backend` приложение командой:
   ```bash
   make uvi
   ```

## Что произойдёт в момент запуска приложения ?
1. Будут выполнены миграции `Clickhouse` в автоматическом режиме.
1. Проверка cоединения с `EMQX MQTT Broker` и его настройка
1. Будет настроена интеграция с `Telegram Bot` в зависимости от `.env` переменных
1. `Fastapi-mqtt` установит соединение с `EMQX MQTT Broker`
1. Бэкенд подпишется на топик `example.com/+/+/+/pepeunit`, авторизация при этом произойдёт через `redis`
1. Бэкенд скачает все отсутствующие локальные репозитории
1. Запуск веб сервера

## Как найти playground`s Swagger UI и GraphQL
1. Введите в связанном Телеграм боте команду `/info`. Команда доступна после верификации, в сообщении будут все основные ссылки
2. `https://BACKEND_DOMAIN/BACKEND_APP_PREFIX/docs` - Swagger UI
3. `https://BACKEND_DOMAIN/BACKEND_APP_PREFIX/graphql` - GraphQL

## Поддержание формата кода
1. Установите `.pre-commit-config.yaml` на основе `.pre-commit-config.example.yaml`
2. Теперь при каждом коммите у вас будет происходить проверка модульных тестов и линтера `Ruff`
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
   make migrate
   ```   

## Тестирование
Подробности на страницах документации:

- [Модульное](https://pepeunit.com/tests/module-test.html)
- [Интеграционное](https://pepeunit.com/tests/integration-test.html)
- [Нагрузочное](https://pepeunit.com/tests/load-test.html)
