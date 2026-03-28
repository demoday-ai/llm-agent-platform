FROM python:3.12-slim

WORKDIR /app

COPY agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ agents/

CMD ["uvicorn", "agents.profile_agent.main:app", "--host", "0.0.0.0", "--port", "8001"]
