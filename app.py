<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>نظام الشفتات الطبي - النسخة النهائية</title>
<style>
    :root {
        --primary-color: #667eea;
        --secondary-color: #764ba2;
        --light-gray: #f0f4f8;
        --white: #fff;
        --dark-gray: #495057;
        --border-color: #e9ecef;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background: var(--light-gray);
        padding: 10px;
        color: #333;
        min-height: 100vh;
    }
    .header {
        background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
        color: var(--white);
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    .header h1 { font-size: 2rem; }
    .controls {
        background: var(--white);
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
    }
    .form-row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 15px;
        align-items: end;
    }
    .form-group { display: flex; flex-direction: column; }
    .form-group label { font-weight: 600; margin-bottom: 5px; color: var(--dark-gray); }
    .form-group input, .form-group select {
        padding: 12px;
        border: 2px solid var(--border-color);
        border-radius: 10px;
        font-size: 16px;
        transition: border-color 0.3s ease;
    }
    .form-group input:focus, .form-group select:focus { outline: none; border-color: var(--primary-color); }
    .btn {
        padding: 12px 20px;
        border: none;
        border-radius: 10px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        margin: 5px 0;
    }
    .btn-primary { background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%); color: var(--white); }
    .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4); }
    .btn-success { background: #28a745; color: var(--white); }
    .btn-warning { background: #ffc107; color: #212529; }
    .btn-settings { background: linear-gradient(135deg, #6c757d 0%, var(--dark-gray) 100%); color: var(--white); }
    
    .table-container {
        background: var(--white);
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
        overflow-x: auto;
        max-height: 80vh;
    }
    .schedule-table { width: 100%; border-collapse: separate; border-spacing: 1px; }
    .schedule-table th {
        background: var(--dark-gray);
        color: var(--white);
        padding: 10px 5px;
        font-size: 0.8rem;
        min-width: 50px;
        position: sticky;
        top: 0;
        z-index: 10;
    }
    .schedule-table th.doctor-name-header {
        background: var(--primary-color);
        min-width: 180px;
        position: sticky;
        right: 0;
        z-index: 11;
    }
    .schedule-table td {
        background: var(--white);
        padding: 4px;
        text-align: center;
        height: 40px;
        border: 1px solid var(--border-color);
        cursor: pointer;
    }
    .schedule-table td.doctor-name {
        font-weight: 600;
        text-align: right;
        padding-right: 15px;
        position: sticky;
        right: 0;
        z-index: 5;
        background: #f8f9fa;
    }
    .shift-cell { font-size: 0.8rem; font-weight: bold; border-radius: 4px; height: 100%; display: flex; align-items: center; justify-content: center; }
    .shift-morning { background: #c8e6c9; color: #2e7d32; }
    .shift-evening { background: #ffecb3; color: #f57f17; }
    .shift-night { background: #d1c4e9; color: #6a1b9a; }
    .shift-off { background: #f5f5f5; color: #9e9e9e; }
    .shift-vacation { background: #ffcdd2; color: #c62828; }
    
    .modal {
        display: none;
        position: fixed;
        z-index: 1001;
        left: 0; top: 0;
        width: 100%; height: 100%;
        background-color: rgba(0, 0, 0, 0.6);
        align-items: center;
        justify-content: center;
    }
    .modal.active { display: flex; }
    .modal-content {
        background-color: var(--white);
        padding: 25px;
        border-radius: 15px;
        width: 90%;
        max-width: 450px;
        box-shadow: 0 5px 25px rgba(0, 0, 0, 0.2);
    }
    .modal-content .close {
        float: left;
        font-size: 28px;
        font-weight: bold;
        cursor: pointer;
    }
    #alertContainer {
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 1100;
    }
    .alert { padding: 15px 25px; border-radius: 10px; margin-bottom: 10px; font-weight: 600; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    .alert-success { background: #d4edda; color: #155724; }
    .alert-warning { background: #fff3cd; color: #856404; }
    .alert-info { background: #d1ecf1; color: #0c5460; }
</style>
</head>
<body>

<div class="header">
  <h1>🏥 نظام إدارة الشفتات الطبي - النسخة النهائية</h1>
</div>

<div class="controls">
  <div class="form-row">
    <div class="form-group">
      <label for="yearSelect">السنة</label>
      <select id="yearSelect"></select>
    </div>
    <div class="form-group">
      <label for="monthSelect">الشهر</label>
      <select id="monthSelect"></select>
    </div>
    <button class="btn btn-primary" onclick="generateSchedule()">🎯 إنشاء / تحديث الجدول</button>
    <button class="btn btn-success" onclick="showModal('addDoctorModal')">👨‍⚕️ إضافة طبيب</button>
    <button class="btn btn-warning" onclick="showModal('assignShiftModal')">✏️ تعيين شفت</button>
    <button class="btn btn-settings" onclick="showModal('settingsModal')">⚙️ إعدادات</button>
  </div>
  <div id="alertContainer"></div>
</div>

<div class="table-container" id="tableContainer" style="display:none;">
  <table class="schedule-table" id="scheduleTable"></table>
</div>

<!-- ===== Modals ===== -->
<div id="addDoctorModal" class="modal">
  <div class="modal-content">
    <span class="close" onclick="closeModal('addDoctorModal')">&times;</span>
    <h2>👨‍⚕️ إضافة طبيب جديد</h2>
    <div class="form-group">
      <label for="newDoctorName">اسم الطبيب</label>
      <input type="text" id="newDoctorName" placeholder="مثال: د. عبدالله محمد">
    </div>
    <button class="btn btn-primary" onclick="addNewDoctor()">إضافة الطبيب</button>
  </div>
</div>

<div id="assignShiftModal" class="modal">
  <div class="modal-content">
    <span class="close" onclick="closeModal('assignShiftModal')">&times;</span>
    <h2>✏️ تعيين شفت</h2>
    <div class="form-group">
      <label for="assignDoctorSelect">اختر الطبيب</label>
      <select id="assignDoctorSelect"></select>
    </div>
    <div class="form-group">
      <label for="assignDateInput">التاريخ</label>
      <input type="date" id="assignDateInput">
    </div>
    <div class="form-group">
      <label for="assignShiftTypeSelect">نوع الشفت</label>
      <select id="assignShiftTypeSelect">
        <option value="morning">🌅 صبح</option>
        <option value="evening">🌆 مساء</option>
        <option value="night">🌙 ليل</option>
        <option value="off">🏠 راحة</option>
        <option value="vacation">✈️ إجازة</option>
      </select>
    </div>
    <button class="btn btn-primary" onclick="assignShift()">تعيين الشفت</button>
  </div>
</div>

<div id="settingsModal" class="modal">
  <!-- محتوى إعدادات التوزيع سيضاف لاحقاً -->
  <div class="modal-content">
      <span class="close" onclick="closeModal('settingsModal')">&times;</span>
      <h2>⚙️ إعدادات التوزيع (قيد التطوير)</h2>
      <p>هنا يمكنك التحكم في قيود التوزيع التلقائي للشفتات.</p>
  </div>
</div>


<script>
class ShiftManager {
    constructor() {
        this.doctors = [];
        this.schedule = {}; // { doctorId: { "YYYY-MM-DD": { type: "morning" } } }
        this.currentYear = new Date().getFullYear();
        this.currentMonth = new Date().getMonth() + 1;
        this.nextDoctorId = 1;
    }

    initializeDefaultDoctors() {
        if (this.doctors.length > 0) return;
        for (let i = 0; i < 60; i++) {
            this.addDoctor(`د. طبيب ${i + 1}`, false);
        }
    }

    addDoctor(name, isNew = true) {
        const newDoctor = {
            id: this.nextDoctorId++,
            name: name,
        };
        this.doctors.push(newDoctor);
        if (isNew) {
            this.updateUIAfterChange();
            showAlert(`تمت إضافة الطبيب ${name} بنجاح!`, 'success');
        }
    }

    getDaysInMonth(year, month) {
        return new Date(year, month, 0).getDate();
    }

    generateEmptySchedule() {
        this.schedule = {};
        this.doctors.forEach(doc => {
            this.schedule[doc.id] = {};
        });
    }

    assignShiftToDoctor(doctorId, dateStr, shiftType) {
        if (!this.schedule[doctorId]) {
            this.schedule[doctorId] = {};
        }
        this.schedule[doctorId][dateStr] = { type: shiftType };
        this.updateUIAfterChange();
    }
    
    updateUIAfterChange() {
        displayScheduleTable(this.currentYear, this.currentMonth);
        updateAssignDoctorSelect();
    }
}

const shiftManager = new ShiftManager();

// --- UI Functions ---

function generateSchedule() {
    shiftManager.currentYear = parseInt(document.getElementById('yearSelect').value);
    shiftManager.currentMonth = parseInt(document.getElementById('monthSelect').value);
    shiftManager.initializeDefaultDoctors();
    shiftManager.generateEmptySchedule();
    shiftManager.updateUIAfterChange();
    showAlert('تم إنشاء الجدول بنجاح. يمكنك الآن إضافة الأطباء وتعيين الشفتات.', 'info');
}

function displayScheduleTable(year, month) {
    const tableContainer = document.getElementById('tableContainer');
    const table = document.getElementById('scheduleTable');
    if (!table || !tableContainer) return;
    
    tableContainer.style.display = 'block';
    table.innerHTML = '';

    const daysInMonth = shiftManager.getDaysInMonth(year, month);
    
    // Header Row
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.innerHTML = '<th class="doctor-name-header">اسم الطبيب</th>';
    for (let d = 1; d <= daysInMonth; d++) {
        const date = new Date(year, month - 1, d);
        const dayName = date.toLocaleDateString('ar-SA', { weekday: 'short' });
        headerRow.innerHTML += `<th>${d}<br>${dayName}</th>`;
    }
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Body Rows
    const tbody = document.createElement('tbody');
    shiftManager.doctors.forEach(doc => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td class="doctor-name">${doc.name}</td>`;
        for (let d = 1; d <= daysInMonth; d++) {
            const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const shift = shiftManager.schedule[doc.id] ? shiftManager.schedule[doc.id][dateStr] : null;
            let cellContent = '';
            if (shift) {
                const shiftInitial = shift.type.charAt(0).toUpperCase();
                cellContent = `<div class="shift-cell shift-${shift.type}">${shiftInitial}</div>`;
            }
            tr.innerHTML += `<td onclick="openQuickAssign(${doc.id}, '${dateStr}')">${cellContent}</td>`;
        }
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
}

function openQuickAssign(doctorId, dateStr) {
    document.getElementById('assignDoctorSelect').value = doctorId;
    document.getElementById('assignDateInput').value = dateStr;
    showModal('assignShiftModal');
}

function addNewDoctor() {
    const nameInput = document.getElementById('newDoctorName');
    const name = nameInput.value.trim();
    if (!name) {
        showAlert('الرجاء إدخال اسم الطبيب', 'warning');
        return;
    }
    shiftManager.addDoctor(name);
    nameInput.value = '';
    closeModal('addDoctorModal');
}

function assignShift() {
    const doctorId = parseInt(document.getElementById('assignDoctorSelect').value);
    const dateStr = document.getElementById('assignDateInput').value;
    const shiftType = document.getElementById('assignShiftTypeSelect').value;

    if (!doctorId || !dateStr) {
        showAlert('الرجاء اختيار الطبيب والتاريخ بشكل صحيح.', 'warning');
        return;
    }
    shiftManager.assignShiftToDoctor(doctorId, dateStr, shiftType);
    showAlert('تم تعيين الشفت بنجاح!', 'success');
    closeModal('assignShiftModal');
}


function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        if (modalId === 'assignShiftModal') {
            updateAssignDoctorSelect();
        }
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
}


function updateAssignDoctorSelect() {
    const select = document.getElementById('assignDoctorSelect');
    select.innerHTML = '';
    shiftManager.doctors.forEach(doc => {
        const option = document.createElement('option');
        option.value = doc.id;
        option.textContent = doc.name;
        select.appendChild(option);
    });
}

function showAlert(message, type = 'info') {
    const container = document.getElementById('alertContainer');
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    container.appendChild(alertDiv);
    setTimeout(() => alertDiv.remove(), 4000);
}

function openSettings() {
    showModal('settingsModal');
}
function saveSettings() {
    // Logic to save settings will be here
    closeModal('settingsModal');
    showAlert('تم حفظ الإعدادات بنجاح (قيد التطوير).', 'info');
}


document.addEventListener('DOMContentLoaded', () => {
    // Populate Year/Month dropdowns
    const yearSelect = document.getElementById('yearSelect');
    const currentYear = new Date().getFullYear();
    for (let y = currentYear - 2; y <= currentYear + 3; y++) {
        const option = document.createElement('option');
        option.value = y;
        option.textContent = y;
        if (y === currentYear) option.selected = true;
        yearSelect.appendChild(option);
    }

    const monthSelect = document.getElementById('monthSelect');
    const monthNames = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
    for (let m = 0; m < 12; m++) {
        const option = document.createElement('option');
        option.value = m + 1;
        option.textContent = monthNames[m];
        if (m === new Date().getMonth()) option.selected = true;
        monthSelect.appendChild(option);
    }
    
    // Add event listeners for dropdowns
    yearSelect.addEventListener('change', generateSchedule);
    monthSelect.addEventListener('change', generateSchedule);

    // Initial generation
    generateSchedule();
});

</script>

</body>
</html>
