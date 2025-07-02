# Dockerfile para Django
FROM python:3.11-slim

# Instala dependencias del sistema
RUN apt-get update && \
    apt-get install -y \
    pkg-config \
    python3-dev \
    default-libmysqlclient-dev \
    build-essential

WORKDIR /app

# Copia requirements.txt e instala dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código
COPY . .

# Expone el puerto 8000
EXPOSE 8000

# Comando por defecto: gunicorn
CMD ["gunicorn", "padel_reservation_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
