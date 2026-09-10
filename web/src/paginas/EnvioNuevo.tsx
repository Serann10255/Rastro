/* Registro de envíos: uno a uno o en lote desde un archivo.
 *
 * El registro masivo no es una comodidad: es la operación habitual de un cliente
 * corporativo, que despacha decenas de envíos de una vez. Sin él, el sistema
 * obliga a teclear cincuenta formularios y nadie lo usa.
 */

import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { DatosEnvio } from "@/api/cliente";
import { useClientes, useCrearEnvio, useCrearLote, useTiendas, useTransportistas } from "@/api/consultas";
import { mensajeDeError, useNotificaciones } from "@/componentes/notificaciones";
import {
  Aviso,
  Boton,
  Campo,
  CampoArea,
  CampoSelect,
  GrupoSegmentado,
  Tarjeta,
} from "@/componentes/ui";
import type { ResultadoLote } from "@/tipos";

type Modo = "uno" | "lote";

export function EnvioNuevo() {
  const [modo, setModo] = useState<Modo>("uno");

  return (
    <>
      <header className="encabezado-pagina">
        <div className="fila-entre">
          <div className="min-cero">
            <h1>Registrar envíos</h1>
            <p className="encabezado-pagina__descripcion">
              El sistema genera un identificador aleatorio por envío y crea el registro maestro en
              estado <strong>CREADO</strong> (código 10). A partir de ahí, cada cambio de estado
              queda atribuido a quien lo hizo.
            </p>
          </div>
          <GrupoSegmentado
            etiqueta="Modo"
            valor={modo}
            opciones={[
              { valor: "uno", texto: "Un envío" },
              { valor: "lote", texto: "Lote" },
            ]}
            onCambio={(valor) => setModo(valor as Modo)}
          />
        </div>
      </header>

      {modo === "uno" ? <FormularioUnico /> : <CargaDeLote />}
    </>
  );
}

/* ---------------------------------------------------------------------- */
/* Un envío                                                               */
/* ---------------------------------------------------------------------- */

interface Formulario {
  origen: string;
  origenReferencia: string;
  destino: string;
  destinoReferencia: string;
  ciudad: string;
  destinatario: string;
  telefono: string;
  descripcion: string;
  ordenCompra: string;
  tiendaId: string;
  clienteId: string;
  transportistaId: string;
  bultos: string;
  pesoKg: string;
  valorDeclarado: string;
  fechaEstimada: string;
  observaciones: string;
}

const VACIO: Formulario = {
  origen: "",
  origenReferencia: "",
  destino: "",
  destinoReferencia: "",
  ciudad: "Bogotá",
  destinatario: "",
  telefono: "",
  descripcion: "",
  ordenCompra: "",
  tiendaId: "",
  clienteId: "",
  transportistaId: "",
  bultos: "1",
  pesoKg: "",
  valorDeclarado: "",
  fechaEstimada: "",
  observaciones: "",
};

