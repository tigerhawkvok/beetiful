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
        radio.addEventListener('change', () => updateRowEmphasis(card));
        keepTd.appendChild(radio);
        tr.appendChild(keepTd);

        tr.appendChild(titleCell(t, cluster, card));
        tr.appendChild(cell(t.artist));
        tr.appendChild(albumCell(t));
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
            pathEl.className = 'dup-path small text-muted font-monospace mt-1';
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
    label.textContent = 'Keep selected and';
    const removeBtn = document.createElement('button');
    removeBtn.className = 'btn btn-warning btn-sm';
    removeBtn.textContent = 'Remove others from library';
    removeBtn.addEventListener('click', () => actOnOthers(idx, cluster, 'remove', card));
    removeBtn.addEventListener('mouseenter', () => setHoverHighlight(card, 'dup-hover-remove', true));
    removeBtn.addEventListener('mouseleave', () => setHoverHighlight(card, 'dup-hover-remove', false));
    const deleteBtn = document.createElement('button');
    deleteBtn.className = 'btn btn-danger btn-sm';
    deleteBtn.textContent = 'Delete others from disk';
    deleteBtn.addEventListener('click', () => actOnOthers(idx, cluster, 'delete', card));
    deleteBtn.addEventListener('mouseenter', () => setHoverHighlight(card, 'dup-hover-delete', true));
    deleteBtn.addEventListener('mouseleave', () => setHoverHighlight(card, 'dup-hover-delete', false));
    footer.appendChild(label);
    footer.appendChild(removeBtn);
    footer.appendChild(deleteBtn);
    card.appendChild(footer);

    updateRowEmphasis(card);
    return card;
}

function cell(text) {
    const td = document.createElement('td');
    td.textContent = text || '';
    return td;
}

// Title cell. When a cluster's titles disagree (e.g. an AcoustID match where one copy is
// mistagged), each title gets a Rename button to fix it in place.
function titleCell(t, cluster, card) {
    const td = document.createElement('td');
    const span = document.createElement('span');
    span.textContent = t.title || '';
    td.appendChild(span);
    if (cluster.titles_diverge) {
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline-secondary btn-sm ms-2 py-0';
        btn.textContent = 'Rename';
        btn.title = 'Fix this title in place (marks this copy as the keeper)';
        btn.addEventListener('click', () => openRenameModal(t, span, card));
        td.appendChild(btn);
    }
    return td;
}

