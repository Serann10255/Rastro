/* Texto con formato y utilidades de rotulado. */

import type { Inline, Linea } from "./tipos";

export function EnLinea({ nodos }: { nodos: Inline[] }) {
  return (
    <>
      {nodos.map((nodo, i) => (
        <Nodo key={i} nodo={nodo} />
      ))}
    </>
  );
}

function Nodo({ nodo }: { nodo: Inline }) {
  switch (nodo.t) {
    case "texto":
      return <>{nodo.v}</>;
    case "fuerte":
      return (
        <strong>
          <EnLinea nodos={nodo.hijos} />
        </strong>
      );
    case "enfasis":
      return (
        <em>
          <EnLinea nodos={nodo.hijos} />
        </em>
      );
    case "codigo":
      return <code className="d-codigo">{nodo.v}</code>;
    case "enlace":
      return (
        <a href={nodo.href}>
          <EnLinea nodos={nodo.hijos} />
        </a>
      );
  }
}

/** Varias líneas separadas por saltos: así las escribió el autor. */
export function Lineas({ lineas }: { lineas: Linea[] }) {
  return (
    <>
      {lineas.map((linea, i) => (
        <span className="d-linea" key={i}>
          <EnLinea nodos={linea} />
        </span>
      ))}
    </>
  );
}

export function textoPlano(nodos: Inline[]): string {
  return nodos.map((n) => (n.t === "texto" || n.t === "codigo" ? n.v : textoPlano(n.hijos))).join("");
}

/** «RIESGOS Y CONTROLES» → «Riesgos y controles». Solo si todo va en mayúsculas:
 *  un título escrito con mayúsculas propias se respeta tal cual. */
export function tituloLegible(titulo: string): string {
  if (titulo !== titulo.toLocaleUpperCase("es")) return titulo;
  const minusculas = titulo.toLocaleLowerCase("es");
  return minusculas.charAt(0).toLocaleUpperCase("es") + minusculas.slice(1);
}