function FormularioUnico() {
  const navegar = useNavigate();
  const { avisar } = useNotificaciones();
  const crear = useCrearEnvio();

  const { data: tiendas } = useTiendas();
  const { data: clientes } = useClientes();
  const { data: transportistas } = useTransportistas();

  const [datos, setDatos] = useState<Formulario>(VACIO);
  const [errores, setErrores] = useState<Partial<Record<keyof Formulario, string>>>({});

  const cambiar =
    (campo: keyof Formulario) =>
    (evento: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      setDatos((previo) => ({ ...previo, [campo]: evento.target.value }));
      setErrores((previo) => ({ ...previo, [campo]: undefined }));
    };

  /* Se valida en el cliente para no gastar un viaje de red en un campo vacío,
   * pero el servidor vuelve a validar: esto es comodidad, no control. */
  const validar = (): boolean => {
    const nuevos: Partial<Record<keyof Formulario, string>> = {};
    if (datos.origen.trim().length < 3) nuevos.origen = "Indique la dirección de recogida.";
    if (datos.destino.trim().length < 3) nuevos.destino = "Indique la dirección de entrega.";
    if (datos.destinatario.trim().length < 2) nuevos.destinatario = "Indique quién recibe el envío.";
    setErrores(nuevos);
    return Object.keys(nuevos).length === 0;
  };

  // Al elegir tienda se propone su dirección como origen: es lo que ocurre en
  // la práctica y ahorra teclear la misma dirección cincuenta veces.
  const elegirTienda = (evento: React.ChangeEvent<HTMLSelectElement>) => {
    const tienda = tiendas?.tiendas.find((t) => t.tienda_id === evento.target.value);
    setDatos((previo) => ({
      ...previo,
      tiendaId: evento.target.value,
      origen: tienda?.direccion || previo.origen,
      origenReferencia: tienda?.nombre || previo.origenReferencia,
    }));
  };

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!validar()) return;

    try {
      const resultado = await crear.mutateAsync(aDatosEnvio(datos));
      avisar(`Envío registrado. Guía ${resultado.envio.envio_id}.`, "exito");
      navegar(`/envios/${resultado.envio.envio_id}`, { state: { recienCreado: true } });
    } catch {
      /* Se muestra bajo el formulario, no en una notificación que desaparece:
       * el usuario tiene que poder leerlo y corregir. */
    }
  };

  return (
    <form onSubmit={enviar} noValidate>
      <div className="doble-panel">
        <div className="pila">
          <Tarjeta titulo="Recogida y entrega">
            <div className="pila-sm">
              <CampoSelect
                etiqueta="Tienda de origen"
                value={datos.tiendaId}
                onChange={elegirTienda}
                ayuda="Al elegirla se propone su dirección como origen."
              >
                <option value="">Sin tienda asociada</option>
                {tiendas?.tiendas.map((tienda) => (
                  <option key={tienda.tienda_id} value={tienda.tienda_id}>
                    {tienda.codigo} · {tienda.nombre}
                  </option>
                ))}
              </CampoSelect>

              <Campo
                etiqueta="Dirección de recogida"
                required
                placeholder="Calle 100 #15-20"
                value={datos.origen}
                onChange={cambiar("origen")}
                error={errores.origen}
              />
              <Campo
                etiqueta="Referencia de recogida"
                opcional
                placeholder="Oficina 402, portería norte"
                value={datos.origenReferencia}
                onChange={cambiar("origenReferencia")}
              />
              <Campo
                etiqueta="Dirección de entrega"
                required
                placeholder="Carrera 7 #32-16"
                value={datos.destino}
                onChange={cambiar("destino")}
                error={errores.destino}
              />
              <Campo
                etiqueta="Referencia de entrega"
                opcional
                placeholder="Piso 8"
                value={datos.destinoReferencia}
                onChange={cambiar("destinoReferencia")}
              />
              <Campo etiqueta="Ciudad" value={datos.ciudad} onChange={cambiar("ciudad")} />
            </div>
          </Tarjeta>

          <Tarjeta titulo="Carga">
            <div className="rejilla rejilla--3">
              <Campo
                etiqueta="Bultos"
                type="number"
                min={1}
                max={500}
                value={datos.bultos}
                onChange={cambiar("bultos")}
              />
              <Campo
                etiqueta="Peso (kg)"
                opcional
                type="number"
                step="0.01"
                min={0}
                value={datos.pesoKg}
                onChange={cambiar("pesoKg")}
              />
              <Campo
                etiqueta="Valor declarado"
                opcional
                type="number"
                min={0}
                value={datos.valorDeclarado}
                onChange={cambiar("valorDeclarado")}
                ayuda="No se imprime en la guía."
              />
            </div>
          </Tarjeta>
        </div>

        <div className="pila">
          <Tarjeta titulo="Destinatario y referencias">
            <div className="pila-sm">
              <Campo
                etiqueta="Nombre del destinatario"
                required
                placeholder="Nombre y apellido"
                value={datos.destinatario}
                onChange={cambiar("destinatario")}
                error={errores.destinatario}
                ayuda="En la consulta pública el nombre se muestra enmascarado."
              />
              <Campo
                etiqueta="Teléfono"
                opcional
                type="tel"
                inputMode="tel"
                value={datos.telefono}
                onChange={cambiar("telefono")}
              />

              <CampoSelect etiqueta="Cliente" value={datos.clienteId} onChange={cambiar("clienteId")}>
                <option value="">Sin cliente asociado</option>
                {clientes?.clientes.map((cliente) => (
                  <option key={cliente.cliente_id} value={cliente.cliente_id}>
                    {cliente.nombre}
                  </option>
                ))}
              </CampoSelect>

              <CampoSelect
                etiqueta="Transportista"
                value={datos.transportistaId}
                onChange={cambiar("transportistaId")}
              >
                <option value="">Por asignar</option>
                {transportistas?.transportistas.map((transportista) => (
                  <option key={transportista.transportista_id} value={transportista.transportista_id}>
                    {transportista.nombre} ({transportista.tipo})
                  </option>
                ))}
              </CampoSelect>

              <Campo
                etiqueta="Orden de compra"
                opcional
                placeholder="OC-2026-1042"
                value={datos.ordenCompra}
                onChange={cambiar("ordenCompra")}
                ayuda="La referencia del cliente. No la genera el sistema y puede repetirse."
              />
              <Campo
                etiqueta="Fecha estimada de entrega"
                opcional
                type="date"
                value={datos.fechaEstimada}
                onChange={cambiar("fechaEstimada")}
                ayuda="Sirve para saber qué envíos van tarde."
              />
              <CampoArea
                etiqueta="Descripción del contenido"
                opcional
                rows={2}
                placeholder="Sobre con documentos contractuales"
                value={datos.descripcion}
                onChange={cambiar("descripcion")}
              />
            </div>
          </Tarjeta>

          <Aviso tono="info" titulo="Datos sintéticos">
            El sistema se puebla únicamente con datos sintéticos, de modo que el proyecto no genera
            obligaciones de tratamiento sobre titulares reales.
          </Aviso>

          {crear.isError && (
            <Aviso tono="error" titulo="No se pudo registrar el envío">
              {mensajeDeError(crear.error)}
            </Aviso>
          )}

          <div className="acciones">
            <Boton type="submit" cargando={crear.isPending} grande>
              Registrar envío
            </Boton>
            <Boton type="button" variante="secundario" onClick={() => navegar(-1)}>
              Cancelar
            </Boton>
          </div>
        </div>
      </div>
    </form>
  );
}

