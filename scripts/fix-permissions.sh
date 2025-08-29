#!/bin/bash

# Script para corrigir permissões dos diretórios de backup
# Uso: ./scripts/fix-permissions.sh

set -e

echo "🔧 Corrigindo permissões dos diretórios de backup..."
echo "📅 $(date '+%d/%m/%Y %H:%M:%S')"
echo ""

# Verificar se o Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker não está rodando. Inicie o Docker e tente novamente."
    exit 1
fi

# Verificar se o container existe
if ! docker compose ps | grep -q "datacom-backup"; then
    echo "⚠️  Container não encontrado. Inicie o sistema primeiro com 'docker compose up -d'"
    exit 1
fi

echo "🔐 Corrigindo permissões dentro do container..."

# Corrigir permissões como root dentro do container
docker exec -u root datacom-backup chown -R backup:backup /app/backups /app/logs /app/config

if [ $? -eq 0 ]; then
    echo "✅ Permissões corrigidas com sucesso!"
    echo "📁 Diretórios: backups/, logs/, config/"
    echo "👤 Proprietário: backup:backup"
else
    echo "❌ Erro ao corrigir permissões"
    exit 1
fi

echo ""
echo "📊 Verificando permissões atuais:"
docker exec datacom-backup ls -la /app/ | grep -E "(backups|logs|config)"

echo ""
echo "💡 Dica: Execute este script sempre que recriar o container"
echo "🏁 Correção de permissões finalizada!"