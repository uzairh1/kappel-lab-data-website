/* ============================================================
   Kappel Lab Data Website — application logic
   Data source: tries the live REST API first (see /api folder), falls back
   to the static data.json bundled with the site (needed for GitHub Pages,
   which can't run the API server).
   ============================================================ */

// Point this at your deployed API once it's hosted somewhere reachable
// (Render, Railway, Fly.io, a university server, etc). Leave as-is for
// local development against `uvicorn main:app --reload --port 8000`.
const API_BASE = "http://localhost:8000/api";

let PROTEINS = [];
let USING_LIVE_API = false;

async function loadData(){
  try {
    const res = await fetch(`${API_BASE}/proteins?limit=200`, {signal: AbortSignal.timeout(1500)});
    if(!res.ok) throw new Error("API returned " + res.status);
    const payload = await res.json();
    // API returns paginated summaries; fetch full detail for each so the
    // rest of the app (which expects full records) keeps working unchanged.
    const details = await Promise.all(payload.results.map(r =>
      fetch(`${API_BASE}/proteins/${r.uniprot}`).then(res => res.json())
    ));
    PROTEINS = details;
    USING_LIVE_API = true;
    console.log(`Kappel Lab Data Website: loaded ${PROTEINS.length} proteins from live API at ${API_BASE}`);
  } catch (err) {
    console.log("Kappel Lab Data Website: live API unavailable, falling back to static data.json —", err.message);
    const res = await fetch('data.json');
    PROTEINS = await res.json();
    USING_LIVE_API = false;
  }
  init();
}

function init(){
  const badge = document.getElementById("data-source-badge");
  badge.style.display = "inline-block";
  badge.textContent = USING_LIVE_API ? "● live API" : "○ static demo data";
  badge.style.color = USING_LIVE_API ? "var(--teal)" : "var(--faint)";
  buildHeroTrack();
  buildStats();
  buildCondensateChips();
  buildFeatured();
  buildColumnToggles();
  renderResults();
}

/* ============================================================
   NAVIGATION
   ============================================================ */
function showView(name){
  document.querySelectorAll(".view").forEach(v=>v.classList.remove("active"));
  document.getElementById("view-"+name).classList.add("active");
  document.querySelectorAll("nav.links button").forEach(b=>b.classList.remove("active"));
  const navBtn = document.querySelector('nav.links button[data-nav="'+name+'"]');
  if(navBtn) navBtn.classList.add("active");
  window.scrollTo({top:0, behavior:"smooth"});
}
document.querySelectorAll("nav.links button").forEach(btn=>{
  btn.addEventListener("click", ()=>{
    const target = btn.dataset.nav;
    if(target==="browse-anchor" || target==="downloads-anchor" || target==="docs-anchor"){
      showView("home");
      setTimeout(()=>{ document.getElementById(target).scrollIntoView({behavior:"smooth", block:"start"}); }, 60);
    } else {
      showView(target);
    }
  });
});

/* ============================================================
   HOME: signature hero track — one protein's disorder architecture,
   scanning left to right like an active prediction run.
   ============================================================ */
function buildHeroTrack(){
  // pick a visually interesting example: highly disordered + condensate-forming
  const candidates = PROTEINS.filter(p=>p.condensate_forming && p.length > 300);
  const p = candidates.sort((a,b)=> b.disorder_fraction - a.disorder_fraction)[0] || PROTEINS[0];

  document.getElementById("hero-track-label").innerHTML =
    `<b>${p.gene}</b> (${p.uniprot}) — disorder &amp; domain architecture, ${p.length} aa`;

  drawArchitecture("hero-track-svg", p, {H:120, animate:true});
}

