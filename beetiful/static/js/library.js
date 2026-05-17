document.addEventListener('DOMContentLoaded', () => {
    fetchLibrary();
    debugLibrary();
    
    
    
});

let currentPage = 1;
const itemsPerPage = 20;
let libraryData = [];
let filteredData = [];
let sortOrder = { column: null, direction: 'asc' };
let batchMode = false;
const selectedIds = new Set();
const BATCH_FIELDS = [
    { id: 'batchArtist', label: 'Artist', key: 'artist', tag: 'input' },
    { id: 'batchAlbum', label: 'Album', key: 'album', tag: 'input' },
    { id: 'batchYear', label: 'Year', key: 'year', tag: 'input' },
    { id: 'batchGenre', label: 'Genre', key: 'genre', tag: 'input' },
    { id: 'batchComposer', label: 'Composer', key: 'composer', tag: 'input' },
    { id: 'batchBpm', label: 'BPM', key: 'bpm', tag: 'input' },
    { id: 'batchComments', label: 'Comments', key: 'comments', tag: 'textarea' },
];

function fetchLibrary() {
    fetch('/api/library')
        .then(response => response.json())
        .then(data => {
            if (Array.isArray(data.items)) {
                libraryData = data.items;
                rebuildFilteredData();
                const totalPages = Math.max(1, Math.ceil(filteredData.length / itemsPerPage));
                currentPage = Math.min(currentPage, totalPages);
                showPage(currentPage);
            } else {
                console.error('Unexpected data format:', data);
                document.getElementById('libraryResults').innerHTML = '<tr><td colspan="6">No library data found.</td></tr>';
            }
        })
        .catch(error => {
            console.error('Error fetching library data:', error);
            document.getElementById('libraryResults').innerHTML = '<tr><td colspan="6">Error loading library data.</td></tr>';
        });
}

function rebuildFilteredData() {
    const filterTitle = document.getElementById('filterTitle').value.toLowerCase();
    const filterArtist = document.getElementById('filterArtist').value.toLowerCase();
    const filterAlbum = document.getElementById('filterAlbum').value.toLowerCase();
    const filterGenre = document.getElementById('filterGenre').value.toLowerCase();

    filteredData = libraryData.filter(item => (
        (!filterTitle || item.title.toLowerCase().includes(filterTitle)) &&
        (!filterArtist || item.artist.toLowerCase().includes(filterArtist)) &&
        (!filterAlbum || item.album.toLowerCase().includes(filterAlbum)) &&
        (!filterGenre || item.genre.toLowerCase().includes(filterGenre))
    ));

    if (sortOrder.column !== null) {
        const { column, direction } = sortOrder;
        filteredData.sort((a, b) => {
            const aValue = Object.values(a)[column]?.toLowerCase() || '';
            const bValue = Object.values(b)[column]?.toLowerCase() || '';
            if (aValue < bValue) return direction === 'asc' ? -1 : 1;
            if (aValue > bValue) return direction === 'asc' ? 1 : -1;
            return 0;
        });
    }
}


