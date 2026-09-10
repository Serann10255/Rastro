/* Pantalla de acceso.
 *
 * No lista cuentas ni las rellena: las credenciales las administra el
 * administrador de cada empresa desde el propio sistema. Mostrar usuarios y
 * contraseñas en la pantalla de entrada convertiría el control de acceso en una
 * formalidad, y es de las cosas que sobreviven a la puesta en producción.
 */

import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { configuracionActual } from "@/api/cliente";
import { useSesion } from "@/api/sesion";
import { mensajeDeError } from "@/componentes/notificaciones";
import { SelectorTema } from "@/componentes/Estructura";
import { Aviso, Boton, Campo, Tarjeta } from "@/componentes/ui";
import { LogotipoRastro } from "@design/marca/rastro";

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
      await entrar(correo, clave);
      navegar(destino, { replace: true });
    } catch (fallo) {
      setError(mensajeDeError(fallo));
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="pantalla-acceso">
      <main className="acceso">
        <div className="acceso__marca">
          <span className="marca__simbolo marca__simbolo--grande" aria-hidden="true">
            <LogotipoRastro tamano={30} id="marca-acceso" />
          </span>
          <div>
            <h1 className="acceso__titulo">Rastro</h1>
            <p className="acceso__lema">Trazabilidad verificable de envíos</p>
          </div>
          <div className="crece" />
          <SelectorTema />
        </div>

        <Tarjeta>
          {/* El aviso de la salida anterior desaparece en cuanto hay un error
              del intento actual: dos mensajes distintos sobre el mismo
              formulario se leen como contradictorios, y el que importa es el
              que acaba de ocurrir. */}
          {motivoDeSalida && !error ? (
            <div style={{ marginBottom: "var(--e-4)" }}>
              <Aviso tono="alerta">{motivoDeSalida}</Aviso>
            </div>
          ) : null}

          <form onSubmit={enviar} className="pila-sm" autoComplete="on">
            <Campo
              etiqueta="Correo"
              type="email"
              name="correo"
              autoComplete="username"
              inputMode="email"
              required
              autoFocus
              placeholder="nombre@empresa.com"
              value={correo}
              onChange={(evento) => setCorreo(evento.target.value)}
            />
            <Campo
              etiqueta="Contraseña"
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
            ¿No tiene cuenta? El administrador de su empresa la crea desde el sistema.
          </p>
        </Tarjeta>

        <Tarjeta>
          <p className="texto-sm texto-suave" style={{ margin: 0 }}>
            ¿Espera un envío? <a href="/rastreo">Consulte su avance con el identificador</a>, sin
            necesidad de cuenta.
          </p>
        </Tarjeta>

        <p className="texto-xs texto-tenue" style={{ textAlign: "center" }}>
          Entorno {configuracionActual().entorno} · región {configuracionActual().region}
        </p>
      </main>
    </div>
  );
}
