/**
 * ==============================================================================
 * DULCE DELICIA - SCRIPT PRINCIPAL DE INTERACTIVIDAD Y FORMULARIOS
 * Avance 11/16 - Validación de Formularios con Flask-WTF y WTForms
 * ==============================================================================
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Auto-cierre suave de alertas Flash después de 6 segundos
    const flashAlerts = document.querySelectorAll('.alert-flash');
    flashAlerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 6000);
    });

    // 2. Asistente dinámico de cálculo de IVA (15% Ecuador) y Total en Facturación
    const inputSubtotal = document.getElementById('factura_subtotal');
    const inputIva = document.getElementById('factura_iva');
    const inputTotal = document.getElementById('factura_total');

    if (inputSubtotal && inputIva && inputTotal) {
        inputSubtotal.addEventListener('input', () => {
            const subtotalVal = parseFloat(inputSubtotal.value);
            if (!isNaN(subtotalVal) && subtotalVal > 0) {
                const ivaCalculado = (subtotalVal * 0.15);
                const totalCalculado = subtotalVal + ivaCalculado;
                inputIva.value = ivaCalculado.toFixed(2);
                inputTotal.value = totalCalculado.toFixed(2);
            }
        });

        inputIva.addEventListener('input', () => {
            const subtotalVal = parseFloat(inputSubtotal.value) || 0;
            const ivaVal = parseFloat(inputIva.value) || 0;
            inputTotal.value = (subtotalVal + ivaVal).toFixed(2);
        });
    }

    // 3. Validación en tiempo real del Formulario de Contacto (Landing Page)
    const formContacto = document.getElementById('formContacto');
    const nombreContacto = document.getElementById('nombreContacto');
    const correoContacto = document.getElementById('correoContacto');
    const categoriaContacto = document.getElementById('categoriaContacto');
    const asuntoContacto = document.getElementById('asuntoContacto');
    const mensajeContacto = document.getElementById('mensajeContacto');

    const modalExito = document.getElementById('modalExito');
    const mensajeExito = document.getElementById('mensajeExito');
    const btnAceptarExito = document.getElementById('btnAceptarExito');

    const modalError = document.getElementById('modalError');
    const mensajeError = document.getElementById('mensajeError');
    const btnAceptarError = document.getElementById('btnAceptarError');

    const listaRegistros = document.getElementById('listaRegistros');
    const contadorRegistros = document.getElementById('contadorRegistros');

    if (formContacto && nombreContacto && correoContacto && categoriaContacto && asuntoContacto && mensajeContacto) {
        const camposContacto = [nombreContacto, correoContacto, categoriaContacto, asuntoContacto, mensajeContacto];

        camposContacto.forEach((campo) => {
            campo.required = true;
            campo.parentElement.querySelectorAll('.form-help-text, .invalid-feedback').forEach((elemento) => elemento.remove());
        });

        function feedbackContacto(campo) {
            let feedback = campo.parentElement.querySelector('.contacto-feedback');
            if (!feedback) {
                feedback = document.createElement('div');
                feedback.className = 'contacto-feedback invalid-feedback';
                feedback.setAttribute('aria-live', 'polite');
                campo.parentElement.appendChild(feedback);
            }
            return feedback;
        }

        function estadoContacto(campo, esValido, mensaje) {
            const feedback = feedbackContacto(campo);
            campo.setAttribute('aria-invalid', String(!esValido));
            campo.classList.toggle('is-valid', esValido);
            campo.classList.toggle('is-invalid', !esValido);
            feedback.textContent = mensaje;
            feedback.style.display = esValido ? 'none' : 'block';
        }
        
        function validarNombre() {
            const val = nombreContacto.value.trim();
            const esValido = val.length >= 3 && /^[A-Za-zÁÉÍÓÚáéíóúñÑ\s]+$/.test(val);
            estadoContacto(nombreContacto, esValido, 'Escribe un nombre de al menos 3 letras.');
            return esValido;
        }

        function validarCorreo() {
            const val = correoContacto.value.trim();
            const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            const esValido = regex.test(val);
            estadoContacto(correoContacto, esValido, 'Ingresa un correo válido. Ejemplo: usuario@dominio.com');
            return esValido;
        }

        function validarCategoria() {
            const val = categoriaContacto.value.trim();
            const esValido = val !== '';
            estadoContacto(categoriaContacto, esValido, 'Selecciona una categoría.');
            return esValido;
        }

        function validarAsunto() {
            const val = asuntoContacto.value.trim();
            const esValido = val.length >= 5;
            estadoContacto(asuntoContacto, esValido, 'El asunto debe tener al menos 5 caracteres.');
            return esValido;
        }

        function validarMensaje() {
            const val = mensajeContacto.value.trim();
            const esValido = val.length >= 10;
            estadoContacto(mensajeContacto, esValido, 'El mensaje debe tener al menos 10 caracteres.');
            return esValido;
        }

        // Listeners para advertencias en tiempo real
        nombreContacto.addEventListener('input', validarNombre);
        correoContacto.addEventListener('input', validarCorreo);
        categoriaContacto.addEventListener('change', validarCategoria);
        asuntoContacto.addEventListener('input', validarAsunto);
        mensajeContacto.addEventListener('input', validarMensaje);

        nombreContacto.addEventListener('blur', validarNombre);
        correoContacto.addEventListener('blur', validarCorreo);
        categoriaContacto.addEventListener('blur', validarCategoria);
        asuntoContacto.addEventListener('blur', validarAsunto);
        mensajeContacto.addEventListener('blur', validarMensaje);

        function actualizarContador() {
            if (contadorRegistros && listaRegistros) {
                contadorRegistros.textContent = listaRegistros.children.length;
            }
        }

        function agregarRegistro(nombre, correo, categoria, asunto, mensaje) {
            if (!listaRegistros) return;
            const li = document.createElement('li');
            li.className = 'list-group-item p-3';
            li.innerHTML = `
                <div class="d-flex justify-content-between align-items-start gap-2">
                    <div>
                        <div class="d-flex align-items-center gap-2 mb-1">
                            <span class="badge badge-artesanal badge-moka">${categoria}</span>
                            <strong class="text-dark">${nombre}</strong>
                            <small class="text-muted">(${correo})</small>
                        </div>
                        <p class="mb-1 text-secondary small"><strong>Asunto:</strong> ${asunto}</p>
                        <p class="mb-0 text-muted small bg-light p-2 rounded">${mensaje}</p>
                    </div>
                    <button type="button" class="btn btn-sm btn-outline-danger rounded-pill" title="Eliminar registro">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </div>
            `;
            li.querySelector('button').addEventListener('click', () => {
                li.remove();
                actualizarContador();
            });
            listaRegistros.prepend(li);
            actualizarContador();
        }

        formContacto.addEventListener('submit', async (e) => {
            e.preventDefault();

            const v1 = validarNombre();
            const v2 = validarCorreo();
            const v3 = validarCategoria();
            const v4 = validarAsunto();
            const v5 = validarMensaje();

            if (!v1 || !v2 || !v3 || !v4 || !v5) {
                if (mensajeError && modalError) {
                    mensajeError.innerHTML = `
                        <h3 class="text-danger fw-bold mb-2">Campos Incompletos</h3>
                        <p>Por favor revisa los campos marcados en rojo y cumple con los requisitos de longitud.</p>
                    `;
                    modalError.style.display = 'flex';
                }
                return;
            }

            const btnSubmit = formContacto.querySelector('button[type="submit"]');
            const textoOriginal = btnSubmit.innerHTML;
            btnSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i> Enviando...';
            btnSubmit.disabled = true;

            try {
                await new Promise(resolve => setTimeout(resolve, 800));

                const nombreVal = nombreContacto.value.trim();
                const correoVal = correoContacto.value.trim();
                const catVal = categoriaContacto.value;
                const asuntoVal = asuntoContacto.value.trim();
                const mensajeVal = mensajeContacto.value.trim();

                agregarRegistro(nombreVal, correoVal, catVal, asuntoVal, mensajeVal);

                if (mensajeExito && modalExito) {
                    mensajeExito.innerHTML = `
                        <h3 class="text-success fw-bold mb-2">¡Mensaje Enviado con Éxito!</h3>
                        <p class="mb-1">Gracias <strong>${nombreVal}</strong>, hemos recibido tu consulta sobre <em>"${asuntoVal}"</em>.</p>
                        <p class="small text-muted">Te responderemos a <strong>${correoVal}</strong> a la brevedad posible.</p>
                    `;
                    modalExito.style.display = 'flex';
                }

                formContacto.reset();
                [nombreContacto, correoContacto, categoriaContacto, asuntoContacto, mensajeContacto].forEach(c => {
                    c.classList.remove('is-valid', 'is-invalid');
                });

            } catch (err) {
                if (mensajeError && modalError) {
                    mensajeError.innerHTML = `
                        <h3 class="text-danger fw-bold mb-2">Error al Enviar</h3>
                        <p>Ocurrió un error inesperado al procesar el envío. Por favor, intenta de nuevo.</p>
                    `;
                    modalError.style.display = 'flex';
                }
            } finally {
                btnSubmit.innerHTML = textoOriginal;
                btnSubmit.disabled = false;
            }
        });

        // Eventos para cerrar los modales
        if (btnAceptarExito && modalExito) {
            btnAceptarExito.addEventListener('click', () => { modalExito.style.display = 'none'; });
            modalExito.addEventListener('click', (e) => { if (e.target === modalExito) modalExito.style.display = 'none'; });
        }
        if (btnAceptarError && modalError) {
            btnAceptarError.addEventListener('click', () => { modalError.style.display = 'none'; });
            modalError.addEventListener('click', (e) => { if (e.target === modalError) modalError.style.display = 'none'; });
        }
    }

    // 4. Validación dinámica general para formularios del sistema: producto, cliente, proveedor y factura
    const formsSistema = document.querySelectorAll('form[method="POST"]');

    function getFieldFeedback(field) {
        if (!field) return null;

        let feedback = field.parentElement.querySelector('.field-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.className = 'field-feedback invalid-feedback d-block';
            feedback.setAttribute('aria-live', 'polite');
            field.parentElement.appendChild(feedback);
        }

        return feedback;
    }

    function setFieldState(field, isValid, message = '') {
        if (!field) return;

        field.setAttribute('aria-invalid', String(!isValid));
        const feedback = getFieldFeedback(field);

        if (!feedback) return;
        feedback.textContent = message;

        if (isValid) {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');
            feedback.classList.remove('d-block');
            feedback.style.display = 'none';
        } else {
            field.classList.remove('is-valid');
            field.classList.add('is-invalid');
            feedback.classList.add('d-block');
            feedback.style.display = 'block';
        }
    }

    function normalizarNumero(valor) {
        if (valor === null || valor === undefined) return NaN;
        return Number(String(valor).replace(/[^0-9.-]/g, ''));
    }

    function validarCampoPorNombre(field, valor) {
        if (!field || !field.name && !field.id) return true;

        const nombre = (field.name || field.id || '').toLowerCase();
        const texto = String(valor ?? '').trim();

        if (!texto && (field.required || nombre.includes('codigo') || nombre.includes('nombre') || nombre.includes('correo') || nombre.includes('telefono') || nombre.includes('direccion') || nombre.includes('numero') || nombre.includes('subtotal') || nombre.includes('iva') || nombre.includes('total') || nombre.includes('contacto') || nombre.includes('ruc') || nombre.includes('razon') || nombre.includes('stock') || nombre.includes('descripcion') || nombre.includes('precio') || nombre.includes('fecha'))) {
            return { valido: false, mensaje: 'Este campo es obligatorio.' };
        }

        if (nombre.includes('codigo')) {
            const ok = /^[A-Z0-9-]{3,20}$/.test(texto);
            return { valido: ok, mensaje: 'Usa entre 3 y 20 caracteres con letras, números y guiones. Ej. TOR-001.' };
        }

        if (nombre.includes('nombre') || nombre.includes('razon_social') || nombre.includes('contacto')) {
            const ok = texto.length >= 3 && texto.length <= 120;
            return { valido: ok, mensaje: 'Debe tener entre 3 y 120 caracteres.' };
        }

        if (nombre.includes('cedula') || nombre.includes('ruc')) {
            const ok = /^\d{10,13}$/.test(texto);
            return { valido: ok, mensaje: 'Debe contener solo números: 10 para cédula y 13 para RUC.' };
        }

        if (nombre.includes('correo')) {
            const ok = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(texto);
            return { valido: ok, mensaje: 'Ingresa un correo válido. Ejemplo: usuario@dominio.com' };
        }

        if (nombre.includes('telefono')) {
            const ok = /^\d{9,15}$/.test(texto);
            return { valido: ok, mensaje: 'El teléfono debe tener entre 9 y 15 dígitos numéricos.' };
        }

        if (nombre.includes('direccion')) {
            const ok = texto.length >= 5 && texto.length <= 200;
            return { valido: ok, mensaje: 'La dirección debe tener entre 5 y 200 caracteres.' };
        }

        if (nombre.includes('descripcion')) {
            const ok = texto.length >= 10 && texto.length <= 250;
            return { valido: ok, mensaje: 'La descripción debe tener entre 10 y 250 caracteres.' };
        }

        if (nombre.includes('precio') || nombre.includes('subtotal') || nombre.includes('iva') || nombre.includes('total')) {
            const valorNum = normalizarNumero(texto);
            const ok = !Number.isNaN(valorNum) && valorNum > 0;
            return { valido: ok, mensaje: 'Ingresa un valor numérico válido mayor que cero.' };
        }

        if (nombre.includes('stock')) {
            const valorNum = normalizarNumero(texto);
            const ok = !Number.isNaN(valorNum) && valorNum >= 0;
            return { valido: ok, mensaje: 'El stock debe ser un número mayor o igual a cero.' };
        }

        if (nombre.includes('numero') && !nombre.includes('telefono')) {
            const ok = /^[A-Z0-9-]{5,30}$/.test(texto);
            return { valido: ok, mensaje: 'Usa letras mayúsculas, números y guiones. Ej. FAC-001.' };
        }

        if (nombre.includes('fecha')) {
            const ok = texto.length >= 8;
            return { valido: ok, mensaje: 'Selecciona una fecha válida.' };
        }

        if (nombre.includes('imagen') && !field.required) {
            return { valido: true, mensaje: '' };
        }

        if (nombre.includes('categoria') || nombre.includes('metodo') || nombre.includes('estado') || nombre.includes('tipo') || nombre.includes('unidad') || (nombre.includes('imagen') && field.type !== 'file')) {
            const ok = texto !== '';
            return { valido: ok, mensaje: 'Debes seleccionar una opción válida.' };
        }

        return { valido: true, mensaje: '' };
    }

    function activarValidacionFormulario(form) {
        const elementos = Array.from(form.querySelectorAll('input, select, textarea'));
        form.querySelectorAll('.form-help-text, .invalid-feedback').forEach((elemento) => elemento.remove());
        const campos = elementos.filter(el => {
            const nombre = (el.name || el.id || '').toLowerCase();
            return nombre && (nombre.includes('codigo') || nombre.includes('nombre') || nombre.includes('cedula') || nombre.includes('correo') || nombre.includes('telefono') || nombre.includes('direccion') || nombre.includes('ruc') || nombre.includes('contacto') || nombre.includes('numero') || nombre.includes('precio') || nombre.includes('subtotal') || nombre.includes('iva') || nombre.includes('total') || nombre.includes('stock') || nombre.includes('descripcion') || nombre.includes('categoria') || nombre.includes('estado') || nombre.includes('metodo') || nombre.includes('tipo') || nombre.includes('unidad') || nombre.includes('fecha') || nombre.includes('imagen'));
        });

        if (!campos.length) return;

        let alertaGeneral = form.querySelector('.alerta-form-general');
        if (!alertaGeneral) {
            alertaGeneral = document.createElement('div');
            alertaGeneral.className = 'alerta-form-general alert alert-danger mt-2 mb-3 d-none';
            alertaGeneral.setAttribute('role', 'alert');
            alertaGeneral.innerHTML = '<strong>Faltan campos por completar.</strong>';
            form.insertBefore(alertaGeneral, form.firstChild);
        }

        function actualizarAlertaGeneral() {
            const invalidos = campos.filter((campo) => {
                const resultado = validarCampoPorNombre(campo, campo.value);
                return !resultado.valido;
            });

            if (invalidos.length > 0) {
                alertaGeneral.classList.remove('d-none');
                alertaGeneral.innerHTML = '<strong>Faltan ' + invalidos.length + ' campos por completar.</strong> Revisa los campos marcados.';
            } else {
                alertaGeneral.classList.add('d-none');
                alertaGeneral.innerHTML = '';
            }
        }

        campos.forEach((campo) => {
            const validar = () => {
                const resultado = validarCampoPorNombre(campo, campo.value);
                setFieldState(campo, resultado.valido, resultado.mensaje);
                actualizarAlertaGeneral();
                return resultado.valido;
            };

            campo.addEventListener('input', validar);
            campo.addEventListener('change', validar);
            campo.addEventListener('blur', validar);
        });

        form.addEventListener('submit', (event) => {
            let hayErrores = false;
            let contador = 0;

            campos.forEach((campo) => {
                const resultado = validarCampoPorNombre(campo, campo.value);
                setFieldState(campo, resultado.valido, resultado.mensaje);
                if (!resultado.valido) {
                    hayErrores = true;
                    contador += 1;
                }
            });

            actualizarAlertaGeneral();

            if (hayErrores) {
                event.preventDefault();
                alertaGeneral.classList.remove('d-none');
                alertaGeneral.innerHTML = '<strong>Faltan ' + contador + ' campos por completar.</strong> Corrige los errores antes de continuar.';
                const boton = form.querySelector('button[type="submit"]');
                if (boton) {
                    boton.disabled = true;
                    const textoOriginal = boton.textContent;
                    boton.textContent = 'Corrige los campos';
                    setTimeout(() => {
                        boton.textContent = textoOriginal;
                        boton.disabled = false;
                    }, 1500);
                }
                return;
            }

            const boton = form.querySelector('button[type="submit"]');
            if (boton) {
                const textoOriginal = boton.textContent;
                boton.disabled = true;
                boton.textContent = 'Guardando...';
                setTimeout(() => {
                    boton.textContent = textoOriginal;
                    boton.disabled = false;
                }, 1200);
            }
        });
    }

    formsSistema.forEach((form) => {
        if (form.id && form.id.includes('formContacto')) return;
        const nombreForm = (form.id || form.action || '').toLowerCase();
        if (nombreForm.includes('contacto')) return;
        activarValidacionFormulario(form);
    });
});
