/* Rastro desplegado en AWS, simplificado para proyectar.
 *
 * Es la misma arquitectura de documentacion/arquitectura/vision-general.md con
 * menos cajas: los ocho servicios se dibujan como una sola, porque lo que
 * importa a distancia es que todos pasan por la misma capa común de control, no
 * cómo se llama cada uno. El registro de actividad va con borde discontinuo
 * porque no lo escribe la aplicación: registra cada llamada a AWS por su cuenta.
 */

import { Caja, PuntaFlecha, useIdSvg } from "@/deck/piezas-svg";
import type { PropiedadesFigura } from "@/figuras";

export default function ArquitecturaRastro({ titulo }: PropiedadesFigura) {
  const flecha = useIdSvg("flecha");
  const tituloId = useIdSvg("titulo");

  return (
    <svg viewBox="0 0 820 720" role="img" aria-labelledby={tituloId} className="fig">
      <title id={tituloId}>{titulo}</title>
      <defs>
        <PuntaFlecha id={flecha} />
      </defs>

      {/* Quién entra: fuera de la cuenta. */}
      <Caja
        x={40}
        y={0}
        ancho={340}
        alto={90}
        variante="actor"
        lineas={[{ texto: "Usuarios", estilo: "fuerte" }, { texto: "cinco roles", estilo: "suave" }]}
      />
      <Caja
        x={440}
        y={0}
        ancho={340}
        alto={90}
        variante="actor"
        lineas={[{ texto: "Destinatario", estilo: "fuerte" }, { texto: "sin cuenta", estilo: "suave" }]}
      />

      {/* La cuenta del laboratorio. */}
      <rect x={10} y={130} width={800} height={585} rx={20} className="fig-marco" />
      <text x={34} y={168} fontSize={25} className="fig-texto fig-texto--rotulo">
        AWS · us-east-1
      </text>

      <path d="M330 90 V183" className="fig-linea" markerEnd={`url(#${flecha})`} />
      <path d="M490 90 V183" className="fig-linea" markerEnd={`url(#${flecha})`} />

      <Caja
        x={60}
        y={185}
        ancho={700}
        alto={100}
        lineas={[{ texto: "Interfaz web", estilo: "fuerte" }, { texto: "sitio estático en S3", estilo: "suave" }]}
      />
      <path d="M410 285 V318" className="fig-linea" markerEnd={`url(#${flecha})`} />

      <Caja
        x={60}
        y={320}
        ancho={700}
        alto={100}
        lineas={[{ texto: "Puerta de enlace HTTP", estilo: "fuerte" }, { texto: "API Gateway", estilo: "suave" }]}
      />
      <path d="M410 420 V453" className="fig-linea" markerEnd={`url(#${flecha})`} />

      <Caja
        x={60}
        y={455}
        ancho={700}
        alto={110}
        variante="acento"
        lineas={[
          { texto: "8 funciones Lambda", estilo: "fuerte" },
          { texto: "una sola capa común de control", estilo: "suave" },
        ]}
      />

      {/* Lo que la capa común alcanza. */}
      <path d="M145 565 V598" className="fig-linea" markerEnd={`url(#${flecha})`} />
      <path d="M410 565 V598" className="fig-linea" markerEnd={`url(#${flecha})`} />
      <path d="M675 565 V598" className="fig-linea fig-linea--discontinua" markerEnd={`url(#${flecha})`} />

      <Caja
        x={25}
        y={600}
        ancho={240}
        alto={100}
        lineas={[{ texto: "3 tablas", estilo: "fuerte" }, { texto: "DynamoDB", estilo: "suave" }]}
      />
      <Caja
        x={290}
        y={600}
        ancho={240}
        alto={100}
        lineas={[{ texto: "Evidencias", estilo: "fuerte" }, { texto: "S3 · cifrado KMS", estilo: "suave" }]}
      />
      <Caja
        x={555}
        y={600}
        ancho={240}
        alto={100}
        variante="discontinua"
        lineas={[{ texto: "Actividad", estilo: "fuerte" }, { texto: "CloudTrail", estilo: "suave" }]}
      />
    </svg>
  );
}
