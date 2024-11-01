FROM python:3.11.0-alpine

WORKDIR /app
RUN apk update && apk upgrade
COPY requirements.txt .
RUN pip install --upgrade pip uv 
RUN uv pip install --system  -r requirements.txt

COPY templates /app/templates

COPY app.py .
COPY urls.txt .

EXPOSE 5000

# CMD ["ddtrace-run","gunicorn", "-b", "0.0.0.0:5000", "app:app", "--timeout 200"]

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000", "--interface", "wsgi"]
