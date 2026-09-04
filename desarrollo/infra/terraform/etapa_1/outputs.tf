output "vpc_id" {
  description = "ID de la VPC principal"
  value = aws_vpc.main.id
}

output "public_subnet_id" {
  description = "ID de la subred pública"
  value = aws_subnet.public.id
}

output "private_subnet_id" {
  description = "ID de la subred privada"
  value = aws_subnet.private.id
}