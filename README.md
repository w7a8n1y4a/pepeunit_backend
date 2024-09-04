# Pepeunit Backend

## [Документация](https://git.pepemoss.com/pepe/pepeunit/pepeunit.git) Pepeunit

## Внешние зависимости
1. Телеграмм Бот и его `Api Key`
2. Чистая база данных `Postgresql`
3. Развёрнутый `EMQX MQTT Broker` c настроенным `acl list`, нужные значения в `acl list`:
    ```
    {allow, {ipaddr, "127.0.0.1"}, all, ["$SYS/#", "#"]}.
    {deny, all, subscribe, ["$SYS/#", {eq, "#"}]}.
    {deny, all}.
    ```
4. `Redis`

## Основные этапы развёртывания
0. Установите пакеты при помощи команды `poetry install`
1. Войдите в окружение при помощи команды `poetry shell`
1. Настройте `.env` файл по образцу `.env_example`, для корректной настройки вам потребуется `API key` доступа от EMQX MQTT Broker, его можно сгенерировать в веб интерфейсе EMQX `admin panel/system/API Key` - это на левой панели*
1. Выполните миграцию в БД `alembic upgrade head` - требуется только при первом запуске
1. Запустите Бэкенд приложение командой - `uvicorn app.main:app --host 0.0.0.0 --port 5000`

## Что произойдёт в момент запуска приложения ?
0. Проверка cоединения с EMQX MQTT Broker
1. Удаление старого http auth web hook в EMQX MQTT Broker
1. Установка нового http auth web hook в EMQX MQTT Broker, он позволяет авторизовать каждый запрос ко всем топикам
2. Установка redis http auth hook для авторизации Бэкенда
1. Установка настроек кэширования для авторизации EMQX MQTT Broker
3. Будет получена информация о текущем состоянии web hook Телеграм бота, если url текущего хука не совпадёт с целевым при запуске, он будет перезаписан
4. Fastapi-mqtt установит соединение с EMQX MQTT Broker
5. Бэкенд подпишется на топики: `example.com/+/pepeunit` и `example.com/+/+/+/pepeunit`
6. Запуск веб сервера



## Как работает интеграция с Telegram Bot

Есть два режима работы: через web hook, и через infinity pooling - 
выбор осуществляется на основании BACKEND_DOMAIN.
- если введён ip адрес, будет использовать pooling
- если введён домен, будет использоваться web hook

## Как найти playground`s Swagger UI и GraphQL
1. Введите в связанном Телеграм боте команду `/info` - она доступна без верификации
2. `https://BACKEND_DOMAIN/APP_PREFIX/docs` - Swagger UI
3. `https://BACKEND_DOMAIN/APP_PREFIX/graphql` - GraphQL

## Полезные команды
1. Создание новой миграции `alembic revision -m 'best_revision_name'`
1. Применение новой миграции `alembic upgrade head` - 
1. Поддержание нормального форматирования кода `black ./app -l 120 --target-version py310 -S`

## Интеграционное тестирование
Запустить интеграционное тестирование можно командой - `pytest tests -v`