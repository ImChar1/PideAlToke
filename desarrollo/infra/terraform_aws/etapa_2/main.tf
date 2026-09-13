terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# 0. DATA SOURCES (AMI Dinámica)
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

# 1. SECURITY GROUPS

resource "aws_security_group" "sg_frontend" {
  name   = "sg-frontend"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "sg_backend" {
  name   = "sg-backend"
  vpc_id = var.vpc_id

  ingress {
    from_port   = 8001
    to_port     = 8004
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
    
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "sg_db" {
  name   = "sg-mariadb"
  vpc_id = var.vpc_id

  ingress {
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.sg_backend.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 2. INSTANCIAS EC2 CON DOCKER

resource "aws_instance" "ec2_frontend" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t2.micro"
  subnet_id              = var.public_subnet_id
  vpc_security_group_ids = [aws_security_group.sg_frontend.id]
  iam_instance_profile   = "LabInstanceProfile"

  user_data = <<-EOF
    #!/bin/bash
    sudo dnf update -y
    sudo dnf install -y docker aws-cli
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker ec2-user

    aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com

    docker pull ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_frontend_repo}:latest
    docker run -d -p 80:80 --name frontend-container ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_frontend_repo}:latest
EOF
}

resource "aws_instance" "ec2_backend" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t2.micro"
  subnet_id              = var.private_subnet_id
  vpc_security_group_ids = [aws_security_group.sg_backend.id]
  iam_instance_profile   = "LabInstanceProfile"

  user_data = <<-EOF
    #!/bin/bash
    sudo dnf update -y
    sudo dnf install -y docker aws-cli
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker ec2-user

    sudo mkdir -p /usr/libexec/docker/cli-plugins
    sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/libexec/docker/cli-plugins/docker-compose
    sudo chmod +x /usr/libexec/docker/cli-plugins/docker-compose

    aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com

    cat << 'DC_EOF' > /home/ec2-user/docker-compose.yml
    version: '3.8'

    services:
      ms-usuarios:
        image: ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_backend_repo}:ms-usuarios
        ports:
          - "8001:8000"
        environment:
          DATABASE_URL: mysql+pymysql://root:${var.db_password}@${aws_instance.ec2_db.private_ip}:3306/${var.db_name}
          AZURE_TENANT_ID: ${var.azure_tenant_id}
          AZURE_CLIENT_ID: ${var.azure_client_id}
        restart: always

      ms-catalogo:
        image: ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_backend_repo}:ms-catalogo
        ports:
          - "8002:8000"
        environment:
          DATABASE_URL: mysql+pymysql://root:${var.db_password}@${aws_instance.ec2_db.private_ip}:3306/${var.db_name}
        restart: always

      ms-inventario:
        image: ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_backend_repo}:ms-inventario
        ports:
          - "8003:8000"
        environment:
          DATABASE_URL: mysql+pymysql://root:${var.db_password}@${aws_instance.ec2_db.private_ip}:3306/${var.db_name}
        restart: always

      ms-pedidos:
        image: ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_backend_repo}:ms-pedidos
        ports:
          - "8004:8000"
        environment:
          DATABASE_URL: mysql+pymysql://root:${var.db_password}@${aws_instance.ec2_db.private_ip}:3306/${var.db_name}
        restart: always
    DC_EOF

    cd /home/ec2-user
    docker compose up -d
EOF
}

resource "aws_instance" "ec2_db" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = "t2.micro"
  subnet_id              = var.private_subnet_id
  vpc_security_group_ids = [aws_security_group.sg_db.id]
  iam_instance_profile   = "LabInstanceProfile"

  user_data = <<-EOF
    #!/bin/bash
    sudo dnf update -y
    sudo dnf install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker ec2-user

    mkdir -p /var/lib/mariadb_data

    docker run -d \
      --name pidealtoke-db \
      -p 3306:3306 \
      -v /var/lib/mariadb_data:/var/lib/mysql \
      -e MYSQL_ROOT_PASSWORD=${var.db_password} \
      -e MYSQL_DATABASE=${var.db_name} \
      --restart always \
      mariadb:11.2
EOF
}

# 3. API GATEWAY HTTP, VPC LINK, INTEGRACIONES Y RUTAS

resource "aws_apigatewayv2_api" "http_api" {
  name          = "BackendGateway"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["Authorization", "Content-Type"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_vpc_link" "vpc_link" {
  name               = "apigw-vpc-link"
  security_group_ids = [aws_security_group.sg_backend.id]
  subnet_ids         = [var.private_subnet_id]
}

resource "aws_apigatewayv2_authorizer" "jwt_auth" {
  api_id           = aws_apigatewayv2_api.http_api.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "azure-entra-authorizer"

  jwt_configuration {
    issuer   = "https://login.microsoftonline.com/${var.azure_tenant_id}/v2.0"
    audience = [var.azure_client_id]
  }
}

# Integraciones asociadas a la VPC Link
resource "aws_apigatewayv2_integration" "usuarios_integration" {
  api_id             = aws_apigatewayv2_api.http_api.id
  integration_type   = "HTTP_PROXY"
  integration_uri    = "http://${aws_instance.ec2_backend.private_ip}:8001/datos"
  integration_method = "GET"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.vpc_link.id
}

resource "aws_apigatewayv2_integration" "catalogo_integration" {
  api_id             = aws_apigatewayv2_api.http_api.id
  integration_type   = "HTTP_PROXY"
  integration_uri    = "http://${aws_instance.ec2_backend.private_ip}:8002/datos"
  integration_method = "GET"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.vpc_link.id
}

resource "aws_apigatewayv2_integration" "inventario_integration" {
  api_id             = aws_apigatewayv2_api.http_api.id
  integration_type   = "HTTP_PROXY"
  integration_uri    = "http://${aws_instance.ec2_backend.private_ip}:8003/datos"
  integration_method = "GET"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.vpc_link.id
}

resource "aws_apigatewayv2_integration" "pedidos_integration" {
  api_id             = aws_apigatewayv2_api.http_api.id
  integration_type   = "HTTP_PROXY"
  integration_uri    = "http://${aws_instance.ec2_backend.private_ip}:8004/datos"
  integration_method = "GET"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.vpc_link.id
}

# Rutas completas del API Gateway
resource "aws_apigatewayv2_route" "route_usuarios" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "GET /v1/usuarios"
  target             = "integrations/${aws_apigatewayv2_integration.usuarios_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_catalogo" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "GET /v1/catalogo"
  target             = "integrations/${aws_apigatewayv2_integration.catalogo_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_inventario" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "GET /v1/inventario"
  target             = "integrations/${aws_apigatewayv2_integration.inventario_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_pedidos" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "GET /v1/pedidos"
  target             = "integrations/${aws_apigatewayv2_integration.pedidos_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_stage" "dev_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "Desarrollo"
  auto_deploy = true
}