function aDatosEnvio(datos: Formulario): DatosEnvio {
  return {
    origen: {
      linea: datos.origen.trim(),
      ciudad: datos.ciudad.trim() || "Bogotá",
      referencia: datos.origenReferencia.trim() || undefined,
    },
    destino: {
      linea: datos.destino.trim(),
      ciudad: datos.ciudad.trim() || "Bogotá",
      referencia: datos.destinoReferencia.trim() || undefined,
    },
    destinatario: {
      nombre: datos.destinatario.trim(),
      telefono: datos.telefono.trim() || undefined,
    },
    descripcion: datos.descripcion.trim() || undefined,
    orden_compra: datos.ordenCompra.trim() || undefined,
    tienda_id: datos.tiendaId || undefined,
    cliente_id: datos.clienteId || undefined,
    transportista_id: datos.transportistaId || undefined,
    bultos: Number(datos.bultos) || 1,
    peso_kg: Number(datos.pesoKg) || 0,
    valor_declarado: Number(datos.valorDeclarado) || 0,
    fecha_estimada: datos.fechaEstimada || undefined,
    observaciones: datos.observaciones.trim() || undefined,
  };
}

/* ---------------------------------------------------------------------- */
/* Lote                                                                   */
/* ---------------------------------------------------------------------- */

const COLUMNAS_LOTE = [
  "destinatario",
  "telefono",
  "direccion_destino",
  "ciudad_destino",
  "direccion_origen",
  "descripcion",
  "orden_compra",
  "bultos",
  "peso_kg",
  "valor_declarado",
  "fecha_estimada",
];

const PLANTILLA = `${COLUMNAS_LOTE.join(",")}
Laura Mejia Rios,3001110001,Carrera 7 #32-16,Bogotá,Calle 100 #15-20,Sobre con documentos,OC-2026-1001,1,0.5,80000,2026-09-15
Andres Pardo Leon,3001110002,Calle 45 #13-05,Bogotá,Calle 100 #15-20,Caja de muestras,OC-2026-1002,2,3.2,150000,2026-09-15`;

