// Estado de la aplicación
let materiasCargadas = [];
let materiasAgregadas = [];
const colores = [
    '#667eea', '#4facfe', '#fdcb6e',
    '#43e97b', '#fa709a', '#30cfd0',
    '#a8edea', '#fed6e3', '#c471f5',
    '#ff7675', '#fd79a8', '#ff9f43',
    '#e17055', '#00b894', '#0984e3',
    '#6c5ce7', '#00cec9', '#636e72',

];
let colorIndex = 0;

// Horarios disponibles
let horas = [
    '07:00', '08:00', '09:00', '10:00', '11:00', '12:00',
    '13:00', '14:00', '15:00', '16:00', '17:00', '18:00',
    '19:00', '20:00', '21:00'
];

let diasMap = {
    'L': 1, 'M': 2, 'I': 3, 'J': 4, 'V': 5, 'S': 6
};

// Inicializar el calendario
function inicializarCalendario() {
    const calendario = document.getElementById('calendario');

    horas.forEach((hora, index) => {
        // Celda de hora
        const celdaHora = document.createElement('div');
        celdaHora.className = 'calendar-cell time';
        celdaHora.textContent = hora;
        calendario.appendChild(celdaHora);

        // Celdas para cada día
        for (let dia = 0; dia < 6; dia++) {
            const celda = document.createElement('div');
            celda.className = 'calendar-cell';
            celda.dataset.hora = index + 7; // 7 = 07:00
            celda.dataset.dia = dia + 1;
            calendario.appendChild(celda);
        }
    });
}

// Buscar materias
document.getElementById('btnBuscar').addEventListener('click', buscarMaterias);

