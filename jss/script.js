/**
 * ========================================
 * FORMULARIO DE CONTACTO - DULCE ENCANTO
 * ========================================
 * 
 * DESCRIPCIÓN: Este script valida y procesa el formulario de contacto
 * del sitio web Dulce Encanto. Realiza validaciones en tiempo real
 * y muestra ventanas emergentes (modales) de éxito o error.
 * 
 * FUNCIONALIDADES:
 * 1. Validación en tiempo real mientras el usuario escribe
 * 2. Validación al hacer blur (perder el foco en el campo)
 * 3. Validación final al enviar el formulario
 * 4. Cambio visual de colores según el estado (rojo=error, verde=correcto)
 * 5. Modal emergente mostrando éxito o error después de enviar
 * 
 * ========================================
 * CÓMO CAMBIAR REQUISITOS DE VALIDACIÓN:
 * ========================================
 * 
 * NOMBRE MÍNIMO: Busca "validarNombre()" y cambia valor.length < 3 por el número deseado
 * ASUNTO MÍNIMO: Busca "validarAsunto()" y cambia valor.length < 5 por el número deseado
 * MENSAJE MÍNIMO: Busca "validarMensaje()" y cambia valor.length < 10 por el número deseado
 * 
 * CORREO DESTINO: Busca "formsubmit.co/ajax/" y cambia contacto@dulceencanto.com
 * 
 * TIEMPO DE ESPERA: Busca "setTimeout(resolve, 1500)" y cambia 1500 (milisegundos)
 * 
 * ========================================
 */

// ===== PASO 1: SELECCIONAR ELEMENTOS DEL HTML =====
// Elementos del formulario
const formularioContacto = document.getElementById("formContacto");
const nombreContacto = document.getElementById("nombreContacto");
const correoContacto = document.getElementById("correoContacto");
const asuntoContacto = document.getElementById("asuntoContacto");
const mensajeContacto = document.getElementById("mensajeContacto");

// Elementos de los modales (ventanas emergentes)
const modalExito = document.getElementById("modalExito");
const mensajeExito = document.getElementById("mensajeExito");
const btnAceptarExito = document.getElementById("btnAceptarExito");

const modalError = document.getElementById("modalError");
const mensajeError = document.getElementById("mensajeError");
const btnAceptarError = document.getElementById("btnAceptarError");

// ===== PASO 2: CREAR FUNCIONES DE VALIDACIÓN =====
// Cada función valida un campo específico del formulario
// Retorna un objeto con { valido: boolean, error: string }

/**
 * Valida el campo de NOMBRE
 * Requisitos: Mínimo 3 caracteres, no vacío
 * CAMBIAR: valor.length < 3 (el número 3 es el mínimo requerido)
 */
function validarNombre() {
  const valor = nombreContacto.value.trim();
  
  if (valor.length === 0) {
    nombreContacto.classList.add("is-invalid");
    nombreContacto.classList.remove("is-valid");
    return { valido: false, error: "El nombre es requerido." };
  }
  
  if (valor.length < 3) {
    nombreContacto.classList.add("is-invalid");
    nombreContacto.classList.remove("is-valid");
    return { valido: false, error: "El nombre debe tener al menos 3 caracteres." };
  }
  
  nombreContacto.classList.add("is-valid");
  nombreContacto.classList.remove("is-invalid");
  return { valido: true };
}

function validarCorreo() {
  const valor = correoContacto.value.trim();
  const patron = /^[^\s@]+@[^\s@]+\.[^\s@]+$/; // CAMBIAR: Esta es la expresión para validar email

  if (valor.length === 0) {
    correoContacto.classList.add("is-invalid");
    correoContacto.classList.remove("is-valid", "is-warning");
    return { valido: false, error: "El correo electrónico es requerido." };
  }

  if (!patron.test(valor)) {
    correoContacto.classList.add("is-invalid");
    correoContacto.classList.remove("is-valid", "is-warning");
    return { valido: false, error: "Ingrese un correo electrónico válido. Ejemplo: usuario@dominio.com" };
  }

  correoContacto.classList.add("is-valid");
  correoContacto.classList.remove("is-invalid", "is-warning");
  return { valido: true };
}

function validarAsunto() {
  const valor = asuntoContacto.value.trim();
  
  if (valor.length === 0) {
    asuntoContacto.classList.add("is-invalid");
    asuntoContacto.classList.remove("is-valid");
    return { valido: false, error: "El asunto es requerido." };
  }
  
  // CAMBIAR: 5 es el número mínimo de caracteres para el asunto
  if (valor.length < 5) {
    asuntoContacto.classList.add("is-invalid");
    asuntoContacto.classList.remove("is-valid");
    return { valido: false, error: "El asunto debe tener al menos 5 caracteres." };
  }
  
  asuntoContacto.classList.add("is-valid");
  asuntoContacto.classList.remove("is-invalid");
  return { valido: true };
}

/**
 * Valida el campo de MENSAJE
 * Requisitos: Mínimo 10 caracteres, no vacío
 * CAMBIAR: valor.length < 10 (el número 10 es el mínimo requerido)
 */
function validarMensaje() {
  const valor = mensajeContacto.value.trim();
  
  if (valor.length === 0) {
    mensajeContacto.classList.add("is-invalid");
    mensajeContacto.classList.remove("is-valid");
    return { valido: false, error: "El mensaje es requerido." };
  }
  
  // CAMBIAR: 10 es el número mínimo de caracteres para el mensaje
  if (valor.length < 10) {
    mensajeContacto.classList.add("is-invalid");
    mensajeContacto.classList.remove("is-valid");
    return { valido: false, error: "El mensaje debe tener al menos 10 caracteres." };
  }
  
  mensajeContacto.classList.add("is-valid");
  mensajeContacto.classList.remove("is-invalid");
  return { valido: true };
}

