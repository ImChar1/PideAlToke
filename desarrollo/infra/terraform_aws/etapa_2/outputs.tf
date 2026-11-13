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


# --- Salidas para operar y demostrar Kafka (EP3). Solo lectura: no cambian la infraestructura ---

output "backend_instance_id" {
  description = "ID de la EC2 del backend (para SSM: port-forward a ms-kafka-admin y ms-mensajeria)"
  value       = aws_instance.ec2_backend.id
}

output "messaging_instance_id" {
  description = "ID de la EC2 de mensajeria (log de arranque: /var/log/mensajeria-setup.log)"
  value       = aws_instance.ec2_mensajeria.id
}

output "kafka_bootstrap_servers" {
  description = "Brokers de Kafka (IP privada, solo alcanzables desde el backend): el valor de KAFKA_BOOTSTRAP_SERVERS"
  value       = "${aws_instance.ec2_mensajeria.private_ip}:9092,${aws_instance.ec2_mensajeria.private_ip}:9093,${aws_instance.ec2_mensajeria.private_ip}:9094"
}

output "ssm_port_forward_kafka_admin" {
  description = "Comando (Git Bash) que expone ms-kafka-admin en http://localhost:8006 (requiere el plugin Session Manager). Llamar con un JWT con rol ADMIN."
  value       = "aws ssm start-session --target ${aws_instance.ec2_backend.id} --document-name AWS-StartPortForwardingSession --parameters '{\"portNumber\":[\"8006\"],\"localPortNumber\":[\"8006\"]}' --region ${var.aws_region}"
}

output "ssm_port_forward_mensajeria_admin" {
  description = "Comando (Git Bash) que expone ms-mensajeria (administrador de RabbitMQ) en http://localhost:8005. Requiere un JWT con rol ADMIN."
  value       = "aws ssm start-session --target ${aws_instance.ec2_backend.id} --document-name AWS-StartPortForwardingSession --parameters '{\"portNumber\":[\"8005\"],\"localPortNumber\":[\"8005\"]}' --region ${var.aws_region}"
}
