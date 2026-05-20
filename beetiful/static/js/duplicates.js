let dupTracks = {};
let dupCounts = {};

document.addEventListener('DOMContentLoaded', () => {
    scan();
    resumeScanIfRunning();
});

const TIER_META = {
    definite: { label: 'Definite', badge: 'text-bg-danger' },
    probable: { label: 'Probable', badge: 'text-bg-warning' },
    possible: { label: 'Possible', badge: 'text-bg-info' },
};
const TIER_ORDER = ['definite', 'probable', 'possible'];

function selectedTiers() {
    const tiers = [];
    if (document.getElementById('tierDefinite').checked) tiers.push('definite');
    if (document.getElementById('tierProbable').checked) tiers.push('probable');
    if (document.getElementById('tierPossible').checked) tiers.push('possible');
    return tiers;
}

function setHashButton(running) {
    const btn = document.getElementById('hashBtn');
    btn.disabled = running;
    btn.textContent = running ? 'Computing hashes' : 'Check by hash';
}

function startHashScan() {
    setHashButton(true);
    fetch('/api/duplicates/scan', { method: 'POST' })
        .then(r => r.json().then(d => ({ ok: r.ok, d })))
        .then(({ ok, d }) => {
            if (!ok) throw new Error(d.error || 'could not start scan');
            pollScan();
        })
        .catch(e => { showToast('Hash scan: ' + e.message, 'danger'); setHashButton(false); });
}

function resumeScanIfRunning() {
    fetch('/api/duplicates/scan/status').then(r => r.json()).then(s => {
        if (s.running) { setHashButton(true); pollScan(); }
    }).catch(() => {});
}

function pollScan() {
    const el = document.getElementById('hashProgress');
    fetch('/api/duplicates/scan/status').then(r => r.json()).then(s => {
        if (s.running) {
            setHashButton(true);
            el.textContent = `Hashing ${s.done}/${s.total} (new ${s.hashed}, cached ${s.skipped}, err ${s.errors})`;
            setTimeout(pollScan, 1500);
        } else {
            setHashButton(false);
            if (s.error) {
                el.textContent = `Error: ${s.error}`;
            } else if (s.total) {
                el.textContent = `Done: ${s.hashed} new, ${s.skipped} cached, ${s.errors} errors.`;
                showToast('File hashing complete — refreshing.');
                scan();
            } else {
                el.textContent = '';
            }
        }
    }).catch(() => {});
}

function scan() {
    const tiers = selectedTiers();
    const summary = document.getElementById('summary');
    const results = document.getElementById('results');
    if (tiers.length === 0) {
        summary.textContent = 'Select at least one tier to scan.';
        results.innerHTML = '';
        return;
    }
    const btn = document.getElementById('scanBtn');
    btn.disabled = true;
    summary.textContent = 'Scanning…';
    results.innerHTML = '';

    fetch(`/api/duplicates?tiers=${encodeURIComponent(tiers.join(','))}`)
        .then(r => r.json().then(data => ({ ok: r.ok, data })))
        .then(({ ok, data }) => {
            if (!ok) throw new Error(data.error || 'Scan failed');
            dupTracks = data.tracks || {};
            renderResults(data.clusters || [], data.counts || {});
        })
        .catch(err => {
            summary.textContent = '';
            showToast('Scan error: ' + err.message, 'danger');
        })
        .finally(() => { btn.disabled = false; });
}

function renderResults(clusters, counts) {
    const results = document.getElementById('results');
    results.innerHTML = '';
    dupCounts = counts || {};

    if (clusters.length === 0) {
        document.getElementById('summary').textContent = 'No duplicates found for the selected tiers.';
        return;
    }
    renderSummary();

    // Strongest tier first; clusters arrive already ordered that way from the API.
    clusters.forEach((cluster, idx) => results.appendChild(renderCluster(cluster, idx)));
}

function renderSummary() {
    const summary = document.getElementById('summary');
    const total = TIER_ORDER.reduce((n, t) => n + (dupCounts[t] || 0), 0);
    if (total === 0) {
        summary.textContent = 'No duplicates remain for the selected tiers.';
        return;
    }
    summary.innerHTML = TIER_ORDER
        .filter(t => dupCounts[t])
        .map(t => `<span class="badge ${TIER_META[t].badge} me-2">${TIER_META[t].label}: ${dupCounts[t]}</span>`)
        .join('');
}

