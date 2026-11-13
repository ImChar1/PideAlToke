# Instancia unica de las notificaciones para el proceso: la escriben los consumidores RabbitMQ
# (hilos) y la leen los endpoints. Vive aqui para que ambos extremos compartan EL MISMO estado.

from app.domain.services.notificacion_service import NotificacionService

notificaciones = NotificacionService()
