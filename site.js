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

  // Search page.
  var list = document.getElementById('results');
  if (!list) return;
  var form = document.getElementById('search-form'), input = form.querySelector('input');
  var sortEl = document.getElementById('sort'), countEl = document.getElementById('count');
  var kicker = document.getElementById('kicker'), empty = document.getElementById('empty');
  var more = document.getElementById('more'), tries = document.getElementById('tries');
  var filters = document.querySelectorAll('.filter');
  var ORDER = { gold: 0, silver: 1, bronze: 2 }, NAMES = { gold: 'Gold', silver: 'Silver', bronze: 'Bronze' };
  var PAGE = 48, products = [], shown = PAGE;
  var params = new URLSearchParams(location.search);
  var state = {
    q: params.get('q') || '',
    tiers: (params.get('tier') || '').split(',').filter(function (t) { return t in ORDER; }),
    direct: params.get('direct') === '1',
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
    return '<li class="card"><a href="p/' + p.s + '.html">' +
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
    matched.forEach(function (p) { counts[p.m]++; });
    var out = matched.filter(function (p) {
      return (!state.tiers.length || state.tiers.indexOf(p.m) !== -1) && (!state.direct || p.d);
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
    filters.forEach(function (f) {
      var on = f.dataset.tier ? state.tiers.indexOf(f.dataset.tier) !== -1 : state.direct;
      f.setAttribute('aria-pressed', on);
      var n = f.querySelector('.n');
      if (n) n.textContent = counts[f.dataset.tier];
    });
    kicker.textContent = state.q ? 'Results for "' + state.q + '"' : 'All British finds';
    countEl.textContent = out.length + (out.length === 1 ? ' result' : ' results');
    tries.hidden = !!state.q;
    list.innerHTML = out.slice(0, shown).map(card).join('');
    empty.hidden = out.length > 0;
    more.hidden = out.length <= shown;
    syncUrl();
  }
  function change() { shown = PAGE; render(); }

  input.addEventListener('input', function () { state.q = input.value.trim(); change(); });
  form.addEventListener('submit', function (e) { e.preventDefault(); input.blur(); });
  sortEl.addEventListener('change', function () { state.sort = sortEl.value; change(); });
  filters.forEach(function (f) {
    f.addEventListener('click', function () {
      if (f.dataset.tier) {
        var i = state.tiers.indexOf(f.dataset.tier);
        if (i === -1) state.tiers.push(f.dataset.tier); else state.tiers.splice(i, 1);
      } else { state.direct = !state.direct; }
      change();
    });
  });
  document.querySelectorAll('.try').forEach(function (b) {
    b.addEventListener('click', function () { input.value = b.textContent; input.dispatchEvent(new Event('input')); });
  });
  document.getElementById('reset').addEventListener('click', function () {
    state.tiers = []; state.direct = false; input.value = ''; input.dispatchEvent(new Event('input'));
  });
  more.addEventListener('click', function () { shown += PAGE; render(); });

  fetch('products.json').then(function (r) { return r.json(); }).then(function (data) {
    products = data; render();
  }).catch(function () { countEl.textContent = 'Search could not load. Please refresh the page.'; });
})();
