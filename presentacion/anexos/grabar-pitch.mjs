/* Renderiza el video pitch de Rastro: 1 min 34 s para presentarlo a toda la
 * universidad, no para enseñar a usarlo (eso es el video demostrativo).
 *
 * Toma seis fragmentos de la aplicación del video demostrativo, sin su franja
 * de leyenda; compone las escenas de `pitch.html` cuadro a cuadro en el Edge
 * del equipo; sintetiza la música con `musica-pitch.mjs`, y lo monta en
 * `documentacion/entregables/anexos/video-pitch-rastro.mp4`.
 *
 * Uso, desde `presentacion/`:
 *
 *   npm install --no-save playwright-core@1.56.1 sharp@0.34.3 qrcode@1.5.4 ffmpeg-static@5.2.0
 *   node anexos/grabar-pitch.mjs                    # el video completo (unos 6 min)
 *   node anexos/grabar-pitch.mjs --sin-musica       # con audio en silencio
 *   node anexos/grabar-pitch.mjs --muestras=3,20,45 # solo esos instantes, en PNG, para revisar
 *
 * No necesita la pila levantada: parte del MP4 del video demostrativo. Las
 * ventanas de cada fragmento (`FRAGMENTOS`) son de la grabación del 2026-11-06,
 * cuyos tiempos por escena imprime `grabar-demo.mjs`; si se vuelve a grabar el
 * demostrativo, hay que revisarlas.
 */

import { execFile } from "node:child_process";
import { mkdir, readdir, rm } from "node:fs/promises";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { promisify } from "node:util";

import { DURACION, generarMusica } from "./musica-pitch.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright-core");
const QRCode = require("qrcode");
const FFMPEG = process.env.FFMPEG ?? require("ffmpeg-static");
const ejecutar = promisify(execFile);

const CARPETA = dirname(fileURLToPath(import.meta.url));
const RAIZ = join(CARPETA, "..", "..");
const ANEXOS = join(RAIZ, "documentacion", "entregables", "anexos");
const DEMO = join(ANEXOS, "video-demostrativo-rastro.mp4");
const SALIDA = join(ANEXOS, "video-pitch-rastro.mp4");
const TRABAJO = join(tmpdir(), `rastro-pitch-${Date.now()}`);
const REPOSITORIO = "https://github.com/Serann10255/Rastro";

const FPS = 30;
/* La música queda en torno a -16 LUFS integrados: presente, sin tapar una voz
 * si alguien narra encima en la sala. */
const VOLUMEN_MUSICA = "-3.5dB";

/* Recortes del video demostrativo (1920 × 1080): la aplicación de escritorio
 * sin la franja de leyenda de abajo, y el teléfono con su marco. */
const ESCRITORIO = "crop=1920:940:0:0";
const TELEFONO = "crop=486:1018:180:31";

/* Seis segundos de cada uno, dentro de su escena y lejos de los fundidos. */
const FRAGMENTOS = {
  asignar: { desde: 52.6, recorte: ESCRITORIO }, // el detalle con el UUID y la asignación
  seguimiento: { desde: 91.0, recorte: ESCRITORIO }, // la ruta elegida en el mapa
  ruta: { desde: 73.6, recorte: TELEFONO }, // «Salir a ruta» y el mapa del conductor
  consulta: { desde: 113.0, recorte: TELEFONO }, // la consulta pública con el vehículo
  entrega: { desde: 130.0, recorte: TELEFONO }, // la foto y la confirmación
  bitacora: { desde: 162.8, recorte: ESCRITORIO }, // «Verificar cadena»
};
const SEGUNDOS_FRAGMENTO = 6;

async function ffmpeg(...argumentos) {
  await ejecutar(FFMPEG, ["-hide_banner", "-loglevel", "error", "-y", ...argumentos], {
    maxBuffer: 64 * 1024 * 1024,
  });
}

