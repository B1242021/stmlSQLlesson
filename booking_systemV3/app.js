// 核心設定：對接 FastAPI 的 8000 埠
const API_BASE = 'http://127.0.0.1:8000/api';
let currentStudentId = null;
let calendar;

async function register() {
    const student_id = document.getElementById('student_id').value;
    const password = document.getElementById('password').value;
    if(!student_id || !password) return alert("請輸入學號與密碼！");
    const res = await fetch(`${API_BASE}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id, password })
    });
    alert((await res.json()).message);
}

async function login() {
    const student_id = document.getElementById('student_id').value;
    const password = document.getElementById('password').value;
    if(!student_id || !password) return alert("請輸入學號與密碼！");
    const res = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id, password })
    });
    const data = await res.json();
    if (res.ok) {
        currentStudentId = data.student_id;
        document.getElementById('auth-section').classList.add('hidden');
        document.getElementById('app-section').classList.remove('hidden');
        document.getElementById('welcome-msg').innerText = `🏐 歡迎，${currentStudentId}！`;
        initCalendar();
    } else alert(data.detail || data.message);
}

function logout() { location.reload(); }

async function manualBook() {
    const date = document.getElementById('book-date').value;
    const hour = document.getElementById('book-hour').value;
    const court = document.getElementById('book-court').value;

    if (!date || !hour || !court) return alert("請完整選擇日期、時間與場地！");

    const dateObj = new Date(date);
    const day = dateObj.getDay();
    const h = parseInt(hour);

    if (day === 0 || day === 6) {
        if (h < 13 || h >= 19) return alert('❌ 假日僅開放 13:00 到 19:00 預約喔！');
    } else {
        if (h < 9 || h >= 21) return alert('❌ 平日僅開放 09:00 到 21:00 預約喔！');
    }

    const res = await fetch(`${API_BASE}/reservations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: currentStudentId, court_name: court, date: date, hour: h })
    });
    alert((await res.json()).message);
    loadReservations();
}

function initCalendar() {
    const calendarEl = document.getElementById('calendar');
    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'timeGridWeek',
        slotMinTime: '09:00:00',
        slotMaxTime: '21:00:00',
        allDaySlot: false,
        height: 650,
        businessHours: [
            { daysOfWeek: [ 1, 2, 3, 4, 5 ], startTime: '09:00', endTime: '21:00' },
            { daysOfWeek: [ 0, 6 ], startTime: '13:00', endTime: '19:00' }
        ],

        dateClick: async function(info) {
            const dateObj = new Date(info.date);
            const day = dateObj.getDay();
            const hour = dateObj.getHours();

            if (day === 0 || day === 6) {
                if (hour < 13 || hour >= 19) return alert('❌ 假日僅開放 13:00 到 19:00 預約喔！');
            } else {
                if (hour < 9 || hour >= 21) return alert('❌ 平日僅開放 09:00 到 21:00 預約喔！');
            }

            const dateStr = dateObj.getFullYear() + '-' + String(dateObj.getMonth() + 1).padStart(2, '0') + '-' + String(dateObj.getDate()).padStart(2, '0');

            // 顯示貼近點擊位置的 popover
            const court = await showCourtPopover(info.jsEvent, dateStr, hour);
            if (!court) return;

            if (court === 'AB') {
                // 同時預約 A場 和 B場，依序送出兩個請求
                const [resA, resB] = await Promise.all([
                    fetch(`${API_BASE}/reservations`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ student_id: currentStudentId, court_name: 'A場', date: dateStr, hour: hour })
                    }),
                    fetch(`${API_BASE}/reservations`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ student_id: currentStudentId, court_name: 'B場', date: dateStr, hour: hour })
                    })
                ]);
                const [dataA, dataB] = await Promise.all([resA.json(), resB.json()]);
                showToast(`A場：${dataA.message} ／ B場：${dataB.message}`);
            } else {
                const res = await fetch(`${API_BASE}/reservations`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ student_id: currentStudentId, court_name: court, date: dateStr, hour: hour })
                });
                showToast((await res.json()).message);
            }
            loadReservations();
        },

        eventClick: async function(info) {
            const resId = info.event.extendedProps.reservation_id;
            const participantsCount = info.event.extendedProps.participants_count;
            const courtName = info.event.extendedProps.court_name;
            const participantList = info.event.extendedProps.participants;

            if (participantList.includes(currentStudentId)) {
                if (confirm(`你已經在【${courtName}】的揪團中。\n確定要退出揪團（或取消預約）嗎？\n⚠️ 若你是最後一人，退出將自動釋放場地。`)) {
                    const res = await fetch(`${API_BASE}/reservations/${resId}/leave`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ student_id: currentStudentId })
                    });
                    showToast((await res.json()).message);
                    loadReservations();
                }
            } else {
                if (confirm(`【${courtName}】目前有 ${participantsCount}/14 人。\n確定要加入這個揪團嗎？`)) {
                    const res = await fetch(`${API_BASE}/reservations/${resId}/join`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ student_id: currentStudentId })
                    });
                    showToast((await res.json()).message);
                    loadReservations();
                }
            }
        }
    });

    calendar.render();
    loadReservations();
}

