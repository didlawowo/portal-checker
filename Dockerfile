FROM python:3.12.0-alpine

WORKDIR /app
RUN apk update && apk upgrade
COPY requirements.txt .
RUN pip install --upgrade pip uv 
RUN uv pip install --system  -r requirements.txt

COPY templates /app/templates
COPY static /app/static
COPY app.py .
COPY urls.txt .

EXPOSE 5000

CMD ["hypercorn", "app:app", "--bind", "0.0.0.0:5000", "--worker-class", "asyncio"]