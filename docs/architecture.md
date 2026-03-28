# Архитектура LLM Agent Platform

Документ описывает внутреннее устройство платформы: поток обработки запроса, механизмы балансировки, circuit breaker и наблюдаемость.

## Обзор системы

```mermaid
graph TB
    subgraph Clients["Клиенты"]
        Agent1["Profile Agent<br/>:8001"]
        Agent2["Curator Agent<br/>:8002"]
        Agent3["Utility Agent<br/>:8003"]
        External["Внешний клиент<br/>(curl, SDK)"]
    end

    subgraph Platform["Платформа (FastAPI :8000)"]
        Auth["Auth Middleware<br/>Bearer Token"]
        Guardrails["Guardrails Pipeline"]
        Router["Model Router"]
        API["REST API<br/>/agents, /providers"]
        Metrics["Prometheus Metrics<br/>/metrics"]
    end

    subgraph Balancer["Балансировщик"]
        HealthFilter["Health Filter"]
        CB["Circuit Breaker"]
        Strategy["Strategy<br/>(Latency / RoundRobin)"]
    end

    subgraph Providers["LLM-провайдеры (OpenRouter)"]
        P1["stepfun/step-3.5-flash"]
        P2["nvidia/nemotron-3-super"]
        P3["deepseek/deepseek-chat"]
        P4["openai/gpt-oss-120b"]
        P5["x-ai/grok-4.1-fast"]
        P6["google/gemini-2.5-flash-lite"]
    end

    subgraph Observability["Наблюдаемость"]
        Prom["Prometheus<br/>:9090"]
        Grafana["Grafana<br/>:3000"]
        Langfuse["Langfuse<br/>:3001"]
        LangfuseDB["PostgreSQL<br/>(Langfuse)"]
    end

    Agent1 & Agent2 & Agent3 & External --> Auth
    Auth --> Guardrails
    Guardrails --> Router
    Auth --> API
    Router --> HealthFilter
    HealthFilter --> CB
    CB --> Strategy
    Strategy --> P1 & P2 & P3 & P4 & P5 & P6

    Platform --> Prom
    Prom --> Grafana
    Platform --> Langfuse
    Langfuse --> LangfuseDB
```

## Поток обработки запроса

```mermaid
sequenceDiagram
    participant C as Клиент
    participant A as Auth Middleware
    participant G as Guardrails
    participant R as Model Router
    participant H as Health Filter
    participant CB as Circuit Breaker
    participant S as Strategy
    participant P as OpenRouter API

    C->>A: POST /v1/chat/completions<br/>Authorization: Bearer <token>
    A->>A: Валидация токена<br/>(master / agent)

    alt Токен невалидный
        A-->>C: 401 Unauthorized
    end

    alt Agent-токен, запрещенный путь
        A-->>C: 403 Forbidden
    end

    A->>G: Проверка запроса
    G->>G: Prompt Injection Detection
    G->>G: Secret Leak Detection

    alt Запрос заблокирован
        G-->>C: 400 Bad Request
    end

    G->>R: route(model)
    R->>H: Фильтрация провайдеров<br/>(healthy > degraded > all)
    H->>CB: Фильтрация по circuit breaker<br/>(closed/half_open only)

    alt Все провайдеры circuit-broken
        CB-->>C: 503 Service Unavailable
    end

    CB->>S: select_provider(candidates)
    S->>S: Latency EMA / Round Robin

    S->>P: POST /chat/completions
    P-->>S: Response / SSE Stream

    alt Ответ без стриминга
        S->>G: Проверка ответа<br/>(маскирование секретов)
        G-->>C: 200 JSON Response
    end

    alt Стриминг
        S-->>C: 200 SSE Stream
    end
```

## Регистрация агента

```mermaid
sequenceDiagram
    participant Ag as Agent Service
    participant P as Platform API
    participant R as Agent Registry
    participant TS as Token Store

    Ag->>P: POST /agents<br/>{name, description, methods, endpoint_url}<br/>Authorization: Bearer <master_token>
    P->>R: add_agent(body)
    R->>R: Генерация UUID + токен
    R-->>P: Agent {id, token, ...}
    P-->>Ag: 201 Created<br/>{id, name, token, ...}

    Note over Ag: Агент сохраняет token<br/>для запросов к /v1/chat/completions

    Ag->>P: POST /v1/chat/completions<br/>Authorization: Bearer <agent_token>
    P->>TS: validate_token(agent_token)
    TS-->>P: TokenInfo(agent_id, is_master=false)
    P->>P: Обработка запроса...
```

## Circuit Breaker - диаграмма состояний

