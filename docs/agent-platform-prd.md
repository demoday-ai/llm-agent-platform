# Product Requirements Document: LLM Agent Platform

**Version**: 1.0
**Date**: 2026-03-28
**Quality Score**: 92/100

---

## Executive Summary

LLM Agent Platform - инфраструктурная платформа для регистрации автономных A2A-агентов, маршрутизации LLM-запросов и сбора телеметрии. Платформа выступает единой точкой входа для всех LLM-вызовов: балансирует нагрузку между моделями через OpenRouter, защищает от prompt injection, авторизует агентов и собирает детальные метрики (TTFT, TPOT, стоимость).

Реальные потребители платформы - агенты проекта EventAI (DemoDay): Profile Agent (профилирование гостей) и Curator Agent (интерактивный помощник с tool use). Это не демо-заглушки, а продакшн-агенты, обслуживающие мероприятия на 330+ проектов.

Домашнее задание по бонус-треку LLM (ИТМО, инфраструктурный трек). Цель - уровень 3 (25 баллов).

---

## Problem Statement

**Current Situation**: LLM-приложения (как EventAI) напрямую вызывают OpenRouter API. Нет единого мониторинга стоимости, нет защиты от prompt injection в пользовательском вводе, нет балансировки между моделями, нет circuit breaker при падении провайдера.

**Proposed Solution**: API-платформа между клиентскими агентами и LLM-провайдерами. Прозрачный прокси с OpenAI-совместимым API, добавляющий балансировку, телеметрию, guardrails и авторизацию.

**Business Impact**: Максимальный балл (25) за ДЗ. Побочная ценность - реальная инфраструктура для мониторинга LLM-расходов EventAI.

---

## Success Metrics

**Primary KPIs:**
- Все критерии приёмки уровней 1-3 выполнены
- Нагрузочный тест на реальном API пройден с фиксацией throughput и латентности
- Grafana dashboards показывают метрики в реальном времени
- DemoDay агенты работают через платформу

**Validation**: Проверяющий поднимает `docker compose up`, видит работающую платформу с дашбордами, может запустить нагрузочный тест.

---

## User Personas

### Primary: Проверяющий (преподаватель)
- **Role**: Оценивает ДЗ
- **Goals**: Убедиться что все уровни реализованы, система работает
- **Pain Points**: Нет времени разбираться в сложном запуске
- **Technical Level**: Advanced

### Secondary: Разработчик LLM-приложения (EventAI)
- **Role**: Подключает агентов к платформе
- **Goals**: Единый LLM-прокси с мониторингом и защитой
- **Pain Points**: Ручной мониторинг расходов, отсутствие guardrails
- **Technical Level**: Advanced

---

## User Stories & Acceptance Criteria

### US-001: Отправка LLM-запроса через платформу

**As a** разработчик
**I want to** отправить запрос к LLM через платформу в OpenAI-совместимом формате
**So that** я могу использовать любой OpenAI-клиент без изменений

**Acceptance Criteria:**
- [ ] POST /v1/chat/completions принимает OpenAI-формат запроса
- [ ] Ответ в OpenAI-совместимом формате
- [ ] Поддержка streaming (SSE) без буферизации
- [ ] Модель указывается в запросе, платформа маршрутизирует к нужному провайдеру

### US-002: Балансировка между провайдерами

**As a** разработчик
**I want to** чтобы платформа автоматически выбирала лучшего провайдера
**So that** запросы обрабатываются быстро и надёжно

**Acceptance Criteria:**
- [ ] Round-robin для одинаковых реплик модели
- [ ] Статические веса для приоритизации провайдеров
- [ ] Latency-based routing: приоритет провайдеру с наименьшей средней латентностью
- [ ] Health-aware: провайдер исключается из пула при 5xx/429/timeout
- [ ] Провайдер возвращается в пул через настраиваемый cooldown

### US-003: Регистрация A2A-агента

**As a** разработчик
**I want to** зарегистрировать агента на платформе с Agent Card
**So that** платформа знает о моих агентах и может маршрутизировать к ним запросы

**Acceptance Criteria:**
- [ ] POST /agents регистрирует агента с Agent Card (имя, описание, методы, URL)
- [ ] GET /agents возвращает список зарегистрированных агентов
- [ ] GET /agents/{id} возвращает конкретную карточку
- [ ] DELETE /agents/{id} удаляет агента
- [ ] При регистрации агент получает API-токен

### US-004: Регистрация LLM-провайдера

**As a** администратор платформы
**I want to** динамически добавлять LLM-провайдеров
**So that** я могу менять набор провайдеров без перезапуска

