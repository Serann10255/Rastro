/* Estado del servidor con React Query.
 *
 * La razón de usarlo en lugar de `useEffect` con `fetch` no es comodidad: es
 * que el conductor trabaja con conectividad intermitente, y aquí quedan
 * centralizados el reintento, la invalidación tras una escritura y el estado de
 * «recargando sin borrar lo que ya se ve». Escribir eso a mano en cada pantalla
 * es donde aparecen las incoherencias.
 */

import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorApi, api } from "@/api/cliente";
import type { DatosEnvio } from "@/api/cliente";
import { cargarEvidencia } from "@/api/cliente";
import type {
  Cliente,
  Estado,
  Grupo,
  LecturaGps,
  PosicionRuta,
  Resultado,
  Ruta,
  Tienda,
  TipoContenido,
  Transportista,
  Ubicacion,
} from "@/tipos";

/** Claves de caché. Centralizarlas evita invalidaciones que no aciertan. */
export const claves = {
  envios: ["envios"] as const,
  envio: (id: string) => ["envio", id] as const,
  transiciones: (id: string) => ["transiciones", id] as const,
  evidencias: (id: string) => ["evidencias", id] as const,
  bitacora: (filtro?: Resultado) => ["bitacora", filtro ?? "todos"] as const,
  verificacion: ["bitacora", "verificacion"] as const,
  publico: (id: string) => ["publico", id] as const,
  tablero: (dias: number) => ["tablero", dias] as const,
  usuarios: ["usuarios"] as const,
  tiendas: ["tiendas"] as const,
  clientes: ["clientes"] as const,
  transportistas: ["transportistas"] as const,
  catalogoEstados: ["catalogo", "estados"] as const,
  modulos: ["catalogo", "modulos"] as const,
  mensajeros: ["equipo", "mensajeros"] as const,
  roles: ["roles"] as const,
  catalogoOperaciones: ["catalogo", "operaciones"] as const,
  rutaActiva: ["rutas", "activa"] as const,
  rutas: (estado: string) => ["rutas", "lista", estado] as const,
  recorrido: (id: string) => ["rutas", "recorrido", id] as const,
  ubicacionPublica: (id: string) => ["publico", id, "ubicacion"] as const,
};

/* Reintentar un 403 o un 404 no cambia el resultado y confunde al usuario con
 * una espera inútil. Solo se reintenta lo que puede resolverse solo. */
function reintentarSoloFallosTransitorios(intentos: number, error: unknown): boolean {
  if (error instanceof ErrorApi) {
    if (error.codigo === "SIN_CONEXION") return intentos < 3;
    if (error.estado >= 400 && error.estado < 500) return false;
  }
  return intentos < 2;
}

const reintento = { retry: reintentarSoloFallosTransitorios };

// --------------------------------------------------------------------------- //
// Catálogos
// --------------------------------------------------------------------------- //

/** El catálogo de estados cambia con el despliegue, no con el uso. */
export function useCatalogoEstados() {
  return useQuery({
    queryKey: claves.catalogoEstados,
    queryFn: api.catalogoEstados,
    staleTime: 60 * 60_000,
    ...reintento,
  });
}

/** Qué estados cierran un envío, según el catálogo del servidor.
 *
 * Antes esta lista estaba escrita en tres pantallas distintas. Al añadir
 * `DEVUELTO` y `CANCELADO` hubo que tocar las tres, y bastaba olvidar una para
 * que un envío cerrado siguiera contando como abierto sin que nadie lo notara.
 * El catálogo ya dice cuáles son finales: preguntarle es una consulta menos que
 * mantener. */
export function useEstadosFinales(): (estado: string) => boolean {
  const { data } = useCatalogoEstados();
  const finales = new Set((data?.estados ?? []).filter((e) => e.final).map((e) => e.estado));
  // Mientras el catálogo no ha llegado, nada se da por cerrado: contar de menos
  // es preferible a mostrar como pendiente algo que ya terminó.
  return (estado: string) => finales.has(estado as never);
}

/** Los roles de la organización, con lo que concede cada uno. */
export function useRoles(habilitado = true) {
  return useQuery({
    queryKey: claves.roles,
    queryFn: api.roles,
    enabled: habilitado,
    staleTime: 5 * 60_000,
    ...reintento,
  });
}

