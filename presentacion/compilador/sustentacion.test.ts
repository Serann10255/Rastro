/* Pruebas del compilador de guiones.
 *
 *   npm test
 *
 * Usan el ejecutor de pruebas de Node, sin dependencias: se comprueba lo que el
 * deck promete —que las notas no se cuelen como contenido, que la numeración
 * sea la del enlace directo, que una figura inexistente detenga la
 * construcción— y que los dos guiones reales compilan sin avisos.
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { describe, it } from "node:test";

import type { Bloque, DiapositivaContenido } from "../src/deck/tipos.ts";
import { comoCifras, enLinea } from "./markdown.ts";
import { compilarSustentacion, ErrorDeLectura } from "./sustentacion.ts";

const FIGURAS = new Set(
  readdirSync(new URL("../src/figuras/", import.meta.url))
    .filter((f) => f.endsWith(".tsx"))
    .map((f) => f.replace(/\.tsx$/, "")),
);

function compilar(cuerpo: string) {
  const fuente = `# Guion de prueba\n\n\`\`\`yaml\nproyecto: Prueba\nequipo: [Ana, Luis]\n\`\`\`\n\n---\n\n${cuerpo}`;
  return compilarSustentacion(fuente, { archivo: "prueba.md", figuras: FIGURAS });
}

function contenido(cuerpo: string): DiapositivaContenido[] {
  return compilar(cuerpo).deck.diapositivas.filter((d): d is DiapositivaContenido => d.tipo === "contenido");
}

describe("formato en línea", () => {
  it("reconoce negrita, cursiva y código sin mezclarlos", () => {
    assert.deepEqual(enLinea("**Rastro** es *verificable* con `ORG#…#ENV#…`"), [
      { t: "fuerte", hijos: [{ t: "texto", v: "Rastro" }] },
      { t: "texto", v: " es " },
      { t: "enfasis", hijos: [{ t: "texto", v: "verificable" }] },
      { t: "texto", v: " con " },
      { t: "codigo", v: "ORG#…#ENV#…" },
    ]);
  });

  it("deja un asterisco suelto como texto", () => {
    assert.deepEqual(enLinea("a * b"), [{ t: "texto", v: "a * b" }]);
  });
});

describe("cifras de resultado", () => {
  it("separa cada cifra de su etiqueta", () => {
    assert.deepEqual(comoCifras("234 superadas · 4 omitidas · 0 fallos · 14 segundos"), [
      { valor: "234", etiqueta: "superadas" },
      { valor: "4", etiqueta: "omitidas" },
      { valor: "0", etiqueta: "fallos" },
      { valor: "14", etiqueta: "segundos" },
    ]);
  });

  it("no toma por resultado un bloque de código cualquiera", () => {
    assert.equal(comoCifras("python -m pytest -q"), null);
  });
});

describe("diapositivas", () => {
  it("separa las notas del presentador de las citas de contenido", () => {
    const [d] = contenido(
      "## 1 · Regla\n\n> Ningún requisito se dio por cumplido sin prueba.\n\n> Notas: Nicolás. Esta regla\n> explica la cobertura.",
    );
    assert.equal(d!.bloques[0]!.tipo, "cita");
    assert.equal(d!.notas.length, 1);
    assert.equal(d!.notas[0]!.presentador, "Nicolás");
    // Las líneas de una nota se unen: son el ajuste de línea del editor.
    assert.deepEqual(d!.notas[0]!.texto, [{ t: "texto", v: "Esta regla explica la cobertura." }]);
  });

  it("conserva los saltos de línea de un párrafo", () => {
    const [d] = contenido("## 1 · Portada\n\n**RASTRO**\nTrazabilidad verificable\n\n> Notas: Ana. Hola.");
    const parrafo = d!.bloques[0] as Extract<Bloque, { tipo: "parrafo" }>;
    assert.equal(parrafo.lineas.length, 2);
    assert.equal(d!.portada, true);
  });

  it("lee una tabla sin fila de separación como tabla sin encabezado", () => {
    const [d] = contenido("## 1 · Conclusiones\n\n| BIEN | Cumplió |\n| MAL | No cumplió |\n\n> Notas: Ana. Hola.");
    const tabla = d!.bloques[0] as Extract<Bloque, { tipo: "tabla" }>;
    assert.equal(tabla.encabezado, null);
    assert.equal(tabla.filas.length, 2);
  });

  it("trata un encabezado vacío como ausencia de encabezado y respeta la alineación", () => {
    const [d] = contenido("## 1 · Hallazgo\n\n| | |\n|---|:---:|\n| **Condición** | ✓ |\n\n> Notas: Ana. Hola.");
    const tabla = d!.bloques[0] as Extract<Bloque, { tipo: "tabla" }>;
    assert.equal(tabla.encabezado, null);
    assert.deepEqual(tabla.alineacion, [null, "centro"]);
  });

  it("arrastra el presentador hasta que las notas nombran a otro", () => {
    const ds = contenido(
      "## 1 · A\n\nx\n\n> Notas: Ana. Empieza.\n\n---\n\n## 2 · B\n\ny\n\n> Notas: Pasar rápido.\n\n---\n\n## 3 · C\n\nz\n\n> Notas: Luis. Sigue.",
    );
    assert.deepEqual(
      ds.map((d) => d.presentador),
      ["Ana", "Ana", "Luis"],
    );
  });

  it("agrupa en cada portadilla las diapositivas de su bloque", () => {
    const { deck } = compilar(
      "# BLOQUE 1 · INICIO\n\n---\n\n## 1 · A\n\nx\n\n> Notas: Ana. a\n\n---\n\n## 2 · B\n\ny\n\n> Notas: Ana. b",
    );
    const portadilla = deck.diapositivas[0]!;
    assert.equal(portadilla.tipo, "bloque");
    assert.equal(portadilla.clave, "bloque-1");
    assert.deepEqual(portadilla.tipo === "bloque" && portadilla.contenido.map((c) => c.numero), [1, 2]);
  });
});

describe("errores y avisos", () => {
  it("rechaza dos diapositivas con el mismo número", () => {
    assert.throws(
      () => compilar("## 1 · A\n\nx\n\n---\n\n## 1 · B\n\ny"),
      (e: unknown) => e instanceof ErrorDeLectura && /ya se usó/.test(e.message),
    );
  });

  it("rechaza una diapositiva sin número", () => {
    assert.throws(() => compilar("## Sin número\n\nx"), /no lleva número/);
  });

  it("rechaza una figura que no existe", () => {
    assert.throws(() => compilar("## 1 · A\n\n![Figura](figura:no-existe)"), /no existe/);
  });

  it("avisa de un salto en la numeración", () => {
    const { avisos } = compilar("## 1 · A\n\nx\n\n> Notas: Ana. a\n\n---\n\n## 3 · B\n\ny\n\n> Notas: Ana. b");
    assert.ok(avisos.some((a) => /le correspondía el 2/.test(a)));
  });
});

describe("los guiones del repositorio", () => {
  for (const nombre of ["sustentacion-rastro.md", "sustentacion-cotejo.md"]) {
    it(`${nombre} compila sin avisos`, () => {
      const fuente = readFileSync(new URL(`../../documentacion/sustentacion/${nombre}`, import.meta.url), "utf8");
      const { deck, avisos } = compilarSustentacion(fuente, { archivo: nombre, figuras: FIGURAS });

      assert.deepEqual(avisos, []);
      assert.equal(deck.resumen.bloques, 7, "los siete bloques que exige el docente");
      const numeradas = deck.diapositivas.filter((d): d is DiapositivaContenido => d.tipo === "contenido");
      assert.ok(numeradas.every((d) => d.presentador), "toda diapositiva tiene quien la presente");
      assert.equal(deck.resumen.intervenciones.length, 3, "participan los tres integrantes");
    });
  }
});
