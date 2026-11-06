/* Música original para el video pitch de Rastro.
 *
 * Se sintetiza aquí, nota por nota, para no depender de ninguna pista con
 * derechos: el resultado es del proyecto y se puede publicar donde sea. Es un
 * fondo «tecnológico» sobrio a 100 pulsaciones por minuto, con la forma del
 * video: una intro en menor que acompaña el problema, la entrada de la batería
 * cuando aparece la marca (0:16.8), un respiro en «Seguro por diseño», la vuelta
 * con las cifras y un cierre que se apaga.
 *
 *   node anexos/musica-pitch.mjs [salida.wav]
 *
 * Sin dependencias: escribe un WAV estéreo de 16 bits a 44,1 kHz. Las marcas de
 * tiempo coinciden con las escenas de `pitch.html` (compases de 2,4 s).
 */

import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const SR = 44100;
const BPM = 100;
const PULSO = 60 / BPM; // 0,6 s
const COMPAS = PULSO * 4; // 2,4 s
export const DURACION = COMPAS * 39; // 93,6 s

/* Secciones, en compases. */
const INTRO = [0, 7]; // problema: menor, sin batería
const PRINCIPAL = [7, 28]; // marca, personas y funcionalidades
const RESPIRO = [28, 31]; // seguro por diseño
const FINAL = [31, 35]; // cifras
const CIERRE = [35, 39]; // marca y créditos

const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);

/* Acordes: notas del colchón y del bajo. */
const ACORDES = {
  Am: { notas: [57, 60, 64, 69], bajo: 45 },
  F: { notas: [53, 57, 60, 64], bajo: 41 },
  Dm: { notas: [50, 57, 62, 65], bajo: 38 },
  E: { notas: [52, 56, 59, 64], bajo: 40 },
  C: { notas: [55, 60, 64, 67], bajo: 36 },
  G: { notas: [55, 59, 62, 67], bajo: 43 },
  Fmaj7: { notas: [53, 57, 60, 64, 69], bajo: 41 },
};

/** El acorde de cada compás. */
function acordeDel(compas) {
  if (compas < INTRO[1]) return ["Am", "Am", "F", "F", "Dm", "Dm", "E"][compas];
  if (compas >= CIERRE[0]) return ["Fmaj7", "Fmaj7", "C", "C"][compas - CIERRE[0]];
  const ciclo = ["F", "C", "G", "Am"];
  return ciclo[(compas - INTRO[1]) % 4];
}

const en = (compas, [a, b]) => compas >= a && compas < b;

/* ------------------------------------------------------------------------ */
/* Piezas de síntesis                                                       */
/* ------------------------------------------------------------------------ */

const N = Math.ceil(DURACION * SR);
const L = new Float32Array(N);
const R = new Float32Array(N);
const envioL = new Float32Array(N); // envío a reverberación
const envioR = new Float32Array(N);
const retardoL = new Float32Array(N); // envío a eco
const retardoR = new Float32Array(N);
const bateriaL = new Float32Array(N); // batería: no pasa por la compresión lateral
const bateriaR = new Float32Array(N);

/* Ruido determinista: la misma pista en cada ejecución. */
let semilla = 20261106;
const ruido = () => {
  semilla = (semilla * 1664525 + 1013904223) >>> 0;
  return semilla / 2147483648 - 1;
};

/** Filtro biquad (RBJ). Devuelve una función que procesa muestra a muestra. */
function biquad(tipo, frecuencia, q = 0.707) {
  let b0, b1, b2, a1, a2;
  let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
  const ajustar = (f) => {
    const w = (2 * Math.PI * Math.min(f, SR * 0.45)) / SR;
    const alfa = Math.sin(w) / (2 * q);
    const cos = Math.cos(w);
    const a0 = 1 + alfa;
    if (tipo === "paso-bajo") {
      b0 = (1 - cos) / 2 / a0; b1 = (1 - cos) / a0; b2 = b0;
    } else if (tipo === "paso-alto") {
      b0 = (1 + cos) / 2 / a0; b1 = -(1 + cos) / a0; b2 = b0;
    } else {
      b0 = alfa / a0; b1 = 0; b2 = -alfa / a0;
    }
    a1 = (-2 * cos) / a0;
    a2 = (1 - alfa) / a0;
  };
  ajustar(frecuencia);
  const procesar = (x) => {
    const y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
    x2 = x1; x1 = x; y2 = y1; y1 = y;
    return y;
  };
  procesar.ajustar = ajustar;
  return procesar;
}

