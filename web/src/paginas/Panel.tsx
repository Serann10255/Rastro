/* Tablero de la empresa.
 *
 * Los indicadores los calcula el servidor y no esta pantalla. La razón es que
 * un tablero calculado en el cliente obliga a enviarle todos los envíos, y eso
 * es a la vez lento y una entrega de datos que la pantalla no necesita mostrar.
 *
 * Cada rol llega buscando algo distinto: el despachador quiere ver qué está
 * atascado, el conductor su siguiente parada, el auditor si la cadena sigue
 * íntegra. Una única pantalla común obligaría a los tres a buscar lo suyo entre
 * lo de los demás.
 */

import { useState } from "react";
import { Link } from "react-router-dom";

import { useBitacora, useEnvios, useTablero, useVerificarBitacora } from "@/api/consultas";
import { useSesion } from "@/api/sesion";
import { mensajeDeError } from "@/componentes/notificaciones";
import {
  Aviso,
  Boton,
  Esqueleto,
  EtiquetaEstado,
  GrupoSegmentado,
  Metrica,
  Tarjeta,
  Vacio,
  fechaRelativa,
} from "@/componentes/ui";
import type { Tablero } from "@/tipos";

export function Panel() {
  const { usuario, empresa, tieneGrupo } = useSesion();
  const [dias, setDias] = useState<number>(30);

  const soloAuditor = tieneGrupo("auditor") && !tieneGrupo("administrador", "despachador", "conductor");

  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <div className="min-cero">
            <h1>{empresa?.nombre ?? "Panel"}</h1>
            <p className="encabezado-pagina__descripcion">
              {usuario?.nombre}, opera con el rol <strong>{usuario?.grupos.join(", ")}</strong>.
              {empresa?.ciudad && ` ${empresa.ciudad}, ${empresa.departamento ?? ""}.`} Cada
              operación queda registrada con su identidad y su marca de tiempo.
            </p>
          </div>
          {!soloAuditor && (
            <GrupoSegmentado
              etiqueta="Periodo"
              valor={String(dias)}
              opciones={[
                { valor: "7", texto: "7 días" },
                { valor: "30", texto: "30 días" },
                { valor: "90", texto: "90 días" },
              ]}
              onCambio={(valor) => setDias(Number(valor))}
            />
          )}
        </div>
      </header>

      {soloAuditor ? <PanelAuditor /> : <PanelOperacion dias={dias} />}
    </>
  );
}

/* ---------------------------------------------------------------------- */
/* Operación                                                              */
/* ---------------------------------------------------------------------- */

function PanelOperacion({ dias }: { dias: number }) {
  const { tieneGrupo } = useSesion();
  const { data, isPending, error } = useTablero(dias);

  if (error) return <Aviso tono="error">{mensajeDeError(error)}</Aviso>;
  if (isPending || !data) return <EsqueletoTablero />;

  const esConductor = data.alcance === "propios";

  return (
    <>
      <div className="rejilla rejilla--2 rejilla--4">
        <Metrica
          etiqueta={esConductor ? "Asignados a usted" : "En curso"}
          valor={data.totales.abiertos}
          nota="Envíos que aún no se cerraron"
          color="var(--acento)"
        />
        <Metrica
          etiqueta="Entregados"
          valor={data.totales.entregados}
          nota={
            data.tasa_entrega === null
              ? "Sin envíos cerrados todavía"
              : `${data.tasa_entrega}% de los cerrados`
          }
          color="var(--exito)"
        />
        <Metrica
          etiqueta="Con incidencia"
          valor={data.atencion.con_incidencia}
          nota="Detenidos, requieren autorización"
          color={data.atencion.con_incidencia ? "var(--peligro)" : undefined}
        />
        <Metrica
          etiqueta={esConductor ? "Sin recoger" : "Sin asignar"}
          valor={data.atencion.sin_asignar}
          nota="Esperan mensajero"
          color={data.atencion.sin_asignar ? "var(--alerta)" : undefined}
        />
      </div>

      {data.atencion.estancados > 0 && (
        <Aviso tono="alerta" titulo={`${data.atencion.estancados} envíos sin movimiento`}>
          Llevan más de dos días sin cambiar de estado. No aparecen como incidencia porque nadie las
          reportó: están detenidos sin que el sistema lo sepa.
          <ul style={{ margin: "var(--e-2) 0 0", paddingLeft: "1.25rem" }}>
            {data.atencion.detalle_estancados.slice(0, 5).map((envio) => (
              <li key={envio.envio_id} className="texto-sm">
                <Link to={`/envios/${envio.envio_id}`}>{envio.destinatario || envio.envio_id}</Link>{" "}
                — {envio.estado.replace(/_/g, " ").toLowerCase()}, {fechaRelativa(envio.actualizado_en)}
              </li>
            ))}
          </ul>
        </Aviso>
      )}

      <div className="doble-panel">
        <Tarjeta
          titulo="Dónde están los envíos"
          ayuda="Todos los estados del catálogo, incluidos los que están en cero: un estado vacío también es información."
        >
          <DesglosePorEstado tablero={data} />
        </Tarjeta>

        <div className="pila">
          <Tarjeta
            titulo={`Movimiento de los últimos ${data.ventana.dias} días`}
            ayuda="Creados frente a entregados, día a día."
          >
            <SerieDiaria serie={data.serie_diaria} />
          </Tarjeta>

          {data.equipo && (
            <Tarjeta
              titulo="Equipo"
              ayuda={`${data.equipo.activos} de ${data.equipo.usuarios} cuentas activas.`}
              acciones={
                tieneGrupo("administrador") ? (
                  <Link to="/administracion" className="boton boton--secundario">
                    Administrar
                  </Link>
                ) : undefined
              }
            >
              <ul className="pila-sm" style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {data.equipo.por_grupo.map((entrada) => (
                  <li key={entrada.grupo} className="fila-entre">
                    <span className="texto-sm" style={{ textTransform: "capitalize" }}>
                      {entrada.grupo}
                    </span>
                    <span className="etiqueta">{entrada.cantidad}</span>
                  </li>
                ))}
              </ul>
            </Tarjeta>
          )}
        </div>
      </div>
    </>
  );
}

