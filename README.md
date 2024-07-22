# Pepeunit Backend

# Начиная работу как разработчик

## Внешние зависимости
1. Настроенный домен с https - `example.com`
2. Чистая база данных Postgresql
3. Развёрнутый EMQX MQTT Broker c настроенным `acl list`, нужные значения в `acl list`:
    ```
    {allow, {ipaddr, "127.0.0.1"}, all, ["$SYS/#", "#"]}.
    {deny, all, subscribe, ["$SYS/#", {eq, "#"}]}.
    {deny, all}.
    ```
4. Redis

## Основные этапы развёртывания
0. Установите пакеты при помощи команды `poetry install`
1. Войдите в окружение при помощи команды `poetry shell`
1. Настройте `.env` файл по образцу `.env_example`, для корректной настройки вам потребуется `API key` доступа от EMQX MQTT Broker, его можно сгенерировать в веб интерфейсе EMQX `admin panel/system/API Key` - это на левой панели*
1. Выполните миграцию в БД `alembic upgrade head` - требуется только при первом запуске
1. Запустите бэкенд приложение командой - `uvicorn app.main:app --host 0.0.0.0 --port 5000`

## Что произойдёт в момент запуска приложения ?
0. Проверка cоединения с EMQX MQTT Broker
1. Удаление старого auth web hook в EMQX MQTT Broker
1. Установка нового auth web hook в EMQX MQTT Broker, он позволяет авторизовать каждый запрос ко всем топикам
1. Установка настроек кэширования для авторизации EMQX MQTT Broker
3. Будет получена информация о текущем состоянии web hook Телеграм бота, если url текущего хука не совпадёт с целевым при запуске, он будет перезаписан
4. Fastapi-mqtt установит соединение с EMQX MQTT Broker
5. Бэкенд подпишется на топики: `example.com/+/pepeunit` и `example.com/+/+/+/pepeunit`
6. Запуск веб сервера

## Как найти плейграунды Swagger UI и GraphiQL
1. `https://BACKEND_DOMAIN/APP_PREFIX/docs` - Swagger UI
2. `https://BACKEND_DOMAIN/APP_PREFIX/graphql` - GraphiQL
3. Ссылки на плейграунды есть по команде `/info` в Телеграм Боте

## Полезные команды
1. Создание новой миграции `alembic revision -m 'best_revision_name'` - **только для разработчиков, если вы не разработчик - НИКОГДА не применяйте эту команду**
2. Поддержание нормального форматирования кода `black ./app -l 120 --target-version py310 -S`

## Commit Lint

- Потренируйтесь в [COMMITLINT](https://commitlint.io/)
- Основные типы коммитов
1. `feat(unit_service): add new function` 
2. `fix(tests, unit_service): hotfix logic create UnitNode`
3. `refactor(permission_service): add new permission, rest, gql and mutatuion for creator UnitNode`
4. `resolve(conflicts): resolve`
5. `ci(Dockerfile): change packages`
