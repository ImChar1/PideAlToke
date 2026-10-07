# Pruebas contra el repositorio REAL (SQLAlchemy + SQLite temporal) con hilos concurrentes.
# Demuestran que reservar/confirmar son atomicos: nunca se vende mas stock del que hay.

import uuid
from concurrent.futures import ThreadPoolExecutor

from app.infrastructure.db.session import Base, SessionLocal, engine
from app.infrastructure.repositories.inventario_repository import InventarioRepository
from app.domain.services.inventario_service import InventarioService, StockInsuficienteError

Base.metadata.create_all(bind=engine)


def _crear(stock: int) -> str:
    sku = f"RACE-{uuid.uuid4().hex[:10]}"
    with SessionLocal() as db:
        InventarioRepository(db).crear({"sku": sku, "cantidad_disponible": stock, "cantidad_reservada": 0})
    return sku


def _leer(sku: str):
    with SessionLocal() as db:
        return InventarioRepository(db).obtener_por_sku(sku)


def _en_paralelo(fn, n_tareas: int, hilos: int = 16):
    with ThreadPoolExecutor(max_workers=hilos) as ex:
        return list(ex.map(fn, range(n_tareas)))


def test_reservas_concurrentes_nunca_superan_el_stock():
    sku = _crear(stock=10)

    def intento(_):
        with SessionLocal() as db:
            try:
                InventarioService(InventarioRepository(db)).reservar_stock(sku, 1)
                return True
            except StockInsuficienteError:
                return False

    resultados = _en_paralelo(intento, n_tareas=40)

    assert sum(resultados) == 10          # exactamente el stock disponible
    assert _leer(sku).cantidad_reservada == 10


def test_confirmar_salida_concurrente_no_deja_negativos():
    sku = _crear(stock=10)
    with SessionLocal() as db:
        InventarioService(InventarioRepository(db)).reservar_stock(sku, 5)

    def intento(_):
        with SessionLocal() as db:
            try:
                InventarioService(InventarioRepository(db)).confirmar_salida(sku, 1)
                return True
            except StockInsuficienteError:
                return False

    resultados = _en_paralelo(intento, n_tareas=20)

    registro = _leer(sku)
    assert sum(resultados) == 5
    assert registro.cantidad_reservada == 0
    assert registro.cantidad_disponible == 5


def test_reponer_concurrente_no_pierde_actualizaciones():
    sku = _crear(stock=0)

    def intento(_):
        with SessionLocal() as db:
            InventarioService(InventarioRepository(db)).reponer_stock(sku, 1)

    _en_paralelo(intento, n_tareas=30)

    assert _leer(sku).cantidad_disponible == 30


def test_liberar_nunca_baja_la_reserva_de_cero():
    sku = _crear(stock=10)
    with SessionLocal() as db:
        svc = InventarioService(InventarioRepository(db))
        svc.reservar_stock(sku, 3)
        assert svc.liberar_stock(sku, 100).cantidad_reservada == 0
