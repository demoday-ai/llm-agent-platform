# Нагрузочное тестирование

Нагрузочные тесты на [Locust](https://locust.io). Три сценария с разной интенсивностью для проверки пропускной способности, латентности и устойчивости платформы.

## Предварительные требования

- Платформа запущена (`docker compose up --build`)
- Python 3.12+

## Установка

```bash
pip install -r loadtests/requirements.txt
```

## Запуск

### Все сценарии последовательно

```bash
export MASTER_TOKEN=<ваш-токен>
./loadtests/run_tests.sh http://localhost:8000
```

Скрипт прогонит Normal -> Peak -> Stress и сохранит CSV-результаты.

### Отдельный сценарий (headless)

```bash
export MASTER_TOKEN=<ваш-токен>

# Normal: 15 пользователей, 60 секунд
locust -f loadtests/locustfile.py --headless \
  --users 15 --spawn-rate 5 --run-time 60s \
  --host http://localhost:8000
```

### Web-интерфейс

```bash
locust -f loadtests/locustfile.py --host http://localhost:8000
# Открыть http://localhost:8089
```

## Сценарии

| Сценарий | Пользователи | Spawn Rate | Время | Модели |
|----------|:-----------:|:----------:|:-----:|--------|
| Normal   | 15          | 5/s        | 60s   | Бесплатные (step-3.5-flash, nemotron-3-super) |
| Peak     | 30          | 10/s       | 60s   | Бесплатные + платные (deepseek-chat, gpt-oss-120b) |
| Stress   | 50          | 20/s       | 30s   | Все модели, провоцирование 429 |

## Безопасность

- Каждый класс пользователей ограничен 200 запросами (по умолчанию)
- Промпты короткие (5-10 токенов), `max_tokens=10`
- Переопределение лимита: `export LOCUST_MAX_REQUESTS=500`

## Результаты

CSV-файлы сохраняются в `loadtests/results/`:

| Файл | Содержимое |
|------|-----------|
| `*_stats.csv` | Общая статистика по эндпоинтам |
| `*_stats_history.csv` | Статистика по времени |
| `*_failures.csv` | Детали ошибок |

### Ключевые метрики

- **RPS** (Requests Per Second) - пропускная способность
- **Median / P95 / P99 latency** - время ответа
- **Failure rate** - доля ошибок (429, 502, 504)

При Stress-сценарии ожидается рост 429-ошибок из-за rate limiting на стороне OpenRouter.

## Переменные окружения

| Переменная | По умолчанию | Описание |
|-----------|:-----------:|----------|
| `MASTER_TOKEN` | `test-master-token` | Токен авторизации |
| `LOCUST_MAX_REQUESTS` | `200` | Максимум запросов на класс пользователей |
