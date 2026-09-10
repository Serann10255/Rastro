/* Contratos de la interfaz de programación, en el lenguaje del dominio.
 *
 * Los nombres son los del backend a propósito: traducirlos aquí introduciría
 * una capa de equivalencias que hay que mantener sincronizada y que, cuando se
 * desincroniza, produce errores silenciosos.
 */

export const ESTADOS = [
  "CREADO",
  "ASIGNADO",
  "RECOLECTADO",
  "EN_TRANSITO",
  "EN_REPARTO",
  "ENTREGADO",
  "INCIDENCIA",
] as const;

export type Estado = (typeof ESTADOS)[number];

/** Secuencia normal del proceso, sin contar la incidencia. */
export const FLUJO_PRINCIPAL: Estado[] = [
  "CREADO",
  "ASIGNADO",
  "RECOLECTADO",
  "EN_TRANSITO",
  "EN_REPARTO",
  "ENTREGADO",
];

export const GRUPOS = ["administrador", "despachador", "conductor", "auditor"] as const;
export type Grupo = (typeof GRUPOS)[number];

export type Resultado = "ALLOW" | "DENY" | "ERROR";

// --------------------------------------------------------------------------- //
// Sesión
// --------------------------------------------------------------------------- //

export interface Usuario {
  sub: string;
  nombre: string;
  email: string;
  org_id: string;
  grupos: Grupo[];
}

export interface Sesion {
  token: string;
  tipo: string;
  vigencia_segundos: number;
  usuario: Usuario;
  /** Momento en que se emitió, para poder avisar antes de que caduque. */
  emitida_en: number;
}

// --------------------------------------------------------------------------- //
// Envíos
// --------------------------------------------------------------------------- //

export interface Direccion {
  linea: string;
  ciudad: string;
  referencia?: string;
}

export interface Destinatario {
  nombre: string;
  telefono?: string;
}

export interface Ubicacion {
  lat: number;
  lon: number;
}

export interface Envio {
  envio_id: string;
  org_id: string;
  estado: Estado;
  estado_previo_incidencia?: Estado | null;
  creado_en: string;
  actualizado_en: string;
  creado_por: string;
  conductor_sub?: string | null;
  conductor_nombre?: string;
  origen: Direccion;
  destino: Direccion;
  destinatario: Destinatario;
  descripcion?: string;
  evidencias?: string[];
}

/** Vista reducida que devuelve el listado. */
export interface EnvioResumen {
  envio_id: string;
  estado: Estado;
  creado_en: string;
  actualizado_en: string;
  conductor_sub?: string | null;
  conductor_nombre?: string;
  destinatario: string;
  destino: string;
  descripcion?: string;
}

export interface Evento {
  evento_id: string;
  envio_id: string;
  org_id: string;
  estado: Estado;
  estado_anterior?: Estado | null;
  ts: string;
  actor_sub: string;
  actor_email?: string;
  actor_grupos?: string[];
  ubicacion?: Ubicacion | null;
  nota?: string;
  evidencia_id?: string | null;
}

export interface DetalleEnvio {
  envio: Envio;
  eventos: Evento[];
}

export interface Transiciones {
  envio_id: string;
  estado_actual: Estado;
  estado_previo_incidencia?: Estado | null;
  transiciones: Estado[];
  exige_autorizacion_despachador: boolean;
}

// --------------------------------------------------------------------------- //
// Evidencias
// --------------------------------------------------------------------------- //

export type TipoContenido = "image/jpeg" | "image/png" | "image/webp" | "application/pdf";

export interface EnlaceCarga {
  evidencia_id: string;
  clave: string;
  url: string;
  metodo: string;
  vigencia_segundos: number;
  encabezados: Record<string, string>;
}

export interface PropiedadesEvidencia {
  clave: string;
  tamano?: number;
  tipo_contenido?: string;
  cifrado?: string | null;
  llave_kms?: string | null;
  version_id?: string | null;
  modificado_en?: string;
  estado?: string;
}

export interface EvidenciaListada {
  evidencia_id: string;
  propiedades: PropiedadesEvidencia;
  url_descarga: string;
}

// --------------------------------------------------------------------------- //
// Bitácora
// --------------------------------------------------------------------------- //

export interface RegistroBitacora {
  org_id: string;
  seq: number;
  ts: string;
  actor_sub: string;
  actor_email: string;
  actor_grupos: string[];
  accion: string;
  recurso: string;
  resultado: Resultado;
  detalle: Record<string, unknown>;
  hash_previo: string;
  hash: string;
}

export interface Ruptura {
  tipo: "CONTENIDO_ALTERADO" | "ENCADENAMIENTO_ROTO" | "SECUENCIA_INCOMPLETA";
  seq?: number;
  seq_esperada?: number;
  seq_encontrada?: number;
  descripcion: string;
  hash_almacenado?: string;
  hash_recalculado?: string;
}

export interface Verificacion {
  org_id: string;
  cadena_valida: boolean;
  registros_verificados: number;
  primera_seq: number | null;
  ultima_seq: number | null;
  hash_final: string;
  rupturas: Ruptura[];
  punto_de_ruptura: Ruptura | null;
  verificado_en: string;
}

// --------------------------------------------------------------------------- //
// Consulta pública
// --------------------------------------------------------------------------- //

export interface EnvioPublico {
  envio_id: string;
  estado: Estado;
  creado_en: string;
  actualizado_en: string;
  destino_ciudad: string;
  destinatario_nombre: string;
}

export interface EventoPublico {
  estado: Estado;
  ts: string;
  nota: string;
  tiene_evidencia: boolean;
}

export interface HistoricoPublico {
  envio: EnvioPublico;
  eventos: EventoPublico[];
  consultado_en: string;
}
