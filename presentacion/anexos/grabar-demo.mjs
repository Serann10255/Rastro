/* Graba el video demostrativo de Rastro para el anexo de la entrega.
 *
 * Recorre la aplicación levantada en la pila local (`docker compose up -d`) con
 * el Edge instalado en el equipo, escena por escena, y monta un MP4 de
 * 1920 × 1080 con ffmpeg. No hay narración: cada escena lleva una leyenda con
 * el rol que actúa y lo que se está viendo. El guion hablado, por si se quiere
 * grabar voz encima, está en
 * `documentacion/entregables/anexos/guion-video-demostrativo.md`.
 *
 * Uso, desde `presentacion/`:
 *
 *   npm install --no-save playwright-core@1.56.1 sharp@0.34.3 ffmpeg-static@5.2.0
 *   node anexos/grabar-demo.mjs
 *
 * Igual que `capturas/capturar.mjs`: no añade dependencias al módulo, no
 * descarga navegadores (usa el canal `msedge`) e intercepta `configuracion.json`
 * para que la interfaz hable con la pila local y no con la cuenta de AWS.
 *
 * Cada ejecución crea una orden nueva con datos sintéticos, la asigna, la lleva
 * en una ruta y la entrega: el recorrido completo de un envío. No escribe nada
 * en el repositorio salvo el MP4: las capturas fijas siguen siendo cosa de
 * `capturas/capturar.mjs`.
 *
 * Cómo se graba: cada escena se captura con el «screencast» del protocolo de
 * DevTools (JPEG por cuadro, con su hora de llegada) y ffmpeg la convierte en
 * un tramo de 30 cuadros por segundo. La aplicación corre dentro de un
 * escenario servido desde su mismo origen —comparte sesión y permiso de
 * ubicación—: en escritorio ocupa la ventana con una franja de leyenda debajo,
 * para que la leyenda no tape lo que se está haciendo; en teléfono se ve a
 * 390 px de ancho dentro de un marco, con la leyenda al lado. Las esperas que no
 * aportan —entre escenas, mientras el conductor avanza— no se graban.
 */

import { execFile } from "node:child_process";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright-core");
const sharp = require("sharp");
const FFMPEG = process.env.FFMPEG ?? require("ffmpeg-static");
const ejecutar = promisify(execFile);

const CARPETA = dirname(fileURLToPath(import.meta.url));
const RAIZ = join(CARPETA, "..", "..");
const SALIDA = join(RAIZ, "documentacion", "entregables", "anexos");
const ARCHIVO_VIDEO = join(SALIDA, "video-demostrativo-rastro.mp4");
const TRABAJO = join(tmpdir(), `rastro-demo-${Date.now()}`);

const URL_RASTRO = process.env.DEMO_URL_RASTRO ?? "http://localhost:5173";
const API_RASTRO = process.env.DEMO_API_RASTRO ?? "http://localhost:8080";

/* Ventana de portátil a 1,5 de densidad: cada cuadro sale de 1920 × 1080 y el
 * texto de la interfaz se lee en el video sin ampliar. */
const VENTANA = { width: 1280, height: 720 };
const DENSIDAD = 1.5;
const FPS = 30;
const FRANJA = 92; // alto de la leyenda bajo la aplicación de escritorio
const TELEFONO = { width: 390, height: 844 };
const ESCALA_TELEFONO = 0.78;

/* Agente de usuario de un Edge corriente: el servidor de teselas de
 * OpenStreetMap no tiene por qué ver «Headless» en cada petición del mapa. */
const AGENTE =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0";

const CONFIGURACION_RASTRO = {
  _nota: "Pila local: sustituye a la configuración de AWS solo durante la grabación.",
  entorno: "local",
  region: "us-east-1",
  url_publica_api: API_RASTRO,
};

/* Datos de la orden que se crea en el video. Sintéticos, como todo el sistema. */
const ORDEN = {
  destinatario: "Valentina Ríos Acosta",
  telefono: "601 555 0142",
  destino: "Carrera 7 #45-10",
  referencia: "Apartamento 302",
  descripcion: "Caja con libros",
  peso: "2.5",
  ordenCompra: "OC-2026-2041",
};

/* Recorrido del conductor por Chapinero, de norte a sur por la carrera 13. */
const RECORRIDO = [
  { latitude: 4.6592, longitude: -74.0601 },
  { latitude: 4.6551, longitude: -74.0619 },
  { latitude: 4.6509, longitude: -74.0634 },
  { latitude: 4.6468, longitude: -74.0648 },
  { latitude: 4.6427, longitude: -74.0661 },
  { latitude: 4.6388, longitude: -74.0672 },
  { latitude: 4.6352, longitude: -74.0683 },
];

/* ------------------------------------------------------------------------ */
/* Utilidades                                                               */
/* ------------------------------------------------------------------------ */

const esperar = (ms) => new Promise((resolver) => setTimeout(resolver, ms));

async function ffmpeg(...argumentos) {
  await ejecutar(FFMPEG, ["-hide_banner", "-loglevel", "error", "-y", ...argumentos], {
    maxBuffer: 64 * 1024 * 1024,
  });
}