**Acceptance Criteria:**
- [ ] POST /providers регистрирует провайдера (URL, модели, цена/токен, лимиты, приоритет)
- [ ] GET /providers возвращает список с текущим статусом (healthy/unhealthy)
- [ ] PUT /providers/{id} обновляет конфигурацию
- [ ] DELETE /providers/{id} удаляет провайдера

### US-005: Мониторинг и дашборды

**As a** оператор платформы
**I want to** видеть метрики в реальном времени
**So that** я понимаю состояние системы и расходы

**Acceptance Criteria:**
- [ ] Prometheus собирает метрики: запросы, латентность (p50/p95), TTFT, TPOT, токены in/out, стоимость, коды ответов, CPU
- [ ] Grafana дашборд: латентность по провайдерам, распределение трафика, стоимость запросов, circuit breaker статус
- [ ] Langfuse трассирует работу агентов: входы, выходы, промежуточные шаги
- [ ] GET /health для каждого сервиса

### US-006: Guardrails

**As a** оператор платформы
**I want to** фильтровать опасные запросы
**So that** агенты защищены от prompt injection и утечки секретов

**Acceptance Criteria:**
- [ ] Входящие запросы проверяются на паттерны prompt injection
- [ ] Исходящие ответы проверяются на утечку API-ключей, токенов, паролей
- [ ] Guardrails включаются/выключаются через конфиг
- [ ] Заблокированные запросы логируются с причиной

### US-007: Авторизация

**As a** оператор платформы
**I want to** контролировать доступ к платформе
**So that** только авторизованные агенты могут отправлять запросы

**Acceptance Criteria:**
- [ ] Bearer token в заголовке Authorization
- [ ] Без валидного токена - 401 Unauthorized
- [ ] Каждый агент имеет свой токен (выдаётся при регистрации)
- [ ] Мастер-токен для администрирования (регистрация провайдеров, управление агентами)

### US-008: Нагрузочное тестирование

**As a** проверяющий
**I want to** запустить нагрузочный тест одной командой
**So that** я вижу поведение платформы под нагрузкой

**Acceptance Criteria:**
- [ ] Скрипт нагрузочного теста (Locust или аналог)
- [ ] Сценарии: нормальная нагрузка (10-15 concurrent), пиковая (20-30), стресс (40-50)
- [ ] Тест на реальном OpenRouter API (дешёвые модели)
- [ ] Отчёт: throughput, латентность (p50/p95/p99), ошибки, поведение circuit breaker
- [ ] Демонстрация graceful degradation при достижении rate limit

---

## Functional Requirements

### Core Features

**Feature 1: LLM Proxy (Уровень 1)**
- OpenAI-совместимый API (/v1/chat/completions)
- Streaming через SSE без буферизации
- Роутинг по модели: запрос с model="deepseek/deepseek-chat" идёт к провайдеру DeepSeek
- Round-robin и статические веса для реплик

**Feature 2: A2A Agent Registry (Уровень 2)**
- CRUD для агентов с Agent Card
- Agent Card: имя, описание, поддерживаемые методы, endpoint URL, статус
- Токен при регистрации

**Feature 3: Provider Registry (Уровень 2)**
- Динамическая регистрация LLM-провайдеров
- Метаданные: URL, модели, цена/токен (input/output), лимиты (RPM/RPS), приоритет
- Health status в реальном времени

**Feature 4: Smart Routing (Уровень 2)**
- Latency-based: скользящее среднее времени ответа, приоритет быстрому
- Health-aware: circuit breaker (порог ошибок -> исключение -> cooldown -> возврат)
- Fallback: автоматический переход на другого провайдера

**Feature 5: Observability Stack (Уровни 1-2)**
- OpenTelemetry: distributed tracing
- Prometheus: метрики (см. NFR раздел 6)
- Grafana: дашборды
- Langfuse (self-hosted): трассировка агентов

**Feature 6: Guardrails (Уровень 3)**
- Middleware pipeline: request -> guardrails -> proxy -> guardrails -> response
- Prompt injection detector (regex + heuristics)
- Secret leak detector (regex для ключей, токенов, паролей)
- Конфигурируемый (вкл/выкл per guardrail)

**Feature 7: Authorization (Уровень 3)**
- Bearer token auth middleware
- Мастер-токен (env variable) для административных операций
- Per-agent токены для LLM-запросов

**Feature 8: Load Testing (Уровень 3)**
- Locust сценарии
- Три профиля нагрузки: normal, peak, stress
- Автоматический отчёт

### Демо-агенты (для интеграционного тестирования)

**DemoDay Profile Agent**
- Регистрируется на платформе с Agent Card
- Профилирует гостей через 1-2 turn диалог
- Использует платформу как LLM-прокси

**DemoDay Curator Agent**
- Регистрируется на платформе с Agent Card
- Tool use: show_project, compare_projects, generate_questions
- Использует платформу как LLM-прокси

