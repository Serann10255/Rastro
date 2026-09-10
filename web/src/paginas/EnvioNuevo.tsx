/* Registro de un envío.
 *
 * El identificador lo genera el servidor y es aleatorio, no consecutivo: con
 * numeración secuencial cualquiera podría recorrer los identificadores contiguos
 * desde el punto de consulta público y obtener los envíos de toda la empresa.
 * Por eso la pantalla insiste en copiarlo: es lo único que el destinatario
 * necesita, y no puede deducirse.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { useCrearEnvio } from "@/api/consultas";
import { mensajeDeError, useNotificaciones } from "@/componentes/notificaciones";
import { Aviso, Boton, Campo, CampoArea, Tarjeta } from "@/componentes/ui";

interface Formulario {
  origen: string;
  origenReferencia: string;
  destino: string;
  destinoReferencia: string;
  ciudad: string;
  destinatario: string;
  telefono: string;
  descripcion: string;
}

const VACIO: Formulario = {
  origen: "",
  origenReferencia: "",
  destino: "",
  destinoReferencia: "",
  ciudad: "Bogotá",
  destinatario: "",
  telefono: "",
  descripcion: "",
};

export function EnvioNuevo() {
  const navegar = useNavigate();
  const { avisar } = useNotificaciones();
  const [datos, setDatos] = useState<Formulario>(VACIO);
  const [errores, setErrores] = useState<Partial<Record<keyof Formulario, string>>>({});

  const crear = useCrearEnvio();

  const cambiar = (campo: keyof Formulario) => (evento: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setDatos((previo) => ({ ...previo, [campo]: evento.target.value }));
    setErrores((previo) => ({ ...previo, [campo]: undefined }));
  };

  /* Se valida en el cliente para no gastar un viaje de red en un campo vacío,
   * pero el servidor vuelve a validar: esto es comodidad, no control. */
  const validar = (): boolean => {
    const nuevos: Partial<Record<keyof Formulario, string>> = {};
    if (datos.origen.trim().length < 3) nuevos.origen = "Indique la dirección de recogida.";
    if (datos.destino.trim().length < 3) nuevos.destino = "Indique la dirección de entrega.";
    if (datos.destinatario.trim().length < 2) nuevos.destinatario = "Indique quién recibe el envío.";
    setErrores(nuevos);
    return Object.keys(nuevos).length === 0;
  };

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!validar()) return;

    try {
      const resultado = await crear.mutateAsync({
        origen: {
          linea: datos.origen.trim(),
          ciudad: datos.ciudad.trim() || "Bogotá",
          referencia: datos.origenReferencia.trim() || undefined,
        },
        destino: {
          linea: datos.destino.trim(),
          ciudad: datos.ciudad.trim() || "Bogotá",
          referencia: datos.destinoReferencia.trim() || undefined,
        },
        destinatario: {
          nombre: datos.destinatario.trim(),
          telefono: datos.telefono.trim() || undefined,
        },
        descripcion: datos.descripcion.trim() || undefined,
      });
      avisar("Envío registrado. Ya puede asignarle un mensajero.", "exito");
      navegar(`/envios/${resultado.envio.envio_id}`, { state: { recienCreado: true } });
    } catch {
      /* El error se muestra bajo el formulario, no en una notificación que
       * desaparece: el usuario tiene que poder leerlo y corregir. */
    }
  };

  return (
    <>
      <header className="encabezado-pagina">
        <h1>Registrar un envío</h1>
        <p className="encabezado-pagina__descripcion">
          El sistema genera un identificador aleatorio y crea el registro maestro en estado{" "}
          <strong>CREADO</strong>. A partir de ahí, cada cambio de estado queda atribuido a quien lo
          hizo.
        </p>
      </header>

      <form onSubmit={enviar} noValidate>
        <div className="doble-panel">
          <div className="pila">
            <Tarjeta titulo="Recogida y entrega">
              <div className="pila-sm">
                <Campo
                  etiqueta="Dirección de recogida"
                  required
                  placeholder="Calle 100 #15-20"
                  value={datos.origen}
                  onChange={cambiar("origen")}
                  error={errores.origen}
                />
                <Campo
                  etiqueta="Referencia de recogida"
                  opcional
                  placeholder="Oficina 402, portería norte"
                  value={datos.origenReferencia}
                  onChange={cambiar("origenReferencia")}
                />
                <Campo
                  etiqueta="Dirección de entrega"
                  required
                  placeholder="Carrera 7 #32-16"
                  value={datos.destino}
                  onChange={cambiar("destino")}
                  error={errores.destino}
                />
                <Campo
                  etiqueta="Referencia de entrega"
                  opcional
                  placeholder="Piso 8"
                  value={datos.destinoReferencia}
                  onChange={cambiar("destinoReferencia")}
                />
                <Campo
                  etiqueta="Ciudad"
                  value={datos.ciudad}
                  onChange={cambiar("ciudad")}
                  ayuda="El alcance del proyecto se delimita a la operación urbana."
                />
              </div>
            </Tarjeta>
          </div>

          <div className="pila">
            <Tarjeta titulo="Destinatario">
              <div className="pila-sm">
                <Campo
                  etiqueta="Nombre"
                  required
                  placeholder="Nombre y apellido"
                  value={datos.destinatario}
                  onChange={cambiar("destinatario")}
                  error={errores.destinatario}
                  ayuda="En la consulta pública el nombre se muestra enmascarado."
                />
                <Campo
                  etiqueta="Teléfono"
                  opcional
                  type="tel"
                  inputMode="tel"
                  placeholder="3000000000"
                  value={datos.telefono}
                  onChange={cambiar("telefono")}
                />
                <CampoArea
                  etiqueta="Descripción"
                  opcional
                  rows={3}
                  placeholder="Sobre con documentos contractuales"
                  value={datos.descripcion}
                  onChange={cambiar("descripcion")}
                />
              </div>
            </Tarjeta>

            <Aviso tono="info" titulo="Datos sintéticos">
              El sistema se puebla únicamente con datos sintéticos, de modo que el proyecto no genera
              obligaciones de tratamiento sobre titulares reales.
            </Aviso>

            {crear.isError && (
              <Aviso tono="error" titulo="No se pudo registrar el envío">
                {mensajeDeError(crear.error)}
              </Aviso>
            )}

            <div className="acciones">
              <Boton type="submit" cargando={crear.isPending} grande>
                Registrar envío
              </Boton>
              <Boton type="button" variante="secundario" onClick={() => navegar(-1)}>
                Cancelar
              </Boton>
            </div>
          </div>
        </div>
      </form>
    </>
  );
}
