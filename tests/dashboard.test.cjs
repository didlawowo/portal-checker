'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SCRIPT_PATH = path.join(__dirname, '..', 'static', 'script.js');
const SEARCH_STORAGE_KEY = 'portal-checker:search';

class FakeElement {
  constructor(id = '', tagName = 'div') {
    this.id = id;
    this.tagName = tagName;
    this.children = [];
    this._innerHTML = '';
    this._textContent = '';
    this.value = '';
    this.checked = false;
    this.disabled = false;
    this.dataset = {};
    this.style = {};
    this.listeners = {};
    this.focused = false;
    this.attributes = {};
    this.options = [];
  }

  set innerHTML(value) {
    this._innerHTML = String(value);
    if ((this.id === 'resultsTable' || this.id === 'mobileResults') && this._innerHTML === '') {
      this.children = [];
    }
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set textContent(value) {
    this._textContent = String(value);
  }

  get textContent() {
    return this._textContent;
  }

  get childElementCount() {
    return this.children.length;
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  addEventListener(type, handler) {
    (this.listeners[type] ||= []).push(handler);
  }

  removeEventListener(type, handler) {
    const handlers = this.listeners[type] || [];
    const index = handlers.indexOf(handler);
    if (index >= 0) handlers.splice(index, 1);
  }

  dispatchEvent(event) {
    (this.listeners[event.type] || []).forEach((handler) => handler.call(this, event));
    return true;
  }

  focus() {
    this.focused = true;
  }

  blur() {
    this.focused = false;
  }

  setAttribute(name, value) {
    this.attributes[String(name)] = String(value);
  }

  getAttribute(name) {
    return this.attributes[String(name)] ?? null;
  }

  querySelector() {
    const child = new FakeElement('', 'button');
    child.addEventListener = FakeElement.prototype.addEventListener;
    return child;
  }
}

class FakeTimers {
  constructor() {
    this.timers = new Map();
    this.nextId = 1;
  }

  setInterval(fn, delay) {
    const id = this.nextId++;
    this.timers.set(id, { type: 'interval', fn, delay, active: true, calls: 0 });
    return id;
  }

  clearInterval(id) {
    const timer = this.timers.get(id);
    if (timer) timer.active = false;
  }

  setTimeout(fn, delay) {
    const id = this.nextId++;
    this.timers.set(id, { type: 'timeout', fn, delay, active: true, calls: 0 });
    return id;
  }

  clearTimeout(id) {
    const timer = this.timers.get(id);
    if (timer) timer.active = false;
  }

  activeIntervals() {
    return [...this.timers.values()].filter((timer) => timer.active && timer.type === 'interval');
  }

  activeTimeouts() {
    return [...this.timers.values()].filter((timer) => timer.active && timer.type === 'timeout');
  }

  runIntervalOnce(id) {
    const timer = this.timers.get(id);
    if (!timer || timer.type !== 'interval' || !timer.active) return undefined;
    timer.calls += 1;
    return timer.fn();
  }
}

function createFakeLocalStorage() {
  const store = new Map();
  return {
    store,
    setItem(key, value) {
      store.set(String(key), String(value));
    },
    getItem(key) {
      return store.has(String(key)) ? store.get(String(key)) : null;
    },
    removeItem(key) {
      store.delete(String(key));
    },
    clear() {
      store.clear();
    }
  };
}

function createFetch(handler) {
  const calls = [];

  async function fetch(url, options = {}) {
    const normalizedUrl = String(url);
    calls.push({ url: normalizedUrl, options });
    const result = handler(normalizedUrl, options);
    return Promise.resolve(result);
  }

  fetch.calls = calls;
  fetch.callsFor = (url) => calls.filter((call) => call.url === url);
  return fetch;
}

function createEnvironment({ initialData = [], autoswaggerEnabled = false, locationHref = 'http://localhost/' } = {}) {
  const statusFilters = ['all', 'success', 'client_errors', 'server_errors'].map((filter) => {
    const button = new FakeElement(`filter-${filter}`, 'button');
    button.dataset.statusFilter = filter;
    return button;
  });
  const elements = {
    searchInput: new FakeElement('searchInput', 'input'),
    refreshBtn: new FakeElement('refreshBtn', 'button'),
    autoRefreshToggle: new FakeElement('autoRefreshToggle', 'input'),
    resultsTable: new FakeElement('resultsTable', 'tbody'),
    mobileResults: new FakeElement('mobileResults', 'section'),
    'count-success': new FakeElement('count-success', 'span'),
    'count-client_errors': new FakeElement('count-client_errors', 'span'),
    'count-server_errors': new FakeElement('count-server_errors', 'span'),
    'count-all': new FakeElement('count-all', 'span'),
    clearSearchBtn: new FakeElement('clearSearchBtn', 'button'),
    refreshStatus: new FakeElement('refreshStatus', 'span'),
    mobileSort: new FakeElement('mobileSort', 'select'),
    annotationsModal: new FakeElement('annotationsModal', 'div'),
    swaggerModal: new FakeElement('swaggerModal', 'div'),
    excludedUrlsModal: new FakeElement('excludedUrlsModal', 'div')
  };
  elements.mobileSort.options = [
    { value: 'url:asc' }, { value: 'url:desc' },
    { value: 'namespace:asc' }, { value: 'namespace:desc' },
    { value: 'name:asc' }, { value: 'name:desc' }
  ];

  const documentListeners = {};
  const document = {
    listeners: documentListeners,
    getElementById(id) {
      return elements[id] || null;
    },
    querySelectorAll(selector) {
      if (selector === '[data-status-filter]') return statusFilters;
      return [];
    },
    createElement(tagName) {
      return new FakeElement('', tagName);
    },
    addEventListener(type, handler) {
      (documentListeners[type] ||= []).push(handler);
    },
    removeEventListener(type, handler) {
      const handlers = documentListeners[type] || [];
      const index = handlers.indexOf(handler);
      if (index >= 0) handlers.splice(index, 1);
    },
    dispatchEvent(event) {
      (documentListeners[event.type] || []).forEach((handler) => handler(event));
      return true;
    }
  };

  const timers = new FakeTimers();
  const localStorage = createFakeLocalStorage();
  const location = { href: locationHref };
  const history = {
    replaceStateCalls: [],
    replaceState(_state, _title, url) {
      this.replaceStateCalls.push(String(url));
      location.href = String(url);
    }
  };

  const sandbox = {
    console,
    URL,
    setTimeout: timers.setTimeout.bind(timers),
    clearTimeout: timers.clearTimeout.bind(timers),
    setInterval: timers.setInterval.bind(timers),
    clearInterval: timers.clearInterval.bind(timers),
    document,
    localStorage,
    history,
    location,
    fetch: createFetch(() => ({ ok: true, status: 200, json: async () => ({}) })),
    alert() {},
    confirm() {
      return true;
    },
    prompt() {
      return null;
    }
  };

  sandbox.window = sandbox;
  sandbox.self = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.initialData = initialData;
  sandbox.autoswaggerEnabled = autoswaggerEnabled;

  vm.createContext(sandbox);
  const source = fs.readFileSync(SCRIPT_PATH, 'utf8');
  vm.runInContext(source, sandbox, { filename: SCRIPT_PATH });

  return {
    sandbox,
    elements,
    document,
    timers,
    localStorage,
    location,
    history,
    setFetch(handler) {
      sandbox.fetch = createFetch(handler);
    },
    get fetchCalls() {
      return sandbox.fetch.calls;
    },
    fireDomContentLoaded() {
      (documentListeners.DOMContentLoaded || []).forEach((handler) => handler({ type: 'DOMContentLoaded' }));
    }
  };
}

function makeItem({ url, status, namespace = 'ns', name = 'app', type = 'ingress' }) {
  return {
    url,
    status,
    namespace,
    name,
    type,
    response_time: 10,
    details: '',
    ssl_info: null
  };
}

function rowUrls(tbody) {
  return tbody.children
    .map((tr) => {
      const match = tr.innerHTML.match(/href="([^"]+)"/);
      return match ? match[1] : null;
    })
    .filter(Boolean);
}

function rowStatuses(tbody) {
  return tbody.children
    .map((tr) => {
      const match = tr.innerHTML.match(/status-badge[^>]*>\s*<[^>]*>\s*(\d+)/);
      return match ? Number(match[1]) : null;
    })
    .filter((status) => Number.isInteger(status));
}

function setInitialData(env, items) {
  env.sandbox.initialData = items;
  env.sandbox.window.initialData = items;
}

test('setStatusFilter applique les catégories de statut et réapplique la recherche courante', async (t) => {
  await t.test('success ne garde que 200..299', async () => {
    const env = createEnvironment();
    setInitialData(env, [
      makeItem({ url: 'https://a.example', status: 200 }),
      makeItem({ url: 'https://b.example', status: 299 }),
      makeItem({ url: 'https://c.example', status: 300 }),
      makeItem({ url: 'https://d.example', status: 400 })
    ]);

    env.sandbox.setStatusFilter('success');

    assert.deepEqual(rowUrls(env.elements.resultsTable).sort(), [
      'https://a.example',
      'https://b.example'
    ]);
  });

  await t.test('client_errors ne garde que 400..499', async () => {
    const env = createEnvironment();
    setInitialData(env, [
      makeItem({ url: 'https://a.example', status: 399 }),
      makeItem({ url: 'https://b.example', status: 400 }),
      makeItem({ url: 'https://c.example', status: 499 }),
      makeItem({ url: 'https://d.example', status: 500 })
    ]);

    env.sandbox.setStatusFilter('client_errors');

    assert.deepEqual(rowUrls(env.elements.resultsTable).sort(), [
      'https://b.example',
      'https://c.example'
    ]);
  });

  await t.test('server_errors ne garde que 500..599', async () => {
    const env = createEnvironment();
    setInitialData(env, [
      makeItem({ url: 'https://a.example', status: 499 }),
      makeItem({ url: 'https://b.example', status: 500 }),
      makeItem({ url: 'https://c.example', status: 599 }),
      makeItem({ url: 'https://d.example', status: 600 })
    ]);

    env.sandbox.setStatusFilter('server_errors');

    assert.deepEqual(rowUrls(env.elements.resultsTable).sort(), [
      'https://b.example',
      'https://c.example'
    ]);
  });

  await t.test('all conserve tous les statuts', async () => {
    const env = createEnvironment();
    const items = [
      makeItem({ url: 'https://a.example', status: 200 }),
      makeItem({ url: 'https://b.example', status: 300 }),
      makeItem({ url: 'https://c.example', status: 400 }),
      makeItem({ url: 'https://d.example', status: 500 }),
      makeItem({ url: 'https://e.example', status: 600 })
    ];
    setInitialData(env, items);

    env.sandbox.setStatusFilter('all');

    assert.equal(env.elements.resultsTable.children.length, items.length);
  });

  await t.test('la recherche courante est conservée lors du changement de catégorie', async () => {
    const env = createEnvironment();
    setInitialData(env, [
      makeItem({ url: 'https://alpha-one.example', status: 200 }),
      makeItem({ url: 'https://alpha-two.example', status: 400 }),
      makeItem({ url: 'https://beta.example', status: 200 })
    ]);

    env.elements.searchInput.value = 'alpha';
    env.sandbox.applySearchFilter('alpha');
    env.sandbox.setStatusFilter('success');

    assert.deepEqual(rowUrls(env.elements.resultsTable), ['https://alpha-one.example']);
  });
});

test('applySearchFilter compose catégorie, recherche insensible à la casse et tri existant', async (t) => {
  await t.test('recherche insensible à la casse', async () => {
    const env = createEnvironment();
    setInitialData(env, [
      makeItem({ url: 'https://Alpha.example', status: 200 }),
      makeItem({ url: 'https://beta.example', status: 200 })
    ]);

    env.sandbox.setStatusFilter('all');
    env.sandbox.applySearchFilter('ALPHA');

    assert.deepEqual(rowUrls(env.elements.resultsTable), ['https://Alpha.example']);
  });

  await t.test('la catégorie active restreint la recherche', async () => {
    const env = createEnvironment();
    setInitialData(env, [
      makeItem({ url: 'https://alpha.example', status: 200 }),
      makeItem({ url: 'https://alpha-error.example', status: 404 })
    ]);

    env.sandbox.setStatusFilter('success');
    env.sandbox.applySearchFilter('alpha');

    assert.deepEqual(rowUrls(env.elements.resultsTable), ['https://alpha.example']);
  });

  await t.test('le tri est appliqué sans changer sa direction', async () => {
    const env = createEnvironment();
    setInitialData(env, [
      makeItem({ url: 'https://a.example', status: 200 }),
      makeItem({ url: 'https://b.example', status: 200 }),
      makeItem({ url: 'https://c.example', status: 200 })
    ]);

    env.sandbox.setStatusFilter('all');
    env.sandbox.sortTable('url');
    const descendingOrder = rowUrls(env.elements.resultsTable);
    assert.deepEqual(descendingOrder, [
      'https://c.example',
      'https://b.example',
      'https://a.example'
    ]);

    env.sandbox.applySearchFilter('');

    assert.deepEqual(rowUrls(env.elements.resultsTable), descendingOrder);
  });
});

test('renderTable rend les cartes mobiles après filtrage', () => {
  const env = createEnvironment();
  setInitialData(env, [
    makeItem({ url: 'https://ok.example', status: 204 }),
    makeItem({ url: 'https://missing.example', status: 404 }),
    makeItem({ url: 'https://failed.example', status: 503 })
  ]);

  env.sandbox.setStatusFilter('all');
  assert.equal(env.elements.mobileResults.childElementCount, 3);

  env.sandbox.setStatusFilter('client_errors');
  assert.equal(env.elements.mobileResults.childElementCount, 1);
  assert.equal(env.elements.mobileResults.children[0].children[0].children[0].textContent, 'app');
});

test('createMobileCard utilise textContent et conserve URL dans les actions', () => {
  const env = createEnvironment({ autoswaggerEnabled: true });
  const url = "https://evil.example/path?q='quoted'";
  const item = makeItem({
    url,
    name: '<img src=x onerror=alert(1)>',
    status: 404
  });
  item.details = '<script>alert(1)</script>';
  item.annotations = { owner: 'platform' };

  const card = env.sandbox.createMobileCard(item);
  const header = card.children[0];
  const link = card.children[1];
  const details = card.children[2];
  const summary = details.children[0];
  const expanded = details.children[1];
  const actions = details.children[4];

  assert.equal(header.children[0].textContent, item.name);
  assert.equal(link.textContent, url.replace(/^https?:\/\//, ''));
  assert.equal(link.href, url);
  assert.equal(link.title, url);
  assert.equal(summary.children[0].textContent, 'ns · ingress');
  assert.equal(summary.children[1].textContent, 'Détails');
  assert.equal(expanded.children[0].textContent, `Nom complet : ${item.name}`);
  assert.equal(expanded.children[1].textContent, url);
  assert.equal(expanded.children[1].href, url);
  assert.equal(expanded.children[1].title, url);
  assert.equal(expanded.children[2].textContent, 'ns · ingress');
  assert.equal(details.children[3].textContent, item.details);
  assert.deepEqual(actions.children.map((button) => button.textContent), [
    'Annotations', 'Scanner API', 'Exclure'
  ]);

  actions.children[2].dispatchEvent({ type: 'click' });
  const exclusion = env.fetchCalls.find((call) => call.url === '/api/exclude');
  assert.ok(exclusion);
  assert.deepEqual(JSON.parse(exclusion.options.body), { url });
});

test('clearSearch vide champ, URL et stockage, restaure focus et conserve la catégorie', async (t) => {
  await t.test('cas nominal avec recherche active', async () => {
    const env = createEnvironment({ locationHref: 'http://localhost/?search=alpha' });
    setInitialData(env, [
      makeItem({ url: 'https://alpha.example', status: 200 }),
      makeItem({ url: 'https://beta.example', status: 400 })
    ]);
    env.localStorage.setItem(SEARCH_STORAGE_KEY, 'alpha');
    env.elements.searchInput.value = 'alpha';
    env.sandbox.setStatusFilter('success');
    env.sandbox.applySearchFilter('alpha');

    env.sandbox.clearSearch();

    assert.equal(env.elements.searchInput.value, '');
    assert.equal(env.elements.searchInput.focused, true);
    assert.ok(
      env.localStorage.getItem(SEARCH_STORAGE_KEY) === null ||
      env.localStorage.getItem(SEARCH_STORAGE_KEY) === ''
    );
    assert.ok(!new URL(env.location.href).searchParams.has('search'));
    assert.deepEqual(rowUrls(env.elements.resultsTable), ['https://alpha.example']);
  });

  await t.test('la catégorie est conservée après effacement', async () => {
    const env = createEnvironment({ locationHref: 'http://localhost/' });
    setInitialData(env, [
      makeItem({ url: 'https://alpha.example', status: 200 }),
      makeItem({ url: 'https://beta.example', status: 400 })
    ]);
    env.sandbox.setStatusFilter('success');
    env.elements.searchInput.value = 'alpha';
    env.sandbox.applySearchFilter('alpha');

    env.sandbox.clearSearch();

    assert.deepEqual(rowUrls(env.elements.resultsTable), ['https://alpha.example']);
  });
});

test('restoreSearchTerm donne priorité à un paramètre URL présent, même vide', () => {
  const env = createEnvironment({ locationHref: 'http://localhost/?search=' });
  env.localStorage.setItem(SEARCH_STORAGE_KEY, 'depuis-storage');

  assert.equal(env.sandbox.restoreSearchTerm(), '');
});

test('persistSearchTerm met à jour l’URL si localStorage est indisponible', () => {
  const env = createEnvironment({ locationHref: 'http://localhost/?page=1' });
  env.localStorage.setItem = () => { throw new Error('storage blocked'); };

  env.sandbox.persistSearchTerm('alpha');

  const url = new URL(env.location.href);
  assert.equal(url.searchParams.get('search'), 'alpha');
  assert.deepEqual(env.history.replaceStateCalls, ['http://localhost/?page=1&search=alpha']);
});

test('updateDashboardCounts met à jour les compteurs depuis window.initialData', async (t) => {
  await t.test('compteurs nominaux et bornes', async () => {
    const env = createEnvironment();
    const items = [
      makeItem({ url: 'https://a.example', status: 200 }),
      makeItem({ url: 'https://b.example', status: 299 }),
      makeItem({ url: 'https://c.example', status: 300 }),
      makeItem({ url: 'https://d.example', status: 400 }),
      makeItem({ url: 'https://e.example', status: 499 }),
      makeItem({ url: 'https://f.example', status: 500 }),
      makeItem({ url: 'https://g.example', status: 599 }),
      makeItem({ url: 'https://h.example', status: 600 })
    ];
    setInitialData(env, items);

    env.sandbox.updateDashboardCounts();

    const successCount = items.filter((item) => item.status >= 200 && item.status <= 299).length;
    const clientCount = items.filter((item) => item.status >= 400 && item.status <= 499).length;
    const serverCount = items.filter((item) => item.status >= 500 && item.status <= 599).length;

    assert.equal(Number(env.elements['count-success'].textContent), successCount);
    assert.equal(Number(env.elements['count-client_errors'].textContent), clientCount);
    assert.equal(Number(env.elements['count-server_errors'].textContent), serverCount);
    assert.equal(Number(env.elements['count-all'].textContent), items.length);
  });

  await t.test('indépendamment du filtre actif', async () => {
    const env = createEnvironment();
    const items = [
      makeItem({ url: 'https://a.example', status: 200 }),
      makeItem({ url: 'https://b.example', status: 400 }),
      makeItem({ url: 'https://c.example', status: 500 })
    ];
    setInitialData(env, items);
    env.sandbox.setStatusFilter('client_errors');

    env.sandbox.updateDashboardCounts();

    assert.equal(Number(env.elements['count-success'].textContent), 1);
    assert.equal(Number(env.elements['count-client_errors'].textContent), 1);
    assert.equal(Number(env.elements['count-server_errors'].textContent), 1);
    assert.equal(Number(env.elements['count-all'].textContent), 3);
  });
});

test('les statuts 2xx gardent la classe et l’icône de succès', () => {
  const env = createEnvironment();

  assert.equal(env.sandbox.getStatusClass(204), 'status-200');
  assert.match(env.sandbox.getStatusIcon(204), /fa-check/);
  assert.equal(env.sandbox.getStatusClass(299), 'status-200');
  assert.match(env.sandbox.getStatusIcon(299), /fa-check/);
});

test('fetchUrlsAndRender conserve filtre et tri, et ignore un timestamp inchangé', async (t) => {
  await t.test('conserve filtre et tri après nouvelles données', async () => {
    const env = createEnvironment();
    setInitialData(env, [makeItem({ url: 'https://old.example', status: 200 })]);
    env.sandbox.setStatusFilter('success');
    env.sandbox.sortTable('url');
    env.elements.searchInput.value = 'new';
    env.sandbox.applySearchFilter('new');

    env.setFetch((url) => {
      if (url === '/api/urls') {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            last_updated: 'T2',
            results: [
              makeItem({ url: 'https://new-a.example', status: 200 }),
              makeItem({ url: 'https://new-b.example', status: 200 }),
              makeItem({ url: 'https://new-c.example', status: 400 })
            ]
          })
        };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });

    await env.sandbox.fetchUrlsAndRender();

    const urls = rowUrls(env.elements.resultsTable);
    assert.deepEqual(urls, ['https://new-b.example', 'https://new-a.example']);
  });

  await t.test('timestamp inchangé ne rerend pas', async () => {
    const env = createEnvironment();
    setInitialData(env, [makeItem({ url: 'https://old.example', status: 200 })]);

    env.setFetch((url) => {
      if (url === '/api/urls') {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            last_updated: 'T1',
            results: [makeItem({ url: 'https://first.example', status: 200 })]
          })
        };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });
    await env.sandbox.fetchUrlsAndRender();
    assert.deepEqual(rowUrls(env.elements.resultsTable), ['https://first.example']);

    env.setFetch((url) => {
      if (url === '/api/urls') {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            last_updated: 'T1',
            results: [makeItem({ url: 'https://second.example', status: 200 })]
          })
        };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });
    await env.sandbox.fetchUrlsAndRender();

