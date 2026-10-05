// The example app's script: renders a few notes and wires the controls.
// Text goes in with textContent, never innerHTML.
(function () {
  'use strict';

  var notes = [
    { title: 'Groceries', body: 'Oats, lemons, coffee beans.', tag: 'today', kind: 'warning' },
    { title: 'Trip ideas', body: 'Coast in spring; mountains in autumn.', tag: 'ideas', kind: 'info' },
    { title: 'Release notes', body: 'Draft the changelog for 1.1.', tag: 'done', kind: 'success' },
  ];

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  }

  function card(note, index) {
    var c = el('article', 'ui-card');
    var meta = el('div', 'note-meta');
    meta.appendChild(el('h3', 'ui-card__title', note.title));
    meta.appendChild(el('span', 'ui-badge ui-badge--' + note.kind, note.tag));
    c.appendChild(meta);
    c.appendChild(el('p', 'note-body', note.body));
    var actions = el('div', 'ui-card__footer');
    var rename = el('button', 'ui-btn ui-btn--sm ui-btn--ghost', 'Rename');
    var remove = el('button', 'ui-btn ui-btn--sm ui-btn--danger', 'Delete');
    rename.type = remove.type = 'button';
    rename.addEventListener('click', function () {
      UIComponents.prompt({ title: 'Rename note', value: note.title }).then(function (name) {
        if (name) { note.title = name; render(); UIComponents.toast('Renamed', { kind: 'success' }); }
      });
    });
    remove.addEventListener('click', function () {
      UIComponents.confirm({ title: 'Delete "' + note.title + '"?', message: 'This cannot be undone.',
                             confirmLabel: 'Delete', danger: true }).then(function (ok) {
        if (ok) { notes.splice(index, 1); render(); UIComponents.toast('Deleted', { kind: 'danger' }); }
      });
    });
    actions.appendChild(rename);
    actions.appendChild(remove);
    c.appendChild(actions);
    return c;
  }

  function render() {
    var grid = document.getElementById('notes');
    grid.textContent = '';
    if (!notes.length) {
      var empty = el('div', 'ui-empty');
      empty.appendChild(el('h3', 'ui-empty__title', 'No notes'));
      empty.appendChild(el('p', null, 'New notes appear here.'));
      grid.appendChild(empty);
      return;
    }
    notes.forEach(function (n, i) { grid.appendChild(card(n, i)); });
  }

  document.getElementById('new-note').addEventListener('click', function () {
    UIComponents.prompt({ title: 'New note', placeholder: 'Title' }).then(function (title) {
      if (title) { notes.unshift({ title: title, body: 'Empty note.', tag: 'new', kind: 'info' }); render(); }
    });
  });

  // Segmented control: one pressed button at a time.
  document.querySelectorAll('.ui-segmented').forEach(function (group) {
    group.addEventListener('click', function (e) {
      var button = e.target.closest('button');
      if (!button || button.disabled) return;
      group.querySelectorAll('button').forEach(function (b) {
        b.setAttribute('aria-pressed', b === button ? 'true' : 'false');
      });
    });
  });

  // Small screens: the menu button shows the folder list.
  document.querySelector('.notes-menu').addEventListener('click', function () {
    var shell = document.querySelector('.ui-app');
    shell.toggleAttribute('data-nav-open');
  });

  // A canvas chart cannot read var(): resolve the tokens to colours with
  // UITheme.colors(), and redraw when the theme changes.
  var activity = [3, 5, 2, 6, 4, 1, 4];
  var days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  function drawChart() {
    var canvas = document.getElementById('activity');
    var ratio = window.devicePixelRatio || 1;
    var w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = w * ratio;
    canvas.height = h * ratio;
    var ctx = canvas.getContext('2d');
    ctx.scale(ratio, ratio);
    var t = UITheme.colors(['--seq-2', '--seq-5', '--chart-grid', '--text-secondary']);
    t['--font-sans'] = UITheme.token('--font-sans');
    var max = Math.max.apply(null, activity), pad = 20, bw = (w - pad) / activity.length;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = t['--chart-grid'];
    ctx.beginPath(); ctx.moveTo(0, h - pad + 0.5); ctx.lineTo(w, h - pad + 0.5); ctx.stroke();
    ctx.font = '12px ' + t['--font-sans'];
    ctx.textAlign = 'center';
    activity.forEach(function (n, i) {
      var bh = (h - pad * 2) * n / max;
      ctx.fillStyle = n === max ? t['--seq-5'] : t['--seq-2'];
      ctx.fillRect(pad / 2 + i * bw + bw * 0.2, h - pad - bh, bw * 0.6, bh);
      ctx.fillStyle = t['--text-secondary'];
      ctx.fillText(days[i], pad / 2 + i * bw + bw / 2, h - 5);
    });
  }
  UITheme.onChange(drawChart);
  window.addEventListener('resize', drawChart);

  render();
  drawChart();
})();