**Utility Agent (простой)**
- Суммаризация текста или перевод
- Для демонстрации что платформа работает с любым агентом

### Out of Scope
- Веб-интерфейс (только API + Grafana)
- Персистентность реестров между перезапусками (in-memory)
- Продакшн-деплой на сервер
- Полная интеграция с DemoDay кодовой базой (только адаптеры агентов)
- Собственные LLM-модели
- MCP protocol (только A2A)

---

## Technical Constraints

### Performance
- Overhead платформы: < 50ms (p95)
- Health-check: < 10ms
- Streaming без буферизации

### Security
- OpenRouter API key в env, не в коде
- Bearer token авторизация
- Guardrails middleware
- .env в .gitignore

### Integration
- **OpenRouter API**: единственный внешний LLM-провайдер (через него все модели)
- **OpenAI-совместимый формат**: /v1/chat/completions

### Technology Stack
- Python 3.12, FastAPI, uvicorn
- Docker Compose
- Prometheus, Grafana, OpenTelemetry
- Langfuse (self-hosted)
- Locust (нагрузочное тестирование)

### LLM-модели через OpenRouter

| Модель | Тип | Input $/1M | Output $/1M | Назначение |
|--------|-----|-----------|------------|------------|
| StepFun Step 3.5 Flash | Free | $0 | $0 | Нагрузочные тесты |
| NVIDIA Nemotron 3 Super | Free | $0 | $0 | Нагрузочные тесты |
| DeepSeek V3.2 | Cheap | $0.26 | $0.38 | Основная работа агентов |
| OpenAI gpt-oss-120b | Cheap | $0.039 | $0.19 | Альтернатива DeepSeek |
| xAI Grok 4.1 Fast | Cheap | $0.20 | $0.50 | Демонстрация multi-provider |
| Google Gemini 2.5 Flash Lite | Cheap | $0.10 | $0.40 | Fallback |

Баланс OpenRouter: $19. Бюджет на тесты: ~$1-2.

---

## MVP Scope & Phasing

### Phase 1: LLM Proxy + Observability (Уровень 1)
- Docker Compose с FastAPI, Prometheus, Grafana
- /v1/chat/completions с streaming
- Round-robin + статические веса
- Базовые метрики и дашборды
- Health-check endpoints

### Phase 2: Registries + Smart Routing (Уровень 2)
- Agent Registry (CRUD + Agent Card)
- Provider Registry (динамическая регистрация)
- Latency-based + health-aware routing
- Circuit breaker
- TTFT, TPOT, стоимость
- Langfuse трассировка (Session -> Trace -> Span -> Event)

### Phase 3: Security + Load Testing (Уровень 3)
- Guardrails middleware
- Bearer token авторизация
- Locust нагрузочные тесты
- Отчёт с результатами

### Phase 4: Demo Agents
- DemoDay Profile Agent адаптер
- DemoDay Curator Agent адаптер
- Utility Agent
- Интеграционный тест всей цепочки

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| OpenRouter rate limits ограничат нагрузочный тест | High | Medium | Использовать бесплатные модели для объёма, платные для качества. Показать circuit breaker на 429. |
| Бесплатные модели нестабильны | Medium | Medium | Fallback на дешёвые платные. Circuit breaker исключит нестабильного. |
| Не уложиться в 1 день | High | High | Параллельная работа через субагентов. Phase 1-2 приоритетнее Phase 3-4. |
| SSE streaming через прокси сложнее ожидаемого | Medium | Medium | FastAPI + httpx поддерживают async streaming нативно. |
| Langfuse добавляет complexity в Docker Compose | Low | Low | Минимальная конфигурация, только трассировка. |

---

## Dependencies & Blockers

**Dependencies:**
- OpenRouter API key (есть, баланс $19)
- Docker + Docker Compose (установлен)
- Доступ к интернету (для OpenRouter API)

**Known Blockers:**
- Нет

---

## Appendix

### Glossary
- **A2A**: Agent-to-Agent protocol (Google)
- **Agent Card**: Метаданные агента (имя, описание, методы, endpoint)
- **TTFT**: Time to First Token - время до первого токена в streaming ответе
- **TPOT**: Time per Output Token - среднее время генерации одного токена
- **Circuit Breaker**: Паттерн отказоустойчивости - исключение нестабильного провайдера из пула
- **Guardrails**: Фильтры безопасности для LLM-запросов и ответов
- **SSE**: Server-Sent Events - протокол streaming ответов

### References
- [OpenRouter API Docs](https://openrouter.ai/docs)
- [Google A2A Protocol](https://github.com/google/A2A)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- Brief: docs/brief.md
- NFR: docs/nfr.md
