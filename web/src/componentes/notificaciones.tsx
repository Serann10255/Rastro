/* Notificaciones emergentes.
 *
 * Existen para confirmar que una acción surtió efecto sin robarle el sitio al
 * contenido. Los errores de una operación concreta se muestran junto al
 * formulario que los produjo, no aquí: un mensaje que desaparece solo no es el
 * lugar para algo que el usuario tiene que leer y corregir.
 */

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { ErrorApi } from "@/api/cliente";

type Tono = "info" | "exito" | "alerta" | "error";

interface Notificacion {
  id: number;
  tono: Tono;
  texto: string;
}

interface ValorNotificaciones {
  avisar: (texto: string, tono?: Tono) => void;
  avisarError: (error: unknown) => void;
}

const Contexto = createContext<ValorNotificaciones | null>(null);

const DURACION_MS = 5000;

export function ProveedorNotificaciones({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Notificacion[]>([]);

  const avisar = useCallback((texto: string, tono: Tono = "info") => {
    const id = Date.now() + Math.random();
    setAvisos((previos) => [...previos, { id, tono, texto }]);
    window.setTimeout(() => {
      setAvisos((previos) => previos.filter((aviso) => aviso.id !== id));
    }, DURACION_MS);
  }, []);

  const avisarError = useCallback(
    (error: unknown) => {
      avisar(mensajeDeError(error), "error");
    },
    [avisar],
  );

  const valor = useMemo(() => ({ avisar, avisarError }), [avisar, avisarError]);

  return (
    <Contexto.Provider value={valor}>
      {children}
      {/* `aria-live=polite` anuncia sin interrumpir lo que el usuario esté haciendo. */}
      <div className="avisos-flotantes" role="status" aria-live="polite">
        {avisos.map((aviso) => (
          <div key={aviso.id} className={`aviso-flotante aviso--${aviso.tono}`}>
            <span className="aviso-flotante__barra" aria-hidden="true" />
            <span className="min-cero">{aviso.texto}</span>
          </div>
        ))}
      </div>
    </Contexto.Provider>
  );
}

export function useNotificaciones(): ValorNotificaciones {
  const valor = useContext(Contexto);
  if (!valor) throw new Error("useNotificaciones debe usarse dentro de ProveedorNotificaciones.");
  return valor;
}

/* Traduce un error a algo que el usuario pueda entender y, cuando aplica,
 * hacer algo al respecto. Los códigos de dominio del backend permiten decir por
 * qué falló sin inspeccionar cadenas de texto. */
export function mensajeDeError(error: unknown): string {
  if (error instanceof ErrorApi) {
    switch (error.codigo) {
      case "SIN_CONEXION":
        return "Sin conexión. El registro no se guardó; inténtelo de nuevo cuando tenga señal.";
      case "NO_AUTORIZADO":
        return "Su rol no puede ejecutar esa operación. El intento quedó registrado en la bitácora.";
      case "NO_ENCONTRADO":
        return "El envío no existe o no pertenece a su organización.";
      case "TRANSICION_INVALIDA": {
        const permitidas = error.transicionesPermitidas;
        return permitidas.length
          ? `${error.message} Desde el estado actual solo se puede pasar a: ${permitidas
              .map((estado) => estado.replace(/_/g, " "))
              .join(", ")}.`
          : error.message;
      }
      case "NO_AUTENTICADO":
        // El servidor sabe por qué rechazó: unas credenciales incorrectas no
        // son una sesión caducada, y decir lo segundo cuando pasó lo primero
        // manda al usuario a reintentar en vez de a revisar lo que escribió.
        // El texto por omisión queda para el 401 que emite el propio cliente
        // cuando no hay sesión guardada.
        return error.message || "La sesión expiró. Vuelva a entrar.";
      default:
        return error.message;
    }
  }
  return error instanceof Error ? error.message : "Ocurrió un error inesperado.";
}
