FROM python:3.14-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 \
PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --uid 10001 --no-create-home app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY viertelwatt/ viertelwatt/
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION
USER 10001
EXPOSE 8000
CMD ["uvicorn", "viertelwatt.api:app", "--host", "0.0.0.0", "--port", "8000"]
