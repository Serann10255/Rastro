/* Cliente de la interfaz de programacion de Rastro.
 *
 * La direccion de la interfaz no esta escrita en el codigo: se lee de
 * configuracion.json en tiempo de ejecucion (REQ-09). Al trasladar el sistema a
 * otra cuenta cambia ese archivo y nada mas.
 */

const RUTA_CONFIGURACION = "./configuracion.json";
const CLAVE_SESION = "rastro.sesion";

let configuracion = null;

export async function cargarConfiguracion() {
  if (configuracion) return configuracion;
  try {
    const respuesta = await fetch(RUTA_CONFIGURACION, { cache: "no-store" });
    configuracion = respuesta.ok ? await respuesta.json() : {};
  } catch {
    configuracion = {};
  }
  // En el entorno local la puerta de enlace corre junto a la interfaz.
  configuracion.url_publica_api ||= `${location.protocol}//${location.hostname}:8080`;
  return configuracion;
}

/* --------------------------------------------------------------------- */
/* Sesion                                                                */
/* --------------------------------------------------------------------- */

export const sesion = {
  leer() {
    try {
      return JSON.parse(sessionStorage.getItem(CLAVE_SESION) || "null");
    } catch {
      return null;
    }
  },
  // El token vive en sessionStorage y no en una cookie: se pierde al cerrar la
  // pestana, que es el comportamiento deseado en un dispositivo compartido.
  guardar(datos) {
    sessionStorage.setItem(CLAVE_SESION, JSON.stringify(datos));
  },
  cerrar() {
    sessionStorage.removeItem(CLAVE_SESION);
  },
  tieneGrupo(...grupos) {
    const actual = this.leer();
    return Boolean(actual && grupos.some((g) => actual.usuario.grupos.includes(g)));
  },
};

export class ErrorApi extends Error {
  constructor(estado, cuerpo) {
    super(cuerpo?.mensaje || `Error ${estado}`);
    this.estado = estado;
    this.codigo = cuerpo?.codigo || "ERROR";
    this.detalle = cuerpo?.detalle || {};
  }
}

/* --------------------------------------------------------------------- */
/* Peticiones                                                            */
/* --------------------------------------------------------------------- */

async function peticion(ruta, { metodo = "GET", cuerpo, autenticada = true } = {}) {
  const config = await cargarConfiguracion();
  const cabeceras = {};

  if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";

  if (autenticada) {
    const actual = sesion.leer();
    if (!actual) throw new ErrorApi(401, { mensaje: "La sesion expiro. Vuelva a entrar." });
    cabeceras.Authorization = `Bearer ${actual.token}`;
  }

  const respuesta = await fetch(`${config.url_publica_api}${ruta}`, {
    method: metodo,
    headers: cabeceras,
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });

  const texto = await respuesta.text();
  const datos = texto ? JSON.parse(texto) : null;

  if (!respuesta.ok) {
    // Un token caducado en mitad de la jornada es normal: las credenciales del
    // laboratorio duran cuatro horas. Se cierra la sesion en vez de dejar la
    // interfaz reintentando contra un token que ya no sirve.
    if (respuesta.status === 401) sesion.cerrar();
    throw new ErrorApi(respuesta.status, datos);
  }
  return datos;
}

export const api = {
  // Autenticacion (en AWS la reemplaza el flujo de Cognito).
  async entrar(usuario, clave) {
    const datos = await peticion("/auth/token", {
      metodo: "POST",
      cuerpo: { usuario, clave },
      autenticada: false,
    });
    sesion.guardar(datos);
    return datos;
  },

  // Envios
  listarEnvios: () => peticion("/envios"),
  consultarEnvio: (id) => peticion(`/envios/${id}`),
  crearEnvio: (datos) => peticion("/envios", { metodo: "POST", cuerpo: datos }),
  asignarConductor: (id, datos) =>
    peticion(`/envios/${id}/asignacion`, { metodo: "POST", cuerpo: datos }),

  // Rastreo
  transiciones: (id) => peticion(`/envios/${id}/transiciones`),
  registrarEvento: (id, datos) =>
    peticion(`/envios/${id}/eventos`, { metodo: "POST", cuerpo: datos }),

  // Evidencias
  solicitarEnlace: (id, datos) =>
    peticion(`/envios/${id}/evidencias`, { metodo: "POST", cuerpo: datos }),
  confirmarEvidencia: (id, evidenciaId, tipo) =>
    peticion(
      `/envios/${id}/evidencias/${evidenciaId}/confirmacion?tipo_contenido=${encodeURIComponent(tipo)}`,
      { metodo: "POST" }
    ),
  listarEvidencias: (id) => peticion(`/envios/${id}/evidencias`),

  // Bitacora
  bitacora: (filtro) => peticion(`/bitacora${filtro ? `?resultado=${filtro}` : ""}`),
  verificarBitacora: () => peticion("/bitacora/verificacion"),

  // Consulta publica: sin token, por diseno.
  consultaPublica: (id) => peticion(`/publico/envios/${id}`, { autenticada: false }),
};

/* --------------------------------------------------------------------- */
/* Carga de la evidencia contra el enlace prefirmado                     */
/* --------------------------------------------------------------------- */

/* El archivo no pasa por los microservicios: el dispositivo lo envia
 * directamente al almacenamiento con el enlace de vigencia limitada. */
export async function cargarEvidencia(enlace, archivo) {
  const respuesta = await fetch(enlace.url, {
    method: enlace.metodo,
    headers: enlace.encabezados,
    body: archivo,
  });
  if (!respuesta.ok) {
    throw new Error(
      `El almacenamiento rechazo la carga (${respuesta.status}). ` +
        "Compruebe que el enlace no haya expirado."
    );
  }
  return true;
}

export function formatearFecha(iso) {
  if (!iso) return "";
  const fecha = new Date(iso);
  return Number.isNaN(fecha.getTime())
    ? iso
    : fecha.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}
