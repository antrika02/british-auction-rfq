FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install packages first, so Docker can reuse this step when only code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY db ./db
COPY scripts ./scripts

EXPOSE 8000

# One worker on purpose: live updates currently pass through memory inside one process
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
