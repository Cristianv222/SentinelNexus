
import os
import django
import sys

# Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

from submodulos.models import MaquinaVirtual

def set_critical(vm_ids, remove=False):
    if not vm_ids:
        print("ℹ️ No se especificaron IDs. Mostrando lista actual...")
    
    action_text = "QUITAR" if remove else "PONER"
    
    for vmid in vm_ids:
        try:
            vm = MaquinaVirtual.objects.get(vmid=vmid)
            vm.is_critical = not remove
            vm.save()
            
            if remove:
                print(f"✅ LIBERADA: La VM '{vm.nombre}' (ID: {vmid}) ya NO es crítica. Puedes apagarla tranquilo.")
            else:
                print(f"✅ PROTEGIDA: La VM '{vm.nombre}' (ID: {vmid}) ahora es CRÍTICA. El Watchdog la vigilará.")
                
        except MaquinaVirtual.DoesNotExist:
            print(f"❌ ERROR: No se encontró ninguna VM con ID {vmid}.")
        except Exception as e:
            print(f"❌ Error al procesar {vmid}: {e}")

    # Mostrar resumen
    print("\n📋 === LISTA DE VMS CRÍTICAS (WATCHDOG) ===")
    criticas = MaquinaVirtual.objects.filter(is_critical=True)
    if criticas.exists():
        for vm in criticas:
            print(f"  - [{vm.vmid}] {vm.nombre} (Nodo: {vm.nodo.nombre})")
    else:
        print("  (Ninguna VM marcada como crítica)")
    print("============================================")

if __name__ == "__main__":
    args = sys.argv[1:]
    remove_mode = False
    
    if "--remove" in args:
        remove_mode = True
        args.remove("--remove")
    elif "-r" in args:
        remove_mode = True
        args.remove("-r")
        
    set_critical(args, remove=remove_mode)
