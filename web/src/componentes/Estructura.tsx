/* Armazón de la aplicación: marca, navegación por rol e identidad de la sesión.
 *
 * La navegación **sale de la base de datos**, no de una lista escrita aquí. Cada
 * organización tiene sus módulos en la tabla de maestros, y esta pantalla los
 * pinta filtrados por el grupo del usuario. Escribirlos aquí obligaría a
 * recompilar el sitio para dar de alta un módulo y haría imposible que dos
 * empresas vieran cosas distintas.
 *
 * El filtro por grupo no es un control de seguridad —el servidor decide en cada
 * operación— sino de claridad: ofrecerle a un conductor un botón de «bitácora»
 * que siempre responderá 403 solo produce intentos fallidos y ruido en la
 * auditoría.
 *
 * En pantalla estrecha el armazón es una barra superior con la navegación
 * deslizable; a partir de 1024px es una columna lateral. Es el mismo bloque con
 * otra rejilla, de modo que no pueden desincronizarse.
 */

import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { configuracionActual } from "@/api/cliente";
import { useEnvios, useEstadosFinales, useModulos } from "@/api/consultas";
import { useSesion } from "@/api/sesion";
import { Boton } from "@/componentes/ui";
import { Icono } from "@design/marca/iconos";
import { LogotipoRastro } from "@design/marca/rastro";

interface EntradaNavegacion {
  a: string;
  texto: string;
  icono: string;
  exacta: boolean;
  contador?: number;
}

export function Estructura() {
  const { usuario, empresa, salir, tieneGrupo } = useSesion();
  const ubicacion = useLocation();
  const { data: envios } = useEnvios();
  const { data: modulos } = useModulos();

  const esFinal = useEstadosFinales();

  const soloConductor = tieneGrupo("conductor") && !tieneGrupo("administrador", "despachador");
  const pendientes = (envios?.envios ?? []).filter((envio) => !esFinal(envio.estado)).length;

  const entradas = useMemo(() => {
    const disponibles = (modulos?.modulos ?? []).filter(
      (modulo) => modulo.disponible && tieneGrupo(...modulo.grupos),
    );

    const secciones: EntradaNavegacion[] = disponibles
      // Qué módulos suben a la navegación principal lo dice el propio módulo:
      // una barra con catorce entradas no es una barra, es una lista, y cuál
      // merece estar arriba depende de la operación de cada empresa.
      .filter((modulo) => modulo.destacado)
      .map((modulo) => ({
        a: modulo.ruta,
        // El conductor no ve «Órdenes» sino «Mis envíos»: el servidor solo le
        // devuelve los suyos, y llamarlo igual que al listado completo daría a
        // entender que la empresa mueve seis envíos.
        texto: modulo.clave === "ordenes" && soloConductor ? "Mis envíos" : modulo.nombre,
        icono: modulo.icono,
        contador: modulo.clave === "ordenes" ? pendientes : undefined,
        exacta: modulo.clave === "ordenes",
      }));

    // Panel y Operaciones no son módulos: son las dos pantallas que enmarcan a
    // los demás. Van siempre, en los extremos.
    const inicio: EntradaNavegacion = { a: "/panel", texto: "Panel", icono: "panel", exacta: false };
    const centro: EntradaNavegacion[] = tieneGrupo("administrador", "despachador", "conductor", "auditor")
      ? [{ a: "/operaciones", texto: "Operaciones", icono: "estados", exacta: false }]
      : [];

    return [inicio, ...secciones, ...centro];
  }, [modulos, pendientes, soloConductor, tieneGrupo]);

  return (
    <div className="aplicacion aplicacion--con-lateral">
      <a className="salto-contenido" href="#contenido">
        Ir al contenido
      </a>

      <header className="armazon">
        <NavLink to="/panel" className="marca armazon__marca">
          <span className="marca__simbolo" aria-hidden="true">
            <LogotipoRastro tamano={22} id="marca-armazon" />
          </span>
          <span className="marca__texto">
            <span className="marca__nombre">Rastro</span>
            <span className="marca__lema">Trazabilidad de envíos</span>
          </span>
        </NavLink>

        {entradas.length > 1 && (
          <nav className="navegacion" aria-label="Secciones">
            <div className="navegacion__interior">
              {entradas.map((entrada) => (
                <NavLink
                  key={entrada.a}
                  to={entrada.a}
                  className="navegacion__enlace"
                  end={entrada.exacta}
                >
                  <span className="navegacion__icono">
                    <Icono nombre={entrada.icono} tamano={17} />
                  </span>
                  {entrada.texto}
                  {entrada.contador ? (
                    <span className="navegacion__contador">{entrada.contador}</span>
                  ) : null}
                </NavLink>
              ))}
            </div>
          </nav>
        )}

        <div className="armazon__identidad">
          {empresa && (
            <span className="insignia-org" title={`${empresa.nombre} · ${empresa.org_id}`}>
              {empresa.nombre}
            </span>
          )}
          {usuario && (
            <span className="identidad__persona">
              <span className="identidad__nombre">{usuario.nombre}</span>
              <span className="identidad__rol">{usuario.grupos.join(" · ")}</span>
            </span>
          )}
        </div>

        <div className="armazon__acciones">
          <SelectorTema />
          {usuario && (
            <Boton variante="secundario" onClick={() => void salir()}>
              Salir
            </Boton>
          )}
        </div>
      </header>

      <div className="marco">
        <main id="contenido" className="contenido" key={ubicacion.pathname}>
          <Outlet />
        </main>

        <PieDePagina />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */

const CLAVE_TEMA = "rastro.tema";
type Tema = "sistema" | "claro" | "oscuro";

export function SelectorTema() {
  const [tema, setTema] = useState<Tema>(() => {
    try {
      return (localStorage.getItem(CLAVE_TEMA) as Tema) ?? "sistema";
    } catch {
      return "sistema";
    }
  });

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
  const { empresa } = useSesion();

  return (
    <footer className="pie">
      <span>
        Entorno <strong>{config.entorno}</strong> · región {config.region}
      </span>
      {empresa?.nit && <span>NIT {empresa.nit}</span>}
      <span>Datos sintéticos: el sistema no trata información de titulares reales.</span>
      <a href="/rastreo">Consulta pública de un envío</a>
    </footer>
  );
}
