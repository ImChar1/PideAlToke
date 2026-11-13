# Fake en memoria del KafkaAdminPort: permite probar el servicio y el router sin cluster.

from typing import Dict, List

from app.domain.ports.kafka_admin_port import (
    GrupoNoEncontradoError,
    KafkaAdminPort,
    TopicoNoEncontradoError,
    TopicoYaExisteError,
)


class FakeKafkaAdmin(KafkaAdminPort):
    def __init__(self, brokers: int = 3):
        self.brokers = brokers
        self.topicos: Dict[str, dict] = {
            "__consumer_offsets": {"partitions": 50, "replication_factor": 3, "config": {}},
        }
        self.grupos: Dict[str, dict] = {}
        self.llamadas: List[tuple] = []

    def cantidad_brokers(self):
        return self.brokers

    def listar_topicos(self):
        return [
            {"name": n, "partitions": t["partitions"], "replication_factor": t["replication_factor"]}
            for n, t in self.topicos.items()
        ]

    def obtener_topico(self, nombre):
        if nombre not in self.topicos:
            raise TopicoNoEncontradoError(f"El topico '{nombre}' no existe")
        t = self.topicos[nombre]
        return {
            "name": nombre,
            "partitions": t["partitions"],
            "replication_factor": t["replication_factor"],
            "particiones": [
                {"id": i, "leader": 1, "replicas": [1, 2, 3][: t["replication_factor"]], "isr": [1, 2, 3][: t["replication_factor"]]}
                for i in range(t["partitions"])
            ],
            "config": dict(t["config"]),
            "config_personalizada": sorted(t["config"]),
        }

    def crear_topico(self, nombre, particiones, factor_replicacion, config):
        if nombre in self.topicos:
            raise TopicoYaExisteError(f"El topico ya existe ({nombre})")
        self.llamadas.append(("crear", nombre, particiones, factor_replicacion, dict(config)))
        self.topicos[nombre] = {"partitions": particiones, "replication_factor": factor_replicacion, "config": dict(config)}

    def actualizar_config(self, nombre, config):
        self.llamadas.append(("config", nombre, dict(config)))
        self.topicos[nombre]["config"].update(config)

    def aumentar_particiones(self, nombre, total):
        self.llamadas.append(("particiones", nombre, total))
        self.topicos[nombre]["partitions"] = total

    def eliminar_topico(self, nombre):
        self.llamadas.append(("eliminar", nombre))
        del self.topicos[nombre]

    def listar_grupos(self):
        return [{"group_id": g, "state": d["state"]} for g, d in self.grupos.items()]

    def describir_grupo(self, group_id):
        if group_id not in self.grupos:
            raise GrupoNoEncontradoError(f"El consumer group '{group_id}' no existe")
        d = self.grupos[group_id]
        return {"group_id": group_id, "state": d["state"], "partition_assignor": "range", "members": d.get("members", [])}

    def lag_grupo(self, group_id):
        self.describir_grupo(group_id)
        parts = self.grupos[group_id].get("lag", [])
        return {"group_id": group_id, "total_lag": sum(p["lag"] for p in parts), "partitions": parts}
