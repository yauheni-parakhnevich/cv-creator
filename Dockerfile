FROM python:3.11-slim

# WeasyPrint system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY constraints.txt pyproject.toml README.md ./
COPY src/ src/

RUN PIP_CONSTRAINT=constraints.txt pip install --no-cache-dir -e .

ENV CV_CREATOR_DATA_DIR=/data

EXPOSE 8000

CMD ["uvicorn", "cv_creator.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
