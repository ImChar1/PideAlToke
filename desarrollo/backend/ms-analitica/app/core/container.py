# Instancia unica de la analitica para el proceso: la escriben los consumidores Kafka (hilos) y la
# leen los endpoints. Vive aqui para que ambos extremos compartan EL MISMO estado.

from app.domain.services.analitica_service import AnaliticaService

analitica = AnaliticaService()
