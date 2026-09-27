/* Interruptor de tema.
 *
 * El mismo control que el de las dos interfaces (web/src/componentes/Estructura.tsx):
 * mismo ciclo sistema → claro → oscuro, mismos símbolos y la misma pieza del
 * sistema de diseño. Difieren en dos cosas deliberadas: aquí el tema por omisión
 * es el claro, porque un proyector lava el oscuro, y la preferencia se guarda
 * con su propia clave, para que quien usa la aplicación en oscuro no proyecte
 * en oscuro sin darse cuenta.
 *
 * `?tema=oscuro` (o `claro`, o `sistema`) en la dirección abre la página con ese
 * tema sin guardarlo como preferencia: sirve para generar el PDF oscuro desde la
 * terminal, donde no hay botón que pulsar.
 */

import { useEffect, useRef, useState } from "react";

export const CLAVE_TEMA = "presentacion.tema";
type Tema = "sistema" | "claro" | "oscuro";

function esTema(valor: string | null): valor is Tema {
  return valor === "sistema" || valor === "oscuro" || valor === "claro";
}

function temaDeLaDireccion(): Tema | null {
  const valor = new URLSearchParams(window.location.search).get("tema");
  return esTema(valor) ? valor : null;
}

function temaInicial(): Tema {
  const deLaDireccion = temaDeLaDireccion();
  if (deLaDireccion) return deLaDireccion;
  try {
    const valor = localStorage.getItem(CLAVE_TEMA);
    return esTema(valor) ? valor : "claro";
  } catch {
    return "claro";
  }
}

export function SelectorTema() {
  const [tema, setTema] = useState<Tema>(temaInicial);
  // El tema que llega en la dirección es de esta visita; solo lo que se elige
  // con el botón pasa a ser la preferencia guardada.
  const elegidoConElBoton = useRef(false);

  useEffect(() => {
    const raiz = document.documentElement;
    if (tema === "sistema") raiz.removeAttribute("data-tema");
    else raiz.setAttribute("data-tema", tema);
    if (temaDeLaDireccion() && !elegidoConElBoton.current) return;
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
      onClick={() => {
        elegidoConElBoton.current = true;
        setTema(siguiente[tema]);
      }}
      title={rotulo[tema]}
      aria-label={`${rotulo[tema]}. Pulse para cambiar.`}
    >
      {tema === "claro" ? "☀" : tema === "oscuro" ? "☾" : "◐"}
    </button>
  );
}

/**
 * Se imprime con el tema que se está viendo, tanto el guion como el PDF de solo
 * diapositivas: lo que sale es lo que había en pantalla. Si el tema es el del
 * sistema, se resuelve en el momento de imprimir y se fija, para no depender de
 * cómo trate cada navegador esa preferencia al imprimir. Al terminar se
 * restaura la elección.
 */
export function temaAlImprimir(): () => void {
  let anterior: string | null = null;
  const antes = () => {
    const raiz = document.documentElement;
    anterior = raiz.getAttribute("data-tema");
    const seVeOscuro =
      anterior === "oscuro" ||
      (anterior === null && window.matchMedia("(prefers-color-scheme: dark)").matches);
    raiz.setAttribute("data-tema", seVeOscuro ? "oscuro" : "claro");
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
