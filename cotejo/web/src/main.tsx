/* Punto de entrada de la interfaz de auditoria. */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { cargarConfiguracion } from "@/api/cliente";
import { App } from "@/App";

// El mismo sistema de diseño que Rastro, sin copia: una copia por aplicación
// diverge en cuanto alguien corrige un color en una sola.
import "@design/tokens.css";
import "@design/base.css";
import "@design/componentes.css";
import "@/estilos/identidad.css";
import "@/estilos/cotejo.css";

const cliente = new QueryClient({
  defaultOptions: {
    queries: {
      // Los papeles de trabajo no cambian una vez escritos: volver a pedirlos
      // no aporta nada y su valor depende justamente de que sean inmutables.
      staleTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: false,
    },
  },
});

async function iniciar() {
  await cargarConfiguracion();
  const raiz = document.getElementById("raiz");
  if (!raiz) throw new Error("No se encontro el nodo raiz.");

  createRoot(raiz).render(
    <StrictMode>
      <QueryClientProvider client={cliente}>
        <App />
      </QueryClientProvider>
    </StrictMode>,
  );
}

void iniciar();
