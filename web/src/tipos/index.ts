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
  "DEVUELTO",
  "CANCELADO",
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

/** Los roles que el sistema trae de fábrica.
 *
 *  No son los únicos: una organización puede crear los suyos, y por eso `Grupo`
 *  admite cualquier cadena. La lista se conserva porque hay reglas que nombran
 *  a estos —el conductor y sus envíos, el auditor y su independencia— y porque
 *  es lo que se ofrece por omisión. */
export const GRUPOS_INTEGRADOS = [
  "administrador",
  "coordinador",
  "despachador",
  "conductor",
  "auditor",
] as const;

export type GrupoIntegrado = (typeof GRUPOS_INTEGRADOS)[number];

/** La clave de un rol. Los de fábrica y los que cree la organización. */
export type Grupo = GrupoIntegrado | (string & {});

/** Un rol de la organización, con lo que concede. */
export interface Rol {
  clave: string;
  nombre: string;
  descripcion: string;
  operaciones: string[];
  /** De fábrica: no se puede eliminar, aunque sí ajustar. */
  integrado: boolean;
  /** El administrador no se edita: es el seguro contra quedarse sin acceso. */
  editable: boolean;
  /** Cuántas cuentas lo tienen asignado. */
  cuentas?: number;
}

/** Una operación del catálogo, tal como se ofrece para componer un rol. */
export interface OperacionDisponible {
  operacion: string;
  descripcion: string;
  escritura: boolean;
}

export interface AreaDeOperaciones {
  area: string;
  nombre: string;
  operaciones: OperacionDisponible[];
}

export type Resultado = "ALLOW" | "DENY" | "ERROR";

// --------------------------------------------------------------------------- //
// Sesión
// --------------------------------------------------------------------------- //

export interface Usuario {
  sub: string;
  nombre: string;
  correo: string;
  org_id: string;
  grupos: Grupo[];
  activo?: boolean;
  telefono?: string;
  ultimo_acceso?: string | null;
}

export interface Sesion {
  token: string;
  /** Token largo que solo sirve para pedir uno de acceso nuevo. Nunca se envía
   *  como credencial de operación: el servidor lo rechazaría. */
  refresco: string;
  tipo: string;
  vigencia_segundos: number;
  vigencia_refresco_segundos: number;
  usuario: Usuario;
  /** Momento en que se emitió, para poder renovar antes de que caduque. */
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
  codigo_estado: number;
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

  orden_compra?: string;
  tienda_id?: string;
  tienda_nombre?: string;
  cliente_id?: string;
  cliente_nombre?: string;
  transportista_id?: string;
  transportista_nombre?: string;
  estacion_actual?: string;
  peso_kg?: number;
  valor_declarado?: number;
  bultos?: number;
  fecha_estimada?: string;
  observaciones?: string;
}

/** Vista reducida que devuelve el listado. */
export interface EnvioResumen {
  envio_id: string;
  estado: Estado;
  codigo_estado: number;
  creado_en: string;
  actualizado_en: string;
  fecha_estimada?: string;
  conductor_sub?: string | null;
  conductor_nombre?: string;
  destinatario: string;
  destino: string;
  ciudad_destino?: string;
  descripcion?: string;
  orden_compra?: string;
  cliente_nombre?: string;
  tienda_nombre?: string;
  transportista_nombre?: string;
  estacion_actual?: string;
  bultos?: number;
}

export interface Evento {
  evento_id: string;
  envio_id: string;
  org_id: string;
  estado: Estado;
  codigo_estado?: number;
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
  codigo_estado: number;
  estado_previo_incidencia?: Estado | null;
  transiciones: Estado[];
  detalle_transiciones: TransicionDetalle[];
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
  codigo_estado: number;
  creado_en: string;
  actualizado_en: string;
  destino_ciudad: string;
  destinatario_nombre: string;
}

export interface EventoPublico {
  estado: Estado;
  codigo_estado?: number;
  ts: string;
  nota: string;
  tiene_evidencia: boolean;
}

export interface HistoricoPublico {
  envio: EnvioPublico;
  eventos: EventoPublico[];
  consultado_en: string;
}

// --------------------------------------------------------------------------- //
// Catálogo de estados
// --------------------------------------------------------------------------- //

export type Fase = "registro" | "preparacion" | "transporte" | "distribucion" | "cierre" | "excepcion";

/** Definición de un estado tal como la sirve el servidor.
 *
 * La interfaz no mantiene su propia copia del catálogo: un catálogo duplicado
 * se desincroniza en cuanto se añade un estado, y el síntoma es una pantalla
 * que muestra un estado en blanco sin decir por qué. */
export interface DefinicionEstado {
  codigo: number;
  estado: Estado;
  fase: Fase;
  etiqueta: string;
  descripcion: string;
  final: boolean;
  exitoso: boolean;
}

