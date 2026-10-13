# DTOs con Pydantic para el API administrativo de RabbitMQ.
# Toda la validacion de entrada vive aqui: nombres vacios o con caracteres raros, tipos de exchange
# invalidos y combinaciones de argumentos imposibles se rechazan con 422 ANTES de tocar el broker.

from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

# Letras, numeros y . _ - : (suficiente para nombres como "inventario.pedidos.dlq").
# Excluye espacios, "/", comillas y caracteres de control.
NOMBRE_PATRON = r"^[A-Za-z0-9_.:\-]+$"
NOMBRE_MAX = 255  # limite de AMQP para nombres de cola / exchange / routing key


def _no_reservado(valor: str) -> str:
    # RabbitMQ reserva el prefijo "amq." para sus objetos internos y rechaza declararlos desde un cliente.
    if valor.lower().startswith("amq."):
        raise ValueError("Los nombres que empiezan con 'amq.' estan reservados por RabbitMQ")
    return valor


# Nombre de un objeto que se DECLARA (cola / exchange nuevos): no puede usar el prefijo reservado.
NombreRabbit = Annotated[
    str,
    StringConstraints(min_length=1, max_length=NOMBRE_MAX, pattern=NOMBRE_PATRON),
    AfterValidator(_no_reservado),
]

# Nombre de un objeto que solo se REFERENCIA (bindings, DLX, rutas de la URL): aqui "amq.topic",
# "amq.direct", etc. si son validos porque son exchanges que ya existen en todo broker.
NombreReferencia = Annotated[
    str,
    StringConstraints(min_length=1, max_length=NOMBRE_MAX, pattern=NOMBRE_PATRON),
]

# La routing key admite patrones de topic ("pedido.*", "#"), por eso es mas permisiva que un nombre.
RoutingKey = Annotated[str, StringConstraints(max_length=NOMBRE_MAX, pattern=r"^[A-Za-z0-9_.:\-*#]*$")]

TipoExchange = Literal["direct", "topic", "fanout", "headers"]
TipoCola = Literal["classic", "quorum"]


class _SchemaEstricto(BaseModel):
    # extra="forbid": un campo mal escrito (p. ej. "durabel") falla con 422 en vez de ignorarse en silencio.
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------ entrada

class ColaCrearSchema(_SchemaEstricto):
    name: NombreRabbit
    durable: bool = True
    auto_delete: bool = False
    queue_type: TipoCola = "classic"
    message_ttl_ms: Optional[int] = Field(None, ge=0, le=4294967295, description="x-message-ttl en milisegundos")
    max_length: Optional[int] = Field(None, ge=1, description="x-max-length (mensajes)")
    dead_letter_exchange: Optional[NombreReferencia] = Field(None, description="x-dead-letter-exchange")
    dead_letter_routing_key: Optional[RoutingKey] = Field(None, description="x-dead-letter-routing-key")

    @model_validator(mode="after")
    def _validar_combinaciones(self):
        # Sin DLX, una routing key de dead-letter no hace nada: casi seguro es un error del cliente.
        if self.dead_letter_routing_key and not self.dead_letter_exchange:
            raise ValueError("dead_letter_routing_key requiere dead_letter_exchange")
        # Las colas quorum deben ser durables y no pueden ser auto-delete (RabbitMQ las rechaza).
        if self.queue_type == "quorum" and (not self.durable or self.auto_delete):
            raise ValueError("Las colas quorum deben ser durable=true y auto_delete=false")
        return self


class ExchangeCrearSchema(_SchemaEstricto):
    name: NombreRabbit
    type: TipoExchange
    durable: bool = True
    auto_delete: bool = False
    internal: bool = False


class BindingCrearSchema(_SchemaEstricto):
    queue: NombreReferencia
    exchange: NombreReferencia
    # En exchanges fanout la routing key se ignora; en direct/topic es la clave o patron del binding.
    routing_key: RoutingKey = ""


# ------------------------------------------------------------------ salida

class ColaInfoSchema(BaseModel):
    name: str
    messages: int
    consumers: int


class ColaEliminadaSchema(BaseModel):
    name: str
    deleted: bool
    messages_discarded: int


class ColaPurgadaSchema(BaseModel):
    name: str
    purged_messages: int


class ExchangeInfoSchema(BaseModel):
    name: str
    type: str
    durable: bool
    auto_delete: bool
    internal: bool


class BindingInfoSchema(BaseModel):
    queue: str
    exchange: str
    routing_key: str