async function buscarMaterias() {
    const ciclo = document.getElementById('ciclo').value;
    const centro = document.getElementById('centro').value;
    const carrera = document.getElementById('carrera').value;
    const btn = document.getElementById('btnBuscar');

    if (!centro) {
        Swal.fire({ title: 'Selecciona un centro', icon: 'warning', confirmButtonColor: '#5a67d8' });
        return;
    }

    btn.classList.add('loading');
    btn.disabled = true;

    try {
        const response = await fetch('/api/buscar_materias', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ciclo, centro, carrera })
        });
        const data = await response.json();

        if (data.materias) {
            materiasCargadas = data.materias;
            mostrarMaterias(materiasCargadas);
            document.getElementById('panelMateriasHeader').style.display = 'flex';
        } else {
            Swal.fire({ title: 'Error', text: data.error || 'Error al buscar', icon: 'error', confirmButtonColor: '#5a67d8' });
        }
    } catch (e) {
        Swal.fire({ title: 'Error de conexión', text: e.message, icon: 'error', confirmButtonColor: '#5a67d8' });
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

// Mostrar materias en la lista (agrupadas por materia, secciones expandibles)
function mostrarMaterias(materias) {
    const lista = document.getElementById('listaMaterias');
    lista.innerHTML = '';

    // Agrupar por Clave+Materia (una entrada por materia, múltiples secciones/NRCs)
    const grupos = {};
    materias.forEach(m => {
        const key = `${m.Clave}_${m.Materia}`;
        if (!grupos[key]) {
            grupos[key] = { nombre: m.Materia, clave: m.Clave, secciones: [] };
        }
        // Verificar que este NRC no esté ya agregado al grupo
        if (!grupos[key].secciones.find(s => s.NRC === m.NRC)) {
            const horarios = [];
            if (m.Horas && m.Dias) horarios.push({ dias: m.Dias, horas: m.Horas, edificio: m.Edificio || '', aula: m.Aula || '' });
            grupos[key].secciones.push({ ...m, horarios });
        } else if (m.Horas && m.Dias) {
            // Agregar horario adicional a sección existente
            const sec = grupos[key].secciones.find(s => s.NRC === m.NRC);
            const nuevoH = { dias: m.Dias, horas: m.Horas, edificio: m.Edificio || '', aula: m.Aula || '' };
            const existe = sec.horarios.some(h => h.dias === nuevoH.dias && h.horas === nuevoH.horas);
            if (!existe) sec.horarios.push(nuevoH);
        }
    });

    document.getElementById('totalMaterias').textContent = Object.keys(grupos).length;

    if (Object.keys(grupos).length === 0) {
        lista.innerHTML = '<div class="panel-empty-state"><i class="fas fa-search"></i><p>Sin resultados.</p></div>';
        return;
    }

    Object.values(grupos).forEach(grupo => {
        const row = document.createElement('div');
        row.className = 'materia-row';
        row.dataset.clave = grupo.clave;

        const seccionesHtml = grupo.secciones.map(sec => {
            const yaAgregada = materiasAgregadas.some(m => m.NRC === sec.NRC);
            const horarioTexto = sec.horarios.map(h => `${h.dias} ${h.horas}`).join(' / ') || 'Sin horario';
            const salonTexto = sec.horarios.length > 0 ? `${sec.horarios[0].edificio} ${sec.horarios[0].aula}`.trim() : '';

            let starsHtml = '';
            if (sec.ProfesorRating && sec.ProfesorRating > 0) {
                const r = Math.round(sec.ProfesorRating);
                starsHtml = `<span class="seccion-stars">${'★'.repeat(r)}${'☆'.repeat(5-r)}</span>`;
            }

            return `
                <div class="seccion-item">
                    <div class="seccion-info">
                        <div class="seccion-nrc">NRC ${sec.NRC} · Sec ${sec.Sec}</div>
                        <div class="seccion-profesor">${sec.Profesor}${starsHtml}</div>
                        <div class="seccion-horario">${horarioTexto}${salonTexto ? ' · ' + salonTexto : ''}</div>
                    </div>
                    <button
                        class="btn-anadir${yaAgregada ? ' added' : ''}"
                        data-nrc="${sec.NRC}"
                        ${yaAgregada ? 'disabled' : ''}
                    >${yaAgregada ? '✓ Añadida' : '+ Añadir'}</button>
                </div>
            `;
        }).join('');

        row.innerHTML = `
            <div class="materia-row-header">
                <div class="materia-row-name">${grupo.nombre}</div>
                <div class="materia-row-meta">${grupo.secciones.length} secc.</div>
                <div class="materia-row-chevron">▼</div>
            </div>
            <div class="seccion-list">${seccionesHtml}</div>
        `;

        // Click en header: toggle expand (solo una a la vez)
        row.querySelector('.materia-row-header').addEventListener('click', () => {
            const isExpanded = row.classList.contains('expanded');
            lista.querySelectorAll('.materia-row.expanded').forEach(r => r.classList.remove('expanded'));
            if (!isExpanded) row.classList.add('expanded');
        });

        // Click en botón añadir (event delegation dentro de la row)
        row.addEventListener('click', e => {
            const btn = e.target.closest('.btn-anadir');
            if (!btn || btn.disabled) return;
            e.stopPropagation();
            const nrc = btn.dataset.nrc;
            const seccion = grupo.secciones.find(s => s.NRC === nrc);
            if (seccion) agregarMateriaAlHorario(seccion);
        });

        lista.appendChild(row);
    });
}

// Filtrar materias
document.getElementById('filtroMaterias').addEventListener('input', (e) => {
    const filtro = e.target.value.toLowerCase();
    const filtradas = materiasCargadas.filter(m =>
        m.Materia.toLowerCase().includes(filtro) ||
        m.Profesor.toLowerCase().includes(filtro) ||
        m.NRC.includes(filtro) ||
        m.Clave.toLowerCase().includes(filtro)
    );
    mostrarMaterias(filtradas);
});

// Agregar materia al horario
function agregarMateriaAlHorario(materia) {
    // Verificar conflictos
    const conflicto = obtenerConflicto(materia);
    if (conflicto) {
        mostrarErrorConflicto(materia, conflicto);
        return;
    }

    // Asignar color
    const color = colores[colorIndex % colores.length];
    colorIndex++;

    materia.color = color;
    materiasAgregadas.push(materia);

    // Actualizar vista
    renderizarHorario();
    actualizarLeyenda();
    mostrarMaterias(materiasCargadas);
}

// Obtener información del conflicto
function obtenerConflicto(nuevaMateria) {
    for (const materiaExistente of materiasAgregadas) {
        for (const horarioNuevo of nuevaMateria.horarios) {
            for (const horarioExistente of materiaExistente.horarios) {
                if (hayTraslape(horarioNuevo, horarioExistente)) {
                    return {
                        materiaExistente: materiaExistente,
                        horarioConflicto: horarioExistente
                    };
                }
            }
        }
    }
    return null;
}

// Mostrar error visual de conflicto
function mostrarErrorConflicto(nuevaMateria, conflicto) {
    Swal.fire({
        title: 'Conflicto de Horario',
        html: `
            <div style="text-align: left; margin-top: 10px;">
                <p>La materia <strong>${nuevaMateria.Materia}</strong> tiene conflicto con:</p>
                <div style="margin: 15px 0; padding: 12px; border-left: 5px solid ${conflicto.materiaExistente.color}; background: #f1f5f9; border-radius: 4px;">
                    <div style="font-weight: 600; color: #1e293b;">${conflicto.materiaExistente.Materia}</div>
                    <div style="font-size: 0.85em; color: #64748b; margin-top: 4px;">
                        <i class="fas fa-calendar-alt"></i> ${conflicto.horarioConflicto.dias} 
                        <i class="fas fa-clock" style="margin-left: 8px;"></i> ${conflicto.horarioConflicto.horas}
                    </div>
                </div>
                <p style="font-size: 0.9em; color: #6b7280; border-top: 1px solid #e2e8f0; pt: 10px; margin-top: 15px;">
                    No es posible agregar materias que se traslapen en el mismo horario.
                </p>
            </div>
        `,
        icon: 'error',
        confirmButtonText: 'Entendido',
        confirmButtonColor: '#667eea',
        customClass: {
            container: 'planner-swal-container',
            popup: 'planner-swal-popup'
        }
    });
}

// Cerrar modal (mantenido por compatibilidad si se usa en otros lados, aunque ahora usamos Swal)
function cerrarModal() {
    const modal = document.getElementById('conflictoModal');
    if (modal) {
        modal.classList.add('modal-closing');
        setTimeout(() => modal.remove(), 200);
    }
}

// Verificar traslape de horarios
function hayTraslape(h1, h2) {
    // Verificar si comparten días
    const dias1 = parseDias(h1.dias);
    const dias2 = parseDias(h2.dias);

    const diasComunes = dias1.filter(d => dias2.includes(d));
    if (diasComunes.length === 0) return false;

    // Verificar si las horas se traslapan
    const [inicio1, fin1] = parseHoras(h1.horas);
    const [inicio2, fin2] = parseHoras(h2.horas);

    if (!inicio1 || !inicio2) return false;

    return (inicio1 < fin2) && (fin1 > inicio2);
}

// Parsear días (ej: ". M . J . ." -> [2, 4])
function parseDias(diasStr) {
    const dias = [];
    const partes = diasStr.split(' ');
    const letras = ['L', 'M', 'I', 'J', 'V', 'S'];

    partes.forEach((parte, idx) => {
        if (parte !== '.' && letras[idx]) {
            dias.push(diasMap[letras[idx]]);
        }
    });

    return dias;
}

// Parsear horas (ej: "0700-0800" -> [7, 8])
function parseHoras(horasStr) {
    if (!horasStr) return [null, null];

    const partes = horasStr.replace(/\s/g, '').split('-');
    if (partes.length !== 2) return [null, null];

    const inicio = parseInt(partes[0]) / 100;
    const fin = parseInt(partes[1]) / 100;

    return [inicio, fin];
}

// Renderizar el horario en el calendario
function renderizarHorario() {
    // Limpiar clases existentes
    document.querySelectorAll('.clase-block').forEach(el => el.remove());

    // Agregar cada materia
    materiasAgregadas.forEach(materia => {
        materia.horarios.forEach(horario => {
            const dias = parseDias(horario.dias);
            const [horaInicio, horaFin] = parseHoras(horario.horas);

            if (!horaInicio || !horaFin) return;

            dias.forEach(dia => {
                // Calcular posición
                const duracion = horaFin - horaInicio;
                const inicioIndex = horaInicio - 7; // 7 es la primera hora (07:00)

                // Encontrar la celda correspondiente
                const celda = document.querySelector(
                    `.calendar-cell[data-hora="${Math.floor(horaInicio)}"][data-dia="${dia}"]`
                );

                if (celda) {
                    const bloque = document.createElement('div');
                    bloque.className = 'clase-block';
                    bloque.style.backgroundColor = materia.color;
                    bloque.style.height = `${duracion * 60}px`;

                    bloque.innerHTML = `
                        <div class="clase-nombre">${materia.Materia.substring(0, 25)}</div>
                        <div class="clase-info">${horario.horas}</div>
                        <div class="clase-info">${horario.edificio} ${horario.aula}</div>
                        <button class="clase-remove" onclick="removerMateria('${materia.NRC}')">×</button>
                    `;

                    celda.appendChild(bloque);
                }
            });
        });
    });
}

// Remover materia del horario
function removerMateria(nrc) {
    materiasAgregadas = materiasAgregadas.filter(m => m.NRC !== nrc);
    renderizarHorario();
    actualizarLeyenda();
    mostrarMaterias(materiasCargadas);
}

// Actualizar leyenda
function actualizarLeyenda() {
    const legendItems = document.getElementById('legendItems');

    if (materiasAgregadas.length === 0) {
        legendItems.innerHTML = '<p class="empty-message">No hay materias agregadas aún</p>';
        return;
    }

    legendItems.innerHTML = '';
    materiasAgregadas.forEach(materia => {
        const item = document.createElement('div');
        item.className = 'legend-item';
        item.innerHTML = `
            <div class="legend-color" style="background-color: ${materia.color}"></div>
            <div class="legend-text">${materia.Materia} (${materia.NRC})</div>
            <button class="legend-remove" onclick="removerMateria('${materia.NRC}')" title="Eliminar materia">×</button>
        `;
        legendItems.appendChild(item);
    });
}

// Limpiar horario
document.getElementById('btnLimpiarHorario').addEventListener('click', () => {
    Swal.fire({
        title: '¿Limpiar todo el horario?',
        text: "Se eliminarán todas las materias que has agregado hasta ahora.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444',
        cancelButtonColor: '#64748b',
        confirmButtonText: 'Sí, limpiar todo',
        cancelButtonText: 'Cancelar',
        reverseButtons: true
    }).then((result) => {
        if (result.isConfirmed) {
            materiasAgregadas = [];
            colorIndex = 0;
            renderizarHorario();
            actualizarLeyenda();
            mostrarMaterias(materiasCargadas);

            Swal.fire({
                title: '¡Limpiado!',
                text: 'Tu horario está vacío de nuevo.',
                icon: 'success',
                timer: 1500,
                showConfirmButton: false
            });
        }
    });
});

// Guardar horario a la base de datos
document.addEventListener('DOMContentLoaded', () => {
    const btnGuardarHorario = document.getElementById('btnGuardarHorario');
    if (btnGuardarHorario) {
        btnGuardarHorario.addEventListener('click', guardarHorario);
    }
});

function guardarHorario() {
    const nombreInput = document.getElementById('nombreHorario');
    const nombre = nombreInput.value.trim() || 'Mi horario';

    if (materiasAgregadas.length === 0) {
        alert('No hay materias en el horario. Agrega materias antes de guardar.');
        return;
    }

    // Serializar el horario
    const horarioData = {
        nombre: nombre,
        materias: materiasAgregadas,
        fecha_creacion: new Date().toISOString()
    };

    // Enviar a la ruta de crear horario
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/schedules/create';

    const nameInput = document.createElement('input');
    nameInput.type = 'hidden';
    nameInput.name = 'name';
    nameInput.value = nombre;

    const dataInput = document.createElement('input');
    dataInput.type = 'hidden';
    dataInput.name = 'data';
    dataInput.value = JSON.stringify(horarioData);

    form.appendChild(nameInput);
    form.appendChild(dataInput);
    document.body.appendChild(form);

    console.log('Guardando horario:', horarioData);
    form.submit();
}

// Inicializar al cargar la página
window.addEventListener('DOMContentLoaded', () => {
    inicializarCalendario();
});
