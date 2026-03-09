function showExamStudentsNotice(message, type = 'success') {
  if (!examStudentsNotice) return;
  examStudentsNotice.textContent = message;
  examStudentsNotice.classList.remove('hidden');
  if (type === 'error') {
    examStudentsNotice.classList.add('inline-notice-error');
  } else {
    examStudentsNotice.classList.remove('inline-notice-error');
  }
  setTimeout(() => {
    examStudentsNotice.classList.add('hidden');
  }, 3000);
}
// Navegación entre secciones
const sections = document.querySelectorAll('.section');
const navButtons = document.querySelectorAll('.bottom-nav-item');

navButtons.forEach((btn) => {
  btn.addEventListener('click', () => {
    const targetId = btn.getAttribute('data-target');
    if (!targetId) return;

    sections.forEach((s) => s.classList.remove('section-active'));
    document.getElementById(targetId)?.classList.add('section-active');

    navButtons.forEach((b) => b.classList.remove('bottom-nav-item-active'));
    btn.classList.add('bottom-nav-item-active');
  });
});

// Helpers API
async function apiGet(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error('Error GET ' + url);
  return res.json();
}

function renderGenericCalendar(targetCalendarEl, selectedDateRef, ymRef, onSelect) {
  if (!targetCalendarEl) return;
  const { year, month } = ymRef.value;
  const firstDay = new Date(year, month, 1);
  const startWeekday = firstDay.getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const monthNames = [
    'Enero','Febrero','Marzo','Abril','Mayo','Junio',
    'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre',
  ];

  const wrapper = document.createElement('div');
  const header = document.createElement('div');
  header.className = 'exam-inline-calendar-header';

  const prevBtn = document.createElement('button');
  prevBtn.type = 'button';
  prevBtn.className = 'btn-icon';
  prevBtn.textContent = '<';
  prevBtn.addEventListener('click', () => {
    console.log('calendar prev month click');
    ymRef.value.month -= 1;
    if (ymRef.value.month < 0) {
      ymRef.value.month = 11;
      ymRef.value.year -= 1;
    }
    renderGenericCalendar(targetCalendarEl, selectedDateRef, ymRef, onSelect);
  });

  const label = document.createElement('div');
  label.className = 'exam-inline-calendar-month';
  label.textContent = `${monthNames[month]} ${year}`;

  const nextBtn = document.createElement('button');
  nextBtn.type = 'button';
  nextBtn.className = 'btn-icon';
  nextBtn.textContent = '>';
  nextBtn.addEventListener('click', () => {
    console.log('calendar next month click');
    ymRef.value.month += 1;
    if (ymRef.value.month > 11) {
      ymRef.value.month = 0;
      ymRef.value.year += 1;
    }
    renderGenericCalendar(targetCalendarEl, selectedDateRef, ymRef, onSelect);
  });

  header.appendChild(prevBtn);
  header.appendChild(label);
  header.appendChild(nextBtn);

  const grid = document.createElement('div');
  grid.className = 'exam-inline-calendar-grid';

  ['D', 'L', 'M', 'M', 'J', 'V', 'S'].forEach((d) => {
    const cell = document.createElement('div');
    cell.className = 'exam-inline-calendar-cell exam-inline-header';
    cell.textContent = d;
    grid.appendChild(cell);
  });

  for (let i = 0; i < startWeekday; i++) {
    const empty = document.createElement('div');
    empty.className = 'exam-inline-calendar-cell';
    grid.appendChild(empty);
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(
      today.getDate(),
    ).padStart(2, '0')}`;
    const cell = document.createElement('div');
    cell.className = 'exam-inline-calendar-cell exam-inline-day';
    cell.textContent = String(day);

    if (selectedDateRef.value === dateStr) {
      cell.classList.add('exam-inline-selected');
    }

    cell.addEventListener('click', () => {
      selectedDateRef.value = dateStr;
      onSelect(dateStr);
      renderGenericCalendar(targetCalendarEl, selectedDateRef, ymRef, onSelect);
    });

    grid.appendChild(cell);
  }

  wrapper.appendChild(header);
  wrapper.appendChild(grid);

  targetCalendarEl.innerHTML = '';
  targetCalendarEl.appendChild(wrapper);
}

async function apiSend(url, method, body) {
  const res = await fetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  // Manejo especial: en DELETE, si el recurso ya no existe (404),
  // lo consideramos como caso "ok" para evitar errores molestos en consola.
  if (!res.ok) {
    if (method === 'DELETE' && res.status === 404) {
      return null;
    }

    let errorMessage = 'Error ' + method + ' ' + url;
    try {
      const data = await res.json();
      if (data && data.error) {
        errorMessage = data.error;
      }
    } catch (e) {
      // ignoramos errores al parsear el cuerpo de error
    }

    throw new Error(errorMessage);
  }
  return res.status === 204 ? null : res.json();
}

// --- Alumnos ---

let studentsCache = [];

const studentsTbody = document.getElementById('students-tbody');
const studentsEmptyState = document.getElementById('students-empty-state');
const studentsBeltFilter = document.getElementById('students-belt-filter');
const studentsStatusFilter = document.getElementById('students-status-filter');
const btnOpenCreateStudent = document.getElementById('btn-open-create-student');
const modalStudent = document.getElementById('modal-student');
const btnCloseStudent = document.getElementById('btn-close-student');
const btnCancelStudent = document.getElementById('btn-cancel-student');
const studentForm = document.getElementById('student-form');
const studentIdInput = document.getElementById('student-id');
const modalStudentTitle = document.getElementById('modal-student-title');
const studentBirthdateDisplay = document.getElementById('student-birthdate-display');
const studentBirthdatePopover = document.getElementById('student-birthdate-popover');
const studentBirthdateCalendarEl = document.getElementById('student-birthdate-calendar');

// Modal legajo de alumno (solo lectura)
const modalStudentRecord = document.getElementById('modal-student-record');
const btnCloseStudentRecord = document.getElementById('btn-close-student-record');
const btnCloseStudentRecordFooter = document.getElementById('btn-close-student-record-footer');
const recordFullName = document.getElementById('record-full-name');
const recordDni = document.getElementById('record-dni');
const recordAge = document.getElementById('record-age');
const recordBirthdate = document.getElementById('record-birthdate');
const recordGender = document.getElementById('record-gender');
const recordBlood = document.getElementById('record-blood');
const recordBelt = document.getElementById('record-belt');
const recordNationality = document.getElementById('record-nationality');
const recordLocation = document.getElementById('record-location');
const recordAddress = document.getElementById('record-address');
const recordSchool = document.getElementById('record-school');
const recordFatherName = document.getElementById('record-father-name');
const recordFatherPhone = document.getElementById('record-father-phone');
const recordMotherName = document.getElementById('record-mother-name');
const recordMotherPhone = document.getElementById('record-mother-phone');
const recordParentEmail = document.getElementById('record-parent-email');

// Modal de eliminación de alumno
const modalStudentDelete = document.getElementById('modal-student-delete');
const btnCloseStudentDelete = document.getElementById('btn-close-student-delete');
const btnCancelStudentDelete = document.getElementById('btn-cancel-student-delete');
const btnConfirmStudentDelete = document.getElementById('btn-confirm-student-delete');
const studentDeleteMessage = document.getElementById('student-delete-message');

// Modal de promoción de alumno
const modalStudentPromote = document.getElementById('modal-student-promote');
const btnCloseStudentPromote = document.getElementById('btn-close-student-promote');
const btnCancelStudentPromote = document.getElementById('btn-cancel-student-promote');
const btnConfirmStudentPromote = document.getElementById('btn-confirm-student-promote');
const studentPromoteMessage = document.getElementById('student-promote-message');

// Menú emergente reutilizable para acciones de alumno
let studentActionsMenu = null;
let currentStudentForMenu = null;
let pendingDeleteStudent = null;
let pendingPromoteStudent = null;

function closeStudentActionsMenu() {
  if (studentActionsMenu) {
    studentActionsMenu.remove();
    studentActionsMenu = null;
  }
}

function formatBeltLabel(belt) {
  if (!belt) return '-';
  return belt.charAt(0).toUpperCase() + belt.slice(1);
}

function openStudentRecord(student) {
  const name = student.full_name || `${student.last_name || ''} ${student.first_name || ''}`;
  if (recordFullName) recordFullName.textContent = name.trim() || '-';
  if (recordDni) recordDni.textContent = student.dni || '-';

  let ageText = '-';
  if (student.birthdate) {
    const age = calcAge(student.birthdate);
    if (age !== '') ageText = `${age} años`;
  }
  if (recordAge) recordAge.textContent = ageText;

  if (recordBirthdate) recordBirthdate.textContent = student.birthdate || '-';
  if (recordGender) recordGender.textContent = student.gender || '-';
  if (recordBlood) recordBlood.textContent = student.blood || '-';
  if (recordBelt) recordBelt.textContent = formatBeltLabel(student.belt || '');
  if (recordNationality) recordNationality.textContent = student.nationality || '-';

  const locParts = [student.city, student.province, student.country].filter(Boolean);
  if (recordLocation) recordLocation.textContent = locParts.join(' · ') || '-';

  const addressParts = [student.address, student.zip].filter(Boolean);
  if (recordAddress) recordAddress.textContent = addressParts.join(' · ') || '-';

  if (recordSchool) recordSchool.textContent = student.school || '-';
  if (recordFatherName) recordFatherName.textContent = student.father_name || '-';
  if (recordFatherPhone) recordFatherPhone.textContent = student.father_phone || '-';
  if (recordMotherName) recordMotherName.textContent = student.mother_name || '-';
  if (recordMotherPhone) recordMotherPhone.textContent = student.mother_phone || '-';
  if (recordParentEmail) recordParentEmail.textContent = student.parent_email || '-';

  modalStudentRecord?.classList.remove('hidden');
}

function openStudentActionsMenu(triggerBtn, student) {
  closeStudentActionsMenu();

  currentStudentForMenu = student;

  const menu = document.createElement('div');
  menu.className = 'students-actions-menu';

  const makeItem = (label, onClick, extraClass) => {
    const item = document.createElement('div');
    item.className = 'students-actions-menu-item' + (extraClass ? ' ' + extraClass : '');
    item.textContent = label;
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      closeStudentActionsMenu();
      onClick();
    });
    return item;
  };

  menu.appendChild(
    makeItem('Ver legajo', () => {
      openStudentRecord(student);
    }),
  );

  menu.appendChild(
    makeItem('Editar alumno', () => {
      openStudentModal({ ...student, full_name: student.full_name });
    }),
  );

  // Promover alumno al siguiente cinturón (abre modal de confirmación)
  menu.appendChild(
    makeItem('Promover', () => {
      const BELT_ORDER = [
        'Blanco',
        'Blanco Punta Amarilla',
        'Amarillo',
        'Amarillo Punta Verde',
        'Verde',
        'Verde Punta Azul',
        'Azul',
        'Azul Punta Roja',
        'Rojo',
        'Rojo Punta Negra',
        'Negro Primer Dan',
      ];

      const currentRaw = student.belt || '';
      const current = currentRaw.toLowerCase();
      const idx = BELT_ORDER.findIndex((b) => b.toLowerCase() === current);

      if (idx === -1) {
        alert('No se reconoce el cinturón actual de este alumno. Editá el alumno primero.');
        return;
      }

      if (idx >= BELT_ORDER.length - 1) {
        alert('Este alumno ya tiene el cinturón máximo.');
        return;
      }

      const nextBelt = BELT_ORDER[idx + 1];
      const name = student.full_name || `${student.last_name || ''} ${student.first_name || ''}`.trim();

      if (studentPromoteMessage) {
        studentPromoteMessage.textContent =
          `¿Querés promover a ${name || 'este alumno'} de "${currentRaw}" a "${nextBelt}"?`;
      }

      pendingPromoteStudent = { ...student, nextBelt };
      modalStudentPromote?.classList.remove('hidden');
    }),
  );

  menu.appendChild(
    makeItem(
      'Eliminar alumno',
      () => {
        pendingDeleteStudent = student;
        if (studentDeleteMessage) {
          const name = student.full_name || `${student.last_name || ''} ${student.first_name || ''}`;
          studentDeleteMessage.textContent =
            '¿Seguro que querés eliminar al alumno "' + name.trim() + '"? Esta acción no se puede deshacer.';
        }
        modalStudentDelete?.classList.remove('hidden');
      },
      'students-actions-menu-item-danger',
    ),
  );

  document.body.appendChild(menu);

  const rect = triggerBtn.getBoundingClientRect();
  const top = rect.bottom + window.scrollY + 4;
  const left = rect.right + window.scrollX - menu.offsetWidth;
  menu.style.top = `${top}px`;
  menu.style.left = `${left}px`;

  studentActionsMenu = menu;
}

function openStudentModal(editData) {
  modalStudent?.classList.remove('hidden');
  if (editData) {
    modalStudentTitle.textContent = 'Editar Alumno';
    studentIdInput.value = editData.id;
    const lastInput = document.getElementById('student-last-name');
    const firstInput = document.getElementById('student-first-name');

    if (lastInput && firstInput) {
      if (editData.last_name || editData.first_name) {
        lastInput.value = editData.last_name || '';
        firstInput.value = editData.first_name || '';
      } else {
        const full = (editData.full_name || '').trim();
        if (full) {
          const parts = full.split(' ');
          lastInput.value = parts.shift() || '';
          firstInput.value = parts.join(' ');
        } else {
          lastInput.value = '';
          firstInput.value = '';
        }
      }
    }
    document.getElementById('student-dni').value = editData.dni || '';
    document.getElementById('student-gender').value = editData.gender || '';
    const birthInput = document.getElementById('student-birthdate');
    const birthDisplay = document.getElementById('student-birthdate-display');
    if (birthInput) birthInput.value = editData.birthdate || '';
    if (birthDisplay) {
      birthDisplay.textContent = formatDateForDisplay(editData.birthdate || '');
    }
    document.getElementById('student-blood').value = editData.blood || '';
    document.getElementById('student-nationality').value = editData.nationality || '';
    document.getElementById('student-province').value = editData.province || '';
    document.getElementById('student-country').value = editData.country || '';
    document.getElementById('student-city').value = editData.city || '';
    document.getElementById('student-address').value = editData.address || '';
    document.getElementById('student-zip').value = editData.zip || '';
    document.getElementById('student-school').value = editData.school || '';
    document.getElementById('student-belt').value = editData.belt || '';
    document.getElementById('student-father-name').value = editData.father_name || '';
    document.getElementById('student-mother-name').value = editData.mother_name || '';
    document.getElementById('student-father-phone').value = editData.father_phone || '';
    document.getElementById('student-mother-phone').value = editData.mother_phone || '';
    document.getElementById('student-parent-email').value = editData.parent_email || '';
    const notesEl = document.getElementById('student-notes');
    if (notesEl) notesEl.value = editData.notes || '';
    const tutorSelect = document.getElementById('student-tutor-type');
    if (tutorSelect) tutorSelect.value = editData.tutor_type || '';
  } else {
    modalStudentTitle.textContent = 'Crear Alumno';
    studentIdInput.value = '';
    studentForm.reset();
    if (document.getElementById('student-belt')) {
      document.getElementById('student-belt').value = '';
    }

    const birthInput = document.getElementById('student-birthdate');
    const birthDisplay = document.getElementById('student-birthdate-display');
    if (birthInput) birthInput.value = '';
    if (birthDisplay) birthDisplay.textContent = 'Seleccionar fecha';
    const tutorSelect = document.getElementById('student-tutor-type');
    if (tutorSelect) tutorSelect.value = '';
  }
}

studentsBeltFilter?.addEventListener('change', () => {
  loadStudents();
});

studentsStatusFilter?.addEventListener('change', () => {
  loadStudents();
});

function closeStudentModal() {
  modalStudent?.classList.add('hidden');
}

btnOpenCreateStudent?.addEventListener('click', () => openStudentModal());
btnCloseStudent?.addEventListener('click', closeStudentModal);
btnCancelStudent?.addEventListener('click', closeStudentModal);

function closeStudentRecordModal() {
  modalStudentRecord?.classList.add('hidden');
}

btnCloseStudentRecord?.addEventListener('click', closeStudentRecordModal);
btnCloseStudentRecordFooter?.addEventListener('click', closeStudentRecordModal);

function closeStudentDeleteModal() {
  modalStudentDelete?.classList.add('hidden');
  pendingDeleteStudent = null;
}

btnCloseStudentDelete?.addEventListener('click', closeStudentDeleteModal);
btnCancelStudentDelete?.addEventListener('click', closeStudentDeleteModal);

btnConfirmStudentDelete?.addEventListener('click', () => {
  if (!pendingDeleteStudent) return;
  apiSend(`/api/students/${pendingDeleteStudent.id}`, 'DELETE')
    .then(() => {
      closeStudentDeleteModal();
      loadStudents();
    })
    .catch((err) => {
      console.error(err);
      if (err && err.message) {
        alert(err.message);
      }
      closeStudentDeleteModal();
    });
});

// --- Modal de promoción de alumno ---
function closeStudentPromoteModal() {
  modalStudentPromote?.classList.add('hidden');
  pendingPromoteStudent = null;
}

btnCloseStudentPromote?.addEventListener('click', closeStudentPromoteModal);
btnCancelStudentPromote?.addEventListener('click', closeStudentPromoteModal);

btnConfirmStudentPromote?.addEventListener('click', async () => {
  if (!pendingPromoteStudent) {
    closeStudentPromoteModal();
    return;
  }

  const BELT_ORDER = [
    'Blanco',
    'Blanco Punta Amarilla',
    'Amarillo',
    'Amarillo Punta Verde',
    'Verde',
    'Verde Punta Azul',
    'Azul',
    'Azul Punta Roja',
    'Rojo',
    'Rojo Punta Negra',
    'Negro Primer Dan',
  ];

  const currentRaw = pendingPromoteStudent.belt || '';
  const current = currentRaw.toLowerCase();
  const idx = BELT_ORDER.findIndex((b) => b.toLowerCase() === current);

  if (idx === -1 || idx >= BELT_ORDER.length - 1) {
    closeStudentPromoteModal();
    return;
  }

  const nextBelt = BELT_ORDER[idx + 1];

  try {
    const today = new Date();
    const dd = String(today.getDate()).padStart(2, '0');
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const yyyy = today.getFullYear();
    const dateStr = `${dd}/${mm}/${yyyy}`;

    const existingNotes = (pendingPromoteStudent.notes || '').trim();
    const noteLine = `Ascendido a ${nextBelt} - ${dateStr}`;
    const newNotes = existingNotes ? `${existingNotes}\n${noteLine}` : noteLine;

    await apiSend(`/api/students/${pendingPromoteStudent.id}`, 'PUT', {
      belt: nextBelt,
      notes: newNotes,
    });
    await loadStudents();
  } catch (err) {
    console.error(err);
    alert('No se pudo ascender al alumno.');
  } finally {
    closeStudentPromoteModal();
  }
});

async function loadStudents() {
  try {
    const list = await apiGet('/api/students');
    studentsCache = list;
    if (!studentsTbody) return;
    studentsTbody.innerHTML = '';

    if (studentsEmptyState) {
      studentsEmptyState.style.display = list.length === 0 ? 'block' : 'none';
    }

    const selectedBelt = studentsBeltFilter ? studentsBeltFilter.value : '';
    const selectedStatus = studentsStatusFilter ? studentsStatusFilter.value : '';

    const filtered = list.filter((s) => {
      // filtro por cinturón (coincidencia exacta por valor de cinturón)
      if (selectedBelt) {
        const beltValue = (s.belt || '').toLowerCase();
        const filterValue = selectedBelt.toLowerCase();
        if (!beltValue || beltValue !== filterValue) return false;
      }

      // filtro por estado (activo/inactivo)
      if (selectedStatus) {
        const rawStatus = (s.status == null || s.status === '') ? 'activo' : String(s.status);
        const statusValue = rawStatus.toLowerCase().trim();

        // "Activos": cualquier alumno que NO esté marcado explícitamente como "inactivo".
        if (selectedStatus === 'active' && statusValue === 'inactivo') return false;
        // "Inactivos": solo los que están exactamente como "inactivo".
        if (selectedStatus === 'inactive' && statusValue !== 'inactivo') return false;
      }

      return true;
    });

    filtered.forEach((st) => {
      const tr = document.createElement('tr');
      const age = st.birthdate ? calcAge(st.birthdate) : '';
      const belt = st.belt || '';
      const beltLabel = belt
        ? belt
            .split(' ')
            .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : ''))
            .join(' ')
        : '';
      const { baseClass, edgeClass, edgeDifferentClass } = getBeltColorClasses(belt);

      const tutorType = (st.tutor_type || 'padre').toLowerCase();
      const tutorName = tutorType === 'madre' ? (st.mother_name || '') : (st.father_name || '');
      const tutorPhone = tutorType === 'madre' ? (st.mother_phone || '') : (st.father_phone || '');

      tr.innerHTML = `
        <td>${st.last_name || ''}</td>
        <td>${st.first_name || ''}</td>
        <td>${age}</td>
        <td>
          ${belt ? `<span class="belt-pill ${baseClass} ${edgeClass} ${edgeDifferentClass}">${beltLabel}</span>` : ''}
        </td>
        <td>${tutorName}</td>
        <td>${tutorPhone}</td>
        <td class="students-status-cell">
          <button class="student-status-pill" data-id="${st.id}"></button>
          <button class="students-menu-btn" data-id="${st.id}">⋮</button>
        </td>
      `;

      const statusBtn = tr.querySelector('.student-status-pill');
      const menuBtn = tr.querySelector('.students-menu-btn');

      const applyStatusToButton = (statusValue) => {
        const isInactive = (statusValue || 'activo').toLowerCase() === 'inactivo';
        statusBtn.textContent = isInactive ? 'Inactivo' : 'Activo';
        statusBtn.classList.toggle('student-status-inactive', isInactive);
        statusBtn.classList.toggle('student-status-active', !isInactive);
      };

      applyStatusToButton(st.status);

      statusBtn.addEventListener('click', async (event) => {
        event.stopPropagation();
        const current = (st.status || 'activo').toLowerCase() === 'inactivo' ? 'inactivo' : 'activo';
        const next = current === 'activo' ? 'inactivo' : 'activo';

        try {
          await apiSend(`/api/students/${st.id}`, 'PUT', { status: next });
          st.status = next;
          applyStatusToButton(st.status);
        } catch (err) {
          console.error(err);
          alert('No se pudo cambiar el estado del alumno.');
        }
      });

      menuBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        openStudentActionsMenu(menuBtn, st);
      });

      studentsTbody.appendChild(tr);
    });
  } catch (e) {
    console.error(e);
  }
}

// Cerrar menú de acciones de alumno al hacer click fuera
document.addEventListener('click', () => {
  closeStudentActionsMenu();
});

// Mapeo de colores de cinturón: key = clase CSS, stems = variantes para buscar en el texto
const BELT_COLOR_DEFS = [
  { key: 'blanco', stems: ['blanco', 'blanca'] },
  { key: 'amarillo', stems: ['amarillo', 'amarilla'] },
  { key: 'verde', stems: ['verde'] },
  { key: 'azul', stems: ['azul'] },
  { key: 'rojo', stems: ['rojo', 'roja'] },
  { key: 'negro', stems: ['negro', 'negra'] },
];

function getBeltColorClasses(beltRaw) {
  if (!beltRaw) return { baseClass: '', edgeClass: '', edgeDifferentClass: '' };
  const value = String(beltRaw).toLowerCase();

  const foundKeys = [];
  BELT_COLOR_DEFS.forEach((def) => {
    if (def.stems.some((stem) => value.includes(stem))) {
      foundKeys.push(def.key);
    }
  });

  const baseKey = foundKeys[0] || '';
  const edgeKey = foundKeys[1] || baseKey || '';

  const baseClass = baseKey ? `belt-color-${baseKey}` : '';
  const edgeClass = edgeKey ? `belt-edge-${edgeKey}` : '';
  const edgeDifferentClass = edgeKey && edgeKey !== baseKey ? 'belt-has-punta' : '';

  return { baseClass, edgeClass, edgeDifferentClass };
}

function formatDniWithDots(value) {
  const digits = value.replace(/\D/g, '');
  if (digits.length <= 2) return digits;
  if (digits.length <= 5) return digits.replace(/(\d{2})(\d+)/, '$1.$2');
  return digits.replace(/(\d{2})(\d{3})(\d+)/, '$1.$2.$3');
}

const studentDniInput = document.getElementById('student-dni');
if (studentDniInput) {
  studentDniInput.addEventListener('input', (e) => {
    const target = e.target;
    target.value = formatDniWithDots(target.value);
  });
}

studentForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = studentIdInput.value;
  const lastName = document.getElementById('student-last-name').value.trim();
  const firstName = document.getElementById('student-first-name').value.trim();
  const fullName = [lastName, firstName].filter(Boolean).join(' ');

  const payload = {
    full_name: fullName,
    last_name: lastName,
    first_name: firstName,
    dni: document.getElementById('student-dni').value,
    gender: document.getElementById('student-gender').value,
    birthdate: document.getElementById('student-birthdate').value,
    blood: document.getElementById('student-blood').value,
    nationality: document.getElementById('student-nationality').value,
    province: document.getElementById('student-province').value,
    country: document.getElementById('student-country').value,
    city: document.getElementById('student-city').value,
    address: document.getElementById('student-address').value,
    zip: document.getElementById('student-zip').value,
    school: document.getElementById('student-school').value,
    belt: document.getElementById('student-belt').value,
    father_name: document.getElementById('student-father-name').value,
    mother_name: document.getElementById('student-mother-name').value,
    father_phone: document.getElementById('student-father-phone').value,
    mother_phone: document.getElementById('student-mother-phone').value,
    parent_email: document.getElementById('student-parent-email').value,
    notes: document.getElementById('student-notes').value,
    tutor_type: document.getElementById('student-tutor-type').value || undefined,
  };

  try {
    if (id) {
      await apiSend(`/api/students/${id}`, 'PUT', payload);
    } else {
      await apiSend('/api/students', 'POST', payload);
    }
    closeStudentModal();
    loadStudents();
  } catch (err) {
    console.error(err);
  }
});

// Fecha de nacimiento (Alumnos) usando calendario genérico

studentBirthdateDisplay?.addEventListener('click', () => {
  if (!studentBirthdatePopover || !studentBirthdateCalendarEl) return;
  const hidden = document.getElementById('student-birthdate');
  const currentValue = hidden.value;
  if (currentValue) {
    birthSelectedDate = currentValue;
    const d = new Date(currentValue);
    if (!Number.isNaN(d.getTime())) {
      birthCalendarYearMonth = { year: d.getFullYear(), month: d.getMonth() };
    }
  }

  renderGenericCalendar(
    studentBirthdateCalendarEl,
    { get value() { return birthSelectedDate; }, set value(v) { birthSelectedDate = v; } },
    { get value() { return birthCalendarYearMonth; }, set value(v) { birthCalendarYearMonth = v; } },
    (dateStr) => {
      hidden.value = dateStr;
      studentBirthdateDisplay.textContent = formatDateForDisplay(dateStr);
    },
  );

  studentBirthdatePopover.classList.remove('hidden');
});

studentBirthdatePopover?.addEventListener('click', (e) => {
  const target = e.target;
  if (target.dataset?.picker === 'birthdate-cancel') {
    studentBirthdatePopover.classList.add('hidden');
  } else if (target.dataset?.picker === 'birthdate-apply') {
    const hidden = document.getElementById('student-birthdate');
    studentBirthdateDisplay.textContent = formatDateForDisplay(hidden.value || birthSelectedDate);
    studentBirthdatePopover.classList.add('hidden');
  }
});

function calcAge(dateStr) {
  const parts = String(dateStr).split('-');
  if (parts.length !== 3) return '';
  const [yStr, mStr, dStr] = parts;
  const year = Number(yStr);
  const month = Number(mStr);
  const day = Number(dStr);
  if (!year || !month || !day) return '';

  const d = new Date(year, month - 1, day);
  if (Number.isNaN(d.getTime())) return '';
  const today = new Date();
  let age = today.getFullYear() - d.getFullYear();
  const m = today.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < d.getDate())) {
    age--;
  }
  return age;
}

// --- Calendario ---

const calendarGrid = document.getElementById('calendar-grid');
const calendarMonthLabel = document.getElementById('calendar-month-label');
const calendarPrev = document.getElementById('calendar-prev');
const calendarNext = document.getElementById('calendar-next');
const calendarDetailsBody = document.getElementById('calendar-details-body');

let currentYearMonth = (() => {
  const d = new Date();
  return { year: d.getFullYear(), month: d.getMonth() };
})();

let eventsCache = [];

function renderCalendar() {
  if (!calendarGrid || !calendarMonthLabel) return;
  const { year, month } = currentYearMonth;
  const firstDay = new Date(year, month, 1);
  const startWeekday = firstDay.getDay(); // 0=Domingo
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const monthNames = [
    'Enero',
    'Febrero',
    'Marzo',
    'Abril',
    'Mayo',
    'Junio',
    'Julio',
    'Agosto',
    'Septiembre',
    'Octubre',
    'Noviembre',
    'Diciembre',
  ];
  calendarMonthLabel.textContent = `${monthNames[month]} ${year}`;

  calendarGrid.innerHTML = '';

  // Encabezados días
  ['D', 'L', 'M', 'M', 'J', 'V', 'S'].forEach((d) => {
    const head = document.createElement('div');
    head.className = 'calendar-cell calendar-cell-head';
    head.style.fontWeight = '600';
    head.textContent = d;
    calendarGrid.appendChild(head);
  });

  // Celdas vacías antes del 1
  for (let i = 0; i < startWeekday; i++) {
    const cell = document.createElement('div');
    cell.className = 'calendar-cell';
    cell.style.visibility = 'hidden';
    calendarGrid.appendChild(cell);
  }

  const today = new Date();
  for (let day = 1; day <= daysInMonth; day++) {
    const cellDate = new Date(year, month, day);
    const cell = document.createElement('div');
    cell.className = 'calendar-cell';

    if (
      cellDate.getFullYear() === today.getFullYear() &&
      cellDate.getMonth() === today.getMonth() &&
      cellDate.getDate() === today.getDate()
    ) {
      cell.classList.add('calendar-cell-today');
    }

    const header = document.createElement('div');
    header.className = 'calendar-cell-header';
    const daySpan = document.createElement('span');
    daySpan.textContent = String(day);
    header.appendChild(daySpan);

    const evDot = document.createElement('span');
    const dateStr = cellDate.toISOString().slice(0, 10);
    const hasExam = eventsCache.some((e) => e.date === dateStr && e.type === 'exam');
    const hasEvent = eventsCache.some((e) => e.date === dateStr);

    // Cumpleaños: comparar solo mes/día en base a las cadenas 'YYYY-MM-DD'
    const [yStr, mStr, dStr] = dateStr.split('-');
    const cellMonth = Number(mStr);
    const cellDay = Number(dStr);
    const hasBirthday = studentsCache.some((s) => {
      if (!s.birthdate) return false;
      const parts = String(s.birthdate).split('-');
      if (parts.length !== 3) return false;
      const bdMonth = Number(parts[1]);
      const bdDay = Number(parts[2]);
      return bdMonth === cellMonth && bdDay === cellDay;
    });

    if (hasEvent) {
      evDot.className = hasBirthday ? 'calendar-event-dot calendar-birthday-dot' : 'calendar-event-dot';
      if (hasExam) cell.classList.add('calendar-cell-exam');
    } else if (hasBirthday) {
      evDot.className = 'calendar-event-dot calendar-birthday-dot';
      cell.classList.add('calendar-cell-birthday');
    }
    header.appendChild(evDot);

    cell.appendChild(header);

    cell.addEventListener('click', () => showDayEvents(dateStr));

    calendarGrid.appendChild(cell);
  }
}

function showDayEvents(dateStr) {
  if (!calendarDetailsBody) return;
  const dayEvents = eventsCache.filter((e) => e.date === dateStr);
  const [, mStr, dStr] = dateStr.split('-');
  const cellMonth = Number(mStr);
  const cellDay = Number(dStr);

  const birthdays = studentsCache.filter((s) => {
    if (!s.birthdate) return false;
    const parts = String(s.birthdate).split('-');
    if (parts.length !== 3) return false;
    const bdMonth = Number(parts[1]);
    const bdDay = Number(parts[2]);
    return bdMonth === cellMonth && bdDay === cellDay;
  });

  if (!dayEvents.length && !birthdays.length) {
    calendarDetailsBody.textContent = 'Sin eventos para este día.';
    return;
  }

  const list = document.createElement('ul');
  list.style.listStyle = 'none';
  list.style.padding = '0';
  list.style.margin = '0';

  dayEvents.forEach((ev) => {
    const li = document.createElement('li');
    li.style.marginBottom = '4px';
    const typeLabel = ev.type === 'exam' ? '[Examen]' : '[Actividad]';
    const levelPart = ev.type === 'exam' && ev.level ? ` - ${ev.level}` : '';
    li.textContent = `${typeLabel} ${ev.title || ''} - ${ev.time || ''}${levelPart} ${ev.notes || ''}`;
    list.appendChild(li);
  });

  birthdays.forEach((s) => {
    const li = document.createElement('li');
    li.style.marginBottom = '4px';
    const name = s.full_name || `${s.last_name || ''} ${s.first_name || ''}`;
    li.textContent = `[Cumpleaños] ${name}`;
    list.appendChild(li);
  });

  calendarDetailsBody.innerHTML = '';
  calendarDetailsBody.appendChild(list);
}

calendarPrev?.addEventListener('click', () => {
  currentYearMonth.month -= 1;
  if (currentYearMonth.month < 0) {
    currentYearMonth.month = 11;
    currentYearMonth.year -= 1;
  }
  renderCalendar();
});

calendarNext?.addEventListener('click', () => {
  currentYearMonth.month += 1;
  if (currentYearMonth.month > 11) {
    currentYearMonth.month = 0;
    currentYearMonth.year += 1;
  }
  renderCalendar();
});

async function loadEvents() {
  try {
    eventsCache = await apiGet('/api/events');
    renderCalendar();
    renderExamsFromEvents();
  } catch (err) {
    console.error(err);
  }
}

// --- Exámenes ---

const examForm = document.getElementById('exam-form');
const examsList = document.getElementById('exams-list');
const examPdfBox = document.getElementById('exam-pdf-box');
// Botones del flujo viejo (un solo alumno)
const btnGenerateExamPdf = document.getElementById('btn-generate-exam-pdf');
const btnGenerateEvalPdf = document.getElementById('btn-generate-eval-pdf');
const examStudentIdInput = document.getElementById('exam-student-id');
// Nuevo flujo: multi-alumno por examen
const btnOpenExamStudents = document.getElementById('btn-open-exam-students');
const btnGenerateExamRindePdf = document.getElementById('btn-generate-exam-rinde-pdf');
const examDateDisplay = document.getElementById('exam-date-display');
const examDatePopover = document.getElementById('exam-date-popover');
const examDateCalendar = document.getElementById('exam-date-calendar');
const examTimeDisplay = document.getElementById('exam-time-display');
const examTimePopover = document.getElementById('exam-time-popover');
const modalExamDelete = document.getElementById('modal-exam-delete');
const btnCloseExamDelete = document.getElementById('btn-close-exam-delete');
const btnCancelExamDelete = document.getElementById('btn-cancel-exam-delete');
const btnConfirmExamDelete = document.getElementById('btn-confirm-exam-delete');
const examDeleteMessage = document.getElementById('exam-delete-message');
// Modal multi-alumno
const modalExamStudents = document.getElementById('modal-exam-students');
const btnCloseExamStudents = document.getElementById('btn-close-exam-students');
const btnCancelExamStudents = document.getElementById('btn-cancel-exam-students');
const btnSaveExamStudents = document.getElementById('btn-save-exam-students');
const examStudentsTbody = document.getElementById('exam-students-tbody');
const examStudentsNotice = document.getElementById('exam-students-notice');
const examGraduationSelect = document.getElementById('exam-graduation');
const examLevelHiddenInput = document.getElementById('exam-level');
const examBeltInput = document.getElementById('exam-belt');
const examGupInput = document.getElementById('exam-gup');

// Configuración fija de graduaciones, cinturones y Gups (1 a 11)
const EXAM_LEVEL_CONFIG = [
  { graduation: 'Primera', belt: 'Blanco', gup: '10º Gup' },
  { graduation: 'Segunda', belt: 'Blanco Punta Amarilla', gup: '9º Gup' },
  { graduation: 'Tercera', belt: 'Amarillo', gup: '8º Gup' },
  { graduation: 'Cuarta', belt: 'Amarillo Punta Verde', gup: '7º Gup' },
  { graduation: 'Quinta', belt: 'Verde', gup: '6º Gup' },
  { graduation: 'Sexta', belt: 'Verde Punta Azul', gup: '5º Gup' },
  { graduation: 'Séptima', belt: 'Azul', gup: '4º Gup' },
  { graduation: 'Octava', belt: 'Azul Punta Roja', gup: '3º Gup' },
  { graduation: 'Novena', belt: 'Rojo', gup: '2º Gup' },
  { graduation: 'Décima', belt: 'Rojo Punta Negra', gup: '1º Gup' },
  { graduation: 'Negro Primer Dan', belt: 'Negro Primer Dan', gup: 'Negro Primer Dan' },
];

function initExamGraduationFields() {
  if (!examGraduationSelect || !examLevelHiddenInput || !examBeltInput || !examGupInput) return;

  // Poblar opciones si están vacías
  if (!examGraduationSelect.options.length) {
    // Placeholder sin valor real
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Seleccionar graduación';
    placeholder.disabled = true;
    placeholder.selected = true;
    examGraduationSelect.appendChild(placeholder);

    EXAM_LEVEL_CONFIG.forEach((cfg, index) => {
      const opt = document.createElement('option');
      // value = índice + 1 para dejar 0 reservado al placeholder
      opt.value = String(index + 1);
      opt.textContent = `${index + 1}. ${cfg.graduation}`;
      examGraduationSelect.appendChild(opt);
    });
  }

  const applyConfigByIndex = (idx) => {
    // idx 0 es placeholder; los niveles reales empiezan en 1
    const cfg = EXAM_LEVEL_CONFIG[idx - 1];
    if (!cfg) return;
    examBeltInput.value = cfg.belt;
    examGupInput.value = cfg.gup;
    examLevelHiddenInput.value = `${cfg.graduation} - ${cfg.belt} - ${cfg.gup}`;
  };

  examGraduationSelect.addEventListener('change', () => {
    const idx = Number(examGraduationSelect.value) || examGraduationSelect.selectedIndex || 0;
    if (idx <= 0) {
      examBeltInput.value = '';
      examGupInput.value = '';
      examLevelHiddenInput.value = '';
      return;
    }
    applyConfigByIndex(idx);
  });
}

initExamGraduationFields();

let examSelectedDate = '';
let examCalendarYearMonth = (() => {
  const d = new Date();
  return { year: d.getFullYear(), month: d.getMonth() };
})();

let pendingDeleteExamId = null;
// Selección en memoria de alumnos por examen (solo sesión actual)
const examStudentsSelection = {}; // { [eventId]: number[] }

function closeExamDeleteModal() {
  modalExamDelete?.classList.add('hidden');
  pendingDeleteExamId = null;
}

btnCloseExamDelete?.addEventListener('click', closeExamDeleteModal);
btnCancelExamDelete?.addEventListener('click', closeExamDeleteModal);

btnConfirmExamDelete?.addEventListener('click', async () => {
  if (!pendingDeleteExamId) {
    closeExamDeleteModal();
    return;
  }
  try {
    await apiSend(`/api/events/${pendingDeleteExamId}`, 'DELETE');
    closeExamDeleteModal();
    loadEvents();
  } catch (err) {
    console.error(err);
    closeExamDeleteModal();
  }
});

// Estado separado para Fecha de pago (Cuotas)
let feesSelectedDate = '';
let feesCalendarYearMonth = (() => {
  const d = new Date();
  return { year: d.getFullYear(), month: d.getMonth() };
})();

// Estado para Fecha de nacimiento (Alumnos)
let birthSelectedDate = '';
let birthCalendarYearMonth = (() => {
  const d = new Date();
  return { year: d.getFullYear(), month: d.getMonth() };
})();

function formatDateForDisplay(value) {
  if (!value) return 'Seleccionar fecha';

  const parts = String(value).split('-');
  if (parts.length !== 3) return 'Seleccionar fecha';

  const [yStr, mStr, dStr] = parts;
  if (!yStr || !mStr || !dStr) return 'Seleccionar fecha';

  const dd = dStr.padStart(2, '0');
  const mm = mStr.padStart(2, '0');
  const yyyy = yStr;

  return `${dd}/${mm}/${yyyy}`;
}

function formatTimeForDisplay(value) {
  if (!value) return '';
  return value.slice(0, 5);
}

function renderExamCalendar() {
  if (!examDateCalendar) return;

  renderGenericCalendar(
    examDateCalendar,
    { get value() { return examSelectedDate; }, set value(v) { examSelectedDate = v; } },
    { get value() { return examCalendarYearMonth; }, set value(v) { examCalendarYearMonth = v; } },
    (dateStr) => {
      const hiddenInput = document.getElementById('exam-date');
      hiddenInput.value = dateStr;
      examDateDisplay.textContent = formatDateForDisplay(dateStr);
    },
  );
}

examDateDisplay?.addEventListener('click', () => {
  if (!examDatePopover) return;
  const currentValue = document.getElementById('exam-date').value;
  if (currentValue) {
    examSelectedDate = currentValue;
    const d = new Date(currentValue);
    if (!Number.isNaN(d.getTime())) {
      examCalendarYearMonth = { year: d.getFullYear(), month: d.getMonth() };
    }
  }
  renderExamCalendar();
  examDatePopover.classList.remove('hidden');
});

examDatePopover?.addEventListener('click', (e) => {
  const target = e.target;
  if (target.dataset?.picker === 'date-cancel') {
    examDatePopover.classList.add('hidden');
  } else if (target.dataset?.picker === 'date-apply') {
    const input = document.getElementById('exam-date');
    examDateDisplay.textContent = formatDateForDisplay(input.value || examSelectedDate);
    examDatePopover.classList.add('hidden');
  }
});
// --- Selector de horario (HH/MM en popover) ---

examTimeDisplay?.addEventListener('click', () => {
  if (!examTimePopover) return;
  const hidden = document.getElementById('exam-time');
  const hourInput = document.getElementById('exam-time-hour');
  const minuteInput = document.getElementById('exam-time-minute');
  if (hidden.value) {
    const [h, m] = hidden.value.split(':');
    hourInput.value = h || '';
    minuteInput.value = m || '';
  }
  examTimePopover.classList.remove('hidden');
});

examTimePopover?.addEventListener('click', (e) => {
  const target = e.target;
  if (target.dataset?.picker === 'time-cancel') {
    examTimePopover.classList.add('hidden');
  } else if (target.dataset?.picker === 'time-apply') {
    const hidden = document.getElementById('exam-time');
    const hourInput = document.getElementById('exam-time-hour');
    const minuteInput = document.getElementById('exam-time-minute');

    let hh = (hourInput.value || '').trim();
    let mm = (minuteInput.value || '').trim();

    if (!hh || !mm || isNaN(Number(hh)) || isNaN(Number(mm))) {
      alert('Ingresá una hora válida en formato 24 hs (ej: 18:30).');
      return;
    }

    hh = String(Math.floor(Number(hh))).padStart(2, '0');
    mm = String(Math.floor(Number(mm))).padStart(2, '0');

    const hNum = Number(hh);
    const mNum = Number(mm);
    if (hNum < 0 || hNum > 23 || mNum < 0 || mNum > 59) {
      alert('Hora fuera de rango. Usá 00-23 para horas y 00-59 para minutos.');
      return;
    }

    hidden.value = `${hh}:${mm}`;
    examTimeDisplay.textContent = formatTimeForDisplay(hidden.value);
    examTimePopover.classList.add('hidden');
  }
});

examForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    type: 'exam',
    date: document.getElementById('exam-date').value,
    time: document.getElementById('exam-time').value,
    level: '',
    place: document.getElementById('exam-place').value,
    notes: document.getElementById('exam-notes').value,
    title: 'Examen',
  };

  try {
    await apiSend('/api/events', 'POST', payload);
    examForm.reset();
    loadEvents();
  } catch (err) {
    console.error(err);
  }
});

function renderExamsFromEvents() {
  if (!examsList) return;
  examsList.innerHTML = '';
  const today = new Date();

  const exams = eventsCache
    .filter((e) => e.type === 'exam')
    .filter((e) => {
      // Filtrar sólo exámenes cuya fecha no haya pasado
      if (!e.date) return true;
      const d = new Date(e.date);
      if (Number.isNaN(d.getTime())) return true;
      // mantener exámenes de hoy o a futuro
      return d >= new Date(today.getFullYear(), today.getMonth(), today.getDate());
    })
    .sort((a, b) => {
      const da = new Date(a.date || '9999-12-31');
      const db = new Date(b.date || '9999-12-31');
      if (da.getTime() !== db.getTime()) return da - db;
      return String(a.time || '').localeCompare(String(b.time || ''));
    });

  exams.forEach((ev) => {
    const li = document.createElement('li');
    li.className = 'exams-list-item';

    const wrapper = document.createElement('div');
    wrapper.className = 'exam-item-inner';

    const left = document.createElement('div');
    left.className = 'exam-item-main';
    const checkbox = document.createElement('span');
    checkbox.className = 'exam-checkbox';
    const label = document.createElement('span');
    label.textContent = `${ev.date || ''} ${ev.time || ''} - ${ev.level || ''} - ${ev.place || ''}`;
    left.appendChild(checkbox);
    left.appendChild(label);

    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.textContent = 'Eliminar';
    delBtn.className = 'btn-secondary exam-delete-btn';
    delBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      pendingDeleteExamId = ev.id;
      if (examDeleteMessage) {
        examDeleteMessage.textContent = `¿Seguro que querés eliminar el examen del ${ev.date || ''} ${ev.time || ''} en ${ev.place || ''}? Esta acción no se puede deshacer.`;
      }
      modalExamDelete?.classList.remove('hidden');
    });

    wrapper.appendChild(left);
    wrapper.appendChild(delBtn);

    li.appendChild(wrapper);
    li.addEventListener('click', () => selectExam(ev.id, li));
    examsList.appendChild(li);
  });
}

// ... (rest of the code remains the same)
async function selectExam(eventId, liElement) {
  if (!examPdfBox) return;
  examPdfBox.setAttribute('data-event-id', String(eventId));

  const children = examsList?.querySelectorAll('.exams-list-item') || [];
  children.forEach((li) => li.classList.remove('exams-list-item-selected'));
  if (liElement) {
    liElement.classList.add('exams-list-item-selected');
  }
  // Habilitar botones del nuevo flujo si existen
  if (btnOpenExamStudents) btnOpenExamStudents.disabled = false;
  if (btnGenerateExamRindePdf) btnGenerateExamRindePdf.disabled = false;

  // Cargar desde backend los alumnos ya inscriptos para este examen
  try {
    const inscriptos = await apiGet(`/api/exams/${eventId}/students`);
    const ids = (inscriptos || []).map((s) => s.id);
    examStudentsSelection[eventId] = ids;
  } catch (err) {
    console.error('No se pudieron leer los alumnos del examen seleccionado', err);
  }
}

// Abrir modal de alumnos que rinden
async function openExamStudentsModal() {
  if (!examPdfBox || !modalExamStudents || !examStudentsTbody) return;
  const eventId = examPdfBox.getAttribute('data-event-id');
  if (!eventId) {
    alert('Primero seleccioná un examen de la lista.');
    return;
  }

  try {
    // Asegurar alumnos cargados
    if (!studentsCache || !studentsCache.length) {
      studentsCache = await apiGet('/api/students');
    }
    // Alumnos ya inscriptos en este examen desde backend
    const inscriptos = await apiGet(`/api/exams/${eventId}/students`);
    const selectedIds = new Set((inscriptos || []).map((s) => s.id));
    examStudentsTbody.innerHTML = '';

    studentsCache.forEach((s) => {
      const tr = document.createElement('tr');
      const belt = s.belt || '';
      const { baseClass, edgeClass, edgeDifferentClass } = getBeltColorClasses(belt);
      const beltLabel = belt
        ? belt
            .split(' ')
            .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : ''))
            .join(' ')
        : '';

      // Normalizar estado igual que en la vista principal
      const rawStatus = (s.status == null || s.status === '') ? 'activo' : String(s.status);
      const statusValue = rawStatus.toLowerCase().trim();
      const isInactive = statusValue === 'inactivo';
      const isActive = !isInactive;

      // Solo mostrar alumnos activos en este modal
      if (!isActive) return;

      const statusLabel = isActive ? 'Activo' : 'Inactivo';

      const checkedAttr = selectedIds.has(s.id) ? 'checked' : '';

      tr.innerHTML = `
        <td><input type="checkbox" class="exam-student-checkbox" data-student-id="${s.id}" ${checkedAttr} /></td>
        <td>${s.last_name || ''}</td>
        <td>${s.first_name || ''}</td>
        <td>${belt ? `<span class="belt-pill ${baseClass} ${edgeClass} ${edgeDifferentClass}">${beltLabel}</span>` : ''}</td>
        <td>${statusLabel}</td>
      `;

      // Permitir click en toda la fila
      tr.addEventListener('click', (e) => {
        const cb = tr.querySelector('.exam-student-checkbox');
        if (!cb) return;
        if (e.target === cb) return;
        cb.checked = !cb.checked;
      });

      examStudentsTbody.appendChild(tr);
    });

    modalExamStudents.classList.remove('hidden');
  } catch (err) {
    console.error(err);
    alert('No se pudieron cargar los alumnos para este examen.');
  }
}

function closeExamStudentsModal() {
  modalExamStudents?.classList.add('hidden');
}

btnOpenExamStudents?.addEventListener('click', openExamStudentsModal);
btnCloseExamStudents?.addEventListener('click', closeExamStudentsModal);
btnCancelExamStudents?.addEventListener('click', closeExamStudentsModal);

btnSaveExamStudents?.addEventListener('click', () => {
  if (!examPdfBox || !examStudentsTbody) {
    closeExamStudentsModal();
    return;
  }

  const eventId = Number(examPdfBox.getAttribute('data-event-id'));
  if (!eventId) {
    closeExamStudentsModal();
    return;
  }

  const checkboxes = examStudentsTbody.querySelectorAll('.exam-student-checkbox');
  const ids = [];
  checkboxes.forEach((cb) => {
    if (cb.checked) {
      const sid = cb.getAttribute('data-student-id');
      if (sid) ids.push(Number(sid));
    }
  });

  apiSend(`/api/exams/${eventId}/students`, 'PUT', { student_ids: ids })
    .then(() => {
      examStudentsSelection[eventId] = ids;
      closeExamStudentsModal();
      showExamStudentsNotice('Alumnos que rinden guardados correctamente.');
    })
    .catch((err) => {
      console.error(err);
      showExamStudentsNotice('No se pudieron guardar los alumnos para este examen.', 'error');
    });
});

btnGenerateExamRindePdf?.addEventListener('click', async () => {
  if (!examPdfBox) return;
  const eventId = Number(examPdfBox.getAttribute('data-event-id'));
  if (!eventId) {
    alert('Primero seleccioná un examen de la lista.');
    return;
  }

  const ids = examStudentsSelection[eventId] || [];
  if (!ids.length) {
    alert('Configurá primero los alumnos que rinden para este examen.');
    return;
  }

  try {
    const res = await fetch(`/api/exams/${eventId}/rinde-pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_ids: ids }),
    });

    if (!res.ok) {
      throw new Error('No se pudo generar el PDF de rendida (código ' + res.status + ').');
    }

    const blob = await res.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);

    // Usar el nombre de archivo que manda el backend en Content-Disposition, si existe
    const dispo = res.headers.get('Content-Disposition') || '';
    let filename = '';
    const match = dispo.match(/filename="?([^";]+)"?/i);
    if (match && match[1]) {
      filename = match[1];
    }

    link.download = filename || `Examen_Taekwondo_${eventId}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } catch (err) {
    console.error(err);
    alert('No se pudo generar el PDF de rendida.');
  }
});

btnGenerateExamPdf?.addEventListener('click', () => {
  if (!examPdfBox) return;
  const eventId = examPdfBox.getAttribute('data-event-id');
  const studentIdValue = examStudentIdInput?.value || '';
  if (!eventId) {
    alert('Primero seleccioná un examen de la lista.');
    return;
  }
  if (!studentIdValue) {
    alert('Seleccioná un Alumno para generar el PDF.');
    return;
  }

  const url = `/api/exams/${eventId}/inscription-pdf`;

  // Usamos fetch para POST y luego creamos un enlace de descarga
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ student_id: Number(studentIdValue) }),
  })
    .then((res) => {
      if (!res.ok) {
        throw new Error('No se pudo generar el PDF (código ' + res.status + ').');
      }
      return res.blob();
    })
    .then((blob) => {
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'inscripcion_examen.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
    })
    .catch((err) => console.error(err));
});

btnGenerateEvalPdf?.addEventListener('click', () => {
  if (!examPdfBox) return;
  const eventId = examPdfBox.getAttribute('data-event-id');
  const studentIdValue = examStudentIdInput?.value || '';
  if (!eventId) {
    alert('Primero seleccioná un examen de la lista.');
    return;
  }
  if (!studentIdValue) {
    alert('Seleccioná un Alumno para generar el PDF.');
    return;
  }

  const url = `/api/exams/${eventId}/evaluation-pdf`;

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ student_id: Number(studentIdValue) }),
  })
    .then((res) => {
      if (!res.ok) {
        throw new Error('No se pudo generar el PDF (código ' + res.status + ').');
      }
      return res.blob();
    })
    .then((blob) => {
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'evaluacion_examen.pdf';
      document.body.appendChild(link);
      link.click();
      link.remove();
    })
    .catch((err) => console.error(err));
});

// --- Cuotas ---

const btnFeesRefresh = document.getElementById('btn-fees-refresh');
const feesSearchInput = document.getElementById('fees-search');
const feesOverviewTbody = document.getElementById('fees-overview-tbody');
const feesOverviewEmpty = document.getElementById('fees-overview-empty');
const btnFeesGenerateMonth = document.getElementById('btn-fees-generate-month');

const feesBulkPeriod = document.getElementById('fees-bulk-period');
const feesBulkProrationMode = document.getElementById('fees-bulk-proration-mode');
const feesBulkProrationPercent = document.getElementById('fees-bulk-proration-percent');
const feesBulkStartDate = document.getElementById('fees-bulk-start-date');

const feesConfigMonthly = document.getElementById('fees-config-monthly');
const feesConfigDueDay = document.getElementById('fees-config-due-day');
const feesConfigProrationMode = document.getElementById('fees-config-proration-mode');
const feesConfigProrationPercent = document.getElementById('fees-config-proration-percent');
const btnSaveFeesConfig = document.getElementById('btn-save-fees-config');

const feesStudentEmpty = document.getElementById('fees-student-empty');
const feesStudentContent = document.getElementById('fees-student-content');
const feesStudentNameEl = document.getElementById('fees-student-name');
const feesStudentMetaEl = document.getElementById('fees-student-meta');
const feesStudentStatusEl = document.getElementById('fees-student-status');

const feesChargesTbody = document.getElementById('fees-charges-tbody');
const feesChargesEmpty = document.getElementById('fees-charges-empty');
const feesPaymentsTbody = document.getElementById('fees-payments-tbody');
const feesPaymentsEmpty = document.getElementById('fees-payments-empty');
const feesApplyList = document.getElementById('fees-apply-list');

const feesChargePeriod = document.getElementById('fees-charge-period');
const feesChargeProrationMode = document.getElementById('fees-charge-proration-mode');
const feesChargeProrationPercent = document.getElementById('fees-charge-proration-percent');
const feesChargeStartDate = document.getElementById('fees-charge-start-date');
const btnFeesGenerateStudent = document.getElementById('btn-fees-generate-student');

const feesPaymentForm = document.getElementById('fees-payment-form');
const feesPaymentDate = document.getElementById('fees-payment-date');
const feesPaymentAmount = document.getElementById('fees-payment-amount');
const feesPaymentMethod = document.getElementById('fees-payment-method');
const feesPaymentReference = document.getElementById('fees-payment-reference');
const feesPaymentNotes = document.getElementById('fees-payment-notes');

const feesDiscountForm = document.getElementById('fees-discount-form');
const feesDiscountType = document.getElementById('fees-discount-type');
const feesDiscountValue = document.getElementById('fees-discount-value');

let feesOverviewCache = [];
let feesSelectedStudentId = null;
let feesSelectedStudentData = null;

function feesTodayDate() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function feesMonthStartDate(baseDate = new Date()) {
  return `${baseDate.getFullYear()}-${String(baseDate.getMonth() + 1).padStart(2, '0')}-01`;
}

function feesMonthEndDate(baseDate = new Date()) {
  const y = baseDate.getFullYear();
  const m = baseDate.getMonth();
  const end = new Date(y, m + 1, 0);
  return `${end.getFullYear()}-${String(end.getMonth() + 1).padStart(2, '0')}-${String(end.getDate()).padStart(2, '0')}`;
}

function parseDateRangeValue(value) {
  const raw = String(value || '').trim();
  if (!raw) return { start: '', end: '' };
  const parts = raw.split(' to ');
  const start = parts[0] || '';
  const end = parts[1] || parts[0] || '';
  return { start, end };
}

function getPeriodRangePayload(inputEl) {
  const { start, end } = parseDateRangeValue(inputEl?.value || '');
  if (!start || !end) return {};
  return {
    period_start: start,
    period_end: end,
  };
}

function formatFeesDate(value) {
  if (!value) return '-';
  return formatDateForDisplay(value);
}

function normalizePeriodLabel(period, dueDate) {
  if (dueDate) {
    const parts = String(dueDate).split('-');
    if (parts.length === 3) {
      const year = parts[0];
      const month = parts[1];
      return `${month}/${year}`;
    }
  }
  if (!period) return '-';
  const parts = String(period).split('-');
  if (parts.length === 2) return `${parts[1]}/${parts[0]}`;
  return period;
}

function feesSetDefaultPeriods() {
  const d = new Date();
  const start = feesMonthStartDate(d);
  const end = feesMonthEndDate(d);
  if (feesBulkPeriod && !feesBulkPeriod.value) feesBulkPeriod.value = `${start} to ${end}`;
  if (feesChargePeriod && !feesChargePeriod.value) feesChargePeriod.value = `${start} to ${end}`;
}

function makeStatusPill(label, variant) {
  const pill = document.createElement('span');
  pill.className = 'status-pill';
  if (variant === 'ok') pill.classList.add('status-pill-ok');
  if (variant === 'debt') pill.classList.add('status-pill-debt');
  if (variant === 'warn') pill.classList.add('status-pill-warn');
  pill.textContent = label;
  return pill;
}

function feesStatusToPill(status) {
  if (status === 'al_dia') return makeStatusPill('Al día', 'ok');
  if (status === 'vencida') return makeStatusPill('Vencida', 'debt');
  if (status === 'pendiente') return makeStatusPill('Pendiente', 'warn');
  return makeStatusPill('Sin registro', 'debt');
}

function feesChargeStatusToPill(charge) {
  if (!charge) return makeStatusPill('-', 'warn');
  if (charge.status === 'paid') return makeStatusPill('Pagada', 'ok');
  if (charge.status === 'partial') return makeStatusPill('Parcial', 'warn');
  if (charge.overdue) return makeStatusPill('Vencida', 'debt');
  return makeStatusPill('Pendiente', 'warn');
}

async function loadFeesConfig() {
  try {
    const cfg = await apiGet('/api/fees/config');
    if (feesConfigMonthly) feesConfigMonthly.value = String(cfg.monthly_amount ?? 0);
    if (feesConfigDueDay) feesConfigDueDay.value = String(cfg.due_day ?? 10);
    if (feesConfigProrationMode) feesConfigProrationMode.value = cfg.proration_mode ?? 'days';
    if (feesConfigProrationPercent) feesConfigProrationPercent.value = String(cfg.proration_percent_default ?? 100);
  } catch (err) {
    console.error(err);
  }
}

btnSaveFeesConfig?.addEventListener('click', async () => {
  const payload = {
    monthly_amount: Number(feesConfigMonthly?.value || 0),
    due_day: Number(feesConfigDueDay?.value || 10),
    proration_mode: feesConfigProrationMode?.value || 'days',
    proration_percent_default: Number(feesConfigProrationPercent?.value || 100),
  };

  try {
    await apiSend('/api/fees/config', 'PUT', payload);
    alert('Configuración guardada.');
  } catch (err) {
    console.error(err);
    alert(err?.message || 'No se pudo guardar la configuración.');
  }
});

function renderFeesOverview() {
  if (!feesOverviewTbody) return;
  const query = (feesSearchInput?.value || '').toLowerCase().trim();
  const list = (feesOverviewCache || []).filter((row) => {
    if (!query) return true;
    const name = (row.full_name || `${row.last_name || ''} ${row.first_name || ''}`).toLowerCase();
    return name.includes(query);
  });

  feesOverviewTbody.innerHTML = '';
  if (feesOverviewEmpty) {
    feesOverviewEmpty.style.display = list.length === 0 ? 'block' : 'none';
  }

  list.forEach((row) => {
    const tr = document.createElement('tr');
    tr.className = 'fees-overview-row';
    if (feesSelectedStudentId != null && Number(row.student_id) === Number(feesSelectedStudentId)) {
      tr.classList.add('fees-overview-row-selected');
    }

    const name = row.full_name || `${row.last_name || ''} ${row.first_name || ''}`;
    const statusCell = document.createElement('td');
    statusCell.appendChild(feesStatusToPill(row.status));

    tr.innerHTML = `
      <td>${name}</td>
      <td></td>
      <td>$${Number(row.overdue_total || 0).toFixed(2)}</td>
      <td>${formatFeesDate(row.last_payment)}</td>
    `;
    tr.children[1].appendChild(statusCell.firstChild);

    tr.addEventListener('click', () => {
      selectFeesStudent(row.student_id);
    });

    feesOverviewTbody.appendChild(tr);
  });
}

async function loadFeesOverview() {
  try {
    const data = await apiGet('/api/fees/overview');
    feesOverviewCache = Array.isArray(data) ? data : [];
    renderFeesOverview();
  } catch (err) {
    console.error(err);
  }
}

async function selectFeesStudent(studentId) {
  feesSelectedStudentId = Number(studentId);
  renderFeesOverview();
  await loadFeesStudentDetail();
}

function renderFeesStudentDetail(data) {
  feesSelectedStudentData = data;
  if (!feesStudentEmpty || !feesStudentContent) return;

  feesStudentEmpty.classList.add('hidden');
  feesStudentContent.classList.remove('hidden');

  const student = data.student || {};
  if (feesStudentNameEl) {
    feesStudentNameEl.textContent = student.full_name || `${student.last_name || ''} ${student.first_name || ''}`;
  }
  if (feesStudentMetaEl) {
    const belt = student.belt ? `Cinturón: ${student.belt}` : '';
    const st = student.status ? `Estado: ${student.status}` : '';
    feesStudentMetaEl.textContent = [belt, st].filter(Boolean).join(' · ');
  }
  if (feesStudentStatusEl) {
    feesStudentStatusEl.innerHTML = '';
    const pill = feesStatusToPill(data.status);
    feesStudentStatusEl.appendChild(pill);
    if (Number(data.overdue_total || 0) > 0) {
      const debt = document.createElement('div');
      debt.className = 'text-muted';
      debt.textContent = `Deuda vencida: $${Number(data.overdue_total || 0).toFixed(2)}`;
      feesStudentStatusEl.appendChild(debt);
    }
  }

  if (feesDiscountType) feesDiscountType.value = data.settings?.discount_type || '';
  if (feesDiscountValue) feesDiscountValue.value = String(data.settings?.discount_value ?? 0);

  feesSetDefaultPeriods();
  if (feesPaymentDate && !feesPaymentDate.value) feesPaymentDate.value = feesTodayDate();

  const charges = Array.isArray(data.charges) ? data.charges : [];
  if (feesChargesTbody) feesChargesTbody.innerHTML = '';
  if (feesChargesEmpty) feesChargesEmpty.style.display = charges.length === 0 ? 'block' : 'none';
  charges.forEach((c) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${normalizePeriodLabel(c.period, c.due_date)}</td>
      <td>${formatFeesDate(c.due_date)}</td>
      <td>$${Number(c.final_amount || 0).toFixed(2)}</td>
      <td>$${Number(c.paid_amount || 0).toFixed(2)}</td>
      <td>$${Number(c.balance || 0).toFixed(2)}</td>
      <td></td>
    `;
    tr.children[5].appendChild(feesChargeStatusToPill(c));
    feesChargesTbody?.appendChild(tr);
  });

  if (feesApplyList) {
    feesApplyList.innerHTML = '';
    const payable = charges.filter((c) => Number(c.balance || 0) > 0);
    if (payable.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'text-muted';
      empty.textContent = 'No hay cuotas con saldo.';
      feesApplyList.appendChild(empty);
    } else {
      payable
        .sort((a, b) => String(a.due_date || '').localeCompare(String(b.due_date || '')))
        .forEach((c) => {
          const row = document.createElement('label');
          row.className = 'fees-apply-item';
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.checked = true;
          cb.dataset.chargeId = String(c.id);
          const text = document.createElement('span');
          text.textContent = `${normalizePeriodLabel(c.period, c.due_date)} · Saldo $${Number(c.balance || 0).toFixed(2)}`;
          row.appendChild(cb);
          row.appendChild(text);
          feesApplyList.appendChild(row);
        });
    }
  }

  const payments = Array.isArray(data.payments) ? data.payments : [];
  if (feesPaymentsTbody) feesPaymentsTbody.innerHTML = '';
  if (feesPaymentsEmpty) feesPaymentsEmpty.style.display = payments.length === 0 ? 'block' : 'none';
  payments.forEach((p) => {
    const tr = document.createElement('tr');
    const methodLabel = p.method === 'transfer' ? 'Transferencia' : (p.method === 'cash' ? 'Efectivo' : '-');
    tr.innerHTML = `
      <td>${formatFeesDate(p.payment_date)}</td>
      <td>$${Number(p.amount || 0).toFixed(2)}</td>
      <td>${methodLabel}</td>
      <td>${p.reference || '-'}</td>
      <td></td>
    `;
    const actionsTd = tr.children[4];
    if (p.id != null) {
      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'btn-secondary';
      del.textContent = 'Eliminar';
      del.addEventListener('click', async (e) => {
        e.stopPropagation();
        try {
          await apiSend(`/api/fees/payment/${p.id}`, 'DELETE');
          await loadFeesStudentDetail();
          await loadFeesOverview();
        } catch (err) {
          console.error(err);
        }
      });
      actionsTd.appendChild(del);
    }
    feesPaymentsTbody?.appendChild(tr);
  });
}