async function loadReservations() {
    const res = await fetch(`${API_BASE}/reservations`);
    const data = await res.json();

    calendar.removeAllEvents();

    data.forEach(item => {
        const startDateTime = `${item.date}T${String(item.hour).padStart(2, '0')}:00:00`;
        const endDateTime = `${item.date}T${String(item.hour + 1).padStart(2, '0')}:00:00`;

        const isFull = item.participants_count >= 14;
        let eventColor = '#f44336'; // 預設 A場 紅色

        if (item.court_name.includes('B') || item.court_name.includes('b')) {
            eventColor = '#4CAF50'; // B場 綠色
        } else if (item.court_name.includes('A') || item.court_name.includes('a')) {
            eventColor = '#f44336'; // A場 紅色
        }

        if (isFull) eventColor = '#9e9e9e';
        let fullText = isFull ? '(已滿團)' : `(${item.participants_count}/14人)`;
        let myPrefix = item.participants.includes(currentStudentId) ? '⭐ ' : '';

        calendar.addEvent({
            title: `${myPrefix}${item.court_name} ${fullText}`,
            start: startDateTime,
            end: endDateTime,
            color: eventColor,
            extendedProps: {
                reservation_id: item.id,
                participants_count: item.participants_count,
                court_name: item.court_name,
                participants: item.participants
            }
        });
    });
}

// ==========================================
// 點擊位置旁邊的 Popover（選 A場 / B場）
// ==========================================
function showCourtPopover(mouseEvent, dateStr, hour) {
    return new Promise((resolve) => {
        closePopover();

        const pop = document.createElement('div');
        pop.id = 'court-popover';
        pop.innerHTML = `
            <div class="cp-header">
                📅 ${dateStr} &nbsp; ${hour}:00 ~ ${hour + 1}:00
                <button class="cp-close" id="cp-close">✕</button>
            </div>
            <div class="cp-body">
                <div class="cp-label">選擇場地</div>
                <div class="cp-btns">
                    <button id="cp-a"  class="cp-btn cp-a">🔴 A 場</button>
                    <button id="cp-b"  class="cp-btn cp-b">🟢 B 場</button>
                    <button id="cp-ab" class="cp-btn cp-ab">🔴🟢 AB場</button>
                </div>
            </div>
        `;
        document.body.appendChild(pop);

        // 先讓瀏覽器 render，再算尺寸定位
        requestAnimationFrame(() => {
            const pw = pop.offsetWidth  || 220;
            const ph = pop.offsetHeight || 130;
            const vw = window.innerWidth;
            const vh = window.innerHeight;

            // 若 mouseEvent 存在就跟著滑鼠，否則置中
            let x, y;
            if (mouseEvent && mouseEvent.clientX != null) {
                x = mouseEvent.clientX + 14;
                y = mouseEvent.clientY + 14;
                if (x + pw > vw) x = mouseEvent.clientX - pw - 14;
                if (y + ph > vh) y = mouseEvent.clientY - ph - 14;
                if (x < 0) x = 8;
                if (y < 0) y = 8;
            } else {
                x = Math.max(8, (vw - pw) / 2);
                y = Math.max(8, (vh - ph) / 2);
            }
            pop.style.left = x + 'px';
            pop.style.top  = y + 'px';
        });

        const done = (val) => { closePopover(); resolve(val); };

        document.getElementById('cp-a').onclick  = () => done('A場');
        document.getElementById('cp-b').onclick  = () => done('B場');
        document.getElementById('cp-ab').onclick = () => done('AB');
        document.getElementById('cp-close').onclick = () => done(null);

        // 點擊 popover 外部自動關閉（延遲掛載避免立刻觸發）
        setTimeout(() => {
            document.addEventListener('click', function handler(e) {
                if (!pop.contains(e.target)) {
                    done(null);
                    document.removeEventListener('click', handler);
                }
            });
        }, 50);
    });
}

function closePopover() {
    const old = document.getElementById('court-popover');
    if (old) old.remove();
}

// ==========================================
// Toast 通知（取代 alert）
// ==========================================
function showToast(msg) {
    const toast = document.createElement('div');
    toast.className = 'toast-msg';
    toast.textContent = msg;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-show'));
    setTimeout(() => {
        toast.classList.remove('toast-show');
        setTimeout(() => toast.remove(), 400);
    }, 2800);
}
