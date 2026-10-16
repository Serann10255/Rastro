/* Mapa de posiciones: conductores en ruta, su recorrido y la posición pública.
 *
 * Es la única pieza de la interfaz que se apoya en una biblioteca de terceros,
 * Leaflet, y la razón está en el ADR-014: dibujar teselas, arrastrar, hacer
 * zoom con dos dedos y proyectar coordenadas es un problema resuelto, y
 * resolverlo de nuevo sería código propio, sí, pero peor y sin revisar.
 * Leaflet no tiene dependencias propias, se fija a una versión exacta y se
 * carga solo en las pantallas que muestran un mapa.
 *
 * El componente es una envoltura delgada. No usa `react-leaflet`: esa capa
 * añadiría otra dependencia para resolver lo que aquí cabe en un archivo.
 *
 * El mapa no es la única forma de leer la información: toda pantalla que lo
 * usa dice también con texto quién está dónde y hace cuánto. Un mapa no se lee
 * con un lector de pantalla, y no debe ser el único camino a un dato.
 */

import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import { configuracionActual } from "@/api/cliente";

export type TonoMapa = "acento" | "exito" | "alerta" | "tenue";

export interface MarcadorMapa {
  id: string;
  lat: number;
  lon: number;
  /** Rótulo visible junto al punto. */
  etiqueta?: string;
  /** Texto para lectores de pantalla y para el título emergente. */
  titulo?: string;
  tono?: TonoMapa;
  /** Radio de incertidumbre en metros: se dibuja como un halo. */
  precision?: number;
  /** Late: es una posición en vivo. */
  pulso?: boolean;
  seleccionado?: boolean;
}

export interface TrazoMapa {
  id: string;
  puntos: [number, number][];
  tono?: "acento" | "tenue";
}

interface PropsMapa {
  marcadores: MarcadorMapa[];
  trazos?: TrazoMapa[];
  /** Cambiar este valor vuelve a encuadrar todo, por ejemplo al elegir otra ruta. */
  encuadre?: string;
  /** El marcador que la vista acompaña mientras el usuario no mueva el mapa. */
  seguir?: string;
  etiqueta: string;
  alSeleccionar?: (id: string) => void;
}

const TESELAS_POR_OMISION = {
  url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  atribucion: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
};

const ZOOM_DE_UN_PUNTO = 16;