/* Shared architecture drawing: folded regions, IDR regions, named domains */
function drawArchitecture(svgId, p, opts={}){
  const svg = document.getElementById(svgId);
  const W = 1116, H = opts.H || 150;
  const trackY = H*0.42, trackH = 26;
  const len = p.length || 1;
  const xScale = x => (x/len) * W;

  let content = "";
  // baseline
  content += `<rect x="0" y="${trackY}" width="${W}" height="${trackH}" rx="4" fill="#EEF1EF" stroke="#D2D9D8"/>`;
  // folded regions
  p.fold_ranges.forEach(([a,b])=>{
    content += `<rect x="${xScale(a).toFixed(1)}" y="${trackY}" width="${(xScale(b)-xScale(a)).toFixed(1)}" height="${trackH}" fill="#3E4A52"/>`;
  });
  // IDR regions
  p.idr_ranges.forEach(([a,b])=>{
    content += `<rect x="${xScale(a).toFixed(1)}" y="${trackY}" width="${(xScale(b)-xScale(a)).toFixed(1)}" height="${trackH}" fill="#C8781E"/>`;
  });
  // domains overlay (violet band above track)
  p.domains.forEach(d=>{
    const x = xScale(d.start), w = Math.max(2, xScale(d.end)-xScale(d.start));
    content += `<rect x="${x.toFixed(1)}" y="${(trackY-12).toFixed(1)}" width="${w.toFixed(1)}" height="8" rx="2" fill="#6B4C9A"/>`;
  });
  // ruler ticks
  const nTicks = 10;
  for(let i=0;i<=nTicks;i++){
    const x = i*(W/nTicks);
    const pos = Math.round((i/nTicks)*len);
    content += `<line x1="${x}" y1="${trackY+trackH+2}" x2="${x}" y2="${trackY+trackH+8}" stroke="#8C949C" stroke-width="1"/>`;
    content += `<text x="${x}" y="${trackY+trackH+22}" font-family="IBM Plex Mono" font-size="9.5" fill="#8C949C" text-anchor="${i===0?'start':(i===nTicks?'end':'middle')}">${pos}</text>`;
  }
  if(opts.animate){
    content += `<line id="${svgId}-cursor" x1="0" y1="${trackY-20}" x2="0" y2="${trackY+trackH+2}" stroke="#14181A" stroke-width="1" stroke-opacity="0.4"/>`;
  }

  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = content;

  if(opts.animate && !window.matchMedia('(prefers-reduced-motion: reduce)').matches){
    let pos = 0;
    function animate(){
      pos = (pos+2.4) % W;
      const cursor = document.getElementById(svgId+"-cursor");
      if(cursor){ cursor.setAttribute("x1", pos); cursor.setAttribute("x2", pos); }
      requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
  }
}

/* ============================================================
   HOME: stats
   ============================================================ */
function buildStats(){
  const n = PROTEINS.length;
  const condN = PROTEINS.filter(p=>p.condensate_forming).length;
  const distinctCond = new Set(PROTEINS.flatMap(p=>p.condensates)).size;
  const meanDisorder = PROTEINS.reduce((s,p)=>s+(p.disorder_fraction||0),0)/n;

  document.getElementById("stats-grid").innerHTML = `
    <div class="stat-cell"><div class="stat-num">${n}</div><div class="stat-label">Curated proteins (pilot release)</div></div>
    <div class="stat-cell"><div class="stat-num">${condN} / ${n}</div><div class="stat-label">Reported condensate-forming</div></div>
    <div class="stat-cell"><div class="stat-num">${distinctCond}</div><div class="stat-label">Distinct condensates cataloged</div></div>
    <div class="stat-cell"><div class="stat-num">${(meanDisorder*100).toFixed(0)}%</div><div class="stat-label">Mean predicted disorder content</div></div>
  `;
}

/* ============================================================
   HOME: condensate chip gallery (click to filter table)
   ============================================================ */
function buildCondensateChips(){
  const counts = {};
  PROTEINS.forEach(p=>{
    p.condensates.forEach(c=>{ counts[c] = (counts[c]||0)+1; });
  });
  const entries = Object.entries(counts).sort((a,b)=>b[1]-a[1]);
  const grid = document.getElementById("condensate-grid");
  grid.innerHTML = entries.map(([name,count])=>{
    const isSynthetic = name.toLowerCase().startsWith("synthetic");
    return `<button class="chip-card ${isSynthetic?'synthetic':''}" onclick="filterByCondensate('${name.replace(/'/g,"\\'")}')">
      ${name} <b>${count}</b>
    </button>`;
  }).join("");
}
function filterByCondensate(name){
  showView("search");
  document.getElementById("filter-search").value = "";
  currentQuery = "";
  currentCondensateFilter = name;
  document.getElementById("condensate-filter-select").value = name;
  renderResults();
}

/* ============================================================
   HOME: featured protein
   ============================================================ */
function buildFeatured(){
  const p = PROTEINS.find(p=>p.gene === "CALD1") ||
            PROTEINS.sort((a,b)=>b.disorder_fraction-a.disorder_fraction)[0];
  document.getElementById("feature-card").innerHTML = `
    <div>
      <div class="eyebrow">Pilot spotlight</div>
      <h3>${p.gene} — ${(p.disorder_fraction*100).toFixed(0)}% predicted disorder, condensate-forming</h3>
      <p>${p.gene} (${p.uniprot}) is predicted to be ${(p.disorder_fraction*100).toFixed(0)}% intrinsically disordered across its ${p.length}-residue dominant isoform, and is reported in ${p.condensates.length} annotated condensate${p.condensates.length===1?'':'s'}${p.condensates.length? ': '+p.condensates.join(', '):''}.</p>
      <button class="btn secondary" onclick="openProteinById('${p.uniprot}')">View full entry →</button>
    </div>
    <div class="feature-meta">
      <div><b>${p.length} aa</b>Sequence length</div>
      <div><b>${p.ppi_partner_count}</b>PPI partners in dataset</div>
      <div><b>${p.condensates.length}</b>Condensates reported</div>
      <div><b>${p.saturation_conc_uM ?? '—'}</b>Csat (µM)</div>
    </div>
  `;
}

/* ============================================================
   COLUMN CONFIG
   ============================================================ */
const COLUMNS = [
  {key:"gene", label:"Gene", locked:true, default:true},
  {key:"uniprot", label:"UniProt ID", locked:true, default:true},
  {key:"isoform", label:"Isoform / variant", default:true},
  {key:"dominant", label:"Dominant isoform", default:true},
  {key:"condensate", label:"Condensate formation", default:true},
  {key:"idr", label:"IDR prediction (% disordered)", default:true},
  {key:"length", label:"Sequence length (aa)", default:false},
  {key:"ppi", label:"PPI partners (in dataset)", default:false},
  {key:"fcr", label:"FCR (net charge/residue)", default:false},
  {key:"ncpr", label:"NCPR", default:false},
  {key:"kappa", label:"κ (charge patterning)", default:false},
  {key:"hydropathy", label:"Mean hydropathy", default:false},
  {key:"pi", label:"Isoelectric point (pI)", default:false},
  {key:"mw", label:"Molecular weight (Da)", default:false},
  {key:"csat", label:"Csat (µM)", default:false},
  {key:"dg", label:"ΔG phase sep. (kT)", default:false},
  {key:"diseases", label:"Disease associations", default:false},
  {key:"rbp", label:"RNA-binding protein", default:false},
  {key:"pathogenic", label:"Pathogenic variants (total)", default:false},
];
let activeColumns = new Set(COLUMNS.filter(c=>c.default).map(c=>c.key));

function buildColumnToggles(){
  const panel = document.getElementById("cols-panel");
  panel.innerHTML = `<h5>Show / hide columns</h5>` + COLUMNS.map(c=>`
    <label class="col-opt ${c.locked?'locked':''}">
      <input type="checkbox" data-col="${c.key}" ${activeColumns.has(c.key)?'checked':''} ${c.locked?'disabled':''}>
      ${c.label}${c.locked?' (always shown)':''}
    </label>
  `).join("");
  panel.querySelectorAll('input[type=checkbox]').forEach(cb=>{
    cb.addEventListener("change", e=>{
      const key = e.target.dataset.col;
      if(e.target.checked) activeColumns.add(key); else activeColumns.delete(key);
      renderResults();
    });
  });
}
document.getElementById("cols-toggle-btn").addEventListener("click", ()=>{
  document.getElementById("cols-panel").classList.toggle("open");
});
document.addEventListener("click", (e)=>{
  const dd = document.getElementById("cols-dropdown");
  if(dd && !dd.contains(e.target)) document.getElementById("cols-panel").classList.remove("open");
});

/* ============================================================
   SEARCH / FILTER STATE
   ============================================================ */
let currentQuery = "";
let currentCondensateFilter = "";
let condensateOnly = "any"; // any | yes | no
let dominantOnly = "any";
let minDisorder = 0;

// populate condensate filter dropdown
function populateCondensateSelect(){
  const sel = document.getElementById("condensate-filter-select");
  const names = Array.from(new Set(PROTEINS.flatMap(p=>p.condensates))).sort();
  sel.innerHTML = `<option value="">Any condensate</option>` + names.map(n=>`<option value="${n}">${n}</option>`).join("");
}

document.getElementById("filter-search").addEventListener("input", e=>{
  currentQuery = e.target.value;
  renderResults();
});
document.getElementById("condensate-forming-select").addEventListener("change", e=>{
  condensateOnly = e.target.value; renderResults();
});
document.getElementById("dominant-select").addEventListener("change", e=>{
  dominantOnly = e.target.value; renderResults();
});
document.getElementById("disorder-range").addEventListener("input", e=>{
  minDisorder = parseInt(e.target.value,10);
  document.getElementById("disorder-range-val").textContent = minDisorder + "%+";
  renderResults();
});

function cellFor(key, p){
  switch(key){
    case "gene": return `<span class="gene-sym">${p.gene}</span>`;
    case "uniprot": return `<span class="uid">${p.uniprot}</span>`;
    case "isoform": return p.isoform_label ? p.isoform_label : `variant ${p.isoform_number}`;
    case "dominant": return p.dominant ? `<span class="badge dominant">Dominant</span>` : `<span class="badge no">Alt.</span>`;
    case "condensate": return p.condensate_forming
        ? `<div class="cond-tags">${p.condensates.slice(0,2).map(c=>`<span class="cond-tag">${c}</span>`).join("")}${p.condensates.length>2?`<span class="cond-tag">+${p.condensates.length-2}</span>`:''}</div>`
        : `<span class="badge no">Not reported</span>`;
    case "idr": {
      const pct = Math.round((p.disorder_fraction||0)*100);
      return `<div class="disorder-bar-cell"><div class="disorder-bar"><i style="width:${pct}%"></i></div><span class="mono" style="font-size:11.5px; color:var(--muted);">${pct}%</span></div>`;
    }
    case "length": return `<span class="mono">${p.length}</span>`;
    case "ppi": return `<span class="mono">${p.ppi_partner_count}</span>`;
    case "fcr": return `<span class="mono">${p.fcr ?? '—'}</span>`;
    case "ncpr": return `<span class="mono">${p.ncpr ?? '—'}</span>`;
    case "kappa": return `<span class="mono">${p.kappa ?? '—'}</span>`;
    case "hydropathy": return `<span class="mono">${p.mean_hydropathy ?? '—'}</span>`;
    case "pi": return `<span class="mono">${p.isoelectric_point ?? '—'}</span>`;
    case "mw": return `<span class="mono">${p.molecular_weight ? p.molecular_weight.toLocaleString() : '—'}</span>`;
    case "csat": return `<span class="mono">${p.saturation_conc_uM ?? '—'}</span>`;
    case "dg": return `<span class="mono">${p.delta_g_kt ?? '—'}</span>`;
    case "diseases": return p.disease_count
        ? `<span class="mono" style="color:var(--muted);">${p.disease_count} associations</span>`
        : `<span class="badge no">None recorded</span>`;
    case "rbp": {
      if(!p.variant_stats) return `<span class="badge no">No data</span>`;
      return p.variant_stats.is_rbp ? `<span class="badge yes">RBP</span>` : `<span class="badge no">No</span>`;
    }
    case "pathogenic": {
      if(!p.variant_stats) return `<span class="mono" style="color:var(--faint);">—</span>`;
      return `<span class="mono">${p.variant_stats.total_pathogenic.toLocaleString()}</span>`;
    }
    default: return "";
  }
}

function renderResults(){
  const q = currentQuery.trim().toLowerCase();
  let filtered = PROTEINS.filter(p=>{
    if(q && !(p.gene.toLowerCase().includes(q) || p.uniprot.toLowerCase().includes(q))) return false;
    if(condensateOnly==="yes" && !p.condensate_forming) return false;
    if(condensateOnly==="no" && p.condensate_forming) return false;
    if(dominantOnly==="yes" && !p.dominant) return false;
    if(dominantOnly==="no" && p.dominant) return false;
    if(currentCondensateFilter && !p.condensates.includes(currentCondensateFilter)) return false;
    if((p.disorder_fraction||0)*100 < minDisorder) return false;
    return true;
  });

  document.getElementById("results-n").textContent = filtered.length;
  document.getElementById("search-title").textContent = q ? `Results for "${currentQuery}"` : (currentCondensateFilter ? `Condensate: ${currentCondensateFilter}` : "All proteins");

  const cols = COLUMNS.filter(c=>activeColumns.has(c.key));
  const thead = document.getElementById("results-thead");
  thead.innerHTML = `<tr>${cols.map(c=>`<th>${c.label}</th>`).join("")}</tr>`;

  const tbody = document.getElementById("results-body");
  tbody.innerHTML = filtered.map(p=>`
    <tr onclick="openProteinById('${p.uniprot}')">
      ${cols.map(c=>`<td>${cellFor(c.key,p)}</td>`).join("")}
    </tr>
  `).join("") || `<tr><td colspan="${cols.length}" style="padding:28px; text-align:center; color:var(--faint);">No proteins match these filters.</td></tr>`;
}

/* ============================================================
   HERO / NAV SEARCH ENTRY POINTS
   ============================================================ */
function runSearch(query){
  currentQuery = query;
  currentCondensateFilter = "";
  document.getElementById("filter-search").value = query;
  showView("search");
  renderResults();
}
document.getElementById("hero-search-btn").addEventListener("click", ()=>{
  runSearch(document.getElementById("hero-search-input").value);
});
document.getElementById("hero-search-input").addEventListener("keydown", e=>{
  if(e.key==="Enter") runSearch(e.target.value);
});
document.getElementById("nav-search-input").addEventListener("keydown", e=>{
  if(e.key==="Enter") runSearch(e.target.value);
});
document.querySelectorAll(".hero-examples button[data-example]").forEach(b=>{
  b.addEventListener("click", ()=>{
    document.getElementById("hero-search-input").value = b.dataset.example;
    runSearch(b.dataset.example);
  });
});
document.getElementById("condensate-filter-select").addEventListener("change", e=>{
  currentCondensateFilter = e.target.value;
  renderResults();
});

/* ============================================================
   DETAIL VIEW
   ============================================================ */
/* ============================================================
   MUTANT VIEW — currently MOCK DATA, structured to match the real schema
   confirmed from variant_table_documentation.xlsx (VariationID, GeneIsoform,
   ProteinPosition, MutatedFrom/To, Germline_Class w/ condition, etc.) so
   swapping in real data later is a data-source change, not a UI rebuild.
   Deterministic per-protein (seeded), not re-randomized on every reload.
   ============================================================ */
const MV_CLASSES = ["Pathogenic","Likely pathogenic","Uncertain significance","Likely benign","Benign"];
const MV_CLASS_COLORS = {
  "Pathogenic":"#B5433A","Likely pathogenic":"#C97B6E",
  "Uncertain significance":"#6B4C9A","Likely benign":"#7FA88A","Benign":"#1D6E63",
};
const MV_CONDITIONS = ["Cardiomyopathy","Long QT syndrome","Neurodevelopmental disorder","Skeletal myopathy","Retinal dystrophy","Hereditary cancer syndrome"];
const MV_SHAPES = ["circle","triangle","square","diamond","star","cross"];
const MV_CONDITION_SHAPE = Object.fromEntries(MV_CONDITIONS.map((c,i)=>[c, MV_SHAPES[i % MV_SHAPES.length]]));

function seededRng(seedStr){
  let h = 0;
  for(let i=0;i<seedStr.length;i++){ h = (h*31 + seedStr.charCodeAt(i)) | 0; }
  let s = Math.abs(h) || 1;
  return function(){ s = (s*16807) % 2147483647; return (s-1)/2147483646; };
}

const MV_CACHE = {};
/* ============================================================
   Real mutation data — lazy-loaded PER ISOFORM, not per protein.
   mutations/{uniprot}/index.json is small (isoform metadata + known
   classifications/conditions, no variant payloads) and fetched immediately.
   mutations/{uniprot}/{isoform_id}.json (the actual variant markers) is
   only fetched for isoforms actually being displayed — dominant on load,
   alternates only when the user expands them. This split exists because
   shipping every isoform's data upfront produced a 131MB single file for
   CTNNA1 (38 isoforms) — well past GitHub's 100MB limit and far more than
   anyone views a protein page needs to download.
   Falls back to mock data (clearly labeled) when no real index exists.
   ============================================================ */
const REAL_INDEX_CACHE = {};
const REAL_ISOFORM_CACHE = {};
let usingRealMutationData = false;

function adaptRealVariant(v){
  return {
    variation_id: v.variation_id, isoform_id: v.isoform_id,
    position: v.position_start, position_end: v.position_end, is_range: v.is_range,
    mutated_from: v.mutated_from, mutated_to: v.mutated_to,
    classification: v.primary_classification || "Uncertain significance",
    condition: v.primary_condition || "Unspecified",
    molecular_consequence: v.molecular_consequence, variant_type: v.variant_type,
    all_classifications: v.all_classifications, n_collapsed_rows: v.n_collapsed_rows,
    isReal: true,
  };
}

async function getMutantViewIndex(p){
  if(p.uniprot in REAL_INDEX_CACHE) return REAL_INDEX_CACHE[p.uniprot];
  try{
    const res = await fetch(`mutations/${p.uniprot}/index.json`);
    if(!res.ok) throw new Error(res.status);
    const idx = await res.json();
    usingRealMutationData = true;
    REAL_INDEX_CACHE[p.uniprot] = idx;
    return idx;
  } catch(err){
    usingRealMutationData = false;
    const mock = getMockMutantData(p);
    // wrap mock into the same index shape, with variants pre-attached per
    // isoform (mock data is small enough that lazy-loading isn't needed)
    const idx = {
      isoforms: mock.isoforms.map(iso => ({...iso, variant_count: mock.variants.filter(v=>v.isoform_id===iso.id).length})),
      known_classifications: MV_CLASSES,
      known_conditions: MV_CONDITIONS,
      _mockVariants: mock.variants, // stashed for the mock path in getIsoformVariants
    };
    REAL_INDEX_CACHE[p.uniprot] = idx;
    return idx;
  }
}

async function getIsoformVariants(p, isoformId){
  const cacheKey = `${p.uniprot}::${isoformId}`;
  if(cacheKey in REAL_ISOFORM_CACHE) return REAL_ISOFORM_CACHE[cacheKey];

  if(!usingRealMutationData){
    const idx = await getMutantViewIndex(p); // already cached, just re-reads
    const vs = (idx._mockVariants || []).filter(v=>v.isoform_id===isoformId);
    REAL_ISOFORM_CACHE[cacheKey] = vs;
    return vs;
  }
  try{
    let res = await fetch(`mutations/${p.uniprot}/${isoformId}.json`);
    if(res.status >= 500 && res.status < 600){
      // transient rate-limit/server error under concurrent load — confirmed
      // to happen in practice, worth one retry rather than giving up
      await new Promise(r=>setTimeout(r, 800));
      res = await fetch(`mutations/${p.uniprot}/${isoformId}.json`);
    }
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const vs = data.variants.map(adaptRealVariant);
    REAL_ISOFORM_CACHE[cacheKey] = vs;
    return vs;
  } catch(err){
    console.warn(`Failed to load variants for ${p.uniprot}/${isoformId}:`, err.message);
    REAL_ISOFORM_CACHE[cacheKey] = [];
    return [];
  }
}

function getMockMutantData(p){
  if(MV_CACHE[p.uniprot]) return MV_CACHE[p.uniprot];
  const rng = seededRng(p.uniprot);
  const isoforms = [{ id: `${p.uniprot}-dom`, label: "Dominant isoform", length: p.length, dominant: true }];
  const nAlt = Math.floor(rng()*3); // 0-2 alternative isoforms
  for(let i=0;i<nAlt;i++){
    const delta = 0.6 + rng()*0.7; // 60%-130% of dominant length
    isoforms.push({ id: `${p.uniprot}-alt${i+1}`, label: `Alternative isoform ${i+1}`, length: Math.max(30, Math.round(p.length*delta)), dominant: false });
  }
  const variants = [];
  isoforms.forEach(iso=>{
    const nVar = 6 + Math.floor(rng()*20);
    for(let v=0; v<nVar; v++){
      const pos = 1 + Math.floor(rng()*iso.length);
      const cls = MV_CLASSES[Math.floor(rng()*MV_CLASSES.length)];
      const cond = MV_CONDITIONS[Math.floor(rng()*MV_CONDITIONS.length)];
      const aa = "ACDEFGHIKLMNPQRSTVWY";
      variants.push({
        variation_id: `MOCK-${p.uniprot}-${iso.id}-${v}`,
        isoform_id: iso.id,
        position: pos,
        mutated_from: aa[Math.floor(rng()*aa.length)],
        mutated_to: aa[Math.floor(rng()*aa.length)],
        classification: cls,
        condition: cond,
        molecular_consequence: rng()>0.15 ? "missense_variant" : "nonsense_variant",
        variant_type: "single nucleotide variant",
        in_disorder: rng()>0.6,
        domain_annotation: rng()>0.8 ? "Predicted domain" : null,
        biophysics_shift: {
          fcr_delta: (rng()*0.06 - 0.03).toFixed(3),
          ncpr_delta: (rng()*0.04 - 0.02).toFixed(3),
          hydropathy_delta: (rng()*0.5 - 0.25).toFixed(3),
        },
      });
    }
  });
  MV_CACHE[p.uniprot] = { isoforms, variants };
  return MV_CACHE[p.uniprot];
}

function mvShapeSvg(shape, x, y, size, fill){
  const s = size;
  switch(shape){
    case "triangle": return `<polygon points="${x},${y-s} ${x-s},${y+s*0.7} ${x+s},${y+s*0.7}" fill="${fill}"/>`;
    case "square": return `<rect x="${x-s*0.8}" y="${y-s*0.8}" width="${s*1.6}" height="${s*1.6}" fill="${fill}"/>`;
    case "diamond": return `<polygon points="${x},${y-s} ${x+s},${y} ${x},${y+s} ${x-s},${y}" fill="${fill}"/>`;
    case "star": return `<polygon points="${x},${y-s} ${x+s*0.3},${y-s*0.3} ${x+s},${y-s*0.2} ${x+s*0.4},${y+s*0.2} ${x+s*0.6},${y+s} ${x},${y+s*0.5} ${x-s*0.6},${y+s} ${x-s*0.4},${y+s*0.2} ${x-s},${y-s*0.2} ${x-s*0.3},${y-s*0.3}" fill="${fill}"/>`;
    case "cross": return `<g stroke="${fill}" stroke-width="${s*0.5}"><line x1="${x-s}" y1="${y-s}" x2="${x+s}" y2="${y+s}"/><line x1="${x-s}" y1="${y+s}" x2="${x+s}" y2="${y-s}"/></g>`;
    default: return `<circle cx="${x}" cy="${y}" r="${s}" fill="${fill}"/>`;
  }
}

let mvCurrentProtein = null;
let mvFilters = { dominantOnly: true, classification: "", condition: "" };
let mvExpandedIsoformIds = new Set(); // which non-dominant isoforms have been individually expanded/loaded
let mvZoomState = {}; // { [isoformId]: {start, end} } in real sequence-position units — absent means full-length view
let mvDragState = null; // active drag tracking, or null when not dragging

function mvZoomToCluster(isoId, minPos, maxPos){
  const padding = Math.max(5, Math.round((maxPos - minPos) * 0.15));
  mvZoomState[isoId] = { start: Math.max(0, minPos - padding), end: maxPos + padding };
  renderMutantView(mvCurrentProtein);
}

function openMvClusterList(variants){
  const panel = document.getElementById("mv-detail-panel");
  panel.style.display = "block";
  panel.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
      <h3>${variants.length} variants at position ${variants[0].position}</h3>
      <button class="btn secondary small" onclick="document.getElementById('mv-detail-panel').style.display='none'">Close</button>
    </div>
    <p class="subnote" style="margin-top:6px;">All at the same residue — zooming can't separate these since they share one position. Pick one for full detail.</p>
    <div style="display:flex; flex-direction:column; gap:6px; margin-top:12px;">
      ${variants.map(v => `
        <div class="cond-card" style="cursor:pointer;" onclick='openMvDetail(${JSON.stringify(v).replace(/'/g,"&apos;")})'>
          <div><div class="cname">${v.mutated_from}${v.position}${v.mutated_to}</div><div class="ctype">${v.condition}</div></div>
          <span class="badge ${v.classification==='Pathogenic'||v.classification==='Likely pathogenic' ? 'no':'yes'}">${v.classification}</span>
        </div>
      `).join("")}
    </div>
  `;
  panel.scrollIntoView({behavior:"smooth", block:"nearest"});
}

function expandIsoform(isoformId){
  mvExpandedIsoformIds.add(isoformId);
  renderMutantView(mvCurrentProtein);
}

const MV_TRACK_W = 1040; // fixed viewBox width every track SVG uses — needed to convert screen pixels to sequence position

function mvSvgX(event, svgEl){
  const rect = svgEl.getBoundingClientRect();
  const scale = MV_TRACK_W / rect.width; // rendered CSS width can differ from the viewBox's internal units
  return Math.max(0, Math.min(MV_TRACK_W, (event.clientX - rect.left) * scale));
}

function mvZoomDragStart(event, isoId){
  const svgEl = event.currentTarget;
  mvDragState = { isoId, svgEl, startX: mvSvgX(event, svgEl), currentX: mvSvgX(event, svgEl) };
  const overlay = document.getElementById(`mv-zoom-overlay-${isoId}`);
  if(overlay){ overlay.setAttribute("width", 0); overlay.style.display = "block"; }
}

function mvZoomDragMove(event){
  if(!mvDragState) return;
  const x = mvSvgX(event, mvDragState.svgEl);
  mvDragState.currentX = x;
  const overlay = document.getElementById(`mv-zoom-overlay-${mvDragState.isoId}`);
  if(overlay){
    const x1 = Math.min(mvDragState.startX, x), x2 = Math.max(mvDragState.startX, x);
    overlay.setAttribute("x", x1);
    overlay.setAttribute("width", x2 - x1);
  }
}

function mvZoomDragEnd(event, isoLength){
  if(!mvDragState) return;
  const { isoId, startX, currentX } = mvDragState;
  const overlay = document.getElementById(`mv-zoom-overlay-${isoId}`);
  if(overlay) overlay.style.display = "none";
  const pixelDist = Math.abs(currentX - startX);
  mvDragState = null;
  if(pixelDist < 8) return; // treat as a plain click (e.g. on a marker), not a zoom drag — don't interfere

  // convert the dragged pixel range, within THIS track's current view window,
  // back into real sequence-position units
  const existing = mvZoomState[isoId];
  const viewStart = existing ? existing.start : 0;
  const viewEnd = existing ? existing.end : isoLength;
  const viewSpan = viewEnd - viewStart;
  const scale = viewSpan / MV_TRACK_W;
  const x1 = Math.min(startX, currentX), x2 = Math.max(startX, currentX);
  const newStart = Math.round(viewStart + x1 * scale);
  const newEnd = Math.round(viewStart + x2 * scale);
  if(newEnd - newStart < 5) return; // ignore near-zero-width drags, avoids zooming into nothing

  mvZoomState[isoId] = { start: newStart, end: newEnd };
  renderMutantView(mvCurrentProtein);
}

function mvZoomReset(isoId){
  delete mvZoomState[isoId];
  renderMutantView(mvCurrentProtein);
}

const MV_SEVERITY_RANK = {
  "Pathogenic": 5, "Likely pathogenic": 4, "Oncogenic": 5, "Likely oncogenic": 4,
  "Uncertain significance": 3, "Uncertain risk allele": 3,
  "Likely benign": 2, "Benign": 1,
};
function mvWorstCase(variants){
  return variants.reduce((worst, v) =>
    (MV_SEVERITY_RANK[v.classification] || 0) > (MV_SEVERITY_RANK[worst.classification] || 0) ? v : worst
  , variants[0]);
}

async function renderMutantView(p){
  mvCurrentProtein = p;
  document.getElementById("mv-isoform-list").innerHTML = `<div class="empty-note">Loading mutation data…</div>`;
  const idx = await getMutantViewIndex(p);
  document.getElementById("mv-detail-panel").style.display = "none";

  const badge = document.querySelector(".mock-badge");
  if(badge){
    badge.textContent = usingRealMutationData
      ? "● Real ClinVar-derived data"
      : "⚠ Mock data — pending real dataset from Hoffman2 filter job";
    badge.style.background = usingRealMutationData ? "var(--teal-soft)" : "var(--amber-soft)";
    badge.style.color = usingRealMutationData ? "#13463D" : "#7A4712";
  }

  // filter dropdowns populate fully from the index's lightweight summary —
  // doesn't require loading every isoform's actual variant data
  const classSel = document.getElementById("mv-class-filter");
  classSel.innerHTML = `<option value="">Any</option>` + idx.known_classifications.map(c=>`<option value="${c}">${c}</option>`).join("");
  const condSel = document.getElementById("mv-condition-filter");
  condSel.innerHTML = `<option value="">Any</option>` + idx.known_conditions.map(c=>`<option value="${c}">${c}</option>`).join("");
  classSel.value = mvFilters.classification;
  condSel.value = mvFilters.condition;
  document.getElementById("mv-dominant-only").checked = mvFilters.dominantOnly;

  const isoforms = idx.isoforms;
  const maxLength = Math.max(...isoforms.map(i=>i.length || 1));
  // "Dominant isoform only" now controls which ROWS are listed at all.
  // Among listed rows, only the dominant one (plus anything individually
  // expanded by click) actually has its variant data fetched — this is
  // what fixes "unchecking is slow": showing 38 isoform rows is instant
  // (just index.json labels), loading their variant data is opt-in per row.
  const visibleIsoforms = mvFilters.dominantOnly ? isoforms.filter(i=>i.dominant) : isoforms;
  const isoformsToLoad = visibleIsoforms.filter(i=>i.dominant || mvExpandedIsoformIds.has(i.id));

  document.getElementById("mv-isoform-list").innerHTML = `<div class="empty-note">Loading ${isoformsToLoad.length} isoform track(s)…</div>`;
  const isoVariantsMap = {};
  const BATCH_SIZE = 6;
  for(let i=0; i<isoformsToLoad.length; i+=BATCH_SIZE){
    const batch = isoformsToLoad.slice(i, i+BATCH_SIZE);
    await Promise.all(batch.map(async iso=>{
      isoVariantsMap[iso.id] = await getIsoformVariants(p, iso.id);
    }));
  }

  // dynamic condition -> shape mapping, computed from whatever's actually
  // loaded right now (updates as more isoforms get expanded) — real
  // ClinVar condition strings are arbitrary, can't hardcode like mock did
  const allLoadedVariants = Object.values(isoVariantsMap).flat();
  const conditionCounts = {};
  allLoadedVariants.forEach(v=>{ conditionCounts[v.condition] = (conditionCounts[v.condition]||0)+1; });
  const topConditions = Object.entries(conditionCounts).sort((a,b)=>b[1]-a[1]).slice(0, MV_SHAPES.length-1).map(x=>x[0]);
  const conditionShape = {};
  topConditions.forEach((c,i)=>{ conditionShape[c] = MV_SHAPES[i]; });
  const OTHER_SHAPE = MV_SHAPES[MV_SHAPES.length-1];
  const shapeFor = cond => conditionShape[cond] || OTHER_SHAPE;
  const colorFor = cls => MV_CLASS_COLORS[cls] || "#8C949C"; // unranked/unknown classification -> neutral gray
  const presentClasses = [...new Set(allLoadedVariants.map(v=>v.classification))].sort();

  const listEl = document.getElementById("mv-isoform-list");
  listEl.innerHTML = visibleIsoforms.map(iso=>{
    const isLoaded = iso.id in isoVariantsMap;
    if(!isLoaded){
      // not fetched yet — lightweight placeholder, click to load this
      // isoform's variants specifically (not everything at once)
      return `<div class="mv-isoform-row" style="cursor:pointer;" onclick="expandIsoform('${iso.id.replace(/'/g,"\\'")}')">
        <div class="mv-isoform-head">
          <span><b>${iso.label}</b></span>
          <span>${iso.length ?? '?'} aa &middot; ${iso.variant_count ?? '?'} variant(s) &middot; <span style="color:var(--teal); text-decoration:underline;">click to load</span></span>
        </div>
      </div>`;
    }

    const W = 1040;
    const stemGap = 16;
    const rangeLaneH = 20; // dedicated lane for span/range variants, separate from point stacking

    const zoom = mvZoomState[iso.id];
    const isZoomed = !!zoom;
    const viewStart = zoom ? zoom.start : 0;
    const viewEnd = zoom ? zoom.end : (iso.length || 1);
    const viewSpan = Math.max(1, viewEnd - viewStart);

    const isoVariants = (isoVariantsMap[iso.id] || [])
      .filter(v=> !mvFilters.classification || v.classification===mvFilters.classification)
      .filter(v=> !mvFilters.condition || v.condition===mvFilters.condition)
      .filter(v=> !isZoomed || (v.position <= viewEnd && (v.position_end ?? v.position) >= viewStart)); // only what overlaps the current view
    const pointVariants = isoVariants.filter(v=>!v.is_range);
    const rangeVariants = isoVariants.filter(v=>v.is_range);

    // zoomed: use the full track width for just the selected region (like
    // zooming into a genome browser). Not zoomed: keep the existing
    // relative-isoform-length overview scale, for cross-isoform comparison.
    const scale = isZoomed ? W : ((iso.length||1)/maxLength) * W;
    const posToX = pos => isZoomed ? ((pos - viewStart)/viewSpan)*W : (pos/(iso.length||1))*scale;
    const trackColor = iso.dominant ? "#C8781E" : "#8C949C";

    // Fixed-width histogram bins, not open-ended proximity chaining: chaining
    // alone can merge an entire dense region into ONE cluster spanning most
    // of the track (confirmed in testing — 2217 uniformly-ish spread
    // variants chain into a single blob), which technically stops the
    // overlap but makes clicking it useless (it wouldn't zoom in
    // meaningfully). Fixed bins guarantee bounded cluster width AND no
    // overlap, since bins are evenly spaced by construction.
    const withX = pointVariants.map(v => ({ v, x: posToX(v.position) }));
    const BIN_WIDTH = 20; // px in track SVG units — also roughly the visual size of a cluster marker
    const binMap = {};
    withX.forEach(item=>{
      const binIdx = Math.floor(item.x / BIN_WIDTH);
      (binMap[binIdx] = binMap[binIdx] || []).push(item);
    });
    const buckets = Object.values(binMap);
    const CLUSTER_THRESHOLD = 5; // groups at/above this render as one cluster marker, not N stacked lollipops
    const maxBucketSize = Math.max(1, ...buckets.map(b=>b.length));
    const headroomLevels = Math.min(maxBucketSize, CLUSTER_THRESHOLD) - 1; // clustered buckets only need cluster-marker height, not full stack height

    const trackY = 20 + headroomLevels*stemGap + (rangeVariants.length ? rangeLaneH : 0);
    const trackH = 14;
    const H = trackY + trackH + 28;
    const rangeLaneY = trackY - (rangeVariants.length ? rangeLaneH - 4 : 0);

    let markers = "";
    buckets.forEach(bucket=>{
      bucket.sort((a,b)=>a.v.position-b.v.position);

      if(bucket.length >= CLUSTER_THRESHOLD){
        const worst = mvWorstCase(bucket.map(item=>item.v));
        const color = colorFor(worst.classification);
        const x = bucket.reduce((s,item)=>s+item.x,0) / bucket.length; // average x of the cluster
        const stemTopY = trackY - 10;
        const distinctPositions = new Set(bucket.map(item=>item.v.position));
        const positions = bucket.map(item=>item.v.position);
        const minPos = Math.min(...positions), maxPos = Math.max(...positions);
        const clickAction = distinctPositions.size > 1
          ? `mvZoomToCluster('${iso.id}', ${minPos}, ${maxPos})`
          : `openMvClusterList(${JSON.stringify(bucket.map(item=>item.v)).replace(/'/g,"&apos;")})`;
        const title = distinctPositions.size > 1
          ? `${bucket.length} variants, positions ${minPos}-${maxPos} — click to zoom in`
          : `${bucket.length} variants at position ${minPos} — click to list`;
        markers += `<g class="mv-marker" onclick="${clickAction}">
          <title>${title}</title>
          <line x1="${x}" y1="${trackY}" x2="${x}" y2="${stemTopY}" stroke="${color}" stroke-width="1.3" stroke-opacity="0.55"/>
          <circle cx="${x}" cy="${stemTopY}" r="12" fill="${color}"/>
          <text x="${x}" y="${stemTopY+4}" font-family="IBM Plex Mono" font-size="10.5" font-weight="600" fill="#fff" text-anchor="middle">${bucket.length}</text>
        </g>`;
        return;
      }

      bucket.forEach((item, level)=>{
        const stemTopY = trackY - 10 - level*stemGap;
        const shape = shapeFor(item.v.condition);
        const color = colorFor(item.v.classification);
        const title = `${item.v.mutated_from}${item.v.position}${item.v.mutated_to} — ${item.v.classification}, ${item.v.condition}`;
        markers += `<g class="mv-marker" onclick='openMvDetail(${JSON.stringify(item.v).replace(/'/g,"&apos;")})'>
          <title>${title}</title>
          <line x1="${item.x}" y1="${trackY}" x2="${item.x}" y2="${stemTopY}" stroke="${color}" stroke-width="1.3" stroke-opacity="0.55"/>
          ${mvShapeSvg(shape, item.x, stemTopY, 6, color)}
        </g>`;
      });
    });

    // range variants — drawn as a highlighted span, not forced into a point
    let rangeMarkers = "";
    rangeVariants.forEach(v=>{
      const x1 = posToX(v.position);
      const x2 = posToX(v.position_end);
      const color = colorFor(v.classification);
      const title = `${v.mutated_from}${v.position}-${v.position_end}${v.mutated_to} (range) — ${v.classification}, ${v.condition}`;
      rangeMarkers += `<g class="mv-marker" onclick='openMvDetail(${JSON.stringify(v).replace(/'/g,"&apos;")})'>
        <title>${title}</title>
        <rect x="${x1}" y="${rangeLaneY}" width="${Math.max(2,x2-x1)}" height="6" rx="2" fill="${color}" fill-opacity="0.7"/>
        <line x1="${x1}" y1="${rangeLaneY-2}" x2="${x1}" y2="${rangeLaneY+8}" stroke="${color}" stroke-width="1.5"/>
        <line x1="${x2}" y1="${rangeLaneY-2}" x2="${x2}" y2="${rangeLaneY+8}" stroke="${color}" stroke-width="1.5"/>
      </g>`;
    });

    let ruler = "";
    const nTicks = 10;
    for(let t=0; t<=nTicks; t++){
      const x = t*(scale/nTicks);
      const pos = isZoomed ? Math.round(viewStart + (t/nTicks)*viewSpan) : Math.round((t/nTicks)*(iso.length||0));
      ruler += `<line x1="${x}" y1="${trackY+trackH+2}" x2="${x}" y2="${trackY+trackH+7}" stroke="#8C949C" stroke-width="1"/>`;
      ruler += `<text x="${x}" y="${trackY+trackH+19}" font-family="IBM Plex Mono" font-size="9.5" fill="#8C949C" text-anchor="${t===0?'start':(t===nTicks?'end':'middle')}">${pos}</text>`;
    }

    const mismatchBadge = iso.dominant_source === "closest_length_inferred"
      ? `<span class="badge no" title="No isoform in the source file exactly matched our verified length — this is the closest available, not a confirmed match" style="margin-left:8px;">⚠ inferred dominant: ${iso.length} aa here vs ${iso.our_known_length} aa on record</span>`
      : "";

    return `<div class="mv-isoform-row ${iso.dominant?'dominant':''}">
      <div class="mv-isoform-head">
        <span><b>${iso.label}</b>${iso.dominant?'<span class="dom-tag">DOMINANT</span>':''}${mismatchBadge}</span>
        <span>${iso.length} aa &middot; ${isoVariants.length} variants shown${isZoomed ? ` &middot; zoomed to ${viewStart}-${viewEnd} aa &middot; <a href="javascript:void(0)" onclick="mvZoomReset('${iso.id}')" style="color:var(--teal); text-decoration:underline;">reset</a>` : ''}</span>
      </div>
      <svg class="mv-track-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMinYMax meet"
           style="cursor:crosshair;"
           onmousedown="mvZoomDragStart(event,'${iso.id}')" onmousemove="mvZoomDragMove(event)"
           onmouseup="mvZoomDragEnd(event, ${iso.length})" onmouseleave="mvZoomDragEnd(event, ${iso.length})"
           ondblclick="mvZoomReset('${iso.id}')" title="Drag to zoom into a region · double-click to reset">
        <rect x="0" y="${trackY}" width="${scale}" height="${trackH}" rx="3" fill="${trackColor}" fill-opacity="0.18" stroke="${trackColor}"/>
        ${ruler}
        ${rangeMarkers}
        ${markers}
        <rect id="mv-zoom-overlay-${iso.id}" x="0" y="0" width="0" height="${H}" fill="#1D6E63" fill-opacity="0.15" style="display:none; pointer-events:none;"/>
      </svg>
    </div>`;
  }).join("");

  // legend — built from what's actually present in this protein's data,
  // not a fixed list (real condition strings are arbitrary, unlike mock)
  document.getElementById("mv-legend").innerHTML = `
    <div class="mv-legend-group">
      <h5>Color — classification</h5>
      ${presentClasses.map(c=>`<div class="mv-legend-item"><span class="swatch" style="background:${colorFor(c)}; border-radius:50%;"></span>${c}</div>`).join("")}
    </div>
    <div class="mv-legend-group">
      <h5>Shape — condition (top ${topConditions.length}, others grouped)</h5>
      ${topConditions.map(c=>{
        const svg = `<svg width="14" height="14" viewBox="-8 -8 16 16">${mvShapeSvg(conditionShape[c],0,0,6,'#3E4A52')}</svg>`;
        return `<div class="mv-legend-item">${svg}${c}</div>`;
      }).join("")}
      <div class="mv-legend-item"><svg width="14" height="14" viewBox="-8 -8 16 16">${mvShapeSvg(OTHER_SHAPE,0,0,6,'#3E4A52')}</svg>Other</div>
    </div>
    <div class="mv-legend-group">
      <h5>Span markers</h5>
      <div class="mv-legend-item"><svg width="24" height="14" viewBox="0 0 24 14"><rect x="2" y="4" width="20" height="6" rx="2" fill="#3E4A52" fill-opacity="0.7"/></svg>Range variant (multi-residue)</div>
    </div>
  `;
}

