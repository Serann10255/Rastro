/* Exporta los PDF de las presentaciones sin pasar por el diálogo de impresión.
 *
 * El diálogo del navegador solo respeta el tamaño y la orientación que fija la
 * hoja de estilos cuando el destino es «Guardar como PDF»; con una impresora
 * del sistema (Microsoft Print to PDF, una física) manda el papel del
 * controlador, casi siempre carta vertical, y cada diapositiva sale partida en
 * dos hojas verticales. Este guion imprime con el motor del Edge instalado y
 * `preferCSSPageSize`, que es lo que el diálogo hace con «Guardar como PDF»,
 * así que el resultado no depende de lo que haya elegido nadie.
 *
 * Uso, con el sitio servido en el puerto 5177 (el contenedor o `npm run dev`):
 *
 *   cd presentacion
 *   npm install --no-save playwright-core@1.56.1
 *   npm run pdf                      # tema claro, en documentacion/entregables/sustentacion/
 *   npm run pdf -- --tema=oscuro     # todos en oscuro, con «oscuro» en el nombre
 *   npm run pdf -- --solo=universidad   # solo ese deck
 *
 * Genera dos archivos por deck: las diapositivas a página completa de 16:9 y el guion
 * como documento de texto en vertical, una hoja por diapositiva, para cada deck. No añade dependencias al módulo: igual que
 * capturas/capturar.mjs, `playwright-core` usa el canal `msedge` del equipo.
 */

import { mkdir, readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright-core");

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..");
const DESTINO = join(RAIZ, "documentacion", "entregables", "sustentacion");
const ORIGEN = process.env.PRESENTACION_URL ?? "http://localhost:5177";

const argumentos = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [clave, valor = "si"] = a.replace(/^--/, "").split("=");
    return [clave, valor];
  }),
);
const tema = argumentos.tema === "oscuro" ? "oscuro" : "claro";
const sufijo = tema === "oscuro" ? " oscuro" : "";

const DECKS = [
  { ruta: "rastro", nombre: "Rastro · sustentación" },
  { ruta: "cotejo", nombre: "Cotejo · sustentación" },
  { ruta: "universidad", nombre: "Rastro · presentación a la universidad" },
];

/** Las dos salidas de cada deck, con el tema pedido: solo diapositivas, y el
 *  guion con una hoja por diapositiva. */
const FORMATOS = [
  { consulta: "diapositivas", archivo: (n) => `${n}${sufijo}.pdf` },
  { consulta: "", archivo: (n) => `${n}${sufijo} guion.pdf` },
];

/** `--solo=universidad` (o `rastro,cotejo`): exportar unos decks sin
 *  regenerar los PDF de los demás. Sin la opción, todos. */
const solo = argumentos.solo?.split(",");

function paginas(pdf) {
  return (pdf.toString("latin1").match(/\/Type\s*\/Page[^s]/g) ?? []).length;
}

async function principal() {
  await mkdir(DESTINO, { recursive: true });
  const navegador = await chromium.launch({ channel: "msedge", headless: true });
  try {
    const pagina = await navegador.newPage();
    for (const deck of DECKS.filter((d) => !solo || solo.includes(d.ruta))) {
      for (const formato of FORMATOS) {
        const parametros = [formato.consulta, `tema=${tema}`].filter(Boolean).join("&");
        await pagina.goto(`${ORIGEN}/${deck.ruta}/?${parametros}`, { waitUntil: "networkidle" });
        // Las capturas y la tipografía pueden llegar después del primer pintado.
        await pagina.evaluate(() => document.fonts.ready);
        await pagina.waitForTimeout(800);
        const destino = join(DESTINO, formato.archivo(deck.nombre));
        const pdf = await pagina.pdf({ path: destino, printBackground: true, preferCSSPageSize: true });
        const kb = Math.round((await readFile(destino)).byteLength / 1024);
        console.log(`  ${formato.archivo(deck.nombre)} · ${paginas(pdf)} páginas · ${kb} KB`);
      }
    }
  } finally {
    await navegador.close();
  }
  console.log(`Listo: ${DESTINO}`);
}

principal().catch((error) => {
  console.error(error);
  process.exit(1);
});
