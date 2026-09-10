/* Datos maestros: tiendas, clientes y transportistas.
 *
 * Las tres pantallas comparten estructura porque comparten necesidad: listar,
 * buscar, crear, editar y dar de baja. Escribirlas tres veces produciría tres
 * comportamientos ligeramente distintos, que es lo que hace que un sistema se
 * sienta improvisado.
 *
 * Lectura y escritura tienen permisos distintos: el despachador consulta las
 * tiendas para registrar un envío, pero cambiar la dirección de una tienda
 * afecta a toda la operación y corresponde al administrador.
 */

import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import {
  useClientes,
  useEliminarCliente,
  useEliminarTienda,
  useEliminarTransportista,
  useGuardarCliente,
  useGuardarTienda,
  useGuardarTransportista,
  useTiendas,
  useTransportistas,
} from "@/api/consultas";
import { useSesion } from "@/api/sesion";
import { mensajeDeError, useNotificaciones } from "@/componentes/notificaciones";
import {
  Aviso,
  Boton,
  Campo,
  CampoSelect,
  Confirmacion,
  Esqueleto,
  Modal,
  TablaDatos,
  Tarjeta,
  Vacio,
} from "@/componentes/ui";
import type { ColumnaTabla } from "@/componentes/ui";
import type { Cliente, Tienda, Transportista } from "@/tipos";

type Recurso = "tiendas" | "clientes" | "transportistas";

export function Maestros() {
  const { recurso } = useParams<{ recurso: Recurso }>();

  if (recurso === "clientes") return <PantallaClientes />;
  if (recurso === "transportistas") return <PantallaTransportistas />;
  return <PantallaTiendas />;
}

/* ---------------------------------------------------------------------- */
/* Estructura común                                                       */
/* ---------------------------------------------------------------------- */

function Encabezado({
  titulo,
  descripcion,
  total,
  busqueda,
  onBuscar,
  onCrear,
  puedeEditar,
  textoCrear,
}: {
  titulo: string;
  descripcion: string;
  total: number;
  busqueda: string;
  onBuscar: (valor: string) => void;
  onCrear: () => void;
  puedeEditar: boolean;
  textoCrear: string;
}) {
  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <div className="min-cero">
            <h1>{titulo}</h1>
            <p className="encabezado-pagina__descripcion">{descripcion}</p>
          </div>
          {puedeEditar && <Boton onClick={onCrear}>{textoCrear}</Boton>}
        </div>
      </header>

      <Tarjeta>
        <div className="filtros">
          <Campo
            etiqueta="Buscar"
            type="search"
            placeholder="Nombre, ciudad o código"
            value={busqueda}
            onChange={(evento) => onBuscar(evento.target.value)}
          />
          <div className="campo">
            <span className="campo__etiqueta">Registros</span>
            <p className="texto-sm texto-suave" style={{ minHeight: "var(--tactil)", display: "flex", alignItems: "center" }}>
              {total}
            </p>
          </div>
        </div>
      </Tarjeta>
    </>
  );
}

function coincide(registro: Record<string, unknown>, termino: string): boolean {
  if (!termino.trim()) return true;
  return Object.values(registro)
    .filter((valor) => typeof valor === "string")
    .join(" ")
    .toLowerCase()
    .includes(termino.trim().toLowerCase());
}

function EstadoActivo({ activo }: { activo: boolean }) {
  return (
    <span className={`etiqueta ${activo ? "etiqueta--ALLOW" : "etiqueta--DENY"}`}>
      {activo ? "activo" : "inactivo"}
    </span>
  );
}

/* ---------------------------------------------------------------------- */
/* Tiendas                                                                */
/* ---------------------------------------------------------------------- */

const TIENDA_VACIA: Partial<Tienda> = {
  nombre: "",
  codigo: "",
  tipo: "tienda",
  direccion: "",
  ciudad: "",
  departamento: "",
  telefono: "",
  responsable: "",
  activa: true,
};

