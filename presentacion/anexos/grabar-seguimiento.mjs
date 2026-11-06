/* Graba un plano limpio del seguimiento en vivo para el video pitch.
 *
 * En el video demostrativo el conductor avanza a saltos de unos 450 m para que
 * el recorrido se dibuje rápido, y la escena de Seguimiento muestra además el
 * reencuadre del mapa al elegir la ruta. Recortado en el pitch, eso se veía
 * como un mapa que «se desubica de un momento a otro». Este plano lo evita:
 *
 * - el conductor circula a velocidad de ciudad (10 m/s, 36 km/h), con una
 *   lectura de GPS por segundo, así que la aplicación envía su posición como lo
 *   haría un teléfono de verdad;
 * - la ruta se elige y el mapa se aleja un nivel antes de grabar: en el plano no
 *   hay reencuadre y el vehículo avanza dentro de la vista;
 * - se graba la pantalla de Seguimiento tal cual, sin escenario ni leyenda, a
 *   1920 × 940 como los demás fragmentos de escritorio del pitch.
 *
 * El marcador sigue moviéndose a pasos, cada vez que la pantalla consulta (cada
 * diez segundos): es como funciona la aplicación y no se disimula.
 *
 * Uso, desde `presentacion/`, con la pila local levantada:
 *
 *   node anexos/grabar-seguimiento.mjs
 *
 * Escribe `anexos/fragmentos/seguimiento-en-vivo.mp4`, que `grabar-pitch.mjs`
 * usa en lugar del tramo del video demostrativo. Al terminar cierra la ruta.
 */

import { mkdir, rm, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { asentar, contexto, entrar, esperar, ffmpeg, terminarRuta, usuarios, FPS, URL_RASTRO } from "./grabar-demo.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright-core");

const CARPETA = dirname(fileURLToPath(import.meta.url));
const SALIDA = join(CARPETA, "fragmentos", "seguimiento-en-vivo.mp4");
const TRABAJO = join(tmpdir(), `rastro-seguimiento-${Date.now()}`);

/* 1280 × 627 a 1,5 de densidad = 1920 × 940, el recorte de escritorio del pitch. */
const VISTA = { width: 1280, height: 627 };
const VELOCIDAD_MS = 10; // metros por segundo
const PREVIO_S = 70; // recorrido antes de grabar, para que haya trazo
const GRABACION_S = 34;

/* Por la carrera 13, de la calle 72 hacia el sur. */
const INICIO = { latitude: 4.6592, longitude: -74.0601 };
const FIN = { latitude: 4.6352, longitude: -74.0683 };
const M_POR_GRADO = 111_320;
const LARGO_M = Math.hypot(
  (FIN.latitude - INICIO.latitude) * M_POR_GRADO,
  (FIN.longitude - INICIO.longitude) * M_POR_GRADO * Math.cos((INICIO.latitude * Math.PI) / 180),
);

const puntoA = (metros) => {
  const p = Math.min(1, metros / LARGO_M);
  return {
    latitude: INICIO.latitude + (FIN.latitude - INICIO.latitude) * p,
    longitude: INICIO.longitude + (FIN.longitude - INICIO.longitude) * p,
    accuracy: 8,
  };
};

