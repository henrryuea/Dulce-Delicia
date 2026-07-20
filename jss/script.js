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

// ===== EFECTO DE SCROLL EN NAVBAR =====
const navbar = document.querySelector(".navbar");
window.addEventListener("scroll", () => {
  if (window.scrollY > 50) {
    navbar.classList.add("scrolled");
  } else {
    navbar.classList.remove("scrolled");
  }
});

// ===== RESALTAR SECCIÓN ACTIVA =====
const links = document.querySelectorAll(".nav-link");
window.addEventListener("scroll", () => {
  let fromTop = window.scrollY + 100;
  links.forEach(link => {
    const section = document.querySelector(link.hash);
    if (section && section.offsetTop <= fromTop && section.offsetTop + section.offsetHeight > fromTop) {
      link.classList.add("active");
    } else {
      link.classList.remove("active");
    }
  });
});


// ===== PASO 1: SELECCIONAR ELEMENTOS DEL HTML =====
const formularioContacto = document.getElementById("formContacto");
const nombreContacto = document.getElementById("nombreContacto");
const correoContacto = document.getElementById("correoContacto");
const categoriaContacto = document.getElementById("categoriaContacto");
const asuntoContacto = document.getElementById("asuntoContacto");
const mensajeContacto = document.getElementById("mensajeContacto");


const modalExito = document.getElementById("modalExito");
const mensajeExito = document.getElementById("mensajeExito");
const btnAceptarExito = document.getElementById("btnAceptarExito");

const modalError = document.getElementById("modalError");
const mensajeError = document.getElementById("mensajeError");
const btnAceptarError = document.getElementById("btnAceptarError");

// ===== PASO 2: FUNCIONES DE VALIDACIÓN =====
function validarNombre() {
  const valor = nombreContacto.value.trim();
  const feedback = nombreContacto.nextElementSibling;
  const patronNombre = /^[A-Za-zÁÉÍÓÚáéíóúñÑ\s]+$/;

  if (valor.length === 0) {
    nombreContacto.classList.add("is-invalid");
    nombreContacto.classList.remove("is-valid");
    feedback.textContent = "El nombre es requerido.";
    return { valido: false };
  }

  if (!patronNombre.test(valor)) {
    nombreContacto.classList.add("is-invalid");
    nombreContacto.classList.remove("is-valid");
    feedback.textContent = "El nombre solo debe contener letras.";
    return { valido: false };
  }

  if (valor.length < 3) {
    nombreContacto.classList.add("is-invalid");
    nombreContacto.classList.remove("is-valid");
    feedback.textContent = "El nombre debe tener al menos 3 caracteres.";
    return { valido: false };
  }

  nombreContacto.classList.add("is-valid");
  nombreContacto.classList.remove("is-invalid");
  feedback.textContent = "";
  return { valido: true };
}

function validarCorreo() {
  const valor = correoContacto.value.trim();
  const feedback = correoContacto.nextElementSibling;
  const patron = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  if (valor.length === 0) {
    correoContacto.classList.add("is-invalid");
    correoContacto.classList.remove("is-valid");
    feedback.textContent = "El correo electrónico es requerido.";
    return { valido: false };
  }

  if (!patron.test(valor)) {
    correoContacto.classList.add("is-invalid");
    correoContacto.classList.remove("is-valid");
    feedback.textContent = "Ingrese un correo válido. Ejemplo: usuario@dominio.com";
    return { valido: false };
  }

  correoContacto.classList.add("is-valid");
  correoContacto.classList.remove("is-invalid");
  feedback.textContent = "";
  return { valido: true };
}

function validarCategoria() {
  const valor = categoriaContacto.value.trim();
  const feedback = categoriaContacto.nextElementSibling;

  if (valor === "") {
    categoriaContacto.classList.add("is-invalid");
    categoriaContacto.classList.remove("is-valid");
    feedback.textContent = "Debe seleccionar una categoría.";
    return { valido: false };
  }

  categoriaContacto.classList.add("is-valid");
  categoriaContacto.classList.remove("is-invalid");
  feedback.textContent = "";
  return { valido: true };
}

function validarAsunto() {
  const valor = asuntoContacto.value.trim();
  const feedback = asuntoContacto.nextElementSibling;

  if (valor.length === 0) {
    asuntoContacto.classList.add("is-invalid");
    asuntoContacto.classList.remove("is-valid");
    feedback.textContent = "El asunto es requerido.";
    return { valido: false };
  }

  if (valor.length < 5) {
    asuntoContacto.classList.add("is-invalid");
    asuntoContacto.classList.remove("is-valid");
    feedback.textContent = "El asunto debe tener al menos 5 caracteres.";
    return { valido: false };
  }

  asuntoContacto.classList.add("is-valid");
  asuntoContacto.classList.remove("is-invalid");
  feedback.textContent = "";
  return { valido: true };
}

function validarMensaje() {
  const valor = mensajeContacto.value.trim();
  const feedback = mensajeContacto.nextElementSibling;

  if (valor.length === 0) {
    mensajeContacto.classList.add("is-invalid");
    mensajeContacto.classList.remove("is-valid");
    feedback.textContent = "El mensaje es requerido.";
    return { valido: false };
  }

  if (valor.length < 10) {
    mensajeContacto.classList.add("is-invalid");
    mensajeContacto.classList.remove("is-valid");
    feedback.textContent = "El mensaje debe tener al menos 10 caracteres.";
    return { valido: false };
  }

  mensajeContacto.classList.add("is-valid");
  mensajeContacto.classList.remove("is-invalid");
  feedback.textContent = "";
  return { valido: true };
}

