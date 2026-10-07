import { TestBed } from '@angular/core/testing';
import { CartService } from './cart.service';
import { Producto } from '../../features/catalogo/models/producto.model';

const prod = (id: number): Producto =>
  ({ id, sku: `SKU-${id}`, nombre: `P${id}`, precio: 1000, activo: true } as Producto);

describe('CartService', () => {
  let cart: CartService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    cart = TestBed.inject(CartService);
  });

  it('agrega un producto nuevo con cantidad 1', () => {
    cart.agregarProducto(prod(1));
    expect(cart.items().length).toBe(1);
    expect(cart.items()[0].cantidad).toBe(1);
  });

  it('incrementa la cantidad si el producto ya esta en el carrito', () => {
    cart.agregarProducto(prod(1));
    cart.agregarProducto(prod(1));
    expect(cart.items().length).toBe(1);
    expect(cart.items()[0].cantidad).toBe(2);
  });

  it('totalCount suma las cantidades de todos los items', () => {
    cart.agregarProducto(prod(1));
    cart.agregarProducto(prod(1));
    cart.agregarProducto(prod(2));
    expect(cart.totalCount()).toBe(3);
  });
});
