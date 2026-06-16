// ============================================================
// main.js — SmartPark ITS Frontend Logic
// Features: Live timer, slot filtering, auto-refresh, UI utils
// ============================================================

/* ---- Live Parking Timer ---- */
function updateTimer() {
  const el = document.getElementById('liveTimer');
  if (!el) return;

  const startStr = el.dataset.start;           // format: "YYYY-MM-DD HH:MM:SS"
  if (!startStr) return;

  const start = new Date(startStr.replace(' ', 'T'));

  function tick() {
    const now  = new Date();
    const diff = Math.floor((now - start) / 1000);  // seconds elapsed

    const h = Math.floor(diff / 3600);
    const m = Math.floor((diff % 3600) / 60);
    const s = diff % 60;

    const pad = n => String(n).padStart(2, '0');
    el.textContent = `${pad(h)}:${pad(m)}:${pad(s)}`;
  }

  tick();
  setInterval(tick, 1000);
}

/* ---- Slot Filtering by Vehicle Type ---- */
function filterSlots(type, btn) {
  // Update active tab
  document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');

  // Show/hide slot cards
  document.querySelectorAll('.slot-card').forEach(card => {
    if (type === 'all' || card.dataset.vehicle === type) {
      card.style.display = '';
    } else {
      card.style.display = 'none';
    }
  });
}

/* ---- Apply a slot snapshot to the grid (shared by WS + polling) ---- */
function applySlots(slots) {
  slots.forEach(slot => {
    const card = document.getElementById(`slot-${slot.id}`);
    if (!card) return;
    card.classList.remove('available', 'occupied', 'reserved');
    card.classList.add(slot.status);
    const badge = card.querySelector('.badge');
    if (badge) {
      const label = slot.status.charAt(0).toUpperCase() + slot.status.slice(1);
      badge.textContent = label;
      badge.className = `badge badge-${slot.status}`;
    }
    // Live surge-aware rate, if shown.
    const rateEl = card.querySelector('[data-rate]');
    if (rateEl && slot.current_rate != null) {
      rateEl.textContent = `₹${Math.round(slot.current_rate)}/hr`;
    }
  });
}

/* ---- Manual refresh button (uses /api/slots) ---- */
function refreshSlots() {
  const icon = document.getElementById('refreshIcon');
  if (icon) icon.classList.add('fa-spin');
  fetch('/api/slots')
    .then(res => res.json())
    .then(applySlots)
    .catch(err => console.warn('Refresh failed:', err))
    .finally(() => setTimeout(() => { if (icon) icon.classList.remove('fa-spin'); }, 600));
}

/* ---- Real-time updates via WebSockets, with polling fallback ---- */
function startRealtime() {
  if (!document.getElementById('slotsGrid')) return;

  let usingSocket = false;
  if (window.io) {
    try {
      const socket = io({ transports: ['websocket', 'polling'] });
      socket.on('connect', () => { usingSocket = true; socket.emit('subscribe_slots'); });
      socket.on('slot_snapshot', applySlots);
      socket.on('slot_update', (slots) => {
        applySlots(slots);
        const dot = document.getElementById('liveDot');
        if (dot) { dot.classList.add('flash'); setTimeout(() => dot.classList.remove('flash'), 600); }
      });
      socket.on('disconnect', () => { usingSocket = false; });
    } catch (e) { console.warn('WS init failed, falling back to polling', e); }
  }
  // Fallback poll only kicks in if the socket isn't delivering.
  setInterval(() => { if (!usingSocket) refreshSlots(); }, 15000);
}

/* ---- Toggle Password Visibility ---- */
function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  const icon  = document.getElementById(`eyeIcon_${inputId}`);
  if (!input || !icon) return;

  if (input.type === 'password') {
    input.type = 'text';
    icon.classList.replace('fa-eye', 'fa-eye-slash');
  } else {
    input.type = 'password';
    icon.classList.replace('fa-eye-slash', 'fa-eye');
  }
}

/* ---- Mobile Hamburger Menu ---- */
function initHamburger() {
  const btn   = document.getElementById('navHamburger');
  const links = document.querySelector('.nav-links');
  if (!btn || !links) return;

  btn.addEventListener('click', () => {
    links.classList.toggle('open');
  });

  // Close menu when a link is clicked
  links.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => links.classList.remove('open'));
  });
}

/* ---- Flash Message Auto-Dismiss (after 5s) ---- */
function initFlashDismiss() {
  document.querySelectorAll('.flash').forEach(flash => {
    setTimeout(() => {
      flash.style.opacity = '0';
      flash.style.transform = 'translateX(30px)';
      flash.style.transition = 'opacity .4s ease, transform .4s ease';
      setTimeout(() => flash.remove(), 400);
    }, 5000);
  });
}

/* ---- Add loading spinner to submit buttons ---- */
function initFormLoading() {
  document.querySelectorAll('form').forEach(form => {
    form.addEventListener('submit', () => {
      const btn = form.querySelector('button[type="submit"]');
      if (btn && !btn.disabled) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Please wait...';
      }
    });
  });
}

/* ---- Animate slot cards on page load ---- */
function animateSlots() {
  const cards = document.querySelectorAll('.slot-card');
  cards.forEach((card, i) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(20px)';
    card.style.transition = 'none';
    setTimeout(() => {
      card.style.transition = 'opacity .35s ease, transform .35s ease';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, 40 * i);
  });
}

/* ---- Init everything on DOM ready ---- */
document.addEventListener('DOMContentLoaded', () => {
  updateTimer();
  startRealtime();
  initHamburger();
  initFlashDismiss();
  initFormLoading();
  animateSlots();
});
