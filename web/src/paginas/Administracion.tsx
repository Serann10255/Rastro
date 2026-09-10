/* Administración de la empresa: cuentas, roles y datos de la organización.
 *
 * Crear usuarios es la operación más sensible del sistema: quien puede crear
 * cuentas puede concederse cualquier permiso. Por eso está restringida al
 * administrador y por eso cada alta, cambio de rol y desactivación queda en la
 * bitácora con quién lo hizo.
 */

import { useMemo, useState } from "react";

import {
  useActualizarUsuario,
  useCambiarClave,
  useCrearUsuario,
  useRoles,
  useUsuarios,
} from "@/api/consultas";
import { Link } from "react-router-dom";
import { useSesion } from "@/api/sesion";
import { mensajeDeError, useNotificaciones } from "@/componentes/notificaciones";
import {
  Aviso,
  Boton,
  Campo,
  Confirmacion,
  Esqueleto,
  Modal,
  TablaDatos,
  Tarjeta,
  Vacio,
  fechaLegible,
  fechaRelativa,
} from "@/componentes/ui";
import type { ColumnaTabla } from "@/componentes/ui";
import type { Rol } from "@/tipos";
import type { Grupo, UsuarioAdmin } from "@/tipos";

export function Administracion() {
  const { usuario, empresa, puede } = useSesion();
  const { avisar } = useNotificaciones();

  const esAdmin = puede("usuario:crear");
  const { data, isPending, error } = useUsuarios(puede("usuario:listar"));
  /* Los roles salen de la organización: incluyen los que ella haya creado. */
  const { data: roles } = useRoles(puede("rol:consultar"));

  const crear = useCrearUsuario();
  const actualizar = useActualizarUsuario();

  const [busqueda, setBusqueda] = useState("");
  const [creando, setCreando] = useState(false);
  const [editando, setEditando] = useState<UsuarioAdmin | null>(null);
  const [porDesactivar, setPorDesactivar] = useState<UsuarioAdmin | null>(null);
  const [cambiandoClave, setCambiandoClave] = useState(false);

  const usuarios = useMemo(() => {
    const termino = busqueda.trim().toLowerCase();
    return (data?.usuarios ?? []).filter((u) =>
      termino ? `${u.nombre} ${u.correo} ${u.grupos.join(" ")}`.toLowerCase().includes(termino) : true,
    );
  }, [data, busqueda]);

  const columnas: ColumnaTabla<UsuarioAdmin>[] = [
    {
      clave: "nombre",
      titulo: "Usuario",
      envuelve: true,
      render: (u) => (
        <>
          <strong>{u.nombre}</strong>
          {u.correo === usuario?.correo && <span className="etiqueta" style={{ marginLeft: ".5rem" }}>usted</span>}
          <br />
          <span className="texto-xs texto-tenue">{u.correo}</span>
        </>
      ),
    },
    {
      clave: "grupos",
      titulo: "Roles",
      envuelve: true,
      render: (u) => (
        <div className="fila">
          {u.grupos.map((grupo) => (
            <span key={grupo} className="etiqueta">
              {grupo}
            </span>
          ))}
        </div>
      ),
    },
    { clave: "telefono", titulo: "Teléfono", render: (u) => u.telefono || "—" },
    {
      clave: "ultimo_acceso",
      titulo: "Último acceso",
      render: (u) =>
        u.ultimo_acceso ? (
          <span title={fechaLegible(u.ultimo_acceso)}>{fechaRelativa(u.ultimo_acceso)}</span>
        ) : (
          <span className="texto-tenue">nunca entró</span>
        ),
    },
    {
      clave: "activo",
      titulo: "Estado",
      render: (u) => (
        <span className={`etiqueta ${u.activo ? "etiqueta--ALLOW" : "etiqueta--DENY"}`}>
          {u.activo ? "activo" : "inactivo"}
        </span>
      ),
    },
  ];

  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <div className="min-cero">
            <h1>Administración</h1>
            <p className="encabezado-pagina__descripcion">
              Cuentas y roles de {empresa?.nombre ?? "su empresa"}. Cada alta, cambio de rol y
              desactivación queda registrada en la bitácora con quién la hizo.
            </p>
          </div>
          {esAdmin && <Boton onClick={() => setCreando(true)}>Crear usuario</Boton>}
        </div>
      </header>

      <div className="doble-panel">
        <div className="pila">
          <Tarjeta>
            <div className="filtros">
              <Campo
                etiqueta="Buscar"
                type="search"
                placeholder="Nombre, correo o rol"
                value={busqueda}
                onChange={(evento) => setBusqueda(evento.target.value)}
              />
              <div className="campo">
                <span className="campo__etiqueta">Cuentas</span>
                <p
                  className="texto-sm texto-suave"
                  style={{ minHeight: "var(--tactil)", display: "flex", alignItems: "center" }}
                >
                  {data?.total ?? 0}
                </p>
              </div>
            </div>
          </Tarjeta>

          {error ? <Aviso tono="error">{mensajeDeError(error)}</Aviso> : null}

          {isPending ? (
            <Esqueleto alto="16rem" />
          ) : (
            <TablaDatos
              columnas={columnas}
              registros={usuarios}
              claveDe={(u) => u.correo}
              acciones={
                esAdmin
                  ? (u) => (
                      <div className="fila">
                        <Boton variante="sutil" onClick={() => setEditando(u)}>
                          Editar
                        </Boton>
                        {u.activo && u.correo !== usuario?.correo && (
                          <Boton variante="sutil" onClick={() => setPorDesactivar(u)}>
                            Desactivar
                          </Boton>
                        )}
                        {!u.activo && (
                          <Boton
                            variante="sutil"
                            onClick={async () => {
                              await actualizar.mutateAsync({
                                correo: u.correo,
                                cambios: { activo: true },
                              });
                              avisar("Cuenta reactivada.", "exito");
                            }}
                          >
                            Reactivar
                          </Boton>
                        )}
                      </div>
                    )
                  : undefined
              }
              vacio={<Vacio titulo="Sin cuentas" />}
            />
          )}
        </div>

        <div className="pila">
          <Tarjeta titulo="Datos de la empresa">
            <dl className="pila-sm" style={{ margin: 0 }}>
              <Dato termino="Razón social" valor={empresa?.nombre ?? "—"} />
              <Dato termino="Identificador" valor={empresa?.org_id ?? "—"} />
              <Dato termino="NIT" valor={empresa?.nit || "—"} />
              <Dato termino="Dirección" valor={empresa?.direccion || "—"} />
              <Dato
                termino="Ciudad"
                valor={empresa?.ciudad ? `${empresa.ciudad}, ${empresa.departamento ?? ""}` : "—"}
              />
              <Dato termino="Teléfono" valor={empresa?.telefono || "—"} />
              <Dato termino="Contacto" valor={empresa?.correo_contacto || "—"} />
            </dl>
            <p className="texto-xs texto-tenue" style={{ marginTop: "var(--e-3)" }}>
              Los datos de la empresa se aprovisionan con el despliegue. El registro autónomo de
              organizaciones está fuera del alcance del proyecto.
            </p>
          </Tarjeta>

          <Tarjeta titulo="Su cuenta" ayuda={usuario?.correo}>
            <dl className="pila-sm" style={{ margin: 0 }}>
              <Dato termino="Nombre" valor={usuario?.nombre ?? "—"} />
              <Dato termino="Roles" valor={usuario?.grupos.join(", ") ?? "—"} />
            </dl>
            <div className="acciones">
              <Boton variante="secundario" onClick={() => setCambiandoClave(true)}>
                Cambiar contraseña
              </Boton>
            </div>
          </Tarjeta>

          <Tarjeta
            titulo="Qué puede hacer cada rol"
            ayuda="Los roles son de su organización: puede ajustarlos y crear otros."
            pie={
              <Link to="/administracion/roles" className="boton boton--secundario">
                Configurar roles
              </Link>
            }
          >
            <ul className="pila-sm" style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {(roles?.roles ?? []).map((rol) => (
                <li key={rol.clave}>
                  <span className="etiqueta">{rol.nombre}</span>
                  <p className="texto-xs texto-suave" style={{ marginTop: "0.25rem" }}>
                    {rol.descripcion}
                  </p>
                </li>
              ))}
            </ul>
          </Tarjeta>
        </div>
      </div>

      <Modal titulo="Crear usuario" abierto={creando} onCerrar={() => setCreando(false)}>
        <FormularioUsuario
          roles={roles?.roles ?? []}
          cargando={crear.isPending}
          error={crear.isError ? mensajeDeError(crear.error) : null}
          onGuardar={async (datos) => {
            try {
              await crear.mutateAsync(datos);
              avisar(`Cuenta creada para ${datos.correo}.`, "exito");
              setCreando(false);
            } catch {
              /* Se muestra dentro del formulario. */
            }
          }}
          onCancelar={() => setCreando(false)}
        />
      </Modal>

      <Modal titulo="Editar usuario" abierto={editando !== null} onCerrar={() => setEditando(null)}>
        {editando && (
          <FormularioEdicion
            roles={roles?.roles ?? []}
            usuario={editando}
            cargando={actualizar.isPending}
            error={actualizar.isError ? mensajeDeError(actualizar.error) : null}
            onGuardar={async (cambios) => {
              try {
                await actualizar.mutateAsync({ correo: editando.correo, cambios });
                avisar("Cuenta actualizada.", "exito");
                setEditando(null);
              } catch {
                /* Se muestra dentro del formulario. */
              }
            }}
            onCancelar={() => setEditando(null)}
          />
        )}
      </Modal>

      <Modal
        titulo="Cambiar contraseña"
        abierto={cambiandoClave}
        onCerrar={() => setCambiandoClave(false)}
      >
        <FormularioClave onCerrar={() => setCambiandoClave(false)} />
      </Modal>

      <Confirmacion
        abierto={porDesactivar !== null}
        titulo="Desactivar cuenta"
        descripcion={
          <>
            <strong>{porDesactivar?.nombre}</strong> no podrá entrar y sus sesiones abiertas se
            cerrarán de inmediato. La cuenta y su historial se conservan: desactivar no borra lo que
            esa persona hizo.
          </>
        }
        textoConfirmar="Desactivar"
        cargando={actualizar.isPending}
        onConfirmar={async () => {
          if (!porDesactivar) return;
          try {
            await actualizar.mutateAsync({
              correo: porDesactivar.correo,
              cambios: { activo: false },
            });
            avisar("Cuenta desactivada y sesiones cerradas.", "exito");
          } catch (fallo) {
            avisar(mensajeDeError(fallo), "error");
          }
          setPorDesactivar(null);
        }}
        onCancelar={() => setPorDesactivar(null)}
      />
    </>
  );
}

