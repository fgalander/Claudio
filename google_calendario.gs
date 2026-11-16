// CLAUDIO · Crear, mover y cancelar citas en tu Google Calendar.
//
// Este código NO va en la Raspberry: se pega en https://script.google.com (ver README).
// Corre dentro de tu cuenta de Google y solo atiende pedidos que traigan la clave correcta.
//
// Si ya tenías una versión anterior publicada: reemplaza el código, conserva tu CLAVE y
// publica de nuevo con Implementar → Gestionar implementaciones → lápiz → Versión: Nueva
// versión → Implementar. Así la dirección no cambia.

// Cambia esto por una clave larga inventada por ti, y pon la misma en config.json.
const CLAVE = 'CAMBIA-ESTA-CLAVE';

function doPost(e) {
  let pedido;
  try {
    pedido = JSON.parse(e.postData.contents);
  } catch (error) {
    return responder({ ok: false, error: 'pedido ilegible' });
  }
  if (CLAVE === 'CAMBIA-ESTA-CLAVE' || pedido.clave !== CLAVE) {
    return responder({ ok: false, error: 'clave incorrecta' });
  }
  try {
    const calendario = CalendarApp.getDefaultCalendar();
    if (pedido.accion === 'crear' && pedido.titulo && pedido.inicio) {
      const opciones = { location: pedido.lugar || '' };
      const inicio = new Date(pedido.inicio);
      const cita = pedido.todo_el_dia
        ? calendario.createAllDayEvent(pedido.titulo, inicio, opciones)
        : calendario.createEvent(pedido.titulo, inicio, new Date(pedido.fin), opciones);
      return responder({ ok: true, id: cita.getId() });
    }
    if ((pedido.accion === 'borrar' || pedido.accion === 'mover') && pedido.inicio) {
      const cita = buscar(calendario, pedido);
      if (!cita) {
        return responder({ ok: false, error: 'no encontré esa cita en tu calendario principal' });
      }
      if (pedido.accion === 'borrar') {
        cita.deleteEvent();
      } else if (pedido.todo_el_dia) {
        cita.setAllDayDate(new Date(pedido.nuevo_inicio));
      } else {
        cita.setTime(new Date(pedido.nuevo_inicio), new Date(pedido.nuevo_fin));
      }
      return responder({ ok: true });
    }
    return responder({ ok: false, error: 'faltan datos' });
  } catch (error) {
    return responder({ ok: false, error: String(error) });
  }
}

// Busca la cita en su día y hora: así, en una cita que se repite, solo toca esa fecha.
function buscar(calendario, pedido) {
  const inicio = new Date(pedido.inicio);
  const citas = pedido.todo_el_dia
    ? calendario.getEventsForDay(inicio)
    : calendario.getEvents(new Date(inicio.getTime() - 60000), new Date(inicio.getTime() + 60000));
  return citas.find((cita) => cita.getId() === pedido.id)
    || citas.find((cita) => cita.getTitle() === pedido.titulo)
    || null;
}

function responder(datos) {
  return ContentService.createTextOutput(JSON.stringify(datos)).setMimeType(ContentService.MimeType.JSON);
}