async function extraerFragmentos() {
  const cuadros = {};
  for (const [nombre, { desde, recorte }] of Object.entries(FRAGMENTOS)) {
    const carpeta = join(TRABAJO, "fragmentos", nombre);
    await mkdir(carpeta, { recursive: true });
    await ffmpeg(
      "-ss", String(desde), "-t", String(SEGUNDOS_FRAGMENTO), "-i", DEMO,
      "-vf", `${recorte},fps=${FPS}`, "-q:v", "2",
      join(carpeta, "f%04d.jpg"),
    );
    cuadros[nombre] = (await readdir(carpeta)).filter((f) => f.endsWith(".jpg")).length;
  }
  return cuadros;
}

async function principal() {
  const argumentos = process.argv.slice(2);
  const muestras = argumentos.find((a) => a.startsWith("--muestras="))?.split("=")[1].split(",").map(Number);
  const sinMusica = argumentos.includes("--sin-musica");

  await mkdir(TRABAJO, { recursive: true });
  console.log("Fragmentos de la aplicación");
  const cuadros = await extraerFragmentos();
  console.log(`  ${Object.entries(cuadros).map(([n, c]) => `${n} ${c}`).join(" · ")}`);

  const qr = await QRCode.toString(REPOSITORIO, {
    type: "svg",
    margin: 0,
    errorCorrectionLevel: "M",
    color: { dark: "#0f2a50", light: "#ffffff" },
  });

  const navegador = await chromium.launch({ channel: "msedge", headless: true });
  const total = Math.round(DURACION * FPS);
  try {
    const pagina = await navegador.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    await pagina.goto(pathToFileURL(join(CARPETA, "pitch.html")).href, { waitUntil: "load" });
    await pagina.evaluate(() => document.fonts.ready);
    await pagina.evaluate(
      ({ base, cuadros, qr }) => {
        window.CLIPS.base = base;
        window.CLIPS.cuadros = cuadros;
        window.ponerQR(qr);
      },
      { base: pathToFileURL(join(TRABAJO, "fragmentos")).href, cuadros, qr },
    );
    const lienzo = pagina.locator("#lienzo");

    if (muestras) {
      for (const t of muestras) {
        await pagina.evaluate((t) => window.fotograma(t), t);
        const ruta = join(TRABAJO, `muestra-${String(t).replace(".", "_")}.png`);
        await lienzo.screenshot({ path: ruta });
        console.log(ruta);
      }
      return;
    }

    console.log(`Cuadros: ${total}`);
    const cuadrosDir = join(TRABAJO, "cuadros");
    await mkdir(cuadrosDir, { recursive: true });
    for (let i = 0; i < total; i++) {
      await pagina.evaluate((t) => window.fotograma(t), i / FPS);
      await lienzo.screenshot({
        path: join(cuadrosDir, `f${String(i + 1).padStart(5, "0")}.jpg`),
        type: "jpeg",
        quality: 93,
      });
      if ((i + 1) % 300 === 0) console.log(`  ${i + 1} / ${total}`);
    }
  } finally {
    await navegador.close();
  }

  const audio = join(TRABAJO, "musica.wav");
  if (!sinMusica) {
    const { rmsDb } = await generarMusica(audio);
    console.log(`Música: ${DURACION} s · RMS ${rmsDb.toFixed(1)} dBFS`);
  }
  await ffmpeg(
    "-framerate", String(FPS), "-i", join(TRABAJO, "cuadros", "f%05d.jpg"),
    ...(sinMusica ? ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"] : ["-i", audio]),
    "-map", "0:v", "-map", "1:a",
    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-r", String(FPS),
    ...(sinMusica ? [] : ["-af", `volume=${VOLUMEN_MUSICA}`]),
    "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
    "-t", DURACION.toFixed(2),
    "-movflags", "+faststart",
    SALIDA,
  );
  console.log(`Listo: ${SALIDA}`);
  if (!process.env.PITCH_CONSERVAR) await rm(TRABAJO, { recursive: true, force: true });
}

principal().catch((error) => {
  console.error(error);
  process.exit(1);
});