function renderCluster(cluster, idx) {
    const meta = TIER_META[cluster.tier] || { label: cluster.tier, badge: 'text-bg-secondary' };
    const card = document.createElement('div');
    card.className = 'card mb-3';

    const header = document.createElement('div');
    header.className = 'card-header d-flex align-items-center gap-2';
    const badge = document.createElement('span');
    badge.className = `badge ${meta.badge}`;
    badge.textContent = meta.label;
    const reason = document.createElement('span');
    reason.className = 'small text-muted';
    reason.textContent = cluster.reason;
    header.appendChild(badge);
    header.appendChild(reason);
    card.appendChild(header);

    const table = document.createElement('table');
    table.className = 'table table-sm mb-0 align-middle';
    table.innerHTML = `
        <thead><tr>
            <th style="width:4rem">Keep</th>
            <th>Title</th><th>Artist</th><th>Album</th>
            <th>Length</th><th>Quality</th><th style="width:14rem">Play</th>
        </tr></thead>`;
    const tbody = document.createElement('tbody');

    cluster.members.forEach(id => {
        const t = dupTracks[String(id)] || {};
        const tr = document.createElement('tr');
        tr.dataset.memberId = id;

        const keepTd = document.createElement('td');
        const radio = document.createElement('input');
        radio.type = 'radio';
        radio.className = 'form-check-input';
        radio.name = `keep-${idx}`;
        radio.value = id;
        radio.checked = id === cluster.keep;
        keepTd.appendChild(radio);
        tr.appendChild(keepTd);

        tr.appendChild(cell(t.title));
        tr.appendChild(cell(t.artist));
        tr.appendChild(cell(t.album));
        tr.appendChild(cell(t.length));
        tr.appendChild(cell([t.format, t.bitrate ? `${t.bitrate}kbps` : null].filter(Boolean).join(' · ')));

        const playTd = document.createElement('td');
        const audio = document.createElement('audio');
        audio.controls = true;
        audio.preload = 'none';
        audio.style.maxWidth = '13rem';
        audio.src = `/api/library/audio/${encodeURIComponent(id)}`;
        playTd.appendChild(audio);
        if (t.path) {
            const pathEl = document.createElement('div');
            pathEl.className = 'small text-muted font-monospace mt-1';
            pathEl.style.wordBreak = 'break-all';
            pathEl.style.maxWidth = '13rem';
            pathEl.textContent = t.path;
            pathEl.title = t.path;
            playTd.appendChild(pathEl);
        }
        tr.appendChild(playTd);

        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    card.appendChild(table);

    const footer = document.createElement('div');
    footer.className = 'card-footer d-flex align-items-center gap-2';
    const label = document.createElement('span');
    label.className = 'small text-muted me-1';
    label.textContent = 'Keep selected, and with others';
    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn btn-warning btn-sm';
    removeBtn.textContent = 'Remove from library';
    removeBtn.addEventListener('click', () => actOnOthers(idx, cluster, 'remove', card));
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn btn-danger btn-sm';
    deleteBtn.textContent = 'Delete from disk';
    deleteBtn.addEventListener('click', () => actOnOthers(idx, cluster, 'delete', card));
    footer.appendChild(label);
    footer.appendChild(removeBtn);
    footer.appendChild(deleteBtn);
    card.appendChild(footer);

    return card;
}

function cell(text) {
    const td = document.createElement('td');
    td.textContent = text || '';
    return td;
}

function actOnOthers(idx, cluster, action, card) {
    const checked = document.querySelector(`input[name="keep-${idx}"]:checked`);
    if (!checked) { showToast('Pick a track to keep first.', 'danger'); return; }
    const keepId = parseInt(checked.value, 10);
    const others = cluster.members.filter(id => id !== keepId);
    if (others.length === 0) return;

    const verb = action === 'delete' ? 'delete from disk' : 'remove from library';
    if (!confirm(`This will ${verb} ${others.length} track(s), keeping id ${keepId}. Continue?`)) return;

    const endpoint = action === 'delete' ? '/api/library/delete' : '/api/library/remove';
    Promise.allSettled(others.map(id =>
        fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        }).then(r => { if (!r.ok) return r.json().then(d => Promise.reject(new Error(d.error || 'failed'))); })
    )).then(outcomes => {
        let ok = 0, failed = 0;
        outcomes.forEach((o, i) => {
            if (o.status === 'fulfilled') {
                ok++;
                card.querySelector(`tr[data-member-id="${others[i]}"]`)?.remove();
            } else {
                failed++;
            }
        });
        if (failed === 0) showToast(`${action === 'delete' ? 'Deleted' : 'Removed'} ${ok} track(s).`);
        else showToast(`${ok} succeeded, ${failed} failed.`, failed === outcomes.length ? 'danger' : 'warning');

        // A cluster with fewer than two members is no longer a duplicate set.
        if (card.querySelectorAll('tbody tr').length <= 1) {
            if (dupCounts[cluster.tier]) {
                dupCounts[cluster.tier]--;
                renderSummary();
            }
            card.remove();
        }
    });
}

function showToast(message, variant) {
    const container = document.getElementById('toastContainer');
    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-bg-${variant || 'success'} border-0`;
    toastEl.setAttribute('role', 'status');
    toastEl.setAttribute('aria-live', 'polite');
    toastEl.setAttribute('aria-atomic', 'true');
    const flex = document.createElement('div');
    flex.className = 'd-flex';
    const body = document.createElement('div');
    body.className = 'toast-body';
    body.textContent = message;
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'btn-close btn-close-white me-2 m-auto';
    close.setAttribute('data-bs-dismiss', 'toast');
    flex.appendChild(body);
    flex.appendChild(close);
    toastEl.appendChild(flex);
    container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    toast.show();
}