/** El catálogo de operaciones del sistema. Cambia con el despliegue, no con el
 *  uso: es la lista cerrada de lo que el sistema sabe hacer. */
export function useCatalogoDeOperaciones() {
  return useQuery({
    queryKey: claves.catalogoOperaciones,
    queryFn: api.catalogoDeOperaciones,
    staleTime: 60 * 60_000,
    ...reintento,
  });
}

/** Los módulos de la organización. Cambian cuando un administrador enciende o
 *  apaga uno, no con cada pantalla: se refrescan poco. */
export function useModulos() {
  return useQuery({
    queryKey: claves.modulos,
    queryFn: api.modulos,
    staleTime: 5 * 60_000,
    ...reintento,
  });
}

// --------------------------------------------------------------------------- //
// Tablero
// --------------------------------------------------------------------------- //

export function useTablero(dias = 30) {
  return useQuery({
    queryKey: claves.tablero(dias),
    queryFn: () => api.tablero(dias),
    ...reintento,
  });
}

// --------------------------------------------------------------------------- //
// Envíos
// --------------------------------------------------------------------------- //

export function useEnvios() {
  return useQuery({ queryKey: claves.envios, queryFn: () => api.listarEnvios(), ...reintento });
}

export function useEnvio(envioId: string | undefined) {
  return useQuery({
    queryKey: claves.envio(envioId ?? ""),
    queryFn: () => api.consultarEnvio(envioId!),
    enabled: Boolean(envioId),
    ...reintento,
  });
}

export function useTransiciones(envioId: string | undefined) {
  return useQuery({
    queryKey: claves.transiciones(envioId ?? ""),
    queryFn: () => api.transiciones(envioId!),
    enabled: Boolean(envioId),
    ...reintento,
  });
}

export function useEvidencias(envioId: string | undefined, habilitado: boolean) {
  return useQuery({
    queryKey: claves.evidencias(envioId ?? ""),
    queryFn: () => api.listarEvidencias(envioId!),
    enabled: Boolean(envioId) && habilitado,
    ...reintento,
  });
}

export function useBitacora(filtro?: Resultado) {
  return useQuery({
    queryKey: claves.bitacora(filtro),
    queryFn: () => api.bitacora({ resultado: filtro }),
    ...reintento,
  });
}

export function useConsultaPublica(envioId: string | null) {
  return useQuery({
    queryKey: claves.publico(envioId ?? ""),
    queryFn: () => api.consultaPublica(envioId!),
    enabled: Boolean(envioId),
    ...reintento,
  });
}

// --------------------------------------------------------------------------- //
// Rutas de entrega
// --------------------------------------------------------------------------- //

/* Cada cuánto se refresca cada vista. El mapa de la empresa es el que más
 * pregunta porque es el que alguien mira esperando ver moverse un punto; el
 * destinatario, menos, porque su envío es uno y la posición pública solo
 * cambia cuando el conductor reporta, cada quince segundos. */
const REFRESCO_SEGUIMIENTO_MS = 10_000;
const REFRESCO_RUTA_PROPIA_MS = 30_000;
const REFRESCO_PUBLICO_MS = 20_000;

/** Guarda el testigo de la última consulta registrada en la bitácora.
 *
 *  Vive lo que vive la pantalla: abrirla de nuevo es otra consulta, y se
 *  registra. Lo que evita es que cada refresco automático deje un eslabón. */
function useTestigo() {
  return useRef<string | undefined>(undefined);
}

/** La ruta abierta del conductor, si la tiene. Es lo que permite retomar el
 *  modo ruta tras cerrar el navegador. */
export function useRutaActiva(habilitado = true) {
  const testigo = useTestigo();
  return useQuery({
    queryKey: claves.rutaActiva,
    queryFn: async () => {
      const datos = await api.rutaActiva(testigo.current);
      testigo.current = datos.testigo ?? undefined;
      return datos;
    },
    enabled: habilitado,
    refetchInterval: REFRESCO_RUTA_PROPIA_MS,
    staleTime: 0,
    ...reintento,
  });
}

