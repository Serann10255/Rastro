/* Deck de Rastro: sistema de diseño compartido, identidad de Rastro y su guion. */

import "@design/tokens.css";
import "@design/base.css";
import "@design/componentes.css";
import "@identidad-rastro";
import "@/estilos/presentacion.css";

import { LogotipoRastro } from "@design/marca/rastro";
import deck from "@sustentacion/sustentacion-rastro.md";

import { montar } from "@/deck/montar";

montar(deck, LogotipoRastro);