async function loadFeesStudentDetail() {
  if (feesSelectedStudentId == null) return;
  try {
    const data = await apiGet(`/api/fees/student/${feesSelectedStudentId}`);
    renderFeesStudentDetail(data);
  } catch (err) {
    console.error(err);
  }
}

btnFeesGenerateStudent?.addEventListener('click', async () => {
  if (feesSelectedStudentId == null) return;
  const payload = {
    proration_mode: feesChargeProrationMode?.value || undefined,
    proration_percent: feesChargeProrationPercent?.value || undefined,
    start_date: feesChargeStartDate?.value || undefined,
    ...getPeriodRangePayload(feesChargePeriod),
  };
  try {
    await apiSend(`/api/fees/student/${feesSelectedStudentId}/charges/generate`, 'POST', payload);
    await loadFeesStudentDetail();
    await loadFeesOverview();
  } catch (err) {
    console.error(err);
    alert(err?.message || 'No se pudo generar la cuota.');
  }
});

btnFeesGenerateMonth?.addEventListener('click', async () => {
  const payload = {
    proration_mode: feesBulkProrationMode?.value || undefined,
    proration_percent: feesBulkProrationPercent?.value || undefined,
    start_date: feesBulkStartDate?.value || undefined,
    ...getPeriodRangePayload(feesBulkPeriod),
  };
  try {
    const res = await apiSend('/api/fees/generate-month', 'POST', payload);
    alert(`Cuotas generadas: ${res?.created ?? 0}`);
    await loadFeesOverview();
    await loadFeesStudentDetail();
  } catch (err) {
    console.error(err);
    alert(err?.message || 'No se pudieron generar cuotas.');
  }
});

feesPaymentForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (feesSelectedStudentId == null) return;

  const chargeIds = [];
  feesApplyList?.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
    if (cb.checked && cb.dataset.chargeId) {
      chargeIds.push(Number(cb.dataset.chargeId));
    }
  });

  const payload = {
    payment_date: feesPaymentDate?.value || undefined,
    amount: Number(feesPaymentAmount?.value || 0),
    method: feesPaymentMethod?.value || 'cash',
    reference: feesPaymentReference?.value || undefined,
    notes: feesPaymentNotes?.value || undefined,
    apply_to_charge_ids: chargeIds,
  };

  const submitBtn = feesPaymentForm.querySelector('button[type="submit"]');
  try {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = 'Registrando...';
    }
    await apiSend(`/api/fees/student/${feesSelectedStudentId}/payments`, 'POST', payload);
    if (feesPaymentAmount) feesPaymentAmount.value = '';
    if (feesPaymentReference) feesPaymentReference.value = '';
    if (feesPaymentNotes) feesPaymentNotes.value = '';
    await loadFeesStudentDetail();
    await loadFeesOverview();
  } catch (err) {
    console.error(err);
    alert(err?.message || 'No se pudo registrar el pago.');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Registrar pago';
    }
  }
});

feesDiscountForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (feesSelectedStudentId == null) return;
  const payload = {
    discount_type: feesDiscountType?.value || '',
    discount_value: Number(feesDiscountValue?.value || 0),
  };
  try {
    await apiSend(`/api/fees/student/${feesSelectedStudentId}/settings`, 'PUT', payload);
    await loadFeesStudentDetail();
    await loadFeesOverview();
    alert('Descuento guardado.');
  } catch (err) {
    console.error(err);
    alert(err?.message || 'No se pudo guardar el descuento.');
  }
});

