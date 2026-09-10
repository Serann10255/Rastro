/* Listado de envíos con búsqueda y filtro por estado.
 *
 * El filtro por organización y por conductor lo aplica el servidor, no esta
 * pantalla: el despachador ve los de su empresa y el conductor solo los que
 * tiene asignados. Lo que se filtra aquí es únicamente presentación sobre lo
 * que el servidor ya decidió entregar.
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useEnvios } from "@/api/consultas";
import { useSesion } from "@/api/sesion";
import { mensajeDeError } from "@/componentes/notificaciones";
import {
  Aviso,
  Boton,
  Campo,
  EtiquetaEstado,
  GrupoSegmentado,
  ListaEsqueleto,
  Tarjeta,
  Vacio,
  fechaRelativa,
} from "@/componentes/ui";
import type { EnvioResumen, Estado } from "@/tipos";

type Filtro = "todos" | "activos" | "sin_asignar" | "incidencia" | "entregados";

const FILTROS: { valor: Filtro; texto: string }[] = [
  { valor: "activos", texto: "En curso" },
  { valor: "sin_asignar", texto: "Sin asignar" },
  { valor: "incidencia", texto: "Incidencia" },
  { valor: "entregados", texto: "Entregados" },
  { valor: "todos", texto: "Todos" },
];

function aplicaFiltro(envio: EnvioResumen, filtro: Filtro): boolean {
  switch (filtro) {
    case "activos":
      return envio.estado !== "ENTREGADO";
    case "sin_asignar":
      return envio.estado === "CREADO";
    case "incidencia":
      return envio.estado === "INCIDENCIA";
    case "entregados":
      return envio.estado === "ENTREGADO";
    default:
      return true;
  }
}

export function Envios() {
  const { tieneGrupo } = useSesion();
  const { data, isPending, error, refetch, isFetching } = useEnvios();
  const [filtro, setFiltro] = useState<Filtro>("activos");
  const [busqueda, setBusqueda] = useState("");

  const esConductor = tieneGrupo("conductor") && !tieneGrupo("despachador");

  const visibles = useMemo(() => {
    const termino = busqueda.trim().toLowerCase();
    return (data?.envios ?? [])
      .filter((envio) => aplicaFiltro(envio, filtro))
      .filter((envio) =>
        termino
          ? [envio.destinatario, envio.destino, envio.envio_id, envio.conductor_nombre ?? ""]
              .join(" ")
              .toLowerCase()
              .includes(termino)
          : true,
      );
  }, [data, filtro, busqueda]);

  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <h1>{esConductor ? "Mis envíos" : "Envíos"}</h1>
          {tieneGrupo("administrador", "despachador") && (
            <Link to="/envios/nuevo" className="boton">
              Registrar envío
            </Link>
          )}
        </div>
        <p className="encabezado-pagina__descripcion">
          {esConductor
            ? "Solo aparecen los envíos que le fueron asignados. El filtro lo aplica el servidor."
            : "Envíos de su organización. Los datos de otras empresas no son alcanzables desde aquí."}
        </p>
      </header>

      <Tarjeta>
        <div className="filtros">
          <Campo
            etiqueta="Buscar"
            type="search"
            placeholder="Destinatario, dirección o identificador"
            value={busqueda}
            onChange={(evento) => setBusqueda(evento.target.value)}
          />
          <GrupoSegmentado
            etiqueta="Estado"
            valor={filtro}
            opciones={FILTROS}
            onCambio={(valor) => setFiltro(valor)}
          />
          <div className="campo">
            <span className="campo__etiqueta">&nbsp;</span>
            <Boton variante="secundario" onClick={() => refetch()} cargando={isFetching}>
              Actualizar
            </Boton>
          </div>
        </div>
      </Tarjeta>

      {error && <Aviso tono="error">{mensajeDeError(error)}</Aviso>}

      {isPending ? (
        <ListaEsqueleto filas={5} />
      ) : visibles.length === 0 ? (
        <Tarjeta>
          <Vacio
            titulo={busqueda ? "Ningún envío coincide" : "No hay envíos en este filtro"}
            descripcion={
              busqueda
                ? "Pruebe con otro término o cambie el filtro de estado."
                : esConductor
                  ? "Cuando el despachador le asigne un envío, aparecerá aquí."
                  : "Registre un envío para empezar."
            }
            accion={
              busqueda ? (
                <Boton variante="secundario" onClick={() => setBusqueda("")}>
                  Limpiar búsqueda
                </Boton>
              ) : undefined
            }
          />
        </Tarjeta>
      ) : (
        <>
          <p className="texto-sm texto-suave">
            {visibles.length} de {data?.total ?? 0} envíos
          </p>
          <ul className="lista">
            {visibles.map((envio) => (
              <li key={envio.envio_id}>
                <FilaEnvio envio={envio} mostrarConductor={!esConductor} />
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function FilaEnvio({ envio, mostrarConductor }: { envio: EnvioResumen; mostrarConductor: boolean }) {
  return (
    <Link to={`/envios/${envio.envio_id}`} className={`envio estado-${envio.estado satisfies Estado}`}>
      <span className="envio__linea">
        <span className="envio__destinatario">{envio.destinatario}</span>
        <EtiquetaEstado estado={envio.estado} conPunto />
      </span>
      <span className="envio__detalle">{envio.destino}</span>
      <span className="envio__linea">
        <span className="envio__id">{envio.envio_id}</span>
        <span className="texto-xs texto-tenue" style={{ whiteSpace: "nowrap" }}>
          {mostrarConductor && envio.conductor_nombre ? `${envio.conductor_nombre} · ` : ""}
          {fechaRelativa(envio.actualizado_en)}
        </span>
      </span>
    </Link>
  );
}
