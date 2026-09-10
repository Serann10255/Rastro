/* Interfaz del programa de auditoría.
 *
 * Tres pantallas, que son los tres momentos del trabajo: ver contra qué criterio
 * se va a juzgar (catálogo), ejecutar y leer el resultado (ejecución), y
 * comprobar que otro obtiene lo mismo (comparación).
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  almacenSesion,
  api,
  configuracionActual,
  ErrorApi,
  fechaLegible,
} from "@/api/cliente";
import type {
  Catalogo,
  Conclusion,
  Ejecucion,
  Hallazgo,
  PapelDeTrabajo,
  SesionAuditor,
} from "@/api/cliente";

type Pestana = "catalogo" | "ejecucion" | "comparacion";

export function App() {
  const [sesion, setSesion] = useState<SesionAuditor | null>(() => almacenSesion.leer());

  if (!sesion) return <Acceso onEntrar={setSesion} />;
  return <Consola sesion={sesion} onSalir={() => { almacenSesion.borrar(); setSesion(null); }} />;
}

/* ---------------------------------------------------------------------- */
/* Acceso                                                                 */
/* ---------------------------------------------------------------------- */

function Acceso({ onEntrar }: { onEntrar: (sesion: SesionAuditor) => void }) {
  const [correo, setCorreo] = useState("auditor@andes.test");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const salud = useQuery({ queryKey: ["salud"], queryFn: api.salud, retry: false });

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const sesion = await api.entrar(correo.trim(), clave);
      if (!sesion.usuario.grupos.includes("auditor")) {
        almacenSesion.borrar();
        setError(
          "Esa cuenta no pertenece al grupo auditor. El almacén de papeles de trabajo concentra información sobre las debilidades del sistema y su lectura está restringida.",
        );
        return;
      }
      onEntrar(sesion);
    } catch (fallo) {
      setError(fallo instanceof Error ? fallo.message : "No fue posible entrar.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="aplicacion">
      <header className="barra">
        <div className="barra__interior">
          <span className="marca">
            <span className="marca__punto" aria-hidden="true" />
            Cotejo
            <span className="marca__lema">programa de auditoría de sistemas</span>
          </span>
        </div>
      </header>

      <main className="contenido" style={{ maxWidth: "34rem" }}>
        <section className="tarjeta">
          <div className="tarjeta__cabecera">
            <div className="min-cero">
              <h1 className="tarjeta__titulo">Acceso del auditor</h1>
              <p className="tarjeta__ayuda">
                La identidad la resuelve el proveedor del sistema auditado: el auditor es un usuario
                de la organización con el grupo <strong>auditor</strong>.
              </p>
            </div>
          </div>
          <div className="tarjeta__cuerpo">
            <form onSubmit={enviar} className="pila-sm">
              <label className="campo">
                <span className="campo__etiqueta">Correo</span>
                <input
                  className="campo__control"
                  type="email"
                  autoComplete="username"
                  required
                  value={correo}
                  onChange={(evento) => setCorreo(evento.target.value)}
                />
              </label>
              <label className="campo">
                <span className="campo__etiqueta">Clave</span>
                <input
                  className="campo__control"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={clave}
                  onChange={(evento) => setClave(evento.target.value)}
                />
              </label>

              {error && (
                <div className="aviso aviso--error" role="alert">
                  <div className="aviso__cuerpo">{error}</div>
                </div>
              )}

              <div className="acciones">
                <button className="boton boton--bloque boton--grande" type="submit" disabled={enviando}>
                  {enviando ? "Entrando…" : "Entrar"}
                </button>
              </div>
            </form>
          </div>
          <footer className="tarjeta__pie texto-xs texto-tenue">
            {salud.data ? (
              <>
                Sistema auditado en <strong>{salud.data.url_auditada}</strong> · entorno{" "}
                <strong>{salud.data.entorno}</strong> · {salud.data.controles_en_catalogo} controles
                en el catálogo.
              </>
            ) : salud.isError ? (
              <>El programa de auditoría no responde. Compruebe que el servicio esté levantado.</>
            ) : (
              <>Consultando el estado del programa…</>
            )}
          </footer>
        </section>
      </main>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Consola                                                                */
/* ---------------------------------------------------------------------- */

function Consola({ sesion, onSalir }: { sesion: SesionAuditor; onSalir: () => void }) {
  const [pestana, setPestana] = useState<Pestana>("ejecucion");
  const [ejecucionId, setEjecucionId] = useState<string | null>(null);

  const cliente = useQueryClient();
  const catalogo = useQuery({ queryKey: ["catalogo"], queryFn: api.catalogo });
  const ejecuciones = useQuery({ queryKey: ["ejecuciones"], queryFn: api.ejecuciones });

  // Al abrir, se muestra la última ejecución almacenada: es lo que el auditor
  // quiere ver primero al volver, y evita una pantalla vacía sin razón.
  useEffect(() => {
    if (!ejecucionId && ejecuciones.data?.ejecuciones.length) {
      setEjecucionId(ejecuciones.data.ejecuciones[0]!.ejecucion_id);
    }
  }, [ejecuciones.data, ejecucionId]);

  const ejecutar = useMutation({
    mutationFn: () => api.ejecutar(),
    onSuccess: async (datos) => {
      setEjecucionId(datos.ejecucion_id);
      await cliente.invalidateQueries({ queryKey: ["ejecuciones"] });
      await cliente.invalidateQueries({ queryKey: ["ejecucion"] });
    },
  });

  return (
    <div className="aplicacion">
      <header className="barra">
        <div className="barra__interior">
          <span className="marca">
            <span className="marca__punto" aria-hidden="true" />
            Cotejo
            <span className="marca__lema">auditoría de Rastro</span>
          </span>
          <div className="crece" />
          <span className="insignia-org">{sesion.usuario.org_id}</span>
          <span className="texto-sm texto-suave">
            <strong style={{ color: "var(--texto)" }}>{sesion.usuario.nombre}</strong> · auditor
          </span>
          <button className="boton boton--secundario" onClick={onSalir}>
            Salir
          </button>
        </div>
      </header>

      <nav className="navegacion" aria-label="Secciones">
        <div className="navegacion__interior">
          {(
            [
              ["ejecucion", "Ejecución"],
              ["catalogo", "Catálogo"],
              ["comparacion", "Reproducibilidad"],
            ] as [Pestana, string][]
          ).map(([clave, texto]) => (
            <button
              key={clave}
              className="navegacion__enlace"
              aria-current={pestana === clave ? "page" : "false"}
              onClick={() => setPestana(clave)}
            >
              {texto}
            </button>
          ))}
        </div>
      </nav>

      <main className="contenido">
        <div className="aviso aviso--info">
          <div className="aviso__cuerpo">
            <strong className="aviso__titulo">Limitación de independencia</strong>
            El equipo audita un sistema que él mismo construyó. Se aplica rotación interna, el
            programa es determinista y un evaluador distinto puede reejecutarlo, pero este trabajo no
            alcanza el grado de independencia de una revisión externa.
          </div>
        </div>

        {pestana === "catalogo" && <VistaCatalogo catalogo={catalogo.data} cargando={catalogo.isPending} />}

        {pestana === "ejecucion" && (
          <VistaEjecucion
            ejecucionId={ejecucionId}
            ejecuciones={ejecuciones.data?.ejecuciones ?? []}
            onElegir={setEjecucionId}
            onEjecutar={() => ejecutar.mutate()}
            ejecutando={ejecutar.isPending}
            errorEjecucion={ejecutar.error}
          />
        )}

        {pestana === "comparacion" && (
          <VistaComparacion ejecuciones={ejecuciones.data?.ejecuciones ?? []} />
        )}
      </main>

      <footer className="pie">
        <span>Entorno {configuracionActual().entorno}</span>
        <span>Los papeles de trabajo no se versionan: su valor depende de que permanezcan sin editar.</span>
      </footer>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Catálogo                                                               */
/* ---------------------------------------------------------------------- */

function VistaCatalogo({ catalogo, cargando }: { catalogo?: Catalogo; cargando: boolean }) {
  if (cargando) return <div className="esqueleto" style={{ height: "20rem" }} />;
  if (!catalogo) return null;

  const porTipo = {
    cumplimiento: catalogo.controles.filter((c) => c.tipo === "cumplimiento"),
    sustantiva: catalogo.controles.filter((c) => c.tipo === "sustantiva"),
    integridad: catalogo.controles.filter((c) => c.tipo === "integridad"),
  };

  return (
    <>
      <header className="encabezado-pagina">
        <h1>Matriz de controles</h1>
        <p className="encabezado-pagina__descripcion">
          Versión {catalogo.version}. El catálogo se deriva de marcos de referencia reconocidos y no
          de la apreciación del equipo, de modo que un control ausente pueda atribuirse a una
          decisión de alcance y no a un olvido. El criterio se declara antes de ejecutar nada.
        </p>
      </header>

      {(
        [
          ["cumplimiento", "Pruebas de cumplimiento", "Consultan la configuración de la infraestructura en modo lectura."],
          ["sustantiva", "Pruebas sustantivas", "Ejercitan la aplicación con usuarios de prueba. Es la cobertura que ninguna herramienta disponible ofrece."],
          ["integridad", "Prueba de integridad", "Recalcula criptográficamente la bitácora del sistema auditado."],
        ] as const
      ).map(([tipo, titulo, ayuda]) => (
        <section className="tarjeta" key={tipo}>
          <div className="tarjeta__cabecera">
            <div className="min-cero">
              <h2 className="tarjeta__titulo">{titulo}</h2>
              <p className="tarjeta__ayuda">{ayuda}</p>
            </div>
            <span className="etiqueta">{porTipo[tipo].length}</span>
          </div>
          <div className="tarjeta__cuerpo pila-sm">
            {porTipo[tipo].map((control) => (
              <article key={control.id} className={`control severidad-${control.severidad_si_desviado}`}>
                <div className="control__cabecera">
                  <span className="control__id">{control.id}</span>
                  <span className={`etiqueta etiqueta--estado severidad-${control.severidad_si_desviado}`}>
                    severidad {control.severidad_si_desviado}
                  </span>
                </div>
                <p className="control__enunciado">{control.control}</p>
                <p className="control__resumen">
                  <strong>Criterio:</strong> {control.criterio}
                </p>
                <p className="control__resumen">
                  <strong>Procedimiento:</strong> {control.procedimiento}
                </p>
                <p className="control__marco">Marco: {control.marco}</p>
              </article>
            ))}
          </div>
        </section>
      ))}

      <section className="tarjeta">
        <div className="tarjeta__cabecera">
          <div className="min-cero">
            <h2 className="tarjeta__titulo">Hallazgos permanentes</h2>
            <p className="tarjeta__ayuda">
              No se automatizan porque el entorno impide corregir la desviación: una prueba que
              siempre da el mismo resultado no aporta información. Omitirlos del informe sí
              transmitiría una cobertura mayor que la real.
            </p>
          </div>
        </div>
        <div className="tarjeta__cuerpo pila-sm">
          {catalogo.hallazgos_permanentes.map((hallazgo) => (
            <article key={hallazgo.id} className={`hallazgo severidad-${hallazgo.severidad}`}>
              <div className="control__cabecera">
                <span className="control__id">{hallazgo.id}</span>
                <span className={`etiqueta etiqueta--estado severidad-${hallazgo.severidad}`}>
                  severidad {hallazgo.severidad}
                </span>
              </div>
              <Campo termino="Condición" valor={hallazgo.condicion} />
              <Campo termino="Criterio" valor={hallazgo.criterio} />
              <Campo termino="Causa" valor={hallazgo.causa} />
              <Campo termino="Efecto" valor={hallazgo.efecto} />
              <Campo termino="Recomendación" valor={hallazgo.recomendacion} />
              <Campo termino="Nota de alcance" valor={hallazgo.nota_de_alcance} />
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

function Campo({ termino, valor }: { termino: string; valor: string }) {
  return (
    <div className="hallazgo__campo">
      <span className="hallazgo__termino">{termino}</span>
      <span className="hallazgo__valor">{valor}</span>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Ejecución                                                              */
/* ---------------------------------------------------------------------- */

function VistaEjecucion({
  ejecucionId,
  ejecuciones,
  onElegir,
  onEjecutar,
  ejecutando,
  errorEjecucion,
}: {
  ejecucionId: string | null;
  ejecuciones: { ejecucion_id: string; cerrado_en: string; desviados: number; no_ejecutados: number }[];
  onElegir: (id: string) => void;
  onEjecutar: () => void;
  ejecutando: boolean;
  errorEjecucion: Error | null;
}) {
  const detalle = useQuery({
    queryKey: ["ejecucion", ejecucionId],
    queryFn: () => api.ejecucion(ejecucionId!),
    enabled: Boolean(ejecucionId),
  });

  const [controlAbierto, setControlAbierto] = useState<string | null>(null);
  const [verInforme, setVerInforme] = useState(false);

  const verificar = useMutation({ mutationFn: () => api.verificarAlmacen(ejecucionId!) });

  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <h1>Ejecución del programa</h1>
          <button className="boton" onClick={onEjecutar} disabled={ejecutando}>
            {ejecutando ? "Ejecutando el catálogo…" : "Ejecutar el catálogo completo"}
          </button>
        </div>
        <p className="encabezado-pagina__descripcion">
          El catálogo completo se recorre en una sola invocación y sin intervención manual. Cada
          prueba conserva el procedimiento, la salida literal, la marca de tiempo y la huella
          criptográfica de su archivo de evidencia.
        </p>
      </header>

      {errorEjecucion && (
        <div className="aviso aviso--error" role="alert">
          <div className="aviso__cuerpo">{errorEjecucion.message}</div>
        </div>
      )}

      {ejecuciones.length > 1 && (
        <label className="campo">
          <span className="campo__etiqueta">Ejecución</span>
          <select
            className="campo__control"
            value={ejecucionId ?? ""}
            onChange={(evento) => onElegir(evento.target.value)}
          >
            {ejecuciones.map((ejecucion) => (
              <option key={ejecucion.ejecucion_id} value={ejecucion.ejecucion_id}>
                {fechaLegible(ejecucion.cerrado_en)} — {ejecucion.desviados} desviados,{" "}
                {ejecucion.no_ejecutados} no ejecutados
              </option>
            ))}
          </select>
        </label>
      )}

      {!ejecucionId && !ejecutando && (
        <section className="tarjeta">
          <div className="tarjeta__cuerpo">
            <div className="vacio">
              <p className="vacio__titulo">Todavía no hay ejecuciones</p>
              <p className="vacio__descripcion">
                Ejecute el catálogo para producir los primeros papeles de trabajo.
              </p>
            </div>
          </div>
        </section>
      )}

      {(detalle.isPending && ejecucionId) || ejecutando ? (
        <div className="esqueleto" style={{ height: "16rem" }} />
      ) : detalle.data ? (
        <ResultadoEjecucion
          ejecucion={detalle.data}
          ejecucionId={ejecucionId!}
          onAbrirControl={setControlAbierto}
          onVerificar={() => verificar.mutate()}
          verificacion={verificar.data}
          verificando={verificar.isPending}
          onVerInforme={() => setVerInforme(true)}
        />
      ) : null}

      {controlAbierto && ejecucionId && (
        <ModalPapel
          ejecucionId={ejecucionId}
          controlId={controlAbierto}
          onCerrar={() => setControlAbierto(null)}
        />
      )}

      {verInforme && ejecucionId && (
        <ModalInforme ejecucionId={ejecucionId} onCerrar={() => setVerInforme(false)} />
      )}
    </>
  );
}

function ResultadoEjecucion({
  ejecucion,
  ejecucionId,
  onAbrirControl,
  onVerificar,
  verificacion,
  verificando,
  onVerInforme,
}: {
  ejecucion: Ejecucion;
  ejecucionId: string;
  onAbrirControl: (id: string) => void;
  onVerificar: () => void;
  verificacion?: { almacen_integro: boolean; papeles_verificados?: number; discrepancias: { control_id: string; tipo: string }[] };
  verificando: boolean;
  onVerInforme: () => void;
}) {
  const { cobertura, controles, hallazgos, metadatos } = ejecucion;
  const propios = hallazgos.filter((h) => !h.permanente);
  const permanentes = hallazgos.filter((h) => h.permanente);

  return (
    <>
      <div className="rejilla rejilla--2 rejilla--4">
        <Metrica etiqueta="Cobertura" valor={cobertura.cobertura} nota="Controles con resultado" color="var(--acento)" />
        <Metrica etiqueta="Conformes" valor={cobertura.conformes} nota="Cumplen el criterio" color="var(--exito)" />
        <Metrica
          etiqueta="Desviados"
          valor={cobertura.desviados}
          nota="Elevados a hallazgo"
          color={cobertura.desviados ? "var(--peligro)" : undefined}
        />
        <Metrica
          etiqueta="No ejecutados"
          valor={cobertura.no_ejecutados}
          nota="No comprobados en este entorno"
          color={cobertura.no_ejecutados ? "var(--alerta)" : undefined}
        />
      </div>

      {cobertura.no_ejecutados > 0 && (
        <div className="aviso aviso--alerta">
          <div className="aviso__cuerpo">
            <strong className="aviso__titulo">Un control no ejecutado no es un control conforme</strong>
            {cobertura.no_ejecutados} control(es) no pudieron comprobarse en este entorno. Su
            conclusión queda pendiente y el informe lo declara: presentar la ausencia de una
            capacidad como conformidad sería el peor resultado posible de un trabajo de
            aseguramiento.
          </div>
        </div>
      )}

      <section className="tarjeta">
        <div className="tarjeta__cabecera">
          <div className="min-cero">
            <h2 className="tarjeta__titulo">Resultado por control</h2>
            <p className="tarjeta__ayuda">
              Ejecutada bajo la identidad <strong>{String(metadatos.identidad_ejecucion ?? "")}</strong> en el
              entorno <strong>{String(metadatos.entorno ?? "")}</strong>. Pulse un control para ver su papel de
              trabajo con la salida literal.
            </p>
          </div>
          <div className="fila">
            <button className="boton boton--secundario" onClick={onVerInforme}>
              Ver informe
            </button>
            <button className="boton boton--secundario" onClick={onVerificar} disabled={verificando}>
              {verificando ? "Verificando…" : "Verificar almacén"}
            </button>
          </div>
        </div>
        <div className="tarjeta__cuerpo pila-sm">
          {verificacion && (
            <div className={`aviso aviso--${verificacion.almacen_integro ? "exito" : "error"}`}>
              <div className="aviso__cuerpo">
                <strong className="aviso__titulo">
                  {verificacion.almacen_integro ? "Almacén íntegro" : "Almacén no íntegro"}
                </strong>
                {verificacion.almacen_integro ? (
                  <>
                    {verificacion.papeles_verificados} papeles verificados: cada huella recalculada
                    coincide con la registrada en el índice.
                  </>
                ) : (
                  <>
                    {verificacion.discrepancias
                      .map((d) => `${d.control_id}: ${d.tipo}`)
                      .join(" · ")}
                  </>
                )}
              </div>
            </div>
          )}

          {controles.map((papel) => (
            <button
              key={papel.control_id}
              className={`control conclusion-${papel.conclusion}`}
              onClick={() => onAbrirControl(papel.control_id)}
            >
              <div className="control__cabecera">
                <span className="control__id">{papel.control_id}</span>
                <span className={`etiqueta etiqueta--estado conclusion-${papel.conclusion}`}>
                  {papel.conclusion.replace(/_/g, " ")}
                </span>
              </div>
              <span className="control__enunciado">{papel.control}</span>
              <span className="control__resumen">{papel.resumen}</span>
              <span className="control__marco huella">
                {papel.tipo} · huella {papel.huella_evidencia.slice(0, 16)}…
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="tarjeta">
        <div className="tarjeta__cabecera">
          <div className="min-cero">
            <h2 className="tarjeta__titulo">Hallazgos</h2>
            <p className="tarjeta__ayuda">
              Cada hallazgo enuncia condición, criterio, causa y efecto, y remite al papel de trabajo
              que lo sustenta. Sin esa referencia, un hallazgo es solo una afirmación.
            </p>
          </div>
          <span className="etiqueta">{hallazgos.length}</span>
        </div>
        <div className="tarjeta__cuerpo pila-sm">
          {propios.length === 0 && (
            <div className="aviso aviso--exito">
              <div className="aviso__cuerpo">
                No se identificaron desviaciones en los controles ejecutados.
              </div>
            </div>
          )}
          {[...propios, ...permanentes].map((hallazgo) => (
            <TarjetaHallazgo key={hallazgo.id} hallazgo={hallazgo} ejecucionId={ejecucionId} />
          ))}
        </div>
      </section>
    </>
  );
}

function TarjetaHallazgo({ hallazgo, ejecucionId }: { hallazgo: Hallazgo; ejecucionId: string }) {
  return (
    <article className={`hallazgo severidad-${hallazgo.severidad}`}>
      <div className="control__cabecera">
        <span className="control__id">
          {hallazgo.id}
          {hallazgo.permanente && <span className="texto-xs texto-tenue"> · permanente</span>}
        </span>
        <span className={`etiqueta etiqueta--estado severidad-${hallazgo.severidad}`}>
          severidad {hallazgo.severidad}
        </span>
      </div>
      <Campo termino="Control" valor={hallazgo.control_id} />
      <Campo termino="Condición" valor={hallazgo.condicion} />
      <Campo termino="Criterio" valor={hallazgo.criterio} />
      <Campo termino="Causa" valor={hallazgo.causa} />
      <Campo termino="Efecto" valor={hallazgo.efecto} />
      <Campo termino="Recomendación" valor={hallazgo.recomendacion} />
      <div className="hallazgo__campo">
        <span className="hallazgo__termino">Papel de trabajo</span>
        <span className="hallazgo__valor huella">
          {ejecucionId}/{hallazgo.papel_de_trabajo}
          {hallazgo.huella_evidencia && <> · huella {hallazgo.huella_evidencia.slice(0, 24)}…</>}
        </span>
      </div>
    </article>
  );
}

function Metrica({
  etiqueta,
  valor,
  nota,
  color,
}: {
  etiqueta: string;
  valor: React.ReactNode;
  nota: string;
  color?: string;
}) {
  return (
    <div className="metrica" style={color ? ({ "--metrica-color": color } as never) : undefined}>
      <span className="metrica__etiqueta">{etiqueta}</span>
      <span className="metrica__valor">{valor}</span>
      <span className="metrica__nota">{nota}</span>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Papel de trabajo                                                       */
/* ---------------------------------------------------------------------- */

function ModalPapel({
  ejecucionId,
  controlId,
  onCerrar,
}: {
  ejecucionId: string;
  controlId: string;
  onCerrar: () => void;
}) {
  const papel = useQuery({
    queryKey: ["papel", ejecucionId, controlId],
    queryFn: () => api.papel(ejecucionId, controlId),
  });

  useEffect(() => {
    const alPulsar = (evento: KeyboardEvent) => evento.key === "Escape" && onCerrar();
    document.addEventListener("keydown", alPulsar);
    return () => document.removeEventListener("keydown", alPulsar);
  }, [onCerrar]);

  const contenido = papel.data?.contenido as PapelDeTrabajo | undefined;

  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && onCerrar()}>
      <div
        className="modal__panel"
        role="dialog"
        aria-modal="true"
        aria-label={`Papel de trabajo ${controlId}`}
        style={{ maxWidth: "52rem" }}
      >
        <div className="tarjeta__cabecera">
          <div className="min-cero">
            <h2 className="tarjeta__titulo">Papel de trabajo {controlId}</h2>
            <p className="tarjeta__ayuda">{contenido?.control}</p>
          </div>
          <button className="boton boton--sutil" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </button>
        </div>

        <div className="tarjeta__cuerpo pila-sm">
          {papel.isPending && <div className="esqueleto" style={{ height: "12rem" }} />}

          {papel.data && (
            <>
              <div className={`aviso aviso--${papel.data.coincide ? "exito" : "error"}`}>
                <div className="aviso__cuerpo">
                  <strong className="aviso__titulo">
                    {papel.data.coincide
                      ? "La huella coincide con la registrada"
                      : "La huella NO coincide: el archivo fue modificado"}
                  </strong>
                  <span className="huella">recalculada {papel.data.huella_recalculada}</span>
                  <span className="huella">registrada {papel.data.huella_registrada ?? "—"}</span>
                </div>
              </div>

              {contenido && (
                <>
                  <Campo termino="Marco de referencia" valor={contenido.marco} />
                  <Campo termino="Tipo de prueba" valor={contenido.tipo} />
                  <Campo termino="Procedimiento" valor={contenido.procedimiento} />
                  <Campo termino="Criterio" valor={contenido.criterio} />
                  <Campo termino="Evidencia esperada" valor={contenido.evidencia_esperada} />
                  <Campo termino="Conclusión" valor={contenido.conclusion} />
                  <Campo termino="Resultado" valor={contenido.resumen} />
                  <Campo
                    termino="Ejecutada"
                    valor={`${fechaLegible(contenido.iniciado_en)} bajo ${contenido.identidad_ejecucion}`}
                  />

                  <div className="hallazgo__campo">
                    <span className="hallazgo__termino">
                      Observaciones ({contenido.observaciones.length}) — salida literal, sin editar
                    </span>
                    <div className="pila-sm">
                      {contenido.observaciones.map((observacion, indice) => (
                        <div key={indice}>
                          <p className="texto-xs texto-suave romper-todo">
                            <strong>{observacion.procedimiento}</strong>
                          </p>
                          {observacion.error && (
                            <p className="texto-xs" style={{ color: "var(--peligro)" }}>
                              {observacion.error}
                            </p>
                          )}
                          <pre className="evidencia">
                            {JSON.stringify(observacion.salida, null, 2)}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ModalInforme({ ejecucionId, onCerrar }: { ejecucionId: string; onCerrar: () => void }) {
  const informe = useQuery({
    queryKey: ["informe", ejecucionId],
    queryFn: () => api.informeTexto(ejecucionId),
  });

  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && onCerrar()}>
      <div
        className="modal__panel"
        role="dialog"
        aria-modal="true"
        aria-label="Informe de auditoría"
        style={{ maxWidth: "60rem" }}
      >
        <div className="tarjeta__cabecera">
          <h2 className="tarjeta__titulo">Informe de auditoría</h2>
          <button className="boton boton--sutil" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </button>
        </div>
        <div className="tarjeta__cuerpo">
          {informe.isPending ? (
            <div className="esqueleto" style={{ height: "20rem" }} />
          ) : (
            <pre className="informe">{informe.data?.texto}</pre>
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Reproducibilidad                                                       */
/* ---------------------------------------------------------------------- */

function VistaComparacion({
  ejecuciones,
}: {
  ejecuciones: { ejecucion_id: string; cerrado_en: string; identidad_ejecucion: string }[];
}) {
  const [a, setA] = useState("");
  const [b, setB] = useState("");

  useEffect(() => {
    if (!a && ejecuciones[1]) setA(ejecuciones[1].ejecucion_id);
    if (!b && ejecuciones[0]) setB(ejecuciones[0].ejecucion_id);
  }, [ejecuciones, a, b]);

  const comparar = useMutation({ mutationFn: () => api.comparar(a, b) });
  const resultado = comparar.data;

  const suficientes = ejecuciones.length >= 2;

  const identidades = useMemo(
    () => ({
      a: ejecuciones.find((e) => e.ejecucion_id === a)?.identidad_ejecucion,
      b: ejecuciones.find((e) => e.ejecucion_id === b)?.identidad_ejecucion,
    }),
    [ejecuciones, a, b],
  );

  return (
    <>
      <header className="encabezado-pagina">
        <h1>Reproducibilidad</h1>
        <p className="encabezado-pagina__descripcion">
          Un tercero debe poder reejecutar el programa y obtener la misma clasificación para cada
          control. Se comparan las conclusiones y no las huellas: cada ejecución tiene su propia
          marca de tiempo y, por lo tanto, su propia huella. Lo que debe reproducirse es el juicio,
          no el byte.
        </p>
      </header>

      {!suficientes ? (
        <section className="tarjeta">
          <div className="tarjeta__cuerpo">
            <div className="vacio">
              <p className="vacio__titulo">Hacen falta al menos dos ejecuciones</p>
              <p className="vacio__descripcion">
                Ejecute el catálogo una segunda vez, idealmente desde otra sesión, para comprobar que
                el resultado se reproduce.
              </p>
            </div>
          </div>
        </section>
      ) : (
        <section className="tarjeta">
          <div className="tarjeta__cuerpo pila-sm">
            <div className="rejilla rejilla--2">
              <SelectorEjecucion etiqueta="Ejecución A" valor={a} onCambio={setA} ejecuciones={ejecuciones} />
              <SelectorEjecucion etiqueta="Ejecución B" valor={b} onCambio={setB} ejecuciones={ejecuciones} />
            </div>

            {identidades.a && identidades.b && identidades.a === identidades.b && (
              <div className="aviso aviso--alerta">
                <div className="aviso__cuerpo">
                  Ambas ejecuciones se hicieron bajo la misma identidad. La comprobación de
                  reproducibilidad tiene más valor cuando la segunda la ejecuta un integrante
                  distinto del que desarrolló el ejecutor.
                </div>
              </div>
            )}

            <div className="acciones">
              <button className="boton" onClick={() => comparar.mutate()} disabled={!a || !b || a === b}>
                Comparar
              </button>
            </div>

            {comparar.isError && (
              <div className="aviso aviso--error">
                <div className="aviso__cuerpo">{(comparar.error as ErrorApi).message}</div>
              </div>
            )}

            {resultado && (
              <div className={`aviso aviso--${resultado.reproducible ? "exito" : "error"}`}>
                <div className="aviso__cuerpo">
                  <strong className="aviso__titulo">
                    {resultado.reproducible ? "Reproducible" : "No reproducible"}
                  </strong>
                  {resultado.coincidencias} de {resultado.controles_comparados} controles clasifican
                  igual.
                  {resultado.diferencias.length > 0 && (
                    <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
                      {resultado.diferencias.map((diferencia) => (
                        <li key={diferencia.control_id}>
                          {diferencia.control_id}: {diferencia.ejecucion_a} vs{" "}
                          {diferencia.ejecucion_b}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            )}
          </div>
        </section>
      )}
    </>
  );
}

function SelectorEjecucion({
  etiqueta,
  valor,
  onCambio,
  ejecuciones,
}: {
  etiqueta: string;
  valor: string;
  onCambio: (valor: string) => void;
  ejecuciones: { ejecucion_id: string; cerrado_en: string; identidad_ejecucion: string }[];
}) {
  return (
    <label className="campo">
      <span className="campo__etiqueta">{etiqueta}</span>
      <select className="campo__control" value={valor} onChange={(evento) => onCambio(evento.target.value)}>
        <option value="">Elija una ejecución</option>
        {ejecuciones.map((ejecucion) => (
          <option key={ejecucion.ejecucion_id} value={ejecucion.ejecucion_id}>
            {fechaLegible(ejecucion.cerrado_en)} · {ejecucion.identidad_ejecucion}
          </option>
        ))}
      </select>
    </label>
  );
}

export type { Conclusion };
