/* Rastro presentado a la universidad: mismo visor e identidad que la
 * sustentación de Rastro, con un guion para público general. */

import "@design/tokens.css";
import "@design/base.css";
import "@design/componentes.css";
import "@identidad-rastro";
import "@/estilos/presentacion.css";

import { LogotipoRastro } from "@design/marca/rastro";
import deck from "@sustentacion/presentacion-universidad.md";

import { montar } from "@/deck/montar";

montar(deck, LogotipoRastro);
