/* Cliente del programa de auditoría.
 *
 * Habla con dos servicios distintos y conviene tenerlo presente: la
 * autenticación la resuelve el proveedor de identidad de Rastro —el auditor es
 * un usuario de la organización, no una cuenta aparte— y todo lo demás lo
 * atiende el programa de auditoría.
 */

// --------------------------------------------------------------------------- //
// Tipos
// --------------------------------------------------------------------------- //

export type Conclusion = "CONFORME" | "DESVIADO" | "NO_EJECUTADA";
export type TipoPrueba = "cumplimiento" | "sustantiva" | "integridad";
export type Severidad = "alta" | "media" | "baja";

export interface Control {
  id: string;
  control: string;
  marco: string;
  tipo: TipoPrueba;
  prueba: string;
  procedimiento: string;
  criterio: string;
  evidencia_esperada: string;
  severidad_si_desviado: Severidad;
}

export interface HallazgoPermanente {
  id: string;
  condicion: string;
  criterio: string;
  causa: string;
  efecto: string;
  severidad: Severidad;
  recomendacion: string;
  nota_de_alcance: string;
}

export interface Catalogo {
  version: string;
  sistema_auditado: string;
  fecha_catalogo: string;
  controles: Control[];
  hallazgos_permanentes: HallazgoPermanente[];
}

export interface Observacion {
  procedimiento: string;
  salida: unknown;
  ts: string;
  error: string | null;
}

export interface PapelDeTrabajo {
  control_id: string;
  control: string;
  marco: string;
  tipo: TipoPrueba;
  procedimiento: string;
  criterio: string;
  evidencia_esperada: string;
  conclusion: Conclusion;
  resumen: string;
  observaciones: Observacion[];
  detalle: Record<string, unknown>;
  identidad_ejecucion: string;
  iniciado_en: string;
  terminado_en: string;
  archivo_evidencia: string;
  huella_evidencia: string;
}

export interface Hallazgo {
  id: string;
  control_id: string;
  condicion: string;
  criterio: string;
  causa: string;
  efecto: string;
  severidad: Severidad;
  recomendacion: string;
  papel_de_trabajo: string;
  huella_evidencia: string;
  permanente: boolean;
}

export interface Cobertura {
  controles_del_catalogo: number;
  controles_con_resultado: number;
  conformes: number;
  desviados: number;
  no_ejecutados: number;
  cobertura: string;
}

export interface Ejecucion {
  metadatos: Record<string, unknown> & { ejecucion_id?: string; entorno?: string; identidad_ejecucion?: string };
  cobertura: Cobertura;
  controles: PapelDeTrabajo[];
  hallazgos: Hallazgo[];
}

export interface ResumenEjecucion {
  ejecucion_id: string;
  cerrado_en: string;
  entorno: string;
  url_api: string;
  identidad_ejecucion: string;
  version_catalogo: string;
  controles: number;
  conformes: number;
  desviados: number;
  no_ejecutados: number;
}

export interface Verificacion {
  almacen_integro: boolean;
  ejecucion_id?: string;
  papeles_verificados?: number;
  discrepancias: { control_id: string; tipo: string; archivo?: string }[];
  motivo?: string;
  verificado_en?: string;
}

export interface Comparacion {
  reproducible: boolean;
  controles_comparados: number;
  coincidencias: number;
  diferencias: { control_id: string; ejecucion_a: string; ejecucion_b: string }[];
}

export interface PapelConHuella {
  contenido: Record<string, unknown>;
  huella_registrada: string | null;
  huella_recalculada: string;
  coincide: boolean;
}

export interface Salud {
  entorno: string;
  url_auditada: string;
  controles_en_catalogo: number;
  catalogo: string;
}

export interface UsuarioAuditor {
  sub: string;
  nombre: string;
  email: string;
  org_id: string;
  grupos: string[];
}

export interface SesionAuditor {
  token: string;
  usuario: UsuarioAuditor;
}

// --------------------------------------------------------------------------- //
// Configuración
// --------------------------------------------------------------------------- //

interface Configuracion {
  entorno: string;
  url_cotejo: string;
  url_rastro: string;
}

let configuracion: Configuracion = { entorno: "local", url_cotejo: "", url_rastro: "" };

export async function cargarConfiguracion(): Promise<Configuracion> {
  try {
    const respuesta = await fetch("/configuracion.json", { cache: "no-store" });
    if (respuesta.ok) {
      configuracion = { ...configuracion, ...((await respuesta.json()) as Partial<Configuracion>) };
    }
  } catch {
    /* Sin archivo se asume el mismo origen, que es lo correcto en desarrollo. */
  }
  return configuracion;
}

export function configuracionActual(): Configuracion {
  return configuracion;
}

// --------------------------------------------------------------------------- //
// Sesión
// --------------------------------------------------------------------------- //