async function principal() {
  await mkdir(TRABAJO, { recursive: true });
  await mkdir(dirname(SALIDA), { recursive: true });
  const cuentas = await usuarios();
  const navegador = await chromium.launch({ channel: "msedge", headless: true });

  let recorridoM = 0;
  let conduciendo = true;
  let ctxConductor;
  let conductor;
  try {
    /* El conductor sale a ruta con las guías que tiene en su poder. */
    ctxConductor = await contexto(navegador, { geolocalizacion: puntoA(0) });
    conductor = await ctxConductor.newPage();
    await conductor.goto(`${URL_RASTRO}/acceso`);
    await entrar(conductor, cuentas.conductor);
    await terminarRuta(conductor);
    const marcar = conductor.getByRole("button", { name: "Marcar todas" });
    if (!(await marcar.count())) throw new Error("El conductor no tiene guías en su poder para salir a ruta.");
    await marcar.click();
    await conductor.getByRole("button", { name: "Salir a ruta" }).click();
    await conductor.getByRole("heading", { name: "Ruta en curso" }).waitFor({ timeout: 20000 });
    console.log("Ruta abierta");

    /* Una lectura de GPS por segundo, como un teléfono en el vehículo. */
    const conducir = (async () => {
      while (conduciendo) {
        await esperar(1000);
        recorridoM += VELOCIDAD_MS;
        await ctxConductor.setGeolocation(puntoA(recorridoM)).catch(() => undefined);
      }
    })();

    await esperar(PREVIO_S * 1000);
    console.log(`Recorrido previo: ${recorridoM} m`);

    /* La empresa: la ruta elegida y el mapa un nivel más lejos, fuera de cámara. */
    const ctxDespacho = await contexto(navegador, { viewport: VISTA });
    const despacho = await ctxDespacho.newPage();
    await despacho.goto(`${URL_RASTRO}/acceso`);
    await entrar(despacho, cuentas.despachador);
    await despacho.goto(`${URL_RASTRO}/seguimiento`);
    await asentar(despacho, 800);
    await despacho.locator("button.envio", { hasText: cuentas.conductor.nombre }).first().click();
    await asentar(despacho, 1500);
    await despacho.locator(".leaflet-control-zoom-out").first().click();
    await esperar(1500);
    await despacho.mouse.move(5, 5);

    /* El plano. */
    const carpeta = join(TRABAJO, "cuadros");
    await mkdir(carpeta, { recursive: true });
    const cdp = await ctxDespacho.newCDPSession(despacho);
    const cuadros = [];
    const escrituras = [];
    cdp.on("Page.screencastFrame", ({ data, sessionId }) => {
      const archivo = join(carpeta, `c${String(cuadros.length).padStart(6, "0")}.jpg`);
      cuadros.push({ archivo, t: Date.now() / 1000 });
      escrituras.push(writeFile(archivo, Buffer.from(data, "base64")));
      cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => undefined);
    });
    await cdp.send("Page.startScreencast", { format: "jpeg", quality: 92, maxWidth: 1920, maxHeight: 940, everyNthFrame: 1 });
    await esperar(GRABACION_S * 1000);
    const fin = Date.now() / 1000;
    await cdp.send("Page.stopScreencast");
    await Promise.all(escrituras);
    console.log(`Grabado: ${GRABACION_S} s · ${cuadros.length} cuadros · conductor a ${recorridoM} m`);

    const lineas = [];
    cuadros.forEach((c, i) => {
      const siguiente = i + 1 < cuadros.length ? cuadros[i + 1].t : fin;
      lineas.push(`file '${c.archivo.replaceAll("\\", "/")}'`, `duration ${Math.max(siguiente - c.t, 1 / FPS).toFixed(4)}`);
    });
    lineas.push(`file '${cuadros.at(-1).archivo.replaceAll("\\", "/")}'`);
    const lista = join(TRABAJO, "lista.txt");
    await writeFile(lista, lineas.join("\n"));
    await ffmpeg(
      "-f", "concat", "-safe", "0", "-i", lista,
      "-vf", `scale=1920:940,fps=${FPS},format=yuv420p`,
      "-t", (fin - cuadros[0].t).toFixed(2),
      "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-an", "-movflags", "+faststart",
      SALIDA,
    );
    console.log(`Listo: ${SALIDA}`);
    await ctxDespacho.close();

    conduciendo = false;
    await conducir;
  } finally {
    conduciendo = false;
    if (conductor) await terminarRuta(conductor).catch(() => undefined);
    await navegador.close();
    await rm(TRABAJO, { recursive: true, force: true });
  }
}

principal().catch((error) => {
  console.error(error);
  process.exit(1);
});
