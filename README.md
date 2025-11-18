# Pepeunit Backend

## [Карта проекта](https://pepeunit.com/development-pepeunit/maps.html)

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

## Важно

### Поддержание формата кода
1. Установите `.pre-commit-config.yaml` на основе `.pre-commit-config.example.yaml`
2. Теперь при каждом коммите у вас будет происходить проверка модульных тестов и линтера `Ruff`
3. В случае, если нужно запустить вручную
   ```bash
   pre-commit run --all-files
   ```

### Миграции базы данных
1. Создание новой миграции:
   ```bash
   alembic revision -m 'best_revision_name'
   ```
1. Применение новой миграции:
   ```bash
   make migrate
   ```

### Набор команд для установки в BotFather
```text
registry - Repo Registry
repo - Repo Actions
unit - Unit Actions
dashboard - Dashboard List url
info - Instance Metrics
help - About Instance
```
