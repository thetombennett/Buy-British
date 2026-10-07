(function () {
  // Search boxes: show the clear button only when there is text.
  document.querySelectorAll('.search').forEach(function (form) {
    var input = form.querySelector('input'), clear = form.querySelector('.search-clear');
    function update() { clear.hidden = !input.value; }
    input.addEventListener('input', update);
    clear.addEventListener('click', function () {
      input.value = '';
      update();
      input.focus();
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    update();
  });

  // Product rails: arrow buttons.
  document.querySelectorAll('.rail-section').forEach(function (s) {
    var rail = s.querySelector('.rail');
    s.querySelectorAll('.rail-btn').forEach(function (b) {
      b.addEventListener('click', function () {
        rail.scrollBy({ left: Number(b.dataset.dir) * rail.clientWidth * 0.8, behavior: 'smooth' });
      });
    });
  });

  // Filter sheet: one "Filter" button opens it; active filters show as removable chips.
  var sheet = document.getElementById('filter-sheet');
  var sheetUI = null;
  if (sheet) {
    var opener = document.getElementById('open-filters'), badge = document.getElementById('filter-badge');
    var activeRow = document.getElementById('active-filters'), done = document.getElementById('sheet-done');
    var clearAll = document.getElementById('sheet-clear'), onClear = function () {};
    opener.addEventListener('click', function () { sheet.showModal(); });
    document.getElementById('sheet-close').addEventListener('click', function () { sheet.close(); });
    done.addEventListener('click', function () { sheet.close(); });
    sheet.addEventListener('click', function (e) { if (e.target === sheet) sheet.close(); });
    clearAll.addEventListener('click', function () { onClear(); });
    sheetUI = {
      // active: [{label, remove}], count: results showing, clear: turns every filter off
      update: function (active, count, clear) {
        onClear = clear;
        badge.hidden = !active.length;
        badge.textContent = active.length;
        opener.classList.toggle('on', active.length > 0);
        opener.setAttribute('aria-label', active.length ? 'Filter, ' + active.length + ' on' : 'Filter');
        clearAll.disabled = !active.length;
        done.textContent = 'Show ' + count + (count === 1 ? ' result' : ' results');
        activeRow.hidden = !active.length;
        activeRow.textContent = '';
        active.forEach(function (a) {
          var chip = document.createElement('button');
          chip.type = 'button';
          chip.className = 'active-chip';
          chip.setAttribute('aria-label', 'Remove filter: ' + a.label);
          chip.textContent = a.label + ' ✕';
          chip.addEventListener('click', a.remove);
          activeRow.appendChild(chip);
        });
      }
    };
  }

  // Category pages: filter the cards already on the page by who they are for.
  var list = document.getElementById('results');
  var pageFilters = list ? [] : Array.prototype.slice.call(document.querySelectorAll('.filter[data-gender]'));
  if (pageFilters.length) {
    var grids = Array.prototype.slice.call(document.querySelectorAll('main ul.grid'));
    var chosen = [];
    var apply = function () {
      var total = 0;
      grids.forEach(function (grid) {
        var visible = 0;
        Array.prototype.forEach.call(grid.children, function (li) {
          var show = !chosen.length || chosen.indexOf(li.dataset.g || 'unspecified') !== -1;
          li.hidden = !show;
          if (show) visible++;
        });
        var heading = grid.previousElementSibling;
        grid.hidden = heading.hidden = !visible;
        var link = heading.id && document.querySelector('.jump a[href="#' + heading.id + '"]');
        if (link) { link.hidden = !visible; link.querySelector('span').textContent = visible; }
        total += visible;
      });
      var active = [];
      pageFilters.forEach(function (f) {
        var on = chosen.indexOf(f.dataset.gender) !== -1;
        f.setAttribute('aria-pressed', on);
        if (on) active.push({ label: f.dataset.label, remove: function () { f.click(); } });
      });
      sheetUI.update(active, total, function () { chosen = []; apply(); });
    };
    pageFilters.forEach(function (f) {
      f.querySelector('.n').textContent = document.querySelectorAll(
        'main ul.grid > li[data-g="' + (f.dataset.gender === 'unspecified' ? '' : f.dataset.gender) + '"]').length;
      f.addEventListener('click', function () {
        var i = chosen.indexOf(f.dataset.gender);
        if (i === -1) chosen.push(f.dataset.gender); else chosen.splice(i, 1);
        apply();
      });
    });
    apply();
  }

  // Search page.
  if (!list) return;
  var form = document.getElementById('search-form'), input = form.querySelector('input');
  var sortEl = document.getElementById('sort'), countEl = document.getElementById('count');
  var kicker = document.getElementById('kicker'), empty = document.getElementById('empty');
  var more = document.getElementById('more'), tries = document.getElementById('tries');
  var filters = document.querySelectorAll('.filter');
  var ORDER = { gold: 0, silver: 1, bronze: 2 }, NAMES = { gold: 'Gold', silver: 'Silver', bronze: 'Bronze' };
  var GENDERS = ['women', 'men', 'unisex', 'unspecified'];
  var PAGE = 48, products = [], shown = PAGE;
  var params = new URLSearchParams(location.search);
  var state = {
    q: params.get('q') || '',
    tiers: (params.get('tier') || '').split(',').filter(function (t) { return t in ORDER; }),
    direct: params.get('direct') === '1',
    genders: (params.get('for') || '').split(',').filter(function (x) { return GENDERS.indexOf(x) !== -1; }),
    sort: params.get('sort') || 'most_british'
  };
  input.value = state.q;
  input.dispatchEvent(new Event('input'));
  sortEl.value = state.sort;
  if (!sortEl.value) { sortEl.value = state.sort = 'most_british'; }

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function money(p) { return '£' + p.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function card(p) {
    return '<li class="card" data-g="' + p.g + '"><a href="p/' + p.s + '.html">' +
      '<div class="thumb"><img src="' + esc(p.i) + '" alt="' + esc(p.t) + '" loading="lazy" width="480" height="600">' +
      '<span class="chips"><span class="chip chip-' + p.m + '"><svg class="medal" width="20" height="23" role="img" aria-label="' +
      NAMES[p.m] + ' medal"><use href="#medal-' + p.m + '"/></svg>' + NAMES[p.m] + '</span>' +
      (p.d ? '<span class="chip chip-direct">Direct</span>' : '') + '</span></div>' +
      '<div class="card-body"><span class="brand">' + esc(p.b) + '</span><span class="name">' + esc(p.t) + '</span>' +
      '<span class="price">' + (p.v ? 'From ' : '') + money(p.p) + '</span><span class="origin">' + esc(p.o) + '</span>' +
      '<span class="strip"><span>' + esc(p.b) + '</span><b>View ›</b></span></div></a></li>';
  }
  function syncUrl() {
    var u = new URLSearchParams();
    if (state.q) u.set('q', state.q);
    if (state.tiers.length) u.set('tier', state.tiers.join(','));
    if (state.direct) u.set('direct', '1');
    if (state.genders.length) u.set('for', state.genders.join(','));
    if (state.sort !== 'most_british') u.set('sort', state.sort);
    var qs = u.toString();
    history.replaceState(null, '', qs ? '?' + qs : location.pathname);
  }
  function render() {
    var words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    var matched = products.filter(function (p) {
      return words.every(function (w) { return p.k.indexOf(w) !== -1; });
    });
    function inName(p) { var t = p.t.toLowerCase(); return words.every(function (w) { return t.indexOf(w) !== -1; }) ? 1 : 0; }
    var counts = { gold: 0, silver: 0, bronze: 0 };
    var forCounts = { women: 0, men: 0, unisex: 0, unspecified: 0 };
    matched.forEach(function (p) { counts[p.m]++; forCounts[p.g || 'unspecified']++; });
    var out = matched.filter(function (p) {
      return (!state.tiers.length || state.tiers.indexOf(p.m) !== -1) && (!state.direct || p.d) &&
        (!state.genders.length || state.genders.indexOf(p.g || 'unspecified') !== -1);
    });
    var by = {
      // Products whose own name matches come before ones matched only by brand or category.
      most_british: function (a, b) { return inName(b) - inName(a) || ORDER[a.m] - ORDER[b.m] || a.p - b.p; },
      price_asc: function (a, b) { return a.p - b.p; },
      price_desc: function (a, b) { return b.p - a.p; },
      name_asc: function (a, b) { return a.t.localeCompare(b.t); },
      name_desc: function (a, b) { return b.t.localeCompare(a.t); }
    };
    out.sort(by[state.sort] || by.most_british);
    var active = [];
    filters.forEach(function (f) {
      var on = f.dataset.tier ? state.tiers.indexOf(f.dataset.tier) !== -1
        : f.dataset.gender ? state.genders.indexOf(f.dataset.gender) !== -1 : state.direct;
      f.setAttribute('aria-pressed', on);
      if (on) active.push({ label: f.dataset.label, remove: function () { f.click(); } });
      var n = f.querySelector('.n');
      if (n) n.textContent = f.dataset.tier ? counts[f.dataset.tier] : forCounts[f.dataset.gender];
    });
    kicker.textContent = state.q ? 'Results for "' + state.q + '"' : 'All British finds';
    countEl.textContent = out.length + (out.length === 1 ? ' result' : ' results');
    tries.hidden = !!state.q;
    list.innerHTML = out.slice(0, shown).map(card).join('');
    empty.hidden = out.length > 0;
    more.hidden = out.length <= shown;
    sheetUI.update(active, out.length, function () {
      state.tiers = []; state.genders = []; state.direct = false; change();
    });
    syncUrl();
  }
  function change() { shown = PAGE; render(); }

  input.addEventListener('input', function () { state.q = input.value.trim(); change(); });
  form.addEventListener('submit', function (e) { e.preventDefault(); input.blur(); });
  sortEl.addEventListener('change', function () { state.sort = sortEl.value; change(); });
  filters.forEach(function (f) {
    f.addEventListener('click', function () {
      var set = f.dataset.tier ? state.tiers : f.dataset.gender ? state.genders : null;
      var value = f.dataset.tier || f.dataset.gender;
      if (set) {
        var i = set.indexOf(value);
        if (i === -1) set.push(value); else set.splice(i, 1);
      } else { state.direct = !state.direct; }
      change();
    });
  });
  document.querySelectorAll('.try').forEach(function (b) {
    b.addEventListener('click', function () { input.value = b.textContent; input.dispatchEvent(new Event('input')); });
  });
  document.getElementById('reset').addEventListener('click', function () {
    state.tiers = []; state.genders = []; state.direct = false; input.value = ''; input.dispatchEvent(new Event('input'));
  });
  more.addEventListener('click', function () { shown += PAGE; render(); });

  fetch('products.json').then(function (r) { return r.json(); }).then(function (data) {
    products = data; render();
  }).catch(function () { countEl.textContent = 'Search could not load. Please refresh the page.'; });
})();
