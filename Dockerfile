FROM php:8.1-cli

# Instalar extensões PDO MySQL
RUN docker-php-ext-install pdo pdo_mysql

# Copiar arquivos do projeto
COPY . /app

WORKDIR /app

# Criar script de inicialização
RUN echo '#!/bin/sh\n\
PORT=${PORT:-8080}\n\
echo "Starting PHP server on port $PORT"\n\
php -S 0.0.0.0:$PORT index.php' > /start.sh && \
    chmod +x /start.sh

EXPOSE 8080

CMD ["/start.sh"]
