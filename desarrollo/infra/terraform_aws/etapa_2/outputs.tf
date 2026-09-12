output "frontend_public_ip" {
  description = "IP Pública del Frontend para acceder desde el navegador"
  value = aws_instance.ec2_frontend.public_ip
}

output "backend_private_ip" {
  description = "IP Privada del Backend"
  value = aws_instance.ec2_backend.private_ip
}

output "db_private_id" {
  description = "IP Privada de MariaDB para conectar el Backend"
  value = aws_instance.ec2_db.private_id
}

output "api_gateway_endpoint" {
  description = "URL invocable del API Gateway protegido con Entra ID"
  value = "${aws_apigatewayv2_stage.dev_stage.invoke_url}/datos"
}