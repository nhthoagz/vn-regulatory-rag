FROM python:3.11-slim

WORKDIR /app

# 1) cài dependency theo pyproject (không cần uv trong image)
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "pyyaml>=6.0" "pydantic>=2.7" "python-dotenv>=1.0" "pdfplumber>=0.11" \
    "fastapi>=0.110" "uvicorn>=0.29" "httpx>=0.27"

# 2) code + cấu hình
COPY src ./src
COPY config ./config

# 3) artifact phải build trước khi docker build (chứa text luật nên không nằm trong git):
#    make build && make rules
COPY data/processed ./data/processed
COPY data/index ./data/index
COPY rules ./rules

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]