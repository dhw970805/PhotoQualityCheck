const API_BASE = `http://127.0.0.1:${window.FLASK_PORT || 5000}`;

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `API error ${res.status}`);
  }
  return data;
}

// --- REST API ---

export function loadPhotos(folderPath) {
  return request('/api/photos', {
    method: 'POST',
    body: JSON.stringify({ folder_path: folderPath }),
  });
}

export function startDetection(folderPath) {
  return request('/api/start', {
    method: 'POST',
    body: JSON.stringify({ folder_path: folderPath }),
  });
}

export function cancelDetection() {
  return request('/api/cancel', { method: 'POST' });
}

export function retryPhoto(fileName, folderPath) {
  return request(`/api/retry/${encodeURIComponent(fileName)}`, {
    method: 'POST',
    body: JSON.stringify({ folder_path: folderPath }),
  });
}

export function updateResult(fileName, folderPath, updates) {
  return request('/api/update-result', {
    method: 'POST',
    body: JSON.stringify({ folder_path: folderPath, file_name: fileName, updates }),
  });
}

export function exportPhotos(folderPath) {
  return request('/api/export', {
    method: 'POST',
    body: JSON.stringify({ folder_path: folderPath }),
  });
}

// --- URL builders ---

export function getThumbUrl(filePath) {
  return filePath ? `${API_BASE}/api/thumb/${encodeURIComponent(filePath)}` : '';
}

export function getImageUrl(filePath) {
  return filePath ? `${API_BASE}/api/image/${encodeURIComponent(filePath)}` : '';
}

/** Build a file:// URL for locally-generated thumbnails. */
export function buildFileThumbUrl(filePath) {
  if (!filePath) return '';
  const normalized = filePath.replace(/\\/g, '/');
  const lastSlash = normalized.lastIndexOf('/');
  const dir = normalized.substring(0, lastSlash);
  const file = normalized.substring(lastSlash + 1);
  return `file:///${dir}/.thumbnails/${file}.jpg`;
}

export function getWsUrl() {
  return `ws://127.0.0.1:${window.FLASK_PORT || 5000}`;
}