/** Diente de sierra con PolyBLEP, para que no suene áspero. */
function sierra(fase, incremento) {
  let v = 2 * fase - 1;
  if (fase < incremento) {
    const t = fase / incremento;
    v -= t + t - t * t - 1;
  } else if (fase > 1 - incremento) {
    const t = (fase - 1) / incremento;
    v -= t * t + t + t + 1;
  }
  return v;
}

/* Golpes de bombo: también mandan la compresión lateral del resto. */
const golpesBombo = [];

function bombo(t0, nivel = 0.82, largo = 0.3) {
  golpesBombo.push(t0);
  const i0 = Math.floor(t0 * SR);
  let fase = 0;
  for (let i = 0; i < SR * 0.6 && i0 + i < N; i++) {
    const t = i / SR;
    const f = 44 + 120 * Math.exp(-t / 0.035);
    fase += f / SR;
    const amp = Math.exp(-t / largo) * nivel;
    const clic = i < 90 ? ruido() * 0.25 * (1 - i / 90) : 0;
    const v = Math.sin(2 * Math.PI * fase) * amp + clic * nivel;
    bateriaL[i0 + i] += v;
    bateriaR[i0 + i] += v;
  }
}

function palmada(t0, nivel = 0.32) {
  const i0 = Math.floor(t0 * SR);
  const bp = biquad("paso-banda", 1500, 0.9);
  for (let i = 0; i < SR * 0.35 && i0 + i < N; i++) {
    const t = i / SR;
    // tres ráfagas cortas y una cola, como las manos de varias personas
    let env = Math.exp(-t / 0.13);
    for (const r of [0, 0.011, 0.022]) if (t >= r && t < r + 0.008) env = Math.max(env, 1);
    const v = bp(ruido()) * env * nivel * 2.2;
    bateriaL[i0 + i] += v * 0.9;
    bateriaR[i0 + i] += v;
    envioL[i0 + i] += v * 0.25;
    envioR[i0 + i] += v * 0.25;
  }
}

function platillo(t0, nivel = 0.1, largo = 0.035, lado = 0) {
  const i0 = Math.floor(t0 * SR);
  const hp = biquad("paso-alto", 7500, 0.8);
  for (let i = 0; i < SR * (largo * 6) && i0 + i < N; i++) {
    const v = hp(ruido()) * Math.exp(-i / SR / largo) * nivel;
    bateriaL[i0 + i] += v * (1 - lado);
    bateriaR[i0 + i] += v * (1 + lado);
  }
}

function tictac(t0, agudo) {
  const i0 = Math.floor(t0 * SR);
  const f = agudo ? 2100 : 1600;
  for (let i = 0; i < SR * 0.06 && i0 + i < N; i++) {
    const t = i / SR;
    const v = (Math.sin(2 * Math.PI * f * t) + 0.4 * Math.sin(2 * Math.PI * f * 1.5 * t)) * Math.exp(-t / 0.012) * 0.06;
    L[i0 + i] += v;
    R[i0 + i] += v * 0.8;
  }
}

/** Nota pulsada: seno y triángulo con caída rápida, con envío a eco y reverb. */
function pulsada(t0, midi, nivel = 0.16, caida = 0.22, pan = 0) {
  const i0 = Math.floor(t0 * SR);
  const f = hz(midi);
  for (let i = 0; i < SR * caida * 5 && i0 + i < N; i++) {
    const t = i / SR;
    const ataque = Math.min(1, t / 0.003);
    const fase = (f * t) % 1;
    const tri = 1 - 4 * Math.abs(fase - 0.5);
    const v = (0.65 * Math.sin(2 * Math.PI * f * t) + 0.35 * tri) * Math.exp(-t / caida) * ataque * nivel;
    L[i0 + i] += v * (1 - pan);
    R[i0 + i] += v * (1 + pan);
    retardoL[i0 + i] += v * 0.45;
    retardoR[i0 + i] += v * 0.45;
    envioL[i0 + i] += v * 0.3;
    envioR[i0 + i] += v * 0.3;
  }
}