function PantallaTiendas() {
  const { puede } = useSesion();
  const { avisar } = useNotificaciones();
  const { data, isPending, error } = useTiendas();
  const guardar = useGuardarTienda();
  const eliminar = useEliminarTienda();

  const [busqueda, setBusqueda] = useState("");
  const [editando, setEditando] = useState<Partial<Tienda> | null>(null);
  const [porEliminar, setPorEliminar] = useState<Tienda | null>(null);

  const puedeEditar = puede("maestro:editar");
  const registros = useMemo(
    () => (data?.tiendas ?? []).filter((t) => coincide(t as never, busqueda)),
    [data, busqueda],
  );

  const columnas: ColumnaTabla<Tienda>[] = [
    { clave: "nombre", titulo: "Nombre", envuelve: true, render: (t) => <strong>{t.nombre}</strong> },
    { clave: "codigo", titulo: "Código", render: (t) => <span className="mono">{t.codigo}</span> },
    { clave: "tipo", titulo: "Tipo", render: (t) => <span style={{ textTransform: "capitalize" }}>{t.tipo}</span> },
    {
      clave: "ubicacion",
      titulo: "Ubicación",
      envuelve: true,
      render: (t) => (
        <>
          {t.ciudad}
          <br />
          <span className="texto-xs texto-tenue">{t.departamento}</span>
        </>
      ),
    },
    { clave: "direccion", titulo: "Dirección", envuelve: true, render: (t) => t.direccion || "—" },
    { clave: "responsable", titulo: "Responsable", envuelve: true, render: (t) => t.responsable || "—" },
    { clave: "activa", titulo: "Estado", render: (t) => <EstadoActivo activo={t.activa} /> },
  ];

  const enviar = async (datos: Partial<Tienda>) => {
    try {
      await guardar.mutateAsync({ id: datos.tienda_id, datos });
      avisar(datos.tienda_id ? "Tienda actualizada." : "Tienda creada.", "exito");
      setEditando(null);
    } catch {
      /* Se muestra dentro del formulario. */
    }
  };

  return (
    <>
      <Encabezado
        titulo="Tiendas"
        descripcion="Tiendas, almacenes y estaciones desde donde sale y por donde pasa la carga."
        total={data?.total ?? 0}
        busqueda={busqueda}
        onBuscar={setBusqueda}
        onCrear={() => setEditando({ ...TIENDA_VACIA })}
        puedeEditar={puedeEditar}
        textoCrear="Agregar tienda"
      />

      {error && <Aviso tono="error">{mensajeDeError(error)}</Aviso>}

      {isPending ? (
        <Esqueleto alto="16rem" />
      ) : (
        <TablaDatos
          columnas={columnas}
          registros={registros}
          claveDe={(t) => t.tienda_id}
          acciones={
            puedeEditar
              ? (t) => (
                  <div className="fila">
                    <Boton variante="sutil" onClick={() => setEditando(t)}>
                      Editar
                    </Boton>
                    <Boton variante="sutil" onClick={() => setPorEliminar(t)}>
                      Eliminar
                    </Boton>
                  </div>
                )
              : undefined
          }
          vacio={
            <Vacio
              titulo={busqueda ? "Ninguna tienda coincide" : "Sin tiendas"}
              descripcion={
                busqueda
                  ? "Pruebe con otro término."
                  : "Agregue la primera para poder asociarla a los envíos."
              }
            />
          }
        />
      )}

      <Modal
        titulo={editando?.tienda_id ? "Editar tienda" : "Nueva tienda"}
        abierto={editando !== null}
        onCerrar={() => setEditando(null)}
      >
        {editando && (
          <FormularioTienda
            inicial={editando}
            cargando={guardar.isPending}
            error={guardar.isError ? mensajeDeError(guardar.error) : null}
            onGuardar={enviar}
            onCancelar={() => setEditando(null)}
          />
        )}
      </Modal>

      <Confirmacion
        abierto={porEliminar !== null}
        titulo="Eliminar tienda"
        descripcion={
          <>
            Se eliminará <strong>{porEliminar?.nombre}</strong>. Los envíos ya registrados conservan
            el nombre de la tienda tal como estaba: no pierden su origen.
          </>
        }
        cargando={eliminar.isPending}
        onConfirmar={async () => {
          if (!porEliminar) return;
          await eliminar.mutateAsync(porEliminar.tienda_id);
          avisar("Tienda eliminada.", "exito");
          setPorEliminar(null);
        }}
        onCancelar={() => setPorEliminar(null)}
      />
    </>
  );
}

