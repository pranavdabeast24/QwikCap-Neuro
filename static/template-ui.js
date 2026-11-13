/* Spreadsheet assignments always map a field identity across every record. */
window.TemplateUI = (() => {
  let mappings = Object.create(null);
  let savedMappings = Object.create(null);
  let templateIdentity = '';
  let sampleRecordId = null;
  let mappingReviewed = false;
  let focusedSource = null;
  let suggestionOpen = false;

  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  const copyMappings = object => Object.assign(Object.create(null), object || {});
  const valueAt = (values, key) => values && own(values, key) ? values[key] : '';
  const columns = () => state.template?.columns || [];
  const source = name => state.schema.find(field => field.name === name);
  const sampleRecord = () => state.records.find(item => item.id === sampleRecordId) || state.records[0];
  const sameMappings = (left, right) => {
    const keys = new Set([...Object.keys(left), ...Object.keys(right)]);
    return [...keys].every(key => own(left, key) === own(right, key) && left[key] === right[key]);
  };
  const isDirty = () => !sameMappings(mappings, savedMappings);

  function onState(force = false) {
    const template = state.template;
    const identity = template ? `${template.id}:${template.revision}` : '';
    if (force || identity !== templateIdentity || !isDirty()) {
      templateIdentity = identity;
      mappings = copyMappings(template?.mappings);
      savedMappings = copyMappings(mappings);
      mappingReviewed = false;
      suggestionOpen = false;
    }
    if (!state.records.some(item => item.id === sampleRecordId)) {
      sampleRecordId = state.records[0]?.id || null;
    }
  }

  function discard() {
    mappings = copyMappings(savedMappings);
    mappingReviewed = false;
    suggestionOpen = false;
  }

  function assignmentSummary() {
    const resolved = columns().filter(column => own(mappings, column.name)).length;
    const mapped = columns().filter(column => source(mappings[column.name])).length;
    return {resolved, mapped, blanks: resolved - mapped, total: columns().length};
  }

  function render() {
    const template = state.template;
    return `<section class="template-workspace">
      <div class="template-heading"><div><div class="template-kicker">SPREADSHEET WORKSPACE</div><h2>See your documents become rows.</h2><p>Drag a source field onto a column, or use its dropdown. Each assignment fills that column for every record.</p></div><span class="template-pill">${template ? esc(template.format.toUpperCase()) + ' template' : 'Choose a template'}</span></div>
      ${templateToolbar()}
      ${template ? mappingWorkspace() : emptyTemplate()}
    </section>`;
  }

  function sampleButtons() {
    return `<div class="template-samples" aria-label="Practice templates"><span>Try a sample:</span><button data-template-sample="redcap">REDCap XLSX</button><button data-template-sample="friendly">Intake XLSX · header row 3</button><button data-template-sample="csv">CSV columns</button></div>`;
  }

  function templateToolbar() {
    const template = state.template;
    return `<div class="template-filebar"><div class="template-file-name"><span class="template-file-icon">▦</span><div><strong>${template ? esc(template.name) : 'Your spreadsheet template'}</strong><small>${template ? `${esc(template.sheet || 'CSV')} · Header row ${template.headerRow} · ${template.columns.length} columns` : 'Import .xlsx or .csv · Up to 4 MB · Synthetic data only'}</small></div></div>${template ? '<a id="downloadOriginalTemplate" class="button" href="/api/template/original" download>Blank original</a>' : ''}<button id="importTemplate" class="${template ? '' : 'primary'}">${template ? 'Replace template' : 'Import template'}</button>${template ? '<button id="clearTemplate" class="template-quiet">Remove</button>' : ''}</div>
      ${template ? `<details class="template-setup-details"><summary>Change worksheet, header row, or practice template</summary><div class="template-config"><label>Worksheet<select id="templateSheet" ${template.format === 'csv' ? 'disabled' : ''}>${(template.sheets?.length ? template.sheets : [template.sheet || 'CSV']).map(sheet => `<option value="${esc(sheet)}" ${sheet === template.sheet ? 'selected' : ''}>${esc(sheet)}</option>`).join('')}</select></label><label>Header row<input id="templateHeaderRow" type="number" min="1" max="1000" value="${template.headerRow}"></label><button id="configureTemplate">Apply worksheet / row</button><p>Use the row that contains your destination column names. Changing this resets the assignments.</p></div><details class="template-sample-details"><summary>Use a sample template</summary>${sampleButtons()}</details></details>` : ''}`;
  }

  function emptyTemplate() {
    return `<div class="template-empty"><div class="template-empty-sheet" aria-hidden="true"><div>A</div><div>B</div><div>C</div><strong>record_id</strong><strong>visit_date</strong><strong>age</strong><span>DEMO-001</span><span>2026-10-20</span><span>42</span><span>DEMO-002</span><span>2026-10-21</span><span>37</span></div><h3>Start with the columns you already use.</h3><p>Import a blank Excel or CSV template. You will see the original source, column assignments, and all populated rows together before exporting.</p>${sampleButtons()}${!state.records.length ? '<p class="template-empty-hint">Then import fictional documents, or <button id="templateLoadDemo" class="template-text-button">load the 10-document sample batch</button>.</p>' : `<p class="template-empty-hint">${state.records.length} documents are ready to preview. Individual record approval is still required for export.</p>`}</div>`;
  }

  function mappingWorkspace() {
    return `<div class="template-mapping-top"><div><h3>Connect fields to columns</h3><p>Assignments use the field name, so values stay connected when you change the sample document.</p></div><button id="reviewSuggestions">Review exact-match suggestions</button></div>
      <div id="templateSuggestions"></div>
      <div class="template-mapper"><section class="template-sources" aria-label="Extracted source fields"><div class="template-panel-heading"><h3>1 <span>Source fields</span></h3><span>${state.schema.length} fields</span></div><div id="templateSourcePanel">${sourcePanel()}</div></section><section class="template-destinations" aria-label="Spreadsheet column assignments"><div class="template-panel-heading"><h3>2 <span>Destination columns</span></h3><span>Drop a field here · scroll for more columns</span></div><div id="templateProgress" aria-live="polite">${progressMarkup()}</div><div id="templateColumns" class="template-column-strip">${columnCards()}</div><div id="templateMappingReview">${mappingReview()}</div></section></div>
      <section class="template-result" aria-label="Populated spreadsheet preview"><div class="template-result-heading"><div><h3>3 <span>Populated spreadsheet</span></h3><p>Every record is shown below. Only approved records are included in the downloaded file.</p></div><div id="templatePreviewBadge">${previewBadge()}</div></div><div id="templatePreview">${previewMarkup()}</div><div id="templateExportPanel">${exportPanel()}</div></section>`;
  }

  function sourcePanel() {
    const record = sampleRecord();
    if (!record) return `<div class="template-source-empty"><p>Import fictional documents to see extracted sample values and their source evidence.</p><button id="templateLoadDemo">Load sample documents</button></div>${sourceCards(null)}`;
    const sourcePage = (record.pages || [])[0];
    const image = sourcePage?.url || record.previewUrl;
    return `<label class="template-record-picker">Sample document<select id="templateRecord">${state.records.map(item => `<option value="${esc(item.id)}" ${item.id === record.id ? 'selected' : ''}>${esc(item.filename)} · ${item.status === 'approved' ? 'Approved' : 'Needs review'}</option>`).join('')}</select></label><p class="template-source-note">This changes sample values only. Your column assignments stay in place.</p>${image ? `<div class="template-source-image"><div class="template-source-page"><img id="templateSourceImage" src="${esc(image)}" alt="Original source for ${esc(record.filename)}"><div id="templateEvidenceHighlight" class="highlight" hidden></div></div><span id="templateEvidenceCaption">Hover or focus a field to find its source.</span></div>` : '<p class="template-source-note">No page image available. Source snippets appear with the fields below.</p>'}<div class="template-source-list">${sourceCards(record)}</div>`;
  }

  function sourceSnippet(field, record) {
    if (!record) return '';
    const evidence = record.evidence?.[field.name];
    const snippet = evidence?.snippet || evidence?.text || evidence?.raw || evidence?.sourceText;
    if (typeof snippet === 'string' && snippet.trim()) return snippet.slice(0, 220);
    const value = String(valueAt(record.values, field.name) ?? '').trim();
    const lines = String(record.sourceText || '').split('\n');
    return (lines.find(line => line.toLowerCase().includes((field.label || field.name).toLowerCase())) || (value && lines.find(line => line.includes(value))) || '').slice(0, 220);
  }

  function sourceCards(record) {
    return state.schema.map(field => {
      const evidence = record?.evidence?.[field.name];
      const region = evidence?.region || field.region;
      const snippet = sourceSnippet(field, record);
      const used = Object.values(mappings).filter(value => value === field.name).length;
      const value = String(valueAt(record?.values, field.name) ?? '');
      return `<article class="template-source-card" draggable="false" tabindex="0" data-source-field="${esc(field.name)}" aria-label="${esc(field.label || field.name)}. Field ${esc(field.name)}. Drag to a destination column, or use a column dropdown."><div class="template-source-title"><strong>${esc(field.label || field.name)}</strong><span data-drag-handle aria-hidden="true" title="Drag this field">⠿</span></div><code>${esc(field.name)}</code>${field === state.schema[0] ? '<small class="template-source-role">Record identifier</small>' : ''}<div class="template-source-value">${value ? esc(value) : '<span>No value in this document</span>'}</div>${snippet && snippet.trim() !== value.trim() ? `<blockquote>${esc(snippet)}</blockquote>` : ''}<div class="template-source-evidence"><span data-source-count="${esc(field.name)}">${used ? `${used} column${used === 1 ? '' : 's'}` : 'Not assigned'}</span>${record && region ? `<a href="/api/crop/${encodeURIComponent(record.id)}/${encodeURIComponent(field.name)}" download>Source region · p${evidence?.page || region.page || 1}</a>` : '<span>Label extraction</span>'}</div></article>`;
    }).join('') || '<p class="template-source-note">Add source fields in Source field setup.</p>';
  }

  function progressMarkup() {
    const summary = assignmentSummary();
    const count = summary.total ? Math.round(summary.resolved / summary.total * 100) : 0;
    return `<div class="template-progress-copy"><strong>${summary.resolved} / ${summary.total} columns ${!isDirty() && state.template.confirmed ? 'reviewed' : 'assigned'}</strong><span>${summary.mapped} mapped · ${summary.blanks} left blank · ${summary.total - summary.resolved} unassigned</span></div><div class="template-progress-track" role="progressbar" aria-label="Columns assigned or explicitly left blank" aria-valuemin="0" aria-valuemax="${summary.total}" aria-valuenow="${summary.resolved}"><span style="width:${count}%"></span></div>`;
  }

  function columnCards() {
    return columns().map((column, index) => {
      const assigned = own(mappings, column.name);
      const field = source(mappings[column.name]);
      const blank = assigned && mappings[column.name] === null;
      const value = valueAt(sampleRecord()?.values, field?.name) ?? '';
      return `<div class="template-column ${field ? 'is-mapped' : blank ? 'is-blank' : ''}" data-drop-column="${index}"><div class="template-column-letter">${esc(column.letter)}</div><div class="template-column-name" title="${esc(column.name)}">${esc(column.name)}</div><div class="template-dropzone"><span class="template-drop-icon" aria-hidden="true">${field ? '↳' : blank ? '—' : '+'}</span><span>${field ? 'Connected field' : blank ? 'Explicitly left blank' : 'Drop source field here'}</span>${field ? `<span class="template-mapping-chip">${esc(field.name)}</span>` : ''}</div><label class="template-column-select-label" for="template-column-${index}">Source for ${esc(column.name)}</label><select id="template-column-${index}" data-map-column="${index}"><option value="__unmapped__" ${!assigned ? 'selected' : ''}>Choose source field…</option><option value="__blank__" ${blank ? 'selected' : ''}>— Leave this column blank</option>${state.schema.map(item => `<option value="field:${esc(item.name)}" ${field?.name === item.name ? 'selected' : ''}>${esc(item.label || item.name)} · ${esc(item.name)}</option>`).join('')}</select><div class="template-column-sample"><span>Sample cell</span><strong>${field && String(value) ? esc(String(value)) : '<span class="template-empty-cell">blank</span>'}</strong></div><button class="template-clear-column" data-clear-column="${index}" ${!assigned ? 'disabled' : ''}>Clear assignment</button></div>`;
    }).join('');
  }

  function mappingReview() {
    const summary = assignmentSummary();
    const savedConfirmed = !isDirty() && state.template.confirmed;
    return `<div class="template-mapping-state"><span class="template-pill ${isDirty() ? 'is-dirty' : savedConfirmed ? 'is-confirmed' : ''}">${isDirty() ? 'Unsaved assignments' : savedConfirmed ? '✓ Mapping confirmed' : 'Saved · mapping review needed'}</span><span>${savedConfirmed ? 'Record approvals are managed separately in Review queue.' : 'Review every column, including columns intentionally left blank.'}</span></div><label class="template-confirm-label"><input id="templateReviewed" type="checkbox" ${mappingReviewed ? 'checked' : ''} ${savedConfirmed ? 'disabled' : ''}><span>I reviewed these column assignments and the populated preview. This confirms the mapping; it does not approve any document.</span></label><div class="template-save-actions"><button id="saveTemplateMapping" ${!isDirty() ? 'disabled' : ''}>Save mapping draft</button><button id="confirmTemplateMapping" class="primary" ${!mappingReviewed || summary.resolved !== summary.total || savedConfirmed || clientMappingIssues().length ? 'disabled' : ''}>Save & confirm mapping</button></div>`;
  }

  function draftPreview() {
    return {rows: state.records.map(record => ({id: record.id, recordId: record.id, status: record.status, values: Object.fromEntries(columns().map(column => [column.name, source(mappings[column.name]) ? String(valueAt(record.values, mappings[column.name]) ?? '') : ''])), errors: []})), errors: [], unmapped: columns().filter(column => !own(mappings, column.name)).map(column => column.name)};
  }

  function currentPreview() {
    return !isDirty() && state.templatePreview ? state.templatePreview : draftPreview();
  }

  function previewBadge() {
    return `<span class="template-pill ${isDirty() ? 'is-dirty' : ''}">${isDirty() ? 'Live draft · not saved' : 'Saved server preview'}</span>`;
  }

  function errorText(error) {
    if (typeof error === 'string') return error;
    return error?.message || error?.error || JSON.stringify(error);
  }

  function clientMappingIssues() {
    const issues = [];
    const destinations = new Map();
    columns().forEach(column => {
      const name = mappings[column.name];
      if (!source(name)) return;
      if (!destinations.has(name)) destinations.set(name, []);
      destinations.get(name).push(column.name);
    });
    const identifier = state.schema[0]?.name;
    if (identifier && !destinations.has(identifier)) issues.push(`Map the record identifier field “${identifier}” to a destination column.`);
    destinations.forEach((headers, name) => {
      if (headers.length > 1) issues.push(`Source field “${name}” is assigned to multiple columns: ${headers.join(', ')}. Choose one destination for each source field.`);
    });
    return issues;
  }

  function previewMarkup() {
    const preview = currentPreview();
    const rows = preview.rows || [];
    const issues = [...(state.template.warnings || []), ...(preview.errors || []), ...clientMappingIssues()];
    const rowIssues = rows.flatMap(row => (row.errors || []).map(error => `${row.recordId || row.id}: ${errorText(error)}`));
    return `${issues.length || rowIssues.length ? `<details class="template-preview-issues" open><summary>Template / export notes (${issues.length + rowIssues.length})</summary>${[...issues, ...rowIssues].map(issue => `<p>${esc(errorText(issue))}</p>`).join('')}</details>` : ''}<div class="template-table-wrap"><table class="template-table"><caption class="template-sr-only">Mapped spreadsheet values for all documents. Only approved rows can be exported.</caption><thead><tr class="template-table-letters"><th scope="col">#</th><th scope="col">REVIEW</th>${columns().map(column => `<th scope="col">${esc(column.letter)}</th>`).join('')}</tr><tr><th scope="col">Document</th><th scope="col">Export status</th>${columns().map(column => `<th scope="col">${esc(column.name)}<small>${!own(mappings, column.name) ? 'Unassigned' : mappings[column.name] === null ? 'Left blank' : esc(mappings[column.name])}</small></th>`).join('')}</tr></thead><tbody>${rows.map((row, index) => {
      const id = row.id;
      const record = state.records.find(item => item.id === id);
      const approved = row.status === 'approved';
      return `<tr class="${id === sampleRecord()?.id ? 'template-sample-row' : ''}"><th scope="row"><span>${index + 1}${row.recordId && row.recordId !== id ? ' · ' + esc(row.recordId) : ''}</span><strong title="${esc(record?.filename || id)}">${esc(record?.filename || id)}</strong></th><td><span class="status ${approved ? 'approved' : 'review'}">${approved ? '✓ Approved' : 'Draft · not exported'}</span>${row.errors?.length ? '<small class="template-row-error">Needs correction</small>' : ''}</td>${columns().map(column => `<td class="${!own(mappings, column.name) ? 'template-cell-unmapped' : ''}">${String(valueAt(row.values, column.name) ?? '') ? esc(valueAt(row.values, column.name)) : '<span class="template-empty-cell">—</span>'}</td>`).join('')}</tr>`;
    }).join('') || `<tr><td colspan="${columns().length + 2}" class="template-table-empty">Import fictional documents to see rows populate here. You can set up column assignments first.</td></tr>`}</tbody></table></div>`;
  }

  function exportGate() {
    const summary = assignmentSummary();
    if (isDirty()) return 'Save and confirm your unsaved column assignments before exporting.';
    if (summary.resolved !== summary.total) return 'Assign every column or choose “Leave this column blank,” then confirm the mapping.';
    if (clientMappingIssues().length) return 'Resolve the mapping notes above before confirming or downloading.';
    if (!state.template.confirmed) return 'Review the assignments and populated preview, then save & confirm the mapping.';
    if (!state.records.length) return 'Import documents, verify their fields, and approve records in Review queue.';
    const approved = state.records.filter(record => record.status === 'approved').length;
    if (!approved) return 'Approve at least one record in Review queue. Draft records stay in the preview only.';
    if (!state.templatePreview?.ready) return 'Resolve the template / export notes above before downloading.';
    if (dirty) return 'Save your document review changes before exporting.';
    return '';
  }

  function exportPanel() {
    const gate = exportGate();
    const approved = state.records.filter(record => record.status === 'approved').length;
    return `<div class="template-export-copy"><strong>${gate ? 'Export needs your review' : `${approved} approved record${approved === 1 ? '' : 's'} ready to export`}</strong><p>${esc(gate || 'The download includes approved records only, using the saved and confirmed column assignments.')}</p></div><div class="template-export-actions"><button id="templateReviewRecords">Review documents</button>${state.template.format === 'xlsx' ? `<button class="primary" data-template-export="xlsx" ${gate ? 'disabled' : ''}>↓ Download filled XLSX</button>` : ''}<button class="${state.template.format === 'csv' ? 'primary' : ''}" data-template-export="csv" ${gate ? 'disabled' : ''}>↓ Download filled CSV</button></div>`;
  }

  function refreshMappingAreas() {
    if (view !== 'spreadsheet' || !state.template) return;
    $('#templateProgress').innerHTML = progressMarkup();
    $('#templateColumns').innerHTML = columnCards();
    $('#templateMappingReview').innerHTML = mappingReview();
    $('#templatePreviewBadge').innerHTML = previewBadge();
    $('#templatePreview').innerHTML = previewMarkup();
    $('#templateExportPanel').innerHTML = exportPanel();
    document.querySelectorAll('[data-source-count]').forEach(element => {
      const count = Object.values(mappings).filter(value => value === element.dataset.sourceCount).length;
      element.textContent = count ? `${count} column${count === 1 ? '' : 's'}` : 'Not assigned';
    });
    bindColumns();
    bindMappingActions();
  }

  function assign(index, value, focus = false) {
    if (busy) return;
    const column = columns()[index];
    if (!column || (value !== null && value !== undefined && !source(value))) return;
    if (value === undefined) delete mappings[column.name];
    else mappings[column.name] = value;
    mappingReviewed = false;
    refreshMappingAreas();
    if (focus) $(`#template-column-${index}`)?.focus();
    message(`${column.name}: ${value === undefined ? 'assignment cleared' : value === null ? 'will be left blank' : `mapped to ${value} for every record`}. Save when ready.`);
  }

  function bindColumns() {
    document.querySelectorAll('[data-map-column]').forEach(select => {
      select.onchange = () => assign(Number(select.dataset.mapColumn), select.value === '__unmapped__' ? undefined : select.value === '__blank__' ? null : select.value.slice(6), true);
    });
    document.querySelectorAll('[data-clear-column]').forEach(button => {
      button.onclick = () => assign(Number(button.dataset.clearColumn), undefined, true);
    });
    document.querySelectorAll('[data-drop-column]').forEach(column => {
      column.ondragover = event => { if (busy) return; event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; column.classList.add('is-drag-over'); };
      column.ondragleave = event => { if (!column.contains(event.relatedTarget)) column.classList.remove('is-drag-over'); };
      column.ondrop = event => {
        event.preventDefault();
        column.classList.remove('is-drag-over');
        const fieldName = event.dataTransfer.getData('application/x-formbridge-field') || event.dataTransfer.getData('text/plain');
        if (source(fieldName)) assign(Number(column.dataset.dropColumn), fieldName);
        else message('Drag one of the source field cards onto the destination column.', 'error');
      };
    });
  }

  function showEvidence(fieldName) {
    focusedSource = fieldName;
    const record = sampleRecord();
    const field = source(fieldName);
    const evidence = record?.evidence?.[fieldName];
    const region = evidence?.region || field?.region;
    const image = $('#templateSourceImage');
    const highlight = $('#templateEvidenceHighlight');
    const caption = $('#templateEvidenceCaption');
    if (!image || !highlight) return;
    const page = Number(evidence?.page || region?.page || 1);
    const sourcePage = (record.pages || []).find(item => item.page === page);
    if (sourcePage) image.src = sourcePage.url;
    highlight.hidden = !region;
    if (region) Object.assign(highlight.style, {left: `${region.x * 100}%`, top: `${region.y * 100}%`, width: `${region.width * 100}%`, height: `${region.height * 100}%`});
    caption.textContent = `${field?.label || fieldName}${region ? ` · source region on page ${page}` : ' · label extraction; check source text'}`;
  }

  function bindSource() {
    const picker = $('#templateRecord');
    if (picker) picker.onchange = () => {
      sampleRecordId = picker.value;
      $('#templateSourcePanel').innerHTML = sourcePanel();
      bindSource();
      refreshMappingAreas();
      if (focusedSource) showEvidence(focusedSource);
    };
    document.querySelectorAll('[data-source-field]').forEach(card => {
      let pointer = null;
      let dragLabel = null;
      function cleanupDrag() {
        pointer = null;
        dragLabel?.remove();
        dragLabel = null;
        card.classList.remove('is-dragging');
        document.querySelectorAll('.is-drag-over').forEach(element => element.classList.remove('is-drag-over'));
      }
      card.onpointerdown = event => {
        if (busy || event.button !== 0 || event.target.closest('a,button,input,select')) return;
        if (event.pointerType === 'touch' && !event.target.closest('[data-drag-handle]')) return;
        pointer = {x: event.clientX, y: event.clientY, dragging: false, id: event.pointerId};
        card.setPointerCapture(event.pointerId);
        showEvidence(card.dataset.sourceField);
        event.preventDefault();
      };
      card.onpointermove = event => {
        if (!pointer) return;
        if (!pointer.dragging && Math.hypot(event.clientX - pointer.x, event.clientY - pointer.y) < 6) return;
        pointer.dragging = true;
        event.preventDefault();
        card.classList.add('is-dragging');
        if (!dragLabel) {
          dragLabel = document.createElement('div');
          dragLabel.className = 'template-drag-label';
          dragLabel.textContent = source(card.dataset.sourceField)?.label || card.dataset.sourceField;
          dragLabel.setAttribute('aria-hidden', 'true');
          document.body.appendChild(dragLabel);
        }
        dragLabel.style.left = event.clientX + 12 + 'px';
        dragLabel.style.top = event.clientY + 12 + 'px';
        document.querySelectorAll('.is-drag-over').forEach(element => element.classList.remove('is-drag-over'));
        document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-drop-column]')?.classList.add('is-drag-over');
      };
      card.onpointerup = event => {
        if (!pointer) return;
        const target = pointer.dragging ? document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-drop-column]') : null;
        const wasDragging = pointer.dragging;
        if (card.hasPointerCapture(event.pointerId)) card.releasePointerCapture(event.pointerId);
        cleanupDrag();
        if (target) assign(Number(target.dataset.dropColumn), card.dataset.sourceField);
        else if (wasDragging) message('Drop the field onto a destination column, or use the column dropdown.', 'error');
      };
      card.onpointercancel = cleanupDrag;
      card.onmouseenter = () => showEvidence(card.dataset.sourceField);
      card.onfocusin = () => showEvidence(card.dataset.sourceField);
    });
    const demo = $('#templateLoadDemo');
    if (demo) demo.onclick = loadDemo;
  }

  function suggestionMarkup() {
    const suggestions = Object.entries(state.template?.suggestions || {}).filter(([header, name]) => columns().some(column => column.name === header) && source(name));
    return `<div class="template-suggestion-panel"><h4>Review exact-match suggestions</h4><p>These match a destination header to a source field name or label. Check the proposed assignments before applying them. Existing assignments are kept.</p>${suggestions.length ? `<ul>${suggestions.map(([header, name]) => `<li><strong>${esc(header)}</strong><span>←</span><code>${esc(name)}</code><small>${own(mappings, header) ? 'Already assigned · will keep' : 'Suggested'}</small></li>`).join('')}</ul><button id="applyTemplateSuggestions">Apply suggestions to unassigned columns</button>` : '<p>No exact matches found. Drag a source field or use each column dropdown.</p>'}<button id="closeTemplateSuggestions" class="template-quiet">Close suggestions</button></div>`;
  }

  async function saveMapping(confirmMapping) {
    if (busy) return;
    if (confirmMapping && (!mappingReviewed || assignmentSummary().resolved !== columns().length || clientMappingIssues().length)) return;
    const result = await request('/api/template/mapping', {mappings: {...mappings}, confirmed: confirmMapping, expectedRevision: state.template.revision});
    if (result) message(confirmMapping ? 'Spreadsheet mapping saved and confirmed. Document approvals remain separate.' : 'Spreadsheet mapping draft saved. Review and confirm it before exporting.');
  }

  function bindMappingActions() {
    if ($('#templateReviewed')) $('#templateReviewed').onchange = event => {
      mappingReviewed = event.target.checked;
      $('#confirmTemplateMapping').disabled = !mappingReviewed || assignmentSummary().resolved !== columns().length || (!isDirty() && state.template.confirmed) || !!clientMappingIssues().length;
    };
    if ($('#saveTemplateMapping')) $('#saveTemplateMapping').onclick = () => saveMapping(false);
    if ($('#confirmTemplateMapping')) $('#confirmTemplateMapping').onclick = () => saveMapping(true);
    if ($('#templateReviewRecords')) $('#templateReviewRecords').onclick = () => navigate('queue');
    document.querySelectorAll('[data-template-export]').forEach(button => button.onclick = () => exportTemplate(button.dataset.templateExport));
  }

  function bind() {
    if (view !== 'spreadsheet') return;
    $('#importTemplate').onclick = () => { if (leave()) $('#templateFile').click(); };
    if ($('#downloadOriginalTemplate')) $('#downloadOriginalTemplate').onclick = guardDownload;
    document.querySelectorAll('[data-template-sample]').forEach(button => button.onclick = () => { if (leave()) request('/api/template/sample', {name: button.dataset.templateSample}); });
    if ($('#clearTemplate')) $('#clearTemplate').onclick = () => {
      if (leave() && window.confirm('Remove the spreadsheet template and its column assignments? Your document reviews will remain.')) request('/api/template/clear', {expectedRevision: state.template.revision});
    };
    if ($('#configureTemplate')) $('#configureTemplate').onclick = () => {
      const headerRow = Number($('#templateHeaderRow').value);
      if (!Number.isInteger(headerRow) || headerRow < 1 || headerRow > 1000) { message('Choose a header row between 1 and 1000.', 'error'); return; }
      if (leave()) request('/api/template/configure', {sheet: $('#templateSheet').value, headerRow, expectedRevision: state.template.revision});
    };
    if ($('#reviewSuggestions')) $('#reviewSuggestions').onclick = () => {
      suggestionOpen = !suggestionOpen;
      renderSuggestions();
    };
    renderSuggestions();
    bindSource();
    bindColumns();
    bindMappingActions();
  }

  function renderSuggestions() {
    const panel = $('#templateSuggestions');
    if (!panel) return;
    panel.innerHTML = suggestionOpen ? suggestionMarkup() : '';
    if ($('#closeTemplateSuggestions')) $('#closeTemplateSuggestions').onclick = () => { suggestionOpen = false; renderSuggestions(); };
    if ($('#applyTemplateSuggestions')) $('#applyTemplateSuggestions').onclick = () => {
      let count = 0;
      Object.entries(state.template.suggestions || {}).forEach(([header, name]) => {
        if (!own(mappings, header) && columns().some(column => column.name === header) && source(name)) { mappings[header] = name; count++; }
      });
      mappingReviewed = false;
      refreshMappingAreas();
      renderSuggestions();
      message(count ? `${count} suggested assignments added to the draft. Check the populated rows before confirming.` : 'All suggested columns already have assignments.');
    };
  }

  async function importFile(file) {
    if (!file || busy) return;
    if (!/\.(xlsx|csv)$/i.test(file.name)) { message('Choose an .xlsx or .csv template.', 'error'); return; }
    if (file.size > 4 * 1024 * 1024) { message('The template exceeds the 4 MB limit.', 'error'); return; }
    setBusy(true);
    try {
      const data = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',')[1]);
        reader.onerror = () => reject(Error('Could not read the template file.'));
        reader.onabort = () => reject(Error('Reading the template was cancelled.'));
        reader.readAsDataURL(file);
      });
      setBusy(false);
      const result = await request('/api/template/import', {filename: file.name, data});
      if (result) message('Template imported. Choose the worksheet and header row, then connect the columns.');
    } catch (error) { setBusy(false); message(error.message, 'error'); }
  }

  async function exportTemplate(format) {
    if (busy) return;
    const gate = exportGate();
    if (gate) { message(gate, 'error'); return; }
    setBusy(true);
    try {
      const response = await fetch(`/api/template/export?format=${encodeURIComponent(format)}&expectedRevision=${encodeURIComponent(state.template.revision)}`);
      if (!response.ok) {
        const result = await response.json();
        throw Error(result.error || 'Template export failed.');
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = response.headers.get('Content-Disposition')?.match(/filename="?([^";]+)/)?.[1] || `formbridge-filled.${format}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      message(`Filled ${format.toUpperCase()} downloaded. Only approved records were included.`);
    } catch (error) { message(error.message, 'error'); }
    finally { setBusy(false); }
  }

  return {render, bind, onState, isDirty, discard, importFile};
})();
