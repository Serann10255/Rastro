/* Estructura común: barra superior, navegación por rol y pie.
 *
 * La navegación se arma a partir de los grupos del token. No es un control de
 * seguridad —el servidor decide en cada operación— sino de claridad: ofrecerle
 * a un conductor un botón de «bitácora» que siempre responderá 403 solo produce
 * intentos fallidos y ruido en la auditoría.
 */

import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { configuracionActual } from "@/api/cliente";
import { useAvisoDeCaducidad, useSesion } from "@/api/sesion";
import { useEnvios } from "@/api/consultas";
import { Aviso, Boton } from "@/componentes/ui";
import type { Grupo } from "@/tipos";

interface EntradaNavegacion {
  a: string;
  texto: string;
  grupos: Grupo[];
  contador?: number;
}

export function Estructura() {
  const { usuario, salir, tieneGrupo, segundosRestantes } = useSesion();
  const avisarCaducidad = useAvisoDeCaducidad();
  const ubicacion = useLocation();
  const { data: envios } = useEnvios();

  const pendientes = (envios?.envios ?? []).filter((envio) => envio.estado !== "ENTREGADO").length;

  const entradas: EntradaNavegacion[] = [
    { a: "/panel", texto: "Panel", grupos: ["administrador", "despachador", "conductor", "auditor"] },
    {
      a: "/envios",
      texto: tieneGrupo("conductor") && !tieneGrupo("despachador") ? "Mis envíos" : "Envíos",
      grupos: ["administrador", "despachador", "conductor"],
      contador: pendientes,
    },
    { a: "/envios/nuevo", texto: "Registrar", grupos: ["administrador", "despachador"] },
    { a: "/bitacora", texto: "Bitácora", grupos: ["auditor"] },
  ];

  const visibles = entradas.filter((entrada) => tieneGrupo(...entrada.grupos));

  return (
    <div className="aplicacion">
      <a className="salto-contenido" href="#contenido">
        Ir al contenido
      </a>

      <header className="barra">
        <div className="barra__interior">
          <NavLink to="/panel" className="marca">
            <span className="marca__punto" aria-hidden="true" />
            Rastro
            <span className="marca__lema">trazabilidad verificable</span>
          </NavLink>

          <div className="crece" />

          {usuario && (
            <>
              <span className="insignia-org" title={`Organización ${usuario.org_id}`}>
                {usuario.org_id}
              </span>
              <span className="texto-sm texto-suave" style={{ minWidth: 0 }}>
                <strong style={{ color: "var(--texto)" }}>{usuario.nombre || usuario.email}</strong>
                <span className="texto-xs"> · {usuario.grupos.join(", ")}</span>
              </span>
            </>
          )}

          <SelectorTema />

          {usuario && (
            <Boton variante="secundario" onClick={() => salir()}>
              Salir
            </Boton>
          )}
        </div>
      </header>

      {visibles.length > 1 && (
        <nav className="navegacion" aria-label="Secciones">
          <div className="navegacion__interior">
            {visibles.map((entrada) => (
              <NavLink
                key={entrada.a}
                to={entrada.a}
                className="navegacion__enlace"
                end={entrada.a === "/envios"}
              >
                {entrada.texto}
                {entrada.contador ? (
                  <span className="navegacion__contador">{entrada.contador}</span>
                ) : null}
              </NavLink>
            ))}
          </div>
        </nav>
      )}

      <main id="contenido" className="contenido" key={ubicacion.pathname}>
        {avisarCaducidad && (
          <Aviso tono="alerta" titulo="La sesión está por expirar">
            Le quedan unos {Math.ceil((segundosRestantes ?? 0) / 60)} minutos. Termine lo que esté
            haciendo y vuelva a entrar: las credenciales del laboratorio duran cuatro horas.
          </Aviso>
        )}
        <Outlet />
      </main>

      <PieDePagina />
    </div>
  );
}

/* ---------------------------------------------------------------------- */

const CLAVE_TEMA = "rastro.tema";
type Tema = "sistema" | "claro" | "oscuro";

export function SelectorTema() {
  const [tema, setTema] = useState<Tema>(() => (localStorage.getItem(CLAVE_TEMA) as Tema) ?? "sistema");

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
  const rotulo: Record<Tema, string> = { sistema: "Tema del sistema", claro: "Tema claro", oscuro: "Tema oscuro" };

  return (
    <Boton
      variante="sutil"
      className="boton--icono"
      onClick={() => setTema(siguiente[tema])}
      title={rotulo[tema]}
      aria-label={`${rotulo[tema]}. Pulse para cambiar.`}
    >
      {tema === "claro" ? "☀" : tema === "oscuro" ? "☾" : "◐"}
    </Boton>
  );
}

export function PieDePagina() {
  const config = configuracionActual();
  return (
    <footer className="pie">
      <span>
        Entorno <strong>{config.entorno}</strong> · región {config.region}
      </span>
      <span>Datos sintéticos: el sistema no trata información de titulares reales.</span>
      <a href="/rastreo">Consulta pública de un envío</a>
    </footer>
  );
}
