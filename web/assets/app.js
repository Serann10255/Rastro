/* Interfaz de operacion de Rastro.
 *
 * Aplicacion de pagina unica sin dependencias ni paso de compilacion: se sirve
 * como sitio estatico desde el almacenamiento de objetos, que es lo que la
 * mantiene disponible entre sesiones del laboratorio.
 *
 * La interfaz oculta lo que un rol no puede hacer, pero eso es comodidad y no
 * control: la autorizacion la decide el servidor en cada operacion. Cualquiera
 * puede editar esta pagina; nadie puede editar la matriz de autorizacion.
 */

import { api, cargarConfiguracion, cargarEvidencia, ErrorApi, formatearFecha, sesion } from "./api.js";

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const estado = {
  vista: "envios",
  envios: [],
  envioActivo: null,
  transiciones: [],
};

/* --------------------------------------------------------------------- */
/* Utilidades de presentacion                                            */
/* --------------------------------------------------------------------- */

function avisar(mensaje, tipo = "info") {
  const caja = $("#aviso");
  caja.textContent = mensaje;
  caja.className = `aviso aviso--${tipo}`;
  caja.hidden = !mensaje;
  if (mensaje) caja.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function manejarError(error) {
  if (error instanceof ErrorApi) {
    if (error.estado === 401) {
      mostrarAcceso();
      avisar("La sesion expiro. Vuelva a entrar.", "error");
      return;
    }
    if (error.estado === 403) {
      avisar(`Operacion no permitida para su rol. El intento quedo en la bitacora.`, "error");
      return;
    }
    if (error.estado === 404) {
      avisar("El recurso no existe o no pertenece a su organizacion.", "error");
      return;
    }
    const permitidas = error.detalle?.permitidas;
    avisar(
      permitidas ? `${error.message} Transiciones permitidas: ${permitidas.join(", ")}.` : error.message,
      "error"
    );
    return;
  }
  avisar(error.message || "Ocurrio un error inesperado.", "error");
}

function etiquetaEstado(valor) {
  return `<span class="etiqueta etiqueta--${valor}">${valor.replace(/_/g, " ")}</span>`;
}

const escapar = (texto) =>
  String(texto ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

/* --------------------------------------------------------------------- */
/* Acceso                                                                */
/* --------------------------------------------------------------------- */

function mostrarAcceso() {
  $("#pantalla-acceso").hidden = false;
  $("#pantalla-trabajo").hidden = true;
  $("#sesion-info").textContent = "";
  $("#boton-salir").hidden = true;
}

async function mostrarTrabajo() {
  const actual = sesion.leer();
  $("#pantalla-acceso").hidden = true;
  $("#pantalla-trabajo").hidden = false;
  $("#boton-salir").hidden = false;
  $("#sesion-info").textContent =
    `${actual.usuario.nombre || actual.usuario.email} · ${actual.usuario.org_id} · ${actual.usuario.grupos.join(", ")}`;

  ajustarNavegacionAlRol();
  await irA(sesion.tieneGrupo("auditor") ? "bitacora" : "envios");
}

function ajustarNavegacionAlRol() {
  $("#nav-nuevo").hidden = !sesion.tieneGrupo("despachador", "administrador");
  $("#nav-bitacora").hidden = !sesion.tieneGrupo("auditor");
  $("#nav-envios").hidden = sesion.tieneGrupo("auditor") && !sesion.tieneGrupo("despachador");
}

$("#formulario-acceso").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const boton = $("#formulario-acceso button[type=submit]");
  boton.disabled = true;
  try {
    await api.entrar($("#acceso-usuario").value.trim(), $("#acceso-clave").value);
    avisar("");
    await mostrarTrabajo();
  } catch (error) {
    manejarError(error);
  } finally {
    boton.disabled = false;
  }
});

$("#boton-salir").addEventListener("click", () => {
  sesion.cerrar();
  mostrarAcceso();
  avisar("Sesion cerrada.", "info");
});

/* --------------------------------------------------------------------- */
/* Navegacion                                                            */
/* --------------------------------------------------------------------- */