async function usuarios() {
  const semilla = JSON.parse(await readFile(join(RAIZ, "seed", "organizaciones.json"), "utf8"));
  const org = (id) => semilla.organizaciones.find((o) => o.org_id === id);
  const porGrupo = (id, grupo) => org(id).usuarios.find((u) => u.grupos.includes(grupo));
  return {
    despachador: porGrupo("org-andes", "despachador"),
    conductor: org("org-andes").usuarios.find((u) => u.correo.startsWith("carlos@")),
    administrador: porGrupo("org-andes", "administrador"),
    auditor: porGrupo("org-andes", "auditor"),
    otraEmpresa: porGrupo("org-sabana", "despachador"),
  };
}

/** La foto de la entrega: una ilustración sintética, no una foto de nadie. */
async function fotoDeEntrega() {
  const svg = `
  <svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900">
    <defs>
      <linearGradient id="pared" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#e9e4da"/><stop offset="1" stop-color="#d8d0c2"/>
      </linearGradient>
      <linearGradient id="caja" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#c8955a"/><stop offset="1" stop-color="#a87339"/>
      </linearGradient>
    </defs>
    <rect width="1200" height="900" fill="url(#pared)"/>
    <rect x="0" y="640" width="1200" height="260" fill="#8d8478"/>
    <rect x="760" y="120" width="300" height="520" rx="8" fill="#6b4f3a"/>
    <circle cx="1020" cy="400" r="12" fill="#d9b25f"/>
    <polygon points="330,470 640,430 820,500 510,545" fill="#d6a669"/>
    <polygon points="330,470 510,545 510,760 330,680" fill="url(#caja)"/>
    <polygon points="510,545 820,500 820,710 510,760" fill="#9a6a35"/>
    <rect x="560" y="590" width="190" height="110" rx="6" fill="#fbfbf7" transform="skewY(-8) translate(0,80)"/>
    <text x="575" y="700" font-family="Segoe UI, Arial" font-size="26" fill="#16202c" transform="skewY(-8) translate(0,80)">RASTRO</text>
    <rect x="575" y="712" width="160" height="10" fill="#16202c" transform="skewY(-8) translate(0,80)"/>
    <text x="40" y="860" font-family="Segoe UI, Arial" font-size="30" fill="#fbfbf7">Evidencia sintética · video demostrativo</text>
  </svg>`;
  const destino = join(TRABAJO, "foto-entrega.jpg");
  await sharp(Buffer.from(svg)).jpeg({ quality: 88 }).toFile(destino);
  return destino;
}

/* ------------------------------------------------------------------------ */
/* Lo que se ve además de la aplicación: puntero, toques y escenarios       */
/* ------------------------------------------------------------------------ */

/* Sin cabeza no hay puntero que grabar: se dibuja uno que sigue al ratón y un
 * círculo en cada clic. En el teléfono, solo el círculo, como un toque. */
const SCRIPT_PUNTERO = `(() => {
  if (window.__demoPuntero || location.pathname.startsWith("/__escenario")) return;
  if (window.top === window) return; // solo dentro de un escenario de grabación
  window.__demoPuntero = true;
  const enTelefono = window.innerWidth < 600;
  const iniciar = () => {
    const estilo = document.createElement("style");
    estilo.textContent = \`
      #demo-puntero{position:fixed;left:0;top:0;pointer-events:none;z-index:2147483647;transform:translate(-80px,-80px)}
      #demo-puntero svg{display:block;filter:drop-shadow(0 1px 2px rgba(0,0,0,.45))}
      .demo-toque{position:fixed;width:38px;height:38px;margin:-19px 0 0 -19px;border-radius:50%;
        background:rgba(23,162,184,.30);border:2px solid rgba(29,79,145,.85);pointer-events:none;
        z-index:2147483646;animation:demo-toque .65s ease-out forwards}
      @keyframes demo-toque{from{transform:scale(.35);opacity:1}to{transform:scale(1.5);opacity:0}}\`;
    document.head.appendChild(estilo);
    if (!enTelefono) {
      const puntero = document.createElement("div");
      puntero.id = "demo-puntero";
      puntero.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24"><path d="M4 2 L4 19 L8.6 14.8 L11.6 21.6 L14.5 20.3 L11.5 13.7 L18 13.7 Z" fill="#fff" stroke="#16202c" stroke-width="1.5" stroke-linejoin="round"/></svg>';
      document.body.appendChild(puntero);
      addEventListener("mousemove", (e) => {
        puntero.style.transform = "translate(" + (e.clientX - 4) + "px," + (e.clientY - 2) + "px)";
      }, true);
    }
    addEventListener("mousedown", (e) => {
      const toque = document.createElement("div");
      toque.className = "demo-toque";
      toque.style.left = e.clientX + "px";
      toque.style.top = e.clientY + "px";
      document.body.appendChild(toque);
      setTimeout(() => toque.remove(), 700);
    }, true);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();`;

const LOGO = (id) => `<svg viewBox="0 0 48 48" aria-hidden="true"><defs><linearGradient id="${id}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1d4f91"/><stop offset="1" stop-color="#17a2b8"/></linearGradient></defs>
  <path d="M14 5H9a4 4 0 0 0-4 4v5M34 5h5a4 4 0 0 1 4 4v5M14 43H9a4 4 0 0 1-4-4v-5M34 43h5a4 4 0 0 0 4-4v-5" fill="none" stroke="url(#${id})" stroke-width="3" stroke-linecap="round"/>
  <path d="M13 33 L24 24 L35 15" fill="none" stroke="url(#${id})" stroke-width="3" stroke-linecap="round" opacity=".35"/>
  <circle cx="13" cy="33" r="3.4" fill="none" stroke="url(#${id})" stroke-width="2.6"/><circle cx="24" cy="24" r="3.4" fill="url(#${id})" opacity=".55"/>
  <circle cx="35" cy="15" r="5.6" fill="url(#${id})"/><path d="M32.6 15.1 L34.4 16.9 L37.6 13.3" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const SCRIPT_LEYENDA = `<script>
  window.leyenda = ({ rol, titulo, texto }) => {
    document.getElementById("rol").textContent = rol;
    document.getElementById("titulo").textContent = titulo;
    document.getElementById("texto").textContent = texto;
    const panel = document.getElementById("panel");
    panel.classList.remove("animar"); void panel.offsetWidth; panel.classList.add("animar");
  };