function openMvDetail(v){
  const panel = document.getElementById("mv-detail-panel");
  panel.style.display = "block";
  const isReal = v.isReal;
  const positionLabel = v.is_range
    ? `${v.mutated_from}${v.position}-${v.position_end}${v.mutated_to} (range)`
    : `${v.mutated_from}${v.position}${v.mutated_to}`;

  let extraSection = "";
  if(isReal && v.all_classifications && v.all_classifications.length){
    extraSection = `
      <span style="display:block; font-size:11px; color:var(--faint); font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.04em; margin:14px 0 8px;">
        All classification records (${v.all_classifications.length}${v.n_collapsed_rows>1 ? `, from ${v.n_collapsed_rows} source rows` : ''})
      </span>
      <div style="display:flex; flex-direction:column; gap:8px;">
        ${v.all_classifications.map(e=>`
          <div style="border:1px solid var(--line); border-radius:7px; padding:8px 10px; font-size:12px;">
            <div><b>${e.classification || '—'}</b> <span class="mono" style="color:var(--faint);">${e.scheme}</span></div>
            <div style="color:var(--muted); margin-top:2px;">${e.condition || 'Unspecified condition'}</div>
            <div style="color:var(--faint); font-size:11px; margin-top:2px;">${e.review_status || ''} ${e.submission_count ? '· '+e.submission_count+' submission(s)' : ''} ${e.date_last_evaluated ? '· '+e.date_last_evaluated : ''}</div>
          </div>
        `).join("")}
      </div>`;
  } else if(!isReal){
    extraSection = `
      <span style="display:block; font-size:11px; color:var(--faint); font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.04em; margin:14px 0 8px;">Biophysical shift (mutant vs. wild-type)</span>
      <div class="kv-list">
        <div><span>ΔFCR</span><b>${v.biophysics_shift.fcr_delta}</b></div>
        <div><span>ΔNCPR</span><b>${v.biophysics_shift.ncpr_delta}</b></div>
        <div><span>ΔHydropathy</span><b>${v.biophysics_shift.hydropathy_delta}</b></div>
      </div>`;
  }

  panel.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
      <h3>${v.variation_id} <span class="mono" style="font-size:12px; color:var(--faint); font-weight:400;">${isReal ? '' : 'MOCK'}</span></h3>
      <button class="btn secondary small" onclick="document.getElementById('mv-detail-panel').style.display='none'">Close</button>
    </div>
    <div class="kv-list" style="margin-top:10px;">
      <div><span>Position</span><b>${positionLabel}</b></div>
      <div><span>Classification (worst-case)</span><b>${v.classification}</b></div>
      <div><span>Condition</span><b>${v.condition}</b></div>
      <div><span>Molecular consequence</span><b>${v.molecular_consequence || '—'}</b></div>
      <div><span>Variant type</span><b>${v.variant_type || '—'}</b></div>
      <div><span>Isoform</span><b>${v.isoform_id}</b></div>
      ${!isReal ? `<div><span>In disordered region</span><b>${v.in_disorder ? 'Yes' : 'No'}</b></div><div><span>Domain</span><b>${v.domain_annotation || 'None'}</b></div>` : ''}
    </div>
    ${extraSection}
    ${!isReal ? `<p class="subnote" style="margin-top:12px;">This is synthetic placeholder data for UI development, generated deterministically per protein — not a real ClinVar record.</p>` : ''}
  `;
  panel.scrollIntoView({behavior:"smooth", block:"nearest"});
}

document.getElementById("mv-dominant-only").addEventListener("change", e=>{
  mvFilters.dominantOnly = e.target.checked;
  if(mvCurrentProtein) renderMutantView(mvCurrentProtein);
});
document.getElementById("mv-class-filter").addEventListener("change", e=>{
  mvFilters.classification = e.target.value;
  if(mvCurrentProtein) renderMutantView(mvCurrentProtein);
});
document.getElementById("mv-condition-filter").addEventListener("change", e=>{
  mvFilters.condition = e.target.value;
  if(mvCurrentProtein) renderMutantView(mvCurrentProtein);
});

function openProteinById(uniprot){
  const p = PROTEINS.find(p=>p.uniprot===uniprot);
  if(!p) return;
  showView("detail");

  document.getElementById("d-gene").textContent = p.gene;
  document.getElementById("d-uniprot").textContent = p.uniprot;
  document.getElementById("d-eyebrow").textContent = p.dominant ? "Dominant isoform" : "Alternative isoform";
  document.getElementById("d-meta").textContent =
    `${p.ensg} · ${p.length} aa · ${p.isoform_label || ('variant '+p.isoform_number)}`;

  document.getElementById("d-kv").innerHTML = `
    <div><span>Gene</span><b>${p.gene}</b></div>
    <div><span>UniProt</span><b>${p.uniprot}</b></div>
    <div><span>Ensembl gene</span><b>${p.ensg}</b></div>
    <div><span>Isoform / variant</span><b>${p.isoform_label || ('variant '+p.isoform_number)}</b></div>
    <div><span>Dominant isoform</span><b>${p.dominant ? 'Yes' : 'No'}</b></div>
    <div><span>Sequence length</span><b>${p.length} aa</b></div>
    <div><span>Predicted disorder content</span><b>${Math.round((p.disorder_fraction||0)*100)}%</b></div>
    <div><span>PPI partners (in dataset)</span><b>${p.ppi_partner_count}</b></div>
    <div><span>Disease associations</span><b>${p.disease_count}</b></div>
  `;

  document.getElementById("d-variants-panel").innerHTML = buildVariantsPanel(p);

  resetDiseaseTab(p.uniprot);

  drawArchitecture("arch-svg", p, {H:150, animate:false});

  document.getElementById("d-arch-legend").innerHTML = `
    <span><i class="swatch" style="background:#3E4A52"></i> Folded region</span>
    <span><i class="swatch" style="background:#C8781E"></i> Predicted IDR</span>
    <span><i class="swatch" style="background:#6B4C9A"></i> Named domain</span>
  `;

  const condHtml = p.condensates.length
    ? p.condensates.map((c,i)=>{
        const conf = p.condensate_confidence[i] || 0;
        const type = p.condensate_types[i] || '';
        let dots = '';
        for(let d=1;d<=3;d++) dots += `<i class="${d<=conf?'on':''}"></i>`;
        return `<div class="cond-card" data-cond-idx="${i}" style="flex-direction:column; align-items:stretch; gap:8px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div><div class="cname">${c}</div><div class="ctype">${type}</div></div>
            <div class="conf-dots" title="Confidence score ${conf}">${dots}</div>
          </div>
          <div class="cond-tags" data-cond-meta="${i}" style="max-width:none;"></div>
        </div>`;
      }).join("")
    : `<div class="empty-note">No condensate association reported for this protein in the current release.</div>`;
  document.getElementById("d-condensates").innerHTML = condHtml;

  document.getElementById("d-biophysics").innerHTML = `
    <div class="kv-list">
      <div><span>FCR</span><b>${p.fcr ?? '—'}</b></div>
      <div><span>NCPR</span><b>${p.ncpr ?? '—'}</b></div>
      <div><span>κ (kappa)</span><b>${p.kappa ?? '—'}</b></div>
      <div><span>Mean hydropathy</span><b>${p.mean_hydropathy ?? '—'}</b></div>
      <div><span>Isoelectric point</span><b>${p.isoelectric_point ?? '—'}</b></div>
      <div><span>Molecular weight</span><b>${p.molecular_weight ? p.molecular_weight.toLocaleString()+' Da' : '—'}</b></div>
      <div><span>Saturation conc. (Csat)</span><b>${p.saturation_conc_uM ? p.saturation_conc_uM+' µM' : '—'}</b></div>
      <div><span>ΔG of phase separation</span><b>${p.delta_g_kt ?? '—'} kT</b></div>
    </div>
    <div class="subnote">FCR = fraction of charged residues; NCPR = net charge per residue; κ describes charge patterning along the sequence (CIDER/localCIDER conventions). Csat and ΔG are derived from coarse-grained phase-separation simulations, not experimental measurement, unless otherwise cited.</div>
  `;

  document.getElementById("d-files").innerHTML = `
    <div class="dl-row"><div class="dl-name">${p.uniprot}.record.json</div><div style="display:flex; gap:12px; align-items:center;"><span class="dl-size">&lt; 5 KB</span><button class="dl-btn" onclick='downloadRecord("${p.uniprot}")'>Download</button></div></div>
    <div class="dl-row"><div class="dl-name">${p.uniprot}.fasta</div><div style="display:flex; gap:12px; align-items:center;"><span class="dl-size">&lt; 2 KB</span><button class="dl-btn" disabled title="Full sequence export coming with full release">Download</button></div></div>
    <div class="dl-row"><div class="dl-name">condensate_microscopy/${p.uniprot}/</div><div style="display:flex; gap:12px; align-items:center;"><span class="dl-size">est. 40–300 GB</span><button class="dl-btn" disabled title="Planned for full-scale release">Coming soon</button></div></div>
  `;
  document.getElementById("d-uniprot-code").textContent = p.uniprot;

  mvExpandedIsoformIds = new Set();
  mvZoomState = {};
  renderMutantView(p);
  switchTab("mutantview");
  loadDetailTabs(p.uniprot);
}

function downloadRecord(uniprot){
  const p = PROTEINS.find(p=>p.uniprot===uniprot);
  const blob = new Blob([JSON.stringify(p, null, 2)], {type:"application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = uniprot + ".record.json";
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/* ============================================================
   Lazy-loaded per-protein detail files (protein_details/{uniprot}.json) —
   sequence, HGVS, full region-by-region biophysics, domain-type stats,
   patterning params, full PPI lists, GO terms, condensate metadata, and
   gene annotation. One small file per protein (not one giant combined
   file) so opening a protein only downloads that protein's data — this
   scales to many more proteins without penalizing every page load.
   Cached per-uniprot after first fetch. Not wired to the live API yet —
   static-file only for now (see enrich_full_mini_dataset.py).
   ============================================================ */
const PROTEIN_DETAILS_CACHE = {};
let currentDetails = null;

async function loadProteinDetails(uniprot){
  if(uniprot in PROTEIN_DETAILS_CACHE) return PROTEIN_DETAILS_CACHE[uniprot];
  try{
    const res = await fetch(`protein_details/${uniprot}.json`);
    if(!res.ok) throw new Error(res.status);
    PROTEIN_DETAILS_CACHE[uniprot] = await res.json();
  } catch(err){
    console.log(`protein_details/${uniprot}.json unavailable —`, err.message);
    PROTEIN_DETAILS_CACHE[uniprot] = null;
  }
  return PROTEIN_DETAILS_CACHE[uniprot];
}

async function loadDetailTabs(uniprot){
  const d = await loadProteinDetails(uniprot);
  currentDetails = d;
  if(!d){
    ["d-region-biophysics","d-domain-types","d-patterning","d-hgvs","d-full-sequence",
     "d-ppi-body","d-annotation-kv","d-synonyms","d-function-desc","d-subcellular",
     "d-pathways","d-go-cc","d-go-bp","d-homology-kv"].forEach(id=>{
      const el = document.getElementById(id);
      if(el) el.innerHTML = `<span class="empty-note">No extended record for this protein in the current release.</span>`;
    });
    return;
  }

  // --- Biophysics: region comparison table ---
  const regions = d.biophysics_regions;
  const metricLabels = {
    fcr:"FCR", ncpr:"NCPR", kappa:"κ", delta:"δ", delta_max:"δ max",
    isoelectric_point:"pI", molecular_weight:"MW (Da)", mean_net_charge:"Mean net charge",
    mean_hydropathy:"Mean hydropathy", uversky_hydropathy:"Uversky hydropathy", ppii_propensity:"PPII propensity",
    fraction_negative:"Fraction negative", fraction_positive:"Fraction positive",
    fraction_expanding:"Fraction expanding", fraction_disorder_promoting:"Fraction disorder-promoting",
  };
  let regionRows = "";
  for(const [key,label] of Object.entries(metricLabels)){
    const w = regions.whole?.[key], i = regions.idr?.[key], f = regions.fold?.[key];
    regionRows += `<tr><td class="gene-sym" style="font-size:12.5px;">${label}</td>
      <td class="mono">${w ?? '—'}</td><td class="mono">${i ?? '—'}</td><td class="mono">${f ?? '—'}</td></tr>`;
  }
  document.getElementById("d-region-biophysics").innerHTML = `
    <div style="overflow-x:auto;">
    <table class="results-table">
      <thead><tr><th></th><th>Whole protein</th><th>IDR only</th><th>Folded region</th></tr></thead>
      <tbody>${regionRows}</tbody>
    </table>
    </div>`;

  // --- Domain-type biophysics ---
  const dtWrap = document.getElementById("d-domain-types-wrap");
  if(!d.domain_types.length){
    dtWrap.style.display = "none";
  } else {
    dtWrap.style.display = "block";
    document.getElementById("d-domain-types").innerHTML = `
      <div style="overflow-x:auto;">
      <table class="results-table">
        <thead><tr><th>Domain</th><th>Count</th><th>Avg size</th><th>FCR</th><th>NCPR</th><th>κ</th><th>Ω</th></tr></thead>
        <tbody>${d.domain_types.map(dt=>`<tr>
          <td class="gene-sym" style="font-size:12.5px;">${dt.name}</td>
          <td class="mono">${dt.count ?? '—'}</td><td class="mono">${dt.avg_size?.toFixed?.(1) ?? dt.avg_size ?? '—'}</td>
          <td class="mono">${dt.fcr ?? '—'}</td><td class="mono">${dt.ncpr ?? '—'}</td>
          <td class="mono">${dt.kappa ?? '—'}</td><td class="mono">${dt.omega ?? '—'}</td>
        </tr>`).join("")}</tbody>
      </table>
      </div>`;
  }

  // --- Patterning params ---
  const pt = d.patterning;
  document.getElementById("d-patterning").innerHTML = `
    <div class="kv-list">
      <div><span>Mean λ</span><b>${pt.mean_lambda ?? '—'}</b></div>
      <div><span>FARO</span><b>${pt.faro ?? '—'}</b></div>
      <div><span>SHD</span><b>${pt.shd ?? '—'}</b></div>
      <div><span>SCD</span><b>${pt.scd ?? '—'}</b></div>
      <div><span>Ah,ij</span><b>${pt.ah_ij ?? '—'}</b></div>
      <div><span>ν (SVR)</span><b>${pt.nu_svr ?? '—'}</b></div>
      <div><span>Csat</span><b>${pt.saturation_conc_mgml ?? '—'} mg/mL</b></div>
    </div>`;

  // --- Sequence tab ---
  document.getElementById("d-hgvs").innerHTML = `
    <div><span>ENSP</span><b>${d.hgvs.ensp || '—'}</b></div>
    <div><span>ENSP (clean)</span><b>${d.hgvs.ensp_clean || '—'}</b></div>
    <div><span>Unique name</span><b>${d.hgvs.unique_name || '—'}</b></div>
    <div><span>Description</span><b>${d.hgvs.description || '—'}</b></div>
  `;
  document.getElementById("d-full-sequence").textContent = (d.sequence || "").match(/.{1,60}/g)?.join("\n") || "—";

  // --- Interactions tab ---
  const pilotSet = new Set(PROTEINS.map(p=>p.uniprot));
  document.getElementById("d-ppi-count-label").textContent = `(${d.ppi.all_partners.length} total)`;
  function renderPpiRows(filterText){
    const rows = d.ppi.all_partners
      .filter(p => !filterText || p.uniprot.toLowerCase().includes(filterText.toLowerCase()))
      .sort((a,b)=>b.score-a.score)
      .slice(0, 300); // guard against rendering a huge DOM for very high-degree proteins
    document.getElementById("d-ppi-body").innerHTML = rows.map(p=>{
      const inPilot = pilotSet.has(p.uniprot);
      return `<tr ${inPilot? `onclick="openProteinById('${p.uniprot}')" style="cursor:pointer;"`:''}>
        <td class="uid">${p.uniprot}</td><td class="mono">${p.score}</td>
        <td>${inPilot? '<span class="badge yes">Yes — click to view</span>' : '<span class="badge no">No</span>'}</td>
      </tr>`;
    }).join("") || `<tr><td colspan="3" style="text-align:center; color:var(--faint); padding:20px;">No partners match.</td></tr>`;
  }
  renderPpiRows("");
  document.getElementById("ppi-search").oninput = (e)=>renderPpiRows(e.target.value);

  // --- Gene Annotation tab ---
  const ga = d.gene_annotation;
  document.getElementById("d-annotation-kv").innerHTML = `
    <div><span>Approved name</span><b>${ga.approved_name || '—'}</b></div>
    <div><span>Biotype</span><b>${ga.biotype || '—'}</b></div>
    <div><span>Canonical transcript</span><b>${ga.canonical_transcript?.id || '—'}</b></div>
    <div><span>Genomic location</span><b>${ga.genomic_location ? `chr${ga.genomic_location.chromosome}:${ga.genomic_location.start}-${ga.genomic_location.end}` : '—'}</b></div>
    <div><span>Transcript count</span><b>${ga.transcript_ids.length}</b></div>
    <div><span>TSS</span><b>${ga.tss ?? '—'}</b></div>
  `;
  document.getElementById("d-synonyms").innerHTML = ga.synonyms.length
    ? ga.synonyms.map(s=>`<span class="cond-tag">${s.label}</span>`).join("")
    : `<span class="empty-note" style="padding:0;">None recorded</span>`;
  document.getElementById("d-function-desc").innerHTML = ga.function_descriptions.length
    ? ga.function_descriptions.map(f=>`<p style="margin-bottom:10px;">${f}</p>`).join("")
    : `<span class="empty-note" style="padding:0;">No function description available.</span>`;
  document.getElementById("d-subcellular").innerHTML = ga.subcellular_locations.length
    ? ga.subcellular_locations.map(s=>`<span class="cond-tag" style="background:var(--teal-soft); color:#13463D;">${s.location}</span>`).join("")
    : `<span class="empty-note" style="padding:0;">None recorded</span>`;
  document.getElementById("d-pathways").innerHTML = ga.pathways.length
    ? `<div style="overflow-x:auto;"><table class="results-table"><thead><tr><th>Pathway</th><th>Top-level term</th></tr></thead><tbody>${
        ga.pathways.map(p=>`<tr><td style="font-size:12.5px;">${p.pathway}</td><td style="font-size:12px; color:var(--muted);">${p.topLevelTerm}</td></tr>`).join("")
      }</tbody></table></div>`
    : `<span class="empty-note">No annotated Reactome pathways.</span>`;
  document.getElementById("d-go-cc").innerHTML = d.go_terms.cellular_component.length
    ? d.go_terms.cellular_component.map(g=>`<div>${g.description} <span class="mono" style="color:var(--faint); font-size:11px;">${g.id}</span></div>`).join("")
    : `<span class="empty-note" style="padding:0;">None recorded</span>`;
  document.getElementById("d-go-bp").innerHTML = d.go_terms.biological_process.length
    ? d.go_terms.biological_process.map(g=>`<div>${g.description} <span class="mono" style="color:var(--faint); font-size:11px;">${g.id}</span></div>`).join("")
    : `<span class="empty-note" style="padding:0;">None recorded</span>`;
  document.getElementById("d-homology-kv").innerHTML = `
    <div><span>Homologue count</span><b>${ga.homologue_count}</b></div>
    <div><span>Tractable assay hits</span><b>${ga.tractability_summary.length}</b></div>
  `;

  // --- Condensates tab enrichment ---
  augmentCondensateCards(d.condensate_details);
}

function augmentCondensateCards(condensateDetails){
  if(!condensateDetails) return;
  condensateDetails.forEach((meta, i)=>{
    const slot = document.querySelector(`[data-cond-meta="${i}"]`);
    if(!slot) return;
    const bits = [];
    if(meta.species_tax_id) bits.push(`<span class="cond-tag">taxon ${meta.species_tax_id}</span>`);
    if(meta.dna_associated) bits.push(`<span class="cond-tag">DNA: ${meta.dna_associated}</span>`);
    if(meta.rna_associated) bits.push(`<span class="cond-tag">RNA: ${meta.rna_associated}</span>`);
    if(meta.chemical_mods) bits.push(`<span class="cond-tag">C-mods: ${meta.chemical_mods}</span>`);
    if(meta.condensatopathy) bits.push(`<span class="cond-tag" style="background:var(--coral); color:#fff;">Condensatopathy: ${meta.condensatopathy}</span>`);
    slot.innerHTML = bits.join("");
  });
}

/* ============================================================
   DETAIL VIEW: Diseases tab — lazy loaded, filter/sort/paginate.
   Tries the live API's per-protein endpoint (server-side filtering) and
   falls back to the bundled diseases.json (client-side filtering) when
   the API isn't reachable — same fallback pattern as the main dataset.
   ============================================================ */
const DISEASE_DATATYPES = ["affected_pathway","animal_model","genetic_association","known_drug","literature","rna_expression","somatic_mutation"];
const DISEASE_PAGE_SIZE = 20;
let STATIC_DISEASES_ALL = null; // lazy-loaded once, only in fallback mode
let currentDetailUniprot = null;
let diseaseState = {query:"", datatype:"", minScore:0, sort:"score", order:"desc", page:1};

function resetDiseaseTab(uniprot){
  currentDetailUniprot = uniprot;
  diseaseState = {query:"", datatype:"", minScore:0, sort:"score", order:"desc", page:1};
  document.getElementById("disease-search").value = "";
  document.getElementById("disease-datatype-select").value = "";
  document.getElementById("disease-min-score").value = 0;
  document.getElementById("disease-min-score-val").textContent = "0+";
  document.getElementById("disease-sort-select").value = "score";
  document.getElementById("disease-table-wrap").style.display = "none";
  document.getElementById("disease-loading").style.display = "block";
  document.getElementById("disease-loading").textContent = "Loading disease associations…";

  const dtSel = document.getElementById("disease-datatype-select");
  if(dtSel.options.length <= 1){
    DISEASE_DATATYPES.forEach(t=>{
      const opt = document.createElement("option");
      opt.value = t; opt.textContent = t.replace(/_/g," ");
      dtSel.appendChild(opt);
    });
  }
  const p = PROTEINS.find(p=>p.uniprot===uniprot);
  document.getElementById("d-disease-count-label").textContent = p ? `(${p.disease_count} total)` : "";
}

async function loadDiseasePage(){
  const {query, datatype, minScore, sort, order, page} = diseaseState;
  const offset = (page-1)*DISEASE_PAGE_SIZE;

  let results, count;
  if(USING_LIVE_API){
    const params = new URLSearchParams({sort, order, limit:DISEASE_PAGE_SIZE, offset});
    if(query) params.set("q", query);
    if(datatype) params.set("datatype", datatype);
    if(minScore) params.set("min_score", (minScore/100).toFixed(2));
    try{
      const res = await fetch(`${API_BASE}/proteins/${currentDetailUniprot}/diseases?${params}`);
      const payload = await res.json();
      results = payload.results; count = payload.count;
    } catch(err){
      console.log("Disease API call failed, falling back to static file —", err.message);
      results = null;
    }
  }
  if(!USING_LIVE_API || results === null){
    if(!STATIC_DISEASES_ALL){
      const res = await fetch('diseases.json');
      STATIC_DISEASES_ALL = await res.json();
    }
    let all = STATIC_DISEASES_ALL[currentDetailUniprot] || [];
    if(query) all = all.filter(d=>d.disease_id.toLowerCase().includes(query.toLowerCase()));
    if(datatype) all = all.filter(d=>d.datatypes.includes(datatype));
    if(minScore) all = all.filter(d=>d.score >= minScore/100);
    all = [...all].sort((a,b)=>{
      const v = a[sort] > b[sort] ? 1 : (a[sort] < b[sort] ? -1 : 0);
      return order==="desc" ? -v : v;
    });
    count = all.length;
    results = all.slice(offset, offset+DISEASE_PAGE_SIZE);
  }

  document.getElementById("disease-loading").style.display = "none";
  document.getElementById("disease-table-wrap").style.display = "block";
  const tbody = document.getElementById("disease-table-body");
  tbody.innerHTML = results.length ? results.map(d=>`
    <tr>
      <td><a href="https://www.ebi.ac.uk/ols4/search?q=${d.disease_id}" target="_blank" rel="noopener" class="mono" style="font-size:12px;">${d.disease_id}</a></td>
      <td class="mono">${d.score.toFixed(3)}</td>
      <td class="mono">${d.evidence_count}</td>
      <td style="font-size:12px; color:var(--muted);">${d.datatypes.join(", ").replace(/_/g," ")}</td>
    </tr>`).join("") : `<tr><td colspan="4" style="text-align:center; color:var(--faint); padding:20px;">No associations match these filters.</td></tr>`;

  const totalPages = Math.max(1, Math.ceil(count/DISEASE_PAGE_SIZE));
  const pag = document.getElementById("disease-pagination");
  pag.innerHTML = `
    <button ${page<=1?'disabled':''} onclick="goDiseasePage(1)" title="First page">«</button>
    <button ${page<=1?'disabled':''} onclick="goDiseasePage(${page-1})" title="Previous page">‹</button>
    <span class="pagination-status">
      Page <input type="number" id="disease-page-input" value="${page}" min="1" max="${totalPages}"> of ${totalPages}
    </span>
    <button ${page>=totalPages?'disabled':''} onclick="goDiseasePage(${page+1})" title="Next page">›</button>
    <button ${page>=totalPages?'disabled':''} onclick="goDiseasePage(${totalPages})" title="Last page">»</button>
  `;
  const pageInput = document.getElementById("disease-page-input");
  const jump = ()=>{
    let target = parseInt(pageInput.value, 10);
    if(isNaN(target)) target = page;
    target = Math.min(Math.max(target, 1), totalPages);
    if(target !== page) goDiseasePage(target);
  };
  pageInput.addEventListener("keydown", e=>{ if(e.key==="Enter") jump(); });
  pageInput.addEventListener("blur", jump);
}
function goDiseasePage(p){ diseaseState.page = p; loadDiseasePage(); }

function ensureDiseasesLoaded(){
  if(!currentDetailUniprot) return;
  loadDiseasePage();
}
document.getElementById("disease-search").addEventListener("input", e=>{
  diseaseState.query = e.target.value; diseaseState.page = 1; loadDiseasePage();
});
document.getElementById("disease-datatype-select").addEventListener("change", e=>{
  diseaseState.datatype = e.target.value; diseaseState.page = 1; loadDiseasePage();
});
document.getElementById("disease-min-score").addEventListener("input", e=>{
  diseaseState.minScore = parseInt(e.target.value,10);
  document.getElementById("disease-min-score-val").textContent = diseaseState.minScore + "%+";
  diseaseState.page = 1; loadDiseasePage();
});
document.getElementById("disease-sort-select").addEventListener("change", e=>{
  diseaseState.sort = e.target.value; diseaseState.page = 1; loadDiseasePage();
});

function buildVariantsPanel(p){
  const v = p.variant_stats;
  if(!v){
    return `<h3>Variant &amp; RNA-binding protein data</h3>
      <div class="empty-note">No matching entry for ${p.uniprot} in the variant/RBP reference set for this release.</div>`;
  }
  const rbdChips = v.rbd_names.length
    ? v.rbd_names.map(n=>`<span class="cond-tag">${n}</span>`).join("")
    : `<span style="color:var(--faint); font-size:12.5px;">None annotated</span>`;
  const diseaseChips = v.disease_names.length
    ? v.disease_names.map(n=>`<span class="cond-tag" style="background:var(--teal-soft); color:#13463D;">${n}</span>`).join("")
    : `<span style="color:var(--faint); font-size:12.5px;">None recorded</span>`;

  return `
    <h3>Variant &amp; RNA-binding protein data</h3>
    <div class="kv-list" style="margin-bottom:20px;">
      <div><span>Gene type</span><b>${v.gene_type}</b></div>
      <div><span>RNA-binding protein</span><b>${v.is_rbp ? "Yes" : "No"}</b></div>
      <div><span>Has annotated RBD</span><b>${v.has_rbd ? "Yes" : "No"}</b></div>
    </div>

    <div style="margin-bottom:20px;">
      <span style="display:block; font-size:11px; color:var(--faint); font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.04em; margin-bottom:8px;">RNA-binding domains</span>
      <div class="cond-tags" style="max-width:none;">${rbdChips}</div>
    </div>

    <span style="display:block; font-size:11px; color:var(--faint); font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.04em; margin-bottom:8px;">ClinVar-derived variant classification counts</span>
    <table class="results-table" style="margin-bottom:20px;">
      <thead><tr><th></th><th>Not in classical RBD</th><th>In classical RBD</th><th>Total</th></tr></thead>
      <tbody>
        <tr><td class="gene-sym" style="font-size:13px;">Pathogenic</td><td class="mono">${v.pathogenic_not_classical_rbd.toLocaleString()}</td><td class="mono">${v.pathogenic_in_classical_rbd.toLocaleString()}</td><td class="mono"><b>${v.total_pathogenic.toLocaleString()}</b></td></tr>
        <tr><td class="gene-sym" style="font-size:13px;">VUS</td><td class="mono">${v.vus_not_classical_rbd.toLocaleString()}</td><td class="mono">${v.vus_in_classical_rbd.toLocaleString()}</td><td class="mono"><b>${v.total_vus.toLocaleString()}</b></td></tr>
        <tr><td class="gene-sym" style="font-size:13px;">Benign</td><td class="mono">${v.benign_not_classical_rbd.toLocaleString()}</td><td class="mono">${v.benign_in_classical_rbd.toLocaleString()}</td><td class="mono"><b>${v.total_benign.toLocaleString()}</b></td></tr>
      </tbody>
    </table>
    <p class="subnote" style="margin-bottom:20px;">VUS = variant of uncertain significance. "Classical RBD" refers to canonical RNA-binding domains as annotated in the source reference set.</p>

    <span style="display:block; font-size:11px; color:var(--faint); font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.04em; margin-bottom:8px;">Known disease associations (named)</span>
    <div class="cond-tags" style="max-width:none;">${diseaseChips}</div>
  `;
}

function switchTab(name){
  document.querySelectorAll(".tabbar button").forEach(b=>b.classList.toggle("active", b.dataset.tab===name));
  document.querySelectorAll(".tab-content").forEach(c=>c.classList.toggle("active", c.id==="tab-"+name));
  if(name === "diseases") ensureDiseasesLoaded();
}
document.querySelectorAll(".tabbar button").forEach(b=>{
  b.addEventListener("click", ()=>switchTab(b.dataset.tab));
});

/* ============================================================
   BOOT
   ============================================================ */
loadData().then(()=>{
  populateCondensateSelect();
});