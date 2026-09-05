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
        
        function validarNombre() {
            const val = nombreContacto.value.trim();
            const esValido = val.length >= 3;
            if (esValido) {
                nombreContacto.classList.remove('is-invalid');
                nombreContacto.classList.add('is-valid');
            } else {
                nombreContacto.classList.remove('is-valid');
                nombreContacto.classList.add('is-invalid');
            }
            return esValido;
        }

        function validarCorreo() {
            const val = correoContacto.value.trim();
            const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            const esValido = regex.test(val);
            if (esValido) {
                correoContacto.classList.remove('is-invalid');
                correoContacto.classList.add('is-valid');
            } else {
                correoContacto.classList.remove('is-valid');
                correoContacto.classList.add('is-invalid');
            }
            return esValido;
        }

        function validarCategoria() {
            const val = categoriaContacto.value.trim();
            const esValido = val !== '';
            if (esValido) {
                categoriaContacto.classList.remove('is-invalid');
                categoriaContacto.classList.add('is-valid');
            } else {
                categoriaContacto.classList.remove('is-valid');
                categoriaContacto.classList.add('is-invalid');
            }
            return esValido;
        }

        function validarAsunto() {
            const val = asuntoContacto.value.trim();
            const esValido = val.length >= 5;
            if (esValido) {
                asuntoContacto.classList.remove('is-invalid');
                asuntoContacto.classList.add('is-valid');
            } else {
                asuntoContacto.classList.remove('is-valid');
                asuntoContacto.classList.add('is-invalid');
            }
            return esValido;
        }

        function validarMensaje() {
            const val = mensajeContacto.value.trim();
            const esValido = val.length >= 10;
            if (esValido) {
                mensajeContacto.classList.remove('is-invalid');
                mensajeContacto.classList.add('is-valid');
            } else {
                mensajeContacto.classList.remove('is-valid');
                mensajeContacto.classList.add('is-invalid');
            }
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
});
