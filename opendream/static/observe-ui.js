    const app = document.getElementById('app');
    const route = location.pathname;
    function odSetMainHtml(html, onAfterInsert) {
      var path = typeof location !== 'undefined' ? location.pathname : '';
      var reduceMotion = false;
      try {
        reduceMotion = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
      } catch (eRm) {}
      var skipVt = path === '/graph' || reduceMotion;
      function apply() {
        app.innerHTML = html;
        if (typeof onAfterInsert === 'function') {
          try {
            onAfterInsert();
          } catch (e) {}
        }
      }
      if (!skipVt && typeof document !== 'undefined' && document.startViewTransition) {
        document.startViewTransition(apply);
      } else {
        apply();
      }
    }
    function odSaveScrollAndGoQueryString(qs) {
      var s = qs && qs.toString ? qs.toString() : String(qs || '');
      try {
        var appEl = document.getElementById('app');
        sessionStorage.setItem(
          'od-scroll-pending',
          JSON.stringify({
            path: location.pathname,
            nextSearch: s ? ('?' + s) : '',
            y: appEl ? appEl.scrollTop : 0,
          }),
        );
      } catch (e) {}
      location.search = s ? ('?' + s) : '';
    }
    function odTryRestoreScrollAfterRender() {
      try {
        var raw = sessionStorage.getItem('od-scroll-pending');
        if (!raw) return;
        var o = JSON.parse(raw);
        if (!o || o.path !== location.pathname) {
          sessionStorage.removeItem('od-scroll-pending');
          return;
        }
        if ((o.nextSearch || '') !== (location.search || '')) {
          sessionStorage.removeItem('od-scroll-pending');
          return;
        }
        sessionStorage.removeItem('od-scroll-pending');
        var appEl = document.getElementById('app');
        if (!appEl || typeof o.y !== 'number') return;
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            appEl.scrollTop = o.y;
          });
        });
      } catch (e) {
        try {
          sessionStorage.removeItem('od-scroll-pending');
        } catch (e2) {}
      }
    }
    function pathMatchesNav(href, path) {
      if (!href) return false;
      if (href === '/overview' && (path === '/' || path === '/overview')) return true;
      if (path === href) return true;
      if (href !== '/' && path.startsWith(href + '/')) return true;
      return false;
    }
    document.querySelectorAll('.sidebar-nav a').forEach((a) => {
      if (pathMatchesNav(a.getAttribute('href'), route)) a.classList.add('active');
    });
    (function themeUi(){
      var KEY='opendream-ui-theme';
      function sync(){
        var t=document.documentElement.getAttribute('data-theme')||'dark';
        document.querySelectorAll('.theme-toggle button[data-theme]').forEach(function(b){
          b.classList.toggle('theme-btn-active', b.getAttribute('data-theme')===t);
          b.setAttribute('aria-pressed', b.getAttribute('data-theme')===t ? 'true' : 'false');
        });
      }
      function set(t){
        document.documentElement.setAttribute('data-theme', t);
        try { localStorage.setItem(KEY, t); } catch(e) {}
        sync();
      }
      document.querySelectorAll('.theme-toggle button[data-theme]').forEach(function(btn){
        btn.addEventListener('click', function(){ set(btn.getAttribute('data-theme')); });
      });
      sync();
    })();
    (function sidebarUi(){
      var KEY='opendream-sidebar';
      function sync(){
        var m=document.documentElement.getAttribute('data-sidebar')||'wide';
        var btn=document.getElementById('sidebar-toggle');
        if(btn){
          btn.setAttribute('aria-pressed', m==='narrow' ? 'true' : 'false');
          btn.title=m==='wide' ? 'Narrow sidebar' : 'Widen sidebar';
          btn.setAttribute('aria-label', m==='wide' ? 'Narrow sidebar' : 'Widen sidebar');
        }
      }
      function set(mode){
        document.documentElement.setAttribute('data-sidebar', mode);
        try { localStorage.setItem(KEY, mode); } catch(e) {}
        sync();
      }
      var tbtn=document.getElementById('sidebar-toggle');
      if(tbtn) tbtn.addEventListener('click', function(){
        var cur=document.documentElement.getAttribute('data-sidebar')||'wide';
        set(cur==='wide' ? 'narrow' : 'wide');
      });
      sync();
    })();
    var OD_DENSITY_KEY = 'opendream-ui-density';
    function applyUiDensity(mode) {
      var m = mode === 'compact' || mode === 'comfortable' ? mode : 'comfortable';
      document.documentElement.setAttribute('data-density', m);
      try {
        localStorage.setItem(OD_DENSITY_KEY, m);
      } catch (e) {}
      syncUiDensitySettingsSegmented();
    }
    function syncUiDensitySettingsSegmented() {
      var d = document.documentElement.getAttribute('data-density') || 'comfortable';
      document.querySelectorAll('.od-settings-density button[data-density]').forEach(function (b) {
        var on = b.getAttribute('data-density') === d;
        b.classList.toggle('active', on);
        b.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    }
    (function mobileNav(){
      function set(open){
        document.documentElement.setAttribute('data-mobile-nav', open ? 'open' : '');
        var b = document.getElementById('sidebar-mobile-open');
        if (b) b.setAttribute('aria-expanded', open ? 'true' : 'false');
        var bd = document.getElementById('sidebar-backdrop');
        if (bd) bd.setAttribute('aria-hidden', open ? 'false' : 'true');
      }
      var openBtn = document.getElementById('sidebar-mobile-open');
      var backdrop = document.getElementById('sidebar-backdrop');
      if (openBtn) openBtn.addEventListener('click', function(){
        set(document.documentElement.getAttribute('data-mobile-nav') !== 'open');
      });
      if (backdrop) backdrop.addEventListener('click', function(){ set(false); });
      document.querySelectorAll('.sidebar-nav a').forEach(function(a){
        a.addEventListener('click', function(){
          try {
            if (window.matchMedia('(max-width: 900px)').matches) set(false);
          } catch (e) {}
        });
      });
      document.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        if (document.documentElement.getAttribute('data-mobile-nav') === 'open') {
          e.preventDefault();
          set(false);
        }
      });
    })();
    const qs = (obj) => new URLSearchParams(obj).toString();
    const escapeHtml = (s) => String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
    function odBreadcrumbHtml(items) {
      if (!items || !items.length) return '';
      const parts = items
        .map((it, i) => {
          const isLast = i === items.length - 1;
          if (isLast || !it.href) {
            return (
              '<span class="od-bc-current"' +
              (isLast ? ' aria-current="page"' : '') +
              '>' +
              escapeHtml(it.label) +
              '</span>'
            );
          }
          return '<a class="od-bc-link" href="' + it.href + '">' + escapeHtml(it.label) + '</a>';
        })
        .join('<span class="od-bc-sep" aria-hidden="true">/</span>');
      return '<nav class="od-breadcrumb" aria-label="Breadcrumb">' + parts + '</nav>';
    }
    function odTruncateMiddle(s, maxLen) {
      s = String(s || '');
      if (s.length <= maxLen) return s;
      const half = Math.floor((maxLen - 1) / 2);
      return s.slice(0, half) + '\u2026' + s.slice(s.length - half);
    }
    var odFsRestore = null;
    function closeOdPanelFullscreen() {
      var dlg = document.getElementById('od-fs-dialog');
      if (dlg && dlg.open) dlg.close();
    }
    window.closeOdPanelFullscreen = closeOdPanelFullscreen;
    (function odFullscreenDialog() {
      var dlg = document.getElementById('od-fs-dialog');
      var host = document.getElementById('od-fs-host');
      if (!dlg || !host) return;
      dlg.addEventListener('close', function() {
        document.documentElement.classList.remove('od-modal-open');
        if (!odFsRestore || !odFsRestore.el || !odFsRestore.section) return;
        var head = odFsRestore.section.querySelector('.panel-head');
        if (head) head.insertAdjacentElement('afterend', odFsRestore.el);
        else odFsRestore.section.appendChild(odFsRestore.el);
        odFsRestore = null;
      });
      dlg.addEventListener('click', function(e) {
        if (e.target === dlg) closeOdPanelFullscreen();
      });
      var xb = document.getElementById('od-fs-close');
      if (xb) xb.addEventListener('click', closeOdPanelFullscreen);
      document.addEventListener('click', function(e) {
        var b = e.target.closest('[data-fs-panel]');
        if (!b || !app.contains(b)) return;
        e.preventDefault();
        var key = b.getAttribute('data-fs-panel');
        var body = document.querySelector('[data-panel-body="' + key + '"]');
        if (!body) return;
        var section = body.closest('section.panel');
        if (!section) return;
        odFsRestore = { section: section, el: body };
        var t = document.getElementById('od-fs-title');
        if (t) t.textContent = body.getAttribute('data-panel-title') || '';
        host.appendChild(body);
        document.documentElement.classList.add('od-modal-open');
        dlg.showModal();
      });
    })();
    const memoryExplorerParams = (updates = {}) => {
      const p = new URLSearchParams(location.search);
      for (const [k, v] of Object.entries(updates)) {
        if (v === '' || v === null || v === undefined) p.delete(k);
        else p.set(k, String(v));
      }
      return p;
    };
    function applyMemoryTimePreset(hours) {
      const now = new Date();
      const from = new Date(now.getTime() - hours * 3600 * 1000);
      const p = memoryExplorerParams({
        updated_after: from.toISOString(),
        updated_before: now.toISOString(),
        offset: '0',
      });
      odSaveScrollAndGoQueryString(p.toString());
    }
    function applyRetrievalTimePreset(hours) {
      const now = new Date();
      const from = new Date(now.getTime() - hours * 3600 * 1000);
      const p = memoryExplorerParams({
        timestamp_after: from.toISOString(),
        timestamp_before: now.toISOString(),
        offset: '0',
      });
      odSaveScrollAndGoQueryString(p.toString());
    }
    function applyRunTimePreset(hours) {
      const now = new Date();
      const from = new Date(now.getTime() - hours * 3600 * 1000);
      const p = memoryExplorerParams({
        ended_after: from.toISOString(),
        ended_before: now.toISOString(),
        offset: '0',
      });
      odSaveScrollAndGoQueryString(p.toString());
    }
    const memoryHref = (id) => '/memories/' + encodeURIComponent(id) + (location.search || '');
    /** URL/API use UTC ISO strings; datetime-local uses the browser's local timezone. */
    const isoUtcToDatetimeLocal = (iso) => {
      if (!iso || !String(iso).trim()) return '';
      const d = new Date(String(iso).trim());
      if (Number.isNaN(d.getTime())) return '';
      const pad = (n) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };
    const datetimeLocalToIsoUtc = (raw) => {
      if (!raw || !String(raw).trim()) return '';
      const d = new Date(String(raw).trim());
      if (Number.isNaN(d.getTime())) return '';
      return d.toISOString();
    };
    const badge = (value) => {
      let cls = 'warning-badge';
      if (value === 'active') cls = 'active-badge';
      else if (value === 'contested') cls = 'contested-badge';
      else if (value === 'superseded') cls = 'superseded-badge';
      else if (value === 'deleted' || value === 'quarantined') cls = 'error-badge';
      return `<span class="badge ${cls}">${escapeHtml(value)}</span>`;
    };
    const memoryTypeHue = (str) => {
      let h = 0;
      const s = String(str || '');
      for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
      return h % 360;
    };
    const memoryTimelineBarHeight = (item) => {
      const s = item.salience;
      if (s != null && s !== '' && !Number.isNaN(Number(s))) return Math.max(28, 32 + Number(s) * 40);
      const c = item.confidence;
      if (c != null && c !== '' && !Number.isNaN(Number(c))) return Math.max(28, 32 + Number(c) * 28);
      return 36;
    };
    const memoryTimelineHighlight = (text, query) => {
      const t = String(text || '');
      const needle = (query || '').trim();
      if (!needle) return escapeHtml(t);
      const low = t.toLowerCase();
      const qi = low.indexOf(needle.toLowerCase());
      if (qi === -1) return escapeHtml(t);
      return (
        escapeHtml(t.slice(0, qi)) +
        '<mark class="timeline-mark">' +
        escapeHtml(t.slice(qi, qi + needle.length)) +
        '</mark>' +
        escapeHtml(t.slice(qi + needle.length))
      );
    };
    const buildMemoryTimelineHtml = (items, searchQuery) => {
      const sorted = [...items].sort((a, b) => {
        const ta = new Date(a.updated_at || 0).getTime();
        const tb = new Date(b.updated_at || 0).getTime();
        return tb - ta;
      });
      let lastDay = '';
      const parts = [];
      for (const item of sorted) {
        const d = new Date(item.updated_at || '');
        const hasTime = !Number.isNaN(d.getTime());
        const dayKey = hasTime
          ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
          : '_nodate';
        if (dayKey !== lastDay) {
          lastDay = dayKey;
          const dayLabel = hasTime
            ? d.toLocaleDateString(undefined, {
                weekday: 'short',
                month: 'numeric',
                day: 'numeric',
                year: 'numeric',
              })
            : 'No date';
          parts.push(`<div class="mem-timeline-day">${escapeHtml(dayLabel)}</div>`);
        }
        const timeStr = hasTime
          ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
          : '—';
        const hue = memoryTypeHue(item.type || item.memory_id || 'x');
        const barH = memoryTimelineBarHeight(item);
        const barColor = `hsl(${hue} 55% 42%)`;
        const titleHtml = memoryTimelineHighlight(item.title || 'Untitled', searchQuery);
        const sumRaw = (item.summary || '').slice(0, 220);
        const sumHtml = memoryTimelineHighlight(sumRaw, searchQuery);
        parts.push(`<div class="mem-timeline-item">
          <div class="mem-timeline-time"><p>${escapeHtml(timeStr)}</p></div>
          <div class="mem-timeline-rail">
            <div class="mem-timeline-dot"></div>
            <div class="mem-timeline-bar" style="height:${barH}px;background:${barColor};"></div>
          </div>
          <div class="mem-timeline-body">
            <div class="t-meta">${badge(item.status)}
              <span class="muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.05em">${escapeHtml(
                item.type || ''
              )}</span>
              <span class="muted" style="font-size:11px">· ${escapeHtml(item.scope || '')}</span>
            </div>
            <div class="t-title"><a href="${memoryHref(item.memory_id)}">${titleHtml}</a></div>
            <div class="t-sum">${sumHtml || '<span class="muted">No summary</span>'}</div>
            <div class="t-id">${escapeHtml(item.memory_id || '')}</div>
          </div>
        </div>`);
      }
      return parts.join('') || '<p class="muted">No memories match.</p>';
    };
    const retrievalTimelineBarHeight = (item) => {
      const n = (item.selected_memory_ids || []).length;
      return Math.max(28, 32 + Math.min(n * 14, 72));
    };
    const buildRetrievalTimelineHtml = (items, searchQuery) => {
      const sorted = [...items].sort((a, b) => {
        const ta = new Date(a.timestamp || 0).getTime();
        const tb = new Date(b.timestamp || 0).getTime();
        return tb - ta;
      });
      let lastDay = '';
      const parts = [];
      for (const item of sorted) {
        const d = new Date(item.timestamp || '');
        const hasTime = !Number.isNaN(d.getTime());
        const dayKey = hasTime
          ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
          : '_nodate';
        if (dayKey !== lastDay) {
          lastDay = dayKey;
          const dayLabel = hasTime
            ? d.toLocaleDateString(undefined, {
                weekday: 'short',
                month: 'numeric',
                day: 'numeric',
                year: 'numeric',
              })
            : 'No date';
          parts.push(`<div class="mem-timeline-day">${escapeHtml(dayLabel)}</div>`);
        }
        const timeStr = hasTime
          ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
          : '—';
        const hue = memoryTypeHue(item.query || item.id || 'x');
        const barH = retrievalTimelineBarHeight(item);
        const barColor = `hsl(${hue} 55% 42%)`;
        const n = (item.selected_memory_ids || []).length;
        const qRaw = item.query || '';
        const titleHtml = memoryTimelineHighlight(qRaw || '(no query)', searchQuery);
        const sumRaw = (item.summary || '').slice(0, 220);
        const sumHtml = sumRaw ? escapeHtml(sumRaw) : '<span class="muted">No summary</span>';
        parts.push(`<div class="mem-timeline-item">
          <div class="mem-timeline-time"><p>${escapeHtml(timeStr)}</p></div>
          <div class="mem-timeline-rail">
            <div class="mem-timeline-dot"></div>
            <div class="mem-timeline-bar" style="height:${barH}px;background:${barColor};"></div>
          </div>
          <div class="mem-timeline-body">
            <div class="t-meta">
              <span class="muted" style="font-size:11px" title="Memories included in the ranked result set for this retrieval">${n} selected</span>
              <span class="muted" style="font-size:11px">· retrieval</span>
            </div>
            <div class="t-title"><a href="${retrievalHref(item.id)}">${titleHtml}</a></div>
            <div class="t-sum">${sumHtml}</div>
            <div class="t-id">${escapeHtml(item.id || '')}</div>
          </div>
        </div>`);
      }
      return parts.join('') || '<p class="muted">No retrievals match.</p>';
    };
    const runEffectiveInstant = (item) => {
      const e = item && item.ended_at != null ? String(item.ended_at).trim() : '';
      if (e) return e;
      const s = item && item.started_at != null ? String(item.started_at).trim() : '';
      return s;
    };
    const buildRunTimelineHtml = (items, searchQuery) => {
      const sorted = [...items].sort((a, b) => {
        const ta = new Date(runEffectiveInstant(a) || 0).getTime();
        const tb = new Date(runEffectiveInstant(b) || 0).getTime();
        return tb - ta;
      });
      let lastDay = '';
      const parts = [];
      const needle = (searchQuery || '').trim().toLowerCase();
      for (const item of sorted) {
        const rawTs = runEffectiveInstant(item);
        const d = new Date(rawTs || '');
        const hasTime = !Number.isNaN(d.getTime());
        const dayKey = hasTime
          ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
          : '_nodate';
        if (dayKey !== lastDay) {
          lastDay = dayKey;
          const dayLabel = hasTime
            ? d.toLocaleDateString(undefined, {
                weekday: 'short',
                month: 'numeric',
                day: 'numeric',
                year: 'numeric',
              })
            : 'No date';
          parts.push(`<div class="mem-timeline-day">${escapeHtml(dayLabel)}</div>`);
        }
        const timeStr = hasTime
          ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
          : '—';
        const hue = memoryTypeHue(item.type || item.run_id || 'x');
        const barH = Math.max(32, 36 + String(item.diff_text || '').length > 200 ? 48 : 36);
        const barColor = `hsl(${hue} 55% 42%)`;
        const rid = String(item.run_id || '');
        const hay = `${rid} ${item.type || ''} ${item.status || ''}`.toLowerCase();
        const hit = needle && hay.includes(needle);
        const titleRaw = `${item.type || 'run'} · ${item.status || ''}`;
        const titleHtml = hit
          ? memoryTimelineHighlight(titleRaw, searchQuery)
          : escapeHtml(titleRaw);
        parts.push(`<div class="mem-timeline-item">
          <div class="mem-timeline-time"><p>${escapeHtml(timeStr)}</p></div>
          <div class="mem-timeline-rail">
            <div class="mem-timeline-dot"></div>
            <div class="mem-timeline-bar" style="height:${barH}px;background:${barColor};"></div>
          </div>
          <div class="mem-timeline-body">
            <div class="t-meta">${badge(String(item.status || 'unknown'))}
              <span class="muted" style="font-size:11px;text-transform:uppercase;letter-spacing:0.05em">${escapeHtml(
                String(item.type || '')
              )}</span>
            </div>
            <div class="t-title"><a href="${runHref(rid)}" title="${escapeHtml(rid)}">${titleHtml}</a></div>
            <div class="t-sum"><span class="muted" style="font-size:12px">Started</span> ${escapeHtml(
              formatInstantLocal(item.started_at) || '—'
            )} · <span class="muted" style="font-size:12px">Ended</span> ${escapeHtml(formatInstantLocal(item.ended_at) || '—')}</div>
            <div class="t-id"><a href="${runHref(rid)}" title="Run id">${escapeHtml(rid)}</a></div>
          </div>
        </div>`);
      }
      return parts.join('') || '<p class="muted">No runs match.</p>';
    };
    window.odDismissFirstSteps = function () {
      try {
        localStorage.setItem('opendream-first-steps-dismissed', '1');
      } catch (_d0) {}
      var inner = document.getElementById('od-first-steps-panel');
      var sec = inner && inner.closest('section.panel');
      if (sec) sec.remove();
    };
    window.odCopyApiUrl = function (btn) {
      var path = btn.getAttribute('data-api-path') || '';
      var method = btn.getAttribute('data-api-method') || 'GET';
      var line = method + ' ' + location.origin + path;
      void navigator.clipboard.writeText(line).catch(function () {});
    };
    window.odCopyApiCurl = function (btn) {
      var path = btn.getAttribute('data-api-path') || '';
      var method = String(btn.getAttribute('data-api-method') || 'GET').toUpperCase();
      var url = location.origin + path;
      var line = method === 'GET' ? 'curl -sS ' + JSON.stringify(url) : 'curl -sS -X ' + method + ' ' + JSON.stringify(url);
      void navigator.clipboard.writeText(line).catch(function () {});
    };
    window.odCopyApiFetch = function (btn) {
      var path = btn.getAttribute('data-api-path') || '';
      var method = String(btn.getAttribute('data-api-method') || 'GET').toUpperCase();
      var url = location.origin + path;
      var line =
        'await fetch(' +
        JSON.stringify(url) +
        ', { method: ' +
        JSON.stringify(method) +
        ' }).then(function (r) { return r.json(); });';
      void navigator.clipboard.writeText(line).catch(function () {});
    };
    const fetchJson = async (path, options={}) => {
      const response = await fetch(path, options);
      const bodyText = await response.text();
      if (!response.ok) {
        let msg = bodyText.slice(0, 800) || ('HTTP ' + response.status);
        try {
          const j = JSON.parse(bodyText);
          if (j && typeof j.error === 'string') msg = j.error;
        } catch (_e) {}
        const err = new Error(msg);
        err.status = response.status;
        throw err;
      }
      if (!bodyText.trim()) return {};
      return JSON.parse(bodyText);
    };
    function odCsvEscape(v) {
      if (v === null || v === undefined) return '';
      if (typeof v === 'object') return odCsvEscape(JSON.stringify(v));
      var s = String(v);
      if (/[",\n\r]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
      return s;
    }
    function odItemsToCsv(data) {
      var items = data && data.items;
      if (!items || !items.length) return 'no_rows\n';
      var keys = Object.keys(items[0]);
      var lines = [keys.join(',')];
      for (var i = 0; i < items.length; i++) {
        var row = items[i];
        lines.push(keys.map(function (k) { return odCsvEscape(row[k]); }).join(','));
      }
      return lines.join('\n');
    }
    function odDownloadBlob(filename, blob) {
      var a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.rel = 'noopener';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(function () { try { URL.revokeObjectURL(a.href); } catch (e) {} }, 1500);
    }
    window.odCopyCurrentViewUrl = function () {
      var u = typeof location !== 'undefined' ? location.href : '';
      if (!u) return;
      void navigator.clipboard.writeText(u).catch(function () {});
    };
    window.odExportCurrentList = async function (kind, format) {
      format = format || 'json';
      var path = location.pathname;
      var search = location.search || '';
      var apiPath;
      if (kind === 'memories' && path.indexOf('/memories/') === 0 && path !== '/memories') {
        apiPath = '/api/memories/' + encodeURIComponent(decodeURIComponent(path.split('/').pop() || ''));
      } else if (kind === 'runs' && path.indexOf('/runs/') === 0 && path !== '/runs') {
        apiPath = '/api/runs/' + encodeURIComponent(decodeURIComponent(path.split('/').pop() || ''));
      } else if (kind === 'retrievals' && path.indexOf('/retrievals/') === 0 && path !== '/retrievals') {
        apiPath = '/api/retrievals/' + encodeURIComponent(decodeURIComponent(path.split('/').pop() || ''));
      } else {
        apiPath = '/api/' + kind + search;
      }
      var data = await fetchJson(apiPath);
      var base = kind.replace(/[^a-z0-9_-]/gi, '_') + '-export';
      if (format === 'json') {
        odDownloadBlob(base + '.json', new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
        return;
      }
      if (format !== 'csv') return;
      if (!data.items || !data.items.length) {
        odDownloadBlob(base + '.csv', new Blob(['single_object\nuse JSON export for this view\n'], { type: 'text/csv;charset=utf-8' }));
        return;
      }
      odDownloadBlob(base + '.csv', new Blob([odItemsToCsv(data)], { type: 'text/csv;charset=utf-8' }));
    };
    function odEmptyState(title, bodyHtml) {
      return (
        '<div class="od-empty-nextsteps od-empty-state" role="status"><p class="muted" style="margin:0 0 8px 0"><strong>' +
        escapeHtml(title) +
        '</strong></p>' +
        bodyHtml +
        '</div>'
      );
    }
    function odInlineError(msg) {
      return '<p class="od-inline-error" role="alert">' + escapeHtml(msg) + '</p>';
    }
    (function odScopeBarBookmarks() {
      var KEY = 'opendream-dashboard-bookmarks';
      var ctxCache = null;
      function readBookmarks() {
        try {
          var raw = localStorage.getItem(KEY);
          if (!raw) return [];
          var arr = JSON.parse(raw);
          return Array.isArray(arr) ? arr : [];
        } catch (e1) {
          return [];
        }
      }
      function writeBookmarks(arr) {
        try {
          localStorage.setItem(KEY, JSON.stringify(arr));
        } catch (e2) {}
      }
      function defaultLabel(ctx) {
        if (ctx && ctx.workspace_name) return ctx.workspace_name;
        var p = (ctx && ctx.workspace_path) || '';
        var parts = String(p).replace(/\\\\/g, '/').split('/').filter(Boolean);
        return parts.length ? parts[parts.length - 1] : p || 'dashboard';
      }
      function renderList() {
        var ul = document.getElementById('od-scope-bookmark-list');
        if (!ul) return;
        var bm = readBookmarks();
        var origin = location.origin;
        if (!bm.length) {
          ul.innerHTML = '<li class="muted" style="font-size:11px">No bookmarks yet.</li>';
          return;
        }
        ul.innerHTML = bm
          .map(function (b) {
            var lab = escapeHtml(b.label || b.origin);
            var o = String(b.origin || '');
            var oEsc = escapeHtml(o);
            if (o === origin) {
              return (
                '<li><span class="od-scope-bm-current">This tab · ' +
                lab +
                '</span> <button type="button" class="od-scope-bm-remove" data-remove-origin="' +
                oEsc +
                '" aria-label="Remove bookmark">Remove</button></li>'
              );
            }
            return (
              '<li><button type="button" class="od-scope-bm-open" data-open-origin="' +
              oEsc +
              '">Open ' +
              lab +
              '</button> <button type="button" class="od-scope-bm-remove" data-remove-origin="' +
              oEsc +
              '" aria-label="Remove bookmark">Remove</button></li>'
            );
          })
          .join('');
      }
      function bindBookmarkList() {
        var ul = document.getElementById('od-scope-bookmark-list');
        if (!ul || ul.getAttribute('data-od-bm-bound') === '1') return;
        ul.setAttribute('data-od-bm-bound', '1');
        ul.addEventListener('click', function (ev) {
          var openBtn = ev.target.closest('.od-scope-bm-open');
          if (openBtn) {
            var target = openBtn.getAttribute('data-open-origin') || '';
            if (target) window.location.href = target + '/overview';
            return;
          }
          var remBtn = ev.target.closest('.od-scope-bm-remove');
          if (remBtn) {
            var rem = remBtn.getAttribute('data-remove-origin') || '';
            writeBookmarks(readBookmarks().filter(function (x) { return x.origin !== rem; }));
            renderList();
          }
        });
      }
      function applyScopeHealthPill(sh) {
        var pill = document.getElementById('od-scope-health-pill');
        if (!pill || !sh) return;
        pill.textContent = sh.label || 'Status';
        pill.className = 'od-scope-health-pill od-scope-health-pill--' + (sh.level || 'ok');
        var tip = 'Memories: ' + (sh.memory_total != null ? sh.memory_total : '—');
        if (sh.contested != null) tip += ', contested: ' + sh.contested;
        if (sh.pending_events != null) tip += ', pending events: ' + sh.pending_events;
        pill.setAttribute('title', tip);
        var link = sh.link || '/overview';
        if (pill.tagName === 'A') pill.setAttribute('href', link);
      }
      var OD_SPARKLES_SVG =
        '<svg class="od-dream-sparkles" viewBox="0 0 24 24" aria-hidden="true" focusable="false" width="14" height="14">' +
        '<path d="M12 2l1.25 5.45L18.75 9l-5.5 1.55L12 16l-1.25-5.45L5.25 9l5.5-1.55z" fill="currentColor"/>' +
        '<path d="M19 14l.55 2.2L21.75 17l-2.2.55L19 19.75 17.55 17.75 15.35 17l2.2-.55z" fill="currentColor" opacity=".55"/>' +
        '</svg>';
      var odDreamModeSelectSyncing = false;
      function odDreamModeClamp(selEl, dm) {
        var m = dm || 'deterministic';
        if (selEl && selEl.querySelector && !selEl.querySelector('option[value="' + m + '"]')) {
          return 'deterministic';
        }
        return m;
      }
      function syncDreamModeUi(ctx, loadError) {
        var sel = document.getElementById('od-dream-mode-select');
        var spark = document.getElementById('od-dream-mode-sparkle');
        var row = document.getElementById('od-dream-mode-row');
        var root = document.documentElement;
        root.removeAttribute('data-od-semantic-state');
        root.removeAttribute('data-od-semantic-raw');
        root.removeAttribute('data-od-workspace-probe');
        if (!sel) return;
        function clearSpark() {
          if (!spark) return;
          spark.innerHTML = '';
          spark.setAttribute('hidden', '');
        }
        function showSpark() {
          if (!spark) return;
          spark.innerHTML = OD_SPARKLES_SVG;
          spark.removeAttribute('hidden');
        }
        if (loadError) {
          sel.disabled = true;
          sel.removeAttribute('aria-invalid');
          clearSpark();
          root.removeAttribute('data-od-dream-mode');
          return;
        }
        var probeSt = ctx && ctx.workspace_probe_status ? String(ctx.workspace_probe_status) : '';
        if (probeSt && probeSt !== 'ok') {
          sel.disabled = true;
          sel.removeAttribute('aria-invalid');
          clearSpark();
          root.setAttribute('data-od-workspace-probe', probeSt);
          root.removeAttribute('data-od-dream-mode');
          return;
        }
        root.setAttribute('data-od-workspace-probe', probeSt || 'ok');
        var dm = odDreamModeClamp(sel, (ctx && ctx.dream_mode) || 'deterministic');
        root.setAttribute('data-od-dream-mode', dm);
        var raw =
          ctx && ctx.semantic_state_summary != null && ctx.semantic_state_summary !== ''
            ? String(ctx.semantic_state_summary)
            : '';
        if (raw) {
          root.setAttribute('data-od-semantic-state', 'on');
          root.setAttribute('data-od-semantic-raw', raw);
        } else {
          root.setAttribute('data-od-semantic-state', 'off');
        }
        if (dm === 'hybrid' || dm === 'semantic') {
          showSpark();
        } else {
          clearSpark();
        }
        sel.disabled = false;
        odDreamModeSelectSyncing = true;
        try {
          if (sel.value !== dm) sel.value = dm;
        } finally {
          odDreamModeSelectSyncing = false;
        }
        sel.removeAttribute('aria-invalid');
        if (row) row.classList.remove('od-dream-mode-row--error');
      }
      function wireDreamModeSelectOnce() {
        var sel = document.getElementById('od-dream-mode-select');
        var statusEl = document.getElementById('od-dream-mode-status');
        if (!sel || sel.getAttribute('data-od-wired') === '1') return;
        sel.setAttribute('data-od-wired', '1');
        sel.addEventListener('change', async function () {
          if (odDreamModeSelectSyncing) return;
          var want = sel.value;
          var prev = (ctxCache && ctxCache.dream_mode) || 'deterministic';
          if (statusEl) statusEl.textContent = '';
          sel.disabled = true;
          try {
            await fetchJson('/api/semantic-dream-mode', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ mode: want }),
            });
            if (statusEl) statusEl.textContent = 'Saved';
            await refreshScopeContext();
          } catch (eSave) {
            odDreamModeSelectSyncing = true;
            try {
              sel.value = prev;
            } finally {
              odDreamModeSelectSyncing = false;
            }
            if (statusEl) {
              statusEl.textContent = 'Save failed: ' + (eSave && eSave.message ? eSave.message : eSave);
            }
            sel.setAttribute('aria-invalid', 'true');
            var row = document.getElementById('od-dream-mode-row');
            if (row) row.classList.add('od-dream-mode-row--error');
            syncDreamModeUi(ctxCache, false);
            sel.disabled = false;
            return;
          }
          if (statusEl) {
            setTimeout(function () {
              if (statusEl.textContent === 'Saved') statusEl.textContent = '';
            }, 3200);
          }
          if (ctxCache && ctxCache.workspace_probe_status === 'ok') {
            sel.disabled = false;
          }
        });
      }
      async function refreshScopeContext() {
        var pathEl = document.getElementById('od-scope-path');
        var originEl = document.getElementById('od-scope-origin');
        if (!pathEl || !originEl) return;
        originEl.textContent = 'This UI: ' + location.origin;
        bindBookmarkList();
        try {
          ctxCache = await fetchJson('/api/ui-context');
        } catch (e3) {
          pathEl.textContent = 'Could not load workspace context.';
          pathEl.classList.add('od-scope-error');
          pathEl.removeAttribute('title');
          var pillErr = document.getElementById('od-scope-health-pill');
          if (pillErr) {
            pillErr.textContent = 'Unknown';
            pillErr.className = 'od-scope-health-pill od-scope-health-pill--attention';
            pillErr.setAttribute('title', 'Could not load scope health');
            if (pillErr.tagName === 'A') pillErr.setAttribute('href', '/overview');
          }
          syncDreamModeUi(null, true);
          return;
        }
        pathEl.classList.remove('od-scope-error');
        var path = ctxCache.workspace_path || '';
        var line = path;
        var title = path;
        if (ctxCache.workspace_name) {
          line = ctxCache.workspace_name + ' — ' + path;
          title = ctxCache.workspace_name + '\\n' + path;
        }
        pathEl.textContent = line;
        pathEl.setAttribute('title', title);
        var addBtn = document.getElementById('od-scope-add-bookmark');
        if (addBtn && !addBtn.getAttribute('data-od-bm-wired')) {
          addBtn.setAttribute('data-od-bm-wired', '1');
          addBtn.setAttribute('aria-label', 'Bookmark this dashboard at ' + location.origin);
          addBtn.addEventListener('click', function () {
            var o = location.origin;
            var label = defaultLabel(ctxCache);
            var next = readBookmarks().filter(function (x) { return x.origin !== o; });
            next.push({ origin: o, label: label });
            writeBookmarks(next);
            renderList();
          });
        }
        renderList();
        if (ctxCache.scope_health) applyScopeHealthPill(ctxCache.scope_health);
        syncDreamModeUi(ctxCache, false);
        wireDreamModeSelectOnce();
      }
      async function boot() {
        await refreshScopeContext();
      }
      document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'visible') void refreshScopeContext();
      });
      void boot();
    })();
    const fsExpandSvg = '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>';
    const panel = (title, body, full=false, panelKey=null) => {
      if (!panelKey) {
        return '<section class="panel ' + (full ? 'full' : '') + '"><h2>' + title + '</h2>' + body + '</section>';
      }
      var safe = escapeHtml(title);
      return '<section class="panel panel-fs ' + (full ? 'full' : '') + '"><div class="panel-head"><h2 class="panel-title">' + safe + '</h2><button type="button" class="icon-btn panel-fs-open" data-fs-panel="' + panelKey + '" aria-label="Open ' + safe + ' in fullscreen" title="Fullscreen">' + fsExpandSvg + '</button></div><div class="panel-body-od" data-panel-body="' + panelKey + '" data-panel-title="' + safe + '">' + body + '</div></section>';
    };
    const pretty = (obj) => `<pre>${JSON.stringify(obj, null, 2)}</pre>`;
    function routeToPageId(path) {
      var p = path || '';
      if (p === '/' || p === '/overview') return 'overview';
      if (p === '/workspaces') return 'workspaces';
      if (p.indexOf('/workspaces/') === 0) return 'workspace-detail';
      if (p === '/memories') return 'memories';
      if (p.indexOf('/memories/') === 0) return 'memory-detail';
      if (p === '/runs') return 'runs';
      if (p.indexOf('/runs/') === 0) return 'run-detail';
      if (p === '/retrievals') return 'retrievals';
      if (p.indexOf('/retrievals/') === 0) return 'retrieval-detail';
      if (p === '/sessions') return 'sessions';
      if (p.indexOf('/sessions/') === 0) return 'session-detail';
      if (p === '/context' || p === '/context/') return 'context';
      if (p.indexOf('/context/') === 0) return 'context-detail';
      if (p === '/reviews') return 'reviews';
      if (p === '/graph') return 'graph';
      if (p === '/evals') return 'evals';
      if (p === '/exports') return 'exports';
      if (p === '/settings') return 'settings';
      return 'overview';
    }
    function applyEntityAttrsFromRoute(path) {
      app.removeAttribute('data-entity-type');
      app.removeAttribute('data-entity-id');
      var parts = path.split('/').filter(function (x) { return x; });
      if (parts.length < 2) return;
      var kind = parts[0];
      var raw = parts[1];
      try {
        raw = decodeURIComponent(raw);
      } catch (e2) {}
      if (kind === 'memories' && raw) {
        app.setAttribute('data-entity-type', 'memory');
        app.setAttribute('data-entity-id', raw);
      } else if (kind === 'runs' && raw) {
        app.setAttribute('data-entity-type', 'run');
        app.setAttribute('data-entity-id', raw);
      } else if (kind === 'retrievals' && raw) {
        app.setAttribute('data-entity-type', 'retrieval');
        app.setAttribute('data-entity-id', raw);
      } else if (kind === 'sessions' && raw) {
        app.setAttribute('data-entity-type', 'session');
        app.setAttribute('data-entity-id', raw);
      } else if (kind === 'context' && raw) {
        app.setAttribute('data-entity-type', 'context');
        app.setAttribute('data-entity-id', raw);
      } else if (kind === 'workspaces' && raw) {
        app.setAttribute('data-entity-type', 'workspace');
        app.setAttribute('data-entity-id', raw);
      }
    }
    function syncOdChromeAfterRender(label) {
      document.title = label + ' · OpenDream Observability';
      document.documentElement.setAttribute('data-page', routeToPageId(route));
      applyEntityAttrsFromRoute(route);
      var ann = document.getElementById('od-route-announce');
      if (ann) {
        ann.textContent = '';
        setTimeout(function () {
          ann.textContent = label + ' loaded';
        }, 50);
      }
      try {
        app.focus({ preventScroll: true, focusVisible: false });
      } catch (eFocus) {
        try {
          app.focus();
        } catch (e2) {}
      }
    }
    function odLoadingSkeletonHtml(label) {
      return (
        '<section class="panel full od-skeleton-wrap" role="status" aria-live="polite" aria-busy="true">' +
        '<h2 class="od-skeleton-h">Loading…</h2>' +
        '<p class="muted" style="margin:0 0 1rem">' +
        escapeHtml(label) +
        '</p>' +
        '<div class="od-skeleton-grid">' +
        '<div><div class="od-skel-metric" style="margin-bottom:10px"></div><div class="od-skel-line od-skel-line--med" style="margin-bottom:8px"></div><div class="od-skel-line od-skel-line--short"></div></div>' +
        '<div><div class="od-skel-metric" style="margin-bottom:10px"></div><div class="od-skel-line od-skel-line--med" style="margin-bottom:8px"></div><div class="od-skel-line"></div></div>' +
        '</div></section>'
      );
    }
    async function runRender(label, fn) {
      closeOdPanelFullscreen();
      app.setAttribute('aria-busy', 'true');
      app.setAttribute('aria-label', 'Loading ' + label);
      odSetMainHtml(odLoadingSkeletonHtml(label));
      try {
        await fn();
        var fr = document.getElementById('od-data-freshness');
        if (fr) {
          fr.textContent = 'Data loaded at ' + new Date().toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' });
        }
        syncOdChromeAfterRender(label);
        odTryRestoreScrollAfterRender();
      } catch (err) {
        const msg = err && err.message ? err.message : String(err);
        const status = err && err.status != null ? String(err.status) : '';
        const clipText = (status ? 'HTTP ' + status + '\\n' : '') + msg;
        const statusLine = status ? `<p class="muted" style="margin:0 0 8px 0">HTTP <strong>${escapeHtml(status)}</strong></p>` : '';
        odSetMainHtml([
          panel('Could not load', statusLine + `<p class="muted">${escapeHtml(msg)}</p><p class="row od-err-actions" style="gap:8px;align-items:center;flex-wrap:wrap"><button type="button" class="icon-btn od-api-copy-btn" id="od-retry-btn" aria-label="Retry" title="Retry"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg></button><button type="button" class="icon-btn od-api-copy-btn" id="od-copy-err-btn" aria-label="Copy error details" title="Copy error"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button></p>`, true),
        ].join(''));
        document.title = 'Could not load · OpenDream Observability';
        document.documentElement.setAttribute('data-page', 'error');
        app.removeAttribute('data-entity-type');
        app.removeAttribute('data-entity-id');
        var annE = document.getElementById('od-route-announce');
        if (annE) {
          annE.textContent = '';
          setTimeout(function () {
            annE.textContent = 'Could not load page';
          }, 50);
        }
        const btn = document.getElementById('od-retry-btn');
        if (btn) btn.onclick = () => { void runRender(label, fn); };
        const copyErr = document.getElementById('od-copy-err-btn');
        if (copyErr) copyErr.onclick = function () { void navigator.clipboard.writeText(clipText).catch(function () {}); };
      } finally {
        app.setAttribute('aria-busy', 'false');
        app.setAttribute('aria-label', 'Main content');
      }
    }
    /** Human-readable instant in the viewer's locale and local timezone (Intl). */
    const formatInstantLocal = (input) => {
      if (input === undefined || input === null || input === '') return '';
      const d = new Date(input);
      if (Number.isNaN(d.getTime())) return String(input);
      const s = typeof input === 'string' ? input.trim() : '';
      const hasTime =
        (s && /T\\d{2}:\\d{2}/.test(s)) ||
        (s && /Z$/.test(s)) ||
        (s && /[+-]\\d{2}:?\\d{2}$/.test(s));
      if (s && !hasTime && /^\\d{4}-\\d{2}-\\d{2}$/.test(s)) {
        const [y, m, day] = s.split('-').map(Number);
        return new Intl.DateTimeFormat(undefined, {
          weekday: 'short',
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        }).format(new Date(y, m - 1, day));
      }
      /* Do not mix dateStyle/timeStyle with timeZoneName — throws in V8/ICU. */
      return new Intl.DateTimeFormat(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
        timeZoneName: 'short',
      }).format(d);
    };
    const looksLikeIsoDateString = (v) =>
      typeof v === 'string' &&
      (/^\\d{4}-\\d{2}-\\d{2}T/.test(v) ||
        /^\\d{4}-\\d{2}-\\d{2}Z?$/.test(v) ||
        /^\\d{4}-\\d{2}-\\d{2}[+-]/.test(v) ||
        /^\\d{4}-\\d{2}-\\d{2}$/.test(v));
    const jsonStringifyWithLocalDates = (obj) =>
      JSON.stringify(
        obj,
        (_k, v) => {
          if (looksLikeIsoDateString(v)) {
            const d = new Date(v);
            if (!Number.isNaN(d.getTime())) return formatInstantLocal(v);
          }
          return v;
        },
        2
      );
    const formatMemoryDetailReadable = (d) => {
      const r = d.raw_json && typeof d.raw_json === 'object' ? d.raw_json : d;
      const line = (label, val) => {
        if (val === undefined || val === null || val === '') return '';
        let v = val;
        if (Array.isArray(v)) {
          if (v.length === 0) return '';
          v = v.join(', ');
        } else if (typeof v === 'object') {
          v = JSON.stringify(v);
        }
        return `<div class="mem-detail-field"><span class="mem-detail-label">${escapeHtml(label)}</span><span class="mem-detail-val">${escapeHtml(String(v))}</span></div>`;
      };
      const lineDate = (label, val) => {
        if (val === undefined || val === null || val === '') return '';
        const formatted = formatInstantLocal(val);
        if (!formatted) return '';
        return `<div class="mem-detail-field"><span class="mem-detail-label">${escapeHtml(label)}</span><span class="mem-detail-val">${escapeHtml(formatted)}</span></div>`;
      };
      let meta = '';
      meta += line('Memory ID', r.memory_id);
      meta += line('Type', r.type);
      meta += line('Scope', r.scope);
      meta += line('Status', r.status);
      if (r.salience != null && r.salience !== '') meta += line('Salience', Number(r.salience).toFixed(4));
      if (r.confidence != null && r.confidence !== '') meta += line('Confidence', Number(r.confidence).toFixed(4));
      meta += lineDate('Created', r.created_at);
      meta += lineDate('Updated', r.updated_at);
      if (r.valid_from) meta += lineDate('Valid from', r.valid_from);
      if (r.valid_to) meta += lineDate('Valid to', r.valid_to);
      if (d.retrieval_frequency != null) meta += line('Retrieval frequency', d.retrieval_frequency);
      if (Array.isArray(r.source_event_ids) && r.source_event_ids.length) meta += line('Source events', r.source_event_ids.join(', '));
      if (r.provenance_tier) meta += line('Provenance tier', r.provenance_tier);
      if (r.claim_class) meta += line('Claim class', r.claim_class);
      if (Array.isArray(r.workflow_steps) && r.workflow_steps.length) meta += line('Workflow steps', r.workflow_steps.join(' → '));

      const body = (r.body || '').trim();
      const bodyHtml = body
        ? `<div class="mem-detail-section"><h4 class="mem-detail-h">Body</h4><div class="mem-detail-body-text">${escapeHtml(body)}</div></div>`
        : '';

      const lin = d.lineage || {};
      const sup = lin.supersedes || r.supersedes;
      const con = lin.conflicts_with || r.conflicts_with;
      let linHtml = '';
      if (Array.isArray(sup) && sup.length) {
        linHtml += `<h4 class="mem-detail-h">Supersedes</h4><ul class="mem-detail-list">` + sup.map((id) => `<li><code>${escapeHtml(String(id))}</code></li>`).join('') + `</ul>`;
      }
      if (Array.isArray(con) && con.length) {
        linHtml += `<h4 class="mem-detail-h">Conflicts with</h4><ul class="mem-detail-list">` + con.map((id) => `<li><code>${escapeHtml(String(id))}</code></li>`).join('') + `</ul>`;
      }
      if (linHtml) linHtml = `<div class="mem-detail-section">${linHtml}</div>`;

      const anns = d.annotations || [];
      let annHtml = '';
      if (anns.length) {
        annHtml = `<div class="mem-detail-section"><h4 class="mem-detail-h">Annotations (${anns.length})</h4><ul class="mem-detail-list">`;
        for (const a of anns.slice(0, 25)) {
          annHtml += `<li><pre>${escapeHtml(jsonStringifyWithLocalDates(a))}</pre></li>`;
        }
        if (anns.length > 25) annHtml += `<li class="muted">… and ${anns.length - 25} more</li>`;
        annHtml += '</ul></div>';
      }

      const revs = d.manual_reviews || [];
      let revHtml = '';
      if (revs.length) {
        revHtml = `<div class="mem-detail-section"><h4 class="mem-detail-h">Manual reviews (${revs.length})</h4><ul class="mem-detail-list">`;
        for (const rr of revs.slice(0, 25)) {
          revHtml += `<li><pre>${escapeHtml(jsonStringifyWithLocalDates(rr))}</pre></li>`;
        }
        if (revs.length > 25) revHtml += `<li class="muted">… and ${revs.length - 25} more</li>`;
        revHtml += '</ul></div>';
      }

      return `<div class="mem-detail-meta">${meta}</div>${bodyHtml}${linHtml}${annHtml}${revHtml}`;
    };
    function memoryDetailToggle(which) {
      const fe = document.getElementById('mem-detail-formatted');
      const re = document.getElementById('mem-detail-raw');
      const bf = document.getElementById('mem-detail-btn-formatted');
      const br = document.getElementById('mem-detail-btn-raw');
      if (!fe || !re) return;
      if (which === 'formatted') {
        fe.style.display = '';
        re.style.display = 'none';
        if (bf) bf.classList.add('mem-view-active');
        if (br) br.classList.remove('mem-view-active');
      } else {
        fe.style.display = 'none';
        re.style.display = '';
        if (br) br.classList.add('mem-view-active');
        if (bf) bf.classList.remove('mem-view-active');
      }
    }

    const retrievalHref = (id) => '/retrievals/' + encodeURIComponent(id) + (location.search || '');
    const runHref = (id) => '/runs/' + encodeURIComponent(id) + (location.search || '');
    const sessionHref = (id) => '/sessions/' + encodeURIComponent(id) + (location.search || '');
    const contextHref = (id) => '/context/' + encodeURIComponent(id) + (location.search || '');
    const labelTip = (label, tip) =>
      tip
        ? `<span class="mem-detail-label" title="${escapeHtml(tip)}">${escapeHtml(label)}</span>`
        : `<span class="mem-detail-label">${escapeHtml(label)}</span>`;
    const formatRetrievalDetailReadable = (d) => {
      const line = (label, val) => {
        if (val === undefined || val === null || val === '') return '';
        let v = val;
        if (Array.isArray(v)) {
          if (v.length === 0) return '';
          v = v.join(', ');
        } else if (typeof v === 'object') {
          v = JSON.stringify(v);
        }
        return `<div class="mem-detail-field">${labelTip(label, '')}<span class="mem-detail-val">${escapeHtml(String(v))}</span></div>`;
      };
      const lineTip = (label, val, tip) => {
        if (val === undefined || val === null || val === '') return '';
        let v = val;
        if (Array.isArray(v)) {
          if (v.length === 0) return '';
          v = v.join(', ');
        } else if (typeof v === 'object') {
          v = JSON.stringify(v);
        }
        return `<div class="mem-detail-field">${labelTip(label, tip)}<span class="mem-detail-val">${escapeHtml(String(v))}</span></div>`;
      };
      const lineDate = (label, val, tip) => {
        if (val === undefined || val === null || val === '') return '';
        const formatted = formatInstantLocal(val);
        if (!formatted) return '';
        return `<div class="mem-detail-field">${labelTip(label, tip || '')}<span class="mem-detail-val">${escapeHtml(formatted)}</span></div>`;
      };
      const formatRetrievalWhyItem = (w) => {
        if (!w || typeof w !== 'object') return '<p class="muted">Invalid entry</p>';
        const mid = w.memory_id;
        const link = mid
          ? `<a href="${memoryHref(String(mid))}"><code>${escapeHtml(String(mid))}</code></a>`
          : '<span class="muted">—</span>';
        const sc = w && w.score != null && !Number.isNaN(Number(w.score)) ? Number(w.score).toFixed(4) : '—';
        const reason = w && w.reason != null ? escapeHtml(String(w.reason)) : '';
        return `<div class="ret-why-card"><div class="row" style="gap:10px;align-items:baseline;flex-wrap:wrap">${link}<span class="muted" style="font-size:12px">Rank score <strong>${escapeHtml(sc)}</strong> (combined retrieval score)</span></div><p style="margin:8px 0 0 0;font-size:13px;line-height:1.55">${reason}</p></div>`;
      };
      const formatRetrievalExplanation = (ex) => {
        if (!ex || typeof ex !== 'object') return '';
        const mid = ex.memory_id;
        const midLink = mid
          ? `<a href="${memoryHref(String(mid))}"><code>${escapeHtml(String(mid))}</code></a>`
          : '';
        const sc = ex.score != null && !Number.isNaN(Number(ex.score)) ? Number(ex.score).toFixed(4) : '—';
        const st = ex.status ? badge(String(ex.status)) : '';
        const tier = ex.provenance_tier
          ? `<span class="muted" style="font-size:11px">provenance: ${escapeHtml(String(ex.provenance_tier))}</span>`
          : '';
        let html = `<div class="ret-ex-card"><div class="row" style="flex-wrap:wrap;gap:8px;align-items:center">${midLink}<span class="muted" style="font-size:12px">Total score <strong>${escapeHtml(sc)}</strong></span>${st}${tier}</div>`;
        if (ex.why_included) {
          html += `<h5>Why included</h5><div class="mem-detail-body-text" style="margin-top:4px">${escapeHtml(String(ex.why_included))}</div>`;
        }
        const me = ex.matched_evidence || {};
        const lex = me.lexical_terms;
        const sem = me.semantic_terms;
        if ((Array.isArray(lex) && lex.length) || (Array.isArray(sem) && sem.length)) {
          html += `<h5>Matched evidence</h5>`;
          if (Array.isArray(lex) && lex.length) {
            html += `<p class="muted" style="font-size:11px;margin:0 0 4px 0">Lexical overlap (terms shared with the query)</p><div>${lex.map((t) => `<span class="ret-tag">${escapeHtml(String(t))}</span>`).join('')}</div>`;
          }
          if (Array.isArray(sem) && sem.length) {
            html += `<p class="muted" style="font-size:11px;margin:8px 0 4px 0">Semantic overlap (embedding-neighborhood terms)</p><div>${sem.map((t) => `<span class="ret-tag">${escapeHtml(String(t))}</span>`).join('')}</div>`;
          }
        }
        const scs = ex.score_contributions;
        if (scs && typeof scs === 'object' && Object.keys(scs).length) {
          html += `<h5>Score contributions</h5><p class="muted" style="font-size:11px;margin:0 0 6px 0">How much each term contributed to the total (lexical, embedding, priors, memory fields, relations).</p><dl class="ret-dl">`;
          for (const [k, v] of Object.entries(scs)) {
            const disp =
              typeof v === 'number' && !Number.isNaN(v)
                ? escapeHtml(String(v))
                : escapeHtml(JSON.stringify(v));
            html += `<dt>${escapeHtml(k)}</dt><dd>${disp}</dd>`;
          }
          html += `</dl>`;
        }
        const rn = ex.relation_notes;
        if (rn != null && rn !== '') {
          html += `<h5>Relation notes</h5>`;
          if (Array.isArray(rn)) {
            html += '<ul class="mem-detail-list">' + rn.map((x) => `<li>${typeof x === 'object' && x !== null ? escapeHtml(jsonStringifyWithLocalDates(x)) : escapeHtml(String(x))}</li>`).join('') + '</ul>';
          } else {
            html += `<div class="mem-detail-body-text">${escapeHtml(String(rn))}</div>`;
          }
        }
        html += `</div>`;
        return html;
      };
      const formatExcludedList = (exc) => {
        if (!Array.isArray(exc) || !exc.length) return '<p class="muted">None recorded.</p>';
        let h = '';
        for (const e of exc) {
          if (e && typeof e === 'object' && e.memory_id) {
            h += `<div class="ret-why-card ret-why-card--error"><div class="row"><a href="${memoryHref(String(e.memory_id))}"><code>${escapeHtml(String(e.memory_id))}</code></a></div>`;
            h += `<p style="margin:6px 0 0 0;font-size:13px;line-height:1.5">${escapeHtml(String(e.reason || ''))}</p></div>`;
          } else {
            h += `<pre class="mem-detail-inline-pre">${escapeHtml(jsonStringifyWithLocalDates(e))}</pre>`;
          }
        }
        return h;
      };
      const formatAssemblyOrder = (ord) => {
        if (!Array.isArray(ord) || !ord.length) return '<p class="muted">None.</p>';
        return `<ol style="margin:0;padding-left:1.2rem;font-size:13px;line-height:1.6">${ord.map((id) => `<li><a href="${memoryHref(String(id))}"><code>${escapeHtml(String(id))}</code></a></li>`).join('')}</ol>`;
      };

      let meta = '';
      meta += line('Retrieval ID', d.id);
      meta += line('Run ID', d.run_id);
      meta += lineDate(
        'Timestamp',
        d.timestamp,
        'When this retrieval audit was written (ISO instant from the store).'
      );
      if (d.summary) meta += line('Summary', d.summary);
      if (d.reranked !== undefined && d.reranked !== null) {
        meta += lineTip(
          'Reranked',
          String(d.reranked),
          'False if the fast path was used; true if ambiguity required a deeper rerank pass.'
        );
      }
      if (d.gated !== undefined && d.gated !== null) {
        meta += lineTip('Gated', String(d.gated), 'Whether retrieval was skipped or short-circuited (e.g. low content).');
      }
      const sel = d.selected_memory_ids || [];
      const lex = d.lexical_only_selected_memory_ids || [];
      meta += lineTip(
        'Selected count',
        String(sel.length),
        'Number of memories in the final ranked result set (top-k) returned to the caller for this query.'
      );
      meta += lineTip(
        'Lexical-only selected',
        String(lex.length),
        'How many memories would have ranked using lexical overlap alone (diagnostic; overlaps with the main selection).'
      );
      const provBits = [];
      if (d.query_source) provBits.push(String(d.query_source));
      if (d.caller_detail) provBits.push(String(d.caller_detail));
      meta += lineTip(
        'Query provenance',
        provBits.length ? provBits.join(' · ') : 'Not recorded',
        'Which pipeline invoked retrieve() for this audit (e.g. cli, prepare_context, evaluation). This does not by itself say whether a human or an agent typed the string — use caller_detail if your integration passes it. Older audits may omit this field.'
      );

      const glossaryHelp = `<details class="mem-detail-details">
        <summary>Glossary — how sections relate</summary>
        <p class="glossary-hint" style="margin-top:8px;margin-bottom:0"><em>Why these memories</em> is the short per-memory rationale and score. <em>Full scorer explanations</em> (collapsed by default) are the detailed breakdown. <em>Excluded &amp; order</em> lists near-misses and context stitch order.</p>
      </details>`;

      const queryHtml = (d.query && String(d.query).trim())
        ? `<div class="mem-detail-section"><h4 class="mem-detail-h">Query text</h4><div class="mem-detail-body-text">${escapeHtml(d.query)}</div></div>`
        : '';

      const why = d.why;
      let whyHtml = '';
      if (Array.isArray(why) && why.length) {
        whyHtml = `<div class="mem-detail-section"><h4 class="mem-detail-h">Why these memories</h4>
          <p class="muted" style="font-size:12px;margin:0 0 10px 0">One row per selected memory: inclusion rationale and the combined rank score at selection time.</p>`;
        for (const w of why.slice(0, 40)) {
          whyHtml += formatRetrievalWhyItem(w);
        }
        if (why.length > 40) whyHtml += `<p class="muted">… and ${why.length - 40} more</p>`;
        whyHtml += '</div>';
      }

      const selIds = sel.slice(0, 100);
      let selHtml = '';
      if (selIds.length) {
        const selOpen = sel.length <= 10 ? 'open' : '';
        selHtml = `<details class="mem-detail-details" ${selOpen}><summary>Selected memory IDs (${sel.length}) — expand for links</summary><ul class="mem-detail-list" style="margin-top:8px">`;
        for (const mid of selIds) {
          selHtml += `<li><a href="${memoryHref(String(mid))}"><code>${escapeHtml(String(mid))}</code></a></li>`;
        }
        if (sel.length > 100) selHtml += `<li class="muted">… and ${sel.length - 100} more</li>`;
        selHtml += '</ul></details>';
      }

      const expl = d.explanations;
      let explHtml = '';
      if (Array.isArray(expl) && expl.length) {
        explHtml = `<details class="mem-detail-details">
          <summary>Full scorer explanations (${expl.length}) — evidence, contributions, relation notes</summary>
          <p class="muted" style="font-size:12px;margin:10px 0 10px 0">Open when you need the full ranker breakdown. Same memories as above, with numeric detail.</p>`;
        for (const ex of expl.slice(0, 25)) {
          explHtml += formatRetrievalExplanation(ex);
        }
        if (expl.length > 25) explHtml += `<p class="muted">… and ${expl.length - 25} more</p>`;
        explHtml += '</details>';
      }

      const exc = d.excluded || [];
      const ord = d.final_context_assembly_order || [];
      const sideHtml = `<details class="mem-detail-details">
        <summary>Excluded (${exc.length}) &amp; context assembly order (${ord.length})</summary>
        <div class="mem-detail-section" style="margin-top:10px"><h4 class="mem-detail-h">Excluded candidates</h4>
        <p class="muted" style="font-size:12px;margin:0 0 10px 0">Considered but not in the top-k (e.g. no match, contested).</p>
        ${formatExcludedList(exc)}
        </div>
        <div class="mem-detail-section"><h4 class="mem-detail-h" title="Order used when assembling context text for the model">Assembly order</h4>
        <p class="muted" style="font-size:12px;margin:0 0 10px 0">Memory IDs in stitch order for the assembled context.</p>
        ${formatAssemblyOrder(ord)}
        </div>
      </details>`;

      return `<div class="mem-detail-meta">${meta}</div>${queryHtml}${whyHtml}${glossaryHelp}${selHtml}${explHtml}${sideHtml}`;
    };

    function retrievalDetailToggle(which) {
      const fe = document.getElementById('ret-detail-formatted');
      const re = document.getElementById('ret-detail-raw');
      const bf = document.getElementById('ret-detail-btn-formatted');
      const br = document.getElementById('ret-detail-btn-raw');
      if (!fe || !re) return;
      if (which === 'formatted') {
        fe.style.display = '';
        re.style.display = 'none';
        if (bf) bf.classList.add('mem-view-active');
        if (br) br.classList.remove('mem-view-active');
      } else {
        fe.style.display = 'none';
        re.style.display = '';
        if (br) br.classList.add('mem-view-active');
        if (bf) bf.classList.remove('mem-view-active');
      }
    }

    const formatRunDetailReadable = (d) => {
      const line = (label, val) => {
        if (val === undefined || val === null || val === '') return '';
        return `<div class="mem-detail-field"><span class="mem-detail-label">${escapeHtml(label)}</span><span class="mem-detail-val">${escapeHtml(
          String(val)
        )}</span></div>`;
      };
      const lineDate = (label, val) => {
        if (val === undefined || val === null || val === '') return '';
        const formatted = formatInstantLocal(val);
        if (!formatted) return '';
        return `<div class="mem-detail-field"><span class="mem-detail-label">${escapeHtml(label)}</span><span class="mem-detail-val">${escapeHtml(
          formatted
        )}</span></div>`;
      };
      let meta = '';
      meta += line('Run ID', d.run_id);
      meta += line('Type', d.type);
      meta += `<div class="mem-detail-field"><span class="mem-detail-label">Status</span><span class="mem-detail-val">${badge(
        String(d.status || 'unknown')
      )}</span></div>`;
      meta += lineDate('Started', d.started_at);
      meta += lineDate('Ended', d.ended_at);
      meta = `<div class="mem-detail-meta">${meta}</div>`;

      const warns = Array.isArray(d.warnings) ? d.warnings : [];
      let whtml = '';
      if (warns.length) {
        whtml = `<div class="mem-detail-section"><h4 class="mem-detail-h">Warnings</h4><ul class="mem-detail-list">${warns
          .map((w) => `<li>${escapeHtml(String(w))}</li>`)
          .join('')}</ul></div>`;
      }

      const phases = Array.isArray(d.phase_traces) ? d.phase_traces : [];
      let phaseHtml = '';
      if (phases.length) {
        phaseHtml = `<details class="mem-detail-details"><summary>Phase timeline (${phases.length})</summary><ol style="margin:8px 0 0 1.1rem;font-size:13px;line-height:1.55">`;
        for (const p of phases) {
          const one =
            typeof p === 'object' && p !== null ? jsonStringifyWithLocalDates(p) : String(p);
          const clipped = one.length > 1200 ? one.slice(0, 1200) + '\\n…' : one;
          phaseHtml += `<li><pre class="mem-detail-inline-pre" style="margin:6px 0">${escapeHtml(clipped)}</pre></li>`;
        }
        phaseHtml += '</ol></details>';
      }

      const ops = Array.isArray(d.operations) ? d.operations : [];
      const opsHtml = `<details class="mem-detail-details"><summary>Op log (${ops.length}) — structured operations</summary><pre class="mem-detail-inline-pre" style="margin-top:8px">${escapeHtml(
        jsonStringifyWithLocalDates(ops)
      )}</pre></details>`;

      const diff = d.diff_text != null ? String(d.diff_text) : '';
      const diffHtml = `<details class="mem-detail-details"><summary>Diff</summary><pre style="margin-top:8px;white-space:pre-wrap;word-break:break-word;font-size:12px;line-height:1.45">${escapeHtml(
        diff || 'No diff artifact.'
      )}</pre></details>`;

      return `${meta}${whtml}${phaseHtml}${opsHtml}${diffHtml}`;
    };

    function runDetailToggle(which) {
      const fe = document.getElementById('run-detail-formatted');
      const re = document.getElementById('run-detail-raw');
      const bf = document.getElementById('run-detail-btn-formatted');
      const br = document.getElementById('run-detail-btn-raw');
      if (!fe || !re) return;
      if (which === 'formatted') {
        fe.style.display = '';
        re.style.display = 'none';
        if (bf) bf.classList.add('mem-view-active');
        if (br) br.classList.remove('mem-view-active');
      } else {
        fe.style.display = 'none';
        re.style.display = '';
        if (br) br.classList.add('mem-view-active');
        if (bf) bf.classList.remove('mem-view-active');
      }
    }

    const sessionLastInstant = (item) => {
      let best = '';
      for (const ev of item.timeline || []) {
        const t = ev && ev.timestamp != null ? String(ev.timestamp) : '';
        if (t && (!best || t > best)) best = t;
      }
      return best;
    };

    const buildSessionTimelineFromDetail = (detail) => {
      const timeline = Array.isArray(detail.timeline) ? detail.timeline : [];
      const sorted = [...timeline].sort((a, b) => {
        const ta = new Date(a.timestamp || 0).getTime();
        const tb = new Date(b.timestamp || 0).getTime();
        return ta - tb;
      });
      let lastDay = '';
      const parts = [];
      const sid = detail.session_id != null ? String(detail.session_id) : '';
      parts.push(
        `<p class="muted" style="margin:0 0 10px 0">Session <code>${escapeHtml(sid)}</code> · ${sorted.length} event(s), chronological.</p>`
      );
      for (const ev of sorted) {
        const rawTs = ev.timestamp != null ? String(ev.timestamp) : '';
        const d = new Date(rawTs || '');
        const hasTime = !Number.isNaN(d.getTime());
        const dayKey = hasTime
          ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
          : '_nodate';
        if (dayKey !== lastDay) {
          lastDay = dayKey;
          const dayLabel = hasTime
            ? d.toLocaleDateString(undefined, {
                weekday: 'short',
                month: 'numeric',
                day: 'numeric',
                year: 'numeric',
              })
            : 'No date';
          parts.push(`<div class="mem-timeline-day">${escapeHtml(dayLabel)}</div>`);
        }
        const timeStr = hasTime
          ? d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          : '—';
        const kind = ev.kind != null ? String(ev.kind) : '';
        const label = ev.label != null ? String(ev.label) : '';
        let linkExtra = '';
        if (kind === 'memory.context.assembled' && ev.object_id) {
          linkExtra = ` · <a href="${contextHref(String(ev.object_id))}">Open context</a>`;
        }
        const payload =
          ev.payload !== undefined && ev.payload !== null
            ? jsonStringifyWithLocalDates(ev.payload)
            : '{}';
        const clipped = payload.length > 8000 ? payload.slice(0, 8000) + '\\n…' : payload;
        parts.push(`<div class="mem-timeline-item">
          <div class="mem-timeline-time"><p>${escapeHtml(timeStr)}</p></div>
          <div class="mem-timeline-rail">
            <div class="mem-timeline-dot"></div>
            <div class="mem-timeline-bar" style="height:44px;background:hsl(${memoryTypeHue(kind)} 45% 40%);"></div>
          </div>
          <div class="mem-timeline-body">
            <div class="t-meta"><span class="muted" style="font-size:11px">${escapeHtml(kind)}</span>${linkExtra}</div>
            <div class="t-title">${escapeHtml(label)}${
              ev.object_id
                ? ` <span class="muted" style="font-size:11px"><code>${escapeHtml(String(ev.object_id))}</code></span>`
                : ''
            }</div>
            <details class="mem-detail-details" style="margin-top:6px"><summary>Payload</summary><pre class="mem-detail-inline-pre" style="margin-top:6px">${escapeHtml(
              clipped
            )}</pre></details>
          </div>
        </div>`);
      }
      return (
        `<div class="table-scroll"><div class="mem-timeline">` +
        (parts.join('') || '<p class="muted">No timeline events.</p>') +
        `</div></div>`
      );
    };

    const formatContextDetailReadable = (data) => {
      let meta = '';
      meta += `<div class="mem-detail-field"><span class="mem-detail-label">Context ID</span><span class="mem-detail-val"><code>${escapeHtml(
        String(data.context_id || '')
      )}</code></span></div>`;
      meta = `<div class="mem-detail-meta">${meta}</div>`;

      const sel = data.selected_memory_ids || [];
      let selHtml = '<div class="mem-detail-section"><h4 class="mem-detail-h">Selected memories</h4>';
      if (!sel.length) selHtml += '<p class="muted">None listed.</p>';
      else {
        selHtml += '<ol style="margin:0;padding-left:1.2rem;line-height:1.6;font-size:13px">';
        for (const mid of sel.slice(0, 200)) {
          selHtml += `<li><a href="${memoryHref(String(mid))}"><code>${escapeHtml(String(mid))}</code></a></li>`;
        }
        selHtml += '</ol>';
        if (sel.length > 200) selHtml += `<p class="muted">… and ${sel.length - 200} more</p>`;
      }
      selHtml += '</div>';

      const om = data.omission_reasons;
      let omitHtml = '<div class="mem-detail-section"><h4 class="mem-detail-h">Omission reasons</h4>';
      if (om && typeof om === 'object' && !Array.isArray(om) && Object.keys(om).length) {
        omitHtml += `<pre class="mem-detail-inline-pre">${escapeHtml(jsonStringifyWithLocalDates(om))}</pre>`;
      } else if (Array.isArray(om) && om.length) {
        omitHtml +=
          '<ul class="mem-detail-list">' +
          om
            .map((x) => {
              const s =
                typeof x === 'object' && x !== null ? jsonStringifyWithLocalDates(x) : String(x);
              return `<li><pre class="mem-detail-inline-pre">${escapeHtml(s)}</pre></li>`;
            })
            .join('') +
          '</ul>';
      } else {
        omitHtml += '<p class="muted">None recorded.</p>';
      }
      omitHtml += '</div>';

      const snap = data.startup_index_snapshot;
      let snapHtml = '<div class="mem-detail-section"><h4 class="mem-detail-h">Startup snapshot</h4>';
      if (snap && typeof snap === 'object' && Object.keys(snap).length) {
        snapHtml += `<details class="mem-detail-details"><summary>JSON (dates localized)</summary><pre class="mem-detail-inline-pre" style="margin-top:8px">${escapeHtml(
          jsonStringifyWithLocalDates(snap)
        )}</pre></details>`;
      } else {
        snapHtml += '<p class="muted">Not captured.</p>';
      }
      snapHtml += '</div>';

      return `${meta}${selHtml}${omitHtml}${snapHtml}`;
    };

    function contextDetailToggle(which) {
      const fe = document.getElementById('ctx-detail-formatted');
      const re = document.getElementById('ctx-detail-raw');
      const bf = document.getElementById('ctx-detail-btn-formatted');
      const br = document.getElementById('ctx-detail-btn-raw');
      if (!fe || !re) return;
      if (which === 'formatted') {
        fe.style.display = '';
        re.style.display = 'none';
        if (bf) bf.classList.add('mem-view-active');
        if (br) br.classList.remove('mem-view-active');
      } else {
        fe.style.display = 'none';
        re.style.display = '';
        if (br) br.classList.add('mem-view-active');
        if (bf) bf.classList.remove('mem-view-active');
      }
    }

    async function renderOverview() {
      const data = await fetchJson('/api/overview');
      const contestedN = Number(data.contested_memories) || 0;
      const memTotal = Number(data.memory_counts && data.memory_counts.total) || 0;
      const contestedCallout =
        contestedN > 0
          ? `<p class="glossary-hint" style="margin-top:12px;margin-bottom:0"><strong>${contestedN}</strong> contested memory record(s) may need review before agents should rely on them. <a href="/memories?status=contested">Open Memories (contested)</a> to triage.</p>`
          : '';
      const emptyNext =
        memTotal === 0
          ? `<div class="od-empty-nextsteps glossary-hint" role="status"><strong>No memories indexed yet.</strong> From your workspace directory (see project README):<pre class="mem-detail-inline-pre">opendream observe index --workspace "$PWD"
opendream observe serve --workspace "$PWD" --port 8000</pre>Open <code>/overview</code> on the same machine after capture. To consolidate durable memory from events, run <code>opendream maintain --workspace "$PWD"</code>.</div>`
          : '';
      const parts = [];
      if (memTotal === 0) parts.push(panel('Get started', emptyNext, true));
      let firstStepsDismissed = false;
      try {
        firstStepsDismissed = localStorage.getItem('opendream-first-steps-dismissed') === '1';
      } catch (_fs0) {}
      const firstStepsOpen = memTotal > 0 ? '' : ' open';
      const reviewsStep =
        contestedN > 0
          ? `<li><a href="/reviews">Review queue</a> — triage contested or flagged items.</li>`
          : `<li>Optional: open <a href="/reviews">Reviews</a> when the queue has items.</li>`;
      if (!firstStepsDismissed) {
        parts.push(
          panel(
            'First steps',
            `<div id="od-first-steps-panel">
            <details class="mem-detail-details od-first-steps" id="od-first-steps"${firstStepsOpen}>
            <summary>What to do in the first few minutes</summary>
            <ol class="glossary-hint" style="margin:10px 0 0 1rem;line-height:1.65;padding:0">
              <li>Confirm <a href="/overview">Overview</a> store health and memory counts.</li>
              <li>Browse <a href="/memories">Memories</a> and open a record to inspect provenance.</li>
              <li>Check <a href="/runs">Runs</a> for consolidation and <a href="/graph">Graph</a> for relationships.</li>
              ${reviewsStep}
            </ol>
            <p class="glossary-hint" style="margin:10px 0 0 0">CLI: <code>opendream observe index --workspace "$PWD"</code> then <code>opendream maintain --workspace "$PWD"</code>. See project README for capture setup.</p>
          </details>
          <p class="row" style="margin:12px 0 0 0;align-items:center;gap:10px;flex-wrap:wrap">
            <button type="button" class="icon-btn" onclick="odDismissFirstSteps()" aria-label="Hide first steps from Overview" title="Hides this panel until you clear site data for this origin (localStorage key opendream-first-steps-dismissed)">Hide first steps</button>
            <span class="muted" style="font-size:11px;line-height:1.45">To show again: delete <code>opendream-first-steps-dismissed</code> in this site’s storage (Application → Local Storage).</span>
          </p>
          </div>`,
            true,
          ),
        );
      }
      const retTotal = Number(data.retrievals && data.retrievals.total) || 0;
      const retSucc = Number(data.retrievals && data.retrievals.successful) || 0;
      const hitPct = retTotal ? Math.round((retSucc / retTotal) * 100) : 0;
      const lastRun = data.last_consolidation_run || (Array.isArray(data.recent_runs) && data.recent_runs[0]) || null;
      const lastRunId = lastRun && lastRun.run_id ? String(lastRun.run_id) : '';
      const lastRunLabel = lastRunId ? odTruncateMiddle(lastRunId, 14) : '—';
      const lastRunHref = lastRunId ? '/runs/' + encodeURIComponent(lastRunId) : '/runs';
      const sig = data.signal_coverage || {};
      const evTotal = (Number(sig.transcript_events) || 0) + (Number(sig.explicit_events) || 0);
      const contestedClass = contestedN > 0 ? ' od-strip-card--warn' : '';
      parts.push(
        '<div class="full od-overview-strip" role="region" aria-label="At a glance">' +
          `<a class="od-strip-card" href="/memories"><span class="od-strip-value">${memTotal}</span><span class="od-strip-label">Memories</span></a>` +
          `<a class="od-strip-card${contestedClass}" href="/memories?status=contested"><span class="od-strip-value">${contestedN}</span><span class="od-strip-label">Contested</span></a>` +
          `<a class="od-strip-card" href="${lastRunHref}"><span class="od-strip-value">${escapeHtml(lastRunLabel)}</span><span class="od-strip-label">Latest run</span></a>` +
          `<a class="od-strip-card" href="/retrievals"><span class="od-strip-value">${hitPct}%</span><span class="od-strip-label">Retrieval hit</span></a>` +
          `<a class="od-strip-card" href="/sessions"><span class="od-strip-value">${evTotal}</span><span class="od-strip-label">Capture events</span></a>` +
          '<a class="od-strip-card" href="/graph"><span class="od-strip-value" style="font-size:0.95rem;font-weight:600">Open</span><span class="od-strip-label">Graph</span></a>' +
          '</div>',
      );
      parts.push(
        panel('Store Health', `
          <div class="metric"><div class="label">State</div><div class="value">${data.store_health.lock.present ? 'Locked' : 'Ready'}</div></div>
          <div class="metric"><div class="label">Memory Root</div><div class="value" style="font-size:16px">${data.store_health.memory_root}</div></div>
          <div class="metric"><div class="label">Contested</div><div class="value">${data.contested_memories}</div></div>
          ${contestedCallout}
        `),
        panel('Counts', `
          <div class="metric"><div class="label">Total Memories</div><div class="value">${data.memory_counts.total}</div></div>
          <div class="metric"><div class="label">Startup Entries</div><div class="value">${data.startup_index.entries}</div></div>
          <div class="metric"><div class="label">Retrieval Hit Rate</div><div class="value">${data.retrievals.total ? Math.round((data.retrievals.successful / data.retrievals.total) * 100) + '%' : '0%'}</div></div>
          <p class="muted" style="margin-top:12px;margin-bottom:0;font-size:12px">Read API: <code>${location.origin}/api/overview</code>
            <span class="od-api-clip-row">
            <button type="button" class="icon-btn od-api-copy-btn" data-api-method="GET" data-api-path="/api/overview" onclick="odCopyApiUrl(this)" aria-label="Copy overview API request" title="Copy API URL"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
            <button type="button" class="icon-btn od-api-copy-btn" data-api-method="GET" data-api-path="/api/overview" onclick="odCopyApiCurl(this)" aria-label="Copy as curl" title="Copy curl"><span style="font-size:10px;font-weight:600">curl</span></button>
            <button type="button" class="icon-btn od-api-copy-btn" data-api-method="GET" data-api-path="/api/overview" onclick="odCopyApiFetch(this)" aria-label="Copy as fetch" title="Copy fetch"><span style="font-size:10px;font-weight:600">fetch</span></button>
            </span>
          </p>
          <p class="muted" style="margin-top:10px;margin-bottom:0;font-size:12px;line-height:1.55">Machine-readable workspace contract (schemas in repo): <code>opendream contract export --workspace &lt;path&gt; --format json</code>. See <code>AGENTS.md</code> in the OpenDream repository for <code>cli_output_version</code> and contract fields.</p>
        `),
        panel('Recent Runs', `<table><caption class="sr-only">Recent consolidation runs</caption><thead><tr><th scope="col">ID</th><th scope="col">Status</th><th scope="col">Type</th></tr></thead><tbody>${data.recent_runs.map(run => `<tr><td><a href="/runs/${run.run_id}">${run.run_id}</a></td><td>${run.status || ''}</td><td>${run.type}</td></tr>`).join('')}</tbody></table>`, true),
        panel('Recent Sessions', `<p class="muted" style="margin:0 0 10px 0">Session timelines and context IDs: see <a href="/sessions">Sessions</a> and <a href="/context">Context</a>.</p><table><caption class="sr-only">Recent capture sessions</caption><thead><tr><th scope="col">Session</th><th scope="col">Events</th><th scope="col">Ended</th></tr></thead><tbody>${data.recent_sessions.map(session => `<tr><td><a href="/sessions/${session.session_id}">${session.session_id}</a></td><td>${session.event_count}</td><td>${session.ended_at ? escapeHtml(formatInstantLocal(session.ended_at)) : ''}</td></tr>`).join('')}</tbody></table>`, true),
        panel('Fidelity Diagnostics', `<div class="split"><div>${pretty(data.signal_coverage)}</div><div>${pretty(data.activation_diagnostics)}</div></div>`, true),
      );
      odSetMainHtml(parts.join(''));
    }

    async function renderMemories(memoryId=null) {
      const params = new URLSearchParams(location.search);
      const q = (k, d='') => params.get(k) || d;
      const search = q('search');
      const type = q('type');
      const scope = q('scope');
      const status = q('status');
      const sort = q('sort', 'updated_at');
      const sortDir = q('sort_dir');
      const offset = q('offset', '0');
      const limit = q('limit', '50');
      const salienceMin = q('salience_min');
      const salienceMax = q('salience_max');
      const confidenceMin = q('confidence_min');
      const confidenceMax = q('confidence_max');
      const updatedAfter = q('updated_after');
      const updatedBefore = q('updated_before');
      const createdAfter = q('created_after');
      const createdBefore = q('created_before');
      const view = q('view', '');
      const isTimeline = view !== 'table';
      const apiParams = {};
      if (search) apiParams.search = search;
      if (type) apiParams.type = type;
      if (scope) apiParams.scope = scope;
      if (status) apiParams.status = status;
      apiParams.sort = sort;
      if (sortDir) apiParams.sort_dir = sortDir;
      apiParams.offset = offset;
      apiParams.limit = limit;
      if (salienceMin) apiParams.salience_min = salienceMin;
      if (salienceMax) apiParams.salience_max = salienceMax;
      if (confidenceMin) apiParams.confidence_min = confidenceMin;
      if (confidenceMax) apiParams.confidence_max = confidenceMax;
      if (updatedAfter) apiParams.updated_after = updatedAfter;
      if (updatedBefore) apiParams.updated_before = updatedBefore;
      if (createdAfter) apiParams.created_after = createdAfter;
      if (createdBefore) apiParams.created_before = createdBefore;
      const data = await fetchJson('/api/memories?' + qs(apiParams));
      const total = data.total;
      const off = parseInt(offset, 10) || 0;
      const lim = parseInt(limit, 10) || 50;
      const startIdx = total === 0 ? 0 : off + 1;
      const endIdx = off + data.items.length;
      const prevOff = Math.max(0, off - lim);
      const nextOff = off + lim;
      const hasPrev = off > 0;
      const hasNext = nextOff < total;
      const optSel = (val, cur) => (val === cur ? 'selected' : '');
      const memTypes = ['semantic_fact','procedural_workflow','user_preference','project_decision','environment_requirement','anti_pattern','pending_item','contested_fact','superseded_record'];
      const memScopes = ['user','project','agent','workspace','global'];
      const memStatuses = ['active','contested','superseded','quarantined','deleted'];
      const sortFields = [
        ['updated_at','Updated'],
        ['created_at','Created'],
        ['title','Title'],
        ['memory_id','ID'],
        ['type','Type'],
        ['scope','Scope'],
        ['status','Status'],
        ['salience','Salience'],
        ['confidence','Confidence'],
        ['retrieval_frequency','Retrievals'],
      ];
      const typeOpts = '<option value="">any type</option>' + memTypes.map(t => `<option value="${t}" ${optSel(t, type)}>${t}</option>`).join('');
      const scopeOpts = '<option value="">any scope</option>' + memScopes.map(s => `<option value="${s}" ${optSel(s, scope)}">${s}</option>`).join('');
      const statusOpts = '<option value="">any status</option>' + memStatuses.map(s => `<option value="${s}" ${optSel(s, status)}">${s}</option>`).join('');
      const sortOpts = sortFields.map(([v, lab]) => `<option value="${v}" ${optSel(v, sort)}>${lab}</option>`).join('');
      const dirAsc = sortDir === 'asc' ? 'selected' : '';
      const dirDesc = sortDir === 'desc' ? 'selected' : '';
      const dirDefault = !sortDir ? 'selected' : '';
      const lim25 = optSel('25', String(lim));
      const lim50 = optSel('50', String(lim));
      const lim100 = optSel('100', String(lim));
      let detailHtml = '<p class="muted">Select a memory record.</p>';
      if (memoryId) {
        const detail = await fetchJson('/api/memories/' + encodeURIComponent(memoryId));
        const readable = formatMemoryDetailReadable(detail);
        detailHtml = `
          <div class="row"><strong>${escapeHtml(detail.title || '')}</strong>${badge(detail.status)}</div>
          <p class="row" style="gap:10px;flex-wrap:wrap;margin:6px 0 0 0"><a href="/graph?focus=${encodeURIComponent(memoryId)}">View in provenance graph</a></p>
          <p>${escapeHtml(detail.summary || '')}</p>
          <p class="muted">Sources: ${escapeHtml((detail.source_event_ids || []).join(', ') || 'none')}</p>
          <div class="mem-view-toggle mem-detail-toggle icon-toolbar" role="group" aria-label="Memory detail format">
            <button type="button" id="mem-detail-btn-formatted" class="icon-btn mem-view-active" onclick="memoryDetailToggle('formatted')" aria-label="Formatted detail" title="Formatted">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
            <button type="button" id="mem-detail-btn-raw" class="icon-btn" onclick="memoryDetailToggle('raw')" aria-label="Raw JSON" title="Raw JSON">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            </button>
          </div>
          <div id="mem-detail-formatted" class="mem-detail-body">${readable}</div>
          <div id="mem-detail-raw" class="mem-detail-body" style="display:none">
            <div class="split">
              <div>${pretty(detail.raw_json)}</div>
              <div>${pretty({lineage: detail.lineage, annotations: detail.annotations, manual_reviews: detail.manual_reviews})}</div>
            </div>
          </div>
          <p class="muted" style="margin-top:10px;font-size:12px">Read API: <code>${location.origin}/api/memories/${encodeURIComponent(memoryId)}</code>
            <span class="od-api-clip-row">
            <button type="button" class="icon-btn od-api-copy-btn" data-api-method="GET" data-api-path="/api/memories/${encodeURIComponent(memoryId)}" onclick="odCopyApiUrl(this)" aria-label="Copy memory API URL" title="Copy API URL"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
            <button type="button" class="icon-btn od-api-copy-btn" data-api-method="GET" data-api-path="/api/memories/${encodeURIComponent(memoryId)}" onclick="odCopyApiCurl(this)" aria-label="Copy memory API as curl" title="Copy curl"><span style="font-size:10px;font-weight:600">curl</span></button>
            <button type="button" class="icon-btn od-api-copy-btn" data-api-method="GET" data-api-path="/api/memories/${encodeURIComponent(memoryId)}" onclick="odCopyApiFetch(this)" aria-label="Copy memory API as fetch" title="Copy fetch"><span style="font-size:10px;font-weight:600">fetch</span></button>
            </span>
          </p>`;
      }
      const rows = data.items.map(item => {
        const sal = item.salience != null && item.salience !== '' ? Number(item.salience).toFixed(2) : '—';
        const conf = item.confidence != null && item.confidence !== '' ? Number(item.confidence).toFixed(2) : '—';
        const rf = item.retrieval_frequency != null ? String(item.retrieval_frequency) : '0';
        return `<tr>
          <td><a href="${memoryHref(item.memory_id)}">${escapeHtml(item.title || '')}</a></td>
          <td>${badge(item.status)}</td>
          <td>${escapeHtml(item.type || '')}</td>
          <td>${escapeHtml(item.scope || '')}</td>
          <td class="num">${escapeHtml(sal)}</td>
          <td class="num">${escapeHtml(conf)}</td>
          <td class="num">${escapeHtml(rf)}</td>
          <td>${escapeHtml(item.updated_at || '')}</td>
        </tr>`;
      }).join('');
      const bcMem =
        memoryId
          ? odBreadcrumbHtml([
              { href: '/memories', label: 'Memories' },
              { href: '', label: odTruncateMiddle(memoryId, 42) },
            ])
          : '';
      odSetMainHtml(
        bcMem +
        [
        panel('Memory Explorer', `
          <div class="od-toolbar-sticky">
          <form class="memories-toolbar" id="memories-filter-form" onsubmit="event.preventDefault(); const f=this; const p = memoryExplorerParams({
            search: f.search.value,
            type: f.type.value,
            scope: f.scope.value,
            status: f.status.value,
            sort: f.sort.value,
            sort_dir: f.sort_dir.value,
            limit: f.limit.value,
            salience_min: f.salience_min.value,
            salience_max: f.salience_max.value,
            confidence_min: f.confidence_min.value,
            confidence_max: f.confidence_max.value,
            updated_after: datetimeLocalToIsoUtc(f.updated_after.value),
            updated_before: datetimeLocalToIsoUtc(f.updated_before.value),
            created_after: datetimeLocalToIsoUtc(f.created_after.value),
            created_before: datetimeLocalToIsoUtc(f.created_before.value),
            offset: '0',
            view: (f.mem_view && f.mem_view.value) ? f.mem_view.value : ''
          }); odSaveScrollAndGoQueryString(p.toString());">
            <input type="hidden" name="mem_view" value="${view === 'table' ? 'table' : ''}">
            <div class="row" style="align-items:flex-end">
              <label style="display:flex;flex-direction:column;gap:4px;min-width:180px;flex:1"><span class="muted" style="font-size:11px">Search</span>
                <input name="search" type="search" placeholder="title, summary, body, id" value="${escapeHtml(search)}"></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Type</span>
                <select name="type">${typeOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Scope</span>
                <select name="scope">${scopeOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Status</span>
                <select name="status">${statusOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Sort</span>
                <select name="sort">${sortOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Dir</span>
                <select name="sort_dir">
                  <option value="" ${dirDefault}>default</option>
                  <option value="asc" ${dirAsc}>asc</option>
                  <option value="desc" ${dirDesc}>desc</option>
                </select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Page size</span>
                <select name="limit">
                  <option value="25" ${lim25}>25</option>
                  <option value="50" ${lim50}>50</option>
                  <option value="100" ${lim100}>100</option>
                </select></label>
              <button type="submit" class="icon-btn" aria-label="Apply filters" title="Apply filters">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
            </div>
            <div class="row" style="align-items:center;margin-top:4px">
              <span class="muted" style="font-size:11px">Updated time window:</span>
              <button type="button" class="icon-btn" onclick="applyMemoryTimePreset(24)" aria-label="Last 24 hours" title="Last 24 hours">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg><span class="sr-only">24h</span>
              </button>
              <button type="button" class="icon-btn" onclick="applyMemoryTimePreset(168)" aria-label="Last 7 days" title="Last 7 days">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg><span class="sr-only">7d</span>
              </button>
            </div>
            <details>
              <summary>Advanced filters (salience, confidence, time)</summary>
              <p class="muted" style="font-size:12px;margin:8px 0 0 0">Date and time pickers use <strong>your browser timezone</strong>. Shared links still store UTC (<code>…Z</code>) in the URL so filters stay stable.</p>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Salience min</span>
                  <input name="salience_min" type="number" step="0.01" min="0" max="1" placeholder="0–1" value="${escapeHtml(salienceMin)}"></label>
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Salience max</span>
                  <input name="salience_max" type="number" step="0.01" min="0" max="1" placeholder="0–1" value="${escapeHtml(salienceMax)}"></label>
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Confidence min</span>
                  <input name="confidence_min" type="number" step="0.01" min="0" max="1" placeholder="0–1" value="${escapeHtml(confidenceMin)}"></label>
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Confidence max</span>
                  <input name="confidence_max" type="number" step="0.01" min="0" max="1" placeholder="0–1" value="${escapeHtml(confidenceMax)}"></label>
              </div>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Updated on or after</span>
                  <input name="updated_after" type="datetime-local" step="60" title="Local date and time; applied as UTC instant to the server filter" value="${escapeHtml(isoUtcToDatetimeLocal(updatedAfter))}"></label>
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Updated on or before</span>
                  <input name="updated_before" type="datetime-local" step="60" title="Local date and time; applied as UTC instant to the server filter" value="${escapeHtml(isoUtcToDatetimeLocal(updatedBefore))}"></label>
              </div>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Created on or after</span>
                  <input name="created_after" type="datetime-local" step="60" title="Local date and time; applied as UTC instant to the server filter" value="${escapeHtml(isoUtcToDatetimeLocal(createdAfter))}"></label>
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Created on or before</span>
                  <input name="created_before" type="datetime-local" step="60" title="Local date and time; applied as UTC instant to the server filter" value="${escapeHtml(isoUtcToDatetimeLocal(createdBefore))}"></label>
              </div>
            </details>
          </form></div>
          ${!memoryId ? `<div class="row od-export-row" style="gap:8px;align-items:center;margin:6px 0 4px 0;flex-wrap:wrap">
            <span class="muted" style="font-size:11px">Export this page:</span>
            <button type="button" class="icon-btn" onclick="void odCopyCurrentViewUrl()" title="Copy URL including filters" aria-label="Copy link to this view"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
            <button type="button" class="icon-btn" onclick="void odExportCurrentList('memories','json')" title="Download JSON" aria-label="Export memories as JSON"><span style="font-size:10px;font-weight:700">JSON</span></button>
            <button type="button" class="icon-btn" onclick="void odExportCurrentList('memories','csv')" title="Download CSV" aria-label="Export memories as CSV"><span style="font-size:10px;font-weight:700">CSV</span></button>
          </div>` : `<div class="row od-export-row" style="gap:8px;align-items:center;margin:6px 0 4px 0;flex-wrap:wrap">
            <span class="muted" style="font-size:11px">Export this memory:</span>
            <button type="button" class="icon-btn" onclick="void odCopyCurrentViewUrl()" title="Copy URL to this memory" aria-label="Copy link to this memory"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
            <button type="button" class="icon-btn" onclick="void odExportCurrentList('memories','json')" title="Download JSON" aria-label="Export memory as JSON"><span style="font-size:10px;font-weight:700">JSON</span></button>
          </div>`}
          ${total === 0 ? '<div class="od-empty-nextsteps glossary-hint" role="status">No rows match your filters, or the store is empty. New workspace: <code>opendream observe index --workspace "$PWD"</code>, capture events, then <code>opendream maintain --workspace "$PWD"</code>. See <a href="/overview">Overview</a>.</div>' : ''}
          <div class="row" style="align-items:center;justify-content:space-between;flex-wrap:wrap;margin:10px 0 8px 0;gap:10px">
            <p class="muted" style="margin:0">Showing <strong>${startIdx}</strong>–<strong>${endIdx}</strong> of <strong>${total}</strong></p>
            <div class="mem-view-toggle icon-toolbar" role="group" aria-label="Result layout">
              <button type="button" class="icon-btn ${view === 'table' ? 'mem-view-active' : ''}" title="Table layout" aria-label="Table layout"
                onclick="(() => { const p = memoryExplorerParams({ view: 'table' }); odSaveScrollAndGoQueryString(p.toString()); })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
              </button>
              <button type="button" class="icon-btn ${isTimeline ? 'mem-view-active' : ''}" title="Timeline layout" aria-label="Timeline layout"
                onclick="(() => { const p = memoryExplorerParams({ view: '' }); odSaveScrollAndGoQueryString(p.toString()); })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
              </button>
            </div>
          </div>
          ${isTimeline ? `<p class="muted" style="font-size:12px;margin:0 0 10px 0">Timeline uses the same filters and pagination as the table. Items on this page are shown <strong>newest first</strong> and grouped by local day (by <code>updated_at</code>).</p>` : ''}
          ${isTimeline
            ? `<div class="table-scroll"><div class="mem-timeline">${buildMemoryTimelineHtml(data.items, search)}</div></div>`
            : `<div class="table-scroll">
            <table class="memories-table"><caption class="sr-only">Memory records matching current filters</caption><thead><tr>
              <th scope="col">Title</th><th scope="col">Status</th><th scope="col">Type</th><th scope="col">Scope</th>
              <th class="num" scope="col">Salience</th><th class="num" scope="col">Confidence</th><th class="num" scope="col">Retr.</th><th scope="col">Updated</th>
            </tr></thead><tbody>
              ${rows || '<tr><td colspan="8" class="muted">No memories match.</td></tr>'}
            </tbody></table>
          </div>`}
          <div class="pager">
            <button type="button" class="icon-btn" ${hasPrev ? '' : 'disabled'} aria-label="Previous page" title="Previous"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${prevOff}) }); odSaveScrollAndGoQueryString(p.toString()); })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <button type="button" class="icon-btn" ${hasNext ? '' : 'disabled'} aria-label="Next page" title="Next"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${nextOff}) }); odSaveScrollAndGoQueryString(p.toString()); })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
            <span class="muted">offset ${off}, limit ${lim}</span>
          </div>
        `, false, 'mem-explorer'),
        panel('Memory Detail', detailHtml, false, 'mem-detail'),
      ].join(''));
      var pMemFocus = new URLSearchParams(location.search);
      if (pMemFocus.get('focus_search') === '1') {
        requestAnimationFrame(function () {
          var inpFs = document.querySelector('#memories-filter-form input[name=search]');
          if (inpFs) {
            inpFs.focus();
            try {
              inpFs.select();
            } catch (eFs) {}
          }
          pMemFocus.delete('focus_search');
          var qsFs = pMemFocus.toString();
          try {
            history.replaceState({}, '', location.pathname + (qsFs ? '?' + qsFs : ''));
          } catch (eFs2) {}
        });
      }
    }

    async function renderRuns(runId=null) {
      const params = new URLSearchParams(location.search);
      const q = (k, d='') => params.get(k) || d;
      const search = q('search');
      const sort = q('sort', 'ended_at');
      const sortDir = q('sort_dir');
      const offset = q('offset', '0');
      const limit = q('limit', '50');
      const endedAfter = q('ended_after');
      const endedBefore = q('ended_before');
      const view = q('view', '');
      const isTimeline = view !== 'table';
      const apiParams = {};
      if (search) apiParams.search = search;
      apiParams.sort = sort;
      if (sortDir) apiParams.sort_dir = sortDir;
      apiParams.offset = offset;
      apiParams.limit = limit;
      if (endedAfter) apiParams.ended_after = endedAfter;
      if (endedBefore) apiParams.ended_before = endedBefore;
      const data = await fetchJson('/api/runs?' + qs(apiParams));
      const total = data.total;
      const off = parseInt(offset, 10) || 0;
      const lim = parseInt(limit, 10) || 50;
      const startIdx = total === 0 ? 0 : off + 1;
      const endIdx = off + data.items.length;
      const prevOff = Math.max(0, off - lim);
      const nextOff = off + lim;
      const hasPrev = off > 0;
      const hasNext = nextOff < total;
      const optSel = (val, cur) => (val === cur ? 'selected' : '');
      const sortFields = [
        ['ended_at', 'Ended'],
        ['started_at', 'Started'],
        ['run_id', 'Run ID'],
        ['type', 'Type'],
        ['status', 'Status'],
      ];
      const sortOpts = sortFields.map(([v, lab]) => `<option value="${v}" ${optSel(v, sort)}>${lab}</option>`).join('');
      const dirAsc = sortDir === 'asc' ? 'selected' : '';
      const dirDesc = sortDir === 'desc' ? 'selected' : '';
      const dirDefault = !sortDir ? 'selected' : '';
      const lim25 = optSel('25', String(lim));
      const lim50 = optSel('50', String(lim));
      const lim100 = optSel('100', String(lim));
      let detailHtml = '<p class="muted">Select a run.</p>';
      if (runId) {
        const detail = await fetchJson('/api/runs/' + encodeURIComponent(runId));
        const readable = formatRunDetailReadable(detail);
        detailHtml = `
          <div class="row" style="flex-wrap:wrap;gap:8px;align-items:center">
            <strong title="Run id">${escapeHtml(String(detail.run_id || ''))}</strong>
            <span class="muted">${escapeHtml(String(detail.type || ''))}</span>
            ${badge(String(detail.status || 'unknown'))}
          </div>
          <div class="mem-view-toggle mem-detail-toggle icon-toolbar" role="group" aria-label="Run detail format">
            <button type="button" id="run-detail-btn-formatted" class="icon-btn mem-view-active" onclick="runDetailToggle('formatted')" aria-label="Formatted detail" title="Formatted">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
            <button type="button" id="run-detail-btn-raw" class="icon-btn" onclick="runDetailToggle('raw')" aria-label="Raw JSON" title="Raw JSON">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            </button>
          </div>
          <div id="run-detail-formatted" class="mem-detail-body">${readable}</div>
          <div id="run-detail-raw" class="mem-detail-body" style="display:none">${pretty(detail)}</div>`;
      }
      const rows = data.items
        .map((run) => {
          const t = formatInstantLocal(runEffectiveInstant(run));
          const rid = String(run.run_id || '');
          return `<tr>
          <td title="Effective sort time (ended_at, else started_at)">${escapeHtml(t || '—')}</td>
          <td title="${escapeHtml(rid)}">${escapeHtml(String(run.type || ''))}</td>
          <td>${badge(String(run.status || 'unknown'))}</td>
          <td class="muted" style="font-size:12px"><a href="${runHref(rid)}" title="${escapeHtml(rid)}">${escapeHtml(rid)}</a></td>
        </tr>`;
        })
        .join('');
      const bcRun =
        runId
          ? odBreadcrumbHtml([
              { href: '/runs', label: 'Runs' },
              { href: '', label: odTruncateMiddle(runId, 42) },
            ])
          : '';
      odSetMainHtml(
        bcRun +
        [
        panel(
          'Runs',
          `
          <div class="od-toolbar-sticky">
          <form class="memories-toolbar" id="runs-filter-form" onsubmit="event.preventDefault(); const f=this; const p = memoryExplorerParams({
            search: f.search.value,
            sort: f.sort.value,
            sort_dir: f.sort_dir.value,
            limit: f.limit.value,
            ended_after: datetimeLocalToIsoUtc(f.ended_after.value),
            ended_before: datetimeLocalToIsoUtc(f.ended_before.value),
            offset: '0',
            view: f.list_view ? f.list_view.value : ''
          }); odSaveScrollAndGoQueryString(p.toString());">
            <input type="hidden" name="list_view" value="${view === 'table' ? 'table' : ''}">
            <div class="row" style="align-items:flex-end">
              <label style="display:flex;flex-direction:column;gap:4px;min-width:180px;flex:1"><span class="muted" style="font-size:11px">Search</span>
                <input name="search" type="search" placeholder="run id, type, status" value="${escapeHtml(search)}"></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Sort</span>
                <select name="sort">${sortOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Dir</span>
                <select name="sort_dir">
                  <option value="" ${dirDefault}>default</option>
                  <option value="asc" ${dirAsc}>asc</option>
                  <option value="desc" ${dirDesc}>desc</option>
                </select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Page size</span>
                <select name="limit">
                  <option value="25" ${lim25}>25</option>
                  <option value="50" ${lim50}>50</option>
                  <option value="100" ${lim100}>100</option>
                </select></label>
              <button type="submit" class="icon-btn" aria-label="Apply filters" title="Apply filters">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
            </div>
            <div class="row" style="align-items:center;margin-top:4px">
              <span class="muted" style="font-size:11px">Run time window (ended_at, else started_at):</span>
              <button type="button" class="icon-btn" onclick="applyRunTimePreset(24)" aria-label="Last 24 hours" title="Last 24 hours">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg><span class="sr-only">24h</span>
              </button>
              <button type="button" class="icon-btn" onclick="applyRunTimePreset(168)" aria-label="Last 7 days" title="Last 7 days">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg><span class="sr-only">7d</span>
              </button>
            </div>
            <details>
              <summary>Advanced filters (time bounds)</summary>
              <p class="muted" style="font-size:12px;margin:8px 0 0 0">Pickers use <strong>your local timezone</strong>; the URL stores UTC instants. Bounds apply to <code>ended_at</code> when set, otherwise <code>started_at</code>.</p>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Ended / effective on or after</span>
                  <input name="ended_after" type="datetime-local" step="60" title="Local time; filter is UTC instant" value="${escapeHtml(isoUtcToDatetimeLocal(endedAfter))}"></label>
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">Ended / effective on or before</span>
                  <input name="ended_before" type="datetime-local" step="60" title="Local time; filter is UTC instant" value="${escapeHtml(isoUtcToDatetimeLocal(endedBefore))}"></label>
              </div>
            </details>
          </form></div>
          ${!runId ? `<div class="row od-export-row" style="gap:8px;align-items:center;margin:6px 0 4px 0;flex-wrap:wrap">
            <span class="muted" style="font-size:11px">Export this page:</span>
            <button type="button" class="icon-btn" onclick="void odCopyCurrentViewUrl()" title="Copy URL including filters" aria-label="Copy link to this view"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
            <button type="button" class="icon-btn" onclick="void odExportCurrentList('runs','json')" title="Download JSON" aria-label="Export runs as JSON"><span style="font-size:10px;font-weight:700">JSON</span></button>
            <button type="button" class="icon-btn" onclick="void odExportCurrentList('runs','csv')" title="Download CSV" aria-label="Export runs as CSV"><span style="font-size:10px;font-weight:700">CSV</span></button>
          </div>` : `<div class="row od-export-row" style="gap:8px;align-items:center;margin:6px 0 4px 0;flex-wrap:wrap">
            <span class="muted" style="font-size:11px">Export this run:</span>
            <button type="button" class="icon-btn" onclick="void odCopyCurrentViewUrl()" title="Copy URL to this run" aria-label="Copy link to this run"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
            <button type="button" class="icon-btn" onclick="void odExportCurrentList('runs','json')" title="Download JSON" aria-label="Export run as JSON"><span style="font-size:10px;font-weight:700">JSON</span></button>
          </div>`}
          ${total === 0 ? '<div class="od-empty-nextsteps glossary-hint" role="status">No runs indexed yet, or none match your filters. Run <code>opendream observe index --workspace "$PWD"</code> and refresh.</div>' : ''}
          <div class="row" style="align-items:center;justify-content:space-between;flex-wrap:wrap;margin:10px 0 8px 0;gap:10px">
            <p class="muted" style="margin:0">Showing <strong>${startIdx}</strong>–<strong>${endIdx}</strong> of <strong>${total}</strong></p>
            <div class="mem-view-toggle icon-toolbar" role="group" aria-label="Run list layout">
              <button type="button" class="icon-btn ${view === 'table' ? 'mem-view-active' : ''}" title="Table layout" aria-label="Table layout"
                onclick="(() => { const p = memoryExplorerParams({ view: 'table' }); odSaveScrollAndGoQueryString(p.toString()); })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
              </button>
              <button type="button" class="icon-btn ${isTimeline ? 'mem-view-active' : ''}" title="Timeline layout" aria-label="Timeline layout"
                onclick="(() => { const p = memoryExplorerParams({ view: '' }); odSaveScrollAndGoQueryString(p.toString()); })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
              </button>
            </div>
          </div>
          ${isTimeline ? `<p class="muted" style="font-size:12px;margin:0 0 10px 0">Timeline matches filters and pagination. <strong>Newest first</strong>, grouped by local day (effective end/start time).</p>` : ''}
          ${isTimeline
            ? `<div class="table-scroll"><div class="mem-timeline">${buildRunTimelineHtml(data.items, search)}</div></div>`
            : `<div class="table-scroll">
            <table class="memories-table"><caption class="sr-only">Runs matching current filters</caption><thead><tr>
              <th scope="col" title="ended_at when present, otherwise started_at (local)">Time</th>
              <th scope="col" title="consolidation, dream, …">Type</th>
              <th scope="col">Status</th>
              <th scope="col" title="Stable run id">ID</th>
            </tr></thead><tbody>
              ${rows || '<tr><td colspan="4" class="muted">No runs match.</td></tr>'}
            </tbody></table>
          </div>`}
          <div class="pager">
            <button type="button" class="icon-btn" ${hasPrev ? '' : 'disabled'} aria-label="Previous page" title="Previous"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${prevOff}) }); odSaveScrollAndGoQueryString(p.toString()); })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <button type="button" class="icon-btn" ${hasNext ? '' : 'disabled'} aria-label="Next page" title="Next"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${nextOff}) }); odSaveScrollAndGoQueryString(p.toString()); })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
            <span class="muted">offset ${off}, limit ${lim}</span>
          </div>
        `,
          false,
          'runs-explorer',
        ),
        panel('Consolidation Inspector', detailHtml, false, 'runs-detail'),
      ].join(''));
    }

    async function renderRetrievals(retrievalId=null) {
      const params = new URLSearchParams(location.search);
      const q = (k, d='') => params.get(k) || d;
      const search = q('search');
      const sort = q('sort', 'timestamp');
      const sortDir = q('sort_dir');
      const offset = q('offset', '0');
      const limit = q('limit', '50');
      const timestampAfter = q('timestamp_after');
      const timestampBefore = q('timestamp_before');
      const minSelected = q('min_selected');
      const maxSelected = q('max_selected');
      const view = q('view', '');
      const isTimeline = view !== 'table';
      const apiParams = {};
      if (search) apiParams.search = search;
      apiParams.sort = sort;
      if (sortDir) apiParams.sort_dir = sortDir;
      apiParams.offset = offset;
      apiParams.limit = limit;
      if (timestampAfter) apiParams.timestamp_after = timestampAfter;
      if (timestampBefore) apiParams.timestamp_before = timestampBefore;
      if (minSelected) apiParams.min_selected = minSelected;
      if (maxSelected) apiParams.max_selected = maxSelected;
      const data = await fetchJson('/api/retrievals?' + qs(apiParams));
      const total = data.total;
      const off = parseInt(offset, 10) || 0;
      const lim = parseInt(limit, 10) || 50;
      const startIdx = total === 0 ? 0 : off + 1;
      const endIdx = off + data.items.length;
      const prevOff = Math.max(0, off - lim);
      const nextOff = off + lim;
      const hasPrev = off > 0;
      const hasNext = nextOff < total;
      const optSel = (val, cur) => (val === cur ? 'selected' : '');
      const sortFields = [
        ['timestamp', 'Time'],
        ['id', 'ID'],
        ['query', 'Query'],
        ['selected_count', 'Selected count'],
      ];
      const sortOpts = sortFields.map(([v, lab]) => `<option value="${v}" ${optSel(v, sort)}>${lab}</option>`).join('');
      const dirAsc = sortDir === 'asc' ? 'selected' : '';
      const dirDesc = sortDir === 'desc' ? 'selected' : '';
      const dirDefault = !sortDir ? 'selected' : '';
      const lim25 = optSel('25', String(lim));
      const lim50 = optSel('50', String(lim));
      const lim100 = optSel('100', String(lim));
      let detailHtml = '<p class="muted">Select a retrieval record.</p>';
      if (retrievalId) {
        const detail = await fetchJson('/api/retrievals/' + encodeURIComponent(retrievalId));
        const readable = formatRetrievalDetailReadable(detail);
        detailHtml = `
          <div class="row"><strong>${escapeHtml(detail.query || '')}</strong></div>
          <div class="mem-view-toggle mem-detail-toggle icon-toolbar" role="group" aria-label="Retrieval detail format">
            <button type="button" id="ret-detail-btn-formatted" class="icon-btn mem-view-active" onclick="retrievalDetailToggle('formatted')" aria-label="Formatted detail" title="Formatted">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
            <button type="button" id="ret-detail-btn-raw" class="icon-btn" onclick="retrievalDetailToggle('raw')" aria-label="Raw JSON" title="Raw JSON">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            </button>
          </div>
          <div id="ret-detail-formatted" class="mem-detail-body">${readable}</div>
          <div id="ret-detail-raw" class="mem-detail-body" style="display:none">${pretty(detail)}</div>`;
      }
      const rows = data.items.map((item) => {
        const n = (item.selected_memory_ids || []).length;
        const t = formatInstantLocal(item.timestamp);
        const qfull = item.query || '';
        const qtext = qfull.slice(0, 120);
        const qcell = qfull
          ? `<a href="${retrievalHref(item.id)}">${escapeHtml(qtext)}${qfull.length > 120 ? '…' : ''}</a>`
          : '<span class="muted">—</span>';
        return `<tr>
          <td>${escapeHtml(t || '—')}</td>
          <td>${qcell}</td>
          <td class="num">${n}</td>
          <td class="muted" style="font-size:12px"><a href="${retrievalHref(item.id)}">${escapeHtml(String(item.id))}</a></td>
        </tr>`;
      }).join('');
      const bcRet =
        retrievalId
          ? odBreadcrumbHtml([
              { href: '/retrievals', label: 'Retrievals' },
              { href: '', label: odTruncateMiddle(retrievalId, 42) },
            ])
          : '';
      odSetMainHtml(
        bcRet +
        [
        panel('Retrieval Explorer', `
          <div class="od-toolbar-sticky">
          <form class="memories-toolbar" id="retrievals-filter-form" onsubmit="event.preventDefault(); const f=this; const p = memoryExplorerParams({
            search: f.search.value,
            sort: f.sort.value,
            sort_dir: f.sort_dir.value,
            limit: f.limit.value,
            timestamp_after: datetimeLocalToIsoUtc(f.timestamp_after.value),
            timestamp_before: datetimeLocalToIsoUtc(f.timestamp_before.value),
            min_selected: f.min_selected.value,
            max_selected: f.max_selected.value,
            offset: '0',
            view: f.list_view ? f.list_view.value : ''
          }); odSaveScrollAndGoQueryString(p.toString());">
            <input type="hidden" name="list_view" value="${view === 'table' ? 'table' : ''}">
            <div class="row" style="align-items:flex-end">
              <label style="display:flex;flex-direction:column;gap:4px;min-width:180px;flex:1"><span class="muted" style="font-size:11px">Search</span>
                <input name="search" type="search" placeholder="id, query, summary" value="${escapeHtml(search)}"></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Sort</span>
                <select name="sort">${sortOpts}</select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Dir</span>
                <select name="sort_dir">
                  <option value="" ${dirDefault}>default</option>
                  <option value="asc" ${dirAsc}>asc</option>
                  <option value="desc" ${dirDesc}>desc</option>
                </select></label>
              <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Page size</span>
                <select name="limit">
                  <option value="25" ${lim25}>25</option>
                  <option value="50" ${lim50}>50</option>
                  <option value="100" ${lim100}>100</option>
                </select></label>
              <button type="submit" class="icon-btn" aria-label="Apply filters" title="Apply filters">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
              </button>
            </div>
            <div class="row" style="align-items:center;margin-top:4px">
              <span class="muted" style="font-size:11px">Retrieval time window:</span>
              <button type="button" class="icon-btn" onclick="applyRetrievalTimePreset(24)" aria-label="Last 24 hours" title="Last 24 hours">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg><span class="sr-only">24h</span>
              </button>
              <button type="button" class="icon-btn" onclick="applyRetrievalTimePreset(168)" aria-label="Last 7 days" title="Last 7 days">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg><span class="sr-only">7d</span>
              </button>
            </div>
            <details>
              <summary>Advanced filters (time, selected count)</summary>
              <p class="muted" style="font-size:12px;margin:8px 0 0 0">Times use <strong>your browser timezone</strong> in the pickers; the URL stores UTC instants for stable filters.</p>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">On or after</span>
                  <input name="timestamp_after" type="datetime-local" step="60" title="Local time; filter is UTC instant" value="${escapeHtml(isoUtcToDatetimeLocal(timestampAfter))}"></label>
                <label style="display:flex;flex-direction:column;gap:4px;min-width:200px;flex:1"><span class="muted" style="font-size:11px">On or before</span>
                  <input name="timestamp_before" type="datetime-local" step="60" title="Local time; filter is UTC instant" value="${escapeHtml(isoUtcToDatetimeLocal(timestampBefore))}"></label>
              </div>
              <div class="row" style="margin-top:10px">
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Min selected</span>
                  <input name="min_selected" type="number" min="0" step="1" placeholder="any" value="${escapeHtml(minSelected)}"></label>
                <label style="display:flex;flex-direction:column;gap:4px"><span class="muted" style="font-size:11px">Max selected</span>
                  <input name="max_selected" type="number" min="0" step="1" placeholder="any" value="${escapeHtml(maxSelected)}"></label>
              </div>
            </details>
          </form></div>
          ${!retrievalId ? `<div class="row od-export-row" style="gap:8px;align-items:center;margin:6px 0 4px 0;flex-wrap:wrap">
            <span class="muted" style="font-size:11px">Export this page:</span>
            <button type="button" class="icon-btn" onclick="void odCopyCurrentViewUrl()" title="Copy URL including filters" aria-label="Copy link to this view"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
            <button type="button" class="icon-btn" onclick="void odExportCurrentList('retrievals','json')" title="Download JSON" aria-label="Export retrievals as JSON"><span style="font-size:10px;font-weight:700">JSON</span></button>
            <button type="button" class="icon-btn" onclick="void odExportCurrentList('retrievals','csv')" title="Download CSV" aria-label="Export retrievals as CSV"><span style="font-size:10px;font-weight:700">CSV</span></button>
          </div>` : `<div class="row od-export-row" style="gap:8px;align-items:center;margin:6px 0 4px 0;flex-wrap:wrap">
            <span class="muted" style="font-size:11px">Export this retrieval:</span>
            <button type="button" class="icon-btn" onclick="void odCopyCurrentViewUrl()" title="Copy URL to this retrieval" aria-label="Copy link to this retrieval"><svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
            <button type="button" class="icon-btn" onclick="void odExportCurrentList('retrievals','json')" title="Download JSON" aria-label="Export retrieval as JSON"><span style="font-size:10px;font-weight:700">JSON</span></button>
          </div>`}
          ${total === 0 ? '<div class="od-empty-nextsteps glossary-hint" role="status">No retrieval audits yet, or none match your filters. Ensure tooling records retrievals and <code>opendream observe index --workspace "$PWD"</code> has been run. See <a href="/overview">Overview</a>.</div>' : ''}
          <div class="row" style="align-items:center;justify-content:space-between;flex-wrap:wrap;margin:10px 0 8px 0;gap:10px">
            <p class="muted" style="margin:0">Showing <strong>${startIdx}</strong>–<strong>${endIdx}</strong> of <strong>${total}</strong></p>
            <div class="mem-view-toggle icon-toolbar" role="group" aria-label="Retrieval list layout">
              <button type="button" class="icon-btn ${view === 'table' ? 'mem-view-active' : ''}" title="Table layout" aria-label="Table layout"
                onclick="(() => { const p = memoryExplorerParams({ view: 'table' }); odSaveScrollAndGoQueryString(p.toString()); })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
              </button>
              <button type="button" class="icon-btn ${isTimeline ? 'mem-view-active' : ''}" title="Timeline layout" aria-label="Timeline layout"
                onclick="(() => { const p = memoryExplorerParams({ view: '' }); odSaveScrollAndGoQueryString(p.toString()); })()">
                <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
              </button>
            </div>
          </div>
          <details class="mem-detail-details" style="margin-bottom:12px">
            <summary>Column tips</summary>
            <p class="glossary-hint" style="margin-top:8px;margin-bottom:0"><strong>Sel.</strong> = memories in the ranked top-k for that query. Open a row for <strong>Query provenance</strong> (which pipeline invoked retrieval). Hover headers for more.</p>
          </details>
          ${isTimeline ? `<p class="muted" style="font-size:12px;margin:0 0 10px 0">Timeline uses the same filters and pagination as the table. Items on this page are <strong>newest first</strong>, grouped by <strong>local calendar day</strong> (by retrieval <code>timestamp</code>).</p>` : ''}
          ${isTimeline
            ? `<div class="table-scroll"><div class="mem-timeline">${buildRetrievalTimelineHtml(data.items, search)}</div></div>`
            : `<div class="table-scroll">
            <table class="memories-table"><caption class="sr-only">Retrieval audit records matching current filters</caption><thead><tr>
              <th scope="col" title="When this retrieval was audited (shown in your local timezone in the cells below)">Time</th>
              <th scope="col" title="Query string passed to retrieve(). Who issued it is shown as Query provenance on the detail panel when the caller records it.">Query</th>
              <th class="num" scope="col" title="Number of memories in the final ranked top-k selection (len(selected_memory_ids))">Sel.</th>
              <th scope="col" title="Stable retrieval / run id (audit file key)">ID</th>
            </tr></thead><tbody>
              ${rows || '<tr><td colspan="4" class="muted">No retrievals match.</td></tr>'}
            </tbody></table>
          </div>`}
          <div class="pager">
            <button type="button" class="icon-btn" ${hasPrev ? '' : 'disabled'} aria-label="Previous page" title="Previous"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${prevOff}) }); odSaveScrollAndGoQueryString(p.toString()); })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="15 18 9 12 15 6"/></svg>
            </button>
            <button type="button" class="icon-btn" ${hasNext ? '' : 'disabled'} aria-label="Next page" title="Next"
              onclick="(() => { const p = memoryExplorerParams({ offset: String(${nextOff}) }); odSaveScrollAndGoQueryString(p.toString()); })()">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
            <span class="muted">offset ${off}, limit ${lim}</span>
          </div>
        `, false, 'ret-explorer'),
        panel('Retrieval Explainability', detailHtml, false, 'ret-detail'),
      ].join(''));
    }

    async function renderReviews() {
      const data = await fetchJson('/api/reviews');
      const rows = (data.items || [])
        .map(
          (item) => `<tr>
          <td title="Queue category for routing actions">${escapeHtml(String(item.queue_item_type || ''))}</td>
          <td title="Target object id (memory, run, retrieval, …)">${escapeHtml(String(item.queue_item_id || ''))}</td>
          <td title="Why this item was queued">${escapeHtml(String(item.reason || ''))}</td>
        </tr>`
        )
        .join('');
      odSetMainHtml([
        panel(
          'Review Queue',
          `<details class="mem-detail-details" style="margin-bottom:12px">
            <summary>About this queue</summary>
            <p class="glossary-hint" style="margin-top:8px;margin-bottom:0">Items are derived from the observability index (contested memories, low confidence, suspicious retrievals, runs with warnings or diffs). Approve or annotate via the API from your workflows.</p>
          </details>
          <table class="memories-table"><caption class="sr-only">Items awaiting operator review</caption><thead><tr>
            <th scope="col" title="Queue category (memory vs run vs retrieval)">Type</th>
            <th scope="col" title="Stable id of the queued object">Item</th>
            <th scope="col" title="Human-readable reason this row appears">Reason</th>
          </tr></thead><tbody>${rows || '<tr><td colspan="3" class="muted">Queue is empty.</td></tr>'}</tbody></table>`,
          true,
        ),
      ].join(''));
    }

    function loadScript(src) {
      return new Promise((resolve, reject) => {
        if (document.querySelector('script[src="' + src + '"]')) return resolve();
        const s = document.createElement('script');
        s.src = src;
        s.onload = resolve;
        s.onerror = () => reject(new Error('failed to load ' + src));
        document.head.appendChild(s);
      });
    }

    async function renderGraph() {
      odSetMainHtml('<section class="panel full" style="padding:0;"><div id="graph-root"></div></section>');
      try {
        if (!window.__opendreamGraph) {
          const scripts = [
            '/static/vendor/graphology.umd.min.js',
            '/static/vendor/graphology-layout-forceatlas2.min.js',
            '/static/vendor/sigma.min.js',
            '/static/graph.js',
          ];
          for (const src of scripts) await loadScript(src);
        }
        window.__opendreamGraph.mount(document.getElementById('graph-root'));
      } catch (err) {
        const data = await fetchJson('/api/graph');
        odSetMainHtml([
          panel('Provenance Graph (fallback view \u2014 interactive renderer failed: ' + err.message + ')', `<div class="split"><div>${pretty(data.nodes)}</div><div>${pretty(data.edges)}</div></div>`, true),
        ].join(''));
      }
    }

    async function renderEvals() {
      const data = await fetchJson('/api/evals');
      odSetMainHtml([
        panel(
          'Health / Evals',
          `<details class="mem-detail-details"><summary>Raw JSON</summary><div style="margin-top:10px">${pretty(data)}</div></details>`,
          true,
        ),
      ].join(''));
    }

    async function renderExports() {
      const data = await fetchJson('/api/exports');
      odSetMainHtml([
        panel(
          'Exports',
          `<details class="mem-detail-details"><summary>Raw JSON</summary><div style="margin-top:10px">${pretty(data)}</div></details>`,
          true,
        ),
      ].join(''));
    }

    async function renderSettings() {
      const data = await fetchJson('/api/overview');
      let meta = {};
      try {
        meta = await fetchJson('/api/ui-meta');
      } catch (_m) {}
      const metaVer = meta.cli_json_version != null ? String(meta.cli_json_version) : '—';
      const assets = (meta.observe_ui && meta.observe_ui.static_assets) || [];
      const assetsLine = assets.length
        ? `<p class="muted" style="margin:8px 0 0 0;font-size:12px">Bundled UI assets: ${assets.map((a) => `<code>${escapeHtml(String(a))}</code>`).join(', ')}</p>`
        : '';
      const odDensity = document.documentElement.getAttribute('data-density') || 'comfortable';
      const densComfort = odDensity === 'comfortable' ? 'active' : '';
      const densCompact = odDensity === 'compact' ? 'active' : '';
      odSetMainHtml(
        [
          panel(
            'UI version',
            `<p class="muted" style="margin-top:0;line-height:1.55">This dashboard is served by the in-repo <code>opendream observe serve</code> static bundle. <strong>CLI JSON schema version</strong> (contract field <code>cli_output_version</code> / <code>CLI_JSON_VERSION</code>): <code>${escapeHtml(metaVer)}</code>.</p>
          ${assetsLine}
          <p class="muted" style="margin-top:10px;margin-bottom:0;font-size:12px">Read API: <code>${location.origin}/api/ui-meta</code></p>`,
            true,
          ),
          panel(
            'Display',
            `<p class="muted" style="margin-top:0;line-height:1.55">Table and panel spacing for this dashboard. Saved in your browser only (<code>localStorage</code> key <code>${escapeHtml(OD_DENSITY_KEY)}</code>).</p>
          <div class="graph-segmented od-settings-density" role="group" aria-label="Display density" style="margin-top:12px">
            <button type="button" data-density="comfortable" class="${densComfort}" aria-pressed="${odDensity === 'comfortable' ? 'true' : 'false'}">Comfortable</button>
            <button type="button" data-density="compact" class="${densCompact}" aria-pressed="${odDensity === 'compact' ? 'true' : 'false'}">Compact</button>
          </div>`,
            true,
          ),
          panel(
            'Store metadata (read-only)',
            `<p class="muted" style="margin-top:0;line-height:1.55">This page is the <strong>raw store snapshot</strong>: lock state, memory root, startup index, and activation diagnostics as returned by the server. Use <a href="/overview">Overview</a> for counts, recent runs/sessions, and contested memory at a glance.</p>
          <h3 class="mem-detail-h" style="margin-top:16px">Structured fields</h3>
          <div class="mem-detail-meta">
            <div class="mem-detail-field"><span class="mem-detail-label">Memory root</span><span class="mem-detail-val">${escapeHtml(
              String((data.store_health && data.store_health.memory_root) || '')
            )}</span></div>
          </div>
          <details class="mem-detail-details" style="margin-top:14px"><summary>Raw JSON (store_health, startup_index, activation_diagnostics)</summary>
            <div style="margin-top:10px">${pretty({
              store_health: data.store_health,
              startup_index: data.startup_index,
              activation_diagnostics: data.activation_diagnostics,
            })}</div>
          </details>`,
            true,
          ),
        ].join(''),
        function bindSettingsDensity() {
          var densSeg = document.querySelector('.od-settings-density');
          if (!densSeg) return;
          densSeg.addEventListener('click', function (ev) {
            var btn = ev.target.closest('button[data-density]');
            if (!btn || !densSeg.contains(btn)) return;
            applyUiDensity(btn.getAttribute('data-density'));
          });
          syncUiDensitySettingsSegmented();
        },
      );
    }

    async function renderSessions(sessionId=null) {
      const data = await fetchJson('/api/sessions');
      let detailHtml = '<p class="muted">Select a session.</p>';
      if (sessionId) {
        const detail = await fetchJson('/api/sessions/' + encodeURIComponent(sessionId) + '/timeline');
        detailHtml = `${buildSessionTimelineFromDetail(detail)}
          <details class="mem-detail-details" style="margin-top:14px"><summary>Raw timeline JSON</summary>${pretty(detail)}</details>`;
      }
      const sessionRows = data.items
        .map((item) => {
          const sid = String(item.session_id || '');
          const last = sessionLastInstant(item);
          const lastDisp = last ? formatInstantLocal(last) : '—';
          return `<tr>
          <td><a href="${sessionHref(sid)}">${escapeHtml(sid)}</a></td>
          <td class="num">${item.event_count != null ? escapeHtml(String(item.event_count)) : '—'}</td>
          <td class="num">${item.context_count != null ? escapeHtml(String(item.context_count)) : '—'}</td>
          <td title="Latest timestamp from embedded timeline">${escapeHtml(lastDisp)}</td>
        </tr>`;
        })
        .join('');
      const bcSes =
        sessionId
          ? odBreadcrumbHtml([
              { href: '/sessions', label: 'Sessions' },
              { href: '', label: odTruncateMiddle(sessionId, 42) },
            ])
          : '';
      odSetMainHtml(
        bcSes +
        [
        panel(
          'Sessions',
          `<p class="muted" style="margin:0 0 10px 0">Context assemblies use opaque IDs. Use <a href="/context">Context</a> with an ID from your tooling, or <code>GET /api/context/&lt;id&gt;</code>.</p>
          <table class="memories-table"><caption class="sr-only">Capture sessions</caption><thead><tr>
            <th scope="col">ID</th>
            <th class="num" scope="col" title="Events captured in this session">Events</th>
            <th class="num" scope="col" title="Context assemblies linked to this session">Contexts</th>
            <th scope="col" title="Max timestamp from the session timeline embedded in the index (client-derived)">Last activity</th>
          </tr></thead><tbody>${sessionRows || '<tr><td colspan="4" class="muted">No sessions.</td></tr>'}</tbody></table>`,
        ),
        panel('Session Timeline', detailHtml, false, 'session-timeline'),
      ].join(''));
    }

    async function renderContext(contextId) {
      if (!contextId || String(contextId).trim() === '') {
        odSetMainHtml([
          panel(
            'Context viewer',
            `<p class="muted">Context assemblies are keyed by an opaque ID (what was stitched for a specific capture).</p>
            <p class="muted">Obtain an ID from your session tooling or <code>GET /api/context/&lt;id&gt;</code>, then open <code>/context/&lt;id&gt;</code> in this UI. Recent sessions: <a href="/sessions">Sessions</a>.</p>`,
            true,
          ),
        ].join(''));
        return;
      }
      const data = await fetchJson('/api/context/' + encodeURIComponent(contextId));
      const readable = formatContextDetailReadable(data);
      const asm = (data.assembled_text || '').trim();
      const asmBlock = asm
        ? `<div class="mem-detail-section"><h4 class="mem-detail-h">Assembled text</h4><div class="mem-detail-body-text">${escapeHtml(asm)}</div></div>`
        : '<p class="muted">No assembled text.</p>';
      const bcCtx = odBreadcrumbHtml([
        { href: '/context', label: 'Context' },
        { href: '', label: odTruncateMiddle(contextId, 42) },
      ]);
      odSetMainHtml(
        bcCtx +
        [
        panel(
          'Context Viewer',
          `<div class="mem-view-toggle mem-detail-toggle icon-toolbar" role="group" aria-label="Context detail format">
            <button type="button" id="ctx-detail-btn-formatted" class="icon-btn mem-view-active" onclick="contextDetailToggle('formatted')" aria-label="Formatted" title="Formatted">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            </button>
            <button type="button" id="ctx-detail-btn-raw" class="icon-btn" onclick="contextDetailToggle('raw')" aria-label="Raw JSON" title="Raw JSON">
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            </button>
          </div>
          <div id="ctx-detail-formatted" class="mem-detail-body"><div class="split"><div>${readable}</div><div>${asmBlock}</div></div></div>
          <div id="ctx-detail-raw" class="mem-detail-body" style="display:none">${pretty(data)}</div>`,
          true,
          'ctx-viewer',
        ),
      ].join(''));
    }

    async function renderWorkspaces() {
      const data = await fetchJson('/api/workspaces');
      const summary = data.summary;
      const entries = data.entries;
      const searchParams = new URLSearchParams(location.search);
      const q = (searchParams.get('q') || '').toLowerCase();
      const statusFilter = searchParams.get('status') || '';
      const filtered = entries.filter(e => {
        if (statusFilter && e.status_kind !== statusFilter) return false;
        if (q) {
          const hay = (e.workspace_path + ' ' + (e.workspace_name || '')).toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });
      const rows = filtered.map(e => {
        const statusCls = e.status_kind === 'ok' ? 'active-badge' : (e.status_kind === 'stale' ? 'warning-badge' : 'error-badge');
        return `<tr>
          <td><a href="/workspaces/${encodeURIComponent(e.workspace_path)}">${e.workspace_name}</a><div class="muted" style="font-size:11px">${e.workspace_path}</div></td>
          <td><span class="badge ${statusCls}">${e.status_kind}</span></td>
          <td>${e.activation_state_summary || '<span class="muted">—</span>'}</td>
          <td>${e.service_state_summary || '<span class="muted">—</span>'}</td>
          <td>${e.memory_dir || '<span class="muted">—</span>'}</td>
          <td>${e.semantic_state_summary || '<span class="muted">—</span>'}</td>
          <td class="muted">${e.last_seen_at || ''}</td>
        </tr>`;
      }).join('');
      odSetMainHtml([
        panel('Workspaces Overview', `
          <p class="muted" style="font-size:12px;line-height:1.55;margin:0 0 12px 0">This table is the machine-local catalog. Overview, Memories, Trace, and Audit in the sidebar still read the workspace bound to <strong>this</strong> running <code>observe serve</code> process; use another port (another tab) to inspect a different workspace.</p>
          <div class="metric"><div class="label">Total</div><div class="value">${summary.total}</div></div>
          <div class="metric"><div class="label">Healthy</div><div class="value">${summary.ok}</div></div>
          <div class="metric"><div class="label">With Service</div><div class="value">${summary.with_service}</div></div>
          <div class="metric"><div class="label">Stale/Missing/Broken</div><div class="value">${summary.stale + summary.missing + summary.broken}</div></div>
        `, true),
        panel('Workspace Catalog', `
          <form class="row" onsubmit="event.preventDefault(); odSaveScrollAndGoQueryString(qs({q:this.q.value, status:this.status.value}));">
            <input name="q" placeholder="search path/name" value="${q}">
            <select name="status">
              <option value="">any status</option>
              <option value="ok" ${statusFilter==='ok'?'selected':''}>ok</option>
              <option value="stale" ${statusFilter==='stale'?'selected':''}>stale</option>
              <option value="missing" ${statusFilter==='missing'?'selected':''}>missing</option>
              <option value="broken" ${statusFilter==='broken'?'selected':''}>broken</option>
            </select>
            <button type="submit">Filter</button>
            <span class="muted">${filtered.length} of ${entries.length} entries</span>
          </form>
          <table>
            <caption class="sr-only">Registered workspaces from local catalog</caption>
            <thead><tr><th scope="col">Workspace</th><th scope="col">Status</th><th scope="col">Activation</th><th scope="col">Service</th><th scope="col">Memory Dir</th><th scope="col">Semantic</th><th scope="col">Last Seen</th></tr></thead>
            <tbody>${rows || '<tr><td colspan="7" class="muted">No workspaces in the local catalog. Run <code>opendream workspace scan --root &lt;path&gt;</code> or initialize a workspace. For this UI against a workspace: <code>opendream observe index --workspace "$PWD"</code> then <code>opendream observe serve --workspace "$PWD" --port 8000</code>.</td></tr>'}</tbody>
          </table>
        `, true),
        panel('Privacy', `<p class="muted">This catalog is machine-local. Workspace <code>.opendream/</code> state remains canonical. Scans only run on explicitly configured roots.</p>`, true),
      ].join(''));
    }

    async function renderWorkspaceDetail(rawPath) {
      const path = decodeURIComponent(rawPath);
      const data = await fetchJson('/api/workspaces/' + encodeURIComponent(path));
      if (data.status === 'missing') {
        const bcWsMiss = odBreadcrumbHtml([
          { href: '/workspaces', label: 'Workspaces' },
          { href: '', label: 'Not found' },
        ]);
        odSetMainHtml(bcWsMiss + [panel('Workspace Detail', `<p class="muted">No catalog entry for <code>${path}</code>.</p>`, true)].join(''));
        return;
      }
      const bcWs = odBreadcrumbHtml([
        { href: '/workspaces', label: 'Workspaces' },
        { href: '', label: odTruncateMiddle(data.entry.workspace_name || path, 40) },
      ]);
      odSetMainHtml(
        bcWs +
        [
        panel('Workspace Detail', `
          <h3>${data.entry.workspace_name}</h3>
          <p class="muted">${data.entry.workspace_path}</p>
          ${pretty(data.entry)}
        `, true),
      ].join(''));
    }

    (function odCommandPalette() {
      /* Cmd/Ctrl+K can overlap browser UI shortcuts when the chrome address bar steals focus; binding is intentional for this observability page. */
      var dlg = document.getElementById('od-command-palette');
      var inp = document.getElementById('od-palette-input');
      var listEl = document.getElementById('od-palette-list');
      var closeBtn = document.getElementById('od-palette-close');
      if (!dlg || !inp || !listEl) return;
      var PAL_RECENT_KEY = 'opendream-palette-recent';
      function odReadPaletteRecent() {
        try {
          var raw = localStorage.getItem(PAL_RECENT_KEY);
          if (!raw) return [];
          var arr = JSON.parse(raw);
          return Array.isArray(arr) ? arr : [];
        } catch (e) {
          return [];
        }
      }
      function odRecordPaletteRecent(href) {
        if (!href) return;
        try {
          var arr = odReadPaletteRecent();
          arr = arr.filter(function (x) {
            return x !== href;
          });
          arr.unshift(href);
          arr = arr.slice(0, 10);
          localStorage.setItem(PAL_RECENT_KEY, JSON.stringify(arr));
        } catch (e) {}
      }
      async function handlePaletteAction(action) {
        if (action === 'copy_workspace_path') {
          try {
            var ctx = await fetchJson('/api/ui-context');
            var p = ctx && ctx.workspace_path;
            if (p) await navigator.clipboard.writeText(String(p));
          } catch (e0) {}
          return;
        }
        if (action === 'copy_overview_url') {
          try {
            var o = location.origin || '';
            await navigator.clipboard.writeText(o ? o + '/overview' : '/overview');
          } catch (e1) {}
          return;
        }
        if (action === 'open_latest_run') {
          try {
            var data = await fetchJson('/api/runs?limit=1&offset=0&sort=ended_at');
            var id = data.items && data.items[0] && data.items[0].run_id;
            if (id) {
              location.href = '/runs/' + encodeURIComponent(String(id));
              return;
            }
          } catch (e2) {}
          location.href = '/runs';
        }
      }
      var items = [
        { href: '/overview', label: 'Overview', kw: 'home health summary' },
        { href: '/workspaces', label: 'Workspaces', kw: 'catalog roots' },
        { href: '/memories', label: 'Memories', kw: 'records durable' },
        { href: '/memories?focus_search=1', label: 'Memories — focus search', kw: 'find filter query search' },
        { href: '/memories?status=contested', label: 'Memories — contested filter', kw: 'triage disputed review queue' },
        { href: '/runs', label: 'Runs', kw: 'consolidation jobs' },
        { href: '/retrievals', label: 'Retrievals', kw: 'audit ranked' },
        { href: '/sessions', label: 'Sessions', kw: 'capture timeline' },
        { href: '/context', label: 'Context', kw: 'assembled' },
        { href: '/reviews', label: 'Reviews', kw: 'queue triage' },
        { href: '/graph', label: 'Provenance graph', kw: 'relations edges sigma' },
        { href: '/graph?view=data', label: 'Graph — data tables (a11y)', kw: 'keyboard screen reader table' },
        { href: '/evals', label: 'Evals', kw: 'health metrics' },
        { href: '/exports', label: 'Exports', kw: 'bundles' },
        { href: '/settings', label: 'Settings', kw: 'store metadata diagnostic' },
        { action: 'copy_workspace_path', label: 'Copy workspace path', kw: 'action clipboard filesystem directory cwd' },
        { action: 'copy_overview_url', label: 'Copy Overview URL', kw: 'action share bookmark link dashboard' },
        { action: 'open_latest_run', label: 'Open latest consolidation run', kw: 'action runs recent newest job' },
      ];
      var filtered = items.slice();
      var activeIdx = 0;
      function renderList() {
        var q = (inp.value || '').trim().toLowerCase();
        if (!q) {
          var recent = odReadPaletteRecent();
          var score = {};
          recent.forEach(function (h, i) {
            score[h] = recent.length - i;
          });
          filtered = items
            .slice()
            .sort(function (a, b) {
              var sa = score[a.href] || 0;
              var sb = score[b.href] || 0;
              return sb - sa;
            });
        } else {
          filtered = items.filter(function (it) {
            var hay = (it.label + ' ' + it.kw + ' ' + (it.href || '') + ' ' + (it.action || '')).toLowerCase();
            return hay.indexOf(q) !== -1;
          });
        }
        if (activeIdx >= filtered.length) activeIdx = Math.max(0, filtered.length - 1);
        listEl.innerHTML = filtered
          .map(function (it, ix) {
            var active = ix === activeIdx ? ' od-palette-active' : '';
            return (
              '<li><button type="button" class="' +
              active.trim() +
              '" data-idx="' +
              ix +
              '">' +
              escapeHtml(it.label) +
              '</button></li>'
            );
          })
          .join('');
      }
      async function navigateItem(it) {
        if (!it) return;
        if (it.action) {
          dlg.close();
          await handlePaletteAction(it.action);
          return;
        }
        if (it.href) {
          odRecordPaletteRecent(it.href);
          dlg.close();
          location.href = it.href;
        }
      }
      function openPalette() {
        inp.value = '';
        activeIdx = 0;
        renderList();
        dlg.showModal();
        setTimeout(function () {
          inp.focus();
        }, 0);
      }
      function closePalette() {
        dlg.close();
      }
      listEl.addEventListener('click', function (ev) {
        var b = ev.target.closest('button[data-idx]');
        if (!b) return;
        var ix = parseInt(b.getAttribute('data-idx'), 10);
        if (!Number.isFinite(ix) || !filtered[ix]) return;
        void navigateItem(filtered[ix]);
      });
      inp.addEventListener('input', function () {
        activeIdx = 0;
        renderList();
      });
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          activeIdx = Math.min(filtered.length - 1, activeIdx + 1);
          renderList();
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          activeIdx = Math.max(0, activeIdx - 1);
          renderList();
        } else if (e.key === 'Enter') {
          e.preventDefault();
          if (filtered[activeIdx]) void navigateItem(filtered[activeIdx]);
        }
      });
      document.addEventListener('keydown', function (e) {
        if ((e.metaKey || e.ctrlKey) && String(e.key || '').toLowerCase() === 'k') {
          e.preventDefault();
          if (dlg.open) closePalette();
          else openPalette();
        }
      });
      if (closeBtn) closeBtn.addEventListener('click', closePalette);
      dlg.addEventListener('cancel', function (e) {
        e.preventDefault();
        closePalette();
      });
    })();
    if (route === '/' || route === '/overview') void runRender('Overview', renderOverview);
    else if (route === '/workspaces') void runRender('Workspaces', renderWorkspaces);
    else if (route.startsWith('/workspaces/')) void runRender('Workspace detail', () => renderWorkspaceDetail(route.split('/').pop()));
    else if (route === '/memories') void runRender('Memories', () => renderMemories());
    else if (route.startsWith('/memories/')) void runRender('Memories', () => renderMemories(route.split('/').pop()));
    else if (route === '/runs') void runRender('Runs', renderRuns);
    else if (route.startsWith('/runs/')) void runRender('Runs', () => renderRuns(route.split('/').pop()));
    else if (route === '/retrievals') void runRender('Retrievals', () => renderRetrievals());
    else if (route.startsWith('/retrievals/')) void runRender('Retrievals', () => renderRetrievals(route.split('/').pop()));
    else if (route === '/reviews') void runRender('Reviews', renderReviews);
    else if (route === '/graph') void runRender('Provenance graph', renderGraph);
    else if (route === '/evals') void runRender('Evals', renderEvals);
    else if (route === '/exports') void runRender('Exports', renderExports);
    else if (route === '/settings') void runRender('Settings', renderSettings);
    else if (route === '/sessions') void runRender('Sessions', () => renderSessions());
    else if (route.startsWith('/sessions/')) void runRender('Sessions', () => renderSessions(route.split('/').pop()));
    else if (route === '/context' || route === '/context/') void runRender('Context', () => renderContext(null));
    else if (route.startsWith('/context/')) void runRender('Context', () => renderContext(route.split('/').pop()));
    else void runRender('Overview', renderOverview);