export function useRutas(estado: "activas" | "finalizadas") {
  const testigo = useTestigo();
  return useQuery({
    queryKey: claves.rutas(estado),
    queryFn: async () => {
      const datos = await api.rutas(estado, testigo.current);
      testigo.current = datos.testigo;
      return datos;
    },
    // Solo las activas se mueven. Las finalizadas no cambian: refrescarlas
    // cada diez segundos sería pagar invocaciones por nada.
    refetchInterval: estado === "activas" ? REFRESCO_SEGUIMIENTO_MS : false,
    refetchIntervalInBackground: false,
    staleTime: 0,
    ...reintento,
  });
}

/** Una ruta con su recorrido, que se va completando.
 *
 *  La primera consulta trae el recorrido entero; las siguientes, solo lo
 *  posterior a la última posición conocida, y se suma a lo que ya había. Pedir
 *  el recorrido completo cada diez segundos sería descargar seis horas de
 *  posiciones para dibujar las dos últimas. */
export function useRecorrido(rutaId: string | null, vivo: boolean) {
  const cliente = useQueryClient();
  const testigo = useTestigo();
  return useQuery({
    queryKey: claves.recorrido(rutaId ?? ""),
    queryFn: async () => {
      const previo = cliente.getQueryData<{ ruta: Ruta; posiciones: PosicionRuta[] }>(
        claves.recorrido(rutaId!),
      );
      const desde = previo?.posiciones.at(-1)?.capturada_en;
      const datos = await api.ruta(rutaId!, { desde, testigo: testigo.current });
      testigo.current = datos.testigo;
      return {
        ruta: datos.ruta,
        posiciones: desde ? [...(previo?.posiciones ?? []), ...datos.posiciones] : datos.posiciones,
      };
    },
    enabled: Boolean(rutaId),
    refetchInterval: vivo ? REFRESCO_SEGUIMIENTO_MS : false,
    refetchIntervalInBackground: false,
    staleTime: 0,
    ...reintento,
  });
}

export function useUbicacionPublica(envioId: string | null, habilitado: boolean) {
  return useQuery({
    queryKey: claves.ubicacionPublica(envioId ?? ""),
    queryFn: () => api.ubicacionPublica(envioId!),
    enabled: Boolean(envioId) && habilitado,
    refetchInterval: REFRESCO_PUBLICO_MS,
    refetchIntervalInBackground: false,
    staleTime: 0,
    ...reintento,
  });
}

export function useIniciarRuta() {
  const invalidar = useInvalidarTrasEscritura();
  return useMutation<
    Awaited<ReturnType<typeof api.iniciarRuta>>,
    ErrorApi,
    { envios: string[]; ubicacion?: LecturaGps }
  >({
    mutationFn: ({ envios, ubicacion }) => api.iniciarRuta(envios, ubicacion),
    onSuccess: invalidar,
  });
}

export function useFinalizarRuta() {
  const invalidar = useInvalidarTrasEscritura();
  return useMutation<Awaited<ReturnType<typeof api.finalizarRuta>>, ErrorApi, { rutaId: string; nota?: string }>(
    {
      mutationFn: ({ rutaId, nota }) => api.finalizarRuta(rutaId, nota),
      onSuccess: invalidar,
    },
  );
}

// --------------------------------------------------------------------------- //
// Datos maestros
// --------------------------------------------------------------------------- //

export function useTiendas() {
  return useQuery({ queryKey: claves.tiendas, queryFn: api.tiendas, ...reintento });
}

export function useClientes() {
  return useQuery({ queryKey: claves.clientes, queryFn: api.clientes, ...reintento });
}

export function useTransportistas() {
  return useQuery({
    queryKey: claves.transportistas,
    queryFn: api.transportistas,
    ...reintento,
  });
}

/** Los mensajeros activos de la empresa, para asignarles un envío. */
export function useMensajeros(habilitado = true) {
  return useQuery({
    queryKey: claves.mensajeros,
    queryFn: api.mensajeros,
    enabled: habilitado,
    staleTime: 5 * 60_000,
    ...reintento,
  });
}

export function useUsuarios(habilitado = true) {
  return useQuery({
    queryKey: claves.usuarios,
    queryFn: api.usuarios,
    enabled: habilitado,
    ...reintento,
  });
}

// --------------------------------------------------------------------------- //
// Escrituras
// --------------------------------------------------------------------------- //

/* Toda escritura invalida las consultas que pudo afectar. La bitácora y el
 * tablero se invalidan siempre: cada operación deja un eslabón y mueve un
 * indicador, y una vista de auditoría desactualizada es peor que ninguna. */
