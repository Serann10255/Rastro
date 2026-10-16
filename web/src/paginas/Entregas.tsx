/* Entregas: el conductor elige sus guías, sale a ruta y entrega.
 *
 * Son dos pantallas en una dirección. Sin ruta abierta, la selección: las guías
 * que el conductor tiene en su poder, para marcar las que lleva en el vehículo.
 * Con ruta abierta, el modo ruta: su posición, las paradas pendientes y las dos
 * acciones de la calle —entregar y reportar una novedad—. Cuál se ve lo dice el
 * servidor (`/rutas/activa`), no un estado guardado en el navegador: así, si el
 * teléfono se reinicia a mitad del recorrido, al volver aparece la ruta tal
 * como quedó.
 *
 * Mientras la ruta está abierta, el teléfono comparte su ubicación con la
 * empresa y con los destinatarios de los envíos en reparto. La pantalla lo dice
 * antes de salir y mientras dura: compartir la ubicación de una persona es algo
 * que esa persona tiene que saber que está pasando.
 */

import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import {
  claves,
  useCargaDeEvidencia,
  useEnvios,
  useEstadosFinales,
  useFinalizarRuta,
  useIniciarRuta,
  useRegistrarEvento,
  useRutaActiva,
} from "@/api/consultas";
import type { FaseEvidencia } from "@/api/consultas";
import { useSesion } from "@/api/sesion";
import {
  leerUbicacion,
  usePantallaEncendida,
  useTransmisionDeUbicacion,
} from "@/api/transmision";
import type { FalloUbicacion, Transmision } from "@/api/transmision";
import { mensajeDeError, useNotificaciones } from "@/componentes/notificaciones";
import {
  Aviso,
  Boton,
  CampoArea,
  Campo,
  Confirmacion,
  Esqueleto,
  EtiquetaEstado,
  ListaEsqueleto,
  Modal,
  Tarjeta,
  Vacio,
  antiguedad,
  fechaLegible,
  fechaRelativa,
  useAhora,
} from "@/componentes/ui";
import type { Estado, EnvioResumen, LecturaGps, ParadaRuta, Ruta } from "@/tipos";

const Mapa = lazy(() => import("@/componentes/Mapa"));

export function Entregas() {
  const activa = useRutaActiva();

  if (activa.isPending) {
    return (
      <div className="pila">
        <Esqueleto alto="5rem" />
        <ListaEsqueleto filas={4} />
      </div>
    );
  }

  if (activa.isError) {
    return (
      <Tarjeta>
        <Vacio
          titulo="No se pudo saber si tiene una ruta abierta"
          descripcion={mensajeDeError(activa.error)}
          accion={
            <Boton variante="secundario" onClick={() => void activa.refetch()}>
              Reintentar
            </Boton>
          }
        />
      </Tarjeta>
    );
  }

  const { ruta, estados_aptos } = activa.data;
  return ruta ? <ModoRuta ruta={ruta} /> : <SeleccionDeGuias aptos={estados_aptos ?? []} />;
}

/* ====================================================================== */
/* Selección de guías                                                     */
/* ====================================================================== */

const MENSAJE_FALLO: Record<FalloUbicacion, { titulo: string; texto: string }> = {
  sin_permiso: {
    titulo: "La ubicación está bloqueada para este sitio",
    texto:
      "El modo ruta existe para compartir dónde va el vehículo, y sin ubicación no puede iniciarse. " +
      "Permítala en los ajustes del navegador para este sitio y vuelva a intentarlo. Mientras tanto, " +
      "puede registrar las entregas una a una desde Mis envíos.",
  },
  sin_gps: {
    titulo: "Todavía no hay señal GPS",
    texto: "Salga a cielo abierto un momento y vuelva a intentarlo.",
  },
  no_compatible: {
    titulo: "Este navegador no entrega la ubicación",
    texto: "Abra el sistema en el navegador del teléfono —Chrome o Safari— para salir a ruta.",
  },
};