feesSearchInput?.addEventListener('input', () => {
  renderFeesOverview();
});

btnFeesRefresh?.addEventListener('click', async () => {
  await loadFeesConfig();
  await loadFeesOverview();
  await loadFeesStudentDetail();
});

function feesInitDefaults() {
  feesSetDefaultPeriods();
  if (feesPaymentDate && !feesPaymentDate.value) feesPaymentDate.value = feesTodayDate();
}

feesInitDefaults();

const examStudentNameInput = document.getElementById('exam-student-name');

function setupStudentNameAutocomplete(inputEl, hiddenEl, suggestionsEl, onSelect) {
  if (!inputEl || !hiddenEl || !suggestionsEl) return;

  inputEl.addEventListener('input', () => {
    hiddenEl.value = '';

    const query = inputEl.value.toLowerCase().trim();
    suggestionsEl.innerHTML = '';
    if (!query || !studentsCache.length) return;

    const matches = studentsCache
      .filter((s) => (s.full_name || '').toLowerCase().includes(query))
      .slice(0, 8);
    matches.forEach((s) => {
      const div = document.createElement('div');
      div.className = 'student-suggestion-item';
      const label = s.full_name || `${s.last_name || ''} ${s.first_name || ''}`;
      const belt = s.belt ? ` • ${s.belt.toUpperCase()}` : '';
      div.textContent = `${label}${belt}`;
      div.addEventListener('click', () => {
        inputEl.value = label;
        hiddenEl.value = s.id;
        suggestionsEl.innerHTML = '';
        if (typeof onSelect === 'function') {
          onSelect(s);
        }
      });
      suggestionsEl.appendChild(div);
    });
  });

  document.addEventListener('click', (e) => {
    if (!suggestionsEl.contains(e.target) && e.target !== inputEl) {
      suggestionsEl.innerHTML = '';
    }
  });
}

