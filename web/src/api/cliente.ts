/* Cliente de la interfaz de programación de Rastro.
 *
 * Tres decisiones gobiernan este archivo:
 *
 * 1. La dirección de la API se lee en tiempo de ejecución de
 *    `configuracion.json`, nunca de una variable horneada en el bundle. Es lo
 *    que permite trasladar el sistema a otra cuenta ejecutando la secuencia de
 *    despliegue, sin recompilar la interfaz (REQ-09).
 *
 * 2. La sesión se renueva sola. El token de acceso vive una hora; cuando
 *    caduca, el cliente lo cambia por uno nuevo con el token de refresco y
 *    repite la petición. Sin esto, el usuario perdería un formulario a medio
 *    llenar cada hora.
 *
 * 3. Los errores del backend se traducen a un tipo propio con su código de
 *    dominio, para que las pantallas puedan distinguir «no autorizado» de «no
 *    existe» sin inspeccionar cadenas de texto.
 */

import type {
  Cliente,
  DefinicionEstado,
  DetalleEnvio,
  Empresa,
  EnlaceCarga,
  Envio,
  EnvioResumen,
  Estado,
  Etiqueta,
  Evento,
  EvidenciaListada,
  Grupo,
  AreaDeOperaciones,
  HistoricoPublico,
  Mensajero,
  Modulo,
  PropiedadesEvidencia,
  RegistroBitacora,
  Resultado,
  Rol,
  ResultadoLote,
  Sesion,
  Tablero,
  Tienda,
  TipoContenido,
  Transiciones,
  Transportista,
  Ubicacion,
  Usuario,
  UsuarioAdmin,
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
    // tanto en desarrollo (Vite reenvía) como tras la puerta de enlace.
    cargada = { ...CONFIGURACION_POR_OMISION };
  }
  configuracion = cargada;
  return cargada;
}

export function configuracionActual(): Configuracion {
  return configuracion ?? CONFIGURACION_POR_OMISION;
}

function baseApi(): string {
  return configuracionActual().url_publica_api.replace(/\/$/, "");
}

// --------------------------------------------------------------------------- //
// Sesión
// --------------------------------------------------------------------------- //

const CLAVE_SESION = "rastro.sesion";

/* La sesión vive en sessionStorage y no en una cookie: se pierde al cerrar la
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

type ManejadorSesion = (sesion: Sesion | null) => void;
let alCambiarSesion: ManejadorSesion = () => {};

export function registrarManejadorDeSesion(manejador: ManejadorSesion) {
  alCambiarSesion = manejador;
}

// --------------------------------------------------------------------------- //
// Renovación de la sesión
// --------------------------------------------------------------------------- //

/* Una sola renovación en curso, compartida por todas las peticiones que
 * caduquen a la vez. Sin esto, cinco consultas simultáneas dispararían cinco
 * renovaciones, y como el refresco se rota, cuatro fallarían y cerrarían la
 * sesión de un usuario que no hizo nada malo. */
let renovacionEnCurso: Promise<Sesion | null> | null = null;

