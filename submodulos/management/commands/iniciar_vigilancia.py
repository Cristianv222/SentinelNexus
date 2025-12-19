from django.core.management.base import BaseCommand
import asyncio
from submodulos.agents.monitor import MonitorAgent
from submodulos.agents.cerebro import CerebroAgent

class Command(BaseCommand):
    help = 'Inicia el sistema de vigilancia Sentinel Nexus con múltiples agentes'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 INICIANDO SENTINEL NEXUS - MODO MULTI-SERVER'))

        # --- CONFIGURACIÓN DE LOS 3 SERVIDORES ---
        SERVIDORES = [
            {
                "nombre": "PRINCIPAL",
                "ip": "10.100.100.40",      
                "user": "root@pam",
                "pass": "Andres_zabala1983",
                "jid": "monitor@sentinelnexus.local" 
            },
            {
                "nombre": "SECUNDARIO",
                "ip": "10.100.100.12",      
                "user": "root@pam",
                "pass": "AdminUpec_2025",
                "jid": "monitor_secundario@sentinelnexus.local"
            },
            {
                "nombre": "BACKUP",
                "ip": "10.100.100.21",      
                "user": "root@pam",
                "pass": "AdminUpec_2025",
                "jid": "monitor_backup@sentinelnexus.local"
            }
        ]
        # -----------------------------------------

        async def main():
            agentes_activos = []

            # 1. Iniciar el CEREBRO
            cerebro = CerebroAgent("cerebro@sentinelnexus.local", "sentinel123")
            await cerebro.start()
            agentes_activos.append(cerebro)
            print("🧠 CEREBRO: Online y escuchando.")

            # 2. Iniciar los 3 MONITORES
            for srv in SERVIDORES:
                print(f"🔌 Iniciando agente para {srv['nombre']} ({srv['ip']})...")
                
                agente = MonitorAgent(
                    srv['jid'], 
                    "sentinel123", # Password del chat XMPP
                    srv['ip'], 
                    srv['user'], 
                    srv['pass']    # Password de Proxmox
                )
                
                await agente.start()
                agentes_activos.append(agente)
            
            print("\n✅ TODOS LOS SISTEMAS OPERATIVOS.")
            print("Presiona Ctrl+C para detener la vigilancia.\n")

            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Deteniendo sistema...")
                for a in agentes_activos:
                    await a.stop()

        # Ejecutar el bucle asíncrono
        asyncio.run(main())