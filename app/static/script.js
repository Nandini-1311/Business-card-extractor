const dropzone   = document.getElementById('dropzone');
const fileInput  = document.getElementById('file-input');
const queueBox   = document.getElementById('queue');
const queueList  = document.getElementById('queue-list');
const queueProg  = document.getElementById('queue-progress');
const banner     = document.getElementById('banner');
const rolodex    = document.getElementById('rolodex');
const emptyState = document.getElementById('empty-state');
const tallyCount = document.getElementById('tally-count');
const search     = document.getElementById('search');

let allCards = [];

// ---- dropzone interactions ----

dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
});

['dragenter', 'dragover'].forEach(evt =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  })
);
['dragleave', 'drop'].forEach(evt =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
  })
);
dropzone.addEventListener('drop', (e) => {
  const files = [...e.dataTransfer.files].filter(f => f.type.startsWith('image/'));
  if (files.length) uploadBatch(files);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files.length) uploadBatch([...fileInput.files]);
  fileInput.value = '';
});

// ---- upload ----

async function uploadBatch(files) {
  showBanner(null);
  queueBox.hidden = false;
  queueList.innerHTML = '';
  queueProg.textContent = `0 / ${files.length}`;

  files.forEach(f => {
    const li = document.createElement('li');
    li.dataset.name = f.name;
    li.innerHTML = `<span>${escapeHtml(f.name)}</span><span class="qstatus">uploading…</span>`;
    queueList.appendChild(li);
  });

  const form = new FormData();
  files.forEach(f => form.append('files', f));

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: form });
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || 'Upload failed');

    const accepted = data.accepted || [];
    const rejected = data.rejected || [];

        queueList.querySelectorAll('li').forEach(li => {
      const name = li.dataset.name;
      const hit = accepted.find(c => c.original_filename === name)
                || rejected.find(c => c.original_filename === name);
      if (!hit) return;
      const label = li.querySelector('.qstatus');
      if (hit.status === 'extracted') {
        li.classList.add('ok');
        label.textContent = 'extracted';
      } else if (hit.status === 'uploaded') {
        li.classList.add('ok');
        label.textContent = 'stored';
      } else {
        li.classList.add('fail');
        label.textContent = hit.error || hit.status;
      }
    });
    queueProg.textContent = `${accepted.length} / ${files.length}`;

    const extracted = accepted.filter(c => c.status === 'extracted').length;
    const failed = accepted.filter(c => c.status === 'failed').length;

    if (rejected.length || failed) {
      const parts = [];
      if (extracted) parts.push(`${extracted} card(s) read and saved`);
      if (failed) parts.push(`${failed} could not be read (use Retry in the table below)`);
      if (rejected.length) parts.push(`${rejected.length} rejected, see the batch log above`);
      showBanner('warn', parts.join(', ') + '.');
    } else {
      showBanner('ok', extracted === accepted.length
        ? `${extracted} card(s) read and saved.`
        : `${accepted.length} card(s) stored.`);
    }

    await loadCards();
  } catch (err) {
    showBanner('warn', `Upload failed: ${err.message}`);
  }
}

function showBanner(type, text) {
  if (!type) { banner.hidden = true; return; }
  banner.hidden = false;
  banner.className = `banner ${type}`;
  banner.textContent = text;
}

// ---- gallery ----

async function loadCards() {
  const res = await fetch('/api/cards');
  const data = await res.json();
  allCards = data.cards || [];
  renderCards(allCards);
}

function renderCards(cards) {
  tallyCount.textContent = allCards.length;
  rolodex.innerHTML = '';
  emptyState.hidden = allCards.length !== 0;

  const template = document.getElementById('card-template');

  cards.forEach((card, i) => {
    const node = template.content.cloneNode(true);
    const article = node.querySelector('.rcard');
    const tilt = ((i * 37) % 7) - 3; // deterministic gentle scatter
    article.style.setProperty('--tilt', `${tilt}deg`);
    article.dataset.id = card.id;

    const img = node.querySelector('img');
    img.src = card.url;
    img.alt = card.original_filename;

    node.querySelector('.rcard-name').textContent = card.original_filename;

    const sizeKb = Math.round(card.size_bytes / 1024);
    const dotClass = card.status === 'extracted' ? 'dot-extracted'
                    : card.status === 'rejected' ? 'dot-rejected'
                    : 'dot-uploaded';
    const sub = node.querySelector('.rcard-sub');
    sub.innerHTML = `<span class="dot ${dotClass}"></span>${sizeKb} KB · ${card.status}`;

    node.querySelector('.rcard-remove').addEventListener('click', () => removeCard(card.id));

    rolodex.appendChild(node);
  });
}

async function removeCard(id) {
  const res = await fetch(`/api/cards/${id}`, { method: 'DELETE' });
  if (res.ok) {
    allCards = allCards.filter(c => c.id !== id);
    renderCards(filteredCards());
  }
}

function filteredCards() {
  const q = search.value.trim().toLowerCase();
  if (!q) return allCards;
  return allCards.filter(c => c.original_filename.toLowerCase().includes(q));
}

search.addEventListener('input', () => renderCards(filteredCards()));

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

loadCards();
