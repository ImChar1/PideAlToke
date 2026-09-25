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
    docker run -d -p 80:80 --name frontend-container ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_frontend_repo}:latest
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
          DATABASE_URL: mysql+pymysql://root:${var.db_password}@${aws_instance.ec2_db.private_ip}:3306/usuarios_db
          AZURE_TENANT_ID: ${var.azure_tenant_id}
          AZURE_CLIENT_ID: ${var.azure_client_id}
        restart: always

      ms-catalogo:
        image: ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_backend_repo}:ms-catalogo
        ports:
          - "8002:8000"
        environment:
          DATABASE_URL: mysql+pymysql://root:${var.db_password}@${aws_instance.ec2_db.private_ip}:3306/catalogo_db
          AZURE_TENANT_ID: ${var.azure_tenant_id}
          AZURE_CLIENT_ID: ${var.azure_client_id}
        restart: always

      ms-inventario:
        image: ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_backend_repo}:ms-inventario
        ports:
          - "8003:8000"
        environment:
          DATABASE_URL: mysql+pymysql://root:${var.db_password}@${aws_instance.ec2_db.private_ip}:3306/inventario_db
          AZURE_TENANT_ID: ${var.azure_tenant_id}
          AZURE_CLIENT_ID: ${var.azure_client_id}
        restart: always

      ms-pedidos:
        image: ${var.aws_account_id}.dkr.ecr.${var.aws_region}.amazonaws.com/${var.ecr_backend_repo}:ms-pedidos
        ports:
          - "8004:8000"
        environment:
          DATABASE_URL: mysql+pymysql://root:${var.db_password}@${aws_instance.ec2_db.private_ip}:3306/pedidos_db
          AZURE_TENANT_ID: ${var.azure_tenant_id}
          AZURE_CLIENT_ID: ${var.azure_client_id}
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

    cat << 'SQL_EOF' > /home/ec2-user/init-db/init-01.sql
    CREATE DATABASE IF NOT EXISTS usuarios_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    CREATE DATABASE IF NOT EXISTS pedidos_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    CREATE DATABASE IF NOT EXISTS inventario_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    CREATE DATABASE IF NOT EXISTS catalogo_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

    USE usuarios_db;
    CREATE TABLE IF NOT EXISTS usuarios (
        id INT AUTO_INCREMENT PRIMARY KEY,
        azure_oid VARCHAR(100) NOT NULL UNIQUE,
        email VARCHAR(150) UNIQUE,
        rol VARCHAR(50) NOT NULL DEFAULT 'CLIENTE',
        activo BOOLEAN DEFAULT TRUE,
        fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_usuarios_azure_oid (azure_oid)
    );

    USE pedidos_db;
    CREATE TABLE IF NOT EXISTS pedidos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        cliente_id VARCHAR(100) NOT NULL,
        monto_total DECIMAL(10, 2) NOT NULL,
        estado VARCHAR(50) NOT NULL DEFAULT 'PENDIENTE',
        items JSON NOT NULL,
        fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_pedidos_cliente_id (cliente_id)
    );

    USE inventario_db;
    CREATE TABLE IF NOT EXISTS inventario (
        id INT AUTO_INCREMENT PRIMARY KEY,
        sku VARCHAR(50) NOT NULL UNIQUE,
        cantidad_disponible INT NOT NULL DEFAULT 0,
        cantidad_reservada INT NOT NULL DEFAULT 0,
        umbral_minimo INT NULL,
        fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
        fecha_actualizacion DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_inventario_sku (sku)
    );

    USE catalogo_db;
    CREATE TABLE IF NOT EXISTS productos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        sku VARCHAR(50) NOT NULL UNIQUE,
        nombre VARCHAR(150) NOT NULL,
        descripcion VARCHAR(500) NULL,
        precio DECIMAL(10, 2) NOT NULL,
        categoria VARCHAR(100) NULL,
        imagen_url VARCHAR(300) NULL,
        activo BOOLEAN NOT NULL DEFAULT TRUE,
        fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
        fecha_actualizacion DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_productos_sku (sku),
        INDEX idx_productos_nombre (nombre),
        INDEX idx_productos_categoria (categoria)
    );
    SQL_EOF

    cat << 'SQL_EOF' > /home/ec2-user/init-db/init-02-seed.sql
    USE catalogo_db;

    INSERT INTO productos (sku, nombre, descripcion, precio, categoria, activo) VALUES
    ('PROD-HAMB-001', 'Hamburguesa Completa', 'Doble carne, queso cheddar, tocino y salsa especial', 6990.00, 'Comida Rapida', 1),
    ('PROD-HAMB-002', 'Hamburguesa Vegana', 'Medallon de garbanzos, palta, tomate y mayonesa vegana', 7490.00, 'Comida Rapida', 1),
    ('PROD-PIZZ-001', 'Pizza Pepperoni Familiar', 'Masa artesanal, salsa de tomate, queso mozzarella y pepperoni', 11990.00, 'Pizzas', 1),
    ('PROD-PIZZ-002', 'Pizza Napolitana Individual', 'Salsa de tomate, queso mozzarella, tomate fresco y oregano', 6490.00, 'Pizzas', 1),
    ('PROD-PIZZ-003', 'Pizza Cuatro Quesos Mediana', 'Mozzarella, gouda, queso azul y parmesano sobre salsa blanca', 9990.00, 'Pizzas', 1),
    ('PROD-BEB-001', 'Bebida Limo 1.5L', 'Bebida gaseosa sabor limon', 2200.00, 'Bebidas', 1),
    ('PROD-BEB-002', 'Jugo Natural Naranja 500ml', 'Jugo de naranja recien exprimido sin azucar anadida', 2800.00, 'Bebidas', 1),
    ('PROD-BEB-003', 'Cerveza Artesanal IPA 330ml', 'Cerveza artesanal de amargor moderado y notas citricas', 3500.00, 'Bebidas', 1),
    ('PROD-PAP-001', 'Papas Fritas Grandes', 'Papas corte tradicional crujientes con sal marina', 3490.00, 'Acompanamientos', 1),
    ('PROD-PAP-002', 'Papas Supremas', 'Papas fritas cubiertas con salsa de queso cheddar y tocino crujiente', 4990.00, 'Acompanamientos', 1),
    ('PROD-ACOM-001', 'Empanadas de Queso (3 uds)', 'Empanadas fritas rellenas de queso mozzarella derretido', 2990.00, 'Acompanamientos', 1),
    ('PROD-ACOM-002', 'Aros de Cebolla', 'Aros de cebolla empanizados y crujientes con salsa BBQ', 3200.00, 'Acompanamientos', 1),
    ('PROD-SAND-001', 'Churrasco Italiano', 'Lomo de vacuno, abundante palta, tomate y mayonesa casera', 6200.00, 'Sandwiches', 1),
    ('PROD-SAND-002', 'Lomo Luco', 'Lomo de vacuno a la plancha con queso mantecoso derretido', 5900.00, 'Sandwiches', 1),
    ('PROD-SAND-003', 'Club Sandwich Pollo', 'Pechuga de pollo, lechuga, tomate, huevo duro, tocino y mayo', 6500.00, 'Sandwiches', 1),
    ('PROD-POS-001', 'Brownie con Helado', 'Brownie caliente de chocolate con una bola de helado de vainilla', 3800.00, 'Postres', 1),
    ('PROD-POS-002', 'Cheesecake de Frutilla', 'Pastel de queso crema sobre base de galleta con mermelada de frutilla', 3900.00, 'Postres', 1),
    ('PROD-POS-003', 'Churros con Dulce de Leche', '6 churros crujientes espolvoreados con azucar y canela', 2990.00, 'Postres', 1),
    ('PROD-PROM-001', 'Combo Pareja Burger', '2 Hamburguesas completas + 1 Papa Frita Grande + 2 Bebidas 500ml', 15990.00, 'Promociones', 1),
    ('PROD-PROM-002', 'Pack Pizza & Acompanamiento', '1 Pizza Familiar a eleccion + 1 Aros de Cebolla + 1 Bebida 1.5L', 18990.00, 'Promociones', 1);
    SQL_EOF

    docker run -d \
      --name pidealtoke-db \
      -p 3306:3306 \
      -v /var/lib/mariadb_data:/var/lib/mysql \
      -v /home/ec2-user/init-db:/docker-entrypoint-initdb.d \
      -e MYSQL_ROOT_PASSWORD=${var.db_password} \
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
    audience = [var.azure_client_id]
  }
}

