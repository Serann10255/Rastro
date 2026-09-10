/* Roles y permisos de la organización.
 *
 * Es la pantalla más delicada del sistema: aquí se decide quién puede hacer
 * qué. Tres cosas la hacen manejable sin volverla peligrosa.
 *
 * **El catálogo de operaciones lo pone el servidor**, agrupado y con una
 * descripción por operación. Marcar casillas llamadas `evento:reanudar` sin
 * saber qué significan es firmar sin leer.
 *
 * **Lo que esta pantalla impide no es el control.** El servidor rechaza igual
 * un permiso inventado, uno que quien edita no tiene, y cualquier rol que
 * mezcle auditar con operar. Aquí solo se avisa antes, para no hacer perder el
 * viaje.
 *
 * **El administrador no se edita.** Se muestra con sus permisos en gris: es el
 * seguro contra que una organización se quede sin nadie que pueda entrar a
 * deshacer un cambio.
 */

import { useMemo, useState } from "react";

import {
  useCatalogoDeOperaciones,
  useEliminarRol,
  useGuardarRol,
  useRoles,
} from "@/api/consultas";
import { useSesion } from "@/api/sesion";
import { mensajeDeError, useNotificaciones } from "@/componentes/notificaciones";
import { Aviso, Boton, Campo, Esqueleto, Modal, Tarjeta, Vacio } from "@/componentes/ui";
import { Icono } from "@design/marca/iconos";
import type { AreaDeOperaciones, Rol } from "@/tipos";

/** Operaciones que, combinadas con la lectura de la bitácora, rompen la
 *  separación de funciones. El servidor lo rechaza; esto lo anticipa. */
const ESCRITURA_Y_AUDITORIA = "auditoria";

export function Roles() {
  const { puede } = useSesion();
  const { data, isPending, error } = useRoles();
  const { data: catalogo } = useCatalogoDeOperaciones();

  const [editando, setEditando] = useState<Rol | null>(null);
  const [creando, setCreando] = useState(false);

  const puedeEditar = puede("rol:administrar");
  const areas = catalogo?.areas ?? [];

  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <div className="min-cero">
            <h1>Roles y permisos</h1>
            <p className="encabezado-pagina__descripcion">
              Qué puede hacer cada rol de su organización. Los de fábrica se pueden ajustar y no se
              pueden eliminar; puede crear los suyos para repartir el trabajo como lo reparte de
              verdad.
            </p>
          </div>
          {puedeEditar && <Boton onClick={() => setCreando(true)}>Crear rol</Boton>}
        </div>
      </header>

      <Aviso tono="info" titulo="Dos reglas que ninguna pantalla puede desactivar">
        Un rol solo puede contener operaciones que el sistema ya sabe hacer, y nadie puede conceder
        un permiso que no tiene. Además, ningún rol —ni ninguna cuenta— puede a la vez operar y leer
        la bitácora: quien revisa el registro no puede ser quien lo produce.
      </Aviso>

      {error ? <Aviso tono="error">{mensajeDeError(error)}</Aviso> : null}

      {isPending ? (
        <Esqueleto alto="18rem" />
      ) : (
        <div className="rejilla rejilla--2">
          {(data?.roles ?? []).map((rol) => (
            <TarjetaRol
              key={rol.clave}
              rol={rol}
              areas={areas}
              puedeEditar={puedeEditar}
              onEditar={() => setEditando(rol)}
            />
          ))}
        </div>
      )}

      <Modal
        titulo={editando ? `Permisos de ${editando.nombre}` : "Crear rol"}
        abierto={creando || editando !== null}
        onCerrar={() => {
          setCreando(false);
          setEditando(null);
        }}
      >
        <FormularioRol
          rol={editando}
          areas={areas}
          onListo={() => {
            setCreando(false);
            setEditando(null);
          }}
        />
      </Modal>
    </>
  );
}

/* ---------------------------------------------------------------------- */

function TarjetaRol({
  rol,
  areas,
  puedeEditar,
  onEditar,
}: {
  rol: Rol;
  areas: AreaDeOperaciones[];
  puedeEditar: boolean;
  onEditar: () => void;
}) {
  const { avisar } = useNotificaciones();
  const eliminar = useEliminarRol();
  const concedidas = new Set(rol.operaciones);

  const porArea = areas
    .map((area) => ({
      nombre: area.nombre,
      cuantas: area.operaciones.filter((o) => concedidas.has(o.operacion)).length,
      total: area.operaciones.length,
    }))
    .filter((area) => area.cuantas > 0);

  return (
    <Tarjeta
      titulo={rol.nombre}
      ayuda={rol.descripcion}
      pie={
        <div className="fila-entre">
          <span className="texto-xs texto-tenue">
            {rol.cuentas === 0
              ? "Sin cuentas asignadas"
              : `${rol.cuentas} cuenta${rol.cuentas === 1 ? "" : "s"}`}
          </span>
          <div className="fila">
            {puedeEditar && rol.editable && (
              <Boton variante="secundario" onClick={onEditar}>
                Editar permisos
              </Boton>
            )}
            {puedeEditar && !rol.integrado && (
              <Boton
                variante="peligro"
                cargando={eliminar.isPending}
                onClick={async () => {
                  try {
                    await eliminar.mutateAsync(rol.clave);
                    avisar(`Rol «${rol.nombre}» eliminado.`, "exito");
                  } catch (fallo) {
                    avisar(mensajeDeError(fallo), "error");
                  }
                }}
              >
                Eliminar
              </Boton>
            )}
          </div>
        </div>
      }
    >
      <div className="fila" style={{ flexWrap: "wrap", gap: "var(--e-2)" }}>
        <span className="etiqueta mono">{rol.clave}</span>
        {rol.integrado && <span className="etiqueta">de fábrica</span>}
        {!rol.editable && <span className="etiqueta etiqueta--DENY">no editable</span>}
      </div>

      <ul className="pila-sm" style={{ listStyle: "none", margin: "var(--e-3) 0 0", padding: 0 }}>
        {porArea.map((area) => (
          <li key={area.nombre} className="fila-entre texto-sm">
            <span className="texto-suave">{area.nombre}</span>
            <span className="mono texto-xs">
              {area.cuantas}/{area.total}
            </span>
          </li>
        ))}
      </ul>

      {!rol.editable && (
        <p className="texto-xs texto-tenue" style={{ marginTop: "var(--e-3)" }}>
          El administrador tiene todas las operaciones salvo la bitácora, y no se puede recortar:
          es lo que garantiza que la organización nunca se quede sin nadie que pueda entrar.
        </p>
      )}
    </Tarjeta>
  );
}