$$(".navegacion__boton").forEach((boton) =>
  boton.addEventListener("click", () => irA(boton.dataset.vista))
);

async function irA(vista) {
  estado.vista = vista;
  $$(".vista").forEach((seccion) => (seccion.hidden = seccion.dataset.vista !== vista));
  $$(".navegacion__boton").forEach((boton) =>
    boton.setAttribute("aria-current", boton.dataset.vista === vista ? "page" : "false")
  );
  avisar("");

  if (vista === "envios") await refrescarEnvios();
  if (vista === "bitacora") await refrescarBitacora();
}

/* --------------------------------------------------------------------- */
/* Envios                                                                */
/* --------------------------------------------------------------------- */

async function refrescarEnvios() {
  const contenedor = $("#lista-envios");
  contenedor.innerHTML = '<li class="vacio">Cargando envios...</li>';
  try {
    const datos = await api.listarEnvios();
    estado.envios = datos.envios;
    contenedor.innerHTML = datos.envios.length
      ? datos.envios.map(plantillaEnvio).join("")
      : '<li class="vacio">No hay envios registrados todavia.</li>';
    contenedor.querySelectorAll(".envio").forEach((boton) =>
      boton.addEventListener("click", () => abrirEnvio(boton.dataset.id))
    );
  } catch (error) {
    contenedor.innerHTML = '<li class="vacio">No fue posible cargar los envios.</li>';
    manejarError(error);
  }
}

function plantillaEnvio(envio) {
  return `
    <li>
      <button class="envio" type="button" data-id="${escapar(envio.envio_id)}">
        <span>
          <span class="envio__dato"><strong>${escapar(envio.destinatario)}</strong></span>
          <span class="envio__dato">${escapar(envio.destino)}</span>
          <span class="envio__id">${escapar(envio.envio_id)}</span>
        </span>
        ${etiquetaEstado(envio.estado)}
      </button>
    </li>`;
}

async function abrirEnvio(envioId) {
  try {
    const [detalle, transiciones] = await Promise.all([
      api.consultarEnvio(envioId),
      api.transiciones(envioId),
    ]);
    estado.envioActivo = detalle.envio;
    estado.transiciones = transiciones.transiciones;
    pintarDetalle(detalle, transiciones);
    await irA("detalle");
  } catch (error) {
    manejarError(error);
  }
}

function pintarDetalle(detalle, transiciones) {
  const { envio, eventos } = detalle;

  $("#detalle-encabezado").innerHTML = `
    <div class="envio__cabecera">
      <h2 class="tarjeta__titulo">${escapar(envio.destinatario.nombre)}</h2>
      ${etiquetaEstado(envio.estado)}
    </div>
    <p class="envio__id">${escapar(envio.envio_id)}</p>
    <p class="envio__dato">Origen: ${escapar(envio.origen.linea)}</p>
    <p class="envio__dato">Destino: ${escapar(envio.destino.linea)}</p>
    <p class="envio__dato">Mensajero: ${escapar(envio.conductor_nombre || "sin asignar")}</p>`;

  $("#detalle-linea").innerHTML = eventos
    .map(
      (evento) => `
      <li class="linea__paso linea__paso--${escapar(evento.estado)}">
        <strong>${escapar(evento.estado.replace(/_/g, " "))}</strong>
        <span class="linea__fecha">${escapar(formatearFecha(evento.ts))} · ${escapar(evento.actor_sub)}</span>
        ${evento.nota ? `<span class="envio__dato">${escapar(evento.nota)}</span>` : ""}
        ${evento.ubicacion ? `<span class="linea__fecha">${evento.ubicacion.lat.toFixed(5)}, ${evento.ubicacion.lon.toFixed(5)}</span>` : ""}
      </li>`
    )
    .join("");

  // La interfaz solo ofrece los estados alcanzables. El servidor los vuelve a
  // comprobar: esto reduce errores, no sustituye el control.
  const selector = $("#evento-estado");
  selector.innerHTML = transiciones.transiciones
    .map((estadoDestino) => `<option value="${estadoDestino}">${estadoDestino.replace(/_/g, " ")}</option>`)
    .join("");

  const puedeRegistrar = transiciones.transiciones.length > 0;
  $("#panel-evento").hidden = !puedeRegistrar;
  $("#panel-cerrado").hidden = puedeRegistrar;

  $("#aviso-reanudacion").hidden = !transiciones.exige_autorizacion_despachador;
  $("#panel-asignacion").hidden = !(
    envio.estado === "CREADO" && sesion.tieneGrupo("despachador", "administrador")
  );
  $("#panel-evidencia").hidden = !sesion.tieneGrupo("conductor");
}

