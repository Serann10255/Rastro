/* Seguimiento: dónde van los conductores en ruta, en vivo.
 *
 * El mapa se refresca cada diez segundos con la última posición de cada ruta
 * abierta. Elegir una ruta dibuja su recorrido y lista sus paradas con el
 * estado de cada una. No hay botones que cambien nada: esta pantalla mira; lo
 * que se hace con un envío se hace en su detalle, donde están los controles.
 *
 * Ver dónde está una persona es leer un dato personal suyo. El servidor deja
 * constancia de cada apertura de esta pantalla en la bitácora —una por pantalla
 * cada pocos minutos, no una por refresco— y la pantalla lo dice.
 */

import { Suspense, lazy, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useEstadosFinales, useRecorrido, useRutas } from "@/api/consultas";
import { mensajeDeError } from "@/componentes/notificaciones";
import type { MarcadorMapa, TonoMapa, TrazoMapa } from "@/componentes/Mapa";
import {
  Aviso,
  Boton,
  Esqueleto,
  EtiquetaEstado,
  GrupoSegmentado,
  ListaEsqueleto,
  Tarjeta,
  Vacio,
  antiguedad,
  fechaLegible,
  fechaRelativa,
} from "@/componentes/ui";
import type { EstadoSenal, Ruta } from "@/tipos";

const Mapa = lazy(() => import("@/componentes/Mapa"));

type Vista = "activas" | "finalizadas";

const SENAL: Record<EstadoSenal, { texto: string; tono: TonoMapa }> = {
  en_linea: { texto: "En línea", tono: "exito" },
  atrasada: { texto: "Señal atrasada", tono: "alerta" },
  sin_senal: { texto: "Sin señal", tono: "tenue" },
  sin_datos: { texto: "Esperando la primera posición", tono: "tenue" },
  cerrada: { texto: "Finalizada", tono: "tenue" },
};

function primerNombre(nombre: string): string {
  return nombre.trim().split(/\s+/)[0] ?? nombre;
}

