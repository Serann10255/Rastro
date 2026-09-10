/* Generación de guías: hoja imprimible con código de barras.
 *
 * El servidor decide qué datos salen en la guía; esta pantalla los compone y
 * los imprime. El PDF no se genera en el servidor a propósito: implicaría una
 * dependencia de composición tipográfica en una función de cómputo bajo
 * demanda, y el navegador ya sabe imprimir a PDF.
 *
 * Lo que el servidor sí decide es el contenido. En particular, la guía no lleva
 * el valor declarado: pegarlo por fuera de la caja le dice a cualquiera cuánto
 * vale lo que hay dentro.
 */

import { useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useEtiquetas } from "@/api/consultas";
import { mensajeDeError } from "@/componentes/notificaciones";
import { CodigoBarras } from "@/componentes/codigo-barras";
import { Aviso, Boton, Esqueleto, Tarjeta, Vacio, fechaLegible } from "@/componentes/ui";
import type { Etiqueta } from "@/tipos";

export function Guias() {
  const navegar = useNavigate();
  const ubicacion = useLocation();
  const identificadores = (ubicacion.state as { envios?: string[] } | null)?.envios ?? [];

  const etiquetas = useEtiquetas();

  useEffect(() => {
    if (identificadores.length) etiquetas.mutate(identificadores);
    // Se pide una sola vez al llegar: las guías no cambian mientras se miran.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (identificadores.length === 0) {
    return (
      <Tarjeta>
        <Vacio
          titulo="No hay envíos seleccionados"
          descripcion="Elija los envíos en el listado y pulse «Generar guías»."
          accion={
            <Link to="/envios" className="boton">
              Ir al listado
            </Link>
          }
        />
      </Tarjeta>
    );
  }

  const datos = etiquetas.data;

  return (
    <>
      <header className="encabezado-pagina no-imprimir">
        <div className="fila-entre">
          <div className="min-cero">
            <h1>Guías</h1>
            <p className="encabezado-pagina__descripcion">
              {datos
                ? `${datos.etiquetas.length} guías listas para imprimir.`
                : "Preparando las guías…"}{" "}
              Use «Imprimir» y elija «Guardar como PDF» si quiere conservarlas.
            </p>
          </div>
          <div className="fila">
            <Boton onClick={() => window.print()} disabled={!datos?.etiquetas.length}>
              Imprimir
            </Boton>
            <Boton variante="secundario" onClick={() => navegar(-1)}>
              Volver
            </Boton>
          </div>
        </div>
      </header>

      {etiquetas.isError && (
        <Aviso tono="error" titulo="No se pudieron generar las guías">
          {mensajeDeError(etiquetas.error)}
        </Aviso>
      )}

      {datos && datos.no_encontrados.length > 0 && (
        <Aviso tono="alerta" titulo={`${datos.no_encontrados.length} envíos sin guía`}>
          No existen o no pertenecen a su organización. El sistema responde igual en ambos casos:
          decir cuál es confirmaría que el otro existe.
        </Aviso>
      )}

      {etiquetas.isPending && <Esqueleto alto="20rem" />}

      {datos && (
        <div className="hoja-guias">
          {datos.etiquetas.map((etiqueta) => (
            <GuiaImprimible key={etiqueta.envio_id} etiqueta={etiqueta} />
          ))}
        </div>
      )}
    </>
  );
}

function GuiaImprimible({ etiqueta }: { etiqueta: Etiqueta }) {
  return (
    <article className="guia">
      <header className="guia__cabecera">
        <div>
          <div className="guia__empresa">{etiqueta.empresa}</div>
          {etiqueta.empresa_nit && <div style={{ fontSize: 10 }}>NIT {etiqueta.empresa_nit}</div>}
        </div>
        <div style={{ textAlign: "right", fontSize: 10 }}>
          <div>{fechaLegible(etiqueta.creado_en).split(",")[0]}</div>
          {etiqueta.fecha_estimada && <div>Entrega: {etiqueta.fecha_estimada}</div>}
        </div>
      </header>

      <div>
        <CodigoBarras valor={etiqueta.envio_id} />
        <div className="guia__codigo">{etiqueta.envio_id}</div>
      </div>

      <div className="guia__bloque">
        <span className="guia__termino">Destinatario</span>
        <span className="guia__destinatario">{etiqueta.destinatario}</span>
        <span className="guia__valor">{etiqueta.direccion}</span>
        {etiqueta.referencia && <span className="guia__valor">{etiqueta.referencia}</span>}
        <span className="guia__valor">
          <strong>{etiqueta.ciudad}</strong>
          {etiqueta.telefono && ` · Tel. ${etiqueta.telefono}`}
        </span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
        <div className="guia__bloque">
          <span className="guia__termino">Origen</span>
          <span className="guia__valor">{etiqueta.tienda_nombre || etiqueta.origen}</span>
        </div>
        <div className="guia__bloque">
          <span className="guia__termino">Transportista</span>
          <span className="guia__valor">{etiqueta.transportista || "por asignar"}</span>
        </div>
      </div>

      {etiqueta.descripcion && (
        <div className="guia__bloque">
          <span className="guia__termino">Contenido</span>
          <span className="guia__valor">{etiqueta.descripcion}</span>
        </div>
      )}

      <footer className="guia__pie">
        <span>
          <strong>{etiqueta.bultos}</strong> bulto{etiqueta.bultos === 1 ? "" : "s"}
        </span>
        {etiqueta.peso_kg > 0 && (
          <span>
            <strong>{etiqueta.peso_kg}</strong> kg
          </span>
        )}
        {etiqueta.orden_compra && <span>OC {etiqueta.orden_compra}</span>}
      </footer>
    </article>
  );
}
