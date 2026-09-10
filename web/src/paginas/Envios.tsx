/* Listado de órdenes con búsqueda, filtros, selección múltiple y exportación.
 *
 * El filtro por organización y por conductor lo aplica el servidor, no esta
 * pantalla: el despachador ve los de su empresa y el conductor solo los que
 * tiene asignados. Lo que se filtra aquí es únicamente presentación sobre lo
 * que el servidor ya decidió entregar.
 */

import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "@/api/cliente";
import { useCatalogoEstados, useEnvios, useEstadosFinales } from "@/api/consultas";
import { useSesion } from "@/api/sesion";
import { mensajeDeError, useNotificaciones } from "@/componentes/notificaciones";
import {
  Aviso,
  Boton,
  Campo,
  CampoSelect,
  EtiquetaEstado,
  ListaEsqueleto,
  Tarjeta,
  Vacio,
  fechaRelativa,
} from "@/componentes/ui";
import type { EnvioResumen } from "@/tipos";

type Filtro = "activos" | "sin_asignar" | "incidencia" | "cerrados" | "todos";

const FILTROS: { valor: Filtro; texto: string }[] = [
  { valor: "activos", texto: "En curso" },
  { valor: "sin_asignar", texto: "Sin asignar" },
  { valor: "incidencia", texto: "Incidencia" },
  { valor: "cerrados", texto: "Cerrados" },
  { valor: "todos", texto: "Todos" },
];

/* Qué estados cierran un envío lo dice el catálogo del servidor, no una lista
 * escrita aquí: cuando se añadieron DEVUELTO y CANCELADO, una lista local
 * habría dejado esos envíos contando como abiertos sin que nadie lo notara. */
function aplicaFiltro(
  envio: EnvioResumen,
  filtro: Filtro,
  esFinal: (estado: string) => boolean,
): boolean {
  switch (filtro) {
    case "activos":
      return !esFinal(envio.estado);
    case "sin_asignar":
      return envio.estado === "CREADO";
    case "incidencia":
      return envio.estado === "INCIDENCIA";
    case "cerrados":
      return esFinal(envio.estado);
    default:
      return true;
  }
}

export function Envios() {
  const { puede } = useSesion();
  const { avisar } = useNotificaciones();
  const navegar = useNavigate();

  const { data, isPending, error, refetch, isFetching } = useEnvios();
  const { data: catalogo } = useCatalogoEstados();
  const esFinal = useEstadosFinales();

  const [filtro, setFiltro] = useState<Filtro>("activos");
  const [estadoExacto, setEstadoExacto] = useState<string>("");
  const [busqueda, setBusqueda] = useState("");
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set());
  const [exportando, setExportando] = useState(false);

  /* Quien no puede asignar solo ve los suyos: es el mismo criterio que aplica
   * el servidor, y sigue valiendo para un rol que la empresa cree mañana. */
  const soloConductor = !puede("envio:asignar");
  const puedeGenerarGuias = puede("envio:consultar");

  const visibles = useMemo(() => {
    const termino = busqueda.trim().toLowerCase();
    return (data?.envios ?? [])
      .filter((envio) =>
        estadoExacto ? envio.estado === estadoExacto : aplicaFiltro(envio, filtro, esFinal),
      )
      .filter((envio) =>
        termino
          ? [
              envio.destinatario,
              envio.destino,
              envio.envio_id,
              envio.orden_compra ?? "",
              envio.cliente_nombre ?? "",
              envio.conductor_nombre ?? "",
              String(envio.codigo_estado),
            ]
              .join(" ")
              .toLowerCase()
              .includes(termino)
          : true,
      );
  }, [data, filtro, estadoExacto, busqueda, esFinal]);

  const alternar = (envioId: string) => {
    setSeleccion((previa) => {
      const nueva = new Set(previa);
      if (nueva.has(envioId)) nueva.delete(envioId);
      else nueva.add(envioId);
      return nueva;
    });
  };

  const todosVisiblesSeleccionados =
    visibles.length > 0 && visibles.every((envio) => seleccion.has(envio.envio_id));

  const exportar = async () => {
    setExportando(true);
    try {
      await api.exportarEnvios();
      avisar("Archivo descargado.", "exito");
    } catch (fallo) {
      avisar(mensajeDeError(fallo), "error");
    } finally {
      setExportando(false);
    }
  };

  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <div className="min-cero">
            <h1>{soloConductor ? "Mis envíos" : "Órdenes"}</h1>
            <p className="encabezado-pagina__descripcion">
              {soloConductor
                ? "Solo aparecen los envíos que le fueron asignados. El filtro lo aplica el servidor."
                : "Envíos de su organización. Los datos de otras empresas no son alcanzables desde aquí."}
            </p>
          </div>
          <div className="fila">
            <Boton variante="secundario" onClick={exportar} cargando={exportando}>
              Exportar CSV
            </Boton>
            {puede("envio:crear") && (
              <Link to="/envios/nuevo" className="boton">
                Registrar
              </Link>
            )}
          </div>
        </div>
      </header>

      <Tarjeta>
        <div className="filtros">
          <Campo
            etiqueta="Buscar"
            type="search"
            placeholder="Destinatario, dirección, guía, orden de compra o código"
            value={busqueda}
            onChange={(evento) => setBusqueda(evento.target.value)}
          />
          <CampoSelect
            etiqueta="Estado exacto"
            value={estadoExacto}
            onChange={(evento) => setEstadoExacto(evento.target.value)}
            ayuda="El código es el que viaja en los archivos de intercambio."
          >
            <option value="">Usar filtro rápido</option>
            {catalogo?.estados.map((estado) => (
              <option key={estado.codigo} value={estado.estado}>
                {estado.codigo} · {estado.etiqueta}
              </option>
            ))}
          </CampoSelect>
          <div className="campo">
            <span className="campo__etiqueta">&nbsp;</span>
            <Boton variante="secundario" onClick={() => refetch()} cargando={isFetching}>
              Actualizar
            </Boton>
          </div>
        </div>

        {!estadoExacto && (
          <div className="grupo-segmentado" role="group" aria-label="Filtro rápido" style={{ marginTop: "var(--e-3)" }}>
            {FILTROS.map((opcion) => (
              <button
                key={opcion.valor}
                type="button"
                className="grupo-segmentado__opcion"
                aria-pressed={filtro === opcion.valor}
                onClick={() => setFiltro(opcion.valor)}
              >
                {opcion.texto}
              </button>
            ))}
          </div>
        )}
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
                ? "Pruebe con otro término o cambie el filtro."
                : soloConductor
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
          <div className="fila-entre">
            <p className="texto-sm texto-suave">
              {visibles.length} de {data?.total ?? 0} envíos
            </p>
            {puedeGenerarGuias && (
              <Boton
                variante="sutil"
                onClick={() =>
                  setSeleccion(
                    todosVisiblesSeleccionados
                      ? new Set()
                      : new Set(visibles.map((envio) => envio.envio_id)),
                  )
                }
              >
                {todosVisiblesSeleccionados ? "Quitar selección" : "Seleccionar todo"}
              </Boton>
            )}
          </div>

          <ul className="lista">
            {visibles.map((envio) => (
              <li key={envio.envio_id}>
                <FilaEnvio
                  envio={envio}
                  mostrarConductor={!soloConductor}
                  seleccionable={puedeGenerarGuias}
                  seleccionado={seleccion.has(envio.envio_id)}
                  onAlternar={() => alternar(envio.envio_id)}
                />
              </li>
            ))}
          </ul>

          {seleccion.size > 0 && (
            <div className="barra-seleccion">
              <span className="texto-sm">
                <strong>{seleccion.size}</strong> envío{seleccion.size === 1 ? "" : "s"}{" "}
                seleccionado{seleccion.size === 1 ? "" : "s"}
              </span>
              <div className="crece" />
              <Boton
                onClick={() =>
                  navegar("/envios/guias", { state: { envios: [...seleccion] } })
                }
              >
                Generar guías
              </Boton>
              <Boton variante="secundario" onClick={() => setSeleccion(new Set())}>
                Cancelar
              </Boton>
            </div>
          )}
        </>
      )}
    </>
  );
}

