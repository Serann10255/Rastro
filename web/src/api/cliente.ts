/* Cliente de la interfaz de programación de Rastro.
 *
 * Dos decisiones gobiernan este archivo:
 *
 * 1. La dirección de la API se lee en tiempo de ejecución de
 *    `configuracion.json`, nunca de una variable horneada en el bundle. Es lo
 *    que permite trasladar el sistema a otra cuenta ejecutando la secuencia de
 *    despliegue, sin recompilar la interfaz (REQ-09).
 *
 * 2. Los errores del backend se traducen a un tipo propio con su código de
 *    dominio, para que las pantallas puedan distinguir «no autorizado» de «no
 *    existe» sin inspeccionar cadenas de texto.
 */

import type {
  DetalleEnvio,
  EnlaceCarga,
  Envio,
  EnvioResumen,
  Estado,
  Evento,
  EvidenciaListada,
  HistoricoPublico,
  PropiedadesEvidencia,
  RegistroBitacora,
  Resultado,
  Sesion,
  TipoContenido,
  Transiciones,
  Ubicacion,
  Verificacion,
} from "@/tipos";

// --------------------------------------------------------------------------- //
// Configuración en tiempo de ejecución
// --------------------------------------------------------------------------- //

export interface Configuracion {
  entorno: string;
  region: string;
  url_publica_api: string;
  account_id?: string;
  supuesto_su01?: string;
  generado_en?: string;
}

const CONFIGURACION_POR_OMISION: Configuracion = {
  entorno: "local",
  region: "us-east-1",
  url_publica_api: "",
};

let configuracion: Configuracion | null = null;

export async function cargarConfiguracion(): Promise<Configuracion> {
  if (configuracion) return configuracion;
  let cargada: Configuracion;
  try {
    const respuesta = await fetch("/configuracion.json", { cache: "no-store" });
    const datos = respuesta.ok ? ((await respuesta.json()) as Partial<Configuracion>) : {};
    cargada = { ...CONFIGURACION_POR_OMISION, ...datos };
  } catch {
    // Sin archivo de configuración se asume el mismo origen, que es lo correcto
    // tanto en desarrollo (Vite reenvía) como en un despliegue tras la puerta
    // de enlace. Fallar aquí dejaría la interfaz inservible por un archivo
    // opcional.
    cargada = { ...CONFIGURACION_POR_OMISION };
  }
  configuracion = cargada;
  return cargada;
}

export function configuracionActual(): Configuracion {
  return configuracion ?? CONFIGURACION_POR_OMISION;
}

/** Vacío significa mismo origen: en desarrollo lo reenvía Vite, en producción
 *  lo hace la puerta de enlace o el propio sitio publicado. */
function baseApi(): string {
  return configuracionActual().url_publica_api.replace(/\/$/, "");
}

// --------------------------------------------------------------------------- //
// Sesión
// --------------------------------------------------------------------------- //

const CLAVE_SESION = "rastro.sesion";

/* El token vive en sessionStorage y no en una cookie: se pierde al cerrar la
 * pestaña, que es el comportamiento deseado en un dispositivo compartido entre
 * mensajeros. */
export const almacenSesion = {
  leer(): Sesion | null {
    try {
      const bruto = sessionStorage.getItem(CLAVE_SESION);
      return bruto ? (JSON.parse(bruto) as Sesion) : null;
    } catch {
      return null;
    }
  },
  guardar(sesion: Sesion) {
    try {
      sessionStorage.setItem(CLAVE_SESION, JSON.stringify(sesion));
    } catch {
      /* Modo privado o almacenamiento bloqueado: la sesión vive solo en memoria. */
    }
  },
  borrar() {
    try {
      sessionStorage.removeItem(CLAVE_SESION);
    } catch {
      /* Nada que hacer. */
    }
  },
};

// --------------------------------------------------------------------------- //
// Errores
// --------------------------------------------------------------------------- //

export type CodigoError =
  | "NO_AUTENTICADO"
  | "NO_AUTORIZADO"
  | "NO_ENCONTRADO"
  | "TRANSICION_INVALIDA"
  | "SOLICITUD_INVALIDA"
  | "CONFLICTO"
  | "SIN_CONEXION"
  | "ERROR_INTERNO";

