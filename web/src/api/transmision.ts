/* Transmisión de la ubicación del conductor mientras su ruta está abierta.
 *
 * El teléfono es la única fuente de la posición, y el navegador impone las
 * reglas: pide permiso, solo entrega el GPS en una página segura (HTTPS o
 * localhost) y deja de entregarlo cuando la página pasa a segundo plano. Este
 * archivo hace lo que se puede dentro de esas reglas:
 *
 * - **Una lectura cada quince segundos**, o antes si el vehículo se movió
 *   mucho. Es lo bastante para ver el punto avanzar y lo bastante poco para no
 *   gastar los datos ni la batería del conductor.
 * - **Las lecturas se guardan si no hay señal** y se envían juntas al volver,
 *   hasta una hora de recorrido. La condición real del mensajero es cobertura
 *   intermitente: perder el tramo sin señal dejaría un salto en el recorrido.
 * - **Si el vehículo está quieto, se pide una lectura fresca** en lugar de
 *   repetir la última: repetirla diría «estoy aquí ahora» con una medición de
 *   hace minutos.
 * - **Si la ruta terminó en el servidor, se deja de transmitir.** El servidor
 *   responde 409 y la pantalla vuelve a la selección de guías.
 *
 * Nada de esto funciona con la pantalla apagada: el navegador detiene la
 * página. Por eso el modo ruta pide mantener la pantalla encendida
 * (`usePantallaEncendida`). Una aplicación instalada podría transmitir en
 * segundo plano; un sitio web, no. Está escrito en el ADR-013.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ErrorApi, api } from "@/api/cliente";
import type { LecturaGps } from "@/tipos";

const INTERVALO_ENVIO_MS = 15_000;
const INTERVALO_MOVIMIENTO_MS = 5_000;
/** Si en cinco segundos se recorrió esto, se envía sin esperar a los quince. */
const DISTANCIA_ADELANTO_M = 100;
/** Una lectura peor que esto es la de una antena, no la de un GPS. */
const PRECISION_UTIL_M = 500;
const MAX_PENDIENTES = 240;
const MAX_POR_ENVIO = 60;
/** Puntos del recorrido local que se dibujan. */
const MAX_RECORRIDO = 2000;

export type EstadoTransmision =
  | "preparando"
  | "transmitiendo"
  | "sin_permiso"
  | "sin_gps"
  | "no_compatible"
  | "detenida";

export interface Transmision {
  estado: EstadoTransmision;
  /** La última lectura del GPS, se haya enviado o no. */
  posicion: LecturaGps | null;
  /** El recorrido de esta sesión, para dibujarlo sin pedirlo al servidor. */
  recorrido: [number, number][];
  /** Cuándo llegó al servidor la última lectura, en hora de este equipo. */
  ultimoEnvio: number | null;
  /** Lecturas guardadas que todavía no llegaron al servidor. */
  pendientes: number;
  sinConexion: boolean;
}