function Dato({ termino, valor }: { termino: string; valor: string }) {
  return (
    <div>
      <dt
        className="texto-xs texto-tenue"
        style={{ textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 700 }}
      >
        {termino}
      </dt>
      <dd style={{ margin: 0 }} className="texto-sm romper-todo">
        {valor}
      </dd>
    </div>
  );
}

/* ---------------------------------------------------------------------- */

function SelectorDeRoles({
  seleccionados,
  onCambio,
  disponibles,
}: {
  seleccionados: Grupo[];
  onCambio: (grupos: Grupo[]) => void;
  disponibles: Rol[];
}) {
  const alternar = (grupo: Grupo) => {
    onCambio(
      seleccionados.includes(grupo)
        ? seleccionados.filter((g) => g !== grupo)
        : [...seleccionados, grupo],
    );
  };

  return (
    <div className="campo">
      <span className="campo__etiqueta">Roles</span>
      <div className="pila-sm">
        {disponibles.map((rol) => (
          <label key={rol.clave} className="casilla">
            <input
              type="checkbox"
              checked={seleccionados.includes(rol.clave)}
              onChange={() => alternar(rol.clave)}
            />
            <span className="casilla__texto">
              <span style={{ fontWeight: 600 }}>{rol.nombre}</span>
              <span className="campo__ayuda" style={{ display: "block" }}>
                {rol.descripcion}
              </span>
            </span>
          </label>
        ))}
      </div>
      <span className="campo__ayuda">
        Una cuenta puede tener varios roles. El servidor concede el permiso si alguno de ellos lo
        autoriza.
      </span>
    </div>
  );
}

