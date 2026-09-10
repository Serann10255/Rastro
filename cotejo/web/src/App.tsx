/* Interfaz del programa de auditoría.
 *
 * Cuatro pantallas, que son los cuatro momentos del trabajo: ver contra qué
 * criterio se va a juzgar (catálogo), ejecutar y leer el resultado (revisión),
 * comprobar que otro obtiene lo mismo (repetición) y entender las palabras
 * (diccionario).
 *
 * Regla de redacción de toda esta interfaz: primero la frase que se entiende
 * sin haber estudiado auditoría, y pegado a ella el término del oficio. Ni una
 * cosa ni la otra sobra. El término técnico es lo que un tercero espera leer en
 * un informe y lo que se evalúa en la asignatura; la frase llana es lo que
 * permite que alguien decida sobre un hallazgo sin necesitar un traductor. Una
 * pantalla que solo trae la segunda no sirve como entregable, y una que solo
 * trae la primera no se lee.
 *
 * Las dos versiones vienen del catálogo, no de aquí: si esta interfaz
 * escribiera su propia explicación de cada control, la web y el informe
 * acabarían diciendo cosas distintas del mismo control, y la del informe es la
 * que vale.
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
import { LogotipoCotejo } from "@design/marca/cotejo";
import { Icono } from "@design/marca/iconos";

type Pestana = "ejecucion" | "catalogo" | "comparacion" | "glosario";

/* Cada conclusión, en la palabra que se entiende sin diccionario. El servidor
 * manda la suya con cada papel y esa es la que manda; esto es el respaldo para
 * cuando todavía no hay papel —el catálogo, por ejemplo— y la fuente del color
 * y el icono, que no viajan por la API. */
const RESPUESTAS: Record<
  Conclusion,
  { palabra: string; explicacion: string; icono: string }
> = {
  CONFORME: {
    palabra: "BIEN",
    explicacion: "Se probó y cumplió la regla que estaba escrita de antemano.",
    icono: "verificado",
  },
  DESVIADO: {
    palabra: "MAL",
    explicacion: "Se probó y no cumplió. Esto se convierte en un hallazgo.",
    icono: "alerta",
  },
  NO_EJECUTADA: {
    palabra: "SIN REVISAR",
    explicacion:
      "Ni bien ni mal: no se pudo probar aquí. Queda pendiente, no aprobado.",
    icono: "reloj",
  },
};

export function App() {
  const [sesion, setSesion] = useState<SesionAuditor | null>(() => almacenSesion.leer());

  if (!sesion) return <Acceso onEntrar={setSesion} />;
  return <Consola sesion={sesion} onSalir={() => { almacenSesion.borrar(); setSesion(null); }} />;
}

/* ---------------------------------------------------------------------- */
/* Piezas compartidas                                                     */
/* ---------------------------------------------------------------------- */

/** El término del oficio, pegado a la frase que lo explica. */
function Tecnicismo({ children }: { children: React.ReactNode }) {
  return <span className="tecnicismo">{children}</span>;
}

/** La respuesta de un control: palabra llana grande, término técnico debajo. */
function Respuesta({
  conclusion,
  palabra,
  tamano = "normal",
}: {
  conclusion: Conclusion;
  palabra?: string;
  tamano?: "normal" | "grande";
}) {
  const base = RESPUESTAS[conclusion];
  return (
    <span
      className={`respuesta respuesta--${tamano} conclusion-${conclusion}`}
      title={base.explicacion}
    >
      <span className="respuesta__icono" aria-hidden="true">
        <Icono nombre={base.icono} tamano={tamano === "grande" ? 20 : 15} />
      </span>
      <span className="respuesta__palabra">{palabra ?? base.palabra}</span>
      <Tecnicismo>{conclusion.replace(/_/g, " ").toLowerCase()}</Tecnicismo>
    </span>
  );
}

