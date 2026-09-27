/* Deck de Cotejo: sistema de diseño compartido, identidad de Cotejo y su guion. */

import "@design/tokens.css";
import "@design/base.css";
import "@design/componentes.css";
import "@identidad-cotejo";
import "@/estilos/presentacion.css";

import { LogotipoCotejo } from "@design/marca/cotejo";
import deck from "@sustentacion/sustentacion-cotejo.md";

import { montar } from "@/deck/montar";

montar(deck, LogotipoCotejo);