function useInvalidarTrasEscritura(envioId?: string) {
  const cliente = useQueryClient();
  return async () => {
    await Promise.all([
      cliente.invalidateQueries({ queryKey: claves.envios }),
      cliente.invalidateQueries({ queryKey: ["bitacora"] }),
      cliente.invalidateQueries({ queryKey: ["tablero"] }),
      envioId ? cliente.invalidateQueries({ queryKey: claves.envio(envioId) }) : Promise.resolve(),
      envioId ? cliente.invalidateQueries({ queryKey: claves.transiciones(envioId) }) : Promise.resolve(),
      envioId ? cliente.invalidateQueries({ queryKey: claves.evidencias(envioId) }) : Promise.resolve(),
      // Una entrega cambia la parada de su ruta: el modo ruta y el mapa de
      // seguimiento tienen que verla sin esperar a su siguiente refresco.
      cliente.invalidateQueries({ queryKey: ["rutas"] }),
    ]);
  };
}

export function useCrearEnvio() {
  const invalidar = useInvalidarTrasEscritura();
  return useMutation<Awaited<ReturnType<typeof api.crearEnvio>>, ErrorApi, DatosEnvio>({
    mutationFn: api.crearEnvio,
    onSuccess: invalidar,
  });
}

export function useCrearLote() {
  const invalidar = useInvalidarTrasEscritura();
  return useMutation<Awaited<ReturnType<typeof api.crearLote>>, ErrorApi, DatosEnvio[]>({
    mutationFn: api.crearLote,
    onSuccess: invalidar,
  });
}

export function useAsignarConductor(envioId: string) {
  const invalidar = useInvalidarTrasEscritura(envioId);
  return useMutation({
    mutationFn: (datos: { conductor_sub: string; conductor_nombre: string }) =>
      api.asignarConductor(envioId, datos),
    onSuccess: invalidar,
  });
}

export function useRegistrarEvento(envioId: string) {
  const invalidar = useInvalidarTrasEscritura(envioId);
  return useMutation({
    mutationFn: (datos: { estado: Estado; nota?: string; ubicacion?: Ubicacion; evidencia_id?: string }) =>
      api.registrarEvento(envioId, datos),
    onSuccess: invalidar,
  });
}

export function useVerificarBitacora() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: api.verificarBitacora,
    onSuccess: (datos) => cliente.setQueryData(claves.verificacion, datos),
  });
}

export function useEtiquetas() {
  return useMutation<Awaited<ReturnType<typeof api.etiquetas>>, ErrorApi, string[]>({
    mutationFn: api.etiquetas,
  });
}

// --------------------------------------------------------------------------- //
// Maestros: escrituras
// --------------------------------------------------------------------------- //

function useInvalidarMaestro(clave: readonly unknown[]) {
  const cliente = useQueryClient();
  return () => cliente.invalidateQueries({ queryKey: clave });
}

export function useGuardarTienda() {
  const invalidar = useInvalidarMaestro(claves.tiendas);
  return useMutation<{ tienda: Tienda }, ErrorApi, { id?: string; datos: Partial<Tienda> }>({
    mutationFn: ({ id, datos }) => (id ? api.actualizarTienda(id, datos) : api.crearTienda(datos)),
    onSuccess: invalidar,
  });
}

export function useEliminarTienda() {
  const invalidar = useInvalidarMaestro(claves.tiendas);
  return useMutation<unknown, ErrorApi, string>({
    mutationFn: api.eliminarTienda,
    onSuccess: invalidar,
  });
}

export function useGuardarCliente() {
  const invalidar = useInvalidarMaestro(claves.clientes);
  return useMutation<{ cliente: Cliente }, ErrorApi, { id?: string; datos: Partial<Cliente> }>({
    mutationFn: ({ id, datos }) => (id ? api.actualizarCliente(id, datos) : api.crearCliente(datos)),
    onSuccess: invalidar,
  });
}

export function useEliminarCliente() {
  const invalidar = useInvalidarMaestro(claves.clientes);
  return useMutation<unknown, ErrorApi, string>({
    mutationFn: api.eliminarCliente,
    onSuccess: invalidar,
  });
}