function FormularioTienda({
  inicial,
  cargando,
  error,
  onGuardar,
  onCancelar,
}: {
  inicial: Partial<Tienda>;
  cargando: boolean;
  error: string | null;
  onGuardar: (datos: Partial<Tienda>) => void;
  onCancelar: () => void;
}) {
  const [datos, setDatos] = useState(inicial);
  const cambiar = (campo: keyof Tienda) => (evento: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setDatos((previo) => ({ ...previo, [campo]: evento.target.value }));

  return (
    <>
      <div className="tarjeta__cabecera">
        <h2 className="tarjeta__titulo">{inicial.tienda_id ? "Editar tienda" : "Nueva tienda"}</h2>
      </div>
      <form
        className="tarjeta__cuerpo pila-sm"
        onSubmit={(evento) => {
          evento.preventDefault();
          onGuardar(datos);
        }}
      >
        <Campo etiqueta="Nombre" required minLength={2} value={datos.nombre ?? ""} onChange={cambiar("nombre")} />
        <div className="rejilla rejilla--2">
          <Campo
            etiqueta="Código"
            value={datos.codigo ?? ""}
            onChange={cambiar("codigo")}
            ayuda="Se guarda en mayúsculas. Si se deja vacío, se usa el nombre."
          />
          <CampoSelect etiqueta="Tipo" value={datos.tipo ?? "tienda"} onChange={cambiar("tipo")}>
            <option value="tienda">Tienda</option>
            <option value="almacen">Almacén</option>
            <option value="estacion">Estación</option>
          </CampoSelect>
        </div>
        <Campo etiqueta="Dirección" value={datos.direccion ?? ""} onChange={cambiar("direccion")} />
        <div className="rejilla rejilla--2">
          <Campo etiqueta="Ciudad" required minLength={2} value={datos.ciudad ?? ""} onChange={cambiar("ciudad")} />
          <Campo
            etiqueta="Departamento"
            required
            minLength={2}
            value={datos.departamento ?? ""}
            onChange={cambiar("departamento")}
          />
        </div>
        <div className="rejilla rejilla--2">
          <Campo etiqueta="Teléfono" opcional value={datos.telefono ?? ""} onChange={cambiar("telefono")} />
          <Campo etiqueta="Responsable" opcional value={datos.responsable ?? ""} onChange={cambiar("responsable")} />
        </div>

        {error && <Aviso tono="error">{error}</Aviso>}

        <div className="acciones">
          <Boton type="submit" cargando={cargando}>
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

/* ---------------------------------------------------------------------- */
/* Clientes                                                               */
/* ---------------------------------------------------------------------- */

const CLIENTE_VACIO: Partial<Cliente> = {
  nombre: "",
  correo: "",
  telefono: "",
  documento: "",
  direccion: "",
  ciudad: "",
  departamento: "",
  activo: true,
};

function PantallaClientes() {
  const { puede } = useSesion();
  const { avisar } = useNotificaciones();
  const { data, isPending, error } = useClientes();
  const guardar = useGuardarCliente();
  const eliminar = useEliminarCliente();

  const [busqueda, setBusqueda] = useState("");
  const [editando, setEditando] = useState<Partial<Cliente> | null>(null);
  const [porEliminar, setPorEliminar] = useState<Cliente | null>(null);

  const puedeEditar = puede("maestro:editar");
  const registros = useMemo(
    () => (data?.clientes ?? []).filter((c) => coincide(c as never, busqueda)),
    [data, busqueda],
  );

  const columnas: ColumnaTabla<Cliente>[] = [
    { clave: "nombre", titulo: "Nombre", envuelve: true, render: (c) => <strong>{c.nombre}</strong> },
    { clave: "documento", titulo: "Documento", render: (c) => c.documento || "—" },
    { clave: "correo", titulo: "Correo", envuelve: true, render: (c) => c.correo || "—" },
    { clave: "telefono", titulo: "Teléfono", render: (c) => c.telefono || "—" },
    {
      clave: "ubicacion",
      titulo: "Ubicación",
      envuelve: true,
      render: (c) => (c.ciudad ? `${c.ciudad}${c.departamento ? `, ${c.departamento}` : ""}` : "—"),
    },
    { clave: "activo", titulo: "Estado", render: (c) => <EstadoActivo activo={c.activo} /> },
  ];

  return (
    <>
      <Encabezado
        titulo="Clientes"
        descripcion="Empresas y personas que despachan envíos a través de su operación."
        total={data?.total ?? 0}
        busqueda={busqueda}
        onBuscar={setBusqueda}
        onCrear={() => setEditando({ ...CLIENTE_VACIO })}
        puedeEditar={puedeEditar}
        textoCrear="Agregar cliente"
      />

      {error && <Aviso tono="error">{mensajeDeError(error)}</Aviso>}

      {isPending ? (
        <Esqueleto alto="16rem" />
      ) : (
        <TablaDatos
          columnas={columnas}
          registros={registros}
          claveDe={(c) => c.cliente_id}
          acciones={
            puedeEditar
              ? (c) => (
                  <div className="fila">
                    <Boton variante="sutil" onClick={() => setEditando(c)}>
                      Editar
                    </Boton>
                    <Boton variante="sutil" onClick={() => setPorEliminar(c)}>
                      Eliminar
                    </Boton>
                  </div>
                )
              : undefined
          }
          vacio={<Vacio titulo={busqueda ? "Ningún cliente coincide" : "Sin clientes"} />}
        />
      )}

      <Modal
        titulo={editando?.cliente_id ? "Editar cliente" : "Nuevo cliente"}
        abierto={editando !== null}
        onCerrar={() => setEditando(null)}
      >
        {editando && (
          <FormularioCliente
            inicial={editando}
            cargando={guardar.isPending}
            error={guardar.isError ? mensajeDeError(guardar.error) : null}
            onGuardar={async (datos) => {
              try {
                await guardar.mutateAsync({ id: datos.cliente_id, datos });
                avisar(datos.cliente_id ? "Cliente actualizado." : "Cliente creado.", "exito");
                setEditando(null);
              } catch {
                /* Se muestra dentro del formulario. */
              }
            }}
            onCancelar={() => setEditando(null)}
          />
        )}
      </Modal>

      <Confirmacion
        abierto={porEliminar !== null}
        titulo="Eliminar cliente"
        descripcion={
          <>
            Se eliminará <strong>{porEliminar?.nombre}</strong>. Los envíos ya registrados conservan
            su nombre: no pierden a quién pertenecían.
          </>
        }
        cargando={eliminar.isPending}
        onConfirmar={async () => {
          if (!porEliminar) return;
          await eliminar.mutateAsync(porEliminar.cliente_id);
          avisar("Cliente eliminado.", "exito");
          setPorEliminar(null);
        }}
        onCancelar={() => setPorEliminar(null)}
      />
    </>
  );
}

function FormularioCliente({
  inicial,
  cargando,
  error,
  onGuardar,
  onCancelar,
}: {
  inicial: Partial<Cliente>;
  cargando: boolean;
  error: string | null;
  onGuardar: (datos: Partial<Cliente>) => void;
  onCancelar: () => void;
}) {
  const [datos, setDatos] = useState(inicial);
  const cambiar = (campo: keyof Cliente) => (evento: React.ChangeEvent<HTMLInputElement>) =>
    setDatos((previo) => ({ ...previo, [campo]: evento.target.value }));

  return (
    <>
      <div className="tarjeta__cabecera">
        <h2 className="tarjeta__titulo">{inicial.cliente_id ? "Editar cliente" : "Nuevo cliente"}</h2>
      </div>
      <form
        className="tarjeta__cuerpo pila-sm"
        onSubmit={(evento) => {
          evento.preventDefault();
          onGuardar(datos);
        }}
      >
        <Campo etiqueta="Nombre o razón social" required minLength={2} value={datos.nombre ?? ""} onChange={cambiar("nombre")} />
        <div className="rejilla rejilla--2">
          <Campo etiqueta="Documento o NIT" opcional value={datos.documento ?? ""} onChange={cambiar("documento")} />
          <Campo etiqueta="Teléfono" opcional type="tel" value={datos.telefono ?? ""} onChange={cambiar("telefono")} />
        </div>
        <Campo etiqueta="Correo" opcional type="email" value={datos.correo ?? ""} onChange={cambiar("correo")} />
        <Campo etiqueta="Dirección" opcional value={datos.direccion ?? ""} onChange={cambiar("direccion")} />
        <div className="rejilla rejilla--2">
          <Campo etiqueta="Ciudad" opcional value={datos.ciudad ?? ""} onChange={cambiar("ciudad")} />
          <Campo etiqueta="Departamento" opcional value={datos.departamento ?? ""} onChange={cambiar("departamento")} />
        </div>

        {error && <Aviso tono="error">{error}</Aviso>}

        <div className="acciones">
          <Boton type="submit" cargando={cargando}>
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

/* ---------------------------------------------------------------------- */
/* Transportistas                                                         */
/* ---------------------------------------------------------------------- */

const TRANSPORTISTA_VACIO: Partial<Transportista> = {
  nombre: "",
  correo: "",
  telefono: "",
  tipo: "tercero",
  nit: "",
  ciudad: "",
  departamento: "",
  activo: true,
};

function PantallaTransportistas() {
  const { puede } = useSesion();
  const { avisar } = useNotificaciones();
  const { data, isPending, error } = useTransportistas();
  const guardar = useGuardarTransportista();
  const eliminar = useEliminarTransportista();

  const [busqueda, setBusqueda] = useState("");
  const [editando, setEditando] = useState<Partial<Transportista> | null>(null);
  const [porEliminar, setPorEliminar] = useState<Transportista | null>(null);

  const puedeEditar = puede("maestro:editar");
  const registros = useMemo(
    () => (data?.transportistas ?? []).filter((t) => coincide(t as never, busqueda)),
    [data, busqueda],
  );

  const columnas: ColumnaTabla<Transportista>[] = [
    { clave: "nombre", titulo: "Nombre", envuelve: true, render: (t) => <strong>{t.nombre}</strong> },
    {
      clave: "tipo",
      titulo: "Tipo",
      render: (t) => (
        <span className={`etiqueta ${t.tipo === "propio" ? "etiqueta--ALLOW" : ""}`}>{t.tipo}</span>
      ),
    },
    { clave: "nit", titulo: "NIT", render: (t) => t.nit || "—" },
    { clave: "correo", titulo: "Correo", envuelve: true, render: (t) => t.correo || "—" },
    { clave: "telefono", titulo: "Teléfono", render: (t) => t.telefono || "—" },
    { clave: "activo", titulo: "Estado", render: (t) => <EstadoActivo activo={t.activo} /> },
  ];

  return (
    <>
      <Encabezado
        titulo="Transportistas"
        descripcion="Flota propia y terceros que mueven la carga. Distinguirlos importa: la responsabilidad ante el cliente no se subcontrata."
        total={data?.total ?? 0}
        busqueda={busqueda}
        onBuscar={setBusqueda}
        onCrear={() => setEditando({ ...TRANSPORTISTA_VACIO })}
        puedeEditar={puedeEditar}
        textoCrear="Agregar transportista"
      />

      {error && <Aviso tono="error">{mensajeDeError(error)}</Aviso>}

      {isPending ? (
        <Esqueleto alto="16rem" />
      ) : (
        <TablaDatos
          columnas={columnas}
          registros={registros}
          claveDe={(t) => t.transportista_id}
          acciones={
            puedeEditar
              ? (t) => (
                  <div className="fila">
                    <Boton variante="sutil" onClick={() => setEditando(t)}>
                      Editar
                    </Boton>
                    <Boton variante="sutil" onClick={() => setPorEliminar(t)}>
                      Eliminar
                    </Boton>
                  </div>
                )
              : undefined
          }
          vacio={<Vacio titulo={busqueda ? "Ningún transportista coincide" : "Sin transportistas"} />}
        />
      )}

      <Modal
        titulo={editando?.transportista_id ? "Editar transportista" : "Nuevo transportista"}
        abierto={editando !== null}
        onCerrar={() => setEditando(null)}
      >
        {editando && (
          <FormularioTransportista
            inicial={editando}
            cargando={guardar.isPending}
            error={guardar.isError ? mensajeDeError(guardar.error) : null}
            onGuardar={async (datos) => {
              try {
                await guardar.mutateAsync({ id: datos.transportista_id, datos });
                avisar(datos.transportista_id ? "Transportista actualizado." : "Transportista creado.", "exito");
                setEditando(null);
              } catch {
                /* Se muestra dentro del formulario. */
              }
            }}
            onCancelar={() => setEditando(null)}
          />
        )}
      </Modal>

      <Confirmacion
        abierto={porEliminar !== null}
        titulo="Eliminar transportista"
        descripcion={
          <>
            Se eliminará <strong>{porEliminar?.nombre}</strong>. Los envíos ya registrados conservan
            su nombre.
          </>
        }
        cargando={eliminar.isPending}
        onConfirmar={async () => {
          if (!porEliminar) return;
          await eliminar.mutateAsync(porEliminar.transportista_id);
          avisar("Transportista eliminado.", "exito");
          setPorEliminar(null);
        }}
        onCancelar={() => setPorEliminar(null)}
      />
    </>
  );
}

function FormularioTransportista({
  inicial,
  cargando,
  error,
  onGuardar,
  onCancelar,
}: {
  inicial: Partial<Transportista>;
  cargando: boolean;
  error: string | null;
  onGuardar: (datos: Partial<Transportista>) => void;
  onCancelar: () => void;
}) {
  const [datos, setDatos] = useState(inicial);
  const cambiar =
    (campo: keyof Transportista) =>
    (evento: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setDatos((previo) => ({ ...previo, [campo]: evento.target.value }));

  return (
    <>
      <div className="tarjeta__cabecera">
        <h2 className="tarjeta__titulo">
          {inicial.transportista_id ? "Editar transportista" : "Nuevo transportista"}
        </h2>
      </div>
      <form
        className="tarjeta__cuerpo pila-sm"
        onSubmit={(evento) => {
          evento.preventDefault();
          onGuardar(datos);
        }}
      >
        <Campo etiqueta="Nombre" required minLength={2} value={datos.nombre ?? ""} onChange={cambiar("nombre")} />
        <div className="rejilla rejilla--2">
          <CampoSelect etiqueta="Tipo" value={datos.tipo ?? "tercero"} onChange={cambiar("tipo")}>
            <option value="propio">Flota propia</option>
            <option value="tercero">Tercero</option>
          </CampoSelect>
          <Campo etiqueta="NIT" opcional value={datos.nit ?? ""} onChange={cambiar("nit")} />
        </div>
        <div className="rejilla rejilla--2">
          <Campo etiqueta="Correo" opcional type="email" value={datos.correo ?? ""} onChange={cambiar("correo")} />
          <Campo etiqueta="Teléfono" opcional type="tel" value={datos.telefono ?? ""} onChange={cambiar("telefono")} />
        </div>
        <div className="rejilla rejilla--2">
          <Campo etiqueta="Ciudad" opcional value={datos.ciudad ?? ""} onChange={cambiar("ciudad")} />
          <Campo etiqueta="Departamento" opcional value={datos.departamento ?? ""} onChange={cambiar("departamento")} />
        </div>

        {error && <Aviso tono="error">{error}</Aviso>}

        <div className="acciones">
          <Boton type="submit" cargando={cargando}>
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
