/* Piezas de interfaz reutilizables.
 *
 * No se usa una biblioteca de componentes de terceros. La razón no es
 * purismo: el sitio se publica como estático en el almacenamiento de objetos y
 * el proyecto se audita a sí mismo, de modo que conviene que todo lo que se
 * sirve sea código propio y revisable, sin dependencias que arrastren su propia
 * cadena de suministro.
 */

import { useEffect, useId, useRef } from "react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import type { Estado, Resultado } from "@/tipos";

// --------------------------------------------------------------------------- //
// Presentación de datos
// --------------------------------------------------------------------------- //

export function textoEstado(estado: Estado): string {
  return estado.replace(/_/g, " ");
}

export function fechaLegible(iso: string | undefined): string {
  if (!iso) return "";
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return iso;
  return fecha.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}

export function fechaRelativa(iso: string | undefined): string {
  if (!iso) return "";
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) return "";
  const segundos = Math.round((Date.now() - fecha.getTime()) / 1000);
  const formato = new Intl.RelativeTimeFormat("es-CO", { numeric: "auto" });
  const escalas: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, "second"],
    [3600, "minute"],
    [86400, "hour"],
    [2592000, "day"],
  ];
  let anterior = 1;
  for (const [limite, unidad] of escalas) {
    if (segundos < limite) return formato.format(-Math.round(segundos / anterior), unidad);
    anterior = limite;
  }
  return formato.format(-Math.round(segundos / 2592000), "month");
}

// --------------------------------------------------------------------------- //
// Etiquetas
// --------------------------------------------------------------------------- //

export function EtiquetaEstado({
  estado,
  codigo,
  conPunto = false,
}: {
  estado: Estado;
  /** Código numérico del catálogo. Se muestra porque es lo que viaja en los
   *  archivos de intercambio con transportistas: quien concilia un archivo
   *  necesita ver el mismo número que aparece en él. */
  codigo?: number;
  conPunto?: boolean;
}) {
  return (
    <span className={`etiqueta etiqueta--estado estado-${estado}`}>
      {conPunto && <span className="punto-estado" aria-hidden="true" />}
      {codigo !== undefined && <span style={{ opacity: 0.7 }}>{codigo}</span>}
      {textoEstado(estado)}
    </span>
  );
}

export function EtiquetaResultado({ resultado }: { resultado: Resultado }) {
  return <span className={`etiqueta etiqueta--${resultado}`}>{resultado}</span>;
}

// --------------------------------------------------------------------------- //
// Superficies
// --------------------------------------------------------------------------- //

export function Tarjeta({
  titulo,
  ayuda,
  acciones,
  children,
  pie,
  className = "",
}: {
  titulo?: ReactNode;
  ayuda?: ReactNode;
  acciones?: ReactNode;
  children: ReactNode;
  pie?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`tarjeta ${className}`}>
      {(titulo || acciones) && (
        <header className="tarjeta__cabecera">
          <div className="min-cero">
            {titulo && <h2 className="tarjeta__titulo">{titulo}</h2>}
            {ayuda && <p className="tarjeta__ayuda">{ayuda}</p>}
          </div>
          {acciones && <div className="fila">{acciones}</div>}
        </header>
      )}
      <div className="tarjeta__cuerpo">{children}</div>
      {pie && <footer className="tarjeta__pie">{pie}</footer>}
    </section>
  );
}