export function useGuardarTransportista() {
  const invalidar = useInvalidarMaestro(claves.transportistas);
  return useMutation<
    { transportista: Transportista },
    ErrorApi,
    { id?: string; datos: Partial<Transportista> }
  >({
    mutationFn: ({ id, datos }) =>
      id ? api.actualizarTransportista(id, datos) : api.crearTransportista(datos),
    onSuccess: invalidar,
  });
}

export function useEliminarTransportista() {
  const invalidar = useInvalidarMaestro(claves.transportistas);
  return useMutation<unknown, ErrorApi, string>({
    mutationFn: api.eliminarTransportista,
    onSuccess: invalidar,
  });
}

// --------------------------------------------------------------------------- //
// Usuarios
// --------------------------------------------------------------------------- //

export function useActualizarModulo() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: ({ clave, disponible, motivo }: { clave: string; disponible: boolean; motivo: string }) =>
      api.actualizarModulo(clave, { disponible, motivo }),
    onSuccess: () => cliente.invalidateQueries({ queryKey: claves.modulos }),
  });
}

export function useGuardarRol() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: ({ clave, nuevo, ...datos }: {
      clave: string;
      nuevo: boolean;
      nombre: string;
      descripcion: string;
      operaciones: string[];
    }) => (nuevo ? api.crearRol({ clave, ...datos }) : api.actualizarRol(clave, datos)),
    onSuccess: async () => {
      await cliente.invalidateQueries({ queryKey: claves.roles });
      // Cambiar permisos cambia lo que el usuario puede ver: la sesión relee
      // sus datos y las pantallas dependientes se recargan.
      await cliente.invalidateQueries({ queryKey: claves.usuarios });
    },
  });
}

export function useEliminarRol() {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (clave: string) => api.eliminarRol(clave),
    onSuccess: () => cliente.invalidateQueries({ queryKey: claves.roles }),
  });
}

export function useCrearUsuario() {
  const invalidar = useInvalidarMaestro(claves.usuarios);
  return useMutation<
    Awaited<ReturnType<typeof api.crearUsuario>>,
    ErrorApi,
    { correo: string; nombre: string; clave: string; grupos: Grupo[]; telefono?: string }
  >({
    mutationFn: api.crearUsuario,
    onSuccess: invalidar,
  });
}

export function useActualizarUsuario() {
  const invalidar = useInvalidarMaestro(claves.usuarios);
  return useMutation<
    Awaited<ReturnType<typeof api.actualizarUsuario>>,
    ErrorApi,
    { correo: string; cambios: { nombre?: string; grupos?: Grupo[]; telefono?: string; activo?: boolean } }
  >({
    mutationFn: ({ correo, cambios }) => api.actualizarUsuario(correo, cambios),
    onSuccess: invalidar,
  });
}

export function useCambiarClave() {
  return useMutation<
    Awaited<ReturnType<typeof api.cambiarClave>>,
    ErrorApi,
    { actual: string; nueva: string }
  >({
    mutationFn: ({ actual, nueva }) => api.cambiarClave(actual, nueva),
  });
}

// --------------------------------------------------------------------------- //
// Evidencia: tres pasos encadenados
// --------------------------------------------------------------------------- //

export type FaseEvidencia = "inactiva" | "solicitando" | "cargando" | "confirmando" | "lista";

export function useCargaDeEvidencia(envioId: string) {
  const invalidar = useInvalidarTrasEscritura(envioId);

  return useMutation({
    mutationFn: async ({
      archivo,
      alCambiarFase,
    }: {
      archivo: File;
      alCambiarFase?: (fase: FaseEvidencia) => void;
    }) => {
      const tipo = (archivo.type || "image/jpeg") as TipoContenido;

      alCambiarFase?.("solicitando");
      const enlace = await api.solicitarEnlace(envioId, {
        nombre_archivo: archivo.name,
        tipo_contenido: tipo,
      });

      // El archivo va directo al almacenamiento: no atraviesa los servicios.
      alCambiarFase?.("cargando");
      await cargarEvidencia(enlace, archivo);

      // El servicio no cree al cliente: comprueba el objeto antes de asociarlo.
      alCambiarFase?.("confirmando");
      const confirmacion = await api.confirmarEvidencia(envioId, enlace.evidencia_id, tipo);

      alCambiarFase?.("lista");
      return confirmacion;
    },
    onSuccess: invalidar,
  });
}
