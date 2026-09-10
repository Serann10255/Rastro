/* Panel de inicio, distinto según el rol.
 *
 * Cada rol llega buscando algo distinto: el despachador quiere ver qué está
 * atascado, el conductor quiere su siguiente parada, el auditor quiere saber si
 * la cadena sigue íntegra. Una única pantalla común obligaría a los tres a
 * buscar lo suyo entre lo de los demás.
 */

import { Link } from "react-router-dom";

import { useSesion } from "@/api/sesion";
import { useBitacora, useEnvios, useVerificarBitacora } from "@/api/consultas";
import { mensajeDeError } from "@/componentes/notificaciones";
import {
  Aviso,
  Boton,
  EtiquetaEstado,
  Esqueleto,
  Metrica,
  Tarjeta,
  Vacio,
  fechaRelativa,
} from "@/componentes/ui";
import { FLUJO_PRINCIPAL } from "@/tipos";
import type { EnvioResumen, Estado } from "@/tipos";

export function Panel() {
  const { usuario, tieneGrupo } = useSesion();

  return (
    <>
      <header className="encabezado-pagina">
        <h1>Hola, {usuario?.nombre?.split(" ")[0] ?? "de nuevo"}</h1>
        <p className="encabezado-pagina__descripcion">
          Opera en nombre de <strong>{usuario?.org_id}</strong> con el rol{" "}
          <strong>{usuario?.grupos.join(", ")}</strong>. Cada operación que realice queda registrada
          con su identidad y su marca de tiempo.
        </p>
      </header>

      {tieneGrupo("auditor") && <PanelAuditor />}
      {tieneGrupo("conductor") && !tieneGrupo("despachador") && <PanelConductor />}
      {tieneGrupo("administrador", "despachador") && <PanelDespachador />}
    </>
  );
}

/* ---------------------------------------------------------------------- */
/* Despachador                                                            */
/* ---------------------------------------------------------------------- */