async function renovarSesion(): Promise<Sesion | null> {
  if (renovacionEnCurso) return renovacionEnCurso;

  renovacionEnCurso = (async () => {
    const actual = almacenSesion.leer();
    if (!actual?.refresco) return null;

    try {
      const respuesta = await fetch(`${baseApi()}/auth/refrescar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresco: actual.refresco }),
      });
      if (!respuesta.ok) return null;

      const datos = (await respuesta.json()) as Omit<Sesion, "emitida_en">;
      const renovada: Sesion = { ...datos, emitida_en: Date.now() };
      almacenSesion.guardar(renovada);
      alCambiarSesion(renovada);
      return renovada;
    } catch {
      return null;
    } finally {
      renovacionEnCurso = null;
    }
  })();

  return renovacionEnCurso;
}

function cerrarSesionLocal() {
  almacenSesion.borrar();
  alCambiarSesion(null);
}

// --------------------------------------------------------------------------- //
// Petición
// --------------------------------------------------------------------------- //

interface OpcionesPeticion {
  metodo?: "GET" | "POST";
  cuerpo?: unknown;
  autenticada?: boolean;
  parametros?: Record<string, string | number | undefined>;
  /** Marca interna para no reintentar en bucle tras renovar la sesión. */
  yaRenovada?: boolean;
}

async function peticion<T>(ruta: string, opciones: OpcionesPeticion = {}): Promise<T> {
  const { metodo = "GET", cuerpo, autenticada = true, parametros, yaRenovada = false } = opciones;

  const cabeceras: Record<string, string> = {};
  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";

  if (autenticada) {
    const sesion = almacenSesion.leer();
    if (!sesion) throw new ErrorApi(401, "NO_AUTENTICADO", "La sesión expiró. Vuelva a entrar.");
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

  // Token caducado: se renueva y se repite la petición una sola vez.
  if (respuesta.status === 401 && autenticada && !yaRenovada) {
    const renovada = await renovarSesion();
    if (renovada) return peticion<T>(ruta, { ...opciones, yaRenovada: true });
    cerrarSesionLocal();
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
    // Solo se cierra la sesión local si la petición llevaba token. Un 401 de
    // una ruta abierta -el propio inicio de sesión, sin ir más lejos- no dice
    // nada sobre la sesión guardada: significa que el servidor rechazó unas
    // credenciales. Cerrarla aquí hacía que un intento fallido de entrar
    // anunciara «la sesión expiró», que es falso y manda al usuario a repetir
    // lo mismo en lugar de revisar lo que escribió; y si había una sesión
    // válida abierta en esa pestaña, la destruía.
    if (respuesta.status === 401 && autenticada) cerrarSesionLocal();

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
  if (estado === 422) {
    if (Array.isArray(detalle) && detalle.length) {
      // FastAPI devuelve el detalle de validación como lista; se muestra el
      // primer campo para que el usuario sepa cuál corregir.
      const primero = detalle[0] as { loc?: unknown[]; msg?: string };
      const campo = Array.isArray(primero.loc) ? primero.loc.at(-1) : "";
      return campo ? `Revise el campo «${String(campo)}»: ${primero.msg ?? ""}` : "Datos no válidos.";
    }
    return "Los datos enviados no son válidos.";
  }
  if (typeof detalle === "string") return detalle;
  return `El servicio respondió con código ${estado}.`;
}

/** Descarga un archivo que el servidor devuelve como adjunto. */
async function descargar(ruta: string, nombrePorOmision: string): Promise<void> {
  const sesion = almacenSesion.leer();
  if (!sesion) throw new ErrorApi(401, "NO_AUTENTICADO", "La sesión expiró. Vuelva a entrar.");

  const respuesta = await fetch(`${baseApi()}${ruta}`, {
    headers: { Authorization: `Bearer ${sesion.token}` },
  });
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, codigoPorEstado(respuesta.status), "No se pudo exportar.");
  }

  const cabecera = respuesta.headers.get("content-disposition") ?? "";
  const nombre = /filename="([^"]+)"/.exec(cabecera)?.[1] ?? nombrePorOmision;

  const url = URL.createObjectURL(await respuesta.blob());
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(url);
}

// --------------------------------------------------------------------------- //
// Operaciones
// --------------------------------------------------------------------------- //

export const api = {
  // -- Sesión -------------------------------------------------------------
  async entrar(correo: string, clave: string): Promise<Sesion> {
    const datos = await peticion<Omit<Sesion, "emitida_en">>("/auth/token", {
      metodo: "POST",
      cuerpo: { correo, clave },
      autenticada: false,
    });
    const sesion: Sesion = { ...datos, emitida_en: Date.now() };
    almacenSesion.guardar(sesion);
    return sesion;
  },

  /** Cierra la sesión en el servidor, no solo en el navegador. Borrar el token
   *  del cliente basta para el uso normal, pero no si el token ya se copió. */
  salir: (todas = false) =>
    peticion<{ cerradas: number }>("/auth/salir", { metodo: "POST", parametros: { todas: String(todas) } }),

  yo: () => peticion<{ usuario: Usuario; empresa: Empresa; permisos: string[] }>("/auth/yo"),

  cambiarClave: (clave_actual: string, clave_nueva: string) =>
    peticion<{ cambiada: boolean }>("/auth/clave", {
      metodo: "POST",
      cuerpo: { clave_actual, clave_nueva },
    }),

  /** El catálogo de operaciones del sistema y los roles de fábrica. Abierto:
   *  describe el modelo de autorización, no los datos de ninguna empresa. */
  catalogoDeOperaciones: () =>
    peticion<{ areas: AreaDeOperaciones[]; integrados: Rol[] }>("/auth/roles", {
      autenticada: false,
    }),

  /** Los roles de la organización, que sí son suyos y puede personalizar. */
  roles: () => peticion<{ roles: Rol[]; total: number }>("/roles"),

  crearRol: (datos: {
    clave: string;
    nombre: string;
    descripcion: string;
    operaciones: string[];
  }) => peticion<{ rol: Rol }>("/roles", { metodo: "POST", cuerpo: datos }),

  actualizarRol: (
    clave: string,
    datos: { nombre?: string; descripcion?: string; operaciones?: string[] },
  ) => peticion<{ rol: Rol }>(`/roles/${encodeURIComponent(clave)}`, {
    metodo: "POST",
    cuerpo: datos,
  }),

  eliminarRol: (clave: string) =>
    peticion<{ eliminado: boolean }>(`/roles/${encodeURIComponent(clave)}/eliminar`, {
      metodo: "POST",
    }),

  // -- Usuarios y empresa -------------------------------------------------
  usuarios: () => peticion<{ usuarios: UsuarioAdmin[]; total: number }>("/usuarios"),

  crearUsuario: (datos: {
    correo: string;
    nombre: string;
    clave: string;
    grupos: Grupo[];
    telefono?: string;
  }) => peticion<{ usuario: UsuarioAdmin }>("/usuarios", { metodo: "POST", cuerpo: datos }),

  actualizarUsuario: (
    correo: string,
    cambios: { nombre?: string; grupos?: Grupo[]; telefono?: string; activo?: boolean },
  ) => peticion<{ usuario: UsuarioAdmin }>(`/usuarios/${encodeURIComponent(correo)}`, {
    metodo: "POST",
    cuerpo: cambios,
  }),

  empresa: () => peticion<{ empresa: Empresa }>("/empresa"),

  /** A quién se le puede asignar un envío. Sale del directorio de la empresa,
   *  no de una lista escrita aquí: el día que entra un mensajero nuevo, nadie
   *  va a recompilar el sitio para que aparezca. */
  mensajeros: () => peticion<{ mensajeros: Mensajero[]; total: number }>("/equipo/mensajeros"),

  // -- Tablero ------------------------------------------------------------
  tablero: (dias = 30) => peticion<Tablero>("/tablero", { parametros: { dias } }),

  // -- Catálogos y maestros ----------------------------------------------
  catalogoEstados: () =>
    peticion<{ estados: DefinicionEstado[] }>("/catalogos/estados", { autenticada: false }),

  /** Qué módulos tiene contratados la organización, con el motivo de los que
   *  no. La lista vive en la tabla de maestros: dos empresas pueden ver cosas
   *  distintas y dar de alta un módulo no exige recompilar. */
  modulos: () => peticion<{ modulos: Modulo[]; total: number }>("/catalogos/modulos"),

  actualizarModulo: (clave: string, datos: { disponible: boolean; motivo: string }) =>
    peticion<{ modulo: Modulo }>(`/catalogos/modulos/${encodeURIComponent(clave)}`, {
      metodo: "POST",
      cuerpo: datos,
    }),

  tiendas: () => peticion<{ tiendas: Tienda[]; total: number }>("/tiendas"),
  crearTienda: (datos: Partial<Tienda>) =>
    peticion<{ tienda: Tienda }>("/tiendas", { metodo: "POST", cuerpo: datos }),
  actualizarTienda: (id: string, datos: Partial<Tienda>) =>
    peticion<{ tienda: Tienda }>(`/tiendas/${id}`, { metodo: "POST", cuerpo: datos }),
  eliminarTienda: (id: string) =>
    peticion<{ eliminada: boolean }>(`/tiendas/${id}/eliminar`, { metodo: "POST" }),

  clientes: () => peticion<{ clientes: Cliente[]; total: number }>("/clientes"),
  crearCliente: (datos: Partial<Cliente>) =>
    peticion<{ cliente: Cliente }>("/clientes", { metodo: "POST", cuerpo: datos }),
  actualizarCliente: (id: string, datos: Partial<Cliente>) =>
    peticion<{ cliente: Cliente }>(`/clientes/${id}`, { metodo: "POST", cuerpo: datos }),
  eliminarCliente: (id: string) =>
    peticion<{ eliminado: boolean }>(`/clientes/${id}/eliminar`, { metodo: "POST" }),

  transportistas: () =>
    peticion<{ transportistas: Transportista[]; total: number }>("/transportistas"),
  crearTransportista: (datos: Partial<Transportista>) =>
    peticion<{ transportista: Transportista }>("/transportistas", { metodo: "POST", cuerpo: datos }),
  actualizarTransportista: (id: string, datos: Partial<Transportista>) =>
    peticion<{ transportista: Transportista }>(`/transportistas/${id}`, {
      metodo: "POST",
      cuerpo: datos,
    }),
  eliminarTransportista: (id: string) =>
    peticion<{ eliminado: boolean }>(`/transportistas/${id}/eliminar`, { metodo: "POST" }),

  // -- Envíos -------------------------------------------------------------
  listarEnvios: (limite = 500) =>
    peticion<{ envios: EnvioResumen[]; total: number }>("/envios", { parametros: { limite } }),

  consultarEnvio: (envioId: string) => peticion<DetalleEnvio>(`/envios/${envioId}`),

  crearEnvio: (datos: DatosEnvio) =>
    peticion<{ envio: Envio; evento: Evento }>("/envios", { metodo: "POST", cuerpo: datos }),

  crearLote: (envios: DatosEnvio[]) =>
    peticion<ResultadoLote>("/envios/lote", { metodo: "POST", cuerpo: { envios } }),

  asignarConductor: (envioId: string, datos: { conductor_sub: string; conductor_nombre: string }) =>
    peticion<{ envio: Envio; evento: Evento }>(`/envios/${envioId}/asignacion`, {
      metodo: "POST",
      cuerpo: datos,
    }),

  etiquetas: (envios: string[]) =>
    peticion<{ etiquetas: Etiqueta[]; no_encontrados: string[] }>("/envios/etiquetas", {
      metodo: "POST",
      cuerpo: { envios },
    }),

  exportarEnvios: () => descargar("/envios/exportar", "envios.csv"),

  // -- Rastreo ------------------------------------------------------------
  transiciones: (envioId: string) => peticion<Transiciones>(`/envios/${envioId}/transiciones`),

  registrarEvento: (
    envioId: string,
    datos: { estado: Estado; nota?: string; ubicacion?: Ubicacion; evidencia_id?: string },
  ) =>
    peticion<{ envio: Envio; evento: Evento }>(`/envios/${envioId}/eventos`, {
      metodo: "POST",
      cuerpo: datos,
    }),

  // -- Evidencias ---------------------------------------------------------
  solicitarEnlace: (envioId: string, datos: { nombre_archivo: string; tipo_contenido: TipoContenido }) =>
    peticion<EnlaceCarga>(`/envios/${envioId}/evidencias`, { metodo: "POST", cuerpo: datos }),

  confirmarEvidencia: (envioId: string, evidenciaId: string, tipo: TipoContenido) =>
    peticion<{ evidencia_id: string; propiedades: PropiedadesEvidencia; envio: Envio }>(
      `/envios/${envioId}/evidencias/${evidenciaId}/confirmacion`,
      { metodo: "POST", parametros: { tipo_contenido: tipo } },
    ),

  listarEvidencias: (envioId: string) =>
    peticion<{ envio_id: string; evidencias: EvidenciaListada[] }>(`/envios/${envioId}/evidencias`),

  // -- Bitácora -----------------------------------------------------------
  bitacora: (filtro?: { resultado?: Resultado; limite?: number }) =>
    peticion<{ org_id: string; registros: RegistroBitacora[]; total: number }>("/bitacora", {
      parametros: { resultado: filtro?.resultado, limite: filtro?.limite ?? 1000 },
    }),

  verificarBitacora: () => peticion<Verificacion>("/bitacora/verificacion"),

  // -- Consulta pública: sin token, por diseño ---------------------------
  consultaPublica: (envioId: string) =>
    peticion<HistoricoPublico>(`/publico/envios/${envioId}`, { autenticada: false }),
};

export interface DatosEnvio {
  origen: { linea: string; ciudad: string; referencia?: string };
  destino: { linea: string; ciudad: string; referencia?: string };
  destinatario: { nombre: string; telefono?: string };
  descripcion?: string;
  orden_compra?: string;
  tienda_id?: string;
  cliente_id?: string;
  transportista_id?: string;
  peso_kg?: number;
  valor_declarado?: number;
  bultos?: number;
  fecha_estimada?: string;
  observaciones?: string;
}

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
