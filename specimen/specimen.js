/* specimen.js — the specimen board's theme tabs and readouts, driven by the
   real runtime (../ui-theme/ui-theme.js -> window.UITheme). Loaded at the end
   of <body>, so the elements it needs already exist. */
(function () {
  'use strict';

  var T = window.UITheme;
  var tablist = document.getElementById('theme-tablist');

  function buildTab(theme) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ui-btn ui-btn--sm';
    btn.setAttribute('role', 'tab');
    btn.dataset.slug = theme.slug;
    var dot = document.createElement('span');
    dot.className = 'spec-swatch';
    dot.setAttribute('aria-hidden', 'true');
    dot.style.background = theme.swatch;
    btn.appendChild(dot);
    btn.appendChild(document.createTextNode(theme.name));
    btn.addEventListener('click', function () { T.set(theme.slug); });
    btn.addEventListener('keydown', onKeydown);
    return btn;
  }

  // Arrow keys move between tabs (roving tabindex), as a tablist should.
  function onKeydown(e) {
    var tabs = Array.prototype.slice.call(tablist.querySelectorAll('[role="tab"]'));
    var i = tabs.indexOf(e.currentTarget);
    var next = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1
      : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : null;
    if (next === null) return;
    e.preventDefault();
    var target = tabs[(next + tabs.length) % tabs.length];
    T.set(target.dataset.slug);
    target.focus();
  }

  function render() {
    var slug = T.current();
    var tabs = tablist.querySelectorAll('[role="tab"]');
    for (var i = 0; i < tabs.length; i++) {
      var on = tabs[i].dataset.slug === slug;
      tabs[i].setAttribute('aria-selected', on ? 'true' : 'false');
      tabs[i].setAttribute('aria-pressed', on ? 'true' : 'false');
      tabs[i].tabIndex = on ? 0 : -1;
    }
    var theme = T.theme();
    document.getElementById('readout-palette').textContent =
      document.documentElement.getAttribute('data-palette') || '(none: Purple)';
    document.getElementById('readout-theme').textContent = document.documentElement.getAttribute('data-theme');
    document.getElementById('readout-set').textContent = theme.set + ' theme';
  }

  T.list().forEach(function (theme) { tablist.appendChild(buildTab(theme)); });
  render();
  T.onChange(render);

  var indet = document.getElementById('spec-indet');
  if (indet) indet.indeterminate = true;

  document.getElementById('spec-confirm').addEventListener('click', function () {
    window.UIComponents.confirm({ title: 'Delete job?', message: 'This cannot be undone.',
                                  confirmLabel: 'Delete', danger: true })
      .then(function (ok) { window.UIComponents.toast(ok ? 'Deleted' : 'Kept', { kind: ok ? 'danger' : 'info' }); });
  });
  document.getElementById('spec-drawer-open').addEventListener('click', function () {
    document.getElementById('spec-drawer').showModal();
  });
  document.getElementById('spec-toast').addEventListener('click', function () {
    window.UIComponents.toast('Settings saved', { kind: 'success' });
  });
})();