function FilaEnvio({
  envio,
  mostrarConductor,
  seleccionable,
  seleccionado,
  onAlternar,
}: {
  envio: EnvioResumen;
  mostrarConductor: boolean;
  seleccionable: boolean;
  seleccionado: boolean;
  onAlternar: () => void;
}) {
  const contenido = (
    <>
      <span className="envio__linea">
        <span className="envio__destinatario">{envio.destinatario}</span>
        <EtiquetaEstado estado={envio.estado} codigo={envio.codigo_estado} conPunto />
      </span>
      <span className="envio__detalle">
        {envio.destino}
        {envio.ciudad_destino ? ` · ${envio.ciudad_destino}` : ""}
      </span>
      {(envio.orden_compra || envio.cliente_nombre) && (
        <span className="envio__detalle">
          {envio.cliente_nombre}
          {envio.cliente_nombre && envio.orden_compra ? " · " : ""}
          {envio.orden_compra && <span className="mono">OC {envio.orden_compra}</span>}
        </span>
      )}
      <span className="envio__linea">
        <span className="envio__id">{envio.envio_id}</span>
        <span className="texto-xs texto-tenue" style={{ whiteSpace: "nowrap" }}>
          {mostrarConductor && envio.conductor_nombre ? `${envio.conductor_nombre} · ` : ""}
          {fechaRelativa(envio.actualizado_en)}
        </span>
      </span>
    </>
  );

  if (!seleccionable) {
    return (
      <Link to={`/envios/${envio.envio_id}`} className={`envio estado-${envio.estado}`}>
        {contenido}
      </Link>
    );
  }

  return (
    <div className={`envio envio--seleccionable estado-${envio.estado}`}>
      <input
        type="checkbox"
        className="envio__casilla"
        checked={seleccionado}
        onChange={onAlternar}
        aria-label={`Seleccionar el envío de ${envio.destinatario}`}
      />
      <Link
        to={`/envios/${envio.envio_id}`}
        style={{ display: "grid", gap: "var(--e-2)", color: "inherit", textDecoration: "none", minWidth: 0 }}
      >
        {contenido}
      </Link>
    </div>
  );
}
