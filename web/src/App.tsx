/* Rutas y proveedores de la aplicación. */

import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";

import { useSesion } from "@/api/sesion";
import { Estructura } from "@/componentes/Estructura";
import { Aviso, Boton, Tarjeta, Vacio } from "@/componentes/ui";
import { Acceso } from "@/paginas/Acceso";
import { Bitacora } from "@/paginas/Bitacora";
import { EnvioDetalle } from "@/paginas/EnvioDetalle";
import { EnvioNuevo } from "@/paginas/EnvioNuevo";
import { Envios } from "@/paginas/Envios";
import { Panel } from "@/paginas/Panel";
import { Rastreo } from "@/paginas/Rastreo";
import type { Grupo } from "@/tipos";

export function App() {
  return (
    <LimiteDeError>
      <Routes>
        {/* Sin sesión: el destinatario no tiene cuenta. */}
        <Route path="/rastreo" element={<Rastreo />} />
        <Route path="/acceso" element={<Acceso />} />

        <Route element={<RutaProtegida />}>
          <Route element={<Estructura />}>
            <Route path="/panel" element={<Panel />} />
            <Route
              path="/envios"
              element={
                <ExigeGrupo grupos={["administrador", "despachador", "conductor"]}>
                  <Envios />
                </ExigeGrupo>
              }
            />
            <Route
              path="/envios/nuevo"
              element={
                <ExigeGrupo grupos={["administrador", "despachador"]}>
                  <EnvioNuevo />
                </ExigeGrupo>
              }
            />
            <Route path="/envios/:envioId" element={<EnvioDetalle />} />
            <Route
              path="/bitacora"
              element={
                <ExigeGrupo grupos={["auditor"]}>
                  <Bitacora />
                </ExigeGrupo>
              }
            />
          </Route>
        </Route>

        <Route path="/" element={<Navigate to="/panel" replace />} />
        <Route path="*" element={<NoEncontrado />} />
      </Routes>
    </LimiteDeError>
  );
}

/* ---------------------------------------------------------------------- */

function RutaProtegida() {
  const { autenticado } = useSesion();
  const ubicacion = useLocation();

  if (!autenticado) {
    // Se recuerda a dónde iba para devolverlo allí tras entrar: perder el
    // destino obliga a repetir la navegación y, con sesiones de cuatro horas,
    // eso ocurre varias veces al día.
    return <Navigate to="/acceso" replace state={{ desde: ubicacion.pathname + ubicacion.search }} />;
  }
  return <Outlet />;
}

/* La comprobación de grupo en el cliente evita ofrecer caminos que el servidor
 * va a rechazar. No es un control de seguridad: la autorización la decide el
 * servidor en cada operación, y este componente no puede afectarla. */
function ExigeGrupo({ grupos, children }: { grupos: Grupo[]; children: ReactNode }) {
  const { tieneGrupo } = useSesion();
  if (tieneGrupo(...grupos)) return <>{children}</>;

  return (
    <Tarjeta>
      <Vacio
        titulo="Esta sección no corresponde a su rol"
        descripcion={`Está reservada a: ${grupos.join(", ")}. Si intentara la operación de todos modos, el servidor la rechazaría y el intento quedaría en la bitácora.`}
      />
    </Tarjeta>
  );
}

function NoEncontrado() {
  return (
    <div className="contenido">
      <Tarjeta>
        <Vacio
          titulo="Esa página no existe"
          descripcion="Compruebe la dirección o vuelva al panel."
          accion={
            <a href="/panel" className="boton">
              Ir al panel
            </a>
          }
        />
      </Tarjeta>
    </div>
  );
}

/* ---------------------------------------------------------------------- */

/* Un fallo de renderizado no debe dejar la pantalla en blanco: en un
 * dispositivo en vía, una pantalla vacía es indistinguible de una caída del
 * sistema y hace perder tiempo diagnosticando lo que no es. */
class LimiteDeError extends Component<{ children: ReactNode }, { error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Fallo de la interfaz:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="contenido" style={{ paddingBlock: "var(--e-6)" }}>
        <Aviso tono="error" titulo="La interfaz encontró un error">
          {this.state.error.message}
        </Aviso>
        <div className="acciones">
          <Boton onClick={() => window.location.reload()}>Recargar la página</Boton>
          <Boton variante="secundario" onClick={() => this.setState({ error: null })}>
            Intentar continuar
          </Boton>
        </div>
        <p className="texto-xs texto-tenue">
          Los datos ya registrados no se pierden por esto: el servidor conserva el histórico y la
          bitácora.
        </p>
      </div>
    );
  }
}
