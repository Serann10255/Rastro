/* Índice: enlaza los dos decks y resume quién presenta qué en cada uno. */

import "@design/tokens.css";
import "@design/base.css";
import "@design/componentes.css";
import "@/estilos/presentacion.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { LogotipoCotejo } from "@design/marca/cotejo";
import { LogotipoRastro } from "@design/marca/rastro";
import cotejo from "@sustentacion/sustentacion-cotejo.md";
import rastro from "@sustentacion/sustentacion-rastro.md";

import { Inicio } from "@/Inicio";

const raiz = document.getElementById("raiz");
if (!raiz) throw new Error("No se encontró el nodo raíz.");

createRoot(raiz).render(
  <StrictMode>
    <Inicio
      decks={[
        { deck: rastro, ruta: "rastro", Logotipo: LogotipoRastro },
        { deck: cotejo, ruta: "cotejo", Logotipo: LogotipoCotejo },
      ]}
    />
  </StrictMode>,
);
