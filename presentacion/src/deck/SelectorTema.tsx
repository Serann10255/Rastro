/* Interruptor de tema.
 *
 * El mismo control que el de las dos interfaces (web/src/componentes/Estructura.tsx):
 * mismo ciclo sistema → claro → oscuro, mismos símbolos y la misma pieza del
 * sistema de diseño. Difieren en dos cosas deliberadas: aquí el tema por omisión
 * es el claro, porque un proyector lava el oscuro, y la preferencia se guarda
 * con su propia clave, para que quien usa la aplicación en oscuro no proyecte
 * en oscuro sin darse cuenta.
 */

import { useEffect, useState } from "react";

export const CLAVE_TEMA = "presentacion.tema";
type Tema = "sistema" | "claro" | "oscuro";

function temaGuardado(): Tema {
  try {
    const valor = localStorage.getItem(CLAVE_TEMA);
    return valor === "sistema" || valor === "oscuro" || valor === "claro" ? valor : "claro";
  } catch {
    return "claro";
  }
}

export function SelectorTema() {
  const [tema, setTema] = useState<Tema>(temaGuardado);

  useEffect(() => {
    const raiz = document.documentElement;
    if (tema === "sistema") raiz.removeAttribute("data-tema");
    else raiz.setAttribute("data-tema", tema);
    try {
      localStorage.setItem(CLAVE_TEMA, tema);
    } catch {
      /* Almacenamiento bloqueado: el tema dura lo que la pestaña. */
    }
  }, [tema]);

  const siguiente: Record<Tema, Tema> = { sistema: "claro", claro: "oscuro", oscuro: "sistema" };
  const rotulo: Record<Tema, string> = {
    sistema: "Tema del sistema",
    claro: "Tema claro",
    oscuro: "Tema oscuro",
  };

  return (
    <button
      type="button"
      className="boton boton--sutil boton--icono"
      onClick={() => setTema(siguiente[tema])}
      title={rotulo[tema]}
      aria-label={`${rotulo[tema]}. Pulse para cambiar.`}
    >
      {tema === "claro" ? "☀" : tema === "oscuro" ? "☾" : "◐"}
    </button>
  );
}

/** Al imprimir se usa siempre el tema claro: el guion en papel no debe gastar
 *  tinta en un fondo oscuro. Se restaura la elección al terminar. */
export function imprimirEnClaro(): () => void {
  let anterior: string | null = null;
  const antes = () => {
    anterior = document.documentElement.getAttribute("data-tema");
    document.documentElement.setAttribute("data-tema", "claro");
  };
  const despues = () => {
    if (anterior === null) document.documentElement.removeAttribute("data-tema");
    else document.documentElement.setAttribute("data-tema", anterior);
  };
  window.addEventListener("beforeprint", antes);
  window.addEventListener("afterprint", despues);
  return () => {
    window.removeEventListener("beforeprint", antes);
    window.removeEventListener("afterprint", despues);
  };
}
