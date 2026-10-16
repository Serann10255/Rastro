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
 *   node capturas/capturar.mjs
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
  return { administrador: porGrupo("administrador"), auditor: porGrupo("auditor") };
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

async function principal() {
  const cuentas = await usuarios();
  const navegador = await chromium.launch({ channel: "msedge", headless: true });
  try {
    await capturarRastro(navegador, cuentas);
    await capturarCotejo(navegador, cuentas);
  } finally {
    await navegador.close();
  }
  console.log("Listo.");
}

principal().catch((error) => {
  console.error(error);
  process.exit(1);
});
