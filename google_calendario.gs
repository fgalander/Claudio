// CLAUDIO · Crear citas en tu Google Calendar.
//
// Este código NO va en la Raspberry: se pega en https://script.google.com (ver README).
// Corre dentro de tu cuenta de Google y solo hace una cosa: crear citas cuando Claudio
// se lo pide con la clave correcta.

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
  if (pedido.accion !== 'crear' || !pedido.titulo || !pedido.inicio) {
    return responder({ ok: false, error: 'faltan datos' });
  }
  const calendario = CalendarApp.getDefaultCalendar();
  const opciones = { location: pedido.lugar || '' };
  const inicio = new Date(pedido.inicio);
  let cita;
  if (pedido.todo_el_dia) {
    cita = calendario.createAllDayEvent(pedido.titulo, inicio, opciones);
  } else {
    cita = calendario.createEvent(pedido.titulo, inicio, new Date(pedido.fin), opciones);
  }
  return responder({ ok: true, id: cita.getId() });
}

function responder(datos) {
  return ContentService.createTextOutput(JSON.stringify(datos)).setMimeType(ContentService.MimeType.JSON);
}