function FormularioUsuario({
  cargando,
  error,
  roles,
  onGuardar,
  onCancelar,
}: {
  cargando: boolean;
  error: string | null;
  roles: Rol[];
  onGuardar: (datos: {
    correo: string;
    nombre: string;
    clave: string;
    grupos: Grupo[];
    telefono?: string;
  }) => void;
  onCancelar: () => void;
}) {
  const [correo, setCorreo] = useState("");
  const [nombre, setNombre] = useState("");
  const [clave, setClave] = useState("");
  const [telefono, setTelefono] = useState("");
  const [grupos, setGrupos] = useState<Grupo[]>(["conductor"]);

  const claveCorta = clave.length > 0 && clave.length < 12;

  return (
    <>
      <div className="tarjeta__cabecera">
        <div className="min-cero">
          <h2 className="tarjeta__titulo">Crear usuario</h2>
          <p className="tarjeta__ayuda">
            La persona entrará con este correo y esta contraseña, y podrá cambiarla después.
          </p>
        </div>
      </div>
      <form
        className="tarjeta__cuerpo pila-sm"
        onSubmit={(evento) => {
          evento.preventDefault();
          onGuardar({ correo, nombre, clave, grupos, telefono });
        }}
      >
        <Campo
          etiqueta="Nombre completo"
          required
          minLength={2}
          value={nombre}
          onChange={(evento) => setNombre(evento.target.value)}
        />
        <Campo
          etiqueta="Correo"
          type="email"
          required
          autoComplete="off"
          value={correo}
          onChange={(evento) => setCorreo(evento.target.value)}
          ayuda="Será su nombre de usuario. No distingue mayúsculas."
        />
        <Campo
          etiqueta="Contraseña inicial"
          type="password"
          required
          minLength={12}
          autoComplete="new-password"
          value={clave}
          onChange={(evento) => setClave(evento.target.value)}
          error={claveCorta ? "Al menos 12 caracteres." : undefined}
          ayuda="Mínimo 12 caracteres. Se almacena derivada, nunca en claro."
        />
        <Campo
          etiqueta="Teléfono"
          opcional
          type="tel"
          value={telefono}
          onChange={(evento) => setTelefono(evento.target.value)}
        />

        <SelectorDeRoles seleccionados={grupos} onCambio={setGrupos} disponibles={roles} />

        {error && <Aviso tono="error">{error}</Aviso>}

        <div className="acciones">
          <Boton type="submit" cargando={cargando} disabled={grupos.length === 0 || claveCorta}>
            Crear cuenta
          </Boton>
          <Boton type="button" variante="secundario" onClick={onCancelar}>
            Cancelar
          </Boton>
        </div>
      </form>
    </>
  );
}