function CargaDeLote() {
  const navegar = useNavigate();
  const { avisar } = useNotificaciones();
  const crearLote = useCrearLote();

  const { data: tiendas } = useTiendas();
  const { data: clientes } = useClientes();

  const [texto, setTexto] = useState("");
  const [tiendaId, setTiendaId] = useState("");
  const [clienteId, setClienteId] = useState("");
  const [resultado, setResultado] = useState<ResultadoLote | null>(null);

  const analisis = useMemo(() => analizarCsv(texto), [texto]);

  const enviar = async () => {
    if (!analisis.filas.length) return;
    const envios = analisis.filas.map((fila) => ({
      ...fila,
      tienda_id: tiendaId || undefined,
      cliente_id: clienteId || undefined,
    }));
    try {
      const respuesta = await crearLote.mutateAsync(envios);
      setResultado(respuesta);
      avisar(
        `${respuesta.resumen.creados} envíos registrados${
          respuesta.resumen.rechazados ? `, ${respuesta.resumen.rechazados} rechazados` : ""
        }.`,
        respuesta.resumen.rechazados ? "alerta" : "exito",
      );
    } catch {
      /* Se muestra bajo el formulario. */
    }
  };

  const descargarPlantilla = () => {
    const url = URL.createObjectURL(new Blob([PLANTILLA], { type: "text/csv;charset=utf-8" }));
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = "plantilla-envios.csv";
    enlace.click();
    URL.revokeObjectURL(url);
  };

  const leerArchivo = async (evento: React.ChangeEvent<HTMLInputElement>) => {
    const archivo = evento.target.files?.[0];
    if (archivo) setTexto(await archivo.text());
  };

  return (
    <div className="doble-panel">
      <div className="pila">
        <Tarjeta
          titulo="Archivo de envíos"
          ayuda="Un envío por fila, separado por comas. La primera fila son los nombres de columna."
          acciones={
            <Boton variante="secundario" onClick={descargarPlantilla}>
              Descargar plantilla
            </Boton>
          }
        >
          <div className="pila-sm">
            <Campo etiqueta="Archivo CSV" type="file" accept=".csv,text/csv" onChange={leerArchivo} />

            <CampoArea
              etiqueta="O pegue el contenido"
              rows={8}
              placeholder={PLANTILLA}
              value={texto}
              onChange={(evento) => setTexto(evento.target.value)}
              ayuda={`Columnas reconocidas: ${COLUMNAS_LOTE.join(", ")}.`}
            />

            <div className="rejilla rejilla--2">
              <CampoSelect
                etiqueta="Tienda para todo el lote"
                value={tiendaId}
                onChange={(evento) => setTiendaId(evento.target.value)}
              >
                <option value="">Sin tienda</option>
                {tiendas?.tiendas.map((tienda) => (
                  <option key={tienda.tienda_id} value={tienda.tienda_id}>
                    {tienda.codigo} · {tienda.nombre}
                  </option>
                ))}
              </CampoSelect>
              <CampoSelect
                etiqueta="Cliente para todo el lote"
                value={clienteId}
                onChange={(evento) => setClienteId(evento.target.value)}
              >
                <option value="">Sin cliente</option>
                {clientes?.clientes.map((cliente) => (
                  <option key={cliente.cliente_id} value={cliente.cliente_id}>
                    {cliente.nombre}
                  </option>
                ))}
              </CampoSelect>
            </div>
          </div>
        </Tarjeta>
      </div>

      <div className="pila">
        <Tarjeta titulo="Vista previa">
          {analisis.error && <Aviso tono="error">{analisis.error}</Aviso>}

          {!texto.trim() && (
            <p className="texto-sm texto-suave">
              Pegue el contenido o elija un archivo para ver aquí lo que se va a registrar.
            </p>
          )}

          {analisis.filas.length > 0 && (
            <>
              <p className="texto-sm">
                <strong>{analisis.filas.length}</strong> envíos listos.
                {analisis.ignoradas > 0 && (
                  <span className="texto-suave">
                    {" "}
                    {analisis.ignoradas} filas se omitieron por no tener destinatario o dirección.
                  </span>
                )}
              </p>
              <ul className="lista" style={{ marginTop: "var(--e-3)" }}>
                {analisis.filas.slice(0, 5).map((fila, indice) => (
                  <li key={indice} className="envio">
                    <span className="envio__destinatario">{fila.destinatario.nombre}</span>
                    <span className="envio__detalle">
                      {fila.destino.linea} · {fila.destino.ciudad}
                    </span>
                    {fila.orden_compra && <span className="envio__id">OC {fila.orden_compra}</span>}
                  </li>
                ))}
              </ul>
              {analisis.filas.length > 5 && (
                <p className="texto-xs texto-tenue" style={{ marginTop: "var(--e-2)" }}>
                  y {analisis.filas.length - 5} más.
                </p>
              )}
            </>
          )}

          {crearLote.isError && (
            <div style={{ marginTop: "var(--e-3)" }}>
              <Aviso tono="error">{mensajeDeError(crearLote.error)}</Aviso>
            </div>
          )}

          <div className="acciones">
            <Boton
              onClick={enviar}
              cargando={crearLote.isPending}
              disabled={analisis.filas.length === 0}
              grande
            >
              Registrar {analisis.filas.length || ""} envíos
            </Boton>
          </div>
        </Tarjeta>

        {resultado && (
          <Tarjeta
            titulo="Resultado del lote"
            acciones={
              resultado.creados.length > 0 ? (
                <Boton
                  onClick={() =>
                    navegar("/envios/guias", {
                      state: { envios: resultado.creados.map((e) => e.envio_id) },
                    })
                  }
                >
                  Generar guías
                </Boton>
              ) : undefined
            }
          >
            <Aviso tono={resultado.resumen.rechazados ? "alerta" : "exito"}>
              {resultado.resumen.creados} de {resultado.resumen.solicitados} envíos registrados.
            </Aviso>

            {resultado.rechazados.length > 0 && (
              <>
                <p className="texto-sm texto-suave" style={{ marginTop: "var(--e-3)" }}>
                  Las filas rechazadas no impidieron el resto. Corrija estas y vuelva a enviarlas:
                </p>
                <div className="tabla-contenedor" style={{ marginTop: "var(--e-2)" }}>
                  <table className="tabla" style={{ minWidth: "28rem" }}>
                    <thead>
                      <tr>
                        <th scope="col">Fila</th>
                        <th scope="col">Destinatario</th>
                        <th scope="col">Motivo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {resultado.rechazados.map((rechazado) => (
                        <tr key={rechazado.indice}>
                          <td className="tabla__numero">{rechazado.indice + 2}</td>
                          <td className="envuelve">{rechazado.destinatario}</td>
                          <td className="envuelve">{rechazado.motivo}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Tarjeta>
        )}
      </div>
    </div>
  );
}

/* Analizador de CSV mínimo, con comillas.
 *
 * Se escribe a mano en lugar de traer una biblioteca porque el formato que hay
 * que aceptar es el que produce una hoja de cálculo al guardar como CSV, y eso
 * son comas, saltos de línea y comillas dobles. Una biblioteca completa
 * añadiría dialectos que nadie va a usar. */
function analizarCsv(texto: string): {
  filas: DatosEnvio[];
  ignoradas: number;
  error: string | null;
} {
  const contenido = texto.trim();
  if (!contenido) return { filas: [], ignoradas: 0, error: null };

  const lineas = contenido.split(/\r?\n/).filter((linea) => linea.trim());
  if (lineas.length < 2) {
    return { filas: [], ignoradas: 0, error: "Hace falta la fila de nombres de columna y al menos un envío." };
  }

  const cabecera = separar(lineas[0]!).map((c) => c.trim().toLowerCase());
  const indice = (nombre: string) => cabecera.indexOf(nombre);

  if (indice("destinatario") === -1 || indice("direccion_destino") === -1) {
    return {
      filas: [],
      ignoradas: 0,
      error: "El archivo debe tener al menos las columnas «destinatario» y «direccion_destino».",
    };
  }

  const filas: DatosEnvio[] = [];
  let ignoradas = 0;

  for (const linea of lineas.slice(1)) {
    const celdas = separar(linea);
    const valor = (nombre: string) => (indice(nombre) >= 0 ? (celdas[indice(nombre)] ?? "").trim() : "");

    const destinatario = valor("destinatario");
    const direccion = valor("direccion_destino");
    if (!destinatario || !direccion) {
      ignoradas += 1;
      continue;
    }

    const ciudad = valor("ciudad_destino") || "Bogotá";
    filas.push({
      origen: { linea: valor("direccion_origen") || direccion, ciudad },
      destino: { linea: direccion, ciudad },
      destinatario: { nombre: destinatario, telefono: valor("telefono") || undefined },
      descripcion: valor("descripcion") || undefined,
      orden_compra: valor("orden_compra") || undefined,
      bultos: Number(valor("bultos")) || 1,
      peso_kg: Number(valor("peso_kg")) || 0,
      valor_declarado: Number(valor("valor_declarado")) || 0,
      fecha_estimada: valor("fecha_estimada") || undefined,
    });
  }

  return { filas, ignoradas, error: null };
}

function separar(linea: string): string[] {
  const celdas: string[] = [];
  let actual = "";
  let entreComillas = false;

  for (let i = 0; i < linea.length; i += 1) {
    const caracter = linea[i]!;
    if (caracter === '"') {
      // Dos comillas seguidas dentro de un campo entrecomillado son una comilla.
      if (entreComillas && linea[i + 1] === '"') {
        actual += '"';
        i += 1;
      } else {
        entreComillas = !entreComillas;
      }
    } else if (caracter === "," && !entreComillas) {
      celdas.push(actual);
      actual = "";
    } else {
      actual += caracter;
    }
  }
  celdas.push(actual);
  return celdas;
}
