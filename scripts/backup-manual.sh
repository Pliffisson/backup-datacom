#!/bin/bash

# Script para execução manual de backup dos equipamentos Datacom
# Uso: ./scripts/backup-manual.sh

set -e

echo "🚀 Iniciando backup manual dos equipamentos Datacom..."
echo "📅 $(date '+%d/%m/%Y %H:%M:%S')"
echo ""

# Verificar se o Docker está rodando
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker não está rodando. Inicie o Docker e tente novamente."
    exit 1
fi

# Verificar se o container existe
if ! docker compose ps | grep -q "datacom-backup"; then
    echo "⚠️  Container não encontrado. Iniciando o sistema..."
    docker compose up -d
    echo "⏳ Aguardando inicialização..."
    sleep 10
fi

# Executar backup
echo "📦 Executando backup..."
docker compose exec datacom-backup python src/datacom_backup.py backup

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Backup manual concluído com sucesso!"
    echo "📁 Verifique os arquivos em: ./backups/"
    echo "📋 Logs disponíveis em: ./logs/"
else
    echo ""
    echo "❌ Erro durante o backup manual"
    echo "📋 Verifique os logs para mais detalhes: ./logs/"
    exit 1
fi

echo ""
echo "📊 Estatísticas dos backups:"
echo "📁 Espaço usado: $(du -sh backups/ 2>/dev/null | cut -f1 || echo 'N/A')"
echo "📄 Total de arquivos: $(find backups/ -type f 2>/dev/null | wc -l || echo '0')"
echo ""
echo "🏁 Backup manual finalizado!"