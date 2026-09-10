/* Bitácora de auditoría.
 *
 * Solo el rol auditor la alcanza. La pantalla no ofrece ninguna forma de
 * escribir: los eslabones los producen los demás servicios como efecto de sus
 * operaciones, y el servicio de bitácora no expone rutas de escritura. Aquí eso
 * se refleja en que no hay un solo formulario de edición.
 */

import { useMemo, useState } from "react";

import { useBitacora, useVerificarBitacora } from "@/api/consultas";
import { mensajeDeError } from "@/componentes/notificaciones";
import {
  Aviso,
  Boton,
  Esqueleto,
  EtiquetaResultado,
  GrupoSegmentado,
  Metrica,
  Tarjeta,
  Vacio,
  fechaLegible,
} from "@/componentes/ui";
import type { RegistroBitacora, Resultado } from "@/tipos";

type FiltroResultado = "todos" | Resultado;

export function Bitacora() {
  const [filtro, setFiltro] = useState<FiltroResultado>("todos");
  const [busqueda, setBusqueda] = useState("");
  const [detalle, setDetalle] = useState<RegistroBitacora | null>(null);

  const { data, isPending, error, refetch, isFetching } = useBitacora(
    filtro === "todos" ? undefined : filtro,
  );
  const verificar = useVerificarBitacora();

  const registros = useMemo(() => {
    const termino = busqueda.trim().toLowerCase();
    const lista = data?.registros ?? [];
    const filtrados = termino
      ? lista.filter((registro) =>
          [registro.actor_sub, registro.accion, registro.recurso, registro.actor_email]
            .join(" ")
            .toLowerCase()
            .includes(termino),
        )
      : lista;
    return [...filtrados].reverse();
  }, [data, busqueda]);

  const rechazos = (data?.registros ?? []).filter((registro) => registro.resultado === "DENY").length;
  const verificacion = verificar.data;

  return (
    <>
      <header className="encabezado-pagina">
        <h1>Bitácora de auditoría</h1>
        <p className="encabezado-pagina__descripcion">
          Registro encadenado por funciones hash. Cada entrada conserva quién ejecutó la acción, cuál
          fue, sobre qué recurso y en qué momento. Modificar o eliminar un registro rompe la
          verificación de todos los posteriores.
        </p>
      </header>

      <div className="rejilla rejilla--3">
        <Metrica
          etiqueta="Registros"
          valor={isPending ? <Esqueleto alto="2rem" ancho="3rem" /> : (data?.total ?? 0)}
          nota="En la cadena de su organización"
          color="var(--acento)"
        />
        <Metrica
          etiqueta="Rechazos registrados"
          valor={isPending ? <Esqueleto alto="2rem" ancho="3rem" /> : rechazos}
          nota="Intentos denegados que dejaron rastro"
          color={rechazos ? "var(--peligro)" : undefined}
        />
        <Metrica
          etiqueta="Estado de la cadena"
          valor={verificacion ? (verificacion.cadena_valida ? "íntegra" : "rota") : "sin verificar"}
          nota={verificacion ? `verificada ${fechaLegible(verificacion.verificado_en)}` : "Pulse verificar"}
          color={verificacion ? (verificacion.cadena_valida ? "var(--exito)" : "var(--peligro)") : undefined}
        />
      </div>

      <Tarjeta
        titulo="Verificación de integridad"
        ayuda="El criterio tiene dos sentidos: sobre una bitácora íntegra debe informar cadena válida, y tras una alteración debe señalar dónde se rompió."
        acciones={
          <Boton onClick={() => verificar.mutate()} cargando={verificar.isPending}>
            Verificar cadena
          </Boton>
        }
      >
        {verificar.isError && <Aviso tono="error">{mensajeDeError(verificar.error)}</Aviso>}

        {verificacion ? (
          <div className="pila-sm">
            <Aviso
              tono={verificacion.cadena_valida ? "exito" : "error"}
              titulo={verificacion.cadena_valida ? "La cadena verifica" : "La cadena está rota"}
            >
              {verificacion.cadena_valida ? (
                <>
                  {verificacion.registros_verificados} registros recalculados, secuencias{" "}
                  {verificacion.primera_seq} a {verificacion.ultima_seq}.
                </>
              ) : (
                <>
                  {verificacion.rupturas.length} ruptura
                  {verificacion.rupturas.length === 1 ? "" : "s"}. La primera en la secuencia{" "}
                  {verificacion.punto_de_ruptura?.seq ?? verificacion.punto_de_ruptura?.seq_esperada}:{" "}
                  {verificacion.punto_de_ruptura?.descripcion}
                </>
              )}
            </Aviso>

            <VistaCadena verificacion={verificacion} />

            <p className="texto-xs texto-tenue mono">Hash final: {verificacion.hash_final}</p>
          </div>
        ) : (
          <p className="texto-sm texto-suave">
            La verificación no se ejecuta sola: es un procedimiento de auditoría y debe quedar
            constancia de quién lo ejecutó. Al pulsar, la consulta también se registra.
          </p>
        )}
      </Tarjeta>

      <Tarjeta>
        <div className="filtros">
          <div className="campo">
            <label className="campo__etiqueta" htmlFor="busqueda-bitacora">
              Buscar
            </label>
            <input
              id="busqueda-bitacora"
              className="campo__control"
              type="search"
              placeholder="Actor, acción o recurso"
              value={busqueda}
              onChange={(evento) => setBusqueda(evento.target.value)}
            />
          </div>
          <GrupoSegmentado
            etiqueta="Resultado"
            valor={filtro}
            opciones={[
              { valor: "todos", texto: "Todos" },
              { valor: "ALLOW", texto: "Permitidas" },
              { valor: "DENY", texto: "Rechazadas" },
            ]}
            onCambio={setFiltro}
          />
          <div className="campo">
            <span className="campo__etiqueta">&nbsp;</span>
            <Boton variante="secundario" onClick={() => refetch()} cargando={isFetching}>
              Actualizar
            </Boton>
          </div>
        </div>
      </Tarjeta>

      {error && <Aviso tono="error">{mensajeDeError(error)}</Aviso>}

      {isPending ? (
        <Esqueleto alto="20rem" />
      ) : registros.length === 0 ? (
        <Tarjeta>
          <Vacio titulo="Sin registros" descripcion="Ninguna entrada coincide con el filtro." />
        </Tarjeta>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <caption className="solo-lectores">
              Registros de la bitácora de la organización, del más reciente al más antiguo
            </caption>
            <thead>
              <tr>
                <th scope="col">Seq</th>
                <th scope="col">Fecha</th>
                <th scope="col">Actor</th>
                <th scope="col">Acción y recurso</th>
                <th scope="col">Resultado</th>
                <th scope="col">Hash</th>
                <th scope="col">
                  <span className="solo-lectores">Detalle</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {registros.map((registro) => (
                <tr key={registro.seq}>
                  <td className="tabla__numero">{registro.seq}</td>
                  <td>{fechaLegible(registro.ts)}</td>
                  <td className="envuelve">
                    {registro.actor_sub}
                    <br />
                    <span className="texto-xs texto-tenue">{registro.actor_grupos.join(", ")}</span>
                  </td>
                  <td className="envuelve">
                    {registro.accion}
                    <br />
                    <span className="texto-xs texto-tenue mono">{registro.recurso}</span>
                  </td>
                  <td>
                    <EtiquetaResultado resultado={registro.resultado} />
                  </td>
                  <td className="mono texto-xs">{registro.hash.slice(0, 12)}…</td>
                  <td>
                    <Boton variante="sutil" onClick={() => setDetalle(registro)}>
                      Ver
                    </Boton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {detalle && <DetalleRegistro registro={detalle} onCerrar={() => setDetalle(null)} />}
    </>
  );
}

/* ---------------------------------------------------------------------- */

/* Representación de la cadena: cada eslabón es un bloque, y los rotos se
 * destacan. Sirve para ver de un vistazo dónde se rompió, que en una tabla de
 * cientos de filas es difícil de localizar. */
function VistaCadena({ verificacion }: { verificacion: { rupturas: { seq?: number; seq_esperada?: number }[]; primera_seq: number | null; ultima_seq: number | null } }) {
  const primera = verificacion.primera_seq ?? 1;
  const ultima = verificacion.ultima_seq ?? 0;
  const total = Math.max(0, ultima - primera + 1);
  if (total === 0) return null;

  const rotos = new Set(
    verificacion.rupturas.map((ruptura) => ruptura.seq ?? ruptura.seq_esperada ?? -1),
  );
  // Con muchos registros se muestra una ventana alrededor de la primera ruptura.
  const limite = 160;
  const eslabones = Array.from({ length: Math.min(total, limite) }, (_, indice) => primera + indice);

  return (
    <div>
      <div className="cadena" aria-hidden="true">
        {eslabones.map((seq) => (
          <span
            key={seq}
            className={`cadena__eslabon ${rotos.has(seq) ? "cadena__eslabon--roto" : ""}`}
            title={`Secuencia ${seq}`}
          />
        ))}
      </div>
      <p className="texto-xs texto-tenue" style={{ marginTop: "var(--e-2)" }}>
        {total} eslabones{total > limite ? ` (se muestran los primeros ${limite})` : ""}.
        {rotos.size > 0 && " En rojo, los puntos donde la verificación falla."}
      </p>
    </div>
  );
}

function DetalleRegistro({ registro, onCerrar }: { registro: RegistroBitacora; onCerrar: () => void }) {
  return (
    <div className="modal" onMouseDown={(evento) => evento.target === evento.currentTarget && onCerrar()}>
      <div className="modal__panel" role="dialog" aria-modal="true" aria-label={`Registro ${registro.seq}`}>
        <div className="tarjeta__cabecera">
          <div className="min-cero">
            <h2 className="tarjeta__titulo">Registro {registro.seq}</h2>
            <p className="tarjeta__ayuda">{fechaLegible(registro.ts)}</p>
          </div>
          <Boton variante="sutil" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </Boton>
        </div>
        <div className="tarjeta__cuerpo pila-sm">
          <Fila termino="Actor" valor={`${registro.actor_sub} (${registro.actor_email || "sin correo"})`} />
          <Fila termino="Grupos" valor={registro.actor_grupos.join(", ") || "ninguno"} />
          <Fila termino="Acción" valor={registro.accion} />
          <Fila termino="Recurso" valor={registro.recurso} />
          <Fila termino="Resultado" valor={registro.resultado} />
          <Fila termino="Organización" valor={registro.org_id} />

          <div>
            <span className="campo__etiqueta">Detalle</span>
            <pre
              className="mono texto-xs"
              style={{
                margin: 0,
                padding: "var(--e-3)",
                background: "var(--superficie-hundida)",
                borderRadius: "var(--r-md)",
                overflowX: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {JSON.stringify(registro.detalle, null, 2)}
            </pre>
          </div>

          <Fila termino="Hash previo" valor={registro.hash_previo} mono />
          <Fila termino="Hash" valor={registro.hash} mono />

          <p className="texto-xs texto-tenue">
            El hash se calcula sobre el hash anterior concatenado con el contenido de este registro.
            Cambiar cualquier campo lo invalida, y reparar este eslabón rompe el siguiente.
          </p>
        </div>
      </div>
    </div>
  );
}

function Fila({ termino, valor, mono = false }: { termino: string; valor: string; mono?: boolean }) {
  return (
    <div>
      <span className="campo__etiqueta">{termino}</span>
      <p className={`texto-sm romper-todo ${mono ? "mono" : ""}`}>{valor}</p>
    </div>
  );
}
