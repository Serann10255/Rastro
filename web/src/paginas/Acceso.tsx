/* Pantalla de acceso.
 *
 * Muestra las cuentas sintéticas porque el sistema se puebla únicamente con
 * datos sintéticos y su propósito es que un evaluador pueda recorrer los cuatro
 * roles y las dos organizaciones sin pedirle credenciales a nadie. En un
 * despliegue con datos reales este bloque no existiría.
 */

import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { configuracionActual } from "@/api/cliente";
import { useSesion } from "@/api/sesion";
import { mensajeDeError } from "@/componentes/notificaciones";
import { SelectorTema } from "@/componentes/Estructura";
import { Aviso, Boton, Campo, Tarjeta } from "@/componentes/ui";

interface CuentaDemo {
  correo: string;
  clave: string;
  rol: string;
  organizacion: string;
  descripcion: string;
}

const CUENTAS: CuentaDemo[] = [
  {
    correo: "despacho@andes.test",
    clave: "Andes.2026",
    rol: "Despachador",
    organizacion: "Mensajería Andes",
    descripcion: "Registra envíos y asigna mensajeros",
  },
  {
    correo: "carlos@andes.test",
    clave: "Andes.2026",
    rol: "Conductor",
    organizacion: "Mensajería Andes",
    descripcion: "Registra puntos de control y carga evidencia",
  },
  {
    correo: "auditor@andes.test",
    clave: "Andes.2026",
    rol: "Auditor",
    organizacion: "Mensajería Andes",
    descripcion: "Consulta la bitácora sin poder modificarla",
  },
  {
    correo: "admin@andes.test",
    clave: "Andes.2026",
    rol: "Administrador",
    organizacion: "Mensajería Andes",
    descripcion: "Mayor nivel de privilegio",
  },
  {
    correo: "despacho@sabana.test",
    clave: "Sabana.2026",
    rol: "Despachador",
    organizacion: "Envíos Sabana",
    descripcion: "Otra empresa sobre la misma infraestructura",
  },
];

export function Acceso() {
  const { autenticado, entrar, motivoDeSalida } = useSesion();
  const navegar = useNavigate();
  const ubicacion = useLocation();

  const [correo, setCorreo] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? "/panel";

  if (autenticado) return <Navigate to={destino} replace />;

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await entrar(correo.trim(), clave);
      navegar(destino, { replace: true });
    } catch (fallo) {
      setError(mensajeDeError(fallo));
    } finally {
      setEnviando(false);
    }
  };

  const usarCuenta = (cuenta: CuentaDemo) => {
    setCorreo(cuenta.correo);
    setClave(cuenta.clave);
    setError(null);
  };

  return (
    <div className="contenido" style={{ maxWidth: "62rem", paddingBlock: "var(--e-6)" }}>
      <div className="fila-entre">
        <div className="marca" style={{ fontSize: "var(--t-xl)" }}>
          <span className="marca__punto" aria-hidden="true" />
          Rastro
          <span className="marca__lema">trazabilidad verificable de envíos</span>
        </div>
        <SelectorTema />
      </div>

      <div className="doble-panel">
        <Tarjeta
          titulo="Entrar"
          ayuda="Cada operación se autoriza en el servidor según el grupo del usuario y su organización."
        >
          {motivoDeSalida && (
            <div style={{ marginBottom: "var(--e-4)" }}>
              <Aviso tono="alerta">{motivoDeSalida}</Aviso>
            </div>
          )}

          <form onSubmit={enviar} className="pila-sm">
            <Campo
              etiqueta="Correo"
              type="email"
              name="usuario"
              autoComplete="username"
              inputMode="email"
              required
              placeholder="despacho@andes.test"
              value={correo}
              onChange={(evento) => setCorreo(evento.target.value)}
            />
            <Campo
              etiqueta="Clave"
              type="password"
              name="clave"
              autoComplete="current-password"
              required
              value={clave}
              onChange={(evento) => setClave(evento.target.value)}
            />

            {error && (
              <Aviso tono="error" titulo="No fue posible entrar">
                {error}
              </Aviso>
            )}

            <div className="acciones">
              <Boton type="submit" cargando={enviando} bloque grande>
                Entrar
              </Boton>
            </div>
          </form>

          <p className="texto-sm texto-suave" style={{ marginTop: "var(--e-4)" }}>
            ¿Espera un envío?{" "}
            <a href="/rastreo">Consulte su avance con el identificador</a>, sin necesidad de cuenta.
          </p>
        </Tarjeta>

        <Tarjeta
          titulo="Cuentas de prueba"
          ayuda="El sistema opera únicamente con datos sintéticos. Las dos organizaciones comparten infraestructura y no deben verse entre sí."
        >
          <ul className="lista">
            {CUENTAS.map((cuenta) => (
              <li key={cuenta.correo}>
                <button type="button" className="envio" onClick={() => usarCuenta(cuenta)}>
                  <span className="envio__linea">
                    <span className="envio__destinatario">{cuenta.rol}</span>
                    <span className="etiqueta">{cuenta.organizacion}</span>
                  </span>
                  <span className="envio__detalle">{cuenta.descripcion}</span>
                  <span className="envio__id">{cuenta.correo}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="texto-xs texto-tenue" style={{ marginTop: "var(--e-3)" }}>
            Pulse una cuenta para rellenar el formulario. Entorno{" "}
            <strong>{configuracionActual().entorno}</strong>.
          </p>
        </Tarjeta>
      </div>
    </div>
  );
}
