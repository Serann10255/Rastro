/* Captura las pantallas de las dos aplicaciones para las diapositivas.
 *
 * Recorre Rastro y Cotejo levantados en la pila local (`docker compose up -d`)
 * con el Edge instalado en el equipo, entra con los usuarios de la semilla y
 * guarda cada pantalla como WebP en esta carpeta. Cada archivo se cita en el
 * guion como `![Título](captura:nombre)`.
 *
 * Uso, desde `presentacion/`:
 *
 *   npm install --no-save playwright-core@1.56.1 sharp@0.34.3
 *   node capturas/capturar.mjs                 # todo
 *   node capturas/capturar.mjs --solo=ruta     # solo el modo ruta (rastro, cotejo, ruta)
 *
 * No añade dependencias al módulo: se instalan sin guardarlas y `npm ci` las
 * retira. No descarga navegadores: usa el canal `msedge` del equipo.
 *
 * Las dos interfaces se sirven con la configuración del despliegue en AWS
 * (`configuracion.json` apunta a la cuenta real). Aquí se intercepta esa
 * petición y se responde con la de la pila local, sin tocar el archivo: las
 * pantallas salen de los datos sintéticos de `seed/`, que es lo que se puede
 * proyectar.
 */

import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright-core");
const sharp = require("sharp");

const CARPETA = dirname(fileURLToPath(import.meta.url));
const RAIZ = join(CARPETA, "..", "..");

const URL_RASTRO = process.env.CAPTURA_URL_RASTRO ?? "http://localhost:5173";
const URL_COTEJO = process.env.CAPTURA_URL_COTEJO ?? "http://localhost:5175";
const API_RASTRO = process.env.CAPTURA_API_RASTRO ?? "http://localhost:8080";
const API_COTEJO = process.env.CAPTURA_API_COTEJO ?? "http://localhost:8007";

/** Tamaño de una pantalla de portátil corriente, a doble densidad para que el
 *  texto siga nítido cuando la captura ocupa media diapositiva de 1920 px. */
const VENTANA = { width: 1440, height: 900 };
const DENSIDAD = 2;
const CALIDAD_WEBP = 82;

const CONFIGURACION_RASTRO = {
  _nota: "Pila local: sustituye a la configuración de AWS solo durante la captura.",
  entorno: "local",
  region: "us-east-1",
  url_publica_api: API_RASTRO,
};
const CONFIGURACION_COTEJO = {
  _nota: "Pila local: sustituye a la configuración de AWS solo durante la captura.",
  entorno: "local",
  url_cotejo: API_COTEJO,
  url_rastro: API_RASTRO,
};

async function usuarios() {
  const semilla = JSON.parse(await readFile(join(RAIZ, "seed", "organizaciones.json"), "utf8"));
  const andes = semilla.organizaciones.find((o) => o.org_id === "org-andes");
  const porGrupo = (grupo) => andes.usuarios.find((u) => u.grupos.includes(grupo));
  return {
    administrador: porGrupo("administrador"),
    auditor: porGrupo("auditor"),
    conductores: andes.usuarios.filter((u) => u.grupos.includes("conductor")),
  };
}

async function guardar(pagina, nombre) {
  const png = await pagina.screenshot({ type: "png", fullPage: false });
  const destino = join(CARPETA, `${nombre}.webp`);
  await sharp(png).webp({ quality: CALIDAD_WEBP }).toFile(destino);
  const kb = Math.round((await readFile(destino)).byteLength / 1024);
  console.log(`  ${nombre}.webp · ${kb} KB`);
}

/** Espera a que la página termine de pedir datos y a que no queden esqueletos. */
async function asentar(pagina) {
  await pagina.waitForLoadState("networkidle");
  await pagina.waitForFunction(() => document.querySelectorAll(".esqueleto").length === 0, null, {
    timeout: 15000,
  });
  // Un respiro para las transiciones de la interfaz.
  await pagina.waitForTimeout(400);
}