export interface TransicionDetalle {
  estado: Estado;
  codigo: number;
  etiqueta: string;
  final: boolean;
  exige_despachador: boolean;
}

// --------------------------------------------------------------------------- //
// Empresa y usuarios
// --------------------------------------------------------------------------- //

export interface Empresa {
  org_id: string;
  nombre: string;
  nit?: string;
  direccion?: string;
  ciudad?: string;
  departamento?: string;
  pais?: string;
  telefono?: string;
  correo_contacto?: string;
  activa?: boolean;
}

export interface UsuarioAdmin {
  sub: string;
  correo: string;
  nombre: string;
  org_id: string;
  grupos: Grupo[];
  activo: boolean;
  telefono?: string;
  creado_en?: string;
  ultimo_acceso?: string | null;
}

/** Vista reducida de quien reparte: lo que el despachador necesita para
 *  asignar, sin la ficha completa de la cuenta. */
export interface Mensajero {
  sub: string;
  nombre: string;
  telefono?: string;
}

// --------------------------------------------------------------------------- //
// Módulos de la organización
// --------------------------------------------------------------------------- //

/** Un módulo del sistema tal como lo tiene esta empresa.
 *
 *  Llega del servidor y no de una lista escrita en la interfaz: qué módulos ve
 *  una organización es un dato suyo, y un módulo apagado tiene que decir por
 *  qué lo está. */
export interface Modulo {
  clave: string;
  nombre: string;
  descripcion: string;
  icono: string;
  ruta: string;
  grupos: Grupo[];
  orden: number;
  /** Si va en la navegación principal o solo en el menú de operaciones. */
  destacado: boolean;
  disponible: boolean;
  motivo: string;
  /** Nombre del contador que la interfaz muestra junto al módulo, si aplica. */
  contador?: string;
  actualizado_en?: string;
}

// --------------------------------------------------------------------------- //
// Datos maestros
// --------------------------------------------------------------------------- //

export type TipoTienda = "tienda" | "almacen" | "estacion";
export type TipoTransportista = "propio" | "tercero";

export interface Tienda {
  tienda_id: string;
  nombre: string;
  codigo: string;
  tipo: TipoTienda;
  direccion: string;
  ciudad: string;
  departamento: string;
  telefono: string;
  responsable: string;
  activa: boolean;
}

export interface Cliente {
  cliente_id: string;
  nombre: string;
  correo: string;
  telefono: string;
  documento: string;
  direccion: string;
  ciudad: string;
  departamento: string;
  activo: boolean;
}

export interface Transportista {
  transportista_id: string;
  nombre: string;
  correo: string;
  telefono: string;
  tipo: TipoTransportista;
  nit: string;
  ciudad: string;
  departamento: string;
  activo: boolean;
}

// --------------------------------------------------------------------------- //
// Tablero
// --------------------------------------------------------------------------- //

export interface Tablero {
  empresa: Pick<Empresa, "org_id" | "nombre" | "nit" | "ciudad" | "departamento">;
  ventana: { dias: number; desde: string; hasta: string };
  alcance: "organizacion" | "propios";
  totales: {
    envios: number;
    abiertos: number;
    cerrados: number;
    entregados: number;
    devueltos: number;
    cancelados: number;
    creados_en_ventana: number;
  };
  tasa_entrega: number | null;
  por_estado: (DefinicionEstado & { cantidad: number })[];
  por_fase: { fase: Fase; cantidad: number }[];
  atencion: {
    sin_asignar: number;
    con_incidencia: number;
    estancados: number;
    detalle_estancados: {
      envio_id: string;
      estado: Estado;
      actualizado_en: string;
      destinatario: string;
    }[];
  };
  serie_diaria: { fecha: string; creados: number; entregados: number }[];
  equipo: {
    usuarios: number;
    activos: number;
    por_grupo: { grupo: Grupo; cantidad: number }[];
  } | null;
  generado_en: string;
}

// --------------------------------------------------------------------------- //
// Guías y lote
// --------------------------------------------------------------------------- //

export interface Etiqueta {
  envio_id: string;
  orden_compra: string;
  empresa: string;
  empresa_nit: string;
  origen: string;
  tienda_nombre: string;
  destinatario: string;
  telefono: string;
  direccion: string;
  referencia: string;
  ciudad: string;
  bultos: number;
  peso_kg: number;
  descripcion: string;
  fecha_estimada: string;
  creado_en: string;
  transportista: string;
}

export interface ResultadoLote {
  creados: EnvioResumen[];
  rechazados: { indice: number; destinatario: string; orden_compra: string; motivo: string }[];
  resumen: { solicitados: number; creados: number; rechazados: number };
}