function PanelDespachador() {
  const { data, isPending, error } = useEnvios();

  if (error) return <Aviso tono="error">{mensajeDeError(error)}</Aviso>;

  const envios = data?.envios ?? [];
  const porEstado = contarPorEstado(envios);
  const sinAsignar = envios.filter((envio) => envio.estado === "CREADO");
  const conIncidencia = envios.filter((envio) => envio.estado === "INCIDENCIA");
  const entregados = porEstado.ENTREGADO ?? 0;

  return (
    <>
      <div className="rejilla rejilla--2 rejilla--4">
        <Metrica
          etiqueta="En curso"
          valor={isPending ? <Esqueleto alto="2rem" ancho="3rem" /> : envios.length - entregados}
          nota="Envíos que aún no se han entregado"
          color="var(--acento)"
        />
        <Metrica
          etiqueta="Sin asignar"
          valor={isPending ? <Esqueleto alto="2rem" ancho="3rem" /> : sinAsignar.length}
          nota="Esperan mensajero"
          color={sinAsignar.length ? "var(--alerta)" : undefined}
        />
        <Metrica
          etiqueta="Con incidencia"
          valor={isPending ? <Esqueleto alto="2rem" ancho="3rem" /> : conIncidencia.length}
          nota="Requieren su autorización para reanudar"
          color={conIncidencia.length ? "var(--peligro)" : undefined}
        />
        <Metrica
          etiqueta="Entregados"
          valor={isPending ? <Esqueleto alto="2rem" ancho="3rem" /> : entregados}
          nota="Con evidencia acreditada"
          color="var(--exito)"
        />
      </div>

      {conIncidencia.length > 0 && (
        <Aviso tono="alerta" titulo="Hay envíos detenidos por una incidencia">
          Reanudarlos requiere su autorización: el conductor reporta el incidente, el despachador
          decide si continúa. Es una separación de funciones deliberada.
        </Aviso>
      )}

      <div className="doble-panel">
        <Tarjeta
          titulo="Distribución del proceso"
          ayuda="Dónde se acumulan los envíos ahora mismo."
        >
          {isPending ? <Esqueleto alto="10rem" /> : <BarrasPorEstado envios={envios} />}
        </Tarjeta>

        <Tarjeta
          titulo="Pendientes de asignar"
          ayuda="Un envío sin mensajero no puede avanzar."
          acciones={
            <Link to="/envios/nuevo" className="boton boton--secundario">
              Registrar envío
            </Link>
          }
        >
          {isPending ? (
            <Esqueleto alto="8rem" />
          ) : sinAsignar.length === 0 ? (
            <Vacio
              titulo="Todo asignado"
              descripcion="No hay envíos esperando mensajero."
            />
          ) : (
            <ul className="lista">
              {sinAsignar.slice(0, 5).map((envio) => (
                <li key={envio.envio_id}>
                  <Link to={`/envios/${envio.envio_id}`} className="envio">
                    <span className="envio__linea">
                      <span className="envio__destinatario">{envio.destinatario}</span>
                      <EtiquetaEstado estado={envio.estado} />
                    </span>
                    <span className="envio__detalle">{envio.destino}</span>
                    <span className="envio__id">creado {fechaRelativa(envio.creado_en)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------------- */
/* Conductor                                                              */
/* ---------------------------------------------------------------------- */

function PanelConductor() {
  const { data, isPending, error } = useEnvios();

  if (error) return <Aviso tono="error">{mensajeDeError(error)}</Aviso>;

  const envios = data?.envios ?? [];
  const activos = envios.filter((envio) => envio.estado !== "ENTREGADO");
  const enReparto = activos.filter((envio) => envio.estado === "EN_REPARTO");
  const siguiente = enReparto[0] ?? activos[0];

  return (
    <>
      <div className="rejilla rejilla--2">
        <Metrica
          etiqueta="Asignados a usted"
          valor={isPending ? <Esqueleto alto="2rem" ancho="3rem" /> : activos.length}
          nota="Envíos que aún no ha entregado"
          color="var(--acento)"
        />
        <Metrica
          etiqueta="En reparto"
          valor={isPending ? <Esqueleto alto="2rem" ancho="3rem" /> : enReparto.length}
          nota="Listos para entregar con evidencia"
          color={enReparto.length ? "var(--alerta)" : undefined}
        />
      </div>

      <Tarjeta
        titulo="Su siguiente parada"
        ayuda="Registrar el avance debe costar menos que enviar un mensaje: un toque para abrir, uno para el estado."
      >
        {isPending ? (
          <Esqueleto alto="6rem" />
        ) : !siguiente ? (
          <Vacio
            titulo="No tiene envíos asignados"
            descripcion="Cuando el despachador le asigne uno, aparecerá aquí."
          />
        ) : (
          <Link to={`/envios/${siguiente.envio_id}`} className="envio">
            <span className="envio__linea">
              <span className="envio__destinatario">{siguiente.destinatario}</span>
              <EtiquetaEstado estado={siguiente.estado} conPunto />
            </span>
            <span className="envio__detalle">{siguiente.destino}</span>
            <span className="envio__id">
              actualizado {fechaRelativa(siguiente.actualizado_en)}
            </span>
          </Link>
        )}
      </Tarjeta>

      {activos.length > 1 && (
        <Tarjeta titulo={`Resto de su ruta (${activos.length - 1})`}>
          <ul className="lista">
            {activos.slice(1).map((envio) => (
              <li key={envio.envio_id}>
                <Link to={`/envios/${envio.envio_id}`} className="envio">
                  <span className="envio__linea">
                    <span className="envio__destinatario">{envio.destinatario}</span>
                    <EtiquetaEstado estado={envio.estado} />
                  </span>
                  <span className="envio__detalle">{envio.destino}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Tarjeta>
      )}
    </>
  );
}

/* ---------------------------------------------------------------------- */
/* Auditor                                                                */
/* ---------------------------------------------------------------------- */

function PanelAuditor() {
  const { data, isPending } = useBitacora();
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
          valor={
            verificacion === undefined
              ? "sin verificar"
              : verificacion.cadena_valida
                ? "íntegra"
                : "rota"
          }
          nota={
            verificacion
              ? `${verificacion.registros_verificados} registros recalculados`
              : "Ejecute la verificación"
          }
          color={
            verificacion === undefined
              ? undefined
              : verificacion.cadena_valida
                ? "var(--exito)"
                : "var(--peligro)"
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

        {!verificacion && !verificar.isPending && (
          <p className="texto-sm texto-suave">
            La verificación no se ejecuta sola: es un procedimiento de auditoría y debe quedar
            constancia de quién lo ejecutó y cuándo. Al pulsar, la consulta también se registra en la
            bitácora.
          </p>
        )}

        {verificacion && (
          <div className="pila-sm">
            <Aviso
              tono={verificacion.cadena_valida ? "exito" : "error"}
              titulo={
                verificacion.cadena_valida
                  ? "La cadena verifica"
                  : "La cadena está rota"
              }
            >
              {verificacion.cadena_valida ? (
                <>
                  {verificacion.registros_verificados} registros recalculados, secuencias{" "}
                  {verificacion.primera_seq} a {verificacion.ultima_seq}. Ninguno fue alterado
                  después de escribirse.
                </>
              ) : (
                <>
                  Ruptura en la secuencia{" "}
                  {verificacion.punto_de_ruptura?.seq ?? verificacion.punto_de_ruptura?.seq_esperada}:{" "}
                  {verificacion.punto_de_ruptura?.tipo}. {verificacion.punto_de_ruptura?.descripcion}
                </>
              )}
            </Aviso>
            <p className="texto-xs texto-tenue mono">Hash final: {verificacion.hash_final}</p>
            <Link to="/bitacora" className="texto-sm">
              Ver la bitácora completa
            </Link>
          </div>
        )}
      </Tarjeta>
    </>
  );
}

/* ---------------------------------------------------------------------- */
/* Auxiliares                                                             */
/* ---------------------------------------------------------------------- */

function contarPorEstado(envios: EnvioResumen[]): Partial<Record<Estado, number>> {
  const conteo: Partial<Record<Estado, number>> = {};
  for (const envio of envios) {
    conteo[envio.estado] = (conteo[envio.estado] ?? 0) + 1;
  }
  return conteo;
}

/* Barras proporcionales en CSS: no hace falta una biblioteca de gráficos para
 * mostrar siete cantidades, y evitarla mantiene el sitio sin dependencias
 * externas que auditar. */
function BarrasPorEstado({ envios }: { envios: EnvioResumen[] }) {
  const conteo = contarPorEstado(envios);
  const estados: Estado[] = [...FLUJO_PRINCIPAL, "INCIDENCIA"];
  const maximo = Math.max(1, ...estados.map((estado) => conteo[estado] ?? 0));

  if (envios.length === 0) {
    return <Vacio titulo="Sin envíos todavía" descripcion="Registre el primero para ver la distribución." />;
  }

  return (
    <ul className="pila-sm" style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {estados.map((estado) => {
        const cantidad = conteo[estado] ?? 0;
        return (
          <li key={estado} className={`estado-${estado}`}>
            <div className="fila-entre" style={{ marginBottom: "var(--e-1)" }}>
              <span className="texto-sm" style={{ fontWeight: 600 }}>
                {estado.replace(/_/g, " ")}
              </span>
              <span className="texto-sm texto-suave" style={{ fontVariantNumeric: "tabular-nums" }}>
                {cantidad}
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
                  width: `${(cantidad / maximo) * 100}%`,
                  height: "100%",
                  background: "var(--estado-color)",
                  transition: "width var(--transicion)",
                }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