resource "aws_apigatewayv2_integration" "usuarios_integration" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8001/api/v1/users/{proxy}"
  connection_type     = "INTERNET"
}

resource "aws_apigatewayv2_integration" "catalogo_integration" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8002/api/v1/productos/{proxy}"
  connection_type     = "INTERNET"
}

resource "aws_apigatewayv2_integration" "inventario_integration" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8003/api/v1/inventario/{proxy}"
  connection_type     = "INTERNET"
}

resource "aws_apigatewayv2_integration" "pedidos_integration" {
  api_id              = aws_apigatewayv2_api.http_api.id
  integration_type    = "HTTP_PROXY"
  integration_method  = "ANY"
  integration_uri     = "http://${aws_instance.ec2_backend.public_ip}:8004/api/v1/pedidos/{proxy}"
  connection_type     = "INTERNET"
}

# Cada microservicio necesita dos rutas: una para el path base ("/api/v1/productos")
# y otra con {proxy+} para subrutas ("/api/v1/productos/5", etc.), porque
# {proxy+} en API Gateway exige al menos un segmento adicional.

resource "aws_apigatewayv2_route" "route_usuarios_base" {
  api_id             = aws_apigatewayv2_api.http_api.id
  route_key          = "ANY /api/v1/users"
  target             = "integrations/${aws_apigatewayv2_integration.usuarios_integration.id}"
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
  target             = "integrations/${aws_apigatewayv2_integration.catalogo_integration.id}"
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
  target             = "integrations/${aws_apigatewayv2_integration.inventario_integration.id}"
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
  target             = "integrations/${aws_apigatewayv2_integration.pedidos_integration.id}"
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

resource "aws_apigatewayv2_stage" "dev_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "Desarrollo"
  auto_deploy = true
}