function FormularioEdicion({
  usuario,
  cargando,
  error,
  roles,
  onGuardar,
  onCancelar,
}: {
  usuario: UsuarioAdmin;
  cargando: boolean;
  error: string | null;
  roles: Rol[];
  onGuardar: (cambios: { nombre?: string; grupos?: Grupo[]; telefono?: string }) => void;
  onCancelar: () => void;
}) {
  const [nombre, setNombre] = useState(usuario.nombre);
  const [telefono, setTelefono] = useState(usuario.telefono ?? "");
  const [grupos, setGrupos] = useState<Grupo[]>(usuario.grupos);

  return (
    <>
      <div className="tarjeta__cabecera">
        <div className="min-cero">
          <h2 className="tarjeta__titulo">Editar usuario</h2>
          <p className="tarjeta__ayuda">{usuario.correo}</p>
        </div>
      </div>
      <form
        className="tarjeta__cuerpo pila-sm"
        onSubmit={(evento) => {
          evento.preventDefault();
          onGuardar({ nombre, grupos, telefono });
        }}
      >
        <Campo
          etiqueta="Nombre completo"
          required
          minLength={2}
          value={nombre}
          onChange={(evento) => setNombre(evento.target.value)}
        />
        <Campo
          etiqueta="Teléfono"
          opcional
          type="tel"
          value={telefono}
          onChange={(evento) => setTelefono(evento.target.value)}
        />

        <SelectorDeRoles seleccionados={grupos} onCambio={setGrupos} disponibles={roles} />

        <Aviso tono="info">
          El correo no se puede cambiar: es la clave con la que se identifica la cuenta y con la que
          están atribuidos sus registros en la bitácora.
        </Aviso>

        {error && <Aviso tono="error">{error}</Aviso>}

        <div className="acciones">
          <Boton type="submit" cargando={cargando} disabled={grupos.length === 0}>
            Guardar
          </Boton>
          <Boton type="button" variante="secundario" onClick={onCancelar}>
            Cancelar
          </Boton>
        </div>
      </form>
    </>
  );
}

