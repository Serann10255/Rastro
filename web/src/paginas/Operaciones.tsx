/* Centro de operaciones: acceso a los módulos del sistema.
 *
 * La lista **sale de la base de datos**, no de una constante escrita aquí. Cada
 * organización tiene sus módulos en la tabla de maestros: dos empresas pueden
 * tener contratado un conjunto distinto, y dar de alta uno nuevo no puede exigir
 * recompilar el sitio.
 *
 * Los módulos que todavía no existen aparecen igualmente, marcados como no
 * disponibles y con la razón. Ocultarlos daría a entender que el sistema no los
 * contempla; mostrarlos activos y que no hagan nada es peor. Decir qué falta y
 * por qué es lo que permite planear.
 */

import { Link } from "react-router-dom";

import { useSesion } from "@/api/sesion";
import {
  useCatalogoEstados,
  useClientes,
  useEnvios,
  useEstadosFinales,
  useModulos,
  useTiendas,
  useTransportistas,
} from "@/api/consultas";
import { Aviso, Tarjeta } from "@/componentes/ui";
import { Icono } from "@design/marca/iconos";
import type { Modulo } from "@/tipos";

export function Operaciones() {
  const { tieneGrupo } = useSesion();
  const { data: modulos, isPending, error } = useModulos();
  const { data: envios } = useEnvios();
  const { data: tiendas } = useTiendas();
  const { data: clientes } = useClientes();
  const { data: transportistas } = useTransportistas();
  const { data: catalogo } = useCatalogoEstados();
  const esFinal = useEstadosFinales();

  /* Los contadores los resuelve la interfaz porque son datos que ya tiene
   * cargados; el módulo solo declara cuál le corresponde. Pedirle al servidor un
   * recuento por módulo serían catorce consultas para pintar un menú. */
  const contadores: Record<string, number | undefined> = {
    envios_abiertos: (envios?.envios ?? []).filter((e) => !esFinal(e.estado)).length,
    tiendas: tiendas?.total,
    clientes: clientes?.total,
    transportistas: transportistas?.total,
    estados: catalogo?.estados.length,
  };

  const visibles = (modulos?.modulos ?? []).filter((modulo) => tieneGrupo(...modulo.grupos));
  const disponibles = visibles.filter((modulo) => modulo.disponible);
  const pendientes = visibles.filter((modulo) => !modulo.disponible);

  const contadorDe = (modulo: Modulo) =>
    modulo.contador ? contadores[modulo.contador] : undefined;

  return (
    <>
      <header className="encabezado-pagina">
        <h1>Operaciones</h1>
        <p className="encabezado-pagina__descripcion">
          Módulos de la organización. Solo aparecen los que corresponden a su rol: ofrecerle un
          acceso que el servidor va a rechazar solo produce intentos fallidos y ruido en la
          auditoría.
        </p>
      </header>

      {error && <Aviso tono="error">No fue posible cargar los módulos de la organización.</Aviso>}

      {isPending ? (
        <p className="texto-sm texto-suave">Cargando módulos…</p>
      ) : (
        <div className="rejilla-modulos">
          {disponibles.map((modulo) => (
            <Link key={modulo.clave} to={modulo.ruta} className="modulo">
              <span className="modulo__icono" aria-hidden="true">
                <Icono nombre={modulo.icono} tamano={20} />
              </span>
              <span className="modulo__texto">
                <span className="modulo__nombre">
                  {modulo.nombre}
                  {contadorDe(modulo) !== undefined && (
                    <span className="modulo__contador">{contadorDe(modulo)}</span>
                  )}
                </span>
                <span className="modulo__descripcion">{modulo.descripcion}</span>
              </span>
            </Link>
          ))}
        </div>
      )}

      {pendientes.length > 0 && (
        <Tarjeta
          titulo="Módulos no disponibles"
          ayuda="Se listan con la razón en lugar de ocultarse: saber qué falta y por qué es lo que permite planear."
        >
          <div className="rejilla-modulos">
            {pendientes.map((modulo) => (
              <div key={modulo.clave} className="modulo modulo--inactivo">
                <span className="modulo__icono" aria-hidden="true">
                  <Icono nombre={modulo.icono} tamano={20} />
                </span>
                <span className="modulo__texto">
                  <span className="modulo__nombre">{modulo.nombre}</span>
                  <span className="modulo__descripcion">{modulo.descripcion}</span>
                  <span className="modulo__motivo">{modulo.motivo}</span>
                </span>
              </div>
            ))}
          </div>
        </Tarjeta>
      )}
    </>
  );
}

/* ---------------------------------------------------------------------- */
/* Catálogo de estados                                                    */
/* ---------------------------------------------------------------------- */

export function CatalogoEstados() {
  const { data, isPending, error } = useCatalogoEstados();

  return (
    <>
      <header className="encabezado-pagina">
        <h1>Catálogo de estados</h1>
        <p className="encabezado-pagina__descripcion">
          Cada estado tiene un código numérico único. El código existe por una razón operativa: es
          lo que viaja en los archivos de intercambio con transportistas y clientes, donde un nombre
          en texto es frágil —cambia con el idioma y con quién escriba el archivo— mientras que un
          número no.
        </p>
      </header>

      <Aviso tono="info" titulo="Los saltos de diez son deliberados">
        Dejan sitio para intercalar estados sin renumerar los existentes, que obligaría a
        reprocesar todo el histórico.
      </Aviso>

      {error && <Aviso tono="error">No fue posible cargar el catálogo.</Aviso>}

      <Tarjeta>
        {isPending ? (
          <p className="texto-sm texto-suave">Cargando…</p>
        ) : (
          <div className="tabla-contenedor">
            <table className="tabla">
              <thead>
                <tr>
                  <th scope="col">Código</th>
                  <th scope="col">Estado</th>
                  <th scope="col">Etiqueta</th>
                  <th scope="col">Fase</th>
                  <th scope="col">Descripción</th>
                  <th scope="col">Cierre</th>
                </tr>
              </thead>
              <tbody>
                {data?.estados.map((estado) => (
                  <tr key={estado.codigo} className={`estado-${estado.estado}`}>
                    <td>
                      <span className="codigo-estado" style={{ fontSize: "var(--t-sm)" }}>
                        {estado.codigo}
                      </span>
                    </td>
                    <td className="mono">{estado.estado}</td>
                    <td>{estado.etiqueta}</td>
                    <td style={{ textTransform: "capitalize" }}>{estado.fase}</td>
                    <td className="envuelve">{estado.descripcion}</td>
                    <td>
                      {estado.final ? (
                        <span className={`etiqueta ${estado.exitoso ? "etiqueta--ALLOW" : "etiqueta--DENY"}`}>
                          {estado.exitoso ? "exitoso" : "por excepción"}
                        </span>
                      ) : (
                        <span className="texto-tenue">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Tarjeta>
    </>
  );
}
