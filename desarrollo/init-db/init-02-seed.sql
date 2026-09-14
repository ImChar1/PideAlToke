USE catalogo_db;

INSERT INTO productos (sku, nombre, descripcion, precio, categoria, activo) VALUES
('PROD-HAMB-001', 'Hamburguesa Completa', 'Doble carne, queso cheddar, tocino y salsa especial', 6990.00, 'Comida Rapida', 1),
('PROD-HAMB-002', 'Hamburguesa Vegana', 'Medallón de garbanzos, palta, tomate y mayonesa vegana', 7490.00, 'Comida Rapida', 1),
('PROD-PIZZ-001', 'Pizza Pepperoni Familiar', 'Masa artesanal, salsa de tomate, queso mozzarella y pepperoni', 11990.00, 'Pizzas', 1),
('PROD-PIZZ-002', 'Pizza Napolitana Individual', 'Salsa de tomate, queso mozzarella, tomate fresco y orégano', 6490.00, 'Pizzas', 1),
('PROD-PIZZ-003', 'Pizza Cuatro Quesos Mediana', 'Mozzarella, gouda, queso azul y parmesano sobre salsa blanca', 9990.00, 'Pizzas', 1),
('PROD-BEB-001', 'Bebida Limo 1.5L', 'Bebida gaseosa sabor limón', 2200.00, 'Bebidas', 1),
('PROD-BEB-002', 'Jugo Natural Naranja 500ml', 'Jugo de naranja recién exprimido sin azúcar añadida', 2800.00, 'Bebidas', 1),
('PROD-BEB-003', 'Cerveza Artesanal IPA 330ml', 'Cerveza artesanal de amargor moderado y notas cítricas', 3500.00, 'Bebidas', 1),
('PROD-PAP-001', 'Papas Fritas Grandes', 'Papas corte tradicional crujientes con sal marina', 3490.00, 'Acompañamientos', 1),
('PROD-PAP-002', 'Papas Supremas', 'Papas fritas cubiertas con salsa de queso cheddar y tocino crujiente', 4990.00, 'Acompañamientos', 1),
('PROD-ACOM-001', 'Empanadas de Queso (3 uds)', 'Empanadas fritas rellenas de queso mozzarella derretido', 2990.00, 'Acompañamientos', 1),
('PROD-ACOM-002', 'Aros de Cebolla', 'Aros de cebolla empanizados y crujientes con salsa BBQ', 3200.00, 'Acompañamientos', 1),
('PROD-SAND-001', 'Churrasco Italiano', 'Lomo de vacuno, abundante palta, tomate y mayonesa casera', 6200.00, 'Sandwiches', 1),
('PROD-SAND-002', 'Lomo Luco', 'Lomo de vacuno a la plancha con queso mantecoso derretido', 5900.00, 'Sandwiches', 1),
('PROD-SAND-003', 'Club Sandwich Pollo', 'Pechuga de pollo, lechuga, tomate, huevo duro, tocino y mayo', 6500.00, 'Sandwiches', 1),
('PROD-POS-001', 'Brownie con Helado', 'Brownie caliente de chocolate con una bola de helado de vainilla', 3800.00, 'Postres', 1),
('PROD-POS-002', 'Cheesecake de Frutilla', 'Pastel de queso crema sobre base de galleta con mermelada de frutilla', 3900.00, 'Postres', 1),
('PROD-POS-003', 'Churros con Dulce de Leche', '6 churros crujientes espolvoreados con azúcar y canela', 2990.00, 'Postres', 1),
('PROD-PROM-001', 'Combo Pareja Burger', '2 Hamburguesas completas + 1 Papa Frita Grande + 2 Bebidas 500ml', 15990.00, 'Promociones', 1),
('PROD-PROM-002', 'Pack Pizza & Acompañamiento', '1 Pizza Familiar a elección + 1 Aros de Cebolla + 1 Bebida 1.5L', 18990.00, 'Promociones', 1);