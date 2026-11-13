output "frontend_public_ip" {
  description = "IP Pública del Frontend para acceder desde el navegador"
  value       = aws_instance.ec2_frontend.public_ip
}

output "backend_public_ip" {
  description = "IP Pública del Backend para pruebas directas o diagnóstico"
  value       = aws_instance.ec2_backend.public_ip
}

output "db_private_ip" {
  description = "IP Privada de MariaDB para conectar el Backend"
  value       = aws_instance.ec2_db.private_ip
}

output "api_gateway_endpoint" {
  description = "URL base del API Gateway invocable desde Angular"
  value       = aws_apigatewayv2_stage.dev_stage.invoke_url
}
output "messaging_public_ip" {
  description = "IP publica de la EC2 de mensajeria (consolas web de RabbitMQ y Kafka-UI)"
  value       = aws_instance.ec2_mensajeria.public_ip
}

output "messaging_private_ip" {
  description = "IP privada de la EC2 de mensajeria (la usa el backend para RabbitMQ y Kafka)"
  value       = aws_instance.ec2_mensajeria.private_ip
}

output "rabbitmq_ui_url" {
  description = "Consola web de RabbitMQ, nodo 1 (el nodo 2 esta en el puerto 15673)"
  value       = "http://${aws_instance.ec2_mensajeria.public_ip}:15672"
}

output "kafka_ui_url" {
  description = "Consola web de Kafka-UI"
  value       = "http://${aws_instance.ec2_mensajeria.public_ip}:8090"
}