/** Distancia en metros entre dos puntos, por la fórmula del haverseno. */
export function distanciaMetros(a: { lat: number; lon: number }, b: { lat: number; lon: number }) {
  const radio = 6_371_000;
  const rad = (grados: number) => (grados * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * radio * Math.asin(Math.sqrt(h));
}

export function lecturaDesde(posicion: GeolocationPosition): LecturaGps {
  const { latitude, longitude, accuracy, heading, speed } = posicion.coords;
  const lectura: LecturaGps = {
    lat: latitude,
    lon: longitude,
    precision_m: Math.round(accuracy * 10) / 10,
    capturada_en: new Date(posicion.timestamp).toISOString(),
  };
  // El rumbo y la velocidad solo existen en movimiento; quieto, el navegador
  // entrega NaN o null, y enviarlos haría fallar la validación del servidor.
  if (heading !== null && Number.isFinite(heading)) lectura.rumbo = Math.round(heading);
  if (speed !== null && Number.isFinite(speed) && speed >= 0) lectura.velocidad = Math.round(speed * 10) / 10;
  return lectura;
}

export type FalloUbicacion = "sin_permiso" | "sin_gps" | "no_compatible";

/** Una lectura única, para salir a ruta o para adjuntar a una entrega.
 *
 *  Distingue la negación del permiso de la falta de señal: lo primero lo
 *  arregla el conductor en los ajustes del navegador; lo segundo, saliendo a
 *  cielo abierto. Un solo mensaje para los dos no ayudaría con ninguno. */
export function leerUbicacion(
  opciones: PositionOptions = { enableHighAccuracy: true, timeout: 15_000, maximumAge: 20_000 },
): Promise<{ lectura: LecturaGps } | { fallo: FalloUbicacion }> {
  return new Promise((resolver) => {
    if (!("geolocation" in navigator)) return resolver({ fallo: "no_compatible" });
    navigator.geolocation.getCurrentPosition(
      (posicion) => resolver({ lectura: lecturaDesde(posicion) }),
      (error) => resolver({ fallo: error.code === error.PERMISSION_DENIED ? "sin_permiso" : "sin_gps" }),
      opciones,
    );
  });
}

export function useTransmisionDeUbicacion(
  rutaId: string | null,
  alTerminarLaRuta: () => void,
): Transmision {
  const [estado, setEstado] = useState<EstadoTransmision>("preparando");
  const [posicion, setPosicion] = useState<LecturaGps | null>(null);
  const [recorrido, setRecorrido] = useState<[number, number][]>([]);
  const [ultimoEnvio, setUltimoEnvio] = useState<number | null>(null);
  const [pendientes, setPendientes] = useState(0);
  const [sinConexion, setSinConexion] = useState(false);

  const cola = useRef<LecturaGps[]>([]);
  const enCurso = useRef(false);
  const ultimaEncolada = useRef<{ lectura: LecturaGps; en: number } | null>(null);
  const ultimaLectura = useRef<{ lectura: LecturaGps; en: number } | null>(null);
  const terminar = useRef(alTerminarLaRuta);
  terminar.current = alTerminarLaRuta;

  const enviar = useCallback(async () => {
    if (!rutaId || enCurso.current || cola.current.length === 0) return;
    enCurso.current = true;
    const lote = cola.current.slice(0, MAX_POR_ENVIO);
    try {
      await api.reportarPosiciones(rutaId, lote);
      cola.current = cola.current.slice(lote.length);
      setUltimoEnvio(Date.now());
      setSinConexion(false);
    } catch (error) {
      if (error instanceof ErrorApi && error.codigo === "CONFLICTO") {
        // La ruta se cerró en otro lado: no queda a quién reportar.
        cola.current = [];
        setEstado("detenida");
        terminar.current();
      } else if (error instanceof ErrorApi && (error.codigo === "SIN_CONEXION" || error.estado >= 500)) {
        setSinConexion(true);
      } else {
        // Un rechazo de validación no se arregla reintentando: se descarta el
        // lote para que no bloquee a los siguientes.
        cola.current = cola.current.slice(lote.length);
      }
    } finally {
      setPendientes(cola.current.length);
      enCurso.current = false;
    }
  }, [rutaId]);

  const encolar = useCallback((lectura: LecturaGps, ahora: number) => {
    cola.current = [...cola.current, lectura].slice(-MAX_PENDIENTES);
    ultimaEncolada.current = { lectura, en: ahora };
    setPendientes(cola.current.length);
  }, []);

  const alLeer = useCallback(
    (geo: GeolocationPosition) => {
      const lectura = lecturaDesde(geo);
      const ahora = Date.now();
      ultimaLectura.current = { lectura, en: ahora };
      setPosicion(lectura);
      setEstado("transmitiendo");
      if ((lectura.precision_m ?? 0) > PRECISION_UTIL_M) return;

      setRecorrido((previo) => {
        const ultimo = previo.at(-1);
        if (ultimo && distanciaMetros({ lat: ultimo[0], lon: ultimo[1] }, lectura) < 5) return previo;
        return [...previo, [lectura.lat, lectura.lon] as [number, number]].slice(-MAX_RECORRIDO);
      });

      const previa = ultimaEncolada.current;
      const transcurrido = previa ? ahora - previa.en : Infinity;
      const recorrida = previa ? distanciaMetros(previa.lectura, lectura) : Infinity;
      if (
        transcurrido >= INTERVALO_ENVIO_MS ||
        (transcurrido >= INTERVALO_MOVIMIENTO_MS && recorrida >= DISTANCIA_ADELANTO_M)
      ) {
        encolar(lectura, ahora);
        void enviar();
      }
    },
    [encolar, enviar],
  );

  const alFallar = useCallback((error: GeolocationPositionError) => {
    setEstado(error.code === error.PERMISSION_DENIED ? "sin_permiso" : "sin_gps");
  }, []);

  useEffect(() => {
    if (!rutaId) return;
    if (!("geolocation" in navigator)) {
      setEstado("no_compatible");
      return;
    }
    setEstado("preparando");
    const vigilancia = navigator.geolocation.watchPosition(alLeer, alFallar, {
      enableHighAccuracy: true,
      maximumAge: 5_000,
      timeout: 30_000,
    });

    // El pulso: reintenta lo pendiente y, si el vehículo está quieto y el
    // navegador no entrega lecturas nuevas, pide una.
    const pulso = window.setInterval(() => {
      const ultima = ultimaLectura.current;
      if (!ultima || Date.now() - ultima.en >= INTERVALO_ENVIO_MS) {
        navigator.geolocation.getCurrentPosition(alLeer, alFallar, {
          enableHighAccuracy: true,
          maximumAge: 0,
          timeout: 20_000,
        });
      }
      void enviar();
    }, INTERVALO_MOVIMIENTO_MS);

    // Al volver a primer plano, una lectura inmediata: la pantalla estuvo
    // apagada y la última posición conocida ya no dice dónde está.
    const alCambiarVisibilidad = () => {
      if (document.visibilityState === "visible") {
        navigator.geolocation.getCurrentPosition(alLeer, alFallar, {
          enableHighAccuracy: true,
          maximumAge: 0,
          timeout: 20_000,
        });
        void enviar();
      }
    };
    document.addEventListener("visibilitychange", alCambiarVisibilidad);

    return () => {
      navigator.geolocation.clearWatch(vigilancia);
      window.clearInterval(pulso);
      document.removeEventListener("visibilitychange", alCambiarVisibilidad);
    };
  }, [rutaId, alLeer, alFallar, enviar]);

  return { estado, posicion, recorrido, ultimoEnvio, pendientes, sinConexion };
}

// --------------------------------------------------------------------------- //
// Pantalla encendida
// --------------------------------------------------------------------------- //

export type EstadoPantalla = "encendida" | "no_compatible" | "rechazada" | "inactiva";

/** Pide al navegador que no apague la pantalla mientras `activo` sea cierto.
 *
 *  El navegador suelta el bloqueo cada vez que la página pasa a segundo plano,
 *  así que se vuelve a pedir al regresar. */
export function usePantallaEncendida(activo: boolean): EstadoPantalla {
  const [estado, setEstado] = useState<EstadoPantalla>("inactiva");

  useEffect(() => {
    if (!activo) return;
    const navegador = navigator as Navigator & {
      wakeLock?: { request: (tipo: "screen") => Promise<{ release: () => Promise<void> }> };
    };
    if (!navegador.wakeLock) {
      setEstado("no_compatible");
      return;
    }

    let bloqueo: { release: () => Promise<void> } | null = null;
    let vigente = true;

    const pedir = async () => {
      try {
        bloqueo = await navegador.wakeLock!.request("screen");
        if (vigente) setEstado("encendida");
      } catch {
        if (vigente) setEstado("rechazada");
      }
    };

    const alCambiarVisibilidad = () => {
      if (document.visibilityState === "visible") void pedir();
    };

    void pedir();
    document.addEventListener("visibilitychange", alCambiarVisibilidad);
    return () => {
      vigente = false;
      document.removeEventListener("visibilitychange", alCambiarVisibilidad);
      void bloqueo?.release().catch(() => undefined);
    };
  }, [activo]);

  return estado;
}
