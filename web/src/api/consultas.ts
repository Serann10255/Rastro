/* Estado del servidor con React Query.
 *
 * La razón de usarlo en lugar de `useEffect` con `fetch` no es comodidad: es
 * que el conductor trabaja con conectividad intermitente, y aquí quedan
 * centralizados el reintento, la invalidación tras una escritura y el estado de
 * «recargando sin borrar lo que ya se ve». Escribir eso a mano en cada pantalla
 * es donde aparecen las incoherencias.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { UseMutationOptions } from "@tanstack/react-query";

import { ErrorApi, api, cargarEvidencia } from "@/api/cliente";
import type { Estado, Resultado, TipoContenido, Ubicacion } from "@/tipos";

/** Claves de caché. Centralizarlas evita invalidaciones que no aciertan. */
export const claves = {
  envios: ["envios"] as const,
  envio: (id: string) => ["envio", id] as const,
  transiciones: (id: string) => ["transiciones", id] as const,
  evidencias: (id: string) => ["evidencias", id] as const,
  bitacora: (filtro?: Resultado) => ["bitacora", filtro ?? "todos"] as const,
  verificacion: ["bitacora", "verificacion"] as const,
  publico: (id: string) => ["publico", id] as const,
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

export const opcionesReintento = { retry: reintentarSoloFallosTransitorios };

// --------------------------------------------------------------------------- //
// Lecturas
// --------------------------------------------------------------------------- //

export function useEnvios() {
  return useQuery({
    queryKey: claves.envios,
    queryFn: () => api.listarEnvios(),
    ...opcionesReintento,
  });
}

export function useEnvio(envioId: string | undefined) {
  return useQuery({
    queryKey: claves.envio(envioId ?? ""),
    queryFn: () => api.consultarEnvio(envioId!),
    enabled: Boolean(envioId),
    ...opcionesReintento,
  });
}

export function useTransiciones(envioId: string | undefined) {
  return useQuery({
    queryKey: claves.transiciones(envioId ?? ""),
    queryFn: () => api.transiciones(envioId!),
    enabled: Boolean(envioId),
    ...opcionesReintento,
  });
}

export function useEvidencias(envioId: string | undefined, habilitado: boolean) {
  return useQuery({
    queryKey: claves.evidencias(envioId ?? ""),
    queryFn: () => api.listarEvidencias(envioId!),
    enabled: Boolean(envioId) && habilitado,
    ...opcionesReintento,
  });
}

export function useBitacora(filtro?: Resultado) {
  return useQuery({
    queryKey: claves.bitacora(filtro),
    queryFn: () => api.bitacora({ resultado: filtro }),
    ...opcionesReintento,
  });
}

export function useConsultaPublica(envioId: string | null) {
  return useQuery({
    queryKey: claves.publico(envioId ?? ""),
    queryFn: () => api.consultaPublica(envioId!),
    enabled: Boolean(envioId),
    ...opcionesReintento,
  });
}

// --------------------------------------------------------------------------- //
// Escrituras
// --------------------------------------------------------------------------- //

/* Toda escritura invalida las consultas que pudo afectar. La bitácora se
 * invalida siempre: cada operación deja un eslabón, tanto si se autorizó como
 * si se rechazó, y una vista de auditoría desactualizada es peor que ninguna. */
function useInvalidarTrasEscritura(envioId?: string) {
  const cliente = useQueryClient();
  return async () => {
    await Promise.all([
      cliente.invalidateQueries({ queryKey: claves.envios }),
      cliente.invalidateQueries({ queryKey: ["bitacora"] }),
      envioId ? cliente.invalidateQueries({ queryKey: claves.envio(envioId) }) : Promise.resolve(),
      envioId ? cliente.invalidateQueries({ queryKey: claves.transiciones(envioId) }) : Promise.resolve(),
      envioId ? cliente.invalidateQueries({ queryKey: claves.evidencias(envioId) }) : Promise.resolve(),
    ]);
  };
}

type OpcionesMutacion<TDatos, TVariables> = Omit<
  UseMutationOptions<TDatos, ErrorApi, TVariables>,
  "mutationFn"
>;

export function useCrearEnvio(opciones?: OpcionesMutacion<Awaited<ReturnType<typeof api.crearEnvio>>, Parameters<typeof api.crearEnvio>[0]>) {
  const invalidar = useInvalidarTrasEscritura();
  return useMutation({
    mutationFn: api.crearEnvio,
    onSuccess: async (...argumentos) => {
      await invalidar();
      await opciones?.onSuccess?.(...argumentos);
    },
    ...opciones,
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
