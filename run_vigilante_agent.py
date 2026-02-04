
import sys
print(f"DEBUG: STARTING EXECUTION. Python: {sys.executable}")
import os
import asyncio
import time
from dotenv import load_dotenv

# Cargar variables de entorno
# Cargar variables de entorno
load_dotenv()

# ======================================================
# 💉 CONFIGURACIÓN PERMISIVA DE TLS (Permitir certificados auto-firmados)
# ======================================================
import sys
import slixmpp

print("[RUNNER] INICIANDO CONFIGURACION TLS PERMISIVA...")

# Parcheamos para asegurar que no verifique certificados
_original_init = slixmpp.ClientXMPP.__init__
def constructor_permissive(self, *args, **kwargs):
    # 🩹 FORZAR ARGS EN EL NACIMIENTO DEL CLIENTE (NUCLEAR OPTION)
    kwargs['use_tls'] = False
    kwargs['use_ssl'] = False
    kwargs['disable_starttls'] = True
    kwargs['force_starttls'] = False 

    _original_init(self, *args, **kwargs)
    
    # 🩹 POST-INIT OVERRIDE (Doble seguridad)
    self.force_starttls = False
    self.disable_starttls = True
    print(f"[RUNNER] CLIENTE INICIALIZADO. force_starttls={self.force_starttls}, disable_starttls={self.disable_starttls}, use_tls={self.use_tls}")
    
    # Configuración para aceptar certificados inválidos/autofirmados
    self.use_tls = False  # <--- FORZADO OFF (PLAIN)
    self.use_ssl = False # No usar SSL legado (puerto 5223)
    self.check_certificate = False # <--- IMPORTANTE: No verificar cert
    self.verify_ssl = False        # <--- IMPORTANTE
    
    # Asegurar que SASL PLAIN esté permitido incluso sin encriptación
    try:
        self.plugin['feature_mechanisms'].unencrypted_plain = True
        self.plugin['feature_mechanisms'].config['unencrypted_plain'] = True
        self.plugin['feature_mechanisms'].config['use_mech'] = 'PLAIN' 
    except Exception:
        pass
    
    # Asegurar que SASL PLAIN esté permitido
    self.plugin['feature_mechanisms'].unencrypted_plain = True

slixmpp.ClientXMPP.__init__ = constructor_permissive

# 🩸 PARCHE AL JAQUE MATE: AGENT.__INIT__
# Si no podemos cambiar el motor, cambiamos al conductor.
try:
    import spade.agent
    _original_agent_init = spade.agent.Agent.__init__
    
    def agent_init_hook(self, *args, **kwargs):
        _original_agent_init(self, *args, **kwargs)
        # YA EXISTE self.client AQUI
        print(f"[RUNNER] INTERCEPTADO AGENTE {self.jid}. FORZANDO CLIENTE...")
        if hasattr(self, 'client') and self.client:
            self.client.use_tls = False
            self.client.use_ssl = False
            self.client.disable_starttls = True
            self.client.force_starttls = False
            self.client.check_certificate = False
            self.client.verify_ssl = False
            try:
                self.client.plugin['feature_mechanisms'].unencrypted_plain = True
            except:
                pass
            print(f"[RUNNER] CLIENTE PARCHEADO EXITOSAMENTE: {self.client.jid}")

    spade.agent.Agent.__init__ = agent_init_hook
    print("[RUNNER] spade.agent.Agent.__init__ INTERCEPTADO.")
    
    # 🩸 PARCHE AL START (ULTIMO RECURSO)
    _original_start = spade.agent.Agent.start
    async def start_hook(self, *args, **kwargs):
        print(f"[RUNNER] START INTERCEPTADO. Spade Version: {spade.__version__}")
        try:
            import inspect
            # Intentar obtener _async_start
            async_start_method = getattr(self, '_async_start', None)
            if async_start_method:
                 src = inspect.getsource(async_start_method)
                 print(f"[DEBUG-SOURCE] Código de _async_start remoto:\n{src}")
            else:
                 print("[DEBUG-SOURCE] No se encontró _async_start")
                 
        except Exception as e:
            print(f"[DEBUG-SOURCE] No se pudo leer source: {e}")
            
        return await _original_start(self, *args, **kwargs)
        
    spade.agent.Agent.start = start_hook
    print("[RUNNER] spade.agent.Agent.start INTERCEPTADO.")