/** Colchón: sierras desafinadas por nota, filtradas, con envolvente suave. */
function colchon(t0, t1, notas, nivel, corte) {
  const ataque = 0.35;
  const caida = 0.9;
  const i0 = Math.floor(t0 * SR);
  const i1 = Math.min(N, Math.floor((t1 + caida) * SR));
  const fl = biquad("paso-bajo", corte, 0.6);
  const fr = biquad("paso-bajo", corte, 0.6);
  const osc = notas.flatMap((m) =>
    [-9, -3, 4, 10].map((cents, k) => ({ f: hz(m) * 2 ** (cents / 1200), fase: (k * 0.37 + m * 0.11) % 1, lado: k % 2 })),
  );
  const escala = nivel / Math.sqrt(osc.length);
  for (let i = i0; i < i1; i++) {
    const t = i / SR - t0;
    const env = Math.min(1, t / ataque) * (t > t1 - t0 ? Math.exp(-(t - (t1 - t0)) / (caida / 3)) : 1);
    let sl = 0, sr = 0;
    for (const o of osc) {
      const inc = o.f / SR;
      o.fase += inc;
      if (o.fase >= 1) o.fase -= 1;
      const v = sierra(o.fase, inc);
      if (o.lado) sr += v; else sl += v;
    }
    const vl = fl(sl * escala * env);
    const vr = fr(sr * escala * env);
    L[i] += vl; R[i] += vr;
    envioL[i] += vl * 0.5; envioR[i] += vr * 0.5;
  }
}

/** Bajo: seno con un poco de sierra filtrada, en corcheas. */
function bajo(t0, duracion, midi, nivel = 0.4) {
  const i0 = Math.floor(t0 * SR);
  const f = hz(midi);
  const lp = biquad("paso-bajo", 380, 0.8);
  let fase = 0;
  for (let i = 0; i < SR * duracion && i0 + i < N; i++) {
    const t = i / SR;
    fase += f / SR;
    if (fase >= 1) fase -= 1;
    const env = Math.min(1, t / 0.006) * Math.exp(-t / (duracion * 1.4)) * Math.min(1, (duracion - t) / 0.02);
    const v = (Math.sin(2 * Math.PI * fase) + 0.35 * lp(sierra(fase, f / SR))) * env * nivel;
    L[i0 + i] += v;
    R[i0 + i] += v;
  }
}

/** Subida de ruido que anuncia un cambio de sección. */
function subida(t0, t1, nivel = 0.22) {
  const i0 = Math.floor(t0 * SR);
  const i1 = Math.floor(t1 * SR);
  const bp = biquad("paso-banda", 300, 1.2);
  for (let i = i0; i < i1 && i < N; i++) {
    const p = (i - i0) / (i1 - i0);
    if ((i - i0) % 64 === 0) bp.ajustar(300 * 20 ** p);
    const v = bp(ruido()) * p * p * nivel * 3;
    L[i] += v * (1 - 0.3 * Math.sin(p * 9));
    R[i] += v * (1 + 0.3 * Math.sin(p * 9));
    envioL[i] += v * 0.3;
    envioR[i] += v * 0.3;
  }
}

/** Golpe grave con cola de ruido, en las entradas fuertes. */
function impacto(t0, nivel = 0.7) {
  const i0 = Math.floor(t0 * SR);
  const lp = biquad("paso-bajo", 2500, 0.7);
  let fase = 0;
  for (let i = 0; i < SR * 2.2 && i0 + i < N; i++) {
    const t = i / SR;
    fase += (36 + 60 * Math.exp(-t / 0.08)) / SR;
    const v = Math.sin(2 * Math.PI * fase) * Math.exp(-t / 0.9) * nivel + lp(ruido()) * Math.exp(-t / 0.35) * nivel * 0.35;
    L[i0 + i] += v;
    R[i0 + i] += v;
    envioL[i0 + i] += v * 0.4;
    envioR[i0 + i] += v * 0.4;
  }
}

/* ------------------------------------------------------------------------ */
/* Efectos                                                                  */
/* ------------------------------------------------------------------------ */

/** Eco cruzado a la corchea con puntillo: izquierda, derecha, izquierda… */
function aplicarEco(mezcla = 0.35) {
  const d = Math.round(PULSO * 0.75 * SR);
  const fb = 0.38;
  const A = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const entrada = (retardoL[i] + retardoR[i]) * 0.5;
    A[i] = entrada + (i >= 2 * d ? fb * A[i - 2 * d] : 0);
    const izq = i >= d ? A[i - d] : 0;
    const der = i >= 2 * d ? A[i - 2 * d] : 0;
    L[i] += izq * mezcla;
    R[i] += der * mezcla;
    envioL[i] += izq * 0.15;
    envioR[i] += der * 0.15;
  }
}