async function contexto(navegador, origen, configuracion) {
  const ctx = await navegador.newContext({
    viewport: VENTANA,
    deviceScaleFactor: DENSIDAD,
    locale: "es-CO",
    timezoneId: "America/Bogota",
    colorScheme: "light",
  });
  await ctx.route(`${origen}/configuracion.json`, (ruta) =>
    ruta.fulfill({ json: configuracion, headers: { "cache-control": "no-store" } }),
  );
  return ctx;
}

/* ------------------------------------------------------------------------ */
/* Rastro                                                                   */
/* ------------------------------------------------------------------------ */

async function entrarEnRastro(pagina, usuario) {
  await pagina.goto(`${URL_RASTRO}/acceso`);
  await pagina.fill('input[name="correo"]', usuario.correo);
  await pagina.fill('input[name="clave"]', usuario.clave);
  await pagina.click('button[type="submit"]');
  await pagina.waitForURL((url) => !url.pathname.startsWith("/acceso"), { timeout: 20000 });
  await asentar(pagina);
}

async function capturarRastro(navegador, cuentas) {
  console.log("Rastro");
  const ctx = await contexto(navegador, URL_RASTRO, CONFIGURACION_RASTRO);
  const pagina = await ctx.newPage();

  await pagina.goto(`${URL_RASTRO}/acceso`);
  await asentar(pagina);
  await guardar(pagina, "rastro-acceso");

  await entrarEnRastro(pagina, cuentas.administrador);
  await pagina.goto(`${URL_RASTRO}/panel`);
  await asentar(pagina);
  await guardar(pagina, "rastro-panel");

  await pagina.goto(`${URL_RASTRO}/envios`);
  await asentar(pagina);
  await guardar(pagina, "rastro-envios");

  // El primer envío de la lista: su identificador sirve después para la
  // consulta pública.
  const enlace = pagina.locator('a[href^="/envios/"]:not([href="/envios/nuevo"]):not([href="/envios/guias"])').first();
  await enlace.click();
  await pagina.waitForURL(/\/envios\/[0-9a-f-]{36}$/);
  await asentar(pagina);
  await guardar(pagina, "rastro-envio");
  const envioId = new URL(pagina.url()).pathname.split("/").pop();

  await pagina.goto(`${URL_RASTRO}/administracion/roles`);
  await asentar(pagina);
  await guardar(pagina, "rastro-roles");

  await pagina.goto(`${URL_RASTRO}/operaciones`);
  await asentar(pagina);
  await guardar(pagina, "rastro-operaciones");

  await ctx.close();

  // El auditor: la bitácora que el administrador no puede leer.
  const ctxAuditor = await contexto(navegador, URL_RASTRO, CONFIGURACION_RASTRO);
  const auditor = await ctxAuditor.newPage();
  await entrarEnRastro(auditor, cuentas.auditor);
  await auditor.goto(`${URL_RASTRO}/bitacora`);
  await asentar(auditor);
  const verificar = auditor.getByRole("button", { name: /verificar/i }).first();
  if (await verificar.count()) {
    await verificar.click();
    await asentar(auditor);
  }
  await guardar(auditor, "rastro-bitacora");
  await ctxAuditor.close();

  // El destinatario, sin cuenta.
  const ctxPublico = await contexto(navegador, URL_RASTRO, CONFIGURACION_RASTRO);
  const publico = await ctxPublico.newPage();
  await publico.goto(`${URL_RASTRO}/rastreo?envio=${envioId}`);
  await asentar(publico);
  await guardar(publico, "rastro-rastreo");
  await ctxPublico.close();
}

/* ------------------------------------------------------------------------ */
/* Modo ruta                                                                */
/* ------------------------------------------------------------------------ */

/** Un recorrido verosímil por Chapinero, de la calle 45 a la 65 por la
 *  Caracas. Las teselas son de OpenStreetMap: hace falta conexión. */
