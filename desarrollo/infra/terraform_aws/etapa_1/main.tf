# Creamos VPC, Subredes públicas y tablas de ruteo con salida internet.

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

# VPC
resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr
  enable_dns_hostnames = true
  tags = { Name = "vpc-pidealtoke"}
}

# Internet Gateway para tráfico público
resource "aws_internet_gateway" "gw" {
    vpc_id = aws_vpc.main.id
}

# Subred Pública para el frontend
resource "aws_subnet" "public" {
  vpc_id = aws_vpc.main.id
  cidr_block = var.public_subnet_cidr
  map_public_ip_on_launch = true
  availability_zone = "${var.aws_region}a"
  tags = { Name = "public-subnet" }
}

# Subred Privada para el backend y la BD
resource "aws_subnet" "private" {
  vpc_id = aws_vpc.main.id
  cidr_block = var.private_subnet_cidr
  availability_zone = "${var.aws_region}a"
  tags = { Name = "private-subnet" }
}

# NAT Gateway para que el backend y la DB descarguen imágenes Docker de Internet
resource "aws_eip" "nat_eip" {
  domain = "vpc"
}

resource "aws_nat_gateway" "nat" {
  allocation_id = aws_eip.nat_eip.id
  subnet_id = aws_subnet.public.id
  tags = { Name = "nat-gateway" }
}

# Tabla de Enrutamiento Pública
resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
}

resource "aws_route_table_association" "public_assoc" {
  subnet_id = aws_subnet.public.id
  route_table_id = aws_route_table.public_rt.id
}

# Tabla de Enrutamiento Privada
resource "aws_route_table" "private_rt" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat.id
  }
}

resource "aws_route_table_association" "private_assoc" {
  subnet_id = aws_subnet.private.id
  route_table_id = aws_route_table.private_rt.id
}