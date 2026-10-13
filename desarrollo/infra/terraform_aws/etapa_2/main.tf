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

# Contrasena de BD distinta por microservicio, derivada de db_password (secreto de CI):
# no hace falta crear 4 secretos nuevos y ningun servicio usa la clave de root.
# Solo hex (0-9a-f): segura dentro de URLs de conexion y de scripts de shell.
locals {
  db_pass = {
    for servicio in ["usuarios", "catalogo", "inventario", "pedidos"] :
    servicio => substr(sha256("${var.db_password}:${servicio}"), 0, 32)
  }
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
  name_prefix   = "frontend-sg"
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

# NOTA DE SEGURIDAD (backend): este API Gateway es un HTTP API SIN VPC Link, asi que llega al
# backend por su IP publica y un Security Group no puede limitar el origen a "API Gateway":
# estos puertos quedan abiertos a Internet. Controles compensatorios:
#   - cada microservicio valida el JWT de Entra ID (firma, issuer y audience), no confia en el gateway;
#   - los endpoints internos de stock (reservar/liberar/confirmar-salida) exigen X-Internal-Key.
# Para cerrarlos de verdad: mover el backend a la subred privada y usar un VPC Link con un
# NLB/ALB interno (si la cuenta lo permite; en AWS Academy Learner Lab suele estar restringido).
resource "aws_security_group" "sg_backend" {
  name_prefix   = "backend-sg"
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
  name_prefix   = "mariadb-sg"
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
  associate_public_ip_address = true
  vpc_security_group_ids = [aws_security_group.sg_frontend.id]
  iam_instance_profile = "LabInstanceProfile"

  tags = {
    Name = "frontend-ec2"
  }

  user_data = <<-EOF
    #!/bin/bash
    sudo dnf update -y
    sudo dnf install -y docker aws-cli
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker ec2-user

    aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com

    docker pull ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_frontend_repo}:latest
    docker run -d -p 80:80 -p 443:443 --name frontend-container ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_frontend_repo}:latest
EOF
}

resource "aws_instance" "ec2_backend" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = "t2.micro"
  subnet_id                   = var.public_subnet_id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.sg_backend.id]
  iam_instance_profile = "LabInstanceProfile"

  tags = {
    Name = "backend-ec2"
  }

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
          DATABASE_URL: mysql+pymysql://svc_usuarios:${local.db_pass.usuarios}@${aws_instance.ec2_db.private_ip}:3306/usuarios_db
          AZURE_TENANT_ID: ${var.azure_tenant_id}
          AZURE_CLIENT_ID: ${var.azure_client_id}
        restart: always

      ms-catalogo:
        image: ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_backend_repo}:ms-catalogo
        ports:
          - "8002:8000"
        environment:
          DATABASE_URL: mysql+pymysql://svc_catalogo:${local.db_pass.catalogo}@${aws_instance.ec2_db.private_ip}:3306/catalogo_db
          AZURE_TENANT_ID: ${var.azure_tenant_id}
          AZURE_CLIENT_ID: ${var.azure_client_id}
        restart: always

      ms-inventario:
        image: ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_backend_repo}:ms-inventario
        ports:
          - "8003:8000"
        environment:
          DATABASE_URL: mysql+pymysql://svc_inventario:${local.db_pass.inventario}@${aws_instance.ec2_db.private_ip}:3306/inventario_db
          AZURE_TENANT_ID: ${var.azure_tenant_id}
          AZURE_CLIENT_ID: ${var.azure_client_id}
          INTERNAL_API_KEY: ${var.internal_api_key}
        restart: always

      ms-pedidos:
        image: ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_backend_repo}:ms-pedidos
        ports:
          - "8004:8000"
        environment:
          DATABASE_URL: mysql+pymysql://svc_pedidos:${local.db_pass.pedidos}@${aws_instance.ec2_db.private_ip}:3306/pedidos_db
          AZURE_TENANT_ID: ${var.azure_tenant_id}
          AZURE_CLIENT_ID: ${var.azure_client_id}
          INVENTARIO_SERVICE_URL: http://ms-inventario:8000
          CATALOGO_SERVICE_URL: http://ms-catalogo:8000
          INTERNAL_API_KEY: ${var.internal_api_key}
        depends_on:
          - ms-inventario
          - ms-catalogo
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
  iam_instance_profile = "LabInstanceProfile"

  tags = {
    Name = "db-ec2"
  }

  user_data = <<-EOF
    #!/bin/bash
    sudo dnf update -y
    sudo dnf install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker ec2-user

    mkdir -p /var/lib/mariadb_data
    mkdir -p /home/ec2-user/init-db

    # El esquema, el seed y el script de usuarios se leen de /init-db (UNICA fuente de verdad,
    # la misma que usa docker compose en local): antes estaban copiados aqui y ya divergian.
    cat << 'SQL_EOF' > /home/ec2-user/init-db/init-01.sql
    ${file("${path.module}/../../../init-db/init-01.sql")}
    SQL_EOF

    cat << 'SQL_EOF' > /home/ec2-user/init-db/init-02-seed.sql
    ${file("${path.module}/../../../init-db/init-02-seed.sql")}
    SQL_EOF

    cat << 'SH_EOF' > /home/ec2-user/init-db/init-03-users.sh
    ${file("${path.module}/../../../init-db/init-03-users.sh")}
    SH_EOF
    chmod +x /home/ec2-user/init-db/init-03-users.sh

    docker run -d \
      --name pidealtoke-db \
      -p 3306:3306 \
      -v /var/lib/mariadb_data:/var/lib/mysql \
      -v /home/ec2-user/init-db:/docker-entrypoint-initdb.d \
      -e MYSQL_ROOT_PASSWORD=${var.db_password} \
      -e DB_PASS_USUARIOS=${local.db_pass.usuarios} \
      -e DB_PASS_CATALOGO=${local.db_pass.catalogo} \
      -e DB_PASS_INVENTARIO=${local.db_pass.inventario} \
      -e DB_PASS_PEDIDOS=${local.db_pass.pedidos} \
      --restart always \
      mariadb:11.2
