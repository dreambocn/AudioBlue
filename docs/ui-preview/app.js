'use strict';

(() => {
  // Windows 优先使用系统 Segoe Fluent Icons；字体不可用时保留 SVG 后备图标。
  const paths = {
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    devices: '<rect x="3" y="6" width="12" height="10" rx="1.5"/><path d="M7 20h5M9.5 16v4"/><rect x="16" y="2" width="6" height="13" rx="1.3"/><path d="M18.5 12h1"/>',
    settings: '<path d="m10 3 .5-1h3l.5 1 1 2 2 .5 2-1 2 3-1.5 2 .5 2 2 1v3l-2 1-.5 2 1 2-3 2-2-1.5-2 .5-1 2h-3l-1-2-2-.5-2 1-2-3 1.5-2-.5-2-2-1v-3l2-1 .5-2-1-2 3-2 2 1.5 2-.5Z" transform="translate(1 -1) scale(.9)"/><circle cx="12" cy="12" r="3.2"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v6M12 7.2v.3"/>',
    plus: '<path d="M12 4v16M4 12h16"/>',
    bluetooth: '<path d="M11 2v20l7-6L5 5M5 19 18 8 11 2"/>',
    note: '<path d="M9 17V5l11-2v12M9 8l11-2"/><ellipse cx="6" cy="18" rx="3" ry="2.5"/><ellipse cx="17" cy="16" rx="3" ry="2.5"/>',
    phone: '<rect x="6" y="2" width="12" height="20" rx="2.7"/><path d="M10 5h4M11 19h2"/>',
    refresh: '<path d="M20 9a8 8 0 0 0-14-3L3 9M3 4v5h5M4 15a8 8 0 0 0 14 3l3-3M21 20v-5h-5"/>',
    power: '<path d="M12 2v9M6.2 5.5a8.5 8.5 0 1 0 11.6 0"/>',
    window: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 6.5h.1M10 6.5h.1"/>',
    bell: '<path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5l-2 3ZM10 20h4M12 2v2"/>',
    paint: '<path d="M12 3a9 9 0 0 0 0 18h2a2 2 0 0 0 1.5-3.3c-.5-.8-.2-1.7.7-2H18a4 4 0 0 0 4-4c0-5-4-8.7-10-8.7Z"/><circle cx="7" cy="10" r=".8"/><circle cx="11" cy="7" r=".8"/><circle cx="16" cy="8" r=".8"/>',
    language: '<path d="M3 5h12M9 2v3M12 5c-1 6-4 10-9 12M5 8c1 3 3 6 7 8M13 21l4-10 4 10M15 17h4"/>',
    tray: '<path d="M4 5h16v12H4zM8 21h8M12 17v4M8 11l4-4 4 4M12 7v7"/>',
    more: '<circle cx="5" cy="12" r=".9"/><circle cx="12" cy="12" r=".9"/><circle cx="19" cy="12" r=".9"/>',
    arrow: '<path d="M4 12h15M14 7l5 5-5 5"/>',
    external: '<path d="M14 3h7v7M21 3l-9 9M10 4H4v16h16v-6"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5"/>',
    moon: '<path d="M20 14a8.5 8.5 0 0 1-10-10 8.7 8.7 0 1 0 10 10Z"/>',
    search: '<circle cx="10" cy="10" r="6.5"/><path d="m15 15 6 6"/>',
    chevron: '<path d="m6 14 6-6 6 6"/>',
    wifi: '<path d="M2 8a16 16 0 0 1 20 0M5 12a11 11 0 0 1 14 0M8 16a6 6 0 0 1 8 0M12 20h.1"/>',
    speaker: '<path d="M10 4 5 8H2v8h3l5 4V4ZM14 8a6 6 0 0 1 0 8M18 4a11 11 0 0 1 0 16"/>',
    download: '<path d="M12 2v14M7 11l5 5 5-5M4 16v5h16v-5"/>',
    warning: '<path d="m12 3 10 18H2L12 3ZM12 9v5M12 17h.1"/>',
    bluetoothOff: '<path d="M11 2v7M11 14v8l7-6M5 19l5-4M15 10l3-2-7-6M3 3l18 18"/>'
  };
  // 字形值来自微软官方 Segoe Fluent Icons 表，不向项目分发系统字体文件。
  const systemGlyphs = { menu: 'E700', devices: 'E772', settings: 'E713', info: 'E946', plus: 'E710', bluetooth: 'E702', phone: 'E8EA', refresh: 'E72C', power: 'E7E8', paint: 'E771', language: 'E775', more: 'E712', arrow: 'E72A', check: 'E73E', search: 'E721', chevron: 'E70E', wifi: 'E701', speaker: 'E767' };
  const icon = (name) => `${systemGlyphs[name] ? `<span class="glyph fluent-glyph" aria-hidden="true">&#x${systemGlyphs[name]};</span>` : ''}<svg class="glyph ${systemGlyphs[name] ? 'glyph-fallback' : ''}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.info}</svg>`;
  document.fonts.load('20px AudioBuleSystemIcons').then(fonts => { if (fonts.length) document.documentElement.classList.add('system-icons'); }).catch(() => { /* 系统字体不可用时继续显示 SVG。 */ });
  const hydrateIcons = (root = document) => root.querySelectorAll('[data-icon]').forEach(el => { el.innerHTML = icon(el.dataset.icon); });
  const escape = value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
  const $ = selector => document.querySelector(selector);
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
  const preferences = { reconnect: true, startup: false, notifications: true, theme: 'system', language: 'system' };
  // 仅保存原型偏好；不访问 AudioBule 的真实配置或 Windows 设置。
  try {
    const saved = JSON.parse(localStorage.getItem('audiobule-design-preferences') || '{}');
    for (const key of ['reconnect', 'startup', 'notifications']) if (typeof saved[key] === 'boolean') preferences[key] = saved[key];
    if (['system', 'light', 'dark'].includes(saved.theme)) preferences.theme = saved.theme;
    if (['system', 'zh', 'en'].includes(saved.language)) preferences.language = saved.language;
  } catch { /* 存储不可用时，使用默认设计偏好。 */ }
  const state = { view: 'window', page: 'devices', filter: 'all', scenario: 'normal', running: true, generation: 0, devices: [] };
  const pendingConnections = new Map();
  let toastTimer;
  let refreshTimer;
  let toastContent;
  let dialogContent;

  // 记录整页文字和辅助标签，切换语言时保留图标、数量和交互状态。
  const translations = window.AudioBuleLocale.english;
  const originalNodes = new Map();
  const originalAttributes = [];
  for (const root of [document.body]) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (translations[node.textContent.trim()]) originalNodes.set(node, node.textContent);
    }
  }
  document.querySelectorAll('[aria-label], [alt], [title]').forEach(element => {
    for (const attribute of ['aria-label', 'alt', 'title']) {
      const original = element.getAttribute(attribute);
      if (translations[original]) originalAttributes.push({ element, attribute, original });
    }
  });
  const language = () => preferences.language === 'system' ? (navigator.language.toLowerCase().startsWith('zh') ? 'zh' : 'en') : preferences.language;
  const locale = () => language() === 'zh' ? 'zh-CN' : 'en-US';
  const t = (zh, en) => language() === 'en' ? en : zh;
  function message(key, values = {}) {
    let template = window.AudioBuleLocale.messages[key][language()];
    if (typeof template === 'object') template = template[new Intl.PluralRules(locale()).select(values.count)] || template.other;
    return template.replace(/\{(\w+)\}/g, (_, name) => name === 'count' ? new Intl.NumberFormat(locale()).format(values[name]) : String(values[name] ?? ''));
  }
  const resolveText = content => typeof content === 'function' ? content() : content;
  function persist() {
    try { localStorage.setItem('audiobule-design-preferences', JSON.stringify(preferences)); } catch { /* 原型在禁用存储时仍可正常交互。 */ }
  }
  function setTheme(theme, save = true) {
    preferences.theme = theme;
    const resolved = theme === 'system' ? (systemTheme.matches ? 'dark' : 'light') : theme;
    document.documentElement.dataset.theme = resolved;
    $('#theme-toggle').innerHTML = icon(resolved === 'light' ? 'moon' : 'sun');
    const toggleLabel = message(resolved === 'light' ? 'themeDark' : 'themeLight');
    $('#theme-toggle').setAttribute('aria-label', toggleLabel); $('#theme-toggle').title = toggleLabel;
    $('#app-theme').value = theme;
    $('#preview-theme').value = theme;
    $('.taskbar-tray-button img').src = `icons/tray-${resolved === 'dark' ? 'light' : 'dark'}.svg`;
    document.querySelectorAll('.size-samples img[src*="tray-"]').forEach(image => { image.src = `icons/tray-${resolved === 'dark' ? 'light' : 'dark'}.svg`; });
    const tokens = getComputedStyle(document.documentElement);
    for (const [index, token] of ['accent', 'green', 'orange', 'red'].entries()) {
      const swatch = document.querySelectorAll('.palette > div')[index];
      const color = tokens.getPropertyValue(`--${token}`).trim();
      swatch.querySelector('i').style.background = color;
      swatch.querySelector('small').textContent = color.toUpperCase();
    }
    if (save) persist();
  }
  function setLanguage(language) {
    preferences.language = language;
    for (const [node, original] of originalNodes) {
      if (node.isConnected) node.textContent = t(original, original.replace(original.trim(), translations[original.trim()]));
    }
    for (const { element, attribute, original } of originalAttributes) element.setAttribute(attribute, t(original, translations[original]));
    document.documentElement.lang = locale();
    document.title = t('AudioBule · WinUI 3 设计预览', translations['AudioBule · WinUI 3 设计预览']);
    $('#app-language').value = language;
    $('#preview-language').value = language;
    const referenceTime = new Date('2026-10-11T10:24:00+08:00');
    const time = new Intl.DateTimeFormat(locale(), { hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Shanghai' }).format(referenceTime);
    const date = new Intl.DateTimeFormat(locale(), { year: 'numeric', month: 'numeric', day: 'numeric', timeZone: 'Asia/Shanghai' }).format(referenceTime);
    $('.taskbar-clock').innerHTML = `${escape(time)}<small>${escape(date)}</small>`;
    setTheme(preferences.theme, false); selectView(state.view); render();
    if ($('#app-dialog').open) renderDialog();
    if (!$('#toast').hidden) renderToast();
    persist();
  }
  function syncSettings() {
    document.querySelectorAll('[data-setting]').forEach(button => button.setAttribute('aria-checked', String(preferences[button.dataset.setting])));
    for (const [key, id] of [['reconnect', 'menu-reconnect'], ['startup', 'menu-startup']]) {
      const button = document.getElementById(id);
      button.setAttribute('aria-checked', String(preferences[key]));
      button.firstElementChild.innerHTML = preferences[key] ? icon('check') : '';
      button.firstElementChild.classList.add('menu-check-space');
    }
  }
  function showToast(title, message = '', force = true) {
    if (!force && !preferences.notifications) return;
    clearTimeout(toastTimer);
    toastContent = { title, message }; renderToast();
    $('#toast').hidden = false;
    toastTimer = setTimeout(() => { $('#toast').hidden = true; }, 4200);
  }
  function renderToast() {
    if (!toastContent) return;
    $('#toast').innerHTML = `<img src="icons/app.svg" alt=""><div><strong>${escape(resolveText(toastContent.title))}</strong><p>${escape(resolveText(toastContent.message))}</p></div><button data-action="dismiss-toast" aria-label="${message('dismissToast')}">×</button>`;
  }
  function selectView(view) {
    if (!['window', 'tray', 'identity'].includes(view)) view = 'window';
    state.view = view;
    document.querySelectorAll('.preview-view').forEach(element => { element.hidden = element.id !== `view-${view}`; });
    document.querySelectorAll('[data-view]').forEach(button => {
      button.classList.toggle('selected', button.dataset.view === view);
      if (button.dataset.view === view) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
    });
    const copy = {
      window: ['01 / APPLICATION', message('sceneWindowTitle'), message('sceneWindowBody')],
      tray: ['02 / SYSTEM TRAY', message('sceneTrayTitle'), message('sceneTrayBody')],
      identity: ['03 / VISUAL IDENTITY', message('sceneIdentityTitle'), message('sceneIdentityBody')]
    }[view];
    $('#scene-number').textContent = copy[0]; $('#scene-title').textContent = copy[1]; $('#scene-description').textContent = copy[2];
    $('.scenario-control').hidden = view === 'identity';
    if (location.hash !== `#${view}`) history.replaceState(null, '', `#${view}`);
  }
  function selectPage(page) {
    state.page = page;
    document.querySelectorAll('.app-page').forEach(element => { element.hidden = element.id !== `page-${page}`; });
    document.querySelectorAll('[data-page]').forEach(button => {
      button.classList.toggle('active', button.dataset.page === page);
      if (button.dataset.page === page) button.setAttribute('aria-current', 'page'); else button.removeAttribute('aria-current');
    });
  }
  function scenario(value) {
    state.generation += 1;
    for (const timer of pendingConnections.values()) clearTimeout(timer);
    pendingConnections.clear();
    state.scenario = value;
    state.filter = 'all';
    state.devices = value === 'empty' || value === 'bluetooth-off' ? [] : [
      { id: 'xiaomi-15', name: 'Xiaomi 15', status: 'connected' },
      { id: 'redmi-note', name: 'Redmi Note 11T Pro+', status: value === 'failed' ? 'failed' : value === 'connecting' ? 'connecting' : 'disconnected' }
    ];
    if (!state.running) resume();
    render();
  }
  function deviceMarkup(device, compact = false) {
    const status = { connected: t('已连接', 'Connected'), connecting: t('连接中', 'Connecting'), disconnected: t('未连接', 'Not connected'), failed: t('连接失败', 'Connection failed') }[device.status];
    const action = { connected: t('断开', 'Disconnect'), connecting: t('取消', 'Cancel'), disconnected: t('连接', 'Connect'), failed: t('重试', 'Retry') }[device.status];
    return `<article class="${compact ? 'tray-device' : 'device-row'} ${device.status}" data-device="${device.id}"><div class="device-avatar">${icon('phone')}</div><div class="device-info"><h4>${escape(device.name)}</h4><div class="device-meta"><span class="badge ${device.status}">${status}</span></div>${device.status === 'failed' ? `<p class="device-error">${icon('warning')}${t('连接请求超时。请靠近电脑并确认手机蓝牙已开启。', 'Connection timed out. Keep your phone nearby and Bluetooth on.')}</p>` : ''}</div><button class="button device-action" data-action="device" data-device-id="${device.id}" aria-label="${escape(device.name)}：${action}">${action}</button></article>`;
  }
  function render() {
    const count = state.devices.filter(device => device.status === 'connected').length;
    const offline = state.scenario === 'bluetooth-off';
    const summary = message('connectedCount', { count });
    $('#all-count').textContent = state.devices.length; $('#nav-count').textContent = state.devices.length; $('#connected-count').textContent = count;
    $('#footer-summary').textContent = state.running ? (offline ? t('蓝牙不可用', 'Bluetooth unavailable') : summary) : t('程序已退出', 'App has exited');
    $('#tray-summary').textContent = state.running ? summary : t('程序已退出', 'App has exited');
    $('#tray-status-dot').style.background = count ? 'var(--green)' : 'var(--muted)';
    $('#tray-icon-button').setAttribute('aria-label', message('trayLabel', { summary }));
    $('#hidden-window-message h2').textContent = message(state.running ? 'hiddenTitle' : 'exitedTitle');
    $('#hidden-window-message p').textContent = message(state.running ? 'hiddenBody' : 'exitedBody');
    $('#hidden-window-message .button').textContent = state.running ? t('打开设备窗口', 'Open device window') : message('restart');
    document.querySelectorAll('[data-filter]').forEach(button => { button.classList.toggle('active', button.dataset.filter === state.filter); button.setAttribute('aria-pressed', String(button.dataset.filter === state.filter)); });
    const devices = state.filter === 'connected' ? state.devices.filter(device => device.status === 'connected') : state.devices;
    if (devices.length) $('#device-list').innerHTML = devices.map(device => deviceMarkup(device)).join('');
    else {
      const filtered = state.devices.length > 0 || (state.filter === 'connected' && !offline);
      $('#device-list').innerHTML = `<div class="empty-state ${filtered ? 'filtered' : ''}"><span data-icon="${offline ? 'bluetoothOff' : 'devices'}"></span><h3>${offline ? t('蓝牙暂不可用', 'Bluetooth is unavailable') : filtered ? t('还没有已连接的设备', 'No devices connected') : t('还没有可连接的设备', 'No paired devices yet')}</h3><p>${offline ? t('请在 Windows 设置中开启蓝牙，或检查蓝牙适配器是否可用。', 'Enable Bluetooth in Windows settings or check your adapter.') : filtered ? t('切换到全部设备，选择手机开始连接。', 'Switch to all devices and connect your phone.') : t('先在 Windows 蓝牙设置中配对手机，再回来刷新列表。', 'Pair your phone in Windows Bluetooth settings, then refresh this list.')}</p><button class="button ${filtered ? '' : 'primary'}" ${filtered ? 'data-filter="all"' : 'data-action="pair"'}>${filtered ? t('查看全部设备', 'View all devices') : t('打开蓝牙设置', 'Open Bluetooth settings')}</button></div>`;
    }
    $('#tray-devices').innerHTML = state.devices.length ? state.devices.map(device => deviceMarkup(device, true)).join('') : `<div class="empty-state filtered"><span data-icon="${offline ? 'bluetoothOff' : 'devices'}"></span><h3>${offline ? t('蓝牙暂不可用', 'Bluetooth is unavailable') : t('还没有可连接的设备', 'No paired devices yet')}</h3><button class="button" data-action="pair">${t('打开蓝牙设置', 'Open Bluetooth settings')}</button></div>`;
    hydrateIcons($('#device-list')); hydrateIcons($('#tray-devices'));
  }
  function operateDevice(id) {
    const device = state.devices.find(item => item.id === id);
    if (!device || !state.running) return;
    if (device.status === 'connected' || device.status === 'connecting') {
      if (pendingConnections.has(id)) clearTimeout(pendingConnections.get(id));
      pendingConnections.delete(id);
      const wasConnected = device.status === 'connected'; device.status = 'disconnected'; render();
      showToast(device.name, () => wasConnected ? t('连接已断开', 'Disconnected') : t('已取消连接', 'Connection canceled'), false);
    } else {
      device.status = 'connecting'; render();
      const generation = state.generation;
      // 计时器仅模拟异步连接；切换场景或退出时取消，防止状态串扰。
      pendingConnections.set(id, setTimeout(() => {
        if (state.generation !== generation || !state.running) return;
        device.status = 'connected'; pendingConnections.delete(id); render();
        showToast(() => t('设备已连接', 'Device connected'), () => message('connectedBody', { name: device.name }), false);
      }, 1350));
    }
  }
  function openDialog(content) {
    dialogContent = content; renderDialog();
    if (!$('#app-dialog').open) $('#app-dialog').showModal();
  }
  function renderDialog() {
    const focusedAction = document.activeElement?.dataset.action;
    $('#dialog-content').innerHTML = resolveText(dialogContent);
    hydrateIcons($('#dialog-content'));
    if (focusedAction) $('#dialog-content').querySelector(`[data-action="${focusedAction}"]`)?.focus();
  }
  function pairDialog() {
    openDialog(() => `<div class="dialog-body"><span data-icon="bluetooth"></span><h2>${t('添加蓝牙设备', 'Add a Bluetooth device')}</h2><p>${t('正式应用会打开 Windows 蓝牙设置。此处可以模拟已完成配对，再返回设备列表。', 'The native app opens Windows Bluetooth settings. This preview can simulate pairing a device.')}</p><ol><li>${t('在手机和电脑上开启蓝牙', 'Enable Bluetooth on your phone and PC')}</li><li>${t('在 Windows 中添加并配对手机', 'Add and pair your phone in Windows')}</li><li>${t('回到 AudioBule，选择设备连接', 'Return to AudioBule and connect your phone')}</li></ol></div><div class="dialog-actions"><button class="button" data-action="close-dialog">${t('返回', 'Back')}</button><button class="button primary" data-action="simulate-pair">${t('模拟配对完成', 'Simulate pairing')}</button></div>`);
  }
  function setPreference(key) { preferences[key] = !preferences[key]; syncSettings(); persist(); }
  function resume() {
    state.running = true;
    $('#tray-icon-button').disabled = false;
    $('#app-window').hidden = false; $('#hidden-window-message').hidden = true; render();
  }
  function showWindow() { resume(); selectView('window'); $('#tray-context').hidden = true; $('#tray-flyout').hidden = false; }
  function showMenu() { $('#tray-context').hidden = false; $('#tray-flyout').hidden = true; $('#tray-context [role="menuitem"]').focus(); }

  document.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) {
      if (!event.target.closest('.tray-context')) $('#tray-context').hidden = true;
      return;
    }
    if (button.dataset.view) { selectView(button.dataset.view); return; }
    if (button.dataset.page) { selectPage(button.dataset.page); $('#app-window').classList.remove('nav-open'); syncNavigation(); return; }
    if (button.dataset.filter) { state.filter = button.dataset.filter; render(); return; }
    if (button.dataset.setting) { setPreference(button.dataset.setting); return; }
    const action = button.dataset.action;
    switch (action) {
      case 'pair': pairDialog(); break;
      case 'close-dialog': $('#app-dialog').close(); break;
      case 'simulate-pair': {
        $('#app-dialog').close();
        state.generation += 1;
        for (const timer of pendingConnections.values()) clearTimeout(timer);
        pendingConnections.clear();
        state.devices.forEach(device => { if (device.status === 'connecting') device.status = 'disconnected'; });
        if (!state.devices.some(device => device.id === 'sample-phone')) state.devices.push({ id: 'sample-phone', name: 'iPhone 16', status: 'disconnected' });
        state.scenario = 'normal'; state.filter = 'all'; $('#scenario').value = 'normal';
        showWindow(); selectPage('devices'); render(); showToast(() => message('pairedTitle'), () => message('pairedBody', { name: 'iPhone 16' })); break;
      }
      case 'device': operateDevice(button.dataset.deviceId); break;
      case 'refresh':
        if (refreshTimer) return;
        button.classList.add('spin'); button.disabled = true;
        refreshTimer = setTimeout(() => { button.classList.remove('spin'); button.disabled = false; refreshTimer = null; render(); showToast(() => message('refreshedTitle'), () => message('refreshedBody', { count: state.devices.length })); }, 700); break;
      case 'hide-window': $('#app-window').hidden = true; $('#hidden-window-message').hidden = false; showToast(() => message('minimizedTitle'), () => message('minimizedBody')); break;
      case 'show-window': showWindow(); break;
      case 'maximize': $('#app-window').classList.toggle('expanded'); break;
      case 'toggle-navigation': {
        const windowElement = $('#app-window');
        windowElement.classList.toggle(windowElement.clientWidth <= 800 ? 'nav-open' : 'nav-collapsed');
        syncNavigation(); break;
      }
      case 'view-tray': selectView('tray'); break;
      case 'tray-toggle': $('#tray-context').hidden = true; $('#tray-flyout').hidden = !$('#tray-flyout').hidden; break;
      case 'tray-more': showMenu(); break;
      case 'toggle-reconnect': setPreference('reconnect'); break;
      case 'toggle-startup': setPreference('startup'); break;
      case 'about': showWindow(); selectPage('about'); break;
      case 'dismiss-toast': $('#toast').hidden = true; clearTimeout(toastTimer); break;
      case 'exit': openDialog(() => `<div class="dialog-body"><h2>${t('退出 AudioBule？', 'Exit AudioBule?')}</h2><p>${t('退出后，所有设备的音频连接都会断开。关闭窗口可以保持连接并继续在托盘运行。', 'Exiting disconnects all devices. Close the window to keep connections running in the tray.')}</p></div><div class="dialog-actions"><button class="button" data-action="close-dialog">${t('取消', 'Cancel')}</button><button class="button primary" data-action="confirm-exit">${t('退出', 'Exit')}</button></div>`); break;
      case 'confirm-exit':
        $('#app-dialog').close(); state.running = false; state.generation += 1;
        for (const timer of pendingConnections.values()) clearTimeout(timer); pendingConnections.clear();
        state.devices.forEach(device => { device.status = 'disconnected'; });
        $('#tray-context').hidden = true; $('#tray-flyout').hidden = true; $('#tray-icon-button').disabled = true;
        $('#app-window').hidden = true; $('#hidden-window-message').hidden = false; selectView('window'); render(); break;
    }
    if (!['tray-more', 'toggle-reconnect', 'toggle-startup'].includes(action) && !button.closest('.tray-context')) $('#tray-context').hidden = true;
  });
  $('#theme-toggle').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
  $('#app-theme').addEventListener('change', event => setTheme(event.target.value));
  $('#app-language').addEventListener('change', event => setLanguage(event.target.value));
  $('#preview-language').addEventListener('change', event => setLanguage(event.target.value));
  $('#preview-theme').addEventListener('change', event => setTheme(event.target.value));
  $('#scenario').addEventListener('change', event => scenario(event.target.value));
  $('#tray-icon-button').addEventListener('contextmenu', event => { event.preventDefault(); if (state.running) showMenu(); });
  $('#tray-context').addEventListener('keydown', event => {
    const buttons = Array.from($('#tray-context').querySelectorAll('button'));
    const current = buttons.indexOf(document.activeElement);
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); buttons[(current + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length].focus(); }
    if (event.key === 'Home') { event.preventDefault(); buttons[0].focus(); }
    if (event.key === 'End') { event.preventDefault(); buttons.at(-1).focus(); }
  });
  function syncNavigation() {
    const windowElement = $('#app-window');
    $('.navigation-toggle').setAttribute('aria-expanded', String(windowElement.clientWidth <= 800 ? windowElement.classList.contains('nav-open') : !windowElement.classList.contains('nav-collapsed')));
  }
  new ResizeObserver(syncNavigation).observe($('#app-window'));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && $('#app-window').classList.contains('nav-open')) { $('#app-window').classList.remove('nav-open'); syncNavigation(); $('.navigation-toggle').focus(); }
    if (event.key === 'Escape' && !$('#tray-context').hidden) { $('#tray-context').hidden = true; $('#tray-icon-button').focus(); }
  });
  $('#app-dialog').addEventListener('click', event => { if (event.target === $('#app-dialog')) { const bounds = $('#app-dialog').getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) $('#app-dialog').close(); } });
  systemTheme.addEventListener('change', () => { if (preferences.theme === 'system') setTheme('system', false); });
  window.addEventListener('languagechange', () => { if (preferences.language === 'system') setLanguage('system'); });
  window.addEventListener('hashchange', () => selectView(location.hash.slice(1)));
  hydrateIcons(); setTheme(preferences.theme, false); syncSettings(); scenario('normal'); setLanguage(preferences.language); selectView(location.hash.slice(1) || 'window');
})();