function Campo({ termino, valor }: { termino: string; valor: React.ReactNode }) {
  return (
    <div className="hallazgo__campo">
      <span className="hallazgo__termino">{termino}</span>
      <span className="hallazgo__valor">{valor}</span>
    </div>
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

/** Bloque plegado con el registro técnico. Cerrado por omisión: quien lo
 *  necesita sabe que existe, y quien no, no tropieza con él. */
function DetalleTecnico({
  resumen = "Ver el registro técnico",
  children,
}: {
  resumen?: string;
  children: React.ReactNode;
}) {
  return (
    <details className="detalle-tecnico">
      <summary className="detalle-tecnico__titulo">{resumen}</summary>
      <div className="detalle-tecnico__cuerpo">{children}</div>
    </details>
  );
}

/* Banderas de interfaz. Se guardan por navegador y no en el servidor: son
 * preferencias de lectura de una persona, no estado del trabajo de auditoría. */
function leerBandera(clave: string): boolean {
  try {
    return localStorage.getItem(clave) === "1";
  } catch {
    return false;
  }
}

function escribirBandera(clave: string, valor: boolean) {
  try {
    if (valor) localStorage.setItem(clave, "1");
    else localStorage.removeItem(clave);
  } catch {
    /* Almacenamiento bloqueado: la ayuda simplemente vuelve a aparecer. */
  }
}

/* ---------------------------------------------------------------------- */
/* Acceso                                                                 */
/* ---------------------------------------------------------------------- */

function Acceso({ onEntrar }: { onEntrar: (sesion: SesionAuditor) => void }) {
  // Sin cuenta prefijada: aunque esta interfaz se sirve en la maquina del
  // auditor, escribir un correo valido en el formulario es publicar una cuenta
  // que existe. Las credenciales estan en la documentacion de despliegue.
  const [correo, setCorreo] = useState("");
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
          "Esa cuenta no puede entrar aquí: hace falta ser auditor. Lo que se guarda en este programa es la lista de puntos débiles del sistema, y por eso solo la ve quien tiene que revisarlos.",
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
    <div className="pantalla-acceso">
      <main className="acceso">
        <div className="acceso__marca">
          <span className="marca__simbolo marca__simbolo--grande" aria-hidden="true">
            <LogotipoCotejo tamano={30} id="marca-acceso" />
          </span>
          <div>
            <h1 className="acceso__titulo">Cotejo</h1>
            <p className="acceso__lema">Comprueba si Rastro cumple lo que promete</p>
          </div>
        </div>

        {salud.data?.que_es_esto && (
          <section className="tarjeta">
            <div className="tarjeta__cuerpo">
              <p className="parrafo-guia">{salud.data.que_es_esto}</p>
            </div>
          </section>
        )}

        <section className="tarjeta">
          <div className="tarjeta__cabecera">
            <div className="min-cero">
              <h2 className="tarjeta__titulo">Entrar</h2>
              <p className="tarjeta__ayuda">
                Se entra con la misma cuenta del sistema auditado, la que tenga el rol de{" "}
                <strong>auditor</strong>. Cotejo no tiene usuarios propios.
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
                  placeholder="usuario@empresa.test"
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
                Ahora mismo revisa el sistema que está en{" "}
                <strong>{salud.data.url_auditada}</strong> ({salud.data.entorno}), y tiene{" "}
                <strong>{salud.data.controles_en_catalogo}</strong> cosas por comprobar.
              </>
            ) : salud.isError ? (
              <>El programa no responde. Comprueba que el servicio esté encendido.</>
            ) : (
              <>Mirando si el programa está encendido…</>
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
    <div className="aplicacion aplicacion--con-lateral">
      <header className="armazon">
        <span className="marca armazon__marca">
          <span className="marca__simbolo" aria-hidden="true">
            <LogotipoCotejo tamano={22} id="marca-armazon" />
          </span>
          <span className="marca__texto">
            <span className="marca__nombre">Cotejo</span>
            <span className="marca__lema">Revisa a Rastro</span>
          </span>
        </span>

        <nav className="navegacion" aria-label="Secciones">
          <div className="navegacion__interior">
            {(
              [
                ["ejecucion", "Revisión", "verificado"],
                ["catalogo", "Qué se revisa", "auditoria"],
                ["comparacion", "Repetir", "cadena"],
                ["glosario", "Diccionario", "documento"],
              ] as [Pestana, string, string][]
            ).map(([clave, texto, icono]) => (
              <button
                key={clave}
                className="navegacion__enlace"
                aria-current={pestana === clave ? "page" : "false"}
                onClick={() => setPestana(clave)}
              >
                <span className="navegacion__icono">
                  <Icono nombre={icono} tamano={17} />
                </span>
                {texto}
              </button>
            ))}
          </div>
        </nav>

        <div className="armazon__identidad">
          <span className="insignia-org">{sesion.usuario.org_id}</span>
          <span className="identidad__persona">
            <span className="identidad__nombre">{sesion.usuario.nombre}</span>
            <span className="identidad__rol">auditor</span>
          </span>
        </div>

        <div className="armazon__acciones">
          <button className="boton boton--secundario" onClick={onSalir}>
            Salir
          </button>
        </div>
      </header>

      <div className="marco">
        <main className="contenido">
          <div className="aviso aviso--alerta">
            <div className="aviso__cuerpo">
              <strong className="aviso__titulo">Quien revisa aquí es quien construyó</strong>
              Es el mismo equipo, así que esto no es una revisión de fuera. Se compensa como
              se puede: el programa da el mismo resultado lo ejecute quien lo ejecute, y otra
              persona puede repetirlo y comparar. Aun así se dice en cada pantalla, porque
              callarlo sería lo grave.{" "}
              <Tecnicismo>en auditoría: amenaza de autorrevisión</Tecnicismo>
            </div>
          </div>

          {pestana === "ejecucion" && (
            <VistaEjecucion
              ejecucionId={ejecucionId}
              ejecuciones={ejecuciones.data?.ejecuciones ?? []}
              catalogo={catalogo.data}
              onElegir={setEjecucionId}
              onEjecutar={() => ejecutar.mutate()}
              ejecutando={ejecutar.isPending}
              errorEjecucion={ejecutar.error}
            />
          )}

          {pestana === "catalogo" && (
            <VistaCatalogo catalogo={catalogo.data} cargando={catalogo.isPending} />
          )}

          {pestana === "comparacion" && (
            <VistaComparacion ejecuciones={ejecuciones.data?.ejecuciones ?? []} />
          )}

          {pestana === "glosario" && (
            <VistaGlosario catalogo={catalogo.data} cargando={catalogo.isPending} />
          )}
        </main>

        <footer className="pie">
          <span>Entorno {configuracionActual().entorno}</span>
          <span>
            Las pruebas guardadas no se editan nunca: su valor depende justamente de eso.
          </span>
        </footer>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Cómo funciona                                                          */
/* ---------------------------------------------------------------------- */

const CLAVE_AYUDA = "cotejo.ayuda-oculta";

/** Los tres pasos del trabajo, para quien abre esto por primera vez.
 *
 *  Se puede ocultar, y se recuerda oculto. Una explicación que no se puede
 *  cerrar acaba siendo ruido para quien ya la leyó. */
function PanelComoFunciona({ queEsEsto }: { queEsEsto?: string }) {
  const [oculto, setOculto] = useState(() => leerBandera(CLAVE_AYUDA));

  if (oculto) {
    return (
      <div className="fila-entre">
        <span className="texto-xs texto-tenue">¿Primera vez por aquí?</span>
        <button
          className="boton boton--sutil"
          onClick={() => {
            setOculto(false);
            escribirBandera(CLAVE_AYUDA, false);
          }}
        >
          Explicar cómo funciona
        </button>
      </div>
    );
  }

  return (
    <section className="tarjeta">
      <div className="tarjeta__cabecera">
        <div className="min-cero">
          <h2 className="tarjeta__titulo">Cómo funciona esto</h2>
          {queEsEsto && <p className="tarjeta__ayuda">{queEsEsto}</p>}
        </div>
        <button
          className="boton boton--sutil"
          onClick={() => {
            setOculto(true);
            escribirBandera(CLAVE_AYUDA, true);
          }}
        >
          Ocultar
        </button>
      </div>
      <div className="tarjeta__cuerpo">
        <ol className="pasos">
          <li className="paso">
            <span className="paso__numero" aria-hidden="true">
              1
            </span>
            <div>
              <p className="paso__titulo">Primero se escribe qué se va a comprobar</p>
              <p className="paso__texto">
                Antes de tocar nada. Si la regla se escribiera después de ver el resultado,
                siempre se podría acomodar para que quede bonito.{" "}
                <Tecnicismo>en auditoría: criterio declarado</Tecnicismo>
              </p>
            </div>
          </li>
          <li className="paso">
            <span className="paso__numero" aria-hidden="true">
              2
            </span>
            <div>
              <p className="paso__titulo">Después se usa el sistema de verdad</p>
              <p className="paso__texto">
                Cotejo entra como un conductor, como una empresa que no debería mirar, e
                intenta hacer lo que no le toca, para ver qué contesta Rastro.{" "}
                <Tecnicismo>en auditoría: prueba sustantiva</Tecnicismo>
              </p>
            </div>
          </li>
          <li className="paso">
            <span className="paso__numero" aria-hidden="true">
              3
            </span>
            <div>
              <p className="paso__titulo">Y se guarda lo que pasó, con un sello</p>
              <p className="paso__texto">
                Se guarda la respuesta tal cual, sin resumir, y se le calcula un sello. Si
                alguien cambiara una letra de ese archivo, el sello dejaría de cuadrar y se
                notaría.{" "}
                <Tecnicismo>en auditoría: papel de trabajo y huella</Tecnicismo>
              </p>
            </div>
          </li>
        </ol>
      </div>
    </section>
  );
}

/* ---------------------------------------------------------------------- */
/* Revisión                                                               */
/* ---------------------------------------------------------------------- */

function VistaEjecucion({
  ejecucionId,
  ejecuciones,
  catalogo,
  onElegir,
  onEjecutar,
  ejecutando,
  errorEjecucion,
}: {
  ejecucionId: string | null;
  ejecuciones: { ejecucion_id: string; cerrado_en: string; conformes: number; desviados: number; no_ejecutados: number }[];
  catalogo?: Catalogo;
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
          <h1>Revisión</h1>
          <button className="boton boton--grande" onClick={onEjecutar} disabled={ejecutando}>
            {ejecutando ? "Revisando…" : "Revisar ahora"}
          </button>
        </div>
        <p className="encabezado-pagina__descripcion">
          Al pulsar el botón, Cotejo comprueba de una sola vez las{" "}
          {catalogo?.controles.length ?? 8} cosas de la lista, sin que nadie tenga que ir
          una por una. Tarda unos segundos.
        </p>
      </header>

      <PanelComoFunciona queEsEsto={catalogo?.que_es_esto} />

      {errorEjecucion && (
        <div className="aviso aviso--error" role="alert">
          <div className="aviso__cuerpo">
            <strong className="aviso__titulo">No se pudo revisar</strong>
            {errorEjecucion.message}
          </div>
        </div>
      )}

      {ejecuciones.length > 1 && (
        <label className="campo">
          <span className="campo__etiqueta">Revisión que se está viendo</span>
          <select
            className="campo__control"
            value={ejecucionId ?? ""}
            onChange={(evento) => onElegir(evento.target.value)}
          >
            {ejecuciones.map((ejecucion) => (
              <option key={ejecucion.ejecucion_id} value={ejecucion.ejecucion_id}>
                {fechaLegible(ejecucion.cerrado_en)} — {ejecucion.conformes} bien,{" "}
                {ejecucion.desviados} mal, {ejecucion.no_ejecutados} sin revisar
              </option>
            ))}
          </select>
        </label>
      )}

      {ejecutando && <EnCurso catalogo={catalogo} />}

      {!ejecucionId && !ejecutando && (
        <section className="tarjeta">
          <div className="tarjeta__cuerpo">
            <div className="vacio">
              <p className="vacio__titulo">Todavía no se ha revisado nada</p>
              <p className="vacio__descripcion">
                Pulsa «Revisar ahora» y en unos segundos aparece aquí qué salió bien y qué
                no.
              </p>
            </div>
          </div>
        </section>
      )}

      {!ejecutando && detalle.isPending && ejecucionId ? (
        <div className="esqueleto" style={{ height: "16rem" }} />
      ) : !ejecutando && detalle.data ? (
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

/** Qué está pasando mientras se ejecuta.
 *
 *  Se enseña la lista de lo que se va a comprobar, sin marcar ninguna como
 *  hecha: el programa responde de una vez y no informa de su avance, así que
 *  fingir un progreso sería inventar. */
function EnCurso({ catalogo }: { catalogo?: Catalogo }) {
  return (
    <section className="tarjeta">
      <div className="tarjeta__cabecera">
        <div className="min-cero">
          <h2 className="tarjeta__titulo">Revisando ahora mismo…</h2>
          <p className="tarjeta__ayuda">
            Cotejo está usando Rastro de verdad: entra, intenta cosas que no debería poder
            hacer y anota lo que le contesta. Suele tardar unos segundos.
          </p>
        </div>
      </div>
      <div className="tarjeta__cuerpo">
        <ul className="pasos-carga">
          {(catalogo?.controles ?? []).map((control) => (
            <li className="paso-carga" key={control.id} data-estado="activo">
              <span className="paso-carga__marca" aria-hidden="true">
                {control.id.replace("C-", "")}
              </span>
              {control.pregunta}
            </li>
          ))}
        </ul>
      </div>
    </section>
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
  const permanentes = hallazgos.filter((h) => !!h.permanente);

  const total = cobertura.controles_del_catalogo;
  const porcentaje = (parte: number) => (total ? (parte / total) * 100 : 0);

  return (
    <>
      <section className="veredicto">
        <p className="veredicto__frase">
          Revisamos <strong>{total}</strong> cosas que Rastro dice cumplir.{" "}
          <strong className="veredicto__bien">{cobertura.conformes} salieron bien</strong>,{" "}
          <strong className={cobertura.desviados ? "veredicto__mal" : undefined}>
            {cobertura.desviados} salieron mal
          </strong>{" "}
          y{" "}
          <strong className={cobertura.no_ejecutados ? "veredicto__pendiente" : undefined}>
            {cobertura.no_ejecutados} quedaron sin revisar
          </strong>
          .
        </p>

        <div
          className="barra-resultado"
          role="img"
          aria-label={`${cobertura.conformes} bien, ${cobertura.desviados} mal, ${cobertura.no_ejecutados} sin revisar, de ${total}`}
        >
          {cobertura.conformes > 0 && (
            <span
              className="barra-resultado__parte barra-resultado__parte--bien"
              style={{ width: `${porcentaje(cobertura.conformes)}%` }}
            />
          )}
          {cobertura.desviados > 0 && (
            <span
              className="barra-resultado__parte barra-resultado__parte--mal"
              style={{ width: `${porcentaje(cobertura.desviados)}%` }}
            />
          )}
          {cobertura.no_ejecutados > 0 && (
            <span
              className="barra-resultado__parte barra-resultado__parte--pendiente"
              style={{ width: `${porcentaje(cobertura.no_ejecutados)}%` }}
            />
          )}
        </div>

        <p className="veredicto__nota">
          Revisado el {fechaLegible(String(metadatos.iniciado_en ?? ""))} sobre el entorno{" "}
          <strong>{String(metadatos.entorno ?? "")}</strong>, por{" "}
          <strong>{String(metadatos.identidad_ejecucion ?? "")}</strong>.
        </p>

        <div className="fila">
          <button className="boton boton--secundario" onClick={onVerInforme}>
            Ver el informe completo
          </button>
          <button className="boton boton--secundario" onClick={onVerificar} disabled={verificando}>
            {verificando ? "Comprobando…" : "¿Alguien tocó estas pruebas?"}
          </button>
        </div>
      </section>

      {verificacion && (
        <div className={`aviso aviso--${verificacion.almacen_integro ? "exito" : "error"}`}>
          <div className="aviso__cuerpo">
            <strong className="aviso__titulo">
              {verificacion.almacen_integro
                ? "Nadie las ha tocado"
                : "Ojo: alguna prueba fue modificada después de guardarse"}
            </strong>
            {verificacion.almacen_integro ? (
              <>
                Se volvió a calcular el sello de {verificacion.papeles_verificados} pruebas
                guardadas y sale el mismo que se anotó el día que se ejecutaron.{" "}
                <Tecnicismo>en auditoría: almacén íntegro</Tecnicismo>
              </>
            ) : (
              <>
                El sello ya no cuadra en: {verificacion.discrepancias.map((d) => d.control_id).join(", ")}.
                El almacén no impide que se edite un archivo; lo que hace es que se note.
              </>
            )}
          </div>
        </div>
      )}

      {cobertura.no_ejecutados > 0 && (
        <div className="aviso aviso--alerta">
          <div className="aviso__cuerpo">
            <strong className="aviso__titulo">
              Lo que quedó sin revisar no está aprobado
            </strong>
            {cobertura.no_ejecutados} de las {total} no se pudieron comprobar aquí: son las
            que miran piezas de la nube que en este computador no existen. Quedan pendientes
            de ejecutarse contra la cuenta desplegada. Contarlas como buenas sería lo peor
            que podría hacer un programa de auditoría, así que tienen su propia casilla.
          </div>
        </div>
      )}

      <div className="rejilla rejilla--2 rejilla--4">
        <Metrica
          etiqueta="Bien"
          valor={cobertura.conformes}
          nota="Se probó y cumplió"
          color="var(--exito)"
        />
        <Metrica
          etiqueta="Mal"
          valor={cobertura.desviados}
          nota="Se probó y no cumplió"
          color={cobertura.desviados ? "var(--peligro)" : undefined}
        />
        <Metrica
          etiqueta="Sin revisar"
          valor={cobertura.no_ejecutados}
          nota="No se pudo probar aquí"
          color={cobertura.no_ejecutados ? "var(--alerta)" : undefined}
        />
        <Metrica
          etiqueta="Se llegó a probar"
          valor={cobertura.cobertura}
          nota="En auditoría: cobertura"
          color="var(--acento)"
        />
      </div>

      <section className="tarjeta">
        <div className="tarjeta__cabecera">
          <div className="min-cero">
            <h2 className="tarjeta__titulo">Una por una</h2>
            <p className="tarjeta__ayuda">
              Toca cualquiera para ver exactamente qué se hizo y qué contestó Rastro,
              palabra por palabra.
            </p>
          </div>
        </div>
        <div className="tarjeta__cuerpo pila-sm">
          {controles.map((papel) => (
            <button
              key={papel.control_id}
              className={`control conclusion-${papel.conclusion}`}
              onClick={() => onAbrirControl(papel.control_id)}
            >
              <div className="control__cabecera">
                <span className="control__id">{papel.control_id}</span>
                <Respuesta conclusion={papel.conclusion} palabra={papel.conclusion_llana} />
              </div>
              <span className="control__pregunta">{papel.pregunta || papel.control}</span>
              <span className="control__resumen">{papel.resumen}</span>
              <span className="control__pie">
                Ver qué se hizo y qué contestó
                <span className="control__marco huella">
                  sello {papel.huella_evidencia.slice(0, 12)}…
                </span>
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="tarjeta">
        <div className="tarjeta__cabecera">
          <div className="min-cero">
            <h2 className="tarjeta__titulo">Lo que hay que arreglar</h2>
            <p className="tarjeta__ayuda">
              Cada cosa se cuenta en cinco partes: qué pasa, con qué regla choca, por qué
              pasa, qué daño puede causar y qué habría que hacer. Y siempre dice de qué
              prueba salió: sin eso, sería solo una afirmación.{" "}
              <Tecnicismo>en auditoría: hallazgo</Tecnicismo>
            </p>
          </div>
          <span className="etiqueta">{hallazgos.length}</span>
        </div>
        <div className="tarjeta__cuerpo pila-sm">
          {propios.length === 0 && (
            <div className="aviso aviso--exito">
              <div className="aviso__cuerpo">
                De lo que se pudo probar, nada salió mal.
              </div>
            </div>
          )}
          {permanentes.length > 0 && (
            <p className="texto-sm texto-suave">
              Las {permanentes.length} de abajo marcadas como «se sabe y no se puede
              arreglar aquí» salen en todos los informes: el laboratorio de clase no permite
              corregirlas. Se dicen igual, porque callarlas haría creer que se revisó más de
              lo que se revisó.
            </p>
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
          {hallazgo.permanente && (
            <span className="texto-xs texto-tenue"> · se sabe y no se puede arreglar aquí</span>
          )}
        </span>
        <span className={`etiqueta etiqueta--estado severidad-${hallazgo.severidad}`}>
          {hallazgo.severidad === "alta"
            ? "grave"
            : hallazgo.severidad === "media"
              ? "importante"
              : "menor"}
          <Tecnicismo>severidad {hallazgo.severidad}</Tecnicismo>
        </span>
      </div>

      {hallazgo.en_simple && <p className="hallazgo__llano">{hallazgo.en_simple}</p>}

      <Campo termino="Qué habría que hacer" valor={hallazgo.recomendacion} />

      <DetalleTecnico>
        <Campo termino="Control" valor={hallazgo.control_id} />
        <Campo termino="Condición" valor={hallazgo.condicion} />
        <Campo termino="Criterio" valor={hallazgo.criterio} />
        <Campo termino="Causa" valor={hallazgo.causa} />
        <Campo termino="Efecto" valor={hallazgo.efecto} />
        <Campo
          termino="Papel de trabajo"
          valor={
            <span className="huella">
              {ejecucionId}/{hallazgo.papel_de_trabajo}
              {hallazgo.huella_evidencia && <> · huella {hallazgo.huella_evidencia.slice(0, 24)}…</>}
            </span>
          }
        />
      </DetalleTecnico>
    </article>
  );
}

/* ---------------------------------------------------------------------- */
/* Papel de trabajo                                                       */
/* ---------------------------------------------------------------------- */

/* Lo que significa cada código de respuesta, dicho como se lo contarías a
 * alguien. No se inventa nada: se describe el número que está en la evidencia. */
const CODIGOS: Record<number, string> = {
  200: "contestó que sí y entregó lo que se le pidió",
  201: "creó lo que se le pidió",
  204: "hizo lo que se le pidió y no tenía nada que devolver",
  400: "rechazó la petición porque no es válida",
  401: "pidió identificarse primero",
  403: "dijo que ese usuario no tiene permiso",
  404: "dijo que eso no existe",
  409: "dijo que choca con algo que ya existe",
  422: "dijo que los datos enviados no sirven",
  500: "se rompió por dentro",
};

function explicarSalida(salida: unknown): string | null {
  if (!salida || typeof salida !== "object") return null;
  const dato = salida as Record<string, unknown>;
  const partes: string[] = [];

  if (typeof dato.codigo === "number") {
    const texto = CODIGOS[dato.codigo];
    partes.push(
      texto
        ? `Rastro ${texto} (código ${dato.codigo}).`
        : `Rastro respondió con el código ${dato.codigo}.`,
    );
  }
  if (typeof dato.registros_totales === "number") {
    partes.push(`Se leyeron ${dato.registros_totales} anotaciones del cuaderno.`);
  }
  if (Array.isArray(dato.coincidencias)) {
    const cuantas = dato.coincidencias.length;
    partes.push(
      cuantas === 0
        ? "Ninguna anotación cuadra con lo que se buscaba."
        : `${cuantas} ${cuantas === 1 ? "anotación cuadra" : "anotaciones cuadran"} con lo que se buscaba.`,
    );
  }
  return partes.length ? partes.join(" ") : null;
}

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

  const contenido = papel.data?.contenido as unknown as PapelDeTrabajo | undefined;

  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && onCerrar()}>
      <div
        className="modal__panel"
        role="dialog"
        aria-modal="true"
        aria-label={`Prueba ${controlId}`}
        style={{ maxWidth: "52rem" }}
      >
        <div className="tarjeta__cabecera">
          <div className="min-cero">
            <h2 className="tarjeta__titulo">{contenido?.pregunta ?? `Prueba ${controlId}`}</h2>
            <p className="tarjeta__ayuda">
              {controlId} · esto es lo que quedó guardado de la prueba{" "}
              <Tecnicismo>en auditoría: papel de trabajo</Tecnicismo>
            </p>
          </div>
          <button className="boton boton--sutil" onClick={onCerrar} aria-label="Cerrar">
            ✕
          </button>
        </div>

        <div className="tarjeta__cuerpo pila-sm">
          {papel.isPending && <div className="esqueleto" style={{ height: "12rem" }} />}

          {papel.data && contenido && (
            <>
              <div className={`aviso aviso--${papel.data.coincide ? "exito" : "error"}`}>
                <div className="aviso__cuerpo">
                  <strong className="aviso__titulo">
                    {papel.data.coincide
                      ? "Este archivo no se ha tocado desde que se guardó"
                      : "Este archivo fue modificado después de guardarse"}
                  </strong>
                  {papel.data.coincide
                    ? "El sello que sale al recalcularlo ahora es el mismo que se anotó al ejecutar la prueba. Si alguien hubiera cambiado una sola letra, no cuadraría."
                    : "El sello que sale ahora no es el que se anotó. Alguien editó el archivo."}
                  <span className="huella">ahora: {papel.data.huella_recalculada}</span>
                  <span className="huella">se anotó: {papel.data.huella_registrada ?? "—"}</span>
                </div>
              </div>

              <div className="bloque-llano">
                <h3 className="bloque-llano__titulo">Qué se hizo</h3>
                <p>{contenido.en_simple || contenido.procedimiento}</p>
              </div>

              <div className="bloque-llano">
                <h3 className="bloque-llano__titulo">Qué contestó Rastro</h3>
                <p>{contenido.resumen}</p>
                <p className="bloque-llano__respuesta">
                  <Respuesta
                    conclusion={contenido.conclusion}
                    palabra={contenido.conclusion_llana}
                    tamano="grande"
                  />
                  <span className="texto-sm texto-suave">
                    {contenido.conclusion_explicada ?? RESPUESTAS[contenido.conclusion].explicacion}
                  </span>
                </p>
              </div>

              {contenido.si_falla && contenido.conclusion !== "CONFORME" && (
                <div className="bloque-llano">
                  <h3 className="bloque-llano__titulo">Por qué importa</h3>
                  <p>{contenido.si_falla}</p>
                </div>
              )}

              <div className="bloque-llano">
                <h3 className="bloque-llano__titulo">
                  Paso a paso, con lo que respondió tal cual
                </h3>
                <p className="texto-sm texto-suave">
                  Sin resumir ni retocar: es lo que permite que otra persona revise si la
                  conclusión es justa. <Tecnicismo>en auditoría: evidencia</Tecnicismo>
                </p>
                <div className="pila-sm">
                  {contenido.observaciones.map((observacion, indice) => {
                    const explicacion = explicarSalida(observacion.salida);
                    return (
                      <div key={indice} className="observacion">
                        <p className="observacion__paso">
                          <span className="observacion__numero" aria-hidden="true">
                            {indice + 1}
                          </span>
                          <span className="mono romper-todo">{observacion.procedimiento}</span>
                        </p>
                        {explicacion && <p className="observacion__llano">{explicacion}</p>}
                        {observacion.error && (
                          <p className="texto-sm" style={{ color: "var(--peligro)" }}>
                            No se pudo completar: {observacion.error}
                          </p>
                        )}
                        {observacion.salida !== null && observacion.salida !== undefined && (
                          <DetalleTecnico resumen="Ver la respuesta tal como llegó">
                            <pre className="evidencia">
                              {JSON.stringify(observacion.salida, null, 2)}
                            </pre>
                          </DetalleTecnico>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <DetalleTecnico resumen="Ver la ficha de auditoría de esta prueba">
                <Campo termino="Control" valor={contenido.control} />
                <Campo termino="Marco de referencia" valor={contenido.marco} />
                <Campo termino="Tipo de prueba" valor={contenido.tipo} />
                <Campo termino="Procedimiento" valor={contenido.procedimiento} />
                <Campo termino="Criterio" valor={contenido.criterio} />
                <Campo termino="Evidencia esperada" valor={contenido.evidencia_esperada} />
                <Campo termino="Conclusión" valor={contenido.conclusion} />
                <Campo
                  termino="Ejecutada"
                  valor={`${fechaLegible(contenido.iniciado_en)} bajo ${contenido.identidad_ejecucion}`}
                />
              </DetalleTecnico>
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

  useEffect(() => {
    const alPulsar = (evento: KeyboardEvent) => evento.key === "Escape" && onCerrar();
    document.addEventListener("keydown", alPulsar);
    return () => document.removeEventListener("keydown", alPulsar);
  }, [onCerrar]);

  return (
    <div className="modal" onMouseDown={(e) => e.target === e.currentTarget && onCerrar()}>
      <div
        className="modal__panel"
        role="dialog"
        aria-modal="true"
        aria-label="Informe"
        style={{ maxWidth: "60rem" }}
      >
        <div className="tarjeta__cabecera">
          <div className="min-cero">
            <h2 className="tarjeta__titulo">El informe completo</h2>
            <p className="tarjeta__ayuda">
              Empieza en palabras normales y sigue con el registro técnico. Es el mismo
              archivo que se guarda junto a las pruebas.
            </p>
          </div>
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
/* Qué se revisa                                                          */
/* ---------------------------------------------------------------------- */

function VistaCatalogo({ catalogo, cargando }: { catalogo?: Catalogo; cargando: boolean }) {
  if (cargando) return <div className="esqueleto" style={{ height: "20rem" }} />;
  if (!catalogo) return null;

  const grupos = [
    {
      tipo: "cumplimiento" as const,
      titulo: "Se mira cómo está puesto",
      ayuda:
        "Comprobar la configuración sin tocar nada. Como revisar que la puerta tenga cerradura.",
      tecnico: "pruebas de cumplimiento",
    },
    {
      tipo: "sustantiva" as const,
      titulo: "Se usa el sistema de verdad",
      ayuda:
        "Empujar la puerta para ver si de verdad está cerrada. Esto no lo hace ninguna herramienta automática de la nube: estas reglas viven en el código, no en la configuración.",
      tecnico: "pruebas sustantivas",
    },
    {
      tipo: "integridad" as const,
      titulo: "Se comprueba que el historial no se pueda retocar",
      ayuda: "Recalcular la cadena de sellos del cuaderno de Rastro.",
      tecnico: "prueba de integridad",
    },
  ];

  return (
    <>
      <header className="encabezado-pagina">
        <h1>Qué se revisa</h1>
        <p className="encabezado-pagina__descripcion">
          Esta lista se escribe <strong>antes</strong> de revisar nada, y las reglas salen de
          listas de buenas prácticas que ya existen y usa medio mundo, no de lo que a este
          equipo le parezca. Así, si algo no está en la lista, es porque se decidió dejarlo
          fuera y no porque se olvidara.{" "}
          <Tecnicismo>en auditoría: matriz de controles, versión {catalogo.version}</Tecnicismo>
        </p>
      </header>

      {grupos.map((grupo) => {
        const controles = catalogo.controles.filter((c) => c.tipo === grupo.tipo);
        if (!controles.length) return null;
        return (
          <section className="tarjeta" key={grupo.tipo}>
            <div className="tarjeta__cabecera">
              <div className="min-cero">
                <h2 className="tarjeta__titulo">{grupo.titulo}</h2>
                <p className="tarjeta__ayuda">
                  {grupo.ayuda} <Tecnicismo>en auditoría: {grupo.tecnico}</Tecnicismo>
                </p>
              </div>
              <span className="etiqueta">{controles.length}</span>
            </div>
            <div className="tarjeta__cuerpo pila-sm">
              {controles.map((control) => (
                <article
                  key={control.id}
                  className={`control control--estatico severidad-${control.severidad_si_desviado}`}
                >
                  <div className="control__cabecera">
                    <span className="control__id">{control.id}</span>
                    <span
                      className={`etiqueta etiqueta--estado severidad-${control.severidad_si_desviado}`}
                    >
                      {control.severidad_si_desviado === "alta" ? "grave" : "importante"}
                      <Tecnicismo>severidad {control.severidad_si_desviado}</Tecnicismo>
                    </span>
                  </div>
                  <p className="control__pregunta">{control.pregunta}</p>
                  <p className="control__resumen">{control.en_simple}</p>
                  <p className="control__riesgo">
                    <strong>Si fallara:</strong> {control.si_falla}
                  </p>

                  <DetalleTecnico>
                    <Campo termino="Control" valor={control.control} />
                    <Campo termino="Marco de referencia" valor={control.marco} />
                    <Campo termino="Criterio de aceptación" valor={control.criterio} />
                    <Campo termino="Procedimiento" valor={control.procedimiento} />
                    <Campo termino="Evidencia esperada" valor={control.evidencia_esperada} />
                  </DetalleTecnico>
                </article>
              ))}
            </div>
          </section>
        );
      })}

      <section className="tarjeta">
        <div className="tarjeta__cabecera">
          <div className="min-cero">
            <h2 className="tarjeta__titulo">Cosas que ya sabemos que están mal</h2>
            <p className="tarjeta__ayuda">
              Y que aquí no se pueden arreglar, porque el laboratorio de clase no lo permite.
              No se prueban —una prueba que siempre da el mismo resultado no aporta nada— pero
              se escriben en todos los informes: quitarlas haría creer que se revisó más de lo
              que se revisó. <Tecnicismo>en auditoría: hallazgos permanentes</Tecnicismo>
            </p>
          </div>
        </div>
        <div className="tarjeta__cuerpo pila-sm">
          {catalogo.hallazgos_permanentes.map((hallazgo) => (
            <article key={hallazgo.id} className={`hallazgo severidad-${hallazgo.severidad}`}>
              <div className="control__cabecera">
                <span className="control__id">{hallazgo.id}</span>
                <span className={`etiqueta etiqueta--estado severidad-${hallazgo.severidad}`}>
                  {hallazgo.severidad === "alta" ? "grave" : "importante"}
                  <Tecnicismo>severidad {hallazgo.severidad}</Tecnicismo>
                </span>
              </div>
              <p className="hallazgo__llano">{hallazgo.en_simple}</p>
              <Campo termino="Qué habría que hacer" valor={hallazgo.recomendacion} />
              <DetalleTecnico>
                <Campo termino="Condición" valor={hallazgo.condicion} />
                <Campo termino="Criterio" valor={hallazgo.criterio} />
                <Campo termino="Causa" valor={hallazgo.causa} />
                <Campo termino="Efecto" valor={hallazgo.efecto} />
                <Campo termino="Nota de alcance" valor={hallazgo.nota_de_alcance} />
              </DetalleTecnico>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

/* ---------------------------------------------------------------------- */
/* Diccionario                                                            */
/* ---------------------------------------------------------------------- */

function VistaGlosario({ catalogo, cargando }: { catalogo?: Catalogo; cargando: boolean }) {
  if (cargando) return <div className="esqueleto" style={{ height: "20rem" }} />;
  if (!catalogo) return null;

  return (
    <>
      <header className="encabezado-pagina">
        <h1>Diccionario</h1>
        <p className="encabezado-pagina__descripcion">
          Las palabras del oficio, explicadas. No se sustituyen por otras más fáciles: son
          las que espera leer quien reciba el informe. Pero nadie debería necesitar
          aprendérselas para entender lo que dice una pantalla.
        </p>
      </header>

      <section className="tarjeta">
        <div className="tarjeta__cuerpo">
          <dl className="glosario">
            {catalogo.glosario.map((entrada) => (
              <div className="glosario__entrada" key={entrada.termino}>
                <dt className="glosario__termino">
                  {entrada.termino}
                  {entrada.tambien_llamado && (
                    <span className="glosario__alias">también: {entrada.tambien_llamado}</span>
                  )}
                </dt>
                <dd className="glosario__definicion">{entrada.en_simple}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
    </>
  );
}

/* ---------------------------------------------------------------------- */
/* Repetir                                                                */
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
        <h1>¿Sale lo mismo si lo repite otra persona?</h1>
        <p className="encabezado-pagina__descripcion">
          Debería. Si el resultado dependiera de quién ejecuta el programa, no sería una
          medida: sería una opinión. Aquí se comparan dos revisiones y se mira si cada cosa
          dio la misma respuesta. No se comparan los sellos, porque cada revisión se hace a
          una hora distinta y por eso su sello es distinto; lo que tiene que repetirse es el
          juicio, no el archivo.{" "}
          <Tecnicismo>en auditoría: reproducibilidad</Tecnicismo>
        </p>
      </header>

      {!suficientes ? (
        <section className="tarjeta">
          <div className="tarjeta__cuerpo">
            <div className="vacio">
              <p className="vacio__titulo">Hacen falta dos revisiones para comparar</p>
              <p className="vacio__descripcion">
                Vuelve a «Revisión» y pulsa «Revisar ahora» una segunda vez. Vale mucho más
                si la segunda la ejecuta otra persona del equipo.
              </p>
            </div>
          </div>
        </section>
      ) : (
        <section className="tarjeta">
          <div className="tarjeta__cuerpo pila-sm">
            <div className="rejilla rejilla--2">
              <SelectorEjecucion etiqueta="Primera revisión" valor={a} onCambio={setA} ejecuciones={ejecuciones} />
              <SelectorEjecucion etiqueta="Segunda revisión" valor={b} onCambio={setB} ejecuciones={ejecuciones} />
            </div>

            {identidades.a && identidades.b && identidades.a === identidades.b && (
              <div className="aviso aviso--alerta">
                <div className="aviso__cuerpo">
                  Las dos las ejecutó la misma persona. Comparar sirve igual, pero prueba
                  mucho menos: lo que se quiere demostrar es que el resultado no depende de
                  quién lo ejecute.
                </div>
              </div>
            )}

            <div className="acciones">
              <button className="boton" onClick={() => comparar.mutate()} disabled={!a || !b || a === b}>
                Comparar las dos
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
                    {resultado.reproducible ? "Sale lo mismo las dos veces" : "No sale lo mismo"}
                  </strong>
                  {resultado.coincidencias} de {resultado.controles_comparados} cosas dieron
                  la misma respuesta.
                  {resultado.diferencias.length > 0 && (
                    <>
                      <span>
                        {" "}
                        Una diferencia no significa que el programa esté mal: puede que Rastro
                        haya cambiado entre una revisión y otra. Hay que abrir las dos pruebas
                        antes de concluir.
                      </span>
                      <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
                        {resultado.diferencias.map((diferencia) => (
                          <li key={diferencia.control_id}>
                            {diferencia.control_id}:{" "}
                            {RESPUESTAS[diferencia.ejecucion_a as Conclusion]?.palabra ??
                              diferencia.ejecucion_a}{" "}
                            la primera vez,{" "}
                            {RESPUESTAS[diferencia.ejecucion_b as Conclusion]?.palabra ??
                              diferencia.ejecucion_b}{" "}
                            la segunda
                          </li>
                        ))}
                      </ul>
                    </>
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
        <option value="">Elige una revisión</option>
        {ejecuciones.map((ejecucion) => (
          <option key={ejecucion.ejecucion_id} value={ejecucion.ejecucion_id}>
            {fechaLegible(ejecucion.cerrado_en)} · la ejecutó {ejecucion.identidad_ejecucion}
          </option>
        ))}
      </select>
    </label>
  );
}

export type { Conclusion };