/* --------------------------------------------------------------------- */
/* Registro de envio y asignacion                                        */
/* --------------------------------------------------------------------- */

$("#formulario-nuevo").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const formulario = new FormData(evento.target);
  try {
    const creado = await api.crearEnvio({
      origen: { linea: formulario.get("origen"), ciudad: formulario.get("ciudad") || "Bogota" },
      destino: { linea: formulario.get("destino"), ciudad: formulario.get("ciudad") || "Bogota" },
      destinatario: {
        nombre: formulario.get("destinatario"),
        telefono: formulario.get("telefono") || "",
      },
      descripcion: formulario.get("descripcion") || "",
    });
    evento.target.reset();
    avisar(`Envio registrado. Identificador de rastreo: ${creado.envio.envio_id}`, "exito");
    await abrirEnvio(creado.envio.envio_id);
  } catch (error) {
    manejarError(error);
  }
});

$("#formulario-asignacion").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const formulario = new FormData(evento.target);
  try {
    await api.asignarConductor(estado.envioActivo.envio_id, {
      conductor_sub: formulario.get("conductor_sub").trim(),
      conductor_nombre: formulario.get("conductor_nombre").trim(),
    });
    avisar("Mensajero asignado.", "exito");
    await abrirEnvio(estado.envioActivo.envio_id);
  } catch (error) {
    manejarError(error);
  }
});

/* --------------------------------------------------------------------- */
/* Punto de control                                                      */
/* --------------------------------------------------------------------- */

/* Un solo formulario y ningun campo obligatorio mas alla del estado: si
 * registrar el avance cuesta mas que enviar un mensaje, el mensajero vuelve al
 * mensaje y el sistema deja de tener datos. */
$("#formulario-evento").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const formulario = new FormData(evento.target);
  const cuerpo = { estado: formulario.get("estado"), nota: formulario.get("nota") || "" };

  const evidenciaId = $("#evidencia-confirmada").value;
  if (evidenciaId) cuerpo.evidencia_id = evidenciaId;

  if ($("#evento-ubicacion").checked) {
    try {
      cuerpo.ubicacion = await posicionActual();
    } catch {
      avisar("No se obtuvo la ubicacion; el punto de control se registra sin ella.", "info");
    }
  }

  try {
    await api.registrarEvento(estado.envioActivo.envio_id, cuerpo);
    evento.target.reset();
    $("#evidencia-confirmada").value = "";
    $("#estado-evidencia").textContent = "";
    avisar("Punto de control registrado.", "exito");
    await abrirEnvio(estado.envioActivo.envio_id);
  } catch (error) {
    manejarError(error);
  }
});

function posicionActual() {
  return new Promise((resolver, rechazar) => {
    if (!navigator.geolocation) return rechazar(new Error("Sin geolocalizacion"));
    navigator.geolocation.getCurrentPosition(
      (posicion) =>
        resolver({ lat: posicion.coords.latitude, lon: posicion.coords.longitude }),
      rechazar,
      { timeout: 8000, maximumAge: 30000 }
    );
  });
}

/* --------------------------------------------------------------------- */
/* Evidencia de entrega                                                  */
/* --------------------------------------------------------------------- */