// Carga inicial
loadStudents();
loadEvents();
loadFeesConfig();
loadFeesOverview();

setupStudentNameAutocomplete(
  examStudentNameInput,
  examStudentIdInput,
  document.getElementById('exam-student-suggestions'),
);

// Establecer fecha de hoy por defecto en los inputs de fecha nativos si están vacíos
(function setDefaultDatesToToday() {
  const today = new Date();
  const yyyy = today.getFullYear();
  const mm = String(today.getMonth() + 1).padStart(2, '0');
  const dd = String(today.getDate()).padStart(2, '0');
  const todayStr = `${yyyy}-${mm}-${dd}`;

  const examDateInput = document.getElementById('exam-date');
  if (examDateInput && !examDateInput.value) {
    examDateInput.value = todayStr;
  }

  const feesPaymentDateInput = document.getElementById('fees-payment-date');
  if (feesPaymentDateInput && !feesPaymentDateInput.value) {
    feesPaymentDateInput.value = todayStr;
  }

  // Fecha de nacimiento: la dejamos vacía por defecto, para que siempre se elija explícitamente
})();

// Inicializar Flatpickr como datepicker oscuro si está disponible
(function initFlatpickrDatepickers() {
  if (typeof flatpickr === 'undefined') return;
  flatpickr('#fees-payment-date', {
    dateFormat: 'Y-m-d',
    defaultDate: document.getElementById('fees-payment-date')?.value || undefined,
    altInput: true,
    altFormat: 'd/m/Y',
    locale: 'es',
    disableMobile: true,
  });

  flatpickr('#fees-bulk-start-date', {
    dateFormat: 'Y-m-d',
    defaultDate: document.getElementById('fees-bulk-start-date')?.value || undefined,
    altInput: true,
    altFormat: 'd/m/Y',
    locale: 'es',
    disableMobile: true,
  });

  flatpickr('#fees-charge-start-date', {
    dateFormat: 'Y-m-d',
    defaultDate: document.getElementById('fees-charge-start-date')?.value || undefined,
    altInput: true,
    altFormat: 'd/m/Y',
    locale: 'es',
    disableMobile: true,
  });

  flatpickr('#fees-bulk-period', {
    mode: 'range',
    dateFormat: 'Y-m-d',
    defaultDate: document.getElementById('fees-bulk-period')?.value
      ? document.getElementById('fees-bulk-period').value.split(' to ')
      : undefined,
    altInput: true,
    altFormat: 'd/m/Y',
    locale: 'es',
    disableMobile: true,
  });

  flatpickr('#fees-charge-period', {
    mode: 'range',
    dateFormat: 'Y-m-d',
    defaultDate: document.getElementById('fees-charge-period')?.value
      ? document.getElementById('fees-charge-period').value.split(' to ')
      : undefined,
    altInput: true,
    altFormat: 'd/m/Y',
    locale: 'es',
    disableMobile: true,
  });

  flatpickr('#exam-date', {
    dateFormat: 'Y-m-d',
    defaultDate: document.getElementById('exam-date')?.value || undefined,
    altInput: true,
    altFormat: 'd/m/Y',
    locale: 'es',
    disableMobile: true,
  });

  flatpickr('#student-birthdate', {
    dateFormat: 'Y-m-d',
    altInput: true,
    altFormat: 'd/m/Y',
    locale: 'es',
    disableMobile: true,
    // No defaultDate para obligar a elegir nacimiento
  });
})();