EOF
}

# 3. API GATEWAY HTTP, INTEGRACIONES Y RUTAS (SIN VPC LINK)

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

resource "aws_apigatewayv2_authorizer" "jwt_auth" {
  api_id           = aws_apigatewayv2_api.http_api.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "azure-entra-authorizer"

  jwt_configuration {
    issuer   = "https://login.microsoftonline.com/${var.azure_tenant_id}/v2.0"
    # Un access token v2 trae aud = <client id>; uno v1 o con identifier URI trae api://<client id>.
    # El backend acepta ambos, asi que el gateway tambien (antes rechazaba los tokens con api://).
    audience = [var.azure_client_id, "api://${var.azure_client_id}"]
  }
}

resource "aws_apigatewayv2_integration" "usuarios_integration" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8001/api/v1/users/{proxy}"
  connection_type     = "INTERNET"
}

resource "aws_apigatewayv2_integration" "usuarios_integration_base" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8001/api/v1/users"
  connection_type     = "INTERNET"
}

resource "aws_apigatewayv2_integration" "catalogo_integration" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8002/api/v1/productos/{proxy}"
  connection_type     = "INTERNET"
}

resource "aws_apigatewayv2_integration" "catalogo_integration_base" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8002/api/v1/productos"
  connection_type     = "INTERNET"
}

resource "aws_apigatewayv2_integration" "inventario_integration" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8003/api/v1/inventario/{proxy}"
  connection_type     = "INTERNET"
}

resource "aws_apigatewayv2_integration" "inventario_integration_base" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8003/api/v1/inventario"
  connection_type     = "INTERNET"
}

resource "aws_apigatewayv2_integration" "pedidos_integration" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8004/api/v1/pedidos/{proxy}"
  connection_type     = "INTERNET"
}

resource "aws_apigatewayv2_integration" "pedidos_integration_base" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8004/api/v1/pedidos"
  connection_type     = "INTERNET"
}

# Cada microservicio necesita dos rutas: una para el path base ("/api/v1/productos")
# y otra con {proxy+} para subrutas ("/api/v1/productos/5", etc.), porque
# {proxy+} en API Gateway exige al menos un segmento adicional.

resource "aws_apigatewayv2_route" "route_usuarios_base" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/users"
  target             = "integrations/${aws_apigatewayv2_integration.usuarios_integration_base.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_usuarios" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/users/{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.usuarios_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_catalogo_base" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/productos"
  target             = "integrations/${aws_apigatewayv2_integration.catalogo_integration_base.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_catalogo" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/productos/{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.catalogo_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_inventario_base" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/inventario"
  target             = "integrations/${aws_apigatewayv2_integration.inventario_integration_base.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_inventario" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/inventario/{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.inventario_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_pedidos_base" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/pedidos"
  target             = "integrations/${aws_apigatewayv2_integration.pedidos_integration_base.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_pedidos" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/pedidos/{proxy+}"
  target             = "integrations/${aws_apigatewayv2_integration.pedidos_integration.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt_auth.id
}

resource "aws_apigatewayv2_route" "route_usuarios_base_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/users"
  target    = "integrations/${aws_apigatewayv2_integration.usuarios_integration_base.id}"
}

resource "aws_apigatewayv2_route" "route_usuarios_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/users/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.usuarios_integration.id}"
}

resource "aws_apigatewayv2_route" "route_catalogo_base_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/productos"
  target    = "integrations/${aws_apigatewayv2_integration.catalogo_integration_base.id}"
}

resource "aws_apigatewayv2_route" "route_catalogo_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/productos/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.catalogo_integration.id}"
}

resource "aws_apigatewayv2_route" "route_inventario_base_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/inventario"
  target    = "integrations/${aws_apigatewayv2_integration.inventario_integration_base.id}"
}

resource "aws_apigatewayv2_route" "route_inventario_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/inventario/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.inventario_integration.id}"
}

resource "aws_apigatewayv2_route" "route_pedidos_base_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/pedidos"
  target    = "integrations/${aws_apigatewayv2_integration.pedidos_integration_base.id}"
}

resource "aws_apigatewayv2_route" "route_pedidos_options" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "OPTIONS /api/v1/pedidos/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.pedidos_integration.id}"
}

resource "aws_apigatewayv2_stage" "dev_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "Desarrollo"
  auto_deploy = true
}