const RECORRIDO = [
  [4.6322, -74.0676],
  [4.6385, -74.066],
  [4.6445, -74.0646],
  [4.6492, -74.0633],
  [4.6497, -74.0605],
  [4.653, -74.0596],
];
const PUNTOS_DEL_RECORRIDO = 30;

function interpolar(tramos, cuantos) {
  const puntos = [];
  for (let i = 0; i < cuantos; i++) {
    const t = (i / (cuantos - 1)) * (tramos.length - 1);
    const k = Math.min(Math.floor(t), tramos.length - 2);
    const f = t - k;
    const [a, b] = [tramos[k], tramos[k + 1]];
    puntos.push({ lat: a[0] + (b[0] - a[0]) * f, lon: a[1] + (b[1] - a[1]) * f });
  }
  return puntos;
}

async function api(metodo, ruta, { token, cuerpo } = {}) {
  const respuesta = await fetch(`${API_RASTRO}${ruta}`, {
    method: metodo,
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  });
  const datos = await respuesta.json().catch(() => null);
  if (!respuesta.ok) throw new Error(`${metodo} ${ruta}: ${respuesta.status} ${JSON.stringify(datos)}`);
  return datos;
}

/**
 * Deja una ruta abierta con su recorrido, por la API y como lo haría el
 * teléfono: el conductor con más guías en su poder sale con todas ellas y
 * reporta las posiciones del recorrido. Si ya tenía una ruta abierta (una
 * captura anterior), la cierra antes: las paradas conservan su estado y
 * vuelven a poder salir.
 */
async function prepararRuta(conductores) {
  let elegido = null;
  for (const conductor of conductores) {
    const { token } = await api("POST", "/auth/token", {
      cuerpo: { correo: conductor.correo, clave: conductor.clave },
    });
    const activa = await api("GET", "/rutas/activa", { token });
    if (activa.ruta) {
      await api("POST", `/rutas/${activa.ruta.ruta_id}/finalizacion`, { token, cuerpo: { nota: "" } });
    }
    const { estados_aptos: aptos } = activa.ruta ? await api("GET", "/rutas/activa", { token }) : activa;
    const { envios } = await api("GET", "/envios", { token });
    const enSuPoder = envios.filter((e) => aptos.includes(e.estado)).map((e) => e.envio_id);
    if (!elegido || enSuPoder.length > elegido.envios.length) elegido = { conductor, token, envios: enSuPoder };
  }
  if (!elegido?.envios.length) throw new Error("Ningún conductor de la semilla tiene guías en su poder.");

  const puntos = interpolar(RECORRIDO, PUNTOS_DEL_RECORRIDO);
  const [inicio] = puntos;
  const { ruta } = await api("POST", "/rutas", {
    token: elegido.token,
    cuerpo: {
      envios: elegido.envios,
      ubicacion: { ...inicio, precision_m: 9, capturada_en: new Date().toISOString() },
    },
  });
  // El servidor recorta al presente cualquier hora futura, y el recorrido se
  // ordena por hora: con todas iguales, el trazo saldría en zigzag. Se deja
  // pasar un segundo por lectura y se reparten entre el inicio y ahora, como
  // las enviaría un teléfono que estuvo sin señal.
  await new Promise((listo) => setTimeout(listo, PUNTOS_DEL_RECORRIDO * 1000));
  const desde = Date.parse(ruta.iniciada_en);
  const paso = (Date.now() - 1000 - desde) / (puntos.length - 1);
  await api("POST", `/rutas/${ruta.ruta_id}/posiciones`, {
    token: elegido.token,
    cuerpo: {
      posiciones: puntos.slice(1).map((p, i) => ({
        ...p,
        precision_m: 8 + (i % 5),
        capturada_en: new Date(desde + (i + 1) * paso).toISOString(),
      })),
    },
  });
  console.log(`  ruta de ${ruta.conductor_nombre} con ${elegido.envios.length} guías`);
  return { conductor: elegido.conductor, envios: elegido.envios, ultima: puntos.at(-1) };
}

