FROM python:3.13-alpine


ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV HTTP_PROXY=http://proxy-cloud.korian.cloud:80
ENV SSL_CERT_DIR=/etc/ssl/certs
# ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
# Create group and user with specific IDs
 
COPY  *.crt /etc/ssl/certs/
RUN update-ca-certificates

# Add certificates and tools needed
RUN apk update && apk add --no-cache ca-certificates uv  

# Créer un utilisateur non-root
RUN addgroup -g 1000 appgroup && adduser -u 1000 -G appgroup -D appuser

# # Installation des dépendances système
# RUN apk update && apk upgrade && \
#     apk add --no-cache gcc musl-dev # 🔧 Nécessaire pour certaines compilations Python

WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --upgrade pip  && \
    uv --native-tls pip install --system -r requirements.txt && \
    rm -rf /root/.cache/pip /root/.cache/uv # 🧹 Nettoyage du cache

# Copie des fichiers application
COPY templates /app/templates
COPY static /app/static
COPY app.py ./
COPY pyproject.toml ./
 

RUN mkdir /app/config && chown -R appuser:appgroup /app && \
    chmod -R 755 /app && \
    chmod 777 /app/config  

# Passage à l'utilisateur non-root
USER appuser

EXPOSE 5000

CMD ["hypercorn", "app:app", "--bind", "0.0.0.0:5000", "--worker-class", "asyncio"]
