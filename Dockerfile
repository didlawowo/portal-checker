FROM python:3.11.0-alpine

WORKDIR /app
RUN apk update && apk upgrade
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip uv 
RUN uv pip install --system -r requirements.txt

COPY . /app

EXPOSE 8000

# CMD ["ddtrace-run","gunicorn", "-b", "0.0.0.0:5000", "app:app", "--timeout 200"]

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app", "--timeout 200"]
