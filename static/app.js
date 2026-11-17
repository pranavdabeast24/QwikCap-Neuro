/* Formbridge: same-origin, dependency-free review workspace. */
let state={schema:[],records:[],activity:[]}, view='queue', selected=null, page=1, search='', filter='all', dirty=false, draft={}, confirmed=new Set(), activeField=null, busy=false, reviewerDraft='';
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function message(text,type='success'){$('#message').className=type;$('#message').textContent=text;}
function setBusy(value) {
  busy = value;
  document.body.setAttribute('aria-busy', String(value));
  document.querySelectorAll('#content, header, aside').forEach(element => {
    element.inert = value;
  });
}
async function request(path, data) {
  if (busy) return;
  setBusy(true);
  message(path === '/api/demo'
    ? 'Processing 10 practice PDFs through rendering and local OCR / text extraction. This can take a minute…'
    : 'Processing locally…', 'loading');
  try {
    const response = await fetch(path, {
      method: data === undefined ? 'GET' : 'POST',
      headers: data === undefined ? {} : {
        'Content-Type': 'application/json',
        'X-CSRF-Token': state.csrfToken || ''
      },
      body: data === undefined ? undefined : JSON.stringify(data)
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.error || 'Request failed');
    state = result;
    TemplateUI.onState(true);
    dirty = false;
    if (!state.records.some(record => record.id === selected)) {
      selected = state.records[0]?.id || null;
    }
    setDraft();
    render();
    message('Workspace updated.');
    return result;
  } catch (error) {
    message(error.message, 'error');
  } finally {
    setBusy(false);
  }
}
function record(){return state.records.find(r=>r.id===selected)}
function setDraft(){const r=record();draft=Object.assign(Object.create(null),r?.values||{});confirmed=new Set(r?.confirmed||[]);reviewerDraft=state.reviewer||'';page=1;activeField=null;}
function hasUnsavedChanges(){return dirty||TemplateUI.isDirty();}
function leave(){return !hasUnsavedChanges()||window.confirm('Discard unsaved review, source field, or spreadsheet assignment changes?');}
function navigate(nextView){if(busy||!leave())return;TemplateUI.discard();view=nextView;dirty=false;setDraft();render();}
function stats(){const total=state.records.length,approved=state.records.filter(r=>r.status==='approved').length;return `<section class="metrics"><div class="metric"><label>TOTAL DOCUMENTS</label><strong>${total}</strong><small>In this workspace</small></div><div class="metric"><label>AWAITING REVIEW</label><strong>${total-approved}</strong><small>Human verification required</small></div><div class="metric approved"><label>APPROVED RECORDS</label><strong>${approved}</strong><small>Eligible after export checks</small></div><div class="metric"><label>SOURCE FIELDS</label><strong>${state.schema.length}</strong><small>Structured data dictionary</small></div></section>`;}
function render(){const titles={queue:'Review queue',spreadsheet:'Spreadsheet preview',mapping:'Source field setup',activity:'Activity'};$('#pageTitle').textContent=titles[view];$('#navCount').textContent=state.records.length;document.querySelectorAll('[data-nav]').forEach(x=>x.classList.toggle('active',x.dataset.nav===view));$('#content').innerHTML=view==='queue'?queue():view==='spreadsheet'?TemplateUI.render():view==='mapping'?mapping():activity();bind();}
function queue(){
  const list=state.records.filter(r=>(filter==='all'||r.status===filter)&&(r.filename+' '+r.id+' '+Object.values(r.values).join(' ')).toLowerCase().includes(search.toLowerCase()));
  const r=record();
  return stats()+`<div class="spreadsheet-entry"><div><strong>Preview your spreadsheet before you export.</strong><p>Connect source fields to Excel or REDCap columns and see every record become a row. Downloads include approved records only.</p></div><button id="openSpreadsheet" class="primary">▦ Open spreadsheet preview →</button></div><div class="toolbar"><h2>Document review <span class="muted">/ ${state.records.length} documents</span></h2><input id="search" aria-label="Search documents" placeholder="⌕ Search documents…" value="${esc(search)}"><select id="filter" aria-label="Filter status"><option value="all" ${filter==='all'?'selected':''}>All statuses</option><option value="review" ${filter==='review'?'selected':''}>Awaiting review</option><option value="approved" ${filter==='approved'?'selected':''}>Approved</option></select><button id="demo">Load sample batch</button></div>`+(state.records.length?`<section class="workbench"><div class="queue"><div class="panel-title">DOCUMENTS <span class="muted">${list.length}</span></div>${list.map(x=>`<button class="record ${x.id===selected?'active':''}" data-record="${esc(x.id)}"><strong>▧ ${esc(x.filename)}</strong><small>${esc(x.values[state.schema[0]?.name]||x.id)}</small><span class="status ${x.status}">${x.status==='approved'?'✓ Approved':'Needs review'}</span></button>`).join('')||'<div class="empty">No matching documents</div>'}</div>${r?preview(r)+review(r):'<div class="empty">Select a document to review.</div>'}</section>`:`<section class="mapping empty"><div class="empty-icon">▧</div><h2>A clear path from paper to data.</h2><p>Import fictional study documents, verify each extracted value, and map the reviewed fields to your spreadsheet columns. Export only the records you have approved.</p><button class="primary" id="emptyDemo">Load 10 sample documents</button><p>Sample PDFs run through the real rendering and OCR pipeline.<br>Supported: PDF, PNG, JPEG and TXT · Up to 12 MB per file</p></section>`);
}
function preview(r){const pages=r.pages||[],p=pages.find(x=>x.page===page)||pages[page-1],url=p?.url||r.previewUrl;let region=activeField&&(r.evidence?.[activeField]?.region||state.schema.find(f=>f.name===activeField)?.region);const highlight=region&&Number(r.evidence?.[activeField]?.page||region.page||1)===page?`<div class="highlight" style="left:${region.x*100}%;top:${region.y*100}%;width:${region.width*100}%;height:${region.height*100}%"></div>`:'';return `<div class="preview"><div class="panel-title">SOURCE DOCUMENT <div class="page-controls"><button id="prevPage" ${page<=1?'disabled':''} aria-label="Previous page">‹</button><span class="muted">${page} / ${pages.length||1}</span><button id="nextPage" ${page>=(pages.length||1)?'disabled':''} aria-label="Next page">›</button></div></div><div class="document-wrap">${url?`<div class="document"><img src="${esc(url)}" alt="Source document page ${page}">${highlight}</div>`:`<div class="no-preview">${esc(r.sourceText||'No page preview available.')}</div>`}</div><div class="source-links"><a href="/api/source/${encodeURIComponent(r.id)}" download>↓ Original source</a><span class="muted">Page ${page}</span></div><details class="ocr"><summary>Processing steps & source text</summary>${(r.pipeline||[]).map(step=>`<p>${esc(step.stage)} · ${esc(step.status)}<br><small>${esc(step.detail)}</small></p>`).join('')}<pre>${esc(r.sourceText||'No OCR text available.')}</pre></details></div>`;}
function review(r){return `<div class="fields"><div class="panel-title">EXTRACTED FIELDS <span class="muted">${confirmed.size} / ${state.schema.length} confirmed</span></div><div class="review-intro">Local extraction suggestions · Compare each value with the source.<br>Confirm all fields, including optional fields, before approval.</div>${issueSummary(r)}<div class="field-list">${state.schema.map(f=>field(f,r)).join('')}</div><div class="review-actions"><label class="reviewer">Reviewer<input id="reviewer" placeholder="Your name or initials" value="${esc(reviewerDraft)}"></label><div class="action-row"><button id="save">Save review</button><button class="primary" id="approve" ${confirmed.size!==state.schema.length?'disabled':''}>✓ Approve record</button></div><div class="evidence">${r.status==='approved'?'Approved record · Editing requires review again.':'Approval validates required fields and confirmed values.'}</div></div></div>`;}
function field(f, r) {
  const value = draft[f.name] ?? '';
  const id = 'field-' + f.name;
  let input;
  if (f.type === 'choice') {
    input = `<select id="${esc(id)}" data-field="${esc(f.name)}"><option value="">Select…</option>${Object.entries(f.choices || {}).map(([code, label]) => `<option value="${esc(code)}" ${value === code ? 'selected' : ''}>${esc(label)} (${esc(code)})</option>`).join('')}</select>`;
  } else if (f.type === 'text') {
    input = `<textarea id="${esc(id)}" data-field="${esc(f.name)}" rows="${f.name === state.schema[0]?.name ? 1 : 3}" maxlength="4000">${esc(value)}</textarea>`;
  } else {
    input = `<input id="${esc(id)}" data-field="${esc(f.name)}" type="${f.type === 'date' ? 'date' : 'number'}" ${f.min !== undefined ? `min="${f.min}"` : ''} ${f.max !== undefined ? `max="${f.max}"` : ''} step="${f.type === 'integer' ? '1' : 'any'}" value="${esc(value)}">`;
  }
  const region = r.evidence?.[f.name]?.region || f.region;
  return `<div class="field"><label for="${esc(id)}">${esc(f.label || f.name)} ${f.required ? '<span class="required">*</span>' : ''}</label><div class="field-row">${input}<button data-confirm="${esc(f.name)}" class="confirm ${confirmed.has(f.name) ? 'done' : ''}" aria-pressed="${confirmed.has(f.name)}">${confirmed.has(f.name) ? '✓ Confirmed' : 'Confirm'}</button></div><div class="evidence"><span>${esc(f.name)} · ${esc(f.type)}${region ? ` · page ${r.evidence?.[f.name]?.page || region.page || 1}` : ''}</span>${region ? `<a href="/api/crop/${encodeURIComponent(r.id)}/${encodeURIComponent(f.name)}" download>Download region</a>` : ''}</div></div>`;
}
let mappingField = null;
function mapping() {
  const source = record();
  const pages = source?.pages || [];
  mappingField = state.schema.some(field => field.name === mappingField) ? mappingField : state.schema[0]?.name;
  const visual = pages.length ? `<section class="region-designer"><div class="region-controls"><label>Target field<select id="regionField">${state.schema.map(field => `<option value="${esc(field.name)}" ${field.name === mappingField ? 'selected' : ''}>${esc(field.label)} (${esc(field.name)})</option>`).join('')}</select></label><label>Source page<select id="regionPage">${pages.map(sourcePage => `<option value="${sourcePage.page}">Page ${sourcePage.page}</option>`).join('')}</select></label></div><p>Source: ${esc(source.filename)}. Drag a rectangle around the answer, then apply the mapping. Match the page orientation and layout before using this region for other documents.</p><div id="regionSurface"><img id="regionImage" src="${esc(pages[0].url)}" alt="Document page for field mapping" draggable="false"><div id="regionBox" hidden></div></div><p id="regionStatus" role="status">Select a field and draw its answer region.</p><button id="clearRegion">Use label matching for this field</button></section>` : '<p class="warnings">Import a fictional PDF or image first to draw field regions. Open its record in the review queue, then return here.</p>';
  return `<section class="mapping"><h2>Set up extraction fields and source regions</h2><p>Import a REDCap data dictionary CSV or a JSON schema. Choose a field and mark its answer area on the document. Applying changes reprocesses documents and requires fresh review. Use Spreadsheet preview to connect these source fields to destination columns.</p><div class="toolbar"><button id="importSchema">Import dictionary</button><button id="sampleSchema">Download schema</button><button id="saveSchema" class="primary">Apply source field setup</button><a class="button" href="/api/export" download>Export field CSV</a></div>${state.schemaWarnings?.length ? `<div class="warnings">${esc(state.schemaWarnings.join('\n'))}</div>` : ''}${visual}<details class="advanced-schema"><summary>Advanced field definitions</summary><label for="schemaEditor">Field schema JSON</label><textarea id="schemaEditor" spellcheck="false">${esc(JSON.stringify(state.schema, null, 2))}</textarea><p>Regions use normalized top-left coordinates. Supported field types are text, integer, number, date, and choice. The first field is the REDCap record identifier.</p></details><button id="reset">Reset workspace</button></section>`;
}
function bindRegionDesigner() {
  const surface = $('#regionSurface');
  if (!surface) return;
  const image = $('#regionImage');
  const box = $('#regionBox');
  const fieldSelect = $('#regionField');
  const pageSelect = $('#regionPage');
  let start = null;
  let current = null;
  function definitions() {
    const raw = JSON.parse($('#schemaEditor').value);
    return Array.isArray(raw) ? raw : raw.fields;
  }
  function show(region) {
    box.hidden = !region;
    if (!region) return;
    Object.assign(box.style, {left: region.x * 100 + '%', top: region.y * 100 + '%', width: region.width * 100 + '%', height: region.height * 100 + '%'});
  }
  function refresh() {
    try {
      const region = definitions().find(field => field.name === fieldSelect.value)?.region;
      show(region && region.page === Number(pageSelect.value) ? region : null);
      $('#regionStatus').textContent = region ? `Saved draft region for ${fieldSelect.value} on page ${region.page}. Apply the mapping to reprocess documents.` : 'This field uses printed label matching. Drag an answer region to change it.';
    } catch {
      show(null);
    }
  }
  function point(event) {
    const rect = surface.getBoundingClientRect();
    return {x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))};
  }
  fieldSelect.onchange = () => {
    mappingField = fieldSelect.value;
    try {
      const field = definitions().find(item => item.name === mappingField);
      if (field?.region && record().pages.some(item => item.page === field.region.page)) {
        pageSelect.value = field.region.page;
      }
    } catch (error) {
      message('Correct the field JSON before selecting a region.', 'error');
    }
    pageSelect.onchange();
  };
  pageSelect.onchange = () => {
    const page = record().pages.find(item => item.page === Number(pageSelect.value));
    if (page) image.src = page.url;
    refresh();
  };
  surface.onpointerdown = event => {
    if (event.button !== 0) return;
    start = point(event);
    current = null;
    surface.setPointerCapture(event.pointerId);
    event.preventDefault();
  };
  surface.onpointermove = event => {
    if (!start) return;
    const end = point(event);
    current = {page: Number(pageSelect.value), x: Math.min(start.x, end.x), y: Math.min(start.y, end.y), width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y)};
    show(current);
  };
  surface.onpointerup = event => {
    if (!start) return;
    start = null;
    if (surface.hasPointerCapture(event.pointerId)) surface.releasePointerCapture(event.pointerId);
    if (!current || current.width < 0.005 || current.height < 0.005) {
      refresh();
      return;
    }
    try {
      const fields = definitions();
      fields.find(field => field.name === fieldSelect.value).region = Object.fromEntries(Object.entries(current).map(([key, value]) => [key, key === 'page' ? value : Number(value.toFixed(6))]));
      $('#schemaEditor').value = JSON.stringify(fields, null, 2);
      dirty = true;
      refresh();
    } catch {
      message('Correct the field JSON before drawing a region.', 'error');
      refresh();
    }
  };
  surface.onpointercancel = () => { start = null; current = null; refresh(); };
  $('#clearRegion').onclick = () => {
    try {
      const fields = definitions();
      delete fields.find(field => field.name === fieldSelect.value).region;
      $('#schemaEditor').value = JSON.stringify(fields, null, 2);
      dirty = true;
      refresh();
    } catch {
      message('Correct the field JSON before changing a region.', 'error');
    }
  };
  fieldSelect.onchange();
}

