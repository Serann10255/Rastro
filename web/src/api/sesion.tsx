/* Contexto de sesión: quién está usando el sistema, en nombre de qué empresa y
 * qué puede hacer.
 *
 * La interfaz oculta lo que un rol no puede hacer, pero eso es comodidad y no
 * control: la autorización la decide el servidor en cada operación. Cualquiera
 * puede editar esta página; nadie puede editar la matriz de autorización.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { almacenSesion, api, registrarManejadorDeSesion } from "@/api/cliente";
import type { Empresa, Grupo, Sesion, Usuario } from "@/tipos";

interface ValorSesion {
  sesion: Sesion | null;
  usuario: Usuario | null;
  empresa: Empresa | null;
  autenticado: boolean;
  entrar: (correo: string, clave: string) => Promise<Sesion>;
  salir: (motivo?: string, todas?: boolean) => Promise<void>;
  tieneGrupo: (...grupos: Grupo[]) => boolean;
  /** Si la sesión tiene el permiso. Es lo que decide qué ofrecer.
   *
   *  Preguntar por el nombre del rol dejó de servir cuando los roles pasaron a
   *  ser configurables: un rol que la empresa cree mañana no aparece en ninguna
   *  lista escrita en una pantalla, pero sus permisos sí llegan aquí. */
  puede: (...operaciones: string[]) => boolean;
  motivoDeSalida: string | null;
}

const ContextoSesion = createContext<ValorSesion | null>(null);

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(() => almacenSesion.leer());
  const [empresa, setEmpresa] = useState<Empresa | null>(null);
  const [permisos, setPermisos] = useState<string[]>([]);
  const [motivoDeSalida, setMotivoDeSalida] = useState<string | null>(null);

  // El cliente avisa cuando renueva la sesión sola o cuando el servidor la
  // rechaza. Sin este puente, la interfaz seguiría mostrando al usuario de una
  // sesión que ya no existe.
  useEffect(() => {
    registrarManejadorDeSesion((nueva) => {
      setSesion(nueva);
      if (!nueva) {
        setEmpresa(null);
        setPermisos([]);
        setMotivoDeSalida("La sesión expiró. Vuelva a entrar.");
      }
    });
  }, []);

  /* Los datos de la empresa se cargan una vez por sesión. Se piden al servidor
   * y no se guardan en el token: si estuvieran en el token, cambiar el nombre
   * de la empresa no surtiría efecto hasta el siguiente inicio de sesión. */
  useEffect(() => {
    if (!sesion) return;
    let vigente = true;
    api
      .yo()
      .then((datos) => {
        if (!vigente) return;
        setEmpresa(datos.empresa);
        setPermisos(datos.permisos ?? []);
      })
      .catch(() => {
        /* Si falla, la interfaz funciona igual: solo falta el nombre de la
         * empresa en la barra, y insistir no lo arreglaría. */
      });
    return () => {
      vigente = false;
    };
  }, [sesion]);

  const entrar = useCallback(async (correo: string, clave: string) => {
    const nueva = await api.entrar(correo.trim(), clave);
    setSesion(nueva);
    setMotivoDeSalida(null);
    return nueva;
  }, []);

  const salir = useCallback(async (motivo?: string, todas = false) => {
    try {
      // Se revoca en el servidor antes de borrar el token local: al revés, ya
      // no habría con qué autenticar la petición de cierre.
      await api.salir(todas);
    } catch {
      /* Sin conexión el cierre local sigue teniendo sentido. */
    }
    almacenSesion.borrar();
    setSesion(null);
    setEmpresa(null);
    setPermisos([]);
    setMotivoDeSalida(motivo ?? null);
  }, []);

  const valor = useMemo<ValorSesion>(
    () => ({
      sesion,
      usuario: sesion?.usuario ?? null,
      empresa,
      autenticado: Boolean(sesion),
      entrar,
      salir,
      motivoDeSalida,
      tieneGrupo: (...grupos: Grupo[]) =>
        Boolean(sesion && grupos.some((grupo) => sesion.usuario.grupos.includes(grupo))),
      puede: (...operaciones: string[]) =>
        operaciones.some((operacion) => permisos.includes(operacion)),
    }),
    [sesion, empresa, permisos, entrar, salir, motivoDeSalida],
  );

  return <ContextoSesion.Provider value={valor}>{children}</ContextoSesion.Provider>;
}

export function useSesion(): ValorSesion {
  const valor = useContext(ContextoSesion);
  if (!valor) throw new Error("useSesion debe usarse dentro de ProveedorSesion.");
  return valor;
}
