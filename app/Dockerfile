FROM python:3.11.0-alpine

WORKDIR /app
RUN apk update && apk upgrade
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

EXPOSE 8000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app", "--timeout 200"]