export function Metrica({
  etiqueta,
  valor,
  nota,
  color,
}: {
  etiqueta: string;
  valor: ReactNode;
  nota?: ReactNode;
  color?: string;
}) {
  return (
    <div className="metrica" style={color ? ({ "--metrica-color": color } as never) : undefined}>
      <span className="metrica__etiqueta">{etiqueta}</span>
      <span className="metrica__valor">{valor}</span>
      {nota && <span className="metrica__nota">{nota}</span>}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Botones
// --------------------------------------------------------------------------- //

type VarianteBoton = "primario" | "secundario" | "sutil" | "peligro";

interface PropsBoton extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: VarianteBoton;
  cargando?: boolean;
  bloque?: boolean;
  grande?: boolean;
}

export function Boton({
  variante = "primario",
  cargando = false,
  bloque = false,
  grande = false,
  disabled,
  children,
  className = "",
  ...resto
}: PropsBoton) {
  const clases = [
    "boton",
    variante !== "primario" ? `boton--${variante}` : "",
    bloque ? "boton--bloque" : "",
    grande ? "boton--grande" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button className={clases} disabled={disabled || cargando} aria-busy={cargando} {...resto}>
      {cargando && <Girador />}
      {children}
    </button>
  );
}

export function Girador({ tamano = 16 }: { tamano?: number }) {
  return (
    <svg
      width={tamano}
      height={tamano}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      style={{ animation: "girar 800ms linear infinite", flex: "0 0 auto" }}
    >
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

// --------------------------------------------------------------------------- //
// Formularios
// --------------------------------------------------------------------------- //

interface PropsCampo {
  etiqueta: string;
  ayuda?: ReactNode;
  error?: string;
  opcional?: boolean;
  children?: ReactNode;
}

export function Campo({
  etiqueta,
  ayuda,
  error,
  opcional,
  children,
  ...resto
}: PropsCampo & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  const idAyuda = `${id}-ayuda`;
  const idError = `${id}-error`;

  return (
    <div className={`campo ${error ? "campo--invalido" : ""}`}>
      <label className="campo__etiqueta" htmlFor={id}>
        {etiqueta} {opcional && <span className="campo__opcional">(opcional)</span>}
      </label>
      {children ?? (
        <input
          id={id}
          className="campo__control"
          aria-describedby={[ayuda ? idAyuda : "", error ? idError : ""].filter(Boolean).join(" ") || undefined}
          aria-invalid={error ? true : undefined}
          {...resto}
        />
      )}
      {ayuda && !error && (
        <span className="campo__ayuda" id={idAyuda}>
          {ayuda}
        </span>
      )}
      {error && (
        <span className="campo__error" id={idError} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

export function CampoArea({
  etiqueta,
  ayuda,
  opcional,
  ...resto
}: PropsCampo & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return (
    <div className="campo">
      <label className="campo__etiqueta" htmlFor={id}>
        {etiqueta} {opcional && <span className="campo__opcional">(opcional)</span>}
      </label>
      <textarea id={id} className="campo__control campo__control--area" {...resto} />
      {ayuda && <span className="campo__ayuda">{ayuda}</span>}
    </div>
  );
}

export function CampoSelect({
  etiqueta,
  ayuda,
  children,
  ...resto
}: PropsCampo & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId();
  return (
    <div className="campo">
      <label className="campo__etiqueta" htmlFor={id}>
        {etiqueta}
      </label>
      <select id={id} className="campo__control" {...resto}>
        {children}
      </select>
      {ayuda && <span className="campo__ayuda">{ayuda}</span>}
    </div>
  );
}

export function GrupoSegmentado<T extends string>({
  etiqueta,
  valor,
  opciones,
  onCambio,
}: {
  etiqueta: string;
  valor: T;
  opciones: { valor: T; texto: string }[];
  onCambio: (valor: T) => void;
}) {
  return (
    <div className="campo">
      <span className="campo__etiqueta" id={`${etiqueta}-etiqueta`}>
        {etiqueta}
      </span>
      <div className="grupo-segmentado" role="group" aria-labelledby={`${etiqueta}-etiqueta`}>
        {opciones.map((opcion) => (
          <button
            key={opcion.valor}
            type="button"
            className="grupo-segmentado__opcion"
            aria-pressed={valor === opcion.valor}
            onClick={() => onCambio(opcion.valor)}
          >
            {opcion.texto}
          </button>
        ))}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Avisos
// --------------------------------------------------------------------------- //

export function Aviso({
  tono = "info",
  titulo,
  children,
  acciones,
}: {
  tono?: "info" | "exito" | "alerta" | "error";
  titulo?: ReactNode;
  children?: ReactNode;
  acciones?: ReactNode;
}) {
  return (
    <div className={`aviso aviso--${tono}`} role={tono === "error" ? "alert" : "status"}>
      <div className="aviso__cuerpo">
        {titulo && <strong className="aviso__titulo">{titulo}</strong>}
        {children}
        {acciones && <div className="fila">{acciones}</div>}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Estados de carga y vacío
// --------------------------------------------------------------------------- //

export function Esqueleto({ alto = "1rem", ancho = "100%" }: { alto?: string; ancho?: string }) {
  return <div className="esqueleto" style={{ height: alto, width: ancho }} aria-hidden="true" />;
}

export function ListaEsqueleto({ filas = 4 }: { filas?: number }) {
  return (
    <div className="pila-sm" aria-busy="true" aria-label="Cargando">
      {Array.from({ length: filas }, (_, indice) => (
        <Esqueleto key={indice} alto="4.5rem" />
      ))}
    </div>
  );
}

export function Vacio({
  titulo,
  descripcion,
  accion,
}: {
  titulo: string;
  descripcion?: ReactNode;
  accion?: ReactNode;
}) {
  return (
    <div className="vacio">
      <p className="vacio__titulo">{titulo}</p>
      {descripcion && <p className="vacio__descripcion">{descripcion}</p>}
      {accion}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Ventana modal
// --------------------------------------------------------------------------- //

export function Modal({
  titulo,
  abierto,
  onCerrar,
  children,
}: {
  titulo: string;
  abierto: boolean;
  onCerrar: () => void;
  children: ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);

  // Escape cierra, y el foco entra en el panel: sin esto, el lector de pantalla
  // seguiría anunciando el contenido de detrás.
  useEffect(() => {
    if (!abierto) return;
    const alPulsar = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") onCerrar();
    };
    document.addEventListener("keydown", alPulsar);
    panel.current?.focus();
    const desbordeOriginal = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", alPulsar);
      document.body.style.overflow = desbordeOriginal;
    };
  }, [abierto, onCerrar]);

  if (!abierto) return null;

  return (
    <div className="modal" onMouseDown={(evento) => evento.target === evento.currentTarget && onCerrar()}>
      <div
        className="modal__panel"
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        tabIndex={-1}
        ref={panel}
      >
        {children}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Copiar al portapapeles
// --------------------------------------------------------------------------- //

export function BotonCopiar({ texto, etiqueta = "Copiar" }: { texto: string; etiqueta?: string }) {
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto);
    } catch {
      // Sin permiso de portapapeles: se selecciona para que el usuario copie.
      const rango = document.createRange();
      const nodo = document.getElementById(`copiable-${texto.slice(0, 8)}`);
      if (nodo) {
        rango.selectNodeContents(nodo);
        window.getSelection()?.removeAllRanges();
        window.getSelection()?.addRange(rango);
      }
    }
  };

  return (
    <Boton variante="sutil" type="button" onClick={copiar} title={`${etiqueta}: ${texto}`}>
      {etiqueta}
    </Boton>
  );
}

// --------------------------------------------------------------------------- //
// Confirmación de acciones irreversibles
// --------------------------------------------------------------------------- //

/* Se pide confirmación solo para lo que no se puede deshacer. Pedirla para todo
 * enseña a pulsar «sí» sin leer, y entonces deja de proteger de nada. */
export function Confirmacion({
  abierto,
  titulo,
  descripcion,
  textoConfirmar = "Eliminar",
  cargando = false,
  onConfirmar,
  onCancelar,
}: {
  abierto: boolean;
  titulo: string;
  descripcion: ReactNode;
  textoConfirmar?: string;
  cargando?: boolean;
  onConfirmar: () => void;
  onCancelar: () => void;
}) {
  return (
    <Modal titulo={titulo} abierto={abierto} onCerrar={onCancelar}>
      <div className="tarjeta__cabecera">
        <h2 className="tarjeta__titulo">{titulo}</h2>
      </div>
      <div className="tarjeta__cuerpo pila-sm">
        <p className="texto-sm texto-suave">{descripcion}</p>
        <div className="acciones">
          <Boton variante="peligro" onClick={onConfirmar} cargando={cargando}>
            {textoConfirmar}
          </Boton>
          <Boton variante="secundario" onClick={onCancelar}>
            Cancelar
          </Boton>
        </div>
      </div>
    </Modal>
  );
}

// --------------------------------------------------------------------------- //
// Tabla responsive de datos maestros
// --------------------------------------------------------------------------- //

export interface ColumnaTabla<T> {
  clave: string;
  titulo: string;
  /** Contenido de la celda. Se pasa el registro entero para poder componer. */
  render: (registro: T) => ReactNode;
  /** Las columnas de texto largo envuelven; las cortas no. */
  envuelve?: boolean;
}

/** Tabla con desplazamiento propio y acciones por fila.
 *
 * En móvil se desplaza dentro de su contenedor, nunca en la página. Se prefiere
 * una tabla a un listado de tarjetas porque los datos maestros se consultan
 * para comparar entre sí -qué tiendas hay en qué ciudad- y comparar exige
 * columnas alineadas.
 */
export function TablaDatos<T>({
  columnas,
  registros,
  claveDe,
  acciones,
  vacio,
}: {
  columnas: ColumnaTabla<T>[];
  registros: T[];
  claveDe: (registro: T) => string;
  acciones?: (registro: T) => ReactNode;
  vacio: ReactNode;
}) {
  if (registros.length === 0) return <>{vacio}</>;

  return (
    <div className="tabla-contenedor">
      <table className="tabla">
        <thead>
          <tr>
            {columnas.map((columna) => (
              <th key={columna.clave} scope="col">
                {columna.titulo}
              </th>
            ))}
            {acciones && (
              <th scope="col">
                <span className="solo-lectores">Acciones</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {registros.map((registro) => (
            <tr key={claveDe(registro)}>
              {columnas.map((columna) => (
                <td key={columna.clave} className={columna.envuelve ? "envuelve" : undefined}>
                  {columna.render(registro)}
                </td>
              ))}
              {acciones && <td>{acciones(registro)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