export class ErrorApi extends Error {
  readonly estado: number;
  readonly codigo: CodigoError;
  readonly detalle: Record<string, unknown>;

  constructor(estado: number, codigo: CodigoError, mensaje: string, detalle: Record<string, unknown> = {}) {
    super(mensaje);
    this.name = "ErrorApi";
    this.estado = estado;
    this.codigo = codigo;
    this.detalle = detalle;
  }

  /** Transiciones que sí eran válidas, cuando el error es de máquina de estados. */
  get transicionesPermitidas(): Estado[] {
    const permitidas = this.detalle.permitidas;
    return Array.isArray(permitidas) ? (permitidas as Estado[]) : [];
  }
}

type ManejadorSesionExpirada = () => void;
let alExpirarSesion: ManejadorSesionExpirada = () => {};

export function registrarManejadorDeSesionExpirada(manejador: ManejadorSesionExpirada) {
  alExpirarSesion = manejador;
}

// --------------------------------------------------------------------------- //
// Petición
// --------------------------------------------------------------------------- //

interface OpcionesPeticion {
  metodo?: "GET" | "POST";
  cuerpo?: unknown;
  autenticada?: boolean;
  parametros?: Record<string, string | number | undefined>;
}

async function peticion<T>(ruta: string, opciones: OpcionesPeticion = {}): Promise<T> {
  const { metodo = "GET", cuerpo, autenticada = true, parametros } = opciones;

  const cabeceras: Record<string, string> = {};
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";

  if (autenticada) {
    const sesion = almacenSesion.leer();
    if (!sesion) {
      throw new ErrorApi(401, "NO_AUTENTICADO", "La sesión expiró. Vuelva a entrar.");
    }
    cabeceras.Authorization = `Bearer ${sesion.token}`;
  }

  const consulta = new URLSearchParams();
  for (const [clave, valor] of Object.entries(parametros ?? {})) {
    if (valor !== undefined && valor !== "") consulta.set(clave, String(valor));
  }
  const sufijo = consulta.size ? `?${consulta}` : "";

  let respuesta: Response;
  try {
    respuesta = await fetch(`${baseApi()}${ruta}${sufijo}`, {
      method: metodo,
      headers: cabeceras,
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch {
    // La condición real del mensajero es conectividad intermitente en vía. Un
    // fallo de red no es un fallo del sistema y no debe presentarse como tal.
    throw new ErrorApi(0, "SIN_CONEXION", "Sin conexión. Compruebe la red e inténtelo de nuevo.");
  }

  const texto = await respuesta.text();
  const datos: unknown = texto ? JSON.parse(texto) : null;

  if (!respuesta.ok) {
    const cuerpoError = (datos ?? {}) as {
      codigo?: CodigoError;
      mensaje?: string;
      detalle?: Record<string, unknown>;
      detail?: unknown;
    };

    // Un token caducado a media jornada es normal: las credenciales del
    // laboratorio duran cuatro horas. Se cierra la sesión en lugar de dejar la
    // interfaz reintentando contra un token que ya no sirve.
    if (respuesta.status === 401) {
      almacenSesion.borrar();
      alExpirarSesion();
    }

    throw new ErrorApi(
      respuesta.status,
      cuerpoError.codigo ?? codigoPorEstado(respuesta.status),
      cuerpoError.mensaje ?? mensajePorEstado(respuesta.status, cuerpoError.detail),
      cuerpoError.detalle ?? {},
    );
  }

  return datos as T;
}

function codigoPorEstado(estado: number): CodigoError {
  if (estado === 401) return "NO_AUTENTICADO";
  if (estado === 403) return "NO_AUTORIZADO";
  if (estado === 404) return "NO_ENCONTRADO";
  if (estado === 409) return "CONFLICTO";
  if (estado === 400 || estado === 422) return "SOLICITUD_INVALIDA";
  return "ERROR_INTERNO";
}

function mensajePorEstado(estado: number, detalle: unknown): string {
  if (estado === 422) return "El identificador no tiene el formato esperado.";
  if (typeof detalle === "string") return detalle;
  return `El servicio respondió con código ${estado}.`;
}

// --------------------------------------------------------------------------- //
// Operaciones
// --------------------------------------------------------------------------- //

export const api = {
  async entrar(usuario: string, clave: string): Promise<Sesion> {
    const datos = await peticion<Omit<Sesion, "emitida_en">>("/auth/token", {
      metodo: "POST",
      cuerpo: { usuario, clave },
      autenticada: false,
    });
    const sesion: Sesion = { ...datos, emitida_en: Date.now() };
    almacenSesion.guardar(sesion);
    return sesion;
  },

  listarEnvios: (limite = 200) =>
    peticion<{ envios: EnvioResumen[]; total: number }>("/envios", { parametros: { limite } }),

  consultarEnvio: (envioId: string) => peticion<DetalleEnvio>(`/envios/${envioId}`),

  crearEnvio: (datos: {
    origen: { linea: string; ciudad: string; referencia?: string };
    destino: { linea: string; ciudad: string; referencia?: string };
    destinatario: { nombre: string; telefono?: string };
    descripcion?: string;
  }) => peticion<{ envio: Envio; evento: Evento }>("/envios", { metodo: "POST", cuerpo: datos }),

  asignarConductor: (envioId: string, datos: { conductor_sub: string; conductor_nombre: string }) =>
    peticion<{ envio: Envio; evento: Evento }>(`/envios/${envioId}/asignacion`, {
      metodo: "POST",
      cuerpo: datos,
    }),

  transiciones: (envioId: string) => peticion<Transiciones>(`/envios/${envioId}/transiciones`),

  registrarEvento: (
    envioId: string,
    datos: { estado: Estado; nota?: string; ubicacion?: Ubicacion; evidencia_id?: string },
  ) =>
    peticion<{ envio: Envio; evento: Evento }>(`/envios/${envioId}/eventos`, {
      metodo: "POST",
      cuerpo: datos,
    }),

  solicitarEnlace: (envioId: string, datos: { nombre_archivo: string; tipo_contenido: TipoContenido }) =>
    peticion<EnlaceCarga>(`/envios/${envioId}/evidencias`, { metodo: "POST", cuerpo: datos }),

  confirmarEvidencia: (envioId: string, evidenciaId: string, tipo: TipoContenido) =>
    peticion<{ evidencia_id: string; propiedades: PropiedadesEvidencia; envio: Envio }>(
      `/envios/${envioId}/evidencias/${evidenciaId}/confirmacion`,
      { metodo: "POST", parametros: { tipo_contenido: tipo } },
    ),

  listarEvidencias: (envioId: string) =>
    peticion<{ envio_id: string; evidencias: EvidenciaListada[] }>(`/envios/${envioId}/evidencias`),

  bitacora: (filtro?: { resultado?: Resultado; limite?: number }) =>
    peticion<{ org_id: string; registros: RegistroBitacora[]; total: number }>("/bitacora", {
      parametros: { resultado: filtro?.resultado, limite: filtro?.limite ?? 500 },
    }),

  verificarBitacora: () => peticion<Verificacion>("/bitacora/verificacion"),

  /* Sin token, por diseño: es el único punto del sistema que responde sin
   * autenticación, y su protección es el identificador aleatorio. */
  consultaPublica: (envioId: string) =>
    peticion<HistoricoPublico>(`/publico/envios/${envioId}`, { autenticada: false }),
};

// --------------------------------------------------------------------------- //
// Carga de la evidencia contra el enlace prefirmado
// --------------------------------------------------------------------------- //

/* El archivo no pasa por los microservicios: el dispositivo lo envía
 * directamente al almacenamiento con un enlace de vigencia limitada. */
export async function cargarEvidencia(enlace: EnlaceCarga, archivo: File): Promise<void> {
  let respuesta: Response;
  try {
    respuesta = await fetch(enlace.url, {
      method: enlace.metodo,
      headers: enlace.encabezados,
      body: archivo,
    });
  } catch {
    throw new ErrorApi(0, "SIN_CONEXION", "No se pudo alcanzar el almacenamiento. Compruebe la red.");
  }

  if (!respuesta.ok) {
    throw new ErrorApi(
      respuesta.status,
      "SOLICITUD_INVALIDA",
      respuesta.status === 403
        ? `El enlace expiró (vigencia de ${enlace.vigencia_segundos} s). Solicite uno nuevo.`
        : `El almacenamiento rechazó la carga con código ${respuesta.status}.`,
    );
  }
}