function SeleccionDeGuias({ aptos }: { aptos: Estado[] }) {
  const { usuario } = useSesion();
  const { avisar } = useNotificaciones();
  const { data, isPending, error, refetch, isFetching } = useEnvios();
  const iniciar = useIniciarRuta();

  const [seleccion, setSeleccion] = useState<Set<string>>(new Set());
  const [busqueda, setBusqueda] = useState("");
  const [fallo, setFallo] = useState<FalloUbicacion | null>(null);
  const [localizando, setLocalizando] = useState(false);

  const conexionSegura = typeof window === "undefined" || window.isSecureContext;

  /* Una ruta solo lleva envíos de quien la conduce, lo diga o no el listado:
   * a quien ve toda la operación el servidor le devuelve los de todos. */
  const propios = useMemo(
    () => (data?.envios ?? []).filter((envio) => envio.conductor_sub === usuario?.sub),
    [data, usuario],
  );
  const coincide = useCallback(
    (envio: EnvioResumen) => {
      const termino = busqueda.trim().toLowerCase();
      if (!termino) return true;
      return [envio.destinatario, envio.destino, envio.ciudad_destino ?? "", envio.envio_id, envio.orden_compra ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(termino);
    },
    [busqueda],
  );

  const paraEntregar = propios.filter((envio) => aptos.includes(envio.estado));
  const porRecoger = propios.filter((envio) => envio.estado === "ASIGNADO");
  const detenidos = propios.filter((envio) => envio.estado === "INCIDENCIA");
  const visibles = paraEntregar.filter(coincide);

  const todosSeleccionados = visibles.length > 0 && visibles.every((e) => seleccion.has(e.envio_id));
  // Lo seleccionado que sigue siendo apto: si una guía cambió de estado por
  // otro lado, no debe colarse en la ruta desde una selección vieja.
  const elegidos = paraEntregar.filter((e) => seleccion.has(e.envio_id)).map((e) => e.envio_id);

  const alternar = (envioId: string) =>
    setSeleccion((previa) => {
      const nueva = new Set(previa);
      if (nueva.has(envioId)) nueva.delete(envioId);
      else nueva.add(envioId);
      return nueva;
    });

  const salir = async () => {
    setFallo(null);
    setLocalizando(true);
    const resultado = await leerUbicacion();
    setLocalizando(false);

    // Sin permiso no se sale: es lo único que el modo ruta no puede suplir.
    // Sin señal sí: la posición llega en cuanto el teléfono la consiga.
    if ("fallo" in resultado && resultado.fallo !== "sin_gps") {
      setFallo(resultado.fallo);
      return;
    }
    const ubicacion: LecturaGps | undefined = "lectura" in resultado ? resultado.lectura : undefined;

    try {
      const { ruta } = await iniciar.mutateAsync({ envios: elegidos, ubicacion });
      avisar(
        `Ruta iniciada con ${ruta.resumen.total} guía${ruta.resumen.total === 1 ? "" : "s"}. Su ubicación se está compartiendo.`,
        "exito",
      );
      setSeleccion(new Set());
    } catch {
      /* Se muestra junto al botón. */
    }
  };

  return (
    <>
      <header className="encabezado-pagina">
        <h1>Entregas</h1>
        <p className="encabezado-pagina__descripcion">
          Marque las guías que lleva en el vehículo y salga a ruta. Mientras la ruta esté abierta,
          la empresa ve dónde va y cada destinatario ve acercarse su paquete.
        </p>
      </header>

      {!conexionSegura && (
        <Aviso tono="alerta" titulo="La ubicación necesita una conexión segura">
          El navegador solo entrega el GPS a sitios abiertos con <span className="mono">https</span>.
          Abra el sistema por su dirección segura para salir a ruta.
        </Aviso>
      )}

      <Aviso tono="info" titulo="Qué se comparte y con quién">
        Su posición, solo mientras la ruta esté abierta. La empresa la ve en el mapa de
        seguimiento; el destinatario de cada envío en reparto ve la del vehículo, sin su nombre
        ni sus otras entregas. Al terminar la ruta, deja de compartirse.
      </Aviso>

      {error && <Aviso tono="error">{mensajeDeError(error)}</Aviso>}

      {isPending ? (
        <ListaEsqueleto filas={4} />
      ) : paraEntregar.length === 0 && porRecoger.length === 0 ? (
        <Tarjeta>
          <Vacio
            titulo="No tiene guías para entregar"
            descripcion="Cuando le asignen envíos y los recoja, aparecerán aquí para salir a ruta."
            accion={
              <Boton variante="secundario" onClick={() => void refetch()} cargando={isFetching}>
                Actualizar
              </Boton>
            }
          />
        </Tarjeta>
      ) : (
        <>
          {detenidos.length > 0 && (
            <Aviso tono="alerta" titulo={`${detenidos.length} detenido${detenidos.length === 1 ? "" : "s"} por incidencia`}>
              No pueden salir a ruta hasta que la empresa autorice continuar.
            </Aviso>
          )}

          <Tarjeta
            titulo={`Para entregar (${paraEntregar.length})`}
            ayuda="Las que ya tiene en su poder: recolectadas, en tránsito o en reparto."
            acciones={
              visibles.length > 0 ? (
                <Boton
                  variante="sutil"
                  onClick={() =>
                    setSeleccion(todosSeleccionados ? new Set() : new Set(visibles.map((e) => e.envio_id)))
                  }
                >
                  {todosSeleccionados ? "Quitar todas" : "Marcar todas"}
                </Boton>
              ) : undefined
            }
          >
            {paraEntregar.length > 4 && (
              <div style={{ marginBottom: "var(--e-3)" }}>
                <Campo
                  etiqueta="Buscar"
                  type="search"
                  placeholder="Destinatario, dirección o guía"
                  value={busqueda}
                  onChange={(evento) => setBusqueda(evento.target.value)}
                />
              </div>
            )}

            {paraEntregar.length === 0 ? (
              <Vacio
                titulo="Aún no tiene guías en su poder"
                descripcion="Marque como recogidas las de abajo cuando las tenga en el vehículo."
              />
            ) : visibles.length === 0 ? (
              <Vacio titulo="Ninguna guía coincide" descripcion="Pruebe con otro término." />
            ) : (
              <ul className="lista">
                {visibles.map((envio) => (
                  <li key={envio.envio_id}>
                    <label className={`envio envio--seleccionable estado-${envio.estado}`}>
                      <input
                        type="checkbox"
                        className="envio__casilla"
                        checked={seleccion.has(envio.envio_id)}
                        onChange={() => alternar(envio.envio_id)}
                      />
                      <span style={{ display: "grid", gap: "var(--e-1)", minWidth: 0 }}>
                        <span className="envio__linea">
                          <span className="envio__destinatario">{envio.destinatario}</span>
                          <EtiquetaEstado estado={envio.estado} codigo={envio.codigo_estado} />
                        </span>
                        <span className="envio__detalle">
                          {envio.destino}
                          {envio.ciudad_destino ? ` · ${envio.ciudad_destino}` : ""}
                        </span>
                        <span className="envio__id">{envio.envio_id}</span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
          </Tarjeta>

          {porRecoger.length > 0 && (
            <Tarjeta
              titulo={`Por recoger (${porRecoger.length})`}
              ayuda="Asignadas a usted pero todavía no en su poder. Márquelas al tenerlas en el vehículo."
            >
              <ul className="lista">
                {porRecoger.map((envio) => (
                  <li key={envio.envio_id}>
                    <FilaPorRecoger envio={envio} />
                  </li>
                ))}
              </ul>
            </Tarjeta>
          )}
        </>
      )}

      {fallo && (
        <Aviso tono={fallo === "sin_gps" ? "alerta" : "error"} titulo={MENSAJE_FALLO[fallo].titulo}>
          {MENSAJE_FALLO[fallo].texto}
        </Aviso>
      )}
      {iniciar.isError && (
        <Aviso tono="error" titulo="No se inició la ruta">
          {mensajeDeError(iniciar.error)}
        </Aviso>
      )}

      {elegidos.length > 0 && (
        <div className="barra-seleccion">
          <span className="texto-sm">
            <strong>{elegidos.length}</strong> guía{elegidos.length === 1 ? "" : "s"} para esta ruta
          </span>
          <div className="crece" />
          <Boton onClick={() => void salir()} cargando={localizando || iniciar.isPending} grande>
            {localizando ? "Buscando su ubicación…" : "Salir a ruta"}
          </Boton>
          <Boton variante="secundario" onClick={() => setSeleccion(new Set())}>
            Quitar
          </Boton>
        </div>
      )}
    </>
  );
}

function FilaPorRecoger({ envio }: { envio: EnvioResumen }) {
  const { avisar } = useNotificaciones();
  const registrar = useRegistrarEvento(envio.envio_id);

  const recoger = async () => {
    const resultado = await leerUbicacion({ enableHighAccuracy: true, timeout: 8_000, maximumAge: 30_000 });
    try {
      await registrar.mutateAsync({
        estado: "RECOLECTADO",
        ubicacion: "lectura" in resultado ? { lat: resultado.lectura.lat, lon: resultado.lectura.lon } : undefined,
      });
      avisar(`Recogido: ${envio.destinatario}.`, "exito");
    } catch (error) {
      avisar(mensajeDeError(error), "error");
    }
  };

  return (
    <div className={`envio estado-${envio.estado}`} style={{ cursor: "default" }}>
      <span className="envio__linea">
        <span className="envio__destinatario">{envio.destinatario}</span>
        <Boton variante="secundario" onClick={() => void recoger()} cargando={registrar.isPending}>
          Recogido
        </Boton>
      </span>
      <span className="envio__detalle">
        {envio.destino}
        {envio.ciudad_destino ? ` · ${envio.ciudad_destino}` : ""}
      </span>
      <span className="envio__id">{envio.envio_id}</span>
    </div>
  );
}

/* ====================================================================== */
/* Modo ruta                                                              */
/* ====================================================================== */

function ModoRuta({ ruta }: { ruta: Ruta }) {
  const cliente = useQueryClient();
  const { avisar } = useNotificaciones();
  const esFinal = useEstadosFinales();
  const finalizar = useFinalizarRuta();

  const alTerminar = useCallback(() => {
    void cliente.invalidateQueries({ queryKey: claves.rutaActiva });
  }, [cliente]);
  const transmision = useTransmisionDeUbicacion(ruta.ruta_id, alTerminar);
  const pantalla = usePantallaEncendida(true);

  const [confirmarCierre, setConfirmarCierre] = useState(false);
  const [entregando, setEntregando] = useState<ParadaRuta | null>(null);
  const [reportando, setReportando] = useState<ParadaRuta | null>(null);

  const abiertas = ruta.paradas.filter((p) => !esFinal(p.estado));
  const cerradas = ruta.paradas.filter((p) => esFinal(p.estado));
  const { resumen } = ruta;
  const avance = resumen.total ? Math.round((resumen.cerradas / resumen.total) * 100) : 0;

  const terminar = async () => {
    try {
      await finalizar.mutateAsync({ rutaId: ruta.ruta_id });
      setConfirmarCierre(false);
      avisar("Ruta terminada. Su ubicación dejó de compartirse.", "exito");
    } catch (error) {
      avisar(mensajeDeError(error), "error");
    }
  };

  const ubicacionActual = transmision.posicion
    ? { lat: transmision.posicion.lat, lon: transmision.posicion.lon }
    : undefined;

  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <div className="min-cero">
            <h1>Ruta en curso</h1>
            <p className="encabezado-pagina__descripcion">
              Salió {fechaRelativa(ruta.iniciada_en)} · paradas cerradas: {resumen.cerradas} de{" "}
              {resumen.total}
            </p>
          </div>
          <Boton
            variante="secundario"
            onClick={() => (abiertas.length ? setConfirmarCierre(true) : void terminar())}
            cargando={finalizar.isPending}
          >
            Terminar ruta
          </Boton>
        </div>
        <div
          className="avance"
          role="progressbar"
          aria-label="Paradas cerradas"
          aria-valuemin={0}
          aria-valuemax={resumen.total}
          aria-valuenow={resumen.cerradas}
        >
          <span className="avance__barra" style={{ width: `${avance}%` }} />
        </div>
      </header>

      <div className="modo-ruta">
        <div className="modo-ruta__mapa pila-sm">
          <EstadoDeTransmision transmision={transmision} />
          <PosicionPropia transmision={transmision} />
          {(pantalla === "no_compatible" || pantalla === "rechazada") && (
            <p className="texto-xs texto-tenue">
              Mantenga la pantalla encendida: con la pantalla apagada, el teléfono deja de enviar su
              ubicación.
            </p>
          )}
          {pantalla === "encendida" && (
            <p className="texto-xs texto-tenue">
              La pantalla se mantiene encendida mientras la ruta está abierta.
            </p>
          )}
        </div>

        <div className="modo-ruta__paradas pila-sm">
          {abiertas.length === 0 ? (
            <Aviso
              tono="exito"
              titulo="Todas las paradas están cerradas"
              acciones={
                <Boton onClick={() => void terminar()} cargando={finalizar.isPending}>
                  Terminar ruta
                </Boton>
              }
            >
              Termine la ruta para dejar de compartir su ubicación.
            </Aviso>
          ) : (
            <h2 className="texto-sm texto-suave" style={{ margin: 0 }}>
              {abiertas.length} parada{abiertas.length === 1 ? "" : "s"} pendiente
              {abiertas.length === 1 ? "" : "s"}
            </h2>
          )}

          <ol className="lista">
            {abiertas.map((parada) => (
              <li key={parada.envio_id}>
                <TarjetaParada
                  parada={parada}
                  onEntregar={() => setEntregando(parada)}
                  onReportar={() => setReportando(parada)}
                />
              </li>
            ))}
          </ol>

          {cerradas.length > 0 && (
            <details className="plegable">
              <summary className="plegable__resumen">
                Cerradas ({cerradas.length})
              </summary>
              <ol className="lista" style={{ marginTop: "var(--e-2)" }}>
                {cerradas.map((parada) => (
                  <li key={parada.envio_id}>
                    <TarjetaParada parada={parada} />
                  </li>
                ))}
              </ol>
            </details>
          )}
        </div>
      </div>

      {entregando && (
        <ModalEntrega
          parada={entregando}
          ubicacion={ubicacionActual}
          onCerrar={() => setEntregando(null)}
        />
      )}
      {reportando && (
        <ModalNovedad
          parada={reportando}
          ubicacion={ubicacionActual}
          onCerrar={() => setReportando(null)}
        />
      )}

      <Confirmacion
        abierto={confirmarCierre}
        titulo="¿Terminar la ruta?"
        descripcion={`Paradas sin cerrar: ${abiertas.length}. Conservan su estado, y las que sigan en reparto podrá llevarlas en otra ruta. La empresa y los destinatarios dejarán de ver su ubicación.`}
        textoConfirmar="Terminar ruta"
        cargando={finalizar.isPending}
        onConfirmar={() => void terminar()}
        onCancelar={() => setConfirmarCierre(false)}
      />
    </>
  );
}

/* ---------------------------------------------------------------------- */

const TEXTO_TRANSMISION: Record<Transmision["estado"], string> = {
  preparando: "Buscando señal GPS…",
  transmitiendo: "Compartiendo su ubicación",
  sin_permiso: "Ubicación bloqueada: permítala para este sitio en los ajustes del navegador",
  sin_gps: "Sin señal GPS. Se reintenta sola",
  no_compatible: "Este navegador no entrega la ubicación",
  detenida: "La ruta terminó: ya no se comparte su ubicación",
};

function EstadoDeTransmision({ transmision }: { transmision: Transmision }) {
  const ahora = useAhora(5_000);
  const { estado, ultimoEnvio, pendientes, sinConexion, posicion } = transmision;

  const tono =
    estado === "transmitiendo" && !sinConexion
      ? "exito"
      : estado === "sin_permiso" || estado === "no_compatible"
        ? "peligro"
        : "alerta";

  const detalle: string[] = [];
  if (estado === "transmitiendo") {
    if (ultimoEnvio) detalle.push(`enviada ${antiguedad((ahora - ultimoEnvio) / 1000)}`);
    if (posicion?.precision_m) detalle.push(`±${Math.round(posicion.precision_m)} m`);
  }
  if (sinConexion) detalle.push(`sin conexión: ${pendientes} posición${pendientes === 1 ? "" : "es"} en espera`);

  return (
    <div className={`senal senal--${tono}`} role="status" aria-live="polite">
      <span className="senal__punto" aria-hidden="true" />
      <span className="min-cero">
        <span className="senal__texto">{TEXTO_TRANSMISION[estado]}</span>
        {detalle.length > 0 && <span className="senal__detalle">{detalle.join(" · ")}</span>}
      </span>
    </div>
  );
}

function PosicionPropia({ transmision }: { transmision: Transmision }) {
  const { posicion, recorrido } = transmision;
  const marcadores = useMemo(
    () =>
      posicion
        ? [
            {
              id: "yo",
              lat: posicion.lat,
              lon: posicion.lon,
              titulo: "Su posición",
              precision: posicion.precision_m,
              pulso: true,
            },
          ]
        : [],
    [posicion],
  );
  const trazos = useMemo(() => [{ id: "recorrido", puntos: recorrido }], [recorrido]);

  if (!posicion) {
    return (
      <div className="mapa mapa--vacio" aria-hidden="true">
        <span className="texto-sm texto-suave">El mapa aparece con la primera lectura del GPS.</span>
      </div>
    );
  }

  return (
    <Suspense fallback={<Esqueleto alto="100%" />}>
      <Mapa marcadores={marcadores} trazos={trazos} seguir="yo" etiqueta="Mapa con su posición y su recorrido" />
    </Suspense>
  );
}

/* ---------------------------------------------------------------------- */

/* «Cómo llegar» abre el navegador de mapas que el conductor ya usa. La
 * dirección sale del sistema solo cuando él lo pulsa, hacia la aplicación que
 * él elige: el sistema no geocodifica direcciones ni se las envía a nadie por
 * su cuenta (ADR-013). */
function enlaceComoLlegar(parada: ParadaRuta): string {
  const destino = [parada.direccion, parada.ciudad].filter(Boolean).join(", ");
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(destino)}`;
}

function TarjetaParada({
  parada,
  onEntregar,
  onReportar,
}: {
  parada: ParadaRuta;
  onEntregar?: () => void;
  onReportar?: () => void;
}) {
  const enReparto = parada.estado === "EN_REPARTO";

  return (
    <article className={`parada estado-${parada.estado}`}>
      <header className="parada__cabecera">
        <span className="parada__orden" aria-label={`Parada ${parada.orden}`}>
          {parada.orden}
        </span>
        <div className="min-cero crece">
          <h3 className="parada__destinatario">{parada.destinatario}</h3>
          <p className="parada__direccion">
            {parada.direccion}
            {parada.referencia ? ` · ${parada.referencia}` : ""}
            {parada.ciudad ? ` · ${parada.ciudad}` : ""}
          </p>
        </div>
        <EtiquetaEstado estado={parada.estado} codigo={parada.codigo_estado} />
      </header>

      {(parada.descripcion || parada.orden_compra || parada.bultos > 1) && (
        <p className="texto-xs texto-tenue romper-todo" style={{ margin: 0 }}>
          {[
            parada.bultos > 1 ? `${parada.bultos} bultos` : "",
            parada.descripcion,
            parada.orden_compra ? `OC ${parada.orden_compra}` : "",
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
      )}

      {parada.estado === "INCIDENCIA" && (
        <p className="texto-xs" style={{ margin: 0 }}>
          Detenida por una novedad. Continuarla lo autoriza la empresa.
        </p>
      )}
      {parada.estado === "ENTREGADO" && (
        <p className="texto-xs texto-tenue" style={{ margin: 0 }}>
          Entregada {fechaLegible(parada.actualizada_en)}
        </p>
      )}

      {(onEntregar || onReportar) && (
        <div className="parada__acciones">
          {parada.telefono && (
            <a className="boton boton--secundario" href={`tel:${parada.telefono}`}>
              Llamar
            </a>
          )}
          <a className="boton boton--secundario" href={enlaceComoLlegar(parada)} target="_blank" rel="noreferrer">
            Cómo llegar
          </a>
          <Link className="boton boton--sutil" to={`/envios/${parada.envio_id}`}>
            Detalle
          </Link>
          {enReparto && onReportar && (
            <Boton variante="secundario" onClick={onReportar}>
              Novedad
            </Boton>
          )}
          {enReparto && onEntregar && <Boton onClick={onEntregar}>Entregar</Boton>}
        </div>
      )}
    </article>
  );
}

/* ---------------------------------------------------------------------- */
/* Entrega y novedad                                                      */
/* ---------------------------------------------------------------------- */

const PASOS_EVIDENCIA: { fase: FaseEvidencia; texto: string }[] = [
  { fase: "solicitando", texto: "Pedir el enlace de carga" },
  { fase: "cargando", texto: "Subir la foto" },
  { fase: "confirmando", texto: "Confirmar que quedó guardada" },
];

function ModalEntrega({
  parada,
  ubicacion,
  onCerrar,
}: {
  parada: ParadaRuta;
  ubicacion?: { lat: number; lon: number };
  onCerrar: () => void;
}) {
  const { avisar } = useNotificaciones();
  const carga = useCargaDeEvidencia(parada.envio_id);
  const registrar = useRegistrarEvento(parada.envio_id);

  const [archivo, setArchivo] = useState<File | null>(null);
  const [fase, setFase] = useState<FaseEvidencia>("inactiva");
  const [nota, setNota] = useState("");
  // Si la foto ya subió y lo que falló fue el registro, reintentar no debe
  // volver a subirla: se conserva la evidencia confirmada.
  const [evidenciaId, setEvidenciaId] = useState<string | null>(null);

  const vistaPrevia = useMemo(() => (archivo ? URL.createObjectURL(archivo) : null), [archivo]);
  useEffect(() => () => void (vistaPrevia && URL.revokeObjectURL(vistaPrevia)), [vistaPrevia]);
  const ocupado = carga.isPending || registrar.isPending;

  const confirmar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    try {
      let evidencia = evidenciaId;
      if (!evidencia) {
        if (!archivo) return;
        const resultado = await carga.mutateAsync({ archivo, alCambiarFase: setFase });
        evidencia = resultado.evidencia_id;
        setEvidenciaId(evidencia);
      }
      await registrar.mutateAsync({
        estado: "ENTREGADO",
        evidencia_id: evidencia,
        nota: nota.trim() || undefined,
        ubicacion,
      });
      avisar(`Entregado a ${parada.destinatario}.`, "exito");
      onCerrar();
    } catch {
      setFase("inactiva");
    }
  };

  const indiceFase = PASOS_EVIDENCIA.findIndex((paso) => paso.fase === fase);

  return (
    <Modal titulo={`Entregar a ${parada.destinatario}`} abierto onCerrar={ocupado ? () => undefined : onCerrar}>
      <div className="tarjeta__cabecera">
        <div className="min-cero">
          <h2 className="tarjeta__titulo">Entregar a {parada.destinatario}</h2>
          <p className="tarjeta__ayuda">{parada.direccion}</p>
        </div>
      </div>
      <form className="tarjeta__cuerpo pila-sm" onSubmit={confirmar}>
        {evidenciaId ? (
          <Aviso tono="exito">La foto ya está guardada. Falta registrar la entrega.</Aviso>
        ) : (
          <Campo
            etiqueta="Foto de la entrega"
            type="file"
            accept="image/*"
            capture="environment"
            required
            onChange={(evento) => setArchivo(evento.target.files?.[0] ?? null)}
            ayuda="Sin foto no se puede dar por entregado. Va cifrada al almacenamiento."
          />
        )}
        {vistaPrevia && !evidenciaId && (
          <img className="vista-previa" src={vistaPrevia} alt="Vista previa de la foto de entrega" />
        )}

        <CampoArea
          etiqueta="Nota"
          opcional
          rows={2}
          placeholder="Recibió en portería"
          value={nota}
          onChange={(evento) => setNota(evento.target.value)}
        />

        {carga.isPending && (
          <ol className="pasos-carga">
            {PASOS_EVIDENCIA.map((paso, indice) => (
              <li
                key={paso.fase}
                className="paso-carga"
                data-estado={indice < indiceFase ? "hecho" : indice === indiceFase ? "activo" : "pendiente"}
              >
                <span className="paso-carga__marca" aria-hidden="true">
                  {indice < indiceFase ? "✓" : indice + 1}
                </span>
                {paso.texto}
              </li>
            ))}
          </ol>
        )}

        {carga.isError && <Aviso tono="error" titulo="La foto no se guardó">{mensajeDeError(carga.error)}</Aviso>}
        {registrar.isError && (
          <Aviso tono="error" titulo="La entrega no se registró">
            {mensajeDeError(registrar.error)}
          </Aviso>
        )}
        {!ubicacion && (
          <p className="texto-xs texto-tenue">
            Sin lectura de GPS en este momento: la entrega se registra sin coordenadas.
          </p>
        )}

        <div className="acciones">
          <Boton type="submit" grande cargando={ocupado} disabled={!archivo && !evidenciaId}>
            Confirmar entrega
          </Boton>
          <Boton type="button" variante="secundario" onClick={onCerrar} disabled={ocupado}>
            Cancelar
          </Boton>
        </div>
      </form>
    </Modal>
  );
}

function ModalNovedad({
  parada,
  ubicacion,
  onCerrar,
}: {
  parada: ParadaRuta;
  ubicacion?: { lat: number; lon: number };
  onCerrar: () => void;
}) {
  const { avisar } = useNotificaciones();
  const registrar = useRegistrarEvento(parada.envio_id);
  const [nota, setNota] = useState("");

  const reportar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    try {
      await registrar.mutateAsync({ estado: "INCIDENCIA", nota: nota.trim(), ubicacion });
      avisar("Novedad reportada. La empresa decide cómo continuar.", "exito");
      onCerrar();
    } catch {
      /* Se muestra en el formulario. */
    }
  };

  return (
    <Modal
      titulo={`Novedad con ${parada.destinatario}`}
      abierto
      onCerrar={registrar.isPending ? () => undefined : onCerrar}
    >
      <div className="tarjeta__cabecera">
        <div className="min-cero">
          <h2 className="tarjeta__titulo">Novedad con {parada.destinatario}</h2>
          <p className="tarjeta__ayuda">
            La parada queda detenida. Continuarla o devolver el paquete lo decide la empresa.
          </p>
        </div>
      </div>
      <form className="tarjeta__cuerpo pila-sm" onSubmit={reportar}>
        <CampoArea
          etiqueta="¿Qué pasó?"
          rows={3}
          required
          minLength={3}
          maxLength={300}
          placeholder="Nadie atiende en la dirección"
          value={nota}
          onChange={(evento) => setNota(evento.target.value)}
        />
        {registrar.isError && (
          <Aviso tono="error" titulo="La novedad no se registró">
            {mensajeDeError(registrar.error)}
          </Aviso>
        )}
        <div className="acciones">
          <Boton type="submit" variante="peligro" cargando={registrar.isPending} disabled={nota.trim().length < 3}>
            Reportar novedad
          </Boton>
          <Boton type="button" variante="secundario" onClick={onCerrar} disabled={registrar.isPending}>
            Cancelar
          </Boton>
        </div>
      </form>
    </Modal>
  );
}