function activity(){return `<section class="activity"><h2>Workspace activity</h2><p class="muted">Local processing and review history.</p>${state.activity.slice().reverse().map(a=>`<div class="activity-row"><time>${esc(new Date(a.time).toLocaleString())}</time><span>${esc(a.message)}</span></div>`).join('')||'<div class="empty">No activity yet. Import documents to get started.</div>'}</section>`;}
function bind(){
  document.querySelectorAll('[data-record]').forEach(button=>button.onclick=()=>{
    if(busy||!leave())return;
    TemplateUI.discard();selected=button.dataset.record;dirty=false;setDraft();render();
  });
  const on=(id,fn)=>{const element=$('#'+id);if(element)element.onclick=fn;};
  on('demo',loadDemo);on('emptyDemo',loadDemo);on('openSpreadsheet',()=>navigate('spreadsheet'));
  if($('#search'))$('#search').oninput=event=>{
    search=event.target.value;const pos=event.target.selectionStart;
    render();$('#search').focus();$('#search').setSelectionRange(pos,pos);
  };
  if($('#filter'))$('#filter').onchange=event=>{filter=event.target.value;render();};
  bindReview();bindPages();bindRegionDesigner();TemplateUI.bind();
  document.querySelectorAll('a[href="/api/export"]').forEach(link=>link.onclick=guardDownload);
  on('importSchema',()=>{if(leave())$('#schemaFile').click();});
  on('sampleSchema',()=>download('formbridge-schema.json',JSON.stringify(state.schema,null,2),'application/json'));
  on('saveSchema',()=>{try{request('/api/schema',{schema:JSON.parse($('#schemaEditor').value)});}catch(error){message('Invalid JSON: '+error.message,'error');}});
  on('reset',()=>{if(confirm('Remove all documents, review data, spreadsheet mappings and activity from this session?'))request('/api/reset',{});});
  if($('#schemaEditor'))$('#schemaEditor').oninput=()=>dirty=true;
}
function bindPages(){if($('#prevPage'))$('#prevPage').onclick=()=>{page--;$('.preview').outerHTML=preview(record());bindPages();};if($('#nextPage'))$('#nextPage').onclick=()=>{page++;$('.preview').outerHTML=preview(record());bindPages();};}
function validDraft(){return state.schema.every(f=>{const value=String(draft[f.name]??'').trim();if(!value)return !f.required;if(f.type==='choice')return Object.hasOwn(f.choices||{},value);if(f.type==='integer'||f.type==='number'){const n=Number(value);return Number.isFinite(n)&&(f.type!=='integer'||Number.isInteger(n))&&(f.min===undefined||n>=f.min)&&(f.max===undefined||n<=f.max);}if(f.type==='date')return /^\d{4}-\d{2}-\d{2}$/.test(value)&&!Number.isNaN(Date.parse(value));return true;});}
function saveReview(approve){const reviewer=$('#reviewer').value.trim();if(approve&&!reviewer){message('Enter a reviewer name or initials before approval.','error');$('#reviewer').focus();return;}request('/api/record',{id:selected,values:draft,confirmed:[...confirmed],approve,reviewer,expectedRevision:record()?.revision});}
function bindReview(){
 const refresh=()=>{const approve=$('#approve');if(approve)approve.disabled=confirmed.size!==state.schema.length||!validDraft();const title=$('.fields .panel-title .muted');if(title)title.textContent=`${confirmed.size} / ${state.schema.length} confirmed`;};
 if($('#save'))$('#save').onclick=()=>saveReview(false);if($('#approve'))$('#approve').onclick=()=>saveReview(true);
 document.querySelectorAll('[data-field]').forEach(i=>{
  if (i.tagName === 'TEXTAREA') i.value = draft[i.dataset.field] ?? '';
  i.required=!!state.schema.find(f=>f.name===i.dataset.field)?.required;
  i.oninput=()=>{draft[i.dataset.field]=i.value;confirmed.delete(i.dataset.field);dirty=true;const b=document.querySelector(`[data-confirm="${CSS.escape(i.dataset.field)}"]`);b.classList.remove('done');b.textContent='Confirm';b.setAttribute('aria-pressed','false');refresh();};
  i.onfocus=()=>{activeField=i.dataset.field;const evidence=record()?.evidence?.[activeField];const region=evidence?.region||state.schema.find(f=>f.name===activeField)?.region;page=Number(evidence?.page||region?.page||page);const old=$('.preview');if(old){old.outerHTML=preview(record());bindPages();}};
 });
 document.querySelectorAll('[data-confirm]').forEach(b=>b.onclick=()=>{const key=b.dataset.confirm;confirmed.has(key)?confirmed.delete(key):confirmed.add(key);dirty=true;b.classList.toggle('done',confirmed.has(key));b.textContent=confirmed.has(key)?'✓ Confirmed':'Confirm';b.setAttribute('aria-pressed',String(confirmed.has(key)));refresh();});
 if($('#reviewer'))$('#reviewer').oninput=e=>{reviewerDraft=e.target.value;dirty=true;};refresh();
}
async function guardDownload(event){
  event.preventDefault();
  if(busy)return;
  if(hasUnsavedChanges()){message('Save your review, source field setup, or spreadsheet assignments before downloading.','error');return;}
  const href=event.currentTarget.href;
  setBusy(true);
  try{
    const response=await fetch(href);
    if(!response.ok){const error=await response.json();throw Error(error.error||'Download failed.');}
    const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
    link.href=url;link.download=response.headers.get('Content-Disposition')?.match(/filename="?([^";]+)/)?.[1]||(blob.type.includes('csv')?'formbridge-approved.csv':'formbridge-project.json');
    link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(error){message(error.message,'error');}
  finally{setBusy(false);}
}
function issueSummary(r){const issues=[...(r.issues||[]),...(Array.isArray(r.validationErrors)?r.validationErrors:Object.values(r.validationErrors||{}))];return issues.length?`<details class="warnings" open><summary>Review notes (${issues.length})</summary>${issues.map(x=>`<p>${esc(typeof x==='string'?x:JSON.stringify(x))}</p>`).join('')}</details>`:'';}
function loadDemo(){if(leave())request('/api/demo',{});}
function download(name,text,type){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function readBase64(file){
  return new Promise((resolve,reject)=>{
    const reader=new FileReader();
    reader.onload=()=>resolve(String(reader.result).split(',')[1]);
    reader.onerror=()=>reject(Error('Could not read '+file.name+'.'));
    reader.onabort=()=>reject(Error('Reading '+file.name+' was cancelled.'));
    reader.readAsDataURL(file);
  });
}
document.querySelector('a[href="/api/project"]').onclick=guardDownload;
document.querySelectorAll('[data-nav]').forEach(button=>button.onclick=()=>navigate(button.dataset.nav));
$('#uploadBtn').onclick=()=>{if(!busy&&leave())$('#files').click();};
$('#files').onchange=async event=>{
  const files=[...event.target.files];
  event.target.value='';
  if(busy)return;
  for(const file of files){
    if(file.size>12*1024*1024){message(file.name+' exceeds the 12 MB limit.','error');break;}
    try{
      setBusy(true);
      const data=await readBase64(file);
      setBusy(false);
      if(!await request('/api/upload',{filename:file.name,data}))break;
    }catch(error){setBusy(false);message(error.message,'error');break;}
  }
};
$('#loadProject').onclick=()=>{if(!busy&&leave())$('#projectFile').click();};
$('#projectFile').onchange=async event=>{
  const file=event.target.files[0];event.target.value='';
  if(!file||busy)return;
  if(file.size>40*1024*1024){message('The project exceeds the 40 MB limit.','error');return;}
  try{
    setBusy(true);
    const project=JSON.parse(await file.text());
    setBusy(false);
    await request('/api/project',project);
  }catch(error){setBusy(false);message('Could not open project: '+error.message,'error');}
};
$('#schemaFile').onchange=async event=>{
  const file=event.target.files[0];event.target.value='';
  if(!file||busy)return;
  if(file.size>1024*1024){message('The field dictionary exceeds the 1 MiB limit.','error');return;}
  try{
    setBusy(true);
    const text=await file.text();
    setBusy(false);
    await request('/api/schema/import',{filename:file.name,text});
  }catch(error){setBusy(false);message('Could not read field dictionary: '+error.message,'error');}
};
$('#templateFile').onchange=async event=>{
  const file=event.target.files[0];event.target.value='';
  await TemplateUI.importFile(file);
};
window.addEventListener('beforeunload',event=>{if(hasUnsavedChanges()){event.preventDefault();event.returnValue='';}});
request('/api/state');