/** Reverberación tipo Freeverb (8 peines y 4 pasa-todo por canal). */
function aplicarReverb(mezcla = 0.28) {
  const peines = [1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617];
  const pasatodo = [556, 441, 341, 225];
  const canal = (entrada, desplaz) => {
    const salida = new Float32Array(N);
    const cs = peines.map((n) => ({ buf: new Float32Array(n + desplaz), i: 0, filtro: 0 }));
    const as = pasatodo.map((n) => ({ buf: new Float32Array(n + desplaz), i: 0 }));
    const fb = 0.84;
    const am = 0.2;
    for (let k = 0; k < N; k++) {
      const x = entrada[k] * 0.015;
      let s = 0;
      for (const c of cs) {
        const y = c.buf[c.i];
        c.filtro = y * (1 - am) + c.filtro * am;
        c.buf[c.i] = x + c.filtro * fb;
        c.i = (c.i + 1) % c.buf.length;
        s += y;
      }
      for (const a of as) {
        const b = a.buf[a.i];
        const y = -s + b;
        a.buf[a.i] = s + b * 0.5;
        a.i = (a.i + 1) % a.buf.length;
        s = y;
      }
      salida[k] = s;
    }
    return salida;
  };
  const rl = canal(envioL, 0);
  const rr = canal(envioR, 23);
  for (let i = 0; i < N; i++) {
    L[i] += rl[i] * mezcla * 3;
    R[i] += rr[i] * mezcla * 3;
  }
}

/* ------------------------------------------------------------------------ */
/* Composición                                                              */
/* ------------------------------------------------------------------------ */

export function componer() {
  const colchonDe = [];
  for (let c = 0; c < 39; c++) {
    const t = c * COMPAS;
    const acorde = ACORDES[acordeDel(c)];

    // Colchón: más cerrado en la intro y el respiro, abierto con la batería.
    const corte = en(c, INTRO) ? 700 + c * 90 : en(c, RESPIRO) ? 1100 : en(c, CIERRE) ? 1500 : 2200;
    const nivel = en(c, INTRO) ? 0.2 : en(c, CIERRE) ? 0.24 : 0.17;
    colchonDe.push({ t, notas: acorde.notas, nivel, corte });

    if (en(c, INTRO)) {
      // Esperar un paquete: un reloj y unas pocas notas sueltas.
      for (let p = 0; p < 4; p++) tictac(t + p * PULSO, p % 2 === 0);
      const sueltas = [0, 3, 6, 10];
      sueltas.forEach((s, k) => pulsada(t + s * PULSO / 4, acorde.notas[k % acorde.notas.length] + 12, 0.11, 0.3, k % 2 ? 0.3 : -0.3));
      if (c >= 4) for (let p = 0; p < 4; p++) bajo(t + p * PULSO, PULSO * 0.9, acorde.bajo, 0.22);
    }

    if (en(c, PRINCIPAL) || en(c, FINAL)) {
      const fuerte = en(c, FINAL);
      for (let p = 0; p < 4; p++) bombo(t + p * PULSO);
      palmada(t + PULSO, 0.3);
      palmada(t + 3 * PULSO, 0.3);
      for (let o = 0; o < 8; o++) {
        const abierto = fuerte && o % 2 === 1;
        platillo(t + o * PULSO / 2, o % 2 ? 0.1 : 0.05, abierto ? 0.12 : 0.03, o % 2 ? 0.25 : -0.25);
      }
      for (let o = 0; o < 8; o++) bajo(t + o * PULSO / 2, PULSO / 2 * 0.85, acorde.bajo + (o % 4 === 3 ? 12 : 0), 0.27);
      // Arpegio en semicorcheas sobre las notas del acorde, una octava arriba.
      const patron = [0, 2, 1, 2, 3, 2, 1, 2, 0, 2, 1, 3, 2, 1, 2, 3];
      patron.forEach((k, s) => {
        const acento = s % 4 === 0 ? 1 : 0.7;
        pulsada(t + s * PULSO / 4, acorde.notas[k % acorde.notas.length] + 12, 0.1 * acento, 0.16, s % 2 ? 0.35 : -0.35);
      });
    }

    if (en(c, RESPIRO)) {
      // Sin batería: solo el pulso del bombo, suave, y notas largas.
      bombo(t, 0.5, 0.25);
      bombo(t + 2 * PULSO, 0.5, 0.25);
      [0, 4, 8, 12].forEach((s, k) => pulsada(t + s * PULSO / 4, acorde.notas[(k + 1) % acorde.notas.length] + 12, 0.12, 0.45, k % 2 ? 0.3 : -0.3));
      for (let p = 0; p < 4; p++) bajo(t + p * PULSO, PULSO * 0.95, acorde.bajo, 0.25);
    }

    if (en(c, CIERRE)) {
      const k = c - CIERRE[0];
      [0, 6, 10].forEach((s, j) => pulsada(t + s * PULSO / 4, acorde.notas[(j + k) % acorde.notas.length] + 12, 0.1, 0.5, j % 2 ? 0.3 : -0.3));
      if (k < 2) bajo(t, COMPAS * 0.95, acorde.bajo, 0.3);
    }
  }

  // Colchones: un acorde sostenido mientras no cambie.
  for (let i = 0; i < colchonDe.length; ) {
    let j = i;
    while (j + 1 < colchonDe.length && colchonDe[j + 1].notas === colchonDe[i].notas) j++;
    colchon(colchonDe[i].t, colchonDe[j].t + COMPAS, colchonDe[i].notas, colchonDe[i].nivel, colchonDe[i].corte);
    i = j + 1;
  }

  // Transiciones.
  subida((INTRO[1] - 1) * COMPAS, INTRO[1] * COMPAS);
  impacto(INTRO[1] * COMPAS, 0.75);
  subida((FINAL[0] - 1) * COMPAS, FINAL[0] * COMPAS, 0.18);
  impacto(FINAL[0] * COMPAS, 0.55);
  impacto(CIERRE[0] * COMPAS, 0.7);

  aplicarEco();

  // Compresión lateral: el colchón, el bajo y el arpegio respiran con el bombo.
  const bombeo = new Float32Array(N).fill(1);
  for (const g of golpesBombo) {
    const i0 = Math.floor(g * SR);
    for (let i = 0; i < SR * 0.4 && i0 + i < N; i++) {
      const v = 1 - 0.45 * Math.exp(-i / SR / 0.11);
      bombeo[i0 + i] = Math.min(bombeo[i0 + i], v);
    }
  }
  // Solo sobre lo melódico; la batería se suma después, sin aplastar.
  for (let i = 0; i < N; i++) {
    L[i] = L[i] * (0.55 + 0.45 * bombeo[i]) + bateriaL[i];
    R[i] = R[i] * (0.55 + 0.45 * bombeo[i]) + bateriaR[i];
  }

  aplicarReverb(0.26);

  // Maestro: sin graves inaudibles, saturación suave, normalización a -1 dBFS
  // y fundidos.
  const hpL = biquad("paso-alto", 35, 0.7);
  const hpR = biquad("paso-alto", 35, 0.7);
  let pico = 0;
  for (let i = 0; i < N; i++) {
    L[i] = Math.tanh(hpL(L[i]) * 1.1);
    R[i] = Math.tanh(hpR(R[i]) * 1.1);
    pico = Math.max(pico, Math.abs(L[i]), Math.abs(R[i]));
  }
  const ganancia = 0.89 / pico;
  const fundidoEntrada = 0.25 * SR;
  const fundidoSalida = 4.5 * SR;
  let energia = 0;
  for (let i = 0; i < N; i++) {
    let g = ganancia;
    if (i < fundidoEntrada) g *= i / fundidoEntrada;
    if (i > N - fundidoSalida) g *= Math.max(0, (N - i) / fundidoSalida) ** 1.5;
    L[i] *= g;
    R[i] *= g;
    energia += L[i] * L[i] + R[i] * R[i];
  }
  return { rms: Math.sqrt(energia / (2 * N)) };
}