except ImportError:
    print("[RUNNER] FATAL: No se pudo importar spade.agent.")

# 1.5 Parche a connect (Para evitar error de argumento 'host' inesperado y FORZAR IP)
_original_connect = slixmpp.ClientXMPP.connect
def connect_parcheado(self, *args, **kwargs):
    print(f"[RUNNER] CONNECT INTERCEPTADO. Args: {kwargs}")
    # Limpieza de argumentos basura de Spade/Legacy
    if 'host' in kwargs: del kwargs['host']
    if 'port' in kwargs: del kwargs['port']
    
    # 🩹 FORZAR PARAMETROS EN CONNECT (CRITICO PARA FIX TLS)
    kwargs['use_ssl'] = False
    kwargs['disable_starttls'] = True
    kwargs['force_starttls'] = False
        
    # INYECCIÓN DE IP CORRECTA DE PROSODY
    xmpp_host = os.getenv('XMPP_HOST')
    if xmpp_host:
        print(f"[PATCH] FORZANDO CONEXION A: {xmpp_host}:5222")
        kwargs['address'] = (xmpp_host, 5222)
        
    return _original_connect(self, *args, **kwargs)
slixmpp.ClientXMPP.connect = connect_parcheado
print(f"[RUNNER] slixmpp.ClientXMPP.connect INTERCEPTADO: {slixmpp.ClientXMPP.connect}")

print("[RUNNER] MODO TEXTO PLANO ACTIVADO (TLS=OFF, PLAIN=ON).")
sys.stdout.flush()
# ======================================================

from submodulos.agents.monitor import MonitorAgent

async def main():
    print("INICIANDO AGENTES VIGILANTES...")
    
    # Configuración XMPP Base
    xmpp_domain = os.getenv('XMPP_DOMAIN', 'sentinelnexus.local')
    xmpp_pass = os.getenv('XMPP_PASSWORD', 'sentinel123')
    
    agents = []

    # Iterar sobre los 3 nodos posibles configurados en .env
    for i in range(1, 4):
        host = os.getenv(f'PROXMOX_NODE{i}_HOST')
        user = os.getenv(f'PROXMOX_NODE{i}_USER')
        password = os.getenv(f'PROXMOX_NODE{i}_PASSWORD')
        name = os.getenv(f'PROXMOX_NODE{i}_NAME', f'Node{i}')

        if host and user and password:
            print(f"   Configurando Vigilante para: {name} ({host})...")
            
            # Usamos el usuario 'monitor' que ya existe
            jid = f"monitor@{xmpp_domain}"
            
            agent = MonitorAgent(jid, xmpp_pass, host, user, password)
            
            # --- PARCHE DE SEGURIDAD TLS (Igual que en Cerebro) ---
            # --- PARCHE DE SEGURIDAD TLS (Acceso Directo al Agente) ---
            agent.use_tls = False
            agent.use_ssl = False
            agent.force_starttls = False
            agent.disable_starttls = True
            # ------------------------------------------------------
            # ------------------------------------------------------

            agents.append(agent)
            
            # BRUTE FORCE PATCH ON CLIENT (Removed - handled in constructor)
            try:
                await agent.start()
                print(f"     Vigilante {i} (monitor) activo y escaneando.")
            except Exception as e:
                print(f"     Error al iniciar Vigilante {i}: {e}")
            
            
            # SOLO INICIAMOS EL PRIMERO PORQUE 'monitor' ES UN SOLO USUARIO
            # break  <-- COMENTADO PARA PROBAR TODOS LOS NODOS (Slixmpp usará resources aleatorios)
            pass

    if not agents:
        print("NO SE ENCONTRARON NODOS PROXMOX EN .ENV")
        return

    print(f"{len(agents)} Vigilantes operando. Presiona CTRL+C para detener.")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Deteniendo Vigilantes...")
        for a in agents:
            await a.stop()

if __name__ == "__main__":
    asyncio.run(main())
