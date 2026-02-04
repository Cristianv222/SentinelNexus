from django.core.management.base import BaseCommand
from submodulos.models import ProxmoxServer, MaquinaVirtual
from submodulos.logic.forecasting import train_and_predict_server, train_and_predict_vm

class Command(BaseCommand):
    help = 'Generates SARIMA predictions for Servers and VMs'

    def add_arguments(self, parser):
        parser.add_argument('--servers', action='store_true', help='Predict for Servers only')
        parser.add_argument('--vms', action='store_true', help='Predict for VMs only')
        parser.add_argument('--days', type=int, default=1, help='Days to predict ahead (default: 1 day / 24 hours)')

    def handle(self, *args, **options):
        steps = options['days'] * 24
        run_all = not options['servers'] and not options['vms']
        
        if run_all or options['servers']:
            self.stdout.write("Starting Server predictions...")
            servers = ProxmoxServer.objects.filter(is_active=True)
            for server in servers:
                self.stdout.write(f"Processing Server: {server.name}")
                train_and_predict_server(server.pk, steps=steps)
        
        if run_all or options['vms']:
            self.stdout.write("Starting VM predictions...")
            vms = MaquinaVirtual.objects.filter(estado='running') # Solo VMs encendidas
            for vm in vms:
                self.stdout.write(f"Processing VM: {vm.nombre}")
                train_and_predict_vm(vm.pk, steps=steps)
                
        self.stdout.write(self.style.SUCCESS('Prediction cycle completed.'))