// ===== PASO 3: AGREGAR EVENTOS DE VALIDACIÓN EN TIEMPO REAL =====
// Estos eventos se ejecutan mientras el usuario escribe o sale del campo
// "input" = mientras escribe | "blur" = cuando sale del campo
// addEventListener: vincula el evento (input/blur) a la función validadora
nombreContacto.addEventListener("input", validarNombre);
nombreContacto.addEventListener("blur", validarNombre);

correoContacto.addEventListener("input", validarCorreo);
correoContacto.addEventListener("blur", validarCorreo);

asuntoContacto.addEventListener("input", validarAsunto);
asuntoContacto.addEventListener("blur", validarAsunto);

mensajeContacto.addEventListener("input", validarMensaje);
mensajeContacto.addEventListener("blur", validarMensaje);

// ===== PASO 4: PROCESAR ENVÍO DEL FORMULARIO =====
// Este evento se dispara cuando el usuario hace clic en "Enviar Mensaje"
formularioContacto.addEventListener("submit", async function(e) {
  e.preventDefault(); // Prevenir recarga de la página

  // Validar todos los campos antes de enviar
  const validacionNombre = validarNombre();
  const validacionCorreo = validarCorreo();
  const validacionAsunto = validarAsunto();
  const validacionMensaje = validarMensaje();

  // Si algún campo falla, mostrar errores y no enviar
  if (!validacionNombre.valido || !validacionCorreo.valido || !validacionAsunto.valido || !validacionMensaje.valido) {
    let errores = [];
    if (!validacionNombre.valido) errores.push(validacionNombre.error);
    if (!validacionCorreo.valido) errores.push(validacionCorreo.error);
    if (!validacionAsunto.valido) errores.push(validacionAsunto.error);
    if (!validacionMensaje.valido) errores.push(validacionMensaje.error);

    // Mostrar modal de error
    mensajeError.innerHTML = "<strong>⚠️ Errores en el formulario:</strong><br>" + errores.join("<br>");
    modalError.style.display = "flex";
    return;
  }

  // Cambiar botón a estado "Enviando..."
  const btnEnviar = formularioContacto.querySelector('button[type="submit"]');
  const textoOriginal = btnEnviar.textContent;
  btnEnviar.textContent = "⏳ Enviando...";
  btnEnviar.disabled = true;

  try {
    // CAMBIAR: Aquí es donde se envía el mensaje
    // Actualmente simula un envío después de 1.5 segundos
    // Para envíos reales, reemplaza con: fetch("tu-servicio-de-correo.com", {...})
    
    // CAMBIAR: El número 1500 es el tiempo de espera en milisegundos
    // 1000 = 1 segundo, 3000 = 3 segundos, etc.
    await new Promise(resolve => setTimeout(resolve, 1500));

    // ✅ Si todo va bien, mostrar mensaje de ÉXITO
    mensajeExito.innerHTML = `
      <strong>✅ ¡Mensaje enviado con éxito!</strong><br>
      <small>Hola <strong>${nombreContacto.value.trim()}</strong>, hemos recibido tu mensaje sobre: <em>"${asuntoContacto.value.trim()}"</em><br><br>
      Te responderemos pronto a: <strong>${correoContacto.value.trim()}</strong><br><br>
      Gracias por contactarnos. 💚</small>
    `;
    modalExito.style.display = "flex";

    // Limpiar formulario después de envío exitoso
    formularioContacto.reset();
    // Remover colores de validación
    [nombreContacto, correoContacto, asuntoContacto, mensajeContacto].forEach(campo => {
      campo.classList.remove("is-valid", "is-invalid", "is-warning");
    });

  } catch (error) {
    console.error("Error:", error);
    
    // ❌ Si hay ERROR, mostrar mensaje de error
    // CAMBIAR: Los datos de contacto en el mensaje de error
    mensajeError.innerHTML = `
      <strong>❌ Error al enviar el mensaje</strong><br>
      <small>Ocurrió un problema al enviar tu mensaje.<br><br>
      Por favor, contáctanos directamente a través de:<br>
      📧 <strong>contacto@dulceencanto.com</strong><br>
      📱 <strong>WhatsApp: +593 9 XXXXXXXX</strong></small>
    `;
    modalError.style.display = "flex";
  } finally {
    // Restaurar botón a su estado original (siempre se ejecuta)
    btnEnviar.textContent = textoOriginal;
    btnEnviar.disabled = false;
  }
});

// ===== PASO 5: CERRAR MODALES (VENTANAS EMERGENTES) =====
// Los usuarios pueden cerrar los modales de dos formas:
// 1. Haciendo clic en el botón "Aceptar"
// 2. Haciendo clic fuera del modal (en el fondo oscuro)

// Cerrar modal de ÉXITO al hacer clic en botón
btnAceptarExito.addEventListener("click", () => {
  modalExito.style.display = "none";
});

// Cerrar modal de ERROR al hacer clic en botón
btnAceptarError.addEventListener("click", () => {
  modalError.style.display = "none";
});

// Cerrar modal de ÉXITO al hacer clic en el fondo oscuro
modalExito.addEventListener("click", (e) => {
  if (e.target === modalExito) modalExito.style.display = "none";
});

// Cerrar modal de ERROR al hacer clic en el fondo oscuro
modalError.addEventListener("click", (e) => {
  if (e.target === modalError) modalError.style.display = "none";
});
