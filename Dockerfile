FROM python:3.11-slim

# Definir variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    openssh-client \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar arquivos de dependências
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Criar diretórios necessários primeiro
RUN mkdir -p backups logs

# Tornar scripts executáveis
RUN chmod +x scripts/*.sh

# Criar usuário não-root com UID específico
RUN id -u backup >/dev/null 2>&1 || useradd -m -u 1000 backup

# Definir permissões corretas para todos os diretórios
RUN chown -R backup:backup /app && \
    chmod -R 755 /app/backups && \
    chmod -R 755 /app/logs

USER backup

# Comando padrão
CMD ["python", "src/datacom_backup.py", "schedule"]