</script>`;

/** Escritorio: la aplicación a todo lo ancho y, debajo, la franja de leyenda. */
const ESCENARIO_ESCRITORIO = `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Rastro · demostración</title>
<style>
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;overflow:hidden}
  body{font:15px/1.4 "Segoe UI",system-ui,sans-serif;background:#0f1b2d;display:grid;grid-template-rows:1fr ${FRANJA}px}
  iframe{width:100%;height:100%;border:0;display:block;background:#f4f6f9}
  .franja{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:22px;padding:0 28px;color:#fff;
    background:linear-gradient(90deg,#0f2a50,#13355f 60%,#0f2a50);border-top:3px solid #17a2b8}
  .rol{font-size:12px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:#0f1b2d;background:#7fd3e0;
    border-radius:999px;padding:3px 12px;white-space:nowrap}
  .textos{display:grid;gap:2px;min-width:0}
  h1{margin:0;font-size:19px;line-height:1.2}
  p{margin:0;font-size:14.5px;color:#d5deea}
  .marca{display:flex;align-items:center;gap:8px;font-weight:700;font-size:16px;color:#cfe4f5}
  .marca svg{width:26px;height:26px}
  .animar .textos,.animar .rol{animation:entra .4s ease-out}
  @keyframes entra{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
</style></head>
<body>
  <iframe id="app" allow="geolocation" title="Rastro"></iframe>
  <div class="franja" id="panel">
    <span class="rol" id="rol"></span>
    <div class="textos"><h1 id="titulo"></h1><p id="texto"></p></div>
    <span class="marca">${LOGO("g1").replace("<svg", '<svg width="26" height="26"')}Rastro</span>
  </div>
${SCRIPT_LEYENDA}
</body></html>`;

/** Teléfono: la aplicación a 390 px dentro de un marco, con la leyenda al lado. */
const ESCENARIO_TELEFONO = `<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Rastro · demostración</title>
<style>
  *{box-sizing:border-box}
  html,body{margin:0;height:100%;overflow:hidden}
  body{font:16px/1.45 "Segoe UI",system-ui,sans-serif;color:#16202c;
    background:radial-gradient(circle at 85% 15%,#dcebf7 0,transparent 55%),linear-gradient(160deg,#f4f6f9,#e7eef7)}
  .escena{height:100%;display:grid;grid-template-columns:auto 1fr;align-items:center;gap:56px;padding:0 64px 0 120px}
  .telefono{width:${TELEFONO.width * ESCALA_TELEFONO + 20}px;height:${TELEFONO.height * ESCALA_TELEFONO + 20}px;padding:10px;border-radius:38px;
    background:#0f1b2d;box-shadow:0 24px 50px rgba(15,27,45,.35)}
  .pantalla{width:${TELEFONO.width * ESCALA_TELEFONO}px;height:${TELEFONO.height * ESCALA_TELEFONO}px;overflow:hidden;border-radius:28px;background:#fff}
  iframe{width:${TELEFONO.width}px;height:${TELEFONO.height}px;border:0;transform:scale(${ESCALA_TELEFONO});transform-origin:0 0;display:block}
  .panel{display:grid;gap:14px;max-width:560px}
  .marca{display:flex;align-items:center;gap:10px;font-weight:700;font-size:22px;color:#1d4f91}
  .marca svg{width:34px;height:34px}
  .rol{justify-self:start;font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
    color:#0f1b2d;background:#7fd3e0;border-radius:999px;padding:3px 12px}
  h1{margin:0;font-size:34px;line-height:1.15}
  p{margin:0;font-size:19px;color:#3d4b60}
  .animar{animation:entra .4s ease-out}
  @keyframes entra{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
</style></head>
<body><div class="escena">
  <div class="telefono"><div class="pantalla"><iframe id="app" allow="geolocation" title="Rastro en un teléfono"></iframe></div></div>
  <aside class="panel" id="panel">
    <div class="marca">${LOGO("g2")}Rastro</div>
    <span class="rol" id="rol"></span>
    <h1 id="titulo"></h1>
    <p id="texto"></p>
  </aside>
</div>
${SCRIPT_LEYENDA}
</body></html>`;

/* ------------------------------------------------------------------------ */
/* Navegador                                                                */
/* ------------------------------------------------------------------------ */

async function contexto(navegador, { geolocalizacion } = {}) {
  const ctx = await navegador.newContext({
    viewport: VENTANA,
    deviceScaleFactor: DENSIDAD,
    locale: "es-CO",
    timezoneId: "America/Bogota",
    colorScheme: "light",
    userAgent: AGENTE,
    ...(geolocalizacion ? { geolocation: { ...geolocalizacion, accuracy: 9 }, permissions: ["geolocation"] } : {}),
  });
  await ctx.route(`${URL_RASTRO}/configuracion.json`, (ruta) =>
    ruta.fulfill({ json: CONFIGURACION_RASTRO, headers: { "cache-control": "no-store" } }),
  );
  await ctx.route(`${URL_RASTRO}/__escenario/escritorio`, (ruta) =>
    ruta.fulfill({ body: ESCENARIO_ESCRITORIO, contentType: "text/html; charset=utf-8" }),
  );
  await ctx.route(`${URL_RASTRO}/__escenario/telefono`, (ruta) =>
    ruta.fulfill({ body: ESCENARIO_TELEFONO, contentType: "text/html; charset=utf-8" }),
  );
  await ctx.addInitScript(SCRIPT_PUNTERO);
  return ctx;
}

/** Espera a que la vista termine de pedir datos y no queden esqueletos. */
async function asentar(superficie, respiro = 500) {
  await superficie.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => undefined);
  await superficie
    .waitForFunction(() => document.querySelectorAll(".esqueleto").length === 0, null, { timeout: 15000 })
    .catch(() => undefined);
  await esperar(respiro);
}

/** Abre un escenario y devuelve la página (lo que se graba) y el marco de la
 *  aplicación (donde se actúa). */
async function escenario(ctx, tipo, ruta) {
  const pagina = await ctx.newPage();
  await pagina.goto(`${URL_RASTRO}/__escenario/${tipo}`);
  await pagina.locator("#app").evaluate((marco, src) => (marco.src = src), ruta);
  const marco = await (await pagina.locator("#app").elementHandle()).contentFrame();
  await marco.waitForLoadState("domcontentloaded");
  await asentar(marco);
  return { pagina, marco };
}

async function leyenda(escena, datos) {
  await escena.pagina.evaluate((d) => window.leyenda(d), datos);
}

async function ir(escena, ruta) {
  await escena.marco.goto(`${URL_RASTRO}${ruta}`);
  await asentar(escena.marco);
}

/** Lleva el puntero hasta el elemento con un recorrido visible y hace clic. */
async function clic(escena, objetivo, { pausa = 450 } = {}) {
  await objetivo.waitFor({ state: "visible", timeout: 20000 });
  await objetivo.scrollIntoViewIfNeeded();
  const caja = await objetivo.boundingBox();
  if (caja) {
    await escena.pagina.mouse.move(caja.x + caja.width / 2, caja.y + caja.height / 2, { steps: 24 });
    await esperar(200);
  }
  await objetivo.click();
  await esperar(pausa);
}

async function escribir(escena, campo, texto, retraso = 40) {
  await clic(escena, campo, { pausa: 120 });
  await campo.pressSequentially(texto, { delay: retraso });
  await esperar(250);
}

/** Desplaza la vista poco a poco, como lo haría una persona. */
async function desplazar(superficie, distancia, pasos = 6, pausa = 140) {
  for (let i = 0; i < pasos; i++) {
    await superficie.evaluate((d) => window.scrollBy({ top: d, behavior: "smooth" }), distancia / pasos);
    await esperar(pausa);
  }
  await esperar(400);
}

async function entrar(superficie, usuario) {
  await superficie.locator('input[name="correo"]').waitFor({ timeout: 20000 });
  await superficie.fill('input[name="correo"]', usuario.correo);
  await superficie.fill('input[name="clave"]', usuario.clave);
  await superficie.click('button[type="submit"]');
  await superficie.waitForURL((url) => !url.pathname.startsWith("/acceso"), { timeout: 20000 });
  await asentar(superficie);
}

/** Escenario de escritorio con la sesión ya iniciada, abierto en `ruta`. */
async function sesionDeEscritorio(navegador, usuario, ruta) {
  const ctx = await contexto(navegador);
  const escena = await escenario(ctx, "escritorio", "/acceso");
  await entrar(escena.marco, usuario);
  await ir(escena, ruta);
  return { ctx, escena };
}

/** Cierra la ruta del conductor si tiene una abierta. Se llama antes de
 *  grabar —una ejecución anterior pudo quedar a medias— y al terminar, para
 *  no dejar su ubicación compartida. */
async function terminarRuta(marco) {
  await marco.goto(`${URL_RASTRO}/entregas`);
  await asentar(marco, 600);
  const enCurso = marco.getByRole("heading", { name: "Ruta en curso" });
  if (!(await enCurso.count())) return;
  await marco.getByRole("button", { name: "Terminar ruta" }).first().click();
  const confirmar = marco.getByRole("dialog").getByRole("button", { name: "Terminar ruta" });
  if (await confirmar.count()) await confirmar.click();
  await enCurso.waitFor({ state: "detached", timeout: 15000 }).catch(() => undefined);
  await asentar(marco, 400);
}

/* ------------------------------------------------------------------------ */
/* Grabación                                                                */
/* ------------------------------------------------------------------------ */

const tramos = [];
const CODIFICACION = ["-c:v", "libx264", "-preset", "slow", "-crf", "19", "-r", String(FPS), "-pix_fmt", "yuv420p"];

/** Graba lo que ocurre en la página de la escena mientras corre `accion` y lo
 *  deja como un tramo MP4 listo para unir. */
async function grabar(nombre, escena, accion) {
  const carpeta = join(TRABAJO, nombre);
  await mkdir(carpeta, { recursive: true });
  const cdp = await escena.pagina.context().newCDPSession(escena.pagina);
  const cuadros = [];
  const escrituras = [];
  cdp.on("Page.screencastFrame", ({ data, sessionId }) => {
    const archivo = join(carpeta, `c${String(cuadros.length).padStart(6, "0")}.jpg`);
    cuadros.push({ archivo, t: Date.now() / 1000 });
    escrituras.push(writeFile(archivo, Buffer.from(data, "base64")));
    cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => undefined);
  });
  await cdp.send("Page.startScreencast", {
    format: "jpeg",
    quality: 92,
    maxWidth: 1920,
    maxHeight: 1080,
    everyNthFrame: 1,
  });
  await esperar(600);
  await accion();
  await esperar(900);
  const fin = Date.now() / 1000;
  await cdp.send("Page.stopScreencast");
  await esperar(150);
  await Promise.all(escrituras);
  await cdp.detach();

  if (cuadros.length === 0) throw new Error(`La escena ${nombre} no produjo cuadros.`);
  const lineas = [];
  cuadros.forEach((cuadro, i) => {
    const siguiente = i + 1 < cuadros.length ? cuadros[i + 1].t : fin;
    lineas.push(`file '${cuadro.archivo.replaceAll("\\", "/")}'`);
    lineas.push(`duration ${Math.max(siguiente - cuadro.t, 1 / FPS).toFixed(4)}`);
  });
  lineas.push(`file '${cuadros.at(-1).archivo.replaceAll("\\", "/")}'`);
  const lista = join(carpeta, "lista.txt");
  await writeFile(lista, lineas.join("\n"));

  const duracion = fin - cuadros[0].t;
  const tramo = join(TRABAJO, `${String(tramos.length).padStart(2, "0")}-${nombre}.mp4`);
  await ffmpeg(
    "-f", "concat", "-safe", "0", "-i", lista,
    "-vf",
    [
      "scale=1920:1080:force_original_aspect_ratio=decrease",
      "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0xf4f6f9",
      `fps=${FPS}`,
      "format=yuv420p",
      "fade=t=in:st=0:d=0.35",
      `fade=t=out:st=${Math.max(duracion - 0.4, 0).toFixed(2)}:d=0.4`,
    ].join(","),
    "-t", duracion.toFixed(2),
    ...CODIFICACION,
    tramo,
  );
  tramos.push({ nombre, archivo: tramo, duracion });
  console.log(`  ${nombre} · ${duracion.toFixed(1)} s · ${cuadros.length} cuadros`);
}

/** Portada y cierre: una lámina fija renderizada a 1920 × 1080. */
async function lamina(navegador, nombre, html, segundos) {
  const pagina = await navegador.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await pagina.setContent(html, { waitUntil: "load" });
  await esperar(300);
  const png = join(TRABAJO, `${nombre}.png`);
  await pagina.screenshot({ path: png });
  await pagina.close();
  const tramo = join(TRABAJO, `${String(tramos.length).padStart(2, "0")}-${nombre}.mp4`);
  await ffmpeg(
    "-loop", "1", "-t", String(segundos), "-i", png,
    "-vf", `fps=${FPS},format=yuv420p,fade=t=in:st=0:d=0.5,fade=t=out:st=${segundos - 0.6}:d=0.6`,
    ...CODIFICACION,
    tramo,
  );
  tramos.push({ nombre, archivo: tramo, duracion: segundos });
  console.log(`  ${nombre} · ${segundos} s`);
}

function htmlLamina(cuerpo) {
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
    *{box-sizing:border-box}
    body{margin:0;width:1920px;height:1080px;font-family:"Segoe UI",system-ui,sans-serif;color:#fff;
      background:radial-gradient(circle at 80% 20%,rgba(23,162,184,.35),transparent 55%),linear-gradient(135deg,#0f2a50,#1d4f91 60%,#17708a);
      display:grid;place-items:center}
    .lamina{width:1600px;display:grid;gap:30px}
    .marca{display:flex;align-items:center;gap:28px}
    h1{margin:0;font-size:150px;letter-spacing:.02em;line-height:1}
    .lema{font-size:50px;color:#d7e9f7;margin:0;line-height:1.15}
    .linea{height:5px;width:200px;background:#7fd3e0;border-radius:4px}
    .datos{font-size:33px;color:#e4eef8;line-height:1.5;margin:0}
    .nota{font-size:27px;color:#a9c3dc;margin:0}
    ul{margin:0;padding:0;list-style:none;display:grid;gap:22px}
    li{font-size:38px;display:grid;grid-template-columns:190px 1fr;gap:28px;align-items:baseline;line-height:1.25}
    li b{color:#7fd3e0;text-align:right;font-size:50px}
    h2{margin:0;font-size:72px}
  </style></head><body><div class="lamina">${cuerpo}</div></body></html>`;
}

const LOGO_BLANCO = `<svg viewBox="0 0 48 48" width="170" height="170" aria-hidden="true">
  <path d="M14 5H9a4 4 0 0 0-4 4v5M34 5h5a4 4 0 0 1 4 4v5M14 43H9a4 4 0 0 1-4-4v-5M34 43h5a4 4 0 0 0 4-4v-5" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"/>
  <path d="M13 33 L24 24 L35 15" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".4"/>
  <circle cx="13" cy="33" r="3.4" fill="none" stroke="#fff" stroke-width="2.6"/><circle cx="24" cy="24" r="3.4" fill="#fff" opacity=".6"/>
  <circle cx="35" cy="15" r="5.6" fill="#7fd3e0"/><path d="M32.6 15.1 L34.4 16.9 L37.6 13.3" fill="none" stroke="#0f2a50" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

const PORTADA = htmlLamina(`
  <div class="marca">${LOGO_BLANCO}<h1>RASTRO</h1></div>
  <p class="lema">Trazabilidad verificable de envíos sobre servicios gestionados en la nube</p>
  <div class="linea"></div>
  <p class="datos">Video demostrativo · Cloud Computing (ISD38) · Grupo 30112 · Periodo 2026B<br>
  Sergio Alejandro Montoya Granados · Nicolás Torres Perdomo · Óscar Julián Rincón Bejarano<br>
  Corporación Unificada Nacional de Educación Superior — CUN · Ingeniería de Sistemas</p>
  <p class="nota">Grabado sobre la pila local con datos sintéticos. El mismo código corre desplegado en AWS.</p>`);

const CIERRE = htmlLamina(`
  <h2>Lo que se comprobó</h2>
  <ul>
    <li><b>9 / 9</b><span>requisitos comprometidos, cada uno con su prueba automatizada</span></li>
    <li><b>327</b><span>pruebas superadas, 5 omitidas y ningún fallo (6/11/2026)</span></li>
    <li><b>AWS</b><span>8 funciones Lambda, API Gateway, 3 tablas DynamoDB, S3 + KMS y CloudTrail: despliegue verificado</span></li>
    <li><b>10 / 11</b><span>controles conformes en una auditoría independiente; el desviado, declarado y corregido</span></li>
  </ul>
  <div class="linea"></div>
  <p class="datos">github.com/Serann10255/Rastro<br>
  Sergio Montoya · Nicolás Torres · Óscar Rincón — Grupo 30112 · CUN</p>`);

/* ------------------------------------------------------------------------ */
/* El recorrido                                                             */
/* ------------------------------------------------------------------------ */

async function principal() {
  await mkdir(TRABAJO, { recursive: true });
  await mkdir(SALIDA, { recursive: true });
  const cuentas = await usuarios();
  const foto = await fotoDeEntrega();
  const navegador = await chromium.launch({ channel: "msedge", headless: true });
  const contextos = [];

  try {
    console.log("Escenas");
    await lamina(navegador, "portada", PORTADA, 7);

    /* 1 · Despachador: acceso y panel ------------------------------------ */
    const ctxDespacho = await contexto(navegador);
    contextos.push(ctxDespacho);
    const despacho = await escenario(ctxDespacho, "escritorio", "/acceso");
    const d = despacho.marco;
    await leyenda(despacho, {
      rol: "Despachador",
      titulo: "Entra con su cuenta",
      texto: "Cada operación queda registrada con su identidad y su marca de tiempo.",
    });
    await grabar("acceso-y-panel", despacho, async () => {
      await esperar(1500);
      await escribir(despacho, d.locator('input[name="correo"]'), cuentas.despachador.correo, 35);
      await escribir(despacho, d.locator('input[name="clave"]'), cuentas.despachador.clave, 35);
      await clic(despacho, d.locator('button[type="submit"]'));
      await d.waitForURL((url) => !url.pathname.startsWith("/acceso"), { timeout: 20000 });
      await asentar(d, 300);
      await leyenda(despacho, {
        rol: "Despachador",
        titulo: "Panel de la empresa",
        texto: "Envíos en curso, entregados, con incidencia y sin asignar; los que llevan días sin movimiento y los nueve estados.",
      });
      await esperar(3500);
      await desplazar(d, 520, 8, 160);
      await esperar(2500);
      await desplazar(d, -520, 4, 120);
    });

    /* 2 · Despachador: nueva orden --------------------------------------- */
    let envioId;
    await grabar("nueva-orden", despacho, async () => {
      await leyenda(despacho, {
        rol: "Despachador",
        titulo: "Registra una orden",
        texto: "Al guardarla, el sistema le asigna un identificador aleatorio (UUID): es la guía que recibe el destinatario.",
      });
      const nueva = d.getByRole("link", { name: /nueva orden/i }).first();
      if (await nueva.count()) await clic(despacho, nueva);
      else await ir(despacho, "/envios/nuevo");
      await d.waitForURL(/\/envios\/nuevo/);
      await asentar(d, 600);
      const tienda = d.getByLabel("Tienda de origen");
      await clic(despacho, tienda, { pausa: 200 });
      await tienda.selectOption({ index: 1 });
      await esperar(700);
      await escribir(despacho, d.getByLabel("Dirección de entrega"), ORDEN.destino);
      await escribir(despacho, d.getByLabel("Referencia de entrega"), ORDEN.referencia);
      await escribir(despacho, d.getByLabel("Peso (kg)"), ORDEN.peso);
      await escribir(despacho, d.getByLabel("Nombre del destinatario"), ORDEN.destinatario);
      await escribir(despacho, d.getByLabel("Teléfono"), ORDEN.telefono);
      const cliente = d.getByLabel("Cliente", { exact: true });
      await clic(despacho, cliente, { pausa: 200 });
      await cliente.selectOption({ index: 1 });
      await escribir(despacho, d.getByLabel("Orden de compra"), ORDEN.ordenCompra);
      await escribir(despacho, d.getByLabel("Descripción del contenido"), ORDEN.descripcion);
      await esperar(500);
      await clic(despacho, d.getByRole("button", { name: "Registrar envío" }));
      await d.waitForURL(/\/envios\/[0-9a-f-]{36}$/, { timeout: 20000 });
      await asentar(d, 300);
      envioId = new URL(d.url()).pathname.split("/").pop();
      await d.evaluate(() => window.scrollTo({ top: 0 }));
      await esperar(3500);
    });
    console.log(`  orden creada: ${envioId}`);

    /* 3 · Despachador: asignar mensajero ---------------------------------- */
    await leyenda(despacho, {
      rol: "Despachador",
      titulo: "Asigna el mensajero",
      texto: "La máquina de estados valida CREADO → ASIGNADO. Una transición no permitida se rechaza y queda en la bitácora.",
    });
    await grabar("asignar", despacho, async () => {
      await esperar(1200);
      await clic(despacho, d.getByRole("button", { name: cuentas.conductor.nombre }).first());
      await clic(despacho, d.getByRole("button", { name: "Asignar", exact: true }));
      await d.getByText("Mensajero asignado").first().waitFor({ timeout: 15000 }).catch(() => undefined);
      await asentar(d, 300);
      const historico = d.getByRole("heading", { name: "Histórico" }).first();
      if (await historico.count()) await historico.scrollIntoViewIfNeeded();
      await esperar(3500);
    });

    /* 4 · Conductor: recoge y sale a ruta (teléfono) ---------------------- */
    const ctxConductor = await contexto(navegador, { geolocalizacion: RECORRIDO[0] });
    contextos.push(ctxConductor);
    const conductor = await escenario(ctxConductor, "telefono", "/acceso");
    const c = conductor.marco;
    await entrar(c, cuentas.conductor);
    await terminarRuta(c);
    await leyenda(conductor, {
      rol: "Conductor · en el teléfono",
      titulo: "Recoge la guía y sale a ruta",
      texto: "Marca la guía como recogida, elige las paradas y sale. Desde ese momento comparte su ubicación, y solo mientras la ruta esté abierta.",
    });
    await grabar("salir-a-ruta", conductor, async () => {
      await esperar(2500);
      const fila = c.locator("li", { hasText: ORDEN.destinatario });
      await clic(conductor, fila.getByRole("button", { name: "Recogido" }).first(), { pausa: 300 });
      await c.locator("label.envio--seleccionable", { hasText: ORDEN.destinatario }).waitFor({ timeout: 15000 });
      await asentar(c, 600);
      // La nueva y, si las tiene, dos guías más que ya llevaba: una ruta de verdad.
      const casillas = c.locator("label.envio--seleccionable");
      await clic(conductor, casillas.filter({ hasText: ORDEN.destinatario }).first(), { pausa: 300 });
      const otras = casillas.filter({ hasNotText: ORDEN.destinatario });
      const cuantas = Math.min(await otras.count(), 2);
      for (let i = 0; i < cuantas; i++) await clic(conductor, otras.nth(i), { pausa: 250 });
      await esperar(600);
      await clic(conductor, c.getByRole("button", { name: "Salir a ruta" }));
      await c.getByRole("heading", { name: "Ruta en curso" }).waitFor({ timeout: 20000 });
      await c.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
      await c.getByText("Compartiendo su ubicación").waitFor({ timeout: 20000 }).catch(() => undefined);
      await asentar(c, 300);
      await esperar(5500);
      await desplazar(c, 620, 8, 180);
      await esperar(2500);
    });

    // Fuera de cámara: el conductor avanza para que haya recorrido que ver.
    for (const punto of RECORRIDO.slice(1, 5)) {
      await ctxConductor.setGeolocation({ ...punto, accuracy: 9 });
      await esperar(6500);
    }

    /* 5 · Despachador: seguimiento en vivo -------------------------------- */
    await ir(despacho, "/seguimiento");
    await leyenda(despacho, {
      rol: "Despachador",
      titulo: "Seguimiento en vivo",
      texto: "Cada conductor en ruta en el mapa, con su recorrido y sus paradas. Se actualiza solo cada diez segundos.",
    });
    await grabar("seguimiento", despacho, async () => {
      await esperar(2500);
      const ruta = d.locator("button.envio", { hasText: cuentas.conductor.nombre }).first();
      if (await ruta.count()) {
        await clic(despacho, ruta);
        await asentar(d, 300);
      }
      await ctxConductor.setGeolocation({ ...RECORRIDO[5], accuracy: 9 });
      await esperar(7000);
      await ctxConductor.setGeolocation({ ...RECORRIDO[6], accuracy: 9 });
      await esperar(7000);
    });

    /* 6 · Destinatario: consulta pública mientras va en camino ------------ */
    const ctxPublico = await contexto(navegador);
    contextos.push(ctxPublico);
    const publico = await escenario(ctxPublico, "telefono", "/rastreo");
    const p = publico.marco;
    await leyenda(publico, {
      rol: "Destinatario · sin cuenta",
      titulo: "Consulta su envío",
      texto: "Con el identificador ve el avance y, mientras va en reparto, dónde está el vehículo. El nombre aparece enmascarado.",
    });
    await grabar("consulta-en-camino", publico, async () => {
      await esperar(1500);
      await escribir(publico, p.locator("#identificador"), envioId, 12);
      await clic(publico, p.getByRole("button", { name: "Consultar" }));
      await p.getByText("Su envío va en camino").waitFor({ timeout: 20000 }).catch(() => undefined);
      await asentar(p, 300);
      await esperar(3000);
      await desplazar(p, 480, 6, 180);
      await esperar(3500);
    });

    /* 7 · Conductor: entrega con evidencia -------------------------------- */
    await leyenda(conductor, {
      rol: "Conductor · en el teléfono",
      titulo: "Entrega con evidencia",
      texto: "La foto sube por un enlace prefirmado que vence en cinco minutos (en AWS, cifrada con llave propia). Sin evidencia, el servidor no acepta ENTREGADO.",
    });
    await grabar("entrega", conductor, async () => {
      await esperar(1800);
      const parada = c.locator("article.parada", { hasText: ORDEN.destinatario }).first();
      await clic(conductor, parada.getByRole("button", { name: "Entregar" }));
      await c.getByLabel("Foto de la entrega").waitFor({ state: "attached", timeout: 15000 });
      await esperar(800);
      await c.getByLabel("Foto de la entrega").setInputFiles(foto);
      await esperar(1500);
      await escribir(conductor, c.getByLabel("Nota"), "Recibió en portería", 45);
      await clic(conductor, c.getByRole("button", { name: "Confirmar entrega" }), { pausa: 200 });
      await c.getByText(/Entregado a/).first().waitFor({ timeout: 25000 });
      await esperar(3500);
    });

    /* 8 · Destinatario: entregado ----------------------------------------- */
    await leyenda(publico, {
      rol: "Destinatario · sin cuenta",
      titulo: "Entregado",
      texto: "La consulta muestra la entrega con su fecha y hora, y el vehículo deja de mostrarse.",
    });
    await grabar("consulta-entregado", publico, async () => {
      await p.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
      await esperar(900);
      await clic(publico, p.getByRole("button", { name: "Consultar" }));
      await p.getByText(/entregado/i).first().waitFor({ timeout: 20000 });
      await asentar(p, 300);
      await esperar(1500);
      await desplazar(p, 420, 6, 180);
      await esperar(3000);
    });

    /* 9 · Otra empresa: aislamiento --------------------------------------- */
    const sabana = await sesionDeEscritorio(navegador, cuentas.otraEmpresa, "/envios");
    contextos.push(sabana.ctx);
    await leyenda(sabana.escena, {
      rol: "Despachador de otra empresa",
      titulo: "Aislamiento entre empresas",
      texto: "Envíos Sabana pide la guía de Mensajería Andes: el sistema responde como si no existiera (404, no 403) y el intento queda registrado.",
    });
    await grabar("aislamiento", sabana.escena, async () => {
      await esperar(2500);
      await ir(sabana.escena, `/envios/${envioId}`);
      await esperar(5500);
    });

    /* 10 · Auditor: bitácora encadenada ------------------------------------ */
    const auditor = await sesionDeEscritorio(navegador, cuentas.auditor, "/bitacora");
    contextos.push(auditor.ctx);
    const a = auditor.escena.marco;
    await leyenda(auditor.escena, {
      rol: "Auditor",
      titulo: "Bitácora encadenada por hash",
      texto: "Cada operación, permitida o rechazada, con actor, recurso y momento. Verificar recalcula la cadena completa; el auditor no puede escribir nada.",
    });
    await grabar("bitacora", auditor.escena, async () => {
      await esperar(2500);
      await clic(auditor.escena, a.getByRole("button", { name: /verificar cadena/i }).first());
      await a.getByText(/la cadena verifica/i).first().waitFor({ timeout: 30000 }).catch(() => undefined);
      await esperar(3500);
      await desplazar(a, 560, 8, 160);
      await esperar(3500);
    });

    /* 11 · Administrador: roles y permisos -------------------------------- */
    const admin = await sesionDeEscritorio(navegador, cuentas.administrador, "/administracion/roles");
    contextos.push(admin.ctx);
    await leyenda(admin.escena, {
      rol: "Administrador",
      titulo: "Roles y permisos",
      texto: "Cinco roles de fábrica y los que cree la empresa. Ningún rol combina escritura con lectura de la bitácora.",
    });
    await grabar("roles", admin.escena, async () => {
      await esperar(3000);
      await desplazar(admin.escena.marco, 480, 8, 170);
      await esperar(3500);
    });

    await lamina(navegador, "cierre", CIERRE, 9);

    // El conductor termina su ruta para no dejar ubicación compartida.
    await terminarRuta(c);
  } finally {
    await Promise.all(contextos.map((ctx) => ctx.close().catch(() => undefined)));
    await navegador.close();
  }

  /* Montaje: los tramos tienen la misma codificación y se unen sin recodificar;
   * se añade una pista de audio en silencio porque algunos reproductores y
   * plataformas tratan mal un MP4 sin audio. */
  const lista = join(TRABAJO, "tramos.txt");
  await writeFile(lista, tramos.map((t) => `file '${t.archivo.replaceAll("\\", "/")}'`).join("\n"));
  await ffmpeg(
    "-f", "concat", "-safe", "0", "-i", lista,
    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
    "-map", "0:v", "-map", "1:a", "-shortest",
    "-c:v", "copy", "-c:a", "aac", "-b:a", "96k",
    "-movflags", "+faststart",
    ARCHIVO_VIDEO,
  );
  const total = tramos.reduce((suma, t) => suma + t.duracion, 0);
  const mb = (await readFile(ARCHIVO_VIDEO)).byteLength / 1024 / 1024;
  console.log(`Listo: ${ARCHIVO_VIDEO}`);
  console.log(`  ${Math.floor(total / 60)} min ${Math.round(total % 60)} s · ${mb.toFixed(1)} MB`);
  if (!process.env.DEMO_CONSERVAR) await rm(TRABAJO, { recursive: true, force: true });
}

principal().catch((error) => {
  console.error(error);
  process.exit(1);
});
