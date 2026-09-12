terraform {
  required_providers {
    aws = {
        source = "hashicorp/aws"
        version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Script de instalación estándar de Docker
locals {
    docker_setup = <<-EOF
        #!/bin/bash
        sudo amazon-linux-extras install docker -y || sudo yum install -y docker
        sudo service docker start
        sudo usermod -a -G docker ec2-user
    EOF
}

# 1. SECURITY GROUPS

# SG Frontend - Subred Pública para Acceso Web
resource "aws_security_group" "sg_frontend" {
    name = "sg-frontend"
    vpc_id = var.vpc_id

    ingress = {
        from_port = 80
        to_port = 80
        protocol = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    ingress {
        from_port = 443
        to_port = 433
        protocol = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }

    egress {
        from_port = 0
        to_port = 0
        protocol = "-1"
        cidr_blocks = ["0.0.0.0/0"]
    }
}

# SG Backend - Subred Privada que recibe peticiones del Gateway/Frontend
resource "aws_security_group" "sg_backend" {
    name = "sg-backend"
    vpc_id = var.vpc_id

    ingress = {
        from_port= 8080
        to_port = 8080
        protocol = "tcp"
        cidr_blocks = ["0.0.0.0/0"]
    }
    
    egress {
        from_port = 0
        to_port = 0
        protocol = "-1"
        cidr_blocks = ["0.0.0.0/0"]
    }
}

# SG Base de Datos - Subred Privada para Aceptar tráfico solo desde el Backend
resource "aws_security_group" "sg_db" {
  name = "sg-mariadb"
  vpc_id = var.vpc_id

  ingress = {
    from_port = 3306
    to_port= 3306
    protocol = "tcp"
    aws_security_group = [aws_security_group.sg_backend.id]
  }

  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 2. INSTANCIAS EC2 CON DOCKER

# EC2 Frontend
resource "aws_instance" "ec2_frontend" {
  ami = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"
  subnet_id = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.sg_frontend.id]
  user_data = local.docker_setup

  tags = { Name = "ec2-frontend-docker" }
}

# EC2 Backend
resource "aws_instance" "ec2_backend" {
  ami = "ami-0c55b159cbfafe1f0"
  instance_type = "t2.micro"
  subnet_id = var.private_subnet_id
  vpc_security_group_ids = [aws_security_group.sg_backend.id]
  user_data = local.docker_setup

  tags = { Name = "ec2-backend-docker" }
}

# EC2 MariaDB
resource "aws_instance" "ec2_db" {
  ami = "ami-0c55b159cbfafe10"
  instance_type = "t2.micro"
  subnet_id = var.private_subnet_id
  vpc_security_group_ids = [aws_security_group.sg_db.id]
  user_data = local.docker_setup
}

# 3. API GATEWAY HTTP - CORS y AZ Entra ID JWT

resource "aws_apigatewayv2_api" "http_api" {
  name = "BackendGateway"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["Authorization", "Content-Type"]
    max_age = 300
  }
}

resource "aws_apigateway2v_authorizer" "jwt_auth" {
  api_id = aws_apigatewayv2_api.http-api.id
  authorizer_type = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name = "azure-entra-authorizer"

  jwt_configuration {
    issuer = "https://${var.azure_tenant_name}.cimlogin.com/${var.azure_tenant_id}/v2.0/"
    audience = [var.azure_client_id]
  }
}

resource "aws_apigatewayv2_integration" "backend_integration" {
  api_id = aws_apigatewayv2_api.http_api.id
  integration_type = "HTTP_PROXY"
  integration_uri = "http://${aws_instance.ec2_backend.private_id}:8080/api/datos"
  integration_method = "GET"
}

resource "aws_apigatewayv2_route" "datos_route" {
    api_id = aws_apigatewayv2_api.http_api.id
    route_key = "GET /datos"
    target = "integrations/${aws_apigatewayv2_integration.backend_integration.id}"
    authorization_type = "JWT"
    authorizer_id = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_stage" "dev_stage" {
  api_id = aws_apigatewayv2_api.http_api.id
  name = "Desarrollo"
  auto_deploy = true
}