const CLAVE = "cotejo.sesion";

export const almacenSesion = {
  leer(): SesionAuditor | null {
    try {
      const bruto = sessionStorage.getItem(CLAVE);
      return bruto ? (JSON.parse(bruto) as SesionAuditor) : null;
    } catch {
      return null;
    }
  },
  guardar(sesion: SesionAuditor) {
    try {
      sessionStorage.setItem(CLAVE, JSON.stringify(sesion));
    } catch {
      /* Almacenamiento bloqueado. */
    }
  },
  borrar() {
    try {
      sessionStorage.removeItem(CLAVE);
    } catch {
      /* Nada que hacer. */
    }
  },
};

// --------------------------------------------------------------------------- //
// Errores y peticiones
// --------------------------------------------------------------------------- //

export class ErrorApi extends Error {
  readonly estado: number;
  readonly codigo: string;

  constructor(estado: number, codigo: string, mensaje: string) {
    super(mensaje);
    this.name = "ErrorApi";
    this.estado = estado;
    this.codigo = codigo;
  }
}

async function peticion<T>(
  ruta: string,
  opciones: { metodo?: "GET" | "POST"; cuerpo?: unknown; base?: "cotejo" | "rastro"; autenticada?: boolean } = {},
): Promise<T> {
  const { metodo = "GET", cuerpo, base = "cotejo", autenticada = true } = opciones;

  const raiz = (base === "cotejo" ? configuracion.url_cotejo : configuracion.url_rastro).replace(/\/$/, "");
  const cabeceras: Record<string, string> = {};
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";

  if (autenticada) {
    const sesion = almacenSesion.leer();
    if (!sesion) throw new ErrorApi(401, "NO_AUTENTICADO", "La sesión expiró. Vuelva a entrar.");
    cabeceras.Authorization = `Bearer ${sesion.token}`;
  }

  let respuesta: Response;
  try {
    respuesta = await fetch(`${raiz}${ruta}`, {
      method: metodo,
      headers: cabeceras,
      body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
    });
  } catch {
    throw new ErrorApi(0, "SIN_CONEXION", "No se pudo alcanzar el servicio. Compruebe que esté levantado.");
  }

  const texto = await respuesta.text();
  const datos: unknown = texto ? JSON.parse(texto) : null;

  if (!respuesta.ok) {
    if (respuesta.status === 401) almacenSesion.borrar();
    const cuerpoError = (datos ?? {}) as { codigo?: string; mensaje?: string; detail?: string };
    throw new ErrorApi(
      respuesta.status,
      cuerpoError.codigo ?? "ERROR",
      cuerpoError.mensaje ?? cuerpoError.detail ?? `El servicio respondió con código ${respuesta.status}.`,
    );
  }

  return datos as T;
}

// --------------------------------------------------------------------------- //
// Operaciones
// --------------------------------------------------------------------------- //

export const api = {
  /* La autenticación va contra Rastro: el auditor es un usuario de la
   * organización auditada, con el grupo `auditor`. Cotejo no mantiene su propio
   * directorio de usuarios, y esa dependencia se declara en la documentación. */
  async entrar(usuario: string, clave: string): Promise<SesionAuditor> {
    const datos = await peticion<{ token: string; usuario: UsuarioAuditor }>("/auth/token", {
      metodo: "POST",
      cuerpo: { usuario, clave },
      base: "rastro",
      autenticada: false,
    });
    const sesion = { token: datos.token, usuario: datos.usuario };
    almacenSesion.guardar(sesion);
    return sesion;
  },

  salud: () => peticion<Salud>("/salud", { autenticada: false }),
  catalogo: () => peticion<Catalogo>("/catalogo"),
  ejecuciones: () => peticion<{ ejecuciones: ResumenEjecucion[] }>("/ejecuciones"),
  ejecutar: (solo?: string[]) =>
    peticion<Ejecucion & { ejecucion_id: string }>("/ejecuciones", {
      metodo: "POST",
      cuerpo: { solo: solo ?? null },
    }),
  ejecucion: (id: string) => peticion<Ejecucion>(`/ejecuciones/${id}`),
  informeTexto: (id: string) => peticion<{ texto: string }>(`/ejecuciones/${id}/informe.txt`),
  papel: (id: string, controlId: string) =>
    peticion<PapelConHuella>(`/ejecuciones/${id}/papeles/${controlId}`),
  verificarAlmacen: (id: string) =>
    peticion<Verificacion>(`/ejecuciones/${id}/verificacion`, { metodo: "POST" }),
  comparar: (a: string, b: string) =>
    peticion<Comparacion>(`/comparacion?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
};

export function fechaLegible(iso: string | undefined): string {
  if (!iso) return "";
  const fecha = new Date(iso);
  return Number.isNaN(fecha.getTime())
    ? iso
    : fecha.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}
