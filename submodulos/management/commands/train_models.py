from django.core.management.base import BaseCommand
from submodulos.logic.forecasting import train_and_predict_all

class Command(BaseCommand):
    help = 'Ejecuta el pipeline de Machine Learning (XGBoost + SHAP XAI) para servidores y máquinas virtuales en SentinelNexus.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--steps',
            type=int,
            default=24,
            help='Número de horas a futuro a predecir (default: 24).'
        )

    def handle(self, *args, **options):
        steps = options['steps']
        self.stdout.write(self.style.SUCCESS(f"Iniciando entrenamiento y predicción XGBoost + SHAP para {steps} horas..."))
        
        try:
            train_and_predict_all(steps=steps)
            self.stdout.write(self.style.SUCCESS("Pipeline completado exitosamente."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error durante la ejecución del pipeline: {str(e)}"))
