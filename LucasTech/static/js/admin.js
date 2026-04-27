/* ═══════════════════════════════════════════
   LUCASTECH ADMIN — Custom JavaScript
═══════════════════════════════════════════ */

document.addEventListener("DOMContentLoaded", function () {

  // ── 1. Compteurs dashboard ──────────────────
  document.querySelectorAll('.stat-number').forEach(el => {
    const target = parseInt(el.dataset.target || el.textContent, 10);
    if (isNaN(target)) return;
    let current = 0;
    const step = Math.ceil(target / 40);
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = current.toLocaleString('fr-FR');
      if (current >= target) clearInterval(timer);
    }, 30);
  });

  // ── 2. Hover fluide sur les lignes table ────
  document.querySelectorAll('#changelist tbody tr').forEach(row => {
    row.style.transition = 'background .15s, transform .15s';
    row.addEventListener('mouseenter', () => {
      row.style.transform = 'translateX(2px)';
    });
    row.addEventListener('mouseleave', () => {
      row.style.transform = 'translateX(0)';
    });
  });

  // ── 3. Animation entrée des cards ──────────
  const observer = new IntersectionObserver(entries => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'translateY(0)';
        }, i * 60);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.card, .module, .app-list .model').forEach(el => {
    el.style.opacity = '0';
    el.style.transform = 'translateY(12px)';
    el.style.transition = 'opacity .4s ease, transform .4s ease';
    observer.observe(el);
  });

  // ── 4. Confirmation suppression ─────────────
  document.querySelectorAll('.deletelink, [type=submit][name=action]').forEach(btn => {
    btn.addEventListener('click', function (e) {
      const action = document.querySelector('select[name=action]');
      if (action && action.value && action.value.includes('delete')) {
        const checked = document.querySelectorAll('#changelist input[type=checkbox]:checked');
        if (checked.length > 0) {
          if (!confirm(`⚠️ Supprimer ${checked.length} élément(s) ? Cette action est irréversible.`)) {
            e.preventDefault();
          }
        }
      }
    });
  });

  // ── 5. Raccourcis clavier ───────────────────
  document.addEventListener('keydown', e => {
    // Alt + N → Nouveau (bouton add)
    if (e.altKey && e.key === 'n') {
      const addBtn = document.querySelector('.addlink, .object-tools .addlink');
      if (addBtn) addBtn.click();
    }
    // Alt + S → Sauvegarder
    if (e.altKey && e.key === 's') {
      const saveBtn = document.querySelector('[name=_save]');
      if (saveBtn) saveBtn.click();
    }
    // Echap → Retour liste
    if (e.key === 'Escape') {
      const back = document.querySelector('.breadcrumb a:last-of-type');
      if (back && document.querySelector('.submit-row')) back.click();
    }
  });

  // ── 6. Indicateur de sauvegarde ────────────
  const saveBtn = document.querySelector('[name=_save]');
  if (saveBtn) {
    saveBtn.addEventListener('click', function () {
      this.textContent = '⏳ Sauvegarde...';
      this.disabled = true;
    });
  }

  // ── 7. Toast notification (si message Django) ──
  document.querySelectorAll('.messagelist li').forEach((msg, i) => {
    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed;
      bottom: ${24 + i * 64}px;
      right: 24px;
      z-index: 9999;
      padding: 14px 20px;
      border-radius: 10px;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: .85rem;
      font-weight: 600;
      box-shadow: 0 8px 32px rgba(0,0,0,.4);
      max-width: 360px;
      animation: slideIn .3s ease;
      cursor: pointer;
    `;

    if (msg.classList.contains('success')) {
      toast.style.background = 'rgba(63,185,80,.15)';
      toast.style.border = '1px solid rgba(63,185,80,.35)';
      toast.style.color = '#3fb950';
      toast.textContent = '✓ ' + msg.textContent.trim();
    } else if (msg.classList.contains('error')) {
      toast.style.background = 'rgba(248,81,73,.15)';
      toast.style.border = '1px solid rgba(248,81,73,.35)';
      toast.style.color = '#f85149';
      toast.textContent = '✗ ' + msg.textContent.trim();
    } else {
      toast.style.background = 'rgba(201,68,10,.15)';
      toast.style.border = '1px solid rgba(201,68,10,.35)';
      toast.style.color = '#c9440a';
      toast.textContent = 'ℹ ' + msg.textContent.trim();
    }

    document.body.appendChild(toast);
    toast.addEventListener('click', () => toast.remove());

    setTimeout(() => {
      toast.style.transition = 'opacity .4s, transform .4s';
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      setTimeout(() => toast.remove(), 400);
    }, 4000);

    // Cache le message original
    msg.style.display = 'none';
  });

  // ── 8. Barre de recherche : focus auto ──────
  const search = document.querySelector('#searchbar');
  if (search && !document.querySelector('.submit-row')) {
    setTimeout(() => search.focus(), 200);
  }

  // ── 9. Sélectionner tout / désélectionner ───
  const selectAll = document.querySelector('#action-toggle');
  if (selectAll) {
    selectAll.addEventListener('change', function () {
      const label = this.checked ? 'Tout désélectionner' : 'Tout sélectionner';
      this.title = label;
    });
  }

  // ── 10. Affichage du nombre de lignes sélectionnées ──
  const checkboxes = document.querySelectorAll('#changelist input[type=checkbox]:not(#action-toggle)');
  if (checkboxes.length > 0) {
    const counter = document.createElement('span');
    counter.style.cssText = `
      font-size: .75rem;
      color: #8b949e;
      margin-left: 10px;
      font-family: 'Plus Jakarta Sans', sans-serif;
    `;
    const actionBar = document.querySelector('#changelist-form .actions');
    if (actionBar) actionBar.appendChild(counter);

    checkboxes.forEach(cb => {
      cb.addEventListener('change', () => {
        const n = document.querySelectorAll('#changelist input[type=checkbox]:not(#action-toggle):checked').length;
        counter.textContent = n > 0 ? `${n} sélectionné${n > 1 ? 's' : ''}` : '';
      });
    });
  }

  console.log('%c LucasTech Admin ✓', 'color:#c9440a;font-weight:800;font-size:14px;');
});

/* Animation CSS injectée via JS */
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from { opacity: 0; transform: translateX(30px); }
    to   { opacity: 1; transform: translateX(0); }
  }
`;
document.head.appendChild(style);