import csv
import argparse
from django.core.management.base import BaseCommand
from submodulos.models import ServerPrediction, ServerMetric, ProxmoxServer

class Command(BaseCommand):
    help = 'Exporta datos de predicciones y/o métricas históricas a CSV.'

    def add_arguments(self, parser):
        parser.add_argument('--server', type=str, help='Nombre del servidor para filtrar')
        parser.add_argument('--output', type=str, default='predictions_export.csv', help='Ruta del archivo de salida')
        parser.add_argument('--include-history', action='store_true', help='Incluir métricas históricas (ServerMetric) en un archivo separado')
        parser.add_argument('--console', action='store_true', help='Imprimir tabla en la consola')

    def handle(self, *args, **options):
        server_name = options['server']
        output_file = options['output']
        include_history = options['include_history']
        show_console = options['console']

        # Exportar Predicciones
        predictions = ServerPrediction.objects.all().order_by('-timestamp')
        if server_name:
            predictions = predictions.filter(server__name=server_name)
            if not predictions.exists():
                self.stdout.write(self.style.WARNING(f'No se encontraron predicciones para el servidor "{server_name}"'))

        if predictions.exists():
            if show_console:
                self.stdout.write(self.style.SUCCESS(f"\nPredicciones para {server_name if server_name else 'todos los servidores'}:"))
                self.stdout.write("-" * 120)
                self.stdout.write(f"{'Servidor':<20} | {'Fecha y Hora':<20} | {'CPU (%)':<10} | {'RAM (%)':<10} | {'Confianza':<15} | {'Creado':<20}")
                self.stdout.write("-" * 120)
                
                for pred in predictions[:20]: # Mostrar solo las primeras 20 en consola para no saturar
                    self.stdout.write(f"{pred.server.name:<20} | {pred.timestamp.strftime('%Y-%m-%d %H:%M'):<20} | {pred.predicted_cpu_usage:<10.2f} | {pred.predicted_memory_usage:<10.2f} | {pred.confidence_lower:.2f}-{pred.confidence_upper:.2f} | {pred.created_at.strftime('%H:%M:%S'):<20}")
                
                if predictions.count() > 20:
                     self.stdout.write(f"... y {predictions.count() - 20} más.")
                self.stdout.write("-" * 120 + "\n")

            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Server', 'Timestamp', 'Predicted CPU (%)', 'Predicted Memory (%)', 'Confidence Lower', 'Confidence Upper', 'Created At']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                for pred in predictions:
                    writer.writerow({
                        'Server': pred.server.name,
                        'Timestamp': pred.timestamp,
                        'Predicted CPU (%)': pred.predicted_cpu_usage,
                        'Predicted Memory (%)': pred.predicted_memory_usage,
                        'Confidence Lower': pred.confidence_lower,
                        'Confidence Upper': pred.confidence_upper,
                        'Created At': pred.created_at,
                    })
            if not show_console:
                 self.stdout.write(self.style.SUCCESS(f'Predicciones exportadas exitosamente a "{output_file}"'))


        # Exportar Histórico si se solicita
        if include_history:
            history_file = output_file.replace('.csv', '_history.csv')
            metrics = ServerMetric.objects.all()
            if server_name:
                metrics = metrics.filter(server__name=server_name)
            
            if metrics.exists():
                with open(history_file, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['Server', 'Timestamp', 'CPU Usage (%)', 'RAM Usage (%)', 'Disk Usage (%)', 'Uptime']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    writer.writeheader()
                    for metric in metrics:
                        writer.writerow({
                             'Server': metric.server.name if metric.server else 'Unknown',
                             'Timestamp': metric.timestamp,
                             'CPU Usage (%)': metric.cpu_usage,
                             'RAM Usage (%)': metric.ram_usage,
                             'Disk Usage (%)': metric.disk_usage,
                             'Uptime': metric.uptime
                        })
                self.stdout.write(self.style.SUCCESS(f'Métricas históricas exportadas exitosamente a "{history_file}"'))
            else:
                 self.stdout.write(self.style.WARNING('No hay métricas históricas para exportar.'))