function wav() {
  const datos = Buffer.alloc(44 + N * 4);
  datos.write("RIFF", 0);
  datos.writeUInt32LE(36 + N * 4, 4);
  datos.write("WAVE", 8);
  datos.write("fmt ", 12);
  datos.writeUInt32LE(16, 16);
  datos.writeUInt16LE(1, 20);
  datos.writeUInt16LE(2, 22);
  datos.writeUInt32LE(SR, 24);
  datos.writeUInt32LE(SR * 4, 28);
  datos.writeUInt16LE(4, 32);
  datos.writeUInt16LE(16, 34);
  datos.write("data", 36);
  datos.writeUInt32LE(N * 4, 40);
  for (let i = 0; i < N; i++) {
    datos.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i])) * 32767), 44 + i * 4);
    datos.writeInt16LE(Math.round(Math.max(-1, Math.min(1, R[i])) * 32767), 46 + i * 4);
  }
  return datos;
}

export async function generarMusica(ruta) {
  const { rms } = componer();
  await writeFile(ruta, wav());
  return { duracion: DURACION, rmsDb: 20 * Math.log10(rms) };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const ruta = process.argv[2] ?? "musica-pitch.wav";
  generarMusica(ruta).then(({ duracion, rmsDb }) =>
    console.log(`${ruta} · ${duracion.toFixed(1)} s · RMS ${rmsDb.toFixed(1)} dBFS`),
  );
}
