#!/bin/bash

# Script para limpeza manual de backups antigos
# Uso: ./scripts/cleanup.sh [dias]
# Exemplo: ./scripts/cleanup.sh 30

set -e

# Definir número de dias (padrão: 30)
DAYS=${1:-30}

echo "🧹 Iniciando limpeza de backups antigos..."
echo "📅 $(date '+%d/%m/%Y %H:%M:%S')"
echo "⏰ Removendo backups mais antigos que $DAYS dias"
echo ""

# Verificar se o diretório de backups existe
if [ ! -d "backups" ]; then
    echo "⚠️  Diretório de backups não encontrado"
    exit 1
fi

# Contar arquivos antes da limpeza
TOTAL_BEFORE=$(find backups/ -type f 2>/dev/null | wc -l || echo '0')
SIZE_BEFORE=$(du -sh backups/ 2>/dev/null | cut -f1 || echo 'N/A')

echo "📊 Estado atual:"
echo "   📄 Arquivos: $TOTAL_BEFORE"
echo "   💾 Espaço: $SIZE_BEFORE"
echo ""

# Verificar se o Docker está rodando
if docker info > /dev/null 2>&1; then
    # Usar o container se estiver disponível
    if docker compose ps | grep -q "datacom-backup"; then
        echo "🐳 Executando limpeza via container..."
        docker compose exec datacom-backup python src/datacom_backup.py cleanup
    else
        echo "⚠️  Container não está rodando. Executando limpeza local..."
        # Limpeza local usando find
        find backups/ -type f -mtime +$DAYS -delete 2>/dev/null || true
        
        # Remover diretórios vazios
        find backups/ -type d -empty -delete 2>/dev/null || true
    fi
else
    echo "⚠️  Docker não disponível. Executando limpeza local..."
    # Limpeza local usando find
    REMOVED=$(find backups/ -type f -mtime +$DAYS -print | wc -l)
    find backups/ -type f -mtime +$DAYS -delete 2>/dev/null || true
    
    # Remover diretórios vazios
    find backups/ -type d -empty -delete 2>/dev/null || true
    
    echo "🗑️  Arquivos removidos: $REMOVED"
fi

# Contar arquivos após a limpeza
TOTAL_AFTER=$(find backups/ -type f 2>/dev/null | wc -l || echo '0')
SIZE_AFTER=$(du -sh backups/ 2>/dev/null | cut -f1 || echo 'N/A')
REMOVED=$((TOTAL_BEFORE - TOTAL_AFTER))

echo ""
echo "📊 Resultado da limpeza:"
echo "   🗑️  Arquivos removidos: $REMOVED"
echo "   📄 Arquivos restantes: $TOTAL_AFTER"
echo "   💾 Espaço atual: $SIZE_AFTER"
echo ""

if [ $REMOVED -gt 0 ]; then
    echo "✅ Limpeza concluída com sucesso!"
else
    echo "ℹ️  Nenhum arquivo antigo encontrado para remoção"
fi

echo ""
echo "💡 Dicas:"
echo "   • Configure BACKUP_RETENTION_DAYS no arquivo .env"
echo "   • A limpeza automática roda toda segunda às 03:00"
echo "   • Use 'docker compose logs' para ver logs detalhados"
echo ""
echo "🏁 Limpeza finalizada!"