```mermaid
stateDiagram-v2
    [*] --> Closed

    Closed --> Open: Ошибок >= threshold<br/>в пределах window
    Closed --> Closed: Успешный запрос

    Open --> HalfOpen: Прошло cooldown<br/>секунд
    Open --> Open: Запросы отклоняются

    HalfOpen --> Closed: Пробный запрос успешен
    HalfOpen --> Open: Пробный запрос неуспешен

    state Closed {
        [*] --> Tracking
        Tracking: Подсчет ошибок<br/>за скользящее окно
    }

    state Open {
        [*] --> Rejecting
        Rejecting: Все запросы<br/>отклоняются
    }

    state HalfOpen {
        [*] --> Probing
        Probing: Один пробный<br/>запрос разрешен
    }
```

Параметры (env vars):
- `CB_ERROR_THRESHOLD` - порог ошибок (по умолчанию: 5)
- `CB_COOLDOWN_SECONDS` - время в состоянии Open (по умолчанию: 30)
- `CB_WINDOW_SECONDS` - окно подсчета ошибок (по умолчанию: 60)

## Поток данных наблюдаемости

```mermaid
graph LR
    subgraph App["FastAPI App"]
        TM["Tracing Middleware<br/>(OpenTelemetry spans)"]
        PM["Prometheus Metrics<br/>(prometheus_client)"]
        LF["Langfuse Client<br/>(трассировка агентов)"]
        JL["JSON Logger<br/>(stdout)"]
    end

    subgraph Storage["Хранилища"]
        Prom["Prometheus<br/>:9090"]
        Grafana["Grafana<br/>:3000"]
        LangfuseS["Langfuse Server<br/>:3001"]
        PG["PostgreSQL"]
    end

    TM -->|spans| Console["Console / OTLP"]
    PM -->|/metrics scrape| Prom
    Prom -->|datasource| Grafana
    LF -->|traces, generations| LangfuseS
    LangfuseS --> PG
    JL -->|JSON lines| Console
```

### Собираемые метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `http.method` | span attr | HTTP-метод запроса |
| `http.url` | span attr | URL запроса |
| `http.status_code` | span attr | Код ответа |
| `http.duration_s` | span attr | Время обработки запроса |
| `X-Trace-Id` | header | ID трассировки для корреляции |

## Компоненты

### Платформа (src/)

| Модуль | Описание |
|--------|----------|
| `api/completions.py` | OpenAI-совместимый прокси `/v1/chat/completions` с поддержкой streaming |
| `api/agents.py` | CRUD API реестра агентов |
| `api/providers.py` | CRUD API реестра провайдеров |
| `api/metrics_endpoint.py` | Prometheus scrape endpoint `/metrics` |
| `auth/middleware.py` | Bearer-токен аутентификация (master + agent токены) |
| `auth/token_store.py` | Валидация токенов из конфига и реестра агентов |
| `balancer/router.py` | Маршрутизатор: health filter -> circuit breaker -> strategy |
| `balancer/round_robin.py` | Round-robin стратегия по модели |
| `balancer/latency_based.py` | Выбор провайдера с наименьшей латентностью (EMA) |
| `balancer/health_aware.py` | Фильтрация по статусу здоровья (healthy > degraded > all) |
| `balancer/circuit_breaker.py` | Circuit breaker по провайдеру (closed/open/half_open) |
| `guardrails/pipeline.py` | Последовательный запуск гарантий безопасности |
| `guardrails/prompt_injection.py` | Детекция prompt injection по regex-паттернам |
| `guardrails/secret_leak.py` | Детекция и маскирование утечек секретов в ответах |
| `providers/openrouter.py` | HTTP-клиент для OpenRouter API (stream + non-stream) |
| `providers/registry.py` | In-memory реестр провайдеров с async-блокировками |
| `providers/seed.py` | Начальная загрузка провайдеров при старте |
| `telemetry/setup.py` | Инициализация OpenTelemetry (console / OTLP exporter) |
| `telemetry/middleware.py` | Tracing middleware - span на каждый HTTP-запрос |
| `telemetry/logging.py` | Структурированное JSON-логирование |

### Агенты (agents/)

| Агент | Порт | Описание |
|-------|------|----------|
| Profile Agent | 8001 | Профилирование гостей DemoDay: извлечение интересов и целей через диалог |
| Curator Agent | 8002 | Кураторский агент с tool use: compare, summarize, suggest_questions |
| Utility Agent | 8003 | Утилитарный агент: summarize, translate, analyze (single-turn) |

Все агенты используют общий `PlatformClient` для регистрации и обращения к платформе.