$("#formulario-evidencia").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  const archivo = $("#evidencia-archivo").files[0];
  if (!archivo) return avisar("Seleccione o capture una imagen.", "error");

  const boton = $("#boton-evidencia");
  boton.disabled = true;
  $("#estado-evidencia").textContent = "Solicitando enlace...";

  try {
    const enlace = await api.solicitarEnlace(estado.envioActivo.envio_id, {
      nombre_archivo: archivo.name,
      tipo_contenido: archivo.type || "image/jpeg",
    });

    $("#estado-evidencia").textContent = "Cargando archivo...";
    await cargarEvidencia(enlace, archivo);

    $("#estado-evidencia").textContent = "Confirmando...";
    const confirmacion = await api.confirmarEvidencia(
      estado.envioActivo.envio_id,
      enlace.evidencia_id,
      archivo.type || "image/jpeg"
    );

    $("#evidencia-confirmada").value = enlace.evidencia_id;
    $("#estado-evidencia").textContent =
      `Evidencia guardada y cifrada (${confirmacion.propiedades.cifrado || "sin KMS en entorno local"}).`;
    avisar("Evidencia cargada. Ya puede registrar la entrega.", "exito");
  } catch (error) {
    $("#estado-evidencia").textContent = "";
    manejarError(error);
  } finally {
    boton.disabled = false;
  }
});

/* --------------------------------------------------------------------- */
/* Bitacora                                                              */
/* --------------------------------------------------------------------- */

async function refrescarBitacora() {
  const cuerpo = $("#tabla-bitacora tbody");
  cuerpo.innerHTML = '<tr><td colspan="6">Cargando...</td></tr>';
  try {
    const filtro = $("#bitacora-filtro").value;
    const datos = await api.bitacora(filtro);
    cuerpo.innerHTML = datos.registros.length
      ? datos.registros
          .slice()
          .reverse()
          .map(
            (registro) => `
        <tr>
          <td>${registro.seq}</td>
          <td>${escapar(formatearFecha(registro.ts))}</td>
          <td class="envuelve">${escapar(registro.actor_sub)}<br><span class="hash">${escapar(registro.actor_grupos.join(", "))}</span></td>
          <td class="envuelve">${escapar(registro.accion)}<br><span class="hash">${escapar(registro.recurso)}</span></td>
          <td><span class="etiqueta etiqueta--${registro.resultado}">${registro.resultado}</span></td>
          <td class="hash">${escapar(registro.hash.slice(0, 16))}...</td>
        </tr>`
          )
          .join("")
      : '<tr><td colspan="6">No hay registros.</td></tr>';
  } catch (error) {
    cuerpo.innerHTML = '<tr><td colspan="6">No fue posible cargar la bitacora.</td></tr>';
    manejarError(error);
  }
}

$("#bitacora-filtro").addEventListener("change", refrescarBitacora);

$("#boton-verificar").addEventListener("click", async () => {
  const caja = $("#resultado-verificacion");
  caja.hidden = false;
  caja.className = "aviso aviso--info";
  caja.textContent = "Recalculando la cadena...";
  try {
    const resultado = await api.verificarBitacora();
    if (resultado.cadena_valida) {
      caja.className = "aviso aviso--exito";
      caja.textContent =
        `Cadena integra: ${resultado.registros_verificados} registros verificados, ` +
        `secuencias ${resultado.primera_seq} a ${resultado.ultima_seq}.`;
    } else {
      const ruptura = resultado.punto_de_ruptura;
      caja.className = "aviso aviso--error";
      caja.textContent =
        `Cadena rota en la secuencia ${ruptura.seq ?? ruptura.seq_esperada}: ` +
        `${ruptura.tipo}. ${ruptura.descripcion}`;
    }
  } catch (error) {
    caja.hidden = true;
    manejarError(error);
  }
});

/* --------------------------------------------------------------------- */
/* Arranque                                                              */
/* --------------------------------------------------------------------- */

(async function iniciar() {
  const config = await cargarConfiguracion();
  $("#pie-entorno").textContent =
    `Entorno ${config.entorno || "local"} · region ${config.region || "us-east-1"}`;

  if (sesion.leer()) {
    await mostrarTrabajo();
  } else {
    mostrarAcceso();
  }
})();