async function capturarRuta(navegador, cuentas) {
  console.log("Modo ruta");
  const { conductor, envios, ultima } = await prepararRuta(cuentas.conductores);

  // La empresa: el mapa de Seguimiento con la ruta elegida y su recorrido.
  const ctx = await contexto(navegador, URL_RASTRO, CONFIGURACION_RASTRO);
  const pagina = await ctx.newPage();
  await entrarEnRastro(pagina, cuentas.administrador);
  await pagina.goto(`${URL_RASTRO}/seguimiento`);
  await asentar(pagina);
  await pagina.locator(".seguimiento__panel button.envio").first().click();
  await asentar(pagina);
  // El encuadre del mapa se anima y las teselas llegan después.
  await pagina.waitForTimeout(1500);
  await asentar(pagina);
  await guardar(pagina, "rastro-seguimiento");
  await ctx.close();

  // El conductor, con el GPS del navegador en el último punto del recorrido.
  const ctxConductor = await contexto(navegador, URL_RASTRO, CONFIGURACION_RASTRO);
  await ctxConductor.grantPermissions(["geolocation"], { origin: URL_RASTRO });
  await ctxConductor.setGeolocation({ latitude: ultima.lat, longitude: ultima.lon, accuracy: 9 });
  const movil = await ctxConductor.newPage();
  await entrarEnRastro(movil, conductor);
  await movil.goto(`${URL_RASTRO}/entregas`);
  await asentar(movil);
  await movil.waitForTimeout(1500);
  await asentar(movil);
  await guardar(movil, "rastro-modo-ruta");
  await ctxConductor.close();

  // El destinatario de la primera parada, sin cuenta.
  const ctxPublico = await contexto(navegador, URL_RASTRO, CONFIGURACION_RASTRO);
  const publico = await ctxPublico.newPage();
  await publico.goto(`${URL_RASTRO}/rastreo?envio=${envios[0]}`);
  await asentar(publico);
  const enCamino = publico.getByText("Su envío va en camino").first();
  await enCamino.waitFor({ timeout: 15000 });
  await enCamino.evaluate((nodo) => nodo.scrollIntoView({ block: "start" }));
  await publico.evaluate(() => window.scrollBy(0, -400));
  await publico.waitForTimeout(1500);
  await asentar(publico);
  await guardar(publico, "rastro-rastreo-en-camino");
  await ctxPublico.close();
}

/* ------------------------------------------------------------------------ */
/* Cotejo                                                                   */
/* ------------------------------------------------------------------------ */

