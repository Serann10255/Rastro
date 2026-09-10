/* Consulta pública del avance de un envío.
 *
 * Es el único punto del sistema que responde sin token, y por eso concentra dos
 * controles: el identificador aleatorio —un consecutivo se recorrería en
 * minutos— y la vista reducida, que devuelve el avance del envío y no la
 * operación de la empresa ni la identidad de sus empleados.
 *
 * Esta pantalla no comparte la estructura del resto: quien llega aquí no tiene
 * cuenta, y mostrarle una navegación de operación solo lo confundiría.
 */

import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useConsultaPublica } from "@/api/consultas";
import { ErrorApi } from "@/api/cliente";
import { SelectorTema } from "@/componentes/Estructura";
import {
  Aviso,
  Boton,
  EtiquetaEstado,
  Esqueleto,
  Tarjeta,
  fechaLegible,
  fechaRelativa,
  textoEstado,
} from "@/componentes/ui";
import { FLUJO_PRINCIPAL } from "@/tipos";
import type { Estado, EventoPublico } from "@/tipos";

export function Rastreo() {
  const [parametros, setParametros] = useSearchParams();
  const inicial = parametros.get("envio") ?? "";

  const [entrada, setEntrada] = useState(inicial);
  const [consultado, setConsultado] = useState<string | null>(inicial || null);

  const { data, isFetching, error } = useConsultaPublica(consultado);

  // El enlace directo permite compartir el avance por mensaje sin dictar el
  // identificador, que es largo justamente por ser aleatorio.
  useEffect(() => {
    if (consultado) setParametros({ envio: consultado }, { replace: true });
  }, [consultado, setParametros]);

  const buscar = (evento: React.FormEvent) => {
    evento.preventDefault();
    setConsultado(entrada.trim());
  };

  return (
    <div className="aplicacion">
      <header className="barra">
        <div className="barra__interior">
          <span className="marca">
            <span className="marca__punto" aria-hidden="true" />
            Rastro
            <span className="marca__lema">consulta de envío</span>
          </span>
          <div className="crece" />
          <SelectorTema />
          <Link to="/acceso" className="boton boton--secundario">
            Acceso de operación
          </Link>
        </div>
      </header>

      <main className="contenido" style={{ maxWidth: "48rem" }}>
        <header className="encabezado-pagina">
          <h1>Consultar un envío</h1>
          <p className="encabezado-pagina__descripcion">
            Escriba el identificador de rastreo que le entregaron. No hace falta crear una cuenta.
          </p>
        </header>

        <Tarjeta>
          <form onSubmit={buscar} className="pila-sm">
            <div className="campo">
              <label className="campo__etiqueta" htmlFor="identificador">
                Identificador de rastreo
              </label>
              <input
                id="identificador"
                className="campo__control mono"
                type="text"
                inputMode="text"
                autoComplete="off"
                spellCheck={false}
                placeholder="00000000-0000-4000-8000-000000000000"
                value={entrada}
                onChange={(evento) => setEntrada(evento.target.value)}
                required
              />
              <span className="campo__ayuda">
                Son 36 caracteres con guiones. Puede pegarlo tal cual lo recibió.
              </span>
            </div>
            <div className="acciones">
              <Boton type="submit" cargando={isFetching} grande>
                Consultar
              </Boton>
            </div>
          </form>
        </Tarjeta>

        {error ? <ErrorConsulta error={error} /> : null}

        {isFetching && !data && <Esqueleto alto="16rem" />}

        {data && !error && (
          <>
            <Tarjeta
              titulo={data.envio.destinatario_nombre}
              ayuda={`Destino: ${data.envio.destino_ciudad}`}
              acciones={<EtiquetaEstado estado={data.envio.estado} conPunto />}
            >
              <ProgresoEnvio estadoActual={data.envio.estado} />
            </Tarjeta>

            <Tarjeta titulo="Avance">
              <ol className="linea">
                {data.eventos.map((evento, indice) => (
                  <PasoPublico key={`${evento.estado}-${indice}`} evento={evento} />
                ))}
              </ol>
            </Tarjeta>

            <p className="texto-xs texto-tenue">
              Consultado el {fechaLegible(data.consultado_en)}. Se muestra el avance del envío; los
              datos de operación de la empresa y la identidad de sus empleados no forman parte de
              esta consulta.
            </p>
          </>
        )}
      </main>
    </div>
  );
}

function ErrorConsulta({ error }: { error: unknown }) {
  if (error instanceof ErrorApi && error.estado === 422) {
    return (
      <Aviso tono="alerta" titulo="El identificador no tiene el formato esperado">
        Debe ser un identificador de 36 caracteres con guiones. Revise que esté completo y que no se
        haya cortado al copiarlo.
      </Aviso>
    );
  }
  if (error instanceof ErrorApi && error.estado === 404) {
    return (
      <Aviso tono="alerta" titulo="No encontramos un envío con ese identificador">
        Compruebe que lo copió completo. Si acaba de recibirlo, espere unos minutos: el envío puede
        no estar registrado todavía.
      </Aviso>
    );
  }
  return (
    <Aviso tono="error" titulo="No fue posible consultar el envío">
      {error instanceof Error ? error.message : "Inténtelo de nuevo en unos momentos."}
    </Aviso>
  );
}

/* Barra de progreso sobre el flujo principal. La incidencia no aparece como un
 * paso más porque no lo es: es una desviación del flujo, y presentarla en la
 * misma línea daría a entender que el envío avanzó cuando se detuvo. */
function ProgresoEnvio({ estadoActual }: { estadoActual: Estado }) {
  const indice = FLUJO_PRINCIPAL.indexOf(estadoActual);
  const enIncidencia = estadoActual === "INCIDENCIA";

  if (enIncidencia) {
    return (
      <Aviso tono="alerta" titulo="El envío está detenido">
        Se reportó una incidencia. La empresa debe autorizar la reanudación.
      </Aviso>
    );
  }

  return (
    <ol
      style={{
        display: "flex",
        gap: "var(--e-1)",
        listStyle: "none",
        margin: 0,
        padding: 0,
        overflowX: "auto",
      }}
    >
      {FLUJO_PRINCIPAL.map((estado, posicion) => {
        const alcanzado = posicion <= indice;
        return (
          <li key={estado} className={`estado-${estado}`} style={{ flex: "1 1 0", minWidth: "4.5rem" }}>
            <div
              style={{
                height: "0.375rem",
                borderRadius: "var(--r-completo)",
                background: alcanzado ? "var(--estado-color)" : "var(--fondo-sutil)",
              }}
            />
            <span
              className="texto-xs"
              style={{
                display: "block",
                marginTop: "var(--e-1)",
                color: alcanzado ? "var(--texto)" : "var(--texto-tenue)",
                fontWeight: posicion === indice ? 700 : 400,
              }}
            >
              {textoEstado(estado)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function PasoPublico({ evento }: { evento: EventoPublico }) {
  return (
    <li className={`linea__paso estado-${evento.estado}`}>
      <span className="linea__estado">{textoEstado(evento.estado)}</span>
      <span className="linea__meta">
        {fechaLegible(evento.ts)} · {fechaRelativa(evento.ts)}
      </span>
      {evento.nota && <p className="linea__nota">{evento.nota}</p>}
      {evento.tiene_evidencia && (
        <span className="linea__meta">Con evidencia de entrega registrada</span>
      )}
    </li>
  );
}
