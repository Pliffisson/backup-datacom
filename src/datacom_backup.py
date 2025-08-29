#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Backup Automatizado para Equipamentos Datacom
Desenvolvido para realizar backups automáticos via SSH com notificações Telegram
"""

import os
import sys
import json
import logging
import paramiko
import schedule
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytz

class DatacomBackup:
    def __init__(self, config_file: str = 'config/devices.json'):
        self.config_file = config_file
        self.backup_dir = Path('backups')
        self.log_dir = Path('logs')
        self.devices = []
        
        # Configurar timezone para São Paulo
        self.timezone = pytz.timezone('America/Sao_Paulo')
        
        # Configurar diretórios
        self.backup_dir.mkdir(exist_ok=True, mode=0o755)
        self.log_dir.mkdir(exist_ok=True, mode=0o755)
        
        # Garantir permissões corretas
        try:
            os.chmod(self.backup_dir, 0o755)
            os.chmod(self.log_dir, 0o755)
        except PermissionError:
            print(f"Aviso: Não foi possível definir permissões para diretórios")
        
        # Configurações do ambiente
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.backup_retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
        self.collect_system_info = os.getenv('COLLECT_SYSTEM_INFO', 'true').lower() == 'true'
        self.ssh_timeout = int(os.getenv('SSH_TIMEOUT', '30'))
        
        # Configurar logging
        self.setup_logging()
        
        # Carregar dispositivos
        self.load_devices()
    
    def get_current_time(self):
        """Retorna o datetime atual no timezone de São Paulo"""
        return datetime.now(self.timezone)
    
    def setup_logging(self):
        """Configura o sistema de logging"""
        self.log_dir.mkdir(exist_ok=True, mode=0o755)
        
        log_file = self.log_dir / f'datacom_backup_{self.get_current_time().strftime("%Y%m%d")}.log'
        
        # Tentar criar o arquivo de log com permissões adequadas
        try:
            log_file.touch(mode=0o644, exist_ok=True)
        except PermissionError:
            print(f"Aviso: Não foi possível criar arquivo de log em {log_file}")
            # Usar apenas console logging se não conseguir criar arquivo
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[logging.StreamHandler(sys.stdout)]
            )
            self.logger = logging.getLogger(__name__)
            return
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def load_devices(self):
        """Carrega a configuração dos dispositivos"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.devices = config.get('devices', [])
            self.logger.info(f"Carregados {len(self.devices)} dispositivos")
        except FileNotFoundError:
            self.logger.error(f"Arquivo de configuração não encontrado: {self.config_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            self.logger.error(f"Erro ao decodificar JSON: {e}")
            sys.exit(1)
    
    def send_telegram_notification(self, message: str, parse_mode: str = 'HTML'):
        """Envia notificação via Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            self.logger.warning("Telegram não configurado - notificação ignorada")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, data=data, timeout=10)
            response.raise_for_status()
            
            self.logger.info("Notificação Telegram enviada com sucesso")
            return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro ao enviar notificação Telegram: {e}")
            return False
    

    
    def connect_ssh(self, device: Dict) -> Optional[paramiko.SSHClient]:
        """Estabelece conexão SSH com o dispositivo"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh.connect(
                hostname=device['host'],
                port=device.get('port', 22),
                username=device['username'],
                password=device['password'],
                timeout=self.ssh_timeout
            )
            
            return ssh
            
        except Exception as e:
            self.logger.error(f"Erro ao conectar SSH em {device['name']}: {e}")
            return None
    
    def execute_command(self, ssh: paramiko.SSHClient, command: str) -> tuple:
        """Executa comando via SSH"""
        try:
            stdin, stdout, stderr = ssh.exec_command(command)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            return output, error
        except Exception as e:
            return None, str(e)
    
    def get_device_info(self, ssh: paramiko.SSHClient, device: Dict) -> str:
        """Coleta informações do sistema do dispositivo Datacom"""
        info_lines = []
        info_lines.append(f"=== Informações do Dispositivo: {device['name']} ===")
        info_lines.append(f"Host: {device['host']}")
        info_lines.append(f"Data/Hora do Backup: {self.get_current_time().strftime('%d/%m/%Y %H:%M:%S')}")
        info_lines.append("")
        
        # Comandos específicos para equipamentos Datacom
        commands = {
            'Versão do Sistema': 'show version',
            'Informações do Hardware': 'show system',
            'Status das Interfaces': 'show interface brief',
            'Tabela de Roteamento': 'show ip route summary',
            'Uptime': 'show uptime',
            'Memória': 'show memory',
            'CPU': 'show cpu'
        }
        
        for desc, cmd in commands.items():
            output, error = self.execute_command(ssh, cmd)
            if output and not error:
                info_lines.append(f"=== {desc} ===")
                info_lines.append(output.strip())
                info_lines.append("")
            else:
                info_lines.append(f"=== {desc} (Erro) ===")
                info_lines.append(f"Erro: {error or 'Comando não suportado'}")
                info_lines.append("")
        
        return "\n".join(info_lines)
    
    def backup_device_config(self, ssh: paramiko.SSHClient, device: Dict, backup_path: Path) -> bool:
        """Realiza backup da configuração do dispositivo Datacom"""
        try:
            # Comando para exportar configuração em equipamentos Datacom
            config_output, error = self.execute_command(ssh, 'show running-config')
            
            if error:
                self.logger.error(f"Erro ao obter configuração de {device['name']}: {error}")
                return False
            
            if not config_output.strip():
                self.logger.warning(f"Configuração vazia recebida de {device['name']}")
                return False
            
            # Salvar configuração
            config_file = backup_path / f"{device['name']}_{self.get_current_time().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(config_output)
            
            self.logger.info(f"Configuração salva: {config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao fazer backup da configuração de {device['name']}: {e}")
            return False
    
    def backup_device(self, device: Dict) -> Dict:
        """Realiza backup completo de um dispositivo"""
        result = {
            'device': device['name'],
            'success': False,
            'files': [],
            'error': None,
            'start_time': self.get_current_time(),
            'end_time': None
        }
        
        try:
            self.logger.info(f"Iniciando backup de {device['name']} ({device['host']})")
            
            # Criar diretório do dispositivo
            device_backup_dir = self.backup_dir / device['name']
            device_backup_dir.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            # Garantir permissões corretas
            try:
                os.chmod(device_backup_dir, 0o755)
            except PermissionError:
                self.logger.warning(f"Não foi possível definir permissões para {device_backup_dir}")
            
            # Conectar via SSH
            ssh = self.connect_ssh(device)
            if not ssh:
                result['error'] = 'Falha na conexão SSH'
                return result
            
            try:
                # Backup da configuração
                if self.backup_device_config(ssh, device, device_backup_dir):
                    config_file = f"{device['name']}_{self.get_current_time().strftime('%Y%m%d_%H%M%S')}.txt"
                    result['files'].append(config_file)
                
                # Coletar informações do sistema (se habilitado)
                if self.collect_system_info:
                    info_content = self.get_device_info(ssh, device)
                    info_file = device_backup_dir / f"{device['name']}_{self.get_current_time().strftime('%Y%m%d_%H%M%S')}_info.txt"
                    
                    with open(info_file, 'w', encoding='utf-8') as f:
                        f.write(info_content)
                    
                    result['files'].append(info_file.name)
                    self.logger.info(f"Informações do sistema salvas: {info_file}")
                
                result['success'] = True
                self.logger.info(f"Backup de {device['name']} concluído com sucesso")
                
            finally:
                ssh.close()
                
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"Erro durante backup de {device['name']}: {e}")
        
        result['end_time'] = self.get_current_time()
        return result
    
    def backup_all_devices(self) -> List[Dict]:
        """Realiza backup de todos os dispositivos configurados"""
        self.logger.info(f"Iniciando backup de {len(self.devices)} dispositivos")
        start_time = self.get_current_time()
        
        results = []
        
        # Backup paralelo dos dispositivos
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_device = {executor.submit(self.backup_device, device): device for device in self.devices}
            
            for future in as_completed(future_to_device):
                result = future.result()
                results.append(result)
        
        end_time = self.get_current_time()
        duration = end_time - start_time
        
        # Estatísticas
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        
        self.logger.info(f"Backup concluído: {successful} sucessos, {failed} falhas em {duration}")
        
        # Enviar notificação
        self.send_backup_notification(results, duration)
        
        return results
    
    def send_backup_notification(self, results: List[Dict], duration):
        """Envia notificação do resultado do backup"""
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        # Emoji baseado no resultado
        if not failed:
            emoji = "✅"
            status = "Sucesso"
        elif not successful:
            emoji = "❌"
            status = "Falha Total"
        else:
            emoji = "⚠️"
            status = "Parcial"
        
        message = f"{emoji} <b>Backup Datacom - {status}</b>\n\n"
        message += f"📊 <b>Resumo:</b>\n"
        message += f"• Sucessos: {len(successful)}\n"
        message += f"• Falhas: {len(failed)}\n"
        message += f"• Duração: {duration}\n"
        message += f"• Data: {self.get_current_time().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        
        if successful:
            message += "✅ <b>Dispositivos com Sucesso:</b>\n"
            for result in successful:
                files_count = len(result['files'])
                message += f"• {result['device']} ({files_count} arquivos)\n"
            message += "\n"
        
        if failed:
            message += "❌ <b>Dispositivos com Falha:</b>\n"
            for result in failed:
                error = result['error'] or 'Erro desconhecido'
                message += f"• {result['device']}: {error}\n"
        
        self.send_telegram_notification(message)
    
    def cleanup_old_backups(self):
        """Remove backups antigos baseado na retenção configurada"""
        self.logger.info(f"Iniciando limpeza de backups antigos (>{self.backup_retention_days} dias)")
        
        cutoff_date = self.get_current_time() - timedelta(days=self.backup_retention_days)
        removed_count = 0
        
        for device_dir in self.backup_dir.iterdir():
            if device_dir.is_dir():
                for backup_file in device_dir.iterdir():
                    if backup_file.is_file():
                        file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)
                        if file_time < cutoff_date:
                            backup_file.unlink()
                            removed_count += 1
                            self.logger.info(f"Removido backup antigo: {backup_file}")
        
        self.logger.info(f"Limpeza concluída: {removed_count} arquivos removidos")
        
        if removed_count > 0:
            message = f"🧹 <b>Limpeza de Backups</b>\n\n" \
                     f"📁 Arquivos removidos: {removed_count}\n" \
                     f"📅 Mais antigos que: {self.backup_retention_days} dias\n" \
                     f"🕐 {self.get_current_time().strftime('%d/%m/%Y %H:%M:%S')}"
            
            self.send_telegram_notification(message)
    
    def schedule_backups(self):
        """Configura o agendamento automático dos backups"""
        self.logger.info("Configurando agendamento de backups")
        
        # Backup diário às 02:00
        schedule.every().day.at("02:00").do(self.backup_all_devices)
        
        # Backup semanal aos domingos às 01:00
        schedule.every().sunday.at("01:00").do(self.backup_all_devices)
        
        # Limpeza semanal às segundas às 03:00
        schedule.every().monday.at("03:00").do(self.cleanup_old_backups)
        
        self.logger.info("Agendamentos configurados:")
        self.logger.info("- Backup diário: 02:00")
        self.logger.info("- Backup semanal: Domingo 01:00")
        self.logger.info("- Limpeza: Segunda 03:00")
        
        # Notificação de inicialização
        message = f"🚀 <b>Sistema de Backup Datacom Iniciado</b>\n\n" \
                 f"📱 Dispositivos configurados: {len(self.devices)}\n" \
                 f"⏰ Backup diário: 02:00\n" \
                 f"📅 Backup semanal: Domingo 01:00\n" \
                 f"🧹 Limpeza: Segunda 03:00\n" \
                 f"📁 Retenção: {self.backup_retention_days} dias\n" \
                 f"🕐 {self.get_current_time().strftime('%d/%m/%Y %H:%M:%S')}"
        
        self.send_telegram_notification(message)
        
        # Loop principal
        while True:
            schedule.run_pending()
            time.sleep(60)

def main():
    parser = argparse.ArgumentParser(description='Sistema de Backup Datacom')
    parser.add_argument('action', nargs='?', default='schedule',
                       choices=['schedule', 'backup', 'cleanup'],
                       help='Ação a ser executada')
    
    args = parser.parse_args()
    
    backup_system = DatacomBackup()
    
    if args.action == 'schedule':
        backup_system.schedule_backups()
    elif args.action == 'backup':
        backup_system.backup_all_devices()
    elif args.action == 'cleanup':
        backup_system.cleanup_old_backups()

if __name__ == '__main__':
    main()