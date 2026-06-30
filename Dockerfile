FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/ ./data/

# Copy pre-built database with 36k real admission records
COPY data/gaokao.db ./data/gaokao.db

EXPOSE 7860

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "7860"]