    assert.deepEqual(rowUrls(env.elements.resultsTable), ['https://first.example']);
  });
});

test('fetchAutoRefreshState synchronise checkbox et intervalle pour true et false', async (t) => {
  await t.test('true active checkbox et un intervalle', async () => {
    const env = createEnvironment();
    env.setFetch((url) => {
      if (url === '/api/auto-refresh') {
        return { ok: true, status: 200, json: async () => ({ enabled: true }) };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });

    await env.sandbox.fetchAutoRefreshState();

    assert.equal(env.elements.autoRefreshToggle.checked, true);
    assert.equal(env.timers.activeIntervals().length, 1);
  });

  await t.test('false désactive checkbox et intervalle', async () => {
    const env = createEnvironment();
    env.setFetch((url) => {
      if (url === '/api/auto-refresh') {
        return { ok: true, status: 200, json: async () => ({ enabled: false }) };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });

    await env.sandbox.fetchAutoRefreshState();

    assert.equal(env.elements.autoRefreshToggle.checked, false);
    assert.equal(env.timers.activeIntervals().length, 0);
  });
});

test('fetchAutoRefreshState ne réécrit pas un choix utilisateur arrivé pendant le GET', async () => {
  const env = createEnvironment();
  let resolveState;
  env.setFetch((url, options) => {
    if (url === '/api/auto-refresh' && options.method === 'POST') {
      return { ok: true, status: 200, json: async () => ({ enabled: true }) };
    }
    if (url === '/api/auto-refresh') {
      return new Promise((resolve) => { resolveState = resolve; });
    }
    return { ok: true, status: 200, json: async () => ({}) };
  });

  const stateRequest = env.sandbox.fetchAutoRefreshState();
  env.elements.autoRefreshToggle.checked = true;
  const userChange = env.sandbox.toggleAutoRefresh(env.elements.autoRefreshToggle);
  await userChange;

  resolveState({ ok: true, status: 200, json: async () => ({ enabled: false }) });
  await stateRequest;

  assert.equal(env.elements.autoRefreshToggle.checked, true);
  assert.equal(env.timers.activeIntervals().length, 1);
});

test('toggleAutoRefresh verrouille les clics concurrents et réactive le contrôle après succès', async () => {
  const env = createEnvironment();
  let resolvePost;
  env.setFetch((url, options) => {
    if (url === '/api/auto-refresh' && options.method === 'POST') {
      return new Promise((resolve) => { resolvePost = resolve; });
    }
    return { ok: true, status: 200, json: async () => ({}) };
  });

  env.elements.autoRefreshToggle.checked = true;
  const first = env.sandbox.toggleAutoRefresh(env.elements.autoRefreshToggle);
  assert.equal(env.elements.autoRefreshToggle.disabled, true);

  const second = env.sandbox.toggleAutoRefresh(env.elements.autoRefreshToggle);
  assert.equal(env.fetchCalls.filter((call) => call.options.method === 'POST').length, 1);

  resolvePost({ ok: true, status: 200, json: async () => ({ enabled: true }) });
  await Promise.all([first, second]);

  assert.equal(env.elements.autoRefreshToggle.checked, true);
  assert.equal(env.elements.autoRefreshToggle.disabled, false);
  assert.equal(env.timers.activeIntervals().length, 1);
});

test('toggleAutoRefresh annule le choix et réactive le contrôle si le POST échoue', async () => {
  const env = createEnvironment();
  env.setFetch((url, options) => {
    if (url === '/api/auto-refresh' && options.method === 'POST') {
      return Promise.reject(new Error('réseau indisponible'));
    }
    return { ok: true, status: 200, json: async () => ({}) };
  });

  env.elements.autoRefreshToggle.checked = true;
  await env.sandbox.toggleAutoRefresh(env.elements.autoRefreshToggle);

  assert.equal(env.elements.autoRefreshToggle.checked, false);
  assert.equal(env.elements.autoRefreshToggle.disabled, false);
  assert.equal(env.timers.activeIntervals().length, 0);
});

test('_manageAutoRefreshInterval ne laisse qu’un intervalle actif', async (t) => {
  await t.test('plusieurs activations ne créent qu’un seul intervalle', async () => {
    const env = createEnvironment();

    env.sandbox._manageAutoRefreshInterval(true);
    env.sandbox._manageAutoRefreshInterval(true);
    env.sandbox._manageAutoRefreshInterval(true);

    assert.equal(env.timers.activeIntervals().length, 1);
  });

  await t.test('désactivation supprime l’intervalle', async () => {
    const env = createEnvironment();

    env.sandbox._manageAutoRefreshInterval(true);
    env.sandbox._manageAutoRefreshInterval(false);

    assert.equal(env.timers.activeIntervals().length, 0);
  });
});

test('triggerRefresh refuse un second appel et libère le bouton en cas d’erreur', async (t) => {
  await t.test('refuse un second appel pendant le premier', async () => {
    const env = createEnvironment();
    let resolveRefresh;
    env.setFetch((url) => {
      if (url === '/api/refresh-async') {
        return new Promise((resolve) => {
          resolveRefresh = () => resolve({ ok: true, status: 200, json: async () => ({}) });
        });
      }
      if (url === '/api/refresh-status') {
        return { ok: true, status: 200, json: async () => ({ running: false }) };
      }
      if (url === '/api/urls') {
        return { ok: true, status: 200, json: async () => ({ last_updated: 'T1', results: [] }) };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });

    const first = env.sandbox.triggerRefresh();
    const second = env.sandbox.triggerRefresh();

    await Promise.resolve();
    assert.equal(env.fetchCalls.filter((call) => call.url === '/api/refresh-async').length, 1);

    resolveRefresh();
    await Promise.allSettled([first, second]);

    assert.equal(env.elements.refreshBtn.disabled, false);
  });

  await t.test('libère le bouton si la réponse refresh est invalide', async () => {
    const env = createEnvironment();
    env.setFetch((url) => {
      if (url === '/api/refresh-async') {
        return { ok: false, status: 500, json: async () => ({}) };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });

    await env.sandbox.triggerRefresh();

    assert.equal(env.elements.refreshBtn.disabled, false);
  });

  await t.test('libère le bouton si le polling est invalide', async () => {
    const env = createEnvironment();
    env.setFetch((url) => {
      if (url === '/api/refresh-async') {
        return { ok: true, status: 200, json: async () => ({}) };
      }
      if (url === '/api/refresh-status') {
        return { ok: false, status: 500, json: async () => ({}) };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });

    await env.sandbox.triggerRefresh();

    assert.equal(env.elements.refreshBtn.disabled, false);
  });

  await t.test('libère le bouton si le polling lève une erreur', async () => {
    const env = createEnvironment();
    env.setFetch((url) => {
      if (url === '/api/refresh-async') {
        return { ok: true, status: 200, json: async () => ({}) };
      }
      if (url === '/api/refresh-status') {
        return Promise.reject(new Error('polling indisponible'));
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });

    await env.sandbox.triggerRefresh();

    assert.equal(env.elements.refreshBtn.disabled, false);
  });

  await t.test('affiche une erreur métier renvoyée par le polling', async () => {
    const env = createEnvironment();
    env.setFetch((url) => {
      if (url === '/api/refresh-async') {
        return { ok: true, status: 202, json: async () => ({}) };
      }
      if (url === '/api/refresh-status') {
        return {
          ok: true,
          status: 200,
          json: async () => ({ running: false, last_error: 'échec du scan' })
        };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });

    await env.sandbox.triggerRefresh();

    assert.equal(env.elements.refreshBtn.disabled, false);
    assert.equal(env.elements.refreshStatus.className, 'refresh-status refresh-status-error');
    assert.match(env.elements.refreshStatus.textContent, /Échec/);
  });

  await t.test('ne signale pas un succès si /api/urls échoue après le refresh', async () => {
    const env = createEnvironment();
    env.setFetch((url) => {
      if (url === '/api/refresh-async') {
        return { ok: true, status: 202, json: async () => ({}) };
      }
      if (url === '/api/refresh-status') {
        return { ok: true, status: 200, json: async () => ({ running: false }) };
      }
      if (url === '/api/urls') {
        return { ok: false, status: 503, json: async () => ({}) };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });

    await env.sandbox.triggerRefresh();

    assert.equal(env.elements.refreshBtn.disabled, false);
    assert.equal(env.elements.refreshStatus.className, 'refresh-status refresh-status-error');
    assert.doesNotMatch(env.elements.refreshStatus.textContent, /terminée/i);
  });
});