function openRenameModal(t, titleSpan, card) {
    document.getElementById('renameModal')?.remove();
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'renameModal';
    modal.tabIndex = -1;
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Rename Track</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <label class="form-label" for="renameInput">Title</label>
                    <input type="text" class="form-control" id="renameInput">
                    <div class="form-text">Saving marks this copy as the one to keep.</div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="renameSave">Save</button>
                </div>
            </div>
        </div>`;
    document.body.appendChild(modal);
    const input = modal.querySelector('#renameInput');
    input.value = t.title || '';
    const bsModal = bootstrap.Modal.getOrCreateInstance(modal);
    const submit = () => {
        const newTitle = input.value.trim();
        if (!newTitle) { showToast('Title cannot be empty.', 'danger'); return; }
        saveRename(t, newTitle, titleSpan, card, bsModal);
    };
    modal.querySelector('#renameSave').addEventListener('click', submit);
    input.addEventListener('keydown', e => { if (e.key === 'Enter') submit(); });
    modal.addEventListener('shown.bs.modal', () => { input.focus(); input.select(); });
    bsModal.show();
}

function saveRename(t, newTitle, titleSpan, card, bsModal) {
    fetch('/api/library/rename', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: t.id, title: newTitle })
    })
    .then(r => r.json().then(d => ({ ok: r.ok, d })))
    .then(({ ok, d }) => {
        if (!ok) throw new Error(d.error || 'rename failed');
        t.title = newTitle;
        titleSpan.textContent = newTitle;
        if (d.path) {
            const pathEl = card.querySelector(`tr[data-member-id="${t.id}"] .dup-path`);
            if (pathEl) { pathEl.textContent = d.path; pathEl.title = d.path; }
            t.path = d.path;
        }
        // Editing a title asserts this copy is the correct one — make it the keeper.
        const radio = card.querySelector(`tr[data-member-id="${t.id}"] input[type="radio"]`);
        if (radio) { radio.checked = true; updateRowEmphasis(card); }
        showToast('Renamed; marked as keeper.');
        bsModal.hide();
    })
    .catch(e => showToast('Rename: ' + e.message, 'danger'));
}

// Album cell with a fixed-size, lazy-loaded cover thumbnail. The 36px slot is reserved
// up-front (and on error) so populating art never reflows the table.
function albumCell(t) {
    const td = document.createElement('td');
    const wrap = document.createElement('div');
    wrap.className = 'd-flex align-items-center gap-2';
    const art = document.createElement('img');
    art.className = 'album-art';
    art.width = 36;
    art.height = 36;
    art.loading = 'lazy';
    art.alt = '';
    art.style.cursor = 'zoom-in';
    art.title = 'Click for full-size art';
    art.src = `/api/library/art/${encodeURIComponent(t.id)}`;
    art.addEventListener('click', () => openArtLightbox(t.id));
    art.addEventListener('error', () => {
        const placeholder = document.createElement('div');
        placeholder.className = 'album-art album-art-missing';
        art.replaceWith(placeholder);
    });
    const text = document.createElement('div');
    const name = document.createElement('div');
    name.textContent = t.album || '';
    text.appendChild(name);
    if (t.art_w && t.art_h) {
        const res = document.createElement('div');
        res.className = 'small text-muted';
        res.textContent = `art ${t.art_w}×${t.art_h}`;
        text.appendChild(res);
    }
    wrap.appendChild(art);
    wrap.appendChild(text);
    td.appendChild(wrap);
    return td;
}

// Full-size art lightbox. Shows the original at true 1:1 resolution (scrollable if it
// exceeds the viewport) with a dimensions caption, so resolution can be judged honestly.
function openArtLightbox(trackId) {
    const overlay = document.createElement('div');
    overlay.className = 'art-lightbox';

    const img = document.createElement('img');
    img.className = 'art-lightbox-img';
    img.src = `/api/library/art/${encodeURIComponent(trackId)}?full=1`;
    img.addEventListener('click', e => e.stopPropagation());  // clicks on the art don't dismiss

    const caption = document.createElement('div');
    caption.className = 'art-lightbox-caption';
    caption.textContent = 'Loading…';
    img.addEventListener('load', () => { caption.textContent = `${img.naturalWidth} × ${img.naturalHeight}`; });
    img.addEventListener('error', () => { caption.textContent = 'No full-size art.'; });

    const close = () => { overlay.remove(); document.removeEventListener('keydown', onKey); };
    const onKey = e => { if (e.key === 'Escape') close(); };
    overlay.addEventListener('click', close);
    document.addEventListener('keydown', onKey);

    overlay.appendChild(img);
    overlay.appendChild(caption);
    document.body.appendChild(overlay);
}

// Dim every row except the chosen keeper so "I'm active" reads at a glance.
function updateRowEmphasis(card) {
    card.querySelectorAll('tbody tr').forEach(tr => {
        const radio = tr.querySelector('input[type="radio"]');
        tr.classList.toggle('dup-unselected', !(radio && radio.checked));
    });
}

// On hovering an action button, tint the rows it would affect (the non-keepers).
function setHoverHighlight(card, cls, on) {
    card.querySelectorAll('tbody tr').forEach(tr => {
        const radio = tr.querySelector('input[type="radio"]');
        tr.classList.toggle(cls, on && !(radio && radio.checked));
    });
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
