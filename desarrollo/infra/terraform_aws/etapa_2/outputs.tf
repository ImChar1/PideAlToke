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