/* ---------------------------------------------------------------------- */

function FormularioRol({
  rol,
  areas,
  onListo,
}: {
  rol: Rol | null;
  areas: AreaDeOperaciones[];
  onListo: () => void;
}) {
  const { avisar } = useNotificaciones();
  const guardar = useGuardarRol();

  const [clave, setClave] = useState(rol?.clave ?? "");
  const [nombre, setNombre] = useState(rol?.nombre ?? "");
  const [descripcion, setDescripcion] = useState(rol?.descripcion ?? "");
  const [operaciones, setOperaciones] = useState<Set<string>>(
    () => new Set(rol?.operaciones ?? []),
  );

  const alternar = (operacion: string) => {
    setOperaciones((actuales) => {
      const siguiente = new Set(actuales);
      if (siguiente.has(operacion)) siguiente.delete(operacion);
      else siguiente.add(operacion);
      return siguiente;
    });
  };

  /* Se avisa antes de enviar por cortesía; el servidor lo rechaza igual. */
  const separacionRota = useMemo(() => {
    const auditoria = areas.find((a) => a.area === ESCRITURA_Y_AUDITORIA);
    const leeBitacora = (auditoria?.operaciones ?? []).some((o) => operaciones.has(o.operacion));
    const escribe = areas
      .flatMap((a) => a.operaciones)
      .some((o) => o.escritura && operaciones.has(o.operacion));
    return leeBitacora && escribe;
  }, [areas, operaciones]);

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    try {
      await guardar.mutateAsync({
        clave: rol?.clave ?? clave.trim().toLowerCase().replace(/\s+/g, "-"),
        nuevo: rol === null,
        nombre: nombre.trim(),
        descripcion: descripcion.trim(),
        operaciones: [...operaciones],
      });
      avisar(rol ? "Permisos actualizados." : "Rol creado.", "exito");
      onListo();
    } catch {
      /* Se muestra bajo el formulario. */
    }
  };

  return (
    <form onSubmit={enviar} className="pila">
      {rol === null && (
        <Campo
          etiqueta="Clave"
          required
          value={clave}
          onChange={(evento) => setClave(evento.target.value)}
          placeholder="supervisor-turno"
          ayuda="Es lo que guardan las cuentas y no se puede cambiar después. Minúsculas y guiones."
        />
      )}

      <Campo
        etiqueta="Nombre"
        required
        value={nombre}
        onChange={(evento) => setNombre(evento.target.value)}
        placeholder="Supervisor de turno"
      />

      <Campo
        etiqueta="Descripción"
        value={descripcion}
        onChange={(evento) => setDescripcion(evento.target.value)}
        ayuda="Para qué existe este rol. Lo lee quien asigna cuentas."
      />

      {separacionRota ? (
        <Aviso tono="alerta" titulo="Esto no se va a poder guardar">
          Un rol no puede leer la bitácora y además operar sobre el sistema: quien revisa el
          registro no puede ser quien lo produce. Separe las dos cosas en roles distintos.
        </Aviso>
      ) : null}

      <div className="pila-sm">
        {areas.map((area) => (
          <fieldset key={area.area} className="grupo-permisos">
            <legend className="campo__etiqueta">{area.nombre}</legend>
            {area.operaciones.map((operacion) => (
              <label key={operacion.operacion} className="casilla">
                <input
                  type="checkbox"
                  checked={operaciones.has(operacion.operacion)}
                  onChange={() => alternar(operacion.operacion)}
                />
                <span className="casilla__texto">
                  <span style={{ fontWeight: 600 }}>
                    {operacion.descripcion}
                    {operacion.escritura && (
                      <span className="etiqueta" style={{ marginLeft: "var(--e-2)" }}>
                        <Icono nombre="alerta" tamano={12} /> escribe
                      </span>
                    )}
                  </span>
                  <span className="campo__ayuda mono" style={{ display: "block" }}>
                    {operacion.operacion}
                  </span>
                </span>
              </label>
            ))}
          </fieldset>
        ))}
      </div>

      {operaciones.size === 0 && (
        <Vacio
          titulo="Sin permisos seleccionados"
          descripcion="Un rol sin operaciones no deja hacer nada: desactive las cuentas en su lugar."
        />
      )}

      {guardar.isError ? <Aviso tono="error">{mensajeDeError(guardar.error)}</Aviso> : null}

      <div className="acciones">
        <Boton
          type="submit"
          cargando={guardar.isPending}
          disabled={operaciones.size === 0 || !nombre.trim() || (rol === null && !clave.trim())}
        >
          {rol ? "Guardar permisos" : "Crear rol"}
        </Boton>
      </div>
    </form>
  );
}
