/* Detalle del envío: histórico, punto de control, asignación y evidencia.
 *
 * Las acciones que se muestran salen de lo que el servidor dice que es posible
 * (`/transiciones`) y no de una copia de la máquina de estados escrita aquí.
 * Duplicar esa lógica en el cliente crearía dos fuentes de verdad, y la del
 * cliente se quedaría atrás sin que nadie lo notara hasta ver un rechazo
 * inexplicable.
 */

import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import {
  useAsignarConductor,
  useCargaDeEvidencia,
  useEnvio,
  useEvidencias,
  useMensajeros,
  useRegistrarEvento,
  useTransiciones,
} from "@/api/consultas";
import type { FaseEvidencia } from "@/api/consultas";
import { useSesion } from "@/api/sesion";
import { mensajeDeError, useNotificaciones } from "@/componentes/notificaciones";
import {
  Aviso,
  Boton,
  BotonCopiar,
  Campo,
  CampoArea,
  Esqueleto,
  EtiquetaEstado,
  Tarjeta,
  Vacio,
  fechaLegible,
  fechaRelativa,
  textoEstado,
} from "@/componentes/ui";
import type { Estado, Evento, TransicionDetalle, Ubicacion } from "@/tipos";

export function EnvioDetalle() {
  const { envioId = "" } = useParams();
  const ubicacion = useLocation();
  const recienCreado = (ubicacion.state as { recienCreado?: boolean } | null)?.recienCreado;

  const { puede } = useSesion();
  const detalle = useEnvio(envioId);
  const transiciones = useTransiciones(envioId);
  const evidencias = useEvidencias(envioId, puede("evidencia:descargar"));

  if (detalle.isPending) {
    return (
      <div className="pila">
        <Esqueleto alto="8rem" />
        <Esqueleto alto="20rem" />
      </div>
    );
  }

  if (detalle.isError) {
    return (
      <Tarjeta>
        <Vacio
          titulo="No se pudo abrir el envío"
          descripcion={mensajeDeError(detalle.error)}
          accion={
            <Link to="/envios" className="boton boton--secundario">
              Volver a la lista
            </Link>
          }
        />
      </Tarjeta>
    );
  }

  const { envio, eventos } = detalle.data;
  const puedeRegistrar = (transiciones.data?.transiciones.length ?? 0) > 0;
  const exigeDespachador = transiciones.data?.exige_autorizacion_despachador ?? false;

  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <div className="min-cero">
            <h1>{envio.destinatario.nombre}</h1>
            <p className="texto-sm texto-suave">
              {envio.destino.linea}
              {envio.destino.referencia ? ` · ${envio.destino.referencia}` : ""} ·{" "}
              {envio.destino.ciudad}
            </p>
          </div>
          <EtiquetaEstado estado={envio.estado} codigo={envio.codigo_estado} conPunto />
        </div>
      </header>

      {recienCreado && (
        <Aviso tono="exito" titulo="Envío registrado">
          Entregue este identificador al destinatario: es lo único que necesita para consultar el
          avance, y no puede deducirse.
        </Aviso>
      )}

      <div className="doble-panel">
        <div className="pila">
          <Tarjeta
            titulo="Identificador de rastreo"
            ayuda="Aleatorio y no consecutivo, para que nadie pueda recorrer los envíos de la empresa desde el punto público."
            acciones={
              <>
                <BotonCopiar texto={envio.envio_id} />
                {puede("envio:asignar") && (
                  <Link
                    to="/envios/guias"
                    state={{ envios: [envio.envio_id] }}
                    className="boton boton--secundario"
                  >
                    Generar guía
                  </Link>
                )}
              </>
            }
          >
            <p className="mono" style={{ fontSize: "var(--t-base)" }}>
              {envio.envio_id}
            </p>
            <p className="texto-xs texto-tenue" style={{ marginTop: "var(--e-2)" }}>
              <a href={`/rastreo?envio=${envio.envio_id}`} target="_blank" rel="noreferrer">
                Ver como lo ve el destinatario
              </a>
            </p>
          </Tarjeta>

          <Tarjeta
            titulo="Histórico"
            ayuda={`${eventos.length} punto${eventos.length === 1 ? "" : "s"} de control, cada uno atribuido a un responsable.`}
          >
            <LineaDeTiempo eventos={eventos} />
          </Tarjeta>

          <Tarjeta titulo="Datos del envío">
            <dl className="pila-sm" style={{ margin: 0 }}>
              <Dato termino="Origen" valor={`${envio.origen.linea}${envio.origen.referencia ? ` · ${envio.origen.referencia}` : ""}`} />
              <Dato termino="Destino" valor={`${envio.destino.linea}${envio.destino.referencia ? ` · ${envio.destino.referencia}` : ""}`} />
              <Dato termino="Destinatario" valor={`${envio.destinatario.nombre}${envio.destinatario.telefono ? ` · ${envio.destinatario.telefono}` : ""}`} />
              <Dato termino="Mensajero" valor={envio.conductor_nombre || "sin asignar"} />
              <Dato termino="Cliente" valor={envio.cliente_nombre || "—"} />
              <Dato termino="Tienda de origen" valor={envio.tienda_nombre || "—"} />
              <Dato termino="Estación actual" valor={envio.estacion_actual || "—"} />
              <Dato termino="Transportista" valor={envio.transportista_nombre || "por asignar"} />
              <Dato termino="Orden de compra" valor={envio.orden_compra || "—"} />
              <Dato
                termino="Carga"
                valor={`${envio.bultos ?? 1} bulto${(envio.bultos ?? 1) === 1 ? "" : "s"}${
                  envio.peso_kg ? ` · ${envio.peso_kg} kg` : ""
                }`}
              />
              <Dato termino="Entrega estimada" valor={envio.fecha_estimada || "sin fecha comprometida"} />
              <Dato termino="Descripción" valor={envio.descripcion || "—"} />
              <Dato termino="Registrado" valor={`${fechaLegible(envio.creado_en)} por ${envio.creado_por}`} />
            </dl>
          </Tarjeta>
        </div>

        <div className="pila">
          {exigeDespachador && (
            <Aviso tono="alerta" titulo="Envío detenido por una incidencia">
              Reanudarlo requiere autorización del despachador. El conductor reporta el incidente;
              otro rol decide si continúa.
            </Aviso>
          )}

          {envio.estado === "CREADO" && puede("envio:asignar") && (
            <PanelAsignacion envioId={envioId} />
          )}

          {puede("evento:registrar") && envio.estado !== "ENTREGADO" && (
            <PanelEvidencia envioId={envioId} evidenciasConfirmadas={envio.evidencias ?? []} />
          )}

          {puedeRegistrar ? (
            <PanelPuntoDeControl
              envioId={envioId}
              transiciones={transiciones.data?.detalle_transiciones ?? []}
              evidenciasConfirmadas={envio.evidencias ?? []}
            />
          ) : (
            <Tarjeta>
              <Vacio
                titulo={envio.estado === "ENTREGADO" ? "Envío entregado" : "Sin acciones disponibles"}
                descripcion={
                  envio.estado === "ENTREGADO"
                    ? "El estado ENTREGADO es final: el envío no admite más cambios."
                    : "Su rol no puede registrar puntos de control en este envío."
                }
              />
            </Tarjeta>
          )}

          {puede("evidencia:descargar") && (
            <Tarjeta
              titulo="Evidencias de entrega"
              ayuda="Almacenadas cifradas. El conductor las carga; consultarlas corresponde a otros roles."
            >
              {evidencias.isPending ? (
                <Esqueleto alto="4rem" />
              ) : evidencias.data?.evidencias.length ? (
                <ul className="lista">
                  {evidencias.data.evidencias.map((evidencia) => (
                    <li key={evidencia.evidencia_id} className="envio">
                      <span className="envio__linea">
                        <span className="texto-sm" style={{ fontWeight: 600 }}>
                          {evidencia.propiedades.cifrado ?? "sin cifrado declarado"}
                        </span>
                        <a href={evidencia.url_descarga} target="_blank" rel="noreferrer" className="texto-sm">
                          Abrir
                        </a>
                      </span>
                      <span className="envio__id">{evidencia.propiedades.clave}</span>
                      <span className="texto-xs texto-tenue">
                        {evidencia.propiedades.tamano ?? 0} bytes
                        {evidencia.propiedades.version_id ? ` · versión ${evidencia.propiedades.version_id.slice(0, 8)}` : ""}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <Vacio titulo="Sin evidencias" descripcion="Se cargan al momento de la entrega." />
              )}
            </Tarjeta>
          )}
        </div>
      </div>
    </>
  );
}

/* ---------------------------------------------------------------------- */

function Dato({ termino, valor }: { termino: string; valor: string }) {
  return (
    <div>
      <dt className="texto-xs texto-tenue" style={{ textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 700 }}>
        {termino}
      </dt>
      <dd style={{ margin: 0 }} className="texto-sm romper-todo">
        {valor}
      </dd>
    </div>
  );
}

function LineaDeTiempo({ eventos }: { eventos: Evento[] }) {
  if (eventos.length === 0) {
    return <Vacio titulo="Sin eventos" descripcion="El histórico se llena al registrar puntos de control." />;
  }

  return (
    <ol className="linea">
      {eventos.map((evento) => (
        <li key={evento.evento_id} className={`linea__paso estado-${evento.estado}`}>
          <span className="linea__estado">
            <span className="codigo-estado">{evento.codigo_estado ?? ""}</span>{" "}
            {textoEstado(evento.estado)}
          </span>
          <span className="linea__meta">
            {fechaLegible(evento.ts)} · {fechaRelativa(evento.ts)}
          </span>
          <span className="linea__meta">
            por {evento.actor_sub}
            {evento.actor_grupos?.length ? ` (${evento.actor_grupos.join(", ")})` : ""}
          </span>
          {evento.nota && <p className="linea__nota">{evento.nota}</p>}
          {evento.ubicacion && (
            <span className="linea__meta mono">
              {evento.ubicacion.lat.toFixed(5)}, {evento.ubicacion.lon.toFixed(5)}
            </span>
          )}
          {evento.evidencia_id && <span className="linea__meta">Con evidencia adjunta</span>}
        </li>
      ))}
    </ol>
  );
}

/* ---------------------------------------------------------------------- */
/* Asignación                                                             */
/* ---------------------------------------------------------------------- */

function PanelAsignacion({ envioId }: { envioId: string }) {
  const { avisar } = useNotificaciones();
  const asignar = useAsignarConductor(envioId);
  /* Los mensajeros salen del directorio de la organización. Antes había tres
   * escritos aquí con su identificador: el día que entrara uno nuevo, nadie iba
   * a recompilar el sitio para que apareciera, y los de la otra empresa se veían
   * igual aunque asignarlos fuera imposible. */
  const { data: equipo, isPending, error } = useMensajeros();
  const [sub, setSub] = useState("");
  const [nombre, setNombre] = useState("");

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    try {
      await asignar.mutateAsync({ conductor_sub: sub.trim(), conductor_nombre: nombre.trim() });
      avisar("Mensajero asignado.", "exito");
    } catch {
      /* Se muestra bajo el formulario. */
    }
  };

  const mensajeros = equipo?.mensajeros ?? [];

  return (
    <Tarjeta titulo="Asignar mensajero" ayuda="Transición CREADO → ASIGNADO. La valida la máquina de estados.">
      <form onSubmit={enviar} className="pila-sm">
        {isPending && <p className="texto-sm texto-suave">Cargando mensajeros…</p>}

        {error ? (
          <Aviso tono="alerta">
            No fue posible leer el equipo. Puede escribir el identificador del mensajero a mano.
          </Aviso>
        ) : null}

        {!isPending && !error && mensajeros.length === 0 && (
          <Aviso tono="alerta" titulo="La empresa no tiene mensajeros activos">
            Cree una cuenta con el rol <strong>conductor</strong> en Administración antes de
            asignar. Sin conductor, el envío no puede salir de CREADO.
          </Aviso>
        )}

        {mensajeros.length > 0 && (
          <div className="fila">
            {mensajeros.map((mensajero) => (
              <Boton
                key={mensajero.sub}
                type="button"
                variante={sub === mensajero.sub ? "primario" : "secundario"}
                onClick={() => {
                  setSub(mensajero.sub);
                  setNombre(mensajero.nombre);
                }}
              >
                {mensajero.nombre}
              </Boton>
            ))}
          </div>
        )}

        <Campo
          etiqueta="Identificador del mensajero"
          required
          value={sub}
          onChange={(evento) => setSub(evento.target.value)}
          ayuda="Se rellena al elegir arriba. Debe coincidir con el sujeto del token del conductor."
        />
        <Campo
          etiqueta="Nombre"
          value={nombre}
          onChange={(evento) => setNombre(evento.target.value)}
        />

        {asignar.isError && <Aviso tono="error">{mensajeDeError(asignar.error)}</Aviso>}

        <div className="acciones">
          <Boton type="submit" cargando={asignar.isPending} disabled={!sub.trim()}>
            Asignar
          </Boton>
        </div>
      </form>
    </Tarjeta>
  );
}

/* ---------------------------------------------------------------------- */
/* Evidencia                                                              */
/* ---------------------------------------------------------------------- */

const PASOS: { fase: FaseEvidencia; texto: string }[] = [
  { fase: "solicitando", texto: "Solicitar enlace prefirmado" },
  { fase: "cargando", texto: "Cargar el archivo al almacenamiento" },
  { fase: "confirmando", texto: "Confirmar que quedó almacenado" },
];

function PanelEvidencia({
  envioId,
  evidenciasConfirmadas,
}: {
  envioId: string;
  evidenciasConfirmadas: string[];
}) {
  const { avisar } = useNotificaciones();
  const [archivo, setArchivo] = useState<File | null>(null);
  const [fase, setFase] = useState<FaseEvidencia>("inactiva");
  const carga = useCargaDeEvidencia(envioId);

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!archivo) return;
    try {
      const resultado = await carga.mutateAsync({ archivo, alCambiarFase: setFase });
      avisar(
        `Evidencia almacenada (${resultado.propiedades.cifrado ?? "sin KMS en entorno local"}). Ya puede registrar la entrega.`,
        "exito",
      );
      setArchivo(null);
    } catch {
      setFase("inactiva");
    }
  };

  const indiceFase = PASOS.findIndex((paso) => paso.fase === fase);

  return (
    <Tarjeta
      titulo="Evidencia de entrega"
      ayuda="El archivo va directo al almacenamiento con un enlace de vigencia limitada: no atraviesa los servicios."
    >
      {evidenciasConfirmadas.length > 0 && (
        <div style={{ marginBottom: "var(--e-3)" }}>
          <Aviso tono="exito">
            {evidenciasConfirmadas.length} evidencia
            {evidenciasConfirmadas.length === 1 ? "" : "s"} confirmada
            {evidenciasConfirmadas.length === 1 ? "" : "s"}. Ya puede registrar la entrega.
          </Aviso>
        </div>
      )}

      <form onSubmit={enviar} className="pila-sm">
        <Campo
          etiqueta="Foto de la entrega"
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(evento) => setArchivo(evento.target.files?.[0] ?? null)}
          ayuda="Se abre la cámara trasera en el teléfono."
        />

        {carga.isPending && (
          <ol className="pasos-carga">
            {PASOS.map((paso, indice) => (
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

        {carga.isError && (
          <Aviso tono="error" titulo="La evidencia no se guardó">
            {mensajeDeError(carga.error)}
          </Aviso>
        )}

        <div className="acciones">
          <Boton type="submit" variante="secundario" disabled={!archivo} cargando={carga.isPending} bloque>
            Cargar evidencia
          </Boton>
        </div>
      </form>
    </Tarjeta>
  );
}

/* ---------------------------------------------------------------------- */
/* Punto de control                                                       */
/* ---------------------------------------------------------------------- */

function PanelPuntoDeControl({
  envioId,
  transiciones,
  evidenciasConfirmadas,
}: {
  envioId: string;
  transiciones: TransicionDetalle[];
  evidenciasConfirmadas: string[];
}) {
  const { avisar } = useNotificaciones();
  const registrar = useRegistrarEvento(envioId);

  const [estado, setEstado] = useState<Estado | null>(transiciones[0]?.estado ?? null);
  const [nota, setNota] = useState("");
  const [adjuntarUbicacion, setAdjuntarUbicacion] = useState(true);

  const exigeEvidencia = estado === "ENTREGADO";
  const faltaEvidencia = exigeEvidencia && evidenciasConfirmadas.length === 0;

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!estado) return;

    let ubicacion: Ubicacion | undefined;
    if (adjuntarUbicacion) {
      ubicacion = await obtenerUbicacion();
      if (!ubicacion) {
        avisar("No se obtuvo la ubicación; el punto de control se registra sin ella.", "alerta");
      }
    }

    try {
      await registrar.mutateAsync({
        estado,
        nota: nota.trim() || undefined,
        ubicacion,
        evidencia_id: exigeEvidencia ? evidenciasConfirmadas.at(-1) : undefined,
      });
      avisar(`Punto de control registrado: ${textoEstado(estado)}.`, "exito");
      setNota("");
    } catch {
      /* Se muestra bajo el formulario. */
    }
  };

  return (
    <Tarjeta
      titulo="Registrar punto de control"
      ayuda="Un solo formulario y ningún campo obligatorio más allá del estado. La marca de tiempo la pone el servidor."
    >
      <form onSubmit={enviar} className="pila-sm">
        <div className="campo">
          <span className="campo__etiqueta" id="etiqueta-estado">
            Nuevo estado
          </span>
          <div className="selector-estado" role="group" aria-labelledby="etiqueta-estado">
            {transiciones.map((destino) => (
              <button
                key={destino.estado}
                type="button"
                className={`opcion-estado estado-${destino.estado}`}
                aria-pressed={estado === destino.estado}
                onClick={() => setEstado(destino.estado)}
              >
                <span className="punto-estado" aria-hidden="true" />
                <span className="min-cero">
                  <span style={{ display: "block" }}>
                    <span className="codigo-estado">{destino.codigo}</span> {destino.etiqueta}
                  </span>
                  {destino.final && (
                    <span className="campo__ayuda" style={{ display: "block" }}>
                      Cierra el envío: no admite más cambios
                    </span>
                  )}
                </span>
              </button>
            ))}
          </div>
          <span className="campo__ayuda">
            Solo se ofrecen los estados alcanzables desde el actual. El servidor los vuelve a
            comprobar.
          </span>
        </div>

        <CampoArea
          etiqueta="Nota"
          opcional
          rows={2}
          placeholder="Recibido en portería"
          value={nota}
          onChange={(evento) => setNota(evento.target.value)}
        />

        <label className="casilla">
          <input
            type="checkbox"
            checked={adjuntarUbicacion}
            onChange={(evento) => setAdjuntarUbicacion(evento.target.checked)}
          />
          <span className="casilla__texto">
            Adjuntar mi ubicación
            <span className="campo__ayuda" style={{ display: "block" }}>
              Se captura solo en este momento. El sistema no hace seguimiento continuo.
            </span>
          </span>
        </label>

        {faltaEvidencia && (
          <Aviso tono="alerta" titulo="La entrega exige evidencia">
            Cargue y confirme la foto de la entrega antes de registrar el estado ENTREGADO.
          </Aviso>
        )}

        {registrar.isError && (
          <Aviso tono="error" titulo="No se registró el punto de control">
            {mensajeDeError(registrar.error)}
          </Aviso>
        )}

        <div className="acciones">
          <Boton
            type="submit"
            cargando={registrar.isPending}
            disabled={!estado || faltaEvidencia}
            bloque
            grande
          >
            Registrar {estado ? textoEstado(estado) : ""}
          </Boton>
        </div>
      </form>
    </Tarjeta>
  );
}

/* La geolocalización puede tardar o ser denegada. No se deja que bloquee el
 * registro: el punto de control sin coordenadas sigue siendo evidencia válida,
 * y perder el registro por esperar una señal sería peor. */
function obtenerUbicacion(): Promise<Ubicacion | undefined> {
  return new Promise((resolver) => {
    if (!navigator.geolocation) return resolver(undefined);
    navigator.geolocation.getCurrentPosition(
      (posicion) => resolver({ lat: posicion.coords.latitude, lon: posicion.coords.longitude }),
      () => resolver(undefined),
      { timeout: 8000, maximumAge: 30_000 },
    );
  });
}
