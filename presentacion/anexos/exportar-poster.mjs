/* Exporta el póster de Rastro a PDF y PNG para el anexo de la entrega.
 *
 * Abre `poster.html` en el Edge del equipo, inserta el código QR del
 * repositorio y escribe en `documentacion/entregables/anexos/`:
 *
 *   poster-rastro.pdf   A1 vertical (594 × 841 mm), texto vectorial
 *   poster-rastro.png   unos 4940 × 6990 px (A1 a 211 ppp), para el formulario
 *   poster-rastro.jpg   la misma imagen, más liviana, por si el formulario limita el peso
 *
 * Uso, desde `presentacion/`:
 *
 *   npm install --no-save playwright-core@1.56.1 sharp@0.34.3 qrcode@1.5.4
 *   node anexos/exportar-poster.mjs
 *
 * Antes de exportar comprueba que nada se desborde del lienzo ni de su
 * bloque: si algo no cabe, falla y dice qué, en lugar de producir un póster
 * con texto cortado.
 */

import { mkdir, stat } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright-core");
const sharp = require("sharp");
const QRCode = require("qrcode");

const CARPETA = dirname(fileURLToPath(import.meta.url));
const RAIZ = join(CARPETA, "..", "..");
const SALIDA = join(RAIZ, "documentacion", "entregables", "anexos");
const REPOSITORIO = "https://github.com/Serann10255/Rastro";

/* A1 a 96 ppp: el lienzo del HTML. */
const LIENZO = { width: 2245, height: 3179 };
/* Densidad del PNG: 2245 × 2,2 ≈ 4940 px de ancho. */
const DENSIDAD_PNG = 2.2;

async function principal() {
  await mkdir(SALIDA, { recursive: true });
  const qr = await QRCode.toString(REPOSITORIO, {
    type: "svg",
    margin: 0,
    errorCorrectionLevel: "M",
    color: { dark: "#0f2a50", light: "#ffffff" },
  });

  const navegador = await chromium.launch({ channel: "msedge", headless: true });
  try {
    const pagina = await navegador.newPage({ viewport: LIENZO, deviceScaleFactor: DENSIDAD_PNG });
    await pagina.goto(pathToFileURL(join(CARPETA, "poster.html")).href, { waitUntil: "load" });
    await pagina.evaluate((svg) => (document.getElementById("qr").innerHTML = svg), qr);
    await pagina.evaluate(() => document.fonts.ready);

    const faltan = await pagina.evaluate(() =>
      [...document.images].filter((img) => !img.complete || img.naturalWidth === 0).map((img) => img.src),
    );
    if (faltan.length) throw new Error(`No cargaron estas imágenes:\n  ${faltan.join("\n  ")}`);

    const desbordes = await pagina.evaluate(() => {
      const avisos = [];
      const poster = document.querySelector(".poster");
      if (poster.scrollHeight > document.body.clientHeight + 1)
        avisos.push(`el contenido mide ${poster.scrollHeight} px de alto y el lienzo ${document.body.clientHeight}`);
      const pie = document.querySelector(".pie").getBoundingClientRect();
      if (pie.bottom > document.body.clientHeight + 1) avisos.push(`el pie termina en ${Math.round(pie.bottom)} px`);
      for (const bloque of document.querySelectorAll(".bloque, .cifra")) {
        const nombre = bloque.querySelector("h2")?.textContent ?? bloque.textContent.slice(0, 40);
        if (bloque.scrollWidth > bloque.clientWidth + 1 || bloque.scrollHeight > bloque.clientHeight + 1)
          avisos.push(`se desborda: ${nombre}`);
        // El cuerpo tiene alto fijo (la fila 1fr de la rejilla): si los bloques
        // no caben, la última fila no se desborda de su bloque sino que pasa
        // por debajo del pie. Hay que medirlo contra el pie.
        const fondo = bloque.getBoundingClientRect().bottom;
        if (fondo > pie.top - 8) avisos.push(`queda bajo el pie (${Math.round(fondo - pie.top + 8)} px): ${nombre}`);
      }
      return avisos;
    });
    if (desbordes.length) throw new Error(`El póster no cabe:\n  ${desbordes.join("\n  ")}`);

    const pdf = join(SALIDA, "poster-rastro.pdf");
    await pagina.pdf({
      path: pdf,
      width: `${LIENZO.width}px`,
      height: `${LIENZO.height}px`,
      printBackground: true,
      pageRanges: "1",
    });

    const png = join(SALIDA, "poster-rastro.png");
    const captura = await pagina.screenshot({ type: "png", fullPage: false });
    await sharp(captura).png({ compressionLevel: 9 }).withMetadata({ density: 211 }).toFile(png);

    const jpg = join(SALIDA, "poster-rastro.jpg");
    await sharp(captura).jpeg({ quality: 88, mozjpeg: true }).withMetadata({ density: 211 }).toFile(jpg);

    for (const archivo of [pdf, png, jpg]) {
      const { size } = await stat(archivo);
      const meta = archivo.endsWith(".pdf") ? "" : await sharp(archivo).metadata();
      const medidas = meta ? ` · ${meta.width} × ${meta.height} px` : " · A1 vertical";
      console.log(`${archivo.split(/[\\/]/).pop()}${medidas} · ${(size / 1024 / 1024).toFixed(1)} MB`);
    }
  } finally {
    await navegador.close();
  }
}

principal().catch((error) => {
  console.error(error.message ?? error);
  process.exit(1);
});