async function capturarCotejo(navegador, cuentas) {
  console.log("Cotejo");
  const ctx = await contexto(navegador, URL_COTEJO, CONFIGURACION_COTEJO);
  const pagina = await ctx.newPage();

  await pagina.goto(URL_COTEJO);
  await asentar(pagina);
  await pagina.fill('input[type="email"]', cuentas.auditor.correo);
  await pagina.fill('input[type="password"]', cuentas.auditor.clave);
  await pagina.click('button[type="submit"]');
  await pagina.getByRole("heading", { name: "Revisión" }).waitFor({ timeout: 20000 });
  await asentar(pagina);

  // La ayuda «Cómo funciona» es para la primera visita; en la diapositiva
  // ocuparía el sitio de los resultados.
  const ocultar = pagina.getByRole("button", { name: "Ocultar" });
  if (await ocultar.count()) await ocultar.click();

  // Dos revisiones frescas contra la pila levantada: la pantalla de repetición
  // compara las dos últimas, y deben ser del mismo catálogo para que salga lo
  // mismo.
  for (let vez = 0; vez < 2; vez++) {
    await pagina.getByRole("button", { name: /revisar ahora/i }).click();
    await pagina.getByRole("button", { name: /revisando/i }).waitFor({ timeout: 10000 }).catch(() => undefined);
    await pagina.getByRole("button", { name: /revisar ahora/i }).waitFor({ timeout: 180000 });
    await asentar(pagina);
  }

  // Para las pantallas de revisión, hallazgos y papel conviene una ejecución
  // con un hallazgo: la primera guardada que diga «1 mal». En la pila local es
  // la que se ejecutó desde el equipo, con `git` disponible, y encontró el
  // secreto que sigue en el historial (C-09b).
  const selector = pagina.locator("select.campo__control").first();
  if (await selector.count()) {
    const opciones = await selector.locator("option").allTextContents();
    const conHallazgo = opciones.findIndex((texto) => /\b1 mal\b/.test(texto));
    if (conHallazgo >= 0) {
      await selector.selectOption({ index: conHallazgo });
      await asentar(pagina);
    }
  }

  // Encuadre: el resumen «Revisamos N cosas…» arriba y los primeros controles.
  const resumen = pagina.getByText(/Revisamos \d+ cosas/).first();
  await resumen.evaluate((nodo) => nodo.scrollIntoView({ block: "start" }));
  await pagina.evaluate(() => window.scrollBy(0, -20));
  await pagina.waitForTimeout(300);
  await guardar(pagina, "cotejo-revision");

  // El control con hallazgo, o el primero si no hay ninguno: su papel de
  // trabajo, con las dos huellas que coinciden.
  const desviado = pagina.locator("button.control.conclusion-DESVIADO").first();
  const control = (await desviado.count()) ? desviado : pagina.locator("button.control").first();
  await control.scrollIntoViewIfNeeded();
  await control.click();
  await pagina.locator(".modal__panel").waitFor({ timeout: 15000 });
  await asentar(pagina);
  await guardar(pagina, "cotejo-papel");
  await pagina.keyboard.press("Escape");

  // Los hallazgos, al final de la revisión.
  const hallazgos = pagina.getByRole("heading", { name: /lo que hay que arreglar/i }).first();
  if (await hallazgos.count()) {
    await hallazgos.evaluate((nodo) => nodo.scrollIntoView({ block: "start" }));
    await pagina.evaluate(() => window.scrollBy(0, -20));
    await pagina.waitForTimeout(300);
    await guardar(pagina, "cotejo-hallazgos");
  }

  await pagina.getByRole("button", { name: "Qué se revisa" }).click();
  await asentar(pagina);
  await pagina.evaluate(() => window.scrollTo(0, 0));
  await pagina.waitForTimeout(300);
  await guardar(pagina, "cotejo-catalogo");

  // Repetir compara por omisión las dos últimas: las dos de hoy.
  await pagina.getByRole("button", { name: "Repetir" }).click();
  await asentar(pagina);
  const comparar = pagina.getByRole("button", { name: /comparar/i }).first();
  if (await comparar.count()) {
    await comparar.click();
    await asentar(pagina);
  }
  await guardar(pagina, "cotejo-comparacion");

  await ctx.close();
}

/* ------------------------------------------------------------------------ */

/** `--solo=ruta` o `--solo=rastro,cotejo`: regenerar una parte sin tocar el
 *  resto de las capturas. Sin la opción, todas. */
const PARTES = { rastro: capturarRastro, ruta: capturarRuta, cotejo: capturarCotejo };

async function principal() {
  const solo = process.argv.find((a) => a.startsWith("--solo="))?.slice("--solo=".length).split(",");
  const desconocidas = (solo ?? []).filter((p) => !(p in PARTES));
  if (desconocidas.length) throw new Error(`Partes desconocidas: ${desconocidas.join(", ")}. Hay: ${Object.keys(PARTES).join(", ")}.`);

  const cuentas = await usuarios();
  const navegador = await chromium.launch({ channel: "msedge", headless: true });
  try {
    for (const [nombre, capturar] of Object.entries(PARTES)) {
      if (!solo || solo.includes(nombre)) await capturar(navegador, cuentas);
    }
  } finally {
    await navegador.close();
  }
  console.log("Listo.");
}

principal().catch((error) => {
  console.error(error);
  process.exit(1);
});