function showPage(page) {
    const start = (page - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const itemsToDisplay = filteredData.slice(start, end);

    populateLibrary(itemsToDisplay);
    updatePaginationControls();
}


function applyFilters() {
    document.querySelectorAll('th').forEach(th => th.classList.remove('asc', 'desc'));
    sortOrder = { column: null, direction: 'asc' };

    rebuildFilteredData();
    currentPage = 1;
    showPage(currentPage);
}

function clearFilters() {
    
    document.getElementById('filterTitle').value = '';
    document.getElementById('filterArtist').value = '';
    document.getElementById('filterAlbum').value = '';
    document.getElementById('filterGenre').value = '';

    
    applyFilters();
}



document.querySelectorAll('.filter-input').forEach(input => {
    input.addEventListener('input', () => {
        applyFilters();
    });
});
function sortByColumn(column) {
    
    document.querySelectorAll('#tableHeaders th').forEach(th => {
        th.classList.remove('asc', 'desc');
        th.querySelector('.sort-arrow')?.remove(); 
    });

    
    if (sortOrder.column === column) {
        sortOrder.direction = sortOrder.direction === 'asc' ? 'desc' : 'asc';
    } else {
        sortOrder.column = column;
        sortOrder.direction = 'asc';
    }

    
    filteredData.sort((a, b) => {
        const aValue = Object.values(a)[column]?.toLowerCase() || '';
        const bValue = Object.values(b)[column]?.toLowerCase() || '';

        if (aValue < bValue) return sortOrder.direction === 'asc' ? -1 : 1;
        if (aValue > bValue) return sortOrder.direction === 'asc' ? 1 : -1;
        return 0;
    });

    
    const header = document.querySelector(`#tableHeaders th[data-column="${column}"]`);
    header.classList.add(sortOrder.direction); 
    const arrow = document.createElement('span');
    arrow.className = 'sort-arrow';
    arrow.innerHTML = sortOrder.direction === 'asc' ? '▲' : '▼';
    header.appendChild(arrow);

    showPage(currentPage); 
}



function clearFilters() {
    document.getElementById('filterTitle').value = '';
    document.getElementById('filterArtist').value = '';
    document.getElementById('filterAlbum').value = '';
    document.getElementById('filterGenre').value = '';

    
    filteredData = libraryData;
    currentPage = 1;

    
    document.querySelectorAll('th').forEach(th => th.classList.remove('asc', 'desc'));
    sortOrder = { column: null, direction: 'asc' };

    showPage(currentPage);
}




function updatePaginationControls() {
    const totalPages = Math.ceil(filteredData.length / itemsPerPage);
    const paginationControls = document.getElementById('paginationControls');
    paginationControls.innerHTML = '';

    const firstButton = document.createElement('button');
    firstButton.innerText = 'First';
    firstButton.disabled = currentPage === 1;
    firstButton.onclick = () => {
        currentPage = 1;
        showPage(currentPage);
    };
    paginationControls.appendChild(firstButton);

    const prevButton = document.createElement('button');
    prevButton.innerText = 'Previous';
    prevButton.disabled = currentPage === 1;
    prevButton.onclick = () => {
        if (currentPage > 1) {
            currentPage--;
            showPage(currentPage);
        }
    };
    paginationControls.appendChild(prevButton);

    
    const maxButtons = 5;
    const startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
    const endPage = Math.min(totalPages, startPage + maxButtons - 1);

    for (let i = startPage; i <= endPage; i++) {
        const pageButton = document.createElement('button');
        pageButton.innerText = i;
        pageButton.disabled = i === currentPage;
        pageButton.classList.toggle('active-page', i === currentPage); 
        pageButton.onclick = () => {
            currentPage = i;
            showPage(currentPage);
        };
        paginationControls.appendChild(pageButton);
    }

    const nextButton = document.createElement('button');
    nextButton.innerText = 'Next';
    nextButton.disabled = currentPage === totalPages;
    nextButton.onclick = () => {
        if (currentPage < totalPages) {
            currentPage++;
            showPage(currentPage);
        }
    };
    paginationControls.appendChild(nextButton);

    const lastButton = document.createElement('button');
    lastButton.innerText = 'Last';
    lastButton.disabled = currentPage === totalPages;
    lastButton.onclick = () => {
        currentPage = totalPages;
        showPage(currentPage);
    };
    paginationControls.appendChild(lastButton);

    const pageInfo = document.createElement('span');
    pageInfo.innerText = ` Page ${currentPage} of ${totalPages} `;
    paginationControls.appendChild(pageInfo);
}




document.getElementById('tableHeaders').addEventListener('click', (event) => {
    const column = event.target.dataset.column;
    if (column !== undefined) {
        sortByColumn(parseInt(column));
    }
});
function populateLibrary(items) {
    const libraryResults = document.getElementById('libraryResults');
    libraryResults.innerHTML = '';
    renderActionHeader();

    items.forEach(item => {
        const row = document.createElement('tr');

        const actionTd = document.createElement('td');
        if (batchMode) {
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.className = 'form-check-input';
            cb.checked = selectedIds.has(item.id);
            cb.disabled = !item.id;
            cb.addEventListener('change', () => {
                if (cb.checked) selectedIds.add(item.id);
                else selectedIds.delete(item.id);
                updateBatchCount();
                updateSelectAllVisibleState();
            });
            actionTd.appendChild(cb);
        } else {
            const editBtn = document.createElement('button');
            editBtn.className = 'btn btn-primary btn-sm';
            editBtn.textContent = 'Edit';
            editBtn.addEventListener('click', () => editTrack(item));
            actionTd.appendChild(editBtn);
        }
        row.appendChild(actionTd);

        const playTd = document.createElement('td');
        if (item.id) {
            const audio = document.createElement('audio');
            audio.controls = true;
            audio.preload = 'none';
            audio.src = `/api/library/audio/${encodeURIComponent(item.id)}`;
            playTd.appendChild(audio);
        }
        row.appendChild(playTd);

        for (const field of ['title', 'artist', 'album', 'genre']) {
            const td = document.createElement('td');
            td.textContent = item[field] || '';
            row.appendChild(td);
        }

        libraryResults.appendChild(row);
    });
}

function renderActionHeader() {
    const th = document.getElementById('actionHeader');
    if (!th) return;
    th.innerHTML = '';
    if (batchMode) {
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'form-check-input';
        cb.id = 'selectAllVisible';
        cb.title = 'Select all on this page';
        cb.addEventListener('change', () => toggleSelectAllVisible(cb.checked));
        th.appendChild(cb);
        updateSelectAllVisibleState();
    } else {
        th.textContent = 'Edit';
    }
}

function getVisibleIds() {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredData.slice(start, start + itemsPerPage)
        .map(i => i.id)
        .filter(Boolean);
}

function updateSelectAllVisibleState() {
    const cb = document.getElementById('selectAllVisible');
    if (!cb) return;
    const visible = getVisibleIds();
    const checked = visible.filter(id => selectedIds.has(id)).length;
    cb.checked = visible.length > 0 && checked === visible.length;
    cb.indeterminate = checked > 0 && checked < visible.length;
}

function toggleSelectAllVisible(checked) {
    const visible = getVisibleIds();
    if (checked) visible.forEach(id => selectedIds.add(id));
    else visible.forEach(id => selectedIds.delete(id));
    updateBatchCount();
    showPage(currentPage);
}

function toggleBatchMode() {
    batchMode = !batchMode;
    if (!batchMode) selectedIds.clear();
    updateBatchUI();
    showPage(currentPage);
}

function updateBatchUI() {
    const batchBtn = document.getElementById('batchToggle');
    const editBatchBtn = document.getElementById('editBatch');
    const countSpan = document.getElementById('batchCount');
    batchBtn.textContent = batchMode ? 'Exit batch' : 'Batch';
    batchBtn.classList.toggle('btn-outline-light', !batchMode);
    batchBtn.classList.toggle('btn-light', batchMode);
    editBatchBtn.classList.toggle('d-none', !batchMode);
    countSpan.classList.toggle('d-none', !batchMode);
    updateBatchCount();
}

function updateBatchCount() {
    const editBatchBtn = document.getElementById('editBatch');
    const countSpan = document.getElementById('batchCount');
    const n = selectedIds.size;
    countSpan.textContent = `${n} selected`;
    editBatchBtn.disabled = n === 0;
}

function openBatchEditor() {
    if (selectedIds.size === 0) return;
    const editFormContainer = document.getElementById('editFormContainer');
    editFormContainer.innerHTML = '';

    const note = document.createElement('p');
    note.className = 'text-muted small mb-2';
    note.textContent = `Editing ${selectedIds.size} track(s). Leave a field blank to keep it unchanged.`;
    editFormContainer.appendChild(note);

    for (const f of BATCH_FIELDS) {
        const label = document.createElement('label');
        label.textContent = f.label + ': ';
        const ctrl = document.createElement(f.tag);
        if (f.tag === 'input') ctrl.type = 'text';
        ctrl.id = f.id;
        ctrl.className = 'form-control';
        ctrl.value = '';
        label.appendChild(ctrl);
        editFormContainer.appendChild(label);
    }

    const applyBtn = document.createElement('button');
    applyBtn.className = 'btn btn-success mt-2';
    applyBtn.textContent = 'Review & Apply…';
    applyBtn.addEventListener('click', confirmBatchEdit);
    editFormContainer.appendChild(applyBtn);

    document.getElementById('editOffcanvasLabel').textContent = `Batch Edit (${selectedIds.size})`;
    bootstrap.Offcanvas.getOrCreateInstance(document.getElementById('editOffcanvas')).show();
}

function confirmBatchEdit() {
    const updates = {};
    for (const f of BATCH_FIELDS) {
        const v = document.getElementById(f.id).value.trim();
        if (v) updates[f.key] = v;
    }
    if (Object.keys(updates).length === 0) {
        alert('Fill at least one field to apply.');
        return;
    }
    showBatchConfirmation(updates);
}

function showBatchConfirmation(updates) {
    document.getElementById('batchConfirmModal')?.remove();

    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'batchConfirmModal';
    modal.tabIndex = -1;
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Confirm Batch Edit</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p class="mb-2">Apply the following to <strong>${selectedIds.size}</strong> track(s)?</p>
                    <table class="table table-sm table-bordered mb-2"><thead><tr><th>Field</th><th>New value</th></tr></thead><tbody></tbody></table>
                    <p class="text-warning small mb-0">This cannot be undone.</p>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-danger" id="batchConfirmBtn">Apply</button>
                </div>
            </div>
        </div>
    `;

    const tbody = modal.querySelector('tbody');
    for (const [k, v] of Object.entries(updates)) {
        const tr = document.createElement('tr');
        const tdK = document.createElement('td');
        tdK.textContent = k;
        const tdV = document.createElement('td');
        tdV.textContent = v;
        tr.appendChild(tdK);
        tr.appendChild(tdV);
        tbody.appendChild(tr);
    }

    document.body.appendChild(modal);
    modal.querySelector('#batchConfirmBtn').addEventListener('click', () => {
        bootstrap.Modal.getOrCreateInstance(modal).hide();
        runBatchUpdate(updates);
    });
    bootstrap.Modal.getOrCreateInstance(modal).show();
}

function runBatchUpdate(updates) {
    const ids = Array.from(selectedIds);
    const overlay = showBusyOverlay(document.getElementById('editOffcanvas'), `Applying to ${ids.length}…`);
    const controller = new AbortController();
    // Longer ceiling for batches — 60s lets large batches finish.
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    fetch('/api/library/batch-update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids, updates }),
        signal: controller.signal
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ ok, data }) => {
        if (!ok) throw new Error(data.error || 'Batch update failed');
        showToast(data.message || `Updated ${ids.length} track(s).`);
        selectedIds.clear();
        batchMode = false;
        updateBatchUI();
        closeEditForm();
        fetchLibrary();
    })
    .catch(error => {
        if (error.name === 'AbortError') {
            alert('Batch update timed out after 60 seconds. The server may still be processing — refresh to check.');
        } else {
            alert('Error during batch update: ' + error.message);
        }
    })
    .finally(() => {
        clearTimeout(timeoutId);
        overlay.remove();
    });
}

function editTrack(track) {
    document.getElementById('editOffcanvasLabel').textContent = 'Edit Track';
    const editFormContainer = document.getElementById('editFormContainer');
    editFormContainer.innerHTML = '';

    const fields = [
        { id: 'editTitle', label: 'Title', key: 'title', tag: 'input' },
        { id: 'editArtist', label: 'Artist', key: 'artist', tag: 'input' },
        { id: 'editAlbum', label: 'Album', key: 'album', tag: 'input' },
        { id: 'editYear', label: 'Year', key: 'year', tag: 'input' },
        { id: 'editGenre', label: 'Genre', key: 'genre', tag: 'input' },
        { id: 'editComposer', label: 'Composer', key: 'composer', tag: 'input' },
        { id: 'editBpm', label: 'BPM', key: 'bpm', tag: 'input' },
        { id: 'editComments', label: 'Comments', key: 'comments', tag: 'textarea' },
        { id: 'editPath', label: 'Path', key: 'path', tag: 'input', readOnly: true },
    ];

    for (const f of fields) {
        const label = document.createElement('label');
        label.textContent = f.label + ': ';
        const ctrl = document.createElement(f.tag);
        if (f.tag === 'input') ctrl.type = 'text';
        ctrl.id = f.id;
        ctrl.className = 'form-control';
        ctrl.value = track[f.key] || '';
        if (f.readOnly) ctrl.readOnly = true;
        label.appendChild(ctrl);
        editFormContainer.appendChild(label);
    }

    const buttons = [
        { label: 'Save', cls: 'btn btn-success mt-2 me-2', onClick: () => saveTrack(track.title, track.artist, track.album) },
        { label: 'Remove', cls: 'btn btn-warning mt-2 me-2', onClick: () => confirmAction('remove', track.id) },
        { label: 'Delete', cls: 'btn btn-danger mt-2', onClick: () => confirmAction('delete', track.id) },
    ];
    for (const b of buttons) {
        const btn = document.createElement('button');
        btn.className = b.cls;
        btn.textContent = b.label;
        btn.addEventListener('click', b.onClick);
        editFormContainer.appendChild(btn);
    }

    bootstrap.Offcanvas.getOrCreateInstance(document.getElementById('editOffcanvas')).show();
}

function saveTrack(originalTitle, originalArtist, originalAlbum) {
    const updatedTrack = {
        title: document.getElementById('editTitle').value,
        artist: document.getElementById('editArtist').value,
        album: document.getElementById('editAlbum').value,
        year: document.getElementById('editYear').value,
        genre: document.getElementById('editGenre').value,
        composer: document.getElementById('editComposer').value,
        bpm: document.getElementById('editBpm').value,
        comments: document.getElementById('editComments').value,
    };

    const overlay = showBusyOverlay(document.getElementById('editOffcanvas'), 'Saving…');
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    fetch('/api/library/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ originalTitle, originalArtist, originalAlbum, updatedTrack }),
        signal: controller.signal
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ ok, data }) => {
        if (!ok) throw new Error(data.error || 'Update failed');
        showToast(data.message || 'Track updated successfully.');
        fetchLibrary();
    })
    .catch(error => {
        if (error.name === 'AbortError') {
            alert('Save timed out after 30 seconds. The server may still be processing — refresh to check.');
        } else {
            alert('Error updating track: ' + error.message);
        }
    })
    .finally(() => {
        clearTimeout(timeoutId);
        overlay.remove();
    });
}

function showBusyOverlay(target, label) {
    const overlay = document.createElement('div');
    overlay.className = 'busy-overlay';
    const spinner = document.createElement('div');
    spinner.className = 'spinner-border text-light';
    spinner.setAttribute('role', 'status');
    const sr = document.createElement('span');
    sr.className = 'visually-hidden';
    sr.textContent = label || 'Loading…';
    spinner.appendChild(sr);
    overlay.appendChild(spinner);
    target.appendChild(overlay);
    return overlay;
}

function removeTrack(id) {
    if (!confirm('Are you sure you want to remove this track from the library?')) return;
    runDestructive('/api/library/remove', { id }, 'remove');
}

function deleteTrack(id) {
    if (!confirm('Are you sure you want to delete this track? This action cannot be undone.')) return;
    runDestructive('/api/library/delete', { id }, 'delete');
}

function runDestructive(endpoint, body, verb) {
    const busyLabel = verb === 'delete' ? 'Deleting…' : 'Removing…';
    const overlay = showBusyOverlay(document.getElementById('editOffcanvas'), busyLabel);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal
    })
    .then(response => response.json().then(data => ({ ok: response.ok, data })))
    .then(({ ok, data }) => {
        if (!ok) throw new Error(data.error || `${verb} failed`);
        showToast(data.message || `Track ${verb}d successfully.`);
        fetchLibrary();
        closeEditForm();
    })
    .catch(error => {
        if (error.name === 'AbortError') {
            showToast(`${verb.charAt(0).toUpperCase() + verb.slice(1)} timed out after 30 seconds. The server may still be processing — refresh to check.`, 'danger');
        } else {
            showToast(`Error ${verb}ing track: ${error.message}`, 'danger');
        }
    })
    .finally(() => {
        clearTimeout(timeoutId);
        overlay.remove();
    });
}


function closeEditForm() {
    const el = document.getElementById('editOffcanvas');
    if (el) bootstrap.Offcanvas.getOrCreateInstance(el).hide();
}

function showToast(message, variant) {
    const container = document.getElementById('toastContainer');
    if (!container) { console.log(message); return; }
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
    close.setAttribute('aria-label', 'Close');
    flex.appendChild(body);
    flex.appendChild(close);
    toastEl.appendChild(flex);
    container.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
    toast.show();
}



function debugLibrary() {
    fetch('/api/debug_library')
        .then(response => response.json())
        .then(data => {
            console.log('Raw items:', data.raw_items);
            console.log('Parsed items:', data.parsed_items);
        })
        .catch(error => console.error('Error fetching debug data:', error));
}



function confirmAction(action, id) {
    const actionText = action === 'delete' ? 'delete this track? This action cannot be undone.' : 'remove this track from the library?';

    document.getElementById('confirmationModal')?.remove();

    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.id = 'confirmationModal';
    modal.tabIndex = -1;
    modal.setAttribute('aria-labelledby', 'confirmationModalLabel');
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="confirmationModalLabel">Confirm Action</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">Are you sure you want to ${actionText}</div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-danger" id="confirmActionBtn">Confirm</button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    modal.querySelector('#confirmActionBtn').addEventListener('click', () => executeAction(action, id));
    const confirmationModal = new bootstrap.Modal(modal);
    confirmationModal.show();
}

function executeAction(action, id) {
    const endpoint = action === 'delete' ? '/api/library/delete' : '/api/library/remove';
    const modalEl = document.getElementById('confirmationModal');
    if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).hide();
    runDestructive(endpoint, { id }, action);
}