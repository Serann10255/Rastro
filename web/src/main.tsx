/* Punto de entrada.
 *
 * La configuración se carga antes de montar la aplicación: si la interfaz
 * arrancara sin saber contra qué API habla, la primera petición fallaría y el
 * usuario vería un error que no tiene nada que ver con lo que hizo.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { cargarConfiguracion } from "@/api/cliente";
import { ProveedorSesion } from "@/api/sesion";
import { App } from "@/App";
import { ProveedorNotificaciones } from "@/componentes/notificaciones";

// El sistema de diseño es compartido con Cotejo y vive en `design/`, fuera de
// esta aplicación. La identidad -el color de marca- es lo único propio.
import "@design/tokens.css";
import "@design/base.css";
import "@design/componentes.css";
import "@/estilos/identidad.css";

const clienteConsultas = new QueryClient({
  defaultOptions: {
    queries: {
      // Los datos se consideran frescos un minuto: el conductor consulta la
      // misma pantalla varias veces seguidas y volver a pedirlo cada vez gasta
      // datos móviles sin aportar nada.
      staleTime: 60_000,
      refetchOnWindowFocus: true,
      retry: false,
    },
  },
});

async function iniciar() {
  await cargarConfiguracion();

  const raiz = document.getElementById("raiz");
  if (!raiz) throw new Error("No se encontró el nodo raíz de la aplicación.");

  createRoot(raiz).render(
    <StrictMode>
      <QueryClientProvider client={clienteConsultas}>
        <BrowserRouter>
          <ProveedorNotificaciones>
            <ProveedorSesion>
              <App />
            </ProveedorSesion>
          </ProveedorNotificaciones>
        </BrowserRouter>
      </QueryClientProvider>
    </StrictMode>,
  );
}

void iniciar();