export function Seguimiento() {
  const [vista, setVista] = useState<Vista>("activas");
  const [seleccionada, setSeleccionada] = useState<string | null>(null);

  const rutas = useRutas(vista);
  const recorrido = useRecorrido(seleccionada, vista === "activas");

  const lista = rutas.data?.rutas ?? [];
  const elegida = lista.find((r) => r.ruta_id === seleccionada) ?? recorrido.data?.ruta ?? null;

  const marcadores = useMemo<MarcadorMapa[]>(
    () =>
      lista
        .filter((ruta) => ruta.ultima_posicion)
        .map((ruta) => ({
          id: ruta.ruta_id,
          lat: ruta.ultima_posicion!.lat,
          lon: ruta.ultima_posicion!.lon,
          etiqueta: primerNombre(ruta.conductor_nombre),
          titulo: `${ruta.conductor_nombre}: ${SENAL[ruta.senal.estado].texto}, ${antiguedad(ruta.senal.edad_segundos)}`,
          tono: SENAL[ruta.senal.estado].tono,
          pulso: ruta.senal.estado === "en_linea",
          seleccionado: ruta.ruta_id === seleccionada,
          precision: ruta.ruta_id === seleccionada ? ruta.ultima_posicion!.precision_m : undefined,
        })),
    [lista, seleccionada],
  );

  const trazos = useMemo<TrazoMapa[]>(() => {
    const posiciones = recorrido.data?.posiciones ?? [];
    if (!seleccionada || posiciones.length < 2) return [];
    return [{ id: seleccionada, puntos: posiciones.map((p) => [p.lat, p.lon] as [number, number]) }];
  }, [recorrido.data, seleccionada]);

  const cambiarVista = (nueva: Vista) => {
    setVista(nueva);
    setSeleccionada(null);
  };

  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <div className="min-cero">
            <h1>Seguimiento</h1>
            <p className="encabezado-pagina__descripcion">
              Conductores en ruta y su última posición. El mapa se actualiza solo cada diez segundos.
            </p>
          </div>
          <Boton variante="secundario" onClick={() => void rutas.refetch()} cargando={rutas.isFetching}>
            Actualizar
          </Boton>
        </div>
      </header>

      <p className="texto-xs texto-tenue">
        La ubicación de una persona es un dato personal: la apertura de esta pantalla queda en la
        bitácora con su nombre.
      </p>

      {rutas.isError && <Aviso tono="error">{mensajeDeError(rutas.error)}</Aviso>}

      <div className="seguimiento">
        <div className="seguimiento__mapa">
          {rutas.isPending ? (
            <Esqueleto alto="100%" />
          ) : marcadores.length === 0 && trazos.length === 0 ? (
            <div className="mapa mapa--vacio">
              <Vacio
                titulo={vista === "activas" ? "No hay conductores en ruta" : "Sin posiciones para mostrar"}
                descripcion={
                  vista === "activas"
                    ? "Cuando un conductor sale a ruta desde Entregas, aparece aquí con su posición."
                    : "Las rutas finalizadas conservan su recorrido treinta días."
                }
              />
            </div>
          ) : (
            <Suspense fallback={<Esqueleto alto="100%" />}>
              <Mapa
                marcadores={marcadores}
                trazos={trazos}
                encuadre={seleccionada ?? `todas-${vista}`}
                etiqueta="Mapa de los conductores en ruta"
                alSeleccionar={setSeleccionada}
              />
            </Suspense>
          )}
        </div>

        <div className="seguimiento__panel pila-sm">
          <GrupoSegmentado
            etiqueta="Rutas"
            valor={vista}
            opciones={[
              { valor: "activas", texto: "En curso" },
              { valor: "finalizadas", texto: "Finalizadas" },
            ]}
            onCambio={cambiarVista}
          />

          {elegida ? (
            <DetalleRuta
              ruta={elegida}
              cargando={recorrido.isPending}
              posiciones={recorrido.data?.posiciones.length ?? 0}
              onVolver={() => setSeleccionada(null)}
            />
          ) : rutas.isPending ? (
            <ListaEsqueleto filas={3} />
          ) : lista.length === 0 ? (
            <Tarjeta>
              <Vacio
                titulo={vista === "activas" ? "Ninguna ruta en curso" : "Ninguna ruta finalizada"}
                descripcion={
                  vista === "activas"
                    ? "Las rutas aparecen en cuanto un conductor sale con sus guías."
                    : "Aquí quedan las rutas cerradas, con su recorrido y el estado de cada parada."
                }
              />
            </Tarjeta>
          ) : (
            <ul className="lista">
              {lista.map((ruta) => (
                <li key={ruta.ruta_id}>
                  <TarjetaRuta ruta={ruta} onElegir={() => setSeleccionada(ruta.ruta_id)} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------------- */

function Senal({ ruta }: { ruta: Ruta }) {
  const { estado, edad_segundos } = ruta.senal;
  return (
    <span className={`senal-breve senal-breve--${SENAL[estado].tono}`}>
      <span className="senal__punto" aria-hidden="true" />
      {SENAL[estado].texto}
      {edad_segundos !== null && estado !== "cerrada" ? ` · ${antiguedad(edad_segundos)}` : ""}
    </span>
  );
}

function Avance({ ruta }: { ruta: Ruta }) {
  const { resumen } = ruta;
  const porcentaje = resumen.total ? Math.round((resumen.cerradas / resumen.total) * 100) : 0;
  return (
    <div className="pila-sm" style={{ gap: "var(--e-1)" }}>
      <div
        className="avance"
        role="progressbar"
        aria-label={`Paradas cerradas de la ruta de ${ruta.conductor_nombre}`}
        aria-valuemin={0}
        aria-valuemax={resumen.total}
        aria-valuenow={resumen.cerradas}
      >
        <span className="avance__barra" style={{ width: `${porcentaje}%` }} />
      </div>
      <span className="texto-xs texto-suave">
        {resumen.entregadas} entregada{resumen.entregadas === 1 ? "" : "s"} · {resumen.pendientes} pendiente
        {resumen.pendientes === 1 ? "" : "s"}
        {resumen.incidencias ? ` · ${resumen.incidencias} con novedad` : ""} · {resumen.total} en total
      </span>
    </div>
  );
}

function TarjetaRuta({ ruta, onElegir }: { ruta: Ruta; onElegir: () => void }) {
  return (
    <button type="button" className="envio" onClick={onElegir}>
      <span className="envio__linea">
        <span className="envio__destinatario">{ruta.conductor_nombre}</span>
        <Senal ruta={ruta} />
      </span>
      <Avance ruta={ruta} />
      <span className="texto-xs texto-tenue">
        {ruta.estado === "ACTIVA"
          ? `Salió ${fechaRelativa(ruta.iniciada_en)}`
          : `Finalizó ${fechaRelativa(ruta.finalizada_en ?? ruta.actualizada_en)}`}
      </span>
    </button>
  );
}

function DetalleRuta({
  ruta,
  cargando,
  posiciones,
  onVolver,
}: {
  ruta: Ruta;
  cargando: boolean;
  posiciones: number;
  onVolver: () => void;
}) {
  const esFinal = useEstadosFinales();
  const ordenadas = [...ruta.paradas].sort(
    (a, b) => Number(esFinal(a.estado)) - Number(esFinal(b.estado)) || a.orden - b.orden,
  );

  return (
    <Tarjeta
      titulo={ruta.conductor_nombre}
      ayuda={
        ruta.estado === "ACTIVA"
          ? `Salió el ${fechaLegible(ruta.iniciada_en)}`
          : `Del ${fechaLegible(ruta.iniciada_en)} al ${fechaLegible(ruta.finalizada_en ?? ruta.actualizada_en)}${
              ruta.cierre === "manual" ? " · terminada con paradas abiertas" : ""
            }`
      }
      acciones={
        <Boton variante="sutil" onClick={onVolver}>
          Ver todas
        </Boton>
      }
    >
      <div className="pila-sm">
        <Senal ruta={ruta} />
        <Avance ruta={ruta} />
        <p className="texto-xs texto-tenue" style={{ margin: 0 }}>
          {cargando ? "Cargando el recorrido…" : `${posiciones} posiciones en el recorrido dibujado.`}
          {ruta.ultima_posicion?.hora_de === "servidor"
            ? " La última hora es la de recepción: la del teléfono no era creíble."
            : ""}
        </p>

        <ol className="lista">
          {ordenadas.map((parada) => (
            <li key={parada.envio_id}>
              <Link to={`/envios/${parada.envio_id}`} className={`envio estado-${parada.estado}`}>
                <span className="envio__linea">
                  <span className="envio__destinatario">
                    <span className="codigo-estado">{parada.orden}</span> {parada.destinatario}
                  </span>
                  <EtiquetaEstado estado={parada.estado} codigo={parada.codigo_estado} />
                </span>
                <span className="envio__detalle">
                  {parada.direccion}
                  {parada.ciudad ? ` · ${parada.ciudad}` : ""}
                </span>
              </Link>
            </li>
          ))}
        </ol>
      </div>
    </Tarjeta>
  );
}