function FormularioClave({ onCerrar }: { onCerrar: () => void }) {
  const { avisar } = useNotificaciones();
  const cambiar = useCambiarClave();

  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");

  const noCoinciden = repetida.length > 0 && nueva !== repetida;
  const corta = nueva.length > 0 && nueva.length < 12;

  return (
    <>
      <div className="tarjeta__cabecera">
        <div className="min-cero">
          <h2 className="tarjeta__titulo">Cambiar contraseña</h2>
          <p className="tarjeta__ayuda">
            Al cambiarla se cerrarán sus demás sesiones. Si la cambia porque sospecha que alguien la
            conoce, dejar esas sesiones abiertas no serviría de nada.
          </p>
        </div>
      </div>
      <form
        className="tarjeta__cuerpo pila-sm"
        onSubmit={async (evento) => {
          evento.preventDefault();
          try {
            await cambiar.mutateAsync({ actual, nueva });
            avisar("Contraseña cambiada. Las demás sesiones se cerraron.", "exito");
            onCerrar();
          } catch {
            /* Se muestra dentro del formulario. */
          }
        }}
      >
        <Campo
          etiqueta="Contraseña actual"
          type="password"
          required
          autoComplete="current-password"
          value={actual}
          onChange={(evento) => setActual(evento.target.value)}
        />
        <Campo
          etiqueta="Contraseña nueva"
          type="password"
          required
          minLength={12}
          autoComplete="new-password"
          value={nueva}
          onChange={(evento) => setNueva(evento.target.value)}
          error={corta ? "Al menos 12 caracteres." : undefined}
        />
        <Campo
          etiqueta="Repita la nueva"
          type="password"
          required
          autoComplete="new-password"
          value={repetida}
          onChange={(evento) => setRepetida(evento.target.value)}
          error={noCoinciden ? "Las contraseñas no coinciden." : undefined}
        />

        {cambiar.isError && <Aviso tono="error">{mensajeDeError(cambiar.error)}</Aviso>}

        <div className="acciones">
          <Boton type="submit" cargando={cambiar.isPending} disabled={noCoinciden || corta}>
            Cambiar
          </Boton>
          <Boton type="button" variante="secundario" onClick={onCerrar}>
            Cancelar
          </Boton>
        </div>
      </form>
    </>
  );
}