function DesglosePorEstado({ tablero }: { tablero: Tablero }) {
  const maximo = Math.max(1, ...tablero.por_estado.map((e) => e.cantidad));

  if (tablero.totales.envios === 0) {
    return (
      <Vacio
        titulo="Sin envíos todavía"
        descripcion="Registre el primero para ver la distribución del proceso."
        accion={
          <Link to="/envios/nuevo" className="boton">
            Registrar envío
          </Link>
        }
      />
    );
  }

  return (
    <ul className="pila-sm" style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {tablero.por_estado.map((entrada) => (
        <li key={entrada.estado} className={`estado-${entrada.estado}`}>
          <div className="fila-entre" style={{ marginBottom: "var(--e-1)" }}>
            <span className="texto-sm" style={{ fontWeight: 600 }}>
              <span className="codigo-estado">{entrada.codigo}</span> {entrada.etiqueta}
            </span>
            <span className="texto-sm texto-suave" style={{ fontVariantNumeric: "tabular-nums" }}>
              {entrada.cantidad}
            </span>
          </div>
          <div
            style={{
              height: "0.5rem",
              borderRadius: "var(--r-completo)",
              background: "var(--fondo-sutil)",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${(entrada.cantidad / maximo) * 100}%`,
                height: "100%",
                background: "var(--estado-color)",
                transition: "width var(--transicion)",
              }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}

/* Barras en CSS: no hace falta una biblioteca de gráficos para mostrar dos
 * series de treinta valores, y evitarla mantiene el sitio sin dependencias
 * externas que auditar. */
function SerieDiaria({ serie }: { serie: Tablero["serie_diaria"] }) {
  const maximo = Math.max(1, ...serie.flatMap((d) => [d.creados, d.entregados]));

  return (
    <>
      <div className="serie" role="img" aria-label="Envíos creados y entregados por día">
        {serie.map((dia) => (
          <div
            key={dia.fecha}
            className="serie__dia"
            title={`${dia.fecha}: ${dia.creados} creados, ${dia.entregados} entregados`}
          >
            <div
              className="serie__barra serie__barra--creados"
              style={{ height: `${(dia.creados / maximo) * 100}%` }}
            />
            <div
              className="serie__barra serie__barra--entregados"
              style={{ height: `${(dia.entregados / maximo) * 100}%` }}
            />
          </div>
        ))}
      </div>
      <div className="leyenda" style={{ marginTop: "var(--e-3)" }}>
        <span>
          <span className="leyenda__punto" style={{ background: "var(--acento)", opacity: 0.55 }} />
          Creados
        </span>
        <span>
          <span className="leyenda__punto" style={{ background: "var(--exito)" }} />
          Entregados
        </span>
        <span className="texto-tenue">
          {serie[0]?.fecha} a {serie.at(-1)?.fecha}
        </span>
      </div>
    </>
  );
}

function EsqueletoTablero() {
  return (
    <>
      <div className="rejilla rejilla--2 rejilla--4">
        {[0, 1, 2, 3].map((i) => (
          <Esqueleto key={i} alto="6.5rem" />
        ))}
      </div>
      <div className="doble-panel">
        <Esqueleto alto="22rem" />
        <Esqueleto alto="22rem" />
      </div>
    </>
  );
}

/* ---------------------------------------------------------------------- */
/* Auditor                                                                */
/* ---------------------------------------------------------------------- */

function PanelAuditor() {
  const { data, isPending } = useBitacora();
  const { data: envios } = useEnvios();
  const verificar = useVerificarBitacora();

  const registros = data?.registros ?? [];
  const rechazos = registros.filter((registro) => registro.resultado === "DENY");
  const verificacion = verificar.data;

  return (
    <>
      <div className="rejilla rejilla--3">
        <Metrica
          etiqueta="Registros en bitácora"
          valor={isPending ? <Esqueleto alto="2rem" ancho="3rem" /> : registros.length}
          nota="Cada operación deja un eslabón"
          color="var(--acento)"
        />
        <Metrica
          etiqueta="Intentos rechazados"
          valor={isPending ? <Esqueleto alto="2rem" ancho="3rem" /> : rechazos.length}
          nota="Operaciones denegadas y registradas"
          color={rechazos.length ? "var(--peligro)" : undefined}
        />
        <Metrica
          etiqueta="Integridad de la cadena"
          valor={verificacion ? (verificacion.cadena_valida ? "íntegra" : "rota") : "sin verificar"}
          nota={
            verificacion
              ? `${verificacion.registros_verificados} registros recalculados`
              : "Ejecute la verificación"
          }
          color={
            verificacion ? (verificacion.cadena_valida ? "var(--exito)" : "var(--peligro)") : undefined
          }
        />
      </div>

      <Tarjeta
        titulo="Verificación de integridad"
        ayuda="Recalcula la cadena de funciones hash completa y señala el punto exacto de ruptura, si lo hay."
        acciones={
          <Boton onClick={() => verificar.mutate()} cargando={verificar.isPending}>
            Verificar ahora
          </Boton>
        }
      >
        {verificar.isError && <Aviso tono="error">{mensajeDeError(verificar.error)}</Aviso>}

        {verificacion ? (
          <div className="pila-sm">
            <Aviso
              tono={verificacion.cadena_valida ? "exito" : "error"}
              titulo={verificacion.cadena_valida ? "La cadena verifica" : "La cadena está rota"}
            >
              {verificacion.cadena_valida ? (
                <>
                  {verificacion.registros_verificados} registros recalculados, secuencias{" "}
                  {verificacion.primera_seq} a {verificacion.ultima_seq}.
                </>
              ) : (
                <>
                  Ruptura en la secuencia{" "}
                  {verificacion.punto_de_ruptura?.seq ?? verificacion.punto_de_ruptura?.seq_esperada}:{" "}
                  {verificacion.punto_de_ruptura?.descripcion}
                </>
              )}
            </Aviso>
            <Link to="/bitacora" className="texto-sm">
              Ver la bitácora completa
            </Link>
          </div>
        ) : (
          <p className="texto-sm texto-suave">
            La verificación no se ejecuta sola: es un procedimiento de auditoría y debe quedar
            constancia de quién lo ejecutó y cuándo. Al pulsar, la consulta también se registra.
          </p>
        )}
      </Tarjeta>

      <Tarjeta
        titulo="Envíos de la organización"
        ayuda="El auditor consulta el estado del sistema; no lo modifica."
      >
        {envios?.envios.length ? (
          <ul className="lista">
            {envios.envios.slice(0, 8).map((envio) => (
              <li key={envio.envio_id}>
                <Link to={`/envios/${envio.envio_id}`} className={`envio estado-${envio.estado}`}>
                  <span className="envio__linea">
                    <span className="envio__destinatario">{envio.destinatario}</span>
                    <EtiquetaEstado estado={envio.estado} codigo={envio.codigo_estado} />
                  </span>
                  <span className="envio__detalle">{envio.destino}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <Vacio titulo="Sin envíos" />
        )}
      </Tarjeta>
    </>
  );
}