// ===== PASO 3: EVENTOS EN TIEMPO REAL =====
[nombreContacto, correoContacto, categoriaContacto, asuntoContacto, mensajeContacto].forEach(campo => {
  campo.addEventListener("input", () => {
    if (campo === nombreContacto) validarNombre();
    if (campo === correoContacto) validarCorreo();
    if (campo === categoriaContacto) validarCategoria();
    if (campo === asuntoContacto) validarAsunto();
    if (campo === mensajeContacto) validarMensaje();
  });
  campo.addEventListener("blur", () => {
    if (campo === nombreContacto) validarNombre();
    if (campo === correoContacto) validarCorreo();
    if (campo === categoriaContacto) validarCategoria();
    if (campo === asuntoContacto) validarAsunto();
    if (campo === mensajeContacto) validarMensaje();
  });
});

// ===== PASO 4: ENVÍO DEL FORMULARIO =====
formularioContacto.addEventListener("submit", async function(e) {
  e.preventDefault();

  const validacionNombre = validarNombre();
  const validacionCorreo = validarCorreo();
  const validacionCategoria = validarCategoria();
  const validacionAsunto = validarAsunto();
  const validacionMensaje = validarMensaje();

  if (!validacionNombre.valido || !validacionCorreo.valido || !validacionCategoria.valido || !validacionAsunto.valido || !validacionMensaje.valido) {
    mensajeError.innerHTML = "<strong>⚠️ Errores en el formulario:</strong><br>Revisa los campos marcados en rojo.";
    modalError.style.display = "flex";
    return;
  }

  const btnEnviar = formularioContacto.querySelector('button[type="submit"]');
  const textoOriginal = btnEnviar.textContent;
  btnEnviar.textContent = "⏳ Enviando...";
  btnEnviar.disabled = true;

  try {
    await new Promise(resolve => setTimeout(resolve, 1500));

    mensajeExito.innerHTML = `
      <strong>✅ ¡Mensaje enviado con éxito!</strong><br>
      <small>Hola <strong>${nombreContacto.value.trim()}</strong>, hemos recibido tu mensaje en la categoría: <em>"${categoriaContacto.value.trim()}"</em> sobre <em>"${asuntoContacto.value.trim()}"</em><br><br>
      Te responderemos pronto a: <strong>${correoContacto.value.trim()}</strong></small>
    `;
    modalExito.style.display = "flex";

    // Crear registro dinámico
    crearRegistro(
      nombreContacto.value.trim(),
      correoContacto.value.trim(),
      categoriaContacto.value.trim(),
      asuntoContacto.value.trim(),
      mensajeContacto.value.trim()
    );

    formularioContacto.reset();
    [nombreContacto, correoContacto, categoriaContacto, asuntoContacto, mensajeContacto].forEach(campo => {
      campo.classList.remove("is-valid", "is-invalid");
    });

  } catch (error) {
    mensajeError.innerHTML = "<strong>❌ Error al enviar el mensaje</strong><br>Por favor, intenta nuevamente.";
    modalError.style.display = "flex";
  } finally {
    btnEnviar.textContent = textoOriginal;
    btnEnviar.disabled = false;
  }

  function crearRegistro(nombre, correo, categoria, asunto, mensaje) {
  const li = document.createElement("li");
  li.className = "list-group-item";

  li.innerHTML = `
    <div class="d-flex justify-content-between align-items-start w-100">
      <div class="me-3">
        <p><strong>👤 Nombre:</strong> ${nombre}</p>
        <p><strong>📧 Correo:</strong> ${correo}</p>
        <p><strong>📂 Categoría:</strong> ${categoria}</p>
        <p><strong>📝 Asunto:</strong> ${asunto}</p>
        <p class="mb-1"><strong>💬 Mensaje:</strong></p>
        <div class="alert alert-secondary p-2" style="white-space: pre-line; max-width: 100%;">
          ${mensaje}
        </div>
      </div>
      <button class="btn btn-sm btn-danger">Eliminar</button>
    </div>
  `;

  li.querySelector("button").addEventListener("click", () => {
    li.remove();
    actualizarContador();
  });

  listaRegistros.appendChild(li);
  actualizarContador();
}
});

// ===== PASO 5: CERRAR MODALES =====
btnAceptarExito.addEventListener("click", () => modalExito.style.display = "none");
btnAceptarError.addEventListener("click", () => modalError.style.display = "none");
modalExito.addEventListener("click", (e) => { if (e.target === modalExito) modalExito.style.display = "none"; });
modalError.addEventListener("click", (e) => { if (e.target === modalError) modalError.style.display = "none"; });

// ===== REGISTROS DINÁMICOS =====
const listaRegistros = document.getElementById("listaRegistros");
const contadorRegistros = document.getElementById("contadorRegistros");

// Función para actualizar el contador
function actualizarContador() {
  contadorRegistros.textContent = listaRegistros.children.length;
}

// Función para crear un registro
function crearRegistro(nombre, correo, asunto, mensaje) {
  const li = document.createElement("li");
  li.className = "list-group-item d-flex justify-content-between align-items-center";

  li.innerHTML = `
    <div>
      <strong>${nombre}</strong> - ${correo}<br>
      <em>${asunto}</em>: ${mensaje}
    </div>
    <button class="btn btn-sm btn-danger">Eliminar</button>
  `;

  // Evento para eliminar registro
  li.querySelector("button").addEventListener("click", () => {
    li.remove();
    actualizarContador();
  });

  listaRegistros.appendChild(li);
  actualizarContador();
}
