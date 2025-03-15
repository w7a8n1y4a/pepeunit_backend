# Дубина для Backend Pepeunit

## Основные этапы запуска
0. Установите пакеты при помощи команды `poetry install`
1. Войдите в окружение при помощи команды `poetry shell`
1. Запустите команду по примеру:

```bash
python load_test.py --url "https://localunit.pepeunit.com" --duration 120 --type mqtt --unit-count 40 --rps 100 --workers 10 --mqtt-admin "admin" --mqtt-password "password"
locust -H "https://localunit.pepeunit.com" --headless -u 400 -r 10 --run-time 2m
```