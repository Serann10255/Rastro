/* Contexto de sesión: quién está usando el sistema y qué puede hacer.
 *
 * La interfaz oculta lo que un rol no puede hacer, pero eso es comodidad y no
 * control: la autorización la decide el servidor en cada operación. Cualquiera
 * puede editar esta página; nadie puede editar la matriz de autorización.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { almacenSesion, api, registrarManejadorDeSesionExpirada } from "@/api/cliente";
import type { Grupo, Sesion, Usuario } from "@/tipos";

interface ValorSesion {
  sesion: Sesion | null;
  usuario: Usuario | null;
  autenticado: boolean;
  entrar: (usuario: string, clave: string) => Promise<Sesion>;
  salir: (motivo?: string) => void;
  tieneGrupo: (...grupos: Grupo[]) => boolean;
  /** Segundos que le quedan al token, o null si no hay sesión. */
  segundosRestantes: number | null;
  motivoDeSalida: string | null;
}

const ContextoSesion = createContext<ValorSesion | null>(null);

/** Margen con el que se avisa antes de que el token caduque. */
const UMBRAL_AVISO_SEGUNDOS = 5 * 60;

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(() => almacenSesion.leer());
  const [motivoDeSalida, setMotivoDeSalida] = useState<string | null>(null);
  const [ahora, setAhora] = useState(() => Date.now());

  const salir = useCallback((motivo?: string) => {
    almacenSesion.borrar();
    setSesion(null);
    setMotivoDeSalida(motivo ?? null);
  }, []);

  // El cliente avisa cuando el backend rechaza el token: las credenciales del
  // laboratorio duran cuatro horas y caducar a media jornada es lo normal.
  useEffect(() => {
    registrarManejadorDeSesionExpirada(() => {
      setSesion(null);
      setMotivoDeSalida("La sesión expiró. Vuelva a entrar.");
    });
  }, []);

  // Cuenta atrás para poder avisar antes de que caduque, en vez de dejar que el
  // usuario lo descubra al perder un formulario a medio llenar.
  useEffect(() => {
    if (!sesion) return;
    const temporizador = window.setInterval(() => setAhora(Date.now()), 30_000);
    return () => window.clearInterval(temporizador);
  }, [sesion]);

  const entrar = useCallback(async (usuario: string, clave: string) => {
    const nueva = await api.entrar(usuario, clave);
    setSesion(nueva);
    setMotivoDeSalida(null);
    setAhora(Date.now());
    return nueva;
  }, []);

  const valor = useMemo<ValorSesion>(() => {
    const segundosRestantes = sesion
      ? Math.max(0, Math.round((sesion.emitida_en + sesion.vigencia_segundos * 1000 - ahora) / 1000))
      : null;

    return {
      sesion,
      usuario: sesion?.usuario ?? null,
      autenticado: Boolean(sesion),
      entrar,
      salir,
      segundosRestantes,
      motivoDeSalida,
      tieneGrupo: (...grupos: Grupo[]) =>
        Boolean(sesion && grupos.some((grupo) => sesion.usuario.grupos.includes(grupo))),
    };
  }, [sesion, entrar, salir, ahora, motivoDeSalida]);

  return <ContextoSesion.Provider value={valor}>{children}</ContextoSesion.Provider>;
}

export function useSesion(): ValorSesion {
  const valor = useContext(ContextoSesion);
  if (!valor) throw new Error("useSesion debe usarse dentro de ProveedorSesion.");
  return valor;
}

export function useAvisoDeCaducidad(): boolean {
  const { segundosRestantes } = useSesion();
  return segundosRestantes !== null && segundosRestantes > 0 && segundosRestantes <= UMBRAL_AVISO_SEGUNDOS;
}