function icono(marcador: MarcadorMapa): L.DivIcon {
  const clases = [
    "mapa-marcador",
    `mapa-marcador--${marcador.tono ?? "acento"}`,
    marcador.pulso ? "mapa-marcador--pulso" : "",
    marcador.seleccionado ? "mapa-marcador--seleccionado" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return L.divIcon({
    className: "mapa-marcador__contenedor",
    html: `<span class="${clases}"><span class="mapa-marcador__punto"></span></span>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
}

function firma(marcador: MarcadorMapa): string {
  return [marcador.tono, marcador.pulso, marcador.seleccionado, marcador.etiqueta].join("|");
}

interface Capa {
  marcador: L.Marker;
  halo: L.Circle | null;
  firma: string;
}

export default function Mapa({ marcadores, trazos = [], encuadre, seguir, etiqueta, alSeleccionar }: PropsMapa) {
  const nodo = useRef<HTMLDivElement>(null);
  const mapa = useRef<L.Map | null>(null);
  const capas = useRef(new Map<string, Capa>());
  const lineas = useRef(new Map<string, L.Polyline>());
  const encuadrado = useRef<string | null>(null);
  const alSeleccionarActual = useRef(alSeleccionar);
  alSeleccionarActual.current = alSeleccionar;
  // Cuando el usuario arrastra o hace zoom, la vista deja de seguir sola: que
  // el mapa le quite de debajo lo que estaba mirando es peor que no seguir.
  const [libre, setLibre] = useState(false);

  // -- Creación ------------------------------------------------------------
  useEffect(() => {
    if (!nodo.current) return;
    const teselas = configuracionActual().teselas ?? TESELAS_POR_OMISION;

    const instancia = L.map(nodo.current, {
      zoomControl: true,
      attributionControl: true,
      // Sin desplazar con la rueda: en una página que se recorre con la rueda,
      // el mapa se tragaba el gesto y la página dejaba de bajar.
      scrollWheelZoom: false,
    });
    instancia.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    L.tileLayer(teselas.url, {
      attribution: teselas.atribucion,
      maxZoom: 19,
      // El sitio no envía la página de origen a nadie (no-referrer), pero el
      // servidor de teselas de OpenStreetMap exige saber desde qué sitio se le
      // pide: sin esto, deja de servirlas.
      referrerPolicy: "strict-origin-when-cross-origin",
    }).addTo(instancia);

    const soltar = (evento: L.LeafletEvent) => {
      // Solo los gestos del usuario sueltan la vista; los movimientos que hace
      // el propio componente no traen evento original.
      if ((evento as L.LeafletEvent & { originalEvent?: Event }).originalEvent) setLibre(true);
    };
    instancia.on("dragstart", () => setLibre(true));
    instancia.on("zoomstart", soltar);

    mapa.current = instancia;
    const observador = new ResizeObserver(() => instancia.invalidateSize());
    observador.observe(nodo.current);

    return () => {
      observador.disconnect();
      instancia.remove();
      mapa.current = null;
      capas.current.clear();
      lineas.current.clear();
      encuadrado.current = null;
    };
  }, []);

  // -- Marcadores ------------------------------------------------------------
  useEffect(() => {
    const instancia = mapa.current;
    if (!instancia) return;
    const vigentes = new Set(marcadores.map((m) => m.id));

    for (const [id, capa] of capas.current) {
      if (!vigentes.has(id)) {
        capa.marcador.remove();
        capa.halo?.remove();
        capas.current.delete(id);
      }
    }

    for (const marcador of marcadores) {
      const punto = L.latLng(marcador.lat, marcador.lon);
      const existente = capas.current.get(marcador.id);
      if (!existente) {
        const nuevo = L.marker(punto, {
          icon: icono(marcador),
          title: marcador.titulo ?? marcador.etiqueta ?? "",
          alt: marcador.titulo ?? marcador.etiqueta ?? "",
          keyboard: Boolean(alSeleccionarActual.current),
          riseOnHover: true,
        }).addTo(instancia);
        if (marcador.etiqueta) {
          nuevo.bindTooltip(marcador.etiqueta, {
            permanent: true,
            direction: "top",
            offset: [0, -14],
            className: "mapa-etiqueta",
          });
        }
        nuevo.on("click", () => alSeleccionarActual.current?.(marcador.id));
        const halo = marcador.precision
          ? L.circle(punto, { radius: marcador.precision, className: "mapa-precision", interactive: false }).addTo(instancia)
          : null;
        capas.current.set(marcador.id, { marcador: nuevo, halo, firma: firma(marcador) });
        continue;
      }

      existente.marcador.setLatLng(punto);
      if (existente.firma !== firma(marcador)) {
        existente.marcador.setIcon(icono(marcador));
        existente.marcador.setTooltipContent(marcador.etiqueta ?? "");
        existente.firma = firma(marcador);
      }
      if (marcador.precision) {
        if (existente.halo) existente.halo.setLatLng(punto).setRadius(marcador.precision);
        else
          existente.halo = L.circle(punto, {
            radius: marcador.precision,
            className: "mapa-precision",
            interactive: false,
          }).addTo(instancia);
      } else if (existente.halo) {
        existente.halo.remove();
        existente.halo = null;
      }
    }
  }, [marcadores]);

  // -- Trazos ------------------------------------------------------------------
  useEffect(() => {
    const instancia = mapa.current;
    if (!instancia) return;
    const vigentes = new Set(trazos.map((t) => t.id));
    for (const [id, linea] of lineas.current) {
      if (!vigentes.has(id)) {
        linea.remove();
        lineas.current.delete(id);
      }
    }
    for (const trazo of trazos) {
      const existente = lineas.current.get(trazo.id);
      if (existente) existente.setLatLngs(trazo.puntos);
      else
        lineas.current.set(
          trazo.id,
          L.polyline(trazo.puntos, {
            className: `mapa-trazo mapa-trazo--${trazo.tono ?? "acento"}`,
            interactive: false,
          }).addTo(instancia),
        );
    }
  }, [trazos]);

  // -- Encuadre y seguimiento ---------------------------------------------------
  useEffect(() => {
    const instancia = mapa.current;
    if (!instancia) return;
    const clave = encuadre ?? "inicial";

    if (encuadrado.current !== clave) {
      const puntos: L.LatLngExpression[] = [
        ...marcadores.map((m) => [m.lat, m.lon] as [number, number]),
        ...trazos.flatMap((t) => t.puntos),
      ];
      if (puntos.length === 0) return;
      encuadrado.current = clave;
      setLibre(false);
      if (puntos.length === 1) instancia.setView(puntos[0]!, ZOOM_DE_UN_PUNTO);
      else instancia.fitBounds(L.latLngBounds(puntos), { padding: [36, 36], maxZoom: ZOOM_DE_UN_PUNTO });
      return;
    }

    if (seguir && !libre) {
      const objetivo = marcadores.find((m) => m.id === seguir);
      if (objetivo) instancia.panTo([objetivo.lat, objetivo.lon], { animate: true });
    }
  }, [marcadores, trazos, encuadre, seguir, libre]);

  const recentrar = () => {
    encuadrado.current = null;
    setLibre(false);
    const instancia = mapa.current;
    if (!instancia) return;
    const puntos: L.LatLngExpression[] = [
      ...marcadores.map((m) => [m.lat, m.lon] as [number, number]),
      ...trazos.flatMap((t) => t.puntos),
    ];
    if (puntos.length === 1) instancia.setView(puntos[0]!, ZOOM_DE_UN_PUNTO);
    else if (puntos.length > 1)
      instancia.fitBounds(L.latLngBounds(puntos), { padding: [36, 36], maxZoom: ZOOM_DE_UN_PUNTO });
    encuadrado.current = encuadre ?? "inicial";
  };

  return (
    <div className="mapa">
      <div ref={nodo} className="mapa__lienzo" role="region" aria-label={etiqueta} />
      {libre && (
        <button type="button" className="boton boton--secundario mapa__recentrar" onClick={recentrar}>
          Centrar
        </button>
      )}
    </div>
  );
}
